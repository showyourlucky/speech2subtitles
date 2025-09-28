# VAD双模型支持功能 - 技术规范

## 问题陈述

### 业务问题
当前Speech2Subtitles系统仅支持单一的Silero VAD模型，限制了系统在不同场景下的适应性。用户需要根据音频环境和质量要求选择最适合的VAD模型以获得最佳的语音检测效果。

### 当前状态
- 直接使用torch.hub加载模型，与sherpa-onnx框架分离
- VadModel枚举只包含SILERO和TEN选项
- 模型路径硬编码在detector.py中的torch.hub加载逻辑

### 预期结果
- 支持通过初始化参数选择silero-vad或ten-vad模型
- 基于sherpa-onnx框架统一管理VAD模型
- 保持现有API接口兼容性
- 自动模型下载和管理机制
- 运行时性能与现有实现相当

## 解决方案概览

### 方案策略
采用sherpa-onnx框架重构现有VAD实现，通过工厂模式支持多种VAD模型，保持API向后兼容的同时增强模型选择灵活性。

### 核心修改
1. **枚举扩展**: 在VadModel中添加TEN_VAD选项
2. **配置增强**: VadConfig添加model_path配置项支持自定义模型路径
3. **框架重构**: 使用sherpa-onnx框架替代直接torch.hub集成
4. **工厂模式**: 实现VAD模型工厂，根据配置动态加载模型
5. **模型管理**: 添加自动下载和缓存机制

### 成功标准
- [ ] 支持silero-vad和ten-vad两种模型类型
- [ ] API接口100%向后兼容
- [ ] 模型自动下载功能正常工作
- [ ] 性能指标不低于现有实现
- [ ] 所有现有测试用例通过

## 技术实现

### 数据库修改
无需数据库修改，本功能为计算模块增强。

### 代码修改

#### 文件修改清单
1. **src/vad/models.py** - 扩展枚举和配置类
2. **src/vad/detector.py** - 重构检测器实现
3. **src/vad/__init__.py** - 导出新的工厂类
4. **pyproject.toml** - 添加sherpa-onnx依赖
5. **tests/test_vad.py** - 添加多模型测试用例

#### 具体实现详情

##### 1. 扩展VadModel枚举 (src/vad/models.py)
```python
class VadModel(Enum):
    """VAD模型枚举 - 支持sherpa-onnx框架"""
    SILERO = "silero_vad"              # Silero VAD v4版本
    TEN_VAD = "ten_vad"                       # Ten VAD模型

    @property
    def model_name(self) -> str:
        """获取sherpa-onnx模型名称"""
        mapping = {
            VadModel.SILERO: "silero_vad_v5.onnx",
            VadModel.TEN_VAD: "ten_vad.onnx"
        }
        return mapping[self]

    @property
    def default_path(self) -> str:
        """获取默认模型路径"""
        return f"models/{self.value}/"
```

##### 2. 增强VadConfig配置 (src/vad/models.py)
```python
@dataclass
class VadConfig:
    """VAD配置类 - 支持多模型选择"""
    model: VadModel = VadModel.SILERO
    model_path: Optional[str] = None          # 自定义模型路径
    threshold: float = 0.5
    min_speech_duration_ms: float = 250.0
    min_silence_duration_ms: float = 100.0
    window_size_samples: int = 512
    sample_rate: int = 16000
    return_confidence: bool = True
    use_sherpa_onnx: bool = True             # 启用sherpa-onnx框架

    @property
    def effective_model_path(self) -> str:
        """获取实际使用的模型路径"""
        if self.model_path:
            return self.model_path
        return os.path.join(self.model.default_path, self.model.model_name)

    def validate(self) -> bool:
        """验证配置有效性，包括模型路径检查"""
        if not super().validate():
            return False

        # 检查模型文件是否存在
        if self.use_sherpa_onnx:
            model_file = self.effective_model_path
            if not os.path.exists(model_file):
                logger.warning(f"模型文件不存在: {model_file}，将尝试自动下载")

        return True
```

