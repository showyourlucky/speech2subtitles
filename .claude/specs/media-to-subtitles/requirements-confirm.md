# 需求确认文档 - 媒体文件转字幕功能

## 📋 元数据

- **功能名称**: media-to-subtitles
- **创建时间**: 2025-10-21
- **需求质量评分**: 94/100 ✅
- **状态**: 已确认,等待用户批准进入实现阶段

---

## 🎯 原始需求

实现传入媒体然后转为字幕的功能,媒体可能为视频也可能为音频, 使用exa搜索阿里开源sense-voice支持的音频格式, 然后使用ffmpeg转换后再进行转录, 在readme文档中加入安装ffmpeg的方法, 如果环境变量中没有ffmpeg, 进行提示并退出任务, 参考@tests/generate-subtitles.py选择合适的方法生成字幕

---

## 🔍 需求澄清过程

### 第一轮澄清 - 12个关键问题

#### A. 功能范围和用户接口
1. **命令行接口设计**: ✅ 确认使用选项1 - 扩展现有main.py
2. **字幕格式支持**: ✅ 优先支持SRT,可扩展支持多种格式
3. **批量处理能力**: ✅ 支持多文件和目录,按顺序处理,无多线程

#### B. 技术实现细节
4. **FFmpeg集成方式**: ✅ 使用subprocess (ffmpeg-python需要额外下载ffmpeg.exe)
5. **音频处理参数**: ✅ 满足Sense-Voice支持的音频格式要求
6. **临时文件管理**: ✅ 保存在项目下temp/目录,任务完成后清理

#### C. 错误处理和边界情况
7. **文件大小限制**: ✅ 不设置限制,不分段处理
8. **不支持格式处理**: ✅ 给出详细错误信息,列出支持格式
9. **磁盘空间检查**: ✅ 不检测 (简化实现)

#### D. 性能和用户体验
10. **进度显示**: ✅ 显示转换进度和转录进度
11. **GPU支持**: ✅ 继承现有--no-gpu参数,ffmpeg不需要GPU加速
12. **输出详细程度**: ✅ 支持--verbose详细日志

### 外部研究确认

#### Sense-Voice支持的音频格式 (官方文档)
- **来源**: GitHub - FunAudioLLM/SenseVoice
- **支持格式**: aac, amr, avi, flac, flv, m4a, mkv, mov, mp3, mp4, mpeg, ogg, opus, wav, webm, wma, wmv
- **输入限制**: 支持任意长度音频 (官方API建议≤30秒,但离线模型无此限制)
- **特性**: 支持50+语言,中文和粤语识别准确率比Whisper提升50%+

#### FFmpeg-Python库调查
- **结论**: ffmpeg-python仅是Python包装器,仍需单独安装ffmpeg.exe
- **决策**: 使用subprocess直接调用系统FFmpeg,避免额外依赖

#### 参考实现分析
- **文件**: `tests/generate-subtitles.py` (line 531-668)
- **关键技术**:
  - FFmpeg命令: `-f s16le -acodec pcm_s16le -ac 1 -ar 16000`
  - VAD分段处理
  - SRT格式生成 (Segment类实现)
  - 环境检查: `shutil.which("ffmpeg")`

---

## ✅ 最终确认的需求规格

### 1. 功能描述

**核心功能**: 扩展现有Speech2Subtitles系统,支持从视频/音频媒体文件生成字幕文件

**主要特性**:
- 支持单文件、多文件、目录批量处理
- 自动检测并转换任意格式媒体为Sense-Voice兼容音频
- 使用现有转录引擎生成高质量字幕
- 优先支持SRT格式,架构可扩展支持VTT/ASS等格式

### 2. 命令行接口设计

#### 基础用法
```bash
# 单个文件
python main.py --model-path models/sense-voice/model.onnx \
               --input-file video.mp4

# 多个文件 (按顺序处理)
python main.py --model-path models/sense-voice/model.onnx \
               --input-file video1.mp4 audio1.mp3 lecture.avi

# 目录批量处理
python main.py --model-path models/sense-voice/model.onnx \
               --input-file ./videos/ \
               --output-dir ./subtitles/

# 禁用GPU
python main.py --model-path models/sense-voice/model.onnx \
               --input-file video.mp4 \
               --no-gpu

# 详细日志
python main.py --model-path models/sense-voice/model.onnx \
               --input-file video.mp4 \
               --verbose
```

