"""
语音活动检测数据模型 (Voice Activity Detection Data Models)

定义VAD检测结果、配置项和状态管理的数据结构
用于在语音识别系统中进行实时语音/静音检测
"""

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING, Dict, Any
from enum import Enum
import time
import os

if TYPE_CHECKING:
    import numpy as np


class VadState(Enum):
    """
    语音活动检测状态枚举
    用于表示VAD检测器当前的状态机状态
    """
    SILENCE = "silence"                       # 静音状态 - 检测到的是背景噪音或无声
    SPEECH = "speech"                         # 语音状态 - 检测到稳定的语音活动
    TRANSITION_TO_SPEECH = "transition_to_speech"    # 转换到语音状态 - 刚开始检测到语音
    TRANSITION_TO_SILENCE = "transition_to_silence"  # 转换到静音状态 - 语音刚结束


class VadModel(Enum):
    """
    可用的VAD模型枚举
    支持sherpa-onnx框架的多种VAD模型
    """
    SILERO = "silero_vad"              # Silero VAD 模型路径
    TEN_VAD = "ten_vad"                       # Ten VAD模型路径
    @property
    def model_name(self) -> str:
        """
        获取sherpa-onnx模型名称

        Returns:
            str: 模型文件名
        """
        mapping = {
            VadModel.SILERO: "silero_vad.onnx",
            VadModel.TEN_VAD: "ten_vad.onnx"
        }
        return mapping[self]

    @property
    def default_path(self) -> str:
        """
        获取默认模型路径

        Returns:
            str: 模型文件的默认存储路径
        """
        return f"models/{self.value}/"


@dataclass
class VadConfig:
    """
    VAD配置类 - 支持多模型选择
    包含语音活动检测的所有配置参数

    增强版配置验证，支持可配置的响应性调整
    """
    model: VadModel = VadModel.SILERO     # 使用的VAD模型版本
    model_path: Optional[str] = None         # 自定义模型路径，None时使用默认路径
    threshold: float = 0.5                   # 语音检测阈值 (0.0-1.0)，值越高越严格
    min_speech_duration_ms: float = 100.0    # 最小语音持续时间(毫秒)，过滤短暂音频
    min_silence_duration_ms: float = 150.0   # 最小静音持续时间(毫秒)，避免频繁切换
    max_speech_duration_ms: float = 30000.0  # 最大语音持续时间(毫秒)，超过时自动分段，默认30秒
    window_size_samples: int = 512           # 音频处理窗口大小(采样点数)
    sample_rate: int = 16000                 # 音频采样率(Hz)，VAD模型需要16kHz
    return_confidence: bool = True           # 是否返回检测置信度分数
    use_sherpa_onnx: bool = True             # 启用sherpa-onnx框架（False时使用原torch.hub方式）

    @property
    def effective_model_path(self) -> str:
        """
        获取实际使用的模型路径

        Returns:
            str: 实际的模型文件路径
        """
        if self.model_path:
            return self.model_path
        return os.path.join(self.model.default_path, self.model.model_name)

    def validate(self) -> bool:
        """
        验证VAD配置的有效性，包括模型路径检查和新增参数验证

        增强版验证，包含类型检查和范围验证

        Returns:
            bool: 配置是否有效

        Raises:
            ConfigurationError: 当配置无效时抛出详细错误信息
        """
        # 基础数值范围验证
        if not 0.0 <= self.threshold <= 1.0:
            raise ConfigurationError(f"语音检测阈值必须在0.0-1.0之间，当前值: {self.threshold}")

        if self.min_speech_duration_ms <= 0:
            raise ConfigurationError(f"最小语音持续时间必须为正数，当前值: {self.min_speech_duration_ms}ms")

        if self.min_silence_duration_ms <= 0:
            raise ConfigurationError(f"最小静音持续时间必须为正数，当前值: {self.min_silence_duration_ms}ms")

        if self.max_speech_duration_ms <= 0:
            raise ConfigurationError(f"最大语音持续时间必须为正数，当前值: {self.max_speech_duration_ms}ms")

        if self.min_speech_duration_ms >= self.max_speech_duration_ms:
            raise ConfigurationError(
                f"最小语音持续时间({self.min_speech_duration_ms}ms)不能大于等于"
                f"最大语音持续时间({self.max_speech_duration_ms}ms)"
            )

        if self.window_size_samples <= 0:
            raise ConfigurationError(f"窗口大小必须为正数，当前值: {self.window_size_samples}")

        if self.sample_rate <= 0:
            raise ConfigurationError(f"采样率必须为正数，当前值: {self.sample_rate}")

        # 类型验证
        if not isinstance(self.threshold, (int, float)):
            raise ConfigurationError(f"语音检测阈值必须为数值类型，当前类型: {type(self.threshold)}")

        if not isinstance(self.min_speech_duration_ms, (int, float)):
            raise ConfigurationError(f"最小语音持续时间必须为数值类型，当前类型: {type(self.min_speech_duration_ms)}")

        # 如果使用sherpa-onnx，检查模型文件路径
        if self.use_sherpa_onnx:
            model_file = self.effective_model_path
            if not os.path.exists(model_file):
                # 模型文件不存在，但这不算配置错误，稍后会尝试自动下载
                pass

        return True

    @property
    def min_speech_samples(self) -> int:
        """
        将最小语音持续时间转换为采样点数

        Returns:
            int: 最小语音持续时间对应的采样点数
        """
        return int((self.min_speech_duration_ms / 1000.0) * self.sample_rate)

    @property
    def min_silence_samples(self) -> int:
        """
        将最小静音持续时间转换为采样点数

        Returns:
            int: 最小静音持续时间对应的采样点数
        """
        return int((self.min_silence_duration_ms / 1000.0) * self.sample_rate)

    @property
    def max_speech_samples(self) -> int:
        """
        将最大语音持续时间转换为采样点数

        Returns:
            int: 最大语音持续时间对应的采样点数
        """
        return int((self.max_speech_duration_ms / 1000.0) * self.sample_rate)