##### 3. VAD模型工厂类 (src/vad/detector.py)
```python
class VadModelFactory:
    """VAD模型工厂类 - 基于sherpa-onnx框架"""

    @staticmethod
    def create_vad_detector(config: VadConfig):
        """根据配置创建VAD检测器"""
        if config.use_sherpa_onnx:
            return SherpaOnnxVAD(config)
        else:
            # 向后兼容：使用原有torch.hub方式
            return LegacyTorchVAD(config)

    @staticmethod
    def download_model(model_type: VadModel, target_path: str) -> bool:
        """自动下载模型文件"""
        download_urls = {
            VadModel.SILERO: "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx",
            VadModel.TEN_VAD: "https://github.com/modelscope/FunASR/releases/download/v2.0.4/speech_fsmn_vad_zh-cn-16k-common-pytorch.onnx"
        }

        if model_type not in download_urls:
            logger.error(f"不支持的模型类型: {model_type}")
            return False

        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # 使用torch.hub.download_url_to_file下载
            torch.hub.download_url_to_file(
                download_urls[model_type],
                target_path,
                progress=True
            )
            logger.info(f"模型下载成功: {target_path}")
            return True

        except Exception as e:
            logger.error(f"模型下载失败: {e}")
            return False
```

##### 4. sherpa-onnx VAD实现 (src/vad/detector.py)
```python
class SherpaOnnxVAD:
    """基于sherpa-onnx的VAD检测器实现"""

    def __init__(self, config: VadConfig):
        self.config = config
        self._vad_model = None
        self._current_state = VadState.SILENCE
        self._state_duration = 0
        self._statistics = VadStatistics()
        self._callbacks: List[Callable[[VadResult], None]] = []

        self._load_model()

    def _load_model(self) -> None:
        """加载sherpa-onnx VAD模型"""
        try:
            import sherpa_onnx

            model_path = self.config.effective_model_path

            # 检查模型文件是否存在
            if not os.path.exists(model_path):
                logger.info(f"模型文件不存在，开始下载: {model_path}")
                if not VadModelFactory.download_model(self.config.model, model_path):
                    raise ModelLoadError(f"无法下载模型: {model_path}")

            # 创建sherpa-onnx VAD配置
            vad_config = sherpa_onnx.VadModelConfig()
            vad_config.silero_vad.model = model_path
            vad_config.silero_vad.threshold = self.config.threshold
            vad_config.silero_vad.min_silence_duration = self.config.min_silence_duration_ms / 1000.0
            vad_config.silero_vad.min_speech_duration = self.config.min_speech_duration_ms / 1000.0
            vad_config.sample_rate = self.config.sample_rate
            vad_config.num_threads = 1
            vad_config.provider = "cpu"

            # 根据模型类型调整配置
            if self.config.model == VadModel.TEN_VAD:
                # Ten VAD特定配置
                vad_config.ten_vad.model = model_path
                vad_config.ten_vad.threshold = self.config.threshold

            # 创建VAD模型实例
            self._vad_model = sherpa_onnx.VoiceActivityDetector(vad_config)

            logger.info(f"sherpa-onnx VAD模型加载成功: {self.config.model.value}")

        except ImportError:
            raise ModelLoadError("sherpa-onnx库未安装，请运行: pip install sherpa-onnx")
        except Exception as e:
            raise ModelLoadError(f"sherpa-onnx VAD模型加载失败: {e}")

    def detect(self, audio_data: np.ndarray) -> VadResult:
        """使用sherpa-onnx进行VAD检测"""
        start_time = time.time()

        try:
            # 音频数据预处理
            if audio_data.dtype == np.int16:
                audio_float = audio_data.astype(np.float32) / 32768.0
            else:
                audio_float = audio_data.astype(np.float32)

            # 使用sherpa-onnx进行检测
            is_speech = self._vad_model.accept_waveform(audio_float)

            # 获取置信度 (如果模型支持)
            confidence = self.config.threshold + 0.1 if is_speech else self.config.threshold - 0.1

            # 更新状态机
            result = self._update_state(is_speech, confidence, len(audio_data))

            # 更新统计信息
            duration_ms = (len(audio_data) / self.config.sample_rate) * 1000
            self._statistics.update_audio_duration(duration_ms)

            if is_speech:
                self._statistics.update_speech_duration(duration_ms)
            else:
                self._statistics.update_silence_duration(duration_ms)

            processing_time = (time.time() - start_time) * 1000
            self._statistics.update_processing_time(processing_time)

            # 调用回调函数
            self._call_callbacks(result)

            return result

        except Exception as e:
            raise DetectionError(f"sherpa-onnx VAD检测失败: {e}")
```

