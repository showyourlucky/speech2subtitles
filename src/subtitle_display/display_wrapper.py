"""
字幕显示组件包装器

自动选择最优的线程安全实现。
支持单例模式，确保全局只有一个字幕窗口实例。
"""

import atexit
import logging
import threading
from typing import Optional

from ..config.models import SubtitleDisplayConfig

# 尝试导入线程安全实现
try:
    from .thread_safe_display import ThreadSafeSubtitleDisplay
    THREAD_SAFE_AVAILABLE = True
except ImportError:
    THREAD_SAFE_AVAILABLE = False

# ============================================================================
# 单例模式实现
# ============================================================================

# 模块级单例变量和线程锁
_subtitle_display_instance: Optional['SubtitleDisplay'] = None
_instance_lock = threading.Lock()
_singleton_enabled = True  # 支持在测试中禁用单例模式


def get_subtitle_display_instance(config: SubtitleDisplayConfig) -> 'SubtitleDisplay':
    """
    获取字幕显示单例实例（线程安全）

    使用双重检查锁定模式确保线程安全，同时优化性能。
    如果单例已存在且配置发生变化，会自动更新配置。

    Args:
        config: 字幕显示配置对象

    Returns:
        SubtitleDisplay: 字幕显示单例实例

    Examples:
        >>> config = SubtitleDisplayConfig()
        >>> display = get_subtitle_display_instance(config)
        >>> display.start()
    """
    global _subtitle_display_instance

    logger = logging.getLogger(__name__)

    # 如果单例被禁用（用于测试），每次创建新实例
    if not _singleton_enabled:
        logger.debug("单例模式已禁用，创建独立实例")
        return _create_subtitle_display_impl(config)

    # 第一次检查（无锁，快速路径）
    if _subtitle_display_instance is None:
        with _instance_lock:
            # 第二次检查（加锁，确保并发安全）
            if _subtitle_display_instance is None:
                logger.info("首次初始化字幕显示单例")
                try:
                    _subtitle_display_instance = _create_subtitle_display_impl(config)
                    logger.info("字幕显示单例创建成功")
                except Exception as e:
                    logger.error(f"单例初始化失败: {e}")
                    logger.warning("降级到多实例模式，可能出现多个字幕窗口")
                    # 降级策略：返回独立实例
                    return _create_subtitle_display_impl(config)
    else:
        # 单例已存在，检查是否需要更新配置
        logger.debug("重用现有字幕显示单例")
        if _subtitle_display_instance.config != config:
            logger.info("检测到配置变化，更新字幕显示配置")
            _subtitle_display_instance.update_config(config)

    return _subtitle_display_instance


def reset_subtitle_display_instance() -> None:
    """
    重置字幕显示单例实例

    安全地清理现有单例并释放资源。
    主要用于测试场景或需要强制重新初始化的情况。

    Warning:
        调用此方法会停止并销毁当前的字幕显示窗口。
    """
    global _subtitle_display_instance

    logger = logging.getLogger(__name__)

    with _instance_lock:
        if _subtitle_display_instance is not None:
            logger.info("正在重置字幕显示单例")
            try:
                # 清理资源
                _subtitle_display_instance._cleanup()
                logger.info("字幕显示单例已重置")
            except Exception as e:
                logger.error(f"清理单例资源时出错: {e}")
            finally:
                _subtitle_display_instance = None


def _create_subtitle_display_impl(config: SubtitleDisplayConfig) -> 'SubtitleDisplay':
    """
    内部方法：创建字幕显示实现（不使用单例）

    Args:
        config: 字幕显示配置

    Returns:
        SubtitleDisplay: 新的字幕显示实例
    """
    # 创建新实例，但不通过 __new__（避免递归）
    instance = object.__new__(SubtitleDisplay)
    instance._init_impl(config)
    return instance


def _cleanup_at_exit():
    """应用退出时的清理处理器"""
    logger = logging.getLogger(__name__)
    if _subtitle_display_instance is not None:
        logger.info("应用退出，清理字幕显示单例")
        reset_subtitle_display_instance()


