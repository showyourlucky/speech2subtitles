# Proposal: Add Model Profile Management

## Summary

添加模型配置方案管理功能，允许用户创建、管理和切换多个语音识别模型配置。类似于现有的VAD方案管理，用户可以保存多个模型配置（包括模型路径、名称、参数等），并在主界面快速选择切换。

## Motivation

**当前问题：**
- 配置系统只支持单一模型路径 (`Config.model_path`)
- 用户需要频繁切换不同模型时，需要手动修改配置文件或重新输入路径
- 无法为不同的使用场景保存不同的模型配置
- 缺少模型元数据管理（如模型名称、描述、支持的语言等）

**用户场景：**
1. **多模型实验**：研究人员需要快速切换不同模型进行对比测试
2. **多语言支持**：用户需要针对不同语言使用专门的模型
3. **性能优化**：在不同硬件条件下切换不同大小/精度的模型
4. **快速切换**：日常使用中根据场景快速切换预配置的模型

**解决方案：**
- 引入 `ModelProfile` 数据类，存储单个模型的完整配置
- 在 `Config` 中添加 `model_profiles` 字典和 `active_model_profile_id`
- 在设置对话框中提供模型列表管理UI（增删改查）
- 在主窗口添加模型选择下拉框，支持快速切换

## Goals

### Primary Goals
- ✅ 支持创建和管理多个模型配置方案
- ✅ 在设置对话框中提供模型列表的增删改功能
- ✅ 在主界面提供下拉框快速切换模型
- ✅ 保持与现有VAD方案管理的一致性
- ✅ 向后兼容现有的 `model_path` 配置

### Non-Goals
- ❌ 自动下载或安装模型
- ❌ 模型格式转换功能
- ❌ 模型性能基准测试
- ❌ 多模型并行运行

## Design Constraints

### Technical Constraints
- 必须保持与现有配置系统的兼容性
- 模型文件验证必须在加载前完成
- UI设计必须与VAD方案管理保持一致风格
- 配置序列化/反序列化必须支持JSON格式

### User Experience Constraints
- 主界面的模型切换操作不应超过2次点击
- 设置对话框必须提供清晰的模型列表和操作按钮
- 必须防止删除当前正在使用的模型配置
- 必须提供默认模型配置，确保首次使用体验

## User Impact

### End Users
- **正面影响**：
  - 模型管理更便捷，支持快速切换
  - 可以为不同场景预设模型配置
  - 无需记忆复杂的模型文件路径

- **学习成本**：
  - 新用户需要理解"模型方案"概念（类似VAD方案）
  - 需要学习如何添加和管理模型配置

- **迁移路径**：
  - 现有的 `model_path` 配置自动迁移为"默认"方案
  - 不影响已有配置文件的加载

### Developers
- 需要实现 `ModelProfile` 数据类
- 需要在 `Config` 中添加方案管理字段
- 需要扩展 `SettingsDialog` 添加模型管理页面
- 需要在 `MainWindow` 添加模型选择组件
- 需要编写配置迁移逻辑

## Implementation Strategy

### Phased Rollout
1. **Phase 1 - 数据模型** (Day 1)
   - 实现 `ModelProfile` 数据类
   - 扩展 `Config` 添加方案管理字段
   - 实现配置验证和迁移逻辑

2. **Phase 2 - 设置对话框** (Day 2)
   - 在 `SettingsDialog` 中添加模型管理页面
   - 实现模型列表显示和选择
   - 实现增删改操作

3. **Phase 3 - 主界面集成** (Day 3)
   - 在 `MainWindow` 添加模型选择下拉框
   - 实现模型切换逻辑
   - 连接信号槽

4. **Phase 4 - 测试和文档** (Day 4)
   - 编写单元测试
   - 编写集成测试
   - 更新用户文档

### Backwards Compatibility
- 旧配置文件的 `model_path` 字段自动转换为默认模型方案
- 如果未指定 `model_profiles`，系统自动创建包含默认方案的字典
- 保留 `Config.model_path` 字段，但标记为已弃用（用于向后兼容）

### Migration Path
```python
# 配置加载时的迁移逻辑
if config.model_profiles is None or len(config.model_profiles) == 0:
    # 从旧版 model_path 创建默认方案
    default_profile = ModelProfile(
        profile_name="默认",
        profile_id="default",
        model_path=config.model_path
    )
    config.model_profiles = {"default": default_profile}
    config.active_model_profile_id = "default"
```

