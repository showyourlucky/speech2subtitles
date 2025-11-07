# Change: 添加 VAD 检测器单例管理器

## Why

**问题背景：**
当前项目中的 VAD（Voice Activity Detector）检测器在每次 `TranscriptionPipeline` 启动时都会重新创建和加载模型，导致以下问题：

1. **启动延迟高**：每次 Pipeline 重启都需要重新加载 VAD 模型（~2秒）
2. **内存浪费**：无法在多次启动间复用已加载的模型
3. **设计不一致**：`TranscriptionEngine` 已有 `TranscriptionEngineManager` 单例管理器，但 VAD 缺少类似机制
4. **资源管理分散**：没有统一的 VAD 资源管理和统计收集

**改进机会：**
参照 `TranscriptionEngineManager` 的成功实践，为 VAD 检测器实现单例模式管理，提供智能复用和统一资源管理。

## What Changes

### 新增组件

1. **VadManager 类** (`src/vad/vad_manager.py`)
   - 单例模式管理 VAD 检测器
   - 智能检测配置变更并决定是否重新加载
   - 提供统计信息收集（加载次数、复用次数等）
   - 线程安全的并发访问保护

2. **集成点更新**
   - `src/coordinator/pipeline.py` - 使用 VadManager 替代直接实例化
   - `main.py` - 更新示例代码使用最佳实践

3. **测试和验证**
   - 单元测试（无模型依赖）
   - 完整功能测试
   - 集成验证脚本

### API 设计

```python
# 推荐使用方式
from src.vad import VadManager, VadConfig

config = VadConfig(threshold=0.5)
detector = VadManager.get_detector(config)  # 首次加载或复用
stats = VadManager.get_statistics()         # 获取统计信息
VadManager.release()                        # 应用退出时释放
```

### 配置变更检测

自动检测以下关键参数变化：
- `model` - VAD 模型类型
- `use_sherpa_onnx` - 实现方式标志
- `threshold` - 检测阈值
- `sample_rate` - 采样率

## Impact

### 受影响的规范
- `specs/vad/spec.md` - VAD 模块规范（新增资源管理要求）

### 受影响的代码
- `src/vad/` - 新增 vad_manager.py
- `src/coordinator/pipeline.py:278` - 使用 VadManager
- `main.py:350` - 更新示例代码
- `src/vad/__init__.py` - 导出 VadManager
- `src/vad/CLAUDE.md` - 更新文档

### 性能改进
- Pipeline 重启速度：从 ~2秒 降低到 ~10ms（200倍提升）
- 内存使用：避免重复加载模型
- 统计监控：可追踪检测器使用情况

### 向后兼容性
- ✅ **完全兼容**：现有代码可继续直接使用 `VoiceActivityDetector`
- ✅ **渐进迁移**：推荐但不强制使用 `VadManager`
- ✅ **API 稳定**：`VoiceActivityDetector` 接口保持不变

### 风险评估
- **低风险**：新增组件，不修改现有逻辑
- **可回滚**：只需移除 VadManager 的使用即可
- **测试充分**：包含单元测试、集成测试和验证脚本
