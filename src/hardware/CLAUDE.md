# src/hardware 模块文档

**模块路径**: `src/hardware/`
**创建日期**: 2025-09-28
**最后更新**: 2025-09-28
**模块状态**: ✅ 已完成分析和注释

## 模块概述

硬件检测和管理模块，负责GPU检测、内存管理、CPU/GPU自适应切换等功能。支持PyTorch和ONNX Runtime的GPU环境检测和配置，为语音转录系统提供硬件适配和性能优化支持。

### 核心功能
- 🔍 **多重GPU检测**: PyTorch + 手动检测保证兼容性
- 📊 **详细信息收集**: 内存、温度、利用率、计算能力等
- 🚀 **智能推荐**: 根据硬件条件推荐最优执行提供器
- 🔄 **缓存机制**: 避免重复检测，提高性能
- 🌐 **跨平台支持**: Windows/Linux/macOS兼容

## 架构设计

### 模块结构
```
src/hardware/
├── __init__.py          # 模块入口和API导出
├── models.py            # 数据模型定义 (GPUInfo, SystemInfo)
├── gpu_detector.py      # GPU检测和管理核心实现
└── BUG_REPORT.md        # Bug分析报告
```

### 设计模式
- **数据模型层**: 使用`@dataclass`定义结构化数据
- **检测引擎层**: 多重检测策略，容错处理
- **缓存管理层**: 智能缓存机制，避免重复开销
- **单例模式**: 全局`gpu_detector`实例

### 技术栈
| 技术组件 | 用途 | 重要性 |
|---------|------|--------|
| PyTorch | 主要CUDA检测方式 | 高 |
| ONNX Runtime | 推理执行提供器 | 高 |
| nvidia-smi | 备用GPU信息获取 | 中 |
| pynvml | 详细GPU状态监控 | 中 |
| psutil | 系统信息收集 | 中 |

## API 参考

### 核心类

#### GPUInfo
```python
@dataclass
class GPUInfo:
    """GPU设备信息数据类"""
    id: int                           # GPU设备ID
    name: str                        # GPU设备名称
    is_available: bool               # GPU是否可用
    total_memory: int                # 总内存 (MB)
    available_memory: int            # 可用内存 (MB)
    used_memory: int                 # 已用内存 (MB)
    compute_capability: Optional[str] # CUDA计算能力
    driver_version: Optional[str]     # 驱动版本
    temperature: Optional[int]        # GPU温度
    utilization: Optional[int]        # GPU利用率
```

**关键方法**:
- `memory_usage_percent() -> float`: 计算内存使用率
- `has_sufficient_memory(required_mb: int) -> bool`: 检查内存是否足够
- `is_suitable_for_inference(min_memory_mb: int = 1024) -> bool`: 检查是否适合推理

#### SystemInfo
```python
@dataclass
class SystemInfo:
    """系统硬件信息数据类"""
    cpu_count: int                   # CPU核心数
    cpu_name: Optional[str]          # CPU型号
    total_ram_mb: int                # 总内存 (MB)
    available_ram_mb: int            # 可用内存 (MB)
    gpus: List[GPUInfo]              # GPU设备列表
    platform: Optional[str]          # 操作系统
    python_version: Optional[str]    # Python版本
```

**关键方法**:
- `get_best_gpu(min_memory_mb: int = 1024) -> Optional[GPUInfo]`: 获取最佳GPU
- `has_cuda_gpu() -> bool`: 检查是否有CUDA GPU
- `get_total_gpu_memory() -> int`: 获取总GPU内存

#### GPUDetector
```python
class GPUDetector:
    """GPU检测和管理核心类"""
```

**主要方法**:
- `detect_cuda() -> bool`: 检测CUDA可用性
- `detect_onnxruntime_gpu() -> bool`: 检测ONNX Runtime GPU支持
- `get_gpu_info() -> List[GPUInfo]`: 获取详细GPU信息
- `get_system_info() -> SystemInfo`: 获取综合系统信息
- `check_memory(required_mb: int, device_id: Optional[int] = None) -> bool`: 检查内存
- `get_recommended_provider(prefer_gpu: bool = True) -> str`: 获取推荐提供器
- `get_provider_options(provider: str, device_id: Optional[int] = None) -> dict`: 获取提供器配置

