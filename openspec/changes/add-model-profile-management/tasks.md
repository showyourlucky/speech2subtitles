# Implementation Tasks: Model Profile Management

## Phase 1: Data Model (Day 1) ✅ **已完成**

### Task 1.1: Create ModelProfile Data Class ✅
- [x] 在 `src/config/models.py` 中创建 `ModelProfile` 数据类
  - [x] 定义基本字段：profile_id, profile_name, model_path
  - [x] 定义可选字段：description, supported_languages
  - [x] 定义时间戳字段：created_at, updated_at
  - [x] 使用 `@dataclass` 装饰器
  - [x] 添加 `default_factory` 为 profile_id 生成唯一ID
- [x] 实现 `ModelProfile.validate()` 方法
  - [x] 验证方案名称非空
  - [x] 验证模型路径非空且文件存在
  - [x] 验证文件格式（.onnx 或 .bin）
  - [x] 验证文件大小（> 1MB）
  - [x] 验证文件可读权限
- [x] 实现 `ModelProfile.to_dict()` 方法
  - [x] 转换所有字段为字典
  - [x] 时间戳使用 ISO 8601 格式
- [x] 实现 `ModelProfile.from_dict()` 静态方法
  - [x] 从字典创建 ModelProfile 实例
  - [x] 正确解析时间戳字符串
  - [x] 处理缺失字段（使用默认值）
- [x] 实现 `ModelProfile.create_default_profile()` 静态方法
  - [x] 创建 ID 为 "default" 的方案
  - [x] 设置默认名称"默认"
  - [x] 接受 model_path 参数
- [x] 添加完整的中文注释和文档字符串

### Task 1.2: Extend Config Data Class ✅
- [x] 在 `src/config/models.py` 的 `Config` 类中添加新字段
  - [x] 添加 `model_profiles: Dict[str, ModelProfile]` 字段
  - [x] 添加 `active_model_profile_id: str` 字段（默认 "default"）
  - [x] 保留 `model_path` 字段（标注已弃用）
- [x] 实现 `Config.get_active_model_profile()` 方法
  - [x] 从 model_profiles 获取活跃方案
  - [x] 方案不存在时抛出 ValueError
- [x] 实现 `Config.set_active_model_profile(profile_id)` 方法
  - [x] 验证 profile_id 存在
  - [x] 更新 active_model_profile_id
  - [x] 同步更新 model_path（向后兼容）
- [x] 添加完整的中文注释

### Task 1.3: Configuration Migration Logic ✅
- [x] 在 `src/config/models.py` 中实现 `migrate_legacy_config()` 函数
  - [x] 检测 model_profiles 为空或不存在
  - [x] 从 model_path 创建默认方案
  - [x] 设置 active_model_profile_id 为 "default"
  - [x] 记录迁移日志
- [x] 更新 `Config.validate()` 方法
  - [x] 调用迁移逻辑（如果需要）
  - [x] 验证至少有一个模型方案
  - [x] 验证活跃方案ID存在
  - [x] 验证所有模型方案（调用每个 profile.validate()）
  - [x] 同步 model_path 字段
- [x] 更新 `Config.__post_init__()` 方法
  - [x] 如果 model_profiles 为空，初始化为包含默认方案的字典

### Task 1.4: Unit Tests for Data Model ⏸️ **待完成**
- [ ] 创建 `tests/config/test_model_profile.py`
  - [ ] 测试 ModelProfile 创建
  - [ ] 测试 validate() 方法（各种验证场景）
  - [ ] 测试 to_dict() / from_dict() 序列化
  - [ ] 测试 create_default_profile()
- [ ] 扩展 `tests/config/test_config.py`
  - [ ] 测试 get_active_model_profile()
  - [ ] 测试 set_active_model_profile()
  - [ ] 测试配置迁移逻辑
  - [ ] 测试 model_profiles 验证
- [ ] 运行测试确保通过：`pytest tests/config/ -v`

---

## Phase 2: Settings Dialog (Day 2) ✅ **已完成**

### Task 2.1: Create Model Management Page UI ✅
- [x] 在 `src/gui/dialogs/settings_dialog.py` 中添加 `_create_model_page()` 方法
  - [ ] 创建主布局（QHBoxLayout）
  - [ ] 创建左侧面板（模型列表区域）
    - [ ] 添加标题标签"模型方案"
    - [ ] 添加 QListWidget (`self.model_profile_list`)
    - [ ] 添加操作按钮栏（新增/删除/复制/重命名）
    - [ ] 设置最大宽度 250px
  - [ ] 创建右侧面板（参数编辑区域）
    - [ ] 添加"方案名称"输入框
    - [ ] 添加"模型路径"输入框 + 浏览按钮
    - [ ] 添加"描述"文本框
    - [ ] 添加"支持语言"输入框（可选）
    - [ ] 添加"验证模型"按钮
    - [ ] 添加说明文本
  - [ ] 存储控件引用到 `self.config_widgets`
