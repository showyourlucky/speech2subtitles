"""
字幕文件生成器

支持SRT、VTT等字幕格式的生成
"""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Segment:
    """
    字幕片段数据类

    表示一段带时间戳的文本内容

    Attributes:
        start: 开始时间(秒)
        duration: 持续时间(秒)
        text: 文本内容

    Example:
        >>> seg = Segment(start=1.5, duration=2.3, text="你好世界")
        >>> print(seg.end)  # 3.8
        >>> print(seg.to_srt_format(1))
    """
    start: float       # 开始时间(秒)
    duration: float    # 持续时间(秒)
    text: str = ""     # 文本内容

    @property
    def end(self) -> float:
        """
        计算结束时间

        Returns:
            float: 结束时间(秒) = start + duration
        """
        return self.start + self.duration

    def to_srt_format(self, index: int) -> str:
        """
        转换为SRT格式字符串

        Args:
            index: 字幕序号(从1开始)

        Returns:
            str: SRT格式的字幕片段

        Note:
            SRT格式示例:
            1
            00:00:01,500 --> 00:00:03,800
            你好世界

        Reference:
            参考 generate-subtitles.py line 500-507
        """
        # 格式化时间戳 (HH:MM:SS,mmm)
        start_str = self._format_timestamp_srt(self.start)
        end_str = self._format_timestamp_srt(self.end)

        # 组装SRT格式
        return f"{index}\n{start_str} --> {end_str}\n{self.text}\n"

    def _format_timestamp_srt(self, seconds: float) -> str:
        """
        格式化时间戳为SRT格式 (HH:MM:SS,mmm)

        Args:
            seconds: 时间(秒)

        Returns:
            str: SRT格式的时间戳

        Example:
            >>> seg._format_timestamp_srt(65.123)
            '00:01:05,123'
            >>> seg._format_timestamp_srt(90061.5)
            '25:01:01,500'
        """
        # 计算小时、分钟、秒、毫秒
        total_milliseconds = int(seconds * 1000)
        milliseconds = total_milliseconds % 1000
        total_seconds = total_milliseconds // 1000

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        # 格式化为 HH:MM:SS,mmm
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def __str__(self) -> str:
        """字符串表示"""
        return f"[{self.start:.2f}s - {self.end:.2f}s] {self.text}"


class SubtitleFormatError(Exception):
    """字幕格式错误"""
    pass


class SubtitleGenerator:
    """
    字幕文件生成器

    支持多种字幕格式的生成 (当前实现SRT,可扩展VTT/ASS)

    Attributes:
        encoding: 输出文件编码 (默认UTF-8)

    Example:
        >>> generator = SubtitleGenerator()
        >>> segments = [
        ...     Segment(0.0, 2.5, "第一句话"),
        ...     Segment(2.5, 3.0, "第二句话"),
        ... ]
        >>> generator.generate_srt(segments, "output.srt")
    """

    def __init__(self, encoding: str = 'utf-8'):
        """
        初始化字幕生成器

        Args:
            encoding: 输出文件编码,默认UTF-8
        """
        self.encoding = encoding
        logger.info(f"字幕生成器初始化完成,编码: {self.encoding}")

    def generate_srt(
        self,
        segments: List[Segment],
        output_file: Path,
        overwrite: bool = True
    ) -> None:
        """
        生成SRT格式字幕文件

        Args:
            segments: 字幕片段列表
            output_file: 输出文件路径
            overwrite: 是否覆盖已存在的文件

        Raises:
            FileExistsError: 文件已存在且overwrite=False
            SubtitleFormatError: 字幕片段格式错误

        Note:
            参考 generate-subtitles.py line 650-655
        """
        # 检查文件是否存在
        if output_file.exists() and not overwrite:
            raise FileExistsError(f"字幕文件已存在: {output_file}")

        # 验证片段列表
        if not segments:
            logger.warning("字幕片段列表为空,生成空字幕文件")

        # 确保输出目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 写入SRT文件
            with open(output_file, 'w', encoding=self.encoding) as f:
                for i, seg in enumerate(segments, start=1):
                    # 验证片段数据
                    if seg.duration <= 0:
                        logger.warning(f"片段 {i} 持续时间无效: {seg.duration}s")
                        continue

                    if not seg.text.strip():
                        logger.debug(f"片段 {i} 文本为空,跳过")
                        continue

                    # 写入片段
                    # f.write(f"{i}\n")
                    f.write(seg.to_srt_format(i))
                    f.write("\n")  # SRT要求片段之间有空行

            logger.info(f"SRT字幕生成成功: {output_file}, 共 {len(segments)} 个片段")

        except Exception as e:
            logger.error(f"生成SRT文件失败: {e}")
            raise SubtitleFormatError(f"生成SRT文件失败: {e}")

    def generate_vtt(
        self,
        segments: List[Segment],
        output_file: Path,
        overwrite: bool = True
    ) -> None:
        """
        生成WebVTT格式字幕文件 (扩展功能)

        Args:
            segments: 字幕片段列表
            output_file: 输出文件路径
            overwrite: 是否覆盖已存在的文件

        Note:
            WebVTT格式与SRT类似,但有以下区别:
            - 文件头需要 "WEBVTT" 标识
            - 时间戳使用 . 而不是 ,
            - 可选的cue标识符
        """
        if output_file.exists() and not overwrite:
            raise FileExistsError(f"字幕文件已存在: {output_file}")

        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_file, 'w', encoding=self.encoding) as f:
                # WebVTT文件头
                f.write("WEBVTT\n\n")

                for i, seg in enumerate(segments, start=1):
                    if seg.duration <= 0 or not seg.text.strip():
                        continue

                    # 格式化时间戳 (WebVTT使用.)
                    start_str = self._format_timestamp_vtt(seg.start)
                    end_str = self._format_timestamp_vtt(seg.end)

                    # 写入片段
                    f.write(f"{i}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{seg.text}\n\n")

            logger.info(f"VTT字幕生成成功: {output_file}, 共 {len(segments)} 个片段")

        except Exception as e:
            logger.error(f"生成VTT文件失败: {e}")
            raise SubtitleFormatError(f"生成VTT文件失败: {e}")

    def _format_timestamp_vtt(self, seconds: float) -> str:
        """
        格式化时间戳为WebVTT格式 (HH:MM:SS.mmm)

        Args:
            seconds: 时间(秒)

        Returns:
            str: WebVTT格式的时间戳

        Example:
            >>> self._format_timestamp_vtt(65.123)
            '00:01:05.123'
            >>> self._format_timestamp_vtt(90061.5)
            '25:01:01.500'
        """
        # 计算小时、分钟、秒、毫秒
        total_milliseconds = int(seconds * 1000)
        milliseconds = total_milliseconds % 1000
        total_seconds = total_milliseconds // 1000

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        # 格式化为 HH:MM:SS.mmm (WebVTT使用点而不是逗号)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
