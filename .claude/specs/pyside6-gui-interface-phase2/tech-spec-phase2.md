# Phase 2 技术规格 - 配置管理和数据管理

**版本**: 1.0
**状态**: 实施就绪 ✅
**创建日期**: 2025-11-06
**目标阶段**: Phase 2 - 系统设置 + 配置持久化 + 历史记录 + 导出

---

## 📋 1. 概述

### 1.1 Phase 2 目标

基于 Phase 1 (v0.1.1) 的成功实施，Phase 2 聚焦于**配置管理**和**数据管理**功能，提升用户体验和数据管理能力。

**核心功能**:
1. ✅ **配置持久化**: JSON文件存储，启动自动加载
2. ✅ **系统设置对话框**: 图形化配置所有参数
3. ✅ **转录历史记录**: SQLite数据库，搜索和管理
4. ✅ **导出功能**: 多格式导出（TXT/SRT/JSON/VTT）

### 1.2 技术原则

遵循 Phase 1 的技术原则:
- **KISS**: 保持简单，避免过度工程
- **YAGNI**: 只实现明确需要的功能
- **DRY**: 复用现有代码，避免重复

### 1.3 文件结构

```
src/gui/
├── dialogs/                    # 新增：对话框组件
│   ├── __init__.py
│   ├── settings_dialog.py      # 系统设置对话框
│   ├── export_dialog.py        # 导出对话框
│   └── history_detail_dialog.py # 历史详情对话框
├── widgets/
│   └── history_panel.py        # 新增：历史记录面板
├── storage/                    # 新增：数据存储层
│   ├── __init__.py
│   ├── config_file_manager.py  # 配置文件管理
│   ├── history_manager.py      # 历史记录管理
│   └── exporters.py            # 导出器
└── models/
    └── history_models.py       # 新增：历史记录数据模型
```

---

## 🗄️ 2. 配置持久化 (ConfigFileManager)

### 2.1 功能概述

**职责**: 管理配置文件的读写，支持配置的持久化存储和版本迁移。

**配置文件路径**:
- Windows: `C:\Users\<username>\.speech2subtitles\config.json`
- Linux/macOS: `~/.speech2subtitles/config.json`

### 2.2 类设计

```python
# 文件: src/gui/storage/config_file_manager.py

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from src.config.models import Config

logger = logging.getLogger(__name__)


class ConfigFileManager:
    """配置文件管理器

    负责配置的持久化存储、加载、验证和版本迁移

    配置文件位置:
        - Windows: %USERPROFILE%\.speech2subtitles\config.json
        - Linux/macOS: ~/.speech2subtitles/config.json

    配置文件格式:
        {
            "version": "1.0",
            "last_modified": "2025-11-06T10:30:00",
            "config": {
                "model_path": "...",
                "use_gpu": true,
                ...
            }
        }
    """

    CONFIG_VERSION = "1.0"

    def __init__(self):
        """初始化配置文件管理器"""
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "config.json"

        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Config file path: {self.config_file}")

    def _get_config_dir(self) -> Path:
        """获取配置目录路径

        Returns:
            Path: 配置目录路径
        """
        import os
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('USERPROFILE', '.'))
        else:  # Linux/macOS
            base_dir = Path.home()

        return base_dir / '.speech2subtitles'

    def save_config(self, config: Config) -> Tuple[bool, str]:
        """保存配置到文件

        Args:
            config: Config对象

        Returns:
            Tuple[bool, str]: (是否成功, 错误消息)
        """
        try:
            # 验证配置
            config.validate()

            # 转换为字典
            from dataclasses import asdict
            config_dict = asdict(config)

            # 构建完整配置结构
            full_config = {
                "version": self.CONFIG_VERSION,
                "last_modified": datetime.now().isoformat(),
                "config": config_dict
            }

            # 写入文件（使用临时文件确保原子性）
            temp_file = self.config_file.with_suffix('.json.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(full_config, f, indent=2, ensure_ascii=False)

            # 原子性重命名
            temp_file.replace(self.config_file)

            logger.info("Configuration saved successfully")
            return True, ""

        except ValueError as e:
            logger.error(f"Config validation failed: {e}")
            return False, f"配置验证失败: {e}"
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False, f"保存配置失败: {e}"

    def load_config(self) -> Optional[Config]:
        """从文件加载配置

        Returns:
            Optional[Config]: 配置对象，加载失败返回None
        """
        if not self.config_file.exists():
            logger.info("Config file not found, will use defaults")
            return None

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                full_config = json.load(f)

            # 检查版本
            version = full_config.get("version", "0.0")
            if version != self.CONFIG_VERSION:
                logger.warning(f"Config version mismatch: {version} != {self.CONFIG_VERSION}")
                # 执行版本迁移
                full_config = self._migrate_config(full_config, version)

            # 提取配置数据
            config_data = full_config.get("config", {})

            # 重建Config对象
            config = Config(**config_data)

            logger.info("Configuration loaded successfully")
            return config

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return None

    def _migrate_config(self, old_config: Dict[str, Any], old_version: str) -> Dict[str, Any]:
        """配置版本迁移

        Args:
            old_config: 旧配置字典
            old_version: 旧版本号

        Returns:
            Dict[str, Any]: 迁移后的配置
        """
        logger.info(f"Migrating config from version {old_version} to {self.CONFIG_VERSION}")

        # 当前只有一个版本，未来添加迁移逻辑
        # 例如: if old_version == "0.9": ... migrate to 1.0

        # 更新版本号
        old_config["version"] = self.CONFIG_VERSION
        old_config["last_modified"] = datetime.now().isoformat()

        return old_config

    def config_exists(self) -> bool:
        """检查配置文件是否存在

        Returns:
            bool: 配置文件是否存在
        """
        return self.config_file.exists()

    def delete_config(self) -> bool:
        """删除配置文件

        Returns:
            bool: 是否成功删除
        """
        try:
            if self.config_file.exists():
                self.config_file.unlink()
                logger.info("Config file deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete config: {e}")
            return False

    def export_config(self, export_path: str, config: Config) -> Tuple[bool, str]:
        """导出配置到指定路径

        Args:
            export_path: 导出文件路径
            config: Config对象

        Returns:
            Tuple[bool, str]: (是否成功, 错误消息)
        """
        try:
            from dataclasses import asdict
            config_dict = asdict(config)

            full_config = {
                "version": self.CONFIG_VERSION,
                "exported_at": datetime.now().isoformat(),
                "config": config_dict
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(full_config, f, indent=2, ensure_ascii=False)

            logger.info(f"Config exported to: {export_path}")
            return True, ""

        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return False, f"导出失败: {e}"

    def import_config(self, import_path: str) -> Tuple[Optional[Config], str]:
        """从指定路径导入配置

        Args:
            import_path: 导入文件路径

        Returns:
            Tuple[Optional[Config], str]: (配置对象, 错误消息)
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                full_config = json.load(f)

            config_data = full_config.get("config", {})
            config = Config(**config_data)

            logger.info(f"Config imported from: {import_path}")
            return config, ""

        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            return None, f"导入失败: {e}"
```