#### 新增参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--input-file` | str/list/path | 否* | None | 输入文件/文件列表/目录路径 |
| `--output-dir` | str | 否 | 与输入同目录 | 字幕输出目录 |
| `--subtitle-format` | str | 否 | srt | 字幕格式 (srt/vtt/ass) |
| `--keep-temp` | bool | 否 | False | 保留临时音频文件 |
| `--verbose` | bool | 否 | False | 显示详细日志 |

*注: `--input-file` 与现有的 `--input-source` 互斥,提供其一即可

#### 互斥逻辑
- 如果提供 `--input-file`: 离线文件转录模式
- 如果提供 `--input-source`: 实时音频捕获模式
- 两者都不提供: 显示帮助信息

### 3. 技术实现规格

#### 3.1 音频格式转换

**支持的输入格式** (基于Sense-Voice官方文档):
```
视频: avi, flv, mkv, mov, mp4, mpeg, webm, wmv
音频: aac, amr, flac, m4a, mp3, ogg, opus, wav, wma
```

**转换目标格式**:
- **格式**: 16位PCM WAV
- **采样率**: 16000 Hz (16kHz)
- **声道**: 单声道 (mono)
- **编码**: pcm_s16le (小端序)

**FFmpeg命令模板**:
```python
ffmpeg_cmd = [
    "ffmpeg",
    "-i", input_file,           # 输入媒体文件
    "-f", "s16le",              # 输出格式: 16位小端序PCM
    "-acodec", "pcm_s16le",     # 音频编解码器
    "-ac", "1",                 # 音频声道: 1 (单声道)
    "-ar", "16000",             # 音频采样率: 16kHz
    "-y",                       # 覆盖已存在文件
    temp_output_file            # 临时输出文件路径
]
```

#### 3.2 临时文件管理

**临时目录**: `./temp/`
- 如果不存在则自动创建
- 添加到 `.gitignore`

**临时文件命名**:
```python
temp_file = f"temp/{Path(input_file).stem}_{timestamp}.wav"
```

**清理策略**:
- 默认行为: 转录完成后自动删除临时文件
- `--keep-temp` 标志: 保留临时文件供调试使用
- 异常退出: 使用 `try-finally` 确保清理

#### 3.3 转录处理流程

**流程图**:
```
1. 环境检查 → 2. 文件验证 → 3. FFmpeg转换 → 4. 转录处理 → 5. 字幕生成 → 6. 清理临时文件
```

**详细步骤**:

1. **环境检查** (启动时执行一次)
   ```python
   if shutil.which("ffmpeg") is None:
       print("错误: 未检测到FFmpeg!")
       print("请参考 README.md 安装FFmpeg")
       sys.exit(1)
   ```

2. **文件验证**
   - 检查文件/目录存在性
   - 检查文件可读性
   - 过滤出支持的媒体格式

3. **FFmpeg转换**
   - 使用 `subprocess.run()` 调用FFmpeg
   - 捕获stderr用于错误诊断
   - 验证输出文件生成成功

4. **转录处理**
   - 复用现有 `TranscriptionEngine`
   - 使用VAD进行语音分段 (基于 `tests/generate-subtitles.py`)
   - 保持与实时转录一致的质量

5. **字幕生成**
   - SRT格式: 实现 `Segment` 数据类
   - 时间戳格式: `HH:MM:SS,mmm --> HH:MM:SS,mmm`
   - 编码: UTF-8

6. **清理与报告**
   - 删除临时文件 (除非 `--keep-temp`)
   - 打印统计信息: 文件数、总时长、RTF (Real-Time Factor)

#### 3.4 批量处理策略

**顺序处理** (无多线程):
```python
for file_path in file_list:
    try:
        process_single_file(file_path)
        print(f"✓ 成功: {file_path}")
    except Exception as e:
        print(f"✗ 失败: {file_path} - {e}")
        continue  # 继续处理下一个文件
```

**进度显示**:
```
处理中: video1.mp4 (1/5)
  [1/3] 转换音频格式... 完成 (2.3s)
  [2/3] 语音识别中... 完成 (15.7s)
  [3/3] 生成字幕文件... 完成 (0.1s)
  ✓ 已保存: video1.srt (RTF: 0.87)

处理中: audio2.mp3 (2/5)
  ...
```

### 4. 错误处理和边界情况

#### 4.1 FFmpeg相关错误

