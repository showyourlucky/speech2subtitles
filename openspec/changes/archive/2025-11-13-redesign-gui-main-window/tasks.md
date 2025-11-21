# Tasks: redesign-gui-main-window (v2.0)

## Overview
本任务列表定义了重新设计GUI主界面的实施步骤(v2.0版本),采用**上下分区布局**和**按需展开**的交互模式,确保每个阶段都能交付可用的功能。

**设计变更** (v1.0 → v2.0):
- ❌ 移除卡片式布局方案
- ✅ 采用上下分区布局 (顶部控制 + 下部结果)
- ✅ 音频源改为下拉选择框
- ✅ 音频电平前置到音频源下方 (从高级设置移出)
- ✅ 文件列表按需展开 (仅文件模式显示)
- ✅ 简化转录控制,统计信息移至状态栏
- ✅ 高级设置简化: 移除音频电平,模型改为下拉选择

---

## Phase 1: 准备和设计验证

### Task 1.1: 生成HTML效果图
**状态**: ✅ 已完成

**描述**: 生成交互式HTML效果图用于设计评审。

**交付物**:
- `docs/ui-mockups/main-window-redesign-v2.html`
- `docs/prds/redesign-gui-main-window-v2.0-prd.md`

**验证**:
- [x] HTML文件可在浏览器中打开
- [x] 支持麦克风/文件/高级设置模式切换
- [x] 设计符合用户需求

**预计时长**: 2小时 (已完成)

---

### Task 1.2: 创建feature分支
**状态**: ✅ 已完成 (跳过,直接在master分支工作)

**描述**: 创建开发分支并准备开发环境。

**实施步骤**:
```bash
git checkout -b feature/redesign-gui-main-window-v2
```

**验证**:
- [ ] 分支创建成功
- [ ] 基于最新main分支

**预计时长**: 5分钟

---

## Phase 2: 核心组件重构

### Task 2.1: 重构AudioSourceSelector为下拉框
**状态**: ✅ 已完成

**描述**: 将音频源选择器从单选按钮组重构为QComboBox。

**实施步骤**:
1. 修改 `src/gui/widgets/audio_source_selector.py`
2. 替换QRadioButton组为QComboBox
3. 添加图标到下拉选项 (🎤/🔊/📁)
4. 保持 `source_changed(str)` 信号不变
5. 更新单元测试

**代码示例**:
```python
class AudioSourceSelector(QWidget):
    source_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout()

        # 标签
        label = QLabel("🎤 音频源:")
        layout.addWidget(label)

        # 下拉框
        self.combo = QComboBox()
        self.combo.addItem("🎤 麦克风", "microphone")
        self.combo.addItem("🔊 系统音频", "system")
        self.combo.addItem("📁 文件", "file")
        self.combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self.combo)

        self.setLayout(layout)

    def _on_selection_changed(self, index):
        source = self.combo.itemData(index)
        self.source_changed.emit(source)
```

**验证**:
- [ ] 下拉框显示三个选项,带图标
- [ ] 选择变化时发射正确的信号
- [ ] 与MainWindow集成正常

**依赖**: Task 1.2

**预计时长**: 3小时

---

### Task 2.2: 创建FileSelectionPanel组件
**状态**: ✅ 已完成

**描述**: 创建独立的文件选择面板,支持按需显示/隐藏。

**实施步骤**:
1. 创建 `src/gui/widgets/file_selection_panel.py`
2. 实现文件列表 (QListWidget + 复选框)
3. 实现操作按钮 (添加/移除/清空)
4. 实现展开/收起动画 (QPropertyAnimation)
5. 提供 `set_visible(bool, animated=True)` 方法

