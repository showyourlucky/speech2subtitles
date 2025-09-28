# 部署指南

本文档详细介绍如何在不同环境中部署实时语音转录系统，包括开发环境、测试环境和生产环境的部署策略。

## 部署概览

### 部署架构

```
实时语音转录系统部署架构

┌─────────────────────────────────────────────┐
│                用户层                        │
├─────────────────────────────────────────────┤
│  命令行界面(CLI) │  批处理脚本  │  API接口    │
├─────────────────────────────────────────────┤
│                应用层                        │
├─────────────────────────────────────────────┤
│ 配置管理 │ 转录引擎 │ VAD │ 音频捕获 │ 输出  │
├─────────────────────────────────────────────┤
│                硬件层                        │
├─────────────────────────────────────────────┤
│    CPU/GPU    │   音频设备   │    内存      │
└─────────────────────────────────────────────┘
```

### 部署模式

1. **单机部署**：完整功能在单台机器上运行
2. **容器化部署**：使用Docker容器进行隔离部署
3. **分布式部署**：音频捕获和转录处理分离
4. **云端部署**：在云服务器上运行系统

## 单机部署

### 开发环境部署

适用于开发测试和个人使用场景。

#### 环境准备

```bash
# 系统要求
- Windows 10/11 (x64)
- Python 3.8+
- 8GB+ RAM
- 2GB+ 可用磁盘空间
- 可选：NVIDIA GPU (CUDA支持)
```

#### 快速部署脚本

创建部署脚本 `deploy_dev.bat`：

```batch
@echo off
echo ========================================
echo     实时语音转录系统 - 开发环境部署
echo ========================================

:: 检查Python版本
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装或不在PATH中
    pause
    exit /b 1
)

:: 创建项目目录
if not exist "speech2subtitles" (
    echo 📁 创建项目目录...
    mkdir speech2subtitles
)

cd speech2subtitles

:: 创建虚拟环境
echo 🔧 创建虚拟环境...
python -m venv .venv

:: 激活虚拟环境
echo 🔌 激活虚拟环境...
call .venv\Scripts\activate.bat

:: 升级pip
echo ⬆️ 升级pip...
python -m pip install --upgrade pip

:: 安装依赖
echo 📦 安装依赖包...
pip install -r requirements.txt

:: 创建模型目录
if not exist "models" (
    echo 📁 创建模型目录...
    mkdir models
)

:: 运行快速测试
echo 🧪 运行系统测试...
python quick_test.py

echo ✅ 开发环境部署完成！
echo.
echo 下一步:
echo 1. 下载sense-voice模型文件到models/目录
echo 2. 运行: python main.py --model-path models/sense-voice.onnx --input-source microphone
echo.
pause
```

#### 验证部署

```bash
# 运行部署脚本
deploy_dev.bat

# 验证安装
.venv\Scripts\activate
python quick_test.py

# 测试基本功能
python main.py --help
```

### 生产环境部署

适用于稳定的生产环境使用。

#### 环境配置

```bash
# 1. 创建专用用户
net user speech2subtitles /add /comment:"语音转录系统服务用户"

# 2. 设置目录权限
mkdir C:\speech2subtitles
icacls C:\speech2subtitles /grant speech2subtitles:F

# 3. 安装Python服务
sc create Speech2Subtitles binPath="C:\speech2subtitles\service.exe" obj=".\speech2subtitles"
```

#### 生产部署脚本

创建 `deploy_prod.bat`：

