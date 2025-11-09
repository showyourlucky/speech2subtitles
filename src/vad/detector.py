"""
基于Silero VAD的语音活动检测实现 (Voice Activity Detection Implementation)

提供可配置敏感度的实时语音检测功能
使用Silero VAD模型进行高性能的语音/静音判断
支持流式处理和回调机制
"""

import logging
import time
import threading
from typing import List, Optional, Callable, Iterator, Dict, Any
from collections import deque
import numpy as np

# 检查PyTorch依赖可用性
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

# 检查Silero VAD依赖可用性
try:
    import silero_vad
    SILERO_AVAILABLE = True
except ImportError:
    SILERO_AVAILABLE = False
    silero_vad = None

# 检查sherpa-onnx依赖可用性
try:
    import sherpa_onnx
    SHERPA_ONNX_AVAILABLE = True
except ImportError:
    SHERPA_ONNX_AVAILABLE = False
    sherpa_onnx = None

from .models import (
    VadConfig, VadResult, VadState, VadModel, SpeechSegment,
    VadStatistics, VadError, ModelLoadError, DetectionError,
    ConfigurationError
)
import os


logger = logging.getLogger(__name__)


class VadModelFactory:
    """
    VAD模型工厂类 - 基于sherpa-onnx框架

    负责根据配置创建合适的VAD检测器实例，支持多种模型类型
    提供模型自动下载和缓存功能
    """

    @staticmethod
    def create_vad_detector(config: VadConfig):
        """
        根据配置创建VAD检测器

        Args:
            config: VAD配置对象

        Returns:
            VAD检测器实例 (SherpaOnnxVAD 或 LegacyTorchVAD)

        Raises:
            ConfigurationError: 当配置无效或依赖缺失时
        """
        if config.use_sherpa_onnx:
            if not SHERPA_ONNX_AVAILABLE:
                logger.warning("sherpa-onnx不可用，回退到传统torch.hub方式")
                # 自动降级到兼容模式
                config.use_sherpa_onnx = False
                return LegacyTorchVAD(config)

            # 尝试创建sherpa-onnx实现
            try:
                return SherpaOnnxVAD(config)
            except ModelLoadError as e:
                logger.warning(f"sherpa-onnx模型加载失败，降级到legacy模式: {e}")
                # 降级到legacy模式
                config.use_sherpa_onnx = False
                return LegacyTorchVAD(config)
        else:
            # 向后兼容：使用原有torch.hub方式
            return LegacyTorchVAD(config)

    @staticmethod
    def verify_download_url(url: str) -> bool:
        """
        验证下载URL的有效性

        Args:
            url: 要验证的URL

        Returns:
            bool: URL是否有效
        """
        try:
            import urllib.request
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"URL验证失败: {url}, 错误: {e}")
            return False

    @staticmethod
    def download_model(model_type: VadModel, target_path: str) -> bool:
        """
        自动下载模型文件

        Args:
            model_type: VAD模型类型
            target_path: 目标文件路径

        Returns:
            bool: 下载是否成功
        """
        # 模型下载URL映射
        download_urls = {
            VadModel.SILERO: "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad_v5.onnx",
            VadModel.TEN_VAD: "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/ten-vad.onnx"
        }

        if model_type not in download_urls:
            logger.error(f"不支持的模型类型: {model_type}")
            return False

        url = download_urls[model_type]

        # 验证URL有效性
        if not VadModelFactory.verify_download_url(url):
            logger.error(f"模型下载URL无效: {url}")
            return False

        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # 下载模型
            import urllib.request
            urllib.request.urlretrieve(url, target_path)
            logger.info(f"模型下载成功 (备用方式): {target_path}")
            return True

        except Exception as e:
            logger.error(f"模型下载失败: {e}")
            return False

    @staticmethod
    def ensure_model_exists(config: VadConfig) -> bool:
        """
        确保模型文件存在，如不存在则自动下载

        Args:
            config: VAD配置对象

        Returns:
            bool: 模型文件是否可用
        """
        model_path = config.effective_model_path

        if os.path.exists(model_path):
            return True

        logger.info(f"模型文件不存在，开始下载: {model_path}")
        return VadModelFactory.download_model(config.model, model_path)