### 2.3 扩展 ConfigBridge

```python
# 文件: src/gui/bridges/config_bridge.py (修改)

# 添加以下方法到 ConfigBridge 类

from src.gui.storage.config_file_manager import ConfigFileManager

class ConfigBridge:
    """配置桥接器 (扩展版本)"""

    def __init__(self):
        """初始化配置桥接器"""
        self.config_manager = ConfigManager()
        self.file_manager = ConfigFileManager()  # 新增
        self._current_config: Optional[Config] = None
        logger.info("ConfigBridge initialized")

    def load_config(self, config_file: Optional[str] = None) -> Config:
        """加载配置

        Args:
            config_file: 配置文件路径（可选，用于导入）

        Returns:
            Config: 配置对象
        """
        if config_file:
            # 从指定文件导入
            config, error = self.file_manager.import_config(config_file)
            if config:
                self._current_config = config
                return config
            logger.warning(f"Failed to import config: {error}")

        # 尝试从默认位置加载
        config = self.file_manager.load_config()
        if config:
            self._current_config = config
            logger.info("Config loaded from file")
            return config

        # 使用默认配置
        self._current_config = self.config_manager.get_default_config()
        logger.info("Using default configuration")
        return self._current_config

    def save_config(self, config: Config, config_file: Optional[str] = None) -> bool:
        """保存配置

        Args:
            config: 要保存的配置对象
            config_file: 配置文件路径（可选，用于导出）

        Returns:
            bool: 保存是否成功
        """
        try:
            # 验证配置
            config.validate()
            self._current_config = config

            if config_file:
                # 导出到指定文件
                success, error = self.file_manager.export_config(config_file, config)
                if not success:
                    logger.error(f"Export failed: {error}")
                    return False
            else:
                # 保存到默认位置
                success, error = self.file_manager.save_config(config)
                if not success:
                    logger.error(f"Save failed: {error}")
                    return False

            logger.info("Configuration saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
```

---

## 🔧 3. 系统设置对话框 (SettingsDialog)

### 3.1 功能概述

**职责**: 提供图形化界面配置所有系统参数

**布局**: QDialog + 左侧导航(QListWidget) + 右侧页面(QStackedWidget)

**配置页面**:
1. 通用设置
2. 模型配置
3. VAD参数
4. 音频设置
5. GPU设置
6. 字幕显示

### 3.2 主对话框类设计