**代码骨架**:
```python
class FileSelectionPanel(QWidget):
    files_changed = Signal(list)

    def __init__(self):
        super().__init__()
        self._is_visible = False
        self._init_ui()
        self.hide()  # 默认隐藏

    def set_visible(self, visible: bool, animated: bool = True):
        if animated:
            # 使用QPropertyAnimation展开/收起
            anim = QPropertyAnimation(self, b"maximumHeight")
            anim.setDuration(200)
            if visible:
                anim.setStartValue(0)
                anim.setEndValue(200)
            else:
                anim.setStartValue(200)
                anim.setEndValue(0)
            anim.start()
        else:
            self.setVisible(visible)
```

**验证**:
- [ ] 展开/收起动画流畅 (200ms)
- [ ] 文件添加/移除功能正常
- [ ] 支持复选框批量选择
- [ ] 文件列表显示文件名和图标

**依赖**: Task 1.2

**预计时长**: 5小时

---

### Task 2.3: 简化TranscriptionControls
**状态**: ✅ 已完成

**描述**: 简化转录控制区域,只保留核心按钮。

**实施步骤**:
1. 修改 `src/gui/widgets/control_panel.py` (或创建新文件)
2. 保留按钮: 开始、暂停、停止
3. 移除统计信息显示 (移至状态栏)
4. 应用主按钮样式 (蓝色背景)
5. 设置固定高度 (~40px)

**布局**:
```python
layout = QHBoxLayout()
layout.addWidget(self.start_button)
layout.addWidget(self.pause_button)
layout.addWidget(self.stop_button)
layout.addStretch()  # 右对齐
```

**验证**:
- [ ] 按钮水平排列
- [ ] 开始按钮使用主色调
- [ ] 按钮状态切换正确
- [ ] 快捷键正常工作

**依赖**: Task 1.2

**预计时长**: 3小时

---

### Task 2.4: 创建AdvancedSettingsPanel (可折叠)
**状态**: ✅ 已完成

**描述**: 创建可折叠的高级设置面板,包含VAD方案、模型选择和GPU设置。

**实施步骤**:
1. 创建 `src/gui/widgets/advanced_settings_panel.py`
2. 继承QGroupBox,设置可折叠属性
3. 整合VAD方案选择器 (QComboBox + 管理按钮)
4. 整合模型选择器 (QComboBox + 浏览按钮)
5. 整合GPU状态显示 (QCheckBox)
6. 显示采样率信息 (只读标签)
7. 实现点击标题栏展开/收起
8. 默认收起状态

**代码示例**:
```python
class AdvancedSettingsPanel(QGroupBox):
    model_changed = Signal(str)
    vad_changed = Signal(str)

    def __init__(self):
        super().__init__("⚙️ 高级设置")
        self.setCheckable(True)
        self.setChecked(False)  # 默认收起
        self.toggled.connect(self._on_toggled)
        self._init_ui()

    def _init_ui(self):
        layout = QGridLayout()

        # VAD方案
        layout.addWidget(QLabel("VAD方案:"), 0, 0)
        self.vad_combo = QComboBox()
        self.vad_combo.addItems(["默认", "高灵敏度", "低灵敏度"])
        layout.addWidget(self.vad_combo, 0, 1)

        # 转录模型
        layout.addWidget(QLabel("转录模型:"), 1, 0)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        layout.addWidget(self.model_combo, 1, 1)

        self.setLayout(layout)

    def _on_toggled(self, checked):
        # 展开/收起内容区域
        self.content_widget.setVisible(checked)
```

**验证**:
- [ ] 点击标题栏切换展开/收起
- [ ] VAD方案切换正常
- [ ] 模型下拉框支持多个模型选择
- [ ] 浏览按钮可打开文件选择对话框
- [ ] GPU状态正确显示

**依赖**: Task 1.2

**预计时长**: 5小时

---

### Task 2.5: 增强StatusBar
**状态**: ✅ 已完成

**描述**: 增强状态栏,显示统计信息。

