# Tasks: redesign-gui-main-window

## Overview
本任务列表定义了重新设计GUI主界面的实施步骤,采用渐进式开发策略,确保每个阶段都能交付可用的功能。

---

## Phase 1: 基础卡片组件实现

### Task 1.1: 创建卡片基类
**描述**: 创建可复用的BaseCard组件,封装卡片的通用样式和行为。

**实现步骤**:
1. 创建 `src/gui/widgets/base_card.py`
2. 实现 `BaseCard(QWidget)` 类
   - 设置默认样式(边框、圆角、内边距)
   - 提供 `set_title()` 方法
   - 提供 `set_content_widget()` 方法
3. 编写单元测试 `tests/gui/widgets/test_base_card.py`

**验证**:
- 卡片显示正确的边框和圆角
- 标题正确显示
- 内容区域可以添加子组件

**依赖**: 无

**预计时长**: 3小时

---

### Task 1.2: 实现AudioSourceCard
**描述**: 基于BaseCard实现音频源选择卡片。

**实现步骤**:
1. 创建 `src/gui/widgets/audio_source_card.py`
2. 继承 `BaseCard`
3. 从现有的 `AudioSourceSelector` 迁移代码
4. 调整布局以适配卡片样式
5. 保持现有的信号/槽接口不变
6. 添加图标美化单选按钮

**验证**:
- 三种音频源模式(麦克风/系统音频/文件)正常工作
- 文件选择功能正常
- `source_changed` 信号正确发出

**依赖**: Task 1.1

**预计时长**: 4小时

---

### Task 1.3: 实现TranscriptionControlCard
**描述**: 基于BaseCard实现转录控制卡片。

**实现步骤**:
1. 创建 `src/gui/widgets/transcription_control_card.py`
2. 继承 `BaseCard`
3. 从现有的 `TranscriptionControlPanel` 迁移代码
4. 调整按钮布局为水平排列
5. 简化状态显示(只保留状态和时长)
6. 应用主按钮样式(绿色)

**验证**:
- 开始/暂停/停止按钮正常工作
- 状态和时长正确显示和更新
- 按钮状态根据转录状态正确切换

**依赖**: Task 1.1

**预计时长**: 4小时

---

### Task 1.4: 实现ResultDisplayCard
**描述**: 基于BaseCard实现结果显示卡片。

**实现步骤**:
1. 创建 `src/gui/widgets/result_display_card.py`
2. 继承 `BaseCard`
3. 从现有的 `TranscriptionResultDisplay` 迁移代码
4. 在标题栏添加"清空"和"复制全部"按钮
5. 优化文本显示样式

**验证**:
- 转录结果正确追加显示
- 清空功能正常
- 复制全部功能正常
- 自动滚动到底部

**依赖**: Task 1.1

**预计时长**: 3小时

---

## Phase 2: 高级设置卡片和折叠功能

### Task 2.1: 实现CollapsibleCard基类
**描述**: 创建可折叠卡片基类,支持展开/收起动画。

**实现步骤**:
1. 创建 `src/gui/widgets/collapsible_card.py`
2. 继承 `BaseCard`
3. 实现折叠/展开逻辑
4. 实现 `QPropertyAnimation` 动画
5. 添加展开/收起按钮(▼/▲)
6. 提供 `set_expanded()` 和 `is_expanded()` 方法

**验证**:
- 折叠/展开动画平滑(300ms)
- 点击标题栏或按钮都能触发
- 折叠状态下内容隐藏

**依赖**: Task 1.1

**预计时长**: 5小时

---

### Task 2.2: 实现AdvancedSettingsCard
**描述**: 基于CollapsibleCard实现高级设置卡片。

**实现步骤**:
1. 创建 `src/gui/widgets/advanced_settings_card.py`
2. 继承 `CollapsibleCard`
3. 整合VAD方案选择器
4. 整合模型信息显示
5. 整合GPU状态显示
6. 整合音频电平显示
7. 默认折叠状态

**验证**:
- VAD方案切换正常
- VAD设置按钮打开设置对话框
- GPU状态正确显示
- 音频电平实时更新(30fps)
- 工具提示正确显示

**依赖**: Task 2.1

**预计时长**: 6小时

---

## Phase 3: 主窗口布局重构

### Task 3.1: 创建TopControlBar组件
**描述**: 创建顶部控制栏,组织AudioSourceCard和TranscriptionControlCard。

**实现步骤**:
1. 创建 `src/gui/widgets/top_control_bar.py`
2. 使用 `QHBoxLayout` 水平布局
3. 添加 AudioSourceCard 和 TranscriptionControlCard
4. 设置拉伸比例(40% / 60%)
5. 实现响应式布局(宽度 < 800px 时改为垂直)

