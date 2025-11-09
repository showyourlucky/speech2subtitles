# Design: 字幕显示单例模式实现

## Context

当前系统中，`SubtitleDisplay`组件可以在多个位置被独立初始化：
- `OutputHandler` - 处理转录结果输出时初始化字幕显示
- `MainWindow` - GUI主窗口启动字幕显示功能时初始化

每个初始化都会创建独立的tkinter窗口和GUI线程，导致屏幕上出现多个字幕窗口的问题。

**技术约束**：
- tkinter要求所有GUI操作在同一线程中执行
- 系统已有`ThreadSafeSubtitleDisplay`实现，使用独立GUI线程和消息队列
- 需要保持向后兼容，不破坏现有代码

**利益相关者**：
- 最终用户：避免多窗口混乱，获得一致的字幕显示体验
- 开发者：清晰的单例API，避免资源泄漏

## Goals / Non-Goals

**Goals**：
1. 确保整个应用只有一个字幕窗口实例
2. 提供线程安全的单例实现
3. 保持向后兼容现有API
4. 支持配置动态更新
5. 优雅的资源清理机制

**Non-Goals**：
1. 不重构整个字幕显示系统架构
2. 不改变字幕显示的视觉效果或行为
3. 不引入新的外部依赖

## Decisions

### Decision 1: 使用模块级单例 + 工厂方法

**选择**：在`display_wrapper.py`模块中维护单例实例，提供`get_subtitle_display_instance()`工厂方法。

**原因**：
- 模块级变量简单直接，符合Python惯用模式
- 工厂方法提供清晰的单例语义，便于理解和测试
- 避免元类或装饰器等过度复杂的实现

**实现细节**：
```python
# src/subtitle_display/display_wrapper.py
import threading

_subtitle_display_instance = None
_instance_lock = threading.Lock()

def get_subtitle_display_instance(config: SubtitleDisplayConfig):
    """获取字幕显示单例实例（线程安全）"""
    global _subtitle_display_instance

    if _subtitle_display_instance is None:
        with _instance_lock:
            if _subtitle_display_instance is None:  # 双重检查锁定
                _subtitle_display_instance = SubtitleDisplay(config)
    else:
        # 配置已存在时，更新配置
        _subtitle_display_instance.update_config(config)

    return _subtitle_display_instance
```

**替代方案考虑**：
1. **元类实现**：过于复杂，不符合KISS原则
2. **单例装饰器**：增加理解成本，不够直观
3. **依赖注入容器**：引入额外依赖，过度设计

### Decision 2: 覆盖 `__new__()` 实现向后兼容

**选择**：覆盖`SubtitleDisplay.__new__()`方法，使直接实例化也返回单例。

**原因**：
- 完全向后兼容，现有的`SubtitleDisplay(config)`调用无需修改
- 用户无感知切换到单例模式
- 减少代码迁移成本

**实现细节**：
```python
class SubtitleDisplay:
    def __new__(cls, config: SubtitleDisplayConfig):
        """覆盖构造方法，返回单例实例"""
        return get_subtitle_display_instance(config)
```

**权衡**：
- **优点**：API兼容性最大化
- **缺点**：可能让开发者误以为每次都创建新实例（通过文档和日志缓解）

### Decision 3: 双重检查锁定 (Double-Checked Locking)

**选择**：使用双重检查锁定模式确保线程安全，同时优化性能。

**原因**：
- 第一次检查避免不必要的锁竞争（已初始化后的快速路径）
- 锁内第二次检查确保并发场景下只创建一个实例
- Python的GIL + `threading.Lock()`确保实现正确性

**替代方案考虑**：
1. **每次都加锁**：性能开销大，单例初始化后每次调用都需要获取锁
2. **不加锁**：并发场景下可能创建多个实例，不满足需求

### Decision 4: 配置更新策略

**选择**：当单例已存在时，调用`update_config(new_config)`动态更新配置。

**原因**：
- 避免重新初始化GUI线程和窗口（资源开销大）
- 支持运行时动态调整字幕样式
- 提供更流畅的用户体验

**实现细节**：
```python
def update_config(self, new_config: SubtitleDisplayConfig) -> None:
    """动态更新配置"""
    self.config = new_config

    # 仅更新GUI属性，不重启线程
    if self._implementation:
        self._send_message("update_config", new_config)
```