##### 5. 重构VoiceActivityDetector (src/vad/detector.py)
```python
class VoiceActivityDetector:
    """统一的VAD检测器接口"""

    def __init__(self, config: VadConfig):
        """初始化VAD检测器，根据配置选择实现"""
        self.config = config

        # 使用工厂模式创建具体实现
        self._detector = VadModelFactory.create_vad_detector(config)

        logger.info(f"VAD检测器初始化完成: {config.model.value}")

    def detect(self, audio_data: np.ndarray) -> VadResult:
        """代理到具体实现"""
        return self._detector.detect(audio_data)

    def add_callback(self, callback: Callable[[VadResult], None]) -> None:
        """添加回调函数"""
        self._detector.add_callback(callback)

    def remove_callback(self, callback: Callable[[VadResult], None]) -> None:
        """移除回调函数"""
        self._detector.remove_callback(callback)

    def get_statistics(self) -> VadStatistics:
        """获取统计信息"""
        return self._detector.get_statistics()

    def reset_state(self) -> None:
        """重置状态"""
        self._detector.reset_state()

    @property
    def current_state(self) -> VadState:
        """获取当前状态"""
        return self._detector.current_state
```

### API修改

#### 新增配置选项
```python
# 使用sherpa-onnx silero-vad
config = VadConfig(
    model=VadModel.SILERO,
    use_sherpa_onnx=True
)

# 使用sherpa-onnx ten-vad
config = VadConfig(
    model=VadModel.TEN_VAD,
    use_sherpa_onnx=True
)

# 自定义模型路径
config = VadConfig(
    model=VadModel.TEN_VAD,
    model_path="custom/path/to/ten_vad.onnx"
)

# 向后兼容模式
config = VadConfig(
    model=VadModel.SILERO,
    use_sherpa_onnx=False  # 使用原有torch.hub方式
)
```

#### 保持的现有接口
```python
# 现有API完全保持不变
vad = VoiceActivityDetector(config)
result = vad.detect(audio_data)
vad.add_callback(callback_function)
stats = vad.get_statistics()
```

### 配置修改

#### pyproject.toml依赖更新
```toml
dependencies = [
    "sherpa-onnx>=1.12.9",
    "torch>=2.6.0",
    "silero-vad>=4.0.0",
    "numpy>=1.21.0",
    "PyAudio>=0.2.11",
    "dataclasses-json>=0.5.7",
    "typing-extensions>=4.0.0",
    "soundfile>=0.12.0",
    "librosa>=0.9.0",
]
```

#### 模型目录结构
```
models/
├── silero-vad/
│   └── silero_vad_v5.onnx
└── ten-vad/
    └── ten_vad.onnx
```

## 实施序列

### 第1阶段: 依赖和基础结构 (估时: 2小时)
**任务清单**:
1. 更新pyproject.toml添加sherpa-onnx依赖
2. 在src/vad/models.py中扩展VadModel枚举添加TEN_VAD
3. 增强VadConfig类添加model_path和use_sherpa_onnx字段
4. 创建模型目录结构 models/ten_vad/

**文件修改**:
- `pyproject.toml` - 添加sherpa-onnx>=1.12.9依赖
- `src/vad/models.py` - 扩展枚举和配置类
- `models/` - 创建ten_vad子目录

**验证标准**:
- sherpa-onnx库成功安装
- VadModel.TEN_VAD枚举可用
- VadConfig.model_path属性正常工作

### 第2阶段: sherpa-onnx集成实现 (估时: 4小时)
**任务清单**:
1. 在src/vad/detector.py中实现VadModelFactory类
2. 实现SherpaOnnxVAD检测器类
3. 添加模型自动下载功能
4. 集成sherpa-onnx VAD配置和推理

**文件修改**:
- `src/vad/detector.py` - 添加工厂类和sherpa-onnx实现
- `src/vad/__init__.py` - 导出新类

**验证标准**:
- 工厂模式正确创建VAD实例
- sherpa-onnx模型加载成功
- 模型自动下载功能正常

