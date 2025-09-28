"""
语音转录结果输出处理模块

提供全面的转录结果格式化和显示功能。
支持多种输出格式(控制台、JSON、纯文本、字幕文件等)，
包含实时显示、颜色方案、时间戳格式化等功能。
"""

# 导入输出处理器主类
from .handler import OutputHandler

# 导入数据模型和配置类
from .models import (
    OutputConfig, OutputFormat, TimestampFormat, OutputLevel, ColorScheme,  # 配置相关
    FormattedOutput, OutputBuffer, DisplayMetrics, SubtitleEntry,           # 数据结构
    OutputError, FormattingError, FileOutputError, ConfigurationError,      # 异常类
    BufferOverflowError                                                      # 缓冲区溢出异常
)

# 模块公开接口
__all__ = [
    # 主要处理器
    'OutputHandler',

    # 配置类和枚举
    'OutputConfig',
    'OutputFormat',
    'TimestampFormat',
    'OutputLevel',
    'ColorScheme',

    # 数据结构
    'FormattedOutput',
    'OutputBuffer',
    'DisplayMetrics',
    'SubtitleEntry',

    # 异常类
    'OutputError',
    'FormattingError',
    'FileOutputError',
    'ConfigurationError',
    'BufferOverflowError'
]