# 注册退出时的清理处理器
atexit.register(_cleanup_at_exit)


class SubtitleDisplay:
    """
    字幕显示组件 - 统一接口

    自动选择最优实现：
    1. 优先使用独立GUI线程的线程安全实现
    2. 降级到原有的简单实现

    支持单例模式，确保全局只有一个字幕窗口实例。
    直接实例化会自动返回单例，推荐使用 get_subtitle_display_instance() 工厂方法。
    """

    def __new__(cls, config: SubtitleDisplayConfig):
        """
        覆盖构造方法，使直接实例化也返回单例

        这确保了向后兼容性：现有的 SubtitleDisplay(config) 调用
        会自动使用单例模式，无需修改调用代码。

        Args:
            config: 字幕显示配置对象

        Returns:
            SubtitleDisplay: 字幕显示单例实例
        """
        # 直接调用工厂方法获取单例
        return get_subtitle_display_instance(config)

    def __init__(self, config: SubtitleDisplayConfig):
        """
        初始化字幕显示组件

        注意：此方法仅在首次创建单例时调用。
        实际初始化逻辑在 _init_impl 中实现。

        Args:
            config: 字幕显示配置对象
        """
        # __init__ 可能被多次调用（因为 __new__ 返回已存在的实例）
        # 实际初始化逻辑在 _init_impl 中，避免重复初始化
        pass

    def _init_impl(self, config: SubtitleDisplayConfig):
        """
        内部初始化方法（仅在首次创建时调用）

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

    def update_config(self, new_config: SubtitleDisplayConfig) -> None:
        """
        动态更新配置

        在单例已存在的情况下，通过此方法更新配置而不需要重新创建实例。
        这避免了重启GUI线程和窗口的开销。

        Args:
            new_config: 新的字幕显示配置对象

        Note:
            部分配置（如GUI线程相关参数）可能无法热更新，需要调用
            reset_subtitle_display_instance() 强制重新初始化。
        """
        self.logger.info("更新字幕显示配置")

        # 验证新配置
        new_config.validate()

        # 更新配置对象
        old_config = self.config
        self.config = new_config

        # 如果实现支持配置更新，通知实现层
        if hasattr(self._implementation, 'update_config'):
            try:
                self._implementation.update_config(new_config)
                self.logger.info("配置更新成功")
            except Exception as e:
                self.logger.error(f"配置更新失败: {e}")
                # 回滚到旧配置
                self.config = old_config
                raise
        else:
            # 实现层不支持热更新，仅更新配置对象
            self.logger.warning("底层实现不支持配置热更新，仅更新配置对象")
            self.logger.warning("如需完全应用新配置，请调用 reset_subtitle_display_instance()")

    def _cleanup(self) -> None:
        """
        清理资源（内部方法）

        停止字幕显示并释放相关资源。
        由 reset_subtitle_display_instance() 或应用退出时调用。
        """
        self.logger.info("清理字幕显示资源")

        try:
            # 停止字幕显示
            if hasattr(self, '_implementation') and self._implementation:
                if self.is_running:
                    self.logger.debug("停止字幕显示")
                    self.stop()

                # 清理底层实现
                if hasattr(self._implementation, 'cleanup'):
                    self.logger.debug("清理底层实现资源")
                    self._implementation.cleanup()

            self.logger.info("资源清理完成")

        except Exception as e:
            self.logger.error(f"资源清理过程中出错: {e}")
            # 不抛出异常，确保清理过程能够完成

    def __del__(self):
        """
        析构函数 - 确保资源正确释放

        作为双重保险，在对象被垃圾回收时尝试清理资源。
        """
        try:
            # 仅在实例确实被销毁时清理（而非单例重用）
            if hasattr(self, '_implementation') and self._implementation:
                self._cleanup()
        except Exception:
            # 析构函数中忽略所有异常
            pass