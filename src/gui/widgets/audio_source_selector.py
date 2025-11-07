"""音频源选择组件
提供麦克风、系统音频、文件的选择功能
支持多文件选择和批量处理
"""

import logging
from typing import Optional, List
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QRadioButton,
    QPushButton,
    QGroupBox,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Signal, Slot, Qt

from src.audio.models import AudioSourceType
from src.gui.models.gui_models import AudioSourceInfo

logger = logging.getLogger(__name__)


class AudioSourceSelector(QWidget):
    """音频源选择器

    核心功能:
        - 音频源类型选择（单选按钮）
        - 多文件选择（文件对话框）
        - 文件列表管理（添加/清空）

    信号:
        source_changed: 音频源发生变化 (AudioSourceInfo)
    """

    # 信号定义
    source_changed = Signal(object)  # AudioSourceInfo

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化音频源选择器

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # UI组件
        self.microphone_radio: Optional[QRadioButton] = None
        self.system_audio_radio: Optional[QRadioButton] = None
        self.file_radio: Optional[QRadioButton] = None
        self.browse_button: Optional[QPushButton] = None
        self.select_all_button: Optional[QPushButton] = None  # 新增：全选按钮
        self.remove_file_button: Optional[QPushButton] = None  # 新增：移除选中文件按钮
        self.clear_files_button: Optional[QPushButton] = None
        self.file_list_widget: Optional[QListWidget] = None

        # 文件路径列表
        self.file_paths: List[str] = []

        # 当前选择
        self._current_source: Optional[AudioSourceInfo] = None

        # 初始化UI
        self._setup_ui()

        # 默认选择麦克风
        self.microphone_radio.setChecked(True)
        self._on_source_changed()

        logger.debug("AudioSourceSelector initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建分组框
        group_box = QGroupBox("音频源选择")
        group_box_layout = QVBoxLayout(group_box)

        # 麦克风选项
        self.microphone_radio = QRadioButton("麦克风")
        self.microphone_radio.toggled.connect(self._on_source_changed)
        group_box_layout.addWidget(self.microphone_radio)

        # 系统音频选项
        self.system_audio_radio = QRadioButton("系统音频")
        self.system_audio_radio.toggled.connect(self._on_source_changed)
        group_box_layout.addWidget(self.system_audio_radio)

        # 文件选项
        self.file_radio = QRadioButton("音频/视频文件")
        self.file_radio.toggled.connect(self._on_source_changed)
        group_box_layout.addWidget(self.file_radio)

        # 文件选择按钮布局
        file_button_layout = QHBoxLayout()

        self.browse_button = QPushButton("选择文件...")
        self.browse_button.setEnabled(False)
        self.browse_button.setFixedWidth(100)
        self.browse_button.clicked.connect(self._on_browse_clicked)
        file_button_layout.addWidget(self.browse_button)

        # 新增：全选按钮
        self.select_all_button = QPushButton("全选")
        self.select_all_button.setEnabled(False)
        self.select_all_button.setFixedWidth(60)
        self.select_all_button.clicked.connect(self._on_toggle_select_all_clicked)
        file_button_layout.addWidget(self.select_all_button)

        self.remove_file_button = QPushButton("移除选中")
        self.remove_file_button.setEnabled(False)
        self.remove_file_button.setFixedWidth(80)
        self.remove_file_button.clicked.connect(self._on_remove_file_clicked)
        file_button_layout.addWidget(self.remove_file_button)

        self.clear_files_button = QPushButton("清空全部")
        self.clear_files_button.setEnabled(False)
        self.clear_files_button.setFixedWidth(80)
        self.clear_files_button.clicked.connect(self._on_clear_files_clicked)
        file_button_layout.addWidget(self.clear_files_button)

        file_button_layout.addStretch()
        group_box_layout.addLayout(file_button_layout)

        # 文件列表显示
        self.file_list_widget = QListWidget()
        self.file_list_widget.setMaximumHeight(100)
        self.file_list_widget.setEnabled(False)
        # 启用水平滚动条（当文件名太长时）
        self.file_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # 设置文本省略模式（如果需要）
        self.file_list_widget.setWordWrap(False)
        # 连接选择变化信号
        self.file_list_widget.itemSelectionChanged.connect(
            self._on_file_selection_changed
        )
        # 连接复选框状态变化信号
        self.file_list_widget.itemChanged.connect(self._on_item_changed)
        group_box_layout.addWidget(self.file_list_widget)

        # 添加到主布局
        main_layout.addWidget(group_box)

    @Slot()
    def _on_source_changed(self) -> None:
        """处理音频源变化"""
        # 更新文件输入组件状态
        file_selected = self.file_radio.isChecked()
        self.browse_button.setEnabled(file_selected)
        self.file_list_widget.setEnabled(file_selected)

        # 更新按钮状态（统一管理）
        self._update_button_states()

        # 确定当前选择的音频源
        if self.microphone_radio.isChecked():
            source_info = AudioSourceInfo(
                source_type=AudioSourceType.MICROPHONE,
                display_name="麦克风",
                device_id=None,  # 使用默认设备
            )
        elif self.system_audio_radio.isChecked():
            source_info = AudioSourceInfo(
                source_type=AudioSourceType.SYSTEM_AUDIO, display_name="系统音频"
            )
        elif self.file_radio.isChecked():
            # 使用文件列表
            source_info = AudioSourceInfo(
                source_type=AudioSourceType.FILE,
                display_name=f"文件 ({len(self.file_paths)}个)"
                if self.file_paths
                else "文件",
                file_path=self.file_paths[0] if self.file_paths else None,
            )
        else:
            return

        # 保存并发射信号
        self._current_source = source_info
        self.source_changed.emit(source_info)

        logger.debug(f"Audio source changed to: {source_info}")

    @Slot()
    def _on_browse_clicked(self) -> None:
        """处理浏览按钮点击 - 支持多文件选择"""
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
                f"{len(file_paths)} file(s) selected, total: {len(self.file_paths)}"
            )

            # 更新按钮状态
            self._update_button_states()

            # 触发源变化
            if self.file_radio.isChecked():
                self._on_source_changed()

    @Slot()
    def _on_remove_file_clicked(self) -> None:
        """移除所有勾选的文件"""
        checked_items = self.get_checked_items()

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

        # 触发源变化
        if self.file_radio.isChecked():
            self._on_source_changed()

    @Slot()
    def _on_clear_files_clicked(self) -> None:
        """清空文件列表"""
        self.file_paths.clear()
        self.file_list_widget.clear()
        logger.info("File list cleared")

        # 更新按钮状态
        self._update_button_states()

        # 触发源变化
        if self.file_radio.isChecked():
            self._on_source_changed()

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

    def _update_select_all_button_text(self) -> None:
        """更新全选按钮文本"""
        if self._are_all_checked() and self.file_list_widget.count() > 0:
            self.select_all_button.setText("取消全选")
        else:
            self.select_all_button.setText("全选")

    def _update_button_states(self) -> None:
        """更新所有按钮的启用/禁用状态"""
        file_mode = self.file_radio.isChecked()
        has_files = len(self.file_paths) > 0
        has_checked = len(self.get_checked_items()) > 0

        # 全选按钮：文件模式且有文件时启用
        self.select_all_button.setEnabled(file_mode and has_files)

        # 移除选中按钮：文件模式且有勾选项时启用
        self.remove_file_button.setEnabled(file_mode and has_checked)

        # 清空全部按钮：文件模式且有文件时启用（保持现有逻辑）
        self.clear_files_button.setEnabled(file_mode and has_files)

        # 更新全选按钮文本
        self._update_select_all_button_text()

    @Slot(object)
    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """处理列表项变化（复选框状态变化）

        Args:
            item: 变化的列表项
        """
        # 更新按钮状态
        self._update_button_states()
        logger.debug(f"Item checkbox changed: {item.text()}")

    @Slot()
    def _on_file_selection_changed(self) -> None:
        """处理文件列表选择变化"""
        # 旧的单选逻辑已被批量删除取代，此方法保留以兼容
        pass

    def get_selected_source(self) -> Optional[AudioSourceInfo]:
        """获取当前选择的音频源

        Returns:
            Optional[AudioSourceInfo]: 当前选择的音频源信息
        """
        return self._current_source

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

    def get_checked_items(self) -> List[QListWidgetItem]:
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

    def set_enabled(self, enabled: bool) -> None:
        """设置是否可选择（转录中禁用）

        Args:
            enabled: 是否启用
        """
        self.microphone_radio.setEnabled(enabled)
        self.system_audio_radio.setEnabled(enabled)
        self.file_radio.setEnabled(enabled)

        file_mode = self.file_radio.isChecked()
        has_files = len(self.file_paths) > 0
        has_checked = len(self.get_checked_items()) > 0

        self.browse_button.setEnabled(enabled and file_mode)
        self.select_all_button.setEnabled(enabled and file_mode and has_files)
        self.remove_file_button.setEnabled(enabled and file_mode and has_checked)
        self.clear_files_button.setEnabled(enabled and file_mode and has_files)
        self.file_list_widget.setEnabled(enabled and file_mode)
