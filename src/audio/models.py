"""
音频数据模型和类型定义 (Audio Data Models and Types)

定义音频设备、配置和音频数据的数据结构
- 音频设备信息和管理
- 音频配置参数和验证
- 音频数据块和流状态
- 音频格式和源类型枚举
- 自定义异常类型定义
"""

from dataclasses import dataclass
from typing import List, Optional, Union
from enum import Enum
import numpy as np


class AudioSourceType(Enum):
    """音频源类型枚举 (Audio Source Types)

    定义支持的音频输入源类型
    """
    MICROPHONE = "microphone"      # 麦克风输入
    SYSTEM_AUDIO = "system_audio"  # 系统音频输入（立体声混音）


class AudioFormat(Enum):
    """音频格式规范 (Audio Format Specifications)

    定义支持的音频格式，包含位深度和采样率信息
    """
    PCM_16_16000 = "pcm_16_16000"  # 16位PCM, 16kHz (语音识别推荐)
    PCM_16_44100 = "pcm_16_44100"  # 16位PCM, 44.1kHz (CD质量)
    PCM_16_48000 = "pcm_16_48000"  # 16位PCM, 48kHz (DVD质量)
    PCM_32_16000 = "pcm_32_16000"  # 32位PCM, 16kHz (高质量语音)
    PCM_32_44100 = "pcm_32_44100"  # 32位PCM, 44.1kHz (高保真)
    PCM_32_48000 = "pcm_32_48000"  # 32位PCM, 48kHz (专业级)


@dataclass
class AudioDevice:
    """音频设备信息类 (Audio Device Information)

    存储音频设备的详细信息，包括索引、名称、声道数等
    """
    index: int                      # 设备索引号
    name: str                       # 设备名称
    max_input_channels: int         # 最大输入声道数
    max_output_channels: int        # 最大输出声道数
    default_sample_rate: float      # 默认采样率
    is_default_input: bool = False  # 是否为默认输入设备
    is_default_output: bool = False # 是否为默认输出设备

    @property
    def is_input_device(self) -> bool:
        """检查设备是否支持音频输入

        Returns:
            bool: 如果设备支持输入返回True
        """
        return self.max_input_channels > 0

    @property
    def is_output_device(self) -> bool:
        """检查设备是否支持音频输出

        Returns:
            bool: 如果设备支持输出返回True
        """
        return self.max_output_channels > 0

    def __str__(self) -> str:
        """返回设备的字符串表示"""
        return f"AudioDevice(index={self.index}, name='{self.name}', channels={self.max_input_channels})"


@dataclass
class AudioConfig:
    """音频捕获配置类 (Audio Capture Configuration)

    包含音频捕获所需的所有配置参数
    """
    source_type: AudioSourceType = AudioSourceType.MICROPHONE  # 音频源类型
    device_index: Optional[int] = None     # 设备索引（None表示使用默认设备）
    sample_rate: int = 16000               # 采样率（Hz），16kHz适合语音识别
    channels: int = 1                      # 声道数（1=单声道，2=立体声）
    chunk_size: int = 1024                 # 音频块大小（帧数）
    format_type: AudioFormat = AudioFormat.PCM_16_16000  # 音频格式
    buffer_duration_ms: int = 100          # 缓冲区持续时间（毫秒）

    @property
    def device_id(self) -> Optional[int]:
        """设备ID别名，向后兼容性支持

        Returns:
            Optional[int]: 设备索引号
        """
        return self.device_index

    @device_id.setter
    def device_id(self, value: Optional[int]) -> None:
        """设置设备ID别名

        Args:
            value: 设备索引号
        """
        self.device_index = value

    @property
    def bytes_per_sample(self) -> int:
        """根据音频格式计算每个样本的字节数

        Returns:
            int: 字节数（16位=2字节，32位=4字节）
        """
        if "16" in self.format_type.value:
            return 2  # 16位 = 2字节
        elif "32" in self.format_type.value:
            return 4  # 32位 = 4字节
        else:
            return 2  # 默认16位

    @property
    def frames_per_buffer(self) -> int:
        """从块大小计算缓冲区的帧数

        Returns:
            int: 每个缓冲区的帧数
        """
        return self.chunk_size

    def validate(self) -> bool:
        """验证音频配置的有效性

        Returns:
            bool: 配置有效返回True，否则返回False
        """
        if self.sample_rate <= 0:          # 采样率必须大于0
            return False
        if self.channels <= 0:             # 声道数必须大于0
            return False
        if self.chunk_size <= 0:           # 块大小必须大于0
            return False
        if self.buffer_duration_ms <= 0:   # 缓冲时间必须大于0
            return False
        return True