```batch
@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   实时语音转录系统 - 生产环境部署
echo ========================================

:: 设置部署变量
set DEPLOY_DIR=C:\speech2subtitles
set SERVICE_NAME=Speech2Subtitles
set PYTHON_VERSION=3.9

:: 检查管理员权限
net session >nul 2>&1
if errorlevel 1 (
    echo ❌ 需要管理员权限，请以管理员身份运行
    pause
    exit /b 1
)

:: 创建部署目录
if not exist "%DEPLOY_DIR%" (
    echo 📁 创建部署目录: %DEPLOY_DIR%
    mkdir "%DEPLOY_DIR%"
)

cd "%DEPLOY_DIR%"

:: 部署应用文件
echo 📂 复制应用文件...
xcopy /E /I /Y "src" "%DEPLOY_DIR%\src"
copy /Y "main.py" "%DEPLOY_DIR%"
copy /Y "requirements.txt" "%DEPLOY_DIR%"

:: 创建Python虚拟环境
echo 🐍 创建Python虚拟环境...
python -m venv venv
call venv\Scripts\activate.bat

:: 安装依赖（生产版本）
echo 📦 安装生产依赖...
pip install --no-cache-dir -r requirements.txt

:: 创建配置文件
echo 🔧 创建配置文件...
echo # 生产环境配置 > config.ini
echo [DEFAULT] >> config.ini
echo debug = false >> config.ini
echo log_level = INFO >> config.ini
echo gpu_enabled = true >> config.ini

:: 创建日志目录
mkdir logs

:: 创建模型目录
mkdir models

:: 设置防火墙规则（如果需要）
netsh advfirewall firewall add rule name="Speech2Subtitles" dir=in action=allow program="%DEPLOY_DIR%\venv\Scripts\python.exe"

:: 安装Windows服务（可选）
echo 🔧 配置Windows服务...
sc create %SERVICE_NAME% binPath="%DEPLOY_DIR%\service_wrapper.exe" start=auto
sc description %SERVICE_NAME% "实时语音转录系统服务"

echo ✅ 生产环境部署完成！
echo.
echo 部署信息:
echo - 安装目录: %DEPLOY_DIR%
echo - 服务名称: %SERVICE_NAME%
echo - 日志目录: %DEPLOY_DIR%\logs
echo.
echo 下一步:
echo 1. 将模型文件复制到 %DEPLOY_DIR%\models\
echo 2. 配置音频设备权限
echo 3. 启动服务: sc start %SERVICE_NAME%
echo.
pause
```

## 容器化部署

### Docker部署

适用于隔离环境和跨平台部署。

#### Dockerfile

创建 `Dockerfile`：

```dockerfile
# 基础镜像
FROM python:3.9-slim-bullseye

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    alsa-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY src/ ./src/
COPY main.py .
COPY tools/ ./tools/
COPY tests/ ./tests/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建必要目录
RUN mkdir -p /app/models /app/logs /app/data

# 设置权限
RUN useradd -m -u 1000 speech2subtitles && \
    chown -R speech2subtitles:speech2subtitles /app
USER speech2subtitles

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import src; print('OK')" || exit 1

# 暴露端口（如果有API）
# EXPOSE 8000

# 启动命令
CMD ["python", "main.py", "--model-path", "/app/models/sense-voice.onnx", "--input-source", "microphone"]
```

