# Design: Model Profile Management

## Overview

本设计文档描述模型配置方案管理功能的技术实现方案。该功能允许用户创建、管理和切换多个语音识别模型配置，类似于现有的VAD方案管理系统。

## Architecture

### System Context

```
┌─────────────────────────────────────────────────────────┐
│                     MainWindow (GUI)                     │
│  ┌────────────────┐        ┌─────────────────────────┐  │
│  │ Model Selector │◄───────┤  Advanced Settings      │  │
│  │   (ComboBox)   │        │    Panel                │  │
│  └────────┬───────┘        └──────────┬──────────────┘  │
│           │                           │                  │
└───────────┼───────────────────────────┼──────────────────┘
            │                           │
            ▼                           ▼
┌───────────────────────────────────────────────────────┐
│              ConfigBridge (Bridge Layer)              │
│  ┌─────────────────────────────────────────────────┐  │
│  │  • switch_model_profile(profile_id)             │  │
│  │  • add_model_profile(profile)                   │  │
│  │  • delete_model_profile(profile_id)             │  │
│  │  • update_model_profile(profile_id, profile)    │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────┬───────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────┐
│              Config (Data Model Layer)                │
│  ┌─────────────────────────────────────────────────┐  │
│  │  model_profiles: Dict[str, ModelProfile]       │  │
│  │  active_model_profile_id: str                  │  │
│  │  model_path: str (deprecated, for compat)     │  │
│  │                                                 │  │
│  │  Methods:                                       │  │
│  │  • get_active_model_profile()                  │  │
│  │  • set_active_model_profile(profile_id)       │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────┬───────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────┐
│           ModelProfile (Data Class)                   │
│  ┌─────────────────────────────────────────────────┐  │
│  │  profile_id: str                                │  │
│  │  profile_name: str                              │  │
│  │  model_path: str                                │  │
│  │  description: Optional[str]                     │  │
│  │  supported_languages: Optional[List[str]]       │  │
│  │  created_at: datetime                           │  │
│  │  updated_at: datetime                           │  │
│  │                                                 │  │
│  │  Methods:                                       │  │
│  │  • validate()                                   │  │
│  │  • to_dict()                                    │  │
│  │  • from_dict(data)                             │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│                  SettingsDialog                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │           Model Management Page                    │  │
│  │  ┌──────────────────┐  ┌─────────────────────────┐│  │
│  │  │  Profile List    │  │   Profile Editor        ││  │
│  │  │  ┌────────────┐  │  │  ┌───────────────────┐ ││  │
│  │  │  │ Default ✓  │  │  │  │ Name:   [____]    │ ││  │
│  │  │  │ Model A    │◄─┼──┼─▶│ Path:   [____][..] │ ││  │
│  │  │  │ Model B    │  │  │  │ Desc:   [____]    │ ││  │
│  │  │  └────────────┘  │  │  │ Lang:   [____]    │ ││  │
│  │  │  [Add] [Delete]  │  │  └───────────────────┘ ││  │
│  │  │  [Copy] [Rename] │  │  [Validate Model]      ││  │
│  │  └──────────────────┘  └─────────────────────────┘│  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                     MainWindow                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │         Advanced Settings Panel                    │  │
│  │  ┌──────────────────────────────────────────────┐ │  │
│  │  │  模型: [Default ▼]    VAD: [默认 ▼]         │ │  │
│  │  │        └─ Model A                            │ │  │
│  │  │           Model B                            │ │  │
│  │  └──────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Data Model

### ModelProfile Class

```python
@dataclass
class ModelProfile:
    """模型配置方案数据类

    存储单个语音识别模型的完整配置信息
    """
    # 基本信息
    profile_id: str = field(default_factory=lambda: f"model_{uuid.uuid4().hex[:8]}")
    profile_name: str = "未命名模型"

    # 模型路径（必需）
    model_path: str = ""

    # 可选元数据
    description: Optional[str] = None
    supported_languages: Optional[List[str]] = None  # ["zh", "en", "ja", "ko", "yue"]

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def validate(self) -> None:
        """验证模型配置的有效性

        Raises:
            ValueError: 配置无效时抛出异常
        """
        # 验证方案名称
        if not self.profile_name or not self.profile_name.strip():
            raise ValueError("模型方案名称不能为空")

        # 验证模型路径
        if not self.model_path or not self.model_path.strip():
            raise ValueError("模型文件路径不能为空")

        model_path = Path(self.model_path)
        if not model_path.exists():
            raise ValueError(f"模型文件不存在: {self.model_path}")

        if not model_path.is_file():
            raise ValueError(f"模型路径不是文件: {self.model_path}")

        if model_path.suffix.lower() not in ['.onnx', '.bin']:
            raise ValueError(
                f"不支持的模型文件格式: {model_path.suffix}, "
                f"支持的格式: .onnx, .bin"
            )

        # 验证文件大小（模型文件不应小于1MB）
        file_size_mb = model_path.stat().st_size / (1024 * 1024)
        if file_size_mb < 1:
            raise ValueError(f"模型文件过小 ({file_size_mb:.2f}MB), 可能不是有效的模型文件")

    @staticmethod
    def create_default_profile(model_path: str = "") -> 'ModelProfile':
        """创建默认模型方案

        Args:
            model_path: 模型文件路径

        Returns:
            ModelProfile: 默认配置方案
        """
        return ModelProfile(
            profile_id="default",
            profile_name="默认",
            model_path=model_path,
            description="系统默认模型配置",
            supported_languages=["zh", "en", "ja", "ko", "yue"]
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "model_path": self.model_path,
            "description": self.description,
            "supported_languages": self.supported_languages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ModelProfile':
        """从字典创建实例（用于反序列化）"""
        return ModelProfile(
            profile_id=data.get("profile_id", f"model_{uuid.uuid4().hex[:8]}"),
            profile_name=data.get("profile_name", "未命名模型"),
            model_path=data.get("model_path", ""),
            description=data.get("description"),
            supported_languages=data.get("supported_languages"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now()
        )
```

### Config Extensions

```python
@dataclass
class Config:
    """系统配置数据类（扩展）"""

    # 现有字段
    model_path: str  # 已弃用，保留用于向后兼容
    # ... 其他字段 ...

    # 新增字段
    model_profiles: Dict[str, ModelProfile] = field(default_factory=dict)
    active_model_profile_id: str = "default"

    def get_active_model_profile(self) -> ModelProfile:
        """获取当前活跃的模型方案

        Returns:
            ModelProfile: 当前活跃的模型配置方案

        Raises:
            ValueError: 如果活跃方案不存在
        """
        if self.active_model_profile_id not in self.model_profiles:
            raise ValueError(f"活跃的模型方案 '{self.active_model_profile_id}' 不存在")
        return self.model_profiles[self.active_model_profile_id]

    def set_active_model_profile(self, profile_id: str) -> None:
        """设置活跃的模型方案

        Args:
            profile_id: 模型方案ID

        Raises:
            ValueError: 如果方案不存在
        """
        if profile_id not in self.model_profiles:
            raise ValueError(f"模型方案 '{profile_id}' 不存在")
        self.active_model_profile_id = profile_id

        # 同步更新 model_path (用于向后兼容)
        self.model_path = self.model_profiles[profile_id].model_path
```

## Configuration Migration

### Migration Strategy

```python
def migrate_legacy_config(config: Config) -> None:
    """迁移旧版配置到新格式

    Args:
        config: 配置对象
    """
    # 如果没有模型方案，从 model_path 创建默认方案
    if not config.model_profiles or len(config.model_profiles) == 0:
        logger.info("检测到旧版配置格式，开始迁移...")

        default_profile = ModelProfile.create_default_profile(
            model_path=config.model_path if config.model_path else ""
        )

        config.model_profiles = {"default": default_profile}
        config.active_model_profile_id = "default"

        logger.info("配置迁移完成，已创建默认模型方案")

    # 验证活跃方案ID存在
    if config.active_model_profile_id not in config.model_profiles:
        logger.warning(f"活跃方案ID '{config.active_model_profile_id}' 不存在，重置为默认方案")

        if "default" in config.model_profiles:
            config.active_model_profile_id = "default"
        else:
            # 使用第一个可用方案
            config.active_model_profile_id = next(iter(config.model_profiles.keys()))

    # 同步 model_path 字段（向后兼容）
    active_profile = config.get_active_model_profile()
    config.model_path = active_profile.model_path
```

### Config Validation Updates

```python
def validate(self) -> None:
    """验证配置的有效性（更新）"""
    # ... 现有验证逻辑 ...

    # 验证模型方案配置
    if not self.model_profiles:
        # 如果没有模型方案，尝试迁移
        migrate_legacy_config(self)

    # 验证至少有一个模型方案
    if not self.model_profiles:
        raise ValueError("至少需要一个模型配置方案")

    # 验证活跃方案ID存在
    if self.active_model_profile_id not in self.model_profiles:
        raise ValueError(
            f"活跃的模型方案ID '{self.active_model_profile_id}' 不存在，"
            f"可用方案: {list(self.model_profiles.keys())}"
        )

    # 验证所有模型方案
    for profile_id, profile in self.model_profiles.items():
        try:
            profile.validate()
        except Exception as e:
            raise ValueError(f"模型方案 '{profile_id}' 配置无效: {e}")

    # 同步 model_path（向后兼容）
    active_profile = self.get_active_model_profile()
    self.model_path = active_profile.model_path
```

## UI Implementation

### SettingsDialog - Model Management Page

**布局设计：**
- 左侧：模型方案列表 + 操作按钮（新增/删除/复制/重命名）
- 右侧：选中方案的参数编辑区域

**关键方法：**
```python
def _create_model_page(self) -> QWidget:
    """创建模型配置页"""
    # 类似 _create_vad_page() 的实现
    # 左侧列表 + 右侧编辑区域
    pass

def _on_model_profile_selected(self, current, previous):
    """处理模型方案选择事件"""
    # 加载选中方案的参数到UI控件
    pass

def _on_add_model_profile(self):
    """新增模型方案"""
    # 弹出对话框输入方案名和模型路径
    # 验证模型文件
    # 添加到配置
    pass

def _on_delete_model_profile(self):
    """删除模型方案"""
    # 确认删除（保护默认方案）
    # 确保至少保留一个方案
    # 如果删除的是活跃方案，切换到其他方案
    pass

def _on_validate_model(self):
    """验证模型文件"""
    # 检查文件存在性
    # 检查文件格式
    # 检查文件大小
    # 显示验证结果
    pass
```

### MainWindow - Model Selector

**位置：** Advanced Settings Panel

**实现：**
```python
def _create_model_selector(self) -> QComboBox:
    """创建模型选择下拉框"""
    model_combo = QComboBox()

    # 加载所有模型方案
    for profile_id, profile in self.config.model_profiles.items():
        model_combo.addItem(profile.profile_name, profile_id)

    # 选中活跃方案
    index = model_combo.findData(self.config.active_model_profile_id)
    if index >= 0:
        model_combo.setCurrentIndex(index)

    # 连接信号
    model_combo.currentIndexChanged.connect(self._on_model_changed)

    return model_combo

def _on_model_changed(self, index: int):
    """处理模型切换事件"""
    profile_id = self.model_combo.itemData(index)

    # 如果Pipeline正在运行，需要重启
    if self.pipeline and self.pipeline.is_running:
        reply = QMessageBox.question(
            self,
            "确认切换",
            "切换模型需要停止当前转录，是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            # 恢复之前的选择
            old_index = self.model_combo.findData(self.config.active_model_profile_id)
            self.model_combo.setCurrentIndex(old_index)
            return

        # 停止Pipeline
        self._stop_transcription()

    # 切换模型
    try:
        self.config_bridge.switch_model_profile(profile_id)
        self.config = self.config_bridge.get_config()
        logger.info(f"已切换到模型方案: {profile_id}")

        # 更新状态栏
        self._update_status_bar()

    except Exception as e:
        logger.error(f"切换模型失败: {e}")
        QMessageBox.warning(self, "切换失败", f"无法切换模型:\n{e}")
```

## ConfigBridge Extensions

```python
class ConfigBridge:
    """配置桥接器（扩展）"""

    def switch_model_profile(self, profile_id: str) -> bool:
        """切换活跃的模型方案

        Args:
            profile_id: 模型方案ID

        Returns:
            bool: 是否切换成功
        """
        try:
            self.config.set_active_model_profile(profile_id)
            self.save_config(self.config)
            self.config_changed.emit(self.config)
            return True
        except Exception as e:
            logger.error(f"切换模型方案失败: {e}")
            return False

    def add_model_profile(self, profile: ModelProfile) -> bool:
        """添加模型方案

        Args:
            profile: 模型方案对象

        Returns:
            bool: 是否添加成功
        """
        try:
            profile.validate()
            self.config.model_profiles[profile.profile_id] = profile
            self.save_config(self.config)
            return True
        except Exception as e:
            logger.error(f"添加模型方案失败: {e}")
            return False

    def delete_model_profile(self, profile_id: str) -> bool:
        """删除模型方案

        Args:
            profile_id: 模型方案ID

        Returns:
            bool: 是否删除成功
        """
        try:
            # 保护默认方案
            if profile_id == "default":
                raise ValueError("默认方案不能被删除")

            # 至少保留一个方案
            if len(self.config.model_profiles) <= 1:
                raise ValueError("必须至少保留一个模型方案")

            # 如果删除的是活跃方案，切换到其他方案
            if profile_id == self.config.active_model_profile_id:
                # 切换到默认方案或第一个可用方案
                if "default" in self.config.model_profiles and "default" != profile_id:
                    self.config.active_model_profile_id = "default"
                else:
                    # 找到第一个不是被删除方案的ID
                    for pid in self.config.model_profiles.keys():
                        if pid != profile_id:
                            self.config.active_model_profile_id = pid
                            break

            # 删除方案
            del self.config.model_profiles[profile_id]
            self.save_config(self.config)
            self.config_changed.emit(self.config)
            return True

        except Exception as e:
            logger.error(f"删除模型方案失败: {e}")
            return False

    def update_model_profile(self, profile_id: str, profile: ModelProfile) -> bool:
        """更新模型方案

        Args:
            profile_id: 模型方案ID
            profile: 新的模型方案对象

        Returns:
            bool: 是否更新成功
        """
        try:
            if profile_id not in self.config.model_profiles:
                raise ValueError(f"模型方案 '{profile_id}' 不存在")

            profile.validate()
            profile.updated_at = datetime.now()
            self.config.model_profiles[profile_id] = profile

            # 如果是活跃方案，同步 model_path
            if profile_id == self.config.active_model_profile_id:
                self.config.model_path = profile.model_path

            self.save_config(self.config)
            self.config_changed.emit(self.config)
            return True

        except Exception as e:
            logger.error(f"更新模型方案失败: {e}")
            return False
```

## Error Handling

### Model File Validation

```python
def validate_model_file(model_path: str) -> tuple[bool, Optional[str]]:
    """验证模型文件

    Args:
        model_path: 模型文件路径

    Returns:
        tuple: (是否有效, 错误信息)
    """
    try:
        path = Path(model_path)

        # 检查文件存在
        if not path.exists():
            return False, f"文件不存在: {model_path}"

        # 检查是文件而非目录
        if not path.is_file():
            return False, f"路径不是文件: {model_path}"

        # 检查文件扩展名
        if path.suffix.lower() not in ['.onnx', '.bin']:
            return False, f"不支持的文件格式: {path.suffix}"

        # 检查文件大小
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb < 1:
            return False, f"文件过小 ({file_size_mb:.2f}MB), 可能不是有效的模型文件"

        # 检查文件权限
        if not os.access(path, os.R_OK):
            return False, f"没有读取权限: {model_path}"

        return True, None

    except Exception as e:
        return False, f"验证时发生错误: {e}"
```

### Pipeline Model Switching

```python
def switch_model_and_restart_pipeline(self, profile_id: str) -> bool:
    """切换模型并重启Pipeline

    Args:
        profile_id: 新的模型方案ID

    Returns:
        bool: 是否成功
    """
    try:
        # 1. 保存当前状态
        was_running = self.pipeline and self.pipeline.is_running

        # 2. 停止Pipeline
        if was_running:
            self._stop_transcription()

        # 3. 切换模型配置
        success = self.config_bridge.switch_model_profile(profile_id)
        if not success:
            raise RuntimeError("切换模型配置失败")

        # 4. 重新加载配置
        self.config = self.config_bridge.get_config()

        # 5. 如果之前在运行，重新启动
        if was_running:
            # 注意：需要重新创建Pipeline实例
            self._initialize_pipeline()
            self._start_transcription()

        return True

    except Exception as e:
        logger.error(f"切换模型并重启Pipeline失败: {e}")
        QMessageBox.critical(
            self,
            "切换失败",
            f"切换模型时发生错误:\n{e}\n\n请检查模型文件是否有效"
        )
        return False
```

## Testing Strategy

### Unit Tests

```python
# tests/config/test_model_profile.py
def test_model_profile_creation():
    """测试模型方案创建"""
    profile = ModelProfile(
        profile_name="Test Model",
        model_path="/path/to/model.onnx"
    )
    assert profile.profile_name == "Test Model"
    assert profile.model_path == "/path/to/model.onnx"

def test_model_profile_validation():
    """测试模型方案验证"""
    # 测试空名称
    # 测试空路径
    # 测试不存在的文件
    # 测试无效的文件格式
    pass

def test_config_model_profiles():
    """测试Config中的模型方案管理"""
    # 测试获取活跃方案
    # 测试设置活跃方案
    # 测试方案不存在的异常
    pass

def test_config_migration():
    """测试配置迁移"""
    # 测试从旧版 model_path 迁移
    # 测试迁移后的方案ID
    # 测试迁移后的活跃方案
    pass
```

### Integration Tests

```python
# tests/gui/test_model_selector.py
def test_model_selector_display():
    """测试模型选择器显示"""
    # 测试加载所有方案到下拉框
    # 测试选中活跃方案
    pass

def test_model_switching():
    """测试模型切换"""
    # 测试切换到其他模型
    # 测试配置更新
    # 测试信号发射
    pass

def test_settings_dialog_model_management():
    """测试设置对话框中的模型管理"""
    # 测试添加模型
    # 测试删除模型
    # 测试编辑模型
    # 测试验证模型
    pass
```

## Performance Considerations

### Memory Usage
- 每个 `ModelProfile` 对象约占用 < 1KB 内存
- 预期用户最多创建 10-20 个模型配置
- 总额外内存开销 < 20KB

### Disk Usage
- 每个模型配置在JSON中约占用 200-500 字节
- 配置文件大小增长约 5-10KB（10个模型）

### UI Performance
- 模型列表加载时间 < 50ms
- 模型切换响应时间 < 200ms
- 设置对话框打开时间 < 100ms

## Security Considerations

### File Path Validation
- 验证文件路径不包含恶意字符
- 检查文件权限
- 防止路径遍历攻击

### Configuration Integrity
- 配置文件读写时进行备份
- 验证JSON格式完整性
- 处理损坏的配置文件

## Future Enhancements

### Phase 2 Features (Future)
- 模型自动扫描（扫描指定目录）
- 模型性能基准测试
- 模型参数配置（温度、束搜索等）
- 模型导入/导出功能
- 模型元数据在线获取
- 云端模型仓库集成

## References

- 类似实现: [src/config/models.py](../../src/config/models.py) - VadProfile
- UI参考: [src/gui/dialogs/settings_dialog.py](../../src/gui/dialogs/settings_dialog.py) - VAD方案管理
- 配置管理: [src/gui/bridges/config_bridge.py](../../src/gui/bridges/config_bridge.py)
