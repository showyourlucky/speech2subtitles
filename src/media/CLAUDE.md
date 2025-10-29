# 媒体处理模块 (Media Processing Module)

[根目录](../../CLAUDE.md) > [src](../) > **media**

## 模块职责
负责媒体文件的格式转换、批量处理和字幕生成功能。实现从视频/音频文件到字幕文件的完整处理流程。

## 入口和启动
- **媒体转换器**: `converter.py::MediaConverter` - FFmpeg集成和音频格式转换
- **字幕生成器**: `subtitle_generator.py::SubtitleGenerator` - 字幕文件生成
- **批量处理器**: `batch_processor.py::BatchProcessor` - 批量文件处理协调
- **调用入口**: 由`main.py`在离线文件转录模式下调用

## 外部接口

### 主要类和方法

#### MediaConverter - 媒体格式转换器
```python
class MediaConverter:
    """使用FFmpeg转换媒体文件为16kHz单声道WAV"""

    @staticmethod
    def check_ffmpeg() -> bool
        # 检查FFmpeg是否已安装

    @staticmethod
    def ensure_ffmpeg() -> None
        # 确保FFmpeg已安装,否则抛出异常

    def convert_to_wav(
        input_file: Path,
        sample_rate: int = 16000,
        show_progress: bool = True
    ) -> Path
        # 转换媒体文件为WAV格式

    def cleanup_temp_file(temp_file: Path) -> None
        # 清理临时文件

    def cleanup_all_temp_files() -> int
        # 清理所有临时文件
```

**支持的格式**:
- 视频: `.avi`, `.flv`, `.mkv`, `.mov`, `.mp4`, `.mpeg`, `.webm`, `.wmv`
- 音频: `.aac`, `.amr`, `.flac`, `.m4a`, `.mp3`, `.ogg`, `.opus`, `.wav`, `.wma`

**转换参数**:
- 格式: 16位PCM WAV
- 采样率: 16000 Hz
- 声道: 单声道 (mono)
- 编码: pcm_s16le (小端序)

#### SubtitleGenerator - 字幕生成器
```python
@dataclass
class Segment:
    """字幕片段数据类"""
    start: float              # 开始时间(秒)
    duration: float           # 持续时间(秒)
    text: str = ""            # 文本内容

    @property
    def end(self) -> float    # 结束时间

    def to_srt_format(index: int) -> str
        # 转换为SRT格式字符串

class SubtitleGenerator:
    """字幕文件生成器"""

    def generate_srt(
        segments: List[Segment],
        output_file: Path,
        overwrite: bool = True
    ) -> None
        # 生成SRT格式字幕

    def generate_vtt(
        segments: List[Segment],
        output_file: Path,
        overwrite: bool = True
    ) -> None
        # 生成WebVTT格式字幕
```

**字幕格式**:
- **SRT格式**: 时间戳使用 `,` 分隔毫秒 (HH:MM:SS,mmm)
- **VTT格式**: 时间戳使用 `.` 分隔毫秒 (HH:MM:SS.mmm)
- **编码**: UTF-8

#### BatchProcessor - 批量处理器
```python
class BatchProcessor:
    """批量文件处理协调器"""

    def process_file(
        file_path: Path,
        transcription_engine,
        vad_detector,
        output_dir: Optional[Path] = None,
        subtitle_format: str = "srt",
        keep_temp: bool = False,
        verbose: bool = False
    ) -> Dict[str, Any]
        # 处理单个文件

    def process_files(
        file_paths: List[Path],
        transcription_engine,
        vad_detector,
        ...
    ) -> Dict[str, Any]
        # 批量处理多个文件

    def process_directory(
        dir_path: Path,
        transcription_engine,
        vad_detector,
        recursive: bool = False,
        ...
    ) -> Dict[str, Any]
        # 处理目录下所有媒体文件
```

## 关键依赖和配置

### 外部依赖
- **FFmpeg**: 系统级依赖,用于媒体格式转换
  - Windows: 需要添加到系统PATH
  - Linux: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`

### Python依赖
- `subprocess`: FFmpeg命令调用
- `soundfile`: 音频文件读写
- `numpy`: 音频数据处理
- `pathlib`: 路径操作

### 内部依赖
- `src.transcription.engine::TranscriptionEngine` - 语音转录
- `src.vad.detector::VoiceActivityDetector` - 语音分段
- `src.utils.logger` - 日志记录

### 配置参数
- `temp_dir`: 临时文件目录 (默认: `temp/`)
- `sample_rate`: 转换目标采样率 (默认: 16000)
- `encoding`: 字幕文件编码 (默认: utf-8)
- `subtitle_format`: 字幕格式 (srt/vtt)

## 数据模型

### 处理流程
```
输入文件 (video.mp4)
    ↓
[MediaConverter] 转换为WAV
    ↓
临时文件 (temp/video_timestamp.wav)
    ↓
[TranscriptionEngine + VAD] 语音识别和分段
    ↓
Segment列表 [(start, duration, text), ...]
    ↓
[SubtitleGenerator] 生成字幕
    ↓
输出文件 (video.srt)
```

### 错误处理
```python
# 自定义异常层次
MediaConverterError (基类)
├── FFmpegNotFoundError          # FFmpeg未安装
└── ConversionError              # 文件转换失败

SubtitleFormatError              # 字幕格式错误
BatchProcessorError              # 批量处理错误
```

### 临时文件管理
- **创建**: `temp/{filename}_{timestamp}.wav`
- **清理**: 处理完成后自动删除 (除非 `keep_temp=True`)
- **目录**: 添加到 `.gitignore`

## 测试和质量保证

### 单元测试
```python
# tests/test_media_converter.py
def test_check_ffmpeg()              # FFmpeg检测
def test_convert_mp4_to_wav()        # MP4转换
def test_convert_mp3_to_wav()        # MP3转换
def test_unsupported_format()        # 不支持格式处理
def test_temp_file_cleanup()         # 临时文件清理

