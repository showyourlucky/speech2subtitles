# VAD Specification Deltas

## ADDED Requirements

### Requirement: VAD配置方案管理

系统 SHALL 支持创建、保存和管理多个命名的VAD配置方案,允许用户针对不同场景快速切换VAD参数组合。

#### Scenario: 创建新的VAD方案

- **GIVEN** 用户打开VAD设置对话框
- **WHEN** 用户点击"新建方案"按钮并输入方案名称(如"会议室")
- **THEN** 系统应创建新的VadProfile实例
- **AND** 使用当前默认参数初始化
- **AND** 将新方案添加到方案列表
- **AND** 自动选中新创建的方案

#### Scenario: 编辑VAD方案参数

- **GIVEN** 用户选中某个VAD方案
- **WHEN** 用户修改任意参数(如threshold从0.5改为0.7)
- **THEN** 系统应实时更新该方案的参数
- **AND** 标记方案为"已修改"状态(未保存)

#### Scenario: 删除VAD方案

- **GIVEN** 用户选中某个非默认VAD方案
- **WHEN** 用户点击"删除方案"按钮并确认
- **THEN** 系统应从方案列表中移除该方案
- **AND** 自动选中"默认"方案
- **AND** 如果删除的是当前活跃方案,切换活跃方案为"默认"

#### Scenario: 保护默认方案

- **GIVEN** 用户选中"默认"VAD方案
- **WHEN** 用户尝试删除该方案
- **THEN** 系统应显示错误提示"默认方案不可删除"
- **AND** 不执行删除操作

#### Scenario: 重命名VAD方案

- **GIVEN** 用户选中某个VAD方案
- **WHEN** 用户点击"重命名"按钮并输入新名称
- **THEN** 系统应更新方案的display_name
- **AND** profile_id保持不变(确保引用稳定)
- **AND** 方案列表显示新名称

#### Scenario: 复制VAD方案

- **GIVEN** 用户选中某个VAD方案
- **WHEN** 用户点击"复制方案"按钮
- **THEN** 系统应创建该方案的完整副本
- **AND** 新方案名称为"原方案名 - 副本"
- **AND** 生成新的唯一profile_id
- **AND** 将副本添加到方案列表

### Requirement: VAD方案完整参数支持

系统 SHALL 在GUI中提供所有sherpa-onnx VAD初始化所需的参数配置,确保GUI参数与底层检测器完全一致。

#### Scenario: 配置VAD阈值

- **GIVEN** 用户编辑VAD方案
- **WHEN** 用户调整"阈值(threshold)"滑块
- **THEN** 系统应接受0.0-1.0范围内的值
- **AND** 实时显示当前数值
- **AND** 该参数应映射到`vad_config.silero_vad.threshold`

#### Scenario: 配置最小语音持续时间

- **GIVEN** 用户编辑VAD方案
- **WHEN** 用户设置"最小语音持续时间"为200ms
- **THEN** 系统应接受正整数值(单位毫秒)
- **AND** 该参数应映射到`vad_config.silero_vad.min_speech_duration`(转换为秒)
- **AND** 验证该值小于最大语音持续时间

#### Scenario: 配置最小静音持续时间

- **GIVEN** 用户编辑VAD方案
- **WHEN** 用户设置"最小静音持续时间"为150ms
- **THEN** 系统应接受正整数值(单位毫秒)
- **AND** 该参数应映射到`vad_config.silero_vad.min_silence_duration`(转换为秒)

#### Scenario: 配置最大语音持续时间

- **GIVEN** 用户编辑VAD方案
- **WHEN** 用户设置"最大语音持续时间"为30000ms
- **THEN** 系统应接受正整数值(单位毫秒)
- **AND** 该参数应映射到`vad_config.silero_vad.max_speech_duration`(转换为秒)
- **AND** 验证该值大于最小语音持续时间

#### Scenario: 选择VAD模型类型

- **GIVEN** 用户编辑VAD方案
- **WHEN** 用户在"模型类型"下拉框中选择"SILERO"或"TEN_VAD"
- **THEN** 系统应更新`VadConfig.model`字段
- **AND** 根据模型类型调整可用参数(如TEN_VAD特有参数)