| 错误类型 | 检测方法 | 处理方式 |
|---------|---------|---------|
| FFmpeg未安装 | `shutil.which("ffmpeg")` | 显示安装指南,退出程序 |
| 不支持的格式 | FFmpeg返回码 | 列出支持格式,跳过该文件 |
| 转换失败 | 检查输出文件 | 记录错误日志,跳过该文件 |

**错误信息示例**:
```
错误: 未检测到FFmpeg!

FFmpeg是必需的依赖,用于转换媒体格式。

安装方法:
  Windows: 请参考 README.md 中的"FFmpeg安装指南"章节
  Linux:   sudo apt install ffmpeg
  macOS:   brew install ffmpeg

安装完成后,请重新运行程序。
```

#### 4.2 文件相关错误

| 错误类型 | 处理方式 |
|---------|---------|
| 文件不存在 | 提示错误,跳过 |
| 文件无读权限 | 提示权限错误,跳过 |
| 文件已损坏 | FFmpeg会报错,记录日志并跳过 |
| 输出目录不可写 | 提前检查,失败则退出 |

#### 4.3 转录相关错误

| 错误类型 | 处理方式 |
|---------|---------|
| 模型加载失败 | 早期失败,退出程序 |
| VAD检测失败 | 记录警告,尝试完整转录 |
| 转录无结果 | 生成空字幕文件,记录警告 |
| GPU内存不足 | 自动回退到CPU模式 |

### 5. 代码模块设计

#### 5.1 新增模块结构

```
src/
  media/                          # 新增模块
    __init__.py
    converter.py                  # 媒体格式转换
    batch_processor.py            # 批量处理逻辑
    subtitle_generator.py         # 字幕生成
    CLAUDE.md                     # 模块文档
```

#### 5.2 核心类设计

**MediaConverter类** (`src/media/converter.py`):
```python
class MediaConverter:
    """媒体文件转音频转换器"""

    def __init__(self, temp_dir: str = "temp"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)

    def convert_to_wav(self,
                       input_file: Path,
                       sample_rate: int = 16000) -> Path:
        """转换媒体文件为16kHz单声道WAV"""
        pass

    def cleanup_temp_file(self, temp_file: Path) -> None:
        """清理临时文件"""
        pass

    @staticmethod
    def check_ffmpeg() -> bool:
        """检查FFmpeg是否已安装"""
        return shutil.which("ffmpeg") is not None
```

**BatchProcessor类** (`src/media/batch_processor.py`):
```python
class BatchProcessor:
    """批量文件处理器"""

    def __init__(self,
                 converter: MediaConverter,
                 engine: TranscriptionEngine,
                 subtitle_gen: SubtitleGenerator):
        self.converter = converter
        self.engine = engine
        self.subtitle_gen = subtitle_gen

    def process_files(self,
                      file_paths: List[Path],
                      output_dir: Path,
                      verbose: bool = False) -> Dict[str, Any]:
        """批量处理文件,返回统计信息"""
        pass

    def process_directory(self,
                         dir_path: Path,
                         output_dir: Path,
                         recursive: bool = False) -> Dict[str, Any]:
        """处理目录下所有媒体文件"""
        pass
```

**SubtitleGenerator类** (`src/media/subtitle_generator.py`):
```python
@dataclass
class Segment:
    """字幕片段"""
    start: float       # 开始时间(秒)
    duration: float    # 持续时间(秒)
    text: str = ""     # 文本内容

    @property
    def end(self) -> float:
        return self.start + self.duration

    def to_srt_format(self, index: int) -> str:
        """转换为SRT格式"""
        pass

class SubtitleGenerator:
    """字幕文件生成器"""

    def generate_srt(self,
                     segments: List[Segment],
                     output_file: Path) -> None:
        """生成SRT格式字幕"""
        pass

    def generate_vtt(self,
                     segments: List[Segment],
                     output_file: Path) -> None:
        """生成WebVTT格式字幕 (扩展功能)"""
        pass
```

#### 5.3 main.py集成

**参数解析扩展**:
```python
# 添加到现有argparse
group = parser.add_mutually_exclusive_group()
group.add_argument("--input-source", ...)  # 现有参数
group.add_argument("--input-file",
                   nargs='+',
                   help="输入文件、文件列表或目录")

parser.add_argument("--output-dir", ...)
parser.add_argument("--subtitle-format", ...)
parser.add_argument("--keep-temp", action="store_true")
parser.add_argument("--verbose", action="store_true")
```