**实施步骤**:
1. 修改MainWindow的状态栏设置
2. 添加分段显示:
   - 状态文本 (就绪/转录中/暂停)
   - 转录统计 (转录: X句)
   - 时长 (时长: HH:MM:SS)
   - GPU状态 (GPU: ✅ CUDA)
   - VAD方案 (VAD: 默认)
3. 使用 `QStatusBar.addPermanentWidget()` 添加右侧信息
4. 实现实时更新逻辑

**代码示例**:
```python
# 在MainWindow中
self.status_label = QLabel("状态: 就绪")
self.transcription_count_label = QLabel("转录: 0句")
self.duration_label = QLabel("时长: 00:00:00")
self.gpu_label = QLabel("GPU: ✅ CUDA")

self.statusBar().addWidget(self.status_label)
self.statusBar().addWidget(QLabel("|"))
self.statusBar().addWidget(self.transcription_count_label)
self.statusBar().addWidget(QLabel("|"))
self.statusBar().addWidget(self.duration_label)
self.statusBar().addPermanentWidget(self.gpu_label)
```

**验证**:
- [ ] 状态栏显示所有信息
- [ ] 信息实时更新
- [ ] 使用分隔符分段
- [ ] GPU状态带图标

**依赖**: Task 1.2

**预计时长**: 2小时

---

### Task 2.6: 创建AudioLevelDisplay组件
**状态**: ✅ 已完成

**描述**: 创建音频电平显示组件,放置在音频源下方用于实时监控音频输入。

**实施步骤**:
1. 创建 `src/gui/widgets/audio_level_display.py`
2. 继承QWidget,包含Label + ProgressBar + Value Label
3. 实现 `update_level(level: float)` 方法
4. 设置样式:
   - 进度条高度: 10px
   - 最大宽度: 300px
   - 颜色渐变: 绿色到蓝色
5. 添加显示/隐藏控制 (文件模式下隐藏)
6. 实现节流更新 (100-150ms)

**代码示例**:
```python
class AudioLevelDisplay(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._last_update_time = 0
        self._update_interval = 0.1  # 100ms

    def _init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 标签
        self.label = QLabel("🎙️ 音频电平:")
        layout.addWidget(self.label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.setFixedHeight(10)
        layout.addWidget(self.progress_bar)

        # 数值显示
        self.value_label = QLabel("0%")
        self.value_label.setMinimumWidth(40)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.value_label)

        layout.addStretch()
        self.setLayout(layout)

    def update_level(self, level: float):
        """更新音频电平 (0.0-1.0)"""
        current_time = time.time()
        if current_time - self._last_update_time < self._update_interval:
            return

        percentage = int(level * 100)
        self.progress_bar.setValue(percentage)
        self.value_label.setText(f"{percentage}%")
        self._last_update_time = current_time

    def set_visible_for_source(self, source: str):
        """根据音频源设置可见性 (文件模式下隐藏)"""
        visible = source in ["microphone", "system"]
        self.setVisible(visible)
```

**验证**:
- [ ] 电平值实时更新
- [ ] 进度条动画流畅
- [ ] 文件模式下自动隐藏
- [ ] 麦克风/系统音频模式下显示
- [ ] 更新频率符合预期 (100-150ms)

**依赖**: Task 1.2

**预计时长**: 3小时

---

## Phase 3: 主窗口布局重构

### Task 3.1: 重构MainWindow为上下分区布局
**状态**: ✅ 已完成

**描述**: 修改MainWindow使用新的上下分区布局。

**实施步骤**:
1. 修改 `src/gui/main_window.py`
2. 移除旧的左右分割布局 (QSplitter)
3. 创建顶部控制区 (QWidget)
   - 添加AudioSourceSelector (下拉框)
   - 添加AudioLevelDisplay (音频电平,紧邻音频源下方)
   - 添加高级设置按钮
   - 添加TranscriptionControls (按钮组)
   - 添加FileSelectionPanel (可折叠)