# tests/test_subtitle_generator.py
def test_segment_to_srt()            # SRT格式转换
def test_generate_srt_file()         # SRT文件生成
def test_generate_vtt_file()         # VTT文件生成
def test_empty_segments()            # 空片段处理

# tests/test_batch_processor.py
def test_process_single_file()       # 单文件处理
def test_process_multiple_files()    # 多文件处理
def test_process_directory()         # 目录处理
```

### 性能指标
- **FFmpeg转换**: < 0.5x 实时 (1分钟音频 < 30秒)
- **转录速度**:
  - GPU: < 0.3x 实时 (RTF < 0.3)
  - CPU: < 2.0x 实时 (RTF < 2.0)
- **内存使用**: < 2GB (含模型)

## 使用示例

### 基本用法 - 单文件处理
```python
from pathlib import Path
from src.media import MediaConverter, SubtitleGenerator, BatchProcessor
from src.transcription.engine import TranscriptionEngine
from src.vad.detector import VoiceActivityDetector

# 初始化组件
converter = MediaConverter(temp_dir="temp/")
subtitle_gen = SubtitleGenerator(encoding='utf-8')
processor = BatchProcessor(converter, subtitle_gen)

# 加载转录引擎和VAD
engine = TranscriptionEngine(config)
vad = VoiceActivityDetector(config)

# 处理单个文件
result = processor.process_file(
    file_path=Path("video.mp4"),
    transcription_engine=engine,
    vad_detector=vad,
    output_dir=Path("subtitles/"),
    subtitle_format="srt",
    verbose=True
)

print(f"成功: {result['success']}")
print(f"RTF: {result['rtf']:.2f}")
```

### 批量处理 - 多文件
```python
# 批量处理文件列表
files = [Path("video1.mp4"), Path("video2.mp4"), Path("audio1.mp3")]

stats = processor.process_files(
    file_paths=files,
    transcription_engine=engine,
    vad_detector=vad,
    output_dir=Path("subtitles/"),
    verbose=True
)

print(f"总文件: {stats['total_files']}")
print(f"成功: {stats['success_count']}")
print(f"失败: {stats['error_count']}")
```

### 目录处理
```python
# 处理目录下所有媒体文件
stats = processor.process_directory(
    dir_path=Path("videos/"),
    transcription_engine=engine,
    vad_detector=vad,
    output_dir=Path("subtitles/"),
    recursive=False,  # 不递归子目录
    verbose=True
)
```

### FFmpeg环境检查
```python
from src.media import MediaConverter

# 检查FFmpeg是否可用
if not MediaConverter.check_ffmpeg():
    print("请先安装FFmpeg!")
    print("参考: README.md - FFmpeg安装指南")
else:
    print("FFmpeg已就绪")

# 或使用ensure_ffmpeg (失败会抛出异常)
try:
    MediaConverter.ensure_ffmpeg()
except FFmpegNotFoundError as e:
    print(e)
    exit(1)
```

## 常见问题 (FAQ)

### Q: 如何检查FFmpeg是否正确安装?
A: 运行 `ffmpeg -version` 命令,或使用 `MediaConverter.check_ffmpeg()`

### Q: 支持哪些视频格式?
A: 所有FFmpeg支持的格式,包括 mp4, avi, mkv, mov, flv, webm, wmv 等

### Q: 如何添加新的字幕格式支持?
A: 在 `SubtitleGenerator` 中添加新的 `generate_xxx()` 方法,实现对应格式的生成逻辑

### Q: 临时文件保存在哪里?
A: 默认保存在 `temp/` 目录,可通过 `MediaConverter(temp_dir="...")` 自定义

### Q: 如何保留临时音频文件?
A: 在调用 `process_file()` 时设置 `keep_temp=True`

### Q: 批量处理时如何处理错误?
A: 单个文件错误不会中断批量处理,会继续处理下一个文件,最终返回统计信息

## 相关文件列表
- `__init__.py` - 模块初始化和导出
- `converter.py` - 媒体格式转换器 (FFmpeg集成)
- `subtitle_generator.py` - 字幕文件生成器 (SRT/VTT)
- `batch_processor.py` - 批量文件处理器
- `CLAUDE.md` - 模块文档 (本文件)

## 变更日志 (Changelog)
- **2025-10-21**: 创建媒体处理模块,实现FFmpeg集成、字幕生成和批量处理功能
- **参考实现**: `tests/generate-subtitles.py` (Sherpa-ONNX官方示例)

## 集成说明

### 与main.py集成
```python
# main.py中添加离线文件转录模式
def run_file_transcription(config):
    """离线文件转录模式"""
    from src.media import MediaConverter, SubtitleGenerator, BatchProcessor

    # 检查FFmpeg
    MediaConverter.ensure_ffmpeg()

    # 初始化组件
    converter = MediaConverter()
    subtitle_gen = SubtitleGenerator()
    processor = BatchProcessor(converter, subtitle_gen)

    # 处理文件...
```

### 配置扩展
需要在 `Config` 数据类中添加:
```python
@dataclass
class Config:
    # 新增字段
    input_file: Optional[List[Path]] = None
    output_dir: Optional[Path] = None
    subtitle_format: str = "srt"
    keep_temp: bool = False
```

---

**模块状态**: ✅ 已实现核心功能
**测试状态**: ⏳ 待添加单元测试
**文档状态**: ✅ 完整
