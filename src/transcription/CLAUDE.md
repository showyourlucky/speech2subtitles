# 转录引擎模块 (Transcription Engine)

[根目录](../../CLAUDE.md) > [src](../) > **transcription**

## 模块职责
基于sherpa-onnx和sense-voice模型实现高质量语音转文本功能，支持GPU/CPU优化、多语言识别、批量处理和实时转录。提供统一的转录接口和性能监控。

## 入口和启动
- **主引擎**: `engine.py::TranscriptionEngine`
- **转录配置**: `models.py::TranscriptionConfig`
- **模型支持**: sense-voice (.onnx/.bin格式)
- **集成方式**: 由`TranscriptionPipeline`创建，接收VAD处理后的语音数据

## 外部接口

### 主要类和方法
```python
# 转录引擎主类
class TranscriptionEngine:
    def __init__(self, config: TranscriptionConfig)         # 初始化转录引擎
    def transcribe_audio(self, audio_data: np.ndarray) -> TranscriptionResult  # 转录音频数据
    def transcribe_batch(self, audio_batches: List[np.ndarray]) -> BatchTranscriptionResult  # 批量转录
    def add_callback(self, callback) -> None                # 添加结果回调
    def remove_callback(self, callback) -> None             # 移除回调
    def get_model_info(self) -> ModelInfo                   # 获取模型信息
    def get_statistics(self) -> TranscriptionStatistics     # 获取转录统计
    def is_model_loaded(self) -> bool                       # 检查模型加载状态
    def reset_statistics(self) -> None                      # 重置统计信息

    # 性能优化
    def warm_up(self) -> None                               # 模型预热
    def set_processor_type(self, processor_type: ProcessorType) -> None  # 设置处理器类型

# 转录结果
@dataclass
class TranscriptionResult:
    text: str                          # 转录文本
    confidence: float                  # 置信度 (0.0-1.0)
    language: LanguageCode            # 检测到的语言
    timestamp: float                  # 时间戳
    duration_ms: float                # 音频持续时间
    processing_time_ms: float         # 处理时间
    word_timestamps: List[WordTimestamp] = None  # 词级时间戳(可选)
    speaker_id: Optional[str] = None   # 说话人ID(如果支持)

# 批量转录结果
@dataclass
class BatchTranscriptionResult:
    results: List[TranscriptionResult] # 转录结果列表
    total_processing_time_ms: float   # 总处理时间
    batch_size: int                   # 批次大小
    average_confidence: float         # 平均置信度
```

### 配置模型
```python
@dataclass
class TranscriptionConfig:
    model: TranscriptionModel = TranscriptionModel.SENSE_VOICE  # 模型类型
    model_path: str                                             # 模型文件路径
    language: LanguageCode = LanguageCode.AUTO                  # 目标语言
    processor_type: ProcessorType = ProcessorType.AUTO         # 处理器类型
    sample_rate: int = 16000                                   # 音频采样率
    use_gpu: bool = True                                       # 是否使用GPU
    beam_size: int = 5                                         # 束搜索大小
    max_active_paths: int = 4                                  # 最大活跃路径
    context_size: int = 2                                      # 上下文大小
    decoding_method: str = "greedy_search"                     # 解码方法
    enable_timestamp: bool = True                              # 启用时间戳
    enable_word_alignment: bool = False                        # 启用词对齐

    def validate(self) -> bool                                 # 验证配置有效性
```

