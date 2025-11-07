# VAD 模块规范增量

## ADDED Requirements

### Requirement: VAD 检测器单例管理

系统 SHALL 提供 VadManager 单例类来管理 VAD 检测器的生命周期，实现智能复用和统一资源管理。

#### Scenario: 首次获取检测器

- **GIVEN** VadManager 尚未加载任何检测器
- **AND** 用户提供有效的 VadConfig
- **WHEN** 调用 VadManager.get_detector(config)
- **THEN** 系统应加载新的 VAD 检测器
- **AND** 统计信息中 detector_loads 应增加 1
- **AND** 返回可用的 VoiceActivityDetector 实例

#### Scenario: 复用已加载的检测器

- **GIVEN** VadManager 已加载配置为 config_A 的检测器
- **WHEN** 再次调用 VadManager.get_detector(config_A)（配置相同）
- **THEN** 系统应返回已缓存的检测器实例
- **AND** 统计信息中 detector_reuses 应增加 1
- **AND** 不应重新加载模型

#### Scenario: 配置变更触发重新加载

- **GIVEN** VadManager 已加载配置为 config_A 的检测器
- **WHEN** 调用 VadManager.get_detector(config_B)（配置不同）
- **THEN** 系统应释放旧检测器
- **AND** 加载新的 VAD 检测器
- **AND** 统计信息中 detector_loads 应增加 1

### Requirement: 配置变更检测

VadManager SHALL 自动检测关键配置参数的变化，以决定是否需要重新加载模型。

#### Scenario: 检测模型类型变化

- **GIVEN** 当前配置使用 VadModel.SILERO
- **WHEN** 新配置使用 VadModel.TEN_VAD
- **THEN** _should_reload() 应返回 True

#### Scenario: 检测阈值变化

- **GIVEN** 当前配置的 threshold 为 0.5
- **WHEN** 新配置的 threshold 为 0.7
- **THEN** _should_reload() 应返回 True

#### Scenario: 配置未变化

- **GIVEN** 当前配置为 VadConfig(threshold=0.5, sample_rate=16000)
- **WHEN** 新配置为 VadConfig(threshold=0.5, sample_rate=16000)
- **THEN** _should_reload() 应返回 False

### Requirement: 线程安全

VadManager SHALL 提供线程安全的并发访问保护，支持多线程同时获取检测器。

#### Scenario: 多线程并发访问

- **GIVEN** 5 个线程同时调用 VadManager.get_detector(config)
- **WHEN** 所有线程完成调用
- **THEN** 所有线程应获得相同的检测器实例
- **AND** 仅应加载一次模型
- **AND** 不应发生竞态条件

### Requirement: 统计信息收集

VadManager SHALL 收集并提供检测器使用统计信息，用于性能监控和诊断。

#### Scenario: 获取统计信息

- **GIVEN** VadManager 已执行 2 次加载和 3 次复用
- **WHEN** 调用 VadManager.get_statistics()
- **THEN** 返回的字典应包含以下字段：
  - detector_loads = 2
  - detector_reuses = 3
  - last_load_time（时间戳）
  - current_model（模型类型字符串）
  - has_detector（布尔值）

#### Scenario: 检查检测器加载状态

- **GIVEN** VadManager 已加载检测器
- **WHEN** 调用 VadManager.is_detector_loaded()
- **THEN** 应返回 True

### Requirement: 资源释放管理

VadManager SHALL 提供统一的资源释放方法，用于应用退出时清理资源。

#### Scenario: 释放已加载的检测器

- **GIVEN** VadManager 已加载检测器
- **WHEN** 调用 VadManager.release()
- **THEN** 检测器应被释放
- **AND** is_detector_loaded() 应返回 False

#### Scenario: 释放未加载的检测器

- **GIVEN** VadManager 未加载任何检测器
- **WHEN** 调用 VadManager.release()
- **THEN** 不应抛出异常
- **AND** 应记录调试日志

### Requirement: Pipeline 集成

TranscriptionPipeline SHALL 使用 VadManager 来获取 VAD 检测器，而不是直接实例化。

#### Scenario: Pipeline 初始化时获取检测器

- **GIVEN** TranscriptionPipeline 正在初始化
- **AND** 提供了有效的 VadConfig
- **WHEN** Pipeline 需要创建 VAD 检测器
- **THEN** 应调用 VadManager.get_detector(config)
- **AND** 不应直接调用 VoiceActivityDetector(config)

#### Scenario: Pipeline 重启时复用检测器

- **GIVEN** Pipeline 已停止
- **AND** 用户再次启动 Pipeline（配置未变）
- **WHEN** Pipeline 重新初始化
- **THEN** VadManager 应返回缓存的检测器
- **AND** 启动速度应显著快于首次启动

### Requirement: 向后兼容性

系统 SHALL 保持向后兼容性，允许现有代码继续直接使用 VoiceActivityDetector。

#### Scenario: 直接实例化仍然可用

- **GIVEN** 用户代码直接使用 VoiceActivityDetector(config)
- **WHEN** 执行代码
- **THEN** 应正常工作
- **AND** 不应影响 VadManager 的功能

#### Scenario: 渐进式迁移

- **GIVEN** 项目中部分代码使用 VadManager
- **AND** 部分代码仍直接使用 VoiceActivityDetector
- **WHEN** 运行应用
- **THEN** 两种方式应能正常共存
- **AND** VadManager 管理的实例与直接创建的实例互不干扰
