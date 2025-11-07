"""状态监控面板组件
显示转录状态、音频电平等实时信息
"""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QGroupBox, QGridLayout
)
from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


class StatusMonitorPanel(QWidget):
    """状态监控面板

    核心功能:
        - 转录状态显示
        - 音频源信息显示
        - 模型信息显示
        - GPU状态显示
        - 音频电平实时显示
        - 处理延迟显示（可选）
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化状态监控面板

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # UI组件
        self.status_label: Optional[QLabel] = None
        self.audio_source_label: Optional[QLabel] = None
        self.model_label: Optional[QLabel] = None
        self.gpu_label: Optional[QLabel] = None
        self.audio_level_bar: Optional[QProgressBar] = None
        self.latency_label: Optional[QLabel] = None

        # 初始化UI
        self._setup_ui()

        logger.debug("StatusMonitorPanel initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建分组框
        group_box = QGroupBox("实时状态监控")
        group_box_layout = QGridLayout(group_box)

        # 状态信息（使用网格布局）
        row = 0

        # 状态行
        group_box_layout.addWidget(QLabel("状态:"), row, 0)
        self.status_label = QLabel("✅ 就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        group_box_layout.addWidget(self.status_label, row, 1)
        row += 1

        # 音频源行
        group_box_layout.addWidget(QLabel("音频源:"), row, 0)
        self.audio_source_label = QLabel("🎤 未选择")
        group_box_layout.addWidget(self.audio_source_label, row, 1)
        row += 1

        # 模型行
        group_box_layout.addWidget(QLabel("模型:"), row, 0)
        self.model_label = QLabel("未加载")
        self.model_label.setWordWrap(True)
        group_box_layout.addWidget(self.model_label, row, 1)
        row += 1

        # GPU行
        group_box_layout.addWidget(QLabel("GPU:"), row, 0)
        self.gpu_label = QLabel("⏳ 检测中...")
        group_box_layout.addWidget(self.gpu_label, row, 1)
        row += 1

        # 音频电平行
        group_box_layout.addWidget(QLabel("音频电平:"), row, 0)
        self.audio_level_bar = QProgressBar()
        self.audio_level_bar.setRange(0, 100)
        self.audio_level_bar.setValue(0)
        self.audio_level_bar.setTextVisible(True)
        self.audio_level_bar.setFormat("%v%")
        group_box_layout.addWidget(self.audio_level_bar, row, 1)
        row += 1

        # 处理延迟行
        group_box_layout.addWidget(QLabel("处理延迟:"), row, 0)
        self.latency_label = QLabel("-- ms")
        group_box_layout.addWidget(self.latency_label, row, 1)

        # 添加到主布局
        main_layout.addWidget(group_box)

    @Slot(str)
    def update_status(self, status_text: str) -> None:
        """更新转录状态

        Args:
            status_text: 状态文本
        """
        self.status_label.setText(status_text)
        logger.debug(f"Status updated: {status_text}")

    @Slot(str)
    def update_audio_source(self, source_text: str) -> None:
        """更新音频源信息

        Args:
            source_text: 音频源文本
        """
        self.audio_source_label.setText(source_text)
        logger.debug(f"Audio source updated: {source_text}")

    @Slot(str)
    def update_model(self, model_text: str) -> None:
        """更新模型信息

        Args:
            model_text: 模型文本
        """
        self.model_label.setText(model_text)
        logger.debug(f"Model updated: {model_text}")

    @Slot(bool, str)
    def update_gpu_status(self, gpu_available: bool, gpu_info: str = "") -> None:
        """更新GPU状态

        Args:
            gpu_available: GPU是否可用
            gpu_info: GPU信息（可选）
        """
        if gpu_available:
            text = f"✅ 已启用 {gpu_info}"
        else:
            text = "❌ 未启用 (使用CPU)"

        self.gpu_label.setText(text)
        logger.debug(f"GPU status updated: {text}")

    @Slot(float)
    def update_audio_level(self, level: float) -> None:
        """更新音频电平（0.0-1.0）

        Args:
            level: 音频电平（0.0-1.0）
        """
        # 转换为百分比
        percentage = int(level * 100)
        self.audio_level_bar.setValue(percentage)

    @Slot(int)
    def update_latency(self, latency_ms: int) -> None:
        """更新处理延迟

        Args:
            latency_ms: 延迟（毫秒）
        """
        self.latency_label.setText(f"{latency_ms} ms")

        # 根据延迟设置颜色
        if latency_ms < 500:
            color = "green"
        elif latency_ms < 2000:
            color = "orange"
        else:
            color = "red"

        self.latency_label.setStyleSheet(f"color: {color}; font-weight: bold;")
