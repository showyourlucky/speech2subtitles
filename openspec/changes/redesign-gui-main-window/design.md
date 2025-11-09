# Design: redesign-gui-main-window

## Architecture

### 组件层次结构

```
MainWindow
├── MenuBar (保持不变)
├── CentralWidget
│   └── MainLayout (QVBoxLayout)
│       ├── TopControlBar (新增)
│       │   ├── AudioSourceCard (重构)
│       │   └── TranscriptionControlCard (重构)
│       ├── ResultDisplayCard (重构)
│       └── AdvancedSettingsCard (新增,可折叠)
└── StatusBar (保持不变)
```

### 核心组件设计

#### 1. TopControlBar (顶部控制栏)
水平布局,包含音频源选择和转录控制两个卡片。

**职责**:
- 组织顶部的主要控制区域
- 提供横向布局管理

**实现**:
```python
class TopControlBar(QWidget):
    """顶部控制栏,包含音频源和转录控制"""
    def __init__(self):
        # QHBoxLayout横向布局
        # 添加AudioSourceCard和TranscriptionControlCard
```

#### 2. AudioSourceCard (音频源卡片)
卡片式设计,包含音频源选择的所有控件。

**职责**:
- 显示和切换音频源(麦克风/系统音频/文件)
- 提供文件选择功能(文件模式)
- 发出音频源变更信号

**变更**:
- 从原来的`AudioSourceSelector`重构而来
- 添加卡片样式(边框、圆角、阴影)
- 使用图标美化单选按钮

#### 3. TranscriptionControlCard (转录控制卡片)
卡片式设计,包含转录控制按钮和基本状态信息。

**职责**:
- 提供开始/暂停/停止按钮
- 显示当前状态和时长
- 发出控制信号

**变更**:
- 从原来的`TranscriptionControlPanel`重构而来
- 添加卡片样式
- 简化状态显示(只保留关键信息)
- 优化按钮布局(水平排列)

#### 4. ResultDisplayCard (结果显示卡片)
卡片式设计,显示转录结果。

**职责**:
- 显示实时转录文本
- 提供清空和复制功能
- 支持滚动显示

**变更**:
- 从原来的`TranscriptionResultDisplay`重构而来
- 添加卡片样式
- 在卡片头部添加标题和操作按钮

#### 5. AdvancedSettingsCard (高级设置卡片)
可折叠的卡片,包含VAD方案、模型信息、GPU状态等。

**职责**:
- 显示高级配置信息
- 提供VAD方案切换
- 显示系统状态(GPU、音频电平)
- 支持展开/折叠

**变更**:
- 整合原来的`StatusMonitorPanel`和VAD选择器
- 添加折叠/展开功能
- 默认折叠状态,减少初始视觉负担

### 布局策略

#### 主布局 (MainLayout)
使用`QVBoxLayout`垂直布局:

```
┌─────────────────────────────────────┐
│  TopControlBar (固定高度 ~150px)    │
├─────────────────────────────────────┤
│                                      │
│  ResultDisplayCard (弹性拉伸)       │
│                                      │
├─────────────────────────────────────┤
│  AdvancedSettingsCard (折叠: 40px)  │
│                         (展开: ~200px)│
└─────────────────────────────────────┘
```

**拉伸因子**:
- TopControlBar: 0 (固定高度)
- ResultDisplayCard: 1 (占据剩余空间)
- AdvancedSettingsCard: 0 (固定高度)

#### 响应式设计
1. **最小窗口尺寸**: 800x600
2. **推荐窗口尺寸**: 1000x700
3. **自适应策略**:
   - 小于800px宽度时,TopControlBar改为垂直堆叠
   - 卡片内部使用相对单位(em),自动缩放

### 样式设计

#### 卡片样式 (QSS)
```css
.card {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    padding: 16px;
    margin: 8px;
}

.card:hover {
    border-color: #B0B0B0;
}

.card-title {
    font-size: 14pt;
    font-weight: bold;
    color: #333333;
    margin-bottom: 12px;
}
```

#### 按钮样式
```css
.primary-button {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 10px 24px;
    font-size: 12pt;
}

.primary-button:hover {
    background-color: #45A049;
}

.secondary-button {
    background-color: #F5F5F5;
    color: #333333;
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    padding: 10px 24px;
}
```

#### 颜色方案
- **主色**: #4CAF50 (绿色 - 转录开始按钮)
- **辅色**: #2196F3 (蓝色 - 信息展示)
- **警告色**: #FF9800 (橙色 - 暂停状态)
- **错误色**: #F44336 (红色 - 错误状态)
- **中性色**: #F5F5F5 (背景), #E0E0E0 (边框)

