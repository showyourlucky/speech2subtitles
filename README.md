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
uv v

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
python main.py --model-path models\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\model.onnx --input-source microphone

# 系统音频输入
python main.py --model-path models\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\model.onnx --input-source system --no-gpu
```

#### 模式2: 媒体文件转字幕 (新功能)

**基本用法**
```bash
# 单个文件
python main.py --model-path models\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\model.onnx --input-file video.mp4

# 多个文件
python main.py --model-path models\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\model.onnx --input-file video1.mp4 audio1.mp3 lecture.avi

# 处理目录
python main.py --model-path models\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\model.onnx --input-file ./videos/
```

**高级用法**
```bash
# 指定输出目录和字幕格式
python main.py \
    --model-path models\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\model.onnx \
    --input-file video.mp4 \
    --output-dir ./subtitles/ \
    --subtitle-format srt \
    --verbose

# 保留临时文件用于调试
python main.py \
    --model-path models\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\model.onnx \
    --input-file video.mp4 \
    --keep-temp \
    --no-gpu
```

**支持的媒体格式**
- **视频**: avi, flv, mkv, mov, mp4, mpeg, webm, wmv
- **音频**: aac, amr, flac, m4a, mp3, ogg, opus, wav, wma

## 📖 详细使用指南

### 命令行参数

#### 运行模式参数（可选）
- `--model-path`：sense-voice模型文件路径（未传时使用 `config/gui_config.json` 中激活模型方案）
- `--input-source` 或 `--input-file`：选择运行模式（二选一，未传时使用 `config/gui_config.json`）
  - `--input-source`：实时音频转录（`microphone` 或 `system`）
  - `--input-file`：离线文件转字幕（文件/目录路径）

#### CLI 覆盖规则
- `config/gui_config.json` 是默认配置来源，建议在其中配置所有常用参数。
- CLI 仅覆盖显式传入的参数；未显式传入时，不会用 CLI 默认值覆盖配置文件。

#### 实时转录可选参数
- `--vad-sensitivity`：VAD敏感度（0.0-1.0，默认0.5，兼容参数）
- `--transcription-language`：转录语言提示（`auto`/`zh`/`en`）
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

#### 屏幕字幕显示参数（仅 `--input-source` 模式）
- `--show-subtitles`：启用屏幕字幕显示
- `--subtitle-position`：字幕位置（`top`/`center`/`bottom`）
- `--subtitle-font-size`：字幕字号
- `--subtitle-font-family`：字幕字体
- `--subtitle-opacity`：字幕透明度（0.1-1.0）
- `--subtitle-max-display-time`：单条字幕最大显示时长（秒）
- `--subtitle-text-color`：字幕文字颜色（十六进制）
- `--subtitle-bg-color`：字幕背景颜色（十六进制）

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

### 配置体系（schema v2）

当前配置采用分区结构（`runtime/audio/vad/output/subtitle`），并通过 `ConfigLoader` 统一合并多来源配置。

合并优先级（高到低）：
- CLI 参数（仅显式传入）
- 环境变量（`S2S_*`）
- 配置文件
- 默认配置

默认 GUI 配置文件位置：

```text
config/gui_config.json
```

建议在 `config/gui_config.json` 中维护完整配置（`runtime/audio/vad/output/subtitle` 及激活方案），这样启动时无需重复传参。

配置文件外层包含版本信息，例如：

```json
{
  "version": "2.0",
  "last_modified": "2026-04-07T12:00:00",
  "config": {
    "runtime": {},
    "audio": {},
    "vad": {},
    "output": {},
    "subtitle": {}
  }
}
```

### gui_config.json 全参数说明（作用 / 配法 / 效果）

> 说明：系统同时兼容“扁平字段”和 `schema v2` 分区结构。  
> 推荐优先使用 `schema v2`（`runtime/audio/vad/output/subtitle`），可读性和可维护性更好。  
> 若仅修改少量参数，也可继续用扁平字段，系统会做兼容映射。

#### 外层包装字段

| 字段 | 作用 | 建议配置 | 影响效果 |
| --- | --- | --- | --- |
| `version` | 配置文件版本号 | 推荐 `2.0` | 便于版本迁移与兼容处理 |
| `last_modified` | 最近修改时间 | ISO 时间字符串 | 便于排查“配置何时被改动” |
| `config` | 实际业务配置对象 | 保持对象结构完整 | 系统启动时读取的核心配置 |

#### 运行与模型字段

| 字段 | 作用 | 建议配置 | 影响效果 |
| --- | --- | --- | --- |
| `input_source` | 实时输入源 | `microphone` 或 `system` | 决定实时模式是麦克风还是系统内录 |
| `input_file` | 离线输入文件/目录 | `null` 或文件数组 | 启用离线批量转字幕模式 |
| `use_gpu` | 是否使用 GPU | 有 CUDA 则 `true` | 开启后速度更快、占用显存更多 |
| `transcription_language` | 转录语言提示 | `auto`/`zh`/`en` | 固定语言可降低误判，`auto` 更通用 |
| `model_profiles` | 模型方案集合 | 至少保留一个方案 | 支持“不同模型一键切换” |
| `active_model_profile_id` | 当前启用模型方案 ID | 指向 `model_profiles` 中存在的 ID | 决定实际使用哪个模型 |
| `model_path`（兼容） | 当前模型路径（旧字段） | 可保留，建议由方案管理 | 兼容旧配置与脚本调用 |

`model_profiles.<profile_id>` 子字段说明：

| 子字段 | 作用 | 建议配置 | 影响效果 |
| --- | --- | --- | --- |
| `profile_id` | 模型方案唯一标识 | 稳定、不可重复 | 供 `active_model_profile_id` 引用 |
| `profile_name` | 展示名称 | 如 `默认`/`int8`/`高精度` | GUI 选择更直观 |
| `model_path` | 模型文件路径 | 指向存在的 `.onnx`/`.bin` | 决定识别能力、速度、显存占用 |
| `description` | 方案备注 | 场景描述 | 便于团队协作与维护 |
| `supported_languages` | 支持语言列表 | 如 `["zh","en"]` | 帮助区分多语言模型用途 |

#### 音频字段

| 字段 | 作用 | 建议配置 | 影响效果 |
| --- | --- | --- | --- |
| `sample_rate` | 采样率 | `16000`（推荐） | 更高采样率可保留更多细节，但计算负担更高 |
| `chunk_size` | 音频分块大小 | `512`~`2048` | 小块更低延迟；大块更稳、更省 CPU 调度 |
| `channels` | 声道数 | `1` | 单声道通常足够，资源占用更低 |
| `device_id` | 指定音频设备 | `null` 或有效设备 ID | 多设备场景可固定输入设备 |

#### VAD（语音活动检测）字段

| 字段 | 作用 | 建议配置 | 影响效果 |
| --- | --- | --- | --- |
| `vad_profiles` | VAD 方案集合 | 至少保留一个方案 | 支持按场景切换（安静/嘈杂） |
| `active_vad_profile_id` | 当前启用 VAD 方案 ID | 指向 `vad_profiles` 中存在的 ID | 决定实时切分与触发行为 |
| `vad_threshold`（兼容） | 当前阈值（0.0~1.0） | `0.4`~`0.6` | 越低越敏感；越高越“保守” |
| `vad_sensitivity`（兼容） | 兼容字段，等价阈值 | 与 `vad_threshold` 二选一 | 兼容老参数名 |
| `vad_window_size`（兼容） | 窗口时长（秒） | `0.32`~`0.64` | 小窗口响应更快；大窗口更平滑 |

`vad_profiles.<profile_id>` 子字段说明：

| 子字段 | 作用 | 建议配置 | 影响效果 |
| --- | --- | --- | --- |
| `threshold` | 语音检测阈值 | `0.4`~`0.6` | 低阈值可捕捉弱语音但更易误触发 |
| `min_speech_duration_ms` | 最短语音时长 | `80`~`250` | 太小会产生碎片文本，太大可能漏短词 |
| `min_silence_duration_ms` | 最短静音时长 | `120`~`300` | 越小分句越快，越大句子更完整 |
| `max_speech_duration_ms` | 最长语音时长 | `10000`~`30000` | 控制超长连续语音的切段行为 |
| `sample_rate` | 该方案采样率 | 与全局一致（常用 16000） | 不一致可能导致效果不稳定 |
| `model` | VAD 模型类型 | `silero_vad` 或 `ten_vad` | 影响检测风格与性能 |
| `model_path` | VAD 模型路径 | 可空或指定文件路径 | 指定后可锁定模型版本 |
| `use_sherpa_onnx` | 是否走 sherpa-onnx 管线 | `true` | 与现有工程默认一致 |
| `window_size_samples` | 窗口采样点数 | 16k 采样率下常用 `512` | 越小响应越快，越大越稳 |

#### 输出与字幕文件字段

| 字段 | 作用 | 建议配置 | 影响效果 |
| --- | --- | --- | --- |
| `output_format` | 实时输出格式 | `text` 或 `json` | `json` 更适合二次处理与调试 |
| `show_confidence` | 是否显示置信度 | 调试时 `true` | 便于判断识别质量 |
| `show_timestamp` | 是否显示时间戳 | 字幕对齐场景 `true` | 便于排查切分和对齐问题 |
| `output_dir` | 离线字幕输出目录 | 显式指定目录 | 便于批量任务统一归档 |
| `subtitle_format` | 字幕格式 | `srt`/`vtt`/`ass` | 不同播放器和剪辑工具兼容性不同 |
| `keep_temp` | 是否保留临时文件 | 调试时 `true`，日常 `false` | 开启后便于问题定位，但占磁盘 |
| `verbose` | 是否输出详细日志 | 调优时 `true` | 提供更细粒度处理过程信息 |

#### 字幕显示字段（`subtitle_display`）

| 字段 | 作用 | 建议配置 | 影响效果 |
| --- | --- | --- | --- |
| `enabled` | 是否启用悬浮字幕 | 实时演示场景 `true` | 屏幕实时显示识别文本 |
| `position` | 字幕位置 | `bottom` | 控制字幕在屏幕显示区域 |
| `font_size` | 字号 | `20`~`30` | 大字号更清晰，小字号遮挡更少 |
| `font_family` | 字体 | 如 `Microsoft YaHei` | 影响可读性与风格 |
| `opacity` | 透明度（0.1~1.0） | `0.7`~`0.9` | 高透明度更醒目，低透明度更不遮挡 |
| `max_display_time` | 单条字幕最大显示时间（秒） | `3.0`~`6.0` | 控制字幕停留时长 |
| `text_color` | 文字颜色 | `#FFFFFF` | 影响对比度与可读性 |
| `background_color` | 背景色 | `#000000` | 与文字形成对比，提升可见性 |

