"""
转录引擎数据模型 (Transcription Engine Data Models)

该模块定义了语音转录系统的核心数据结构，包括:
- 转录配置管理
- 转录结果封装
- 模型信息和统计
- 批量处理结果
- 自定义异常类型

所有数据模型都支持序列化和反序列化，便于存储和传输。

Author: Speech2Subtitles Project
Created: 2025-09-28
"""

# 标准库导入
from dataclasses import dataclass, field  # 数据类装饰器和字段定义
from typing import List, Optional, Dict, Any  # 类型提示支持
from enum import Enum  # 枚举类型支持
import time  # 时间处理函数


class TranscriptionModel(Enum):
    """
    可用的转录模型类型枚举

    定义系统支持的不同语音识别模型类型，每种模型有不同的特性:
    - SHERPA_ONNX_STREAMING: 支持实时流式转录，延迟低
    - SHERPA_ONNX_OFFLINE: 离线批量转录，准确率高
    - SENSE_VOICE: 阿里巴巴开源的多语言模型，质量优秀
    """
    SHERPA_ONNX_STREAMING = "sherpa_onnx_streaming"  # sherpa-onnx流式模型
    SHERPA_ONNX_OFFLINE = "sherpa_onnx_offline"      # sherpa-onnx离线模型
    SENSE_VOICE = "sense_voice"                      # sense-voice模型
    QWEN_ARS = "qwen_ars"


class ProcessorType(Enum):
    """
    处理器类型枚举

    定义模型推理时使用的计算资源类型:
    - CPU: 使用CPU进行推理，兼容性好但速度较慢
    - GPU: 使用GPU加速，需要CUDA支持，速度快
    - AUTO: 自动检测并选择最佳处理器类型
    """
    CPU = "cpu"      # CPU处理器
    GPU = "gpu"      # GPU处理器(需要CUDA)
    AUTO = "auto"    # 自动选择


class LanguageCode(Enum):
    """
    支持的语言代码枚举

    定义系统支持的语言类型，用于模型选择和语言特定优化:
    - CHINESE: 中文(包括普通话、方言)
    - ENGLISH: 英文
    - AUTO: 自动语言检测
    """
    CHINESE = "zh"   # 中文
    ENGLISH = "en"   # 英文
    AUTO = "auto"    # 自动检测语言


