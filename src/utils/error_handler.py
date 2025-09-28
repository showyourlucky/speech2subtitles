"""
统一错误处理系统

提供异常管理、错误恢复和状态监控功能
"""

import logging
import traceback
import sys
import functools
import threading
from typing import Optional, Callable, Dict, Any, List, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import inspect


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"           # 可忽略的错误，不影响主要功能
    MEDIUM = "medium"     # 部分功能受影响，但系统可继续运行
    HIGH = "high"         # 主要功能受影响，需要立即处理
    CRITICAL = "critical" # 系统无法继续运行


class ErrorCategory(Enum):
    """错误类别"""
    HARDWARE = "hardware"           # 硬件相关错误（GPU、音频设备等）
    NETWORK = "network"            # 网络相关错误
    FILE_SYSTEM = "file_system"    # 文件系统错误
    CONFIGURATION = "configuration" # 配置错误
    MODEL = "model"                # 模型加载/推理错误
    AUDIO = "audio"                # 音频处理错误
    TRANSCRIPTION = "transcription" # 转录过程错误
    SYSTEM = "system"              # 系统级错误
    UNKNOWN = "unknown"            # 未知错误


@dataclass
class ErrorContext:
    """错误上下文信息"""
    component: str                          # 组件名称
    function_name: str                      # 函数名称
    file_path: str                          # 文件路径
    line_number: int                        # 行号
    local_variables: Dict[str, Any] = field(default_factory=dict)  # 局部变量
    thread_id: int = field(default_factory=lambda: threading.get_ident())  # 线程ID
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳


@dataclass
class ErrorRecord:
    """错误记录"""
    exception: Exception                    # 异常对象
    severity: ErrorSeverity                # 严重程度
    category: ErrorCategory                # 错误类别
    context: ErrorContext                  # 错误上下文
    user_message: str                      # 用户友好的错误消息
    developer_message: str                 # 开发者消息
    recovery_suggestion: Optional[str] = None  # 恢复建议
    is_recoverable: bool = True            # 是否可恢复
    retry_count: int = 0                   # 重试次数
    handled: bool = False                  # 是否已处理


class SpeechTranscriptionError(Exception):
    """语音转录系统基础异常"""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        recovery_suggestion: Optional[str] = None,
        is_recoverable: bool = True,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.severity = severity
        self.category = category
        self.recovery_suggestion = recovery_suggestion
        self.is_recoverable = is_recoverable
        self.original_exception = original_exception


class ConfigurationError(SpeechTranscriptionError):
    """配置错误"""
    def __init__(self, message: str, recovery_suggestion: Optional[str] = None):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.CONFIGURATION,
            recovery_suggestion=recovery_suggestion,
            is_recoverable=True
        )


class HardwareError(SpeechTranscriptionError):
    """硬件错误"""
    def __init__(self, message: str, recovery_suggestion: Optional[str] = None):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.HARDWARE,
            recovery_suggestion=recovery_suggestion,
            is_recoverable=True
        )


class AudioError(SpeechTranscriptionError):
    """音频处理错误"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, recovery_suggestion: Optional[str] = None):
        super().__init__(
            message,
            severity=severity,
            category=ErrorCategory.AUDIO,
            recovery_suggestion=recovery_suggestion,
            is_recoverable=True
        )


class ModelError(SpeechTranscriptionError):
    """模型相关错误"""
    def __init__(self, message: str, recovery_suggestion: Optional[str] = None):
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.MODEL,
            recovery_suggestion=recovery_suggestion,
            is_recoverable=False
        )


class TranscriptionError(SpeechTranscriptionError):
    """转录过程错误"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, recovery_suggestion: Optional[str] = None):
        super().__init__(
            message,
            severity=severity,
            category=ErrorCategory.TRANSCRIPTION,
            recovery_suggestion=recovery_suggestion,
            is_recoverable=True
        )


