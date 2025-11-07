"""
历史记录查看对话框

提供转录历史记录的查看、搜索、删除和导出功能
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox, QLabel,
    QComboBox, QSpinBox, QProgressBar, QSplitter,
    QTextBrowser, QCheckBox, QMenu, QWidget
)
from PySide6.QtCore import Slot, Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QAction

from src.gui.models.history_models import TranscriptionRecord
from src.gui.storage.history_manager import HistoryManager
from src.gui.dialogs.export_dialog import ExportDialog

logger = logging.getLogger(__name__)


class HistoryDialog(QDialog):
    """历史记录查看对话框

    提供历史记录的查看、搜索、过滤、删除和导出功能
    """

    def __init__(self, history_manager: HistoryManager, parent=None):
        """初始化历史记录对话框

        Args:
            history_manager: 历史记录管理器
            parent: 父窗口
        """
        super().__init__(parent)
        self.history_manager = history_manager
        self.current_records: List[TranscriptionRecord] = []
        self.selected_record: Optional[TranscriptionRecord] = None

        self.setWindowTitle("转录历史记录")
        self.setGeometry(200, 200, 1000, 700)
        self.setModal(False)  # 非模态对话框，允许同时使用主窗口

        self._setup_ui()
        self._load_records()

        logger.info("History dialog initialized")

    def _setup_ui(self) -> None:
        """设置用户界面"""
        layout = QVBoxLayout(self)

        # 搜索和过滤区域
        search_group = self._create_search_group()
        layout.addWidget(search_group)

        # 主分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧：记录列表
        self.record_table = self._create_record_table()
        splitter.addWidget(self.record_table)

        # 右侧：记录详情
        self.detail_panel = self._create_detail_panel()
        splitter.addWidget(self.detail_panel)

        # 设置分割器比例
        splitter.setStretchFactor(0, 2)  # 记录列表占2份
        splitter.setStretchFactor(1, 1)  # 详情面板占1份

        # 按钮区域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)

    def _create_search_group(self) -> QGroupBox:
        """创建搜索和过滤组"""
        group = QGroupBox("搜索和过滤")
        layout = QHBoxLayout(group)

        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索转录文本、模型名或文件路径...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(QLabel("搜索:"))
        layout.addWidget(self.search_edit)

        # 音频源过滤
        layout.addWidget(QLabel("音频源:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(["全部", "麦克风", "系统音频", "文件"])
        self.source_combo.currentTextChanged.connect(self._on_filter_changed)
        layout.addWidget(self.source_combo)

        # 时间范围过滤
        layout.addWidget(QLabel("最近:"))
        self.date_combo = QComboBox()
        self.date_combo.addItems(["全部", "今天", "本周", "本月", "最近3个月"])
        self.date_combo.currentTextChanged.connect(self._on_filter_changed)
        layout.addWidget(self.date_combo)

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._load_records)
        layout.addWidget(refresh_btn)

        return group

    def _create_record_table(self) -> QTableWidget:
        """创建记录表格"""
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "时间", "音频源", "文件/路径", "时长", "模型", "文本预览"
        ])

        # 设置列宽
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 音频源
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # 文件路径
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 时长
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 模型
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # 文本预览

        # 设置选择行为
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.itemSelectionChanged.connect(self._on_selection_changed)

        # 设置右键菜单
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_context_menu)

        return table

    def _create_detail_panel(self) -> QWidget:
        """创建详情面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 详情标题
        title_label = QLabel("记录详情")
        title_label.setFont(QFont("", 12, QFont.Bold))
        layout.addWidget(title_label)

        # 详情字段
        form_layout = QFormLayout()

        self.detail_time = QLabel("-")
        self.detail_source = QLabel("-")
        self.detail_file = QLabel("-")
        self.detail_duration = QLabel("-")
        self.detail_model = QLabel("-")

        form_layout.addRow("记录时间:", self.detail_time)
        form_layout.addRow("音频源:", self.detail_source)
        form_layout.addRow("文件路径:", self.detail_file)
        form_layout.addRow("转录时长:", self.detail_duration)
        form_layout.addRow("使用模型:", self.detail_model)

        layout.addLayout(form_layout)

        # 转录文本
        text_label = QLabel("转录文本:")
        text_label.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(text_label)

        self.detail_text = QTextBrowser()
        self.detail_text.setMaximumHeight(200)
        layout.addWidget(self.detail_text)

        return panel

    def _create_button_layout(self) -> QHBoxLayout:
        """创建按钮布局"""
        layout = QHBoxLayout()

        # 左侧按钮
        delete_btn = QPushButton("删除选中")
        delete_btn.clicked.connect(self._delete_selected)
        layout.addWidget(delete_btn)

        export_selected_btn = QPushButton("导出选中")
        export_selected_btn.clicked.connect(self._export_selected)
        layout.addWidget(export_selected_btn)

        export_all_btn = QPushButton("导出全部")
        export_all_btn.clicked.connect(self._export_all)
        layout.addWidget(export_all_btn)

        layout.addStretch()

        # 右侧按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return layout

    @Slot()
    def _load_records(self) -> None:
        """加载历史记录"""
        try:
            # 获取基础记录列表
            self.current_records = self.history_manager.get_all_records(limit=1000)

            # 应用过滤
            self._apply_filters()

            logger.info(f"Loaded {len(self.current_records)} records")

        except Exception as e:
            logger.error(f"Failed to load records: {e}")
            QMessageBox.critical(self, "错误", f"加载历史记录失败: {e}")

    @Slot()
    def _on_search_changed(self) -> None:
        """搜索文本变化处理"""
        self._apply_filters()

    @Slot()
    def _on_filter_changed(self) -> None:
        """过滤条件变化处理"""
        self._apply_filters()

    def _apply_filters(self) -> None:
        """应用搜索和过滤条件"""
        try:
            # 获取基础记录
            all_records = self.history_manager.get_all_records(limit=1000)
            filtered_records = []

            # 搜索文本过滤
            search_text = self.search_edit.text().strip().lower()
            if search_text:
                filtered_records = [
                    record for record in all_records
                    if (search_text in (record.text or "").lower() or
                        search_text in (record.model_name or "").lower() or
                        search_text in (record.audio_path or "").lower())
                ]
            else:
                filtered_records = all_records

            # 音频源过滤
            source_filter = self.source_combo.currentText()
            if source_filter != "全部":
                source_map = {
                    "麦克风": "MICROPHONE",
                    "系统音频": "SYSTEM_AUDIO",
                    "文件": "FILE"
                }
                if source_filter in source_map:
                    source_type = source_map[source_filter]
                    filtered_records = [
                        record for record in filtered_records
                        if record.audio_source and record.audio_source.value == source_type
                    ]

            # 时间范围过滤
            date_filter = self.date_combo.currentText()
            if date_filter != "全部":
                now = datetime.now()
                if date_filter == "今天":
                    start_date = now.replace(hour=0, minute=0, second=0)
                elif date_filter == "本周":
                    start_date = now - timedelta(days=now.weekday())
                elif date_filter == "本月":
                    start_date = now.replace(day=1)
                elif date_filter == "最近3个月":
                    start_date = now - timedelta(days=90)
                else:
                    start_date = None

                if start_date:
                    filtered_records = [
                        record for record in filtered_records
                        if record.timestamp >= start_date
                    ]

            # 更新显示
            self.current_records = filtered_records
            self._update_table()

        except Exception as e:
            logger.error(f"Failed to apply filters: {e}")

    def _update_table(self) -> None:
        """更新表格显示"""
        self.record_table.setRowCount(len(self.current_records))

        for row, record in enumerate(self.current_records):
            # 时间
            time_str = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            self.record_table.setItem(row, 0, QTableWidgetItem(time_str))

            # 音频源
            source_str = record.audio_source.value if record.audio_source else "-"
            self.record_table.setItem(row, 1, QTableWidgetItem(source_str))

            # 文件路径
            file_path = record.audio_path or "-"
            if len(file_path) > 50:
                file_path = "..." + file_path[-47:]
            self.record_table.setItem(row, 2, QTableWidgetItem(file_path))

            # 时长
            duration_str = f"{record.duration:.1f}s" if record.duration > 0 else "-"
            self.record_table.setItem(row, 3, QTableWidgetItem(duration_str))

            # 模型
            model_name = record.model_name or "-"
            self.record_table.setItem(row, 4, QTableWidgetItem(model_name))

            # 文本预览
            text_preview = (record.text or "")[:100]
            if len(record.text or "") > 100:
                text_preview += "..."
            self.record_table.setItem(row, 5, QTableWidgetItem(text_preview))

    @Slot()
    def _on_selection_changed(self) -> None:
        """表格选择变化处理"""
        current_row = self.record_table.currentRow()
        if 0 <= current_row < len(self.current_records):
            self.selected_record = self.current_records[current_row]
            self._update_detail_panel()
        else:
            self.selected_record = None
            self._clear_detail_panel()

    def _update_detail_panel(self) -> None:
        """更新详情面板"""
        if not self.selected_record:
            self._clear_detail_panel()
            return

        record = self.selected_record

        # 更新字段
        self.detail_time.setText(record.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        self.detail_source.setText(record.audio_source.value if record.audio_source else "-")
        self.detail_file.setText(record.audio_path or "-")
        self.detail_duration.setText(f"{record.duration:.1f}秒" if record.duration > 0 else "-")
        self.detail_model.setText(record.model_name or "-")
        self.detail_text.setText(record.text or "")

    def _clear_detail_panel(self) -> None:
        """清空详情面板"""
        self.detail_time.setText("-")
        self.detail_source.setText("-")
        self.detail_file.setText("-")
        self.detail_duration.setText("-")
        self.detail_model.setText("-")
        self.detail_text.setText("-")

    def _show_context_menu(self, position) -> None:
        """显示右键菜单"""
        if self.record_table.itemAt(position) is None:
            return

        menu = QMenu(self)

        # 导出当前记录
        export_action = QAction("导出此记录", self)
        export_action.triggered.connect(self._export_selected)
        menu.addAction(export_action)

        # 删除当前记录
        delete_action = QAction("删除此记录", self)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)

        menu.exec_(self.record_table.mapToGlobal(position))

    @Slot()
    def _delete_selected(self) -> None:
        """删除选中的记录"""
        if not self.selected_record:
            QMessageBox.warning(self, "警告", "请先选择要删除的记录")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除这条记录吗？\n\n时间: {self.selected_record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"文本: {(self.selected_record.text or '')[:50]}...",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.history_manager.delete_record(self.selected_record.id)
                if success:
                    QMessageBox.information(self, "成功", "记录已删除")
                    self._load_records()
                else:
                    QMessageBox.warning(self, "警告", "删除失败")
            except Exception as e:
                logger.error(f"Failed to delete record: {e}")
                QMessageBox.critical(self, "错误", f"删除记录失败: {e}")

    @Slot()
    def _export_selected(self) -> None:
        """导出选中的记录"""
        if not self.selected_record:
            QMessageBox.warning(self, "警告", "请先选择要导出的记录")
            return

        # 打开导出对话框
        dialog = ExportDialog([self.selected_record], self)
        dialog.exec()

    @Slot()
    def _export_all(self) -> None:
        """导出所有记录"""
        if not self.current_records:
            QMessageBox.information(self, "提示", "没有可导出的记录")
            return

        # 打开导出对话框
        dialog = ExportDialog(self.current_records, self)
        dialog.exec()

    def closeEvent(self, event) -> None:
        """关闭事件处理"""
        logger.info("History dialog closed")
        super().closeEvent(event)