### 第3阶段: 向后兼容和重构 (估时: 3小时)
**任务清单**:
1. 重构VoiceActivityDetector为统一接口
2. 实现LegacyTorchVAD类保持向后兼容
3. 确保所有现有API保持不变
4. 优化错误处理和日志记录

**文件修改**:
- `src/vad/detector.py` - 重构主检测器类
- `tests/test_vad.py` - 验证API兼容性

**验证标准**:
- 所有现有测试用例通过
- API接口100%向后兼容
- 错误处理机制完善

### 第4阶段: 测试和文档 (估时: 2小时)
**任务清单**:
1. 添加多模型单元测试用例
2. 创建集成测试验证模型切换
3. 更新模块文档和使用示例
4. 性能对比测试

**文件修改**:
- `tests/test_vad.py` - 添加多模型测试
- `src/vad/CLAUDE.md` - 更新文档
- `tools/vad_test.py` - 添加性能测试

**验证标准**:
- 测试覆盖率≥90%
- 性能指标不低于现有实现
- 文档完整准确

## 验证方案

### 单元测试场景
```python
def test_vad_model_factory():
    """测试VAD模型工厂"""
    # 测试silero-vad创建
    config = VadConfig(model=VadModel.SILERO, use_sherpa_onnx=True)
    vad = VadModelFactory.create_vad_detector(config)
    assert isinstance(vad, SherpaOnnxVAD)

    # 测试ten-vad创建
    config = VadConfig(model=VadModel.TEN_VAD, use_sherpa_onnx=True)
    vad = VadModelFactory.create_vad_detector(config)
    assert isinstance(vad, SherpaOnnxVAD)

    # 测试向后兼容
    config = VadConfig(model=VadModel.SILERO, use_sherpa_onnx=False)
    vad = VadModelFactory.create_vad_detector(config)
    assert isinstance(vad, LegacyTorchVAD)

def test_model_auto_download():
    """测试模型自动下载"""
    temp_path = "temp/test_model.onnx"
    success = VadModelFactory.download_model(VadModel.TEN_VAD, temp_path)
    assert success == True
    assert os.path.exists(temp_path)

def test_api_compatibility():
    """测试API向后兼容性"""
    # 使用新配置的旧接口
    config = VadConfig(model=VadModel.TEN_VAD)
    vad = VoiceActivityDetector(config)

    # 验证所有旧接口仍然可用
    assert hasattr(vad, 'detect')
    assert hasattr(vad, 'add_callback')
    assert hasattr(vad, 'get_statistics')
    assert hasattr(vad, 'current_state')
```

### 集成测试场景
```python
def test_end_to_end_vad_detection():
    """端到端VAD检测测试"""
    test_audio = generate_test_audio()  # 生成测试音频

    # 测试两种模型的检测结果
    configs = [
        VadConfig(model=VadModel.SILERO, use_sherpa_onnx=True),
        VadConfig(model=VadModel.TEN_VAD, use_sherpa_onnx=True)
    ]

    for config in configs:
        vad = VoiceActivityDetector(config)
        result = vad.detect(test_audio)

        assert isinstance(result, VadResult)
        assert result.confidence >= 0.0 and result.confidence <= 1.0
        assert result.state in VadState

        stats = vad.get_statistics()
        assert stats.total_audio_duration_ms > 0
```

### 性能验证目标
- **模型加载时间**: < 3秒 (首次加载含下载)
- **检测延迟**: < 50ms (单帧处理)
- **内存占用**: < 200MB (包含模型)
- **CPU使用率**: < 15% (单核)
- **向后兼容**: 100% API兼容性

### 业务逻辑验证
1. **模型切换功能**: 验证通过配置可以无缝切换VAD模型
2. **自动下载机制**: 验证模型文件缺失时自动下载功能
3. **错误恢复**: 验证模型加载失败时的降级策略
4. **配置验证**: 验证无效配置的错误处理机制
5. **统计功能**: 验证不同模型的统计信息准确性

---

**实施优先级**: 🔥 高优先级 - 增强系统模型选择灵活性的核心功能
**预估工作量**: 11小时 (包含测试和文档)
**技术风险**: ⚠️ 中等 - 需要仔细处理API兼容性和依赖管理
**依赖关系**: 依赖sherpa-onnx库的稳定性和模型文件的可访问性