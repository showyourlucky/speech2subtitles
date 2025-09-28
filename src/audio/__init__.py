"""
音频捕获和处理模块 (Audio Capture and Processing Module)

提供实时音频捕获功能，支持麦克风和系统音频源
- 支持多种音频设备的检测和管理
- 提供统一的音频捕获接口
- 支持实时音频流处理和回调机制
- 包含完整的错误处理和状态监控
"""

# 导入音频数据模型和类型定义
from .models import (
    AudioDevice,           # 音频设备信息类
    AudioConfig,           # 音频配置类
    AudioChunk,            # 音频数据块类
    AudioStreamStatus,     # 音频流状态信息类
    AudioSourceType,       # 音频源类型枚举
    AudioFormat,           # 音频格式枚举
    AudioCaptureError,     # 音频捕获基础异常
    DeviceNotFoundError,   # 设备未找到异常
    StreamError,           # 音频流异常
    ConfigurationError     # 配置错误异常
)

# 导入音频捕获实现类
from .capture import (
    AudioCapture,          # 音频捕获基础类
    SystemAudioCapture,    # 系统音频捕获类
    MicrophoneCapture,     # 麦克风音频捕获类
    create_audio_capture   # 音频捕获工厂函数
)

# 模块对外导出的公共接口
__all__ = [
    # 数据模型类 (Data Models)
    "AudioDevice",           # 音频设备信息
    "AudioConfig",           # 音频配置
    "AudioChunk",            # 音频数据块
    "AudioStreamStatus",     # 音频流状态
    "AudioSourceType",       # 音频源类型枚举
    "AudioFormat",           # 音频格式枚举

    # 异常类 (Exceptions)
    "AudioCaptureError",     # 音频捕获基础异常
    "DeviceNotFoundError",   # 设备未找到异常
    "StreamError",           # 音频流异常
    "ConfigurationError",    # 配置错误异常

    # 音频捕获类 (Capture Classes)
    "AudioCapture",          # 音频捕获基础类
    "SystemAudioCapture",    # 系统音频捕获类
    "MicrophoneCapture",     # 麦克风音频捕获类
    "create_audio_capture"   # 音频捕获工厂函数
]