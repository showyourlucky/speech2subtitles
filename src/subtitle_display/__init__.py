"""
字幕显示模块

提供基于tkinter的实时字幕显示功能，支持自定义样式、位置和透明度。
创建无边框、置顶的半透明字幕窗口，用于实时显示语音转录结果。
"""

import logging
from typing import Optional

# 尝试导入线程安全实现
try:
    from .thread_safe_display import ThreadSafeSubtitleDisplay
    THREAD_SAFE_AVAILABLE = True
except ImportError:
    THREAD_SAFE_AVAILABLE = False

# 导入包装器
from .display_wrapper import SubtitleDisplay

# 导入配置和异常类
from ..config.models import SubtitleDisplayConfig
from ..utils.error_handler import ConfigurationError, ComponentInitializationError

# 导出主要类
__all__ = ['SubtitleDisplay', 'ThreadSafeSubtitleDisplay', 'SubtitleDisplayConfig']

# 模块级别的日志
logger = logging.getLogger(__name__)

def create_subtitle_display(config: SubtitleDisplayConfig) -> SubtitleDisplay:
    """
    创建字幕显示组件的工厂函数

    Args:
        config: 字幕显示配置对象

    Returns:
        SubtitleDisplay: 字幕显示组件实例

    Raises:
        ComponentInitializationError: 组件初始化失败
        ConfigurationError: 配置验证失败
    """
    try:
        return SubtitleDisplay(config)
    except Exception as e:
        logger.error(f"创建字幕显示组件失败: {e}")
        raise ComponentInitializationError(f"创建字幕显示组件失败: {e}")

def is_thread_safe_available() -> bool:
    """
    检查线程安全实现是否可用

    Returns:
        bool: 如果线程安全实现可用则返回True
    """
    return THREAD_SAFE_AVAILABLE