# GUI模块 (Graphical User Interface Module)

[根目录](../../CLAUDE.md) > [src](../) > **gui**

## 模块职责
提供基于PySide6的图形用户界面,支持实时音频转录和批量文件处理。

## 目录结构
```
gui/
├── __init__.py              - 模块初始化
├── main_window.py           - 主窗口
├── widgets/                 - UI组件
│   ├── audio_source_selector.py  - 音频源选择器
│   ├── control_panel.py          - 控制面板
│   ├── result_display.py         - 结果显示
│   └── status_monitor.py         - 状态监控
├── dialogs/                 - 对话框
│   ├── file_transcription_dialog.py  - 文件转录对话框 (2025-11-10新增)
│   ├── settings_dialog.py            - 设置对话框
│   ├── history_dialog.py             - 历史记录对话框
│   └── export_dialog.py              - 导出对话框
├── bridges/                 - 桥接层
│   ├── pipeline_bridge.py   - Pipeline桥接器
│   └── config_bridge.py     - 配置桥接器
├── models/                  - 数据模型
│   ├── gui_models.py        - GUI数据模型
│   └── history_models.py    - 历史记录模型
└── storage/                 - 存储管理
    ├── config_file_manager.py  - 配置文件管理
    ├── history_manager.py      - 历史记录管理
    └── exporters.py            - 导出器
```

## 主要功能

### 1. MainWindow - 主窗口
**文件**: `main_window.py`

**功能**:
- 实时音频转录 (麦克风/系统音频)
- 菜单和工具栏管理
- 状态栏显示
- 全局快捷键

**主要方法**:
```python
class MainWindow(QMainWindow):
    def __init__(self, config: Config)
    def _create_menu_bar(self)           # 创建菜单栏
    def _show_settings_dialog(self)      # 显示设置对话框
    def _show_batch_transcription_dialog(self)  # 显示批量转录对话框 (新增)
    def start_transcription(self)        # 开始实时转录
    def stop_transcription(self)         # 停止实时转录
```

### 2. FileTranscriptionDialog - 文件转录对话框 (2025-11-10新增)
**文件**: `dialogs/file_transcription_dialog.py`

**功能**:
- 批量选择媒体文件
- 实时显示转录进度和预览
- 自动生成字幕文件
- 支持取消操作
- 错误处理和统计

**UI组件**:
- 文件列表 (支持拖放,添加/移除)
- 输出目录选择
- 字幕格式选择 (SRT/VTT)
- 总进度条和当前文件进度条
- 转录结果预览区 (最近50条)
- 统计信息 (成功/失败/总数)

**信号**:
```python
class FileTranscriptionDialog(QDialog):
    # 信号定义
    file_progress_changed = Signal(int, float)  # (file_index, progress_percent)
    segment_received = Signal(object)           # (segment)
    file_completed = Signal(str, str)           # (file_path, subtitle_file)
    all_completed = Signal(dict)                # (statistics)
```

**Worker线程**:
```python
class TranscriptionWorker(QThread):
    """后台转录线程"""
    file_started = Signal(int, int, str)             # (index, total, filename)
    file_progress = Signal(int, float)               # (index, progress)
    segment_received = Signal(object)                # (segment)
    file_completed = Signal(str, str, float, float)  # (file, subtitle, duration, rtf)
    all_completed = Signal(dict)                     # (stats)
    error_occurred = Signal(str)                     # (error_msg)
```

**使用示例**:
```python
# 从MainWindow调用
@Slot()
def _show_batch_transcription_dialog(self):
    dialog = FileTranscriptionDialog(self.config, parent=self)
    dialog.exec()
```

### 3. SettingsDialog - 设置对话框
**文件**: `dialogs/settings_dialog.py`

**功能**:
- 模型路径配置
- VAD参数调整
- 音频设备选择
- GPU/CPU模式切换

### 4. Bridges - 桥接层
**功能**:
- `PipelineBridge`: 连接GUI和TranscriptionPipeline
- `ConfigBridge`: 管理GUI配置和核心配置同步

## 技术细节

### 线程模型
- **主线程**: UI更新和事件处理
- **Worker线程**:
  - 实时转录: Pipeline在独立线程运行
  - 文件转录: TranscriptionWorker运行BatchProcessor

### 信号-槽机制
所有跨线程通信使用Qt信号-槽:
```python
# Worker线程发射信号
self.segment_received.emit(segment)

# 主线程接收信号
worker.segment_received.connect(self._on_segment_received)
```

### 资源管理
- 对话框关闭时自动清理Worker线程
- 取消操作通过 `threading.Event` 实现
- 临时文件由BatchProcessor管理

## 依赖关系

### 外部依赖
- `PySide6`: Qt框架的Python绑定
- `PySide6.QtCore`: 核心功能(信号、线程等)
- `PySide6.QtWidgets`: UI组件
- `PySide6.QtGui`: GUI工具

### 内部依赖
- `src.config`: 配置管理
- `src.coordinator.pipeline`: 实时转录流水线
- `src.media.batch_processor`: 批量文件处理
- `src.transcription.engine`: 转录引擎
- `src.vad.detector`: VAD检测器

## 常见问题

### Q: FileTranscriptionDialog如何与BatchProcessor交互?
A: 通过TranscriptionWorker线程调用BatchProcessor,回调函数发射Qt信号更新UI

### Q: 如何支持拖放文件?
A: 实现 `dragEnterEvent()` 和 `dropEvent()` 方法,验证文件类型

### Q: 如何限制预览区内容数量?
A: 使用deque限制最大长度,或在追加时检查行数并删除旧内容

### Q: 取消操作如何工作?
A: 设置 `cancel_event`,BatchProcessor在关键点检查此事件并抛出 `BatchProcessorCancelled`

## 变更日志 (Changelog)
- **2025-11-10**: 新增FileTranscriptionDialog,实现GUI批量文件转录功能
  - 支持多文件选择和批量处理
  - 实时显示进度和转录预览
  - 自动生成字幕文件
  - 支持取消和错误恢复
- **2025-09-28**: 创建GUI模块,实现基本的实时转录界面

## 相关文件
- `main_window.py` - 主窗口实现
- `dialogs/file_transcription_dialog.py` - 文件转录对话框
- `dialogs/settings_dialog.py` - 设置对话框
- `CLAUDE.md` - 模块文档 (本文件)
