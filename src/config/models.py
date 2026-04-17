"""
配置数据模型

定义系统配置的数据结构和验证逻辑
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG_SCHEMA_VERSION = "2.0"


# 系统常量定义
class AudioConstants:
    """音频相关常量"""
    SUPPORTED_SAMPLE_RATES: list[int] = [8000, 16000, 22050, 44100, 48000]
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
    SUPPORTED_EXTENSIONS: list[str] = ['.onnx', '.bin']
    SUPPORTED_INPUT_SOURCES: list[str] = ["microphone", "system"]  # 实时音频输入源
    SUPPORTED_TRANSCRIPTION_MODEL_TYPES: list[str] = [
        "sense_voice",
        "sherpa_onnx_streaming",
        "sherpa_onnx_offline",
        "qwen_asr",
    ]


class OutputConstants:
    """输出相关常量"""
    SUPPORTED_FORMATS: list[str] = ["text", "json"]
    DEFAULT_FORMAT: str = "text"


class SubtitleConstants:
    """字幕相关常量"""
    SUPPORTED_FORMATS: list[str] = ["srt", "vtt", "ass"]
    DEFAULT_FORMAT: str = "srt"
    # 离线字幕切分/合并参数默认值
    DEFAULT_STREAM_MERGE_TARGET_DURATION: float = 15.0
    DEFAULT_STREAM_LONG_SEGMENT_THRESHOLD: float = 8.0
    DEFAULT_STREAM_MERGE_MAX_GAP: float = 0.6
    DEFAULT_MAX_SUBTITLE_DURATION: float = 5.0
    DEFAULT_TRANSCRIBE_PER_VAD_SEGMENT: bool = True


class SubtitleDisplayConstants:
    """字幕显示相关常量"""
    SUPPORTED_POSITIONS: list[str] = ["top", "center", "bottom"]
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
    model_path: str | None = None                     # 自定义模型路径,None时使用默认路径
    use_sherpa_onnx: bool = True                         # 是否使用sherpa-onnx框架

    # 窗口配置
    window_size_samples: int = 512                       # 音频处理窗口大小(采样点数)

    # 在实例化 VadConfigProfile 后手动设置 profile_id
    def __post_init__(self):
        if not self.profile_id:
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
    model_type: str = "sense_voice"                                                   # 转录模型类型

    # qwen3_asr参数（仅在 model_type=QWEN_ASR 时生效）
    hotwords: str = ""                                                                # 热词（逗号分隔）
    num_threads: int = 2                                                              # 推理线程数
    feature_dim: int = 128                                                            # 特征维度
    max_total_len: int = 512                                                          # 最大总长度
    max_new_tokens: int = 128                                                         # 最大新生成token
    temperature: float = 1.0                                                          # 采样温度
    top_p: float = 0.8                                                                # top-p采样
    seed: int = 48                                                                    # 随机种子

    # 可选元数据
    description: str | None = None                                                 # 模型描述信息
    supported_languages: list[str] | None = None                                   # 支持的语言列表 ["zh", "en", "ja", "ko", "yue"]

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

        # 仅校验模型路径是否存在（支持文件或目录）
        if not self.model_path or not self.model_path.strip():
            raise ValueError("模型路径不能为空")

        model_path = Path(self.model_path)
        if not model_path.exists():
            raise ValueError(f"模型路径不存在: {self.model_path}")

        # 验证模型类型
        if self.model_type.lower() not in [item.lower() for item in ModelConstants.SUPPORTED_TRANSCRIPTION_MODEL_TYPES]:
            raise ValueError(
                f"不支持的转录模型类型: {self.model_type}, "
                f"支持: {ModelConstants.SUPPORTED_TRANSCRIPTION_MODEL_TYPES}"
            )

        # 仅在Qwen ASR时校验专属参数
        if self.model_type == "qwen_asr":
            if self.num_threads <= 0:
                raise ValueError(f"num_threads必须大于0: {self.num_threads}")
            if self.feature_dim <= 0:
                raise ValueError(f"feature_dim必须大于0: {self.feature_dim}")
            if self.max_total_len <= 0:
                raise ValueError(f"max_total_len必须大于0: {self.max_total_len}")
            if self.max_new_tokens <= 0:
                raise ValueError(f"max_new_tokens必须大于0: {self.max_new_tokens}")
            if not (0.0 < self.top_p <= 1.0):
                raise ValueError(f"top_p必须在(0,1]区间: {self.top_p}")
            if self.temperature <= 0:
                raise ValueError(f"temperature必须大于0: {self.temperature}")

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
            model_type="sense_voice",
            description="系统默认模型配置",
            supported_languages=["zh", "en", "ja", "ko", "yue"]
        )

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典(用于序列化)

        Returns:
            Dict[str, Any]: 字典形式的配置数据
        """
        data = {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "model_path": self.model_path,
            "model_type": self.model_type,
            "description": self.description,
            "supported_languages": self.supported_languages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

        # 仅在QWEN_ASR时序列化专属参数，避免污染其它模型配置
        if self.model_type == "qwen_asr":
            data.update({
                "hotwords": self.hotwords,
                "num_threads": self.num_threads,
                "feature_dim": self.feature_dim,
                "max_total_len": self.max_total_len,
                "max_new_tokens": self.max_new_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "seed": self.seed,
            })

        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> 'ModelProfile':
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
            model_type=data.get("model_type", "sense_voice"),
            hotwords=data.get("hotwords", ""),
            num_threads=data.get("num_threads", 2),
            feature_dim=data.get("feature_dim", 128),
            max_total_len=data.get("max_total_len", 512),
            max_new_tokens=data.get("max_new_tokens", 128),
            temperature=data.get("temperature", 1.0),
            top_p=data.get("top_p", 0.8),
            seed=data.get("seed", 48),
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
class RuntimeConfig:
    """运行时配置分区"""
    input_source: str | None = None
    input_file: list[str] | None = None
    use_gpu: bool = True
    transcription_language: str | None = None
    model_profiles: dict[str, ModelProfile] = field(default_factory=dict)
    active_model_profile_id: str = "default"


@dataclass
class AudioConfigSettings:
    """音频配置分区"""
    sample_rate: int = AudioConstants.DEFAULT_SAMPLE_RATE
    chunk_size: int = AudioConstants.DEFAULT_CHUNK_SIZE
    channels: int = AudioConstants.DEFAULT_CHANNELS
    device_id: int | None = None


@dataclass
class VadConfigSettings:
    """VAD配置分区"""
    vad_profiles: dict[str, VadProfile] = field(default_factory=dict)
    active_vad_profile_id: str = "default"


@dataclass
class OutputConfigSettings:
    """输出配置分区"""
    output_format: str = OutputConstants.DEFAULT_FORMAT
    show_confidence: bool = True
    show_timestamp: bool = True


@dataclass
class SubtitleConfigSettings:
    """字幕相关配置分区"""
    output_dir: str | None = None
    subtitle_format: str = SubtitleConstants.DEFAULT_FORMAT
    keep_temp: bool = False
    verbose: bool = False
    transcribe_per_vad_segment: bool = SubtitleConstants.DEFAULT_TRANSCRIBE_PER_VAD_SEGMENT
    # 离线文件模式下的 stream 合并和字幕切分策略
    stream_merge_target_duration: float = SubtitleConstants.DEFAULT_STREAM_MERGE_TARGET_DURATION
    stream_long_segment_threshold: float = SubtitleConstants.DEFAULT_STREAM_LONG_SEGMENT_THRESHOLD
    stream_merge_max_gap: float = SubtitleConstants.DEFAULT_STREAM_MERGE_MAX_GAP
    max_subtitle_duration: float = SubtitleConstants.DEFAULT_MAX_SUBTITLE_DURATION
    subtitle_display: SubtitleDisplayConfig = field(default_factory=SubtitleDisplayConfig)


@dataclass
class Config:
    """系统配置数据类 (schema v2)"""
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    audio: AudioConfigSettings = field(default_factory=AudioConfigSettings)
    vad: VadConfigSettings = field(default_factory=VadConfigSettings)
    output: OutputConfigSettings = field(default_factory=OutputConfigSettings)
    subtitle: SubtitleConfigSettings = field(default_factory=SubtitleConfigSettings)

    def __post_init__(self):
        """初始化后处理，补齐默认方案"""
        self._ensure_default_profiles()

    # ===== 兼容字段代理（旧字段访问方式仍可用） =====
    @property
    def model_path(self) -> str:
        active_profile = self.get_active_model_profile()
        return active_profile.model_path

    @model_path.setter
    def model_path(self, value: str) -> None:
        if not self.runtime.model_profiles:
            self.runtime.model_profiles = {
                "default": ModelProfile.create_default_profile(model_path=value or "")
            }
            self.runtime.active_model_profile_id = "default"
            return
        active_profile = self.get_active_model_profile()
        active_profile.model_path = value or ""

    @property
    def input_source(self) -> str | None:
        return self.runtime.input_source

    @input_source.setter
    def input_source(self, value: str | None) -> None:
        self.runtime.input_source = value

    @property
    def input_file(self) -> list[str] | None:
        return self.runtime.input_file

    @input_file.setter
    def input_file(self, value: list[str] | None) -> None:
        self.runtime.input_file = value

    @property
    def use_gpu(self) -> bool:
        return self.runtime.use_gpu

    @use_gpu.setter
    def use_gpu(self, value: bool) -> None:
        self.runtime.use_gpu = value

    @property
    def transcription_language(self) -> str | None:
        return self.runtime.transcription_language

    @transcription_language.setter
    def transcription_language(self, value: str | None) -> None:
        self.runtime.transcription_language = value

    @property
    def model_profiles(self) -> dict[str, ModelProfile]:
        return self.runtime.model_profiles

    @model_profiles.setter
    def model_profiles(self, value: dict[str, ModelProfile]) -> None:
        self.runtime.model_profiles = value

    @property
    def active_model_profile_id(self) -> str:
        return self.runtime.active_model_profile_id

    @active_model_profile_id.setter
    def active_model_profile_id(self, value: str) -> None:
        self.runtime.active_model_profile_id = value

    @property
    def sample_rate(self) -> int:
        return self.audio.sample_rate

    @sample_rate.setter
    def sample_rate(self, value: int) -> None:
        self.audio.sample_rate = value

    @property
    def chunk_size(self) -> int:
        return self.audio.chunk_size

    @chunk_size.setter
    def chunk_size(self, value: int) -> None:
        self.audio.chunk_size = value

    @property
    def channels(self) -> int:
        return self.audio.channels

    @channels.setter
    def channels(self, value: int) -> None:
        self.audio.channels = value

    @property
    def device_id(self) -> int | None:
        return self.audio.device_id

    @device_id.setter
    def device_id(self, value: int | None) -> None:
        self.audio.device_id = value

    @property
    def vad_profiles(self) -> dict[str, VadProfile]:
        return self.vad.vad_profiles

    @vad_profiles.setter
    def vad_profiles(self, value: dict[str, VadProfile]) -> None:
        self.vad.vad_profiles = value

    @property
    def active_vad_profile_id(self) -> str:
        return self.vad.active_vad_profile_id

    @active_vad_profile_id.setter
    def active_vad_profile_id(self, value: str) -> None:
        self.vad.active_vad_profile_id = value

    @property
    def output_format(self) -> str:
        return self.output.output_format

    @output_format.setter
    def output_format(self, value: str) -> None:
        self.output.output_format = value

    @property
    def show_confidence(self) -> bool:
        return self.output.show_confidence

    @show_confidence.setter
    def show_confidence(self, value: bool) -> None:
        self.output.show_confidence = value

    @property
    def show_timestamp(self) -> bool:
        return self.output.show_timestamp

    @show_timestamp.setter
    def show_timestamp(self, value: bool) -> None:
        self.output.show_timestamp = value

    @property
    def output_dir(self) -> str | None:
        return self.subtitle.output_dir

    @output_dir.setter
    def output_dir(self, value: str | None) -> None:
        self.subtitle.output_dir = value

    @property
    def subtitle_format(self) -> str:
        return self.subtitle.subtitle_format

    @subtitle_format.setter
    def subtitle_format(self, value: str) -> None:
        self.subtitle.subtitle_format = value

    @property
    def keep_temp(self) -> bool:
        return self.subtitle.keep_temp

    @keep_temp.setter
    def keep_temp(self, value: bool) -> None:
        self.subtitle.keep_temp = value

    @property
    def verbose(self) -> bool:
        return self.subtitle.verbose

    @verbose.setter
    def verbose(self, value: bool) -> None:
        self.subtitle.verbose = value

    @property
    def transcribe_per_vad_segment(self) -> bool:
        return self.subtitle.transcribe_per_vad_segment

    @transcribe_per_vad_segment.setter
    def transcribe_per_vad_segment(self, value: bool) -> None:
        self.subtitle.transcribe_per_vad_segment = value

    @property
    def stream_merge_target_duration(self) -> float:
        return self.subtitle.stream_merge_target_duration

    @stream_merge_target_duration.setter
    def stream_merge_target_duration(self, value: float) -> None:
        self.subtitle.stream_merge_target_duration = value

    @property
    def stream_long_segment_threshold(self) -> float:
        return self.subtitle.stream_long_segment_threshold

    @stream_long_segment_threshold.setter
    def stream_long_segment_threshold(self, value: float) -> None:
        self.subtitle.stream_long_segment_threshold = value

    @property
    def stream_merge_max_gap(self) -> float:
        return self.subtitle.stream_merge_max_gap

    @stream_merge_max_gap.setter
    def stream_merge_max_gap(self, value: float) -> None:
        self.subtitle.stream_merge_max_gap = value

    @property
    def max_subtitle_duration(self) -> float:
        return self.subtitle.max_subtitle_duration

    @max_subtitle_duration.setter
    def max_subtitle_duration(self, value: float) -> None:
        self.subtitle.max_subtitle_duration = value

    @property
    def subtitle_display(self) -> SubtitleDisplayConfig:
        return self.subtitle.subtitle_display

    @subtitle_display.setter
    def subtitle_display(self, value: SubtitleDisplayConfig) -> None:
        self.subtitle.subtitle_display = value

    # 兼容旧VAD字段：映射到当前活跃VAD方案
    @property
    def vad_threshold(self) -> float:
        return self.get_active_vad_profile().threshold

    @vad_threshold.setter
    def vad_threshold(self, value: float) -> None:
        profile = self.get_active_vad_profile()
        profile.threshold = value

    @property
    def vad_window_size(self) -> float:
        profile = self.get_active_vad_profile()
        if self.sample_rate <= 0:
            return VadConstants.DEFAULT_WINDOW_SIZE
        return profile.window_size_samples / float(self.sample_rate)

    @vad_window_size.setter
    def vad_window_size(self, value: float) -> None:
        profile = self.get_active_vad_profile()
        window_samples = max(1, int(value * max(1, self.sample_rate)))
        profile.window_size_samples = window_samples

    @property
    def vad_sensitivity(self) -> float:
        # 兼容字段，等价映射到阈值
        return self.vad_threshold

    @vad_sensitivity.setter
    def vad_sensitivity(self, value: float) -> None:
        self.vad_threshold = value

    # ===== 行为方法 =====
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
        self._ensure_default_profiles()
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
        self._ensure_default_profiles()
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

    def _ensure_default_profiles(self) -> None:
        """确保默认VAD/模型方案存在"""
        if not self.vad_profiles:
            self.vad_profiles = {"default": VadProfile.create_default_profile()}
        if not self.model_profiles:
            self.model_profiles = {"default": ModelProfile.create_default_profile("")}
            self.active_model_profile_id = "default"

    def _normalize_input_source(self) -> str | None:
        """归一化 input_source，统一空白字符串为 None。"""
        input_source = self.input_source
        if input_source is None:
            return None
        if not isinstance(input_source, str):
            raise ValueError("input_source 必须是字符串或 None")

        normalized_source = input_source.strip()
        return normalized_source or None

    def _normalize_input_file(self) -> list[str] | None:
        """归一化 input_file，统一输出为非空字符串列表或 None。"""
        input_file = self.input_file
        if input_file is None:
            return None

        # 兼容单文件字符串输入
        if isinstance(input_file, str):
            stripped_file = input_file.strip()
            return [stripped_file] if stripped_file else None

        if not isinstance(input_file, list):
            raise ValueError("input_file 必须是字符串、字符串列表或 None")

        cleaned_files: list[str] = []
        for file_path in input_file:
            if not isinstance(file_path, str):
                raise ValueError("input_file 必须是字符串列表")
            stripped_file = file_path.strip()
            if stripped_file:
                cleaned_files.append(stripped_file)
        return cleaned_files or None

    def validate(self) -> None:
        """验证配置的有效性"""
        # 先归一化输入参数，减少后续校验分支复杂度
        self.input_source = self._normalize_input_source()
        self.input_file = self._normalize_input_file()

        has_input_source = self.input_source is not None
        has_input_file = self.input_file is not None

        # 验证输入模式: --input-source {microphone,system} | --input-file FILE
        # 规则1: 必须提供其中之一
        if not has_input_source and not has_input_file:
            raise ValueError(
                "必须提供以下参数之一：\n"
                "  - 实时模式: --input-source {microphone,system}\n"
                "  - 离线模式: --input-file FILE"
            )

        # 规则2: 两者互斥，不能同时提供
        if has_input_source and has_input_file:
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
            for file_path in self.input_file:
                path = Path(file_path)
                if not path.exists():
                    raise ValueError(f"输入文件/目录不存在: {file_path}")

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

        # 验证离线字幕切分/合并参数
        if self.stream_merge_target_duration <= 0:
            raise ValueError(f"stream_merge_target_duration 必须大于0: {self.stream_merge_target_duration}")
        if self.stream_long_segment_threshold <= 0:
            raise ValueError(f"stream_long_segment_threshold 必须大于0: {self.stream_long_segment_threshold}")
        if self.stream_merge_max_gap < 0:
            raise ValueError(f"stream_merge_max_gap 不能小于0: {self.stream_merge_max_gap}")
        if self.max_subtitle_duration <= 0:
            raise ValueError(f"max_subtitle_duration 必须大于0: {self.max_subtitle_duration}")
        if not isinstance(self.transcribe_per_vad_segment, bool):
            raise ValueError(
                f"transcribe_per_vad_segment 必须为布尔值: {self.transcribe_per_vad_segment}"
            )

        # 确保默认方案
        self._ensure_default_profiles()

        # 验证活跃方案ID存在
        if self.active_vad_profile_id not in self.vad_profiles:
            raise ValueError(
                f"活跃的VAD方案ID '{self.active_vad_profile_id}' 不存在，"
                f"可用方案: {list(self.vad_profiles.keys())}"
            )

        if self.active_model_profile_id not in self.model_profiles:
            raise ValueError(
                f"活跃的模型方案ID '{self.active_model_profile_id}' 不存在，"
                f"可用方案: {list(self.model_profiles.keys())}"
            )

        # 验证所有VAD方案
        for profile_id, profile in self.vad_profiles.items():
            try:
                profile.validate()
            except Exception as e:
                raise ValueError(f"VAD方案 '{profile_id}' 配置无效: {e}")

        # 验证所有模型方案
        for profile_id, profile in self.model_profiles.items():
            try:
                profile.validate()
            except Exception as e:
                raise ValueError(f"模型方案 '{profile_id}' 配置无效: {e}")

        # 同步 model_path 字段（向后兼容）
        active_profile = self.get_active_model_profile()
        active_profile.model_path = active_profile.model_path

    @staticmethod
    def create_default() -> 'Config':
        """创建默认配置"""
        config = Config()
        config.model_path = "models/sherpa-onnx-sense-voice-funasr-nano-2025-12-17/model.onnx"
        config.input_source = ""
        return config

    def to_dict_v2(self) -> dict[str, Any]:
        """输出schema v2的配置字典"""
        return {
            "runtime": {
                "input_source": self.input_source,
                "input_file": self.input_file,
                "use_gpu": self.use_gpu,
                "transcription_language": self.transcription_language,
                "model": {
                    "active_profile_id": self.active_model_profile_id,
                    "profiles": {
                        profile_id: profile.to_dict()
                        for profile_id, profile in self.model_profiles.items()
                    }
                }
            },
            "audio": {
                "sample_rate": self.sample_rate,
                "chunk_size": self.chunk_size,
                "channels": self.channels,
                "device_id": self.device_id
            },
            "vad": {
                "active_profile_id": self.active_vad_profile_id,
                "profiles": {
                    profile_id: {
                        "profile_name": profile.profile_name,
                        "profile_id": profile.profile_id,
                        "threshold": profile.threshold,
                        "min_speech_duration_ms": profile.min_speech_duration_ms,
                        "min_silence_duration_ms": profile.min_silence_duration_ms,
                        "max_speech_duration_ms": profile.max_speech_duration_ms,
                        "sample_rate": profile.sample_rate,
                        "model": profile.model,
                        "model_path": profile.model_path,
                        "use_sherpa_onnx": profile.use_sherpa_onnx,
                        "window_size_samples": profile.window_size_samples
                    }
                    for profile_id, profile in self.vad_profiles.items()
                }
            },
            "output": {
                "format": self.output_format,
                "show_confidence": self.show_confidence,
                "show_timestamp": self.show_timestamp
            },
            "subtitle": {
                "file": {
                    "output_dir": self.output_dir,
                    "format": self.subtitle_format,
                    "keep_temp": self.keep_temp,
                    "verbose": self.verbose,
                    "transcribe_per_vad_segment": self.transcribe_per_vad_segment,
                    "stream_merge_target_duration": self.stream_merge_target_duration,
                    "stream_long_segment_threshold": self.stream_long_segment_threshold,
                    "stream_merge_max_gap": self.stream_merge_max_gap,
                    "max_subtitle_duration": self.max_subtitle_duration,
                },
                "display": {
                    "enabled": self.subtitle_display.enabled,
                    "position": self.subtitle_display.position,
                    "font_size": self.subtitle_display.font_size,
                    "font_family": self.subtitle_display.font_family,
                    "opacity": self.subtitle_display.opacity,
                    "max_display_time": self.subtitle_display.max_display_time,
                    "text_color": self.subtitle_display.text_color,
                    "background_color": self.subtitle_display.background_color
                }
            }
        }

    def to_dict(self) -> dict[str, Any]:
        """兼容接口：默认输出schema v2字典"""
        return self.to_dict_v2()

    @staticmethod
    def from_dict(config_dict: dict[str, Any]) -> 'Config':
        """根据字典结构自动解析"""
        if "runtime" in config_dict or "audio" in config_dict or "vad" in config_dict:
            return Config.from_dict_v2(config_dict)
        return Config.from_legacy_dict(config_dict)

    @staticmethod
    def from_dict_v2(config_dict: dict[str, Any]) -> 'Config':
        """从schema v2字典构建配置"""
        runtime_dict = config_dict.get("runtime", {})
        audio_dict = config_dict.get("audio", {})
        vad_dict = config_dict.get("vad", {})
        output_dict = config_dict.get("output", {})
        subtitle_dict = config_dict.get("subtitle", {})

        # 模型方案
        model_profiles = {}
        model_section = runtime_dict.get("model", {})
        model_profiles_dict = model_section.get("profiles", {})
        for profile_id, profile_data in model_profiles_dict.items():
            model_profiles[profile_id] = ModelProfile.from_dict(profile_data)

        # VAD方案
        vad_profiles = {}
        vad_profiles_dict = vad_dict.get("profiles", {})
        for profile_id, profile_data in vad_profiles_dict.items():
            vad_profiles[profile_id] = VadProfile(
                profile_name=profile_data.get("profile_name", "未命名"),
                profile_id=profile_data.get("profile_id", profile_id),
                threshold=profile_data.get("threshold", 0.5),
                min_speech_duration_ms=profile_data.get("min_speech_duration_ms", 100.0),
                min_silence_duration_ms=profile_data.get("min_silence_duration_ms", 150.0),
                max_speech_duration_ms=profile_data.get("max_speech_duration_ms", 30000.0),
                sample_rate=profile_data.get("sample_rate", 16000),
                model=profile_data.get("model", "silero_vad"),
                model_path=profile_data.get("model_path"),
                use_sherpa_onnx=profile_data.get("use_sherpa_onnx", True),
                window_size_samples=profile_data.get("window_size_samples", 512)
            )

        subtitle_display_dict = subtitle_dict.get("display", {})
        subtitle_display = SubtitleDisplayConfig(
            enabled=subtitle_display_dict.get("enabled", False),
            position=subtitle_display_dict.get("position", "bottom"),
            font_size=subtitle_display_dict.get("font_size", 24),
            font_family=subtitle_display_dict.get("font_family", "Microsoft YaHei"),
            opacity=subtitle_display_dict.get("opacity", 0.8),
            max_display_time=subtitle_display_dict.get("max_display_time", 5.0),
            text_color=subtitle_display_dict.get("text_color", "#FFFFFF"),
            background_color=subtitle_display_dict.get("background_color", "#000000"),
        )

        config = Config(
            runtime=RuntimeConfig(
                input_source=runtime_dict.get("input_source"),
                input_file=runtime_dict.get("input_file"),
                use_gpu=runtime_dict.get("use_gpu", True),
                transcription_language=runtime_dict.get("transcription_language"),
                model_profiles=model_profiles,
                active_model_profile_id=model_section.get("active_profile_id", "default")
            ),
            audio=AudioConfigSettings(
                sample_rate=audio_dict.get("sample_rate", 16000),
                chunk_size=audio_dict.get("chunk_size", 1024),
                channels=audio_dict.get("channels", 1),
                device_id=audio_dict.get("device_id")
            ),
            vad=VadConfigSettings(
                vad_profiles=vad_profiles,
                active_vad_profile_id=vad_dict.get("active_profile_id", "default")
            ),
            output=OutputConfigSettings(
                output_format=output_dict.get("format", "text"),
                show_confidence=output_dict.get("show_confidence", True),
                show_timestamp=output_dict.get("show_timestamp", True)
            ),
            subtitle=SubtitleConfigSettings(
                output_dir=subtitle_dict.get("file", {}).get("output_dir"),
                subtitle_format=subtitle_dict.get("file", {}).get("format", "srt"),
                keep_temp=subtitle_dict.get("file", {}).get("keep_temp", False),
                verbose=subtitle_dict.get("file", {}).get("verbose", False),
                transcribe_per_vad_segment=subtitle_dict.get("file", {}).get(
                    "transcribe_per_vad_segment",
                    SubtitleConstants.DEFAULT_TRANSCRIBE_PER_VAD_SEGMENT,
                ),
                stream_merge_target_duration=subtitle_dict.get("file", {}).get(
                    "stream_merge_target_duration",
                    SubtitleConstants.DEFAULT_STREAM_MERGE_TARGET_DURATION,
                ),
                stream_long_segment_threshold=subtitle_dict.get("file", {}).get(
                    "stream_long_segment_threshold",
                    SubtitleConstants.DEFAULT_STREAM_LONG_SEGMENT_THRESHOLD,
                ),
                stream_merge_max_gap=subtitle_dict.get("file", {}).get(
                    "stream_merge_max_gap",
                    SubtitleConstants.DEFAULT_STREAM_MERGE_MAX_GAP,
                ),
                max_subtitle_duration=subtitle_dict.get("file", {}).get(
                    "max_subtitle_duration",
                    SubtitleConstants.DEFAULT_MAX_SUBTITLE_DURATION,
                ),
                subtitle_display=subtitle_display
            )
        )

        # 兼容：如果runtime里仅提供model_path
        model_path = runtime_dict.get("model_path")
        if model_path and not config.model_profiles:
            config.model_profiles = {"default": ModelProfile.create_default_profile(model_path)}
            config.active_model_profile_id = "default"

        config._ensure_default_profiles()
        # 兼容：允许在 v2 结构中混用旧版扁平字段（用于 CLI 显式覆盖）。
        # 仅当键显式存在时才覆盖，避免影响文件中的激活方案选择与默认值。
        if "model_path" in config_dict and config_dict.get("model_path") is not None:
            config.model_path = config_dict.get("model_path")
        if "input_source" in config_dict:
            config.input_source = config_dict.get("input_source")
        if "input_file" in config_dict:
            config.input_file = config_dict.get("input_file")
        if "use_gpu" in config_dict:
            config.use_gpu = config_dict.get("use_gpu")
        if "transcription_language" in config_dict:
            config.transcription_language = config_dict.get("transcription_language")

        if "sample_rate" in config_dict and config_dict.get("sample_rate") is not None:
            config.sample_rate = config_dict.get("sample_rate")
        if "chunk_size" in config_dict and config_dict.get("chunk_size") is not None:
            config.chunk_size = config_dict.get("chunk_size")
        if "channels" in config_dict and config_dict.get("channels") is not None:
            config.channels = config_dict.get("channels")
        if "device_id" in config_dict:
            config.device_id = config_dict.get("device_id")

        if "vad_threshold" in config_dict and config_dict.get("vad_threshold") is not None:
            config.vad_threshold = config_dict.get("vad_threshold")
        elif "vad_sensitivity" in config_dict and config_dict.get("vad_sensitivity") is not None:
            config.vad_sensitivity = config_dict.get("vad_sensitivity")
        if "vad_window_size" in config_dict and config_dict.get("vad_window_size") is not None:
            config.vad_window_size = config_dict.get("vad_window_size")

        if "output_format" in config_dict and config_dict.get("output_format") is not None:
            config.output_format = config_dict.get("output_format")
        if "show_confidence" in config_dict:
            config.show_confidence = config_dict.get("show_confidence")
        if "show_timestamp" in config_dict:
            config.show_timestamp = config_dict.get("show_timestamp")

        if "output_dir" in config_dict:
            config.output_dir = config_dict.get("output_dir")
        if "subtitle_format" in config_dict and config_dict.get("subtitle_format") is not None:
            config.subtitle_format = config_dict.get("subtitle_format")
        if "keep_temp" in config_dict:
            config.keep_temp = config_dict.get("keep_temp")
        if "verbose" in config_dict:
            config.verbose = config_dict.get("verbose")
        if "transcribe_per_vad_segment" in config_dict and config_dict.get("transcribe_per_vad_segment") is not None:
            config.transcribe_per_vad_segment = config_dict.get("transcribe_per_vad_segment")
        if "stream_merge_target_duration" in config_dict and config_dict.get("stream_merge_target_duration") is not None:
            config.stream_merge_target_duration = config_dict.get("stream_merge_target_duration")
        if "stream_long_segment_threshold" in config_dict and config_dict.get("stream_long_segment_threshold") is not None:
            config.stream_long_segment_threshold = config_dict.get("stream_long_segment_threshold")
        if "stream_merge_max_gap" in config_dict and config_dict.get("stream_merge_max_gap") is not None:
            config.stream_merge_max_gap = config_dict.get("stream_merge_max_gap")
        if "max_subtitle_duration" in config_dict and config_dict.get("max_subtitle_duration") is not None:
            config.max_subtitle_duration = config_dict.get("max_subtitle_duration")

        subtitle_display_flat = config_dict.get("subtitle_display")
        if isinstance(subtitle_display_flat, dict):
            if "enabled" in subtitle_display_flat:
                config.subtitle_display.enabled = subtitle_display_flat.get("enabled")
            if "position" in subtitle_display_flat and subtitle_display_flat.get("position") is not None:
                config.subtitle_display.position = subtitle_display_flat.get("position")
            if "font_size" in subtitle_display_flat and subtitle_display_flat.get("font_size") is not None:
                config.subtitle_display.font_size = subtitle_display_flat.get("font_size")
            if "font_family" in subtitle_display_flat and subtitle_display_flat.get("font_family") is not None:
                config.subtitle_display.font_family = subtitle_display_flat.get("font_family")
            if "opacity" in subtitle_display_flat and subtitle_display_flat.get("opacity") is not None:
                config.subtitle_display.opacity = subtitle_display_flat.get("opacity")
            if "max_display_time" in subtitle_display_flat and subtitle_display_flat.get("max_display_time") is not None:
                config.subtitle_display.max_display_time = subtitle_display_flat.get("max_display_time")
            if "text_color" in subtitle_display_flat and subtitle_display_flat.get("text_color") is not None:
                config.subtitle_display.text_color = subtitle_display_flat.get("text_color")
            if "background_color" in subtitle_display_flat and subtitle_display_flat.get("background_color") is not None:
                config.subtitle_display.background_color = subtitle_display_flat.get("background_color")

        return config

    @staticmethod
    def from_legacy_dict(config_dict: dict[str, Any]) -> 'Config':
        """从旧版(扁平字段)配置字典构建配置"""
        subtitle_display_dict = config_dict.get("subtitle_display", {})
        subtitle_display = SubtitleDisplayConfig(
            enabled=subtitle_display_dict.get("enabled", False),
            position=subtitle_display_dict.get("position", "bottom"),
            font_size=subtitle_display_dict.get("font_size", 24),
            font_family=subtitle_display_dict.get("font_family", "Microsoft YaHei"),
            opacity=subtitle_display_dict.get("opacity", 0.8),
            max_display_time=subtitle_display_dict.get("max_display_time", 5.0),
            text_color=subtitle_display_dict.get("text_color", "#FFFFFF"),
            background_color=subtitle_display_dict.get("background_color", "#000000"),
        )

        vad_profiles_dict = config_dict.get("vad_profiles", {})
        vad_profiles = {}
        if vad_profiles_dict:
            for profile_id, profile_data in vad_profiles_dict.items():
                vad_profiles[profile_id] = VadProfile(
                    profile_name=profile_data.get("profile_name", "未命名"),
                    profile_id=profile_data.get("profile_id", profile_id),
                    threshold=profile_data.get("threshold", 0.5),
                    min_speech_duration_ms=profile_data.get("min_speech_duration_ms", 100.0),
                    min_silence_duration_ms=profile_data.get("min_silence_duration_ms", 150.0),
                    max_speech_duration_ms=profile_data.get("max_speech_duration_ms", 30000.0),
                    sample_rate=profile_data.get("sample_rate", 16000),
                    model=profile_data.get("model", "silero_vad"),
                    model_path=profile_data.get("model_path"),
                    use_sherpa_onnx=profile_data.get("use_sherpa_onnx", True),
                    window_size_samples=profile_data.get("window_size_samples", 512)
                )
        else:
            vad_profiles = {"default": VadProfile.create_default_profile()}
            vad_profiles["default"].threshold = config_dict.get("vad_threshold", 0.5)

        model_profiles_dict = config_dict.get("model_profiles", {})
        model_profiles = {}
        if model_profiles_dict:
            for profile_id, profile_data in model_profiles_dict.items():
                model_profiles[profile_id] = ModelProfile.from_dict(profile_data)

        config = Config(
            runtime=RuntimeConfig(
                input_source=config_dict.get("input_source"),
                input_file=config_dict.get("input_file"),
                use_gpu=config_dict.get("use_gpu", True),
                transcription_language=config_dict.get("transcription_language"),
                model_profiles=model_profiles,
                active_model_profile_id=config_dict.get("active_model_profile_id", "default")
            ),
            audio=AudioConfigSettings(
                sample_rate=config_dict.get("sample_rate", 16000),
                chunk_size=config_dict.get("chunk_size", 1024),
                channels=config_dict.get("channels", 1),
                device_id=config_dict.get("device_id")
            ),
            vad=VadConfigSettings(
                vad_profiles=vad_profiles,
                active_vad_profile_id=config_dict.get("active_vad_profile_id", "default")
            ),
            output=OutputConfigSettings(
                output_format=config_dict.get("output_format", "text"),
                show_confidence=config_dict.get("show_confidence", True),
                show_timestamp=config_dict.get("show_timestamp", True)
            ),
            subtitle=SubtitleConfigSettings(
                output_dir=config_dict.get("output_dir"),
                subtitle_format=config_dict.get("subtitle_format", "srt"),
                keep_temp=config_dict.get("keep_temp", False),
                verbose=config_dict.get("verbose", False),
                transcribe_per_vad_segment=config_dict.get(
                    "transcribe_per_vad_segment",
                    SubtitleConstants.DEFAULT_TRANSCRIBE_PER_VAD_SEGMENT,
                ),
                stream_merge_target_duration=config_dict.get(
                    "stream_merge_target_duration",
                    SubtitleConstants.DEFAULT_STREAM_MERGE_TARGET_DURATION,
                ),
                stream_long_segment_threshold=config_dict.get(
                    "stream_long_segment_threshold",
                    SubtitleConstants.DEFAULT_STREAM_LONG_SEGMENT_THRESHOLD,
                ),
                stream_merge_max_gap=config_dict.get(
                    "stream_merge_max_gap",
                    SubtitleConstants.DEFAULT_STREAM_MERGE_MAX_GAP,
                ),
                max_subtitle_duration=config_dict.get(
                    "max_subtitle_duration",
                    SubtitleConstants.DEFAULT_MAX_SUBTITLE_DURATION,
                ),
                subtitle_display=subtitle_display
            )
        )

        # 兼容：若无model_profiles，则用model_path创建默认方案
        model_path = config_dict.get("model_path", "")
        if model_path and not config.model_profiles:
            config.model_profiles = {"default": ModelProfile.create_default_profile(model_path)}
            config.active_model_profile_id = "default"

        config._ensure_default_profiles()
        return config


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


# 兼容导出名称
AppConfig = Config