## Dependencies

### Internal Dependencies
- `src/config/models.py` - 数据模型定义
- `src/config/manager.py` - 配置管理器
- `src/gui/dialogs/settings_dialog.py` - 设置对话框
- `src/gui/main_window.py` - 主窗口
- `src/gui/bridges/config_bridge.py` - 配置桥接器

### External Dependencies
- 无新增外部依赖

### Blocked By
- 无阻塞项

### Blocks
- 无被阻塞项

## Alternatives Considered

### Alternative 1: 使用配置文件模板
**描述**：提供多个预设配置文件，用户复制并修改

**优点**：
- 实现简单，无需修改数据模型
- 灵活性高，用户可以完全自定义

**缺点**：
- 用户体验差，需要手动编辑文件
- 无法在GUI中直观管理
- 容易出现配置错误

**决策**：不采用，用户体验不佳

### Alternative 2: 命令行参数切换
**描述**：通过命令行参数动态指定模型路径

**优点**：
- 无需修改配置系统
- 适合脚本自动化

**缺点**：
- GUI用户无法使用
- 无法保存配置方案
- 每次启动都需要指定参数

**决策**：不采用，不符合GUI用户需求

### Alternative 3: 模型目录自动扫描
**描述**：自动扫描指定目录下的所有模型文件

**优点**：
- 无需手动添加模型
- 自动发现新模型

**缺点**：
- 无法添加模型元数据
- 可能扫描到无效模型
- 性能开销大

**决策**：不采用，可作为未来增强功能

## Success Metrics

### Technical Metrics
- 模型配置加载时间 < 100ms
- 模型切换响应时间 < 200ms
- 配置文件大小增长 < 1KB per profile
- 单元测试覆盖率 > 90%

### User Metrics
- 模型切换操作次数减少 50%（相比手动修改配置）
- 用户反馈：模型管理功能满意度 > 4.0/5.0
- 首次使用时间 < 2分钟（包含添加第一个自定义模型）

### Acceptance Criteria
- ✅ 用户可以在设置对话框中添加、删除、编辑模型配置
- ✅ 用户可以在主界面下拉框中选择和切换模型
- ✅ 模型切换后转录使用新模型
- ✅ 配置自动保存，重启后保持
- ✅ 旧配置文件自动迁移到新格式
- ✅ 至少保留一个模型配置（防止全部删除）
- ✅ 提供默认模型配置
- ✅ 模型文件路径验证正确

## Open Questions

1. **Q: 是否需要支持模型参数配置（如温度、束搜索等）？**
   - **A**: 当前版本不支持，可作为未来增强功能
   - **Reason**: sherpa-onnx模型参数通常在模型文件中固定

2. **Q: 是否需要支持模型别名/标签？**
   - **A**: 通过 `profile_name` 字段实现，用户可以自定义名称
   - **Reason**: 足够满足基本需求，避免过度设计

3. **Q: 是否需要模型元数据（支持语言、模型大小等）？**
   - **A**: 当前版本添加基本字段（描述、语言），详细元数据未来扩展
   - **Reason**: 保持KISS原则，满足核心需求

4. **Q: 模型切换是否需要重启Pipeline？**
   - **A**: 是的，需要停止当前Pipeline并重新初始化
   - **Reason**: TranscriptionEngine在初始化时加载模型，无法热切换

## Timeline

- **Week 1**: Phase 1-2 (数据模型 + 设置对话框)
- **Week 2**: Phase 3-4 (主界面集成 + 测试)
- **Total**: 2 weeks

## Risks and Mitigations

### Risk 1: 配置迁移失败
**Impact**: 高 - 用户无法加载旧配置
**Probability**: 中
**Mitigation**:
- 充分测试迁移逻辑
- 提供配置备份机制
- 失败时回退到默认配置

### Risk 2: 模型切换导致Pipeline崩溃
**Impact**: 高 - 用户无法使用系统
**Probability**: 低
**Mitigation**:
- 切换前验证模型文件
- 使用try-catch捕获异常
- 失败时回退到之前的模型

### Risk 3: UI复杂度增加
**Impact**: 中 - 用户学习成本增加
**Probability**: 中
**Mitigation**:
- 保持与VAD方案管理一致的UI设计
- 提供清晰的操作说明
- 提供默认配置，降低初次使用门槛

## Approval

- **Author**: AI Assistant
- **Reviewers**: [待分配]
- **Status**: Draft
- **Last Updated**: 2025-11-13
