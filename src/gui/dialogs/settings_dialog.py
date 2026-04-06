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

        # VAD方案管理组件
        self.vad_profile_list: Optional[QListWidget] = None
        self.vad_add_button: Optional[QPushButton] = None
        self.vad_delete_button: Optional[QPushButton] = None
        self.vad_copy_button: Optional[QPushButton] = None
        self.current_editing_profile_id: Optional[str] = None  # 当前正在编辑的VAD方案ID

        # 模型方案管理组件
        self.model_profile_list: Optional[QListWidget] = None
        self.model_add_button: Optional[QPushButton] = None
        self.model_delete_button: Optional[QPushButton] = None
        self.model_copy_button: Optional[QPushButton] = None
        self.current_editing_model_profile_id: Optional[str] = None  # 当前正在编辑的模型方案ID

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
        """创建模型方案管理页面

        布局:
            左侧: 模型方案列表 + 操作按钮(新增/删除/复制)
            右侧: 选中方案的参数编辑区域
        """
        page = QWidget()
        main_layout = QHBoxLayout(page)

        # === 左侧: 方案列表区域 ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 方案列表标题
        list_title = QLabel("模型方案")
        list_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(list_title)

        # 方案列表
        self.model_profile_list = QListWidget()
        self.model_profile_list.currentItemChanged.connect(self._on_model_profile_selected)
        left_layout.addWidget(self.model_profile_list)

        # 方案操作按钮栏
        button_layout = QHBoxLayout()

        self.model_add_button = QPushButton("新增")
        self.model_add_button.clicked.connect(self._on_add_model_profile)
        button_layout.addWidget(self.model_add_button)

        self.model_delete_button = QPushButton("删除")
        self.model_delete_button.clicked.connect(self._on_delete_model_profile)
        button_layout.addWidget(self.model_delete_button)

        self.model_copy_button = QPushButton("复制")
        self.model_copy_button.clicked.connect(self._on_duplicate_model_profile)
        button_layout.addWidget(self.model_copy_button)


        left_layout.addLayout(button_layout)
        left_widget.setMaximumWidth(250)

        # === 右侧: 参数编辑区域 ===
        right_widget = QWidget()
        right_layout = QFormLayout(right_widget)

        # 方案名称
        profile_name_edit = QLineEdit()
        right_layout.addRow("方案名称:", profile_name_edit)
        self.config_widgets['model_profile_name'] = profile_name_edit

        # 模型路径
        model_path_layout = QHBoxLayout()
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
        model_path_layout.addWidget(model_path_edit)
        model_path_layout.addWidget(browse_button)
        right_layout.addRow("模型路径:", model_path_layout)
        self.config_widgets['model_profile_path'] = model_path_edit

        # 描述
        description_edit = QLineEdit()
        description_edit.setPlaceholderText("可选: 模型描述信息")
        right_layout.addRow("描述:", description_edit)
        self.config_widgets['model_profile_description'] = description_edit

        # 支持的语言
        languages_edit = QLineEdit()
        languages_edit.setPlaceholderText("可选: 例如 zh,en,ja,ko,yue")
        right_layout.addRow("支持语言:", languages_edit)
        self.config_widgets['model_profile_languages'] = languages_edit

        # 验证模型按钮
        validate_button = QPushButton("验证模型文件")
        validate_button.clicked.connect(self._on_validate_model_file)
        right_layout.addRow("", validate_button)

        # 说明文本
        help_label = QLabel(
            "提示:\n"
            "• 支持的模型格式: .onnx, .bin\n"
            "• 支持语言用逗号分隔,例如: zh,en,ja\n"
            "• 修改后需点击'保存'按钮保存配置"
        )
        help_label.setStyleSheet("color: gray; font-size: 11px;")
        help_label.setWordWrap(True)
        right_layout.addRow(help_label)

        # 添加左右面板到主布局
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)

        return page

    def _create_vad_page(self) -> QWidget:
        """创建VAD方案管理页面

        布局:
            左侧: VAD方案列表 + 操作按钮(新增/删除/复制)
            右侧: 选中方案的参数编辑区域
        """
        page = QWidget()
        main_layout = QHBoxLayout(page)

        # === 左侧: 方案列表区域 ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 方案列表标题
        list_title = QLabel("VAD方案")
        list_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(list_title)

        # 方案列表
        self.vad_profile_list = QListWidget()
        self.vad_profile_list.currentItemChanged.connect(self._on_vad_profile_selected)
        left_layout.addWidget(self.vad_profile_list)

        # 方案操作按钮栏
        button_layout = QHBoxLayout()

        self.vad_add_button = QPushButton("新增")
        self.vad_add_button.clicked.connect(self._on_add_vad_profile)
        button_layout.addWidget(self.vad_add_button)

        self.vad_delete_button = QPushButton("删除")
        self.vad_delete_button.clicked.connect(self._on_delete_vad_profile)
        button_layout.addWidget(self.vad_delete_button)

        self.vad_copy_button = QPushButton("复制")
        self.vad_copy_button.clicked.connect(self._on_duplicate_vad_profile)
        button_layout.addWidget(self.vad_copy_button)


        left_layout.addLayout(button_layout)
        left_widget.setMaximumWidth(250)

        # === 右侧: 参数编辑区域 ===
        right_widget = QWidget()
        right_layout = QFormLayout(right_widget)


        # 方案名称
        profile_name_edit = QLineEdit()
        right_layout.addRow("方案名称:", profile_name_edit)
        self.config_widgets['vad_profile_name'] = profile_name_edit

        # 阈值 (threshold)
        threshold_layout = QHBoxLayout()
        threshold_slider = QSlider(Qt.Horizontal)
        threshold_slider.setRange(0, 100)
        threshold_spinbox = QDoubleSpinBox()
        threshold_spinbox.setRange(0.0, 1.0)
        threshold_spinbox.setSingleStep(0.01)
        threshold_spinbox.setDecimals(3)

        def sync_threshold_slider(value):
            threshold_spinbox.setValue(value / 100.0)
        def sync_threshold_spinbox(value):
            threshold_slider.setValue(int(value * 100))

        threshold_slider.valueChanged.connect(sync_threshold_slider)
        threshold_spinbox.valueChanged.connect(sync_threshold_spinbox)

        threshold_layout.addWidget(threshold_slider)
        threshold_layout.addWidget(threshold_spinbox)
        right_layout.addRow("阈值 (0.0-1.0):", threshold_layout)
        self.config_widgets['vad_profile_threshold'] = threshold_spinbox

        # 最小语音持续时间 (min_speech_duration_ms)
        min_speech_spinbox = QSpinBox()
        min_speech_spinbox.setRange(10, 5000)
        min_speech_spinbox.setSingleStep(10)
        min_speech_spinbox.setSuffix(" ms")
        right_layout.addRow("最小语音持续时间:", min_speech_spinbox)
        self.config_widgets['vad_profile_min_speech_duration_ms'] = min_speech_spinbox

        # 最小静音持续时间 (min_silence_duration_ms)
        min_silence_spinbox = QSpinBox()
        min_silence_spinbox.setRange(10, 5000)
        min_silence_spinbox.setSingleStep(10)
        min_silence_spinbox.setSuffix(" ms")
        right_layout.addRow("最小静音持续时间:", min_silence_spinbox)
        self.config_widgets['vad_profile_min_silence_duration_ms'] = min_silence_spinbox

        # 最大语音持续时间 (max_speech_duration_ms)
        max_speech_spinbox = QSpinBox()
        max_speech_spinbox.setRange(1000, 60000)
        max_speech_spinbox.setSingleStep(1000)
        max_speech_spinbox.setSuffix(" ms")
        right_layout.addRow("最大语音持续时间:", max_speech_spinbox)
        self.config_widgets['vad_profile_max_speech_duration_ms'] = max_speech_spinbox

        # 采样率 (sample_rate)
        sample_rate_combo = QComboBox()
        sample_rate_combo.addItems(["8000", "16000", "22050", "44100", "48000"])
        right_layout.addRow("采样率 (Hz):", sample_rate_combo)
        self.config_widgets['vad_profile_sample_rate'] = sample_rate_combo

        # 窗口大小 (window_size_samples)
        window_size_spinbox = QSpinBox()
        window_size_spinbox.setRange(256, 2048)
        window_size_spinbox.setSingleStep(256)
        window_size_spinbox.setSuffix(" samples")
        right_layout.addRow("窗口大小:", window_size_spinbox)
        self.config_widgets['vad_profile_window_size_samples'] = window_size_spinbox

        # 模型类型 (model)
        model_combo = QComboBox()
        model_combo.addItems(["silero_vad", "ten_vad"])
        right_layout.addRow("模型类型:", model_combo)
        self.config_widgets['vad_profile_model'] = model_combo

        # 模型路径 (model_path)
        model_path_layout = QHBoxLayout()
        model_path_edit = QLineEdit()
        model_path_browse_button = QPushButton("浏览...")

        def browse_vad_model():
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择VAD模型文件",
                "",
                "ONNX模型 (*.onnx);;所有文件 (*.*)"
            )
            if file_path:
                model_path_edit.setText(file_path)

        model_path_browse_button.clicked.connect(browse_vad_model)
        model_path_layout.addWidget(model_path_edit)
        model_path_layout.addWidget(model_path_browse_button)
        right_layout.addRow("模型路径:", model_path_layout)
        self.config_widgets['vad_profile_model_path'] = model_path_edit

        # 使用sherpa-onnx (use_sherpa_onnx)
        use_sherpa_checkbox = QCheckBox("使用 sherpa-onnx 实现")
        use_sherpa_checkbox.setChecked(True)
        right_layout.addRow(use_sherpa_checkbox)
        self.config_widgets['vad_profile_use_sherpa_onnx'] = use_sherpa_checkbox

        # 添加说明文本
        help_text = QLabel(
            "提示: 不同场景可创建不同方案,如\"安静环境\"、\"嘈杂环境\"等。\n"
            "调整参数以适应您的使用场景,保存后可在主界面快速切换。"
        )
        help_text.setStyleSheet("color: gray; font-size: 11px;")
        help_text.setWordWrap(True)
        right_layout.addRow(help_text)

        # 组装左右布局
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, stretch=1)

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
        gpu_checkbox.setChecked(self.config.use_gpu)
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
        """加载模型设置 - 加载所有模型方案到列表"""
        if self.model_profile_list is None:
            return

        # 清空列表
        self.model_profile_list.clear()

        # 加载所有模型方案
        for profile_id, profile in self.config.model_profiles.items():
            item = QListWidgetItem(profile.profile_name)
            item.setData(Qt.UserRole, profile_id)  # 存储profile_id
            self.model_profile_list.addItem(item)

            # 如果是活跃方案,选中它
            if profile_id == self.config.active_model_profile_id:
                self.model_profile_list.setCurrentItem(item)

        # 如果没有选中任何方案,选中第一个
        if self.model_profile_list.currentItem() is None and self.model_profile_list.count() > 0:
            self.model_profile_list.setCurrentRow(0)

    def _load_vad_settings(self) -> None:
        """加载VAD设置 - 加载所有VAD方案到列表"""
        if self.vad_profile_list is None:
            return

        # 清空列表
        self.vad_profile_list.clear()

        # 加载所有VAD方案
        for profile_id, profile in self.config.vad_profiles.items():
            item = QListWidgetItem(profile.profile_name)
            item.setData(Qt.UserRole, profile_id)  # 存储profile_id
            self.vad_profile_list.addItem(item)

            # 如果是活跃方案,选中它
            if profile_id == self.config.active_vad_profile_id:
                self.vad_profile_list.setCurrentItem(item)

        # 如果没有选中任何方案,选中第一个
        if self.vad_profile_list.currentItem() is None and self.vad_profile_list.count() > 0:
            self.vad_profile_list.setCurrentRow(0)

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
            self.config_widgets['use_gpu'].setChecked(self.config.use_gpu)

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
        """收集模型设置 - 保存当前编辑的方案参数"""
        if self.current_editing_model_profile_id is None:
            return

        # 从UI控件收集参数
        profile = self.config.model_profiles.get(self.current_editing_model_profile_id)
        if profile is None:
            logger.warning(f"Cannot collect settings: model profile {self.current_editing_model_profile_id} not found")
            return

        # 更新方案名称 - 添加重复校验
        if 'model_profile_name' in self.config_widgets:
            new_profile_name = self.config_widgets['model_profile_name'].text().strip()

            # 检查方案名是否发生变化
            if new_profile_name != profile.profile_name:
                # 检查新名称是否与其他方案重复
                for pid, existing_profile in self.config.model_profiles.items():
                    if pid != self.current_editing_model_profile_id and existing_profile.profile_name == new_profile_name:
                        QMessageBox.warning(
                            self,
                            "名称重复",
                            f"方案名称'{new_profile_name}'已存在,请使用其他名称"
                        )
                        # 恢复原名称到UI
                        self.config_widgets['model_profile_name'].setText(profile.profile_name)
                        return

            profile.profile_name = new_profile_name

        # 更新模型路径
        if 'model_profile_path' in self.config_widgets:
            profile.model_path = self.config_widgets['model_profile_path'].text().strip()

        # 更新描述
        if 'model_profile_description' in self.config_widgets:
            description_text = self.config_widgets['model_profile_description'].text().strip()
            profile.description = description_text if description_text else None

        # 更新支持的语言
        if 'model_profile_languages' in self.config_widgets:
            languages_text = self.config_widgets['model_profile_languages'].text().strip()
            if languages_text:
                # 解析逗号分隔的语言列表
                languages = [lang.strip() for lang in languages_text.split(',') if lang.strip()]
                profile.supported_languages = languages if languages else None
            else:
                profile.supported_languages = None

        # 更新时间戳
        from datetime import datetime
        profile.updated_at = datetime.now()

        # 保存到配置
        self.config.model_profiles[self.current_editing_model_profile_id] = profile

        # 同步更新 model_path（向后兼容）
        if self.current_editing_model_profile_id == self.config.active_model_profile_id:
            self.config.model_path = profile.model_path

        # 如果方案名称发生变化,刷新模型方案列表（同步到UI）
        if 'model_profile_name' in self.config_widgets:
            current_item = self.model_profile_list.currentItem()
            if current_item and current_item.data(Qt.UserRole) == self.current_editing_model_profile_id:
                # 只更新列表项文本,不触发selection change事件
                current_item.setText(profile.profile_name)
                logger.debug(f"Updated model profile list item: {profile.profile_name}")

        logger.debug(f"Collected model profile settings: {self.current_editing_model_profile_id}")

    def _collect_vad_settings(self) -> None:
        """收集VAD设置 - 保存当前编辑的方案参数"""
        if self.current_editing_profile_id is None:
            return

        # 从UI控件收集参数
        profile = self.config.vad_profiles.get(self.current_editing_profile_id)
        if profile is None:
            return

        # 更新方案名称 - 添加重复校验
        if 'vad_profile_name' in self.config_widgets:
            new_profile_name = self.config_widgets['vad_profile_name'].text().strip()

            # 检查方案名是否发生变化
            if new_profile_name != profile.profile_name:
                # 检查新名称是否与其他方案重复
                for pid, existing_profile in self.config.vad_profiles.items():
                    if pid != self.current_editing_profile_id and existing_profile.profile_name == new_profile_name:
                        QMessageBox.warning(
                            self,
                            "名称重复",
                            f"方案名称'{new_profile_name}'已存在,请使用其他名称"
                        )
                        # 恢复原名称到UI
                        self.config_widgets['vad_profile_name'].setText(profile.profile_name)
                        return

            profile.profile_name = new_profile_name
        if 'vad_profile_threshold' in self.config_widgets:
            profile.threshold = self.config_widgets['vad_profile_threshold'].value()
        if 'vad_profile_min_speech_duration_ms' in self.config_widgets:
            profile.min_speech_duration_ms = float(self.config_widgets['vad_profile_min_speech_duration_ms'].value())
        if 'vad_profile_min_silence_duration_ms' in self.config_widgets:
            profile.min_silence_duration_ms = float(self.config_widgets['vad_profile_min_silence_duration_ms'].value())
        if 'vad_profile_max_speech_duration_ms' in self.config_widgets:
            profile.max_speech_duration_ms = float(self.config_widgets['vad_profile_max_speech_duration_ms'].value())
        if 'vad_profile_sample_rate' in self.config_widgets:
            profile.sample_rate = int(self.config_widgets['vad_profile_sample_rate'].currentText())
        if 'vad_profile_window_size_samples' in self.config_widgets:
            profile.window_size_samples = self.config_widgets['vad_profile_window_size_samples'].value()
        if 'vad_profile_model' in self.config_widgets:
            profile.model = self.config_widgets['vad_profile_model'].currentText()
        if 'vad_profile_model_path' in self.config_widgets:
            profile.model_path = self.config_widgets['vad_profile_model_path'].text().strip() or None
        if 'vad_profile_use_sherpa_onnx' in self.config_widgets:
            profile.use_sherpa_onnx = self.config_widgets['vad_profile_use_sherpa_onnx'].isChecked()

        # 更新配置中的方案
        self.config.vad_profiles[self.current_editing_profile_id] = profile

        # 如果方案名称发生变化,刷新VAD方案列表（同步到UI）
        if 'vad_profile_name' in self.config_widgets:
            current_item = self.vad_profile_list.currentItem()
            if current_item and current_item.data(Qt.UserRole) == self.current_editing_profile_id:
                # 只更新列表项文本,不触发selection change事件
                current_item.setText(profile.profile_name)
                logger.debug(f"Updated VAD profile list item: {profile.profile_name}")

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
            self.config.use_gpu = self.config_widgets['use_gpu'].isChecked()

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
        

        QMessageBox.information(self, "验证成功", f"模型文件验证通过\n文件大小: {file_size_mb:.1f} MB")

    # ========== VAD方案管理槽函数 ==========

    @Slot()
    def _on_vad_profile_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """处理VAD方案选择事件

        Args:
            current: 当前选中的列表项
            previous: 之前选中的列表项
        """
        if current is None:
            self.current_editing_profile_id = None
            return

        # 获取选中方案的ID
        profile_id = current.data(Qt.UserRole)
        self.current_editing_profile_id = profile_id

        # 加载方案参数到UI
        profile = self.config.vad_profiles.get(profile_id)
        if profile is None:
            logger.warning(f"VAD profile not found: {profile_id}")
            return

        # 设置UI控件的值
        if 'vad_profile_name' in self.config_widgets:
            self.config_widgets['vad_profile_name'].setText(profile.profile_name)
        if 'vad_profile_threshold' in self.config_widgets:
            self.config_widgets['vad_profile_threshold'].setValue(profile.threshold)
        if 'vad_profile_min_speech_duration_ms' in self.config_widgets:
            self.config_widgets['vad_profile_min_speech_duration_ms'].setValue(int(profile.min_speech_duration_ms))
        if 'vad_profile_min_silence_duration_ms' in self.config_widgets:
            self.config_widgets['vad_profile_min_silence_duration_ms'].setValue(int(profile.min_silence_duration_ms))
        if 'vad_profile_max_speech_duration_ms' in self.config_widgets:
            self.config_widgets['vad_profile_max_speech_duration_ms'].setValue(int(profile.max_speech_duration_ms))
        if 'vad_profile_sample_rate' in self.config_widgets:
            self.config_widgets['vad_profile_sample_rate'].setCurrentText(str(profile.sample_rate))
        if 'vad_profile_window_size_samples' in self.config_widgets:
            self.config_widgets['vad_profile_window_size_samples'].setValue(profile.window_size_samples)
        if 'vad_profile_model' in self.config_widgets:
            self.config_widgets['vad_profile_model'].setCurrentText(profile.model)
        if 'vad_profile_model_path' in self.config_widgets:
            self.config_widgets['vad_profile_model_path'].setText(profile.model_path or "")
        if 'vad_profile_use_sherpa_onnx' in self.config_widgets:
            self.config_widgets['vad_profile_use_sherpa_onnx'].setChecked(profile.use_sherpa_onnx)

        logger.debug(f"Loaded VAD profile: {profile.profile_name} ({profile_id})")

    @Slot()
    def _on_add_vad_profile(self) -> None:
        """新增VAD方案"""
        from PySide6.QtWidgets import QInputDialog

        # 弹出对话框输入方案名
        profile_name, ok = QInputDialog.getText(
            self,
            "新增VAD方案",
            "请输入方案名称:",
            text="新方案"
        )

        if not ok or not profile_name.strip():
            return

        profile_name = profile_name.strip()

        # 检查名称是否重复
        for profile in self.config.vad_profiles.values():
            if profile.profile_name == profile_name:
                QMessageBox.warning(self, "名称重复", f"方案名称'{profile_name}'已存在,请使用其他名称")
                return

        # 创建新方案(使用ConfigBridge)
        from src.config.models import VadProfile

        new_profile = VadProfile.create_default_profile()
        new_profile.profile_name = profile_name
        new_profile.profile_id = f"profile_{profile_name}"

        # 添加到配置
        success = self.config_bridge.add_vad_profile(new_profile)
        if not success:
            QMessageBox.warning(self, "添加失败", "无法添加VAD方案,请检查日志")
            return

        # 刷新列表
        self._load_vad_settings()

        # 选中新添加的方案
        for i in range(self.vad_profile_list.count()):
            item = self.vad_profile_list.item(i)
            if item.data(Qt.UserRole) == new_profile.profile_id:
                self.vad_profile_list.setCurrentItem(item)
                break

        logger.info(f"Added new VAD profile: {profile_name} ({new_profile.profile_id})")

    @Slot()
    def _on_delete_vad_profile(self) -> None:
        """删除VAD方案"""
        current_item = self.vad_profile_list.currentItem()
        if current_item is None:
            return

        profile_id = current_item.data(Qt.UserRole)
        profile = self.config.vad_profiles.get(profile_id)
        if profile is None:
            return

        # 保护"默认"方案
        if profile_id == "default":
            QMessageBox.warning(self, "无法删除", "默认方案不能被删除")
            return

        # 至少保留一个方案
        if len(self.config.vad_profiles) <= 1:
            QMessageBox.warning(self, "无法删除", "必须至少保留一个VAD方案")
            return

        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除方案'{profile.profile_name}'吗?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 删除方案(使用ConfigBridge)
        success = self.config_bridge.delete_vad_profile(profile_id)
        if not success:
            QMessageBox.warning(self, "删除失败", "无法删除VAD方案,请检查日志")
            return

        # 刷新列表
        self._load_vad_settings()

        logger.info(f"Deleted VAD profile: {profile.profile_name} ({profile_id})")

    @Slot()
    def _on_duplicate_vad_profile(self) -> None:
        """复制VAD方案"""
        from PySide6.QtWidgets import QInputDialog

        current_item = self.vad_profile_list.currentItem()
        if current_item is None:
            return

        source_profile_id = current_item.data(Qt.UserRole)
        source_profile = self.config.vad_profiles.get(source_profile_id)
        if source_profile is None:
            return

        # 弹出对话框输入新方案名
        new_profile_name, ok = QInputDialog.getText(
            self,
            "复制VAD方案",
            "请输入新方案名称:",
            text=f"{source_profile.profile_name} 副本"
        )

        if not ok or not new_profile_name.strip():
            return

        new_profile_name = new_profile_name.strip()

        # 检查名称是否重复
        for profile in self.config.vad_profiles.values():
            if profile.profile_name == new_profile_name:
                QMessageBox.warning(self, "名称重复", f"方案名称'{new_profile_name}'已存在,请使用其他名称")
                return

        # 复制方案(使用ConfigBridge)
        success, new_profile_id, message = self.config_bridge.duplicate_vad_profile(
            source_profile_id,
            new_profile_name
        )

        if not success:
            QMessageBox.warning(self, "复制失败", message)
            return

        # 刷新列表
        self._load_vad_settings()

        # 选中新复制的方案
        for i in range(self.vad_profile_list.count()):
            item = self.vad_profile_list.item(i)
            if item.data(Qt.UserRole) == new_profile_id:
                self.vad_profile_list.setCurrentItem(item)
                break

        logger.info(f"Duplicated VAD profile: {source_profile.profile_name} -> {new_profile_name} ({new_profile_id})")

    # ==================== 模型方案管理事件处理 ====================

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_model_profile_selected(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """处理模型方案选择事件

        Args:
            current: 当前选中的列表项
            previous: 之前选中的列表项
        """
        if current is None:
            self.current_editing_model_profile_id = None
            return

        # 获取选中方案的ID
        profile_id = current.data(Qt.UserRole)
        self.current_editing_model_profile_id = profile_id

        # 加载方案参数到UI
        profile = self.config.model_profiles.get(profile_id)
        if profile is None:
            logger.warning(f"Model profile not found: {profile_id}")
            return

        # 设置UI控件的值
        if 'model_profile_name' in self.config_widgets:
            self.config_widgets['model_profile_name'].setText(profile.profile_name)
        if 'model_profile_path' in self.config_widgets:
            self.config_widgets['model_profile_path'].setText(profile.model_path)
        if 'model_profile_description' in self.config_widgets:
            self.config_widgets['model_profile_description'].setText(profile.description or "")
        if 'model_profile_languages' in self.config_widgets:
            # 将语言列表转换为逗号分隔的字符串
            languages_str = ",".join(profile.supported_languages) if profile.supported_languages else ""
            self.config_widgets['model_profile_languages'].setText(languages_str)

        logger.debug(f"Model profile selected: {profile_id}")

    @Slot()
    def _on_add_model_profile(self) -> None:
        """新增模型方案"""
        from PySide6.QtWidgets import QInputDialog

        # 弹出对话框输入方案名
        profile_name, ok = QInputDialog.getText(
            self,
            "新增模型方案",
            "请输入方案名称:",
            text="新模型"
        )

        if not ok or not profile_name.strip():
            return

        profile_name = profile_name.strip()

        # 检查名称是否重复
        for profile in self.config.model_profiles.values():
            if profile.profile_name == profile_name:
                QMessageBox.warning(self, "名称重复", f"方案名称'{profile_name}'已存在,请使用其他名称")
                return

        # 弹出文件选择对话框选择模型文件
        model_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择模型文件",
            "",
            "ONNX模型 (*.onnx);;二进制模型 (*.bin);;所有文件 (*.*)"
        )

        if not model_path:
            return

        # 验证模型文件
        from src.config.models import ModelProfile
        try:
            # 创建临时profile进行验证
            temp_profile = ModelProfile(
                profile_name=profile_name,
                model_path=model_path
            )
            temp_profile.validate()
        except Exception as e:
            QMessageBox.warning(
                self,
                "模型验证失败",
                f"无法添加模型方案:\n{str(e)}"
            )
            return

        # 创建新方案(使用ConfigBridge)
        import uuid
        new_profile = ModelProfile(
            profile_id=f"model_{uuid.uuid4().hex[:8]}",
            profile_name=profile_name,
            model_path=model_path,
            description="",
            supported_languages=None
        )

        # 添加到配置
        success = self.config_bridge.add_model_profile(new_profile)
        if not success:
            QMessageBox.warning(self, "添加失败", "无法添加模型方案,请检查日志")
            return

        # 重新加载配置
        self.config = self.config_bridge.get_config()

        # 刷新列表
        self._load_model_settings()

        # 选中新添加的方案
        for i in range(self.model_profile_list.count()):
            item = self.model_profile_list.item(i)
            if item.data(Qt.UserRole) == new_profile.profile_id:
                self.model_profile_list.setCurrentItem(item)
                break

        logger.info(f"Added new model profile: {new_profile.profile_id}")

    @Slot()
    def _on_delete_model_profile(self) -> None:
        """删除模型方案"""
        current_item = self.model_profile_list.currentItem()
        if current_item is None:
            return

        profile_id = current_item.data(Qt.UserRole)
        profile = self.config.model_profiles.get(profile_id)
        if profile is None:
            return

        # 保护"默认"方案
        if profile_id == "default":
            QMessageBox.warning(self, "无法删除", "默认方案不能被删除")
            return

        # 至少保留一个方案
        if len(self.config.model_profiles) <= 1:
            QMessageBox.warning(self, "无法删除", "必须至少保留一个模型方案")
            return

        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除方案'{profile.profile_name}'吗?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 删除方案(使用ConfigBridge)
        success = self.config_bridge.delete_model_profile(profile_id)
        if not success:
            QMessageBox.warning(self, "删除失败", "无法删除模型方案,请检查日志")
            return

        # 重新加载配置
        self.config = self.config_bridge.get_config()

        # 刷新列表
        self._load_model_settings()

        logger.info(f"Deleted model profile: {profile_id}")

    @Slot()
    def _on_duplicate_model_profile(self) -> None:
        """复制模型方案"""
        from PySide6.QtWidgets import QInputDialog

        current_item = self.model_profile_list.currentItem()
        if current_item is None:
            return

        profile_id = current_item.data(Qt.UserRole)
        source_profile = self.config.model_profiles.get(profile_id)
        if source_profile is None:
            return

        # 弹出对话框输入新方案名称
        new_name, ok = QInputDialog.getText(
            self,
            "复制模型方案",
            "请输入新方案名称:",
            text=f"{source_profile.profile_name} - 副本"
        )

        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()

        # 检查名称是否重复
        for profile in self.config.model_profiles.values():
            if profile.profile_name == new_name:
                QMessageBox.warning(self, "名称重复", f"方案名称'{new_name}'已存在,请使用其他名称")
                return

        # 创建方案副本
        from src.config.models import ModelProfile
        import uuid
        from datetime import datetime

        new_profile = ModelProfile(
            profile_id=f"model_{uuid.uuid4().hex[:8]}",
            profile_name=new_name,
            model_path=source_profile.model_path,
            description=source_profile.description,
            supported_languages=source_profile.supported_languages.copy() if source_profile.supported_languages else None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # 添加到配置
        success = self.config_bridge.add_model_profile(new_profile)
        if not success:
            QMessageBox.warning(self, "复制失败", "无法复制模型方案,请检查日志")
            return

        # 重新加载配置
        self.config = self.config_bridge.get_config()

        # 刷新列表
        self._load_model_settings()

        # 选中新方案
        for i in range(self.model_profile_list.count()):
            item = self.model_profile_list.item(i)
            if item.data(Qt.UserRole) == new_profile.profile_id:
                self.model_profile_list.setCurrentItem(item)
                break

        logger.info(f"Duplicated model profile {profile_id} to {new_profile.profile_id}")

    @Slot()
    def _on_validate_model_file(self) -> None:
        """验证模型文件"""
        if 'model_profile_path' not in self.config_widgets:
            return

        model_path = self.config_widgets['model_profile_path'].text().strip()

        if not model_path:
            QMessageBox.warning(self, "验证失败", "请先输入模型文件路径")
            return

        # 验证模型文件
        from pathlib import Path
        import os

        try:
            path = Path(model_path)

            # 检查文件存在
            if not path.exists():
                QMessageBox.warning(self, "验证失败", f"文件不存在:\n{model_path}")
                return

            # 检查是文件而非目录
            if not path.is_file():
                QMessageBox.warning(self, "验证失败", f"路径不是文件:\n{model_path}")
                return

            # 检查文件扩展名
            from src.config.models import ModelConstants
            if path.suffix.lower() not in ModelConstants.SUPPORTED_EXTENSIONS:
                QMessageBox.warning(
                    self,
                    "验证失败",
                    f"不支持的文件格式: {path.suffix}\n"
                    f"支持的格式: {', '.join(ModelConstants.SUPPORTED_EXTENSIONS)}"
                )
                return

            # 检查文件大小
            file_size_mb = path.stat().st_size / (1024 * 1024)
            if file_size_mb < 1:
                QMessageBox.warning(
                    self,
                    "验证失败",
                    f"文件过小 ({file_size_mb:.2f}MB)\n"
                    f"可能不是有效的模型文件"
                )
                return

            # 检查文件权限
            if not os.access(path, os.R_OK):
                QMessageBox.warning(self, "验证失败", f"没有读取权限:\n{model_path}")
                return

            # 验证通过
            QMessageBox.information(
                self,
                "验证成功",
                f"模型文件验证通过!\n\n"
                f"路径: {model_path}\n"
                f"格式: {path.suffix}\n"
                f"大小: {file_size_mb:.2f}MB"
            )

            logger.info(f"Model file validated: {model_path}")

        except Exception as e:
            QMessageBox.critical(
                self,
                "验证错误",
                f"验证过程中发生错误:\n{str(e)}"
            )
            logger.error(f"Model validation error: {e}", exc_info=True)