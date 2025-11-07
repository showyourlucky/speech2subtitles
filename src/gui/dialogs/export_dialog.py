"""
导出对话框

提供转录记录的导出功能，支持多种格式和选项
"""

import logging
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QCheckBox, QLineEdit, QPushButton,
    QGroupBox, QMessageBox, QFileDialog, QWidget,
    QLabel, QProgressBar, QSpinBox
)
from PySide6.QtCore import Slot, Qt, QThread, Signal
from PySide6.QtGui import QFont

from src.gui.models.history_models import TranscriptionRecord
from src.gui.storage.exporters import ExporterFactory, BatchExporter

logger = logging.getLogger(__name__)


class ExportWorker(QThread):
    """导出工作线程"""

    progress_updated = Signal(int)  # 进度更新 (0-100)
    export_completed = Signal(int, list)  # 导出完成 (成功数量, 错误列表)
    export_failed = Signal(str)  # 导出失败

    def __init__(self, records: List[TranscriptionRecord], output_dir: str,
                 format_type: str, options: Dict[str, Any]):
        """初始化导出工作线程

        Args:
            records: 要导出的记录列表
            output_dir: 输出目录
            format_type: 导出格式
            options: 导出选项
        """
        super().__init__()
        self.records = records
        self.output_dir = output_dir
        self.format_type = format_type
        self.options = options

    def run(self) -> None:
        """执行导出任务"""
        try:
            batch_exporter = BatchExporter()
            total_records = len(self.records)

            # 模拟进度更新
            for i in range(total_records):
                progress = int((i + 1) / total_records * 100)
                self.progress_updated.emit(progress)

            # 执行批量导出
            success_count, errors = batch_exporter.export_multiple(
                self.records, self.output_dir, self.format_type, self.options
            )

            self.export_completed.emit(success_count, errors)

        except Exception as e:
            self.export_failed.emit(str(e))


