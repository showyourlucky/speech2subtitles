"""
系统设置对话框

提供图形化界面配置所有系统参数

布局:
    - 左侧: 导航列表 (QListWidget)
    - 右侧: 配置页面 (QStackedWidget)
    - 底部: 按钮栏 (保存/取消/恢复默认/导入/导出)

信号:
    settings_changed: 配置已更改 (Config)
"""

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QStackedWidget, QPushButton, QMessageBox,
    QWidget, QListWidgetItem, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QSlider,
    QSpinBox, QDoubleSpinBox, QComboBox,
    QGroupBox, QFileDialog, QColorDialog,
    QFontComboBox
)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QIcon, QColor, QFont, QFontDatabase

from src.config.models import Config, SubtitleDisplayConfig
from src.gui.bridges.config_bridge import ConfigBridge

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """系统设置对话框

    提供图形化界面配置所有系统参数
    """

    # 信号定义
    settings_changed = Signal(object)  # Config

    def __init__(self, config: Config, config_bridge: ConfigBridge, parent: Optional[QWidget] = None):
        """初始化设置对话框

        Args:
            config: 当前配置对象
            config_bridge: 配置桥接器
            parent: 父组件
        """
        super().__init__(parent)

        self.config = config
        self.config_bridge = config_bridge
        self.original_config = self._clone_config(config)  # 保存原始配置

        # UI组件
        self.nav_list: Optional[QListWidget] = None
        self.pages_widget: Optional[QStackedWidget] = None
        self.save_button: Optional[QPushButton] = None
        self.cancel_button: Optional[QPushButton] = None
        self.restore_button: Optional[QPushButton] = None
        self.import_button: Optional[QPushButton] = None
        self.export_button: Optional[QPushButton] = None

        # 配置页面
        self.general_page: Optional[QWidget] = None
        self.model_page: Optional[QWidget] = None
        self.vad_page: Optional[QWidget] = None
        self.audio_page: Optional[QWidget] = None
        self.gpu_page: Optional[QWidget] = None
        self.subtitle_page: Optional[QWidget] = None

        # 配置控件引用（用于收集设置）
        self.config_widgets: Dict[str, Any] = {}

        # 初始化UI
        self._setup_ui()
        self._create_pages()
        self._load_settings()

        logger.debug("SettingsDialog initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        self.setWindowTitle("系统设置")
        self.setMinimumSize(800, 600)
        self.setModal(True)

        # 主布局
        main_layout = QVBoxLayout(self)

        # 内容区域（左右分割）
        content_layout = QHBoxLayout()

        # 左侧导航列表
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(150)
        self.nav_list.currentRowChanged.connect(self._on_page_changed)
        content_layout.addWidget(self.nav_list)

        # 右侧页面容器
        self.pages_widget = QStackedWidget()
        content_layout.addWidget(self.pages_widget)

        main_layout.addLayout(content_layout)

        # 底部按钮栏
        button_layout = QHBoxLayout()

        # 导入/导出按钮
        self.import_button = QPushButton("导入配置...")
        self.import_button.clicked.connect(self._on_import_clicked)
        button_layout.addWidget(self.import_button)

        self.export_button = QPushButton("导出配置...")
        self.export_button.clicked.connect(self._on_export_clicked)
        button_layout.addWidget(self.export_button)

        button_layout.addStretch()

        # 恢复默认按钮
        self.restore_button = QPushButton("恢复默认")
        self.restore_button.clicked.connect(self._on_restore_defaults)
        button_layout.addWidget(self.restore_button)

        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        # 保存按钮
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self._on_save_clicked)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)

    def _create_pages(self) -> None:
        """创建所有配置页面"""
        # 通用设置页
        self.general_page = self._create_general_page()
        self._add_page("通用", self.general_page)

        # 模型配置页
        self.model_page = self._create_model_page()
        self._add_page("模型", self.model_page)

        # VAD参数页
        self.vad_page = self._create_vad_page()
        self._add_page("VAD", self.vad_page)

        # 音频设置页
        self.audio_page = self._create_audio_page()
        self._add_page("音频", self.audio_page)

        # GPU设置页
        self.gpu_page = self._create_gpu_page()
        self._add_page("GPU", self.gpu_page)

        # 字幕显示页
        self.subtitle_page = self._create_subtitle_page()
        self._add_page("字幕", self.subtitle_page)

    def _add_page(self, title: str, widget: QWidget) -> None:
        """添加配置页面

        Args:
            title: 页面标题
            widget: 页面组件
        """
        item = QListWidgetItem(title)
        self.nav_list.addItem(item)
        self.pages_widget.addWidget(widget)

    @Slot(int)
    def _on_page_changed(self, index: int) -> None:
        """处理页面切换

        Args:
            index: 新页面索引
        """
        self.pages_widget.setCurrentIndex(index)

    @Slot()
    def _on_save_clicked(self) -> None:
        """处理保存按钮点击"""
        try:
            # 从UI收集配置
            self._collect_settings()

            # 验证配置
            self.config.validate()

            # 保存配置
            success = self.config_bridge.save_config(self.config)
            if not success:
                QMessageBox.warning(self, "保存失败", "配置保存失败，请检查日志")
                return

            # 发射信号
            self.settings_changed.emit(self.config)

            # 关闭对话框
            self.accept()

            logger.info("Settings saved successfully")

        except ValueError as e:
            QMessageBox.warning(self, "配置错误", f"配置验证失败:\n{e}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.critical(self, "错误", f"保存设置时发生错误:\n{e}")

    @Slot()
    def _on_restore_defaults(self) -> None:
        """恢复默认配置"""
        reply = QMessageBox.question(
            self,
            "确认恢复",
            "确定要恢复所有设置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            from src.config.manager import ConfigManager
            config_manager = ConfigManager()
            self.config = config_manager.get_default_config()
            self._load_settings()
            logger.info("Settings restored to defaults")

    @Slot()
    def _on_import_clicked(self) -> None:
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入配置文件",
            "",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )

        if file_path:
            config, error = self.config_bridge.file_manager.import_config(file_path)
            if config:
                self.config = config
                self._load_settings()
                QMessageBox.information(self, "导入成功", "配置已成功导入")
                logger.info(f"Config imported from: {file_path}")
            else:
                QMessageBox.warning(self, "导入失败", f"导入配置失败:\n{error}")

    @Slot()
    def _on_export_clicked(self) -> None:
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出配置文件",
            "",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )

        if file_path:
            # 确保文件扩展名
            if not file_path.endswith('.json'):
                file_path += '.json'

            success, error = self.config_bridge.file_manager.export_config(file_path, self.config)
            if success:
                QMessageBox.information(self, "导出成功", f"配置已导出到:\n{file_path}")
                logger.info(f"Config exported to: {file_path}")
            else:
                QMessageBox.warning(self, "导出失败", f"导出配置失败:\n{error}")

    def _clone_config(self, config: Config) -> Config:
        """克隆配置对象

        Args:
            config: 源配置对象

        Returns:
            Config: 克隆的配置对象
        """
        from dataclasses import asdict
        return Config(**asdict(config))

    def _ensure_audio_input_mutual_exclusion(self) -> None:
        """确保音频输入配置的互斥性

        规则：input_source 和 input_file 不能同时设置
        """
        # 如果同时设置了两个参数，根据优先级决定保留哪个
        if self.config.input_source is not None and self.config.input_file is not None:
            # 检查input_file是否有效（文件是否存在）
            input_file_valid = False
            if self.config.input_file:
                from pathlib import Path
                if isinstance(self.config.input_file, list):
                    input_file_valid = any(Path(f).exists() for f in self.config.input_file if f)
                else:
                    input_file_valid = Path(self.config.input_file).exists()

            # 如果input_file指向有效文件，优先保留文件模式
            if input_file_valid:
                self.config.input_source = None
                logger.info("配置调整：文件模式有效，清除input_source设置")
            else:
                # 否则保留实时模式，清除文件设置
                self.config.input_file = None
                logger.info("配置调整：保留实时模式，清除input_file设置")

        # 如果只设置了input_file但无效，清除它
        elif self.config.input_file is not None:
            from pathlib import Path
            input_file_valid = False
            if isinstance(self.config.input_file, list):
                input_file_valid = any(Path(f).exists() for f in self.config.input_file if f)
            else:
                input_file_valid = Path(self.config.input_file).exists()

            if not input_file_valid:
                self.config.input_file = None
                logger.info("配置调整：input_file无效，已清除")

        logger.debug(f"音频输入配置调整完成: input_source={self.config.input_source}, input_file={self.config.input_file}")

    def _load_settings(self) -> None:
        """从Config对象加载设置到UI"""
        # 通用设置
        self._load_general_settings()

        # 模型设置
        self._load_model_settings()

        # VAD设置
        self._load_vad_settings()

        # 音频设置
        self._load_audio_settings()

        # GPU设置
        self._load_gpu_settings()

        # 字幕设置
        self._load_subtitle_settings()

    def _collect_settings(self) -> None:
        """从UI收集设置到Config对象"""
        # 通用设置
        self._collect_general_settings()

        # 模型设置
        self._collect_model_settings()

        # VAD设置
        self._collect_vad_settings()

        # 音频设置
        self._collect_audio_settings()

        # GPU设置
        self._collect_gpu_settings()

        # 字幕设置
        self._collect_subtitle_settings()

        # 确保input_source和input_file的互斥性
        # 根据当前GUI的状态来决定保留哪个参数
        self._ensure_audio_input_mutual_exclusion()

    # ========== 配置页面创建方法 ==========

    def _create_general_page(self) -> QWidget:
        """创建通用设置页"""
        page = QWidget()
        layout = QFormLayout(page)

        # 语言设置（预留）
        language_combo = QComboBox()
        language_combo.addItems(["简体中文", "English"])
        language_combo.setCurrentText("简体中文")
        layout.addRow("界面语言:", language_combo)
        self.config_widgets['language'] = language_combo

        # 启动时恢复上次设置
        restore_checkbox = QCheckBox("启动时恢复上次设置")
        layout.addRow(restore_checkbox)
        self.config_widgets['restore_settings'] = restore_checkbox

        # 自动保存转录历史
        auto_save_checkbox = QCheckBox("自动保存转录历史记录")
        auto_save_checkbox.setChecked(True)
        layout.addRow(auto_save_checkbox)
        self.config_widgets['auto_save_history'] = auto_save_checkbox

        return page

    def _create_model_page(self) -> QWidget:
        """创建模型配置页"""
        page = QWidget()
        layout = QFormLayout(page)

        # 模型路径
        model_layout = QHBoxLayout()
        model_path_edit = QLineEdit()
        browse_button = QPushButton("浏览...")

        def browse_model():
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择模型文件",
                "",
                "ONNX模型 (*.onnx);;所有文件 (*.*)"
            )
            if file_path:
                model_path_edit.setText(file_path)

        browse_button.clicked.connect(browse_model)
        model_layout.addWidget(model_path_edit)
        model_layout.addWidget(browse_button)

        layout.addRow("模型路径:", model_layout)
        self.config_widgets['model_path'] = model_path_edit

        # 模型验证按钮
        validate_button = QPushButton("验证模型")
        validate_button.clicked.connect(lambda: self._validate_model(model_path_edit.text()))
        layout.addRow(validate_button)

        return page

    def _create_vad_page(self) -> QWidget:
        """创建VAD参数页"""
        page = QWidget()
        layout = QFormLayout(page)

        # VAD敏感度
        sensitivity_layout = QHBoxLayout()
        sensitivity_slider = QSlider(Qt.Horizontal)
        sensitivity_slider.setRange(0, 100)
        sensitivity_slider.setValue(int(self.config.vad_sensitivity * 100))
        sensitivity_spinbox = QDoubleSpinBox()
        sensitivity_spinbox.setRange(0.0, 1.0)
        sensitivity_spinbox.setSingleStep(0.1)
        sensitivity_spinbox.setValue(self.config.vad_sensitivity)
        sensitivity_spinbox.setDecimals(2)

        def sync_sensitivity_slider(value):
            sensitivity_spinbox.setValue(value / 100.0)

        def sync_sensitivity_spinbox(value):
            sensitivity_slider.setValue(int(value * 100))

        sensitivity_slider.valueChanged.connect(sync_sensitivity_slider)
        sensitivity_spinbox.valueChanged.connect(sync_sensitivity_spinbox)

        sensitivity_layout.addWidget(sensitivity_slider)
        sensitivity_layout.addWidget(sensitivity_spinbox)
        layout.addRow("敏感度:", sensitivity_layout)
        self.config_widgets['vad_sensitivity'] = sensitivity_spinbox

        # VAD阈值
        threshold_layout = QHBoxLayout()
        threshold_slider = QSlider(Qt.Horizontal)
        threshold_slider.setRange(0, 100)
        threshold_slider.setValue(int(self.config.vad_threshold * 100))
        threshold_spinbox = QDoubleSpinBox()
        threshold_spinbox.setRange(0.0, 1.0)
        threshold_spinbox.setSingleStep(0.1)
        threshold_spinbox.setValue(self.config.vad_threshold)
        threshold_spinbox.setDecimals(2)

        def sync_threshold_slider(value):
            threshold_spinbox.setValue(value / 100.0)

        def sync_threshold_spinbox(value):
            threshold_slider.setValue(int(value * 100))

        threshold_slider.valueChanged.connect(sync_threshold_slider)
        threshold_spinbox.valueChanged.connect(sync_threshold_spinbox)

        threshold_layout.addWidget(threshold_slider)
        threshold_layout.addWidget(threshold_spinbox)
        layout.addRow("阈值:", threshold_layout)
        self.config_widgets['vad_threshold'] = threshold_spinbox

        # VAD窗口大小
        window_size_spinbox = QDoubleSpinBox()
        window_size_spinbox.setRange(0.1, 2.0)
        window_size_spinbox.setSingleStep(0.1)
        window_size_spinbox.setValue(self.config.vad_window_size)
        window_size_spinbox.setDecimals(3)
        layout.addRow("窗口大小(秒):", window_size_spinbox)
        self.config_widgets['vad_window_size'] = window_size_spinbox

        return page

    def _create_audio_page(self) -> QWidget:
        """创建音频设置页"""
        page = QWidget()
        layout = QFormLayout(page)

        # 采样率选择
        sample_rate_combo = QComboBox()
        sample_rate_combo.addItems(["8000", "16000", "22050", "44100", "48000"])
        sample_rate_combo.setCurrentText(str(self.config.sample_rate))
        layout.addRow("采样率(Hz):", sample_rate_combo)
        self.config_widgets['sample_rate'] = sample_rate_combo

        # 缓冲区大小
        chunk_size_combo = QComboBox()
        chunk_size_combo.addItems(["512", "1024", "2048", "4096"])
        chunk_size_combo.setCurrentText(str(self.config.chunk_size))
        layout.addRow("缓冲区大小:", chunk_size_combo)
        self.config_widgets['chunk_size'] = chunk_size_combo

        # 音频设备ID（暂时禁用，未来实现）
        device_id_spinbox = QSpinBox()
        device_id_spinbox.setRange(-1, 10)
        device_id_spinbox.setValue(self.config.device_id or -1)
        device_id_spinbox.setSpecialValueText("默认设备")
        device_id_spinbox.setEnabled(False)  # 暂时禁用
        layout.addRow("设备ID:", device_id_spinbox)
        self.config_widgets['device_id'] = device_id_spinbox

        # 设备信息显示
        device_info_label = QLabel("音频设备检测功能将在未来版本中实现")
        device_info_label.setStyleSheet("color: gray;")
        layout.addRow(device_info_label)

        return page

    def _create_gpu_page(self) -> QWidget:
        """创建GPU设置页"""
        page = QWidget()
        layout = QFormLayout(page)

        # GPU启用复选框
        gpu_checkbox = QCheckBox("启用GPU加速")
        gpu_checkbox.setChecked(not self.config.use_gpu)
        layout.addRow(gpu_checkbox)
        self.config_widgets['use_gpu'] = gpu_checkbox

        # GPU设备选择（暂时禁用，未来实现）
        gpu_device_combo = QComboBox()
        gpu_device_combo.addItems(["自动选择", "GPU 0", "GPU 1"])
        gpu_device_combo.setEnabled(False)  # 暂时禁用
        layout.addRow("GPU设备:", gpu_device_combo)
        self.config_widgets['gpu_device'] = gpu_device_combo

        # GPU信息显示
        gpu_info_label = QLabel("多GPU支持将在未来版本中实现")
        gpu_info_label.setStyleSheet("color: gray;")
        layout.addRow(gpu_info_label)

        return page

    def _create_subtitle_page(self) -> QWidget:
        """创建字幕显示页"""
        page = QWidget()
        layout = QFormLayout(page)

        # 启用字幕显示
        subtitle_enabled_checkbox = QCheckBox("启用字幕显示")
        subtitle_enabled_checkbox.setChecked(self.config.subtitle_display.enabled)
        layout.addRow(subtitle_enabled_checkbox)
        self.config_widgets['subtitle_enabled'] = subtitle_enabled_checkbox

        # 字体选择
        font_combo = QFontComboBox()
        font_combo.setCurrentFont(QFont(self.config.subtitle_display.font_family))
        layout.addRow("字体:", font_combo)
        self.config_widgets['subtitle_font_family'] = font_combo

        # 字体大小
        font_size_spinbox = QSpinBox()
        font_size_spinbox.setRange(10, 72)
        font_size_spinbox.setValue(self.config.subtitle_display.font_size)
        layout.addRow("字体大小:", font_size_spinbox)
        self.config_widgets['subtitle_font_size'] = font_size_spinbox

        # 字幕位置
        position_combo = QComboBox()
        position_combo.addItems(["顶部", "中间", "底部"])
        position_mapping = {"顶部": "top", "中间": "center", "底部": "bottom"}
        reverse_mapping = {v: k for k, v in position_mapping.items()}
        current_pos = reverse_mapping.get(self.config.subtitle_display.position, "底部")
        position_combo.setCurrentText(current_pos)
        layout.addRow("位置:", position_combo)
        self.config_widgets['subtitle_position'] = position_combo

        # 文本颜色
        text_color_layout = QHBoxLayout()
        text_color_button = QPushButton("选择颜色")
        text_color_label = QLabel(self.config.subtitle_display.text_color)

        def choose_text_color():
            color = QColorDialog.getColor(QColor(self.config.subtitle_display.text_color), self)
            if color.isValid():
                text_color_label.setText(color.name())
                self.config.subtitle_display.text_color = color.name()

        text_color_button.clicked.connect(choose_text_color)
        text_color_layout.addWidget(text_color_button)
        text_color_layout.addWidget(text_color_label)
        layout.addRow("文本颜色:", text_color_layout)
        self.config_widgets['subtitle_text_color'] = text_color_label

        # 背景颜色
        bg_color_layout = QHBoxLayout()
        bg_color_button = QPushButton("选择颜色")
        bg_color_label = QLabel(self.config.subtitle_display.background_color)

        def choose_bg_color():
            color = QColorDialog.getColor(QColor(self.config.subtitle_display.background_color), self)
            if color.isValid():
                bg_color_label.setText(color.name())
                self.config.subtitle_display.background_color = color.name()

        bg_color_button.clicked.connect(choose_bg_color)
        bg_color_layout.addWidget(bg_color_button)
        bg_color_layout.addWidget(bg_color_label)
        layout.addRow("背景颜色:", bg_color_layout)
        self.config_widgets['subtitle_background_color'] = bg_color_label

        # 透明度
        opacity_layout = QHBoxLayout()
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(int(self.config.subtitle_display.opacity * 100))
        opacity_spinbox = QDoubleSpinBox()
        opacity_spinbox.setRange(0.0, 1.0)
        opacity_spinbox.setSingleStep(0.1)
        opacity_spinbox.setValue(self.config.subtitle_display.opacity)
        opacity_spinbox.setDecimals(2)

        def sync_opacity_slider(value):
            opacity_spinbox.setValue(value / 100.0)

        def sync_opacity_spinbox(value):
            opacity_slider.setValue(int(value * 100))

        opacity_slider.valueChanged.connect(sync_opacity_slider)
        opacity_spinbox.valueChanged.connect(sync_opacity_spinbox)

        opacity_layout.addWidget(opacity_slider)
        opacity_layout.addWidget(opacity_spinbox)
        layout.addRow("透明度:", opacity_layout)
        self.config_widgets['subtitle_opacity'] = opacity_spinbox

        return page

    # ========== 设置加载和收集方法 ==========

    def _load_general_settings(self) -> None:
        """加载通用设置"""
        # 通用设置暂时使用默认值
        pass

    def _load_model_settings(self) -> None:
        """加载模型设置"""
        if 'model_path' in self.config_widgets:
            self.config_widgets['model_path'].setText(self.config.model_path or "")

    def _load_vad_settings(self) -> None:
        """加载VAD设置"""
        if 'vad_sensitivity' in self.config_widgets:
            self.config_widgets['vad_sensitivity'].setValue(self.config.vad_sensitivity)
        if 'vad_threshold' in self.config_widgets:
            self.config_widgets['vad_threshold'].setValue(self.config.vad_threshold)
        if 'vad_window_size' in self.config_widgets:
            self.config_widgets['vad_window_size'].setValue(self.config.vad_window_size)

    def _load_audio_settings(self) -> None:
        """加载音频设置"""
        if 'sample_rate' in self.config_widgets:
            self.config_widgets['sample_rate'].setCurrentText(str(self.config.sample_rate))
        if 'chunk_size' in self.config_widgets:
            self.config_widgets['chunk_size'].setCurrentText(str(self.config.chunk_size))
        if 'device_id' in self.config_widgets:
            self.config_widgets['device_id'].setValue(self.config.device_id or -1)

    def _load_gpu_settings(self) -> None:
        """加载GPU设置"""
        if 'use_gpu' in self.config_widgets:
            self.config_widgets['use_gpu'].setChecked(not self.config.use_gpu)

    def _load_subtitle_settings(self) -> None:
        """加载字幕设置"""
        subtitle_config = self.config.subtitle_display

        if 'subtitle_enabled' in self.config_widgets:
            self.config_widgets['subtitle_enabled'].setChecked(subtitle_config.enabled)
        if 'subtitle_font_family' in self.config_widgets:
            self.config_widgets['subtitle_font_family'].setCurrentFont(QFont(subtitle_config.font_family))
        if 'subtitle_font_size' in self.config_widgets:
            self.config_widgets['subtitle_font_size'].setValue(subtitle_config.font_size)
        if 'subtitle_position' in self.config_widgets:
            position_mapping = {"top": "顶部", "center": "中间", "bottom": "底部"}
            current_pos = position_mapping.get(subtitle_config.position, "底部")
            self.config_widgets['subtitle_position'].setCurrentText(current_pos)
        if 'subtitle_text_color' in self.config_widgets:
            self.config_widgets['subtitle_text_color'].setText(subtitle_config.text_color)
        if 'subtitle_background_color' in self.config_widgets:
            self.config_widgets['subtitle_background_color'].setText(subtitle_config.background_color)
        if 'subtitle_opacity' in self.config_widgets:
            self.config_widgets['subtitle_opacity'].setValue(subtitle_config.opacity)

    def _collect_general_settings(self) -> None:
        """收集通用设置"""
        # 通用设置暂时不保存到Config对象
        pass

    def _collect_model_settings(self) -> None:
        """收集模型设置"""
        if 'model_path' in self.config_widgets:
            self.config.model_path = self.config_widgets['model_path'].text().strip()

    def _collect_vad_settings(self) -> None:
        """收集VAD设置"""
        if 'vad_sensitivity' in self.config_widgets:
            self.config.vad_sensitivity = self.config_widgets['vad_sensitivity'].value()
        if 'vad_threshold' in self.config_widgets:
            self.config.vad_threshold = self.config_widgets['vad_threshold'].value()
        if 'vad_window_size' in self.config_widgets:
            self.config.vad_window_size = self.config_widgets['vad_window_size'].value()

    def _collect_audio_settings(self) -> None:
        """收集音频设置"""
        if 'sample_rate' in self.config_widgets:
            self.config.sample_rate = int(self.config_widgets['sample_rate'].currentText())
        if 'chunk_size' in self.config_widgets:
            self.config.chunk_size = int(self.config_widgets['chunk_size'].currentText())
        if 'device_id' in self.config_widgets:
            device_id = self.config_widgets['device_id'].value()
            self.config.device_id = device_id if device_id != -1 else None

    def _collect_gpu_settings(self) -> None:
        """收集GPU设置"""
        if 'use_gpu' in self.config_widgets:
            self.config.use_gpu = not self.config_widgets['use_gpu'].isChecked()

    def _collect_subtitle_settings(self) -> None:
        """收集字幕设置"""
        subtitle_config = self.config.subtitle_display

        if 'subtitle_enabled' in self.config_widgets:
            subtitle_config.enabled = self.config_widgets['subtitle_enabled'].isChecked()
        if 'subtitle_font_family' in self.config_widgets:
            subtitle_config.font_family = self.config_widgets['subtitle_font_family'].currentFont().family()
        if 'subtitle_font_size' in self.config_widgets:
            subtitle_config.font_size = self.config_widgets['subtitle_font_size'].value()
        if 'subtitle_position' in self.config_widgets:
            position_mapping = {"顶部": "top", "中间": "center", "底部": "bottom"}
            current_text = self.config_widgets['subtitle_position'].currentText()
            subtitle_config.position = position_mapping.get(current_text, "bottom")
        if 'subtitle_text_color' in self.config_widgets:
            subtitle_config.text_color = self.config_widgets['subtitle_text_color'].text()
        if 'subtitle_background_color' in self.config_widgets:
            subtitle_config.background_color = self.config_widgets['subtitle_background_color'].text()
        if 'subtitle_opacity' in self.config_widgets:
            subtitle_config.opacity = self.config_widgets['subtitle_opacity'].value()

    def _validate_model(self, model_path: str) -> None:
        """验证模型文件

        Args:
            model_path: 模型文件路径
        """
        if not model_path.strip():
            QMessageBox.warning(self, "验证失败", "请先选择模型文件路径")
            return

        from pathlib import Path
        model_file = Path(model_path.strip())

        if not model_file.exists():
            QMessageBox.warning(self, "验证失败", f"模型文件不存在:\n{model_path}")
            return

        if not model_file.suffix.lower() == '.onnx':
            QMessageBox.warning(self, "验证失败", "模型文件必须是 ONNX 格式")
            return

        # 简单的文件大小检查
        file_size_mb = model_file.stat().st_size / (1024 * 1024)
        if file_size_mb < 1:
            QMessageBox.warning(self, "验证失败", "模型文件过小，可能不是有效的模型文件")
            return

        QMessageBox.information(self, "验证成功", f"模型文件验证通过\n文件大小: {file_size_mb:.1f} MB")