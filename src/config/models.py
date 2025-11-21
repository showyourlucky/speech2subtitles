"""
配置数据模型

定义系统配置的数据结构和验证逻辑
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import uuid
import os


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
    SUPPORTED_INPUT_SOURCES: List[str] = ["microphone", "system"]  # 实时音频输入源


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


def migrate_legacy_config(config: 'Config') -> None:
    """
    迁移旧版配置到新格式

    Args:
        config: 配置对象
    """
    import logging
    logger = logging.getLogger(__name__)

    # 如果没有模型方案,从 model_path 创建默认方案
    if not config.model_profiles or len(config.model_profiles) == 0:
        logger.info("检测到旧版配置格式(缺少model_profiles),开始迁移...")

        default_profile = ModelProfile.create_default_profile(
            model_path=config.model_path if config.model_path else ""
        )

        config.model_profiles = {"default": default_profile}
        config.active_model_profile_id = "default"

        logger.info("配置迁移完成，已创建默认模型方案")

    # 验证活跃方案ID存在
    if config.active_model_profile_id not in config.model_profiles:
        logger.warning(f"活跃方案ID '{config.active_model_profile_id}' 不存在，重置为默认方案")

        if "default" in config.model_profiles:
            config.active_model_profile_id = "default"
        else:
            # 使用第一个可用方案
            config.active_model_profile_id = next(iter(config.model_profiles.keys()))

    # 同步 model_path 字段（向后兼容）
    active_profile = config.get_active_model_profile()
    config.model_path = active_profile.model_path


@dataclass
class VadProfile:
    """
    VAD配置方案数据类

    包含完整的VAD参数配置,支持保存和切换多个配置方案
    所有参数与VadConfig模型和detector.py初始化逻辑保持一致
    """
    # 方案基本信息
    profile_name: str                                    # 方案名称 (如"默认"、"安静环境"、"嘈杂环境")
    profile_id: str 
    # VAD核心参数 (对应 VadConfig 和 detector.py:228-263)
    threshold: float = VadConstants.DEFAULT_THRESHOLD    # 语音检测阈值 (0.0-1.0)
    min_speech_duration_ms: float = 100.0                # 最小语音持续时间(毫秒)
    min_silence_duration_ms: float = 150.0               # 最小静音持续时间(毫秒)
    max_speech_duration_ms: float = 30000.0              # 最大语音持续时间(毫秒),默认30秒
    sample_rate: int = AudioConstants.DEFAULT_SAMPLE_RATE # 音频采样率(Hz)

    # 模型配置
    model: str = "silero_vad"                            # 模型类型: "silero_vad" 或 "ten_vad"
    model_path: Optional[str] = None                     # 自定义模型路径,None时使用默认路径
    use_sherpa_onnx: bool = True                         # 是否使用sherpa-onnx框架

    # 窗口配置
    window_size_samples: int = 512                       # 音频处理窗口大小(采样点数)
    
    # 在实例化 VadConfigProfile 后手动设置 profile_id
    def __post_init__(self):
        self.profile_id = f"profile_{self.profile_name}"

    def validate(self) -> None:
        """验证VAD方案配置的有效性"""
        # 验证阈值范围
        if not VadConstants.MIN_THRESHOLD <= self.threshold <= VadConstants.MAX_THRESHOLD:
            raise ValueError(
                f"VAD阈值必须在{VadConstants.MIN_THRESHOLD}-{VadConstants.MAX_THRESHOLD}之间: "
                f"{self.threshold}"
            )

        # 验证持续时间参数
        if self.min_speech_duration_ms <= 0:
            raise ValueError(f"最小语音持续时间必须为正数: {self.min_speech_duration_ms}ms")

        if self.min_silence_duration_ms <= 0:
            raise ValueError(f"最小静音持续时间必须为正数: {self.min_silence_duration_ms}ms")

        if self.max_speech_duration_ms <= 0:
            raise ValueError(f"最大语音持续时间必须为正数: {self.max_speech_duration_ms}ms")

        if self.min_speech_duration_ms >= self.max_speech_duration_ms:
            raise ValueError(
                f"最小语音持续时间({self.min_speech_duration_ms}ms)不能大于等于"
                f"最大语音持续时间({self.max_speech_duration_ms}ms)"
            )

        # 验证采样率
        if self.sample_rate not in AudioConstants.SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                f"不支持的采样率: {self.sample_rate}, "
                f"支持的采样率: {AudioConstants.SUPPORTED_SAMPLE_RATES}"
            )

        # 验证模型类型
        if self.model not in ["silero_vad", "ten_vad"]:
            raise ValueError(f"不支持的模型类型: {self.model}, 支持: silero_vad, ten_vad")

        # 验证方案名称
        if not self.profile_name or not self.profile_name.strip():
            raise ValueError("VAD方案名称不能为空")

    def to_vad_config(self):
        """
        转换为VadConfig对象

        Returns:
            VadConfig: VAD配置对象,用于初始化检测器
        """
        from src.vad.models import VadConfig, VadModel

        # 将字符串模型名转换为VadModel枚举
        vad_model = VadModel.SILERO if self.model == "silero_vad" else VadModel.TEN_VAD

        return VadConfig(
            model=vad_model,
            model_path=self.model_path,
            threshold=self.threshold,
            min_speech_duration_ms=self.min_speech_duration_ms,
            min_silence_duration_ms=self.min_silence_duration_ms,
            max_speech_duration_ms=self.max_speech_duration_ms,
            window_size_samples=self.window_size_samples,
            sample_rate=self.sample_rate,
            return_confidence=True,
            use_sherpa_onnx=self.use_sherpa_onnx
        )

    @staticmethod
    def create_default_profile() -> 'VadProfile':
        """
        创建默认VAD方案

        Returns:
            VadProfile: 默认配置方案
        """
        return VadProfile(
            profile_name="默认",
            profile_id="default",
            threshold=VadConstants.DEFAULT_THRESHOLD,
            min_speech_duration_ms=100.0,
            min_silence_duration_ms=150.0,
            max_speech_duration_ms=30000.0,
            sample_rate=AudioConstants.DEFAULT_SAMPLE_RATE,
            model="silero_vad",
            use_sherpa_onnx=True,
            window_size_samples=512
        )


@dataclass
class ModelProfile:
    """
    模型配置方案数据类

    存储单个语音识别模型的完整配置信息,支持保存和切换多个模型配置
    """
    # 基本信息
    profile_id: str = field(default_factory=lambda: f"model_{uuid.uuid4().hex[:8]}")  # 方案唯一ID
    profile_name: str = "未命名模型"                                                    # 方案名称

    # 模型路径(必需)
    model_path: str = ""                                                              # 模型文件路径

    # 可选元数据
    description: Optional[str] = None                                                 # 模型描述信息
    supported_languages: Optional[List[str]] = None                                   # 支持的语言列表 ["zh", "en", "ja", "ko", "yue"]

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)                        # 创建时间
    updated_at: datetime = field(default_factory=datetime.now)                        # 最后更新时间

    def validate(self) -> None:
        """
        验证模型配置的有效性

        Raises:
            ValueError: 配置无效时抛出异常
        """
        # 验证方案名称
        if not self.profile_name or not self.profile_name.strip():
            raise ValueError("模型方案名称不能为空")

        # 验证模型路径
        if not self.model_path or not self.model_path.strip():
            raise ValueError("模型文件路径不能为空")

        model_path = Path(self.model_path)
        if not model_path.exists():
            raise ValueError(f"模型文件不存在: {self.model_path}")

        if not model_path.is_file():
            raise ValueError(f"模型路径不是文件: {self.model_path}")

        if model_path.suffix.lower() not in ModelConstants.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"不支持的模型文件格式: {model_path.suffix}, "
                f"支持的格式: {ModelConstants.SUPPORTED_EXTENSIONS}"
            )

    
        # 验证文件权限
        if not os.access(model_path, os.R_OK):
            raise ValueError(f"没有读取权限: {self.model_path}")

    @staticmethod
    def create_default_profile(model_path: str = "") -> 'ModelProfile':
        """
        创建默认模型方案

        Args:
            model_path: 模型文件路径

        Returns:
            ModelProfile: 默认配置方案
        """
        return ModelProfile(
            profile_id="default",
            profile_name="默认",
            model_path=model_path,
            description="系统默认模型配置",
            supported_languages=["zh", "en", "ja", "ko", "yue"]
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典(用于序列化)

        Returns:
            Dict[str, Any]: 字典形式的配置数据
        """
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "model_path": self.model_path,
            "description": self.description,
            "supported_languages": self.supported_languages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ModelProfile':
        """
        从字典创建实例(用于反序列化)

        Args:
            data: 字典形式的配置数据

        Returns:
            ModelProfile: 模型配置方案实例
        """
        return ModelProfile(
            profile_id=data.get("profile_id", f"model_{uuid.uuid4().hex[:8]}"),
            profile_name=data.get("profile_name", "未命名模型"),
            model_path=data.get("model_path", ""),
            description=data.get("description"),
            supported_languages=data.get("supported_languages"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now()
        )


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
    vad_sensitivity: float = VadConstants.DEFAULT_SENSITIVITY # VAD敏感度 (0.0-1.0) [已废弃,保留用于向后兼容]
    output_format: str = OutputConstants.DEFAULT_FORMAT      # 输出格式类型
    device_id: Optional[int] = None                          # 音频设备ID

    # 音频配置
    sample_rate: int = AudioConstants.DEFAULT_SAMPLE_RATE    # 采样率
    chunk_size: int = AudioConstants.DEFAULT_CHUNK_SIZE     # 音频块大小
    channels: int = AudioConstants.DEFAULT_CHANNELS         # 音频声道数

    # VAD配置 (旧版字段,保留用于向后兼容)
    vad_window_size: float = VadConstants.DEFAULT_WINDOW_SIZE # VAD窗口大小(秒) [已废弃]
    vad_threshold: float = VadConstants.DEFAULT_THRESHOLD    # VAD阈值 [已废弃]

    # VAD方案管理 (新增)
    vad_profiles: Dict[str, VadProfile] = field(default_factory=dict)  # VAD配置方案字典 {profile_id: VadProfile}
    active_vad_profile_id: str = "default"                   # 当前活跃的VAD方案ID

    # 模型方案管理 (新增)
    model_profiles: Dict[str, ModelProfile] = field(default_factory=dict)  # 模型配置方案字典 {profile_id: ModelProfile}
    active_model_profile_id: str = "default"                 # 当前活跃的模型方案ID

    # 输出配置
    show_confidence: bool = True                             # 显示置信度
    show_timestamp: bool = True                              # 显示时间戳

    # 媒体文件转字幕配置 (新增)
    input_file: Optional[List[str]] = field(default=None)   # 输入文件/文件列表/目录路径
    output_dir: Optional[str] = None                         # 字幕输出目录
    subtitle_format: str = SubtitleConstants.DEFAULT_FORMAT  # 字幕格式 (srt/vtt/ass)
    keep_temp: bool = False                                  # 保留临时音频文件
    verbose: bool = False                                    # 显示详细日志

    # 字幕显示配置 (新增)
    subtitle_display: SubtitleDisplayConfig = field(default_factory=SubtitleDisplayConfig)  # 字幕显示配置

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

        # 验证输入模式: --input-source {microphone,system} | --input-file FILE
        # 规则1: 必须提供其中之一
        if self.input_source is None and self.input_file is None:
            raise ValueError(
                "必须提供以下参数之一：\n"
                "  - 实时模式: --input-source {microphone,system}\n"
                "  - 离线模式: --input-file FILE"
            )

        # 规则2: 两者互斥，不能同时提供
        if self.input_source is not None and self.input_file is not None:
            raise ValueError(
                "参数冲突：--input-source 和 --input-file 互斥，请只提供其中之一\n"
                "  - 实时转录: 使用 --input-source {microphone,system}\n"
                "  - 离线转录: 使用 --input-file FILE"
            )

        # 规则3: 如果提供了 input_source，验证其有效性
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

        # 验证VAD方案配置
        if not self.vad_profiles:
            # 如果没有VAD方案,自动创建默认方案
            self.vad_profiles = {"default": VadProfile.create_default_profile()}

        # 验证活跃方案ID存在
        if self.active_vad_profile_id not in self.vad_profiles:
            raise ValueError(
                f"活跃的VAD方案ID '{self.active_vad_profile_id}' 不存在，"
                f"可用方案: {list(self.vad_profiles.keys())}"
            )

        # 验证所有VAD方案
        for profile_id, profile in self.vad_profiles.items():
            try:
                profile.validate()
            except Exception as e:
                raise ValueError(f"VAD方案 '{profile_id}' 配置无效: {e}")

        # 验证模型方案配置（先迁移旧配置）
        migrate_legacy_config(self)

        # 验证活跃模型方案ID存在
        if self.active_model_profile_id not in self.model_profiles:
            raise ValueError(
                f"活跃的模型方案ID '{self.active_model_profile_id}' 不存在，"
                f"可用方案: {list(self.model_profiles.keys())}"
            )

        # 验证所有模型方案
        for profile_id, profile in self.model_profiles.items():
            try:
                profile.validate()
            except Exception as e:
                raise ValueError(f"模型方案 '{profile_id}' 配置无效: {e}")

        # 同步 model_path 字段（向后兼容）
        active_profile = self.get_active_model_profile()
        self.model_path = active_profile.model_path

    def __post_init__(self):
        """初始化后验证"""
        # 注意: 在配置未完全加载前不验证,由ConfigManager调用validate()
        # 如果 vad_profiles 为空,初始化为包含默认方案的字典
        if not self.vad_profiles:
            self.vad_profiles = {"default": VadProfile.create_default_profile()}

        # 如果 model_profiles 为空,初始化为包含默认方案的字典
        if not self.model_profiles:
            self.model_profiles = {"default": ModelProfile.create_default_profile(self.model_path)}

    def is_realtime_mode(self) -> bool:
        """判断是否为实时转录模式（麦克风或系统音频）"""
        return self.input_source is not None and self.input_source in ["microphone", "system"]

    def is_file_mode(self) -> bool:
        """判断是否为离线文件模式"""
        return self.input_file is not None

    def get_active_vad_profile(self) -> VadProfile:
        """
        获取当前活跃的VAD方案

        Returns:
            VadProfile: 当前活跃的VAD配置方案

        Raises:
            ValueError: 如果活跃方案不存在
        """
        if self.active_vad_profile_id not in self.vad_profiles:
            raise ValueError(f"活跃的VAD方案 '{self.active_vad_profile_id}' 不存在")
        return self.vad_profiles[self.active_vad_profile_id]

    def set_active_vad_profile(self, profile_id: str) -> None:
        """
        设置活跃的VAD方案

        Args:
            profile_id: VAD方案ID

        Raises:
            ValueError: 如果方案不存在
        """
        if profile_id not in self.vad_profiles:
            raise ValueError(f"VAD方案 '{profile_id}' 不存在")
        self.active_vad_profile_id = profile_id

    def get_active_model_profile(self) -> ModelProfile:
        """
        获取当前活跃的模型方案

        Returns:
            ModelProfile: 当前活跃的模型配置方案

        Raises:
            ValueError: 如果活跃方案不存在
        """
        if self.active_model_profile_id not in self.model_profiles:
            raise ValueError(f"活跃的模型方案 '{self.active_model_profile_id}' 不存在")
        return self.model_profiles[self.active_model_profile_id]

    def set_active_model_profile(self, profile_id: str) -> None:
        """
        设置活跃的模型方案

        Args:
            profile_id: 模型方案ID

        Raises:
            ValueError: 如果方案不存在
        """
        if profile_id not in self.model_profiles:
            raise ValueError(f"模型方案 '{profile_id}' 不存在")
        self.active_model_profile_id = profile_id

        # 同步更新 model_path (用于向后兼容)
        self.model_path = self.model_profiles[profile_id].model_path


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