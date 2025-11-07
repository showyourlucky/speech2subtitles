# -*- coding: utf-8 -*-
"""
转录引擎管理器 (Transcription Engine Manager)

提供单例模式的转录引擎管理，支持引擎复用和资源优化。

主要特性:
- 单例模式：全局唯一的引擎管理器
- 引擎复用：相同配置下复用已加载的引擎
- 智能释放：仅在配置变化或显式释放时卸载模型
- 线程安全：使用锁保护并发访问
- 统计监控：记录引擎复用和加载统计

Author: Speech2Subtitles Project
Created: 2025-11-05
"""

import logging
import threading
from typing import Optional, Dict, Any
from datetime import datetime

from .engine import TranscriptionEngine
from .models import TranscriptionConfig

logger = logging.getLogger(__name__)


class TranscriptionEngineManager:
    """
    转录引擎管理器（单例模式）

    负责转录引擎的生命周期管理，包括创建、复用和释放。
    使用单例模式确保全局只有一个引擎管理器实例。

    主要职责:
    1. 引擎实例管理：创建、缓存和复用TranscriptionEngine
    2. 配置变更检测：自动检测配置变化并重新加载模型
    3. 资源生命周期：统一管理模型资源的加载和释放
    4. 统计信息：记录引擎使用情况和性能指标

    线程安全:
    - 使用threading.Lock保护所有共享状态
    - 支持多线程并发访问

    使用示例:
    ```python
    # 获取引擎（首次加载模型）
    config = TranscriptionConfig(model_path="model.onnx")
    engine = TranscriptionEngineManager.get_engine(config)

    # 再次获取（复用已加载的引擎）
    engine2 = TranscriptionEngineManager.get_engine(config)  # 无需重新加载

    # 应用退出时释放
    TranscriptionEngineManager.release()
    ```
    """

    # 单例实例（类变量）
    _instance: Optional['TranscriptionEngineManager'] = None
    _lock = threading.Lock()  # 保护单例创建的锁

    def __init__(self):
        """
        私有初始化方法

        注意：不要直接调用，请使用get_engine()类方法
        """
        # 当前缓存的引擎实例
        self._engine: Optional[TranscriptionEngine] = None

        # 当前引擎的配置快照
        self._current_config: Optional[TranscriptionConfig] = None

        # 实例操作锁（保护引擎访问）
        self._engine_lock = threading.Lock()

        # 统计信息
        self._stats = {
            "engine_loads": 0,       # 引擎加载次数
            "engine_reuses": 0,      # 引擎复用次数
            "last_load_time": None,  # 最后加载时间
            "current_model": None    # 当前模型路径
        }

        logger.info("TranscriptionEngineManager initialized")

    @classmethod
    def get_instance(cls) -> 'TranscriptionEngineManager':
        """
        获取单例实例（懒加载）

        线程安全的单例模式实现，首次调用时创建实例。

        Returns:
            TranscriptionEngineManager: 全局唯一的管理器实例
        """
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定（避免竞态条件）
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def get_engine(cls, config: TranscriptionConfig) -> TranscriptionEngine:
        """
        获取或创建转录引擎（智能复用）

        根据配置决定是否需要重新加载模型：
        - 配置未变化：直接返回缓存的引擎（快速）
        - 配置已变化：释放旧引擎，加载新引擎（慢速）

        Args:
            config: 转录配置对象

        Returns:
            TranscriptionEngine: 可用的转录引擎实例

        Raises:
            ModelLoadError: 模型加载失败
            ConfigurationError: 配置参数错误
        """
        instance = cls.get_instance()

        with instance._engine_lock:
            # 检查是否需要重新加载
            need_reload = instance._should_reload(config)

            if need_reload:
                # 需要重新加载模型
                logger.info("Configuration changed, reloading transcription engine...")

                # 释放旧引擎（如果存在）
                if instance._engine:
                    logger.info(f"Releasing old engine (model: {instance._stats['current_model']})")
                    instance._release_engine()

                # 加载新引擎
                logger.info(f"Loading new engine (model: {config.model_path})")
                start_time = datetime.now()

                instance._engine = TranscriptionEngine(config)
                instance._current_config = config

                load_time = (datetime.now() - start_time).total_seconds()

                # 更新统计
                instance._stats["engine_loads"] += 1
                instance._stats["last_load_time"] = datetime.now()
                instance._stats["current_model"] = config.model_path

                logger.info(f"Engine loaded successfully in {load_time:.2f}s "
                          f"(total loads: {instance._stats['engine_loads']})")
            else:
                # 复用现有引擎
                instance._stats["engine_reuses"] += 1
                logger.info(f"Reusing cached engine (reuses: {instance._stats['engine_reuses']}, "
                          f"model: {instance._stats['current_model']})")

            return instance._engine

    def _should_reload(self, new_config: TranscriptionConfig) -> bool:
        """
        判断是否需要重新加载模型

        比较新旧配置，检测关键参数是否变化。

        关键参数包括:
        - model_path: 模型文件路径
        - use_gpu: GPU使用标志
        - sample_rate: 采样率

        Args:
            new_config: 新的配置对象

        Returns:
            bool: True表示需要重新加载，False表示可以复用
        """
        # 首次加载
        if self._engine is None or self._current_config is None:
            return True

        old = self._current_config

        # 检查模型路径是否变化（最关键）
        if old.model_path != new_config.model_path:
            logger.debug(f"Model path changed: {old.model_path} -> {new_config.model_path}")
            return True

        # 检查GPU配置是否变化
        if old.use_gpu != new_config.use_gpu:
            logger.debug(f"GPU setting changed: {old.use_gpu} -> {new_config.use_gpu}")
            return True

        # 检查采样率是否变化
        if old.sample_rate != new_config.sample_rate:
            logger.debug(f"Sample rate changed: {old.sample_rate} -> {new_config.sample_rate}")
            return True

        # 配置未变化，可以复用
        return False

    def _release_engine(self) -> None:
        """
        释放当前引擎资源（内部方法）

        关闭引擎并清理相关资源。
        注意：此方法应在持有_engine_lock的情况下调用。
        """
        if self._engine:
            try:
                self._engine.close()
            except Exception as e:
                logger.error(f"Error closing engine: {e}")
            finally:
                self._engine = None
                self._current_config = None

    @classmethod
    def release(cls) -> None:
        """
        释放所有引擎资源（应用退出时调用）

        主动释放缓存的引擎，清理模型资源。
        通常在以下场景调用：
        1. 应用程序退出时
        2. 主窗口关闭时
        3. 需要强制重新加载模型时

        线程安全，可以在任何线程调用。
        """
        instance = cls.get_instance()

        with instance._engine_lock:
            if instance._engine:
                logger.info("Releasing TranscriptionEngine resources...")
                instance._release_engine()
                logger.info("Resources released successfully")
            else:
                logger.debug("No engine to release")

    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """
        获取引擎使用统计信息

        Returns:
            Dict[str, Any]: 包含以下统计数据：
                - engine_loads: 引擎加载次数
                - engine_reuses: 引擎复用次数
                - last_load_time: 最后加载时间
                - current_model: 当前模型路径
                - has_engine: 是否有活跃引擎
        """
        instance = cls.get_instance()

        with instance._engine_lock:
            stats = instance._stats.copy()
            stats["has_engine"] = instance._engine is not None
            return stats

    @classmethod
    def is_engine_loaded(cls) -> bool:
        """
        检查是否有已加载的引擎

        Returns:
            bool: True表示引擎已加载，False表示未加载
        """
        instance = cls.get_instance()
        with instance._engine_lock:
            return instance._engine is not None

    @classmethod
    def get_current_model_path(cls) -> Optional[str]:
        """
        获取当前加载的模型路径

        Returns:
            Optional[str]: 模型路径，如果未加载则返回None
        """
        instance = cls.get_instance()
        with instance._engine_lock:
            return instance._stats.get("current_model")

    def __repr__(self) -> str:
        """字符串表示"""
        with self._engine_lock:
            return (f"TranscriptionEngineManager("
                   f"loaded={self._engine is not None}, "
                   f"loads={self._stats['engine_loads']}, "
                   f"reuses={self._stats['engine_reuses']}, "
                   f"model={self._stats['current_model']})")
