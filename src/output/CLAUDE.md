# 输出处理模块 (Output Handler)

[根目录](../../CLAUDE.md) > [src](../) > **output**

## 模块职责
负责转录结果的格式化、显示和输出处理。支持多种输出格式(文本、JSON)，提供实时显示、置信度显示、时间戳标注等功能。

## 入口和启动
- **主处理器**: `handler.py::OutputHandler`
- **输出配置**: `models.py::OutputConfig`
- **格式支持**: 控制台输出、JSON格式、文件输出
- **集成方式**: 由`TranscriptionPipeline`创建，接收转录结果并进行格式化输出

## 外部接口

### 主要类和方法
```python
# 输出处理器主类
class OutputHandler:
    def __init__(self, config: OutputConfig)                # 初始化输出处理器
    def start(self) -> None                                 # 启动输出处理
    def stop(self) -> None                                  # 停止输出处理
    def process_result(self, result: TranscriptionResult) -> None  # 处理转录结果
    def flush_output(self) -> None                          # 刷新输出缓冲
    def set_output_level(self, level: OutputLevel) -> None  # 设置输出级别
    def get_statistics(self) -> OutputStatistics            # 获取输出统计

    # 输出格式化
    def format_text_output(self, result: TranscriptionResult) -> str     # 格式化文本输出
    def format_json_output(self, result: TranscriptionResult) -> str     # 格式化JSON输出
    def format_console_output(self, result: TranscriptionResult) -> str  # 格式化控制台输出

# 输出配置
@dataclass
class OutputConfig:
    format: OutputFormat = OutputFormat.CONSOLE            # 输出格式
    show_confidence: bool = True                           # 显示置信度
    show_timestamps: bool = True                           # 显示时间戳
    real_time_update: bool = True                          # 实时更新
    output_level: OutputLevel = OutputLevel.NORMAL        # 输出级别
    file_path: Optional[str] = None                        # 输出文件路径
    encoding: str = "utf-8"                                # 文件编码
    buffer_size: int = 1024                                # 缓冲区大小
    auto_flush: bool = True                                # 自动刷新

    def validate(self) -> bool                             # 验证配置有效性

# 输出统计
@dataclass
class OutputStatistics:
    total_outputs: int = 0                                 # 总输出次数
    total_characters: int = 0                              # 总字符数
    total_words: int = 0                                   # 总词数
    start_time: float = 0.0                                # 开始时间
    last_output_time: float = 0.0                          # 最后输出时间

    @property
    def output_rate(self) -> float                         # 输出速率(次/秒)
    @property
    def character_rate(self) -> float                      # 字符速率(字符/秒)
```

### 枚举类型
```python
class OutputFormat(Enum):
    CONSOLE = "console"                    # 控制台输出
    TEXT = "text"                         # 纯文本格式
    JSON = "json"                         # JSON格式
    XML = "xml"                          # XML格式(预留)
    SRT = "srt"                          # SRT字幕格式(预留)

class OutputLevel(Enum):
    MINIMAL = "minimal"                   # 最小输出(仅文本)
    NORMAL = "normal"                     # 正常输出(文本+基本信息)
    DETAILED = "detailed"                 # 详细输出(包含置信度、时间戳等)
    DEBUG = "debug"                       # 调试输出(包含所有信息)

# 自定义异常
class OutputError(Exception): pass
class FormattingError(OutputError): pass
class FileOutputError(OutputError): pass
class ConfigurationError(OutputError): pass
```

### 输出格式示例
```python
# 控制台输出格式
"""
[14:30:25] 这是一段语音转录文本 (置信度: 0.95)
[14:30:27] 继续的转录内容 (置信度: 0.88)
"""

# JSON输出格式
{
    "timestamp": "2025-09-27T14:30:25.123Z",
    "text": "这是一段语音转录文本",
    "confidence": 0.95,
    "language": "zh-cn",
    "duration_ms": 2500,
    "processing_time_ms": 145
}

# 文本输出格式
"""
这是一段语音转录文本
继续的转录内容
"""
```

## 关键依赖和配置

### 内部依赖
- `json`: JSON格式处理
- `datetime`: 时间戳格式化
- `pathlib`: 文件路径处理
- `threading`: 线程安全输出

### 输出配置策略
```python
# 实时控制台输出配置
console_config = OutputConfig(
    format=OutputFormat.CONSOLE,
    show_confidence=True,
    show_timestamps=True,
    real_time_update=True,
    output_level=OutputLevel.NORMAL
)

# 文件输出配置
file_config = OutputConfig(
    format=OutputFormat.JSON,
    file_path="transcription_results.json",
    show_confidence=True,
    show_timestamps=True,
    auto_flush=True
)

# 最小化输出配置
minimal_config = OutputConfig(
    format=OutputFormat.TEXT,
    show_confidence=False,
    show_timestamps=False,
    output_level=OutputLevel.MINIMAL
)
```

### 编码和本地化
- **UTF-8编码**: 支持多语言字符输出
- **时间格式**: 可配置的时间戳格式
- **数字格式**: 置信度和时间的格式化

## 数据模型

### 输出处理流程
1. **结果接收**: 从TranscriptionPipeline接收转录结果
2. **格式验证**: 验证结果数据的完整性
3. **格式化处理**: 根据配置格式化输出内容
4. **输出执行**: 输出到控制台、文件或其他目标
5. **统计更新**: 更新输出统计信息
6. **缓冲管理**: 处理输出缓冲和刷新