### 枚举类型
```python
class TranscriptionModel(Enum):
    SENSE_VOICE = "sense_voice"           # sense-voice模型
    WHISPER = "whisper"                   # Whisper模型(预留)

class LanguageCode(Enum):
    AUTO = "auto"                         # 自动检测
    ZH_CN = "zh-cn"                      # 简体中文
    EN_US = "en-us"                      # 美式英语
    JA_JP = "ja-jp"                      # 日语
    KO_KR = "ko-kr"                      # 韩语
    YUE_HK = "yue-hk"                    # 粤语

class ProcessorType(Enum):
    AUTO = "auto"                         # 自动选择
    CPU = "cpu"                          # CPU处理
    GPU = "gpu"                          # GPU处理
    ONNX_CPU = "onnx_cpu"                # ONNX CPU推理
    ONNX_GPU = "onnx_gpu"                # ONNX GPU推理

# 自定义异常
class TranscriptionError(Exception): pass
class ModelLoadError(TranscriptionError): pass
class TranscriptionProcessingError(TranscriptionError): pass
class UnsupportedModelError(TranscriptionError): pass
class AudioFormatError(TranscriptionError): pass
```

### 统计和监控
```python
@dataclass
class TranscriptionStatistics:
    total_requests: int = 0               # 总转录请求数
    successful_transcriptions: int = 0    # 成功转录数
    failed_transcriptions: int = 0        # 失败转录数
    total_processing_time: float = 0.0    # 总处理时间
    total_audio_duration: float = 0.0     # 总音频时长
    average_confidence: float = 0.0       # 平均置信度
    real_time_factor: float = 0.0         # 实时因子 (处理时间/音频时长)

    @property
    def success_rate(self) -> float:      # 成功率
        if self.total_requests == 0:
            return 0.0
        return self.successful_transcriptions / self.total_requests

@dataclass
class ModelInfo:
    name: str                            # 模型名称
    version: str                         # 模型版本
    supported_languages: List[LanguageCode]  # 支持的语言
    sample_rate: int                     # 建议采样率
    input_channels: int                  # 输入声道数
    model_size_mb: float                 # 模型大小(MB)
    loaded_time: float                   # 加载时间戳

@dataclass
class WordTimestamp:
    word: str                            # 词汇
    start_time: float                    # 开始时间
    end_time: float                      # 结束时间
    confidence: float                    # 置信度
```

## 关键依赖和配置

### 外部依赖
- **sherpa-onnx**: 核心语音识别库
- **onnxruntime**: ONNX模型推理引擎
- **torch**: PyTorch深度学习框架(可选)
- **numpy**: 音频数据处理

### 模型管理
```python
# sense-voice模型配置
SENSE_VOICE_CONFIG = {
    "tokens": "models/sherpa-onnx-sense-voice/tokens.txt",
    "encoder": "models/sherpa-onnx-sense-voice/model.onnx",
    "use_itn": True,  # 启用逆文本归一化
    "num_threads": 4,  # 线程数
}

# GPU加速配置
GPU_PROVIDER_OPTIONS = {
    "device_id": 0,
    "arena_extend_strategy": "kNextPowerOfTwo",
    "gpu_mem_limit": 2 * 1024 * 1024 * 1024,  # 2GB限制
}
```

### 性能优化参数
- **beam_size**: 控制搜索宽度，影响准确性和速度
- **max_active_paths**: 限制并发路径数，平衡内存和性能
- **num_threads**: CPU线程数，根据硬件配置调整
- **chunk_size**: 音频块大小，影响实时性和准确性

## 数据模型

### 转录流程
1. **音频预处理**: 重采样、归一化、格式转换
2. **模型推理**: 使用sherpa-onnx进行语音识别
3. **后处理**: 文本清理、标点符号、时间戳对齐
4. **置信度计算**: 计算转录结果的可信度
5. **结果封装**: 创建TranscriptionResult对象
6. **回调分发**: 通过回调机制发送结果

### 实时转录优化
```python
# 流式处理配置
streaming_config = TranscriptionConfig(
    model_path="models/sense-voice-streaming.onnx",
    chunk_size=1600,  # 100ms @ 16kHz
    overlap_size=320,  # 20ms重叠
    enable_vad_endpoint=True,  # VAD端点检测
    max_segment_length=30.0    # 最大段长度(秒)
)
```

### 多语言支持
- **自动语言检测**: 基于音频内容自动识别语言
- **多语言混合**: 支持在同一音频中处理多种语言
- **语言特定优化**: 针对不同语言的专门配置

