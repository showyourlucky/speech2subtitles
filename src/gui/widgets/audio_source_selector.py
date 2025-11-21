"""音频源选择组件 (v2.0 - 下拉框版本)
提供麦克风、系统音频、文件的选择功能
使用QComboBox替代单选按钮组,更简洁紧凑
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QComboBox,
)
from PySide6.QtCore import Signal, Slot

logger = logging.getLogger(__name__)


class AudioSourceSelector(QWidget):
    """音频源选择器 (v2.0)

    核心功能:
        - 音频源类型选择（下拉框）
        - 简洁紧凑的UI设计

    变更 (v1.0 -> v2.0):
        - 使用QComboBox替代QRadioButton组
        - 移除文件列表管理（由FileSelectionPanel负责）
        - 添加图标支持(Emoji)

    信号:
        source_changed: 音频源发生变化 (str: 'microphone'/'system'/'file')
    """

    # 信号定义 - 发射音频源类型字符串
    source_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化音频源选择器

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # UI组件
        self.source_combo: Optional[QComboBox] = None
        self.source_label: Optional[QLabel] = None

        # 当前选择
        self._current_source: str = "microphone"

        # 初始化UI
        self._setup_ui()

        logger.debug("AudioSourceSelector v2.0 initialized")

    def _setup_ui(self) -> None:
        """设置UI布局 (v2.0 - 水平布局 + 下拉框)"""
        # 主布局 - 水平
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 标签
        self.source_label = QLabel("🎤 音频源:")
        layout.addWidget(self.source_label)

        # 下拉框
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(150)

        # 添加选项（使用Emoji图标）
        self.source_combo.addItem("🎤 麦克风", "microphone")
        self.source_combo.addItem("🔊 系统音频", "system")
        # 有批量转录够用了, 这个隐藏吧
        # self.source_combo.addItem("📁 文件", "file")

        # 设置工具提示
        self.source_combo.setToolTip("选择音频输入源")

        # 连接信号
        self.source_combo.currentIndexChanged.connect(self._on_selection_changed)

        layout.addWidget(self.source_combo)
        layout.addStretch()  # 添加弹性空间

    @Slot(int)
    def _on_selection_changed(self, index: int) -> None:
        """处理下拉框选择变化

        Args:
            index: 选择的索引
        """
        # 获取选择的音频源类型
        source_type = self.source_combo.itemData(index)

        if source_type:
            self._current_source = source_type
            self.source_changed.emit(source_type)
            logger.debug(f"Audio source changed to: {source_type}")

    # ========== 公共接口 ==========

    def get_selected_source(self) -> str:
        """获取当前选择的音频源类型

        Returns:
            str: 音频源类型 ('microphone'/'system'/'file')
        """
        return self._current_source

    def set_source(self, source_type: str) -> None:
        """设置音频源

        Args:
            source_type: 音频源类型 ('microphone'/'system'/'file')
        """
        # 查找对应的索引
        for i in range(self.source_combo.count()):
            if self.source_combo.itemData(i) == source_type:
                self.source_combo.setCurrentIndex(i)
                break

    def set_enabled(self, enabled: bool) -> None:
        """设置是否可选择（转录中禁用）

        Args:
            enabled: 是否启用
        """
        self.source_combo.setEnabled(enabled)
        self.source_label.setEnabled(enabled)
