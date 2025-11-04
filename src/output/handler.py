"""
语音转录结果输出处理器

负责处理、格式化和显示语音转录结果，支持多种输出格式、实时更新和用户友好的展示方式。
提供控制台彩色输出、JSON格式化、字幕文件生成、实时屏幕字幕显示等功能。

字幕显示功能使用示例：
=====================

1. 启用字幕显示的基本用法：
   ```python
   from src.output.handler import OutputHandler
   from src.config.models import SubtitleDisplayConfig

   # 创建字幕显示配置
   subtitle_config = SubtitleDisplayConfig(
       enabled=True,                    # 启用字幕显示
       position="bottom",              # 字幕位置：top/center/bottom
       font_size=24,                   # 字体大小
       font_family="Microsoft YaHei",  # 字体
       opacity=0.8,                    # 透明度 (0.1-1.0)
       max_display_time=5.0,           # 最大显示时间(秒)
       text_color="#FFFFFF",           # 文字颜色
       background_color="#000000"      # 背景颜色
   )

   # 创建输出处理器
   handler = OutputHandler(subtitle_display_config=subtitle_config)
   handler.start()
   ```

2. 完整的命令行使用示例：
   ```bash
   # 基本字幕显示
   python main.py --model-path models/sense-voice.onnx --input-source microphone --show-subtitles

   # 自定义字幕显示参数
   python main.py \
       --model-path models/sense-voice.onnx \
       --input-source microphone \
       --show-subtitles \
       --subtitle-position bottom \
       --subtitle-font-size 24 \
       --subtitle-font-family "Microsoft YaHei" \
       --subtitle-opacity 0.9 \
       --subtitle-max-display-time 4.0

   # 字幕显示在屏幕顶部，字体更大
   python main.py \
       --model-path models/sense-voice.onnx \
       --input-source microphone \
       --show-subtitles \
       --subtitle-position top \
       --subtitle-font-size 32 \
       --subtitle-opacity 0.85
   ```

3. 编程方式使用字幕显示：
   ```python
   from src.output.handler import OutputHandler
   from src.output.models import OutputConfig, OutputFormat
   from src.config.models import SubtitleDisplayConfig
   from src.transcription.models import TranscriptionResult

   # 配置输出处理器
   output_config = OutputConfig(
       format=OutputFormat.CONSOLE,
       show_confidence=True,
       show_timestamps=True,
       real_time_update=True
   )

   # 配置字幕显示
   subtitle_config = SubtitleDisplayConfig(
       enabled=True,
       position="bottom",
       font_size=28,
       opacity=0.8
   )

   # 创建并启动输出处理器
   handler = OutputHandler(
       config=output_config,
       subtitle_display_config=subtitle_config
   )
   handler.start()

   # 模拟转录结果
   result = TranscriptionResult(
       text="这是实时语音转录的字幕内容",
       confidence=0.95,
       is_final=True,
       timestamp=time.time(),
       start_time=time.time(),
       end_time=time.time() + 2.0
   )

   # 处理结果（这将更新屏幕字幕）
   handler.process_result(result)

   # 清理资源
   handler.stop()
   ```

调试模式：
```bash
# 启用详细日志查看字幕显示状态
python main.py --model-path model.onnx --input-source microphone --show-subtitles --log-level DEBUG
```

字幕窗口特性：
==============
- 支持鼠标拖拽移动位置
- 半透明背景，不遮挡重要内容
- 自动文本换行，适应长字幕
- 根据置信度调整显示内容
- 自动隐藏机制，避免屏幕杂乱

性能优化：
==========
- 字幕更新在独立线程中执行，不阻塞转录
- 使用高效的GUI更新机制
- 智能的文本过滤和长度限制
- 优化的内存管理和资源清理
"""

# 标准库导入
import json                    # JSON格式处理
import logging                # 日志记录
import sys                    # 系统功能
import time                   # 时间处理
from datetime import datetime # 日期时间处理
from pathlib import Path      # 路径处理
from typing import List, Optional, Dict, Any, TextIO, Union  # 类型注解
import threading              # 多线程支持
from queue import Queue, Empty  # 队列和异常

# 本地模块导入
from .models import (
    OutputConfig, OutputFormat, TimestampFormat, OutputLevel, ColorScheme,  # 配置和枚举
    FormattedOutput, OutputBuffer, DisplayMetrics, SubtitleEntry,           # 数据结构
    OutputError, FormattingError, FileOutputError, ConfigurationError       # 异常类
)
from ..transcription.models import TranscriptionResult, BatchTranscriptionResult  # Transcription results