class ExportDialog(QDialog):
    """导出对话框

    功能:
        - 选择导出格式
        - 配置导出选项
        - 选择保存位置
        - 执行导出
        - 批量导出支持
    """

    def __init__(self, records: List[TranscriptionRecord], parent: Optional[QWidget] = None):
        """初始化导出对话框

        Args:
            records: 要导出的转录记录列表
            parent: 父组件
        """
        super().__init__(parent)

        self.records = records
        self.export_worker: Optional[ExportWorker] = None

        # UI组件
        self.format_combo: Optional[QComboBox] = None
        self.include_timestamp_check: Optional[QCheckBox] = None
        self.include_metadata_check: Optional[QCheckBox] = None
        self.output_path_edit: Optional[QLineEdit] = None
        self.browse_button: Optional[QPushButton] = None
        self.export_button: Optional[QPushButton] = None
        self.cancel_button: Optional[QPushButton] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.status_label: Optional[QLabel] = None

        # 初始化UI
        self._setup_ui()
        self._load_settings()

        logger.debug("ExportDialog initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        self.setWindowTitle("导出转录结果")
        self.setMinimumWidth(600)
        self.setModal(True)

        # 主布局
        main_layout = QVBoxLayout(self)

        # 记录数量信息
        info_label = QLabel(f"将导出 {len(self.records)} 条转录记录")
        info_font = QFont()
        info_font.setBold(True)
        info_label.setFont(info_font)
        main_layout.addWidget(info_label)

        # 格式选择
        format_group = QGroupBox("导出格式")
        format_layout = QFormLayout(format_group)

        self.format_combo = QComboBox()
        formats = ExporterFactory.get_supported_formats()
        for fmt in formats:
            description = ExporterFactory.get_format_description(fmt)
            self.format_combo.addItem(f"{description} (*.{fmt})", fmt)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addRow("格式:", self.format_combo)

        main_layout.addWidget(format_group)

        # 导出选项
        options_group = QGroupBox("导出选项")
        options_layout = QVBoxLayout(options_group)

        self.include_timestamp_check = QCheckBox("包含时间戳")
        self.include_timestamp_check.setChecked(True)
        options_layout.addWidget(self.include_timestamp_check)

        self.include_metadata_check = QCheckBox("包含元数据（音频源、模型等）")
        self.include_metadata_check.setChecked(True)
        options_layout.addWidget(self.include_metadata_check)

        main_layout.addWidget(options_group)

        # 保存位置
        save_group = QGroupBox("保存位置")
        save_layout = QVBoxLayout(save_group)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("选择保存位置...")
        save_layout.addWidget(self.output_path_edit)

        save_button_layout = QHBoxLayout()
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        save_button_layout.addWidget(self.browse_button)
        save_button_layout.addStretch()

        save_layout.addLayout(save_button_layout)

        main_layout.addWidget(save_group)

        # 进度显示
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel()
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)

        # 按钮栏
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.export_button = QPushButton("导出")
        self.export_button.clicked.connect(self._on_export_clicked)
        self.export_button.setDefault(True)
        button_layout.addWidget(self.export_button)

        main_layout.addLayout(button_layout)

    @Slot(int)
    def _on_format_changed(self, index: int) -> None:
        """处理格式变化

        Args:
            index: 格式索引
        """
        # 获取当前格式
        format_type = self.format_combo.itemData(index)

        # SRT和VTT固定包含时间戳
        if format_type in ['srt', 'vtt']:
            self.include_timestamp_check.setEnabled(False)
            self.include_timestamp_check.setChecked(True)
        else:
            self.include_timestamp_check.setEnabled(True)

    @Slot()
    def _on_browse_clicked(self) -> None:
        """打开文件夹选择对话框"""
        # 获取当前格式
        current_index = self.format_combo.currentIndex()
        format_type = self.format_combo.itemData(current_index)

        # 选择文件夹
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择导出文件夹",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder_path:
            self.output_path_edit.setText(folder_path)

    @Slot()
    def _on_export_clicked(self) -> None:
        """执行导出"""
        output_path = self.output_path_edit.text().strip()

        if not output_path:
            QMessageBox.warning(self, "输入错误", "请选择保存位置")
            return

        # 获取当前格式
        current_index = self.format_combo.currentIndex()
        format_type = self.format_combo.itemData(current_index)

        # 收集选项
        options = {
            'include_timestamp': self.include_timestamp_check.isChecked(),
            'include_metadata': self.include_metadata_check.isChecked(),
            'include_display_info': True  # JSON格式额外选项
        }

        # 禁用控件，显示进度
        self._set_exporting_state(True)

        # 创建导出工作线程
        self.export_worker = ExportWorker(self.records, output_path, format_type, options)
        self.export_worker.progress_updated.connect(self._on_progress_updated)
        self.export_worker.export_completed.connect(self._on_export_completed)
        self.export_worker.export_failed.connect(self._on_export_failed)
        self.export_worker.start()

    @Slot(int)
    def _on_progress_updated(self, progress: int) -> None:
        """处理进度更新

        Args:
            progress: 进度百分比 (0-100)
        """
        self.progress_bar.setValue(progress)

    @Slot(int, list)
    def _on_export_completed(self, success_count: int, errors: List[str]) -> None:
        """处理导出完成

        Args:
            success_count: 成功导出的记录数量
            errors: 错误消息列表
        """
        self._set_exporting_state(False)

        total_count = len(self.records)
        if success_count == total_count:
            QMessageBox.information(
                self,
                "导出完成",
                f"成功导出 {success_count} 条记录"
            )
            self.accept()
        else:
            error_details = "\n".join(errors[:5])  # 只显示前5个错误
            if len(errors) > 5:
                error_details += f"\n... 还有 {len(errors) - 5} 个错误"

            QMessageBox.warning(
                self,
                "导出部分完成",
                f"成功导出 {success_count}/{total_count} 条记录\n\n错误详情:\n{error_details}"
            )

    @Slot(str)
    def _on_export_failed(self, error_message: str) -> None:
        """处理导出失败

        Args:
            error_message: 错误消息
        """
        self._set_exporting_state(False)
        QMessageBox.critical(self, "导出失败", f"导出过程中发生错误:\n{error_message}")

    def _set_exporting_state(self, is_exporting: bool) -> None:
        """设置导出状态

        Args:
            is_exporting: 是否正在导出
        """
        if is_exporting:
            self.export_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("正在导出...")
            self.status_label.setVisible(True)
        else:
            self.export_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setVisible(False)

    def _load_settings(self) -> None:
        """加载默认设置"""
        # 默认选择TXT格式
        self.format_combo.setCurrentIndex(0)

        # 如果只有一条记录，设置默认文件名
        if len(self.records) == 1:
            record = self.records[0]
            timestamp_str = record.timestamp.strftime('%Y%m%d_%H%M%S')
            default_name = f"transcription_{timestamp_str}"
            self.output_path_edit.setPlaceholderText(f"选择保存位置（默认文件夹名: {default_name}）")

    def closeEvent(self, event) -> None:
        """处理关闭事件

        Args:
            event: 关闭事件
        """
        # 如果正在导出，确认是否取消
        if self.export_worker and self.export_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认取消",
                "导出正在进行中，确定要取消吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.export_worker.terminate()
                self.export_worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()