- [ ] 在 `_create_pages()` 中调用 `_create_model_page()`
  - [ ] 添加到导航列表和页面容器

### Task 2.2: Implement Model Profile List Loading
- [ ] 实现 `_load_model_settings()` 方法
  - [ ] 清空模型列表
  - [ ] 遍历 `self.config.model_profiles`
  - [ ] 为每个方案创建 QListWidgetItem
  - [ ] 存储 profile_id 到 item.data(Qt.UserRole)
  - [ ] 标记活跃方案（选中或添加图标）
  - [ ] 如果没有选中项，选中第一个
- [ ] 在 `_load_settings()` 中调用 `_load_model_settings()`

### Task 2.3: Implement Model Profile Selection Handler
- [ ] 实现 `_on_model_profile_selected()` 槽函数
  - [ ] 获取选中项的 profile_id
  - [ ] 更新 `self.current_editing_model_profile_id`
  - [ ] 从 config.model_profiles 获取方案对象
  - [ ] 加载方案参数到右侧UI控件
    - [ ] 设置方案名称
    - [ ] 设置模型路径
    - [ ] 设置描述
    - [ ] 设置支持语言
- [ ] 连接信号：`self.model_profile_list.currentItemChanged.connect()`

### Task 2.4: Implement Model Profile Operations
- [ ] 实现 `_on_add_model_profile()` 槽函数
  - [ ] 弹出对话框输入方案名称
  - [ ] 检查名称是否重复
  - [ ] 弹出文件选择对话框选择模型文件
  - [ ] 验证模型文件（调用 validate_model_file()）
  - [ ] 创建新的 ModelProfile 对象
  - [ ] 调用 `config_bridge.add_model_profile()`
  - [ ] 刷新模型列表
  - [ ] 选中新添加的方案
- [ ] 实现 `_on_delete_model_profile()` 槽函数
  - [ ] 获取选中方案的 profile_id
  - [ ] 检查是否为默认方案（阻止删除）
  - [ ] 检查是否为唯一方案（阻止删除）
  - [ ] 弹出确认对话框
  - [ ] 调用 `config_bridge.delete_model_profile()`
  - [ ] 刷新模型列表
- [ ] 实现 `_on_copy_model_profile()` 槽函数
  - [ ] 获取源方案
  - [ ] 弹出对话框输入新方案名称
  - [ ] 创建方案副本（新profile_id）
  - [ ] 调用 `config_bridge.add_model_profile()`
  - [ ] 刷新列表并选中新方案
- [ ] 实现 `_on_rename_model_profile()` 槽函数
  - [ ] 弹出对话框输入新名称
  - [ ] 检查名称是否重复
  - [ ] 更新方案名称
  - [ ] 调用 `config_bridge.update_model_profile()`
  - [ ] 更新列表项显示
- [ ] 连接所有按钮的 clicked 信号

### Task 2.5: Implement Model Validation
- [ ] 实现 `_validate_model_file()` 方法
  - [ ] 获取当前模型路径
  - [ ] 检查路径非空
  - [ ] 检查文件存在
  - [ ] 检查文件格式
  - [ ] 检查文件大小
  - [ ] 显示验证结果对话框（成功/失败 + 详细信息）
- [ ] 连接"验证模型"按钮的 clicked 信号

### Task 2.6: Implement Settings Collection
- [ ] 实现 `_collect_model_settings()` 方法
  - [ ] 检查是否有正在编辑的方案
  - [ ] 从UI控件收集参数
  - [ ] 更新 ModelProfile 对象
  - [ ] 更新 config.model_profiles
  - [ ] 设置 updated_at 时间戳
- [ ] 在 `_collect_settings()` 中调用 `_collect_model_settings()`

### Task 2.7: Integration Testing
- [ ] 手动测试设置对话框功能
  - [ ] 添加模型方案
  - [ ] 删除模型方案
  - [ ] 复制模型方案
  - [ ] 重命名模型方案
  - [ ] 编辑模型参数
  - [ ] 验证模型文件
  - [ ] 保存设置
  - [ ] 取消设置
- [ ] 测试边界情况
  - [ ] 删除唯一方案
  - [ ] 删除默认方案
  - [ ] 无效的模型文件
  - [ ] 名称重复

---

## Phase 3: Main Window Integration (Day 3)

