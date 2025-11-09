# Design: GUI文件转录统一实现 - 完全替代FileAudioCapture

## Context

### 背景
当前系统有**两套独立的文件转录实现**:

1. **命令行模式**: main.py → run_file_transcription() → BatchProcessor → 字幕文件
   - ✅ 成熟、高效、生成字幕文件
   - ❌ 无GUI进度反馈

2. **GUI模式**: main_window.py → TranscriptionPipeline → FileAudioCapture → 实时显示
   - ✅ 实时显示转录结果
   - ❌ 不生成字幕文件
   - ❌ 整个文件加载到内存
   - ❌ 代码重复(文件加载、重采样等)

### 核心问题
- **代码冗余**: FileAudioCapture 和 BatchProcessor 有约300行重复代码
- **功能分裂**: GUI用户需要命令行才能生成字幕
- **维护成本**: Bug需要在两处修复

### 约束
- 必须保持命令行模式完全向后兼容
- GUI实时转录(麦克风/系统音频)不受影响
- Windows平台,需要处理文件路径和编码问题

### 利益相关者
- **终端用户**: 需要统一的GUI文件转录体验
- **开发者**: 需要单一代码路径,减少维护成本
- **测试人员**: 减少测试覆盖面积

## Goals / Non-Goals

### Goals
✅ **完全移除** FileAudioCapture 的文件处理功能
✅ 统一使用 BatchProcessor 处理所有文件转录场景
✅ 提供**实时预览模式**和**批量处理模式**两种UI
✅ 所有文件转录都**自动生成字幕文件**
✅ 提供**导出按钮**支持多种格式(SRT/VTT/TXT)
✅ 支持取消操作和错误恢复

### Non-Goals
❌ 不修改TranscriptionPipeline的麦克风/系统音频路径
❌ 不改变命令行使用方式
❌ 不实现并行文件处理(顺序处理即可)
❌ 不实现实时字幕编辑功能

## Decisions

### 🔥 决策1: 完全废弃FileAudioCapture的文件模式

**选择**: 移除 FileAudioCapture,统一使用 BatchProcessor

**理由**:
- **DRY原则**: 消除300+行重复代码
- **单一职责**: FileAudioCapture保留用于未来可能的流式音频场景
- **简化架构**: 减少代码路径,降低维护成本
- **功能完整**: BatchProcessor + 回调接口 = 实时预览 + 字幕生成

**影响**:
- ⚠️ **BREAKING**: 现有GUI文件模式(通过音频源选择器)将被移除
- ✅ **替代**: 提供两种新的文件转录入口:
  1. "快速转录" - 单文件实时预览 + 字幕生成
  2. "批量转录" - 多文件批量处理

**迁移路径**:
```python
# 移除 src/coordinator/pipeline.py:212-233
# if self.config.input_file is not None:
#     self.audio_capture = FileAudioCapture(...)  ← 删除

# 替代为
if self.config.input_file is not None:
    raise ValueError(
        "文件转录不再通过Pipeline支持。\n"
        "请使用 '文件' → '快速转录' 或 '批量转录文件'"
    )
```

### 决策2: BatchProcessor支持实时预览配置

**选择**: 添加 `realtime_preview` 模式

**实现**:
```python
class BatchProcessor:
    def process_file(
        self,
        file_path: Path,
        ...,
        # 新增参数
        realtime_preview: bool = False,  # 是否实时回调每个segment
        on_segment: Optional[Callable[[Segment], None]] = None,
        on_progress: Optional[Callable[[float], None]] = None,
    ):
        """
        Args:
            realtime_preview:
                - True: 每个segment立即回调(实时预览模式)
                - False: 只在最后生成字幕文件(批量模式,默认)
        """
```

**性能权衡**:
- `realtime_preview=True`: 轻微性能损失(~5%),获得实时反馈
- `realtime_preview=False`: 最佳性能,适合批量处理