### 常用配置方案（按效果选）

#### 1) 低延迟实时会议（响应优先）

```json
{
  "config": {
    "input_source": "system",
    "use_gpu": true,
    "sample_rate": 16000,
    "chunk_size": 512,
    "active_vad_profile_id": "meeting_fast",
    "vad_profiles": {
      "meeting_fast": {
        "profile_name": "会议低延迟",
        "profile_id": "meeting_fast",
        "threshold": 0.45,
        "min_speech_duration_ms": 100.0,
        "min_silence_duration_ms": 120.0,
        "max_speech_duration_ms": 15000.0,
        "sample_rate": 16000,
        "model": "silero_vad",
        "model_path": null,
        "use_sherpa_onnx": true,
        "window_size_samples": 512
      }
    }
  }
}
```

效果：触发快、延迟低，适合直播字幕和会议跟打。

#### 2) 高准确率离线字幕（质量优先）

```json
{
  "config": {
    "input_file": ["./videos/lesson.mp4"],
    "use_gpu": true,
    "chunk_size": 2048,
    "output_format": "json",
    "show_confidence": true,
    "show_timestamp": true,
    "subtitle_format": "srt",
    "output_dir": "./subtitles"
  }
}
```

效果：信息更完整、可复盘性更好，适合课程和访谈素材整理。

