"""音频电平显示组件 (v2.0新增)
实时显示音频输入电平,支持节流更新
"""

import logging
import time
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QProgressBar,
)
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class AudioLevelDisplay(QWidget):
    """音频电平显示组件 (v2.0)

    核心功能:
        - 实时显示音频输入电平
        - 节流更新(防止过于频繁)
        - 根据音频源自动显示/隐藏

    设计特点:
        - 紧凑的水平布局
        - 进度条 + 百分比显示
        - 文件模式下自动隐藏
        - 更新频率限制(100ms)

    使用场景:
        - 麦克风模式: 显示
        - 系统音频模式: 显示
        - 文件模式: 隐藏
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化音频电平显示组件

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # UI组件
        self.label: Optional[QLabel] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.value_label: Optional[QLabel] = None

        # 节流控制
        self._last_update_time: float = 0
        self._update_interval: float = 0.1  # 100ms

        # 初始化UI
        self._setup_ui()

        logger.debug("AudioLevelDisplay initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        # 主布局 - 水平
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 标签
        self.label = QLabel("🎙️ 音频电平:")
        layout.addWidget(self.label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #CCC;
                border-radius: 5px;
                background-color: #F0F0F0;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50,
                    stop:1 #2196F3
                );
                border-radius: 4px;
            }
            """
        )
        layout.addWidget(self.progress_bar)

        # 数值显示
        self.value_label = QLabel("0%")
        self.value_label.setMinimumWidth(40)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.value_label)

        layout.addStretch()  # 添加弹性空间

    # ========== 公共接口 ==========

    def update_level(self, level: float) -> None:
        """更新音频电平 (带节流控制)

        Args:
            level: 电平值 (0.0-1.0)
        """
        # 节流检查
        current_time = time.time()
        if current_time - self._last_update_time < self._update_interval:
            return

        # 限制范围
        level = max(0.0, min(1.0, level))

        # 更新UI
        percentage = int(level * 100)
        self.progress_bar.setValue(percentage)
        self.value_label.setText(f"{percentage}%")

        # 更新时间戳
        self._last_update_time = current_time

    def set_visible_for_source(self, source: str) -> None:
        """根据音频源设置可见性

        Args:
            source: 音频源类型 ('microphone'/'system'/'file')
        """
        # 文件模式下隐藏,其他模式显示
        visible = source in ["microphone", "system"]
        self.setVisible(visible)

        # 隐藏时重置电平
        if not visible:
            self.reset_level()

    def reset_level(self) -> None:
        """重置电平为0"""
        self.progress_bar.setValue(0)
        self.value_label.setText("0%")
        self._last_update_time = 0

    def set_update_interval(self, interval_ms: int) -> None:
        """设置更新间隔

        Args:
            interval_ms: 间隔时间(毫秒)
        """
        self._update_interval = interval_ms / 1000.0
        logger.debug(f"AudioLevelDisplay update interval set to {interval_ms}ms")
