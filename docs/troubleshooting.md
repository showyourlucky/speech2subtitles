# 故障排除指南

本文档提供详细的问题诊断和解决方案，帮助您快速解决使用过程中遇到的各种问题。

## 快速诊断

### 系统自检工具

运行以下工具快速诊断系统状态：

```bash
# 激活虚拟环���
.venv\Scripts\activate

# 运行快速测试
python quick_test.py

# 运行GPU检测
python tools/gpu_info.py

# 运行音频设备检测
python tools/audio_info.py

# 运行VAD测试
python tools/vad_test.py
```

### 环境检查清单

在报告问题前，请确认以下项目：

- [ ] Python版本 >= 3.8
- [ ] 虚拟环境已正确激活
- [ ] 所有依赖已正确安装
- [ ] 模型文件存在且路径正确
- [ ] 音频设备权限已授予
- [ ] 系统内存充足（建议 >= 8GB）

## 安装相关问题

### 1. 依赖安装失败

#### 问题症状
```
ERROR: Could not find a version that satisfies the requirement xxx
ERROR: No matching distribution found for xxx
```

#### 解决方案

**方案A：更新pip和工具**
```bash
# 升级pip
python -m pip install --upgrade pip

# 升级setuptools和wheel
pip install --upgrade setuptools wheel

# 重新安装依赖
pip install -r requirements.txt
```

**方案B：使用国内镜像源**
```bash
# 使用清华大学镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 使用阿里云镜像
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

**方案C：逐个安装依赖**
```bash
# 核心依赖
pip install torch
pip install numpy
pip install sherpa-onnx
pip install silero-vad
pip install PyAudio

# 如果PyAudio安装失败
pip install pipwin
pipwin install pyaudio
```

### 2. PyAudio安装问题

#### 问题症状
```
Microsoft Visual C++ 14.0 is required
error: Microsoft Visual Studio 14.0 is required
```

#### 解决方案

**方案A：使用预编译包**
```bash
# 安装pipwin
pip install pipwin

# 使用pipwin安装PyAudio
pipwin install pyaudio
```

**方案B：下载wheel文件**
```bash
# 访问 https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
# 下载对应Python版本的.whl文件
# 例如：PyAudio-0.2.11-cp39-cp39-win_amd64.whl

pip install PyAudio-0.2.11-cp39-cp39-win_amd64.whl
```

**方案C：安装Visual Studio Build Tools**
- 下载Visual Studio Installer
- 安装"C++ build tools"
- 重新运行pip install

### 3. CUDA/GPU相关安装问题

#### 问题症状
```
ImportError: DLL load failed while importing _torch_cuda
CUDA runtime error: no kernel image is available for execution
```

#### 解决方案

**检查CUDA兼容性**
```bash
# 检查NVIDIA驱动
nvidia-smi

# 检查CUDA版本
nvcc --version

# 检查PyTorch CUDA支持
python -c "import torch; print(torch.cuda.is_available())"
```

**重新安装PyTorch**
```bash
# 卸载现有PyTorch
pip uninstall torch

# 安装CPU版本（如果不需要GPU）
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 或安装GPU版本（根据CUDA版本选择）
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

## 运行时问题

### 1. 模型加载失败

#### 问题症状
```
FileNotFoundError: [Errno 2] No such file or directory: 'models/sense-voice.onnx'
Failed to load model: Invalid model format
```

#### 诊断步骤
```bash
# 检查模型文件存在性
python -c "
import os
model_path = 'models/sense-voice.onnx'
print(f'文件存在: {os.path.exists(model_path)}')
if os.path.exists(model_path):
    print(f'文件大小: {os.path.getsize(model_path)} bytes')
"
```

#### 解决方案

**检查文件路径**
```bash
# 使用绝对路径
python main.py --model-path "F:\py\speech2subtitles\models\sense-voice.onnx" --input-source microphone

# 确认当前���作目录
python -c "import os; print(os.getcwd())"
```

**验证模型文件**
```bash
# 检查文件完整性
python -c "
import onnx
try:
    model = onnx.load('models/sense-voice.onnx')
    print('模型文件有效')
except Exception as e:
    print(f'模型文件无效: {e}')
"
```

**重新下载模型**
- 确认模型来源可靠
- 验证下载完整性
- 检查文件格式（.onnx或.bin）

### 2. 音频设备问题

#### 问题症状
```
OSError: [Errno -9996] Invalid input device
PermissionError: [Errno 13] Permission denied
No audio input device found
```

#### 诊断步骤
```bash
# 列出所有音频设备
python tools/audio_info.py

# 测试音频权限
python -c "
import pyaudio
p = pyaudio.PyAudio()
print(f'设备数量: {p.get_device_count()}')
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f'{i}: {info[\"name\"]} (输入通道: {info[\"maxInputChannels\"]})')
p.terminate()
"
```

#### 解决方案

**Windows权限设置**
1. 设置 → 隐私 → 麦克风
2. 启用"允许应用访问麦克风"
3. 在应用列表中找到Python并允许

**启用立体声混音**
1. 右键音量图标 → 声音
2. 录制标签 → 右键空白处 → 显示禁用设备
3. 右键"立体声混音" → 启用

