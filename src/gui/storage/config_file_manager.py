"""
配置文件管理器

负责配置的持久化存储、加载、验证和版本迁移

配置文件位置:
    - 优先使用项目根目录下的 config 文件夹: <project_root>/config/gui_config.json
    - 回退到用户目录（兼容旧版本):
        - Windows: config\config.json
        - Linux/macOS: ~/.speech2subtitles/config.json

配置文件格式:
    {
        "version": "1.0",
        "last_modified": "2025-11-06T10:30:00",
        "config": {
            "model_path": "...",
            "use_gpu": true,
            ...
        }
    }
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from src.config.models import Config, SubtitleDisplayConfig

logger = logging.getLogger(__name__)


class ConfigFileManager:
    """配置文件管理器

    负责配置的持久化存储、加载、验证和版本迁移
    """

    CONFIG_VERSION = "1.0"

    def __init__(self):
        """初始化配置文件管理器"""
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "gui_config.json"

        # 保存旧配置文件路径（用于迁移）
        self.legacy_config_dir = self._get_legacy_config_dir()
        self.legacy_config_file = self.legacy_config_dir / "config.json"

        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 迁移旧配置文件（如果存在）
        self._migrate_legacy_config()

        logger.info(f"Config file path: {self.config_file}")

    def _get_config_dir(self) -> Path:
        """获取配置目录路径（项目根目录下的 config 文件夹）

        Returns:
            Path: 配置目录路径
        """
        # 获取项目根目录（从当前文件向上3层：src/gui/storage -> src/gui -> src -> root）
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent

        config_dir = project_root / "config"

        logger.debug(f"Project config directory: {config_dir}")
        return config_dir

    def _get_legacy_config_dir(self) -> Path:
        """获取旧版配置目录路径（用户主目录）

        Returns:
            Path: 旧版配置目录路径
        """
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('USERPROFILE', '.'))
        else:  # Linux/macOS
            base_dir = Path.home()

        return base_dir / '.speech2subtitles'

    def _migrate_legacy_config(self) -> None:
        """迁移旧版配置文件到新位置"""
        # 如果新配置文件已存在，无需迁移
        if self.config_file.exists():
            return

        # 如果旧配置文件存在,迁移到新位置
        if self.legacy_config_file.exists():
            try:
                shutil.copy2(self.legacy_config_file, self.config_file)
                logger.info(f"Migrated legacy config from {self.legacy_config_file} to {self.config_file}")

                # 可选：删除旧配置文件（可以根据需求决定是否启用）
                # self.legacy_config_file.unlink()
                # logger.info("Removed legacy config file")
            except Exception as e:
                logger.warning(f"Failed to migrate legacy config: {e}")

    def _config_to_dict(self, config: Config) -> Dict[str, Any]:
        """将Config对象转换为字典

        Args:
            config: Config对象

        Returns:
            Dict[str, Any]: 配置字典
        """
        config_dict = {
            # 核心配置
            "model_path": config.model_path,
            "input_source": config.input_source,

            # 可选配置
            "use_gpu": config.use_gpu,
            "vad_sensitivity": config.vad_sensitivity,
            "output_format": config.output_format,
            "device_id": config.device_id,

            # 音频配置
            "sample_rate": config.sample_rate,
            "chunk_size": config.chunk_size,
            "channels": config.channels,

            # VAD配置
            "vad_window_size": config.vad_window_size,
            "vad_threshold": config.vad_threshold,

            # 输出配置
            "show_confidence": config.show_confidence,
            "show_timestamp": config.show_timestamp,

            # 媒体文件转字幕配置
            "input_file": config.input_file,
            "output_dir": config.output_dir,
            "subtitle_format": config.subtitle_format,
            "keep_temp": config.keep_temp,
            "verbose": config.verbose,

            # 字幕显示配置
            "subtitle_display": {
                "enabled": config.subtitle_display.enabled,
                "position": config.subtitle_display.position,
                "font_size": config.subtitle_display.font_size,
                "font_family": config.subtitle_display.font_family,
                "opacity": config.subtitle_display.opacity,
                "max_display_time": config.subtitle_display.max_display_time,
                "text_color": config.subtitle_display.text_color,
                "background_color": config.subtitle_display.background_color,
            }
        }

        return config_dict

    def _dict_to_config(self, config_dict: Dict[str, Any]) -> Config:
        """将字典转换为Config对象

        Args:
            config_dict: 配置字典

        Returns:
            Config: Config对象
        """
        # 处理字幕显示配置
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

        # 创建Config对象
        config = Config(
            # 核心配置
            model_path=config_dict.get("model_path", ""),
            input_source=config_dict.get("input_source"),

            # 可选配置
            use_gpu=config_dict.get("use_gpu", True),
            vad_sensitivity=config_dict.get("vad_sensitivity", 0.5),
            output_format=config_dict.get("output_format", "text"),
            device_id=config_dict.get("device_id"),

            # 音频配置
            sample_rate=config_dict.get("sample_rate", 16000),
            chunk_size=config_dict.get("chunk_size", 1024),
            channels=config_dict.get("channels", 1),

            # VAD配置
            vad_window_size=config_dict.get("vad_window_size", 0.512),
            vad_threshold=config_dict.get("vad_threshold", 0.5),

            # 输出配置
            show_confidence=config_dict.get("show_confidence", True),
            show_timestamp=config_dict.get("show_timestamp", True),

            # 媒体文件转字幕配置
            input_file=config_dict.get("input_file"),
            output_dir=config_dict.get("output_dir"),
            subtitle_format=config_dict.get("subtitle_format", "srt"),
            keep_temp=config_dict.get("keep_temp", False),
            verbose=config_dict.get("verbose", False),

            # 字幕显示配置
            subtitle_display=subtitle_display,
        )

        return config

    def save_config(self, config: Config) -> bool:
        """保存配置到文件

        Args:
            config: Config对象

        Returns:
            bool: 是否成功保存
        """
        try:
            # 构建保存数据
            save_data = {
                "version": self.CONFIG_VERSION,
                "last_modified": datetime.now().isoformat(),
                "config": self._config_to_dict(config)
            }

            # 写入文件 (使用UTF-8编码)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Config saved successfully: {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def load_config(self) -> Optional[Config]:
        """从文件加载配置

        Returns:
            Optional[Config]: Config对象，失败返回None
        """
        try:
            # 检查文件是否存在
            if not self.config_file.exists():
                logger.info("Config file not found, will use default config")
                return None

            # 读取配置文件
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 版本检查和迁移
            config_version = data.get("version", "1.0")
            if config_version != self.CONFIG_VERSION:
                logger.warning(f"Config version mismatch: {config_version} vs {self.CONFIG_VERSION}")
                data = self._migrate_config(data, config_version)

            # 提取配置数据
            config_dict = data.get("config", {})
            config = self._dict_to_config(config_dict)

            logger.info(f"Config loaded successfully: {self.config_file}")
            return config

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return None

    def _migrate_config(self, data: Dict[str, Any], from_version: str) -> Dict[str, Any]:
        """迁移旧版本配置到新版本

        Args:
            data: 原始配置数据
            from_version: 原始版本号

        Returns:
            Dict[str, Any]: 迁移后的配置数据
        """
        logger.info(f"Migrating config from version {from_version} to {self.CONFIG_VERSION}")

        # 示例：从1.0迁移到1.1
        # if from_version == "1.0":
        #     # 添加新字段的默认值
        #     config_dict = data.get("config", {})
        #     config_dict["new_field"] = "default_value"
        #     data["config"] = config_dict
        #     data["version"] = "1.1"

        # 当前版本统一标记为最新版本
        data["version"] = self.CONFIG_VERSION

        return data

    def config_exists(self) -> bool:
        """检查配置文件是否存在

        Returns:
            bool: 配置文件是否存在
        """
        return self.config_file.exists()

    def delete_config(self) -> bool:
        """删除配置文件

        Returns:
            bool: 是否成功删除
        """
        try:
            if self.config_file.exists():
                self.config_file.unlink()
                logger.info(f"Config file deleted: {self.config_file}")
                return True
            else:
                logger.warning("Config file does not exist, nothing to delete")
                return False

        except Exception as e:
            logger.error(f"Failed to delete config file: {e}")
            return False

    def export_config(self, export_path: str, config: Config) -> bool:
        """导出配置到指定路径

        Args:
            export_path: 导出文件路径
            config: Config对象

        Returns:
            bool: 是否成功导出
        """
        try:
            export_file = Path(export_path)

            # 确保父目录存在
            export_file.parent.mkdir(parents=True, exist_ok=True)

            # 构建导出数据
            export_data = {
                "version": self.CONFIG_VERSION,
                "exported_at": datetime.now().isoformat(),
                "config": self._config_to_dict(config)
            }

            # 写入文件
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Config exported to: {export_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return False

    def import_config(self, import_path: str) -> Optional[Config]:
        """从指定路径导入配置

        Args:
            import_path: 导入文件路径

        Returns:
            Optional[Config]: Config对象，失败返回None
        """
        try:
            import_file = Path(import_path)

            # 检查文件是否存在
            if not import_file.exists():
                logger.error(f"Import file not found: {import_file}")
                return None

            # 读取配置文件
            with open(import_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 版本检查和迁移
            config_version = data.get("version", "1.0")
            if config_version != self.CONFIG_VERSION:
                logger.warning(f"Imported config version mismatch: {config_version} vs {self.CONFIG_VERSION}")
                data = self._migrate_config(data, config_version)

            # 提取配置数据
            config_dict = data.get("config", {})
            config = self._dict_to_config(config_dict)

            logger.info(f"Config imported from: {import_file}")
            return config

        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            return None

    def get_config_info(self) -> Dict[str, Any]:
        """获取配置文件信息

        Returns:
            Dict[str, Any]: 配置文件信息
        """
        info = {
            "config_file": str(self.config_file),
            "config_dir": str(self.config_dir),
            "legacy_config_file": str(self.legacy_config_file),
            "exists": self.config_file.exists(),
            "version": self.CONFIG_VERSION,
        }

        if self.config_file.exists():
            try:
                # 获取文件修改时间
                stat = self.config_file.stat()
                info["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                info["file_size"] = stat.st_size

                # 读取版本信息
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    info["saved_version"] = data.get("version", "unknown")

            except Exception as e:
                logger.error(f"Failed to get config file info: {e}")

        return info

    def backup_config(self, backup_path: Optional[str] = None) -> bool:
        """备份配置文件

        Args:
            backup_path: 备份文件路径，如果为None则自动生成

        Returns:
            bool: 是否成功备份
        """
        try:
            if not self.config_file.exists():
                logger.warning("Config file does not exist, nothing to backup")
                return False

            # 自动生成备份路径
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = str(self.config_dir / f"gui_config_backup_{timestamp}.json")

            # 复制文件
            shutil.copy2(self.config_file, backup_path)
            logger.info(f"Config backed up to: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to backup config: {e}")
            return False

    def restore_config(self, backup_path: str) -> bool:
        """从备份恢复配置文件

        Args:
            backup_path: 备份文件路径

        Returns:
            bool: 是否成功恢复
        """
        try:
            backup_file = Path(backup_path)

            # 检查备份文件是否存在
            if not backup_file.exists():
                logger.error(f"Backup file not found: {backup_file}")
                return False

            # 验证备份文件格式
            with open(backup_file, 'r', encoding='utf-8') as f:
                json.load(f)  # 验证JSON格式

            # 复制文件
            shutil.copy2(backup_file, self.config_file)
            logger.info(f"Config restored from: {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore config: {e}")
            return False