**验证**:
- 两个卡片正确排列
- 窗口缩放时布局自动调整

**依赖**: Task 1.2, Task 1.3

**预计时长**: 3小时

---

### Task 3.2: 重构MainWindow布局
**描述**: 修改MainWindow使用新的卡片组件。

**实现步骤**:
1. 修改 `src/gui/main_window.py`
2. 移除旧的左右分割布局
3. 使用 `QVBoxLayout` 垂直布局
4. 添加 TopControlBar
5. 添加 ResultDisplayCard
6. 添加 AdvancedSettingsCard
7. 设置拉伸因子
8. 更新信号/槽连接

**验证**:
- 主界面使用新布局
- 所有功能正常工作(音频源选择、转录控制、结果显示)
- 旧组件的信号/槽兼容

**依赖**: Task 3.1, Task 1.4, Task 2.2

**预计时长**: 4小时

---

### Task 3.3: 设置最小窗口尺寸
**描述**: 设置主窗口的最小尺寸和默认尺寸。

**实现步骤**:
1. 在 `MainWindow.__init__()` 中设置:
   - `setMinimumSize(800, 600)`
   - `setGeometry(100, 100, 1000, 700)`
2. 测试不同屏幕尺寸下的显示效果

**验证**:
- 窗口无法缩小到800x600以下
- 默认尺寸为1000x700
- 所有元素在最小尺寸下可见

**依赖**: Task 3.2

**预计时长**: 1小时

---

## Phase 4: 样式和视觉美化

### Task 4.1: 创建QSS样式表
**描述**: 创建统一的QSS样式表文件。

**实现步骤**:
1. 创建 `src/gui/styles/main_style.qss`
2. 定义卡片样式(.card)
3. 定义按钮样式(.primary-button, .secondary-button)
4. 定义字体和间距规范
5. 定义颜色变量(如果支持)

**验证**:
- 样式表正确应用到所有组件
- 卡片显示圆角、阴影
- 按钮显示正确的颜色和悬停效果

**依赖**: Task 3.2

**预计时长**: 4小时

---

### Task 4.2: 应用样式表到MainWindow
**描述**: 在MainWindow中加载和应用样式表。

**实现步骤**:
1. 在 `MainWindow.__init__()` 中加载样式表
2. 使用 `self.setStyleSheet()` 应用
3. 为组件添加对象名称(setObjectName)以匹配样式
4. 测试样式表热重载(开发时)

**验证**:
- 界面应用了统一的样式
- 所有卡片和按钮显示正确
- 样式与设计稿一致

**依赖**: Task 4.1

**预计时长**: 2小时

---

### Task 4.3: 添加图标和表情符号
**描述**: 为卡片标题和状态指示器添加图标。

**实现步骤**:
1. 使用Emoji图标:
   - 🎤 音频源
   - ▶️ 转录控制
   - 📊 实时转录结果
   - ⚙️ 高级设置
2. 或者使用Qt图标资源(QIcon)
3. 调整图标大小和对齐

**验证**:
- 图标正确显示
- 图标大小适中
- 图标与文字对齐

**依赖**: Task 4.2

**预计时长**: 2小时

---

## Phase 5: 工具提示和辅助功能

### Task 5.1: 添加工具提示
**描述**: 为所有图标按钮和状态指示器添加工具提示。

**实现步骤**:
1. 为VAD设置按钮设置: `setToolTip("打开VAD设置")`
2. 为GPU状态设置: `setToolTip("GPU已启用...")`
3. 为音频电平设置: `setToolTip("当前音频输入电平...")`
4. 设置工具提示延迟: 500ms

**验证**:
- 悬停显示正确的工具提示
- 工具提示内容准确

**依赖**: Task 2.2

**预计时长**: 1小时

---

### Task 5.2: 实现键盘导航
**描述**: 确保所有交互元素支持键盘导航。

**实现步骤**:
1. 设置Tab顺序: `setTabOrder()`
2. 为按钮添加焦点指示样式
3. 测试Tab键导航流程

**验证**:
- Tab键按正确顺序移动焦点
- 焦点有明显的视觉指示

**依赖**: Task 3.2

**预计时长**: 2小时

---

### Task 5.3: 添加键盘快捷键
**描述**: 为主要操作添加键盘快捷键。

**实现步骤**:
1. 在MainWindow中添加QShortcut:
   - Ctrl+S: 开始转录
   - Ctrl+P: 暂停转录
   - Ctrl+T: 停止转录
   - Ctrl+L: 清空结果
2. 连接到相应的槽函数

**验证**:
- 快捷键正确触发对应操作
- 快捷键在工具提示中显示

