"""
转录引擎核心实现 (Transcription Engine Implementation)

基于sherpa-onnx和sense-voice模型的高质量语音转文本引擎。
支持GPU/CPU优化、实时流式处理和批量转录。

主要特性:
- 多模型支持: sherpa-onnx streaming/offline, sense-voice
- GPU/CPU自动选择和优化
- 实时流式处理和端点检测
- 批量处理和性能统计
- 线程安全和异常处理
- 可配置的回调机制

Author: Speech2Subtitles Project
Created: 2025-09-28
"""

# 标准库导入
import logging           # 日志系统
import time             # 时间处理
import threading        # 线程同步
import os               # 操作系统接口
from pathlib import Path # 路径处理
from datetime import datetime  # 日期时间处理
from typing import List, Optional, Callable, Iterator, Dict, Any  # 类型提示
import numpy as np      # 数值计算库

# ============================================================================
# 可选依赖导入和可用性检测 (Optional Dependencies Detection)
# ============================================================================

# sherpa-onnx: 核心语音识别库
try:
    import sherpa_onnx
    SHERPA_ONNX_AVAILABLE = True
except ImportError:
    SHERPA_ONNX_AVAILABLE = False
    sherpa_onnx = None

# PyTorch: GPU加速和深度学习支持
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

# ONNX Runtime: ONNX模型推理引擎
try:
    import onnxruntime as ort
    ONNXRUNTIME_AVAILABLE = True
except ImportError:
    ONNXRUNTIME_AVAILABLE = False
    ort = None

# soundfile: 音频文件读写库
try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False
    sf = None

from .models import (
    TranscriptionConfig, TranscriptionResult, BatchTranscriptionResult,
    ModelInfo, TranscriptionStatistics, TranscriptionModel, ProcessorType,
    LanguageCode, TranscriptionError, ModelLoadError, TranscriptionProcessingError,
    ConfigurationError, ModelNotLoadedError, UnsupportedModelError,
    AudioFormatError
)

# 内部模块导入
from .models import (
    TranscriptionConfig, TranscriptionResult, BatchTranscriptionResult,
    ModelInfo, TranscriptionStatistics, TranscriptionModel, ProcessorType,
    LanguageCode, TranscriptionError, ModelLoadError, TranscriptionProcessingError,
    ConfigurationError, ModelNotLoadedError, UnsupportedModelError,
    AudioFormatError
)

# GPU检测器可选导入
try:
    from ..hardware.gpu_detector import GPUDetector
    GPU_DETECTOR_AVAILABLE = True
except ImportError:
    GPU_DETECTOR_AVAILABLE = False
    GPUDetector = None

# 初始化日志器
logger = logging.getLogger(__name__)


