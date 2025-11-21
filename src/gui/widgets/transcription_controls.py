"""转录控制组件 (v2.0 - 简化版)
只保留核心控制按钮,统计信息移至状态栏
"""

import logging
from typing import Optional

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Slot

from src.gui.models.gui_models import TranscriptionState

logger = logging.getLogger(__name__)


class TranscriptionControls(QWidget):
    """转录控制组件 (v2.0)

    核心功能:
        - 开始/暂停/停止按钮
        - 按钮状态管理

    变更 (v1.0 -> v2.0):
        - 移除状态显示(移至状态栏)
        - 移除时长显示(移至状态栏)
        - 简化布局,只保留按钮
        - 去除分组框,更紧凑

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
        """初始化转录控制组件

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # 内部状态
        self._current_state = TranscriptionState.READY

        # UI组件
        self.start_button: Optional[QPushButton] = None
        self.pause_button: Optional[QPushButton] = None
        self.stop_button: Optional[QPushButton] = None

        # 初始化UI
        self._setup_ui()
        self._update_button_states()

        logger.debug("TranscriptionControls v2.0 initialized")

    def _setup_ui(self) -> None:
        """设置UI布局 (v2.0 - 水平布局,无分组框)"""
        # 主布局 - 水平
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 开始按钮
        self.start_button = QPushButton("▶️ 开始")
        self.start_button.setMinimumSize(100, 36)
        self.start_button.setObjectName("start_button")  # 用于样式表
        self.start_button.setToolTip("开始转录 (Ctrl+R)")
        self.start_button.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_button)

        # 暂停按钮
        self.pause_button = QPushButton("⏸️ 暂停")
        self.pause_button.setMinimumSize(100, 36)
        self.pause_button.setObjectName("pause_button")
        self.pause_button.setToolTip("暂停转录 (Ctrl+P)")
        self.pause_button.clicked.connect(self._on_pause_clicked)
        layout.addWidget(self.pause_button)

        # 停止按钮
        self.stop_button = QPushButton("⏹️ 停止")
        self.stop_button.setMinimumSize(100, 36)
        self.stop_button.setObjectName("stop_button")
        self.stop_button.setToolTip("停止转录 (Ctrl+T)")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        layout.addWidget(self.stop_button)

        layout.addStretch()  # 右侧添加弹性空间

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

    # ========== 公共接口 ==========

    def set_state(self, state: TranscriptionState) -> None:
        """设置控制组件状态

        Args:
            state: 新的转录状态
        """
        self._current_state = state
        self._update_button_states()
        logger.debug(f"TranscriptionControls state changed to: {state.value}")

    def get_state(self) -> TranscriptionState:
        """获取当前状态

        Returns:
            TranscriptionState: 当前转录状态
        """
        return self._current_state

    def _update_button_states(self) -> None:
        """更新按钮启用/禁用状态"""
        state = self._current_state

        # 开始按钮
        self.start_button.setEnabled(
            state
            in [
                TranscriptionState.READY,
                TranscriptionState.STOPPED,
                TranscriptionState.PAUSED,
            ]
        )
        # 暂停状态下显示"继续"
        if state == TranscriptionState.PAUSED:
            self.start_button.setText("▶️ 继续")
        else:
            self.start_button.setText("▶️ 开始")

        # 暂停按钮（仅运行时可用）
        self.pause_button.setEnabled(state == TranscriptionState.RUNNING)

        # 停止按钮
        self.stop_button.setEnabled(
            state in [TranscriptionState.RUNNING, TranscriptionState.PAUSED]
        )
