"""
批量文件转录对话框

支持选择多个文件进行批量转录,实时显示进度和预览
"""

import logging
import threading
from pathlib import Path
from typing import Optional, List
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QLabel,
    QProgressBar,
    QTextEdit,
    QFileDialog,
    QLineEdit,
    QComboBox,
    QListWidget,
    QMessageBox,
    QWidget,
    QCheckBox,
)
from PySide6.QtCore import Slot, Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor

from src.config.manager import Config
from src.media.batch_processor import BatchProcessor, BatchProcessorCancelled
from src.media.converter import MediaConverter
from src.media.subtitle_generator import SubtitleGenerator, Segment
from src.transcription.engine_manager import TranscriptionEngineManager
from src.transcription.config_factory import build_transcription_config
from src.vad import VadManager
from src.vad.models import VadConfig, VadModel

logger = logging.getLogger(__name__)


class TranscriptionWorker(QThread):
    """转录工作线程"""

    # 信号定义
    file_started = Signal(int, int, str)  # (file_index, total_files, filename)
    file_progress = Signal(int, float)  # (file_index, progress_percent)
    segment_received = Signal(object)  # (Segment)
    file_completed = Signal(
        str, str, float, float
    )  # (file_path, subtitle_file, duration, rtf)
    all_completed = Signal(dict)  # 所有文件完成
    error_occurred = Signal(str)  # 错误发生

    def __init__(
        self,
        file_paths: List[Path],
        config: Config,
        output_dir: Path,
        subtitle_format: str,
        show_preview: bool = True,
    ):
        """初始化转录工作线程

        Args:
            file_paths: 待转录文件列表
            config: 配置对象
            output_dir: 输出目录
            subtitle_format: 字幕格式 (srt/vtt)
            show_preview: 是否显示实时预览
        """
        super().__init__()
        self.file_paths = file_paths
        self.config = config
        self.output_dir = output_dir
        self.subtitle_format = subtitle_format
        self.show_preview = show_preview
        self.cancel_event = threading.Event()

    def run(self) -> None:
        """执行批量转录任务"""
        try:
            # 初始化组件
            converter = MediaConverter()
            subtitle_gen = SubtitleGenerator()
            processor = BatchProcessor(
                converter,
                subtitle_gen,
                transcribe_per_vad_segment=self.config.transcribe_per_vad_segment,
                stream_merge_target_duration=self.config.stream_merge_target_duration,
                stream_long_segment_threshold=self.config.stream_long_segment_threshold,
                stream_merge_max_gap=self.config.stream_merge_max_gap,
                max_subtitle_duration=self.config.max_subtitle_duration,
            )

            # 1. 创建VAD配置并通过VadManager获取检测器实例(智能复用)
            vad_config = VadConfig(
                model=VadModel.SILERO,  # 使用Silero VAD模型
                threshold=self.config.vad_threshold,  # VAD检测阈值
                sample_rate=self.config.sample_rate,  # 采样率
                return_confidence=True,  # 返回置信度
            )
            # 使用VadManager实现智能复用,避免重复加载模型
            vad_detector = VadManager.get_detector(vad_config)

            # 2. 创建转录引擎配置对象
            transcription_config = build_transcription_config(
                self.config,
                on_warning=logger.warning,
            )
            transcription_engine = TranscriptionEngineManager.get_engine(
                transcription_config
            )
            # 执行批量处理
            stats = processor.process_files(
                self.file_paths,
                transcription_engine,
                vad_detector,
                output_dir=self.output_dir,
                subtitle_format=self.subtitle_format,
                on_file_start=self._on_file_start,
                on_file_progress=self._on_file_progress,
                on_segment=self._on_segment if self.show_preview else None,
                on_file_complete=self._on_file_complete,
                cancel_event=self.cancel_event,
                continue_on_error=True,  # 遇到错误继续处理
            )

            # 发送完成信号
            self.all_completed.emit(stats)

        except BatchProcessorCancelled:
            logger.info("批量转录被用户取消")

        except Exception as e:
            logger.error(f"批量转录失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def _on_file_start(self, file_index: int, total_files: int, filename: str):
        """文件开始回调"""
        self.file_started.emit(file_index, total_files, filename)

    def _on_file_progress(self, file_index: int, progress: float):
        """文件进度回调"""
        self.file_progress.emit(file_index, progress)

    def _on_segment(self, segment: Segment):
        """Segment回调 (实时预览)"""
        self.segment_received.emit(segment)

    def _on_file_complete(
        self, file_path: str, subtitle_file: str, duration: float, rtf: float
    ):
        """文件完成回调"""
        self.file_completed.emit(file_path, subtitle_file, duration, rtf)

    def cancel(self):
        """取消转录"""
        self.cancel_event.set()


class FileTranscriptionDialog(QDialog):
    """批量文件转录对话框

    功能:
        - 选择多个媒体文件
        - 配置输出目录和格式
        - 批量转录并生成字幕
        - 实时显示进度和转录预览
        - 支持取消操作
    """

    def __init__(self, config: Config, parent: Optional[QWidget] = None):
        """初始化对话框

        Args:
            config: 配置对象
            parent: 父组件
        """
        super().__init__(parent)
        self.config = config
        self.worker: Optional[TranscriptionWorker] = None

        # UI组件
        self.file_list: Optional[QListWidget] = None
        self.output_dir_edit: Optional[QLineEdit] = None
        self.format_combo: Optional[QComboBox] = None
        self.preview_check: Optional[QCheckBox] = None
        self.total_progress_bar: Optional[QProgressBar] = None
        self.current_progress_bar: Optional[QProgressBar] = None
        self.current_file_label: Optional[QLabel] = None
        self.preview_text: Optional[QTextEdit] = None
        self.stats_label: Optional[QLabel] = None
        self.start_button: Optional[QPushButton] = None
        self.cancel_button: Optional[QPushButton] = None
        self.close_button: Optional[QPushButton] = None

        # 状态变量
        self.current_file_index = 0
        self.total_files = 0
        self.success_count = 0
        self.error_count = 0
        self.preview_segments = []  # 存储预览的segment

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("批量文件转录")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)

        main_layout = QVBoxLayout(self)

        # 文件选择区域
        file_group_layout = QVBoxLayout()

        file_label = QLabel("选择文件:")
        file_label.setFont(QFont("", 10, QFont.Weight.Bold))
        file_group_layout.addWidget(file_label)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        file_group_layout.addWidget(self.file_list)

        # 文件操作按钮
        file_btn_layout = QHBoxLayout()
        add_files_btn = QPushButton("添加文件")
        add_files_btn.clicked.connect(self._on_add_files)
        file_btn_layout.addWidget(add_files_btn)

        remove_files_btn = QPushButton("移除选中")
        remove_files_btn.clicked.connect(self._on_remove_files)
        file_btn_layout.addWidget(remove_files_btn)

        clear_files_btn = QPushButton("清空列表")
        clear_files_btn.clicked.connect(self._on_clear_files)
        file_btn_layout.addWidget(clear_files_btn)

        file_btn_layout.addStretch()
        file_group_layout.addLayout(file_btn_layout)

        main_layout.addLayout(file_group_layout)

        # 配置区域
        config_layout = QFormLayout()

        # 输出目录
        output_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("选择输出目录 (留空则与源文件同目录)")
        output_layout.addWidget(self.output_dir_edit)

        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._on_browse_output)
        output_layout.addWidget(browse_btn)

        config_layout.addRow("输出目录:", output_layout)

        # 字幕格式
        self.format_combo = QComboBox()
        self.format_combo.addItems(["SRT", "VTT"])
        config_layout.addRow("字幕格式:", self.format_combo)

        # 实时预览选项
        self.preview_check = QCheckBox("显示实时预览 (可能略微降低性能)")
        self.preview_check.setChecked(True)
        config_layout.addRow("", self.preview_check)

        main_layout.addLayout(config_layout)

        # 进度区域
        progress_layout = QVBoxLayout()

        # 总进度
        total_progress_layout = QHBoxLayout()
        total_progress_layout.addWidget(QLabel("总进度:"))
        self.total_progress_bar = QProgressBar()
        self.total_progress_bar.setFormat("%v/%m (%p%)")
        total_progress_layout.addWidget(self.total_progress_bar)
        progress_layout.addLayout(total_progress_layout)

        # 当前文件进度
        current_progress_layout = QHBoxLayout()
        current_progress_layout.addWidget(QLabel("当前文件:"))
        self.current_progress_bar = QProgressBar()
        self.current_progress_bar.setFormat("%p%")
        current_progress_layout.addWidget(self.current_progress_bar)
        progress_layout.addLayout(current_progress_layout)

        # 当前文件信息
        self.current_file_label = QLabel("等待开始...")
        self.current_file_label.setWordWrap(True)
        progress_layout.addWidget(self.current_file_label)

        main_layout.addLayout(progress_layout)

        # 预览区域
        preview_label = QLabel("转录预览:")
        preview_label.setFont(QFont("", 10, QFont.Weight.Bold))
        main_layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        self.preview_text.setPlaceholderText("转录结果将在这里实时显示...")
        main_layout.addWidget(self.preview_text)

        # 统计信息
        self.stats_label = QLabel("统计: 等待开始")
        main_layout.addWidget(self.stats_label)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.start_button = QPushButton("开始转录")
        self.start_button.clicked.connect(self._on_start)
        button_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self._on_cancel)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        main_layout.addLayout(button_layout)

    @Slot()
    def _on_add_files(self):
        """添加文件"""
        file_filter = (
            "媒体文件 (*.mp4 *.avi *.mkv *.mov *.flv *.wmv "
            "*.mp3 *.wav *.m4a *.flac);;所有文件 (*.*)"
        )
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择媒体文件", "", file_filter
        )

        if files:
            for file in files:
                # 检查是否已存在
                existing_items = self.file_list.findItems(file, Qt.MatchExactly)
                if not existing_items:
                    self.file_list.addItem(file)

            logger.info(f"添加了 {len(files)} 个文件")

    @Slot()
    def _on_remove_files(self):
        """移除选中的文件"""
        selected_items = self.file_list.selectedItems()
        for item in selected_items:
            row = self.file_list.row(item)
            self.file_list.takeItem(row)

    @Slot()
    def _on_clear_files(self):
        """清空文件列表"""
        self.file_list.clear()

    @Slot()
    def _on_browse_output(self):
        """浏览输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self.output_dir_edit.text() or str(Path.home())
        )

        if dir_path:
            self.output_dir_edit.setText(dir_path)

    @Slot()
    def _on_start(self):
        """开始转录"""
        # 验证输入
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "提示", "请至少选择一个文件")
            return

        # 检查模型配置
        if not self.config.model_path or not Path(self.config.model_path).exists():
            QMessageBox.warning(self, "配置错误", "请先在设置中配置转录模型")
            return

        # 收集文件路径
        file_paths = []
        for i in range(self.file_list.count()):
            file_paths.append(Path(self.file_list.item(i).text()))

        # 确定输出目录
        output_dir = None
        if self.output_dir_edit.text().strip():
            output_dir = Path(self.output_dir_edit.text())
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"无法创建输出目录: {e}")
                    return

        # 获取字幕格式
        subtitle_format = self.format_combo.currentText().lower()

        # 重置状态
        self.current_file_index = 0
        self.total_files = len(file_paths)
        self.success_count = 0
        self.error_count = 0
        self.preview_segments = []
        self.preview_text.clear()
        self.total_progress_bar.setMaximum(self.total_files)
        self.total_progress_bar.setValue(0)
        self.current_progress_bar.setValue(0)

        # 更新UI状态
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.close_button.setEnabled(False)

        # 创建并启动工作线程
        self.worker = TranscriptionWorker(
            file_paths,
            self.config,
            output_dir,
            subtitle_format,
            show_preview=self.preview_check.isChecked(),
        )

        # 连接信号
        self.worker.file_started.connect(self._on_file_started)
        self.worker.file_progress.connect(self._on_file_progress)
        self.worker.segment_received.connect(self._on_segment_received)
        self.worker.file_completed.connect(self._on_file_completed)
        self.worker.all_completed.connect(self._on_all_completed)
        self.worker.error_occurred.connect(self._on_error)

        self.worker.start()
        logger.info(f"开始批量转录 {self.total_files} 个文件")

    @Slot()
    def _on_cancel(self):
        """取消转录"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认取消",
                "确定要取消转录吗?\n已完成的文件不会受影响。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.Yes:
                self.cancel_button.setEnabled(False)
                self.current_file_label.setText("正在取消...")
                self.worker.cancel()
                logger.info("用户请求取消转录")

    @Slot(int, int, str)
    def _on_file_started(self, file_index: int, total_files: int, filename: str):
        """文件开始处理"""
        self.current_file_index = file_index
        self.current_file_label.setText(
            f"正在处理 {file_index + 1}/{total_files}: {filename}"
        )
        self.current_progress_bar.setValue(0)
        logger.debug(f"开始处理文件 {file_index + 1}/{total_files}: {filename}")

    @Slot(int, float)
    def _on_file_progress(self, file_index: int, progress: float):
        """文件进度更新"""
        self.current_progress_bar.setValue(int(progress))

    @Slot(object)
    def _on_segment_received(self, segment: Segment):
        """接收到转录片段"""
        # 添加到预览区域 (限制最多显示100条)
        self.preview_segments.append(segment)
        if len(self.preview_segments) > 100:
            self.preview_segments.pop(0)

        # 格式化时间
        start_time = self._format_time(segment.start)
        text = f"[{start_time}] {segment.text}"

        # 追加到预览文本
        self.preview_text.append(text)

        # 自动滚动到底部
        cursor = self.preview_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.preview_text.setTextCursor(cursor)

    @Slot(str, str, float, float)
    def _on_file_completed(
        self, file_path: str, subtitle_file: str, duration: float, rtf: float
    ):
        """文件处理完成（成功或失败）

        Args:
            file_path: 源文件路径
            subtitle_file: 字幕文件路径（失败时为空字符串）
            duration: 音频时长（失败时为0.0）
            rtf: Real-Time Factor（失败时为0.0）
        """
        # 根据subtitle_file是否为空判断成功/失败
        if subtitle_file:
            # 成功
            self.success_count += 1
            logger.info(
                f"文件完成: {Path(file_path).name} -> {Path(subtitle_file).name}, RTF={rtf:.2f}"
            )
        else:
            # 失败
            self.error_count += 1
            logger.warning(f"文件处理失败: {Path(file_path).name}")

        # 更新总进度条
        self.total_progress_bar.setValue(self.success_count + self.error_count)

        # 更新统计
        self._update_stats()

    @Slot(dict)
    def _on_all_completed(self, stats: dict):
        """所有文件处理完成"""
        self.current_file_label.setText("转录完成!")
        self.current_progress_bar.setValue(100)

        # 更新最终统计
        self.success_count = stats["success_count"]
        self.error_count = stats["error_count"]
        self._update_stats()

        # 显示完成对话框
        msg = "批量转录完成!\n\n"
        msg += f"总文件数: {stats['total_files']}\n"
        msg += f"成功: {stats['success_count']}\n"
        msg += f"失败: {stats['error_count']}\n"
        msg += f"总耗时: {stats['total_time']:.1f}秒"

        if stats["errors"]:
            msg += "\n\n错误详情:\n"
            for file_path, error in stats["errors"][:5]:  # 最多显示5个错误
                msg += f"- {Path(file_path).name}: {error}\n"
            if len(stats["errors"]) > 5:
                msg += f"... 还有 {len(stats['errors']) - 5} 个错误"

        QMessageBox.information(self, "完成", msg)

        # 恢复UI状态
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)

        logger.info(f"批量转录完成: 成功{self.success_count}, 失败{self.error_count}")

    @Slot(str)
    def _on_error(self, error_msg: str):
        """处理错误"""
        QMessageBox.critical(self, "错误", f"批量转录失败:\n{error_msg}")

        # 恢复UI状态
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)

        logger.error(f"批量转录失败: {error_msg}")

    def _update_stats(self):
        """更新统计信息"""
        self.stats_label.setText(
            f"统计: 成功 {self.success_count}, 失败 {self.error_count}, "
            f"剩余 {self.total_files - self.success_count - self.error_count}"
        )

    def _format_time(self, seconds: float) -> str:
        """格式化时间为 HH:MM:SS

        Args:
            seconds: 秒数

        Returns:
            格式化的时间字符串
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def closeEvent(self, event):
        """关闭事件处理"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认关闭",
                "转录正在进行中,确定要关闭吗?\n已完成的文件不会受影响。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.worker.cancel()
                self.worker.wait(5000)  # 等待最多5秒
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