### Task 3.1: Add Model Selector to Advanced Settings Panel
- [ ] 在 `src/gui/main_window.py` 中定位 `AdvancedSettingsPanel`
- [ ] 在 `_setup_ui()` 或相关方法中添加模型选择器
  - [ ] 创建 QLabel("模型:")
  - [ ] 创建 QComboBox (`self.model_selector`)
  - [ ] 添加到面板布局（VAD 选择器旁边）
- [ ] 实现 `_populate_model_selector()` 方法
  - [ ] 清空现有项
  - [ ] 遍历 `config.model_profiles`
  - [ ] 添加每个方案的名称和 profile_id
  - [ ] 选中活跃方案
- [ ] 在初始化时调用 `_populate_model_selector()`

### Task 3.2: Implement Model Switching Logic
- [ ] 实现 `_on_model_changed()` 槽函数
  - [ ] 获取新选择的 profile_id
  - [ ] 检查是否与当前活跃方案相同（跳过）
  - [ ] 检查 Pipeline 是否正在运行
    - [ ] 如果运行中，显示确认对话框
    - [ ] 用户取消时恢复之前的选择
  - [ ] 停止 Pipeline（如果需要）
  - [ ] 调用 `config_bridge.switch_model_profile(profile_id)`
  - [ ] 重新加载配置
  - [ ] 更新状态栏
  - [ ] 可选：自动重启 Pipeline
  - [ ] 处理切换失败（显示错误对话框）
- [ ] 连接信号：`self.model_selector.currentIndexChanged.connect()`

### Task 3.3: Update Status Bar to Show Model Info
- [ ] 在状态栏添加模型信息标签（如果还没有）
- [ ] 实现 `_update_model_status()` 方法
  - [ ] 获取当前活跃模型方案
  - [ ] 更新状态栏显示：模型名称
- [ ] 在以下场景调用：
  - [ ] 主窗口初始化后
  - [ ] 模型切换后
  - [ ] 配置更新后

### Task 3.4: Handle Config Updates
- [ ] 实现 `_on_config_changed()` 槽函数（或扩展现有方法）
  - [ ] 重新加载模型选择器
  - [ ] 更新状态栏
- [ ] 连接 `config_bridge.config_changed` 信号

### Task 3.5: Integration Testing
- [ ] 手动测试主窗口功能
  - [ ] 模型选择器显示所有方案
  - [ ] 选择不同模型
  - [ ] 运行中切换模型（确认对话框）
  - [ ] 切换后状态栏更新
  - [ ] 切换后转录使用新模型
- [ ] 测试错误场景
  - [ ] 模型文件被删除后切换
  - [ ] 配置损坏时的处理

---

## Phase 4: ConfigBridge Extensions (Day 3) ✅ **已完成**

### Task 4.1: Implement ConfigBridge Model Management Methods ✅
- [x] 在 `src/gui/bridges/config_bridge.py` 中实现方法
  - [x] `switch_model_profile(profile_id: str) -> bool`
    - [x] 调用 `config.set_active_model_profile()`
    - [x] 返回 True/False
    - [x] 捕获并记录异常
  - [x] `add_model_profile(profile: ModelProfile) -> bool`
    - [x] 调用 `profile.validate()`
    - [x] 添加到 `config.model_profiles`
    - [x] 返回 True/False
  - [x] `delete_model_profile(profile_id: str) -> bool`
    - [x] 验证不是默认方案
    - [x] 验证不是唯一方案
    - [x] 如果是活跃方案，切换到其他方案
    - [x] 删除方案
    - [x] 返回 True/False
  - [x] `update_model_profile(profile_id: str, profile: ModelProfile) -> bool`
    - [x] 验证 profile_id 存在
    - [x] 调用 `profile.validate()`
    - [x] 更新 updated_at 时间戳
    - [x] 更新到 `config.model_profiles`
    - [x] 如果是活跃方案，同步 model_path
    - [x] 返回 True/False
- [x] 添加完整的中文注释和文档字符串
- [x] 更新 `_dict_to_config()` 方法处理 ModelProfile 序列化

### Task 4.2: Unit Tests for ConfigBridge ⏸️ **待完成**
- [ ] 创建或扩展 `tests/gui/test_config_bridge.py`
  - [ ] 测试 switch_model_profile()
  - [ ] 测试 add_model_profile()
  - [ ] 测试 delete_model_profile()
  - [ ] 测试 update_model_profile()
  - [ ] 测试异常处理
  - [ ] 测试信号发射
- [ ] 运行测试：`pytest tests/gui/test_config_bridge.py -v`

---

## Phase 5: Testing and Documentation (Day 4)

