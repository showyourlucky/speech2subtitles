# 实时语音转录系统

一个基于 sherpa-onnx 和 silero_vad 的高性能实时语音识别系统，支持麦克风和系统音频捕获，提供离线语音转文本功能。

## ✨ 特性

- 🎯 **实时转录**：低延迟语音转文字，支持实时处理
- 🔒 **完全离线**：无需网络连接，保护隐私数据
- 🎤 **多音频源**：支持麦克风和系统音频捕获
- ⚡ **GPU加速**：支持CUDA加速，提升处理性能
- 🎛️ **智能VAD**：基于silero_vad的语音活动检测
- 🛠️ **命令行界面**：简单易用的CLI工具
- 🔧 **高度可配置**：灵活的参数配置和模型选择

## 📋 系统要求

### 基础要求
- **操作系统**：Windows 10/11, Linux, macOS
- **Python版本**：3.10 或更高
- **内存**：推荐 8GB 以上
- **存储空间**：至少 2GB 可用空间
- **FFmpeg**：用于媒体文件转换（离线字幕生成模式必需）

### 硬件要求
- **CPU**：现代多核处理器
- **GPU（可选）**：支持CUDA的NVIDIA显卡（推荐用于加速）
- **音频设备**：麦克风或音频输入设备

## 🚀 快速开始

### 1. 安装FFmpeg (媒体文件转字幕功能必需)

Speech2Subtitles使用FFmpeg进行媒体格式转换。请根据您的操作系统安装FFmpeg:

#### Windows

**方法1: 使用包管理器 (推荐)**
```bash
# 使用 Chocolatey
choco install ffmpeg

# 或使用 Scoop
scoop install ffmpeg
```

**方法2: 手动安装**
1. 访问 https://www.gyan.dev/ffmpeg/builds/
2. 下载 "ffmpeg-release-essentials.zip"
3. 解压到 `C:\ffmpeg\`
4. 添加 `C:\ffmpeg\bin` 到系统PATH环境变量:
   - 右键"此电脑" → 属性 → 高级系统设置
   - 环境变量 → 系统变量 → Path → 编辑
   - 新建 → 输入 `C:\ffmpeg\bin` → 确定
5. 验证安装:
   ```cmd
   ffmpeg -version
   ```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install ffmpeg

# 验证安装
ffmpeg -version
```

#### macOS

```bash
# 使用 Homebrew
brew install ffmpeg

# 验证安装
ffmpeg -version
```

#### 验证FFmpeg安装

运行以下命令确认FFmpeg已正确安装:
```bash
ffmpeg -version
```

应该看到FFmpeg的版本信息,例如:
```
ffmpeg version 6.0 Copyright (c) 2000-2023 the FFmpeg developers
...
```

### 2. 安装Python依赖

#### 使用 uv（推荐）
```bash
# 安装 uv
pip install uv

# 克隆项目
git clone <repository-url>
cd speech2subtitles

# 创建虚拟环境并安装依赖
uv sync
```

#### 使用 pip
```bash
# 克隆项目
git clone <repository-url>
cd speech2subtitles

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 准备模型文件

下载 sense-voice 模型文件：
- 支持 `.onnx` 和 `.bin` 格式
- 推荐下载官方预训练模型
- 将模型文件放置在 `models/` 目录下

```bash
# 创建模型目录
mkdir models

# 下载示例模型（请替换为实际下载链接）
# wget -O models/sense-voice.onnx <model-download-url>
```

### 4. 运行系统

#### 模式1: 实时音频转录

**基本用法**
```bash
# 激活虚拟环境（如果使用uv）
.venv\Scripts\activate

# 麦克风输入
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone

# 系统音频输入
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source system --no-gpu
```

#### 模式2: 媒体文件转字幕 (新功能)

**基本用法**
```bash
# 单个文件
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-file video.mp4

# 多个文件
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-file video1.mp4 audio1.mp3 lecture.avi

# 处理目录
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-file ./videos/
```

**高级用法**
```bash
# 指定输出目录和字幕格式
python main.py \
    --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx \
    --input-file video.mp4 \
    --output-dir ./subtitles/ \
    --subtitle-format srt \
    --verbose

# 保留临时文件用于调试
python main.py \
    --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx \
    --input-file video.mp4 \
    --keep-temp \
    --no-gpu
