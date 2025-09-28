"""
配置数据模型

定义系统配置的数据结构和验证逻辑
"""

from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path


# 系统常量定义
class AudioConstants:
    """音频相关常量"""
    SUPPORTED_SAMPLE_RATES: List[int] = [8000, 16000, 22050, 44100, 48000]
    DEFAULT_SAMPLE_RATE: int = 16000
    MIN_CHUNK_SIZE: int = 1
    MAX_CHUNK_SIZE: int = 8192
    DEFAULT_CHUNK_SIZE: int = 1024
    DEFAULT_CHANNELS: int = 1


class VadConstants:
    """VAD相关常量"""
    MIN_SENSITIVITY: float = 0.0
    MAX_SENSITIVITY: float = 1.0
    DEFAULT_SENSITIVITY: float = 0.5
    MIN_THRESHOLD: float = 0.0
    MAX_THRESHOLD: float = 1.0
    DEFAULT_THRESHOLD: float = 0.5
    MIN_WINDOW_SIZE: float = 0.1
    MAX_WINDOW_SIZE: float = 2.0
    DEFAULT_WINDOW_SIZE: float = 0.512


class ModelConstants:
    """模型相关常量"""
    SUPPORTED_EXTENSIONS: List[str] = ['.onnx', '.bin']
    SUPPORTED_INPUT_SOURCES: List[str] = ["microphone", "system"]


class OutputConstants:
    """输出相关常量"""
    SUPPORTED_FORMATS: List[str] = ["text", "json"]
    DEFAULT_FORMAT: str = "text"


@dataclass
class Config:
    """系统配置数据类"""

    # 核心配置
    model_path: str                                          # sense-voice模型文件路径
    input_source: str                                        # "microphone" 或 "system"

    # 可选配置
    use_gpu: bool = True                                     # 是否使用GPU加速
    vad_sensitivity: float = VadConstants.DEFAULT_SENSITIVITY # VAD敏感度 (0.0-1.0)
    output_format: str = OutputConstants.DEFAULT_FORMAT      # 输出格式类型
    device_id: Optional[int] = None                          # 音频设备ID

    # 音频配置
    sample_rate: int = AudioConstants.DEFAULT_SAMPLE_RATE    # 采样率
    chunk_size: int = AudioConstants.DEFAULT_CHUNK_SIZE     # 音频块大小
    channels: int = AudioConstants.DEFAULT_CHANNELS         # 音频声道数

    # VAD配置
    vad_window_size: float = VadConstants.DEFAULT_WINDOW_SIZE # VAD窗口大小(秒)
    vad_threshold: float = VadConstants.DEFAULT_THRESHOLD    # VAD阈值

    # 输出配置
    show_confidence: bool = True                             # 显示置信度
    show_timestamp: bool = True                              # 显示时间戳

    def validate(self) -> None:
        """验证配置的有效性"""

        # 验证模型路径
        model_path = Path(self.model_path)
        if not model_path.exists():
            raise ValueError(f"模型文件不存在: {self.model_path}")

        if not model_path.suffix.lower() in ModelConstants.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"不支持的模型文件格式: {model_path.suffix}，"
                f"支持的格式: {ModelConstants.SUPPORTED_EXTENSIONS}"
            )

        # 验证输入源
        if self.input_source not in ModelConstants.SUPPORTED_INPUT_SOURCES:
            raise ValueError(
                f"不支持的输入源: {self.input_source}，"
                f"支持的输入源: {ModelConstants.SUPPORTED_INPUT_SOURCES}"
            )

        # 验证VAD敏感度
        if not VadConstants.MIN_SENSITIVITY <= self.vad_sensitivity <= VadConstants.MAX_SENSITIVITY:
            raise ValueError(
                f"VAD敏感度必须在{VadConstants.MIN_SENSITIVITY}-{VadConstants.MAX_SENSITIVITY}之间: "
                f"{self.vad_sensitivity}"
            )

        # 验证采样率
        if self.sample_rate not in AudioConstants.SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                f"不支持的采样率: {self.sample_rate}，"
                f"支持的采样率: {AudioConstants.SUPPORTED_SAMPLE_RATES}"
            )

        # 验证音频块大小
        if not AudioConstants.MIN_CHUNK_SIZE <= self.chunk_size <= AudioConstants.MAX_CHUNK_SIZE:
            raise ValueError(
                f"音频块大小必须在{AudioConstants.MIN_CHUNK_SIZE}-{AudioConstants.MAX_CHUNK_SIZE}之间: "
                f"{self.chunk_size}"
            )

        # 验证VAD阈值
        if not VadConstants.MIN_THRESHOLD <= self.vad_threshold <= VadConstants.MAX_THRESHOLD:
            raise ValueError(
                f"VAD阈值必须在{VadConstants.MIN_THRESHOLD}-{VadConstants.MAX_THRESHOLD}之间: "
                f"{self.vad_threshold}"
            )

        # 验证VAD窗口大小
        if not VadConstants.MIN_WINDOW_SIZE <= self.vad_window_size <= VadConstants.MAX_WINDOW_SIZE:
            raise ValueError(
                f"VAD窗口大小必须在{VadConstants.MIN_WINDOW_SIZE}-{VadConstants.MAX_WINDOW_SIZE}秒之间: "
                f"{self.vad_window_size}"
            )

        # 验证输出格式
        if self.output_format not in OutputConstants.SUPPORTED_FORMATS:
            raise ValueError(
                f"不支持的输出格式: {self.output_format}，"
                f"支持的格式: {OutputConstants.SUPPORTED_FORMATS}"
            )

    def __post_init__(self):
        """初始化后验证"""
        self.validate()


@dataclass
class AudioDevice:
    """音频设备信息"""

    id: int                    # 设备ID
    name: str                 # 设备名称
    channels: int             # 声道数
    sample_rate: int          # 支持的采样率
    is_input: bool           # 是否为输入设备
    is_default: bool = False # 是否为默认设备

    def __str__(self) -> str:
        """设备信息字符串表示"""
        device_type = "输入" if self.is_input else "输出"
        default_mark = " [默认]" if self.is_default else ""
        return f"ID:{self.id} - {self.name} ({device_type}, {self.channels}声道, {self.sample_rate}Hz){default_mark}"