### Task 5.1: Unit Tests
- [ ] 完善所有单元测试
  - [ ] `tests/config/test_model_profile.py` - 100% 覆盖
  - [ ] `tests/config/test_config.py` - 模型方案相关测试
  - [ ] `tests/gui/test_config_bridge.py` - 桥接方法测试
- [ ] 运行完整测试套件：`pytest tests/ -v --cov=src`
- [ ] 确保覆盖率 > 90%

### Task 5.2: Integration Tests
- [ ] 创建 `tests/integration/test_model_management.py`
  - [ ] 测试完整的添加流程（UI -> Bridge -> Config）
  - [ ] 测试完整的切换流程
  - [ ] 测试配置持久化和加载
  - [ ] 测试配置迁移
- [ ] 运行集成测试

### Task 5.3: Manual Testing
- [ ] 创建测试检查清单
  - [ ] 首次启动（配置迁移）
  - [ ] 添加自定义模型
  - [ ] 编辑模型信息
  - [ ] 删除模型
  - [ ] 主窗口切换模型
  - [ ] 运行中切换模型
  - [ ] 配置导入/导出
  - [ ] 错误场景处理
- [ ] 执行完整手动测试
- [ ] 记录发现的 bug 并修复

### Task 5.4: Update Documentation
- [ ] 更新 `src/config/CLAUDE.md`
  - [ ] 添加 ModelProfile 说明
  - [ ] 更新 Config 字段说明
  - [ ] 添加使用示例
- [ ] 更新 `src/gui/CLAUDE.md`
  - [ ] 添加模型管理 UI 说明
  - [ ] 更新主窗口功能说明
- [ ] 更新根目录 `CLAUDE.md`
  - [ ] 更新变更日志（Changelog）
  - [ ] 添加模型管理功能描述
- [ ] 创建用户文档（可选）
  - [ ] 如何添加模型配置
  - [ ] 如何切换模型
  - [ ] 常见问题解答

### Task 5.5: Code Review and Cleanup
- [ ] 代码格式化：`black src/ tests/`
- [ ] 代码检查：`flake8 src/ tests/`
- [ ] 检查所有中文注释的正确性
- [ ] 移除调试代码
- [ ] 优化导入语句
- [ ] 检查代码重复（DRY 原则）

### Task 5.6: Performance Testing
- [ ] 测试模型列表加载时间
- [ ] 测试模型切换响应时间
- [ ] 测试配置文件读写性能
- [ ] 测试大量模型方案场景（10+ 个）

---

## Acceptance Checklist

### Functional Requirements
- [ ] ✅ 用户可以在设置对话框中添加模型配置
- [ ] ✅ 用户可以在设置对话框中删除模型配置
- [ ] ✅ 用户可以在设置对话框中编辑模型配置
- [ ] ✅ 用户可以在主界面下拉框中选择模型
- [ ] ✅ 用户可以在主界面快速切换模型
- [ ] ✅ 模型切换后转录使用新模型
- [ ] ✅ 配置自动保存并在重启后恢复
- [ ] ✅ 旧配置文件自动迁移到新格式
- [ ] ✅ 至少保留一个模型配置
- [ ] ✅ 默认方案不能被删除
- [ ] ✅ 模型文件路径验证正确

### Non-Functional Requirements
- [ ] ✅ 模型列表加载时间 < 50ms
- [ ] ✅ 模型切换响应时间 < 200ms
- [ ] ✅ 单元测试覆盖率 > 90%
- [ ] ✅ 所有测试通过
- [ ] ✅ 代码通过 flake8 检查
- [ ] ✅ 代码通过 black 格式化
- [ ] ✅ 中文注释完整且准确

### Documentation
- [ ] ✅ CLAUDE.md 已更新
- [ ] ✅ 代码注释完整
- [ ] ✅ 文档字符串完整
- [ ] ✅ 用户文档已创建（可选）

---

## Rollback Plan

如果实现过程中遇到严重问题，可以按以下步骤回滚：

1. **保留数据兼容性**：
   - model_path 字段始终保留
   - 即使没有 model_profiles，系统仍可运行

2. **渐进式禁用**：
   - 隐藏主窗口的模型选择器
   - 隐藏设置对话框的模型管理页
   - 使用 model_path 作为唯一配置

3. **数据恢复**：
   - 从配置文件备份恢复
   - 使用默认模型配置

---

## Notes

- 严格遵循 KISS 原则，避免过度设计
- 复用 VAD 方案管理的代码模式
- 确保向后兼容性
- 充分测试边界情况
- 保持代码可维护性

---

**预计工作量**: 4 天（32 小时）
**优先级**: 高
**风险等级**: 中
