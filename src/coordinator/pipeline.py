"""
实时语音转录流水线协调器

提供事件驱动的处理流水线，协调所有组件的工作流程
"""

import logging  # 日志记录
import threading  # 多线程支持
import time  # 时间相关操作
import signal  # 信号处理（用于优雅停止）
import sys  # 系统相关功能
from typing import Optional, List, Callable, Dict, Any  # 类型注解
from queue import Queue, Empty  # 线程安全队列和空队列异常
from dataclasses import dataclass  # 数据类装饰器
from enum import Enum  # 枚举类型
from contextlib import contextmanager  # 上下文管理器

# 导入系统配置和各功能模块
# 这些模块组成了完整的语音转录流水线
from src.config.models import Config, AudioConstants, VadConstants  # 系统主配置和常量
from src.hardware.gpu_detector import GPUDetector  # GPU硬件检测
from src.audio.capture import AudioCapture  # 音频捕获组件
from src.audio.models import AudioConfig, AudioChunk, AudioSourceType, AudioFormat  # 音频相关数据模型
from src.vad.detector import VoiceActivityDetector  # 语音活动检测器
from src.vad.models import VadConfig, VadResult, VadState, VadModel  # VAD相关数据模型
from src.transcription.engine import TranscriptionEngine  # 语音转录引擎
from src.transcription.models import TranscriptionConfig, TranscriptionResult, TranscriptionModel, LanguageCode, ProcessorType  # 转录相关数据模型
from src.output.handler import OutputHandler  # 输出处理器
from src.output.models import OutputConfig, OutputFormat, OutputLevel  # 输出相关数据模型


# 创建模块专用的日志记录器
logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """流水线状态枚举

    定义了流水线在生命周期中的各种状态
    状态转换: IDLE -> INITIALIZING -> RUNNING -> STOPPING -> IDLE
    异常情况下可能进入ERROR状态
    """
    IDLE = "idle"  # 空闲状态，未启动或已停止
    INITIALIZING = "initializing"  # 初始化中，正在加载各组件
    RUNNING = "running"  # 运行中，正在处理音频数据
    STOPPING = "stopping"  # 停止中，正在清理资源
    ERROR = "error"  # 错误状态，需要重新初始化


class EventType(Enum):
    """事件类型枚举

    定义了流水线中流转的各种事件类型
    事件流: AUDIO_DATA -> VAD_RESULT -> TRANSCRIPTION_RESULT
    """
    AUDIO_DATA = "audio_data"  # 音频数据事件，携带原始音频块
    VAD_RESULT = "vad_result"  # VAD检测结果事件，携带语音活动状态
    TRANSCRIPTION_RESULT = "transcription_result"  # 转录结果事件，携带识别文本
    ERROR = "error"  # 错误事件，携带错误信息
    STATE_CHANGE = "state_change"  # 状态变化事件，用于状态监控


@dataclass
class PipelineEvent:
    """流水线事件数据结构

    封装了事件的完整信息，包括类型、时间戳、数据内容等
    通过事件队列在各组件间传递，实现松耦合的架构
    """
    event_type: EventType  # 事件类型，决定处理方式
    timestamp: float  # 事件发生的时间戳，用于性能分析
    data: Any  # 事件携带的具体数据，类型由事件类型决定
    source: str  # 事件来源组件名称，用于调试和日志
    metadata: Dict[str, Any] = None  # 附加元数据，用于扩展信息

    def __post_init__(self):
        """初始化后处理，确保metadata不为None"""
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PipelineStatistics:
    """流水线统计信息

    记录流水线运行过程中的各种统计数据
    用于性能监控、问题诊断和系统优化
    """
    start_time: float = 0.0  # 流水线启动时间戳
    total_audio_chunks: int = 0  # 处理的音频块总数
    total_vad_detections: int = 0  # VAD检测的总次数
    total_transcriptions: int = 0  # 成功转录的总次数
    total_errors: int = 0  # 发生错误的总次数
    last_activity_time: float = 0.0  # 最后一次活动时间

    @property
    def uptime(self) -> float:
        """获取运行时间"""
        if self.start_time == 0.0:
            return 0.0
        return time.time() - self.start_time

    @property
    def audio_throughput(self) -> float:
        """计算音频处理吞吐量（块/秒）"""
        if self.uptime == 0.0:
            return 0.0
        return self.total_audio_chunks / self.uptime

    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity_time = time.time()