### 全局实例
```python
from src.hardware import gpu_detector

# 全局GPU检测器实例，方便访问
gpu_detector: GPUDetector
```

## 使用指南

### 基本使用

#### 1. 检测GPU环境
```python
from src.hardware import gpu_detector

# 检测CUDA是否可用
if gpu_detector.detect_cuda():
    print("CUDA is available")

    # 获取GPU信息
    gpus = gpu_detector.get_gpu_info()
    for gpu in gpus:
        print(f"GPU {gpu.id}: {gpu.name}")
        print(f"Memory: {gpu.available_memory}/{gpu.total_memory}MB")
```

#### 2. 获取系统信息
```python
# 获取完整系统信息
system_info = gpu_detector.get_system_info()
print(system_info)

# 检查是否有CUDA GPU
if system_info.has_cuda_gpu():
    best_gpu = system_info.get_best_gpu(min_memory_mb=2048)
    if best_gpu:
        print(f"Best GPU: {best_gpu.name}")
```

#### 3. 配置ONNX Runtime
```python
# 获取推荐的执行提供器
provider = gpu_detector.get_recommended_provider(prefer_gpu=True)
print(f"Recommended provider: {provider}")

# 获取提供器配置
if provider == "CUDAExecutionProvider":
    options = gpu_detector.get_provider_options(provider, device_id=0)

    # 创建ONNX Runtime会话
    import onnxruntime as ort
    session = ort.InferenceSession(
        model_path,
        providers=[(provider, options)]
    )
```

#### 4. 内存检查
```python
# 检查特定GPU的内存
required_memory_mb = 1024
if gpu_detector.check_memory(required_memory_mb, device_id=0):
    print("GPU 0 has sufficient memory")

# 检查最佳可用GPU的内存
if gpu_detector.check_memory(required_memory_mb):
    print("Found GPU with sufficient memory")
```

### 高级使用

#### 1. 自定义GPU选择策略
```python
def select_gpu_for_task(task_memory_mb: int, max_utilization: int = 80):
    """根据任务需求选择GPU"""
    system_info = gpu_detector.get_system_info()

    suitable_gpus = []
    for gpu in system_info.gpus:
        if (gpu.is_available and
            gpu.has_sufficient_memory(task_memory_mb) and
            (gpu.utilization or 0) < max_utilization):
            suitable_gpus.append(gpu)

    if suitable_gpus:
        # 选择利用率最低的GPU
        return min(suitable_gpus, key=lambda g: g.utilization or 0)
    return None
```

#### 2. 性能监控
```python
def monitor_gpu_performance():
    """监控GPU性能指标"""
    gpus = gpu_detector.get_gpu_info()

    for gpu in gpus:
        print(f"GPU {gpu.id}: {gpu.name}")
        print(f"  Memory Usage: {gpu.memory_usage_percent:.1f}%")
        if gpu.temperature:
            print(f"  Temperature: {gpu.temperature}°C")
        if gpu.utilization:
            print(f"  Utilization: {gpu.utilization}%")
```

#### 3. 环境诊断
```python
def diagnose_environment():
    """诊断GPU环境配置"""
    print("=== GPU Environment Diagnosis ===")

    # CUDA检测
    cuda_available = gpu_detector.detect_cuda()
    print(f"CUDA Available: {cuda_available}")

    # ONNX Runtime GPU支持
    onnx_gpu = gpu_detector.detect_onnxruntime_gpu()
    print(f"ONNX Runtime GPU: {onnx_gpu}")

    # 系统信息
    gpu_detector.print_system_info()

    # 推荐配置
    provider = gpu_detector.get_recommended_provider()
    print(f"Recommended Provider: {provider}")
```

## 配置选项