class ErrorHandler:
    """统一错误处理器"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._error_records: List[ErrorRecord] = []
        self._error_counts: Dict[str, int] = {}
        self._recovery_callbacks: Dict[ErrorCategory, List[Callable]] = {}
        self._lock = threading.Lock()

    def register_recovery_callback(self, category: ErrorCategory, callback: Callable):
        """
        注册错误恢复回调函数

        Args:
            category: 错误类别
            callback: 回调函数
        """
        if category not in self._recovery_callbacks:
            self._recovery_callbacks[category] = []
        self._recovery_callbacks[category].append(callback)

    def handle_exception(
        self,
        exception: Exception,
        context_info: Optional[Dict[str, Any]] = None,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        user_message: Optional[str] = None,
        recovery_suggestion: Optional[str] = None
    ) -> ErrorRecord:
        """
        处理异常

        Args:
            exception: 异常对象
            context_info: 上下文信息
            severity: 错误严重程度
            category: 错误类别
            user_message: 用户友好消息
            recovery_suggestion: 恢复建议

        Returns:
            ErrorRecord: 错误记录
        """
        # 获取调用栈信息
        frame = inspect.currentframe()
        caller_frame = frame.f_back
        context = self._extract_context(caller_frame, context_info or {})

        # 推断错误类别和严重程度
        if isinstance(exception, SpeechTranscriptionError):
            severity = severity or exception.severity
            category = category or exception.category
            recovery_suggestion = recovery_suggestion or exception.recovery_suggestion
        else:
            severity = severity or self._infer_severity(exception)
            category = category or self._infer_category(exception)

        # 生成用户友好的消息
        if not user_message:
            user_message = self._generate_user_message(exception, category)

        # 生成开发者消息
        developer_message = self._generate_developer_message(exception, context)

        # 创建错误记录
        error_record = ErrorRecord(
            exception=exception,
            severity=severity,
            category=category,
            context=context,
            user_message=user_message,
            developer_message=developer_message,
            recovery_suggestion=recovery_suggestion,
            is_recoverable=getattr(exception, 'is_recoverable', True)
        )

        # 记录错误
        self._record_error(error_record)

        # 执行恢复策略
        if error_record.is_recoverable:
            self._attempt_recovery(error_record)

        return error_record

    def _extract_context(self, frame, context_info: Dict[str, Any]) -> ErrorContext:
        """提取错误上下文信息"""
        file_path = frame.f_code.co_filename
        function_name = frame.f_code.co_name
        line_number = frame.f_lineno

        # 提取局部变量（过滤敏感信息）
        local_variables = {}
        if frame.f_locals:
            for name, value in frame.f_locals.items():
                if not name.startswith('_') and not callable(value):
                    try:
                        # 尝试转换为字符串，避免复杂对象
                        str_value = str(value)
                        if len(str_value) < 200:  # 限制长度
                            local_variables[name] = str_value
                    except Exception:
                        local_variables[name] = f"<{type(value).__name__}>"

        # 添加额外的上下文信息
        local_variables.update(context_info)

        return ErrorContext(
            component=self._extract_component_name(file_path),
            function_name=function_name,
            file_path=file_path,
            line_number=line_number,
            local_variables=local_variables
        )

    def _extract_component_name(self, file_path: str) -> str:
        """从文件路径提取组件名称"""
        parts = file_path.replace('\\', '/').split('/')
        if 'src' in parts:
            src_index = parts.index('src')
            if src_index + 1 < len(parts):
                return parts[src_index + 1]
        return "unknown"

    def _infer_severity(self, exception: Exception) -> ErrorSeverity:
        """推断错误严重程度"""
        if isinstance(exception, (FileNotFoundError, ImportError, ModuleNotFoundError)):
            return ErrorSeverity.HIGH
        elif isinstance(exception, (ValueError, TypeError)):
            return ErrorSeverity.MEDIUM
        elif isinstance(exception, (ConnectionError, TimeoutError)):
            return ErrorSeverity.HIGH
        elif isinstance(exception, KeyboardInterrupt):
            return ErrorSeverity.LOW
        else:
            return ErrorSeverity.MEDIUM

    def _infer_category(self, exception: Exception) -> ErrorCategory:
        """推断错误类别"""
        if isinstance(exception, (FileNotFoundError, PermissionError, OSError)):
            return ErrorCategory.FILE_SYSTEM
        elif isinstance(exception, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK
        elif isinstance(exception, (ImportError, ModuleNotFoundError)):
            return ErrorCategory.CONFIGURATION
        elif isinstance(exception, (ValueError, TypeError)):
            return ErrorCategory.SYSTEM
        else:
            return ErrorCategory.UNKNOWN

    def _generate_user_message(self, exception: Exception, category: ErrorCategory) -> str:
        """生成用户友好的错误消息"""
        message_templates = {
            ErrorCategory.HARDWARE: "硬件设备访问失败，请检查设备连接和权限设置",
            ErrorCategory.NETWORK: "网络连接异常，请检查网络设置",
            ErrorCategory.FILE_SYSTEM: "文件访问失败，请检查文件路径和权限",
            ErrorCategory.CONFIGURATION: "配置错误，请检查配置参数",
            ErrorCategory.MODEL: "模型加载或推理失败，请检查模型文件",
            ErrorCategory.AUDIO: "音频处理失败，请检查音频设备和设置",
            ErrorCategory.TRANSCRIPTION: "语音转录过程出错，请稍后重试",
            ErrorCategory.SYSTEM: "系统内部错误",
        }

        base_message = message_templates.get(category, "发生了未知错误")

        # 添加具体的异常信息（如果有用）
        if hasattr(exception, 'args') and exception.args:
            specific_info = str(exception.args[0])
            if len(specific_info) < 100:  # 避免过长的技术信息
                base_message += f"：{specific_info}"

        return base_message

    def _generate_developer_message(self, exception: Exception, context: ErrorContext) -> str:
        """生成开发者调试消息"""
        return (
            f"[{context.component}:{context.function_name}:{context.line_number}] "
            f"{type(exception).__name__}: {str(exception)}"
        )

    def _record_error(self, error_record: ErrorRecord):
        """记录错误"""
        with self._lock:
            self._error_records.append(error_record)

            # 更新错误计数
            error_key = f"{error_record.category.value}:{type(error_record.exception).__name__}"
            self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1

            # 保持最近100条记录
            if len(self._error_records) > 100:
                self._error_records = self._error_records[-100:]

        # 记录到日志
        self._log_error(error_record)

    def _log_error(self, error_record: ErrorRecord):
        """记录错误到日志"""
        log_methods = {
            ErrorSeverity.LOW: self.logger.info,
            ErrorSeverity.MEDIUM: self.logger.warning,
            ErrorSeverity.HIGH: self.logger.error,
            ErrorSeverity.CRITICAL: self.logger.critical,
        }

        log_method = log_methods.get(error_record.severity, self.logger.error)

        # 构建日志消息
        log_message = (
            f"[{error_record.category.value.upper()}] "
            f"{error_record.user_message}"
        )

        if error_record.recovery_suggestion:
            log_message += f" | 建议: {error_record.recovery_suggestion}"

        log_method(log_message)

        # 详细的调试信息
        self.logger.debug(
            f"错误详情 - {error_record.developer_message} | "
            f"上下文: {error_record.context.local_variables} | "
            f"线程: {error_record.context.thread_id}"
        )

        # 如果是严重错误，记录完整的堆栈跟踪
        if error_record.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.logger.debug(
                f"堆栈跟踪:\n{traceback.format_exception(type(error_record.exception), error_record.exception, error_record.exception.__traceback__)}"
            )

    def _attempt_recovery(self, error_record: ErrorRecord):
        """尝试错误恢复"""
        if error_record.category in self._recovery_callbacks:
            for callback in self._recovery_callbacks[error_record.category]:
                try:
                    callback(error_record)
                    error_record.handled = True
                    self.logger.info(f"错误恢复成功: {error_record.user_message}")
                    break
                except Exception as e:
                    self.logger.warning(f"错误恢复失败: {e}")

    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        with self._lock:
            total_errors = len(self._error_records)
            recent_errors = [r for r in self._error_records if (datetime.now() - r.context.timestamp).seconds < 3600]

            severity_counts = {}
            category_counts = {}

            for record in self._error_records:
                severity_counts[record.severity.value] = severity_counts.get(record.severity.value, 0) + 1
                category_counts[record.category.value] = category_counts.get(record.category.value, 0) + 1

            return {
                'total_errors': total_errors,
                'recent_errors_1h': len(recent_errors),
                'severity_distribution': severity_counts,
                'category_distribution': category_counts,
                'error_counts': self._error_counts.copy(),
                'handled_errors': len([r for r in self._error_records if r.handled])
            }

    def clear_error_history(self):
        """清除错误历史"""
        with self._lock:
            self._error_records.clear()
            self._error_counts.clear()
        self.logger.info("错误历史已清除")


def handle_exceptions(
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    user_message: Optional[str] = None,
    recovery_suggestion: Optional[str] = None,
    reraise: bool = False,
    return_on_error: Any = None
):
    """
    异常处理装饰器

    Args:
        severity: 错误严重程度
        category: 错误类别
        user_message: 用户友好消息
        recovery_suggestion: 恢复建议
        reraise: 是否重新抛出异常
        return_on_error: 异常时的返回值

    Returns:
        装饰器函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler = ErrorHandler()
                error_record = error_handler.handle_exception(
                    e,
                    severity=severity,
                    category=category,
                    user_message=user_message,
                    recovery_suggestion=recovery_suggestion
                )

                if reraise:
                    raise
                else:
                    return return_on_error
        return wrapper
    return decorator


# 全局错误处理器实例
_global_error_handler = ErrorHandler()


def get_global_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    return _global_error_handler


def handle_exception(
    exception: Exception,
    context_info: Optional[Dict[str, Any]] = None,
    severity: Optional[ErrorSeverity] = None,
    category: Optional[ErrorCategory] = None,
    user_message: Optional[str] = None,
    recovery_suggestion: Optional[str] = None
) -> ErrorRecord:
    """
    处理异常的便捷函数

    Args:
        exception: 异常对象
        context_info: 上下文信息
        severity: 错误严重程度
        category: 错误类别
        user_message: 用户友好消息
        recovery_suggestion: 恢复建议

    Returns:
        ErrorRecord: 错误记录
    """
    return _global_error_handler.handle_exception(
        exception, context_info, severity, category, user_message, recovery_suggestion
    )