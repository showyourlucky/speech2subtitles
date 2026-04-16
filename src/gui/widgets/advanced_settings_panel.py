"""高级设置面板组件 (v2.0新增)
可折叠的高级设置面板,包含VAD方案、模型选择等
"""

import logging
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QPushButton,
    QCheckBox,
)
from PySide6.QtCore import Signal, Slot

logger = logging.getLogger(__name__)


class AdvancedSettingsPanel(QGroupBox):
    """高级设置面板 (v2.0)

    核心功能:
        - VAD方案选择
        - 转录模型选择
        - GPU状态显示
        - 采样率信息显示
        - 可折叠/展开

    设计特点:
        - 使用QGroupBox的checkable属性实现折叠
        - 默认收起状态
        - 点击标题栏切换展开/收起

    信号:
        vad_changed: VAD方案发生变化 (str: profile_id)
        model_changed: 模型方案发生变化 (str: profile_id)
        vad_settings_clicked: VAD设置按钮被点击
    """

    # 信号定义
    vad_changed = Signal(str)
    model_changed = Signal(str)  # 发射 profile_id 而不是 model_path
    vad_settings_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        """初始化高级设置面板

        Args:
            parent: 父组件
        """
        super().__init__("⚙️ 高级设置", parent)

        # 设置可折叠
        self.setCheckable(True)
        self.setChecked(False)  # 默认收起

        # UI组件
        self.vad_combo: Optional[QComboBox] = None
        self.vad_manage_button: Optional[QPushButton] = None
        self.model_combo: Optional[QComboBox] = None
        self.model_browse_button: Optional[QPushButton] = None
        self.gpu_checkbox: Optional[QCheckBox] = None
        self.gpu_info_label: Optional[QLabel] = None
        self.sample_rate_label: Optional[QLabel] = None

        # 内容容器
        self.content_widget: Optional[QWidget] = None

        # VAD方案映射: profile_name -> profile_id
        self.vad_profile_mapping: dict = {}

        # 初始化UI
        self._setup_ui()

        # 连接折叠/展开信号
        self.toggled.connect(self._on_toggled)

        logger.debug("AdvancedSettingsPanel initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 内容容器
        self.content_widget = QWidget()
        content_layout = QGridLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        row = 0

        # VAD方案
        content_layout.addWidget(QLabel("VAD方案:"), row, 0)
        self.vad_combo = QComboBox()
        self.vad_combo.setMinimumWidth(200)
        self.vad_combo.addItems(["默认", "高灵敏度", "低灵敏度"])
        self.vad_combo.currentIndexChanged.connect(self._on_vad_changed)
        content_layout.addWidget(self.vad_combo, row, 1)

        self.vad_manage_button = QPushButton("管理方案...")
        self.vad_manage_button.setFixedWidth(100)
        self.vad_manage_button.clicked.connect(self._on_vad_manage_clicked)
        content_layout.addWidget(self.vad_manage_button, row, 2)

        row += 1

        # 转录模型
        content_layout.addWidget(QLabel("转录模型:"), row, 0)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        self.model_combo.addItem("sense-voice-zh-en-ja-ko-yue", "")
        self.model_combo.setToolTip("选择转录模型")
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        content_layout.addWidget(self.model_combo, row, 1)


        row += 1

        # GPU加速
        content_layout.addWidget(QLabel("GPU加速:"), row, 0)
        gpu_layout = QHBoxLayout()
        self.gpu_checkbox = QCheckBox("启用")
        self.gpu_checkbox.setEnabled(False)  # 只读显示
        gpu_layout.addWidget(self.gpu_checkbox)

        self.gpu_info_label = QLabel("未检测到")
        self.gpu_info_label.setStyleSheet("color: #666;")
        gpu_layout.addWidget(self.gpu_info_label)
        gpu_layout.addStretch()

        content_layout.addLayout(gpu_layout, row, 1, 1, 2)

        row += 1

        # 采样率
        content_layout.addWidget(QLabel("采样率:"), row, 0)
        self.sample_rate_label = QLabel("16000 Hz")
        self.sample_rate_label.setStyleSheet("color: #666;")
        content_layout.addWidget(self.sample_rate_label, row, 1)

        # 设置列拉伸
        content_layout.setColumnStretch(1, 1)

        main_layout.addWidget(self.content_widget)

        # 默认隐藏内容
        self.content_widget.setVisible(False)

    @Slot(bool)
    def _on_toggled(self, checked: bool) -> None:
        """处理展开/收起切换

        Args:
            checked: 是否展开
        """
        self.content_widget.setVisible(checked)
        logger.debug(f"AdvancedSettingsPanel {'expanded' if checked else 'collapsed'}")

    @Slot(int)
    def _on_vad_changed(self, index: int) -> None:
        """处理VAD方案变化

        Args:
            index: 选择的索引
        """
        profile_name = self.vad_combo.itemText(index)
        # 从映射中获取 profile_id
        profile_id = self.vad_profile_mapping.get(profile_name, profile_name)
        self.vad_changed.emit(profile_id)
        logger.debug(f"VAD profile changed: {profile_name} -> {profile_id}")

    @Slot()
    def _on_vad_manage_clicked(self) -> None:
        """处理VAD管理按钮点击"""
        self.vad_settings_clicked.emit()
        logger.debug("VAD settings button clicked")

    @Slot(int)
    def _on_model_changed(self, index: int) -> None:
        """处理模型方案变化

        Args:
            index: 选择的索引
        """
        profile_id = self.model_combo.itemData(index)
        if profile_id:
            self.model_changed.emit(profile_id)
            logger.debug(f"Model profile changed to: {profile_id}")


    # ========== 公共接口 ==========

    def update_vad_profiles(self, profiles: dict, current_profile_id: str = None) -> None:
        """更新VAD方案列表

        Args:
            profiles: VAD方案字典 {profile_id: VadProfile对象}
            current_profile_id: 当前选中的方案ID
        """
        self.vad_combo.clear()
        self.vad_profile_mapping.clear()

        # 构建映射并添加到下拉框
        for profile_id, profile in profiles.items():
            profile_name = profile.profile_name
            self.vad_profile_mapping[profile_name] = profile_id
            self.vad_combo.addItem(profile_name)

        # 选中当前活跃方案
        if current_profile_id and current_profile_id in profiles:
            current_profile_name = profiles[current_profile_id].profile_name
            self.vad_combo.setCurrentText(current_profile_name)

        logger.debug(f"VAD profiles updated, count: {len(profiles)}, current: {current_profile_id}")

    def update_model_profiles(self, profiles: dict, current_profile_id: str = None) -> None:
        """更新模型方案列表

        Args:
            profiles: 模型方案字典 {profile_id: ModelProfile}
            current_profile_id: 当前选中的方案ID
        """
        # 阻塞信号，避免初始化/更新时触发 model_changed 导致弹框
        self.model_combo.blockSignals(True)
        try:
            self.model_combo.clear()

            # 添加所有模型方案
            for profile_id, profile in profiles.items():
                self.model_combo.addItem(profile.profile_name, profile_id)

            # 选中当前活跃方案
            if current_profile_id:
                for i in range(self.model_combo.count()):
                    if self.model_combo.itemData(i) == current_profile_id:
                        self.model_combo.setCurrentIndex(i)
                        break
        finally:
            self.model_combo.blockSignals(False)

        logger.debug(f"Model profiles updated, count: {len(profiles)}, current: {current_profile_id}")

    def update_model(self, model_name: str, model_path: str = "") -> None:
        """更新模型显示 (已弃用，保留用于向后兼容)

        Args:
            model_name: 模型名称
            model_path: 模型路径
        """
        # 查找是否已存在
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == model_path:
                self.model_combo.setCurrentIndex(i)
                return

        # 不存在则添加
        self.model_combo.addItem(model_name, model_path)
        self.model_combo.setCurrentIndex(self.model_combo.count() - 1)

    def update_gpu_status(self, enabled: bool, info: str = "") -> None:
        """更新GPU状态

        Args:
            enabled: 是否启用GPU
            info: GPU信息（如"CUDA"/"未检测到"）
        """
        self.gpu_checkbox.setChecked(enabled)
        self.gpu_info_label.setText(info if info else ("已启用" if enabled else "未检测到"))

        if enabled:
            self.gpu_info_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.gpu_info_label.setStyleSheet("color: #666;")

    def update_sample_rate(self, sample_rate: int) -> None:
        """更新采样率显示

        Args:
            sample_rate: 采样率（Hz）
        """
        self.sample_rate_label.setText(f"{sample_rate} Hz")

    def set_expanded(self, expanded: bool) -> None:
        """设置展开/收起状态

        Args:
            expanded: 是否展开
        """
        self.setChecked(expanded)

    def is_expanded(self) -> bool:
        """检查是否展开

        Returns:
            bool: 是否展开
        """
        return self.isChecked()