class TranscriptionPipeline:
    """
    实时语音转录流水线

    协调音频捕获、VAD检测、语音转录和输出处理等组件
    实现事件驱动的处理架构，支持实时处理和状态管理
    """

    def __init__(self, config: Config):
        """
        初始化流水线

        Args:
            config: 系统配置对象，包含所有运行参数
        """
        self.config = config  # 保存系统配置
        self.state = PipelineState.IDLE  # 初始状态为空闲
        self.statistics = PipelineStatistics()  # 初始化统计信息

        # 事件处理系统：基于队列的异步事件处理机制
        self.event_queue = Queue()  # 线程安全的事件队列
        self.event_handlers: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType  # 为每种事件类型初始化处理器列表
        }

        # 各功能组件实例，初始化时为None，在initialize()中创建
        self.gpu_detector: Optional[GPUDetector] = None  # GPU硬件检测器
        self.audio_capture: Optional[AudioCapture] = None  # 音频捕获组件
        self.vad_detector: Optional[VoiceActivityDetector] = None  # 语音活动检测器
        self.transcription_engine: Optional[TranscriptionEngine] = None  # 语音转录引擎
        self.output_handler: Optional[OutputHandler] = None  # 输出处理器

        # 线程管理：用于异步事件处理和生命周期控制
        self.event_thread: Optional[threading.Thread] = None  # 事件处理线程
        self.is_running = False  # 运行状态标志
        self.shutdown_event = threading.Event()  # 停止信号事件

        # 设置系统信号处理器，支持Ctrl+C等优雅停止
        self._setup_signal_handlers()

        # 错误处理回调函数列表
        self.error_callbacks: List[Callable[[Exception], None]] = []

        logger.info("TranscriptionPipeline initialized")

    def _setup_signal_handlers(self):
        """设置系统信号处理器以支持优雅停止

        当用户按Ctrl+C或系统发送终止信号时，能够优雅地停止流水线
        避免数据丢失和资源泄漏
        """
        def signal_handler(signum, frame):
            """信号处理函数，负责接收和处理系统信号"""
            logger.info(f"Received signal {signum}, stopping pipeline...")
            self.stop()  # 调用正常的停止流程

        # 注册信号处理器
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C 信号
        signal.signal(signal.SIGTERM, signal_handler)  # 终止信号

    def initialize(self) -> bool:
        """
        初始化所有组件

        Returns:
            bool: 初始化是否成功
        """
        try:
            self._change_state(PipelineState.INITIALIZING)
            logger.info("Initializing pipeline components...")

            # 1. 初始化GPU检测器：检测CUDA环境和显卡支持
            self.gpu_detector = GPUDetector()
            gpu_available = self.gpu_detector.detect_cuda()
            logger.info(f"GPU available: {gpu_available}")

            # 2. 初始化音频捕获：根据配置设置音频源和参数
            # 根据采样率动态选择正确的音频格式
            if self.config.sample_rate == AudioConstants.DEFAULT_SAMPLE_RATE:
                audio_format = AudioFormat.PCM_16_16000
            elif self.config.sample_rate == 44100:
                audio_format = AudioFormat.PCM_16_44100
            elif self.config.sample_rate == 48000:
                audio_format = AudioFormat.PCM_16_48000
            else:
                # 默认使用16kHz格式
                audio_format = AudioFormat.PCM_16_16000
                logger.warning(
                    f"不支持的采样率 {self.config.sample_rate}，"
                    f"使用默认的{AudioConstants.DEFAULT_SAMPLE_RATE}Hz"
                )

            audio_config = AudioConfig(
                # 根据配置选择音频源：麦克风或系统音频
                source_type=AudioSourceType.MICROPHONE if self.config.input_source == "microphone" else AudioSourceType.SYSTEM_AUDIO,
                sample_rate=self.config.sample_rate,  # 采样率，一般为16kHz
                chunk_size=self.config.chunk_size,    # 音频块大小，影响延迟
                device_index=self.config.device_id,   # 指定的音频设备ID
                channels=self.config.channels,        # 使用配置中的声道数
                format_type=audio_format               # 使用动态选择的音频格式
            )
            # 根据音频源类型选择相应的捕获器
            if self.config.input_source == "system":
                from src.audio.capture import SystemAudioCapture
                self.audio_capture = SystemAudioCapture(audio_config)
                logger.info(f"Using SystemAudioCapture with backend: {self.audio_capture.backend_type}")
            else:
                # 麦克风输入使用标准的AudioCapture
                self.audio_capture = AudioCapture(audio_config)
                logger.info("Using standard AudioCapture for microphone input")

            self.audio_capture.add_callback(self._on_audio_data)  # 注册音频数据回调

            # 3. 初始化VAD检测器：语音活动检测，过滤静音段
            # 将VAD窗口大小从秒转换为采样点数
            vad_window_samples = int(self.config.vad_window_size * self.config.sample_rate)

            vad_config = VadConfig(
                model=VadModel.SILERO,                                       # 使用Silero V5 VAD模型
                threshold=self.config.vad_threshold,                            # VAD敏感度阈值
                window_size_samples=vad_window_samples,                         # VAD检测窗口大小（采样点数）
                sample_rate=self.config.sample_rate,                            # 与音频采样率保持一致
                #min_speech_duration_ms=VadConstants.DEFAULT_SENSITIVITY * 500,  # 基于敏感度的语音持续时间
                #min_silence_duration_ms=VadConstants.DEFAULT_SENSITIVITY * 200, # 基于敏感度的静音持续时间
                return_confidence=True                                          # 返回置信度分数
            )
            self.vad_detector = VoiceActivityDetector(vad_config)
            self.vad_detector.add_callback(self._on_vad_result)  # 注册VAD结果回调

            # 4. 初始化转录引擎：使用sense-voice模型进行语音识别
            transcription_config = TranscriptionConfig(
                model=TranscriptionModel.SENSE_VOICE,  # 使用sense-voice模型
                model_path=self.config.model_path,     # 模型文件路径
                language=LanguageCode.AUTO,            # 自动语言检测
                # 根据GPU可用性选择处理器类型
                processor_type=ProcessorType.GPU if (self.config.use_gpu and gpu_available) else ProcessorType.CPU,
                sample_rate=self.config.sample_rate,   # 与音频采样率保持一致
                use_gpu=self.config.use_gpu and gpu_available  # GPU加速标志
            )
            self.transcription_engine = TranscriptionEngine(transcription_config)
            self.transcription_engine.add_callback(self._on_transcription_result)  # 注册转录结果回调

            # 5. 初始化输出处理器：格式化和显示转录结果
            output_config = OutputConfig(
                # 根据配置选择输出格式：JSON或控制台
                format=OutputFormat.JSON if self.config.output_format == "json" else OutputFormat.CONSOLE,
                show_confidence=self.config.show_confidence,  # 是否显示置信度分数
                show_timestamps=self.config.show_timestamp,   # 是否显示时间戳
                real_time_update=True,                        # 实时更新显示
                output_level=OutputLevel.NORMAL               # 输出详细级别
            )
            # 创建输出处理器，传递字幕显示配置
            self.output_handler = OutputHandler(
                output_config,
                subtitle_display_config=getattr(self.config, 'subtitle_display', None)
            )

            logger.info("All pipeline components initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            self._change_state(PipelineState.ERROR)
            self._emit_event(EventType.ERROR, str(e), "pipeline_init")
            return False

    def start(self) -> bool:
        """
        启动流水线

        Returns:
            bool: 启动是否成功
        """
        if self.state == PipelineState.RUNNING:
            logger.warning("Pipeline is already running")
            return True

        if not self.initialize():
            return False

        try:
            logger.info("Starting transcription pipeline...")
            self.is_running = True
            self.shutdown_event.clear()
            self.statistics.start_time = time.time()

            # 启动事件处理线程
            self.event_thread = threading.Thread(target=self._event_loop, daemon=True)
            self.event_thread.start()

            # 启动组件
            self.output_handler.start()
            self.audio_capture.start()

            self._change_state(PipelineState.RUNNING)
            logger.info("Pipeline started successfully")

            return True

        except Exception as e:
            logger.error(f"Failed to start pipeline: {e}")
            self._change_state(PipelineState.ERROR)
            self._emit_event(EventType.ERROR, str(e), "pipeline_start")
            return False

    def stop(self) -> None:
        """停止流水线"""
        if self.state == PipelineState.IDLE:
            logger.info("Pipeline is already stopped")
            return

        logger.info("Stopping transcription pipeline...")
        self._change_state(PipelineState.STOPPING)

        try:
            # 停止接收新数据
            self.is_running = False
            self.shutdown_event.set()

            # 停止组件
            if self.audio_capture:
                self.audio_capture.stop()

            if self.output_handler:
                self.output_handler.stop()

            # 等待事件处理线程结束
            if self.event_thread and self.event_thread.is_alive():
                self.event_thread.join(timeout=2.0)

            self._change_state(PipelineState.IDLE)
            logger.info("Pipeline stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping pipeline: {e}")
            self._change_state(PipelineState.ERROR)

    def run(self) -> None:
        """运行流水线直到停止"""
        if not self.start():
            logger.error("Failed to start pipeline")
            return

        try:
            logger.info("Pipeline running. Press Ctrl+C to stop...")

            # 主循环
            while self.is_running and not self.shutdown_event.is_set():
                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.stop()

    def _event_loop(self) -> None:
        """事件处理循环"""
        logger.info("Event processing loop started")

        while self.is_running and not self.shutdown_event.is_set():
            try:
                # 获取事件（超时避免阻塞）
                event = self.event_queue.get(timeout=0.1)
                self._process_event(event)
                self.event_queue.task_done()

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in event loop: {e}")

        logger.info("Event processing loop stopped")

    def _process_event(self, event: PipelineEvent) -> None:
        """
        处理单个事件

        Args:
            event: 要处理的事件
        """
        try:
            # 更新统计
            self.statistics.update_activity()

            # 调用注册的事件处理器
            for handler in self.event_handlers.get(event.event_type, []):
                handler(event)

            # 内置事件处理逻辑
            if event.event_type == EventType.AUDIO_DATA:
                self._handle_audio_data(event)
            elif event.event_type == EventType.VAD_RESULT:
                self._handle_vad_result(event)
            elif event.event_type == EventType.TRANSCRIPTION_RESULT:
                self._handle_transcription_result(event)
            elif event.event_type == EventType.ERROR:
                self._handle_error_event(event)

        except Exception as e:
            logger.error(f"Error processing event {event.event_type}: {e}")

    def _handle_audio_data(self, event: PipelineEvent) -> None:
        """处理音频数据事件"""
        if self.vad_detector and isinstance(event.data, AudioChunk):
            self.statistics.total_audio_chunks += 1
            self.vad_detector.process_audio(event.data.data)

    def _handle_vad_result(self, event: PipelineEvent) -> None:
        """处理VAD检测结果事件 - 增强版转录触发逻辑"""
        if self.transcription_engine and isinstance(event.data, VadResult):
            self.statistics.total_vad_detections += 1

            # 增强版调试日志，包含更多详细信息
            vad_result = event.data
            logger.debug(
                f"VAD结果: state={vad_result.state.name}, is_speech={vad_result.is_speech}, "
                f"has_audio_data={vad_result.audio_data is not None}, "
                f"confidence={vad_result.confidence:.3f}, "
                f"timestamp={vad_result.timestamp:.3f}, "
                f"duration_ms={vad_result.duration_ms:.1f}"
            )

            # 修复：增强转录触发条件验证
            speech_states = [VadState.SPEECH, VadState.TRANSITION_TO_SPEECH]
            has_valid_audio = (
                vad_result.audio_data is not None and
                len(vad_result.audio_data) > 0
            )

            # 新增：置信度检查，避免低质量语音的转录 - 降低阈值提高响应性
            confidence_threshold = 0.1  # 降低最低置信度阈值
            has_sufficient_confidence = vad_result.confidence >= confidence_threshold

            # 新增：音频质量检查 - 降低阈值提高响应性
            min_audio_samples = 32   # 降低最小音频样本数（约2ms @ 16kHz）
            has_sufficient_audio = has_valid_audio and len(vad_result.audio_data) >= min_audio_samples

            should_transcribe = (
                vad_result.is_speech and
                vad_result.state in speech_states and
                has_sufficient_audio and
                has_sufficient_confidence
            )

            if should_transcribe:

                logger.info(
                    f"触发转录: state={vad_result.state.name}, "
                    f"音频数据长度={len(vad_result.audio_data)}, "
                    f"置信度={vad_result.confidence:.3f}, "
                    f"持续时间={vad_result.duration_ms:.1f}ms"
                )
                try:
                    self.transcription_engine.transcribe_audio(vad_result.audio_data)
                    # 更新成功统计
                    self.statistics.update_activity()
                except Exception as e:
                    logger.error(f"转录处理失败: {e}")
                    self._emit_event(EventType.ERROR, str(e), "transcription_trigger")
            else:
                # 增强的调试信息，帮助排查问题
                skip_reasons = []
                if not vad_result.is_speech:
                    skip_reasons.append("no_speech")
                if vad_result.state not in speech_states:
                    skip_reasons.append(f"wrong_state({vad_result.state.name})")
                if not has_sufficient_audio:
                    audio_len = len(vad_result.audio_data) if vad_result.audio_data is not None else 0
                    skip_reasons.append(f"insufficient_audio({audio_len}<{min_audio_samples})")
                if not has_sufficient_confidence:
                    skip_reasons.append(f"low_confidence({vad_result.confidence:.3f}<{confidence_threshold})")

                # logger.debug(
                #     f"未触发转录: {', '.join(skip_reasons)}, "
                #     f"state={vad_result.state.name}"
                # )

    def _handle_transcription_result(self, event: PipelineEvent) -> None:
        """处理转录结果事件"""
        if self.output_handler and isinstance(event.data, TranscriptionResult):
            self.statistics.total_transcriptions += 1
            self.output_handler.process_result(event.data)

    def _handle_error_event(self, event: PipelineEvent) -> None:
        """处理错误事件"""
        self.statistics.total_errors += 1
        error_msg = event.data if isinstance(event.data, str) else str(event.data)
        logger.error(f"Pipeline error from {event.source}: {error_msg}")

        # 调用错误回调
        for callback in self.error_callbacks:
            try:
                callback(Exception(error_msg))
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

    def _on_audio_data(self, audio_chunk: AudioChunk) -> None:
        """音频数据回调"""
        self._emit_event(EventType.AUDIO_DATA, audio_chunk, "audio_capture")

    def _on_vad_result(self, vad_result: VadResult) -> None:
        """VAD检测结果回调函数

        由VAD检测器调用，将VAD检测结果包装为事件发送到事件队列
        """
        self._emit_event(EventType.VAD_RESULT, vad_result, "vad_detector")

    def _on_transcription_result(self, transcription_result: TranscriptionResult) -> None:
        """转录结果回调函数

        由转录引擎调用，将转录结果包装为事件发送到事件队列
        """
        self._emit_event(EventType.TRANSCRIPTION_RESULT, transcription_result, "transcription_engine")

    def _emit_event(self, event_type: EventType, data: Any, source: str, metadata: Dict[str, Any] = None) -> None:
        """
        发射事件到事件队列

        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件源
            metadata: 额外的元数据
        """
        event = PipelineEvent(
            event_type=event_type,
            timestamp=time.time(),
            data=data,
            source=source,
            metadata=metadata or {}
        )

        try:
            self.event_queue.put_nowait(event)
        except Exception as e:
            logger.error(f"Failed to emit event {event_type}: {e}")

    def _change_state(self, new_state: PipelineState) -> None:
        """
        改变流水线状态

        Args:
            new_state: 新状态
        """
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.info(f"Pipeline state changed: {old_state.value} -> {new_state.value}")
            self._emit_event(EventType.STATE_CHANGE, {"old": old_state.value, "new": new_state.value}, "pipeline")

    def add_event_handler(self, event_type: EventType, handler: Callable[[PipelineEvent], None]) -> None:
        """
        添加事件处理器

        Args:
            event_type: 事件类型
            handler: 处理器函数
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def remove_event_handler(self, event_type: EventType, handler: Callable[[PipelineEvent], None]) -> None:
        """
        移除事件处理器

        Args:
            event_type: 事件类型
            handler: 处理器函数
        """
        if event_type in self.event_handlers and handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)

    def add_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """
        添加错误回调

        Args:
            callback: 错误处理回调函数
        """
        self.error_callbacks.append(callback)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取流水线统计信息

        Returns:
            Dict: 统计信息字典
        """
        return {
            # 基础统计
            "state": self.state.value,
            "uptime": self.statistics.uptime,
            "total_audio_chunks": self.statistics.total_audio_chunks,
            "total_vad_detections": self.statistics.total_vad_detections,
            "total_transcriptions": self.statistics.total_transcriptions,
            "total_errors": self.statistics.total_errors,
            "audio_throughput": self.statistics.audio_throughput,
            "last_activity": self.statistics.last_activity_time,
            "event_queue_size": self.event_queue.qsize() if hasattr(self.event_queue, 'qsize') else 0
        }

    def get_status(self) -> Dict[str, Any]:
        """
        获取流水线状态信息 - 增强版包含组件状态和配置信息

        Returns:
            Dict: 状态信息字典
        """
        status = {
            "state": self.state.value,
            "is_running": self.is_running,
            "components": {},
            "configuration": {}
        }

        # 组件状态
        if self.audio_capture:
            status["components"]["audio_capture"] = "initialized"
        if self.vad_detector:
            status["components"]["vad_detector"] = "initialized"
            # 添加VAD配置信息
            if hasattr(self.vad_detector, '_detector') and hasattr(self.vad_detector._detector, 'config'):
                vad_config = self.vad_detector._detector.config
                status["configuration"]["vad"] = vad_config.get_responsiveness_config()
        if self.transcription_engine:
            status["components"]["transcription_engine"] = "initialized"
        if self.output_handler:
            status["components"]["output_handler"] = "initialized"

        return status

    @contextmanager
    def pipeline_context(self):
        """流水线上下文管理器

        提供一个替代的上下文管理方式，可以使用with语句管理流水线生命周期
        自动处理启动和停止，确保资源正确清理
        """
        try:
            if not self.start():
                raise RuntimeError("Failed to start pipeline")
            yield self  # 返回流水线实例供使用
        finally:
            self.stop()  # 确保在任何情况下都会停止流水线

    def __enter__(self):
        """上下文管理器入口

        实现Python的with语句支持，在进入with块时自动启动流水线
        """
        if not self.start():
            raise RuntimeError("Failed to start pipeline")
        return self  # 返回自身供使用

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出

        在退出with块时自动停止流水线，无论是正常退出还是发生异常
        """
        self.stop()  # 确保流水线停止，清理资源