class SherpaOnnxVAD:
    """
    基于sherpa-onnx的VAD检测器实现

    使用sherpa-onnx框架进行VAD检测，支持silero-vad和ten-vad模型
    提供与原VoiceActivityDetector相同的接口
    """

    def __init__(self, config: VadConfig):
        """
        初始化sherpa-onnx VAD检测器

        Args:
            config: VAD配置对象

        Raises:
            ModelLoadError: 模型加载失败时抛出
        """
        self.config = config
        self._vad_model = None
        self._current_state = VadState.SILENCE
        self._state_duration = 0
        self._current_segment: Optional[SpeechSegment] = None
        self._completed_segments: List[SpeechSegment] = []
        self._statistics = VadStatistics()
        self._callbacks: List[Callable[[VadResult], None]] = []
        self._callback_lock = threading.Lock()

        # 音频缓冲区
        self._audio_buffer = deque(maxlen=self.config.sample_rate * 3)
        self._buffer_lock = threading.Lock()

        self._load_model()
        logger.info(f"sherpa-onnx VAD检测器初始化完成: {config.model.value}")

    def _load_model(self) -> None:
        """
        加载sherpa-onnx VAD模型

        Raises:
            ModelLoadError: 模型加载失败时抛出
        """
        try:
            if not SHERPA_ONNX_AVAILABLE:
                raise ModelLoadError("sherpa-onnx库未安装，请运行: pip install sherpa-onnx")

            # 确保模型文件存在
            if not VadModelFactory.ensure_model_exists(self.config):
                raise ModelLoadError(f"无法获取模型文件: {self.config.effective_model_path}")

            model_path = self.config.effective_model_path

            # 创建sherpa-onnx VAD配置
            vad_config = sherpa_onnx.VadModelConfig()

            # 根据模型类型配置
            if self.config.model == VadModel.SILERO:
                # Silero VAD配置
                self._configure_silero_vad(vad_config, model_path)
            elif self.config.model == VadModel.TEN_VAD:
                # Ten VAD配置
                self._configure_ten_vad(vad_config, model_path)

            vad_config.sample_rate = self.config.sample_rate
            vad_config.num_threads = 1
            vad_config.provider = "cpu"

            # 创建VAD模型实例
            self._vad_model = sherpa_onnx.VoiceActivityDetector(vad_config)

            logger.info(f"sherpa-onnx VAD模型加载成功: {self.config.model.value}")

        except Exception as e:
            # 不再抛出异常，而是让工厂类处理降级
            raise ModelLoadError(f"sherpa-onnx VAD模型加载失败: {e}")

    def _configure_silero_vad(self, vad_config, model_path: str) -> None:
        """
        配置Silero VAD模型

        Args:
            vad_config: sherpa-onnx VAD配置对象
            model_path: 模型文件路径
        """
        vad_config.silero_vad.model = model_path
        vad_config.silero_vad.threshold = self.config.threshold
        vad_config.silero_vad.min_silence_duration = self.config.min_silence_duration_ms / 1000.0
        vad_config.silero_vad.min_speech_duration = self.config.min_speech_duration_ms / 1000.0
        logger.info(f"配置Silero vad_config: threshold={self.config.threshold}, min_silence_duration={self.config.min_silence_duration_ms}ms, min_speech_duration={self.config.min_speech_duration_ms}ms")
        # 检查是否支持最大语音持续时间配置
        if hasattr(vad_config.silero_vad, 'max_speech_duration'):
            vad_config.silero_vad.max_speech_duration = self.config.max_speech_duration_ms / 1000.0
            logger.info(f"配置Silero VAD: max_speech_duration={self.config.max_speech_duration_ms}ms")

    def _configure_ten_vad(self, vad_config, model_path: str) -> None:
        """
        配置Ten VAD模型

        Args:
            vad_config: sherpa-onnx VAD配置对象
            model_path: 模型文件路径

        Raises:
            ModelLoadError: 当sherpa-onnx不支持Ten VAD时
        """
        try:
            # 检查sherpa-onnx是否支持Ten VAD
            if hasattr(vad_config, 'ten_vad'):
                # 使用FSMN VAD配置（Ten VAD基于FSMN）
                vad_config.ten_vad.model = model_path
                vad_config.ten_vad.threshold = self.config.threshold
                vad_config.ten_vad.min_silence_duration = self.config.min_silence_duration_ms / 1000.0
                vad_config.ten_vad.min_speech_duration = self.config.min_speech_duration_ms / 1000.0
                logger.info(f"配置Ten vad_config: threshold={self.config.threshold}, min_silence_duration={self.config.min_silence_duration_ms}ms, min_speech_duration={self.config.min_speech_duration_ms}ms")

                # 检查是否支持最大语音持续时间配置
                if hasattr(vad_config.ten_vad, 'max_speech_duration'):
                    vad_config.ten_vad.max_speech_duration = self.config.max_speech_duration_ms / 1000.0
                    logger.info(f"配置Ten VAD (FSMN):  max_speech_duration={self.config.max_speech_duration_ms}ms")
            else:
                # 降级到使用Silero配置加载Ten VAD模型
                logger.warning("sherpa-onnx当前版本不支持专门的Ten VAD配置，使用Silero配置加载, 模型路径可能错误")
                vad_config.silero_vad.model = model_path
                vad_config.silero_vad.threshold = self.config.threshold
                vad_config.silero_vad.min_silence_duration = self.config.min_silence_duration_ms / 1000.0
                vad_config.silero_vad.min_speech_duration = self.config.min_speech_duration_ms / 1000.0
                # 检查是否支持最大语音持续时间配置
                if hasattr(vad_config.silero_vad, 'max_speech_duration'):
                    vad_config.silero_vad.max_speech_duration = self.config.max_speech_duration_ms / 1000.0
                    logger.info(f"配置Ten VAD (兼容模式): threshold={self.config.threshold}, max_speech_duration={self.config.max_speech_duration_ms}ms")
        except Exception as e:
            raise ModelLoadError(f"Ten VAD配置失败: {e}")

    def detect(self, audio_data: np.ndarray) -> VadResult:
        """
        使用sherpa-onnx进行VAD检测

        Args:
            audio_data: 音频数据 (16kHz, 单声道)

        Returns:
            VadResult: 检测结果

        Raises:
            DetectionError: 检测过程出错时抛出
        """
        start_time = time.time()

        try:
            # 音频数据预处理
            if audio_data.dtype == np.int16:
                audio_float = audio_data.astype(np.float32) / 32768.0
            else:
                audio_float = audio_data.astype(np.float32)

            # 确保音频数据在正确的范围内
            audio_float = np.clip(audio_float, -1.0, 1.0)

            # 将音频数据添加到缓冲区以备语音开始时使用
            with self._buffer_lock:
                self._audio_buffer.extend(audio_float)

            # 使用sherpa-onnx进行VAD检测
            # 向VAD模型输入音频数据
            self._vad_model.accept_waveform(audio_float)

            # 检查是否有新的语音段被检测到
            is_speech = False
            confidence = self.config.threshold
            real_data = None
            if not self._vad_model.empty():
                # 获取检测结果
                segment = self._vad_model.front
                # 判断是否为语音段
                is_speech = len(segment.samples) > 0
                real_data = self._vad_model.front.samples
                self._vad_model.pop()  # 移除已处理的段
                # 尝试获取更准确的置信度
                confidence = self._get_confidence_score(is_speech)

            # 更新状态机，传递音频数据用于语音段包含
            result = self._update_state(is_speech, confidence, len(audio_data), audio_float)

            # 更新统计信息
            duration_ms = (len(audio_data) / self.config.sample_rate) * 1000
            self._statistics.update_audio_duration(duration_ms)

            if is_speech:
                self._statistics.update_speech_duration(duration_ms)
                result.audio_data = real_data
            else:
                self._statistics.update_silence_duration(duration_ms)

            processing_time = (time.time() - start_time) * 1000
            self._statistics.update_processing_time(processing_time)

            # 调用回调函数
            self._call_callbacks(result)

            return result

        except Exception as e:
            raise DetectionError(f"sherpa-onnx VAD检测失败: {e}")

    def _get_confidence_score(self, is_speech: bool) -> float:
        """
        获取置信度分数

        Args:
            is_speech: 是否检测到语音

        Returns:
            float: 置信度分数
        """

        # 回退到基于阈值的估算
        base_score = self.config.threshold
        if is_speech:
            return min(1.0, base_score + 0.15)  # 略高于阈值
        else:
            return max(0.0, base_score - 0.15)  # 略低于阈值

    def _update_state(self, is_speech: bool, confidence: float, samples: int, audio_data: np.ndarray = None) -> VadResult:
        """更新VAD状态机 - 增强版使用自适应阈值"""
        timestamp = time.time()
        duration_ms = (samples / self.config.sample_rate) * 1000

        # 更新状态持续时间
        self._state_duration += samples

        # 确定新状态
        new_state = self._current_state
        speech_start_time = None
        speech_end_time = None

        if is_speech:
            if self._current_state == VadState.SILENCE:
                # 转换到语音状态
                if self._state_duration >= self.config.min_speech_samples:
                    new_state = VadState.TRANSITION_TO_SPEECH
                    speech_start_time = timestamp
                    self._start_speech_segment(timestamp, confidence)
                    self._state_duration = 0
                    logger.debug(
                        f"转换到语音状态: 持续时间={self._state_duration}采样点, "
                    )
            elif self._current_state == VadState.TRANSITION_TO_SPEECH:
                # 继续语音状态
                new_state = VadState.SPEECH
                if self._current_segment:
                    self._current_segment.add_confidence_score(confidence)
            elif self._current_state == VadState.SPEECH:
                # 保持语音状态，但检查是否超过最大语音持续时间
                if self._current_segment:
                    self._current_segment.add_confidence_score(confidence)
                    # 检查当前语音段是否超过最大持续时间
                    current_duration_samples = int((timestamp - self._current_segment.start_time) * self.config.sample_rate)
                    if current_duration_samples >= self.config.max_speech_samples:
                        # 自动分段：结束当前语音段并立即开始新的语音段
                        self._end_speech_segment(timestamp)
                        self._start_speech_segment(timestamp, confidence)
                        logger.debug(f"语音段超过最大持续时间 ({self.config.max_speech_duration_ms}ms)，自动分段")
        else:
            if self._current_state in [VadState.SPEECH, VadState.TRANSITION_TO_SPEECH]:
                # 转换到静音状态
                if self._state_duration >= self.config.min_silence_samples:
                    new_state = VadState.TRANSITION_TO_SILENCE
                    speech_end_time = timestamp
                    self._end_speech_segment(timestamp)
                    self._state_duration = 0
                    logger.debug(
                        f"转换到静音状态: 持续时间={self._state_duration}采样点, "
                    )
            elif self._current_state == VadState.TRANSITION_TO_SILENCE:
                # 继续静音状态
                new_state = VadState.SILENCE

        # 更新当前状态
        if new_state != self._current_state:
            old_state = self._current_state
            self._current_state = new_state
            self._state_duration = 0
            logger.debug(f"VAD状态变化: {old_state.name} -> {new_state.name}")

        # 修复：扩展音频数据包含条件，包括过渡状态
        # 在语音活动期间（包括过渡状态）都包含音频数据
        speech_activity_states = [VadState.SPEECH, VadState.TRANSITION_TO_SPEECH]
        include_audio = is_speech and new_state in speech_activity_states

        # 新增：在语音开始时，包含缓冲区中的历史音频
        result_audio_data = None
        if include_audio:
            if new_state == VadState.TRANSITION_TO_SPEECH and speech_start_time is not None:
                # 语音开始：包含缓冲区中的历史音频 + 当前音频
                with self._buffer_lock:
                    buffer_audio = np.array(list(self._audio_buffer), dtype=np.float32)
                if len(buffer_audio) > 0:
                    # 只取最近的一秒音频作为前置缓冲
                    max_buffer_samples = self.config.sample_rate * 2 # 1秒
                    if len(buffer_audio) > max_buffer_samples:
                        buffer_audio = buffer_audio[-max_buffer_samples:]
                    result_audio_data = buffer_audio
                    logger.debug(f"语音开始：包含缓冲音频 {len(buffer_audio)} 采样点")
                else:
                    result_audio_data = audio_data
            else:
                # 正常语音状态：只包含当前音频
                result_audio_data = audio_data

        result = VadResult(
            is_speech=is_speech,
            confidence=confidence,
            timestamp=timestamp,
            duration_ms=duration_ms,
            state=new_state,
            audio_data=result_audio_data,
            speech_start_time=speech_start_time,
            speech_end_time=speech_end_time
        )

        # 增强的调试信息，包含自适应阈值信息
        if include_audio:
            logger.debug(
                f"[SherpaOnnx] VAD输出包含音频数据: 状态={new_state.name}, "
                f"音频长度={len(audio_data)}, 置信度={confidence:.3f}, "
            )
        # else:
            # logger.debug(
            #     f"[SherpaOnnx] VAD输出不包含音频数据: is_speech={is_speech}, "
            #     f"state={new_state.name}, 置信度={confidence:.3f}, "
            # )

        return result

    def _start_speech_segment(self, timestamp: float, confidence: float) -> None:
        """开始新的语音段"""
        self._current_segment = SpeechSegment(
            start_time=timestamp,
            end_time=None,
            confidence_scores=[confidence]
        )
        logger.debug(f"Started speech segment at {timestamp:.3f}")

    def _end_speech_segment(self, timestamp: float) -> None:
        """结束当前语音段"""
        if self._current_segment:
            self._current_segment.finalize(timestamp)
            self._completed_segments.append(self._current_segment)
            self._statistics.increment_speech_segments()

            logger.debug(f"Ended speech segment: {self._current_segment.duration_ms:.1f}ms, "
                        f"confidence: {self._current_segment.average_confidence:.3f}")

            self._current_segment = None

    def add_callback(self, callback: Callable[[VadResult], None]) -> None:
        """添加VAD结果回调"""
        with self._callback_lock:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[VadResult], None]) -> None:
        """移除VAD结果回调"""
        with self._callback_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _call_callbacks(self, result: VadResult) -> None:
        """调用所有注册的回调函数"""
        with self._callback_lock:
            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Error in VAD callback {callback.__name__}: {e}")

    def get_completed_segments(self) -> List[SpeechSegment]:
        """获取已完成的语音段列表"""
        return self._completed_segments.copy()

    def clear_segments(self) -> None:
        """清空已完成的语音段"""
        self._completed_segments.clear()

    def get_statistics(self) -> VadStatistics:
        """获取VAD处理统计信息"""
        return self._statistics

    def reset_statistics(self) -> None:
        """重置VAD统计信息"""
        self._statistics = VadStatistics()

    def reset_state(self) -> None:
        """重置VAD状态"""
        self._current_state = VadState.SILENCE
        self._state_duration = 0
        if self._current_segment:
            # 强制结束当前语音段
            self._end_speech_segment(time.time())
        self._audio_buffer.clear()

    @property
    def is_speech_active(self) -> bool:
        """检查是否有语音活动"""
        return self._current_state in [VadState.SPEECH, VadState.TRANSITION_TO_SPEECH]

    @property
    def current_state(self) -> VadState:
        """获取当前VAD状态"""
        return self._current_state

    @property
    def current_segment(self) -> Optional[SpeechSegment]:
        """获取当前语音段（如果活跃）"""
        return self._current_segment