#### Docker Compose

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  speech2subtitles:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: speech2subtitles
    restart: unless-stopped

    # 环境变量
    environment:
      - PYTHONPATH=/app
      - LOG_LEVEL=INFO
      - GPU_ENABLED=false

    # 卷挂载
    volumes:
      - ./models:/app/models:ro
      - ./logs:/app/logs
      - ./data:/app/data
      - /dev/snd:/dev/snd  # 音频设备

    # 设备访问
    devices:
      - /dev/snd:/dev/snd

    # 特权模式（音频设备访问）
    privileged: true

    # 网络模式
    network_mode: host

    # 资源限制
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'

    # 健康检查
    healthcheck:
      test: ["CMD", "python", "-c", "import src; print('OK')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # 可选：添加监控服务
  monitoring:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

volumes:
  models:
  logs:
  data:
```

#### 构建和运行

```bash
# 构建镜像
docker build -t speech2subtitles:latest .

# 运行容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 云端部署

### AWS部署

在Amazon Web Services上部署系统。

#### EC2实例配置

```bash
# 1. 创建EC2实例
aws ec2 run-instances \
    --image-id ami-0abcdef1234567890 \
    --count 1 \
    --instance-type g4dn.xlarge \
    --key-name my-key-pair \
    --security-group-ids sg-903004f8 \
    --subnet-id subnet-6e7f829e

# 2. 配置安全组
aws ec2 authorize-security-group-ingress \
    --group-id sg-903004f8 \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0
```

#### 部署脚本（云端）

创建 `deploy_aws.sh`：

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "   AWS EC2 部署脚本"
echo "=========================================="

# 更新系统
sudo apt-get update
sudo apt-get upgrade -y

# 安装Python和依赖
sudo apt-get install -y python3.9 python3.9-venv python3.9-dev
sudo apt-get install -y portaudio19-dev python3-pyaudio
sudo apt-get install -y git wget curl

# 安装NVIDIA驱动（如果是GPU实例）
if lspci | grep -i nvidia; then
    echo "检测到NVIDIA GPU，安装驱动..."
    sudo apt-get install -y nvidia-driver-470
    wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run
    sudo sh cuda_11.8.0_520.61.05_linux.run --silent --toolkit
fi

# 创建应用目录
sudo mkdir -p /opt/speech2subtitles
sudo chown $USER:$USER /opt/speech2subtitles
cd /opt/speech2subtitles

# 克隆代码
git clone <repository-url> .

# 创建虚拟环境
python3.9 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 创建systemd服务
sudo tee /etc/systemd/system/speech2subtitles.service > /dev/null <<EOF
[Unit]
Description=Real-time Speech Transcription System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/speech2subtitles
Environment=PATH=/opt/speech2subtitles/venv/bin
ExecStart=/opt/speech2subtitles/venv/bin/python main.py --model-path /opt/speech2subtitles/models/sense-voice.onnx --input-source microphone
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable speech2subtitles

echo "✅ AWS部署完成！"
echo "下一步："
echo "1. 上传模型文件到 /opt/speech2subtitles/models/"
echo "2. 启动服务: sudo systemctl start speech2subtitles"
echo "3. 查看状态: sudo systemctl status speech2subtitles"
```

### Azure部署

在Microsoft Azure上部署系统。

#### ARM模板

创建 `azure-deploy.json`：

```json
{
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "vmName": {
            "type": "string",
            "defaultValue": "speech2subtitles-vm"
        },
        "adminUsername": {
            "type": "string",
            "defaultValue": "azureuser"
        },
        "adminPassword": {
            "type": "securestring"
        }
    },
    "variables": {
        "location": "[resourceGroup().location]",
        "vmSize": "Standard_NC6s_v3"
    },
    "resources": [
        {
            "type": "Microsoft.Compute/virtualMachines",
            "apiVersion": "2021-03-01",
            "name": "[parameters('vmName')]",
            "location": "[variables('location')]",
            "properties": {
                "hardwareProfile": {
                    "vmSize": "[variables('vmSize')]"
                },
                "osProfile": {
                    "computerName": "[parameters('vmName')]",
                    "adminUsername": "[parameters('adminUsername')]",
                    "adminPassword": "[parameters('adminPassword')]"
                },
                "storageProfile": {
                    "imageReference": {
                        "publisher": "Canonical",
                        "offer": "0001-com-ubuntu-server-focal",
                        "sku": "20_04-lts-gen2",
                        "version": "latest"
                    }
                }
            }
        }
    ]
}
```

#### 部署命令

```bash
# 创建资源组
az group create --name speech2subtitles-rg --location eastus

# 部署VM
az deployment group create \
    --resource-group speech2subtitles-rg \
    --template-file azure-deploy.json \
    --parameters adminPassword=<your-password>