```

**支持的媒体格式**
- **视频**: avi, flv, mkv, mov, mp4, mpeg, webm, wmv
- **音频**: aac, amr, flac, m4a, mp3, ogg, opus, wav, wma

## 📖 详细使用指南

### 命令行参数

#### 必需参数
- `--model-path`：sense-voice模型文件路径
- `--input-source` 或 `--input-file`：选择运行模式（二选一）
  - `--input-source`：实时音频转录（`microphone` 或 `system`）
  - `--input-file`：离线文件转字幕（文件/目录路径）

#### 实时转录可选参数
- `--vad-sensitivity`：VAD敏感度（0.0-1.0，默认0.5）
- `--output-format`：输出格式（text/json，默认text）
- `--device-id`：指定音频设备ID
- `--no-confidence`：不显示置信度
- `--no-timestamp`：不显示时间戳

#### 离线字幕生成可选参数
- `--output-dir`：字幕输出目录（默认与输入文件同目录）
- `--subtitle-format`：字幕格式（srt/vtt/ass，默认srt）
- `--keep-temp`：保留临时音频文件
- `--verbose`：显示详细处理过程

#### 通用可选参数
- `--no-gpu`：禁用GPU加速
- `--sample-rate`：采样率（默认16000Hz）
- `--vad-threshold`：VAD阈值（默认0.5）
- `--help`：显示帮助信息

### 音频输入源说明

#### 麦克风输入 (`microphone`)
- 从系统默认麦克风捕获音频
- 适用于实时语音输入、会议记录等场景
- 需要确保麦克风权限已授予

#### 系统音频输入 (`system`)
- 从系统音频输出捕获音频
- 适用于转录视频播放、网络会议等场景
- 支持捕获浏览器、播放器等应用的音频

### VAD（语音活动检测）配置

VAD敏感度参数控制语音检测的灵敏度：
- `0.1-0.3`：高敏感度，检测微弱语音
- `0.4-0.6`：中等敏感度（推荐）
- `0.7-0.9`：低敏感度，只检测清晰语音

### GPU加速配置

系统会自动检测CUDA环境：
- 如果检测到CUDA，默认启用GPU加速
- 使用 `--no-gpu` 强制使用CPU处理
- GPU加速可显著提升处理速度

## 🔧 配置文件

### 项目结构
```
speech2subtitles/
├── main.py                    # 主程序入口
├── requirements.txt           # 依赖列表
├── pyproject.toml            # 项目配置
├── README.md                 # 用户文档
├── models/                   # 模型文件目录
├── src/                      # 源代码
│   ├── config/              # 配置管理
│   ├── audio/               # 音频捕获
│   ├── vad/                 # 语音活动检测
│   ├── transcription/       # 转录引擎
│   ├── output/              # 输出处理
│   ├── hardware/            # 硬件检测
│   ├── coordinator/         # 流程协调
│   └── utils/               # 工具函数
├── tests/                   # 测试文件
├── tools/                   # 调试工具
└── .spec-workflow/          # 规范文档
```

### 环境变量（可选）
```bash
# GPU相关
export CUDA_VISIBLE_DEVICES=0
export ONNXRUNTIME_LOG_SEVERITY_LEVEL=3

# 音频相关
export PULSE_RUNTIME_PATH=/tmp/pulse
```

## 🛠️ 故障排除

### 常见问题

#### 1. 模块导入错误
```
ModuleNotFoundError: No module named 'xxx'
```
**解决方案：**
```bash
# 确保虚拟环境已激活
.venv\Scripts\activate

# 重新安装依赖
pip install -r requirements.txt
```

#### 2. 音频权限问题
```
PermissionError: [Errno 13] Permission denied
```
**解决方案：**
- 确保应用程序具有麦克风访问权限
- Windows：设置 → 隐私 → 麦克风 → 允许应用访问麦克风

#### 3. CUDA相关错误
```
CUDA driver version is insufficient
```
**解决方案：**
- 更新NVIDIA驱动程序
- 或使用 `--no-gpu` 参数强制CPU处理

#### 4. 模型加载失败
```
Failed to load model: xxx
```
**解决方案：**
- 检查模型文件路径是否正确
- 确保模型文件格式受支持（.onnx 或 .bin）
- 验证模型文件是否损坏

#### 5. 音频设备未找到
```
No audio input device found
```
**解决方案：**
```bash
# 运行音频设备检测工具
python tools/audio_info.py

# 检查系统音频设备
```

### 调试工具

项目提供了多个调试工具：

```bash
# 检查GPU信息
python tools/gpu_info.py

# 检查音频设备
python tools/audio_info.py

# 测试VAD功能
python tools/vad_test.py

# 运行集成测试
python test_integration.py
```

### 日志分析

启用调试日志：
```bash
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG
```

日志文件位置：
- 控制台输出：实时显示
- 文件输出：可配置日志文件路径

## ⚡ 性能优化

### 硬件优化建议

1. **GPU加速**
   - 使用NVIDIA GPU可显著提升性能
   - 推荐显存 ≥ 4GB
   - 确保CUDA环境正确安装

2. **CPU优化**
   - 推荐使用多核CPU
   - 增加系统内存可提升缓冲性能

3. **音频配置**
   - 使用高质量音频设备
   - 调整麦克风增益避免失真
   - 在安静环境中使用以提升识别准确率

### 系统调优

1. **VAD参数调整**
   ```bash
   # 针对安静环境
   python main.py --vad-sensitivity 0.3 ...

   # 针对嘈杂环境
   python main.py --vad-sensitivity 0.8 ...
   ```

2. **模型选择**
   - 较大模型：更高精度，更高延迟
   - 较小模型：更低延迟，适中精度

## 🧪 测试

### 运行测试套件
```bash
# 运行所有测试
python run_tests.py

# 运行特定测试
pytest tests/test_config.py -v

# 运行带覆盖率的测试
pytest tests/ --cov=src --cov-report=html
```

### 集成测试
```bash
# 快速集成测试
python quick_test.py

# 完整集成测试
python test_integration.py
```

## 📚 API参考

主要组件和接口：

### ConfigManager
配置管理和命令行解析
```python
from src.config.manager import ConfigManager
config_manager = ConfigManager()
config = config_manager.parse_arguments()
```

### TranscriptionPipeline
核心转录流水线
```python
from src.coordinator.pipeline import TranscriptionPipeline
pipeline = TranscriptionPipeline(config)
with pipeline:
    pipeline.run()
```

### AudioCapture
音频捕获组件
```python
from src.audio.capture import AudioCapture
capture = AudioCapture(config)
```

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 支持

如遇问题请：
1. 查看本文档的故障排除部分
2. 查看项目 Issues
3. 运行调试工具获取更多信息
4. 创建新的 Issue 并提供详细的错误信息

## 📊 系统监控

程序运行时会显示：
- 实时转录结果
- 系统状态信息
- 性能指标
- 错误和警告信息

按 `Ctrl+C` 可安全停止程序。

---

**感谢使用实时语音转录系统！**