class LegacyTorchVAD:
    """
    传统的torch.hub VAD实现

    保持与原VoiceActivityDetector完全相同的实现
    用于向后兼容和sherpa-onnx不可用时的降级选项
    """

    def __init__(self, config: VadConfig):
        """初始化传统VAD检测器（完全复制原实现）"""
        # 检查必需的依赖是否可用
        if not TORCH_AVAILABLE:
            raise ConfigurationError("PyTorch不可用，请使用以下命令安装: pip install torch")

        self.config = config
        self._model = None
        self._current_state = VadState.SILENCE
        self._state_duration = 0
        self._current_segment: Optional[SpeechSegment] = None
        self._completed_segments: List[SpeechSegment] = []
        self._statistics = VadStatistics()
        self._callbacks: List[Callable[[VadResult], None]] = []
        self._callback_lock = threading.Lock()

        # 音频缓冲区
        self._audio_buffer = deque(maxlen=self.config.sample_rate * 2)
        self._buffer_lock = threading.Lock()

        # 验证配置有效性
        if not self.config.validate():
            raise ConfigurationError("VAD配置无效，请检查参数设置")

        # 加载VAD模型
        self._load_model()
        logger.info(f"Legacy VAD检测器初始化完成，配置: {config}")

    def _load_model(self) -> None:
        """加载Silero VAD模型（复制原实现）"""
        try:
            # 根据配置确定模型名称
            if self.config.model == VadModel.SILERO:
                model_name = 'silero_vad'
           
            # 从torch.hub加载Silero VAD模型和工具函数
            self._model, utils = torch.hub.load(
                repo_or_dir='models/silero-vad/',
                model=model_name,
                force_reload=False,
                onnx=False
            )

            # 提取工具函数
            self._get_speech_timestamps = utils[0]
            self._save_audio = utils[1]
            self._read_audio = utils[2]
            self._VADIterator = utils[3]
            self._collect_chunks = utils[4]

            # 设置模型为评估模式
            self._model.eval()

            # 创建VAD流式迭代器
            self._vad_iterator = self._VADIterator(
                model=self._model,
                threshold=self.config.threshold,
                sampling_rate=self.config.sample_rate,
                min_silence_duration_ms=int(self.config.min_silence_duration_ms),
                speech_pad_ms=int(self.config.min_speech_duration_ms)
            )

            logger.info(f"Silero VAD模型加载成功: {model_name}")

        except Exception as e:
            raise ModelLoadError(f"VAD模型加载失败: {e}")

    # 复制所有原VoiceActivityDetector的方法 - 增强版使用自适应阈值
    def detect(self, audio_data: np.ndarray) -> VadResult:
        """对音频数据进行语音活动检测 - 增强版使用自适应阈值"""
        start_time = time.time()

        try:
            # 音频数据格式归一化处理
            if audio_data.dtype == np.int16:
                audio_float = audio_data.astype(np.float32) / 32768.0
            elif audio_data.dtype == np.float32:
                audio_float = audio_data
            else:
                audio_float = audio_data.astype(np.float32)

            # 确保音频数据在正确的范围内
            audio_float = np.clip(audio_float, -1.0, 1.0)

            # 将音频数据添加到缓冲区以备语音开始时使用
            with self._buffer_lock:
                self._audio_buffer.extend(audio_float)

            # 转换为PyTorch张量
            audio_tensor = torch.from_numpy(audio_float)

            # 使用VAD模型进行语音概率预测
            with torch.no_grad():
                result = self._model(audio_tensor, self.config.sample_rate)
                # 处理不同类型的返回值
                if hasattr(result, 'item'):
                    speech_prob = result.item()
                else:
                    speech_prob = float(result)

            # 根据阈值判断是否为语音
            is_speech = speech_prob >= self.config.threshold

            # 更新状态机并生成检测结果，传递音频数据用于语音段包含
            result = self._update_state(is_speech, speech_prob, len(audio_data), audio_float)

            # 更新处理统计信息
            duration_ms = (len(audio_data) / self.config.sample_rate) * 1000
            self._statistics.update_audio_duration(duration_ms)

            if is_speech:
                self._statistics.update_speech_duration(duration_ms)
            else:
                self._statistics.update_silence_duration(duration_ms)

            # 记录处理耗时
            processing_time = (time.time() - start_time) * 1000
            self._statistics.update_processing_time(processing_time)

            # 调用注册的回调函数
            self._call_callbacks(result)

            return result

        except Exception as e:
            logger.error(f"VAD检测失败: {e}")
            # 返回默认结果而不是抛出异常，保持系统稳定性
            return self._create_error_result(start_time, str(e))

    def _create_error_result(self, start_time: float, error_msg: str) -> VadResult:
        """创建错误结果"""
        timestamp = time.time()
        return VadResult(
            is_speech=False,
            confidence=0.0,
            timestamp=timestamp,
            duration_ms=(timestamp - start_time) * 1000,
            state=VadState.SILENCE,
            audio_data=None,
            speech_start_time=None,
            speech_end_time=None
        )

    # 添加所有其他原方法的实现 - 增强版使用自适应阈值
    def _update_state(self, is_speech: bool, confidence: float, samples: int, audio_data: np.ndarray = None) -> VadResult:
        """更新VAD状态机 - 增强版使用自适应阈值（与SherpaOnnxVAD相同的逻辑）"""
        timestamp = time.time()
        duration_ms = (samples / self.config.sample_rate) * 1000

        self._state_duration += samples
        new_state = self._current_state
        speech_start_time = None
        speech_end_time = None

        if is_speech:
            if self._current_state == VadState.SILENCE:
                if self._state_duration >= self.config.min_speech_samples:
                    new_state = VadState.TRANSITION_TO_SPEECH
                    speech_start_time = timestamp
                    self._start_speech_segment(timestamp, confidence)
                    self._state_duration = 0
            elif self._current_state == VadState.TRANSITION_TO_SPEECH:
                new_state = VadState.SPEECH
                if self._current_segment:
                    self._current_segment.add_confidence_score(confidence)
            elif self._current_state == VadState.SPEECH:
                # 保持语音状态，但检查是否超过最大语音持续时间
                if self._current_segment:
                    self._current_segment.add_confidence_score(confidence)
                    # 检查当前语音段是否超过最大持续时间
                    current_duration_samples = int((timestamp - self._current_segment.start_time) * self.config.sample_rate)
                    if current_duration_samples >= self.config.max_speech_samples:
                        # 自动分段：结束当前语音段并立即开始新的语音段
                        self._end_speech_segment(timestamp)
                        self._start_speech_segment(timestamp, confidence)
                        logger.debug(f"语音段超过最大持续时间 ({self.config.max_speech_duration_ms}ms)，自动分段")
        else:
            if self._current_state in [VadState.SPEECH, VadState.TRANSITION_TO_SPEECH]:
                if self._state_duration >= self.config.min_silence_samples:
                    new_state = VadState.TRANSITION_TO_SILENCE
                    speech_end_time = timestamp
                    self._end_speech_segment(timestamp)
                    self._state_duration = 0
            elif self._current_state == VadState.TRANSITION_TO_SILENCE:
                new_state = VadState.SILENCE

        if new_state != self._current_state:
            old_state = self._current_state
            self._current_state = new_state
            self._state_duration = 0
            logger.debug(
                f"[Legacy] VAD状态变化: {old_state.name} -> {new_state.name}, "
            )

        # 修复：扩展音频数据包含条件，包括过渡状态
        # 在语音活动期间（包括过渡状态）都包含音频数据
        speech_activity_states = [VadState.SPEECH, VadState.TRANSITION_TO_SPEECH]
        include_audio = is_speech and new_state in speech_activity_states

        # 新增：在语音开始时，包含缓冲区中的历史音频
        result_audio_data = None
        if include_audio:
            if new_state == VadState.TRANSITION_TO_SPEECH and speech_start_time is not None:
                # 语音开始：包含缓冲区中的历史音频 + 当前音频
                with self._buffer_lock:
                    buffer_audio = np.array(list(self._audio_buffer), dtype=np.float32)
                if len(buffer_audio) > 0:
                    # 只取最近的一秒音频作为前置缓冲
                    max_buffer_samples = self.config.sample_rate  # 1秒
                    if len(buffer_audio) > max_buffer_samples:
                        buffer_audio = buffer_audio[-max_buffer_samples:]
                    result_audio_data = buffer_audio
                    logger.debug(f"[Legacy] 语音开始：包含缓冲音频 {len(buffer_audio)} 采样点")
                else:
                    result_audio_data = audio_data
            else:
                # 正常语音状态：只包含当前音频
                result_audio_data = audio_data

        result = VadResult(
            is_speech=is_speech,
            confidence=confidence,
            timestamp=timestamp,
            duration_ms=duration_ms,
            state=new_state,
            audio_data=result_audio_data,
            speech_start_time=speech_start_time,
            speech_end_time=speech_end_time
        )

        # 增强的调试信息，包含自适应阈值信息
        if include_audio:
            logger.debug(
                f"[Legacy] VAD输出包含音频数据: 状态={new_state.name}, "
                f"音频长度={len(audio_data)}, 置信度={confidence:.3f}, "
            )
        else:
            logger.debug(
                f"[Legacy] VAD输出不包含音频数据: is_speech={is_speech}, "
                f"state={new_state.name}, 置信度={confidence:.3f}, "
            )

        return result

    def _start_speech_segment(self, timestamp: float, confidence: float) -> None:
        """开始新的语音段"""
        self._current_segment = SpeechSegment(
            start_time=timestamp,
            end_time=None,
            confidence_scores=[confidence]
        )
        logger.debug(f"Started speech segment at {timestamp:.3f}")

    def _end_speech_segment(self, timestamp: float) -> None:
        """结束当前语音段"""
        if self._current_segment:
            self._current_segment.finalize(timestamp)
            self._completed_segments.append(self._current_segment)
            self._statistics.increment_speech_segments()
            logger.debug(f"Ended speech segment: {self._current_segment.duration_ms:.1f}ms")
            self._current_segment = None

    def add_callback(self, callback: Callable[[VadResult], None]) -> None:
        """添加VAD结果回调"""
        with self._callback_lock:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[VadResult], None]) -> None:
        """移除VAD结果回调"""
        with self._callback_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _call_callbacks(self, result: VadResult) -> None:
        """调用所有注册的回调函数"""
        with self._callback_lock:
            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Error in VAD callback {callback.__name__}: {e}")

    def get_completed_segments(self) -> List[SpeechSegment]:
        """获取已完成的语音段列表"""
        return self._completed_segments.copy()

    def clear_segments(self) -> None:
        """清空已完成的语音段"""
        self._completed_segments.clear()

    def get_statistics(self) -> VadStatistics:
        """获取VAD处理统计信息"""
        return self._statistics

    def reset_statistics(self) -> None:
        """重置VAD统计信息"""
        self._statistics = VadStatistics()

    def reset_state(self) -> None:
        """重置VAD状态"""
        self._current_state = VadState.SILENCE
        self._state_duration = 0
        if self._current_segment:
            self._end_speech_segment(time.time())
        self._audio_buffer.clear()

    @property
    def is_speech_active(self) -> bool:
        """检查是否有语音活动"""
        return self._current_state in [VadState.SPEECH, VadState.TRANSITION_TO_SPEECH]

    @property
    def current_state(self) -> VadState:
        """获取当前VAD状态"""
        return self._current_state

    @property
    def current_segment(self) -> Optional[SpeechSegment]:
        """获取当前语音段"""
        return self._current_segment


