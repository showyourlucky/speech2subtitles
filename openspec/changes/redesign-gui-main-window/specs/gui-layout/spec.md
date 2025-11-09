# Spec: gui-layout

## Overview

本规范定义了Speech2Subtitles GUI主界面的布局结构、组件行为和视觉样式。目标是提供现代化、易用、美观的用户界面,解决当前界面元素过多、层次不清晰、屏幕适配差的问题。

## ADDED Requirements

### Requirement: 卡片式布局系统
主界面SHALL采用卡片式布局,将不同功能区域封装在独立的卡片组件中。

#### Scenario: 显示主界面时
**Given** 用户启动应用程序
**When** 主窗口加载完成
**Then** 界面显示以下卡片:
- 音频源卡片(AudioSourceCard)
- 转录控制卡片(TranscriptionControlCard)
- 结果显示卡片(ResultDisplayCard)
- 高级设置卡片(AdvancedSettingsCard)

**And** 每个卡片具有:
- 白色背景(#FFFFFF)
- 1px灰色边框(#E0E0E0)
- 8px圆角
- 16px内边距
- 适当的外边距和阴影效果

#### Scenario: 卡片悬停效果
**Given** 主界面已显示
**When** 鼠标悬停在卡片上
**Then** 卡片边框颜色变为深灰色(#B0B0B0)
**And** 提供视觉反馈

---

### Requirement: 顶部控制栏
顶部SHALL包含音频源选择和转录控制两个并排的卡片,作为主要操作区域。

#### Scenario: 顶部控制栏布局
**Given** 主窗口宽度 >= 800px
**When** 主界面加载
**Then** 顶部控制栏包含:
- 左侧: AudioSourceCard (占比 40%)
- 右侧: TranscriptionControlCard (占比 60%)

**And** 两个卡片水平排列
**And** 总高度固定在150px左右

#### Scenario: 窄屏幕适配
**Given** 主窗口宽度 < 800px
**When** 主界面加载
**Then** 顶部控制栏改为垂直布局
**And** AudioSourceCard在上
**And** TranscriptionControlCard在下

---

### Requirement: 音频源卡片
AudioSourceCard SHALL提供音频源选择功能,支持麦克风、系统音频和文件三种模式。

#### Scenario: 显示音频源选项
**Given** AudioSourceCard已渲染
**When** 卡片显示
**Then** 显示以下元素:
- 卡片标题: "🎤 音频源"
- 单选按钮组:
  - ● 麦克风
  - ○ 系统音频
  - ○ 音频/视频文件

**And** 当前选中的音频源单选按钮被选中

#### Scenario: 切换到文件模式
**Given** 当前选中"麦克风"
**When** 用户点击"音频/视频文件"单选按钮
**Then** 显示文件选择区域
**And** 包含:
- "选择文件..."按钮
- "全选"按钮
- "移除选中"按钮
- "清空全部"按钮
- 文件列表显示区域

**And** 发出`source_changed(AudioSourceInfo)`信号

#### Scenario: 选择音频文件
**Given** 当前选中"音频/视频文件"模式
**When** 用户点击"选择文件..."按钮
**Then** 打开文件选择对话框
**And** 过滤器为: "音频文件 (*.mp3 *.wav *.flac *.m4a);;视频文件 (*.mp4 *.avi *.mkv *.mov);;所有文件 (*.*)"
**When** 用户选择一个或多个文件
**Then** 文件路径添加到文件列表
**And** 发出`source_changed`信号

---

### Requirement: 转录控制卡片
TranscriptionControlCard SHALL提供转录的开始、暂停、停止控制,以及状态和时长显示。

#### Scenario: 显示转录控制
**Given** TranscriptionControlCard已渲染
**When** 卡片显示且未转录
**Then** 显示以下元素:
- 卡片标题: "▶️ 转录控制"
- 按钮组(水平排列):
  - [开始转录] (绿色主按钮)
  - [暂停] (灰色禁用)
  - [停止] (灰色禁用)
- 状态行: "状态: 🔵 就绪  |  时长: 00:00:00"

#### Scenario: 点击开始转录
**Given** 转录处于停止状态
**And** 音频源已选择
**When** 用户点击"开始转录"按钮
**Then** 发出`start_requested()`信号
**And** 按钮状态更新为:
  - [开始转录] (禁用)
  - [暂停] (启用)
  - [停止] (启用,红色)
**And** 状态显示: "状态: ✅ 运行中  |  时长: 00:00:01" (持续计时)

#### Scenario: 点击停止转录
**Given** 转录正在运行
**When** 用户点击"停止"按钮
**Then** 发出`stop_requested()`信号
**And** 按钮状态恢复到初始状态
**And** 状态显示: "状态: 🔵 已停止  |  时长: 00:00:00"

#### Scenario: 转录时长计时
**Given** 转录正在运行
**When** 每秒更新一次
**Then** 时长显示递增: "00:00:01" → "00:00:02" → ...
**And** 格式为: HH:MM:SS

---

### Requirement: 结果显示卡片
ResultDisplayCard SHALL显示实时转录结果,支持清空和复制操作。

#### Scenario: 显示转录结果
**Given** ResultDisplayCard已渲染
**When** 卡片显示
**Then** 显示以下元素:
- 卡片标题: "📊 实时转录结果"
- 操作按钮(右上角):
  - [清空] 按钮
  - [复制全部] 按钮
- 文本显示区域(可滚动)

**And** 文本显示区域占据大部分垂直空间

#### Scenario: 接收新转录结果
**Given** 转录正在运行
**When** 收到新的TranscriptionResult
**Then** 转录文本追加到显示区域底部
**And** 格式为: `[HH:MM:SS] 转录文本`
**And** 自动滚动到底部(如果用户未手动滚动)

#### Scenario: 清空转录结果
**Given** 转录结果显示区域有内容
**When** 用户点击"清空"按钮
**Then** 文本显示区域清空
**And** 显示占位提示: "转录结果将显示在这里..."

#### Scenario: 复制全部内容
**Given** 转录结果显示区域有内容
**When** 用户点击"复制全部"按钮
**Then** 所有转录文本复制到系统剪贴板
**And** 显示提示消息: "已复制全部内容"

---

### Requirement: 高级设置卡片(可折叠)
AdvancedSettingsCard SHALL显示VAD方案、模型信息、GPU状态和音频电平,支持折叠/展开。

#### Scenario: 默认折叠状态
**Given** 主界面首次加载
**When** AdvancedSettingsCard显示
**Then** 卡片处于折叠状态
**And** 只显示:
- 标题栏: "⚙️ 高级设置"
- 展开/收起按钮: [▼]

**And** 卡片高度: 40px

#### Scenario: 展开高级设置
**Given** 高级设置卡片处于折叠状态
**When** 用户点击展开按钮或标题栏
**Then** 卡片平滑展开(动画300ms)
**And** 显示内容:
- VAD方案: [下拉框] [⚙️ 设置按钮]
- 模型: model.onnx
- GPU: ✅ 已启用 (CUDA)
- 音频电平: [进度条] 70%

**And** 展开按钮变为: [▲]
**And** 卡片高度: ~200px

#### Scenario: 收起高级设置
**Given** 高级设置卡片处于展开状态
**When** 用户点击收起按钮或标题栏
**Then** 卡片平滑收起(动画300ms)
**And** 恢复到折叠状态

#### Scenario: 切换VAD方案
**Given** 高级设置卡片处于展开状态
**When** 用户在VAD方案下拉框中选择新方案
**Then** 发出`vad_profile_changed(profile_id)`信号
**And** 显示提示: "已切换到VAD方案: [方案名]"

**When** 转录正在运行
**Then** 额外显示警告: "VAD方案已切换,将在下次启动转录时生效。"

#### Scenario: 打开VAD设置
**Given** 高级设置卡片处于展开状态
**When** 用户点击VAD方案旁的[⚙️]按钮
**Then** 打开设置对话框
**And** 直接跳转到VAD设置页面(标签索引2)

#### Scenario: 更新音频电平
**Given** 转录正在运行
**When** 每隔33ms(~30fps)更新一次音频电平
**Then** 音频电平进度条更新
**And** 显示数值: 0-100%
**And** 颜色根据电平变化:
  - 0-30%: 绿色
  - 30-70%: 黄色
  - 70-100%: 红色

---

### Requirement: 响应式布局
界面SHALL支持不同屏幕尺寸,自动调整布局。

#### Scenario: 最小窗口尺寸
**Given** 用户尝试调整窗口大小
**When** 窗口宽度 < 800px 或 高度 < 600px
**Then** 窗口尺寸限制为最小值 800x600
**And** 无法继续缩小

#### Scenario: 推荐窗口尺寸
**Given** 主窗口首次打开
**When** 窗口初始化
**Then** 窗口尺寸设置为 1000x700
**And** 所有元素完整显示

#### Scenario: 大屏幕适配
**Given** 主窗口宽度 >= 1200px
**When** 窗口渲染
**Then** 卡片自动扩展
**And** 文本和按钮保持合理大小(不会过大)
**And** 使用相对单位保持比例

---

### Requirement: 视觉样式
界面SHALL使用统一的现代化视觉样式,包括颜色、字体、间距。

#### Scenario: 主色调
**Given** 界面渲染
**When** 显示任何UI元素
**Then** 使用以下颜色方案:
- 主色(Primary): #4CAF50 (开始按钮)
- 辅色(Secondary): #2196F3 (信息展示)
- 警告色(Warning): #FF9800 (暂停状态)
- 错误色(Error): #F44336 (错误状态)
- 中性色(Neutral): #F5F5F5 (背景), #E0E0E0 (边框)

#### Scenario: 按钮样式
**Given** 界面包含按钮
**When** 按钮渲染
**Then** 应用以下样式:
- 主按钮: 绿色背景, 白色文字, 4px圆角, 10px上下内边距
- 次要按钮: 灰色背景, 深色文字, 1px边框
- 悬停效果: 颜色加深10%

#### Scenario: 字体和间距
**Given** 界面包含文本
**When** 文本渲染
**Then** 使用以下规范:
- 卡片标题: 14pt, 粗体
- 正文: 10pt, 常规
- 按钮文字: 12pt, 常规
- 行间距: 1.5倍
- 卡片内边距: 16px
- 卡片外边距: 8px

---

### Requirement: 交互动画
界面SHALL提供平滑的动画效果提升用户体验。

#### Scenario: 折叠展开动画
**Given** 高级设置卡片准备折叠或展开
**When** 用户触发操作
**Then** 使用QPropertyAnimation
**And** 动画时长: 300ms
**And** 缓动函数: InOutCubic (先加速后减速)
**And** 动画属性: maximumHeight

#### Scenario: 按钮点击反馈
**Given** 用户点击按钮
**When** 鼠标按下
**Then** 按钮轻微缩小(0.95倍)
**When** 鼠标释放
**Then** 按钮恢复原始大小
**And** 整个过程 < 100ms

---

### Requirement: 工具提示
系统SHALL为图标按钮和简化的状态指示器提供工具提示。

#### Scenario: VAD设置按钮工具提示
**Given** 鼠标悬停在VAD设置按钮[⚙️]上
**When** 悬停持续 > 500ms
**Then** 显示工具提示: "打开VAD设置"

#### Scenario: GPU状态工具提示
**Given** 鼠标悬停在GPU状态图标上
**When** GPU启用
**Then** 显示工具提示: "GPU已启用,使用CUDA加速"
**When** GPU禁用
**Then** 显示工具提示: "GPU未启用,使用CPU模式"

#### Scenario: 音频电平工具提示
**Given** 鼠标悬停在音频电平进度条上
**When** 转录运行中
**Then** 显示工具提示: "当前音频输入电平: [数值]%"

---

### Requirement: 状态保持
界面状态如折叠/展开 SHALL在重启应用时保持。

#### Scenario: 保存折叠状态
**Given** 用户展开了高级设置卡片
**When** 应用关闭
**Then** 折叠/展开状态保存到配置文件
**And** 配置键: `ui.advanced_settings_expanded`

#### Scenario: 恢复折叠状态
**Given** 上次关闭时高级设置卡片处于展开状态
**When** 应用重新启动
**Then** 高级设置卡片自动展开
**And** 显示上次的状态

---

### Requirement: 辅助功能
系统SHALL支持键盘导航和屏幕阅读器。

#### Scenario: 键盘导航
**Given** 主界面已加载
**When** 用户按Tab键
**Then** 焦点按顺序移动:
  1. 音频源单选按钮
  2. 文件选择按钮(如果可见)
  3. 开始转录按钮
  4. 暂停按钮
  5. 停止按钮
  6. VAD方案下拉框
  7. VAD设置按钮

**And** 焦点有明显的视觉指示(蓝色边框)

#### Scenario: 键盘快捷键
**Given** 主界面已加载
**When** 用户按以下快捷键
**Then** 执行对应操作:
- `Ctrl+S`: 开始转录
- `Ctrl+P`: 暂停转录
- `Ctrl+T`: 停止转录
- `Ctrl+L`: 清空结果
- `Ctrl+C`: 复制全部(焦点在结果区域时)

---

## MODIFIED Requirements

_无修改的需求_

---

## REMOVED Requirements

_无移除的需求_

---

## Non-Functional Requirements

### 性能
- 界面渲染时间 < 500ms
- 动画帧率 >= 30fps
- 音频电平更新延迟 < 50ms

### 兼容性
- 支持PySide6 6.0+
- 支持Windows 10+, macOS 10.15+, Linux (主流发行版)
- 支持屏幕分辨率: 800x600 至 4K

### 可维护性
- 所有组件独立封装
- 样式使用QSS统一管理
- 遵循单一职责原则

### 可访问性
- 符合WCAG 2.1 AA级标准
- 支持键盘导航
- 支持屏幕阅读器(初步)
- 最小字体: 10pt
- 最小点击区域: 32x32px
