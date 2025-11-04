"""
字幕显示组件包装器

自动选择最优的线程安全实现。
"""

import logging
from typing import Optional

from ..config.models import SubtitleDisplayConfig

# 尝试导入线程安全实现
try:
    from .thread_safe_display import ThreadSafeSubtitleDisplay
    THREAD_SAFE_AVAILABLE = True
except ImportError:
    THREAD_SAFE_AVAILABLE = False


class SubtitleDisplay:
    """
    字幕显示组件 - 统一接口

    自动选择最优实现：
    1. 优先使用独立GUI线程的线程安全实现
    2. 降级到原有的简单实现
    """

    def __init__(self, config: SubtitleDisplayConfig):
        """
        初始化字幕显示组件

        Args:
            config: 字幕显示配置对象
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        # 验证配置
        self.config.validate()

        # 选择实现
        self._implementation = self._create_implementation()

        self.logger.info(f"字幕显示组件初始化完成，使用: {type(self._implementation).__name__}")

    def _create_implementation(self):
        """创建字幕显示实现"""
        if THREAD_SAFE_AVAILABLE:
            try:
                self.logger.info("使用独立GUI线程的线程安全实现")
                return ThreadSafeSubtitleDisplay(self.config)
            except Exception as e:
                self.logger.error(f"线程安全实现初始化失败: {e}")

        # 使用简单实现作为后备
        try:
            from .simple_display import SimpleSubtitleDisplay
            self.logger.info("使用简单字幕显示实现")
            return SimpleSubtitleDisplay(self.config)
        except ImportError:
            raise ImportError("无法创建任何字幕显示实现")

    # 公共接口方法
    def start(self) -> None:
        """启动字幕显示"""
        self._implementation.start()

    def stop(self) -> None:
        """停止字幕显示"""
        self._implementation.stop()

    def show_subtitle(self, text: str, confidence: float = 1.0) -> None:
        """
        显示字幕文本

        Args:
            text: 要显示的字幕文本
            confidence: 转录置信度 (0.0-1.0)
        """
        self._implementation.show_subtitle(text, confidence)

    def clear_subtitle(self) -> None:
        """清除当前显示的字幕"""
        self._implementation.clear_subtitle()

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._implementation.is_running