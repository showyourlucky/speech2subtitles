"""
工具模块测试

测试错误处理和日志系统的功能
"""

import sys
import os
import pytest
import logging
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch
from io import StringIO

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.logger import (
    LogLevel, LogConfig, PerformanceTimer, LoggerManager,
    setup_logging, get_logger, get_performance_timer
)
from utils.error_handler import (
    ErrorSeverity, ErrorCategory, ErrorContext, ErrorRecord,
    SpeechTranscriptionError, ConfigurationError, HardwareError,
    ErrorHandler, handle_exceptions, get_global_error_handler
)


class TestLogConfig:
    """LogConfig类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = LogConfig()

        assert config.level == LogLevel.INFO
        assert config.console_enabled == True
        assert config.file_enabled == False
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.backup_count == 5

    def test_custom_config(self):
        """测试自定义配置"""
        config = LogConfig(
            level=LogLevel.DEBUG,
            console_enabled=False,
            file_enabled=True,
            file_path=Path("test.log"),
            max_file_size=5 * 1024 * 1024,
            backup_count=3,
            performance_logging=True
        )

        assert config.level == LogLevel.DEBUG
        assert config.console_enabled == False
        assert config.file_enabled == True
        assert config.file_path == Path("test.log")
        assert config.max_file_size == 5 * 1024 * 1024
        assert config.backup_count == 3
        assert config.performance_logging == True


class TestLoggerManager:
    """LoggerManager类测试"""

    def setup_method(self):
        """测试前设置"""
        # 每次测试前重置日志管理器
        LoggerManager._instance = None

    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = LoggerManager()
        manager2 = LoggerManager()

        assert manager1 is manager2

    def test_setup_console_logging(self):
        """测试控制台日志设置"""
        config = LogConfig(
            level=LogLevel.DEBUG,
            console_enabled=True,
            file_enabled=False
        )

        manager = LoggerManager()
        manager.setup(config)

        # 获取日志器
        logger = manager.get_logger("test")
        assert logger is not None
        assert logger.level <= logging.DEBUG

    def test_setup_file_logging(self):
        """测试文件日志设置"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            log_file = Path(f.name)

        try:
            config = LogConfig(
                level=LogLevel.INFO,
                console_enabled=False,
                file_enabled=True,
                file_path=log_file
            )

            manager = LoggerManager()
            manager.setup(config)

            # 获取日志器并记录消息
            logger = manager.get_logger("test")
            logger.info("测试日志消息")

            # 检查文件是否存在且包含消息
            assert log_file.exists()

        finally:
            # 清理
            manager.shutdown()
            log_file.unlink(missing_ok=True)

    def test_get_logger_with_component(self):
        """测试带组件名的日志器"""
        config = LogConfig(console_enabled=True)
        manager = LoggerManager()
        manager.setup(config)

        logger = manager.get_logger("test", "audio")

        assert logger is not None
        # 应该能够正常记录消息
        logger.info("组件测试消息")

    def test_performance_timer(self):
        """测试性能计时器"""
        config = LogConfig(console_enabled=True, performance_logging=True)
        manager = LoggerManager()
        manager.setup(config)

        logger = manager.get_logger("test")

        with manager.get_performance_timer(logger, "测试操作") as timer:
            time.sleep(0.01)  # 模拟操作

        # 检查性能统计
        stats = manager.get_performance_summary()
        assert "测试操作" in stats
        assert stats["测试操作"]["count"] == 1

    def test_performance_stats_limit(self):
        """测试性能统计限制"""
        config = LogConfig(console_enabled=True, performance_logging=True)
        manager = LoggerManager()
        manager.setup(config)

        # 添加超过100条记录
        for i in range(150):
            manager.log_performance_stats("测试操作", 0.001)

        stats = manager.get_performance_summary()
        # 应该只保留最近100条
        assert stats["测试操作"]["count"] == 100

    def test_thread_safety(self):
        """测试线程安全"""
        config = LogConfig(console_enabled=True)
        manager = LoggerManager()
        manager.setup(config)

        results = []
        errors = []

        def worker():
            try:
                logger = manager.get_logger(f"worker-{threading.current_thread().ident}")
                logger.info("工作线程消息")
                results.append(True)
            except Exception as e:
                errors.append(e)

        # 创建多个线程
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 检查结果
        assert len(errors) == 0
        assert len(results) == 10


class TestPerformanceTimer:
    """PerformanceTimer类测试"""

    def test_timer_context_manager(self):
        """测试计时器上下文管理器"""
        logger = Mock()
        operation_name = "测试操作"

        with PerformanceTimer(logger, operation_name) as timer:
            assert timer.start_time is not None
            time.sleep(0.01)

        # 检查日志调用
        assert logger.debug.call_count >= 2  # 开始和结束消息

    def test_timer_with_exception(self):
        """测试计时器异常处理"""
        logger = Mock()
        operation_name = "测试操作"

        try:
            with PerformanceTimer(logger, operation_name):
                raise ValueError("测试异常")
        except ValueError:
            pass

        # 应该记录异常完成消息
        logger.warning.assert_called()