### 交互设计

#### 折叠/展开动画
使用`QPropertyAnimation`实现平滑过渡:

```python
self.animation = QPropertyAnimation(self.content_widget, b"maximumHeight")
self.animation.setDuration(300)  # 300ms
self.animation.setEasingCurve(QEasingCurve.InOutCubic)
```

#### 状态指示
- **就绪**: 灰色圆点 + "就绪"文字
- **运行中**: 绿色圆点 + "运行中"文字 + 时长计时器
- **暂停**: 橙色圆点 + "已暂停"文字
- **错误**: 红色圆点 + "错误"文字

#### 工具提示
为所有图标按钮和简化的状态指示器添加工具提示:
- VAD设置按钮: "打开VAD设置"
- GPU状态: "GPU已启用,使用CUDA加速"
- 音频电平: "当前音频输入电平"

## Data Flow

### 信号流
```
User Action → Widget Signal → MainWindow Slot → Pipeline/Config
                                    ↓
                            Update UI State
```

### 关键信号
保持现有的信号/槽机制不变:
- `source_changed(AudioSourceInfo)` - 音频源变更
- `start_requested()` - 开始转录
- `pause_requested()` - 暂停转录
- `stop_requested()` - 停止转录
- `new_result(TranscriptionResult)` - 新转录结果
- `status_changed(str, str)` - 状态变更
- `error_occurred(str, str)` - 错误发生

## Component Interfaces

### AudioSourceCard

**公共方法**:
```python
def get_selected_source() -> Optional[AudioSourceInfo]
def get_file_paths() -> List[str]
def set_enabled(enabled: bool) -> None
```

**信号**:
```python
source_changed = Signal(object)  # AudioSourceInfo
```

### TranscriptionControlCard

**公共方法**:
```python
def set_state(state: TranscriptionState) -> None
def get_elapsed_time() -> float
```

**信号**:
```python
start_requested = Signal()
pause_requested = Signal()
stop_requested = Signal()
```

### ResultDisplayCard

**公共方法**:
```python
def append_result(result: TranscriptionResult) -> None
def get_full_text() -> str
def clear() -> None
```

**信号**:
```python
# 无新增信号
```

### AdvancedSettingsCard

**公共方法**:
```python
def update_vad_profile(profile_id: str) -> None
def update_model(model_name: str) -> None
def update_gpu_status(enabled: bool, info: str = "") -> None
def update_audio_level(level: float) -> None
def set_expanded(expanded: bool) -> None
def is_expanded() -> bool
```

**信号**:
```python
vad_profile_changed = Signal(str)  # profile_id
vad_settings_clicked = Signal()
```

## Performance Considerations

1. **样式表缓存**: QSS样式表在应用启动时一次性加载,避免重复解析
2. **延迟渲染**: AdvancedSettingsCard在折叠状态下不渲染内部细节
3. **防抖动**: 音频电平更新使用防抖动,限制更新频率(最多30fps)
4. **避免重排**: 使用固定高度或最小高度,避免频繁布局重排

## Error Handling

1. **组件加载失败**: 显示占位符和错误提示
2. **样式加载失败**: 回退到默认Qt样式
3. **动画性能问题**: 自动禁用动画(检测到低性能设备)

## Security Considerations

无特殊安全考虑(纯UI变更)。

## Migration Strategy

### 兼容性保证
- 保持所有公共API不变
- 信号/槽接口保持不变
- 配置系统保持不变

### 渐进式迁移
1. **阶段1**: 实现新组件,与旧组件并存
2. **阶段2**: 在MainWindow中切换到新组件
3. **阶段3**: 移除旧组件代码(标记为deprecated)

### 回退方案
如果新界面出现严重问题,可以通过配置开关回退到旧界面:
```python
# config.yaml
ui:
  use_legacy_layout: false  # true=使用旧界面
```

## Testing Strategy

### 单元测试
- 测试各个Card组件的独立功能
- 测试折叠/展开逻辑
- 测试信号发射

### 集成测试
- 测试MainWindow与各Card的集成
- 测试完整的交互流程(选择音频源→开始转录→显示结果)

### 视觉测试
- 截图对比测试(不同状态、不同尺寸)
- 手动验证样式和动画效果

### 性能测试
- 测量界面渲染时间
- 测量动画帧率
- 测量内存占用

## Future Enhancements

1. **主题系统**: 支持深色/浅色主题切换
2. **布局配置**: 允许用户自定义布局和卡片位置
3. **插件化卡片**: 支持第三方扩展添加自定义卡片
4. **快捷键**: 为所有主要操作添加键盘快捷键
5. **辅助功能**: 增强屏幕阅读器支持和高对比度模式
