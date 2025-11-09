# Change: 统一文件转录实现 - 完全替代FileAudioCapture

## Why

当前系统中文件转录功能存在**两套完全独立的实现路径**,导致严重的代码冗余和维护问题:

### 命令行模式 (main.py)
- 使用 `run_file_transcription()` → **BatchProcessor**
- 完整流程: MediaConverter → VAD → TranscriptionEngine → SubtitleGenerator
- **优点**: 成熟、高效、生成字幕文件
- **缺点**: 无GUI进度反馈

### GUI模式 (main_window.py + pipeline.py)
- 使用 **FileAudioCapture** + TranscriptionPipeline
- 分块流式处理: 加载文件 → 分块发送 → Pipeline处理 → 实时显示
- **优点**: 实时显示转录进度和结果
- **缺点**:
  - ❌ 不生成字幕文件
  - ❌ 处理效率低(整个文件加载到内存)
  - ❌ 约**300行重复代码**(文件加载、重采样、声道转换等)

### 核心问题

1. **严重的代码冗余**:
   - FileAudioCapture (475行) 和 BatchProcessor 重复实现:
     - 文件格式检测 (soundfile/pydub)
     - 采样率转换
     - 立体声转单声道
     - 错误处理

2. **维护成本高**: Bug修复需要两处同步,功能增强需要两次实现

3. **功能分裂**: GUI用户必须切换到命令行才能生成字幕

4. **用户体验割裂**: 同一个文件转录任务,GUI和命令行提供完全不同的功能

## What Changes

**核心方案**: 完全移除FileAudioCapture的文件模式,统一使用BatchProcessor

### 1. **🔥 移除FileAudioCapture的文件处理**
- 删除Pipeline对 `config.input_file` 的支持
- AudioSourceSelector移除"文件"选项
- FileAudioCapture标记为废弃,下个版本完全移除

### 2. **BatchProcessor功能增强**
添加 `realtime_preview` 模式:
```python
class BatchProcessor:
    def process_file(
        self,
        file_path: Path,
        ...,
        realtime_preview: bool = False,  # 新增:实时预览开关
        on_segment: Optional[Callable[[Segment], None]] = None,
        on_progress: Optional[Callable[[float], None]] = None,
        on_complete: Optional[Callable[[Path, Path], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ):
        """
        realtime_preview=True:  每个segment立即回调(GUI实时预览)
        realtime_preview=False: 只在最后返回结果(批量模式,默认)
        """
```

### 3. **新增两个GUI对话框**

#### 3.1 快速转录对话框 (`QuickTranscriptionDialog`)
**用途**: 单文件实时预览
- 选择单个文件
- 实时显示每句转录 (`realtime_preview=True`)
- 自动生成字幕文件
- **导出按钮**: SRT/VTT/TXT/剪贴板

#### 3.2 批量转录对话框 (`BatchTranscriptionDialog`)
**用途**: 多文件批量处理
- 选择多个文件
- 轻量级进度反馈 (`realtime_preview=False`)
- 批量生成字幕文件
- 成功/失败统计

### 4. **MainWindow菜单调整**
```
文件菜单:
  ├ 快速转录 (Ctrl+T)        ← 新增:单文件实时预览
  ├ 批量转录文件 (Ctrl+B)    ← 新增:多文件批量处理
  └ 退出 (Ctrl+Q)

音频源选择器:
  ⚫ 麦克风                   ← 保留
  ⚪ 系统音频                 ← 保留
  ❌ 文件                     ← 移除!
```

### 5. **所有文件转录都生成字幕**
- BatchProcessor始终生成字幕文件(无论GUI还是命令行)
- GUI对话框提供"导出为..."功能转换格式
- 避免用户困惑:"为什么有时有字幕文件,有时没有?"

## Impact

### 受影响的规范
- **新增**: `file-transcription-gui` - GUI文件转录统一规范

### 受影响的代码

#### 核心修改 (~600行新增, ~200行删除)
- **`src/media/batch_processor.py`**:
  - 添加 `realtime_preview` 参数 (+20行)
  - 添加回调接口 (+80行)
  - 添加 `process_files()` 批量方法 (+50行)
  - 添加取消支持 (+30行)