**执行逻辑**:
```python
def main():
    args = parse_args()

    if args.input_file:
        # 离线文件转录模式
        run_file_transcription(args)
    elif args.input_source:
        # 实时音频捕获模式 (现有功能)
        run_realtime_transcription(args)
    else:
        parser.print_help()
        sys.exit(1)
```

### 6. 文档更新

#### 6.1 README.md新增章节

**FFmpeg安装指南**:
```markdown
## FFmpeg安装指南

Speech2Subtitles使用FFmpeg进行媒体格式转换。请根据您的操作系统安装FFmpeg:

### Windows

1. **下载FFmpeg**:
   - 访问 https://www.gyan.dev/ffmpeg/builds/
   - 下载 "ffmpeg-release-essentials.zip"

2. **解压并配置环境变量**:
   - 解压到 `C:\ffmpeg\`
   - 添加 `C:\ffmpeg\bin` 到系统PATH环境变量

3. **验证安装**:
   ```cmd
   ffmpeg -version
   ```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install ffmpeg
```

### macOS

```bash
brew install ffmpeg
```

### 验证安装

运行以下命令确认FFmpeg已正确安装:
```bash
ffmpeg -version
```

应该看到FFmpeg的版本信息。
```

**使用示例更新**:
```markdown
## 使用方法

### 实时音频转录

```bash
# 麦克风输入
python main.py --model-path models/.../model.onnx --input-source microphone

# 系统音频
python main.py --model-path models/.../model.onnx --input-source system --no-gpu
```

### 媒体文件转字幕 (新功能)

```bash
# 单个文件
python main.py --model-path models/.../model.onnx --input-file video.mp4

# 批量处理
python main.py --model-path models/.../model.onnx --input-file video1.mp4 audio1.mp3

# 目录处理
python main.py --model-path models/.../model.onnx --input-file ./videos/

# 自定义输出目录
python main.py --model-path models/.../model.onnx \
               --input-file ./videos/ \
               --output-dir ./subtitles/
```

### 支持的媒体格式

**视频**: avi, flv, mkv, mov, mp4, mpeg, webm, wmv
**音频**: aac, amr, flac, m4a, mp3, ogg, opus, wav, wma
```

#### 6.2 新增模块文档

创建 `src/media/CLAUDE.md`:
```markdown
# Media Processing Module (媒体处理模块)

## 模块概述
负责媒体文件的格式转换、批量处理和字幕生成功能。

## 核心组件
- MediaConverter: FFmpeg集成和音频转换
- BatchProcessor: 批量文件处理逻辑
- SubtitleGenerator: 字幕文件生成 (SRT/VTT/ASS)

## 依赖关系
- 外部依赖: FFmpeg (系统级)
- 内部依赖: TranscriptionEngine, Config, Logger
```

### 7. 测试策略

#### 7.1 单元测试

**测试文件**: `tests/test_media_converter.py`
```python
def test_check_ffmpeg_installed()
def test_convert_mp4_to_wav()
def test_convert_mp3_to_wav()
def test_unsupported_format_handling()
def test_corrupted_file_handling()
def test_temp_file_cleanup()
```

**测试文件**: `tests/test_subtitle_generator.py`
```python
def test_segment_to_srt_format()
def test_generate_srt_file()
def test_empty_segments_handling()
def test_utf8_encoding()
```

#### 7.2 集成测试

**测试文件**: `tests/test_batch_processor.py`
```python
def test_process_single_file()
def test_process_multiple_files()
def test_process_directory()
def test_error_recovery_in_batch()
```

#### 7.3 端到端测试

使用测试数据:
```
tests/data/
  sample.mp4      # 视频样本
  sample.mp3      # 音频样本
  expected.srt    # 期望的字幕输出
```

### 8. 性能指标

#### 8.1 预期性能

| 场景 | 目标 | 测量方式 |
|------|------|----------|
| FFmpeg转换 | < 0.5x实时 | 1分钟音频 < 30秒转换 |
| 转录速度 (GPU) | < 0.3x实时 | RTF < 0.3 |
| 转录速度 (CPU) | < 2x实时 | RTF < 2.0 |
| 内存占用 | < 2GB | 包含模型加载 |

#### 8.2 进度报告格式

```
=== Speech2Subtitles - 批量转录 ===

处理文件: 3/10
当前: lecture_part3.mp4

[转换音频] ████████████░░░░░░░░ 60% (12.3s / 20.5s)
[语音识别] 等待中...
[生成字幕] 等待中...

