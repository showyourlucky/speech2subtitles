"""
转录引擎模块 (Transcription Engine Module)

基于sherpa-onnx和sense-voice模型实现高质量语音转文本功能，
支持GPU/CPU优化、多语言识别和实时转录。

核心组件:
- TranscriptionEngine: 主转录引擎类
- TranscriptionConfig: 转录配置
- TranscriptionResult: 转录结果数据
- 模型管理和异常处理

Author: Speech2Subtitles Project
Created: 2025-09-28
"""

# 核心转录引擎
from .engine import TranscriptionEngine, StreamingTranscriptionEngine

# 数据模型和配置类
from .models import (
    # 配置类
    TranscriptionConfig,

    # 结果类
    TranscriptionResult,
    BatchTranscriptionResult,

    # 信息和统计类
    ModelInfo,
    TranscriptionStatistics,

    # 枚举类
    TranscriptionModel,
    ProcessorType,
    LanguageCode,

    # 异常类
    TranscriptionError,
    ModelLoadError,
    TranscriptionProcessingError,
    ConfigurationError,
    ModelNotLoadedError,
    UnsupportedModelError,
    AudioFormatError
)

# 模块导出列表
__all__ = [
    # 引擎类
    'TranscriptionEngine',
    'StreamingTranscriptionEngine',

    # 配置和数据模型
    'TranscriptionConfig',
    'TranscriptionResult',
    'BatchTranscriptionResult',
    'ModelInfo',
    'TranscriptionStatistics',

    # 枚举类型
    'TranscriptionModel',
    'ProcessorType',
    'LanguageCode',

    # 异常类型
    'TranscriptionError',
    'ModelLoadError',
    'TranscriptionProcessingError',
    'ConfigurationError',
    'ModelNotLoadedError',
    'UnsupportedModelError',
    'AudioFormatError'
]

# 模块版本信息
__version__ = '1.0.0'
__author__ = 'Speech2Subtitles Project'
__description__ = '语音转文本转录引擎'