@dataclass
class AudioChunk:
    """音频数据块类 (Audio Data Chunk)

    表示一个音频数据片段，包含原始音频数据和元信息
    """
    data: np.ndarray     # 音频数据数组（numpy数组）
    timestamp: float     # 时间戳（Unix时间）
    sample_rate: int     # 采样率（Hz）
    channels: int        # 声道数
    duration_ms: float   # 持续时间（毫秒）

    @property
    def length_samples(self) -> int:
        """获取音频块中的样本数量

        Returns:
            int: 样本数量
        """
        return len(self.data)

    @property
    def length_bytes(self) -> int:
        """获取音频数据的字节大小

        Returns:
            int: 字节大小
        """
        return self.data.nbytes

    def to_mono(self) -> 'AudioChunk':
        """将立体声音频转换为单声道

        如果已经是单声道，则直接返回当前对象。
        立体声转换通过对左右声道求平均值实现。

        Returns:
            AudioChunk: 单声道音频块
        """
        if self.channels == 1:
            return self

        # 将立体声转换为单声道，通过对声道求平均值
        mono_data = np.mean(self.data.reshape(-1, self.channels), axis=1)

        return AudioChunk(
            data=mono_data,
            timestamp=self.timestamp,
            sample_rate=self.sample_rate,
            channels=1,
            duration_ms=self.duration_ms
        )

    def normalize(self) -> 'AudioChunk':
        """将音频数据标准化到 [-1.0, 1.0] 范围

        将整型音频数据转换为浮点型并标准化到标准范围，
        便于后续的音频处理和分析。

        Returns:
            AudioChunk: 标准化后的音频块
        """
        if self.data.dtype == np.float32:
            # 已经是浮点型，假设已标准化
            return self

        # 转换为float32并标准化
        if self.data.dtype == np.int16:
            # 16位整型: -32768 到 32767 -> -1.0 到 1.0
            normalized_data = self.data.astype(np.float32) / 32768.0
        elif self.data.dtype == np.int32:
            # 32位整型: -2147483648 到 2147483647 -> -1.0 到 1.0
            normalized_data = self.data.astype(np.float32) / 2147483648.0
        else:
            # 假设已经在正确范围内
            normalized_data = self.data.astype(np.float32)

        return AudioChunk(
            data=normalized_data,
            timestamp=self.timestamp,
            sample_rate=self.sample_rate,
            channels=self.channels,
            duration_ms=self.duration_ms
        )


@dataclass
class AudioStreamStatus:
    """音频流状态信息类 (Audio Stream Status Information)

    包含音频流的运行状态、延迟和性能信息
    """
    is_active: bool       # 流是否处于活动状态
    is_stopped: bool      # 流是否已停止
    input_latency: float  # 输入延迟（秒）
    output_latency: float # 输出延迟（秒）
    sample_rate: float    # 当前采样率（Hz）
    cpu_load: float       # CPU负载（0.0-1.0）

    @property
    def total_latency(self) -> float:
        """计算总延迟（输入延迟 + 输出延迟）

        Returns:
            float: 总延迟时间（秒）
        """
        return self.input_latency + self.output_latency

    @property
    def is_healthy(self) -> bool:
        """检查音频流是否处于健康状态

        健康状态的标准：
        - 流处于活动状态
        - 流未停止
        - CPU负载低于80%
        - 总延迟低于100ms

        Returns:
            bool: 流健康返回True，否则返回False
        """
        return (
            self.is_active and              # 流必须是活动的
            not self.is_stopped and         # 流不能停止
            self.cpu_load < 0.8 and         # CPU负载必须低于80%
            self.total_latency < 0.1         # 总延迟必须低于100ms
        )


class AudioCaptureError(Exception):
    """音频捕获基础异常类 (Base Audio Capture Exception)

    所有音频捕获相关异常的基类
    """
    pass


class DeviceNotFoundError(AudioCaptureError):
    """设备未找到异常 (Device Not Found Error)

    当指定的音频设备不存在或无法访问时抛出
    """
    pass


class StreamError(AudioCaptureError):
    """音频流异常 (Audio Stream Error)

    音频流创建、启动或操作过程中发生错误时抛出
    """
    pass


class ConfigurationError(AudioCaptureError):
    """音频配置异常 (Audio Configuration Error)

    音频配置参数无效或不支持时抛出
    """
    pass