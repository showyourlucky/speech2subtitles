# subtitle-display Specification

## Purpose
TBD - created by archiving change add-subtitle-singleton-pattern. Update Purpose after archive.
## Requirements
### Requirement: 单例模式实例管理

字幕显示组件 SHALL 使用单例模式，确保整个应用程序生命周期内只存在一个字幕窗口实例。

#### Scenario: 首次获取实例创建单例

- **WHEN** 应用程序首次调用 `get_subtitle_display_instance(config)` 或 `SubtitleDisplay(config)`
- **THEN** 系统创建唯一的字幕显示实例
- **AND** 返回该实例的引用

#### Scenario: 重复获取实例返回同一对象

- **WHEN** 应用程序在不同组件中多次调用 `get_subtitle_display_instance(config)`
- **THEN** 系统返回相同的字幕显示实例
- **AND** 不创建新的GUI窗口或线程

#### Scenario: 配置更新应用到现有实例

- **WHEN** 调用 `get_subtitle_display_instance(new_config)` 传入新配置
- **AND** 单例已经存在
- **THEN** 系统使用新配置更新现有实例的显示参数（位置、字体、透明度等）
- **AND** 不创建新实例

### Requirement: 线程安全的单例初始化

单例初始化过程 MUST 是线程安全的，防止并发调用时创建多个实例。

#### Scenario: 并发初始化仅创建一个实例

- **WHEN** 多个线程同时首次调用 `get_subtitle_display_instance(config)`
- **THEN** 只有一个线程成功创建实例
- **AND** 其他线程等待并获取相同的实例引用
- **AND** 最终所有线程持有同一个对象

#### Scenario: 线程竞争不导致资源泄漏

- **WHEN** 并发初始化发生线程竞争
- **THEN** 未被采用的实例立即释放资源（关闭GUI线程、销毁窗口）
- **AND** 不存在多余的后台线程或窗口

### Requirement: 单例生命周期管理

单例 SHALL 提供明确的生命周期管理方法，支持重置和资源清理。

#### Scenario: 手动重置单例用于重启

- **WHEN** 调用 `reset_subtitle_display_instance()`
- **THEN** 当前单例实例被标记为无效
- **AND** 停止字幕显示并清理GUI资源
- **AND** 下次调用 `get_subtitle_display_instance()` 将创建新实例

#### Scenario: 应用退出时自动清理资源

- **WHEN** 应用程序退出或模块卸载
- **THEN** 单例自动停止字幕显示
- **AND** 关闭GUI线程和窗口
- **AND** 释放所有相关资源

### Requirement: 向后兼容的接口

新的单例实现 MUST 保持向后兼容，支持现有的直接实例化方式。

#### Scenario: 直接构造函数调用返回单例

- **WHEN** 代码使用 `SubtitleDisplay(config)` 直接实例化
- **THEN** 系统返回单例实例（而非创建新对象）
- **AND** 行为与 `get_subtitle_display_instance(config)` 一致

#### Scenario: 向后兼容现有方法调用

- **WHEN** 调用单例实例的 `start()`, `stop()`, `show_subtitle()` 等方法
- **THEN** 方法行为与非单例实现完全一致
- **AND** 不引入任何API破坏性变更

### Requirement: 单例失败降级策略

当单例模式无法正常工作时，系统 SHALL 降级到多实例模式并记录警告。

#### Scenario: 单例初始化失败时创建独立实例

- **WHEN** 单例管理器因异常无法维护单例状态
- **THEN** 系统记录错误日志
- **AND** 降级创建独立的字幕显示实例
- **AND** 记录警告提示可能存在多窗口问题

#### Scenario: 降级模式不阻塞应用运行

- **WHEN** 单例模式降级到多实例模式
- **THEN** 应用程序继续正常运行
- **AND** 字幕显示功能仍然可用
- **AND** 仅在日志中记录降级警告

### Requirement: 字幕窗口基本显示功能

字幕显示组件 SHALL 提供透明悬浮窗口，支持可配置的位置、字体和样式。

#### Scenario: 显示字幕文本到屏幕

- **WHEN** 调用 `show_subtitle(text="你好世界", confidence=0.95)`
- **THEN** 屏幕上显示包含文本"你好世界"的半透明字幕窗口
- **AND** 窗口位置符合配置的位置参数（top/center/bottom）
- **AND** 文本使用配置的字体、大小和颜色

#### Scenario: 自动清除过期字幕

- **WHEN** 显示字幕后经过配置的 `max_display_time` 秒
- **THEN** 字幕窗口自动清除文本或隐藏
- **AND** 不需要手动调用清除方法

#### Scenario: 新字幕替换旧字幕

- **WHEN** 字幕显示过程中调用 `show_subtitle()` 显示新文本
- **THEN** 旧字幕立即被新字幕替换
- **AND** 重置自动清除定时器
- **AND** 不会出现多条字幕同时显示

### Requirement: 线程安全的字幕更新

字幕显示更新操作 MUST 是线程安全的，支持从任意线程调用。

#### Scenario: 多线程并发更新字幕

- **WHEN** 不同线程同时调用 `show_subtitle()` 更新字幕
- **THEN** 所有更新操作按顺序正确处理
- **AND** 不会导致GUI线程崩溃或界面错乱
- **AND** 最终显示的是最新的字幕内容

#### Scenario: 非GUI线程安全调用显示方法

- **WHEN** 从音频处理线程或转录线程调用 `show_subtitle()`
- **THEN** 方法调用不会抛出线程安全相关异常
- **AND** 字幕正确显示在GUI窗口中