```python
# 文件: src/gui/dialogs/settings_dialog.py

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QStackedWidget, QPushButton, QMessageBox,
    QWidget, QListWidgetItem
)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QIcon

from src.config.models import Config
from src.gui.bridges.config_bridge import ConfigBridge

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """系统设置对话框

    提供图形化界面配置所有系统参数

    布局:
        - 左侧: 导航列表 (QListWidget)
        - 右侧: 配置页面 (QStackedWidget)
        - 底部: 按钮栏 (保存/取消/恢复默认/导入/导出)

    信号:
        settings_changed: 配置已更改 (Config)
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
        from PySide6.QtWidgets import QFileDialog

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
        from PySide6.QtWidgets import QFileDialog

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

    def _load_settings(self) -> None:
        """从Config对象加载设置到UI"""
        # 由各个页面实现具体加载逻辑
        # 这里调用各页面的load方法
        pass  # TODO: 实现加载逻辑

    def _collect_settings(self) -> None:
        """从UI收集设置到Config对象"""
        # 由各个页面实现具体收集逻辑
        # 这里调用各页面的collect方法
        pass  # TODO: 实现收集逻辑

    # ========== 配置页面创建方法 ==========
    # 注: 这里仅提供框架，具体实现见下一节

    def _create_general_page(self) -> QWidget:
        """创建通用设置页"""
        from PySide6.QtWidgets import QLabel, QFormLayout

        page = QWidget()
        layout = QFormLayout(page)

        layout.addRow(QLabel("通用设置页面"))
        layout.addRow(QLabel("TODO: 添加语言选择、日志级别等"))

        return page

    def _create_model_page(self) -> QWidget:
        """创建模型配置页"""
        from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QFormLayout, QFileDialog

        page = QWidget()
        layout = QFormLayout(page)

        # 模型路径
        model_path_edit = QLineEdit()
        model_path_edit.setText(self.config.model_path or "")
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
                self.config.model_path = file_path

        browse_button.clicked.connect(browse_model)

        model_layout = QHBoxLayout()
        model_layout.addWidget(model_path_edit)
        model_layout.addWidget(browse_button)

        layout.addRow("模型路径:", model_layout)

        return page

    def _create_vad_page(self) -> QWidget:
        """创建VAD参数页"""
        from PySide6.QtWidgets import QLabel, QSlider, QDoubleSpinBox, QFormLayout

        page = QWidget()
        layout = QFormLayout(page)

        # VAD敏感度滑块
        sensitivity_slider = QSlider(Qt.Horizontal)
        sensitivity_slider.setRange(0, 100)
        sensitivity_slider.setValue(50)
        layout.addRow("敏感度:", sensitivity_slider)

        layout.addRow(QLabel("TODO: 添加其他VAD参数"))

        return page

    def _create_audio_page(self) -> QWidget:
        """创建音频设置页"""
        from PySide6.QtWidgets import QLabel, QComboBox, QFormLayout

        page = QWidget()
        layout = QFormLayout(page)

        # 采样率选择
        sample_rate_combo = QComboBox()
        sample_rate_combo.addItems(["8000", "16000", "44100", "48000"])
        sample_rate_combo.setCurrentText(str(self.config.sample_rate))
        layout.addRow("采样率:", sample_rate_combo)

        layout.addRow(QLabel("TODO: 添加设备选择等"))

        return page

    def _create_gpu_page(self) -> QWidget:
        """创建GPU设置页"""
        from PySide6.QtWidgets import QLabel, QCheckBox, QFormLayout

        page = QWidget()
        layout = QFormLayout(page)

        # GPU启用复选框
        gpu_checkbox = QCheckBox("启用GPU加速")
        gpu_checkbox.setChecked(not self.config.no_gpu)
        layout.addRow(gpu_checkbox)

        layout.addRow(QLabel("TODO: 添加GPU设备选择"))

        return page

    def _create_subtitle_page(self) -> QWidget:
        """创建字幕显示页"""
        from PySide6.QtWidgets import QLabel, QFormLayout

        page = QWidget()
        layout = QFormLayout(page)

        layout.addRow(QLabel("字幕显示设置页面"))
        layout.addRow(QLabel("TODO: 添加字体、颜色、位置等"))

        return page
```

---

## 📊 4. 转录历史记录系统

### 4.1 数据模型

