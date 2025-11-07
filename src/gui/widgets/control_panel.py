"""转录控制面板组件
提供转录的开始、暂停、停止控制
"""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QGroupBox
)
from PySide6.QtCore import Signal, Slot, QTimer
from PySide6.QtGui import QFont
from datetime import timedelta

from src.gui.models.gui_models import TranscriptionState

logger = logging.getLogger(__name__)


class TranscriptionControlPanel(QWidget):
    """转录控制面板

    核心功能:
        - 开始/暂停/停止按钮
        - 状态显示（图标+文字）
        - 转录时长显示
        - 按钮状态管理

    信号:
        start_requested: 用户点击开始按钮
        pause_requested: 用户点击暂停按钮
        stop_requested: 用户点击停止按钮
    """

    # 信号定义
    start_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化控制面板

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # 内部状态
        self._current_state = TranscriptionState.READY
        self._start_time: Optional[float] = None
        self._elapsed_seconds = 0

        # UI组件
        self.start_button: Optional[QPushButton] = None
        self.pause_button: Optional[QPushButton] = None
        self.stop_button: Optional[QPushButton] = None
        self.status_label: Optional[QLabel] = None
        self.duration_label: Optional[QLabel] = None

        # 定时器（用于更新时长）
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_duration)

        # 初始化UI
        self._setup_ui()
        self._update_button_states()

        logger.debug("TranscriptionControlPanel initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建分组框
        group_box = QGroupBox("转录控制")
        group_box_layout = QVBoxLayout(group_box)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 开始按钮
        self.start_button = QPushButton("开始转录")
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self._on_start_clicked)
        button_layout.addWidget(self.start_button)

        # 暂停按钮
        self.pause_button = QPushButton("暂停")
        self.pause_button.setMinimumHeight(40)
        self.pause_button.clicked.connect(self._on_pause_clicked)
        button_layout.addWidget(self.pause_button)

        # 停止按钮
        self.stop_button = QPushButton("停止")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        button_layout.addWidget(self.stop_button)

        group_box_layout.addLayout(button_layout)

        # 状态信息布局
        info_layout = QHBoxLayout()

        # 状态标签
        status_container = QVBoxLayout()
        status_title = QLabel("状态:")
        self.status_label = QLabel("⚫ 就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        status_container.addWidget(status_title)
        status_container.addWidget(self.status_label)
        info_layout.addLayout(status_container)

        # 时长标签
        duration_container = QVBoxLayout()
        duration_title = QLabel("时长:")
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFont(QFont("Courier New", 10))
        duration_container.addWidget(duration_title)
        duration_container.addWidget(self.duration_label)
        info_layout.addLayout(duration_container)

        group_box_layout.addLayout(info_layout)

        # 添加到主布局
        main_layout.addWidget(group_box)

    @Slot()
    def _on_start_clicked(self) -> None:
        """处理开始按钮点击"""
        logger.info("Start button clicked")
        self.start_requested.emit()

    @Slot()
    def _on_pause_clicked(self) -> None:
        """处理暂停按钮点击"""
        logger.info("Pause button clicked")
        self.pause_requested.emit()

    @Slot()
    def _on_stop_clicked(self) -> None:
        """处理停止按钮点击"""
        logger.info("Stop button clicked")
        self.stop_requested.emit()

    @Slot(TranscriptionState)
    def set_state(self, state: TranscriptionState) -> None:
        """设置控制面板状态

        Args:
            state: 新的转录状态
        """
        self._current_state = state
        self._update_button_states()
        self._update_status_display()

        # 处理计时器
        if state == TranscriptionState.RUNNING:
            if not self.timer.isActive():
                import time
                self._start_time = time.time()
                self.timer.start(1000)  # 每秒更新一次
        elif state in [TranscriptionState.STOPPED, TranscriptionState.ERROR]:
            self.timer.stop()
            self._elapsed_seconds = 0
            self.duration_label.setText("00:00:00")
        elif state == TranscriptionState.PAUSED:
            self.timer.stop()

        logger.debug(f"Control panel state changed to: {state.value}")

    def _update_button_states(self) -> None:
        """更新按钮启用/禁用状态"""
        state = self._current_state

        # 开始按钮
        self.start_button.setEnabled(
            state in [TranscriptionState.READY, TranscriptionState.STOPPED, TranscriptionState.PAUSED]
        )
        if state == TranscriptionState.PAUSED:
            self.start_button.setText("继续")
        else:
            self.start_button.setText("开始转录")

        # 暂停按钮（仅运行时可用）
        self.pause_button.setEnabled(state == TranscriptionState.RUNNING)

        # 停止按钮
        self.stop_button.setEnabled(
            state in [TranscriptionState.RUNNING, TranscriptionState.PAUSED]
        )

    def _update_status_display(self) -> None:
        """更新状态显示"""
        state = self._current_state

        # 状态图标映射
        icon_map = {
            TranscriptionState.READY: "⚫",
            TranscriptionState.RUNNING: "🟢",
            TranscriptionState.PAUSED: "🟡",
            TranscriptionState.STOPPED: "🔵",
            TranscriptionState.ERROR: "🔴",
        }

        icon = icon_map.get(state, "⚫")
        text = state.to_display_text()
        color = state.to_color()

        self.status_label.setText(f"{icon} {text}")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    @Slot()
    def _update_duration(self) -> None:
        """更新转录时长显示"""
        if self._start_time is not None:
            import time
            self._elapsed_seconds = int(time.time() - self._start_time)

            # 格式化为 HH:MM:SS
            td = timedelta(seconds=self._elapsed_seconds)
            hours, remainder = divmod(td.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            self.duration_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