- **`src/gui/dialogs/quick_transcription_dialog.py`** (新建, ~250行):
  - 单文件实时预览UI
  - 导出功能实现

- **`src/gui/dialogs/batch_transcription_dialog.py`** (新建, ~300行):
  - 多文件批量处理UI
  - 进度管理和统计

- **`src/gui/main_window.py`**:
  - 添加菜单项 (+20行)
  - 移除音频源选择器文件选项 (-10行)

- **`src/coordinator/pipeline.py`**:
  - 移除 `input_file` 支持 (-30行)
  - 添加错误提示引导用户 (+5行)

- **`src/gui/widgets/audio_source_selector.py`**:
  - 移除文件选项 (-50行)

#### 废弃但暂不删除
- **`src/audio/file_capture.py`**:
  - 添加 `@deprecated` 警告
  - 下个版本完全移除 (-475行)

#### 测试修改
- **`tests/media/test_batch_processor.py`**:
  - 添加回调接口测试 (+100行)

- **`tests/gui/test_quick_transcription_dialog.py`** (新建, ~150行)
- **`tests/gui/test_batch_transcription_dialog.py`** (新建, ~150行)

### ⚠️ Breaking Changes
1. **音频源选择器移除文件选项**
   - 影响: 用户不能再通过主窗口选择文件
   - 迁移: 使用菜单 → 快速转录/批量转录

2. **Pipeline不再支持 config.input_file**
   - 影响: 如果有外部代码直接调用Pipeline处理文件,将报错
   - 迁移: 改用BatchProcessor

### 预期收益

#### 代码质量
- **-300行**: 移除FileAudioCapture重复代码
- **单一代码路径**: 所有文件转录都用BatchProcessor
- **测试简化**: 减少测试覆盖面积30%

#### 用户体验
- **统一行为**: 所有文件转录都生成字幕
- **实时预览**: 快速转录模式实时显示
- **批量处理**: 高效处理多个文件
- **灵活导出**: 一键转换多种格式

#### 维护成本
- **Bug修复**: 只需修改一处(BatchProcessor)
- **功能增强**: 一次实现,两处受益(命令行+GUI)
- **架构清晰**: Pipeline专注实时流,BatchProcessor专注文件

### 风险评估
- **中等风险**: Breaking Change影响现有用户习惯
- **缓解措施**:
  - 首次启动显示迁移指南
  - 音频源选择器显示提示:"文件转录已移至菜单"
  - 完整的用户文档更新

## Migration Plan

### 阶段1: 实现新功能 (第1-2周)
1. BatchProcessor添加 `realtime_preview` 支持
2. 创建QuickTranscriptionDialog
3. 创建BatchTranscriptionDialog
4. MainWindow添加菜单项

### 阶段2: 移除旧代码 (第3周)
1. Pipeline移除 `input_file` 支持
2. AudioSourceSelector移除文件选项
3. 添加迁移提示和文档

### 阶段3: 废弃FileAudioCapture (第4周)
1. 标记为 `@deprecated`
2. 性能测试和优化
3. 用户文档和视频教程

### 阶段4: 完全移除 (下个版本)
1. 删除 `src/audio/file_capture.py`
2. 删除相关测试
3. Release Notes

## Summary

通过**完全统一文件转录实现**,消除代码冗余,提升用户体验:

### 之前
- 命令行: BatchProcessor → 字幕文件
- GUI: FileAudioCapture → 实时显示(无字幕)
- **300行重复代码,用户困惑**

### 之后
- 命令行: BatchProcessor (realtime_preview=False)
- GUI快速转录: BatchProcessor (realtime_preview=True) + 实时显示 + 字幕文件
- GUI批量转录: BatchProcessor (realtime_preview=False) + 进度 + 批量字幕
- **单一代码路径,统一用户体验**

### 核心原则
**KISS + DRY + Single Source of Truth + Breaking Change with Migration Path**
