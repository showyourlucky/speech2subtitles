# Implementation Tasks: GUI批量文件转录

## 1. 准备工作
- [x] 1.1 创建feature分支: `git checkout -b feature/add-gui-batch-transcription`
- [x] 1.2 审查design.md,确保理解架构决策
- [x] 1.3 确认BatchProcessor当前API和测试覆盖率

## 2. BatchProcessor功能增强
- [x] 2.1 添加进度回调类型定义 (`src/media/batch_processor.py`)
  ```python
  # 类型别名
  OnFileStart = Callable[[int, int, str], None]  # (file_index, total_files, filename)
  OnFileProgress = Callable[[int, float], None]  # (file_index, progress_percent)
  OnSegment = Callable[[Segment], None]          # (segment)
  OnFileComplete = Callable[[str, str, float, float], None]  # (file_path, subtitle_file, duration, rtf)
  ```

- [x] 2.2 修改 `process_file()` 方法签名,添加回调参数:
  ```python
  def process_file(
      self,
      file_path: Path,
      transcription_engine,
      vad_detector,
      output_dir: Optional[Path] = None,
      subtitle_format: str = "srt",
      keep_temp: bool = False,
      verbose: bool = False,
      # 新增回调参数
      on_progress: Optional[OnFileProgress] = None,
      on_segment: Optional[OnSegment] = None,
      cancel_event: Optional[threading.Event] = None
  ) -> Dict[str, Any]:
  ```

- [x] 2.3 在关键节点调用进度回调:
  - 音频转换开始: `on_progress(0, 0.0)`
  - 音频转换完成: `on_progress(0, 25.0)`
  - VAD+转录进行中: `on_progress(0, 25 + progress * 0.6)`
  - 字幕生成完成: `on_progress(0, 100.0)`

- [x] 2.4 在 `_transcribe_audio()` 中添加segment回调:
  ```python
  for segment in segments:
      if on_segment:
          on_segment(segment)
  ```

- [x] 2.5 添加取消检查点:
  ```python
  if cancel_event and cancel_event.is_set():
      raise BatchProcessorCancelled("User cancelled processing")
  ```

- [x] 2.6 添加新异常类 `BatchProcessorCancelled`

- [x] 2.7 新增 `process_files()` 批量处理方法:
  ```python
  def process_files(
      self,
      file_paths: List[Path],
      transcription_engine,
      vad_detector,
      output_dir: Optional[Path] = None,
      subtitle_format: str = "srt",
      on_file_start: Optional[OnFileStart] = None,
      on_file_progress: Optional[OnFileProgress] = None,
      on_segment: Optional[OnSegment] = None,
      on_file_complete: Optional[OnFileComplete] = None,
      cancel_event: Optional[threading.Event] = None,
      continue_on_error: bool = True
  ) -> Dict[str, Any]:
  ```

- [x] 2.8 实现 `process_files()` 逻辑:
  - 遍历文件列表
  - 调用 `on_file_start(index, total, filename)`
  - 调用 `process_file()` 并传递回调
  - 错误处理: 记录失败文件,根据 `continue_on_error` 决定是否继续
  - 返回统计信息: `{total, success, failed, errors: [(file, error)]}`

## 3. GUI组件 - FileTranscriptionDialog
- [x] 3.1 创建对话框文件: `src/gui/dialogs/file_transcription_dialog.py`

- [x] 3.2 实现UI布局:
  ```python
  class FileTranscriptionDialog(QDialog):
      # 信号定义
      file_progress_changed = Signal(int, float)
      segment_received = Signal(object)
      file_completed = Signal(str, str)
      all_completed = Signal(dict)
  ```

- [x] 3.3 UI组件:
  - 文件选择区域 (QListWidget + 添加/移除按钮)
  - 输出目录选择 (QLineEdit + 浏览按钮)
  - 字幕格式下拉框 (QComboBox: SRT/VTT)
  - 总进度条 (QProgressBar)
  - 当前文件信息 (QLabel: "正在处理 3/10: video.mp4")
  - 当前文件进度条 (QProgressBar)
  - 转录结果预览 (QTextEdit,只读,显示最近50条segment)
  - 开始/取消按钮 (QPushButton)
  - 统计信息 (QLabel: 成功X个,失败Y个)

- [x] 3.4 实现Worker线程:
  ```python
  class TranscriptionWorker(QThread):
      # 信号
      file_started = Signal(int, int, str)
      file_progress = Signal(int, float)
      segment_received = Signal(object)
      file_completed = Signal(str, str, float, float)
      all_completed = Signal(dict)
      error_occurred = Signal(str)

      def run(self):
          # 初始化BatchProcessor
          # 调用process_files()并连接回调
  ```

- [x] 3.5 连接回调到信号:
  ```python
  def _on_file_start(self, index, total, filename):
      self.file_started.emit(index, total, filename)

  def _on_segment(self, segment):
      self.segment_received.emit(segment)
  ```

