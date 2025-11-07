"""转录结果显示组件
在主界面内实时显示转录结果
"""

import logging
from typing import Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QGroupBox, QLabel
)
from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QFont, QTextCursor

from src.transcription.models import TranscriptionResult

logger = logging.getLogger(__name__)


class TranscriptionResultDisplay(QWidget):
    """转录结果实时显示

    核心功能:
        - 实时滚动显示转录文本
        - 时间戳前缀（HH:MM:SS）
        - 自动滚动到最新
        - 文本选择和复制
        - 清空当前会话
        - 复制全部文本
        - 字数统计
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化转录结果显示

        Args:
            parent: 父组件
        """
        super().__init__(parent)

        # UI组件
        self.text_edit: Optional[QTextEdit] = None
        self.clear_button: Optional[QPushButton] = None
        self.copy_all_button: Optional[QPushButton] = None
        self.word_count_label: Optional[QLabel] = None

        # 内部状态
        self._auto_scroll = True
        self._word_count = 0

        # 初始化UI
        self._setup_ui()

        logger.debug("TranscriptionResultDisplay initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建分组框
        group_box = QGroupBox("实时转录结果")
        group_box_layout = QVBoxLayout(group_box)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        # 清空按钮
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.clear)
        toolbar_layout.addWidget(self.clear_button)

        # 复制全部按钮
        self.copy_all_button = QPushButton("复制全部")
        self.copy_all_button.clicked.connect(self._copy_all)
        toolbar_layout.addWidget(self.copy_all_button)

        # 弹簧（将后续元素推到右侧）
        toolbar_layout.addStretch()

        # 字数统计标签
        self.word_count_label = QLabel("字数: 0")
        self.word_count_label.setStyleSheet("color: gray;")
        toolbar_layout.addWidget(self.word_count_label)

        group_box_layout.addLayout(toolbar_layout)

        # 文本显示区域
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Microsoft YaHei", 10))
        self.text_edit.setMinimumHeight(200)
        group_box_layout.addWidget(self.text_edit)

        # 添加到主布局
        main_layout.addWidget(group_box)

    @Slot(object)
    def append_result(self, result: TranscriptionResult) -> None:
        """追加转录结果

        Args:
            result: 转录结果对象
        """
        # 格式化时间戳
        if result.start_time:
            dt = datetime.fromtimestamp(result.start_time)
            timestamp_str = dt.strftime("%H:%M:%S")
        else:
            timestamp_str = datetime.now().strftime("%H:%M:%S")

        # 格式化文本
        formatted_text = f"[{timestamp_str}] {result.text}"

        # 追加到文本编辑器
        self.text_edit.append(formatted_text)

        # 自动滚动到底部
        if self._auto_scroll:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.text_edit.setTextCursor(cursor)

        # 更新字数统计
        self._update_word_count()

        logger.debug(f"Result appended: {result.text[:50]}...")

    @Slot()
    def clear(self) -> None:
        """清空显示"""
        self.text_edit.clear()
        self._word_count = 0
        self._update_word_count()
        logger.debug("Result display cleared")

    @Slot()
    def _copy_all(self) -> None:
        """复制全部文本到剪贴板"""
        from PySide6.QtWidgets import QApplication

        full_text = self.text_edit.toPlainText()
        QApplication.clipboard().setText(full_text)
        logger.info("All text copied to clipboard")

    def get_full_text(self) -> str:
        """获取完整文本

        Returns:
            str: 完整转录文本
        """
        return self.text_edit.toPlainText()

    def _update_word_count(self) -> None:
        """更新字数统计"""
        full_text = self.text_edit.toPlainText()

        # 简单字数统计（中文字符 + 英文单词）
        chinese_chars = len([c for c in full_text if '\u4e00' <= c <= '\u9fff'])
        english_words = len(full_text.split())

        self._word_count = chinese_chars + english_words
        self.word_count_label.setText(f"字数: {self._word_count}")