#### Scenario: 配置采样率

- **GIVEN** 用户编辑VAD方案
- **WHEN** 用户选择采样率(8000/16000/48000 Hz)
- **THEN** 系统应更新`VadConfig.sample_rate`字段
- **AND** 该参数应映射到`vad_config.sample_rate`

#### Scenario: 配置自定义模型路径

- **GIVEN** 用户编辑VAD方案
- **WHEN** 用户点击"浏览"按钮选择自定义VAD模型文件(.onnx)
- **THEN** 系统应更新`VadConfig.model_path`字段
- **AND** 如果model_path为空,使用模型类型的默认路径
- **AND** 验证文件存在且为有效的ONNX文件

### Requirement: 主界面VAD方案快速切换

系统 SHALL 在主窗口提供VAD方案选择控件,支持用户在运行时快速切换活跃的VAD配置方案。

#### Scenario: 显示可用VAD方案列表

- **GIVEN** 应用启动完成
- **WHEN** 用户查看主窗口控制面板
- **THEN** 应显示VAD方案选择下拉框
- **AND** 下拉框列出所有已保存的方案名称
- **AND** 当前活跃方案应被高亮/选中

#### Scenario: 切换VAD方案(Pipeline未运行)

- **GIVEN** TranscriptionPipeline未运行
- **WHEN** 用户在下拉框中选择不同的VAD方案
- **THEN** 系统应更新`Config.active_vad_profile_id`
- **AND** 保存配置到文件
- **AND** 下次启动Pipeline时使用新方案

#### Scenario: 切换VAD方案(Pipeline运行中)

- **GIVEN** TranscriptionPipeline正在运行
- **WHEN** 用户尝试切换VAD方案
- **THEN** 系统应显示提示"切换VAD方案需要重启转录,是否继续?"
- **AND** 如果用户确认,停止Pipeline并应用新方案
- **AND** 如果用户取消,保持当前方案不变

#### Scenario: 快捷打开VAD设置

- **GIVEN** 用户在主窗口
- **WHEN** 用户点击VAD方案选择器旁的"设置"按钮
- **THEN** 系统应打开设置对话框
- **AND** 自动跳转到VAD配置页面
- **AND** 高亮当前活跃方案

### Requirement: 配置文件版本迁移

系统 SHALL 自动检测旧版配置文件并将其VAD参数迁移为新的方案管理格式,确保平滑升级。

#### Scenario: 检测旧版配置文件

- **GIVEN** 用户首次启动新版本应用
- **AND** 配置文件中存在`vad_sensitivity`、`vad_threshold`等旧字段
- **AND** 缺少`vad_profiles`字段
- **WHEN** 系统加载配置
- **THEN** 应识别为旧版配置文件

#### Scenario: 自动迁移VAD配置

- **GIVEN** 检测到旧版配置文件
- **WHEN** 系统执行配置迁移
- **THEN** 应创建名为"默认"的VadProfile
- **AND** 将旧字段值映射到VadProfile参数:
  - `vad_threshold` → `threshold`
  - `sample_rate` → `sample_rate`
  - 其他参数使用VadConfig默认值
- **AND** 设置`active_vad_profile_id = "default"`
- **AND** 保存迁移后的配置文件

#### Scenario: 清理废弃字段

- **GIVEN** 配置迁移完成
- **WHEN** 系统保存新配置文件
- **THEN** 不应包含`vad_sensitivity`字段
- **AND** 不应包含`vad_window_size`字段
- **AND** 保留所有非VAD相关的配置

### Requirement: VadProfile数据模型

系统 SHALL 定义VadProfile数据类,封装完整的VAD配置参数并提供转换方法。

#### Scenario: 创建VadProfile实例