class TranscriptionEngine:
    """
    高级转录引擎 - 支持多模型和流式处理

    提供基于sherpa-onnx和sense-voice的语音转文本功能，
    支持GPU加速、实时流式处理和批量转录。

    核心功能:
    - 多种模型支持: streaming/offline/sense-voice
    - 自动GPU/CPU选择和优化
    - 实时流式转录和端点检测
    - 异步回调机制和统计监控
    - 线程安全和异常处理

    使用示例:
    ```python
    config = TranscriptionConfig(
        model=TranscriptionModel.SENSE_VOICE,
        model_path="models/sense-voice.onnx",
        use_gpu=True
    )

    with TranscriptionEngine(config) as engine:
        result = engine.transcribe_audio(audio_data)
        print(result.text)
    ```
    """

    def __init__(self, config: TranscriptionConfig):
        """
        初始化转录引擎

        执行完整的初始化流程，包括依赖检查、配置验证、
        GPU检测和模型加载。初始化失败将抛出相应异常。

        Args:
            config: 转录配置对象，包含所有必需参数

        Raises:
            ConfigurationError: 配置参数错误或依赖缺失
            ModelLoadError: 模型加载失败
        """
        self.config = config                           # 转录配置
        self._model = None                             # 加载的模型对象
        self._recognizer = None                        # 识别器实例
        self._model_info: Optional[ModelInfo] = None   # 模型信息
        self._gpu_detector: Optional[GPUDetector] = None  # GPU检测器
        self._statistics = TranscriptionStatistics()   # 性能统计
        self._callbacks: List[Callable[[TranscriptionResult], None]] = []  # 结果回调列表
        self._callback_lock = threading.Lock()         # 回调线程锁
        self._model_lock = threading.Lock()            # 模型操作线程锁

        # 音频保存相关配置（从配置对象获取）
        self._audio_save_enabled = config.enable_audio_save and SOUNDFILE_AVAILABLE  # 是否启用音频保存
        self._audio_save_dir = config.audio_save_dir                                  # 音频保存目录
        self._audio_save_format = config.audio_save_format                           # 保存格式(wav/flac/ogg)
        self._audio_save_successful_only = config.audio_save_successful_only         # 仅保存成功转录的音频
        self._audio_counter = 0                                                      # 音频文件计数器

        # 创建音频保存目录
        if self._audio_save_enabled:
            Path(self._audio_save_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"音频保存功能已启用: {self._audio_save_dir} ({self._audio_save_format}格式)")

        # 验证系统依赖
        self._validate_dependencies()

        # 验证配置参数
        if not self.config.validate():
            raise ConfigurationError("转录配置参数无效")

        # 初始化GPU检测器(如果需要)
        if GPU_DETECTOR_AVAILABLE and self.config.processor_type in [ProcessorType.AUTO, ProcessorType.GPU]:
            self._gpu_detector = GPUDetector()

        # 确定最佳处理器类型
        self._determine_processor_type()

        # 加载转录模型
        self._load_model()

        logger.info(f"转录引擎初始化成功: {config}")

    def _validate_dependencies(self) -> None:
        """
        验证系统依赖

        检查所有必需的第三方库是否已正确安装和可用。
        如果缺少关键依赖，将抛出ConfigurationError异常。

        Raises:
            ConfigurationError: 缺少必需依赖库
        """
        if not SHERPA_ONNX_AVAILABLE:
            raise ConfigurationError(
                "sherpa-onnx不可用。请安装: pip install sherpa-onnx"
            )

        if not ONNXRUNTIME_AVAILABLE:
            raise ConfigurationError(
                "onnxruntime不可用。请安装: pip install onnxruntime"
            )

        if self.config.use_gpu and not TORCH_AVAILABLE:
            logger.warning("PyTorch不可用，禁用GPU加速")
            self.config.use_gpu = False

        # 检查音频保存功能依赖
        if self.config.enable_audio_save and not SOUNDFILE_AVAILABLE:
            logger.warning("soundfile库不可用，音频保存功能将被禁用。请安装: uv add soundfile")
            self.config.enable_audio_save = False

    def _determine_processor_type(self) -> None:
        """
        确定最优处理器类型

        根据系统硬件可用性和配置选择最优的处理器类型。
        AUTO模式下会自动检测GPU可用性并选择最佳选项。
        """
        if self.config.processor_type == ProcessorType.AUTO:
            # 自动检测最佳处理器
            if self._gpu_detector and self._gpu_detector.detect_cuda() and self.config.use_gpu:
                self.config.processor_type = ProcessorType.GPU
                logger.info("自动选择GPU处理")
            else:
                self.config.processor_type = ProcessorType.CPU
                logger.info("自动选择CPU处理")
        elif self.config.processor_type == ProcessorType.GPU:
            # 验证GPU可用性
            if not self._gpu_detector or not self._gpu_detector.detect_cuda():
                logger.warning("请求GPU但不可用，回退到CPU处理")
                self.config.processor_type = ProcessorType.CPU

    def _load_model(self) -> None:
        """Load the specified transcription model"""
        start_time = time.time()

        try:
            if not os.path.exists(self.config.model_path):
                raise ModelLoadError(f"Model path does not exist: {self.config.model_path}")

            if self.config.model == TranscriptionModel.SHERPA_ONNX_STREAMING:
                self._load_sherpa_streaming_model()
            elif self.config.model == TranscriptionModel.SHERPA_ONNX_OFFLINE:
                self._load_sherpa_offline_model()
            elif self.config.model == TranscriptionModel.SENSE_VOICE:
                self._load_sense_voice_model()
            else:
                raise UnsupportedModelError(f"Unsupported model type: {self.config.model}")

            # Create model info
            load_time = (time.time() - start_time) * 1000
            self._model_info = ModelInfo(
                model_type=self.config.model,
                model_path=self.config.model_path,
                language=self.config.language.value,
                sample_rate=self.config.sample_rate,
                is_loaded=True,
                load_time_ms=load_time,
                supports_streaming=self.config.is_streaming
            )

            logger.info(f"Model loaded successfully in {load_time:.1f}ms")

        except Exception as e:
            raise ModelLoadError(f"Failed to load model: {e}")

    def _load_sherpa_streaming_model(self) -> None:
        """Load sherpa-onnx streaming model"""
        try:
            logger.info(f"正在加载sherpa-onnx streaming模型: {self.config.model_path}")

            # 尝试加载流式模型配置
            model_config = sherpa_onnx.OnlineTransducerModelConfig(
                encoder_filename=self.config.model_path + "/encoder.onnx",
                decoder_filename=self.config.model_path + "/decoder.onnx",
                joiner_filename=self.config.model_path + "/joiner.onnx"
            )

            recognizer_config = sherpa_onnx.OnlineRecognizerConfig(
                feat_config=sherpa_onnx.FeatureConfig(
                    sample_rate=self.config.sample_rate,
                    feature_dim=80
                ),
                model_config=sherpa_onnx.OnlineModelConfig(
                    transducer=model_config,
                    tokens=os.path.join(self.config.model_path, "tokens.txt"),
                    num_threads=4
                )
            )

            self._recognizer = sherpa_onnx.OnlineRecognizer(recognizer_config)
            logger.info("sherpa-onnx streaming模型加载成功")

        except Exception as e:
            logger.warning(f"sherpa-onnx streaming模型加载失败，使用基础实现: {e}")

    def _load_sherpa_offline_model(self) -> None:
        """Load sherpa-onnx offline model"""
        try:
            logger.info(f"正在加载sherpa-onnx offline模型: {self.config.model_path}")

            # 尝试加载离线模型配置
            model_config = sherpa_onnx.OfflineTransducerModelConfig(
                encoder_filename=self.config.model_path + "/encoder.onnx",
                decoder_filename=self.config.model_path + "/decoder.onnx",
                joiner_filename=self.config.model_path + "/joiner.onnx"
            )

            recognizer_config = sherpa_onnx.OfflineRecognizerConfig(
                feat_config=sherpa_onnx.FeatureConfig(
                    sample_rate=self.config.sample_rate,
                    feature_dim=80
                ),
                model_config=sherpa_onnx.OfflineModelConfig(
                    transducer=model_config,
                    tokens=os.path.join(self.config.model_path, "tokens.txt"),
                    num_threads=4
                )
            )

            self._recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)
            logger.info("sherpa-onnx offline模型加载成功")

        except Exception as e:
            logger.warning(f"sherpa-onnx offline模型加载失败，使用基础实现: {e}")

    def _resolve_sense_voice_language_hint(self) -> str:
        """
        解析 sense-voice 语言提示参数。

        返回值：
        - "auto"：自动识别
        - "zh"/"en"：显式语言提示
        """
        if self.config.language == LanguageCode.CHINESE:
            return "zh"
        if self.config.language == LanguageCode.ENGLISH:
            return "en"
        return "auto"

    def _load_sense_voice_model(self) -> None:
        """Load sense-voice model - enhanced implementation with fallback"""
        try:
            # 检查模型文件是否存在
            if not os.path.exists(self.config.model_path):
                raise ModelLoadError(f"模型文件不存在: {self.config.model_path}")

            # 基本的sherpa-onnx sense-voice模型加载
            logger.info(f"正在加载sense-voice模型: {self.config.model_path}")
            language_hint = self._resolve_sense_voice_language_hint()
            logger.info(f"sense-voice语言提示: {language_hint}")

            # 创建sense-voice配置
            # model_config = sherpa_onnx.OfflineSenseVoiceModelConfig(
            #     model=self.config.model_path,
            #     language="auto",  # 自动检测语言
            #     use_itn=True      # 启用逆文本归一化
            # )

            # # 创建离线识别器配置
            # recognizer_config = sherpa_onnx.OfflineRecognizerConfig(
            #     feat_config=sherpa_onnx.FeatureConfig(
            #         sample_rate=self.config.sample_rate,
            #         feature_dim=80
            #     ),
            #     model_config=sherpa_onnx.OfflineModelConfig(
            #         sense_voice=model_config,
            #         tokens=os.path.join(os.path.dirname(self.config.model_path), "tokens.txt"),
            #         num_threads=4,
            #         debug=False
            #     )
            # )

            # # 创建识别器
            # self._recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)
            #ort.preload_dlls()
            #print(ort.get_available_providers())
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=self.config.model_path,
                tokens=os.path.join(os.path.dirname(self.config.model_path), "tokens.txt"),
                num_threads=2,
                use_itn=True,
                debug=False,
                provider='cuda' if self.config.use_gpu else 'cpu',
                language=language_hint,
                # hr_dict_dir=args.hr_dict_dir,
                # hr_rule_fsts=args.hr_rule_fsts,
                # hr_lexicon=args.hr_lexicon,
            )
            logger.info("sense-voice模型加载成功")

        except Exception as e:
            if "sherpa_onnx" in str(e) or "not found" in str(e).lower():
                # 如果是sherpa-onnx相关错误，提供详细的错误信息
                logger.warning(f"sherpa-onnx模型加载失败，使用基础实现: {e}")
            else:
                raise ModelLoadError(f"加载sense-voice模型失败: {e}")

    def transcribe_audio(self, audio_data: np.ndarray, return_partial: bool = False) -> TranscriptionResult:
        """
        Transcribe audio data with enhanced error handling

        Args:
            audio_data: Audio data (sample_rate, mono, float32)
            return_partial: Whether to return partial results

        Returns:
            TranscriptionResult with transcription
        """
        if not self._recognizer:
            raise ModelNotLoadedError("Model not loaded")

        start_time = time.time()

        try:
            # Validate audio format
            # if audio_data.dtype != np.float32:
                # audio_data = audio_data.astype(np.float32)

            # Ensure audio is in correct range
            # audio_data = np.clip(audio_data, -1.0, 1.0)

            # 检查音频数据有效性
            if len(audio_data) == 0:
                logger.warning("音频数据为空，跳过转录")
                return self._create_empty_result(start_time)

            # 检查音频能量级别
            audio_energy = np.mean(np.abs(audio_data))
            logger.debug(f"转录音频: 长度={len(audio_data)}, 能量={audio_energy:.4f}")

            # Create audio stream for recognition
            stream = self._recognizer.create_stream()

            # Accept audio data
            stream.accept_waveform(
                sample_rate=self.config.sample_rate,
                waveform=audio_data
            )

            # Process audio
            if hasattr(self._recognizer, 'is_ready'):
                while self._recognizer.is_ready(stream):
                    self._recognizer.decode_stream(stream)
            else:
                self._recognizer.decode_stream(stream)
                
            # Get result
            if hasattr(self._recognizer, 'get_result'):
                result = self._recognizer.get_result(stream)
            else:
                result = stream.result
            result_text = result.text.strip() if hasattr(result, 'text') else f"检测到语音信号 (能量: {audio_energy:.4f})"

            # 判断转录是否成功
            is_successful_transcription = result_text and result_text.strip() and not result_text.startswith("[检测到语音但无法识别内容]")

            # 如果是空结果，提供有意义的反馈
            if not is_successful_transcription:
                result_text = f"[检测到语音但无法识别内容] 能量: {audio_energy:.4f}"

            # 保存音频文件到本地（根据配置决定是否保存）
            should_save_audio = self._audio_save_enabled and (
                not self._audio_save_successful_only or is_successful_transcription
            )

            if should_save_audio:
                saved_path = self._save_audio(audio_data, result_text if is_successful_transcription else "")
                if saved_path:
                    if is_successful_transcription:
                        logger.info(f"成功转录并保存音频: {saved_path}")
                    else:
                        logger.debug(f"保存音频文件: {saved_path}")
                else:
                    logger.debug("音频保存失败")
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000

            # Create result
            result = TranscriptionResult(
                text=result_text,
                confidence=min(1.0, audio_energy * 10),  # 基于音频能量的简单置信度估算
                start_time=start_time,
                end_time=time.time(),
                duration_ms=len(audio_data) / self.config.sample_rate * 1000,
                language=self.config.language.value,
                is_final=not return_partial,
                is_partial=return_partial,
                processing_time_ms=processing_time
            )

            # Update statistics
            self._update_statistics(result)

            # Call callbacks
            self._call_callbacks(result)

            logger.info(f"转录完成: '{result_text}' (用时: {processing_time:.1f}ms)")

            return result

        except Exception as e:
            self._statistics.increment_errors()
            logger.error(f"转录失败: {e}")
            # 返回错误结果而不是抛出异常，保持系统稳定性
            return self._create_error_result(start_time, str(e))

    def _create_empty_result(self, start_time: float) -> TranscriptionResult:
        """创建空结果"""
        return TranscriptionResult(
            text="[空音频数据]",
            confidence=0.0,
            start_time=start_time,
            end_time=time.time(),
            duration_ms=0.0,
            language=self.config.language.value,
            is_final=True,
            is_partial=False,
            processing_time_ms=(time.time() - start_time) * 1000
        )

    def _create_error_result(self, start_time: float, error_msg: str) -> TranscriptionResult:
        """创建错误结果"""
        return TranscriptionResult(
            text=f"[转录错误: {error_msg}]",
            confidence=0.0,
            start_time=start_time,
            end_time=time.time(),
            duration_ms=0.0,
            language=self.config.language.value,
            is_final=True,
            is_partial=False,
            processing_time_ms=(time.time() - start_time) * 1000
        )

    def transcribe_streaming(self, audio_chunk: np.ndarray) -> Optional[TranscriptionResult]:
        """
        Process streaming audio chunk

        Args:
            audio_chunk: Audio chunk (sample_rate, mono, float32)

        Returns:
            TranscriptionResult if text detected, None otherwise
        """
        if not self.config.is_streaming:
            raise UnsupportedModelError("Current model does not support streaming")

        if not self._recognizer:
            raise ModelNotLoadedError("Model not loaded")

        try:
            # Validate audio format
            if audio_chunk.dtype != np.float32:
                audio_chunk = audio_chunk.astype(np.float32)

            # Create stream if not exists (for continuous streaming)
            if not hasattr(self, '_streaming_stream') or self._streaming_stream is None:
                self._streaming_stream = self._recognizer.create_stream()

            # Accept audio chunk
            self._streaming_stream.accept_waveform(
                sample_rate=self.config.sample_rate,
                waveform=audio_chunk
            )

            # Process if ready
            if self._recognizer.is_ready(self._streaming_stream):
                self._recognizer.decode_stream(self._streaming_stream)

            # Check for endpoint detection
            if self.config.enable_endpoint_detection and self._recognizer.is_endpoint(self._streaming_stream):
                # Get final result
                result_text = self._recognizer.get_result(self._streaming_stream).text.strip()

                if result_text:
                    result = TranscriptionResult(
                        text=result_text,
                        confidence=1.0,
                        start_time=time.time() - len(audio_chunk) / self.config.sample_rate,
                        end_time=time.time(),
                        duration_ms=len(audio_chunk) / self.config.sample_rate * 1000,
                        language=self.config.language.value,
                        is_final=True,
                        is_partial=False
                    )

                    # Reset stream for next utterance
                    self._streaming_stream = self._recognizer.create_stream()

                    # Update statistics
                    self._update_statistics(result)

                    # Call callbacks
                    self._call_callbacks(result)

                    return result

            # Get partial result if available
            partial_text = self._recognizer.get_result(self._streaming_stream).text.strip()
            if partial_text:
                return TranscriptionResult(
                    text=partial_text,
                    confidence=0.5,  # Lower confidence for partial results
                    start_time=time.time() - len(audio_chunk) / self.config.sample_rate,
                    end_time=time.time(),
                    duration_ms=len(audio_chunk) / self.config.sample_rate * 1000,
                    language=self.config.language.value,
                    is_final=False,
                    is_partial=True
                )

            return None

        except Exception as e:
            self._statistics.increment_errors()
            logger.error(f"Streaming transcription error: {e}")
            return None

    def transcribe_batch(self, audio_segments: List[np.ndarray]) -> BatchTranscriptionResult:
        """
        Transcribe multiple audio segments

        Args:
            audio_segments: List of audio data arrays

        Returns:
            BatchTranscriptionResult with all results
        """
        batch_result = BatchTranscriptionResult()

        for i, audio_data in enumerate(audio_segments):
            try:
                result = self.transcribe_audio(audio_data)
                batch_result.add_result(result)
                logger.debug(f"Processed batch segment {i+1}/{len(audio_segments)}")
            except Exception as e:
                logger.error(f"Failed to process batch segment {i+1}: {e}")
                self._statistics.increment_errors()

        return batch_result

    def add_callback(self, callback: Callable[[TranscriptionResult], None]) -> None:
        """Add callback for transcription results"""
        with self._callback_lock:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[TranscriptionResult], None]) -> None:
        """Remove callback"""
        with self._callback_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _call_callbacks(self, result: TranscriptionResult) -> None:
        """Call all registered callbacks"""
        with self._callback_lock:
            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

    def _update_statistics(self, result: TranscriptionResult) -> None:
        """Update processing statistics"""
        if result.duration_ms:
            self._statistics.update_audio_duration(result.duration_ms)

        if result.processing_time_ms:
            self._statistics.update_processing_time(result.processing_time_ms)

        self._statistics.increment_segments()
        self._statistics.update_words_count(result.word_count)
        self._statistics.update_characters_count(result.characters_count)
        self._statistics.update_confidence(result.confidence)
        self._statistics.increment_successful()

    def _save_audio(self, audio_data: np.ndarray, result_text: str = "") -> Optional[str]:
        """
        保存音频数据到文件

        Args:
            audio_data: 要保存的音频数据 (numpy数组, float32格式)
            result_text: 转录结果文本，用于生成文件名

        Returns:
            保存的文件路径，如果保存失败则返回None
        """
        if not self._audio_save_enabled or not SOUNDFILE_AVAILABLE:
            return None

        try:
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 增加音频计数器
            self._audio_counter += 1

            # 生成文件名：基于时间戳、计数器和转录文本的简短片段
            text_snippet = ""
            if result_text:
                # 取转录文本的前10个字符作为文件名的一部分
                clean_text = "".join(c for c in result_text[:10] if c.isalnum() or c in "一二三四五六七八九十")
                if clean_text:
                    text_snippet = f"_{clean_text}"

            filename = f"audio_{timestamp}_{self._audio_counter:04d}{text_snippet}.{self._audio_save_format}"
            filepath = Path(self._audio_save_dir) / filename

            # 确保音频数据格式正确
            # if audio_data.dtype != np.float32:
                # audio_data = audio_data.astype(np.float32)

            # 确保音频数据在正确范围内
            audio_data = np.clip(audio_data, -1.0, 1.0)

            # 保存音频文件
            sf.write(
                str(filepath),
                audio_data,
                self.config.sample_rate,
                format=self._audio_save_format.upper()
            )

            logger.debug(f"音频已保存: {filepath} (长度: {len(audio_data)}, 采样率: {self.config.sample_rate})")
            return str(filepath)

        except Exception as e:
            logger.error(f"音频保存失败: {e}")
            return None

    @property
    def model_info(self) -> Optional[ModelInfo]:
        """Get model information"""
        return self._model_info

    @property
    def statistics(self) -> TranscriptionStatistics:
        """Get processing statistics"""
        return self._statistics

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._recognizer is not None

    @property
    def supports_streaming(self) -> bool:
        """Check if current model supports streaming"""
        return self.config.is_streaming and self._recognizer is not None

    def reset_statistics(self) -> None:
        """Reset processing statistics"""
        self._statistics = TranscriptionStatistics()

    def close(self) -> None:
        """Clean up resources"""
        try:
            if hasattr(self, '_streaming_stream') and self._streaming_stream:
                self._streaming_stream = None

            if self._recognizer:
                # Note: sherpa-onnx recognizers don't have explicit cleanup methods
                self._recognizer = None

            self._callbacks.clear()
            logger.info("TranscriptionEngine closed successfully")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class StreamingTranscriptionEngine(TranscriptionEngine):
    """
    Specialized engine for streaming transcription

    Optimized for real-time processing with minimal latency
    """

    def __init__(self, config: TranscriptionConfig):
        """Initialize streaming engine"""
        if not config.is_streaming:
            raise ConfigurationError("StreamingTranscriptionEngine requires a streaming model")

        super().__init__(config)
        self._stream = None
        self._initialize_stream()

    def _initialize_stream(self) -> None:
        """Initialize streaming interface"""
        if self._recognizer:
            self._stream = self._recognizer.create_stream()

    def process_chunk(self, audio_chunk: np.ndarray) -> Optional[TranscriptionResult]:
        """
        Process single audio chunk with optimized streaming

        Args:
            audio_chunk: Audio chunk for processing

        Returns:
            TranscriptionResult if available, None otherwise
        """
        if not self._stream:
            raise ModelNotLoadedError("Streaming not initialized")

        return self.transcribe_streaming(audio_chunk)

    def reset_stream(self) -> None:
        """Reset streaming state"""
        if self._recognizer:
            self._stream = self._recognizer.create_stream()

    def close(self) -> None:
        """Clean up streaming resources"""
        if self._stream:
            self._stream = None
        super().close()