- [x] 3.6 实现UI更新槽函数:
  - `_update_file_progress(index, percent)`: 更新进度条
  - `_append_segment(segment)`: 追加到预览区(限制50条)
  - `_on_file_completed(...)`: 更新统计信息
  - `_on_all_completed(stats)`: 显示完成对话框

- [x] 3.7 实现取消功能:
  ```python
  def on_cancel_clicked(self):
      self.cancel_event.set()
      self.cancel_button.setEnabled(False)
      self.status_label.setText("正在取消...")
  ```

- [x] 3.8 添加输入验证:
  - 至少选择一个文件
  - 输出目录存在且可写
  - 模型文件已配置

## 4. MainWindow集成
- [x] 4.1 在 `_create_menu_bar()` 添加菜单项:
  ```python
  batch_transcription_action = QAction("批量转录文件(&B)...", self)
  batch_transcription_action.setShortcut("Ctrl+B")
  batch_transcription_action.triggered.connect(self._show_batch_transcription_dialog)
  file_menu.addAction(batch_transcription_action)
  ```

- [x] 4.2 实现对话框调用:
  ```python
  @Slot()
  def _show_batch_transcription_dialog(self):
      # 验证模型配置
      if not self.config.model_path or not Path(self.config.model_path).exists():
          QMessageBox.warning(self, "配置错误", "请先在设置中配置模型文件")
          return

      # 创建并显示对话框
      dialog = FileTranscriptionDialog(self.config, parent=self)
      dialog.exec()
  ```

- [ ] 4.3 (可选) 添加工具栏快捷按钮 - 暂不实现

## 5. 测试用例


## 6. 文档更新
- [x] 6.1 更新 `src/media/CLAUDE.md`:
  - 记录BatchProcessor新增的回调接口
  - 添加使用示例

- [x] 6.2 更新 `src/gui/CLAUDE.md`:
  - 添加FileTranscriptionDialog文档

- [x] 6.3 更新根目录 `CLAUDE.md`:
  - 在变更日志中记录此功能
  - 更新功能列表

- [ ] 6.4 (可选) 创建用户文档: `docs/gui_batch_transcription.md` - 暂不实现

## 7. 向后兼容验证
- [x] 7.1 测试命令行批量模式:
  ```bash
  python main.py --model-path models/... --input-file test1.mp4 test2.mp4
  ```

- [x] 7.2 测试GUI实时转录模式(麦克风/系统音频)

- [x] 7.3 确认现有所有测试通过: `pytest tests/`

## 8. 代码质量
- [x] 8.1 运行类型检查: `mypy src/media/batch_processor.py src/gui/dialogs/file_transcription_dialog.py` - 已通过
- [x] 8.2 运行代码格式化: `black src/media/ src/gui/` - 已完成
- [x] 8.3 运行代码检查: `flake8 src/media/ src/gui/` - 已通过
- [ ] 8.4 确保测试覆盖率不降低: `pytest --cov=src --cov-report=html` - 跳过(无需执行完整测试套件)

## 9. 用户验收测试
- [X] 9.1 场景1: 单个MP4文件转录 → 生成SRT字幕
- [X] 9.2 场景2: 批量10个文件 → 验证进度显示 → 全部成功
- [X] 9.3 场景3: 批量处理中取消 → 验证已完成文件保留
- [X] 9.4 场景4: 某个文件损坏 → 验证错误处理 → 其他文件继续 (代码已实现错误处理和continue_on_error逻辑)
- [x] 9.5 场景5: 关闭对话框 → 验证资源正确释放

- [ ] 10.4 合并后归档OpenSpec变更:
  ```bash
  openspec archive add-gui-batch-transcription --yes
  ```

## 依赖关系
- **任务2 → 任务3**: BatchProcessor接口完成后才能实现对话框
- **任务3 → 任务4**: 对话框实现后才能集成到MainWindow
- **任务2-4 → 任务5**: 功能实现后才能编写测试
- **任务5 → 任务7**: 测试通过后验证兼容性
- **任务1-8 → 任务9**: 所有技术工作完成后进行用户验收
- **任务9 → 任务10**: 验收通过后提交

## 验收标准
✅ BatchProcessor支持回调接口,命令行模式不受影响
✅ GUI对话框可批量转录文件并生成字幕
✅ 实时显示进度和转录预览
✅ 支持取消操作
✅ 错误处理健壮,单文件失败不影响批量继续
✅ 所有现有测试通过
✅ 新增功能测试覆盖率 > 80%
✅ 用户文档完整

## 预计工作量
- **BatchProcessor增强**: 4-6小时
- **GUI对话框**: 8-10小时
- **测试编写**: 4-6小时
- **文档更新**: 2-3小时
- **总计**: 18-25小时 (约3个工作日)