### 执行提供器配置
```python
# CUDA执行提供器默认配置
cuda_options = {
    'device_id': 0,                                    # GPU设备ID
    'arena_extend_strategy': 'kSameAsRequested',       # 内存分配策略
    'gpu_mem_limit': 2 * 1024 * 1024 * 1024,         # GPU内存限制 (2GB)
    'cudnn_conv_algo_search': 'EXHAUSTIVE',           # cuDNN算法搜索
    'do_copy_in_default_stream': True,                # 默认流复制
}

# CPU执行提供器配置
cpu_options = {}  # CPU提供器通常不需要特殊配置
```

### 内存管理配置
```python
# GPU内存检查阈值
MEMORY_THRESHOLDS = {
    'minimum_available': 1024,      # 最小可用内存 (MB)
    'usage_limit': 90,              # 使用率上限 (%)
    'inference_minimum': 512,       # 推理最小内存 (MB)
}
```

## 性能考虑

### 缓存策略
- **检测结果缓存**: CUDA可用性和系统信息被缓存，避免重复检测
- **缓存失效**: 目前缓存不会自动失效，在长期运行的应用中需要考虑刷新
- **内存占用**: 缓存的系统信息占用内存较少，通常可忽略

### 性能指标
| 操作 | 平均耗时 | 缓存后耗时 |
|------|----------|------------|
| CUDA检测 | 50-200ms | < 1ms |
| GPU信息收集 | 100-500ms | < 1ms |
| 系统信息获取 | 200-1000ms | < 1ms |

### 优化建议
1. **首次初始化**: 在应用启动时执行一次完整检测
2. **按需检测**: 只在需要时获取详细信息
3. **错误处理**: 对检测失败有降级方案
4. **并发控制**: 避免多线程同时进行重复检测

## 错误处理

### 常见错误情况

#### 1. GPU不可用
```python
try:
    if not gpu_detector.detect_cuda():
        print("CUDA not available, falling back to CPU")
        provider = "CPUExecutionProvider"
except Exception as e:
    logger.error(f"GPU detection failed: {e}")
    provider = "CPUExecutionProvider"
```

#### 2. 内存不足
```python
required_memory = 2048  # MB
if not gpu_detector.check_memory(required_memory):
    print("Insufficient GPU memory, reducing model size or using CPU")
    # 降级处理逻辑
```

#### 3. 驱动问题
```python
try:
    gpus = gpu_detector.get_gpu_info()
    if not gpus:
        print("No GPU detected, check drivers")
except Exception as e:
    logger.warning(f"GPU driver issue: {e}")
```

### 日志配置
```python
import logging

# 配置日志级别
logging.getLogger('src.hardware').setLevel(logging.INFO)

# 详细调试信息
logging.getLogger('src.hardware').setLevel(logging.DEBUG)
```

## 测试

### 单元测试示例
```python
import pytest
from src.hardware import GPUInfo, SystemInfo, GPUDetector

def test_gpu_info_memory_calculation():
    """测试GPU内存计算"""
    gpu = GPUInfo(
        id=0, name="Test GPU", is_available=True,
        total_memory=8192, used_memory=2048, available_memory=6144
    )

    assert gpu.memory_usage_percent == 25.0
    assert gpu.has_sufficient_memory(4096) == True
    assert gpu.has_sufficient_memory(8192) == False

def test_system_info_best_gpu():
    """测试最佳GPU选择"""
    gpu1 = GPUInfo(id=0, name="GPU1", is_available=True,
                   total_memory=4096, used_memory=1024, available_memory=3072)
    gpu2 = GPUInfo(id=1, name="GPU2", is_available=True,
                   total_memory=8192, used_memory=2048, available_memory=6144)

    system = SystemInfo(cpu_count=8, gpus=[gpu1, gpu2])
    best = system.get_best_gpu(min_memory_mb=2048)

    assert best.id == 1  # GPU2有更多可用内存

def test_cuda_detection():
    """测试CUDA检测"""
    detector = GPUDetector()
    result = detector.detect_cuda()
    assert isinstance(result, bool)
```

### 集成测试
```python
def test_end_to_end_gpu_detection():
    """端到端GPU检测测试"""
    from src.hardware import gpu_detector

    # 获取系统信息
    system_info = gpu_detector.get_system_info()
    assert system_info.cpu_count > 0
    assert system_info.total_ram_mb > 0

    # 获取推荐提供器
    provider = gpu_detector.get_recommended_provider()
    assert provider in ["CUDAExecutionProvider", "CPUExecutionProvider"]

    # 检查配置选项
    options = gpu_detector.get_provider_options(provider)
    assert isinstance(options, dict)
```