**理由**:
- 一个参数控制两种行为模式
- 命令行默认 False,GUI默认 True
- 避免重复代码

### 决策3: 提供两种GUI入口

**选择**: 创建两个对话框

#### 3.1 快速转录对话框 (`QuickTranscriptionDialog`)
**用途**: 单文件实时预览

**特点**:
- 选择单个文件
- 实时显示每句转录(`realtime_preview=True`)
- 自动生成字幕文件
- 提供"导出为..."按钮(SRT/VTT/TXT)
- 进度条 + 实时文本预览

**UI布局**:
```
┌─────────────────────────────────────┐
│  快速转录                            │
├─────────────────────────────────────┤
│  文件: [video.mp4        ] [浏览]   │
│  输出: [./subtitles/     ] [浏览]   │
│  格式: [SRT ▼]                      │
├─────────────────────────────────────┤
│  ━━━━━━━━━━━━━━━━━ 45%             │
│  正在转录... (已处理 1:23 / 3:05)   │
├─────────────────────────────────────┤
│  转录预览:                           │
│  ┌─────────────────────────────┐   │
│  │ [00:00:12] 大家好           │   │
│  │ [00:00:15] 欢迎收看这期视频  │   │
│  │ [00:00:18] 今天我们来讲...   │   │
│  │ ...                         │   │
│  └─────────────────────────────┘   │
├─────────────────────────────────────┤
│         [开始] [取消] [导出为...▼]  │
└─────────────────────────────────────┘
```

**导出按钮菜单**:
- 导出为 SRT
- 导出为 VTT
- 导出为纯文本
- 复制到剪贴板

#### 3.2 批量转录对话框 (`BatchTranscriptionDialog`)
**用途**: 多文件批量处理

**特点**:
- 选择多个文件
- 轻量级进度反馈(`realtime_preview=False`)
- 批量生成字幕文件
- 显示成功/失败统计

**UI布局**:
```
┌─────────────────────────────────────┐
│  批量转录文件                        │
├─────────────────────────────────────┤
│  文件列表:                           │
│  ┌─────────────────────────────┐   │
│  │ ✅ video1.mp4               │   │
│  │ ⏳ video2.avi  (处理中...)  │   │
│  │ ⬜ video3.mkv               │   │
│  └─────────────────────────────┘   │
│  [添加文件] [移除选中]              │
│  输出: [./subtitles/] [浏览]        │
│  格式: [SRT ▼]                      │
├─────────────────────────────────────┤
│  总进度: ━━━━━━━━━ 2/10 (20%)       │
│  当前: ━━━━━━━━━━━━ 45%             │
│  正在处理: video2.avi               │
├─────────────────────────────────────┤
│  最近转录: (可选,最多显示10条)       │
│  [00:01:23] 这是第二个视频的内容...  │
├─────────────────────────────────────┤
│  统计: 成功2, 失败0, 剩余8          │
│               [开始] [取消] [关闭]  │
└─────────────────────────────────────┘
```

**理由**:
- 两种对话框满足不同使用场景
- 快速转录关注实时体验
- 批量转录关注效率和统计

**备选方案**:
- 单一对话框通过选项卡切换 ❌
  - UI复杂,用户困惑
  - 两种模式行为差异大

### 决策4: 字幕文件自动生成 + 导出功能

**选择**: 所有文件转录都生成字幕文件,并提供额外导出选项

**实现**:
```python
# BatchProcessor 始终生成字幕文件
result = processor.process_file(file_path, output_dir, subtitle_format="srt")
# 返回: {"subtitle_file": "video.srt", "segments": [...]}

# GUI对话框提供导出按钮
class QuickTranscriptionDialog:
    def export_as(self, format: str):
        """
        导出选项:
        - SRT (默认已生成)
        - VTT (转换SRT → VTT)
        - TXT (纯文本,无时间戳)
        - 剪贴板 (复制所有文本)
        """
        if format == "vtt":
            SubtitleGenerator.convert_srt_to_vtt(self.subtitle_file)
        elif format == "txt":
            SubtitleGenerator.extract_text_only(self.subtitle_file)
        ...
```

