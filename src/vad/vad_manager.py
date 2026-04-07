# -*- coding: utf-8 -*-
"""
VAD 检测器管理器 (VAD Detector Manager)

提供单例模式的 VAD 检测器管理，支持检测器复用和资源优化。

主要特性:
- 单例模式：全局唯一的 VAD 管理器
- 检测器复用：相同配置下复用已加载的检测器
- 智能释放：仅在配置变化或显式释放时卸载模型
- 线程安全：使用锁保护并发访问
- 统计监控：记录检测器复用和加载统计

Author: Speech2Subtitles Project
Created: 2025-11-06
"""

import logging
import threading
from typing import Optional, Dict, Any
from datetime import datetime

from .detector import VoiceActivityDetector
from .models import VadConfig

logger = logging.getLogger(__name__)


class VadManager:
    """
    VAD 检测器管理器（单例模式）

    负责 VAD 检测器的生命周期管理，包括创建、复用和释放。
    使用单例模式确保全局只有一个 VAD 管理器实例。

    主要职责:
    1. 检测器实例管理：创建、缓存和复用 VoiceActivityDetector
    2. 配置变更检测：自动检测配置变化并重新加载模型
    3. 资源生命周期：统一管理模型资源的加载和释放
    4. 统计信息：记录检测器使用情况和性能指标

    线程安全:
    - 使用 threading.Lock 保护所有共享状态
    - 支持多线程并发访问

    使用示例:
    ```python
    # 获取检测器（首次加载模型）
    config = VadConfig()
    detector = VadManager.get_detector(config)

    # 再次获取（复用已加载的检测器）
    detector2 = VadManager.get_detector(config)  # 无需重新加载

    # 应用退出时释放
    VadManager.release()
    ```
    """

    # 单例实例（类变量）
    _instance: Optional['VadManager'] = None
    _lock = threading.Lock()  # 保护单例创建的锁

    def __init__(self):
        """
        私有初始化方法

        注意：不要直接调用，请使用 get_detector() 类方法
        """
        # 当前缓存的检测器实例
        self._detector: Optional[VoiceActivityDetector] = None

        # 当前检测器的配置快照
        self._current_config: Optional[VadConfig] = None

        # 实例操作锁（保护检测器访问）
        self._detector_lock = threading.Lock()

        # 统计信息
        self._stats = {
            "detector_loads": 0,       # 检测器加载次数
            "detector_reuses": 0,      # 检测器复用次数
            "last_load_time": None,    # 最后加载时间
            "current_model": None      # 当前模型类型
        }

        logger.info("VadManager initialized")

    @classmethod
    def get_instance(cls) -> 'VadManager':
        """
        获取单例实例（懒加载）

        线程安全的单例模式实现，首次调用时创建实例。

        Returns:
            VadManager: 全局唯一的管理器实例
        """
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定（避免竞态条件）
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def get_detector(cls, config: VadConfig) -> VoiceActivityDetector:
        """
        获取或创建 VAD 检测器（智能复用）

        根据配置决定是否需要重新加载模型：
        - 配置未变化：直接返回缓存的检测器（快速）
        - 配置已变化：释放旧检测器，加载新检测器（慢速）

        Args:
            config: VAD 配置对象

        Returns:
            VoiceActivityDetector: 可用的 VAD 检测器实例

        Raises:
            ModelLoadError: 模型加载失败
            ConfigurationError: 配置参数错误
        """
        instance = cls.get_instance()

        with instance._detector_lock:
            # 检查是否需要重新加载
            need_reload = instance._should_reload(config)

            if need_reload:
                # 需要重新加载模型
                logger.info("加载VAD detector...")

                # 释放旧检测器（如果存在）
                if instance._detector:
                    logger.info(f"存在老的 vad 检测器 (模型: {instance._stats['current_model']})")
                    instance._release_detector()

                # 加载新检测器
                logger.info(f"正在加载新的 vad 检测器 (模型: {config.model.value})")
                start_time = datetime.now()

                instance._detector = VoiceActivityDetector(config)
                instance._current_config = config

                load_time = (datetime.now() - start_time).total_seconds()

                # 更新统计
                instance._stats["detector_loads"] += 1
                instance._stats["last_load_time"] = datetime.now()
                instance._stats["current_model"] = config.model.value

                logger.info(f"vad 检测器已成功加载，耗时 {load_time:.2f}s "
                          f"(总加载次数: {instance._stats['detector_loads']})")
            else:
                # 复用现有检测器
                instance._stats["detector_reuses"] += 1
                logger.info(f"复用缓存的 detector (reuses: {instance._stats['detector_reuses']}, "
                          f"模型: {instance._stats['current_model']})")
            # 打印config参数
            logger.info(f"VAD Config: {config}")
            return instance._detector

    def _should_reload(self, new_config: VadConfig) -> bool:
        """
        判断是否需要重新加载模型

        比较新旧配置，检测关键参数是否变化。

        关键参数包括:
        - model: VAD 模型类型（SILERO/TEN_VAD）
        - use_sherpa_onnx: 是否使用 sherpa-onnx 实现
        - threshold: VAD 阈值
        - sample_rate: 采样率

        Args:
            new_config: 新的配置对象

        Returns:
            bool: True 表示需要重新加载，False 表示可以复用
        """
        # 首次加载
        if self._detector is None or self._current_config is None:
            return True

        old = self._current_config

        # 检查模型类型是否变化
        if old.model != new_config.model:
            logger.debug(f"Model type changed: {old.model} -> {new_config.model}")
            return True

        # 检查 sherpa-onnx 配置是否变化
        if old.use_sherpa_onnx != new_config.use_sherpa_onnx:
            logger.debug(f"Sherpa-onnx setting changed: {old.use_sherpa_onnx} -> {new_config.use_sherpa_onnx}")
            return True

        # 检查阈值是否变化（影响检测结果）
        if abs(old.threshold - new_config.threshold) > 0.001:
            logger.debug(f"Threshold changed: {old.threshold} -> {new_config.threshold}")
            return True

        # 检查采样率是否变化
        if old.sample_rate != new_config.sample_rate:
            logger.debug(f"Sample rate changed: {old.sample_rate} -> {new_config.sample_rate}")
            return True

        # 配置未变化，可以复用
        return False

    def _release_detector(self) -> None:
        """
        释放当前检测器资源（内部方法）

        清理检测器并重置相关状态。
        注意：此方法应在持有 _detector_lock 的情况下调用。
        """
        if self._detector:
            try:
                # VAD 检测器没有显式的 close 方法
                # 只需要解除引用，让 Python GC 回收
                self._detector = None
                logger.debug("Detector released")
            except Exception as e:
                logger.error(f"Error releasing detector: {e}")
            finally:
                self._detector = None
                self._current_config = None

    @classmethod
    def release(cls) -> None:
        """
        释放所有检测器资源（应用退出时调用）

        主动释放缓存的检测器，清理模型资源。
        通常在以下场景调用：
        1. 应用程序退出时
        2. 主窗口关闭时
        3. 需要强制重新加载模型时

        线程安全，可以在任何线程调用。
        """
        instance = cls.get_instance()

        with instance._detector_lock:
            if instance._detector:
                logger.info("Releasing VAD Detector resources...")
                instance._release_detector()
                logger.info("Resources released successfully")
            else:
                logger.debug("No detector to release")

    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """
        获取检测器使用统计信息

        Returns:
            Dict[str, Any]: 包含以下统计数据：
                - detector_loads: 检测器加载次数
                - detector_reuses: 检测器复用次数
                - last_load_time: 最后加载时间
                - current_model: 当前模型类型
                - has_detector: 是否有活跃检测器
        """
        instance = cls.get_instance()

        with instance._detector_lock:
            stats = instance._stats.copy()
            stats["has_detector"] = instance._detector is not None
            return stats

    @classmethod
    def is_detector_loaded(cls) -> bool:
        """
        检查是否有已加载的检测器

        Returns:
            bool: True 表示检测器已加载，False 表示未加载
        """
        instance = cls.get_instance()
        with instance._detector_lock:
            return instance._detector is not None

    @classmethod
    def get_current_model_type(cls) -> Optional[str]:
        """
        获取当前加载的模型类型

        Returns:
            Optional[str]: 模型类型（如 'silero'），如果未加载则返回 None
        """
        instance = cls.get_instance()
        with instance._detector_lock:
            return instance._stats.get("current_model")

    def __repr__(self) -> str:
        """字符串表示"""
        with self._detector_lock:
            return (f"VadManager("
                   f"loaded={self._detector is not None}, "
                   f"loads={self._stats['detector_loads']}, "
                   f"reuses={self._stats['detector_reuses']}, "
                   f"model={self._stats['current_model']})")
