"""配置管理桥接器
提供GUI和ConfigManager之间的配置同步接口
"""

import logging
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

from src.config.manager import ConfigManager
from src.config.models import Config, SubtitleDisplayConfig, VadProfile, ModelProfile
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
                success = self.file_manager.export_config(config_file, config)
            else:
                # 保存到默认位置
                success = self.file_manager.save_config(config)
            if not success:
                return False
            logger.info("配置保存成功") 
            return True

        except Exception as e:
            logger.error(f"配置保存失败: {e}")
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

        # 处理嵌套的VadProfile字典
        if 'vad_profiles' in config_copy:
            vad_profiles = config_copy['vad_profiles']
            if isinstance(vad_profiles, dict):
                # 检查是否所有值都已经是VadProfile对象
                converted_profiles = {}
                for profile_id, profile_data in vad_profiles.items():
                    if isinstance(profile_data, dict):
                        # 将字典转换为VadProfile对象
                        converted_profiles[profile_id] = VadProfile(**profile_data)
                    elif isinstance(profile_data, VadProfile):
                        # 已经是VadProfile对象，直接使用
                        converted_profiles[profile_id] = profile_data
                config_copy['vad_profiles'] = converted_profiles

        # 处理嵌套的ModelProfile字典
        if 'model_profiles' in config_copy:
            model_profiles = config_copy['model_profiles']
            if isinstance(model_profiles, dict):
                # 检查是否所有值都已经是ModelProfile对象
                converted_profiles = {}
                for profile_id, profile_data in model_profiles.items():
                    if isinstance(profile_data, dict):
                        # 将字典转换为ModelProfile对象
                        converted_profiles[profile_id] = ModelProfile.from_dict(profile_data)
                    elif isinstance(profile_data, ModelProfile):
                        # 已经是ModelProfile对象，直接使用
                        converted_profiles[profile_id] = profile_data
                config_copy['model_profiles'] = converted_profiles

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

    # ========== VAD方案管理方法 ==========

    def add_vad_profile(self, profile: VadProfile) -> Tuple[bool, str]:
        """
        添加新的VAD配置方案

        Args:
            profile: VAD配置方案对象

        Returns:
            Tuple[bool, str]: (是否成功, 错误消息)
        """
        if self._current_config is None:
            return False, "配置未初始化"

        try:
            # 验证方案配置
            profile.validate()

            # 检查方案ID是否已存在
            if profile.profile_id in self._current_config.vad_profiles:
                return False, f"方案ID '{profile.profile_id}' 已存在"

            # 检查方案名称是否重复
            for existing_profile in self._current_config.vad_profiles.values():
                if existing_profile.profile_name == profile.profile_name:
                    return False, f"方案名称 '{profile.profile_name}' 已存在"

            # 添加方案
            self._current_config.vad_profiles[profile.profile_id] = profile
            logger.info(f"Added VAD profile: {profile.profile_name} ({profile.profile_id})")
            return True, ""

        except Exception as e:
            logger.error(f"Failed to add VAD profile: {e}")
            return False, str(e)

    def update_vad_profile(self, profile_id: str, profile: VadProfile) -> Tuple[bool, str]:
        """
        更新VAD配置方案

        Args:
            profile_id: 要更新的方案ID
            profile: 新的VAD配置方案对象

        Returns:
            Tuple[bool, str]: (是否成功, 错误消息)
        """
        if self._current_config is None:
            return False, "配置未初始化"

        try:
            # 验证方案配置
            profile.validate()

            # 检查方案是否存在
            if profile_id not in self._current_config.vad_profiles:
                return False, f"方案 '{profile_id}' 不存在"

            # 如果方案名称改变，检查新名称是否重复
            if profile.profile_name != self._current_config.vad_profiles[profile_id].profile_name:
                for pid, existing_profile in self._current_config.vad_profiles.items():
                    if pid != profile_id and existing_profile.profile_name == profile.profile_name:
                        return False, f"方案名称 '{profile.profile_name}' 已存在"

            # 更新方案
            self._current_config.vad_profiles[profile_id] = profile
            logger.info(f"Updated VAD profile: {profile.profile_name} ({profile_id})")
            return True, ""

        except Exception as e:
            logger.error(f"Failed to update VAD profile: {e}")
            return False, str(e)

    def delete_vad_profile(self, profile_id: str) -> Tuple[bool, str]:
        """
        删除VAD配置方案

        Args:
            profile_id: 要删除的方案ID

        Returns:
            Tuple[bool, str]: (是否成功, 错误消息)
        """
        if self._current_config is None:
            return False, "配置未初始化"

        try:
            # 不允许删除默认方案
            if profile_id == "default":
                return False, "不能删除默认方案"

            # 检查方案是否存在
            if profile_id not in self._current_config.vad_profiles:
                return False, f"方案 '{profile_id}' 不存在"

            # 如果删除的是活跃方案，切换到默认方案
            if self._current_config.active_vad_profile_id == profile_id:
                self._current_config.active_vad_profile_id = "default"
                logger.info(f"Switched to default profile because active profile was deleted")

            # 删除方案
            profile_name = self._current_config.vad_profiles[profile_id].profile_name
            del self._current_config.vad_profiles[profile_id]
            logger.info(f"Deleted VAD profile: {profile_name} ({profile_id})")
            return True, ""

        except Exception as e:
            logger.error(f"Failed to delete VAD profile: {e}")
            return False, str(e)

    def get_active_vad_profile(self) -> Optional[VadProfile]:
        """
        获取当前活跃的VAD方案

        Returns:
            Optional[VadProfile]: 当前活跃的VAD方案，如果不存在返回None
        """
        if self._current_config is None:
            return None

        try:
            return self._current_config.get_active_vad_profile()
        except Exception as e:
            logger.error(f"Failed to get active VAD profile: {e}")
            return None

    def set_active_vad_profile(self, profile_id: str = "default") -> Tuple[bool, str]:
        """
        设置活跃的VAD方案

        Args:
            profile_id: VAD方案ID

        Returns:
            Tuple[bool, str]: (是否成功, 错误消息)
        """
        if self._current_config is None:
            return False, "配置未初始化"

        try:
            # 检查方案是否存在
            if profile_id not in self._current_config.vad_profiles:
                return False, f"方案 '{profile_id}' 不存在"

            # 设置活跃方案
            self._current_config.set_active_vad_profile(profile_id)
            profile_name = self._current_config.vad_profiles[profile_id].profile_name
            logger.info(f"Set active VAD profile: {profile_name} ({profile_id})")
            return True, ""

        except Exception as e:
            logger.error(f"Failed to set active VAD profile: {e}")
            return False, str(e)

    def get_all_vad_profiles(self) -> Dict[str, VadProfile]:
        """
        获取所有VAD配置方案

        Returns:
            Dict[str, VadProfile]: VAD方案字典 {profile_id: VadProfile}
        """
        if self._current_config is None:
            return {}

        return self._current_config.vad_profiles.copy()

    def duplicate_vad_profile(self, source_profile_id: str, new_profile_name: str) -> Tuple[bool, str, Optional[str]]:
        """
        复制VAD配置方案

        Args:
            source_profile_id: 源方案ID
            new_profile_name: 新方案名称

        Returns:
            Tuple[bool, str, Optional[str]]: (是否成功, 错误消息, 新方案ID)
        """
        if self._current_config is None:
            return False, "配置未初始化", None

        try:
            # 检查源方案是否存在
            if source_profile_id not in self._current_config.vad_profiles:
                return False, f"源方案 '{source_profile_id}' 不存在", None

            # 检查新方案名称是否重复
            for existing_profile in self._current_config.vad_profiles.values():
                if existing_profile.profile_name == new_profile_name:
                    return False, f"方案名称 '{new_profile_name}' 已存在", None

            # 复制方案
            source_profile = self._current_config.vad_profiles[source_profile_id]
            new_profile = VadProfile(
                profile_name=new_profile_name,
                threshold=source_profile.threshold,
                min_speech_duration_ms=source_profile.min_speech_duration_ms,
                min_silence_duration_ms=source_profile.min_silence_duration_ms,
                max_speech_duration_ms=source_profile.max_speech_duration_ms,
                sample_rate=source_profile.sample_rate,
                model=source_profile.model,
                model_path=source_profile.model_path,
                use_sherpa_onnx=source_profile.use_sherpa_onnx,
                window_size_samples=source_profile.window_size_samples
            )

            # 添加新方案
            success, error = self.add_vad_profile(new_profile)
            if success:
                logger.info(f"Duplicated VAD profile: {source_profile.profile_name} -> {new_profile_name}")
                return True, "", new_profile.profile_id
            else:
                return False, error, None

        except Exception as e:
            logger.error(f"Failed to duplicate VAD profile: {e}")
            return False, str(e), None

    # ========== 模型方案管理方法 ==========

    def switch_model_profile(self, profile_id: str) -> bool:
        """
        切换活跃的模型方案

        Args:
            profile_id: 模型方案ID

        Returns:
            bool: 是否切换成功
        """
        if self._current_config is None:
            logger.error("配置未初始化")
            return False

        try:
            self._current_config.set_active_model_profile(profile_id)
            logger.info(f"Switched to model profile: {profile_id}")
            return True
        except Exception as e:
            logger.error(f"切换模型方案失败: {e}")
            return False

    def add_model_profile(self, profile: ModelProfile) -> bool:
        """
        添加模型方案

        Args:
            profile: 模型方案对象

        Returns:
            bool: 是否添加成功
        """
        if self._current_config is None:
            logger.error("配置未初始化")
            return False

        try:
            profile.validate()
            self._current_config.model_profiles[profile.profile_id] = profile
            logger.info(f"Added model profile: {profile.profile_name} ({profile.profile_id})")
            return True
        except Exception as e:
            logger.error(f"添加模型方案失败: {e}")
            return False

    def delete_model_profile(self, profile_id: str) -> bool:
        """
        删除模型方案

        Args:
            profile_id: 模型方案ID

        Returns:
            bool: 是否删除成功
        """
        if self._current_config is None:
            logger.error("配置未初始化")
            return False

        try:
            # 保护默认方案
            if profile_id == "default":
                raise ValueError("默认方案不能被删除")

            # 至少保留一个方案
            if len(self._current_config.model_profiles) <= 1:
                raise ValueError("必须至少保留一个模型方案")

            # 如果删除的是活跃方案，切换到其他方案
            if profile_id == self._current_config.active_model_profile_id:
                # 切换到默认方案或第一个可用方案
                if "default" in self._current_config.model_profiles and "default" != profile_id:
                    self._current_config.active_model_profile_id = "default"
                else:
                    # 找到第一个不是被删除方案的ID
                    for pid in self._current_config.model_profiles.keys():
                        if pid != profile_id:
                            self._current_config.active_model_profile_id = pid
                            break

            # 删除方案
            del self._current_config.model_profiles[profile_id]
            logger.info(f"Deleted model profile: {profile_id}")
            return True

        except Exception as e:
            logger.error(f"删除模型方案失败: {e}")
            return False

    def update_model_profile(self, profile_id: str, profile: ModelProfile) -> bool:
        """
        更新模型方案

        Args:
            profile_id: 模型方案ID
            profile: 新的模型方案对象

        Returns:
            bool: 是否更新成功
        """
        if self._current_config is None:
            logger.error("配置未初始化")
            return False

        try:
            if profile_id not in self._current_config.model_profiles:
                raise ValueError(f"模型方案 '{profile_id}' 不存在")

            profile.validate()
            profile.updated_at = datetime.now()
            self._current_config.model_profiles[profile_id] = profile

            # 如果是活跃方案，同步 model_path
            if profile_id == self._current_config.active_model_profile_id:
                self._current_config.model_path = profile.model_path

            logger.info(f"Updated model profile: {profile.profile_name} ({profile_id})")
            return True

        except Exception as e:
            logger.error(f"更新模型方案失败: {e}")
            return False