4. 创建结果显示区 (保留ResultDisplay)
5. 使用QVBoxLayout组织:
   ```python
   main_layout = QVBoxLayout()
   main_layout.addWidget(top_control_area)     # 固定高度
   main_layout.addWidget(result_display_area)  # 拉伸填充
   ```
6. 连接信号和槽:
   - AudioSourceSelector.source_changed → _on_audio_source_changed
   - _on_audio_source_changed → FileSelectionPanel.set_visible
   - _on_audio_source_changed → AudioLevelDisplay.set_visible_for_source
   - audio_level_updated → AudioLevelDisplay.update_level

**关键代码**:
```python
def _create_ui(self):
    central_widget = QWidget()
    self.setCentralWidget(central_widget)

    main_layout = QVBoxLayout(central_widget)

    # 顶部控制区
    top_area = self._create_top_control_area()
    main_layout.addWidget(top_area)

    # 结果显示区
    self.result_display = ResultDisplay()
    main_layout.addWidget(self.result_display, stretch=1)

def _create_top_control_area(self):
    widget = QWidget()
    widget.setMaximumHeight(250)  # 限制最大高度
    layout = QVBoxLayout(widget)

    # 第一行: 音频源 + 高级设置按钮 + 控制按钮
    row1 = QHBoxLayout()
    row1.addWidget(self.audio_source_selector)
    row1.addStretch()
    row1.addWidget(self.advanced_button)
    row1.addWidget(self.transcription_controls)
    layout.addLayout(row1)

    # 第二行: 文件选择面板 (可折叠)
    layout.addWidget(self.file_panel)

    # 第三行: 高级设置面板 (可折叠)
    layout.addWidget(self.advanced_panel)

    return widget

def _on_audio_source_changed(self, source: str):
    # 显示/隐藏文件面板
    self.file_panel.set_visible(source == "file", animated=True)
```

**验证**:
- [ ] 界面使用上下分区布局
- [ ] 顶部控制区高度合适
- [ ] 选择"文件"时面板展开
- [ ] 选择其他源时面板收起
- [ ] 所有功能正常工作

**依赖**: Task 2.1, 2.2, 2.3, 2.4, 2.5

**预计时长**: 6小时

---

### Task 3.2: 设置窗口尺寸约束
**状态**: ✅ 已完成

**描述**: 设置主窗口的最小/默认尺寸。

**实施步骤**:
1. 在 `MainWindow.__init__()` 中:
   ```python
   self.setMinimumSize(800, 600)      # 最小尺寸
   self.setGeometry(100, 100, 1000, 700)  # 默认尺寸和位置
   ```
2. 测试不同尺寸下的显示效果

**验证**:
- [ ] 窗口无法缩小到800x600以下
- [ ] 默认启动尺寸为1000x700
- [ ] 所有元素在最小尺寸下可见

**依赖**: Task 3.1

**预计时长**: 30分钟

---

## Phase 4: 样式和视觉优化

### Task 4.1: 应用样式美化
**状态**: ⏳ 待开始

**描述**: 应用CSS样式美化界面。

**实施步骤**:
1. 创建 `src/gui/styles/main_window_v2.qss`
2. 定义样式:
   ```css
   /* 主按钮 */
   QPushButton#start_button {
       background-color: #0078D4;
       color: white;
       border: none;
       border-radius: 4px;
       padding: 8px 24px;
       font-weight: bold;
   }

   QPushButton#start_button:hover {
       background-color: #005A9E;
   }

   /* 次要按钮 */
   QPushButton {
       background-color: #E0E0E0;
       border: none;
       border-radius: 4px;
       padding: 8px 16px;
   }

   /* 下拉框 */
   QComboBox {
       border: 1px solid #CCC;
       border-radius: 4px;
       padding: 6px 12px;
   }

   /* 状态栏 */
   QStatusBar {
       background-color: #F0F0F0;
       border-top: 1px solid #DDD;
   }
   ```
