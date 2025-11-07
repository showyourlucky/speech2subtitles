# Project Context

## Purpose
Speech2Subtitles 是一个基于 sherpa-onnx 和 silero_vad 的**高性能实时语音转录系统**，提供离线、低延迟的语音转文本功能。系统采用事件驱动的流水线架构，支持麦克风和系统音频捕获，具备 GPU 加速能力，适用于实时会议记录、音频转录等场景。

**核心目标：**
- 提供低延迟（< 500ms）的实时语音识别
- 支持离线运行，无需网络连接
- 多语言支持（中文、英语、日语、韩语、粤语）
- 模块化设计，易于扩展

## Tech Stack

### 核心技术栈
- **Python**: 3.10+ (使用 uv 包管理器)
- **深度学习引擎**:
  - sherpa-onnx (语音识别引擎)
  - silero_vad (语音活动检测)
  - sense-voice 模型（多语言识别）
- **音频处理**: PyAudio, numpy, soundfile
- **深度学习框架**: torch, onnxruntime
- **开发工具**: pytest, black, flake8

### 关键依赖
- `sherpa-onnx`: 离线语音识别
- `torch`: VAD 模型推理
- `pyaudio`: 音频设备捕获
- `onnxruntime-gpu`: GPU 加速（可选）

## Project Conventions

### Code Style
- **格式化工具**: Black (line-length=88)
- **代码检查**: flake8
- **命名规范**:
  - 模块: snake_case
  - 类: PascalCase
  - 函数/变量: snake_case
  - 常量: UPPER_SNAKE_CASE
  - 私有成员: _leading_underscore
- **文档字符串**: Google 风格
- **导入顺序**: isort 兼容
- **注释**: 优先使用中文注释

### Architecture Patterns
- **事件驱动架构**: 基于 `TranscriptionPipeline` 的事件处理机制
- **模块化设计**: 清晰的职责分离（音频捕获、VAD、转录、输出）
- **配置管理**: 使用 dataclass 进行类型安全的配置
- **错误处理**: 自定义异常类和详细的错误信息
- **异步处理**: 多线程协调和队列管理

**核心原则：**
- **KISS**: 简单至上，避免不必要的复杂性
- **YAGNI**: 仅实现当前明确需要的功能
- **DRY**: 避免代码重复，抽象共同模式
- **SOLID**: 单一职责、开闭原则等

### Testing Strategy
- **测试框架**: pytest
- **覆盖率要求**:
  - 配置管理: 95%+
  - 音频捕获: 85%+
  - VAD检测: 90%+
  - 输出处理: 95%+
- **测试层次**:
  1. 单元测试：每个模块的核心功能
  2. 集成测试：模块间协作测试
  3. 端到端测试：完整流水线测试
  4. 性能测试：延迟和吞吐量测试
- **运行方式**: `pytest tests/ --cov=src`

### Git Workflow
- **主分支**: master
- **提交规范**:
  - 使用描述性提交信息
  - 关注"为什么"而非"是什么"
  - 简洁（1-2句话）
- **代码审查**: 确保代码质量和测试覆盖率
- **发布流程**: 语义化版本控制

## Domain Context

### 语音识别领域知识
- **采样率**: 默认 16000 Hz（适合语音识别）
- **VAD阈值**: 控制语音活动检测的敏感度
- **音频缓冲**: 平衡延迟和处理效率
- **GPU加速**: CUDA 环境下的性能优化

### 关键概念
- **TranscriptionPipeline**: 事件驱动的流水线协调器
- **AudioCapture**: 音频捕获抽象（麦克风/系统音频）
- **VoiceActivityDetector**: 实时语音活动检测
- **TranscriptionEngine**: 基于 sense-voice 的转录引擎
- **OutputHandler**: 格式化和展示转录结果

### 典型使用场景
1. **实时会议记录**: 麦克风输入 → 实时转录
2. **视频会议转录**: 系统音频捕获 → 转录保存
3. **音频文件处理**: 文件输入 → 批量转录

## Important Constraints

### 技术限制
- **Windows 系统音频**: 需要启用"立体声混音"设备
- **GPU 加速**: 需要 CUDA 环境和 onnxruntime-gpu
- **模型文件**: 需要预先下载 sense-voice 模型（~300MB）
- **内存使用**: 需要 4GB+ 内存（推荐 8GB+）
- **文件编码**: Windows 环境需要注意文件编码格式

### 性能目标
- **音频延迟**: < 100ms
- **转录延迟**: < 500ms (GPU) / < 2s (CPU)
- **内存使用**: < 2GB (含模型)
- **CPU使用**: < 30% (单核心)

### 运行环境
- **Python版本**: 3.10+
- **虚拟环境**: 使用 uv 创建的 .venv
- **激活方式**: `.venv\Scripts\activate` (Windows)
- **包管理**: 使用 `uv pip` 命令

## External Dependencies

### 必需的外部服务
- 无（完全离线运行）

### 模型文件
- **Silero VAD**: 自动下载（首次运行）
- **Sense-Voice**: 需要手动下载到 `models/` 目录
  - 位置: `models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx`
  - 大小: ~300MB
  - 支持语言: 中文、英语、日语、韩语、粤语

### 系统依赖
- **音频设备**: 麦克风或立体声混音设备
- **CUDA**: 可选，用于 GPU 加速
- **音频驱动**: Windows 需要正确的音频驱动配置
