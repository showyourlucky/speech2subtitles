# Specification: Model Profile Management

## Overview

模型配置方案管理能力，允许用户创建、管理和切换多个语音识别模型配置。

## ADDED Requirements

### Requirement: Model Profile Data Model

**ID**: MODEL-MGMT-001

**Priority**: High

**Description**:
系统MUST提供 `ModelProfile` 数据类，用于存储和管理单个模型的完整配置信息。

**Acceptance Criteria**:
- ModelProfile 包含必需字段：profile_id, profile_name, model_path
- ModelProfile 包含可选字段：description, supported_languages
- ModelProfile 包含时间戳字段：created_at, updated_at
- 提供 `validate()` 方法验证配置有效性
- 提供 `to_dict()` 和 `from_dict()` 方法支持序列化
- 提供 `create_default_profile()` 静态方法创建默认方案

#### Scenario: 创建新的模型方案

**Given**: 用户想要添加一个新的语音识别模型配置

**When**: 创建 ModelProfile 实例并设置必要参数
```python
profile = ModelProfile(
    profile_name="英文专用模型",
    model_path="/models/english-model.onnx",
    description="适用于英文语音识别的专用模型",
    supported_languages=["en"]
)
```

**Then**:
- ModelProfile 对象创建成功
- 自动生成唯一的 profile_id
- 自动设置 created_at 和 updated_at 时间戳

#### Scenario: 验证无效的模型配置

**Given**: ModelProfile 配置了不存在的模型文件路径

**When**: 调用 `profile.validate()` 方法

**Then**:
- 抛出 `ValueError` 异常
- 异常信息包含"模型文件不存在"

---

### Requirement: Config Model Extensions

**ID**: MODEL-MGMT-002

**Priority**: High

**Description**:
Config 数据类MUST扩展以支持多模型方案管理，包括模型方案字典和活跃方案ID。

**Acceptance Criteria**:
- Config 包含 `model_profiles: Dict[str, ModelProfile]` 字段
- Config 包含 `active_model_profile_id: str` 字段
- 提供 `get_active_model_profile()` 方法获取当前活跃方案
- 提供 `set_active_model_profile(profile_id)` 方法切换活跃方案
- 保留 `model_path` 字段用于向后兼容（标记为已弃用）

#### Scenario: 获取当前活跃的模型方案

**Given**: Config 配置了多个模型方案，active_model_profile_id 设置为 "english"

**When**: 调用 `config.get_active_model_profile()`

**Then**:
- 返回 ID 为 "english" 的 ModelProfile 对象
- 该对象包含完整的模型配置信息

#### Scenario: 切换到不存在的模型方案

**Given**: Config 的 model_profiles 不包含 ID 为 "nonexistent" 的方案

**When**: 调用 `config.set_active_model_profile("nonexistent")`

**Then**:
- 抛出 `ValueError` 异常
- 异常信息包含"模型方案 'nonexistent' 不存在"
- active_model_profile_id 保持不变

---

### Requirement: Configuration Migration

**ID**: MODEL-MGMT-003

**Priority**: High

**Description**:
系统MUST支持从旧版配置（单一 model_path）自动迁移到新版配置（model_profiles）。

**Acceptance Criteria**:
- 检测到旧版配置时自动执行迁移
- 从 model_path 创建默认模型方案（ID: "default"）
- 设置 active_model_profile_id 为 "default"
- 迁移完成后保留原 model_path 字段（向后兼容）
- 记录迁移日志

#### Scenario: 加载旧版配置文件

**Given**: 配置文件只包含 `model_path` 字段，不包含 `model_profiles`
```json
{
  "model_path": "/models/sense-voice.onnx",
  "input_source": "microphone"
}
```

**When**: 加载配置并验证

**Then**:
- 自动创建 model_profiles 字典
- 包含一个 ID 为 "default" 的方案
- 该方案的 model_path 为 "/models/sense-voice.onnx"
- active_model_profile_id 设置为 "default"
- 日志输出"配置迁移完成"

#### Scenario: 加载新版配置文件

**Given**: 配置文件已包含 model_profiles
```json
{
  "model_profiles": {
    "default": {...},
    "custom": {...}
  },
  "active_model_profile_id": "custom"
}
```

**When**: 加载配置

**Then**:
- 不触发迁移逻辑
- 直接使用配置中的 model_profiles
- 保持 active_model_profile_id 为 "custom"

---

### Requirement: Settings Dialog - Model Management UI

**ID**: MODEL-MGMT-004

**Priority**: High

**Description**:
设置对话框MUST提供模型方案管理界面，包括列表显示、增删改查操作。

