# 流程协调模块 (Coordinator)

[根目录](../../CLAUDE.md) > [src](../) > **coordinator**

## 模块职责
实现事件驱动的转录流水线，协调音频捕获、VAD检测、语音转录和输出处理等组件的工作流程。提供统一的生命周期管理、错误处理和性能监控。

## 入口和启动
- **核心流水线**: `pipeline.py::TranscriptionPipeline`
- **事件系统**: 基于队列的异步事件处理
- **状态管理**: 完整的流水线状态跟踪
- **集成方式**: 作为main.py的核心组件，统一管理所有子系统

## 外部接口

### 主要类和方法
```python
# 转录流水线核心类
class TranscriptionPipeline:
    def __init__(self, config: Config)                      # 初始化流水线
    def initialize(self) -> bool                            # 初始化所有组件
    def start(self) -> bool                                 # 启动流水线
    def stop(self) -> None                                  # 停止流水线
    def run(self) -> None                                   # 运行流水线直到停止

    # 事件处理
    def add_event_handler(self, event_type: EventType, handler) -> None     # 添加事件处理器
    def remove_event_handler(self, event_type: EventType, handler) -> None  # 移除事件处理器
    def add_error_callback(self, callback) -> None          # 添加错误回调

    # 状态和统计
    def get_statistics(self) -> Dict[str, Any]              # 获取流水线统计
    def get_status(self) -> Dict[str, Any]                  # 获取流水线状态
    @property
    def state(self) -> PipelineState                        # 当前状态

    # 上下文管理器支持
    def __enter__(self)                                     # 进入上下文
    def __exit__(self, exc_type, exc_val, exc_tb)          # 退出上下文

# 事件数据结构
@dataclass
class PipelineEvent:
    event_type: EventType                   # 事件类型
    timestamp: float                        # 时间戳
    data: Any                              # 事件数据
    source: str                            # 事件源
    metadata: Dict[str, Any] = None        # 元数据

# 流水线统计信息
@dataclass
class PipelineStatistics:
    start_time: float = 0.0                # 启动时间
    total_audio_chunks: int = 0            # 处理的音频块数
    total_vad_detections: int = 0          # VAD检测次数
    total_transcriptions: int = 0          # 转录次数
    total_errors: int = 0                  # 错误次数
    last_activity_time: float = 0.0       # 最后活动时间

    @property
    def uptime(self) -> float              # 运行时间
    @property
    def audio_throughput(self) -> float    # 音频吞吐量(块/秒)
```

### 枚举类型
```python
class PipelineState(Enum):
    IDLE = "idle"                          # 空闲状态
    INITIALIZING = "initializing"          # 初始化中
    RUNNING = "running"                    # 运行中
    STOPPING = "stopping"                 # 停止中
    ERROR = "error"                       # 错误状态

class EventType(Enum):
    AUDIO_DATA = "audio_data"             # 音频数据事件
    VAD_RESULT = "vad_result"             # VAD检测结果
    TRANSCRIPTION_RESULT = "transcription_result"  # 转录结果
    ERROR = "error"                       # 错误事件
    STATE_CHANGE = "state_change"         # 状态变化事件
```

### 上下文管理器
```python
# 支持with语句的资源管理
with TranscriptionPipeline(config) as pipeline:
    pipeline.run()  # 自动处理启动和清理
```

## 关键依赖和配置

### 组件依赖关系
```
TranscriptionPipeline
├── GPUDetector (硬件检测)
├── AudioCapture (音频捕获)
├── VoiceActivityDetector (VAD检测)
├── TranscriptionEngine (转录引擎)
└── OutputHandler (输出处理)
```

### 事件处理架构
- **事件队列**: 基于`queue.Queue`的线程安全队列
- **事件循环**: 独立线程处理事件，避免阻塞主流程
- **回调机制**: 支持多个监听器监听同一事件类型
- **错误隔离**: 单个组件错误不影响整体流程

### 信号处理
```python
# 优雅停止信号处理
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
```

## 数据模型

### 组件初始化流程
1. **GPU检测**: 检测CUDA环境和GPU可用性
2. **音频配置**: 根据配置创建AudioCapture实例
3. **VAD初始化**: 加载Silero VAD模型并配置参数
4. **转录引擎**: 加载sense-voice模型并设置处理器类型
5. **输出处理**: 配置输出格式和显示选项

### 事件处理流程
```
AudioCapture → [音频数据] → VoiceActivityDetector
                                    ↓
OutputHandler ← [转录结果] ← TranscriptionEngine
```

### 生命周期管理
```python
# 完整的生命周期管理
class TranscriptionPipeline:
    def _setup_signal_handlers(self):      # 设置信号处理器
    def _change_state(self, new_state):    # 状态变化管理
    def _emit_event(self, ...):            # 事件发射
    def _process_event(self, event):       # 事件处理
    def _cleanup(self):                    # 资源清理
```