**理由**:
- 统一行为: 所有文件转录都有字幕文件输出
- 灵活导出: 用户可以根据需要转换格式
- 避免重复转录: 已生成的字幕可以快速转换格式

### 决策5: 移除Pipeline的文件模式支持

**选择**: TranscriptionPipeline 不再支持 `config.input_file`

**实现**:
```python
# src/coordinator/pipeline.py
def initialize(self):
    # 检查配置
    if self.config.input_file is not None:
        raise ValueError(
            "Pipeline不再支持文件输入模式。\n"
            "文件转录请使用:\n"
            "  - 菜单 → 文件 → 快速转录 (单文件实时预览)\n"
            "  - 菜单 → 文件 → 批量转录文件 (多文件批量处理)"
        )

    # 只支持麦克风和系统音频
    if self.config.input_source == "system":
        self.audio_capture = SystemAudioCapture(...)
    elif self.config.input_source == "microphone":
        self.audio_capture = AudioCapture(...)
    else:
        raise ValueError("不支持的音频源")
```

**理由**:
- 清晰的职责划分:
  - Pipeline = 实时音频流处理(麦克风/系统音频)
  - BatchProcessor = 文件处理
- 避免混淆: 用户不会尝试通过音频源选择器选择文件
- 简化Pipeline代码: 移除文件相关逻辑

**迁移影响**:
- ⚠️ 主窗口的音频源选择器移除"文件"选项
- ✅ 新增菜单项引导用户使用正确入口

### 决策6: 回调接口设计

**选择**: 最小化回调接口,避免过度设计

**接口定义**:
```python
# 类型别名
OnProgress = Callable[[float], None]           # 进度百分比 0-100
OnSegment = Callable[[Segment], None]          # 转录片段
OnFileComplete = Callable[[Path, Path], None]  # (原文件, 字幕文件)

class BatchProcessor:
    def process_file(
        self,
        file_path: Path,
        ...,
        realtime_preview: bool = False,
        on_progress: Optional[OnProgress] = None,
        on_segment: Optional[OnSegment] = None,    # 仅当 realtime_preview=True 时调用
        on_complete: Optional[OnFileComplete] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> Dict[str, Any]:
        """
        返回值 (保持向后兼容):
        {
            # 核心字段 (必需)
            "success": bool,                # 是否成功
            "file": str,                    # 输入文件路径
            "subtitle_file": str,           # 输出字幕文件路径
            "error": Optional[str],         # 错误描述 (失败时)

            # 转录结果 (成功时)
            "segments": List[Segment],      # 新增: 完整segment列表 (用于GUI显示)
            "segments_count": int,          # segment数量

            # 性能统计
            "duration": float,              # 音频时长(秒)
            "rtf": float,                   # Real-Time Factor
            "convert_time": float,          # 音频转换耗时
            "transcribe_time": float,       # 转录耗时
            "subtitle_time": float,         # 字幕生成耗时
            "total_time": float             # 总耗时
        }

        注意: 所有现有字段保持不变,确保命令行代码无需修改
        """
```

**调用时机**:
```python
# 进度回调 (始终可用)
on_progress(0.0)    # 开始
on_progress(25.0)   # 音频转换完成
on_progress(85.0)   # 转录完成
on_progress(100.0)  # 字幕生成完成

# Segment回调 (仅 realtime_preview=True)
if realtime_preview and on_segment:
    for segment in transcription_results:
        on_segment(segment)  # 每个segment立即回调

# 完成回调
if on_complete:
    on_complete(file_path, subtitle_file)
```

**理由**:
- 简洁: 只有3个回调函数
- 灵活: realtime_preview控制行为
- 性能: 批量模式无额外开销

## Architecture

### 新架构图

