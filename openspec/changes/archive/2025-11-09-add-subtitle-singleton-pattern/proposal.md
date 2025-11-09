# Change: 为字幕显示组件添加单例模式

## Why

当前系统存在多个组件(`OutputHandler`和`MainWindow`)独立初始化`SubtitleDisplay`的情况，导致以下问题：

1. **多个字幕窗口**：屏幕上同时出现多个tkinter字幕窗口，造成用户困惑和视觉混乱
2. **资源浪费**：每个`SubtitleDisplay`实例都会创建独立的GUI线程和tkinter窗口，浪费系统资源
3. **状态不一致**：多个实例之间无法共享显示状态，可能导致字幕显示不同步或冲突

**根因分析**：
- `src/output/handler.py:271` - `OutputHandler.__init__()`创建字幕显示实例
- `src/gui/main_window.py:713` - `MainWindow._start_subtitle_display()`也创建字幕显示实例
- 两个组件在同一应用中被同时使用时，会创建两个独立的字幕窗口

## What Changes

实现**单例模式(Singleton Pattern)**，确保整个应用程序生命周期内只有一个`SubtitleDisplay`实例：

1. **添加单例管理器**：
   - 在`src/subtitle_display/`模块中添加单例管理逻辑
   - 提供`get_instance()`工厂方法替代直接实例化
   - 确保线程安全的单例初始化

2. **更新现有调用点**：
   - 修改`src/output/handler.py`使用单例获取方法
   - 修改`src/gui/main_window.py`使用单例获取方法
   - 保持配置更新机制的兼容性

3. **生命周期管理**：
   - 添加`reset_instance()`方法用于测试和重启场景
   - 确保单例在应用退出时正确清理资源

## Impact

**受影响的组件**：
- `src/subtitle_display/display_wrapper.py` - 添加单例模式实现
- `src/subtitle_display/__init__.py` - 更新导出接口
- `src/output/handler.py` - 修改初始化逻辑
- `src/gui/main_window.py` - 修改初始化逻辑

**受影响的spec**：
- 新增：`subtitle-display` capability（当前不存在字幕显示相关spec）

**向后兼容性**：
- **非破坏性变更**：现有的`SubtitleDisplay(config)`调用方式仍然支持，但内部会返回单例
- 新增`get_subtitle_display_instance(config)`工厂方法作为推荐用法

**风险评估**：
- **低风险**：单例模式是经过验证的设计模式，不会引入新的依赖
- **测试需求**：需要添加单元测试验证单例行为
- **降级策略**：保留原有构造函数，单例失败时降级到多实例模式并记录警告
