"""配置管理桥接器
提供GUI和ConfigManager之间的配置同步接口
"""

import logging
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from dataclasses import asdict

from src.config.manager import ConfigManager
from src.config.models import Config, SubtitleDisplayConfig
from src.gui.storage.config_file_manager import ConfigFileManager

logger = logging.getLogger(__name__)


class ConfigBridge:
    """配置桥接器

    负责GUI和ConfigManager之间的配置管理

    核心职责:
        1. 加载和保存配置
        2. 配置验证
        3. 配置更新和同步
        4. 配置文件持久化

    使用方式:
        bridge = ConfigBridge()
        config = bridge.load_config()
        bridge.update_config({'model_path': '/path/to/model'})
    """

    def __init__(self):
        """初始化配置桥接器"""
        self.config_manager = ConfigManager()
        self.file_manager = ConfigFileManager()  # 新增：文件管理器
        self._current_config: Optional[Config] = None
        logger.info("ConfigBridge initialized")

    def load_config(self, config_file: Optional[str] = None) -> Config:
        """加载配置

        Args:
            config_file: 配置文件路径（可选，用于导入）

        Returns:
            Config: 配置对象
        """
        if config_file:
            # 从指定文件导入
            config, error = self.file_manager.import_config(config_file)
            if config:
                self._current_config = config
                return config
            logger.warning(f"Failed to import config: {error}")

        # 尝试从默认位置加载
        config = self.file_manager.load_config()
        if config:
            self._current_config = config
            logger.info("Config loaded from file")
            return config

        # 使用默认配置
        self._current_config = self.config_manager.get_default_config()
        logger.info("Using default configuration")
        return self._current_config

    def save_config(self, config: Config, config_file: Optional[str] = None) -> bool:
        """保存配置

        Args:
            config: 要保存的配置对象
            config_file: 配置文件路径（可选，用于导出）

        Returns:
            bool: 保存是否成功
        """
        try:
            # 验证配置
            config.validate()
            self._current_config = config

            if config_file:
                # 导出到指定文件
                success, error = self.file_manager.export_config(config_file, config)
                if not success:
                    logger.error(f"Export failed: {error}")
                    return False
            else:
                # 保存到默认位置
                success, error = self.file_manager.save_config(config)
                if not success:
                    logger.error(f"Save failed: {error}")
                    return False

            logger.info("Configuration saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def update_config(self, updates: Dict[str, Any]) -> Tuple[bool, str]:
        """更新配置

        Args:
            updates: 配置更新字典，支持点分路径
                例如: {"model_path": "/path/to/model", "use_gpu": True}

        Returns:
            Tuple[bool, str]: (成功, 错误消息)
        """
        if self._current_config is None:
            return False, "配置未初始化"

        try:
            # 创建配置副本
            config_dict = self._config_to_dict(self._current_config)

            # 应用更新
            for key, value in updates.items():
                if '.' in key:
                    # 支持嵌套配置更新，如 "subtitle_display.enabled"
                    self._set_nested_value(config_dict, key, value)
                else:
                    config_dict[key] = value

            # 重建配置对象
            new_config = self._dict_to_config(config_dict)

            # 验证配置
            new_config.validate()

            # 应用新配置
            self._current_config = new_config
            logger.info(f"Configuration updated: {list(updates.keys())}")
            return True, ""

        except ValueError as e:
            logger.error(f"Config validation failed: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Config update failed: {e}")
            return False, f"配置更新失败: {str(e)}"

    def get_config(self) -> Optional[Config]:
        """获取当前配置

        Returns:
            Optional[Config]: 当前配置对象
        """
        return self._current_config

    def validate_config(self, config: Config) -> Tuple[bool, str]:
        """验证配置有效性

        Args:
            config: 要验证的配置对象

        Returns:
            Tuple[bool, str]: (是否有效, 错误消息)
        """
        try:
            config.validate()
            return True, ""
        except ValueError as e:
            return False, str(e)

    def _config_to_dict(self, config: Config) -> Dict[str, Any]:
        """将Config对象转换为字典

        Args:
            config: Config对象

        Returns:
            Dict: 配置字典
        """
        return asdict(config)

    def _dict_to_config(self, config_dict: Dict[str, Any]) -> Config:
        """将字典转换为Config对象

        正确处理嵌套配置对象（如SubtitleDisplayConfig）

        Args:
            config_dict: 配置字典

        Returns:
            Config: Config对象
        """
        # 创建配置字典副本，避免修改原始数据
        config_copy = config_dict.copy()

        # 处理嵌套的SubtitleDisplayConfig
        if 'subtitle_display' in config_copy:
            subtitle_config = config_copy['subtitle_display']
            if isinstance(subtitle_config, dict):
                # 将字典转换为SubtitleDisplayConfig对象
                config_copy['subtitle_display'] = SubtitleDisplayConfig(**subtitle_config)
            # 如果已经是SubtitleDisplayConfig对象，保持不变

        # TODO: 如果未来添加其他嵌套配置，在此处理
        # 例如: AudioConfig, VadConfig等

        return Config(**config_copy)

    def _set_nested_value(self, d: Dict, path: str, value: Any) -> None:
        """设置嵌套字典的值

        Args:
            d: 目标字典
            path: 点分路径，如 "subtitle_display.enabled"
            value: 要设置的值
        """
        keys = path.split('.')
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