## 测试和质量保证

### 单元测试覆盖
- **配置验证测试**: `tests/test_transcription.py`
  - 配置参数验证
  - 模型路径检查
  - GPU/CPU模式切换

### 功能测试
- **转录准确性测试**: 使用标准语音数据集
- **多语言测试**: 验证各语言的识别能力
- **性能基准测试**: 测试处理速度和内存使用

### 质量指标
- **WER (Word Error Rate)**: < 5% (标准语音)
- **实时因子**: < 0.3 (GPU), < 1.0 (CPU)
- **延迟**: < 200ms (流式处理)

## 使用示例

### 基本转录使用
```python
from src.transcription.engine import TranscriptionEngine
from src.transcription.models import TranscriptionConfig, TranscriptionModel, LanguageCode

# 创建转录配置
config = TranscriptionConfig(
    model=TranscriptionModel.SENSE_VOICE,
    model_path="models/sense-voice.onnx",
    language=LanguageCode.ZH_CN,
    use_gpu=True,
    enable_timestamp=True
)

# 初始化转录引擎
engine = TranscriptionEngine(config)

# 添加结果处理回调
def handle_transcription(result):
    print(f"转录结果: {result.text}")
    print(f"置信度: {result.confidence:.3f}")
    print(f"处理时间: {result.processing_time_ms:.1f}ms")

engine.add_callback(handle_transcription)

# 转录音频数据
audio_data = load_audio_data("audio.wav")
result = engine.transcribe_audio(audio_data)
```

### 批量转录处理
```python
# 批量处理配置
batch_config = TranscriptionConfig(
    model_path="models/sense-voice.onnx",
    processor_type=ProcessorType.GPU,
    beam_size=10,  # 提高准确性
    enable_word_alignment=True
)

engine = TranscriptionEngine(batch_config)

# 批量转录
audio_files = ["file1.wav", "file2.wav", "file3.wav"]
audio_batches = [load_audio(f) for f in audio_files]

batch_result = engine.transcribe_batch(audio_batches)
print(f"批量处理完成: {len(batch_result.results)} 个文件")
print(f"平均置信度: {batch_result.average_confidence:.3f}")
```

### 性能监控和调优
```python
# 获取模型信息
model_info = engine.get_model_info()
print(f"模型: {model_info.name} v{model_info.version}")
print(f"支持语言: {[lang.value for lang in model_info.supported_languages]}")

# 模型预热(提高首次转录速度)
engine.warm_up()

# 获取性能统计
stats = engine.get_statistics()
print(f"成功率: {stats.success_rate:.1%}")
print(f"实时因子: {stats.real_time_factor:.2f}")
print(f"平均置信度: {stats.average_confidence:.3f}")

# 动态调整处理器类型
if stats.real_time_factor > 1.0:
    engine.set_processor_type(ProcessorType.GPU)
```

## 常见问题 (FAQ)

### Q: 模型加载失败如何处理？
A: 检查模型文件路径和格式，确保依赖库版本兼容，查看详细错误日志

### Q: GPU内存不足怎么办？
A: 减少beam_size和max_active_paths，或切换到CPU模式

### Q: 转录准确率不高如何改善？
A: 提高音频质量，调整VAD阈值，使用更大的beam_size，选择合适的语言模式

### Q: 实时性能不佳如何优化？
A: 使用GPU加速，减少chunk_size，启用流式处理，调整线程数

### Q: 如何支持新的语言？
A: 下载对应语言的模型文件，在LanguageCode枚举中添加新语言代码

## 相关文件列表
- `engine.py` - 转录引擎实现，包含模型加载和推理逻辑
- `models.py` - 转录相关数据模型和配置定义
- `__init__.py` - 模块初始化文件

## 变更日志 (Changelog)
- **2025-09-27**: 创建转录引擎模块文档，包含sherpa-onnx集成和完整的性能优化指南