**指定音频设备**
```bash
# 查看设备ID
python tools/audio_info.py

# 修改代码指定设备ID（如果需要）
# 在src/audio/capture.py中设置device_index
```

### 3. GPU内存问题

#### 问题症状
```
CUDA out of memory
RuntimeError: CUDA error: out of memory
```

#### 诊断步骤
```bash
# 检查GPU内存使用
nvidia-smi

# 运行GPU信息工具
python tools/gpu_info.py
```

#### 解决方案

**释放GPU内存**
```bash
# 关闭其他GPU应用程序
# 重启电脑清理内存

# 强制使用CPU
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --no-gpu
```

**优化内存使用**
```bash
# 设置GPU内存增长
export CUDA_VISIBLE_DEVICES=0

# 限制GPU内存使用
# 在代码中添加：
# torch.cuda.set_per_process_memory_fraction(0.8)
```

### 4. 性能问题

#### 问题症状
- 转录延迟过高
- CPU/GPU使用率过高
- 系统响应缓慢

#### 诊断步骤
```bash
# 启用性能监控
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG

# 检查系统资源
# Windows: 任务管理器
# 查看CPU、内存、GPU使用率
```

#### 解决方案

**调整VAD敏感度**
```bash
# 降��敏感度减少处理量
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --vad-sensitivity 0.7
```

**优化系统设置**
```bash
# 设置线程数
set OMP_NUM_THREADS=4

# 设置优先级
start /high python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone
```

**使用较小模型**
- 选择较小的sense-voice模型
- 牺牲一定精度换取速度

## 特殊错误处理

### 1. 编码问题

#### 问题症状
```
UnicodeDecodeError: 'utf-8' codec can't decode
UnicodeEncodeError: 'gbk' codec can't encode
```

#### 解决方案
```bash
# 设置环境变量
set PYTHONIOENCODING=utf-8

# 或在代码中指定编码
python -c "import sys; print(sys.stdout.encoding)"
```

### 2. 网络相关问题

#### 问题症状
```
URLError: [Errno 11001] getaddrinfo failed
ConnectionError: HTTPSConnectionPool
```

#### 解决方案
```bash
# 设置网络代理
set HTTP_PROXY=http://proxy.company.com:8080
set HTTPS_PROXY=http://proxy.company.com:8080

# 使用离线模式
# VAD模型会自动下载，如果网络不可用需要手动下载
```

### 3. 权限问题

#### 问题症状
```
PermissionError: [WinError 5] 拒绝访问
OSError: [WinError 32] 另一个程序正在使用此文件
```

#### 解决方案
```bash
# 以管理员身份运行
# 右键��令提示符 → 以管理员身份运行

# 检查文件占用
# 使用Process Explorer或任务管理器查看

# 重启相关服务
net stop "Windows Audio"
net start "Windows Audio"
```

## 调试技巧

### 1. 启用详细日志

```bash
# 最详细的调试信息
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG

# 将日志输出到文件
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG > debug.log 2>&1
```

### 2. 分步测试

```bash
# 1. 测试配置加载
python -c "from src.config.manager import ConfigManager; print('配置模块正常')"

# 2. 测试GPU检测
python -c "from src.hardware.gpu_detector import GPUDetector; GPUDetector().detect_cuda()"

# 3. 测试音频捕获
python -c "from src.audio.capture import AudioCapture; print('音频模块正常')"

# 4. 测试VAD
python tools/vad_test.py

# 5. 测试转录引擎
python test_transcription_engine.py
```

### 3. 隔离问题

```bash
# 使用最小配置测试
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --no-gpu --log-level WARNING

# 禁用VAD测试
# 临时修改代码跳过VAD处理

# 使用模拟数据测试
# 使用预录音频文件而非实时音频
```

## 性能基准

### 正常性能指标

在配置良好的系统上，预期性能如下：

- **启动时间**：< 10秒
- **转录延迟**：< 500ms
- **CPU使用率**：< 50%（CPU模式）
- **GPU使用率**：< 30%（GPU模式）
- **内存使用**：< 2GB

### 性能测试

```bash
# 运行性能测试
python -c "
import time
start_time = time.time()
# 这里放置性能测试代码
end_time = time.time()
print(f'执行时间: {end_time - start_time:.2f}秒')
"
```

## 获取帮助

### 收集诊断信息

在报告问题时，请提供以下信息：

```bash
# 系统信息
python --version
pip list
python -c "import platform; print(platform.platform())"

# GPU信息
nvidia-smi

# 音频设备信息
python tools/audio_info.py

# 错误日志
# 完整的错误输出和堆栈跟踪
```

### 创建最小复现示例

```bash
# 创建最简单的复现步骤
python main.py --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone --log-level DEBUG
```

### 联系支持

1. 检查现有的GitHub Issues
2. 查看项目文档和FAQ
3. 创建新的Issue并提供：
   - 详细的问题描述
   - 完整的错误信息
   - 系统环境信息
   - 复现步骤

---

如果问题仍未解决，请查看 [API文档](api.md) 或 [开发指南](development.md) 获取更深入的技术信息。