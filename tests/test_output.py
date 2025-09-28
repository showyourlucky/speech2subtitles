"""
输出处理模块测试

测试OutputHandler类的功能
"""

import sys
import os
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from io import StringIO
from datetime import datetime

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from output.handler import OutputHandler
from output.models import (
    OutputConfig, OutputFormat, TimestampFormat, OutputLevel, ColorScheme,
    FormattedOutput, OutputBuffer, SubtitleEntry, OutputError
)
from transcription.models import TranscriptionResult, LanguageCode


class TestOutputConfig:
    """OutputConfig类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = OutputConfig()

        assert config.format == OutputFormat.CONSOLE
        assert config.timestamp_format == TimestampFormat.HH_MM_SS
        assert config.show_confidence == True
        assert config.show_timestamps == True
        assert config.level == OutputLevel.INFO

    def test_custom_config(self):
        """测试自定义配置"""
        config = OutputConfig(
            format=OutputFormat.JSON,
            timestamp_format=TimestampFormat.MILLISECONDS,
            show_confidence=False,
            show_timestamps=False,
            level=OutputLevel.DEBUG,
            color_scheme=ColorScheme.DARK
        )

        assert config.format == OutputFormat.JSON
        assert config.timestamp_format == TimestampFormat.MILLISECONDS
        assert config.show_confidence == False
        assert config.show_timestamps == False
        assert config.level == OutputLevel.DEBUG
        assert config.color_scheme == ColorScheme.DARK

    def test_invalid_buffer_size(self):
        """测试无效缓冲区大小"""
        with pytest.raises(ValueError, match="缓冲区大小必须大于0"):
            OutputConfig(buffer_size=0)


class TestOutputBuffer:
    """OutputBuffer类测试"""

    def test_buffer_creation(self):
        """测试缓冲区创建"""
        buffer = OutputBuffer(max_size=10)

        assert buffer.max_size == 10
        assert len(buffer) == 0
        assert buffer.is_empty == True
        assert buffer.is_full == False

    def test_buffer_add_entries(self):
        """测试添加条目"""
        buffer = OutputBuffer(max_size=3)

        result1 = TranscriptionResult(text="第一句", confidence=0.9)
        result2 = TranscriptionResult(text="第二句", confidence=0.8)

        buffer.add(result1)
        buffer.add(result2)

        assert len(buffer) == 2
        assert buffer.is_empty == False

    def test_buffer_overflow(self):
        """测试缓冲区溢出"""
        buffer = OutputBuffer(max_size=2)

        result1 = TranscriptionResult(text="第一句", confidence=0.9)
        result2 = TranscriptionResult(text="第二句", confidence=0.8)
        result3 = TranscriptionResult(text="第三句", confidence=0.7)

        buffer.add(result1)
        buffer.add(result2)
        buffer.add(result3)  # 应该移除第一个

        assert len(buffer) == 2
        assert buffer.get_all()[0].text == "第二句"

    def test_buffer_clear(self):
        """测试清空缓冲区"""
        buffer = OutputBuffer(max_size=5)
        buffer.add(TranscriptionResult(text="测试", confidence=0.9))

        buffer.clear()

        assert len(buffer) == 0
        assert buffer.is_empty == True


class TestSubtitleEntry:
    """SubtitleEntry类测试"""

    def test_subtitle_entry_creation(self):
        """测试字幕条目创建"""
        entry = SubtitleEntry(
            index=1,
            start_time=1.5,
            end_time=3.2,
            text="测试字幕"
        )

        assert entry.index == 1
        assert entry.start_time == 1.5
        assert entry.end_time == 3.2
        assert entry.text == "测试字幕"
        assert entry.duration == 1.7

    def test_subtitle_srt_format(self):
        """测试SRT格式"""
        entry = SubtitleEntry(
            index=1,
            start_time=61.5,
            end_time=65.2,
            text="测试字幕"
        )

        srt_format = entry.to_srt()

        assert "1" in srt_format
        assert "01:01:30,500" in srt_format  # 1分1.5秒
        assert "01:05:12,000" in srt_format  # 1分5.2秒
        assert "测试字幕" in srt_format

    def test_subtitle_vtt_format(self):
        """测试VTT格式"""
        entry = SubtitleEntry(
            index=1,
            start_time=1.5,
            end_time=3.2,
            text="测试字幕"
        )

        vtt_format = entry.to_vtt()

        assert "00:01.500" in vtt_format
        assert "00:03.200" in vtt_format
        assert "测试字幕" in vtt_format


class TestOutputHandler:
    """OutputHandler类测试"""

    def setup_method(self):
        """测试前设置"""
        self.config = OutputConfig(
            format=OutputFormat.CONSOLE,
            show_confidence=True,
            show_timestamps=True
        )

    def test_handler_initialization(self):
        """测试处理器初始化"""
        handler = OutputHandler(self.config)

        assert handler.config == self.config
        assert handler.metrics is not None
        assert handler.buffer is not None
        assert len(handler.subtitle_entries) == 0

    def test_handler_default_config(self):
        """测试默认配置初始化"""
        handler = OutputHandler()

        assert handler.config is not None
        assert handler.config.format == OutputFormat.CONSOLE

    @patch('sys.stdout', new_callable=StringIO)
    def test_console_output(self, mock_stdout):
        """测试控制台输出"""
        handler = OutputHandler(self.config)

        result = TranscriptionResult(
            text="测试文本",
            confidence=0.95,
            start_time=1.0,
            end_time=3.0
        )

        handler.output_result(result)

        output = mock_stdout.getvalue()
        assert "测试文本" in output
        assert "0.95" in output  # 置信度

    def test_json_output(self):
        """测试JSON输出"""
        json_config = OutputConfig(format=OutputFormat.JSON)
        handler = OutputHandler(json_config)

        result = TranscriptionResult(
            text="测试文本",
            confidence=0.95,
            start_time=1.0,
            end_time=3.0
        )

        formatted = handler._format_result(result)

        # 解析JSON确保格式正确
        json_data = json.loads(formatted.content)
        assert json_data["text"] == "测试文本"
        assert json_data["confidence"] == 0.95

    def test_srt_output(self):
        """测试SRT输出"""
        srt_config = OutputConfig(format=OutputFormat.SRT)
        handler = OutputHandler(srt_config)

        result = TranscriptionResult(
            text="测试字幕",
            confidence=0.95,
            start_time=1.0,
            end_time=3.0
        )

        handler.output_result(result)

        # 检查字幕条目是否添加
        assert len(handler.subtitle_entries) == 1
        entry = handler.subtitle_entries[0]
        assert entry.text == "测试字幕"
        assert entry.start_time == 1.0

    def test_vtt_output(self):
        """测试VTT输出"""
        vtt_config = OutputConfig(format=OutputFormat.VTT)
        handler = OutputHandler(vtt_config)

        result = TranscriptionResult(
            text="测试字幕",
            confidence=0.95,
            start_time=1.0,
            end_time=3.0
        )

        handler.output_result(result)

        # 检查字幕条目是否添加
        assert len(handler.subtitle_entries) == 1

    def test_file_output(self):
        """测试文件输出"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_file = f.name

        try:
            file_config = OutputConfig(
                format=OutputFormat.FILE,
                output_file=temp_file
            )
            handler = OutputHandler(file_config)

            result = TranscriptionResult(
                text="文件输出测试",
                confidence=0.95
            )

            handler.output_result(result)

            # 检查文件内容
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "文件输出测试" in content

        finally:
            # 清理临时文件
            Path(temp_file).unlink(missing_ok=True)

    def test_batch_output(self):
        """测试批量输出"""
        handler = OutputHandler(self.config)

        results = [
            TranscriptionResult(text="第一句", confidence=0.9),
            TranscriptionResult(text="第二句", confidence=0.8),
            TranscriptionResult(text="第三句", confidence=0.7)
        ]

        batch_result = BatchTranscriptionResult(
            results=results,
            total_duration=10.0,
            processing_time=2.0
        )

        # 测试批量输出不会抛出异常
        handler.output_batch(batch_result)

    def test_real_time_output(self):
        """测试实时输出"""
        handler = OutputHandler(self.config)

        # 测试部分结果
        partial_result = TranscriptionResult(
            text="部分结果",
            confidence=0.5,
            is_partial=True
        )

        # 实时输出应该处理部分结果
        handler.output_real_time(partial_result)

        # 检查缓冲区
        assert not handler.buffer.is_empty

    def test_timestamp_formatting(self):
        """测试时间戳格式化"""
        handler = OutputHandler(self.config)

        # 测试不同格式
        test_time = 3661.5  # 1小时1分1.5秒

        # HH:MM:SS格式
        formatted = handler._format_timestamp(test_time, TimestampFormat.HH_MM_SS)
        assert "01:01:01" in formatted

        # 毫秒格式
        formatted = handler._format_timestamp(test_time, TimestampFormat.MILLISECONDS)
        assert "3661500" in formatted

        # ISO格式
        formatted = handler._format_timestamp(test_time, TimestampFormat.ISO)
        assert "T" in formatted  # ISO格式包含T

    def test_confidence_formatting(self):
        """测试置信度格式化"""
        handler = OutputHandler(self.config)

        # 测试不同置信度值
        assert handler._format_confidence(0.95) == "95%"
        assert handler._format_confidence(0.123) == "12%"
        assert handler._format_confidence(1.0) == "100%"

    def test_color_formatting(self):
        """测试颜色格式化"""
        color_config = OutputConfig(
            format=OutputFormat.CONSOLE,
            color_scheme=ColorScheme.LIGHT
        )
        handler = OutputHandler(color_config)

        result = TranscriptionResult(
            text="彩色文本",
            confidence=0.95
        )

        formatted = handler._format_result(result)

        # 检查是否包含ANSI颜色代码
        assert formatted.content is not None

    def test_metrics_update(self):
        """测试指标更新"""
        handler = OutputHandler(self.config)

        initial_count = handler.metrics.total_outputs

        result = TranscriptionResult(text="测试", confidence=0.9)
        handler.output_result(result)

        # 检查指标是否更新
        assert handler.metrics.total_outputs == initial_count + 1

    def test_buffer_management(self):
        """测试缓冲区管理"""
        small_buffer_config = OutputConfig(buffer_size=2)
        handler = OutputHandler(small_buffer_config)

        # 添加多个结果
        for i in range(5):
            result = TranscriptionResult(text=f"结果{i}", confidence=0.9)
            handler.buffer.add(result)

        # 缓冲区应该只保留最新的条目
        assert len(handler.buffer) == 2

    def test_error_handling(self):
        """测试错误处理"""
        # 测试无效文件路径
        invalid_config = OutputConfig(
            format=OutputFormat.FILE,
            output_file="/invalid/path/file.txt"
        )
        handler = OutputHandler(invalid_config)

        result = TranscriptionResult(text="测试", confidence=0.9)

        # 应该优雅处理文件写入错误
        try:
            handler.output_result(result)
        except Exception as e:
            # 错误应该被捕获并记录
            assert isinstance(e, (OSError, IOError, OutputError))

    def test_export_subtitles(self):
        """测试字幕导出"""
        handler = OutputHandler(self.config)

        # 添加一些字幕条目
        handler.subtitle_entries = [
            SubtitleEntry(1, 0.0, 2.0, "第一句字幕"),
            SubtitleEntry(2, 2.5, 5.0, "第二句字幕"),
        ]

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.srt') as f:
            temp_file = f.name

        try:
            # 导出SRT格式
            handler.export_subtitles(temp_file, "srt")

            # 检查文件内容
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "第一句字幕" in content
                assert "第二句字幕" in content
                assert "00:00:00,000" in content  # SRT时间格式

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_handler_cleanup(self):
        """测试处理器清理"""
        handler = OutputHandler(self.config)

        # 添加一些数据
        result = TranscriptionResult(text="测试", confidence=0.9)
        handler.output_result(result)

        # 清理
        handler.cleanup()

        # 检查是否清理
        assert handler.buffer.is_empty
        assert len(handler.subtitle_entries) == 0


if __name__ == "__main__":
    print("Running output handler module tests...")

    try:
        # Test output configuration
        config = OutputConfig(
            format=OutputFormat.CONSOLE,
            show_confidence=True,
            show_timestamps=True
        )
        print("+ OutputConfig created successfully")

        # Test output handler
        handler = OutputHandler(config)
        print("+ OutputHandler created successfully")

        # Test formatting
        result = TranscriptionResult(
            text="测试输出",
            confidence=0.95,
            start_time=1.0,
            end_time=3.0
        )

        formatted = handler._format_result(result)
        print(f"+ Formatted result: {formatted.format_type}")

        # Test buffer
        buffer = OutputBuffer(max_size=5)
        buffer.add(formatted)
        print(f"+ Buffer contains {buffer.current_size} items")

        # Test subtitle entry
        subtitle = SubtitleEntry(1, 1.0, 3.0, "测试字幕")
        print(f"+ Subtitle entry: {subtitle.text} ({subtitle.duration}s)")

        print("\nAll tests passed!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()