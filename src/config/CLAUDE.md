# 配置管理模块 (Config Management)

[根目录](../../CLAUDE.md) > [src](../) > **config**

## 模块职责
负责系统配置的管理、命令行参数解析、配置验证和默认值设定。提供统一的配置接口，确保所有组件使用一致的配置参数。

## 入口和启动
- **主配置管理器**: `manager.py::ConfigManager`
- **配置数据模型**: `models.py::Config`
- **调用入口**: 由`main.py`创建ConfigManager实例并解析命令行参数

## 外部接口

### 主要类和方法
```python
# 配置管理器 - 处理命令行解析和验证
class ConfigManager:
    def parse_arguments(self, args=None) -> Config  # 解析命令行参数
    def get_default_config() -> Config              # 获取默认配置
    def validate_config(self, config: Config) -> bool  # 验证配置有效性
    def print_config(self, config: Config) -> None  # 打印配置信息

# 配置数据模型 - 存储所有系统配置
@dataclass
class Config:
    model_path: str                    # sense-voice模型文件路径
    input_source: str                  # 音频输入源 ("microphone" | "system")
    use_gpu: bool = True              # 是否启用GPU加速
    vad_sensitivity: float = 0.5      # VAD敏感度 (0.0-1.0)
    output_format: str = "text"       # 输出格式 ("text" | "json")
    device_id: Optional[int] = None   # 音频设备ID
    sample_rate: int = 16000          # 音频采样率
    chunk_size: int = 1024            # 音频块大小
    vad_window_size: float = 0.512    # VAD窗口大小(秒)
    vad_threshold: float = 0.5        # VAD检测阈值
    show_confidence: bool = True      # 显示置信度
    show_timestamp: bool = True       # 显示时间戳

# 音频设备信息
@dataclass
class AudioDevice:
    id: int                           # 设备ID
    name: str                        # 设备名称
    channels: int                    # 声道数
    sample_rate: int                 # 支持的采样率
    is_input: bool                   # 是否为输入设备
    is_default: bool = False         # 是否为默认设备
```

### 配置验证规则
- **模型路径**: 必须存在且为.onnx或.bin格式
- **输入源**: 必须为"microphone"或"system"
- **VAD参数**: 敏感度和阈值必须在0.0-1.0之间
- **采样率**: 必须为[8000, 16000, 22050, 44100, 48000]之一
- **音频块大小**: 必须在1-8192之间

## 关键依赖和配置

### 内部依赖
- `pathlib.Path` - 路径验证
- `argparse` - 命令行参数解析
- `dataclasses` - 配置数据结构

### 配置文件
- **pyproject.toml**: 项目元信息和依赖管理
- **requirements.txt**: Python包依赖列表

### 环境变量支持
```bash
# 可选的环境变量配置
CUDA_VISIBLE_DEVICES=0           # 指定GPU设备
ONNXRUNTIME_LOG_SEVERITY_LEVEL=3 # ONNX运行时日志级别
```

## 数据模型

### 配置验证流程
1. **参数解析**: 通过argparse解析命令行参数
2. **数据模型创建**: 将解析结果映射到Config数据类
3. **自动验证**: Config.__post_init__触发validate()方法
4. **错误处理**: 验证失败抛出ValueError异常

### 默认配置策略
```python
# 获取带默认值的配置实例
config = ConfigManager().get_default_config()
config.model_path = "path/to/model.onnx"  # 唯一需要手动设置的参数
```

### 音频设备管理
```python
# AudioDevice类提供设备信息的标准化表示
device = AudioDevice(
    id=0,
    name="默认麦克风",
    channels=2,
    sample_rate=44100,
    is_input=True,
    is_default=True
)
print(device)  # 自动格式化输出设备信息
```

## 测试和质量保证

### 单元测试覆盖
- **配置验证测试**: `tests/test_config.py`
  - 有效配置验证
  - 无效配置异常处理
  - 默认值设置验证
  - 边界值测试

### 测试用例示例
```python
def test_config_validation():
    """测试配置验证功能"""
    # 测试有效配置
    config = Config(
        model_path="models/valid_model.onnx",
        input_source="microphone"
    )
    assert config.validate() is None  # 无异常表示验证通过

    # 测试无效VAD敏感度
    with pytest.raises(ValueError):
        Config(
            model_path="models/valid_model.onnx",
            input_source="microphone",
            vad_sensitivity=1.5  # 超出有效范围
        )
```

### 使用示例
```python
# 基本用法 - 解析命令行参数
from src.config.manager import ConfigManager

config_manager = ConfigManager()
config = config_manager.parse_arguments()
print(f"使用模型: {config.model_path}")
print(f"输入源: {config.input_source}")

# 编程方式创建配置
config = Config(
    model_path="models/sense-voice.onnx",
    input_source="microphone",
    use_gpu=True,
    vad_sensitivity=0.6
)

# 打印配置信息
config_manager.print_config(config)
```

## 常见问题 (FAQ)

### Q: 如何添加新的配置参数？
A: 1. 在Config数据类中添加新字段
   2. 在ConfigManager._create_parser()中添加命令行参数
   3. 在parse_arguments()中处理新参数
   4. 在validate()中添加验证逻辑

### Q: 配置验证失败如何调试？
A: 查看ValueError异常信息，通常包含具体的验证失败原因和建议的解决方案

### Q: 如何支持配置文件输入？
A: 当前版本仅支持命令行参数，可扩展ConfigManager添加配置文件解析功能

## 相关文件列表
- `manager.py` - 配置管理器实现，命令行参数解析
- `models.py` - 配置数据模型和验证逻辑
- `__init__.py` - 模块初始化文件

## 变更日志 (Changelog)
- **2025-09-27**: 创建配置管理模块文档，包含完整的API说明和使用示例