```python
# 文件: src/gui/models/history_models.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import json

from src.audio.models import AudioSourceType


@dataclass
class TranscriptionRecord:
    """转录记录数据模型

    对应数据库表: transcription_history
    """
    id: Optional[int] = None  # 数据库自增ID
    timestamp: datetime = None  # 转录时间
    audio_source: AudioSourceType = None  # 音频源类型
    audio_path: Optional[str] = None  # 文件路径（文件模式）
    duration: float = 0.0  # 转录时长（秒）
    text: str = ""  # 转录文本
    model_name: str = ""  # 使用的模型
    config_snapshot: str = ""  # 配置快照（JSON字符串）

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于数据库存储）

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'audio_source': self.audio_source.value if self.audio_source else None,
            'audio_path': self.audio_path,
            'duration': self.duration,
            'text': self.text,
            'model_name': self.model_name,
            'config_snapshot': self.config_snapshot
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TranscriptionRecord':
        """从字典反序列化

        Args:
            data: 字典数据

        Returns:
            TranscriptionRecord: 记录对象
        """
        # 解析时间戳
        timestamp = None
        if data.get('timestamp'):
            timestamp = datetime.fromisoformat(data['timestamp'])

        # 解析音频源类型
        audio_source = None
        if data.get('audio_source'):
            audio_source = AudioSourceType(data['audio_source'])

        return cls(
            id=data.get('id'),
            timestamp=timestamp,
            audio_source=audio_source,
            audio_path=data.get('audio_path'),
            duration=data.get('duration', 0.0),
            text=data.get('text', ''),
            model_name=data.get('model_name', ''),
            config_snapshot=data.get('config_snapshot', '')
        )
```

### 4.2 HistoryManager (数据库管理)

```python
# 文件: src/gui/storage/history_manager.py

import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from src.gui.models.history_models import TranscriptionRecord

logger = logging.getLogger(__name__)


class HistoryManager:
    """转录历史记录管理器

    使用 SQLite 数据库存储转录历史记录

    数据库位置:
        - Windows: %USERPROFILE%\.speech2subtitles\history.db
        - Linux/macOS: ~/.speech2subtitles/history.db

    表结构:
        transcription_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            audio_source TEXT NOT NULL,
            audio_path TEXT,
            duration REAL NOT NULL,
            text TEXT NOT NULL,
            model_name TEXT,
            config_snapshot TEXT
        )
    """

    def __init__(self):
        """初始化历史记录管理器"""
        self.db_path = self._get_db_path()
        self._init_database()
        logger.info(f"History database: {self.db_path}")

    def _get_db_path(self) -> Path:
        """获取数据库文件路径

        Returns:
            Path: 数据库文件路径
        """
        import os
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('USERPROFILE', '.'))
        else:  # Linux/macOS
            base_dir = Path.home()

        config_dir = base_dir / '.speech2subtitles'
        config_dir.mkdir(parents=True, exist_ok=True)

        return config_dir / 'history.db'

    def _init_database(self) -> None:
        """初始化数据库（创建表）"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 创建历史记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transcription_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    audio_source TEXT NOT NULL,
                    audio_path TEXT,
                    duration REAL NOT NULL,
                    text TEXT NOT NULL,
                    model_name TEXT,
                    config_snapshot TEXT
                )
            ''')

            # 创建索引（加速查询）
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON transcription_history(timestamp DESC)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_audio_source
                ON transcription_history(audio_source)
            ''')

            conn.commit()
            conn.close()

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def add_record(self, record: TranscriptionRecord) -> int:
        """添加转录记录

        Args:
            record: 转录记录对象

        Returns:
            int: 插入记录的ID
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO transcription_history
                (timestamp, audio_source, audio_path, duration, text, model_name, config_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.timestamp.isoformat() if record.timestamp else datetime.now().isoformat(),
                record.audio_source.value if record.audio_source else '',
                record.audio_path,
                record.duration,
                record.text,
                record.model_name,
                record.config_snapshot
            ))

            record_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"Record added: ID={record_id}")
            return record_id

        except Exception as e:
            logger.error(f"Failed to add record: {e}")
            raise

    def get_all_records(self, limit: int = 100, offset: int = 0) -> List[TranscriptionRecord]:
        """获取所有记录（时间倒序）

        Args:
            limit: 返回记录数量限制
            offset: 偏移量（分页）

        Returns:
            List[TranscriptionRecord]: 记录列表
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row  # 使用Row对象
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM transcription_history
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

            rows = cursor.fetchall()
            conn.close()

            records = [self._row_to_record(row) for row in rows]
            logger.debug(f"Retrieved {len(records)} records")
            return records

        except Exception as e:
            logger.error(f"Failed to get records: {e}")
            return []

    def search_records(self, query: str, limit: int = 100) -> List[TranscriptionRecord]:
        """搜索记录（全文搜索）

        Args:
            query: 搜索关键词
            limit: 返回记录数量限制

        Returns:
            List[TranscriptionRecord]: 匹配的记录列表
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 简单的LIKE搜索（未来可升级为FTS全文搜索）
            cursor.execute('''
                SELECT * FROM transcription_history
                WHERE text LIKE ? OR model_name LIKE ? OR audio_path LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', limit))

            rows = cursor.fetchall()
            conn.close()

            records = [self._row_to_record(row) for row in rows]
            logger.debug(f"Search found {len(records)} records")
            return records

        except Exception as e:
            logger.error(f"Failed to search records: {e}")
            return []

    def filter_by_source(self, audio_source: str, limit: int = 100) -> List[TranscriptionRecord]:
        """按音频源类型过滤

        Args:
            audio_source: 音频源类型
            limit: 返回记录数量限制

        Returns:
            List[TranscriptionRecord]: 过滤后的记录列表
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM transcription_history
                WHERE audio_source = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (audio_source, limit))

            rows = cursor.fetchall()
            conn.close()

            records = [self._row_to_record(row) for row in rows]
            logger.debug(f"Filtered {len(records)} records by source: {audio_source}")
            return records

        except Exception as e:
            logger.error(f"Failed to filter records: {e}")
            return []

    def get_record_by_id(self, record_id: int) -> Optional[TranscriptionRecord]:
        """根据ID获取记录

        Args:
            record_id: 记录ID

        Returns:
            Optional[TranscriptionRecord]: 记录对象，不存在返回None
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM transcription_history WHERE id = ?', (record_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._row_to_record(row)
            return None

        except Exception as e:
            logger.error(f"Failed to get record: {e}")
            return None

    def delete_record(self, record_id: int) -> bool:
        """删除记录

        Args:
            record_id: 记录ID

        Returns:
            bool: 是否成功删除
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('DELETE FROM transcription_history WHERE id = ?', (record_id,))
            conn.commit()

            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                logger.info(f"Record deleted: ID={record_id}")
            else:
                logger.warning(f"Record not found: ID={record_id}")

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete record: {e}")
            return False

    def get_record_count(self) -> int:
        """获取记录总数

        Returns:
            int: 记录总数
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM transcription_history')
            count = cursor.fetchone()[0]
            conn.close()

            return count

        except Exception as e:
            logger.error(f"Failed to get record count: {e}")
            return 0

    def _row_to_record(self, row: sqlite3.Row) -> TranscriptionRecord:
        """将数据库行转换为TranscriptionRecord对象

        Args:
            row: 数据库行对象

        Returns:
            TranscriptionRecord: 记录对象
        """
        from src.audio.models import AudioSourceType

        return TranscriptionRecord(
            id=row['id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            audio_source=AudioSourceType(row['audio_source']) if row['audio_source'] else None,
            audio_path=row['audio_path'],
            duration=row['duration'],
            text=row['text'],
            model_name=row['model_name'],
            config_snapshot=row['config_snapshot']
        )
```