class TestErrorHandler:
    """ErrorHandler类测试"""

    def test_error_severity(self):
        """测试错误严重性"""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_error_category(self):
        """测试错误类别"""
        assert ErrorCategory.HARDWARE.value == "hardware"
        assert ErrorCategory.AUDIO.value == "audio"
        assert ErrorCategory.MODEL.value == "model"
        assert ErrorCategory.TRANSCRIPTION.value == "transcription"

    def test_error_context(self):
        """测试错误上下文"""
        context = ErrorContext(
            component="audio_capture",
            function_name="record_audio",
            file_path="test_file.py",
            line_number=1,
            local_variables={"device_id": 0, "sample_rate": 16000}
        )

        assert context.component == "audio_capture"
        assert context.function_name == "record_audio"
        assert context.local_variables["device_id"] == 0

    def test_error_record(self):
        """测试错误记录"""
        context = ErrorContext(
            component="test",
            function_name="test_op",
            file_path="test_file.py",
            line_number=1
        )
        exception = ValueError("测试错误")

        record = ErrorRecord(
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.AUDIO,
            exception=exception,
            context=context,
            user_message="用户友好的错误消息"
        )

        assert record.severity == ErrorSeverity.MEDIUM
        assert record.category == ErrorCategory.AUDIO
        assert record.exception == exception
        assert record.user_message == "用户友好的错误消息"
        assert record.timestamp is not None

    def test_custom_exceptions(self):
        """测试自定义异常"""
        # 测试SpeechTranscriptionError
        error = SpeechTranscriptionError("转录错误", ErrorSeverity.HIGH)
        assert error.severity == ErrorSeverity.HIGH
        assert str(error) == "转录错误"

        # 测试ConfigurationError
        config_error = ConfigurationError("配置错误")
        assert config_error.severity == ErrorSeverity.MEDIUM

        # 测试HardwareError
        hardware_error = HardwareError("硬件错误")
        assert hardware_error.severity == ErrorSeverity.HIGH

    def test_error_handler_initialization(self):
        """测试错误处理器初始化"""
        handler = ErrorHandler()

        assert handler.error_count == 0
        assert len(handler.error_history) == 0
        assert handler.max_history_size == 1000

    def test_handle_error(self):
        """测试错误处理"""
        handler = ErrorHandler()
        context = ErrorContext(
            component="test",
            function_name="test_op",
            file_path="test_file.py",
            line_number=1
        )

        try:
            raise ValueError("测试错误")
        except Exception as e:
            result = handler.handle_error(
                exception=e,
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.AUDIO,
                context=context,
                user_message="处理音频时出错"
            )

        assert result is not None
        assert result.severity == ErrorSeverity.MEDIUM
        assert result.user_message == "处理音频时出错"
        assert len(handler._error_records) == 1
        assert len(handler.error_history) == 1

    def test_error_recovery(self):
        """测试错误恢复"""
        recovery_called = False

        def recovery_callback():
            nonlocal recovery_called
            recovery_called = True
            return "恢复成功"

        handler = ErrorHandler()
        context = ErrorContext(
            component="test",
            function_name="test_op",
            file_path="test_file.py",
            line_number=1
        )

        try:
            raise ValueError("测试错误")
        except Exception as e:
            result = handler.handle_error(
                exception=e,
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.AUDIO,
                context=context,
                recovery_callback=recovery_callback
            )

        assert recovery_called == True
        assert result.recovery_attempted == True

    def test_error_statistics(self):
        """测试错误统计"""
        handler = ErrorHandler()
        context = ErrorContext(
            component="test",
            function_name="test_op",
            file_path="test_file.py",
            line_number=1
        )

        # 添加不同类型的错误
        for i in range(3):
            try:
                raise ValueError(f"错误{i}")
            except Exception as e:
                handler.handle_error(e, ErrorSeverity.LOW, ErrorCategory.AUDIO, context)

        for i in range(2):
            try:
                raise RuntimeError(f"运行时错误{i}")
            except Exception as e:
                handler.handle_error(e, ErrorSeverity.HIGH, ErrorCategory.MODEL, context)

        stats = handler.get_error_statistics()

        assert stats["total_errors"] == 5
        assert stats["by_severity"][ErrorSeverity.LOW] == 3
        assert stats["by_severity"][ErrorSeverity.HIGH] == 2
        assert stats["by_category"][ErrorCategory.AUDIO] == 3
        assert stats["by_category"][ErrorCategory.MODEL] == 2

    def test_error_history_limit(self):
        """测试错误历史限制"""
        handler = ErrorHandler(max_history_size=3)
        context = ErrorContext(
            component="test",
            function_name="test_op",
            file_path="test_file.py",
            line_number=1
        )

        # 添加超过限制的错误
        for i in range(5):
            try:
                raise ValueError(f"错误{i}")
            except Exception as e:
                handler.handle_error(e, ErrorSeverity.LOW, ErrorCategory.AUDIO, context)

        # 应该只保留最新的3个
        assert len(handler.error_history) == 3
        assert handler.error_count == 5  # 总计数不受限制