已完成: 2个文件
预计剩余时间: 约 8 分钟

统计信息:
  ✓ lecture_part1.mp4 → lecture_part1.srt (RTF: 0.28)
  ✓ lecture_part2.mp4 → lecture_part2.srt (RTF: 0.31)
```

### 9. 与现有系统的集成

#### 9.1 复用现有组件

| 现有组件 | 复用方式 |
|---------|---------|
| `TranscriptionEngine` | 直接使用进行离线转录 |
| `VoiceActivityDetector` | 用于语音分段 (基于generate-subtitles.py) |
| `Config` | 扩展支持新参数 |
| `Logger` | 统一日志记录 |
| `GPUDetector` | GPU可用性检测 |

#### 9.2 配置扩展

**Config类新增字段**:
```python
@dataclass
class Config:
    # 现有字段...

    # 新增字段
    input_file: Optional[List[Path]] = None
    output_dir: Optional[Path] = None
    subtitle_format: str = "srt"
    keep_temp: bool = False
    verbose: bool = False
```

### 10. 开发优先级和里程碑

#### Phase 1: 核心功能 (MVP)
- [ ] FFmpeg检查和集成
- [ ] 单文件转换和转录
- [ ] SRT格式字幕生成
- [ ] 基础错误处理
- [ ] README FFmpeg安装指南

#### Phase 2: 批量处理
- [ ] 多文件顺序处理
- [ ] 目录遍历支持
- [ ] 进度显示
- [ ] 统计报告

#### Phase 3: 用户体验优化
- [ ] 详细日志模式
- [ ] 临时文件管理
- [ ] 错误恢复机制
- [ ] 性能优化

#### Phase 4: 扩展功能 (可选)
- [ ] VTT格式支持
- [ ] ASS格式支持
- [ ] 递归目录处理
- [ ] 字幕样式自定义

---

## 📊 最终质量评分

| 维度 | 得分 | 满分 | 评价 |
|------|------|------|------|
| **功能清晰度** | 28 | 30 | ✅ 优秀 |
| **技术特定性** | 24 | 25 | ✅ 优秀 |
| **实现完整性** | 23 | 25 | ✅ 优秀 |
| **业务上下文** | 19 | 20 | ✅ 优秀 |
| **总分** | **94** | **100** | **✅ 已达标** |

---

## 🛑 用户批准检查点

**需求已完全明确 (94分 > 90分门槛)**

### 确认的关键决策:
1. ✅ 扩展main.py而非独立脚本
2. ✅ 使用subprocess调用FFmpeg
3. ✅ 支持批量处理但无多线程
4. ✅ 临时文件存储在temp/目录
5. ✅ 优先支持SRT格式
6. ✅ 继承现有GPU参数
7. ✅ 基于tests/generate-subtitles.py实现

### 与仓库上下文的契合度:
- ✅ 遵循现有的模块化架构
- ✅ 复用TranscriptionEngine和VAD
- ✅ 保持配置管理一致性
- ✅ 遵循现有编码标准 (PEP 8, Google风格)
- ✅ 符合KISS和YAGNI原则

### 待用户确认:
**您是否批准进入Phase 2 (实现阶段)?**
- 回复 "yes" / "确认" / "继续" → 开始执行实现
- 回复 "no" / "修改" → 返回需求澄清

---

## 📚 附录

### A. Sense-Voice格式支持 (官方文档)

来源: https://github.com/FunAudioLLM/SenseVoice

**支持格式**: aac, amr, avi, flac, flv, m4a, mkv, mov, mp3, mp4, mpeg, ogg, opus, wav, webm, wma, wmv

**特性**:
- 多语言: 中文、粤语、英语、日语、韩语
- 情感识别: 支持情感检测
- 音频事件: 可检测笑声、掌声等

### B. FFmpeg-Python库调查结果

**结论**: ffmpeg-python是Python包装器,需要单独安装ffmpeg.exe

**决策理由**:
1. 避免额外依赖
2. 更直接的错误控制
3. 与generate-subtitles.py一致

### C. 参考实现

**文件**: `tests/generate-subtitles.py`

**关键代码段**:
- FFmpeg命令: Line 531-548
- VAD配置: Line 554-582
- Segment类: Line 490-507
- SRT生成: Line 650-655
- FFmpeg检查: Line 665-666

---

**文档版本**: 1.0
**最后更新**: 2025-10-21
**下一步**: 等待用户批准进入实现阶段