---

## 📤 5. 导出功能

### 5.1 导出器类设计

```python
# 文件: src/gui/storage/exporters.py

import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import timedelta
import json

from src.gui.models.history_models import TranscriptionRecord

logger = logging.getLogger(__name__)


class BaseExporter:
    """导出器基类"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出记录

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            bool: 是否成功
        """
        raise NotImplementedError


class TXTExporter(BaseExporter):
    """TXT格式导出器"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出为TXT格式

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项
                - include_timestamp: 是否包含时间戳
                - include_metadata: 是否包含元数据

        Returns:
            bool: 是否成功
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # 元数据
                if options.get('include_metadata', False):
                    f.write(f"# 转录记录\n")
                    f.write(f"# 时间: {record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# 音频源: {record.audio_source.value if record.audio_source else '未知'}\n")
                    if record.audio_path:
                        f.write(f"# 文件: {record.audio_path}\n")
                    f.write(f"# 时长: {timedelta(seconds=int(record.duration))}\n")
                    f.write(f"# 模型: {record.model_name}\n")
                    f.write(f"\n")

                # 时间戳
                if options.get('include_timestamp', True):
                    timestamp_str = record.timestamp.strftime('[%H:%M:%S]')
                    f.write(f"{timestamp_str} {record.text}\n")
                else:
                    f.write(f"{record.text}\n")

            logger.info(f"Exported to TXT: {output_path}")
            return True

        except Exception as e:
            logger.error(f"TXT export failed: {e}")
            return False


class SRTExporter(BaseExporter):
    """SRT字幕格式导出器"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出为SRT字幕格式

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            bool: 是否成功
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # SRT格式示例:
                # 1
                # 00:00:00,000 --> 00:00:05,000
                # 转录文本内容

                # 简化实现：整个转录作为一个字幕块
                f.write("1\n")
                f.write(f"00:00:00,000 --> {self._format_timecode(record.duration)}\n")
                f.write(f"{record.text}\n")

            logger.info(f"Exported to SRT: {output_path}")
            return True

        except Exception as e:
            logger.error(f"SRT export failed: {e}")
            return False

    def _format_timecode(self, seconds: float) -> str:
        """格式化时间码为SRT格式

        Args:
            seconds: 秒数

        Returns:
            str: SRT时间码 (HH:MM:SS,mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class JSONExporter(BaseExporter):
    """JSON格式导出器"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出为JSON格式

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            bool: 是否成功
        """
        try:
            data = record.to_dict()

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported to JSON: {output_path}")
            return True

        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False


class VTTExporter(BaseExporter):
    """WebVTT字幕格式导出器"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出为VTT字幕格式

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            bool: 是否成功
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # WebVTT格式
                f.write("WEBVTT\n\n")
                f.write("1\n")
                f.write(f"00:00:00.000 --> {self._format_timecode(record.duration)}\n")
                f.write(f"{record.text}\n")

            logger.info(f"Exported to VTT: {output_path}")
            return True

        except Exception as e:
            logger.error(f"VTT export failed: {e}")
            return False

    def _format_timecode(self, seconds: float) -> str:
        """格式化时间码为VTT格式

        Args:
            seconds: 秒数

        Returns:
            str: VTT时间码 (HH:MM:SS.mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


class ExporterFactory:
    """导出器工厂类"""

    @staticmethod
    def get_exporter(format_type: str) -> BaseExporter:
        """根据格式类型获取导出器

        Args:
            format_type: 格式类型 (txt/srt/json/vtt)

        Returns:
            BaseExporter: 导出器实例

        Raises:
            ValueError: 不支持的格式
        """
        exporters = {
            'txt': TXTExporter(),
            'srt': SRTExporter(),
            'json': JSONExporter(),
            'vtt': VTTExporter(),
        }

        exporter = exporters.get(format_type.lower())
        if not exporter:
            raise ValueError(f"Unsupported format: {format_type}")

        return exporter
```