## 故障排除

### 常见问题

#### Q1: CUDA检测失败
**症状**: `detect_cuda()` 返回 `False`
**可能原因**:
- NVIDIA驱动未安装或版本过低
- CUDA toolkit未安装
- PyTorch未安装或不支持CUDA

**解决方案**:
```bash
# 检查NVIDIA驱动
nvidia-smi

# 检查CUDA版本
nvcc --version

# 检查PyTorch CUDA支持
python -c "import torch; print(torch.cuda.is_available())"
```

#### Q2: GPU信息获取不完整
**症状**: GPU温度、利用率信息为 `None`
**原因**: pynvml库未安装或权限不足

**解决方案**:
```bash
# 安装pynvml
pip install pynvml

# 或使用conda
conda install pynvml
```

#### Q3: 内存信息不准确
**症状**: 内存使用率计算异常
**原因**: GPU内存碎片或PyTorch缓存

**解决方案**:
```python
# 清理PyTorch缓存
import torch
torch.cuda.empty_cache()

# 强制刷新检测
detector = GPUDetector()
detector._cuda_available = None  # 清除缓存
detector._system_info = None
```

### 调试技巧

#### 1. 详细日志
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看详细检测过程
gpu_detector.print_system_info()
```

#### 2. 手动检测
```python
# 测试各个检测组件
detector = GPUDetector()

print("Manual CUDA detection:", detector._manual_cuda_detection())
print("ONNX Runtime GPU:", detector.detect_onnxruntime_gpu())
print("Fallback GPU info:", detector._get_fallback_gpu_info())
```

#### 3. 环境验证
```python
# 验证所有依赖
try:
    import torch
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
except ImportError:
    print("PyTorch not installed")

try:
    import onnxruntime as ort
    print(f"ONNX Runtime: {ort.__version__}")
    print(f"Providers: {ort.get_available_providers()}")
except ImportError:
    print("ONNX Runtime not installed")
```

## 已知限制

### 当前限制
1. **缓存策略**: 检测结果永久缓存，无自动刷新机制
2. **平台支持**: nvidia-smi检测主要针对Windows优化
3. **内存精度**: 可用内存计算可能不包含系统保留内存
4. **线程安全**: 全局实例在多线程环境下存在竞态条件风险

### 兼容性
- **Python**: 3.8+
- **操作系统**: Windows 10+, Ubuntu 18.04+, macOS 10.15+
- **CUDA**: 10.2+ (如果使用GPU)
- **依赖**: torch, onnxruntime, psutil, pynvml (可选)

## 版本历史

### v1.0.0 (2025-09-28)
- ✅ 初始实现GPU检测功能
- ✅ 支持PyTorch和ONNX Runtime集成
- ✅ 添加详细中文注释
- ✅ 完成Bug分析和报告
- ⚠️ 已知18个问题待修复 (见BUG_REPORT.md)

## 开发指南

### 代码风格
- 使用中文注释增强可读性
- 遵循Google Python风格指南
- 使用类型注解提高代码质量
- 采用dataclass简化数据结构

### 扩展开发
```python
# 添加新的GPU信息字段
@dataclass
class GPUInfo:
    # 现有字段...
    power_consumption: Optional[int] = None  # 功耗 (瓦特)
    fan_speed: Optional[int] = None          # 风扇转速 (%)

# 扩展检测功能
class GPUDetector:
    def get_power_info(self, device_id: int) -> dict:
        """获取GPU功耗信息"""
        # 实现功耗检测逻辑
        pass
```

### 贡献指南
1. 遵循现有代码风格和注释规范
2. 添加相应的单元测试
3. 更新文档和使用示例
4. 确保跨平台兼容性

---

**模块维护者**: AI Assistant
**文档版本**: 1.0.0
**最后审核**: 2025-09-28

如需技术支持或功能建议，请参考项目主文档或提交Issue。