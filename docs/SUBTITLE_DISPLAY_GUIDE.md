# 屏幕字幕显示功能使用指南

## 概述

屏幕字幕显示功能为实时语音转录系统添加了可视化字幕支持，在屏幕上实时显示转录结果。该功能基于tkinter实现，提供轻量级、高性能的字幕显示窗口。

## 功能特性

- **实时字幕显示**: 在屏幕上实时显示语音转录结果
- **可配置样式**: 支持自定义字体大小、颜色、透明度等
- **多位置显示**: 支持顶部、居中、底部三种字幕位置
- **可拖拽窗口**: 字幕窗口支持鼠标拖拽移动
- **自动文本换行**: 长文本自动换行显示
- **时间控制**: 可配置字幕最大显示时间
- **低性能开销**: 优化的渲染机制，最小化对转录性能的影响

## 命令行参数

### 基本参数

- `--show-subtitles`: 启用屏幕字幕显示功能
- `--subtitle-position {top,center,bottom}`: 设置字幕位置（默认：bottom）
- `--subtitle-font-size INT`: 设置字体大小（默认：24）
- `--subtitle-font-family FONT`: 设置字体（默认：Microsoft YaHei）
- `--subtitle-opacity FLOAT`: 设置窗口透明度（0.1-1.0，默认：0.8）

### 高级参数

- `--subtitle-max-display-time FLOAT`: 设置字幕最大显示时间，单位秒（默认：5.0）
- `--subtitle-text-color COLOR`: 设置文字颜色（十六进制格式，默认：#FFFFFF）
- `--subtitle-bg-color COLOR`: 设置背景颜色（十六进制格式，默认：#000000）

## 使用示例

### 基本使用

```bash
# 启用基本字幕显示
python main.py --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx --input-source microphone --show-subtitles

# 系统音频输入 + 字幕显示
python main.py --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx --input-source system --show-subtitles --no-gpu
```

### 自定义样式

```bash
# 大字体，顶部显示
python main.py --model-path models/model.onnx --input-source microphone --show-subtitles --subtitle-font-size 32 --subtitle-position top

# 高透明度，居中显示
python main.py --model-path models/model.onnx --input-source microphone --show-subtitles --subtitle-opacity 0.6 --subtitle-position center

# 自定义颜色
python main.py --model-path models/model.onnx --input-source microphone --show-subtitles --subtitle-text-color "#FFFF00" --subtitle-bg-color "#000080"
```

### 完整配置示例

```bash
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-position bottom \
  --subtitle-font-size 28 \
  --subtitle-font-family "Microsoft YaHei" \
  --subtitle-opacity 0.85 \
  --subtitle-max-display-time 4.0 \
  --subtitle-text-color "#FFFFFF" \
  --subtitle-bg-color "#1a1a1a" \
  --no-gpu
```

## 配置说明

### 字幕位置

- `top`: 字幕显示在屏幕顶部，距离顶部50像素
- `center`: 字幕显示在屏幕中央
- `bottom`: 字幕显示在屏幕底部，距离底部50像素（默认）

### 字体配置

- **字体大小**: 支持12-72像素，推荐20-30像素
- **字体**: 支持系统安装的任何字体，中文字体推荐使用"Microsoft YaHei"
- **颜色**: 使用十六进制颜色代码，如#FFFFFF（白色）、#000000（黑色）

### 透明度

- **范围**: 0.1（几乎透明）到1.0（完全不透明）
- **推荐值**: 0.7-0.9，既能看清字幕又不会过度遮挡内容

### 显示时间

- **默认**: 5秒，适合一般语速
- **快速模式**: 2-3秒，适合快节奏内容
- **慢速模式**: 7-10秒，适合需要仔细阅读的内容

## 使用技巧

### 窗口操作

1. **拖拽移动**: 点击字幕窗口并拖拽可以移动位置
2. **置顶显示**: 字幕窗口始终保持在其他窗口之上
3. **自动隐藏**: 字幕在显示时间结束后自动清除

### 性能优化

1. **适当字体大小**: 过大的字体可能影响渲染性能
2. **合理透明度**: 极低透明度可能增加渲染开销
3. **显示时间**: 过短的显示时间会增加更新频率

### 兼容性

- **操作系统**: Windows、Linux、macOS
- **Python版本**: 3.7+
- **依赖**: tkinter（Python标准库）

## 故障排除

### 常见问题

**Q: 字幕窗口没有显示**
A: 确保`--show-subtitles`参数已添加，并且tkinter可用

**Q: 字幕显示乱码**
A: 检查字体设置，确保使用了支持中文的字体

**Q: 字幕窗口无法拖拽**
A: 尝试重启程序，确保没有其他程序占用鼠标事件

**Q: 性能影响明显**
A: 尝试减小字体大小或增加显示时间

### 错误处理

程序包含完善的错误处理机制：
- **配置验证**: 自动检查参数范围和有效性
- **异常恢复**: 字幕显示失败不会影响转录功能
- **资源清理**: 程序退出时自动清理字幕窗口

## 技术细节

### 实现架构

```
ConfigManager → SubtitleDisplayConfig → OutputHandler → SubtitleDisplay
```

1. **配置管理**: ConfigManager解析命令行参数
2. **配置传递**: SubtitleDisplayConfig封装显示配置
3. **集成处理**: OutputHandler集成字幕显示到转录流程
4. **窗口显示**: SubtitleDisplay管理tkinter窗口和渲染

### 性能特性

- **多线程安全**: 使用线程锁确保GUI操作安全
- **异步更新**: 通过after方法避免阻塞主线程
- **资源管理**: 自动清理定时器和事件处理器
- **内存优化**: 限制文本长度，避免内存泄漏

### 扩展接口

字幕显示组件提供以下扩展接口：
- `show_subtitle(text, confidence)`: 显示字幕
- `clear_subtitle()`: 清除字幕
- `update_config(new_config)`: 更新配置
- `get_window_position()`: 获取窗口位置

## 开发集成

### 在代码中使用

```python
from src.config.models import SubtitleDisplayConfig
from src.subtitle_display import SubtitleDisplay

# 创建配置
config = SubtitleDisplayConfig(
    enabled=True,
    position="bottom",
    font_size=24
)

# 创建和使用字幕显示
with SubtitleDisplay(config) as subtitle_display:
    subtitle_display.show_subtitle("Hello, World!", 0.95)
    time.sleep(3)
```

### 自定义样式

```python
# 深色主题
dark_theme = SubtitleDisplayConfig(
    enabled=True,
    font_size=26,
    text_color="#00ff00",
    background_color="#1a1a1a",
    opacity=0.9
)

# 浅色主题
light_theme = SubtitleDisplayConfig(
    enabled=True,
    font_size=24,
    text_color="#000000",
    background_color="#ffffcc",
    opacity=0.8
)
```

## 更新日志

### v1.0 (2025-10-29)
- 初始版本发布
- 基本字幕显示功能
- 可配置样式和位置
- 多线程安全设计
- 完整的错误处理

## 许可证

本功能遵循项目的整体许可证协议。

---

**提示**: 字幕显示功能需要配合`--input-source`参数使用，仅支持实时转录模式。