class VoiceActivityDetector:
    """
    统一的VAD检测器接口

    根据配置自动选择合适的VAD实现（sherpa-onnx或legacy torch），
    提供向后兼容的API接口
    """

    def __init__(self, config: VadConfig):
        """
        初始化VAD检测器，根据配置选择实现

        Args:
            config: VAD配置对象

        Raises:
            ConfigurationError: 当依赖缺失或配置无效时
        """
        self.config = config

        # 使用工厂模式创建具体实现
        self._detector = VadModelFactory.create_vad_detector(config)

        logger.info(f"VAD检测器初始化完成: {config.model.value} "
                   f"(sherpa-onnx: {config.use_sherpa_onnx})")

    def detect(self, audio_data: np.ndarray) -> VadResult:
        """
        代理到具体实现进行音频检测

        Args:
            audio_data: 音频数据 (16kHz, 单声道, int16或float32格式)

        Returns:
            VadResult: 包含检测信息的结果对象
        """
        return self._detector.detect(audio_data)

    def process_audio(self, audio_data: np.ndarray) -> None:
        """
        处理音频数据进行VAD检测

        这是一个便利方法，用于与事件驱动的流水线架构兼容。
        它调用底层的detect方法并通过回调系统传播结果。

        Args:
            audio_data: 音频数据 (16kHz, 单声道, int16或float32格式)

        Note:
            检测结果将通过已注册的回调函数传播，不直接返回结果
        """
        try:
            # 调用底层检测器进行音频检测
            result = self._detector.detect(audio_data)

            # 结果已经通过回调系统在detect方法中传播，无需额外处理
            logger.debug(f"处理音频数据完成: {len(audio_data)} 样本, "
                        f"状态: {result.state.name}, 置信度: {result.confidence:.3f}")

        except Exception as e:
            logger.error(f"处理音频数据时发生错误: {e}")
            raise

    def detect_streaming(self, audio_data: np.ndarray) -> Optional[VadResult]:
        """
        使用VAD迭代器进行流式检测（仅Legacy实现支持）

        Args:
            audio_data: 音频数据块 (16kHz, 单声道)

        Returns:
            Optional[VadResult]: 检测到语音边界时返回结果，否则返回None
        """
        if hasattr(self._detector, 'detect_streaming'):
            return self._detector.detect_streaming(audio_data)
        else:
            # 对于不支持流式检测的实现，使用普通检测
            return self._detector.detect(audio_data)

    def add_callback(self, callback: Callable[[VadResult], None]) -> None:
        """添加回调函数"""
        self._detector.add_callback(callback)

    def remove_callback(self, callback: Callable[[VadResult], None]) -> None:
        """移除回调函数"""
        self._detector.remove_callback(callback)

    def get_statistics(self) -> VadStatistics:
        """获取统计信息"""
        return self._detector.get_statistics()

    def reset_state(self) -> None:
        """重置状态"""
        self._detector.reset_state()

    def get_completed_segments(self) -> List[SpeechSegment]:
        """获取已完成的语音段列表"""
        return self._detector.get_completed_segments()

    def clear_segments(self) -> None:
        """清空已完成的语音段"""
        self._detector.clear_segments()

    def reset_statistics(self) -> None:
        """重置统计信息"""
        self._detector.reset_statistics()

    @property
    def current_state(self) -> VadState:
        """获取当前状态"""
        return self._detector.current_state

    @property
    def is_speech_active(self) -> bool:
        """检查是否有语音活动"""
        return self._detector.is_speech_active

    @property
    def current_segment(self) -> Optional[SpeechSegment]:
        """获取当前语音段（如果活跃）"""
        return self._detector.current_segment