```
┌─────────────────────────────────────────────────────┐
│                    MainWindow                       │
│  ┌───────────────────────────────────────────────┐ │
│  │  菜单栏                                        │ │
│  │  ┌──────────┬──────────┬──────────┐          │ │
│  │  │ 文件     │ 设置     │ 帮助     │          │ │
│  │  │ ├ 快速转录│          │          │          │ │
│  │  │ ├ 批量转录│          │          │          │ │
│  │  │ └ 退出   │          │          │          │ │
│  │  └──────────┴──────────┴──────────┘          │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │  音频源选择器 (仅麦克风/系统音频)              │ │
│  │  ⚫ 麦克风                                     │ │
│  │  ⚪ 系统音频                                   │ │
│  │  ❌ 文件 (已移除)                             │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │  TranscriptionPipeline                        │ │
│  │  (仅处理实时音频流)                            │ │
│  │  AudioCapture / SystemAudioCapture            │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘

         ↓ 用户点击 "快速转录"
┌─────────────────────────────────────────────────────┐
│       QuickTranscriptionDialog (模态对话框)         │
│  ┌───────────────────────────────────────────────┐ │
│  │  Worker Thread                                │ │
│  │  ┌─────────────────────────────────────────┐ │ │
│  │  │  BatchProcessor.process_file()          │ │ │
│  │  │  realtime_preview=True                  │ │ │
│  │  │  on_segment=_handle_segment  ←实时回调  │ │ │
│  │  │  on_progress=_update_progress           │ │ │
│  │  └─────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────┘ │
│  实时显示 + 生成字幕文件                            │
└─────────────────────────────────────────────────────┘

         ↓ 用户点击 "批量转录文件"
┌─────────────────────────────────────────────────────┐
│      BatchTranscriptionDialog (模态对话框)          │
│  ┌───────────────────────────────────────────────┐ │
│  │  Worker Thread                                │ │
│  │  ┌─────────────────────────────────────────┐ │ │
│  │  │  BatchProcessor.process_files()         │ │ │
│  │  │  realtime_preview=False  ←仅进度回调    │ │ │
│  │  │  on_file_start, on_file_complete        │ │ │
│  │  └─────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────┘ │
│  进度显示 + 批量生成字幕文件                        │
└─────────────────────────────────────────────────────┘

命令行模式 (不受影响):
main.py → run_file_transcription() → BatchProcessor (realtime_preview=False)
```

### 数据流对比

#### 快速转录模式
```
用户选择文件 → QuickTranscriptionDialog
    ↓
Worker线程调用 BatchProcessor.process_file(realtime_preview=True)
    ↓
MediaConverter 转换音频 → on_progress(25%)
    ↓
VAD + TranscriptionEngine → 每个segment
    ├→ on_segment(seg)  ← 实时回调GUI显示
    └→ on_progress(25% + progress * 60%)
    ↓
SubtitleGenerator 生成SRT → on_progress(100%)
    ↓
返回: {"subtitle_file": "video.srt", "segments": [...]}
    ↓
GUI显示: "转录完成! 字幕已保存至 video.srt"
用户点击 "导出为VTT" → 转换格式
```

#### 批量转录模式
```
用户选择10个文件 → BatchTranscriptionDialog
    ↓
Worker线程调用 BatchProcessor.process_files(realtime_preview=False)
    ↓
逐个处理文件:
  File 1: process_file() → on_progress() → 完成
  File 2: process_file() → on_progress() → 完成
  ...
    ↓
返回统计: {total: 10, success: 9, failed: 1}
    ↓
GUI显示: "批量转录完成! 成功9个, 失败1个"
```

## Risks / Trade-offs

### 风险1: Breaking Change - 移除现有文件模式

**风险**: 用户习惯通过音频源选择器选择文件

**缓解**:
- ✅ 在音频源选择器显示提示信息:
  ```
  "文件转录已移至菜单:
   - 文件 → 快速转录 (单文件)
   - 文件 → 批量转录文件 (多文件)"
  ```
