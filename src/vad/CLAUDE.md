# 语音活动检测模块 (Voice Activity Detection)

[根目录](../../CLAUDE.md) > [src](../) > **vad**

## 模块职责
基于Silero VAD模型实现实时语音活动检测，区分语音和非语音音频段，提供可配置的检测敏感度和状态管理，为转录引擎提供预处理支持。

## 入口和启动
- **主检测器**: `detector.py::VoiceActivityDetector`
- **VAD管理器**: `vad_manager.py::VadManager` (单例模式，智能复用)
- **VAD配置**: `models.py::VadConfig`
- **模型加载**: 自动下载并加载Silero VAD v5模型或 Ten VAD 模型
- **集成方式**: 由`TranscriptionPipeline`通过`VadManager`创建并管理VAD检测器

## 外部接口

### 主要类和方法

#### VAD 管理器（推荐使用）
```python
# VAD 检测器管理器 - 单例模式
class VadManager:
    # 类方法 - 推荐使用方式
    @classmethod
    def get_detector(cls, config: VadConfig) -> VoiceActivityDetector
        """获取或创建 VAD 检测器（智能复用）"""

    @classmethod
    def release(cls) -> None
        """释放所有检测器资源（应用退出时调用）"""

    @classmethod
    def get_statistics(cls) -> Dict[str, Any]
        """获取检测器使用统计信息"""

    @classmethod
    def is_detector_loaded(cls) -> bool
        """检查是否有已加载的检测器"""

    @classmethod
    def get_current_model_type(cls) -> Optional[str]
        """获取当前加载的模型类型"""

# 使用示例
config = VadConfig(threshold=0.5)
detector = VadManager.get_detector(config)  # 首次加载
detector2 = VadManager.get_detector(config)  # 复用已加载的检测器
```

#### 语音活动检测器
```python
# 语音活动检测器（通过 VadManager 获取）
class VoiceActivityDetector:
    def __init__(self, config: VadConfig)                    # 初始化VAD检测器
    def process_audio(self, audio_data: np.ndarray) -> VadResult  # 处理音频数据
    def add_callback(self, callback) -> None                 # 添加结果回调
    def remove_callback(self, callback) -> None              # 移除回调
    def reset_state(self) -> None                           # 重置检测状态
    def get_statistics(self) -> VadStatistics               # 获取检测统计
    def is_model_loaded(self) -> bool                       # 检查模型是否已加载

    # 状态管理
    @property
    def current_state(self) -> VadState                     # 当前检测状态
    @property
    def confidence_threshold(self) -> float                 # 置信度阈值

# 结果处理
@dataclass
class VadResult:
    state: VadState                    # 检测状态 (SPEECH/SILENCE)
    confidence: float                  # 置信度 (0.0-1.0)
    timestamp: float                   # 时间戳
    audio_data: Optional[np.ndarray]   # 音频数据(仅语音段)
    duration_ms: float                 # 音频段持续时间
    is_speech_start: bool = False      # 是否为语音开始
    is_speech_end: bool = False        # 是否为语音结束

# 语音段信息
@dataclass
class SpeechSegment:
    start_time: float                  # 开始时间
    end_time: float                    # 结束时间
    confidence: float                  # 平均置信度
    audio_data: np.ndarray            # 音频数据
    sample_rate: int                  # 采样率
```

### 配置模型
```python
@dataclass
class VadConfig:
    model: VadModel = VadModel.SILERO       # VAD模型类型
    threshold: float = 0.5                     # 检测阈值 (0.0-1.0)
    window_size_samples: int = 512             # 窗口大小(采样点)
    sample_rate: int = 16000                   # 采样率
    min_speech_duration_ms: float = 250.0     # 最小语音持续时间
    min_silence_duration_ms: float = 100.0    # 最小静音持续时间
    return_confidence: bool = True             # 是否返回置信度
    batch_size: int = 1                       # 批处理大小

    def validate(self) -> bool                 # 验证配置有效性
```

### 枚举和异常
```python
class VadModel(Enum):
    SILERO = "SILERO"           # Silero VAD v4模型

class VadState(Enum):
    SILENCE = "silence"               # 静音状态
    SPEECH = "speech"                 # 语音状态
    UNKNOWN = "unknown"               # 未知状态

# 自定义异常
class VadError(Exception): pass
class ModelLoadError(VadError): pass
class DetectionError(VadError): pass
class ConfigurationError(VadError): pass

# 统计信息
@dataclass
class VadStatistics:
    total_audio_processed: int = 0    # 处理的音频总量
    speech_segments_detected: int = 0  # 检测到的语音段数
    total_speech_duration: float = 0.0  # 总语音持续时间
    total_silence_duration: float = 0.0  # 总静音持续时间
    average_confidence: float = 0.0   # 平均置信度
    last_detection_time: float = 0.0  # 最后检测时间
```

## 关键依赖和配置

### 外部依赖
- **silero_vad**: Silero VAD模型库
- **torch**: PyTorch深度学习框架
- **numpy**: 音频数据处理
- **onnxruntime**: ONNX模型推理(可选)

### 模型管理
```python
# 模型自动下载和缓存
def download_silero_vad_model():
    """自动下载Silero VAD模型到models/目录"""
    model_path = "models/silero-vad/"
    if not os.path.exists(model_path):
        # 自动下载模型文件
        torch.hub.download_url_to_file(model_url, model_path)

# 模型加载和初始化
model = torch.jit.load('models/silero-vad/silero_vad.jit')
model.eval()
```

### 参数调优指南
- **threshold (0.0-1.0)**:
  - 0.1-0.3: 高敏感度，检测微弱语音
  - 0.4-0.6: 中等敏感度(推荐)
  - 0.7-0.9: 低敏感度，只检测清晰语音

