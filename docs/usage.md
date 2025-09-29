# 使用指南

本文档详细介绍如何使用实时语音转录系统进行各种场景的语音转录任务。

## 基本使用

### 启动系统

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 基本启动命令
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone
```

### 系统输出

程序启动后会显示以下信息：

```
════════════════════════════════════════════════════════════════
                  实时语音转录系统 v1.0
                Real-time Speech Transcription

  基于 sherpa-onnx + silero_vad + sense-voice
  支持麦克风和系统音频实时转录

  作者: AI Assistant
  项目: speech2subtitles
════════════════════════════════════════════════════════════════

✅ 依赖检查通过

系统信息:
  操作系统: Windows 11
  Python版本: 3.9.0
  CPU: Intel64 Family 6 Model 142 Stepping 12
  内存: 16 GB
  CUDA可用: 是
  GPU 0: NVIDIA GeForce GTX 1660 Ti (6144 MB)

使用说明:
  - 程序将开始实时音频捕获和转录
  - 转录结果将实时显示在控制台
  - 按 Ctrl+C 停止程序
```

## 命令行参数详解

### 必需参数

#### --model-path
指定sense-voice模型文件的路径。

```bash
# 使用ONNX格式模型
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone

# 使用BIN格式模型
python main.py --model-path models/sense-voice.bin --input-source microphone

# 使用绝对路径
python main.py --model-path "C:\models\sense-voice.onnx" --input-source microphone
```

#### --input-source
指定音频输入源。

```bash
# 麦克风输入
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone

# 系统音频输入
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source system
```

### 可选参数

#### --vad-sensitivity
控制语音活动检测的敏感度（0.0-1.0）。

```bash
# 高敏感度（适合安静环境）
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --vad-sensitivity 0.3

# 中等敏感度（推荐设置）
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --vad-sensitivity 0.5

# 低敏感度（适合嘈杂环境）
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --vad-sensitivity 0.8
```

#### GPU控制参数

```bash
# 强制启用GPU（默认自动检测）
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --use-gpu

# 强制使用CPU
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --no-gpu
```

#### --log-level
控制日志输出级别。

```bash
# 调试模式（详细输出）
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG

# 信息模式（默认）
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level INFO

# 警告模式（仅警告和错误）
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level WARNING

# 错误模式（仅错误）
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level ERROR
```

## 使用场景

### 场景1：会议记录

适用于会议、讲座等正式场合的语音记录。

```bash
# 推荐配置
python main.py \
    --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx \
    --input-source microphone \
    --vad-sensitivity 0.4 \
    --use-gpu \
    --log-level INFO
```

**特点：**
- 中等VAD敏感度，平衡准确性和响应性
- 启用GPU加速以获得更好性能
- 适中的日志级别，便于监控状态

### 场景2：直播字幕

适用于直播、在线会议等需要实时字幕的场景。

```bash
# 推荐配置
python main.py \
    --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx \
    --input-source system \
    --vad-sensitivity 0.6 \
    --use-gpu
```

**特点：**
- 使用系统音频输入，捕获播放内容
- 较低VAD敏感度，避免背景音乐干扰
- GPU加速确保实时性能

### 场景3：语音笔记

适用于个人语音备忘录、思维录音等场景。

```bash
# 推荐配置
python main.py \
    --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx \
    --input-source microphone \
    --vad-sensitivity 0.3 \
    --log-level WARNING
```

**特点：**
- 高VAD敏感度，捕获轻声说话
- 减少日志输出，专注于转录内容
- 适合安静环境使用

### 场景4：视频转录

适用于转录本地视频、网络视频等内容。

```bash
# 推荐配置
python main.py \
    --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx \
    --input-source system \
    --vad-sensitivity 0.7 \
    --use-gpu
```

**特点：**
- 使用系统音频捕获视频声音
- 低VAD敏感度，避免音效干扰
- GPU加速处理高质量音频

## 高级功能

### 实时状态监控

程序运行时会显示实时状态信息：

```
[启动] 开始实时语音转录...
按 Ctrl+C 停止程序