class StreamingVAD:
    """
    Streaming VAD processor for real-time detection

    Handles continuous audio stream with buffering
    """

    def __init__(self, config: VadConfig):
        """Initialize streaming VAD"""
        self.detector = VoiceActivityDetector(config)
        self.config = config
        self._is_running = False
        self._audio_queue = deque()
        self._processing_thread = None

    def start(self) -> None:
        """Start streaming VAD processing"""
        if self._is_running:
            return

        self._is_running = True
        self._processing_thread = threading.Thread(target=self._processing_loop)
        self._processing_thread.start()
        logger.info("Started streaming VAD")

    def stop(self) -> None:
        """Stop streaming VAD processing"""
        if not self._is_running:
            return

        self._is_running = False
        if self._processing_thread:
            self._processing_thread.join(timeout=1.0)
        logger.info("Stopped streaming VAD")

    def process_audio(self, audio_data: np.ndarray) -> None:
        """Add audio data for processing"""
        if self._is_running:
            self._audio_queue.append(audio_data)

    def _processing_loop(self) -> None:
        """Main processing loop"""
        while self._is_running:
            try:
                if self._audio_queue:
                    audio_data = self._audio_queue.popleft()
                    self.detector.detect(audio_data)
                else:
                    time.sleep(0.001)  # Small sleep to prevent busy waiting
            except Exception as e:
                logger.error(f"Error in VAD processing loop: {e}")

    def add_callback(self, callback: Callable[[VadResult], None]) -> None:
        """Add VAD callback"""
        self.detector.add_callback(callback)

    def remove_callback(self, callback: Callable[[VadResult], None]) -> None:
        """Remove VAD callback"""
        self.detector.remove_callback(callback)