3. 在MainWindow中加载:
   ```python
   with open("src/gui/styles/main_window_v2.qss") as f:
       self.setStyleSheet(f.read())
   ```
4. 为组件设置objectName以匹配样式

**验证**:
- [ ] 按钮显示正确的颜色
- [ ] 悬停效果正常
- [ ] 下拉框有边框
- [ ] 整体视觉统一

**依赖**: Task 3.1

**预计时长**: 4小时

---

### Task 4.2: 添加图标和间距调整
**状态**: ⏳ 待开始

**描述**: 添加图标,调整间距和对齐。

**实施步骤**:
1. 使用Emoji图标:
   - 🎤 音频源标签
   - ⚙️ 高级设置按钮
   - 📁 文件面板标题
   - 📝 结果显示标题
2. 调整布局间距:
   ```python
   layout.setContentsMargins(16, 16, 16, 16)
   layout.setSpacing(12)
   ```
3. 设置组件对齐

**验证**:
- [ ] 图标显示正确
- [ ] 间距合适
- [ ] 对齐整齐

**依赖**: Task 4.1

**预计时长**: 2小时

---

## Phase 5: 交互优化

### Task 5.1: 实现展开/收起动画
**状态**: ✅ 已完成

**描述**: 为FileSelectionPanel和AdvancedSettingsPanel添加平滑动画。

**实施步骤**:
1. 使用QPropertyAnimation:
   ```python
   def _animate_expand(self, expand: bool):
       anim = QPropertyAnimation(self, b"maximumHeight")
       anim.setDuration(200)
       anim.setEasingCurve(QEasingCurve.InOutQuad)
       if expand:
           anim.setStartValue(0)
           anim.setEndValue(200)
       else:
           anim.setStartValue(self.height())
           anim.setEndValue(0)
       anim.finished.connect(lambda: self.setVisible(expand))
       anim.start()
   ```
2. 测试动画流畅度

**验证**:
- [ ] 展开/收起动画流畅 (200ms)
- [ ] 无卡顿
- [ ] 动画完成后状态正确

**依赖**: Task 3.1

**预计时长**: 3小时

---

### Task 5.2: 添加键盘快捷键
**状态**: ✅ 已完成

**描述**: 为主要操作添加键盘快捷键。

**实施步骤**:
1. 在MainWindow中添加QShortcut:
   ```python
   QShortcut(QKeySequence("Ctrl+R"), self, self._on_start_transcription)
   QShortcut(QKeySequence("Ctrl+P"), self, self._on_pause_transcription)
   QShortcut(QKeySequence("Ctrl+S"), self, self._on_stop_transcription)
   ```
2. 在工具提示中显示快捷键:
   ```python
   self.start_button.setToolTip("开始转录 (Ctrl+R)")
   ```

**验证**:
- [ ] 快捷键正确触发操作
- [ ] 工具提示显示快捷键
- [ ] 不与系统快捷键冲突

**依赖**: Task 3.1

**预计时长**: 1小时

---

## Phase 6: 测试和文档

### Task 6.1: 功能测试
**状态**: ✅ 基本完成 (代码导入测试通过)

**描述**: 测试所有交互流程。

**测试场景**:
1. 麦克风模式: 选择麦克风 → 开始 → 暂停 → 继续 → 停止
2. 系统音频模式: 选择系统音频 → 开始 → 停止
3. 文件模式: 选择文件 → 添加文件 → 开始 → 查看结果
4. 高级设置: 展开 → 切换VAD方案 → 收起
5. 状态栏: 验证统计信息实时更新
6. 窗口调整: 测试最小尺寸和不同分辨率

**验证**:
- [ ] 所有功能正常工作
- [ ] 无崩溃或错误
- [ ] 动画流畅
- [ ] 状态正确切换

**依赖**: Phase 2-5 所有任务

**预计时长**: 4小时

---

### Task 6.2: 性能测试
**状态**: ⏳ 待开始