# 连接到VM
az ssh vm --resource-group speech2subtitles-rg --name speech2subtitles-vm
```

## 配置管理

### 环境配置文件

创建不同环境的配置文件：

#### 开发环境 (`config/dev.ini`)
```ini
[DEFAULT]
debug = true
log_level = DEBUG
gpu_enabled = true
model_path = models/sense-voice.onnx
input_source = microphone
vad_sensitivity = 0.5

[audio]
sample_rate = 16000
channels = 1
chunk_size = 1024

[logging]
log_file = logs/dev.log
max_log_size = 10MB
backup_count = 5
```

#### 生产环境 (`config/prod.ini`)
```ini
[DEFAULT]
debug = false
log_level = INFO
gpu_enabled = true
model_path = /app/models/sense-voice.onnx
input_source = microphone
vad_sensitivity = 0.6

[audio]
sample_rate = 16000
channels = 1
chunk_size = 2048

[logging]
log_file = /var/log/speech2subtitles/app.log
max_log_size = 100MB
backup_count = 10

[performance]
max_memory_mb = 4096
max_cpu_percent = 80
```

### 环境变量管理

创建 `.env` 文件：

```bash
# 应用配置
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# 硬件配置
GPU_ENABLED=true
CUDA_VISIBLE_DEVICES=0

# 音频配置
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1

# 路径配置
MODEL_PATH=/app/models/sense-voice.onnx
LOG_DIR=/var/log/speech2subtitles
DATA_DIR=/var/lib/speech2subtitles