### 5.2 导出对话框

```python
# 文件: src/gui/dialogs/export_dialog.py

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QCheckBox, QLineEdit, QPushButton,
    QGroupBox, QMessageBox, QFileDialog, QWidget
)
from PySide6.QtCore import Slot

from src.gui.models.history_models import TranscriptionRecord
from src.gui.storage.exporters import ExporterFactory

logger = logging.getLogger(__name__)


class ExportDialog(QDialog):
    """导出对话框

    功能:
        - 选择导出格式
        - 配置导出选项
        - 选择保存位置
        - 执行导出
    """

    def __init__(self, record: TranscriptionRecord, parent: Optional[QWidget] = None):
        """初始化导出对话框

        Args:
            record: 要导出的转录记录
            parent: 父组件
        """
        super().__init__(parent)

        self.record = record

        # UI组件
        self.format_combo: Optional[QComboBox] = None
        self.include_timestamp_check: Optional[QCheckBox] = None
        self.include_metadata_check: Optional[QCheckBox] = None
        self.output_path_edit: Optional[QLineEdit] = None
        self.browse_button: Optional[QPushButton] = None
        self.export_button: Optional[QPushButton] = None
        self.cancel_button: Optional[QPushButton] = None

        # 初始化UI
        self._setup_ui()

        logger.debug("ExportDialog initialized")

    def _setup_ui(self) -> None:
        """设置UI布局"""
        self.setWindowTitle("导出转录结果")
        self.setMinimumWidth(500)
        self.setModal(True)

        # 主布局
        main_layout = QVBoxLayout(self)

        # 格式选择
        format_group = QGroupBox("导出格式")
        format_layout = QFormLayout(format_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["TXT (文本文件)", "SRT (字幕文件)", "JSON (数据文件)", "VTT (Web字幕)"])
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
        save_layout = QHBoxLayout()

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("选择保存位置...")
        save_layout.addWidget(self.output_path_edit)

        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        save_layout.addWidget(self.browse_button)

        main_layout.addLayout(save_layout)

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
        # 根据格式调整选项可用性
        format_map = {0: 'txt', 1: 'srt', 2: 'json', 3: 'vtt'}
        format_type = format_map.get(index, 'txt')

        # SRT和VTT固定包含时间戳
        if format_type in ['srt', 'vtt']:
            self.include_timestamp_check.setEnabled(False)
            self.include_timestamp_check.setChecked(True)
        else:
            self.include_timestamp_check.setEnabled(True)

    @Slot()
    def _on_browse_clicked(self) -> None:
        """打开文件保存对话框"""
        # 获取当前格式
        format_map = {
            0: ('txt', "文本文件 (*.txt)"),
            1: ('srt', "SRT字幕 (*.srt)"),
            2: ('json', "JSON文件 (*.json)"),
            3: ('vtt', "WebVTT字幕 (*.vtt)")
        }
        format_type, filter_str = format_map.get(self.format_combo.currentIndex(), ('txt', "文本文件 (*.txt)"))

        # 默认文件名
        default_name = f"transcription_{self.record.timestamp.strftime('%Y%m%d_%H%M%S')}.{format_type}"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存导出文件",
            default_name,
            filter_str
        )

        if file_path:
            # 确保文件扩展名正确
            if not file_path.endswith(f'.{format_type}'):
                file_path += f'.{format_type}'

            self.output_path_edit.setText(file_path)

    @Slot()
    def _on_export_clicked(self) -> None:
        """执行导出"""
        output_path = self.output_path_edit.text().strip()

        if not output_path:
            QMessageBox.warning(self, "输入错误", "请选择保存位置")
            return

        # 获取格式
        format_map = {0: 'txt', 1: 'srt', 2: 'json', 3: 'vtt'}
        format_type = format_map.get(self.format_combo.currentIndex(), 'txt')

        # 收集选项
        options = {
            'include_timestamp': self.include_timestamp_check.isChecked(),
            'include_metadata': self.include_metadata_check.isChecked()
        }

        try:
            # 获取导出器
            exporter = ExporterFactory.get_exporter(format_type)

            # 执行导出
            success = exporter.export(self.record, output_path, options)

            if success:
                QMessageBox.information(self, "导出成功", f"文件已保存到:\n{output_path}")
                self.accept()
            else:
                QMessageBox.warning(self, "导出失败", "导出过程中发生错误，请查看日志")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            QMessageBox.critical(self, "导出错误", f"导出失败:\n{e}")
```