[状态变化] initializing -> running
[转录] 你好，这是一段测试语音。
[转录] 系统运行正常。
[VAD] 检测到语音活动: 开始
[VAD] 语音活动结束
```

### 错误处理和恢复

系统具备完善的错误处理机制：

```bash
# 模型文件不存在
❌ 模型文件不存在: models/sense-voice.onnx
请检查文件路径是否正确

# 音频设备不可用
❌ 无法访问音频设备
请检查麦克风权限设置

# GPU内存不足
⚠️ GPU内存不足，自动切换到CPU模式
```

### 性能监控

启用调试模式可查看详细性能信息：

```bash
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG
```

输出示例：
```
[DEBUG] 音频缓冲区大小: 1024 samples
[DEBUG] VAD处理时间: 15.2ms
[DEBUG] 转录处理时间: 245.8ms
[DEBUG] GPU内存使用: 1024MB / 6144MB
```

## 输出格式

### 标准输出

默认情况下，转录结果会实时显示在控制台：

```
[2024-09-27 10:30:15] 你好，欢迎使用实时语音转录系统。
[2024-09-27 10:30:18] 这个系统可以将语音实时转换为文字。
[2024-09-27 10:30:22] 支持多种音频输入源。
```

### 时间戳格式

每个转录结果都包含精确的时间戳：
- 格式：`[YYYY-MM-DD HH:MM:SS]`
- 精度：秒级
- 时区：本地时区

### 置信度信息

在调试模式下会显示置信度信息：

```bash
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG
```

输出：
```
[2024-09-27 10:30:15] (置信度: 0.95) 你好，欢迎使用实时语音转录系统。
[2024-09-27 10:30:18] (置信度: 0.88) 这个系统可以将语音实时转换为文字。
```

## 快捷操作

### 快速启动脚本

创建批处理文件 `start_transcription.bat`：

```batch
@echo off
cd /d "F:\py\speech2subtitles"
call .venv\Scripts\activate.bat
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --vad-sensitivity 0.5
pause
```

双击运行即可快速启动转录系统。

### 预设配置

为不同场景创建配置快捷方式：

#### 会议模式
```bash
# meeting.bat
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --vad-sensitivity 0.4 --use-gpu
```

#### 直播模式
```bash
# streaming.bat
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source system --vad-sensitivity 0.6 --use-gpu
```

#### 调试模式
```bash
# debug.bat
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG
```

## 停止和退出

### 正常退出

按 `Ctrl+C` 安全停止程序：

```
^C
[中断] 用户中断程序
[清理] 正在关闭音频设备...
[清理] 正在释放GPU资源...
[完成] 程序正常退出

感谢使用实时语音转录系统！
```

### 强制退出

如果程序无响应，可以：

1. **Windows任务管理器**
   - Ctrl+Shift+Esc 打开任务管理器
   - 找到Python进程并结束

2. **命令行强制结束**
   ```bash
   # 查找Python进程
   tasklist | findstr python

   # 结束进程（替换PID）
   taskkill /PID 1234 /F
   ```

## 性能优化技巧

### 1. 硬件优化

```bash
# 启用GPU加速
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --use-gpu

# 设置GPU内存分配
set CUDA_VISIBLE_DEVICES=0
```

### 2. 参数调优

```bash
# 降低VAD敏感度以减少误触发
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --vad-sensitivity 0.7

# 优化日志级别
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level WARNING
```

### 3. 系统优化

```bash
# 设置线程数
set OMP_NUM_THREADS=4

# 禁用调试输出
set PYTHONOPTIMIZE=1
```

## 故障排除快速指南

### 常见问题及解决方案

1. **无声音输出**
   ```bash
   # 检查音频设备
   python tools/audio_info.py

   # 测试不同输入源
   python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source system
   ```

2. **转录准确率低**
   ```bash
   # 调整VAD敏感度
   python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --vad-sensitivity 0.3

   # 检查音频质量
   python tools/audio_info.py
   ```

3. **程序运行缓慢**
   ```bash
   # 启用GPU加速
   python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --use-gpu

   # 检查GPU状态
   python tools/gpu_info.py
   ```

4. **内存使用过高**
   ```bash
   # 强制使用CPU（降低内存使用）
   python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --no-gpu
   ```

---

更多详细信息请参考 [故障排除指南](troubleshooting.md) 和 [API文档](api.md)。