@dataclass
class TranscriptionConfig:
    """
    转录引擎配置类

    存储转录引擎的所有配置参数，包括模型选择、处理器设置、
    性能参数和语言配置等。所有参数都有默认值，可以逐步调优。

    关键参数说明:
    - model: 模型类型选择
    - model_path: 模型文件路径(必须)
    - use_gpu: 是否启用GPU加速
    - beam_size: 束搜索大小，影响准确性和速度
    - endpoint_threshold: 端点检测阈值，用于断句
    """
    model: TranscriptionModel = TranscriptionModel.SHERPA_ONNX_STREAMING
    model_path: str = ""
    language: LanguageCode = LanguageCode.CHINESE
    processor_type: ProcessorType = ProcessorType.AUTO
    sample_rate: int = 16000
    chunk_size: int = 1024
    use_gpu: bool = True
    beam_size: int = 4
    max_active_paths: int = 4
    enable_endpoint_detection: bool = True
    endpoint_threshold: float = 0.5
    rule1_min_trailing_silence: float = 2.4
    rule2_min_trailing_silence: float = 1.2
    rule3_min_utterance_length: float = 20.0
    hotwords_score: float = 1.5
    hotwords_file: str = ""
    blank_penalty: float = 0.0
    temperature: float = 1.0

    # 下面为qwen3-ars参数
    hotwords: str = ""              # 可选逗号分隔热词短语    
    num_threads: int = 2            # qwen3-ars推理线程数
    feature_dim: int = 128          # qwen3-ars特征维度
    seed: int = 48                  # 随机seed
    top_p: float = 0.8
    max_new_tokens: int = 128
    max_total_len: int = 512

    # 音频保存配置
    enable_audio_save: bool = False                    # 是否启用音频保存
    audio_save_dir: str = "saved_audio"               # 音频保存目录
    audio_save_format: str = "wav"                    # 音频保存格式 (wav/flac/ogg)
    audio_save_successful_only: bool = True           # 仅保存成功转录的音频

    def validate(self) -> bool:
        """
        验证转录配置的有效性

        检查所有关键参数是否正确设置，包括:
        - 模型路径是否为空
        - 采样率和块大小是否为正数
        - 阈值参数是否在有效范围内
        - 束搜索参数是否合理

        Returns:
            bool: 配置是否有效
        """
        if not self.model_path:
            return False
        if self.sample_rate <= 0:
            return False
        if self.chunk_size <= 0:
            return False
        if not 0.0 <= self.endpoint_threshold <= 1.0:
            return False
        if self.beam_size <= 0:
            return False
        if self.max_active_paths <= 0:
            return False
        # 验证音频保存格式
        if self.audio_save_format.lower() not in ['wav', 'flac', 'ogg']:
            return False
        return True

    @property
    def is_streaming(self) -> bool:
        """
        检查当前模型是否支持流式处理

        根据模型类型判断是否支持实时流式转录。
        流式模型可以处理连续的音频数据流，适合实时应用。

        Returns:
            bool: 是否支持流式处理
        """
        return self.model in [
            TranscriptionModel.SHERPA_ONNX_STREAMING,
            TranscriptionModel.SENSE_VOICE
        ]

    @property
    def device_config(self) -> Dict[str, Any]:
        """
        生成ONNX运行时的设备配置

        根据处理器类型和GPU设置，生成适合的ONNX执行提供程序配置。
        这个配置将被传递给onnxruntime来优化推理性能。

        Returns:
            Dict[str, Any]: ONNX设备配置字典
        """
        if self.processor_type == ProcessorType.CPU:
            return {"provider": "CPUExecutionProvider"}
        elif self.processor_type == ProcessorType.GPU and self.use_gpu:
            return {"provider": "CUDAExecutionProvider"}
        else:
            return {"provider": "CPUExecutionProvider"}


@dataclass
class TranscriptionResult:
    """
    单个音频段的转录结果

    封装一次转录操作的所有结果信息，包括转录文本、
    置信度、时间信息和元数据。支持部分结果和最终结果区分。

    字段说明:
    - text: 转录的文本内容
    - confidence: 置信度分数(0.0-1.0)
    - start_time/end_time: 音频的开始和结束时间
    - is_final: 是否为最终结果(非中间结果)
    - word_timestamps: 词级别的时间戳信息
    """
    text: str
    confidence: float
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    language: Optional[str] = None
    is_final: bool = False
    is_partial: bool = False
    word_timestamps: List[Dict[str, Any]] = field(default_factory=list)
    processing_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        """
        数据类初始化后的处理

        自动计算一些派生字段，如音频持续时间。
        这个方法在dataclass创建后自动调用。
        """
        if self.end_time and not self.duration_ms:
            self.duration_ms = (self.end_time - self.start_time) * 1000

    @property
    def is_empty(self) -> bool:
        """
        检查转录结果是否为空

        判断转录结果是否包含有效文本内容。
        空结果通常表示没有检测到语音或识别失败。

        Returns:
            bool: 是否为空结果
        """
        return not self.text or self.text.strip() == ""

    @property
    def word_count(self) -> int:
        """
        获取词数统计

        通过空格分割文本来统计词数。
        注意:这个方法主要适用于英文，中文计数可能不准确。

        Returns:
            int: 词数
        """
        return len(self.text.split()) if self.text else 0

    @property
    def characters_count(self) -> int:
        """
        获取字符数统计

        计算转录文本的字符总数，包括中文字符、英文字母和标点符号。

        Returns:
            int: 字符数
        """
        return len(self.text) if self.text else 0

    @property
    def has_word_timestamps(self) -> bool:
        """
        检查是否包含词级别时间戳

        判断转录结果是否包含详细的词级别时间戳信息。
        这些信息可用于精确的字幕同步和语音分析。

        Returns:
            bool: 是否包含词级时间戳
        """
        return bool(self.word_timestamps)

    def add_word_timestamp(self, word: str, start: float, end: float, confidence: float = 1.0) -> None:
        """
        添加词级别时间戳

        为转录结果添加单个词的时间戳信息。
        这些信息可用于字幕的精确同步和语音分析。

        Args:
            word: 词汇文本
            start: 开始时间(秒)
            end: 结束时间(秒)
            confidence: 该词的置信度(0.0-1.0)
        """
        self.word_timestamps.append({
            "word": word,
            "start": start,
            "end": end,
            "confidence": confidence
        })

    def finalize(self, end_time: Optional[float] = None) -> None:
        """
        终结转录结果

        将转录结果标记为最终版本，并计算最终的时间信息。
        一旦终结，结果将不再是部分结果。

        Args:
            end_time: 指定的结束时间，如果不提供则使用已有值
        """
        if end_time:
            self.end_time = end_time
            self.duration_ms = (end_time - self.start_time) * 1000
        self.is_final = True
        self.is_partial = False