---

## 🔗 6. 集成和修改现有代码

### 6.1 MainWindow 集成

```python
# 文件: src/gui/main_window.py (新增部分)

# 在 MainWindow 类中添加以下内容

from src.gui.dialogs.settings_dialog import SettingsDialog
from src.gui.storage.history_manager import HistoryManager
from src.gui.models.history_models import TranscriptionRecord

class MainWindow(QMainWindow):
    # ... 现有代码 ...

    def __init__(self):
        # ... 现有初始化代码 ...

        # 新增：历史记录管理器
        self.history_manager = HistoryManager()

    def _create_menu_bar(self) -> None:
        """创建菜单栏（扩展版本）"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        # 新增：设置菜单项
        settings_action = QAction("设置(&S)...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings_dialog)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        # 退出操作
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 新增：历史记录菜单
        history_menu = menubar.addMenu("历史记录(&H)")

        view_history_action = QAction("查看历史记录...", self)
        view_history_action.setShortcut("Ctrl+H")
        view_history_action.triggered.connect(self._show_history_panel)
        history_menu.addAction(view_history_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&?)")

        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    @Slot()
    def _show_settings_dialog(self) -> None:
        """显示设置对话框"""
        dialog = SettingsDialog(self.config, self.config_bridge, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    @Slot(object)
    def _on_settings_changed(self, new_config: Config) -> None:
        """处理设置变化

        Args:
            new_config: 新配置对象
        """
        self.config = new_config

        # 更新状态监控显示
        from pathlib import Path
        model_name = Path(self.config.model_path).name if self.config.model_path else "未指定"
        self.status_monitor.update_model(model_name)

        # 更新GPU状态
        self.status_monitor.update_gpu_status(not self.config.no_gpu)

        logger.info("Settings updated from dialog")

    @Slot()
    def _show_history_panel(self) -> None:
        """显示历史记录面板"""
        # TODO: 实现历史记录面板
        QMessageBox.information(self, "功能提示", "历史记录面板将在后续实现")

    def _connect_pipeline_signals(self) -> None:
        """连接Pipeline桥接器信号（扩展版本）"""
        if not self.pipeline_bridge:
            return

        # ... 现有信号连接 ...

        # 新增：转录完成信号（用于保存历史记录）
        self.pipeline_bridge.transcription_stopped.connect(self._on_transcription_completed)

    @Slot()
    def _on_transcription_completed(self) -> None:
        """处理转录完成事件（保存历史记录）"""
        try:
            # 收集转录结果
            full_text = self.result_display.get_full_text()

            if not full_text:
                logger.debug("No transcription text to save")
                return

            # 创建历史记录
            from src.audio.models import AudioSourceType
            from pathlib import Path
            import json
            from dataclasses import asdict

            # 确定音频源
            source_info = self.audio_source_selector.get_selected_source()
            audio_source = source_info.source_type if source_info else AudioSourceType.MICROPHONE
            audio_path = source_info.file_path if source_info and source_info.file_path else None

            # 计算时长（从控制面板获取）
            duration = self.control_panel._elapsed_seconds

            # 获取模型名称
            model_name = Path(self.config.model_path).name if self.config.model_path else "未知模型"

            # 配置快照
            config_snapshot = json.dumps(asdict(self.config), ensure_ascii=False, indent=2)

            # 创建记录对象
            record = TranscriptionRecord(
                timestamp=datetime.now(),
                audio_source=audio_source,
                audio_path=audio_path,
                duration=duration,
                text=full_text,
                model_name=model_name,
                config_snapshot=config_snapshot
            )

            # 保存到数据库
            record_id = self.history_manager.add_record(record)

            logger.info(f"Transcription saved to history: ID={record_id}")

        except Exception as e:
            logger.error(f"Failed to save transcription history: {e}")
```

