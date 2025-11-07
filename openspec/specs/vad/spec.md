# VAD (Voice Activity Detection) 模块规范

## Purpose

VAD 模块负责实时语音活动检测，区分语音和非语音音频段，为转录引擎提供预处理支持。通过智能检测语音边界，过滤静音段，优化转录效率和准确性。
## Requirements
### Requirement: 语音活动检测

系统 SHALL 提供基于 Silero VAD 或 Ten VAD 模型的实时语音活动检测功能。

#### Scenario: 检测语音段

- **GIVEN** 音频流包含语音和静音
- **WHEN** VAD 检测器处理音频数据
- **THEN** 应正确识别语音段
- **AND** 返回语音活动结果

#### Scenario: 检测静音段

- **GIVEN** 音频流仅包含静音或噪声
- **WHEN** VAD 检测器处理音频数据
- **THEN** 应正确识别静音段
- **AND** 不触发语音活动事件

### Requirement: 可配置的检测参数

系统 SHALL 支持通过 VadConfig 配置检测参数，包括阈值、采样率等。

#### Scenario: 配置检测阈值

- **GIVEN** 用户设置 threshold 为 0.5
- **WHEN** 创建 VAD 检测器
- **THEN** 检测器应使用指定的阈值
- **AND** 检测灵敏度应符合预期

#### Scenario: 配置采样率

- **GIVEN** 用户设置 sample_rate 为 16000
- **WHEN** 创建 VAD 检测器
- **THEN** 检测器应处理 16kHz 采样率的音频

### Requirement: 回调机制

系统 SHALL 支持通过回调函数接收 VAD 检测结果。

#### Scenario: 注册回调函数

- **GIVEN** VAD 检测器已初始化
- **WHEN** 用户注册回调函数
- **THEN** 检测结果应通过回调函数传递

#### Scenario: 移除回调函数

- **GIVEN** VAD 检测器已注册回调函数
- **WHEN** 用户移除回调函数
- **THEN** 该回调应不再接收检测结果

### Requirement: 状态管理

系统 SHALL 维护 VAD 检测状态（SILENCE/SPEECH/TRANSITION）。

#### Scenario: 状态转换

- **GIVEN** 当前状态为 SILENCE
- **WHEN** 检测到语音活动
- **THEN** 状态应转换为 TRANSITION_TO_SPEECH
- **AND** 持续检测到语音后应转换为 SPEECH

### Requirement: 统计信息

系统 SHALL 提供 VAD 处理统计信息，包括处理时长、语音段数量等。

#### Scenario: 获取统计信息

- **GIVEN** VAD 检测器已处理音频数据
- **WHEN** 调用 get_statistics()
- **THEN** 应返回包含处理时长、语音段数等信息的统计对象

### Requirement: 模型支持

系统 SHALL 支持多种 VAD 模型（Silero VAD、Ten VAD）。

#### Scenario: 使用 Silero VAD 模型

- **GIVEN** 配置指定 VadModel.SILERO
- **WHEN** 初始化检测器
- **THEN** 应加载 Silero VAD 模型

#### Scenario: 使用 sherpa-onnx 实现

- **GIVEN** 配置设置 use_sherpa_onnx=True
- **WHEN** 初始化检测器
- **THEN** 应使用 sherpa-onnx 框架实现

### Requirement: 错误处理

系统 SHALL 提供明确的错误处理和异常类型。

#### Scenario: 模型加载失败

- **GIVEN** 模型文件不存在或损坏
- **WHEN** 初始化 VAD 检测器
- **THEN** 应抛出 ModelLoadError 异常
- **AND** 错误信息应包含失败原因

#### Scenario: 检测过程出错

- **GIVEN** VAD 检测器正在运行
- **WHEN** 检测过程中发生错误
- **THEN** 应抛出 DetectionError 异常
- **AND** 应记录错误日志

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

