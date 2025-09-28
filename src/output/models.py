"""
输出处理器数据模型

定义输出格式化、显示配置和结果处理所需的数据结构。
包含输出格式枚举、配置类、显示指标、格式化输出等核心数据类型。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import time
import re
from datetime import datetime

# 模块级别的正则表达式编译，避免重复编译
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class OutputFormat(Enum):
    """输出格式类型枚举

    定义系统支持的各种输出格式，用于控制转录结果的展示方式。
    """
    CONSOLE = "console"      # 控制台彩色输出(支持颜色和格式化)
    JSON = "json"           # JSON格式输出(结构化数据)
    PLAIN_TEXT = "plain_text"  # 纯文本输出(无格式化)
    SRT = "srt"             # SRT字幕文件格式
    VTT = "vtt"             # WebVTT字幕文件格式
    XML = "xml"             # XML格式输出(预留)


class TimestampFormat(Enum):
    """时间戳格式类型枚举

    定义时间戳的不同显示格式，适用于不同的使用场景。
    """
    ABSOLUTE = "absolute"  # 绝对时间: 2024-01-01 12:00:00
    RELATIVE = "relative"  # 相对时间: 00:01:23.456
    UNIX = "unix"         # Unix时间戳: 1234567890.123
    ISO8601 = "iso8601"   # ISO8601格式: 2024-01-01T12:00:00.000Z


class OutputLevel(Enum):
    """输出详细程度级别枚举

    控制输出信息的详细程度，平衡信息完整性和可读性。
    """
    MINIMAL = "minimal"      # 最小输出: 仅显示最终结果
    NORMAL = "normal"        # 正常输出: 最终结果 + 重要的部分结果
    VERBOSE = "verbose"      # 详细输出: 所有结果包括部分结果
    DEBUG = "debug"          # 调试输出: 所有信息 + 调试详情


class ColorScheme(Enum):
    """控制台颜色方案枚举

    定义控制台输出的颜色主题，提升用户体验和信息识别度。
    """
    NONE = "none"           # 无颜色输出(纯文本)
    BASIC = "basic"         # 基础颜色方案(标准ANSI颜色)
    RICH = "rich"           # 丰富颜色方案(增强显示效果)
    DARK = "dark"           # 深色主题适配
    LIGHT = "light"         # 浅色主题适配


@dataclass
class OutputConfig:
    """输出处理器配置类

    包含所有输出相关的配置参数，用于控制输出行为、格式和显示选项。
    支持配置验证和属性查询方法。
    """
    # 输出格式配置
    format: OutputFormat = OutputFormat.CONSOLE              # 输出格式类型
    timestamp_format: TimestampFormat = TimestampFormat.RELATIVE  # 时间戳格式
    output_level: OutputLevel = OutputLevel.NORMAL          # 输出详细程度
    color_scheme: ColorScheme = ColorScheme.BASIC           # 颜色方案

    # 显示选项配置
    show_confidence: bool = True      # 是否显示置信度分数
    show_timestamps: bool = True      # 是否显示时间戳
    show_processing_info: bool = False  # 是否显示处理信息(耗时等)
    show_word_timestamps: bool = False  # 是否显示词级时间戳

    # 实时更新配置
    real_time_update: bool = True     # 是否启用实时更新
    buffer_size: int = 100           # 输出缓冲区大小
    max_line_length: int = 80        # 最大行长度

    # 格式化选项
    indent_partial: bool = True       # 是否缩进部分结果
    highlight_final: bool = True      # 是否高亮最终结果

    # 文件输出配置
    log_to_file: bool = False        # 是否记录到文件
    log_file_path: str = ""          # 日志文件路径

    # 元数据配置
    include_metadata: bool = False    # 是否包含元数据信息
    language_display: bool = False    # 是否显示语言标识

    def validate(self) -> bool:
        """验证输出配置的有效性

        Returns:
            bool: 配置是否有效
        """
        # 检查缓冲区大小是否合理
        if self.buffer_size <= 0:
            return False

        # 检查最大行长度是否合理
        if self.max_line_length <= 0:
            return False

        # 检查文件输出配置是否完整
        if self.log_to_file and not self.log_file_path:
            return False

        return True

    @property
    def uses_color(self) -> bool:
        """检查是否启用颜色输出

        Returns:
            bool: 是否使用颜色输出
        """
        return self.color_scheme != ColorScheme.NONE

    @property
    def is_real_time(self) -> bool:
        """检查是否启用实时输出

        Returns:
            bool: 是否启用实时输出
        """
        return self.real_time_update

    @property
    def shows_partials(self) -> bool:
        """检查是否应显示部分结果

        Returns:
            bool: 是否显示部分结果
        """
        return self.output_level in [OutputLevel.VERBOSE, OutputLevel.DEBUG]

    @property
    def shows_debug(self) -> bool:
        """检查是否应显示调试信息

        Returns:
            bool: 是否显示调试信息
        """
        return self.output_level == OutputLevel.DEBUG


@dataclass
class DisplayMetrics:
    """显示和格式化指标类

    用于跟踪和统计输出显示的各种指标，包括输出数量、速率、尺寸等。
    """
    # 输出统计数据
    total_lines_output: int = 0          # 总输出行数
    total_characters_output: int = 0     # 总输出字符数
    partial_updates_count: int = 0       # 部分结果更新次数
    final_results_count: int = 0         # 最终结果数量
    average_line_length: float = 0.0     # 平均行长度

    # 时间相关指标
    last_output_time: float = field(default_factory=time.time)  # 最后输出时间
    output_rate_per_second: float = 0.0  # 每秒输出率

    # 控制台尺寸
    console_width: int = 80              # 控制台宽度
    console_height: int = 24             # 控制台高度

    @property
    def output_frequency(self) -> float:
        """计算输出频率(Hz)

        Returns:
            float: 输出频率(次/秒)
        """
        current_time = time.time()
        time_diff = current_time - self.last_output_time
        # 防止除零错误
        if time_diff > 0:
            return 1.0 / time_diff
        return 0.0

    def update_output_stats(self, line_count: int, char_count: int, is_final: bool = False) -> None:
        """更新输出统计数据

        Args:
            line_count: 输出行数
            char_count: 输出字符数
            is_final: 是否为最终结果
        """
        self.total_lines_output += line_count
        self.total_characters_output += char_count

        if is_final:
            self.final_results_count += 1
        else:
            self.partial_updates_count += 1

        # Update average line length
        if self.total_lines_output > 0:
            self.average_line_length = self.total_characters_output / self.total_lines_output

        # Update timing
        current_time = time.time()
        time_diff = current_time - self.last_output_time
        if time_diff > 0:
            self.output_rate_per_second = 1.0 / time_diff
        self.last_output_time = current_time


@dataclass
class FormattedOutput:
    """Formatted output result"""
    content: str
    format_type: OutputFormat
    timestamp: float = field(default_factory=time.time)
    is_final: bool = False
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    color_codes: List[str] = field(default_factory=list)
    line_count: int = 1
    character_count: int = 0

    def __post_init__(self):
        """Initialize derived fields"""
        if not self.character_count:
            self.character_count = len(self.content)
        if not self.line_count:
            self.line_count = self.content.count('\n') + 1

    @property
    def has_color(self) -> bool:
        """Check if output contains color codes"""
        return bool(self.color_codes)

    @property
    def display_timestamp(self) -> str:
        """Get formatted display timestamp"""
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm

    @property
    def size_bytes(self) -> int:
        """Get content size in bytes"""
        return len(self.content.encode('utf-8'))

    def add_color_code(self, code: str) -> None:
        """Add a color code"""
        if code not in self.color_codes:
            self.color_codes.append(code)

    def strip_colors(self) -> str:
        """Get content without color codes"""
        # 使用模块级别预编译的正则表达式
        return ANSI_ESCAPE.sub('', self.content)


@dataclass
class OutputBuffer:
    """Output buffer for managing display updates"""
    items: List[FormattedOutput] = field(default_factory=list)
    max_size: int = 100
    current_size: int = 0
    last_final_index: int = -1

    def add(self, output: FormattedOutput) -> None:
        """Add output to buffer"""
        self.items.append(output)
        self.current_size += 1

        # Track final results
        if output.is_final:
            self.last_final_index = len(self.items) - 1

        # Manage buffer size
        if self.current_size > self.max_size:
            self._trim_buffer()

    def _trim_buffer(self) -> None:
        """Trim buffer to maintain size limit"""
        # Keep final results and recent items
        keep_count = min(self.max_size, len(self.items))
        if self.last_final_index >= 0:
            # Keep from last final result
            start_index = max(0, self.last_final_index - keep_count // 2)
        else:
            # Keep most recent items
            start_index = len(self.items) - keep_count

        self.items = self.items[start_index:]
        self.current_size = len(self.items)

        # Update final index
        if self.last_final_index >= 0:
            self.last_final_index = max(0, self.last_final_index - start_index)

    @property
    def has_partial_results(self) -> bool:
        """Check if buffer contains partial results"""
        return any(not item.is_final for item in self.items)

    @property
    def latest_final(self) -> Optional[FormattedOutput]:
        """Get latest final result"""
        if self.last_final_index >= 0 and self.last_final_index < len(self.items):
            return self.items[self.last_final_index]
        return None

    @property
    def latest_item(self) -> Optional[FormattedOutput]:
        """Get latest item"""
        return self.items[-1] if self.items else None

    def get_recent(self, count: int = 10) -> List[FormattedOutput]:
        """Get recent items"""
        return self.items[-count:] if self.items else []

    def clear_partials(self) -> None:
        """Clear partial results, keep only finals"""
        self.items = [item for item in self.items if item.is_final]
        self.current_size = len(self.items)
        self.last_final_index = len(self.items) - 1 if self.items else -1


@dataclass
class SubtitleEntry:
    """Subtitle entry for SRT/VTT formats"""
    index: int
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None

    @property
    def duration(self) -> float:
        """Get duration in seconds"""
        return self.end_time - self.start_time

    def to_srt_format(self) -> str:
        """Convert to SRT format"""
        start = self._seconds_to_srt_time(self.start_time)
        end = self._seconds_to_srt_time(self.end_time)

        result = f"{self.index}\n"
        result += f"{start} --> {end}\n"
        result += f"{self.text}\n\n"
        return result

    def to_vtt_format(self) -> str:
        """Convert to VTT format"""
        start = self._seconds_to_vtt_time(self.start_time)
        end = self._seconds_to_vtt_time(self.end_time)

        result = f"{start} --> {end}\n"
        result += f"{self.text}\n\n"
        return result

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

    def _seconds_to_vtt_time(self, seconds: float) -> str:
        """Convert seconds to VTT time format (HH:MM:SS.mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"


# Custom exceptions
class OutputError(Exception):
    """Base exception for output errors"""
    pass


class FormattingError(OutputError):
    """Formatting error"""
    pass


class BufferOverflowError(OutputError):
    """Buffer overflow error"""
    pass


class FileOutputError(OutputError):
    """File output error"""
    pass


class ConfigurationError(OutputError):
    """Output configuration error"""
    pass