# 性能配置
MAX_MEMORY_MB=4096
OMP_NUM_THREADS=4
```

## 监控和日志

### 日志配置

创建 `logging.yaml`：

```yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s:%(lineno)d - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: detailed
    filename: /var/log/speech2subtitles/app.log
    maxBytes: 104857600  # 100MB
    backupCount: 10

  error_file:
    class: logging.handlers.RotatingFileHandler
    level: ERROR
    formatter: detailed
    filename: /var/log/speech2subtitles/error.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  speech2subtitles:
    level: DEBUG
    handlers: [console, file, error_file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

### 监控脚本

创建 `monitor.py`：

```python
#!/usr/bin/env python3
"""
系统监控脚本
监控CPU、内存、GPU使用情况和应用状态
"""

import psutil
import time
import logging
from datetime import datetime

def monitor_system():
    """监控系统资源"""
    while True:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)

        # 内存使用
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # 磁盘使用
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100

        # GPU使用（如果有NVIDIA GPU）
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            gpu_percent = gpus[0].load * 100 if gpus else 0
            gpu_memory = gpus[0].memoryUtil * 100 if gpus else 0
        except ImportError:
            gpu_percent = 0
            gpu_memory = 0

        # 记录监控数据
        logging.info(f"系统监控 - CPU: {cpu_percent:.1f}%, "
                    f"内存: {memory_percent:.1f}%, "
                    f"磁盘: {disk_percent:.1f}%, "
                    f"GPU: {gpu_percent:.1f}%, "
                    f"GPU内存: {gpu_memory:.1f}%")

        # 检查阈值并报警
        if cpu_percent > 90:
            logging.warning(f"CPU使用率过高: {cpu_percent:.1f}%")
        if memory_percent > 90:
            logging.warning(f"内存使用率过高: {memory_percent:.1f}%")
        if gpu_memory > 90:
            logging.warning(f"GPU内存使用率过高: {gpu_memory:.1f}%")

        time.sleep(60)  # 每分钟检查一次

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor_system()
```

## 备份和恢复

### 备份脚本

创建 `backup.bat`：

```batch
@echo off
set BACKUP_DIR=C:\backups\speech2subtitles
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set BACKUP_NAME=speech2subtitles_%TIMESTAMP%

echo 开始备份系统...

:: 创建备份目录
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

:: 备份应用文件
echo 备份应用文件...
xcopy /E /I /Y "C:\speech2subtitles\src" "%BACKUP_DIR%\%BACKUP_NAME%\src"
copy /Y "C:\speech2subtitles\main.py" "%BACKUP_DIR%\%BACKUP_NAME%"
copy /Y "C:\speech2subtitles\requirements.txt" "%BACKUP_DIR%\%BACKUP_NAME%"

:: 备份配置文件
echo 备份配置文件...
xcopy /E /I /Y "C:\speech2subtitles\config" "%BACKUP_DIR%\%BACKUP_NAME%\config"

:: 备份模型文件
echo 备份模型文件...
xcopy /E /I /Y "C:\speech2subtitles\models" "%BACKUP_DIR%\%BACKUP_NAME%\models"

:: 备份日志文件（最近30天）
echo 备份日志文件...
forfiles /p "C:\speech2subtitles\logs" /m *.log /d -30 /c "cmd /c copy @path %BACKUP_DIR%\%BACKUP_NAME%\logs"

:: 创建压缩包
echo 创建压缩包...
powershell Compress-Archive -Path "%BACKUP_DIR%\%BACKUP_NAME%\*" -DestinationPath "%BACKUP_DIR%\%BACKUP_NAME%.zip"

:: 清理临时文件
rmdir /s /q "%BACKUP_DIR%\%BACKUP_NAME%"

echo 备份完成: %BACKUP_DIR%\%BACKUP_NAME%.zip
```

### 恢复脚本

创建 `restore.bat`：

```batch
@echo off
set BACKUP_DIR=C:\backups\speech2subtitles
set RESTORE_DIR=C:\speech2subtitles

echo 可用备份文件:
dir /b "%BACKUP_DIR%\*.zip"
echo.

set /p BACKUP_FILE=请输入要恢复的备份文件名（不含.zip）:

if not exist "%BACKUP_DIR%\%BACKUP_FILE%.zip" (
    echo 错误: 备份文件不存在
    pause
    exit /b 1
)

echo 开始恢复系统...

:: 停止服务
sc stop Speech2Subtitles

:: 备份当前系统（以防恢复失败）
echo 备份当前系统...
xcopy /E /I /Y "%RESTORE_DIR%" "%BACKUP_DIR%\current_backup"

:: 解压备份文件
echo 解压备份文件...
powershell Expand-Archive -Path "%BACKUP_DIR%\%BACKUP_FILE%.zip" -DestinationPath "%BACKUP_DIR%\temp_restore" -Force

:: 恢复文件
echo 恢复应用文件...
xcopy /E /I /Y "%BACKUP_DIR%\temp_restore\*" "%RESTORE_DIR%"

:: 清理临时文件
rmdir /s /q "%BACKUP_DIR%\temp_restore"

:: 重新安装依赖
echo 重新安装依赖...
cd "%RESTORE_DIR%"
call .venv\Scripts\activate.bat
pip install -r requirements.txt

:: 启动服务
sc start Speech2Subtitles

echo 系统恢复完成！
```

## 安全配置

### 用户权限配置

```bash
# 创建专用用户
net user speech2subtitles P@ssw0rd123 /add /comment:"语音转录系统用户"

# 设置用户权限
net localgroup Users speech2subtitles /delete
net localgroup "Performance Log Users" speech2subtitles /add

# 设置目录权限
icacls C:\speech2subtitles /grant speech2subtitles:(OI)(CI)F
icacls C:\speech2subtitles\models /grant speech2subtitles:(OI)(CI)R
```

### 防火墙配置

```bash
# 允许音频设备访问
netsh advfirewall firewall add rule name="Speech2Subtitles Audio" dir=in action=allow program="C:\speech2subtitles\.venv\Scripts\python.exe"

# 阻止不必要的网络访问
netsh advfirewall firewall add rule name="Block Speech2Subtitles Outbound" dir=out action=block program="C:\speech2subtitles\.venv\Scripts\python.exe"
```

---

以上是完整的部署指南。根据您的具体需求选择合适的部署方式，并按照相应的步骤进行部署。如有问题，请参考 [故障排除指南](troubleshooting.md)。