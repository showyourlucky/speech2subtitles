"""
配置加载器

负责统一合并配置来源: CLI > ENV > 文件 > 默认
"""

from typing import Optional, Dict, Any
import os

from .models import Config
from .manager import ConfigManager
from .file_manager import ConfigFileManager


class ConfigLoader:
    """统一配置加载器"""

    def __init__(self, file_manager: Optional[ConfigFileManager] = None):
        self.file_manager = file_manager or ConfigFileManager()

    def load(
        self,
        cli_overrides: Optional[Dict[str, Any]] = None,
        config_file: Optional[str] = None,
        config_path: Optional[str] = None,
        validate: bool = True
    ) -> Config:
        """
        合并配置来源并返回最终配置

        Args:
            cli_overrides: CLI解析后的覆盖字典
            config_file: 指定配置文件路径(可选)

        Returns:
            Config: 合并后的配置对象
        """
        base_config = Config.create_default()
        merged = base_config.to_dict_v2()

        file_config = None
        selected_path = config_path or config_file
        if selected_path:
            file_config, _ = self.file_manager.import_config(selected_path)
        else:
            file_config = self.file_manager.load_config()

        if file_config:
            _deep_merge(merged, file_config.to_dict_v2())

        env_overrides = self._load_env(os.environ)
        if env_overrides:
            _deep_merge(merged, env_overrides)

        if cli_overrides:
            _deep_merge(merged, cli_overrides)

        config = Config.from_dict_v2(merged)
        if validate:
            config.validate()
        return config

    def load_from_cli(self, args=None, config_file: Optional[str] = None) -> Config:
        """
        通过CLI解析并加载最终配置

        Args:
            args: CLI参数列表
            config_file: 指定配置文件路径(可选)

        Returns:
            Config: 合并后的配置对象
        """
        manager = ConfigManager()
        cli_overrides = manager.parse_cli_overrides(args)
        return self.load(cli_overrides=cli_overrides, config_file=config_file)

    def _load_env(self, env: Dict[str, str]) -> Dict[str, Any]:
        """解析环境变量为覆盖字典"""
        overrides: Dict[str, Any] = {}

        def set_path(path: str, value: Any) -> None:
            keys = path.split('.')
            cursor = overrides
            for key in keys[:-1]:
                if key not in cursor or not isinstance(cursor[key], dict):
                    cursor[key] = {}
                cursor = cursor[key]
            cursor[keys[-1]] = value

        if env.get("S2S_INPUT_SOURCE"):
            set_path("runtime.input_source", env.get("S2S_INPUT_SOURCE"))

        if env.get("S2S_INPUT_FILE"):
            raw = env.get("S2S_INPUT_FILE", "")
            if raw:
                set_path("runtime.input_file", [p for p in raw.split(os.pathsep) if p])

        if env.get("S2S_USE_GPU"):
            set_path("runtime.use_gpu", _parse_bool(env.get("S2S_USE_GPU")))

        if env.get("S2S_TRANSCRIPTION_LANGUAGE"):
            set_path("runtime.transcription_language", env.get("S2S_TRANSCRIPTION_LANGUAGE"))

        if env.get("S2S_MODEL_PATH"):
            # 兼容字段，交由Config.from_dict_v2处理
            set_path("runtime.model_path", env.get("S2S_MODEL_PATH"))

        if env.get("S2S_MODEL_PROFILE"):
            set_path("runtime.model.active_profile_id", env.get("S2S_MODEL_PROFILE"))

        if env.get("S2S_VAD_PROFILE"):
            set_path("vad.active_profile_id", env.get("S2S_VAD_PROFILE"))

        if env.get("S2S_SAMPLE_RATE"):
            parsed = _parse_int(env.get("S2S_SAMPLE_RATE"))
            if parsed is not None:
                set_path("audio.sample_rate", parsed)

        if env.get("S2S_CHUNK_SIZE"):
            parsed = _parse_int(env.get("S2S_CHUNK_SIZE"))
            if parsed is not None:
                set_path("audio.chunk_size", parsed)

        if env.get("S2S_CHANNELS"):
            parsed = _parse_int(env.get("S2S_CHANNELS"))
            if parsed is not None:
                set_path("audio.channels", parsed)

        if env.get("S2S_DEVICE_ID"):
            parsed = _parse_int(env.get("S2S_DEVICE_ID"))
            if parsed is not None:
                set_path("audio.device_id", parsed)

        if env.get("S2S_OUTPUT_FORMAT"):
            set_path("output.format", env.get("S2S_OUTPUT_FORMAT"))

        if env.get("S2S_SHOW_CONFIDENCE"):
            set_path("output.show_confidence", _parse_bool(env.get("S2S_SHOW_CONFIDENCE")))

        if env.get("S2S_SHOW_TIMESTAMP"):
            set_path("output.show_timestamp", _parse_bool(env.get("S2S_SHOW_TIMESTAMP")))

        if env.get("S2S_SUBTITLE_FORMAT"):
            set_path("subtitle.file.format", env.get("S2S_SUBTITLE_FORMAT"))

        if env.get("S2S_OUTPUT_DIR"):
            set_path("subtitle.file.output_dir", env.get("S2S_OUTPUT_DIR"))

        if env.get("S2S_KEEP_TEMP"):
            set_path("subtitle.file.keep_temp", _parse_bool(env.get("S2S_KEEP_TEMP")))

        if env.get("S2S_VERBOSE"):
            set_path("subtitle.file.verbose", _parse_bool(env.get("S2S_VERBOSE")))
        if env.get("S2S_STREAM_MERGE_TARGET_DURATION"):
            parsed = _parse_float(env.get("S2S_STREAM_MERGE_TARGET_DURATION"))
            if parsed is not None:
                set_path("subtitle.file.stream_merge_target_duration", parsed)
        if env.get("S2S_STREAM_LONG_SEGMENT_THRESHOLD"):
            parsed = _parse_float(env.get("S2S_STREAM_LONG_SEGMENT_THRESHOLD"))
            if parsed is not None:
                set_path("subtitle.file.stream_long_segment_threshold", parsed)
        if env.get("S2S_STREAM_MERGE_MAX_GAP"):
            parsed = _parse_float(env.get("S2S_STREAM_MERGE_MAX_GAP"))
            if parsed is not None:
                set_path("subtitle.file.stream_merge_max_gap", parsed)
        if env.get("S2S_MAX_SUBTITLE_DURATION"):
            parsed = _parse_float(env.get("S2S_MAX_SUBTITLE_DURATION"))
            if parsed is not None:
                set_path("subtitle.file.max_subtitle_duration", parsed)

        if env.get("S2S_SUBTITLE_ENABLED"):
            set_path("subtitle.display.enabled", _parse_bool(env.get("S2S_SUBTITLE_ENABLED")))

        if env.get("S2S_SUBTITLE_POSITION"):
            set_path("subtitle.display.position", env.get("S2S_SUBTITLE_POSITION"))

        if env.get("S2S_SUBTITLE_FONT_SIZE"):
            parsed = _parse_int(env.get("S2S_SUBTITLE_FONT_SIZE"))
            if parsed is not None:
                set_path("subtitle.display.font_size", parsed)

        if env.get("S2S_SUBTITLE_FONT_FAMILY"):
            set_path("subtitle.display.font_family", env.get("S2S_SUBTITLE_FONT_FAMILY"))

        if env.get("S2S_SUBTITLE_OPACITY"):
            parsed = _parse_float(env.get("S2S_SUBTITLE_OPACITY"))
            if parsed is not None:
                set_path("subtitle.display.opacity", parsed)

        if env.get("S2S_SUBTITLE_MAX_DISPLAY_TIME"):
            parsed = _parse_float(env.get("S2S_SUBTITLE_MAX_DISPLAY_TIME"))
            if parsed is not None:
                set_path("subtitle.display.max_display_time", parsed)

        if env.get("S2S_SUBTITLE_TEXT_COLOR"):
            set_path("subtitle.display.text_color", env.get("S2S_SUBTITLE_TEXT_COLOR"))

        if env.get("S2S_SUBTITLE_BG_COLOR"):
            set_path("subtitle.display.background_color", env.get("S2S_SUBTITLE_BG_COLOR"))

        return overrides


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> None:
    """递归合并配置字典"""
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
