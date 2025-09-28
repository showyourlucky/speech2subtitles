"""
统一日志系统

提供分级日志记录、多种输出目标和性能监控功能
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import threading
import traceback
from dataclasses import dataclass
from enum import Enum


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogConfig:
    """日志配置"""
    level: LogLevel = LogLevel.INFO
    console_enabled: bool = True
    file_enabled: bool = False
    file_path: Optional[Path] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format_template: str = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    date_format: str = '%Y-%m-%d %H:%M:%S'
    encoding: str = 'utf-8'
    performance_logging: bool = False


class PerformanceTimer:
    """性能计时器"""

    def __init__(self, logger: logging.Logger, operation_name: str):
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"[性能] 开始 {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            if exc_type:
                self.logger.warning(f"[性能] {self.operation_name} 异常完成，耗时: {duration:.3f}s")
            else:
                self.logger.debug(f"[性能] {self.operation_name} 完成，耗时: {duration:.3f}s")


class SpeechTranscriptionFormatter(logging.Formatter):
    """语音转录系统专用格式化器"""

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)

    def format(self, record):
        # 为不同的日志级别添加颜色标记（如果支持的话）
        level_colors = {
            'DEBUG': '\033[36m',    # 青色
            'INFO': '\033[32m',     # 绿色
            'WARNING': '\033[33m',  # 黄色
            'ERROR': '\033[31m',    # 红色
            'CRITICAL': '\033[35m', # 紫色
        }

        # 添加组件标识
        if hasattr(record, 'component'):
            record.name = f"{record.component}.{record.name}"

        formatted = super().format(record)

        # 如果是控制台输出且支持颜色，添加颜色
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            color = level_colors.get(record.levelname, '')
            if color:
                formatted = f"{color}{formatted}\033[0m"

        return formatted


class LoggerManager:
    """日志管理器

    提供统一的日志配置和管理功能
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._config: Optional[LogConfig] = None
        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: List[logging.Handler] = []
        self._performance_stats: Dict[str, List[float]] = {}
        self._initialized = True

    def setup(self, config: LogConfig):
        """
        设置日志系统

        Args:
            config: 日志配置
        """
        self._config = config

        # 清理现有处理器
        self._cleanup_handlers()

        # 创建格式化器
        formatter = SpeechTranscriptionFormatter(
            fmt=config.format_template,
            datefmt=config.date_format
        )

        # 控制台处理器
        if config.console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self._handlers.append(console_handler)

        # 文件处理器
        if config.file_enabled and config.file_path:
            self._setup_file_handler(config, formatter)

        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.level.value))

        for handler in self._handlers:
            root_logger.addHandler(handler)

        # 设置第三方库日志级别
        self._configure_third_party_loggers()

        # 记录初始化信息
        logger = self.get_logger("LoggerManager")
        logger.info(f"日志系统初始化完成 - 级别: {config.level.value}")
        if config.file_enabled:
            logger.info(f"日志文件: {config.file_path}")

    def _setup_file_handler(self, config: LogConfig, formatter: logging.Formatter):
        """设置文件处理器"""
        try:
            # 确保日志目录存在
            config.file_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用轮转文件处理器
            file_handler = logging.handlers.RotatingFileHandler(
                filename=config.file_path,
                maxBytes=config.max_file_size,
                backupCount=config.backup_count,
                encoding=config.encoding
            )

            file_handler.setFormatter(formatter)
            self._handlers.append(file_handler)

        except Exception as e:
            # 如果文件处理器设置失败，记录到控制台
            console_logger = logging.getLogger("LoggerManager")
            console_logger.error(f"文件日志处理器设置失败: {e}")

    def _configure_third_party_loggers(self):
        """配置第三方库的日志级别"""
        third_party_loggers = {
            'pyaudio': logging.WARNING,
            'onnxruntime': logging.WARNING,
            'torch': logging.WARNING,
            'transformers': logging.WARNING,
            'numba': logging.WARNING,
            'matplotlib': logging.WARNING,
        }

        for logger_name, level in third_party_loggers.items():
            logging.getLogger(logger_name).setLevel(level)

    def _cleanup_handlers(self):
        """清理现有的处理器"""
        root_logger = logging.getLogger()

        # 移除我们添加的处理器
        for handler in self._handlers:
            root_logger.removeHandler(handler)
            handler.close()

        self._handlers.clear()

    def get_logger(self, name: str, component: Optional[str] = None) -> logging.Logger:
        """
        获取日志器

        Args:
            name: 日志器名称
            component: 组件名称（用于标识）

        Returns:
            logging.Logger: 配置好的日志器
        """
        logger_key = f"{component}.{name}" if component else name

        if logger_key not in self._loggers:
            logger = logging.getLogger(logger_key)

            # 添加组件信息
            if component:
                # 创建适配器来添加组件信息
                class ComponentAdapter(logging.LoggerAdapter):
                    def process(self, msg, kwargs):
                        return msg, kwargs

                # 为原始记录添加组件标识
                original_handle = logger.handle
                def handle_with_component(record):
                    record.component = component
                    return original_handle(record)
                logger.handle = handle_with_component

            self._loggers[logger_key] = logger

        return self._loggers[logger_key]

    def get_performance_timer(self, logger: logging.Logger, operation_name: str) -> PerformanceTimer:
        """
        获取性能计时器

        Args:
            logger: 日志器
            operation_name: 操作名称

        Returns:
            PerformanceTimer: 性能计时器
        """
        return PerformanceTimer(logger, operation_name)

    def log_performance_stats(self, operation_name: str, duration: float):
        """
        记录性能统计

        Args:
            operation_name: 操作名称
            duration: 执行时间（秒）
        """
        if not self._config or not self._config.performance_logging:
            return

        if operation_name not in self._performance_stats:
            self._performance_stats[operation_name] = []

        self._performance_stats[operation_name].append(duration)

        # 保持最近100条记录
        if len(self._performance_stats[operation_name]) > 100:
            self._performance_stats[operation_name] = self._performance_stats[operation_name][-100:]

    def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """
        获取性能摘要

        Returns:
            Dict: 性能统计摘要
        """
        summary = {}

        for operation, times in self._performance_stats.items():
            if times:
                summary[operation] = {
                    'count': len(times),
                    'avg': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'total': sum(times)
                }

        return summary

    def shutdown(self):
        """关闭日志系统"""
        logger = self.get_logger("LoggerManager")
        logger.info("日志系统关闭")

        # 输出性能摘要
        if self._performance_stats and self._config and self._config.performance_logging:
            summary = self.get_performance_summary()
            if summary:
                logger.info("性能统计摘要:")
                for operation, stats in summary.items():
                    logger.info(f"  {operation}: 平均 {stats['avg']:.3f}s, "
                              f"最小 {stats['min']:.3f}s, 最大 {stats['max']:.3f}s, "
                              f"总计 {stats['count']} 次")

        self._cleanup_handlers()