**Acceptance Criteria**:
- 在设置对话框添加"模型"配置页
- 左侧显示模型方案列表（QListWidget）
- 右侧显示选中方案的参数编辑区域
- 提供操作按钮：新增、删除、复制、重命名
- 提供模型文件路径选择器（浏览按钮）
- 提供"验证模型"按钮
- 当前活跃方案在列表中标记

#### Scenario: 添加新模型方案

**Given**: 用户在设置对话框的模型页面

**When**:
1. 点击"新增"按钮
2. 输入方案名称"英文模型"
3. 选择模型文件路径"/models/english.onnx"
4. 输入描述信息
5. 点击"保存"

**Then**:
- 模型方案列表中显示"英文模型"
- 方案配置保存到 Config.model_profiles
- 配置文件自动保存

#### Scenario: 删除模型方案

**Given**: 模型列表中有 3 个方案：默认、英文、中文

**When**:
1. 选中"英文"方案
2. 点击"删除"按钮
3. 确认删除

**Then**:
- "英文"方案从列表中移除
- Config.model_profiles 中删除该方案
- 如果"英文"是活跃方案，自动切换到"默认"
- 配置文件自动保存

#### Scenario: 尝试删除唯一的模型方案

**Given**: 模型列表中只有 1 个方案

**When**: 选中该方案并点击"删除"按钮

**Then**:
- 显示警告消息"必须至少保留一个模型方案"
- 删除操作被阻止
- 方案保持不变

#### Scenario: 尝试删除默认方案

**Given**: 模型列表中包含 ID 为 "default" 的默认方案

**When**: 选中默认方案并点击"删除"按钮

**Then**:
- 显示警告消息"默认方案不能被删除"
- 删除操作被阻止

#### Scenario: 验证模型文件

**Given**: 用户在编辑模型方案，设置了模型路径

**When**: 点击"验证模型"按钮

**Then**:
- 检查文件是否存在
- 检查文件格式（.onnx 或 .bin）
- 检查文件大小（> 1MB）
- 显示验证结果对话框
- 如果验证失败，显示具体错误原因

---

### Requirement: Main Window - Model Selector

**ID**: MODEL-MGMT-005

**Priority**: High

**Description**:
主窗口MUST在高级设置面板中提供模型选择下拉框，支持快速切换模型。

**Acceptance Criteria**:
- 在高级设置面板添加模型选择下拉框（QComboBox）
- 下拉框显示所有可用模型方案的名称
- 当前活跃方案被选中
- 选择不同方案时触发切换逻辑
- 如果 Pipeline 正在运行，提示用户并请求确认
- 切换成功后更新状态栏

#### Scenario: 在主窗口切换模型

**Given**:
- 主窗口已打开
- 高级设置面板中的模型下拉框显示当前模型"默认"
- 转录未在运行

**When**:
1. 点击模型下拉框
2. 选择"英文专用模型"

**Then**:
- Config.active_model_profile_id 更新为 "english"
- Config.model_path 同步更新为英文模型的路径
- 配置自动保存
- 状态栏显示"已切换到模型: 英文专用模型"

#### Scenario: 运行中切换模型需要确认

**Given**:
- 转录正在运行（Pipeline.is_running = True）
- 用户想要切换到其他模型

**When**: 在模型下拉框中选择新模型

**Then**:
- 显示确认对话框"切换模型需要停止当前转录，是否继续？"
- 如果用户点击"是"：
  - 停止当前 Pipeline
  - 切换模型配置
  - 可选：自动重启 Pipeline
- 如果用户点击"否"：
  - 取消切换
  - 下拉框恢复到之前的选择

#### Scenario: 切换模型失败的处理

**Given**: 用户选择了一个模型配置，但模型文件已被删除或移动

**When**: 尝试切换到该模型

**Then**:
- 模型验证失败
- 显示错误对话框"无法切换模型: 模型文件不存在"
- 保持之前的模型配置
- 下拉框恢复到之前的选择

---

### Requirement: ConfigBridge Model Management Methods

**ID**: MODEL-MGMT-006

**Priority**: High

**Description**:
ConfigBridge MUST提供模型方案管理的桥接方法，连接 UI 和配置系统。

**Acceptance Criteria**:
- 提供 `switch_model_profile(profile_id)` 方法
- 提供 `add_model_profile(profile)` 方法
- 提供 `delete_model_profile(profile_id)` 方法
- 提供 `update_model_profile(profile_id, profile)` 方法
- 所有方法执行成功后自动保存配置
- 发射 `config_changed` 信号通知其他组件