- **GIVEN** 系统需要新建VAD方案
- **WHEN** 调用`VadProfile`构造函数
- **THEN** 应创建包含以下字段的实例:
  - `profile_id: str` (唯一标识符)
  - `profile_name: str` (显示名称)
  - `model: VadModel` (模型类型)
  - `model_path: Optional[str]` (自定义模型路径,None时使用默认路径)
  - `threshold: float` (阈值)
  - `min_speech_duration_ms: float` (最小语音时长)
  - `min_silence_duration_ms: float` (最小静音时长)
  - `max_speech_duration_ms: float` (最大语音时长)
  - `sample_rate: int` (采样率)
  - `use_sherpa_onnx: bool` (是否使用sherpa-onnx)

#### Scenario: 转换为VadConfig

- **GIVEN** 存在有效的VadProfile实例
- **WHEN** 调用`profile.to_vad_config()`方法
- **THEN** 应返回VadConfig对象
- **AND** 所有参数值应正确映射
- **AND** 返回的VadConfig应通过`validate()`验证

#### Scenario: VadProfile验证

- **GIVEN** 创建或修改VadProfile
- **WHEN** 调用`profile.validate()`方法
- **THEN** 应验证所有参数在有效范围内
- **AND** `min_speech_duration_ms < max_speech_duration_ms`
- **AND** `threshold`在0.0-1.0范围内
- **AND** 如果验证失败,抛出ConfigurationError异常

## MODIFIED Requirements

### Requirement: 配置持久化

系统 SHALL 支持将VAD方案列表和活跃方案ID持久化到配置文件,并在加载时恢复。

**修改说明:** 扩展现有的`ConfigFileManager`以支持`vad_profiles`字段的序列化。

#### Scenario: 保存包含VAD方案的配置

- **GIVEN** Config对象包含多个VadProfile
- **WHEN** 调用`config_file_manager.save_config(config)`
- **THEN** JSON文件应包含`vad_profiles`字段
- **AND** `vad_profiles`应为字典,key为profile_id,value为VadProfile的JSON表示
- **AND** 应包含`active_vad_profile_id`字段

#### Scenario: 加载包含VAD方案的配置

- **GIVEN** 配置文件包含`vad_profiles`字段
- **WHEN** 调用`config_file_manager.load_config()`
- **THEN** 应正确反序列化为`Dict[str, VadProfile]`
- **AND** 恢复`active_vad_profile_id`
- **AND** 如果active_vad_profile_id不存在于profiles中,回退到"default"

### Requirement: Pipeline VAD初始化

TranscriptionPipeline SHALL 使用活跃VAD方案的参数初始化VAD检测器,而非直接使用Config中的简化字段。

**修改说明:** 更新Pipeline构造VAD检测器的逻辑。

#### Scenario: 从活跃方案构建VadConfig

- **GIVEN** Config.active_vad_profile_id为"meeting_room"
- **AND** vad_profiles["meeting_room"]存在
- **WHEN** Pipeline初始化VAD检测器
- **THEN** 应调用`config.vad_profiles[config.active_vad_profile_id].to_vad_config()`
- **AND** 使用返回的VadConfig创建检测器
- **AND** 不应使用废弃的`config.vad_sensitivity`等字段

#### Scenario: 活跃方案缺失时的降级处理

- **GIVEN** Config.active_vad_profile_id指向不存在的方案
- **WHEN** Pipeline尝试初始化VAD检测器
- **THEN** 系统应记录警告日志
- **AND** 回退到"default"方案
- **AND** 如果"default"也不存在,使用VadConfig默认值

## REMOVED Requirements

### Requirement: 简化VAD参数配置

**移除原因:** 简化的`vad_sensitivity`和`vad_window_size`参数无法映射到sherpa-onnx的实际初始化参数,造成配置gap和用户困惑。

**迁移路径:**
- 旧配置中的`vad_threshold`保留并映射到VadProfile.threshold
- `vad_sensitivity`字段废弃,其语义由`threshold`和`min_speech_duration_ms`组合表达
- `vad_window_size`字段废弃,VAD窗口由sherpa-onnx内部管理

**影响范围:**
- `src/config/models.py:Config` - 移除`vad_sensitivity`和`vad_window_size`字段
- `src/gui/dialogs/settings_dialog.py` - 移除对应的UI控件和加载/收集逻辑