@dataclass
class VadResult:
    """
    VAD检测结果数据类
    包含单次音频帧的语音活动检测结果和相关信息
    """
    is_speech: bool                              # 是否检测到语音
    confidence: float                            # 检测置信度 (0.0-1.0)
    timestamp: float                             # 检测时间戳 (Unix时间)
    duration_ms: float                           # 音频帧持续时间(毫秒)
    state: VadState                              # 当前VAD状态
    audio_data: Optional['np.ndarray'] = None    # 音频数据(仅语音段包含)
    speech_start_time: Optional[float] = None    # 语音开始时间戳(如果是语音开始)
    speech_end_time: Optional[float] = None      # 语音结束时间戳(如果是语音结束)

    @property
    def is_speech_start(self) -> bool:
        """
        检查是否为语音开始事件

        Returns:
            bool: 是否为语音开始的转换
        """
        return self.state == VadState.TRANSITION_TO_SPEECH

    @property
    def is_speech_end(self) -> bool:
        """
        检查是否为语音结束事件

        Returns:
            bool: 是否为语音结束的转换
        """
        return self.state == VadState.TRANSITION_TO_SILENCE

    @property
    def is_stable_speech(self) -> bool:
        """
        检查是否为稳定的语音状态

        Returns:
            bool: 是否为持续的语音活动
        """
        return self.state == VadState.SPEECH

    @property
    def is_stable_silence(self) -> bool:
        """
        检查是否为稳定的静音状态

        Returns:
            bool: 是否为持续的静音
        """
        return self.state == VadState.SILENCE


@dataclass
class SpeechSegment:
    """
    语音段信息类
    记录完整语音段的开始、结束时间及相关统计信息
    """
    start_time: float                            # 语音段开始时间 (Unix时间戳)
    end_time: Optional[float] = None             # 语音段结束时间 (Unix时间戳)
    duration_ms: Optional[float] = None          # 语音段持续时间(毫秒)
    confidence_scores: List[float] = None        # 置信度分数列表
    is_complete: bool = False                    # 语音段是否已完成

    def __post_init__(self):
        """
        初始化派生字段
        确保置信度分数列表不为空
        """
        if self.confidence_scores is None:
            self.confidence_scores = []

    @property
    def average_confidence(self) -> float:
        """
        计算平均置信度分数

        Returns:
            float: 语音段的平均置信度
        """
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores) / len(self.confidence_scores)

    @property
    def max_confidence(self) -> float:
        """
        获取最高置信度分数

        Returns:
            float: 语音段的最高置信度
        """
        if not self.confidence_scores:
            return 0.0
        return max(self.confidence_scores)

    @property
    def calculated_duration_ms(self) -> Optional[float]:
        """
        根据开始和结束时间计算持续时间

        Returns:
            Optional[float]: 计算得出的持续时间(毫秒)，如果语音段未完成则返回None
        """
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def add_confidence_score(self, score: float) -> None:
        """
        向语音段添加新的置信度分数

        Args:
            score: 置信度分数 (0.0-1.0)
        """
        self.confidence_scores.append(score)

    def finalize(self, end_time: float) -> None:
        """
        完成语音段，设置结束时间并计算最终持续时间

        Args:
            end_time: 语音段结束时间戳
        """
        self.end_time = end_time
        self.duration_ms = self.calculated_duration_ms
        self.is_complete = True


