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


class SubtitleConstants:
    """字幕相关常量"""
    SUPPORTED_FORMATS: List[str] = ["srt", "vtt", "ass"]
    DEFAULT_FORMAT: str = "srt"


class SubtitleDisplayConstants:
    """字幕显示相关常量"""
    SUPPORTED_POSITIONS: List[str] = ["top", "center", "bottom"]
    DEFAULT_POSITION: str = "bottom"
    MIN_FONT_SIZE: int = 12
    MAX_FONT_SIZE: int = 72
    DEFAULT_FONT_SIZE: int = 24
    MIN_OPACITY: float = 0.1
    MAX_OPACITY: float = 1.0
    DEFAULT_OPACITY: float = 0.8
    DEFAULT_MAX_DISPLAY_TIME: float = 5.0
    DEFAULT_FONT_FAMILY: str = "Microsoft YaHei"


@dataclass
class SubtitleDisplayConfig:
    """字幕显示配置数据类"""
    enabled: bool = False                                    # 是否启用字幕显示
    position: str = SubtitleDisplayConstants.DEFAULT_POSITION # 字幕位置
    font_size: int = SubtitleDisplayConstants.DEFAULT_FONT_SIZE # 字体大小
    font_family: str = SubtitleDisplayConstants.DEFAULT_FONT_FAMILY # 字体
    opacity: float = SubtitleDisplayConstants.DEFAULT_OPACITY # 窗口透明度
    max_display_time: float = SubtitleDisplayConstants.DEFAULT_MAX_DISPLAY_TIME # 最大显示时间
    text_color: str = "#FFFFFF"                              # 文字颜色 (白色)
    background_color: str = "#000000"                        # 背景颜色 (黑色)

    def validate(self) -> None:
        """验证字幕显示配置的有效性"""
        # 验证字幕位置
        if self.position not in SubtitleDisplayConstants.SUPPORTED_POSITIONS:
            raise ValueError(
                f"不支持的字幕位置: {self.position}，"
                f"支持的位置: {SubtitleDisplayConstants.SUPPORTED_POSITIONS}"
            )

        # 验证字体大小
        if not (SubtitleDisplayConstants.MIN_FONT_SIZE <= self.font_size <= SubtitleDisplayConstants.MAX_FONT_SIZE):
            raise ValueError(
                f"字体大小超出范围: {self.font_size}，"
                f"允许范围: {SubtitleDisplayConstants.MIN_FONT_SIZE}-{SubtitleDisplayConstants.MAX_FONT_SIZE}"
            )

        # 验证透明度
        if not (SubtitleDisplayConstants.MIN_OPACITY <= self.opacity <= SubtitleDisplayConstants.MAX_OPACITY):
            raise ValueError(
                f"透明度超出范围: {self.opacity}，"
                f"允许范围: {SubtitleDisplayConstants.MIN_OPACITY}-{SubtitleDisplayConstants.MAX_OPACITY}"
            )

        # 验证显示时间
        if self.max_display_time <= 0:
            raise ValueError(f"最大显示时间必须大于0: {self.max_display_time}")


@dataclass
class Config:
    """系统配置数据类"""

    # 核心配置
    model_path: str                                          # sense-voice模型文件路径
    input_source: Optional[str] = None                       # "microphone" 或 "system" (与input_file互斥)

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

    # 媒体文件转字幕配置 (新增)
    input_file: Optional[List[str]] = None                   # 输入文件/文件列表/目录路径
    output_dir: Optional[str] = None                         # 字幕输出目录
    subtitle_format: str = SubtitleConstants.DEFAULT_FORMAT  # 字幕格式 (srt/vtt/ass)
    keep_temp: bool = False                                  # 保留临时音频文件
    verbose: bool = False                                    # 显示详细日志

    # 字幕显示配置 (新增)
    subtitle_display: SubtitleDisplayConfig = SubtitleDisplayConfig()  # 字幕显示配置

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

        # 验证输入源 - input_source和input_file至少提供一个
        if self.input_source is None and self.input_file is None:
            raise ValueError(
                "必须提供 --input-source (实时音频) 或 --input-file (离线文件) 之一"
            )

        # 验证输入源互斥
        if self.input_source is not None and self.input_file is not None:
            raise ValueError(
                "--input-source 和 --input-file 不能同时使用，"
                "请选择实时转录模式或离线文件模式"
            )

        # 验证实时音频输入源
        if self.input_source is not None:
            if self.input_source not in ModelConstants.SUPPORTED_INPUT_SOURCES:
                raise ValueError(
                    f"不支持的输入源: {self.input_source}，"
                    f"支持的输入源: {ModelConstants.SUPPORTED_INPUT_SOURCES}"
                )

        # 验证离线文件输入
        if self.input_file is not None:
            if not isinstance(self.input_file, list):
                self.input_file = [self.input_file]

            for file_path in self.input_file:
                path = Path(file_path)
                if not path.exists():
                    raise ValueError(f"输入文件/目录不存在: {file_path}")

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

        # 验证字幕格式
        if self.subtitle_format not in SubtitleConstants.SUPPORTED_FORMATS:
            raise ValueError(
                f"不支持的字幕格式: {self.subtitle_format}，"
                f"支持的格式: {SubtitleConstants.SUPPORTED_FORMATS}"
            )

        # 验证字幕显示配置
        if self.subtitle_display:
            self.subtitle_display.validate()

    def __post_init__(self):
        """初始化后验证"""
        # 注意: 在配置未完全加载前不验证,由ConfigManager调用validate()
        pass

    def is_realtime_mode(self) -> bool:
        """判断是否为实时转录模式"""
        return self.input_source is not None

    def is_file_mode(self) -> bool:
        """判断是否为离线文件模式"""
        return self.input_file is not None


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