class TestHandleExceptionsDecorator:
    """handle_exceptions装饰器测试"""

    def test_decorator_success(self):
        """测试装饰器成功情况"""
        @handle_exceptions(
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.AUDIO,
            user_message="音频处理失败"
        )
        def successful_function():
            return "成功"

        result = successful_function()
        assert result == "成功"

    def test_decorator_exception_handling(self):
        """测试装饰器异常处理"""
        @handle_exceptions(
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.AUDIO,
            user_message="音频处理失败",
            return_on_error="默认值"
        )
        def failing_function():
            raise ValueError("测试异常")

        result = failing_function()
        assert result == "默认值"

        # 检查全局错误处理器
        global_handler = get_global_error_handler()
        assert global_handler.error_count > 0

    def test_decorator_with_recovery(self):
        """测试装饰器恢复功能"""
        recovery_called = False

        def recovery_callback():
            nonlocal recovery_called
            recovery_called = True
            return "恢复值"

        @handle_exceptions(
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.AUDIO,
            recovery_callback=recovery_callback
        )
        def failing_function():
            raise ValueError("测试异常")

        result = failing_function()
        assert recovery_called == True
        assert result == "恢复值"

    def test_decorator_context_information(self):
        """测试装饰器上下文信息"""
        @handle_exceptions(
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.AUDIO,
            component="test_component",
            return_on_error=None
        )
        def function_with_context():
            raise ValueError("上下文测试")

        function_with_context()

        # 检查错误记录中的上下文
        global_handler = get_global_error_handler()
        latest_error = global_handler.error_history[-1]
        assert latest_error.context.component == "test_component"
        assert latest_error.context.operation == "function_with_context"


class TestIntegration:
    """集成测试"""

    def test_logging_and_error_handling_integration(self):
        """测试日志和错误处理集成"""
        # 设置日志
        config = LogConfig(
            level=LogLevel.DEBUG,
            console_enabled=True,
            file_enabled=False
        )
        setup_logging(config)

        # 获取日志器
        logger = get_logger("integration_test")

        # 测试错误处理
        handler = ErrorHandler()
        context = ErrorContext(
            component="integration",
            function_name="test_function",
            file_path="test_file.py",
            line_number=1
        )

        try:
            logger.info("开始集成测试")
            raise RuntimeError("集成测试错误")
        except Exception as e:
            error_record = handler.handle_exception(
                exception=e,
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.TRANSCRIPTION,
                user_message="集成测试失败"
            )
            logger.error(f"处理错误: {error_record.user_message}")

        assert error_record is not None
        assert len(handler._error_records) == 1

    def test_performance_monitoring_integration(self):
        """测试性能监控集成"""
        config = LogConfig(
            console_enabled=True,
            performance_logging=True
        )
        setup_logging(config)

        logger = get_logger("performance_test")

        # 使用性能计时器
        with get_performance_timer(logger, "集成测试操作"):
            time.sleep(0.01)

        # 检查性能统计
        from utils.logger import _logger_manager
        stats = _logger_manager.get_performance_summary()
        assert "集成测试操作" in stats


if __name__ == "__main__":
    print("Running utils module tests...")

    try:
        # Test log configuration
        config = LogConfig(
            level=LogLevel.INFO,
            console_enabled=True,
            file_enabled=False
        )
        print("+ LogConfig created successfully")

        # Test logger manager
        manager = LoggerManager()
        manager.setup(config)
        print("+ LoggerManager setup successfully")

        # Test logger
        logger = manager.get_logger("test")
        logger.info("测试日志消息")
        print("+ Logger working correctly")

        # Test error handler
        handler = ErrorHandler()
        context = ErrorContext(
            component="test",
            function_name="test_operation",
            file_path="test_file.py",
            line_number=1
        )

        try:
            raise ValueError("测试错误")
        except Exception as e:
            error_record = handler.handle_exception(
                exception=e,
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.AUDIO,
                user_message="测试用户消息"
            )
            print(f"+ Error handled: {error_record.user_message}")

        # Test decorator
        @handle_exceptions(
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.AUDIO,
            user_message="装饰器测试",
            return_on_error="默认返回值"
        )
        def test_function():
            raise RuntimeError("装饰器测试错误")

        result = test_function()
        print(f"+ Decorator test result: {result}")

        # Test performance timer
        with manager.get_performance_timer(logger, "性能测试"):
            time.sleep(0.001)
        print("+ Performance timer working")

        # Get statistics
        stats = handler.get_error_statistics()
        print(f"+ Error statistics: {stats['total_errors']} total errors")

        manager.shutdown()
        print("\nAll tests passed!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()