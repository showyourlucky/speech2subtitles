# 安装指南

本文档提供详细的安装和配置指导，帮助您快速搭建实时语音转录系统。

## 环境准备

### 系统要求检查

在开始安装之前，请确认您的系统满足以下要求：

```bash
# 检查Python版本
python --version  # 应该 >= 3.8

# 检查系统内存
wmic computersystem get TotalPhysicalMemory  # Windows

# 检查可用磁盘空间
dir C:\ | findstr "bytes free"  # Windows
```

### Windows专用配置

1. **启用开发者模式**（可选，便于调试）
   - 设置 → 更新和安全 → 针对开发人员 → 开发者模式

2. **音频设备权限**
   - 设置 → 隐私 → 麦克风 → 允许应用访问麦克风
   - 设置 → 隐私 → 摄像头 → 允许应用访问摄像头（如果需要）

## 安装方法

### 方法一：使用 uv（推荐）

uv 是一个现代的Python包管理器，提供更快的依赖解析和安装：

```bash
# 1. 安装 uv
pip install uv

# 2. 验证安装
uv --version

# 3. 克隆项目
git clone <repository-url>
cd speech2subtitles

# 4. 创建并激活虚拟环境，安装依赖
uv sync

# 5. 激活虚拟环境
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# 6. 验证安装
python -c "import src; print('安装成功')"
```

### 方法二：使用传统 pip

```bash
# 1. 克隆项目
git clone <repository-url>
cd speech2subtitles

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# 4. 升级pip
python -m pip install --upgrade pip

# 5. 安装依赖
pip install -r requirements.txt

# 6. 验证安装
python -c "import src; print('安装成功')"
```

## 模型文件配置

### 下载模型

sense-voice模型文件是系统运行的核心，支持以下格式：

1. **ONNX格式** (.onnx) - 推荐
2. **二进制格式** (.bin)

#### 官方模型下载

```bash
# 创建模型目录
mkdir models

# 下载示例（请替换为实际下载链接）
# 从阿里云或官方仓库下载sense-voice模型
# wget -O models/sense-voice.onnx https://example.com/sense-voice.onnx
```

#### 模型验证

```bash
# 检查模型文件
python -c "
import os
model_path = 'models/sense-voice.onnx'
if os.path.exists(model_path):
    size = os.path.getsize(model_path) / (1024*1024)
    print(f'模型文件存在，大小: {size:.1f} MB')
else:
    print('模型文件不存在')
"
```

### 模型优化建议

1. **选择合适的模型大小**
   - 小模型：更快速度，适中精度
   - 大模型：更高精度，较高延迟

2. **模型存储位置**
   - 推荐放置在项目根目录的 `models/` 文件夹
   - 确保有足够的磁盘空间
   - 避免网络驱动器（影响加载速度）

## GPU配置（可选）

GPU加速可显著提升转录性能，特别适合高频使用场景。

### CUDA环境配置

1. **安装NVIDIA驱动**
   ```bash
   # 检查当前驱动版本
   nvidia-smi
   ```

2. **安装CUDA Toolkit**（如果需要）
   - 下载CUDA Toolkit 11.8或更高版本
   - 验证安装：`nvcc --version`

3. **安装GPU版本依赖**
   ```bash
   # 使用uv
   uv add onnxruntime-gpu

   # 或使用pip
   pip install onnxruntime-gpu
   ```

### 验证GPU配置

```bash
# 运行GPU检测工具
python tools/gpu_info.py

# 预期输出示例：
# ✅ CUDA可用: 是
# GPU 0: NVIDIA GeForce RTX 3080 (10240 MB)
# 推荐使用GPU加速
```

### 故障排除

如果GPU检测失败：

1. **驱动问题**
   ```bash
   # 更新NVIDIA驱动
   # 访问 https://www.nvidia.com/drivers/
   ```

2. **CUDA版本不兼容**
   ```bash
   # 检查兼容性
   python -c "
   import torch
   print(f'PyTorch CUDA可用: {torch.cuda.is_available()}')
   print(f'CUDA版本: {torch.version.cuda}')
   "
   ```

3. **回退到CPU**
   ```bash
   # 强制使用CPU
   python main.py --model-path models/sense-voice.onnx --input-source microphone --no-gpu
   ```

## 音频设备配置

### 设备检测

```bash
# 运行音频设备检测
python tools/audio_info.py

# 输出示例：
# 可用音频输入设备:
# [0] 麦克风 (Realtek High Definition Audio)
# [1] 立体声混音 (Realtek High Definition Audio)
```

### 权限配置

1. **Windows麦克风权限**
   - 设置 → 隐私 → 麦克风
   - 启用"允许应用访问麦克风"
   - 在应用列表中找到Python或终端并允许

2. **系统音频捕获**
   - 确保"立体声混音"设备已启用
   - 控制面板 → 声音 → 录制 → 立体声混音 → 启用

### 音频测试

```bash
# 测试麦克风输入
python main.py --model-path models/sense-voice.onnx --input-source microphone

# 测试系统音频输入
python main.py --model-path models/sense-voice.onnx --input-source system
```

## 验证安装

### 快速验证

```bash
# 运行快速测试
python quick_test.py

# 预期输出：
# ✅ 配置管理模块正常
# ✅ GPU检测模块正常
# ✅ 音频捕获模块正常
# ✅ VAD模块正常
# ✅ 转录引擎模块正常
```

### 完整测试

```bash
# 运行完整测试套件
python run_tests.py

# 运行集成测试
python test_integration.py
```

### 功能验证

```bash
# 验证基本功能（需要真实模型文件）
python main.py --model-path models/sense-voice.onnx --input-source microphone --help

# 验证所有组件
python -c "
from src.config.manager import ConfigManager
from src.hardware.gpu_detector import GPUDetector
from src.audio.capture import AudioCapture
print('所有核心组件导入成功')
"
```

## 常见安装问题

### 依赖冲突

```bash
# 清理现有环境
pip uninstall -y sherpa-onnx torch pyaudio

# 重新安装
pip install -r requirements.txt
```

### 虚拟环境问题

```bash
# 删除现有虚拟环境
rmdir /s .venv  # Windows
# rm -rf .venv  # Linux/macOS

# 重新创建
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 网络代理配置

```bash
# 如果在企业网络环境中
pip install -r requirements.txt --proxy http://proxy.company.com:8080

# 或配置环境变量
set HTTP_PROXY=http://proxy.company.com:8080
set HTTPS_PROXY=http://proxy.company.com:8080
```

## 高级配置

### 开发环境

```bash
# 安装开发依赖
pip install -r requirements.txt
pip install pytest pytest-cov black flake8

# 配置pre-commit钩子
pip install pre-commit
pre-commit install
```

### 生产环境

```bash
# 仅安装运行时依赖
pip install sherpa-onnx torch silero-vad numpy PyAudio dataclasses-json psutil

# 禁用调试输出
export PYTHONOPTIMIZE=1
```

### 性能调优

```bash
# 设置环境变量优化性能
set OMP_NUM_THREADS=4
set CUDA_VISIBLE_DEVICES=0
set ONNXRUNTIME_LOG_SEVERITY_LEVEL=3
```

## 卸载

### 完全卸载

```bash
# 停用虚拟环境
deactivate

# 删除项目目录
cd ..
rmdir /s speech2subtitles  # Windows
# rm -rf speech2subtitles  # Linux/macOS
```

### 保留配置卸载

```bash
# 仅删除虚拟环境
rmdir /s .venv  # Windows

# 保留项目文件和配置
```

---

安装完成后，请参考 [使用指南](usage.md) 了解详细的使用方法。