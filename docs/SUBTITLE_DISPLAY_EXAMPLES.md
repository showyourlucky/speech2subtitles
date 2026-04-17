# 屏幕字幕显示功能使用示例

## 基本使用示例

### 1. 最简单的使用方式

```bash
# 启用基本的字幕显示
python main.py --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx --input-source microphone --show-subtitles
```

这将使用默认设置显示字幕：
- 位置：屏幕底部
- 字体大小：24px
- 透明度：0.8
- 字体：Microsoft YaHei
- 显示时间：5秒

### 2. 麦克风输入 + 大字体

```bash
# 适合演示或教学场景的大字体字幕
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-font-size 36 \
  --subtitle-position center \
  --subtitle-opacity 0.9
```

### 3. 系统音频 + 顶部字幕

```bash
# 捕获系统音频并显示在屏幕顶部
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source system \
  --show-subtitles \
  --subtitle-position top \
  --subtitle-font-size 20 \
  --no-gpu
```

## 自定义样式示例

### 4. 深色主题

```bash
# 使用深色背景和亮色文字
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-text-color "#00FF00" \
  --subtitle-bg-color "#1a1a1a" \
  --subtitle-opacity 0.95
```

### 5. 高对比度主题

```bash
# 黑底白字的高对比度显示
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-text-color "#FFFFFF" \
  --subtitle-bg-color "#000000" \
  --subtitle-font-size 28
```

### 6. 轻盈透明主题

```bash
# 半透明背景，适合观看视频
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-opacity 0.6 \
  --subtitle-text-color "#FFFF00" \
  --subtitle-bg-color "#000000"
```

## 性能优化示例

### 7. 快速更新模式

```bash
# 适用于快节奏内容，较短显示时间
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-max-display-time 2.0 \
  --subtitle-font-size 22
```

### 8. 稳定模式

```bash
# 较长显示时间，减少更新频率
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-max-display-time 8.0 \
  --subtitle-font-size 24
```

## 多语言场景示例

### 9. 中英文混合会议

```bash
# 适合中英文混合的会议场景
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-font-size 26 \
  --subtitle-font-family "Microsoft YaHei" \
  --subtitle-position bottom \
  --subtitle-max-display-time 4.0
```

### 10. 多语言支持

```bash
# 使用支持多语言的字体
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-font-family "Arial Unicode MS" \
  --subtitle-font-size 24 \
  --show-confidence
```

## 特殊场景示例

### 11. 演讲者模式

```bash
# 适合演讲者查看提示字幕
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-position top \
  --subtitle-font-size 32 \
  --subtitle-max-display-time 10.0 \
  --show-timestamp
```

### 12. 笔记模式

```bash
# 适合做笔记，较长时间显示
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-font-size 20 \
  --subtitle-max-display-time 15.0 \
  --show-confidence
```

## 完整配置示例

### 13. 生产环境配置

```bash
# 稳定可靠的生产环境配置
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-position bottom \
  --subtitle-font-size 24 \
  --subtitle-font-family "Microsoft YaHei" \
  --subtitle-opacity 0.85 \
  --subtitle-max-display-time 5.0 \
  --subtitle-text-color "#FFFFFF" \
  --subtitle-bg-color "#1a1a1a" \
  --vad-threshold 0.6 \
  --output-format text
```

### 14. 开发测试配置

```bash
# 开发和测试用的详细配置
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-position center \
  --subtitle-font-size 22 \
  --subtitle-opacity 0.7 \
  --subtitle-max-display-time 3.0 \
  --show-confidence \
  --show-timestamp \
  --verbose
```

## 故障排除示例

### 15. 兼容性模式

```bash
# 如果遇到问题，使用最简单的配置
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --subtitle-font-size 20 \
  --no-gpu
```

### 16. 调试模式

```bash
# 启用详细日志进行调试
python main.py \
  --model-path models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx \
  --input-source microphone \
  --show-subtitles \
  --verbose
```

## 使用技巧

### 字幕窗口操作
- **拖拽移动**: 点击字幕窗口可以拖拽到任意位置
- **自动清除**: 字幕会在指定时间后自动消失
- **置顶显示**: 字幕窗口始终保持在其他窗口之上

### 性能优化建议
- **字体大小**: 推荐使用20-30px，过大会影响性能
- **显示时间**: 根据语速调整，一般3-6秒比较合适
- **透明度**: 0.7-0.9效果最佳，过低可能影响性能

### 最佳实践
1. 首次使用建议用基本配置测试功能
2. 根据使用场景调整字体大小和位置
3. 如果字幕更新不及时，可以适当减少显示时间
4. 多语言场景建议使用Unicode兼容字体

## 常见问题解答

**Q: 为什么字幕没有显示？**
A: 确保添加了`--show-subtitles`参数，并且模型路径正确

**Q: 字幕显示乱码怎么办？**
A: 检查字体设置，确保使用了支持中文的字体如"Microsoft YaHei"

**Q: 如何调整字幕位置？**
A: 使用`--subtitle-position`参数，可选择top、center、bottom

**Q: 字幕影响性能怎么办？**
A: 尝试减小字体大小或使用`--no-gpu`参数

**Q: 可以同时使用字幕文件和屏幕字幕吗？**
A: 可以，但屏幕字幕只在`--input-source`模式下有效