#### Scenario: 通过 ConfigBridge 切换模型

**Given**: ConfigBridge 已初始化，Config 包含多个模型方案

**When**: 调用 `config_bridge.switch_model_profile("english")`

**Then**:
- Config.active_model_profile_id 更新为 "english"
- Config.model_path 同步更新
- 配置文件自动保存
- 发射 config_changed 信号
- 返回 True

#### Scenario: 通过 ConfigBridge 添加模型方案

**Given**:
- ConfigBridge 已初始化
- 创建了新的 ModelProfile 对象

**When**: 调用 `config_bridge.add_model_profile(new_profile)`

**Then**:
- 先调用 `new_profile.validate()` 验证
- 添加到 Config.model_profiles
- 配置文件自动保存
- 返回 True

#### Scenario: 添加无效的模型方案

**Given**: ModelProfile 配置了不存在的文件路径

**When**: 调用 `config_bridge.add_model_profile(invalid_profile)`

**Then**:
- 验证失败，抛出异常
- 不添加到 Config.model_profiles
- 记录错误日志
- 返回 False

---

### Requirement: Model Profile Validation

**ID**: MODEL-MGMT-007

**Priority**: High

**Description**:
系统MUST在添加或修改模型方案时执行完整的验证，确保配置有效性。

**Acceptance Criteria**:
- 验证方案名称非空
- 验证模型路径非空
- 验证模型文件存在且可读
- 验证文件格式为 .onnx 或 .bin
- 验证文件大小 > 1MB
- 提供清晰的错误信息

#### Scenario: 验证模型文件格式

**Given**: ModelProfile 配置了 model_path = "/models/test.txt"

**When**: 调用 `profile.validate()`

**Then**:
- 抛出 ValueError
- 错误信息："不支持的模型文件格式: .txt, 支持的格式: .onnx, .bin"

#### Scenario: 验证模型文件大小

**Given**: ModelProfile 配置了一个仅 500KB 的 .onnx 文件

**When**: 调用 `profile.validate()`

**Then**:
- 抛出 ValueError
- 错误信息："模型文件过小 (0.49MB), 可能不是有效的模型文件"

#### Scenario: 验证方案名称

**Given**: ModelProfile 的 profile_name 为空字符串 ""

**When**: 调用 `profile.validate()`

**Then**:
- 抛出 ValueError
- 错误信息："模型方案名称不能为空"

---

### Requirement: Configuration Persistence

**ID**: MODEL-MGMT-008

**Priority**: Medium

**Description**:
模型方案配置MUST正确地序列化到配置文件并在重启后恢复。

**Acceptance Criteria**:
- model_profiles 完整序列化到 JSON
- 时间戳字段正确序列化（ISO 8601 格式）
- 配置加载时正确反序列化
- 支持配置文件备份和恢复

#### Scenario: 保存模型方案到配置文件

**Given**: Config 包含 2 个模型方案

**When**: 调用 `config_bridge.save_config(config)`

**Then**:
- 配置文件包含完整的 model_profiles 字段
- 每个方案的所有字段都被保存
- 时间戳以 ISO 8601 格式保存
- 文件格式正确（有效的 JSON）

#### Scenario: 从配置文件加载模型方案

**Given**: 配置文件包含 model_profiles 数据

**When**: 调用 `config_bridge.load_config()`

**Then**:
- Config.model_profiles 包含所有保存的方案
- 每个 ModelProfile 对象完整恢复
- 时间戳正确解析为 datetime 对象
- active_model_profile_id 正确恢复

---

## Dependencies

### Internal
- `src/config/models.py` - 数据模型定义
- `src/gui/dialogs/settings_dialog.py` - UI 实现
- `src/gui/main_window.py` - 主窗口集成
- `src/gui/bridges/config_bridge.py` - 桥接层

### External
- PySide6 - UI 框架
- Python dataclasses - 数据模型
- pathlib - 文件路径处理

## Non-Functional Requirements

### Performance
- 模型列表加载时间 < 50ms
- 模型切换响应时间 < 200ms
- 配置文件读写 < 100ms

### Usability
- 模型切换操作不超过 2 次点击
- 提供清晰的错误提示
- 保持与 VAD 方案管理一致的 UI 风格

### Reliability
- 配置迁移成功率 100%
- 防止删除唯一的模型方案
- 防止删除默认方案

### Maintainability
- 代码复用 VAD 方案管理的模式
- 清晰的代码注释
- 完整的单元测试覆盖

## Future Considerations

- 模型自动扫描功能
- 模型性能基准测试
- 模型参数配置（温度、束搜索等）
- 云端模型仓库集成
