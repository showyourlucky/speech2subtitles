"""
基于Silero VAD的语音活动检测模块

提供实时语音检测和语音边界识别功能
支持流式处理、状态管理和统计信息收集
用于在语音识别系统中进行语音/静音预处理
"""

from .models import (
    VadConfig, VadResult, VadState, VadModel, SpeechSegment,
    VadStatistics, VadError, ModelLoadError, DetectionError,
    ConfigurationError
)
from .detector import VoiceActivityDetector, StreamingVAD, VadModelFactory, SherpaOnnxVAD, LegacyTorchVAD
from .vad_manager import VadManager

__all__ = [
    # 数据模型和配置
    "VadConfig",         # VAD配置类
    "VadResult",         # VAD检测结果
    "VadState",          # VAD状态枚举
    "VadModel",          # VAD模型枚举
    "SpeechSegment",     # 语音段信息
    "VadStatistics",     # 处理统计信息
    # 异常类
    "VadError",          # VAD基础异常
    "ModelLoadError",    # 模型加载异常
    "DetectionError",    # 检测过程异常
    "ConfigurationError", # 配置错误异常
    # 检测器类
    "VoiceActivityDetector", # 主VAD检测器（统一接口）
    "StreamingVAD",      # 流式VAD处理器
    # 管理器类
    "VadManager",        # VAD检测器单例管理器
    # 工厂和实现类
    "VadModelFactory",   # VAD模型工厂类
    "SherpaOnnxVAD",     # sherpa-onnx VAD实现
    "LegacyTorchVAD"     # 传统torch.hub VAD实现
]