**权衡**：
- **优点**：性能好，用户体验流畅
- **缺点**：部分配置（如GUI线程相关）可能无法热更新，需要重启

### Decision 5: 降级策略 - 优雅失败

**选择**：单例初始化失败时，降级创建独立实例并记录警告。

**原因**：
- 遵循"可用性优先"原则，不因单例失败阻塞应用
- 日志警告提示用户可能出现多窗口问题
- 支持故障排查和调试

**实现细节**：
```python
try:
    return get_subtitle_display_instance(config)
except Exception as e:
    logger.warning(f"单例模式初始化失败，降级到多实例模式: {e}")
    logger.warning("可能出现多个字幕窗口，建议检查系统日志")
    return _create_fallback_instance(config)
```

## Risks / Trade-offs

### Risk 1: 单例模式增加测试复杂度

**风险**：单元测试之间可能相互影响，因为单例状态全局共享。

**缓解措施**：
- 提供`reset_subtitle_display_instance()`方法用于测试清理
- 在测试的`setUp()`中重置单例状态
- 使用`_singleton_enabled`标志位支持在测试中禁用单例

### Risk 2: 配置更新可能不完整

**风险**：某些配置（如GUI线程参数）无法在运行时热更新。

**缓解措施**：
- 在文档中明确标注哪些配置支持热更新
- 对于不支持热更新的配置，记录警告日志
- 提供`reset_subtitle_display_instance()`强制重新初始化

### Risk 3: 资源清理时机问题

**风险**：应用异常退出时可能无法正确清理单例资源。

**缓解措施**：
- 使用`atexit`注册清理处理器
- 在`__del__()`中实现双重保险清理
- 使用`try...finally`确保资源释放

## Migration Plan

### Phase 1: 单例实现（不破坏现有功能）

1. 添加单例管理代码，但保持现有构造函数行为
2. 运行测试确保无回归
3. 部署到测试环境验证

### Phase 2: 更新调用点

1. 更新`OutputHandler`使用工厂方法
2. 更新`MainWindow`使用工厂方法
3. 逐步验证各个场景

### Phase 3: 文档和监控

1. 更新文档推荐使用工厂方法
2. 添加日志记录单例初始化和重用事件
3. 监控生产环境是否还有多窗口报告

### Rollback Plan

如果单例模式引入问题：
1. 将`get_subtitle_display_instance()`降级为简单的直接实例化
2. 保留工厂方法接口，避免调用点回退
3. 记录详细日志用于问题诊断

## Open Questions

1. **Q**: 是否需要支持多配置多实例场景（如不同位置的多个字幕窗口）？
   **A**: 当前不支持。如有需求，可扩展为键值对单例（基于配置哈希）。

2. **Q**: 配置热更新失败时是否应该抛出异常？
   **A**: 否，记录警告日志即可，避免影响应用运行。

3. **Q**: 是否需要提供`destroy_instance()`强制销毁单例？
   **A**: 提供`reset_subtitle_display_instance()`即可，语义更清晰。

## Performance Considerations

- **单例初始化开销**：仅在首次调用时加锁，后续调用几乎零开销
- **配置更新开销**：通过消息队列异步更新GUI，不阻塞调用线程
- **内存占用**：单例减少了内存占用（仅一个GUI线程和窗口）

## Security Considerations

- **无敏感数据**：字幕显示组件不涉及敏感信息
- **线程安全**：双重检查锁定确保并发安全
- **资源限制**：单例避免了恶意代码创建大量窗口的攻击向量

## Testing Strategy

1. **单元测试**：
   - 单例行为验证
   - 线程安全测试（并发初始化）
   - 配置更新测试
   - 资源清理测试

2. **集成测试**：
   - 验证`OutputHandler`和`MainWindow`共享单例
   - 端到端字幕显示功能测试

3. **手动测试**：
   - 启动应用，检查仅有一个字幕窗口
   - 验证字幕正常显示和更新
   - 验证应用退出时资源正确清理

## Implementation Notes

- 优先使用`logging`记录单例生命周期事件
- 在DEBUG级别记录每次单例重用
- 在WARNING级别记录降级和异常情况
- 确保所有公共方法包含详细的docstring