@dataclass
class BatchTranscriptionResult:
    """Result for batch transcription"""
    results: List[TranscriptionResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    total_processing_time_ms: float = 0.0
    average_confidence: float = 0.0
    total_text: str = ""

    def __post_init__(self):
        """Calculate derived statistics"""
        self.update_statistics()

    def add_result(self, result: TranscriptionResult) -> None:
        """Add a transcription result"""
        self.results.append(result)
        self.update_statistics()

    def update_statistics(self) -> None:
        """Update batch statistics"""
        if not self.results:
            return

        # Calculate totals
        confidences = [r.confidence for r in self.results if r.confidence > 0]
        self.average_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        self.total_duration_ms = sum(
            r.duration_ms for r in self.results if r.duration_ms
        )

        self.total_processing_time_ms = sum(
            r.processing_time_ms for r in self.results
        )

        # Combine all text
        texts = [r.text for r in self.results if r.text and not r.is_empty]
        self.total_text = " ".join(texts)

    @property
    def result_count(self) -> int:
        """Get number of results"""
        return len(self.results)

    @property
    def final_results_count(self) -> int:
        """Get number of final results"""
        return sum(1 for r in self.results if r.is_final)

    @property
    def partial_results_count(self) -> int:
        """Get number of partial results"""
        return sum(1 for r in self.results if r.is_partial)

    @property
    def processing_real_time_factor(self) -> float:
        """Calculate processing speed relative to real-time"""
        if self.total_duration_ms <= 0:
            return 0.0
        return self.total_processing_time_ms / self.total_duration_ms

    @property
    def total_word_count(self) -> int:
        """Get total word count"""
        return sum(r.word_count for r in self.results)

    @property
    def total_character_count(self) -> int:
        """Get total character count"""
        return sum(r.characters_count for r in self.results)


@dataclass
class ModelInfo:
    """Information about a loaded model"""
    model_type: TranscriptionModel
    model_path: str
    language: str
    sample_rate: int
    is_loaded: bool = False
    load_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    supports_streaming: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def model_name(self) -> str:
        """Get model name from path"""
        return self.model_path.split("/")[-1] if self.model_path else "unknown"

    @property
    def is_streaming_capable(self) -> bool:
        """Check if model supports streaming"""
        return self.supports_streaming


@dataclass
class TranscriptionStatistics:
    """Transcription processing statistics"""
    total_audio_duration_ms: float = 0.0
    total_processing_time_ms: float = 0.0
    segments_processed: int = 0
    words_transcribed: int = 0
    characters_transcribed: int = 0
    average_confidence: float = 0.0
    error_count: int = 0
    successful_transcriptions: int = 0

    @property
    def processing_real_time_factor(self) -> float:
        """Calculate processing speed relative to real-time"""
        if self.total_audio_duration_ms <= 0:
            return 0.0
        return self.total_processing_time_ms / self.total_audio_duration_ms

    @property
    def success_rate(self) -> float:
        """Calculate transcription success rate"""
        total_attempts = self.successful_transcriptions + self.error_count
        if total_attempts <= 0:
            return 0.0
        return self.successful_transcriptions / total_attempts

    @property
    def words_per_second(self) -> float:
        """Calculate words per second processing rate"""
        if self.total_audio_duration_ms <= 0:
            return 0.0
        return self.words_transcribed / (self.total_audio_duration_ms / 1000.0)

    @property
    def average_segment_duration_ms(self) -> float:
        """Calculate average segment duration"""
        if self.segments_processed <= 0:
            return 0.0
        return self.total_audio_duration_ms / self.segments_processed

    def update_audio_duration(self, duration_ms: float) -> None:
        """Update total audio duration"""
        self.total_audio_duration_ms += duration_ms

    def update_processing_time(self, time_ms: float) -> None:
        """Update total processing time"""
        self.total_processing_time_ms += time_ms

    def increment_segments(self) -> None:
        """Increment segments processed"""
        self.segments_processed += 1

    def update_words_count(self, count: int) -> None:
        """Update words transcribed count"""
        self.words_transcribed += count

    def update_characters_count(self, count: int) -> None:
        """Update characters transcribed count"""
        self.characters_transcribed += count

    def update_confidence(self, confidence: float) -> None:
        """Update average confidence (running average)"""
        if self.segments_processed <= 1:
            self.average_confidence = confidence
        else:
            # Running average calculation
            self.average_confidence = (
                (self.average_confidence * (self.segments_processed - 1) + confidence)
                / self.segments_processed
            )

    def increment_errors(self) -> None:
        """Increment error count"""
        self.error_count += 1

    def increment_successful(self) -> None:
        """Increment successful transcription count"""
        self.successful_transcriptions += 1


# ============================================================================
# 自定义异常类 (Custom Exceptions)
# ============================================================================

class TranscriptionError(Exception):
    """
    转录系统基本异常类

    所有转录相关异常的基类，提供统一的错误处理接口。
    可以用于捕获所有转录相关的异常。
    """
    pass


class ModelLoadError(TranscriptionError):
    """
    模型加载错误

    在加载转录模型时出现的错误，包括:
    - 模型文件不存在或损坏
    - 模型格式不支持
    - 依赖库缺失或版本不兼容
    - GPU/CPU资源不足
    """
    pass


class TranscriptionProcessingError(TranscriptionError):
    """
    转录处理错误

    在执行语音转录过程中出现的错误，包括:
    - 音频数据格式错误
    - 模型推理失败
    - 内存不足或超时
    - 网络连接问题(如果使用远程模型)
    """
    pass


class ConfigurationError(TranscriptionError):
    """
    配置错误

    转录引擎配置参数错误，包括:
    - 必需参数缺失
    - 参数值超出有效范围
    - 参数类型不匹配
    - 依赖组件不可用
    """
    pass


class ModelNotLoadedError(TranscriptionError):
    """
    模型未加载错误

    尝试使用未成功加载的模型进行转录操作时抛出。
    通常需要先调用模型加载方法或检查加载状态。
    """
    pass


class UnsupportedModelError(TranscriptionError):
    """
    不支持的模型错误

    当请求的模型类型或功能不被当前系统支持时抛出。
    包括不可用的模型架构、版本或特定功能。
    """
    pass


class AudioFormatError(TranscriptionError):
    """
    音频格式错误

    输入的音频数据格式不符合要求时抛出，包括:
    - 采样率不匹配
    - 声道数不支持
    - 数据类型错误
    - 音频数据损坏或格式异常
    """
    pass