- **window_size_samples**:
  - 512: 低延迟，适合实时应用
  - 1024: 平衡延迟和准确性
  - 2048: 高准确性，延迟较高

## 数据模型

### 检测流程
1. **音频预处理**: 重采样到16kHz，归一化音频数据
2. **窗口分割**: 按配置的窗口大小分割音频
3. **模型推理**: 使用Silero VAD模型计算语音概率
4. **状态判断**: 根据阈值判断是否为语音
5. **后处理**: 应用最小持续时间过滤，合并相邻语音段
6. **结果回调**: 通过回调机制发送检测结果

### 状态机设计
```
    [SILENCE] -----(detect speech)-----> [SPEECH]
        ^                                    |
        |                                    |
        +--------(detect silence)-----------+
```

### 语音段合并逻辑
- 相邻语音段间隔小于`min_silence_duration_ms`时自动合并
- 语音段持续时间小于`min_speech_duration_ms`时过滤掉
- 提供完整的语音段边界检测

## 测试和质量保证

### 单元测试覆盖
- **配置验证测试**: `tests/test_vad.py`
  - 有效配置验证
  - 阈值边界测试
  - 模型加载测试

### 功能测试
- **检测准确性测试**: 使用标准语音数据集验证
- **实时性能测试**: 处理延迟和吞吐量测试
- **鲁棒性测试**: 噪声环境下的检测稳定性

### 性能基准
- **处理延迟**: < 50ms (单个窗口)
- **内存使用**: < 100MB (模型加载后)
- **CPU使用**: < 10% (单核心)

## 使用示例

### ⭐ 推荐方式：使用 VadManager（单例模式）
```python
from src.vad import VadManager, VadConfig, VadModel, VadState

# 创建VAD配置
config = VadConfig(
    model=VadModel.SILERO,
    threshold=0.5,
    sample_rate=16000,
    min_speech_duration_ms=250.0,
    return_confidence=True
)

# 使用 VadManager 获取检测器（智能复用）
vad = VadManager.get_detector(config)

# 添加结果处理回调
def handle_vad_result(result):
    if result.state == VadState.SPEECH:
        print(f"检测到语音: 置信度={result.confidence:.2f}")

vad.add_callback(handle_vad_result)

# 处理音频数据
import numpy as np
audio_data = np.random.randn(16000).astype(np.float32)
vad.process_audio(audio_data)

# 应用退出时释放资源
VadManager.release()
```

### 传统方式：直接使用 VoiceActivityDetector
```python
from src.vad.detector import VoiceActivityDetector
from src.vad.models import VadConfig, VadModel, VadState

# 创建VAD配置
config = VadConfig(
    model=VadModel.SILERO,
    threshold=0.5,
    sample_rate=16000,
    min_speech_duration_ms=250.0,
    return_confidence=True
)

# 初始化VAD检测器（不复用，每次都创建新实例）
vad = VoiceActivityDetector(config)

# 添加结果处理回调
def handle_vad_result(result):
    if result.state == VadState.SPEECH:
        print(f"检测到语音: 置信度={result.confidence:.2f}")
        if result.is_speech_start:
            print("语音开始")
        # 处理语音音频数据
        process_speech_audio(result.audio_data)
    elif result.state == VadState.SILENCE and result.is_speech_end:
        print("语音结束")

vad.add_callback(handle_vad_result)

# 处理音频流
for audio_chunk in audio_stream:
    result = vad.process_audio(audio_chunk)
    # 结果通过回调函数处理
```

### 高级配置和调优
```python
# 高敏感度配置 - 适合安静环境
sensitive_config = VadConfig(
    threshold=0.3,
    min_speech_duration_ms=100.0,
    min_silence_duration_ms=50.0
)

# 低敏感度配置 - 适合嘈杂环境
robust_config = VadConfig(
    threshold=0.8,
    min_speech_duration_ms=500.0,
    min_silence_duration_ms=200.0
)

# 获取检测统计信息
stats = vad.get_statistics()
print(f"处理音频总量: {stats.total_audio_processed}")
print(f"语音段数量: {stats.speech_segments_detected}")
print(f"平均置信度: {stats.average_confidence:.3f}")
```

### 调试和监控
```python
# 启用详细日志
import logging
logging.getLogger('src.vad').setLevel(logging.DEBUG)

# 实时监控VAD状态
def monitor_vad_state(result):
    print(f"[{result.timestamp:.3f}] {result.state.value} "
          f"(置信度: {result.confidence:.3f})")

vad.add_callback(monitor_vad_state)

# 重置检测状态
vad.reset_state()
```

## 常见问题 (FAQ)

### Q: VAD检测延迟过高如何优化？
A: 减少window_size_samples，使用GPU加速，调整batch_size

### Q: 在嘈杂环境中检测不准确？
A: 提高threshold值(0.7-0.9)，增加min_speech_duration_ms

### Q: 检测过于敏感，误检太多？
A: 降低threshold值，增加min_silence_duration_ms过滤短暂停顿

### Q: 模型加载失败怎么办？
A: 检查网络连接，手动下载模型文件到models/silero-vad/目录

### Q: 如何支持其他VAD模型？
A: 扩展VadModel枚举，在VoiceActivityDetector中添加新模型的加载和推理逻辑

## 相关文件列表
- `detector.py` - VAD检测器实现，包含模型加载和推理
- `models.py` - VAD相关数据模型和配置定义
- `__init__.py` - 模块初始化文件

## 变更日志 (Changelog)
- **2025-09-27**: 创建VAD模块文档，包含Silero VAD集成和完整的配置指南