"""Pipeline事件桥接器
将TranscriptionPipeline的事件转换为Qt信号
"""

import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal

from src.coordinator.pipeline import (
    TranscriptionPipeline, PipelineEvent, EventType, PipelineState
)
from src.transcription.models import TranscriptionResult

logger = logging.getLogger(__name__)


class PipelineBridge(QObject):
    """流水线事件桥接器

    负责将Pipeline的回调事件转换为Qt信号，实现线程安全的GUI通信

    核心职责:
        1. 注册Pipeline事件处理器
        2. 将事件转换为Qt信号发射
        3. 确保线程安全通信

    使用方式:
        bridge = PipelineBridge(pipeline)
        bridge.transcription_result.connect(my_slot)
    """

    # Qt信号定义（所有信号必须在类级别定义）
    transcription_started = Signal()                    # 转录已启动
    transcription_stopped = Signal()                    # 转录已停止
    transcription_paused = Signal()                     # 转录已暂停
    transcription_resumed = Signal()                    # 转录已恢复

    new_result = Signal(object)                         # 新转录结果 (TranscriptionResult)
    audio_level_changed = Signal(float)                 # 音频电平变化 (0.0-1.0)
    status_changed = Signal(str, str)                   # 状态变化 (old_state, new_state)
    error_occurred = Signal(str, str)                   # 错误发生 (error_type, error_message)
    latency_updated = Signal(int)                       # 延迟更新 (latency_ms)

    def __init__(self, pipeline: TranscriptionPipeline, parent: Optional[QObject] = None):
        """初始化桥接器

        Args:
            pipeline: TranscriptionPipeline实例
            parent: Qt父对象
        """
        super().__init__(parent)
        self.pipeline = pipeline
        self._register_pipeline_callbacks()
        logger.info("PipelineBridge initialized")

    def _register_pipeline_callbacks(self) -> None:
        """注册Pipeline事件回调

        将Pipeline的事件处理器注册到对应的事件类型
        每个事件类型都有一个lambda函数来发射相应的Qt信号
        """
        # 转录结果事件
        self.pipeline.add_event_handler(
            EventType.TRANSCRIPTION_RESULT,
            self._on_transcription_result
        )

        # 状态变化事件
        self.pipeline.add_event_handler(
            EventType.STATE_CHANGE,
            self._on_state_change
        )

        # 错误事件
        self.pipeline.add_event_handler(
            EventType.ERROR,
            self._on_error
        )

        # 音频数据事件（用于电平监控）
        self.pipeline.add_event_handler(
            EventType.AUDIO_DATA,
            self._on_audio_data
        )

        logger.debug("Pipeline event handlers registered")

    def _on_transcription_result(self, event: PipelineEvent) -> None:
        """处理转录结果事件

        Args:
            event: Pipeline事件对象，data字段包含TranscriptionResult
        """
        if isinstance(event.data, TranscriptionResult):
            # 发射Qt信号（自动在主线程执行）
            self.new_result.emit(event.data)
            logger.debug(f"Transcription result emitted: {event.data.text[:50]}...")

    def _on_state_change(self, event: PipelineEvent) -> None:
        """处理状态变化事件

        Args:
            event: Pipeline事件对象，data字段包含{'old': str, 'new': str}
        """
        if isinstance(event.data, dict):
            old_state = event.data.get('old', '')
            new_state = event.data.get('new', '')

            # 发射状态变化信号
            self.status_changed.emit(old_state, new_state)

            # 根据新状态发射特定信号
            if new_state == PipelineState.RUNNING.value:
                self.transcription_started.emit()
            elif new_state == PipelineState.IDLE.value:
                self.transcription_stopped.emit()

            logger.info(f"Pipeline state changed: {old_state} -> {new_state}")

    def _on_error(self, event: PipelineEvent) -> None:
        """处理错误事件

        Args:
            event: Pipeline事件对象，data字段包含错误信息
        """
        error_type = event.metadata.get('error_type', 'UnknownError')
        error_message = str(event.data)

        self.error_occurred.emit(error_type, error_message)
        logger.error(f"Pipeline error: {error_type} - {error_message}")

    def _on_audio_data(self, event: PipelineEvent) -> None:
        """处理音频数据事件（用于电平监控）

        Args:
            event: Pipeline事件对象，data字段包含AudioChunk
        """
        # 计算音频电平（健壮实现）
        try:
            if not hasattr(event.data, 'data'):
                return

            import numpy as np
            audio_data = event.data.data

            # 验证数据有效性
            if not isinstance(audio_data, np.ndarray) or len(audio_data) == 0:
                return

            # 根据数据类型动态调整归一化参数
            if audio_data.dtype == np.int16:
                max_val = 32768.0  # 16位音频
            elif audio_data.dtype == np.int32:
                max_val = 2147483648.0  # 32位音频
            elif audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                max_val = 1.0  # 浮点音频
            else:
                # 未知格式，使用默认值
                max_val = 32768.0
                logger.debug(f"Unknown audio dtype: {audio_data.dtype}, using default max_val")

            # 计算RMS电平
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))

            # 归一化到0.0-1.0范围
            normalized_level = min(rms / max_val, 1.0) if max_val > 0 else 0.0

            # 发射信号
            self.audio_level_changed.emit(normalized_level)

        except Exception as e:
            # 仅记录调试信息，避免干扰主流程
            logger.debug(f"Failed to calculate audio level: {e}")