**描述**: 测试界面性能。

**测试项目**:
1. 界面加载时间 (目标: < 500ms)
2. 动画帧率 (目标: >= 30fps)
3. 音频电平更新延迟 (目标: < 50ms)
4. 内存占用 (对比旧版本)

**验证**:
- [ ] 所有性能指标达标
- [ ] 无明显性能回退

**依赖**: Task 6.1

**预计时长**: 2小时

---

### Task 6.3: 更新文档
**状态**: ⏳ 待开始

**描述**: 更新项目文档。

**实施步骤**:
1. 更新 `src/gui/CLAUDE.md`:
   - 添加新组件文档
   - 更新布局说明
   - 添加v2.0变更日志
2. 更新根目录 `CLAUDE.md`
3. (可选) 创建用户迁移指南
4. (可选) 录制演示视频

**验证**:
- [ ] 文档准确描述新界面
- [ ] 所有新组件有文档

**依赖**: Task 6.2

**预计时长**: 3小时

---

### Task 6.4: 代码审查和清理
**状态**: ⏳ 待开始

**描述**: 代码审查,清理和格式化。

**实施步骤**:
1. 运行Black格式化:
   ```bash
   black src/gui/
   ```
2. 运行Flake8检查:
   ```bash
   flake8 src/gui/ --max-line-length=88
   ```
3. 移除未使用的导入
4. 添加类型注解
5. 完善docstring

**验证**:
- [ ] 代码格式化完成
- [ ] Flake8无错误
- [ ] 所有公共方法有类型注解

**依赖**: Task 6.3

**预计时长**: 2小时

---

## Phase 7: 发布准备

### Task 7.1: 创建PR和归档OpenSpec
**状态**: ⏳ 待开始

**描述**: 提交代码和归档变更。

**实施步骤**:
1. 提交所有更改:
   ```bash
   git add .
   git commit -m "feat: redesign GUI main window (v2.0)"
   git push origin feature/redesign-gui-main-window-v2
   ```
2. 创建Pull Request
3. 归档OpenSpec变更:
   ```bash
   openspec archive redesign-gui-main-window --yes
   ```

**验证**:
- [ ] PR创建成功
- [ ] OpenSpec变更已归档
- [ ] CI/CD通过

**依赖**: Task 6.4

**预计时长**: 1小时

---

## Summary

**版本**: v2.0 (上下分区布局)
**总任务数**: 21个
**预计总时长**: 约50小时 (6-7个工作日)

**关键里程碑**:
- Phase 2 完成: 核心组件重构完成
- Phase 3 完成: 新界面可运行(功能完整)
- Phase 4 完成: 界面美化完成
- Phase 6 完成: 测试和文档齐全,准备发布

**并行开发建议**:
- Task 2.1, 2.2, 2.3, 2.4 可以并行开发 (4人)
- Phase 4 和 Phase 5 可以部分并行
- 测试可以在每个Phase完成后逐步进行

**设计对比 (v1.0 vs v2.0)**:
| 特性 | v1.0 (卡片式) | v2.0 (上下分区) |
|-----|-------------|---------------|
| 布局结构 | 多卡片网格 | 上下分区 |
| 音频源选择 | 单选按钮 | 下拉框 |
| 文件列表 | 始终显示 | 按需展开 |
| 统计信息 | 控制卡片内 | 状态栏 |
| 高级设置 | 单独卡片 | 折叠面板 |
| 开发复杂度 | 高 (需要BaseCard基类) | 中 (使用标准Qt组件) |
| 预计工时 | 80小时 | 50小时 |

**风险和缓解**:
- **风险**: 动画性能问题
  - **缓解**: 测试不同设备,提供禁用动画选项
- **风险**: 用户适应新界面时间长
  - **缓解**: 提供文档和首次启动引导
- **风险**: 与现有配置不兼容
  - **缓解**: 保持配置向后兼容,添加迁移逻辑