### 实时输出优化
```python
# 非阻塞输出实现
class RealTimeOutputHandler(OutputHandler):
    def __init__(self, config):
        super().__init__(config)
        self.output_queue = Queue()
        self.output_thread = None

    def _output_worker(self):
        """独立线程处理输出，避免阻塞主流程"""
        while self.is_running:
            try:
                result = self.output_queue.get(timeout=0.1)
                self._write_output(result)
            except Empty:
                continue
```

### 输出缓冲策略
- **行缓冲**: 每个转录结果作为一行输出
- **时间缓冲**: 按时间间隔批量输出
- **大小缓冲**: 达到一定字符数后刷新输出

## 测试和质量保证

### 单元测试覆盖
- **格式化测试**: `tests/test_output.py`
  - 各种格式的输出验证
  - 特殊字符和编码测试
  - 配置参数影响测试

### 输出验证
- **格式正确性**: 验证JSON、XML格式的有效性
- **编码测试**: 多语言字符的正确显示
- **性能测试**: 大量输出的性能表现

### 质量指标
- **输出延迟**: < 10ms
- **内存使用**: 控制缓冲区大小
- **文件输出**: 无数据丢失

## 使用示例

### 基本输出处理
```python
from src.output.handler import OutputHandler
from src.output.models import OutputConfig, OutputFormat, OutputLevel
from src.transcription.models import TranscriptionResult

# 创建输出配置
config = OutputConfig(
    format=OutputFormat.CONSOLE,
    show_confidence=True,
    show_timestamps=True,
    output_level=OutputLevel.NORMAL
)

# 初始化输出处理器
handler = OutputHandler(config)
handler.start()

# 处理转录结果
result = TranscriptionResult(
    text="这是转录的文本内容",
    confidence=0.95,
    timestamp=time.time(),
    duration_ms=2500.0,
    processing_time_ms=145.0
)

handler.process_result(result)
```

### 多格式输出
```python
# 同时输出到控制台和文件
class MultiFormatOutputHandler:
    def __init__(self):
        # 控制台输出
        self.console_handler = OutputHandler(OutputConfig(
            format=OutputFormat.CONSOLE,
            show_confidence=True,
            output_level=OutputLevel.NORMAL
        ))

        # JSON文件输出
        self.file_handler = OutputHandler(OutputConfig(
            format=OutputFormat.JSON,
            file_path="results.json",
            show_timestamps=True
        ))

    def process_result(self, result):
        # 同时处理两种输出
        self.console_handler.process_result(result)
        self.file_handler.process_result(result)

    def start(self):
        self.console_handler.start()
        self.file_handler.start()

    def stop(self):
        self.console_handler.stop()
        self.file_handler.stop()
```

### 自定义格式化
```python
# 扩展输出格式
class CustomOutputHandler(OutputHandler):
    def format_custom_output(self, result):
        """自定义输出格式"""
        timestamp = datetime.fromtimestamp(result.timestamp)
        confidence_bar = "█" * int(result.confidence * 10)

        return f"""
┌─ 转录结果 [{timestamp.strftime('%H:%M:%S')}] ─┐
│ 文本: {result.text}
│ 置信度: {confidence_bar} ({result.confidence:.2f})
│ 处理时间: {result.processing_time_ms:.1f}ms
└─────────────────────────────────────────────┘
"""

    def process_result(self, result):
        if self.config.format == OutputFormat.CUSTOM:
            output = self.format_custom_output(result)
            print(output)
        else:
            super().process_result(result)
```

### 性能监控
```python
# 输出性能监控
def monitor_output_performance(handler):
    stats = handler.get_statistics()

    print(f"输出统计:")
    print(f"  总输出次数: {stats.total_outputs}")
    print(f"  总字符数: {stats.total_characters}")
    print(f"  输出速率: {stats.output_rate:.2f} 次/秒")
    print(f"  字符速率: {stats.character_rate:.2f} 字符/秒")

# 定期监控
import threading
import time

def periodic_monitor(handler, interval=10):
    while handler.is_running:
        monitor_output_performance(handler)
        time.sleep(interval)

monitor_thread = threading.Thread(
    target=periodic_monitor,
    args=(handler, 5),
    daemon=True
)
monitor_thread.start()
```

## 常见问题 (FAQ)

### Q: 中文字符显示乱码如何解决？
A: 确保输出编码设置为UTF-8，检查终端的编码设置

### Q: 实时输出有延迟怎么办？
A: 启用auto_flush，减少buffer_size，使用独立输出线程

### Q: 如何添加新的输出格式？
A: 在OutputFormat枚举中添加新格式，实现对应的格式化方法

### Q: 文件输出权限被拒绝？
A: 检查文件路径权限，确保目录存在，使用绝对路径

### Q: 输出性能影响转录速度？
A: 使用异步输出处理，避免在主线程中执行耗时的输出操作

## 相关文件列表
- `handler.py` - 输出处理器实现，包含格式化和输出逻辑
- `models.py` - 输出相关数据模型和配置定义
- `__init__.py` - 模块初始化文件

## 变更日志 (Changelog)
- **2025-09-27**: 创建输出处理模块文档，包含多格式输出支持和性能优化指南