---

## 📝 7. 文件清单

### 7.1 新增文件

| 文件路径 | 说明 | 行数估计 |
|---------|------|----------|
| `src/gui/storage/__init__.py` | 存储模块导出 | 10 |
| `src/gui/storage/config_file_manager.py` | 配置文件管理器 | 250 |
| `src/gui/storage/history_manager.py` | 历史记录管理器 | 300 |
| `src/gui/storage/exporters.py` | 导出器类 | 250 |
| `src/gui/models/history_models.py` | 历史记录数据模型 | 80 |
| `src/gui/dialogs/__init__.py` | 对话框模块导出 | 10 |
| `src/gui/dialogs/settings_dialog.py` | 系统设置对话框 | 500 |
| `src/gui/dialogs/export_dialog.py` | 导出对话框 | 200 |
| **总计** | **8个新文件** | **~1600行** |

### 7.2 修改文件

| 文件路径 | 修改内容 | 新增行数估计 |
|---------|---------|-------------|
| `src/gui/bridges/config_bridge.py` | 添加文件持久化方法 | +50 |
| `src/gui/main_window.py` | 集成设置对话框和历史管理 | +100 |
| `src/gui/bridges/pipeline_bridge.py` | 添加转录完成信号 | +10 |

---

## 🧪 8. 测试策略

### 8.1 单元测试

```python
# tests/gui/test_config_file_manager.py

import pytest
from pathlib import Path
from src.gui.storage.config_file_manager import ConfigFileManager
from src.config.models import Config

def test_save_and_load_config(tmp_path):
    """测试配置保存和加载"""
    # 创建临时配置管理器
    manager = ConfigFileManager()
    manager.config_file = tmp_path / "test_config.json"

    # 创建配置
    from src.config.manager import ConfigManager
    config = ConfigManager().get_default_config()
    config.model_path = "/test/model.onnx"

    # 保存配置
    success, error = manager.save_config(config)
    assert success, f"Save failed: {error}"

    # 加载配置
    loaded_config = manager.load_config()
    assert loaded_config is not None
    assert loaded_config.model_path == "/test/model.onnx"

# tests/gui/test_history_manager.py

import pytest
from src.gui.storage.history_manager import HistoryManager
from src.gui.models.history_models import TranscriptionRecord
from src.audio.models import AudioSourceType
from datetime import datetime

def test_add_and_get_record(tmp_path):
    """测试添加和获取记录"""
    # 创建临时历史管理器
    manager = HistoryManager()
    manager.db_path = tmp_path / "test_history.db"
    manager._init_database()

    # 创建记录
    record = TranscriptionRecord(
        timestamp=datetime.now(),
        audio_source=AudioSourceType.MICROPHONE,
        duration=60.0,
        text="测试转录文本",
        model_name="test-model"
    )

    # 添加记录
    record_id = manager.add_record(record)
    assert record_id > 0

    # 获取记录
    loaded_record = manager.get_record_by_id(record_id)
    assert loaded_record is not None
    assert loaded_record.text == "测试转录文本"
```

### 8.2 集成测试建议

- 测试设置对话框的配置保存流程
- 测试历史记录的完整生命周期（添加→查询→删除）
- 测试导出功能的所有格式
- 测试配置持久化的版本迁移

---

## ✅ 9. 实施检查清单

### 9.1 配置持久化
- [ ] 实现 ConfigFileManager
- [ ] 扩展 ConfigBridge
- [ ] 集成到 MainWindow 启动流程
- [ ] 单元测试

### 9.2 系统设置对话框
- [ ] 实现 SettingsDialog 基础框架
- [ ] 实现 6 个配置页面
- [ ] 集成到 MainWindow 菜单
- [ ] 测试配置保存和验证

### 9.3 转录历史记录
- [ ] 实现 TranscriptionRecord 数据模型
- [ ] 实现 HistoryManager（SQLite）
- [ ] 集成到 MainWindow（自动保存）
- [ ] 实现历史记录面板 UI
- [ ] 测试搜索和过滤功能

### 9.4 导出功能
- [ ] 实现 4 种导出器（TXT/SRT/JSON/VTT）
- [ ] 实现 ExportDialog
- [ ] 集成到历史记录面板
- [ ] 测试所有导出格式

### 9.5 最终验收
- [ ] 完整功能测试
- [ ] 性能测试（配置加载 < 500ms）
- [ ] 用户体验测试
- [ ] 代码审查

---

**文档结束**

本技术规格提供了 Phase 2 实施所需的所有技术细节，可直接用于代码生成。