# 字幕显示组件导入 - 优先使用主模块导入，避免复杂的回退逻辑
try:
    from ..subtitle_display import SubtitleDisplay
    SUBTITLE_DISPLAY_AVAILABLE = True
    logging.debug("字幕显示组件导入成功：使用主模块")
except ImportError as e:
    SUBTITLE_DISPLAY_AVAILABLE = False
    SubtitleDisplay = None
    logging.debug(f"字幕显示组件导入失败: {e}")


class OutputHandler:
    """
    转录结果输出处理器主类

    提供全面的输出格式化功能，支持：
    - 多种输出格式 (控制台、JSON、SRT、VTT等)
    - 实时显示部分和最终结果
    - 可配置的时间戳和样式
    - 文件日志记录和缓冲
    - 彩色控制台输出
    - 字幕文件生成和导出
    """

    def __init__(self, config: Optional[OutputConfig] = None, subtitle_display_config=None):
        """
        初始化输出处理器

        Args:
            config: 输出配置对象，如果为None则使用默认配置
            subtitle_display_config: 字幕显示配置对象（可选）

        Raises:
            ConfigurationError: 配置验证失败时抛出

        初始化流程：
            1. 设置输出配置和缓冲区
            2. 初始化文件处理和队列系统
            3. 设置控制台颜色代码
            4. 初始化字幕显示组件（如果启用）
            5. 验证所有配置的有效性
        """
        # 第1步：设置基础配置和组件
        self.config = config or OutputConfig()
        self.subtitle_display_config = subtitle_display_config
        self.metrics = DisplayMetrics()                    # 显示统计信息
        self.buffer = OutputBuffer(max_size=self.config.buffer_size)  # 输出缓冲区
        self.subtitle_entries: List[SubtitleEntry] = []    # 字幕条目列表
        self.subtitle_counter = 1                         # 字幕条目计数器

        # 第2步：初始化文件处理和队列系统
        self.log_file: Optional[TextIO] = None            # 日志文件句柄
        self.output_queue: Queue = Queue()                # 异步输出队列
        self.is_running = False                           # 运行状态标志
        self.output_thread: Optional[threading.Thread] = None  # 输出处理线程
        self._lock = threading.Lock()                     # 线程安全锁

        # 第3步：设置控制台颜色代码
        self.colors = self._init_color_codes()

        # 第4步：初始化文件日志记录（如果配置启用）
        if self.config.log_to_file:
            self._init_file_logging()

        # 第5步：初始化字幕显示组件
        self.subtitle_display = None
        self._init_subtitle_display()

        # 第6步：验证所有配置的有效性
        if not self.config.validate():
            raise ConfigurationError("Invalid output configuration")

        # 记录初始化完成信息
        logging.info(f"OutputHandler初始化完成 - 字幕显示: {'启用' if self.subtitle_display else '禁用'}")

    def _init_subtitle_display(self) -> None:
        """
        初始化字幕显示组件，包含详细的错误处理和日志记录

        初始化策略：
            1. 验证字幕显示配置是否存在且启用
            2. 检查字幕显示模块是否可用
            3. 验证字幕显示配置的有效性
            4. 创建字幕显示组件实例
            5. 处理各种可能的初始化错误

        异常处理：
            - 配置缺失：跳过字幕显示初始化
            - 模块不可用：记录警告并跳过
            - 配置无效：记录错误并跳过
            - 初始化失败：记录详细错误信息并提供解决建议
        """
        # 第1步：检查字幕显示配置是否存在且启用
        if not self.subtitle_display_config:
            logging.debug("字幕显示配置未提供，跳过字幕显示初始化")
            return

        if not self.subtitle_display_config.enabled:
            logging.debug("字幕显示功能未启用，跳过初始化")
            return

        # 第2步：检查字幕显示模块是否可用
        if not SUBTITLE_DISPLAY_AVAILABLE:
            logging.warning("字幕显示模块不可用，无法启用屏幕字幕显示功能")
            logging.info("建议：请检查字幕显示模块是否正确安装")
            return

        # 第3步：验证字幕显示配置的有效性
        try:
            self.subtitle_display_config.validate()
            logging.debug("字幕显示配置验证通过")
        except Exception as e:
            logging.error(f"字幕显示配置验证失败: {e}")
            logging.warning("字幕显示功能将不可用，请检查配置参数")
            return

        # 第4步：创建字幕显示组件实例
        try:
            logging.info("正在初始化字幕显示组件...")
            logging.debug(f"字幕配置: 位置={self.subtitle_display_config.position}, "
                         f"字体={self.subtitle_display_config.font_family}, "
                         f"大小={self.subtitle_display_config.font_size}px, "
                         f"透明度={self.subtitle_display_config.opacity}")

            # 创建字幕显示组件
            self.subtitle_display = SubtitleDisplay(self.subtitle_display_config)

            logging.info("字幕显示组件初始化成功")
            logging.info(f"字幕窗口位置: {self.subtitle_display_config.position}")

        except ImportError as e:
            logging.error(f"字幕显示组件导入失败: {e}")
            logging.warning("建议：检查tkinter安装是否完整")
            self.subtitle_display = None

        except Exception as e:
            logging.error(f"字幕显示组件初始化失败: {e}")
            self._handle_subtitle_display_error(e, "初始化")
            self.subtitle_display = None

    def _handle_subtitle_display_error(self, error: Exception, context: str) -> None:
        """
        统一的字幕显示错误处理，提供详细的错误信息和解决建议

        Args:
            error: 发生的异常对象
            context: 错误发生的上下文（如"初始化"、"显示字幕"等）

        错误处理策略：
            - ImportError：提供tkinter安装建议
            - ComponentInitializationError：提供系统环境检查建议
            - 其他异常：提供通用故障排除建议
        """
        error_msg = f"字幕显示错误 - {context}: {error}"
        logging.error(error_msg)

        # 根据错误类型提供具体的解决建议
        error_str = str(error).lower()

        if "tkinter" in error_str or "import" in error_str:
            logging.warning("可能的解决方案:")
            logging.warning("  1. 确认系统已安装tkinter (Python自带)")
            logging.warning("  2. Linux系统可能需要: sudo apt-get install python3-tk")
            logging.warning("  3. 重新安装Python或检查环境配置")

        elif "display" in error_str or "gui" in error_str:
            logging.warning("可能的解决方案:")
            logging.warning("  1. 检查系统是否支持图形界面")
            logging.warning("  2. 确认当前用户有权限创建窗口")
            logging.warning("  3. 检查显示器配置和分辨率设置")

        elif "font" in error_str:
            logging.warning("可能的解决方案:")
            logging.warning("  1. 确认系统已安装指定字体")
            logging.warning("  2. 使用系统默认字体，如：Arial, Times New Roman")
            logging.warning("  3. 检查字体文件权限和路径")

        else:
            logging.warning("通用解决方案:")
            logging.warning("  1. 检查系统资源使用情况")
            logging.warning("  2. 尝试重启应用程序")
            logging.warning("  3. 如问题持续，请提供详细错误日志")

    def _validate_subtitle_config(self, config) -> bool:
        """
        验证字幕显示配置的有效性，包含系统环境检查

        Args:
            config: 字幕显示配置对象

        Returns:
            bool: 配置是否有效

        验证内容：
            1. 配置对象的基本验证
            2. tkinter可用性检查
            3. 字体可用性检查
            4. 显示参数合理性检查
        """
        try:
            # 基本配置验证
            if not config:
                logging.debug("字幕显示配置为空")
                return False

            if not config.enabled:
                logging.debug("字幕显示功能未启用")
                return False

            # 调用配置自身的验证方法
            config.validate()

            # 检查系统环境
            if not self._check_tkinter_availability():
                logging.warning("系统不支持tkinter，字幕显示功能不可用")
                return False

            # 检查字体可用性
            if not self._check_font_availability(config.font_family):
                logging.warning(f"字体 {config.font_family} 不可用，使用默认字体")
                config.font_family = "Arial"

            return True

        except Exception as e:
            logging.error(f"字幕显示配置验证失败: {e}")
            return False

    def _check_tkinter_availability(self) -> bool:
        """
        检查tkinter是否可用

        Returns:
            bool: tkinter是否可用
        """
        try:
            import tkinter
            # 尝试创建一个简单的测试窗口
            test_root = tkinter.Tk()
            test_root.withdraw()  # 隐藏测试窗口
            test_root.destroy()
            return True
        except Exception as e:
            logging.debug(f"tkinter不可用: {e}")
            return False

    def _check_font_availability(self, font_family: str) -> bool:
        """
        检查指定字体是否可用

        Args:
            font_family: 字体名称

        Returns:
            bool: 字体是否可用
        """
        try:
            import tkinter.font as tkFont
            # 尝试创建字体对象来检查可用性
            test_font = tkFont.Font(family=font_family, size=12)
            # 获取实际使用的字体名称
            actual_font = test_font.actual()["family"]
            return actual_font.lower() == font_family.lower() or actual_font in ["arial", "times", "courier"]
        except Exception:
            return False

    def _test_subtitle_display_functionality(self) -> bool:
        """
        测试字幕显示功能是否正常工作

        Returns:
            bool: 字幕显示功能是否正常

        测试流程：
            1. 检查字幕显示组件是否存在
            2. 尝试显示测试文本
            3. 检查窗口是否正确创建
            4. 清理测试内容
        """
        if not self.subtitle_display:
            return False

        try:
            # 显示测试文本
            test_text = "字幕显示测试"
            self.subtitle_display.show_subtitle(test_text, 1.0)

            # 等待短暂时间让窗口显示
            import time
            time.sleep(0.1)

            # 检查窗口是否可见
            if self.subtitle_display.is_visible():
                logging.info("字幕显示功能测试通过")
                # 清除测试文本
                self.subtitle_display.clear_subtitle()
                return True
            else:
                logging.warning("字幕显示功能测试失败：窗口不可见")
                return False

        except Exception as e:
            logging.error(f"字幕显示功能测试失败: {e}")
            return False

    def _init_color_codes(self) -> Dict[str, str]:
        """根据颜色方案初始化控制台颜色代码"""
        if not self.config.uses_color:
            return {key: "" for key in ['reset', 'final', 'partial', 'timestamp', 'confidence', 'error', 'info']}

        if self.config.color_scheme == ColorScheme.BASIC:
            return {
                'reset': '\033[0m',
                'final': '\033[92m',      # Bright green
                'partial': '\033[93m',     # Yellow
                'timestamp': '\033[94m',   # Blue
                'confidence': '\033[96m',  # Cyan
                'error': '\033[91m',       # Red
                'info': '\033[95m'         # Magenta
            }
        elif self.config.color_scheme == ColorScheme.RICH:
            return {
                'reset': '\033[0m',
                'final': '\033[1;32m',     # Bold green
                'partial': '\033[0;33m',   # Yellow
                'timestamp': '\033[0;36m', # Cyan
                'confidence': '\033[0;35m',# Magenta
                'error': '\033[1;31m',     # Bold red
                'info': '\033[0;34m'       # Blue
            }
        else:
            # Default to basic colors
            return {
                'reset': '\033[0m',
                'final': '\033[92m',      # Bright green
                'partial': '\033[93m',     # Yellow
                'timestamp': '\033[94m',   # Blue
                'confidence': '\033[96m',  # Cyan
                'error': '\033[91m',       # Red
                'info': '\033[95m'         # Magenta
            }

    def _init_file_logging(self) -> None:
        """Initialize file logging"""
        try:
            log_path = Path(self.config.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_file = open(log_path, 'a', encoding='utf-8')
        except Exception as e:
            raise FileOutputError(f"Failed to initialize log file: {e}")

    def start(self) -> None:
        """
        启动输出处理器和相关组件

        启动流程：
            1. 检查是否已经在运行状态，避免重复启动
            2. 设置运行状态标志
            3. 启动字幕显示组件（如果已初始化）
            4. 启动异步输出处理线程（如果配置了实时更新）

        异常处理：
            - 字幕显示启动失败：记录错误但不影响主要功能
            - 输出线程启动失败：使用同步模式作为降级方案
        """
        # 第1步：检查是否已经在运行状态
        if self.is_running:
            logging.debug("OutputHandler已经在运行状态，跳过启动")
            return

        # 第2步：设置运行状态标志
        self.is_running = True
        logging.info("正在启动OutputHandler...")

        # 第3步：启动字幕显示组件
        if self.subtitle_display:
            try:
                logging.debug("正在启动字幕显示组件...")
                self.subtitle_display.start()
                logging.info("字幕显示组件已启动")

                # 可选：执行功能测试
                if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                    self._test_subtitle_display_functionality()

            except Exception as e:
                logging.error(f"启动字幕显示组件失败: {e}")
                self._handle_subtitle_display_error(e, "启动")
                # 注意：字幕显示失败不影响主要转录功能

        # 第4步：启动异步输出处理线程（如果需要）
        if self.config.real_time_update:
            try:
                logging.debug("正在启动异步输出处理线程...")
                self.output_thread = threading.Thread(
                    target=self._output_worker,
                    daemon=True,
                    name="OutputWorker"
                )
                self.output_thread.start()
                logging.debug("异步输出处理线程已启动")
            except Exception as e:
                logging.error(f"启动异步输出线程失败: {e}")
                logging.warning("将使用同步输出模式")
                # 降级为同步模式，继续运行

        logging.info("OutputHandler启动完成")

    def stop(self) -> None:
        """
        停止输出处理器并清理所有相关资源

        停止流程：
            1. 设置停止标志，通知所有组件准备停止
            2. 等待异步输出线程正常结束
            3. 停止字幕显示组件并清理窗口资源
            4. 关闭日志文件并清理文件句柄

        异常处理：
            - 线程停止超时：强制标记为停止，避免程序阻塞
            - 字幕显示停止失败：记录错误但继续清理其他资源
            - 文件关闭失败：记录错误，文件句柄会被垃圾回收
        """
        # 第1步：设置停止标志
        logging.info("正在停止OutputHandler...")
        self.is_running = False

        # 第2步：等待异步输出线程正常结束
        if self.output_thread and self.output_thread.is_alive():
            try:
                logging.debug("正在等待异步输出线程结束...")
                self.output_thread.join(timeout=2.0)  # 增加超时时间

                if self.output_thread.is_alive():
                    logging.warning("异步输出线程未能在指定时间内结束")
                else:
                    logging.debug("异步输出线程已正常结束")

            except Exception as e:
                logging.error(f"停止异步输出线程时发生错误: {e}")

        # 第3步：停止字幕显示组件
        if self.subtitle_display:
            try:
                logging.debug("正在停止字幕显示组件...")
                self.subtitle_display.stop()
                logging.info("字幕显示组件已停止")
            except Exception as e:
                logging.error(f"停止字幕显示组件失败: {e}")
                self._handle_subtitle_display_error(e, "停止")

        # 第4步：关闭日志文件
        if self.log_file:
            try:
                logging.debug("正在关闭日志文件...")
                self.log_file.close()
                logging.debug("日志文件已关闭")
            except Exception as e:
                logging.error(f"关闭日志文件失败: {e}")
            finally:
                self.log_file = None

        logging.info("OutputHandler已停止")

    def _output_worker(self) -> None:
        """Background worker for real-time output processing"""
        while self.is_running:
            try:
                # Process queued outputs with timeout
                output = self.output_queue.get(timeout=0.1)
                self._display_output(output)
                self.output_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logging.error(f"Output worker error: {e}")

    def process_result(self, result: TranscriptionResult) -> None:
        """
        处理单个转录结果，包含格式化、显示和字幕更新

        Args:
            result: 包含转录文本、置信度、时间戳等信息的转录结果对象

        处理流程：
            1. 根据配置格式化转录结果
            2. 将结果添加到输出缓冲区（支持内存管理）
            3. 更新显示统计信息（用于性能监控）
            4. 如果是最终结果，生成字幕条目（用于文件导出）
            5. 如果启用了字幕显示，更新屏幕字幕（实时显示功能）
            6. 根据配置选择输出方式（同步或异步）

        异常处理：
            - 转录结果格式化失败：记录错误，继续处理
            - 字幕显示失败：记录警告，不影响主要功能
            - 输出失败：根据输出级别决定是否显示错误
            - 整体处理异常：记录详细错误信息，调试模式下显示给用户

        性能考虑：
            - 字幕显示操作在独立线程中执行，不阻塞主流程
            - 使用缓冲区管理内存，避免无限增长
            - 异步输出处理提高实时性能
        """
        try:
            # 第1步：格式化转录结果
            formatted = self._format_result(result)

            # 第2步：添加到缓冲区（支持内存管理）
            self.buffer.add(formatted)

            # 第3步：更新统计信息（用于性能监控）
            self.metrics.update_output_stats(
                formatted.line_count,        # 输出行数
                formatted.character_count,   # 字符数
                result.is_final             # 是否为最终结果
            )

            # 第4步：处理字幕生成（用于文件导出）
            if result.is_final and result.end_time:
                self._add_subtitle_entry(result)

            # 第5步：更新屏幕字幕显示（实时显示功能）
            self._update_screen_subtitle(result)

            # 第6步：根据配置选择输出方式
            if self._should_display_result(result):
                if self.config.real_time_update and self.is_running:
                    # 异步输出（适用于实时场景，避免阻塞）
                    self.output_queue.put(formatted)
                else:
                    # 同步输出（适用于简单场景）
                    self._display_output(formatted)

        except Exception as e:
            # 记录处理错误，避免程序崩溃
            logging.error(f"处理转录结果时发生错误: {e}")

            # 在调试模式下显示详细错误信息
            if self.config.output_level == OutputLevel.DEBUG:
                self._display_error(f"处理错误: {e}")

            # 重要：即使单个结果处理失败，也不应影响后续处理
            # 继续处理下一个结果，保持系统稳定性

    def _update_screen_subtitle(self, result: TranscriptionResult) -> None:
        """
        更新屏幕字幕显示，包含详细的错误处理和状态检查

        Args:
            result: 转录结果对象

        显示条件：
            1. 字幕显示组件已成功初始化
            2. 结果为最终转录结果（排除中间结果）
            3. 结果包含有效文本内容（排除空结果）
            4. 字幕显示组件当前处于运行状态

        线程安全：
            - 字幕显示操作本身是线程安全的
            - 使用after方法调度GUI更新到主线程
            - 任何线程都可以安全调用此方法

        错误处理：
            - 组件未初始化：静默跳过，避免日志噪音
            - 显示失败：记录警告，不影响转录功能
            - 线程错误：捕获并处理所有可能的异常
        """
        # 检查字幕显示基本条件
        if not self.subtitle_display:
            # 字幕显示组件未初始化，这在配置中是正常的
            return

        # 检查结果有效性
        if not result.is_final:
            # 仅显示最终结果，避免中间结果造成闪烁
            logging.debug(f"跳过中间结果: {result.text[:50]}...")
            return

        if not result.text or result.text.strip() == "":
            # 空结果不显示，避免界面闪烁
            return

        # 执行字幕显示操作
        try:
            # 显示字幕文本和置信度
            self.subtitle_display.show_subtitle(
                text=result.text,
                confidence=result.confidence
            )

            # 记录调试信息（仅在DEBUG级别）
            if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                logging.debug(f"字幕已更新: \"{result.text[:50]}...\" "
                             f"(置信度: {result.confidence:.2f})")

        except Exception as e:
            # 字幕显示失败不应影响转录功能，仅记录警告
            logging.warning(f"屏幕字幕显示失败: {e}")

            # 在调试模式下提供更详细的错误信息
            if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                logging.debug(f"字幕显示详情 - 文本: \"{result.text[:30]}...\", "
                             f"置信度: {result.confidence:.2f}, "
                             f"组件状态: {self.subtitle_display.is_running if hasattr(self.subtitle_display, 'is_running') else '未知'}")

            # 尝试重新初始化字幕显示组件（可选的恢复策略）
            self._try_recover_subtitle_display(e)

    def _try_recover_subtitle_display(self, original_error: Exception) -> None:
        """
        尝试恢复字幕显示功能

        Args:
            original_error: 导致恢复的原始错误

        恢复策略：
            1. 检查组件是否仍然存在
            2. 尝试停止并重新启动组件
            3. 如果恢复失败，禁用字幕显示以避免持续错误

        注意：此方法是可选的恢复机制，仅在严重错误时调用
        """
        try:
            logging.info("尝试恢复字幕显示功能...")

            if self.subtitle_display and hasattr(self.subtitle_display, 'stop'):
                # 尝试停止当前组件
                self.subtitle_display.stop()

                # 短暂等待后重新启动
                import time
                time.sleep(0.1)

                self.subtitle_display.start()
                logging.info("字幕显示功能恢复成功")

        except Exception as recovery_error:
            logging.warning(f"字幕显示功能恢复失败: {recovery_error}")
            logging.info("将禁用字幕显示功能以避免持续错误")

            # 禁用字幕显示以避免持续的错误日志
            self.subtitle_display = None

    def process_batch(self, batch: BatchTranscriptionResult) -> None:
        """
        Process a batch of transcription results

        Args:
            batch: Batch transcription result to process
        """
        for result in batch.results:
            self.process_result(result)

        # Display batch summary if configured
        if self.config.include_metadata and self.config.output_level in [OutputLevel.VERBOSE, OutputLevel.DEBUG]:
            self._display_batch_summary(batch)

    def _should_display_result(self, result: TranscriptionResult) -> bool:
        """Determine if result should be displayed based on configuration"""
        if result.is_final:
            return True

        if self.config.output_level == OutputLevel.MINIMAL:
            return False
        elif self.config.output_level == OutputLevel.NORMAL:
            return not result.is_partial or result.confidence > 0.7
        else:  # VERBOSE or DEBUG
            return True

    def _format_result(self, result: TranscriptionResult) -> FormattedOutput:
        """Format a transcription result according to configuration"""
        try:
            if self.config.format == OutputFormat.CONSOLE:
                content = self._format_console_output(result)
            elif self.config.format == OutputFormat.JSON:
                content = self._format_json_output(result)
            elif self.config.format == OutputFormat.PLAIN_TEXT:
                content = self._format_plain_text_output(result)
            else:
                content = self._format_console_output(result)  # Fallback

            return FormattedOutput(
                content=content,
                format_type=self.config.format,
                is_final=result.is_final,
                confidence=result.confidence,
                metadata={
                    'start_time': result.start_time,
                    'end_time': result.end_time,
                    'duration_ms': result.duration_ms,
                    'processing_time_ms': result.processing_time_ms,
                    'language': result.language,
                    'word_count': result.word_count
                }
            )
        except Exception as e:
            raise FormattingError(f"Failed to format result: {e}")

    def _format_console_output(self, result: TranscriptionResult) -> str:
        """Format result for console display"""
        parts = []

        # Timestamp
        if self.config.show_timestamps:
            timestamp = self._format_timestamp(result.start_time)
            parts.append(f"{self.colors['timestamp']}[{timestamp}]{self.colors['reset']}")

        # Confidence indicator
        if self.config.show_confidence and result.confidence > 0:
            confidence_str = f"({result.confidence:.2f})"
            parts.append(f"{self.colors['confidence']}{confidence_str}{self.colors['reset']}")

        # Text with styling
        if result.is_final:
            text_color = self.colors['final']
            prefix = "> " if self.config.highlight_final else ""
        else:
            text_color = self.colors['partial']
            prefix = "  " if self.config.indent_partial else ""

        text = f"{text_color}{prefix}{result.text}{self.colors['reset']}"
        parts.append(text)

        # Processing info
        if self.config.show_processing_info and result.processing_time_ms > 0:
            proc_info = f"({result.processing_time_ms:.1f}ms)"
            parts.append(f"{self.colors['info']}{proc_info}{self.colors['reset']}")

        # Language info
        if self.config.language_display and result.language:
            lang_info = f"[{result.language}]"
            parts.append(f"{self.colors['info']}{lang_info}{self.colors['reset']}")

        return " ".join(parts)

    def _format_json_output(self, result: TranscriptionResult) -> str:
        """Format result as JSON"""
        data = {
            'text': result.text,
            'confidence': result.confidence,
            'start_time': result.start_time,
            'end_time': result.end_time,
            'duration_ms': result.duration_ms,
            'is_final': result.is_final,
            'is_partial': result.is_partial,
            'timestamp': result.timestamp,
            'language': result.language,
            'processing_time_ms': result.processing_time_ms
        }

        if self.config.show_word_timestamps and result.has_word_timestamps:
            data['word_timestamps'] = result.word_timestamps

        return json.dumps(data, ensure_ascii=False, indent=2 if self.config.output_level == OutputLevel.DEBUG else None)

    def _format_plain_text_output(self, result: TranscriptionResult) -> str:
        """Format result as plain text"""
        if self.config.show_timestamps:
            timestamp = self._format_timestamp(result.start_time)
            return f"[{timestamp}] {result.text}"
        else:
            return result.text

    def _format_timestamp(self, timestamp: float) -> str:
        """Format timestamp according to configuration"""
        if self.config.timestamp_format == TimestampFormat.ABSOLUTE:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif self.config.timestamp_format == TimestampFormat.RELATIVE:
            minutes = int(timestamp // 60)
            seconds = timestamp % 60
            return f"{minutes:02d}:{seconds:06.3f}"
        elif self.config.timestamp_format == TimestampFormat.UNIX:
            return f"{timestamp:.3f}"
        elif self.config.timestamp_format == TimestampFormat.ISO8601:
            dt = datetime.fromtimestamp(timestamp)
            return dt.isoformat()
        else:
            return f"{timestamp:.3f}"

    def _display_output(self, output: FormattedOutput) -> None:
        """Display formatted output to console and/or file"""
        with self._lock:
            # Console output
            print(output.content, flush=True)

            # File logging
            if self.log_file:
                try:
                    timestamp = datetime.now().isoformat()
                    self.log_file.write(f"[{timestamp}] {output.strip_colors()}\n")
                    self.log_file.flush()
                except Exception as e:
                    logging.error(f"File logging error: {e}")

    def _display_error(self, message: str) -> None:
        """Display error message"""
        error_output = f"{self.colors['error']}ERROR: {message}{self.colors['reset']}"
        print(error_output, file=sys.stderr, flush=True)

    def _display_batch_summary(self, batch: BatchTranscriptionResult) -> None:
        """Display batch processing summary"""
        summary_parts = [
            f"{self.colors['info']}--- Batch Summary ---{self.colors['reset']}",
            f"Results: {batch.result_count}",
            f"Final: {batch.final_results_count}",
            f"Partial: {batch.partial_results_count}",
            f"Average confidence: {batch.average_confidence:.3f}",
            f"Total text: {len(batch.total_text)} chars",
            f"Processing RTF: {batch.processing_real_time_factor:.3f}",
            f"{self.colors['info']}--- End Summary ---{self.colors['reset']}"
        ]

        summary = "\n".join(summary_parts)
        print(summary, flush=True)

    def _add_subtitle_entry(self, result: TranscriptionResult) -> None:
        """Add a subtitle entry for final results"""
        if not result.is_final or not result.end_time or result.is_empty:
            return

        entry = SubtitleEntry(
            index=self.subtitle_counter,
            start_time=result.start_time,
            end_time=result.end_time,
            text=result.text,
            confidence=result.confidence
        )

        self.subtitle_entries.append(entry)
        self.subtitle_counter += 1

    def export_subtitles(self, file_path: str, format_type: str = "srt") -> None:
        """
        Export subtitles to file

        Args:
            file_path: Output file path
            format_type: Subtitle format ('srt' or 'vtt')
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                if format_type.lower() == "srt":
                    self._write_srt_file(f)
                elif format_type.lower() == "vtt":
                    self._write_vtt_file(f)
                else:
                    raise ValueError(f"Unsupported subtitle format: {format_type}")

        except Exception as e:
            raise FileOutputError(f"Failed to export subtitles: {e}")

    def _write_srt_file(self, file: TextIO) -> None:
        """Write SRT format subtitle file"""
        for entry in self.subtitle_entries:
            file.write(entry.to_srt_format())

    def _write_vtt_file(self, file: TextIO) -> None:
        """Write VTT format subtitle file"""
        file.write("WEBVTT\n\n")
        for entry in self.subtitle_entries:
            file.write(entry.to_vtt_format())

    def get_statistics(self) -> Dict[str, Any]:
        """Get output processing statistics"""
        return {
            'display_metrics': {
                'total_lines_output': self.metrics.total_lines_output,
                'total_characters_output': self.metrics.total_characters_output,
                'partial_updates_count': self.metrics.partial_updates_count,
                'final_results_count': self.metrics.final_results_count,
                'average_line_length': self.metrics.average_line_length,
                'output_rate_per_second': self.metrics.output_rate_per_second
            },
            'buffer_info': {
                'buffer_size': self.buffer.current_size,
                'has_partials': self.buffer.has_partial_results,
                'latest_final_available': self.buffer.latest_final is not None
            },
            'subtitle_info': {
                'total_entries': len(self.subtitle_entries),
                'total_duration': sum(entry.duration for entry in self.subtitle_entries)
            },
            'configuration': {
                'format': self.config.format.value,
                'timestamp_format': self.config.timestamp_format.value,
                'output_level': self.config.output_level.value,
                'real_time_enabled': self.config.real_time_update,
                'color_enabled': self.config.uses_color
            }
        }

    def clear_buffer(self) -> None:
        """Clear output buffer"""
        with self._lock:
            self.buffer = OutputBuffer(max_size=self.config.buffer_size)

    def clear_subtitles(self) -> None:
        """Clear subtitle entries"""
        with self._lock:
            self.subtitle_entries.clear()
            self.subtitle_counter = 1

    def update_config(self, new_config: OutputConfig) -> None:
        """
        Update output configuration

        Args:
            new_config: New configuration to apply
        """
        if not new_config.validate():
            raise ConfigurationError("Invalid output configuration")

        with self._lock:
            self.config = new_config
            self.buffer.max_size = new_config.buffer_size
            self.colors = self._init_color_codes()

            # Reinitialize file logging if needed
            if new_config.log_to_file and new_config.log_file_path != (self.config.log_file_path if hasattr(self, 'config') else ''):
                if self.log_file:
                    self.log_file.close()
                self._init_file_logging()

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()