## 测试和质量保证

### 单元测试覆盖
- **流水线生命周期测试**: `tests/test_coordinator.py`
  - 初始化和启动流程
  - 停止和清理流程
  - 错误状态处理

### 集成测试
- **端到端流程测试**: `tests/test_integration.py`
  - 完整的音频处理流程
  - 组件间数据传递
  - 异常情况处理

### 性能测试
- **事件处理延迟**: < 10ms
- **内存使用**: 稳定无泄漏
- **CPU使用**: 合理的资源分配

## 使用示例

### 基本流水线使用
```python
from src.coordinator.pipeline import TranscriptionPipeline, EventType
from src.config.models import Config

# 创建配置
config = Config(
    model_path="models/sense-voice.onnx",
    input_source="microphone",
    use_gpu=True
)

# 创建流水线
pipeline = TranscriptionPipeline(config)

# 添加事件处理器
def on_transcription_result(event):
    result = event.data
    print(f"转录结果: {result.text}")

pipeline.add_event_handler(EventType.TRANSCRIPTION_RESULT, on_transcription_result)

# 运行流水线
try:
    with pipeline:
        pipeline.run()
except KeyboardInterrupt:
    print("用户中断")
```

### 高级事件处理
```python
# 完整的事件监听示例
class PipelineMonitor:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.setup_handlers()

    def setup_handlers(self):
        # 状态变化监听
        self.pipeline.add_event_handler(
            EventType.STATE_CHANGE,
            self.on_state_change
        )

        # 错误监听
        self.pipeline.add_event_handler(
            EventType.ERROR,
            self.on_error
        )

        # 音频数据监听
        self.pipeline.add_event_handler(
            EventType.AUDIO_DATA,
            self.on_audio_data
        )

    def on_state_change(self, event):
        old_state = event.data.get('old')
        new_state = event.data.get('new')
        print(f"状态变化: {old_state} → {new_state}")

    def on_error(self, event):
        print(f"错误: {event.source} - {event.data}")

    def on_audio_data(self, event):
        audio_chunk = event.data
        print(f"音频数据: {len(audio_chunk.data)} 采样点")

# 使用监听器
monitor = PipelineMonitor(pipeline)
```

### 性能监控
```python
# 实时性能监控
import time

def monitor_pipeline_performance(pipeline):
    while pipeline.state == PipelineState.RUNNING:
        stats = pipeline.get_statistics()
        status = pipeline.get_status()

        print(f"运行时间: {stats.uptime:.1f}s")
        print(f"音频吞吐量: {stats.audio_throughput:.2f} 块/秒")
        print(f"转录次数: {stats.total_transcriptions}")
        print(f"错误次数: {stats.total_errors}")
        print(f"事件队列大小: {status.get('event_queue_size', 0)}")
        print("-" * 40)

        time.sleep(5)  # 每5秒输出一次

# 在独立线程中运行监控
import threading
monitor_thread = threading.Thread(
    target=monitor_pipeline_performance,
    args=(pipeline,),
    daemon=True
)
monitor_thread.start()
```

### 错误处理和恢复
```python
# 自定义错误处理
def error_handler(exception):
    print(f"流水线错误: {exception}")

    # 根据错误类型执行不同的恢复策略
    if "CUDA" in str(exception):
        print("GPU错误，尝试切换到CPU模式")
        # 重新配置为CPU模式
    elif "Audio" in str(exception):
        print("音频错误，尝试重新初始化音频设备")
        # 重新初始化音频捕获

pipeline.add_error_callback(error_handler)
```

## 常见问题 (FAQ)

### Q: 流水线初始化失败如何排查？
A: 检查各组件的依赖是否满足，查看详细的错误日志，确认模型文件和设备可用性

### Q: 事件处理延迟过高怎么办？
A: 检查事件队列大小，减少事件处理器的处理时间，考虑使用更高优先级的线程

### Q: 内存使用持续增长如何解决？
A: 检查事件队列是否堆积，确保所有回调函数正确释放资源，监控各组件的内存使用

### Q: 如何添加新的事件类型？
A: 在EventType枚举中添加新类型，在相应组件中发射事件，添加对应的处理逻辑

### Q: 流水线停止时间过长？
A: 检查各组件的停止逻辑，确保没有阻塞操作，考虑添加超时机制

## 相关文件列表
- `pipeline.py` - 流水线核心实现，包含事件处理和组件协调
- `__init__.py` - 模块初始化文件

## 变更日志 (Changelog)
- **2025-09-27**: 创建流程协调模块文档，包含完整的事件驱动架构说明和使用指南