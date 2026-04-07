"""
配置文件管理器

负责配置文件的持久化存储、加载、验证和版本迁移

配置文件位置:
    - 优先使用项目根目录下的 config 文件夹: <project_root>/config/gui_config.json
    - 回退到用户目录（兼容旧版本）:
        - Windows: config\config.json
        - Linux/macOS: ~/.speech2subtitles/config.json

配置文件格式:
    {
        "version": "2.0",
        "last_modified": "2025-11-06T10:30:00",
        "config": {
            "runtime": {...},
            "audio": {...},
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

from src.config.models import AppConfig

logger = logging.getLogger(__name__)


class ConfigFileManager:
    """配置文件管理器

    负责配置的持久化存储、加载、验证和版本迁移
    """

    CONFIG_VERSION = "2.0"

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

        logger.info(f"配置文件路径: {self.config_file}")

    def _get_config_dir(self) -> Path:
        """获取配置目录路径（项目根目录下的config文件夹）

        Returns:
            Path: 配置目录路径
        """
        # 获取项目根目录（从当前文件向上3层：src/config/file_manager.py -> src/config -> src -> 项目根目录）
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent  # src/config/file_manager.py -> src/config -> src -> 项目根目录
        config_dir = project_root / "config"
        
        logger.debug(f"项目根目录: {project_root}")
        logger.debug(f"配置目录: {config_dir}")
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

        # 如果旧配置文件存在，迁移到新位置
        if self.legacy_config_file.exists():
            try:
                shutil.copy2(self.legacy_config_file, self.config_file)
                logger.info(f"迁移旧版配置文件: {self.legacy_config_file} -> {self.config_file}")
            except Exception as e:
                logger.warning(f"迁移旧版配置文件失败: {e}")

    def _config_to_dict(self, config: AppConfig) -> dict:
        """将配置对象转换为字典

        Args:
            config: AppConfig对象

        Returns:
            dict: 配置字典
        """
        return config.to_dict()

    def _dict_to_config(self, config_dict: dict) -> AppConfig:
        """将字典转换为配置对象

        Args:
            config_dict: 配置字典

        Returns:
            AppConfig: 配置对象
        """
        return AppConfig.from_dict(config_dict)

    def save_config(self, config: AppConfig) -> bool:
        """保存配置到文件

        Args:
            config: AppConfig对象

        Returns:
            bool: 是否保存成功
        """
        try:
            # 构建保存数据
            save_data = {
                "version": self.CONFIG_VERSION,
                "last_modified": datetime.now().isoformat(),
                "config": self._config_to_dict(config)
            }

            # 写入文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)

            logger.info(f"配置保存成功: {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def load_config(self) -> Optional[AppConfig]:
        """从文件加载配置

        Returns:
            Optional[AppConfig]: 配置对象，失败返回None
        """
        try:
            # 检查配置文件是否存在
            if not self.config_file.exists():
                logger.info("配置文件不存在，使用默认配置")
                return None

            # 读取配置文件
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 版本检查和迁移
            config_version = data.get("version", "1.0")
            if config_version != self.CONFIG_VERSION:
                logger.warning(f"配置版本不匹配: {config_version} vs {self.CONFIG_VERSION}")
                data = self._migrate_config(data, config_version)

            # 提取配置数据并转换为配置对象
            config_dict = data.get("config", {})
            return self._dict_to_config(config_dict)

        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return None

    def _migrate_config(self, data: dict, from_version: str) -> dict:
        """迁移旧版本配置到新版本

        Args:
            data: 原始配置数据
            from_version: 原始版本号

        Returns:
            dict: 迁移后的配置数据
        """
        logger.info(f"迁移配置: {from_version} -> {self.CONFIG_VERSION}")

        # 这里可以添加版本迁移逻辑
        # 目前简单返回原始数据，实际项目中需要根据版本差异进行转换
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
            bool: 是否删除成功
        """
        try:
            if self.config_file.exists():
                self.config_file.unlink()
                logger.info(f"已删除配置文件: {self.config_file}")
                return True
        except Exception as e:
            logger.error(f"删除配置文件失败: {e}")
        
        return False

    def export_config(self, export_path: str, config: AppConfig) -> bool:
        """导出配置到指定路径

        Args:
            export_path: 导出文件路径
            config: 配置对象

        Returns:
            bool: 是否导出成功
        """
        try:
            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)

            export_data = {
                "version": self.CONFIG_VERSION,
                "exported_at": datetime.now().isoformat(),
                "config": self._config_to_dict(config)
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"配置已导出到: {export_path}")
            return True

        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return False

    def import_config(self, import_path: str) -> Tuple[Optional[AppConfig], Optional[str]]:
        """从指定路径导入配置

        Args:
            import_path: 导入文件路径

        Returns:
            Tuple[Optional[AppConfig], Optional[str]]: (配置对象, 错误信息)
        """
        try:
            import_file = Path(import_path)
            if not import_file.exists():
                return None, f"导入文件不存在: {import_path}"

            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 版本检查
            config_version = data.get("version", "1.0")
            if config_version != self.CONFIG_VERSION:
                logger.warning(f"导入配置版本不匹配: {config_version}")

            config_dict = data.get("config", {})
            config = self._dict_to_config(config_dict)
            return config, None

        except Exception as e:
            return None, f"导入配置失败: {e}"

    def get_config_info(self) -> dict:
        """获取配置文件信息

        Returns:
            dict: 配置文件信息
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
                stat = self.config_file.stat()
                info["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                info["file_size"] = stat.st_size
            except Exception as e:
                logger.error(f"获取文件信息失败: {e}")

        return info

    def backup_config(self, backup_path: Optional[str] = None) -> bool:
        """备份配置文件

        Args:
            backup_path: 备份文件路径，为None时自动生成

        Returns:
            bool: 是否备份成功
        """
        try:
            if not self.config_file.exists():
                logger.warning("配置文件不存在，无需备份")
                return False

            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.config_dir / f"gui_config_backup_{timestamp}.json"

            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.config_file, backup_file)
            
            logger.info(f"配置已备份到: {backup_file}")
            return True

        except Exception as e:
            logger.error(f"备份配置失败: {e}")
            return False

    def restore_config(self, backup_path: str) -> bool:
        """从备份恢复配置文件

        Args:
            backup_path: 备份文件路径

        Returns:
            bool: 是否恢复成功
        """
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                logger.error(f"备份文件不存在: {backup_path}")
                return False

            # 验证备份文件格式
            with open(backup_path, 'r', encoding='utf-8') as f:
                json.load(f)  # 验证JSON格式

            # 备份当前配置
            if self.config_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_current = self.config_file.with_name(f"{self.config_file.stem}_pre_restore_{timestamp}.json")
                shutil.copy2(self.config_file, backup_current)
                logger.info(f"当前配置已备份到: {backup_current}")

            # 恢复备份
            shutil.copy2(backup_path, self.config_file)
            logger.info(f"配置已从备份恢复: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"恢复配置失败: {e}")
            return False