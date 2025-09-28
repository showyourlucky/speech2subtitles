# -*- coding: utf-8 -*-
"""
统一工具模块

提供日志记录、错误处理等通用功能
"""

from .logger import (
    LogLevel,
    LogConfig,
    PerformanceTimer,
    LoggerManager,
    setup_logging,
    get_logger,
    get_performance_timer,
    log_performance_stats,
    get_performance_summary,
    shutdown_logging
)

from .error_handler import (
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    ErrorRecord,
    SpeechTranscriptionError,
    ConfigurationError,
    HardwareError,
    AudioError,
    ModelError,
    TranscriptionError,
    ErrorHandler,
    handle_exceptions,
    get_global_error_handler,
    handle_exception
)

__all__ = [
    # 日志相关
    'LogLevel',
    'LogConfig',
    'PerformanceTimer',
    'LoggerManager',
    'setup_logging',
    'get_logger',
    'get_performance_timer',
    'log_performance_stats',
    'get_performance_summary',
    'shutdown_logging',

    # 错误处理相关
    'ErrorSeverity',
    'ErrorCategory',
    'ErrorContext',
    'ErrorRecord',
    'SpeechTranscriptionError',
    'ConfigurationError',
    'HardwareError',
    'AudioError',
    'ModelError',
    'TranscriptionError',
    'ErrorHandler',
    'handle_exceptions',
    'get_global_error_handler',
    'handle_exception'
]