- ✅ 首次启动时显示欢迎对话框,介绍新功能
- ✅ 更新用户文档和视频教程

### 风险2: 实时预览性能开销

**风险**: 频繁回调可能影响处理速度

**测试数据** (需验证):
- `realtime_preview=False`: 100% 基准性能
- `realtime_preview=True`: 约95% 性能 (可接受)

**缓解**:
- ✅ 限制回调频率: 每个segment最多100ms调用一次
- ✅ 快速转录默认启用,批量转录默认禁用
- ✅ 提供设置选项: "批量模式显示实时预览"

### 风险3: FileAudioCapture完全移除

**风险**: 可能有未知的依赖或用例

**缓解**:
- ✅ 保留 `FileAudioCapture` 类定义,只移除集成点
- ✅ 添加废弃警告: `@deprecated("请使用BatchProcessor")`
- ✅ 下个版本完全移除

**回滚计划**:
- 如果发现问题,可以快速恢复Pipeline的文件模式
- 新增代码完全独立,回滚无副作用

### 权衡: 统一 vs 灵活性

**权衡**:
- ✅ 统一代码路径 → 降低维护成本
- ⚠️ 失去分块流式处理的灵活性

**决策**: 接受权衡
- 文件转录不需要真正的流式处理
- 批量模式已经足够高效
- 未来如需流式处理,可以在BatchProcessor内部优化

## Migration Plan

### 阶段1: 实现新功能 (本提案,第1-2周)
1. ✅ BatchProcessor添加 `realtime_preview` 支持
2. ✅ 创建 QuickTranscriptionDialog
3. ✅ 创建 BatchTranscriptionDialog
4. ✅ MainWindow添加菜单项

### 阶段2: 移除旧代码 (第3周)
1. ⚠️ Pipeline移除 `input_file` 支持
2. ⚠️ AudioSourceSelector移除文件选项
3. ⚠️ 添加迁移提示和文档

### 阶段3: 清理和优化 (第4周)
1. 🗑️ 标记 FileAudioCapture 为废弃
2. 📝 更新所有文档和示例
3. ✅ 性能测试和优化

### 阶段4: 完全移除 (下个版本)
1. 🗑️ 删除 `src/audio/file_capture.py`
2. 🗑️ 删除相关测试
3. 📝 Release Notes

### 回滚计划
如果发现严重问题:
1. 恢复Pipeline的文件模式支持
2. AudioSourceSelector恢复文件选项
3. 保留新对话框作为额外选项

## Open Questions

### Q1: 实时预览是否支持"仅预览不保存"?
**决策**: ❌ 不支持
**理由**: 所有文件转录都生成字幕,避免用户困惑

### Q2: 批量模式是否显示实时预览?
**决策**: ⚪ 可选 (默认关闭)
**理由**: 用户可在设置中开启,但默认追求效率

### Q3: 是否支持拖放文件?
**决策**: ✅ 阶段2实现
**理由**: 提升用户体验,但非核心功能

### Q4: 导出格式是否支持ASS/SSA?
**决策**: ⏳ 评估后决定
**理由**: SRT/VTT已覆盖主要需求,ASS可后续添加

## Summary

本设计通过**完全统一文件转录实现**,达到:

### 技术收益
- ✅ 移除300+行重复代码 (FileAudioCapture)
- ✅ 单一代码路径: BatchProcessor
- ✅ 简化Pipeline: 仅处理实时音频流
- ✅ 降低测试复杂度

### 用户收益
- ✅ **统一体验**: 所有文件转录都生成字幕
- ✅ **实时预览**: 快速转录模式实时显示
- ✅ **批量处理**: 高效处理多个文件
- ✅ **灵活导出**: 多种格式一键转换

### 核心原则
**KISS + DRY + Single Source of Truth**

**关键实现**: `BatchProcessor.realtime_preview` 参数统一两种模式行为