**依赖**: Task 3.2

**预计时长**: 2小时

---

## Phase 6: 状态保持和配置

### Task 6.1: 保存折叠状态到配置
**描述**: 将高级设置卡片的折叠状态保存到配置文件。

**实现步骤**:
1. 在Config中添加字段: `ui.advanced_settings_expanded: bool`
2. 在MainWindow关闭时保存状态
3. 在MainWindow启动时恢复状态

**验证**:
- 关闭应用后重启,折叠状态恢复

**依赖**: Task 2.2

**预计时长**: 2小时

---

### Task 6.2: (可选)添加回退开关
**描述**: 添加配置开关支持回退到旧界面(用于紧急情况)。

**实现步骤**:
1. 在Config中添加: `ui.use_legacy_layout: bool`
2. 在MainWindow中检查此标志
3. 根据标志选择新/旧布局

**验证**:
- 设置`use_legacy_layout=true`后显示旧界面
- 设置`use_legacy_layout=false`后显示新界面

**依赖**: Task 3.2

**预计时长**: 3小时

---

## Phase 7: 测试和文档

### Task 7.1: 编写单元测试
**描述**: 为新组件编写全面的单元测试。

**实现步骤**:
1. 测试各Card组件的独立功能
2. 测试折叠/展开逻辑
3. 测试信号发射
4. 确保测试覆盖率 >= 80%

**文件**:
- `tests/gui/widgets/test_base_card.py`
- `tests/gui/widgets/test_audio_source_card.py`
- `tests/gui/widgets/test_transcription_control_card.py`
- `tests/gui/widgets/test_result_display_card.py`
- `tests/gui/widgets/test_advanced_settings_card.py`
- `tests/gui/widgets/test_collapsible_card.py`

**验证**:
- 所有测试通过
- 覆盖率报告 >= 80%

**依赖**: Phase 1-6 所有任务

**预计时长**: 8小时

---

### Task 7.2: 集成测试
**描述**: 测试完整的用户交互流程。

**实现步骤**:
1. 测试场景:
   - 选择音频源 → 开始转录 → 显示结果 → 停止转录
   - 切换VAD方案 → 验证生效
   - 折叠/展开高级设置 → 验证状态保持
2. 在不同屏幕尺寸下测试
3. 测试键盘导航和快捷键

**验证**:
- 所有交互流程正常工作
- 无明显性能问题
- 界面响应流畅

**依赖**: Task 7.1

**预计时长**: 4小时

---

### Task 7.3: 性能测试
**描述**: 测试界面渲染性能和响应速度。

**实现步骤**:
1. 测量界面加载时间
2. 测量动画帧率
3. 测量音频电平更新延迟
4. 使用性能分析工具(如cProfile)

**验证**:
- 界面加载时间 < 500ms
- 动画帧率 >= 30fps
- 音频电平更新延迟 < 50ms

**依赖**: Task 7.2

**预计时长**: 3小时

---

### Task 7.4: 更新文档
**描述**: 更新项目文档以反映新界面。

**实现步骤**:
1. 更新 `CLAUDE.md` 中的GUI模块描述
2. 更新 `src/gui/CLAUDE.md`
3. 添加新组件的文档字符串
4. (可选)创建用户指南截图

**验证**:
- 文档准确描述新界面
- 所有新组件有完整的docstring

**依赖**: Task 7.3

**预计时长**: 3小时

---

### Task 7.5: 代码审查和清理
**描述**: 进行代码审查,移除旧代码,清理临时注释。

**实现步骤**:
1. 标记旧组件为deprecated
2. 移除未使用的导入和代码
3. 统一代码风格(black格式化)
4. 进行代码审查

**验证**:
- 代码符合项目编码规范
- 无未使用的代码
- 代码审查通过

**依赖**: Task 7.4

**预计时长**: 4小时

---

## Summary

**总任务数**: 25个
**预计总时长**: 约80小时 (10个工作日)

**关键里程碑**:
- Phase 1 完成: 基础卡片组件可用
- Phase 3 完成: 新界面可运行(功能完整)
- Phase 4 完成: 界面美化完成
- Phase 7 完成: 测试和文档齐全,准备发布

**并行开发**:
- Phase 1 中的 Task 1.2, 1.3, 1.4 可以并行开发
- Phase 4 和 Phase 5 可以部分并行
- Phase 7 的测试可以在每个Phase完成后逐步进行

**风险和缓解**:
- **风险**: 样式表兼容性问题
  - **缓解**: 提前在多个平台测试
- **风险**: 动画性能问题
  - **缓解**: 提供禁用动画选项
- **风险**: 用户适应新界面时间长
  - **缓解**: 提供回退开关,渐进式发布