# 全局日志管理器实例
_logger_manager = LoggerManager()


def setup_logging(config: LogConfig):
    """
    设置全局日志系统

    Args:
        config: 日志配置
    """
    _logger_manager.setup(config)


def get_logger(name: str, component: Optional[str] = None) -> logging.Logger:
    """
    获取日志器

    Args:
        name: 日志器名称
        component: 组件名称

    Returns:
        logging.Logger: 配置好的日志器
    """
    return _logger_manager.get_logger(name, component)


def get_performance_timer(logger: logging.Logger, operation_name: str) -> PerformanceTimer:
    """
    获取性能计时器

    Args:
        logger: 日志器
        operation_name: 操作名称

    Returns:
        PerformanceTimer: 性能计时器
    """
    return _logger_manager.get_performance_timer(logger, operation_name)


def log_performance_stats(operation_name: str, duration: float):
    """
    记录性能统计

    Args:
        operation_name: 操作名称
        duration: 执行时间（秒）
    """
    _logger_manager.log_performance_stats(operation_name, duration)


def get_performance_summary() -> Dict[str, Dict[str, float]]:
    """
    获取性能摘要

    Returns:
        Dict: 性能统计摘要
    """
    return _logger_manager.get_performance_summary()


def shutdown_logging():
    """关闭日志系统"""
    _logger_manager.shutdown()