#### 3) 嘈杂环境防误触发（抗噪优先）

```json
{
  "config": {
    "active_vad_profile_id": "noisy_env",
    "vad_profiles": {
      "noisy_env": {
        "profile_name": "嘈杂环境",
        "profile_id": "noisy_env",
        "threshold": 0.65,
        "min_speech_duration_ms": 180.0,
        "min_silence_duration_ms": 260.0,
        "max_speech_duration_ms": 30000.0,
        "sample_rate": 16000,
        "model": "silero_vad",
        "model_path": null,
        "use_sherpa_onnx": true,
        "window_size_samples": 512
      }
    }
  }
}
```

效果：背景噪声触发明显减少，但对很轻的语音可能更“迟钝”。

#### 4) 安静环境弱语音捕捉（灵敏优先）

```json
{
  "config": {
    "active_vad_profile_id": "quiet_sensitive",
    "vad_profiles": {
      "quiet_sensitive": {
        "profile_name": "安静环境高灵敏",
        "profile_id": "quiet_sensitive",
        "threshold": 0.35,
        "min_speech_duration_ms": 80.0,
        "min_silence_duration_ms": 140.0,
        "max_speech_duration_ms": 20000.0,
        "sample_rate": 16000,
        "model": "silero_vad",
        "model_path": null,
        "use_sherpa_onnx": true,
        "window_size_samples": 512
      }
    }
  }
}
```

效果：能捕获更轻微的语音，但更容易把环境音识别成语音。

### 调优顺序建议（最省时间）

1. 先确认 `active_model_profile_id` 与 `active_vad_profile_id` 正确。
2. 再调 `threshold`（先每次改 0.05）。
3. 再调 `min_silence_duration_ms` 与 `chunk_size`，平衡“响应速度 vs 分句稳定”。
4. 最后根据观感微调 `subtitle_display`（字号、透明度、颜色）。

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
└── openspec/                # 规范文档
```

### 环境变量（可选，`S2S_*`）
```bash
# 运行时
S2S_INPUT_SOURCE=microphone
S2S_USE_GPU=true
S2S_TRANSCRIPTION_LANGUAGE=auto
S2S_MODEL_PATH=models/your-model/model.onnx

# 音频
S2S_SAMPLE_RATE=16000
S2S_CHUNK_SIZE=1024
S2S_DEVICE_ID=0

# 输出
S2S_OUTPUT_FORMAT=text
S2S_SHOW_CONFIDENCE=true
S2S_SHOW_TIMESTAMP=true

# 字幕文件输出
S2S_SUBTITLE_FORMAT=srt
S2S_OUTPUT_DIR=./subtitles
S2S_KEEP_TEMP=false

# 屏幕字幕显示
S2S_SUBTITLE_ENABLED=true
S2S_SUBTITLE_POSITION=bottom
S2S_SUBTITLE_FONT_SIZE=24
S2S_SUBTITLE_OPACITY=0.8
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
python main.py --model-path models\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\model.onnx --input-source microphone --log-level DEBUG
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
