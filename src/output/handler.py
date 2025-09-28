"""
语音转录结果输出处理器

负责处理、格式化和显示语音转录结果，支持多种输出格式、实时更新和用户友好的展示方式。
提供控制台彩色输出、JSON格式化、字幕文件生成等功能。
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

    def __init__(self, config: Optional[OutputConfig] = None):
        """
        Initialize output handler

        Args:
            config: Output configuration, uses defaults if None
        """
        self.config = config or OutputConfig()
        self.metrics = DisplayMetrics()
        self.buffer = OutputBuffer(max_size=self.config.buffer_size)
        self.subtitle_entries: List[SubtitleEntry] = []
        self.subtitle_counter = 1

        # File handling
        self.log_file: Optional[TextIO] = None
        self.output_queue: Queue = Queue()
        self.is_running = False
        self.output_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Color codes for console output
        self.colors = self._init_color_codes()

        # Initialize logging if configured
        if self.config.log_to_file:
            self._init_file_logging()

        # Validate configuration
        if not self.config.validate():
            raise ConfigurationError("Invalid output configuration")

    def _init_color_codes(self) -> Dict[str, str]:
        """Initialize console color codes based on scheme"""
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
        """Start the output handler"""
        if self.is_running:
            return

        self.is_running = True
        if self.config.real_time_update:
            self.output_thread = threading.Thread(target=self._output_worker, daemon=True)
            self.output_thread.start()

    def stop(self) -> None:
        """Stop the output handler and cleanup resources"""
        self.is_running = False

        if self.output_thread:
            self.output_thread.join(timeout=1.0)

        if self.log_file:
            self.log_file.close()
            self.log_file = None

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
        Process a single transcription result

        Args:
            result: Transcription result to process and display
        """
        try:
            formatted = self._format_result(result)

            # Add to buffer
            self.buffer.add(formatted)

            # Update metrics
            self.metrics.update_output_stats(
                formatted.line_count,
                formatted.character_count,
                result.is_final
            )

            # Handle subtitle generation
            if result.is_final and result.end_time:
                self._add_subtitle_entry(result)

            # Output based on configuration
            if self._should_display_result(result):
                if self.config.real_time_update and self.is_running:
                    self.output_queue.put(formatted)
                else:
                    self._display_output(formatted)

        except Exception as e:
            logging.error(f"Error processing result: {e}")
            if self.config.output_level == OutputLevel.DEBUG:
                self._display_error(f"Processing error: {e}")

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