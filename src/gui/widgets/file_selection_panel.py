"""文件选择面板组件 (v2.0新增)
提供文件列表管理功能，支持按需展开/收起
仅在选择"文件"音频源时显示
"""

import logging
import time
from typing import List, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QLabel,
)
from PySide6.QtCore import Signal, Slot, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


class FileSelectionPanel(QWidget):
    """文件选择面板 (v2.0)

    核心功能:
        - 多文件选择和管理
        - 批量操作(添加/移除/清空)
        - 支持复选框批量删除
        - 平滑展开/收起动画

    设计特点:
        - 默认隐藏,仅在文件模式下显示
        - 支持动画展开/收起(200ms)
        - 文件列表包含复选框支持

    信号:
        files_changed: 文件列表发生变化 (List[str])
    """

    # 信号定义
    files_changed = Signal(list)  # List[str] 文件路径列表

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化文件选择面板

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # 文件路径列表
        self.file_paths: List[str] = []

        # UI组件
        self.title_label: Optional[QLabel] = None
        self.file_list_widget: Optional[QListWidget] = None
        self.browse_button: Optional[QPushButton] = None
        self.select_all_button: Optional[QPushButton] = None
        self.remove_button: Optional[QPushButton] = None
        self.clear_button: Optional[QPushButton] = None

        # 动画对象
        self._animation: Optional[QPropertyAnimation] = None
        self._is_visible: bool = False
        self._target_height: int = 200  # 展开时的目标高度

        # 初始化UI
        self._setup_ui()

        # 默认隐藏
        self.setMaximumHeight(0)
        self.hide()

        logger.debug("FileSelectionPanel initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题行
        title_layout = QHBoxLayout()
        self.title_label = QLabel("📁 待转录文件:")
        title_font = QFont()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 文件列表
        self.file_list_widget = QListWidget()
        self.file_list_widget.setMaximumHeight(100)
        self.file_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.file_list_widget.setWordWrap(False)
        # 连接复选框状态变化信号
        self.file_list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.file_list_widget)

        # 按钮行
        button_layout = QHBoxLayout()

        self.browse_button = QPushButton("添加文件")
        self.browse_button.setFixedWidth(80)
        self.browse_button.clicked.connect(self._on_browse_clicked)
        button_layout.addWidget(self.browse_button)

        self.select_all_button = QPushButton("全选")
        self.select_all_button.setFixedWidth(60)
        self.select_all_button.setEnabled(False)
        self.select_all_button.clicked.connect(self._on_toggle_select_all_clicked)
        button_layout.addWidget(self.select_all_button)

        self.remove_button = QPushButton("移除选中")
        self.remove_button.setFixedWidth(80)
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self._on_remove_clicked)
        button_layout.addWidget(self.remove_button)

        self.clear_button = QPushButton("清空列表")
        self.clear_button.setFixedWidth(80)
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        button_layout.addWidget(self.clear_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    @Slot()
    def _on_browse_clicked(self) -> None:
        """处理添加文件按钮点击"""
        # 打开文件对话框（多选）
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择音频或视频文件（可多选）",
            "",
            "媒体文件 (*.mp3 *.wav *.flac *.m4a *.ogg *.mp4 *.avi *.mkv "
            "*.mov *.flv *.webm);;所有文件 (*.*)",
        )

        if file_paths:
            # 添加到文件列表
            for file_path in file_paths:
                if file_path not in self.file_paths:
                    self.file_paths.append(file_path)
                    # 添加到显示列表（只显示文件名）
                    file_name = Path(file_path).name
                    item = QListWidgetItem(file_name)
                    # 设置工具提示显示完整路径
                    item.setToolTip(file_path)
                    # 存储完整路径作为数据
                    item.setData(Qt.UserRole, file_path)
                    # 添加复选框支持
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)  # 默认未勾选
                    self.file_list_widget.addItem(item)

            logger.info(
                f"{len(file_paths)} file(s) added, total: {len(self.file_paths)}"
            )

            # 更新按钮状态
            self._update_button_states()

            # 发射信号
            self.files_changed.emit(self.file_paths.copy())

    @Slot()
    def _on_remove_clicked(self) -> None:
        """移除所有勾选的文件"""
        checked_items = self._get_checked_items()

        if not checked_items:
            logger.debug("No files checked for removal")
            return

        # 收集要删除的文件路径
        files_to_remove = []
        for item in checked_items:
            file_path = item.data(Qt.UserRole)
            files_to_remove.append(file_path)

        # 从内部列表移除
        for file_path in files_to_remove:
            if file_path in self.file_paths:
                self.file_paths.remove(file_path)

        # 从UI中移除（逆序删除，避免索引问题）
        for item in reversed(checked_items):
            row = self.file_list_widget.row(item)
            self.file_list_widget.takeItem(row)

        logger.info(f"{len(files_to_remove)} file(s) removed")

        # 更新按钮状态
        self._update_button_states()

        # 发射信号
        self.files_changed.emit(self.file_paths.copy())

    @Slot()
    def _on_clear_clicked(self) -> None:
        """清空文件列表"""
        self.file_paths.clear()
        self.file_list_widget.clear()
        logger.info("File list cleared")

        # 更新按钮状态
        self._update_button_states()

        # 发射信号
        self.files_changed.emit([])

    @Slot()
    def _on_toggle_select_all_clicked(self) -> None:
        """切换全选/取消全选"""
        all_checked = self._are_all_checked()
        new_state = Qt.Unchecked if all_checked else Qt.Checked

        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            item.setCheckState(new_state)

        logger.debug(f"Toggle select all: {new_state == Qt.Checked}")

        # 更新按钮状态
        self._update_button_states()

    @Slot(object)
    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """处理列表项变化（复选框状态变化）

        Args:
            item: 变化的列表项
        """
        # 更新按钮状态
        self._update_button_states()

    def _are_all_checked(self) -> bool:
        """检查是否所有文件都被勾选

        Returns:
            bool: 所有文件都勾选返回True，否则返回False
        """
        if self.file_list_widget.count() == 0:
            return False

        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            if item.checkState() == Qt.Unchecked:
                return False
        return True

    def _get_checked_items(self) -> List[QListWidgetItem]:
        """获取所有勾选的文件项

        Returns:
            List[QListWidgetItem]: 勾选的文件项列表
        """
        checked_items = []
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                checked_items.append(item)
        return checked_items

    def _update_button_states(self) -> None:
        """更新所有按钮的启用/禁用状态"""
        has_files = len(self.file_paths) > 0
        has_checked = len(self._get_checked_items()) > 0

        # 全选按钮：有文件时启用
        self.select_all_button.setEnabled(has_files)

        # 移除选中按钮：有勾选项时启用
        self.remove_button.setEnabled(has_checked)

        # 清空列表按钮：有文件时启用
        self.clear_button.setEnabled(has_files)

        # 更新全选按钮文本
        self._update_select_all_button_text()

    def _update_select_all_button_text(self) -> None:
        """更新全选按钮文本"""
        if self._are_all_checked() and self.file_list_widget.count() > 0:
            self.select_all_button.setText("取消全选")
        else:
            self.select_all_button.setText("全选")

    @Slot()
    def _on_animation_finished(self) -> None:
        """动画完成回调

        收起动画完成后隐藏组件，展开动画完成后不做处理
        """
        # 只有在收起状态时才隐藏组件
        if not self._is_visible:
            self.hide()
            logger.debug("FileSelectionPanel hidden after collapse animation")


    # ========== 公共接口 ==========

    def set_visible(self, visible: bool, animated: bool = True) -> None:
        """设置面板可见性，支持动画

        Args:
            visible: 是否可见
            animated: 是否使用动画（默认True）
        """
        if visible == self._is_visible:
            return

        self._is_visible = visible

        if animated:
            # 使用动画展开/收起
            if self._animation is None:
                self._animation = QPropertyAnimation(self, b"maximumHeight")
                self._animation.setDuration(200)  # 200ms
                self._animation.setEasingCurve(QEasingCurve.InOutQuad)
                # 连接动画完成信号（只连接一次）
                self._animation.finished.connect(self._on_animation_finished)

            # 停止之前的动画
            if self._animation.state() == QPropertyAnimation.Running:
                self._animation.stop()

            if visible:
                self.show()  # 先显示
                self._animation.setStartValue(0)
                self._animation.setEndValue(self._target_height)
            else:
                self._animation.setStartValue(self.height())
                self._animation.setEndValue(0)

            self._animation.start()
            logger.debug(f"FileSelectionPanel animated {'expand' if visible else 'collapse'}")
        else:
            # 直接设置可见性
            if visible:
                self.setMaximumHeight(self._target_height)
                self.show()
            else:
                self.setMaximumHeight(0)
                self.hide()
            logger.debug(f"FileSelectionPanel {'shown' if visible else 'hidden'}")

    def get_file_paths(self) -> List[str]:
        """获取所有选择的文件路径

        Returns:
            List[str]: 文件路径列表
        """
        return self.file_paths.copy()

    def get_file_count(self) -> int:
        """获取文件数量

        Returns:
            int: 文件数量
        """
        return len(self.file_paths)

    def clear_files(self) -> None:
        """清空文件列表（程序调用）"""
        self._on_clear_clicked()

    def is_visible_panel(self) -> bool:
        """检查面板是否可见

        Returns:
            bool: 面板是否可见
        """
        return self._is_visible