@dataclass
class VadStatistics:
    """
    VAD处理统计信息类
    记录语音检测过程中的各种统计数据和性能指标
    """
    total_audio_duration_ms: float = 0.0        # 处理的音频总时长(毫秒)
    speech_duration_ms: float = 0.0             # 检测到的语音总时长(毫秒)
    silence_duration_ms: float = 0.0            # 检测到的静音总时长(毫秒)
    speech_segments_count: int = 0              # 语音段总数
    false_positives: int = 0                    # 误检次数(静音被误识别为语音)
    processing_time_ms: float = 0.0             # 处理耗时(毫秒)

    @property
    def speech_ratio(self) -> float:
        """
        计算语音占总音频的比例

        Returns:
            float: 语音时长占总时长的比例 (0.0-1.0)
        """
        if self.total_audio_duration_ms <= 0:
            return 0.0
        return self.speech_duration_ms / self.total_audio_duration_ms

    @property
    def silence_ratio(self) -> float:
        """
        计算静音占总音频的比例

        Returns:
            float: 静音时长占总时长的比例 (0.0-1.0)
        """
        if self.total_audio_duration_ms <= 0:
            return 0.0
        return self.silence_duration_ms / self.total_audio_duration_ms

    @property
    def average_segment_duration_ms(self) -> float:
        """
        计算平均语音段持续时间

        Returns:
            float: 平均语音段时长(毫秒)
        """
        if self.speech_segments_count <= 0:
            return 0.0
        return self.speech_duration_ms / self.speech_segments_count

    @property
    def processing_real_time_factor(self) -> float:
        """
        计算处理速度相对于实时的倍数
        值小于1表示快于实时，大于1表示慢于实时

        Returns:
            float: 处理时间与音频时长的比值
        """
        if self.total_audio_duration_ms <= 0:
            return 0.0
        return self.processing_time_ms / self.total_audio_duration_ms

    def update_audio_duration(self, duration_ms: float) -> None:
        """
        更新处理的音频总时长

        Args:
            duration_ms: 要添加的音频时长(毫秒)
        """
        self.total_audio_duration_ms += duration_ms

    def update_speech_duration(self, duration_ms: float) -> None:
        """
        更新检测到的语音总时长

        Args:
            duration_ms: 要添加的语音时长(毫秒)
        """
        self.speech_duration_ms += duration_ms

    def update_silence_duration(self, duration_ms: float) -> None:
        """
        更新检测到的静音总时长

        Args:
            duration_ms: 要添加的静音时长(毫秒)
        """
        self.silence_duration_ms += duration_ms

    def increment_speech_segments(self) -> None:
        """
        增加语音段计数
        """
        self.speech_segments_count += 1

    def increment_false_positives(self) -> None:
        """
        增加误检计数
        """
        self.false_positives += 1

    def update_processing_time(self, time_ms: float) -> None:
        """
        更新处理耗时

        Args:
            time_ms: 要添加的处理时间(毫秒)
        """
        self.processing_time_ms += time_ms


class VadError(Exception):
    """
    VAD错误基类
    所有VAD相关异常的基础类
    """
    pass


class ModelLoadError(VadError):
    """
    VAD模型加载错误
    当Silero VAD模型下载或加载失败时抛出
    """
    pass


class DetectionError(VadError):
    """
    VAD检测错误
    当音频检测过程中发生错误时抛出
    """
    pass


class ConfigurationError(VadError):
    """
    VAD配置错误
    当VAD配置参数无效或缺少依赖时抛出
    """
    pass