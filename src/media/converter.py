"""
媒体格式转换器

使用FFmpeg将各种媒体格式转换为Sense-Voice支持的音频格式
"""

import subprocess
import shutil
import sys
from pathlib import Path
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)


class MediaConverterError(Exception):
    """媒体转换错误基类"""
    pass


class FFmpegNotFoundError(MediaConverterError):
    """FFmpeg未安装错误"""
    pass


class ConversionError(MediaConverterError):
    """文件转换错误"""
    pass


class MediaConverter:
    """
    媒体文件转音频转换器

    使用FFmpeg将视频/音频文件转换为16kHz单声道WAV格式,
    以满足Sense-Voice模型的输入要求

    Attributes:
        temp_dir: 临时文件存储目录
        supported_formats: 支持的媒体格式列表

    Example:
        >>> converter = MediaConverter("temp/")
        >>> wav_file = converter.convert_to_wav("video.mp4")
        >>> # 使用转换后的音频文件...
        >>> converter.cleanup_temp_file(wav_file)
    """

    # Sense-Voice官方支持的媒体格式
    SUPPORTED_VIDEO_FORMATS = ['.avi', '.flv', '.mkv', '.mov', '.mp4', '.mpeg', '.webm', '.wmv']
    SUPPORTED_AUDIO_FORMATS = ['.aac', '.amr', '.flac', '.m4a', '.mp3', '.ogg', '.opus', '.wav', '.wma']

    def __init__(self, temp_dir: str = "temp"):
        """
        初始化媒体转换器

        Args:
            temp_dir: 临时文件存储目录路径

        Note:
            会自动创建临时目录如果不存在
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        logger.info(f"媒体转换器初始化完成,临时目录: {self.temp_dir.absolute()}")

    @staticmethod
    def check_ffmpeg() -> bool:
        """
        检查FFmpeg是否已安装

        Returns:
            bool: True表示FFmpeg可用,False表示未安装

        Example:
            >>> if not MediaConverter.check_ffmpeg():
            ...     print("请先安装FFmpeg")
        """
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def ensure_ffmpeg():
        """
        确保FFmpeg已安装,否则抛出异常并提供安装指南

        Raises:
            FFmpegNotFoundError: 当FFmpeg未安装时

        Note:
            应该在程序启动时调用,确保运行环境正确
        """
        if not MediaConverter.check_ffmpeg():
            error_msg = """
错误: 未检测到FFmpeg!

FFmpeg是必需的依赖,用于转换媒体格式。

安装方法:
  Windows: 请参考 README.md 中的"FFmpeg安装指南"章节
  Linux:   sudo apt install ffmpeg
  macOS:   brew install ffmpeg

安装完成后,请重新运行程序。
"""
            logger.error("FFmpeg未安装")
            print(error_msg)
            raise FFmpegNotFoundError("FFmpeg未安装,请先安装FFmpeg")

    def is_supported_format(self, file_path: Path) -> bool:
        """
        检查文件格式是否受支持

        Args:
            file_path: 文件路径

        Returns:
            bool: True表示格式受支持,False表示不支持
        """
        suffix = file_path.suffix.lower()
        return suffix in self.SUPPORTED_VIDEO_FORMATS or suffix in self.SUPPORTED_AUDIO_FORMATS

    def get_supported_formats_str(self) -> str:
        """
        获取支持格式的字符串表示

        Returns:
            str: 格式化的支持格式列表
        """
        video_formats = ', '.join(self.SUPPORTED_VIDEO_FORMATS)
        audio_formats = ', '.join(self.SUPPORTED_AUDIO_FORMATS)
        return f"视频: {video_formats}\n音频: {audio_formats}"

    def convert_to_wav(
        self,
        input_file: Path,
        sample_rate: int = 16000,
        show_progress: bool = True
    ) -> Path:
        """
        转换媒体文件为16kHz单声道WAV格式

        Args:
            input_file: 输入媒体文件路径
            sample_rate: 目标采样率,默认16000Hz
            show_progress: 是否显示转换进度

        Returns:
            Path: 转换后的WAV文件路径

        Raises:
            FileNotFoundError: 输入文件不存在
            ConversionError: 文件转换失败

        Note:
            转换参数:
            - 格式: 标准WAV文件格式 (兼容soundfile库)
            - 采样率: 16000 Hz
            - 声道: 单声道 (mono)
            - 编码: pcm_s16le (16位小端序PCM)
        """
        # 验证输入文件
        if not input_file.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_file}")

        if not self.is_supported_format(input_file):
            supported = self.get_supported_formats_str()
            raise ConversionError(
                f"不支持的文件格式: {input_file.suffix}\n\n"
                f"支持的格式:\n{supported}"
            )

        # 生成临时文件名 (使用时间戳避免冲突)
        timestamp = int(time.time() * 1000)
        temp_filename = f"{input_file.stem}_{timestamp}.wav"
        temp_output = self.temp_dir / temp_filename

        # 构建FFmpeg命令 (修复：使用标准WAV格式而不是原始PCM)
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", str(input_file),          # 输入文件
            "-acodec", "pcm_s16le",         # 音频编解码器: 16位小端序PCM
            "-ac", "1",                     # 音频声道: 1 (单声道)
            "-ar", str(sample_rate),        # 音频采样率: 16kHz
            "-y",                           # 覆盖已存在文件
            str(temp_output)                # 输出文件 (WAV格式)
        ]

        try:
            if show_progress:
                print(f"  [转换音频] {input_file.name} -> {temp_filename}")
                logger.info(f"开始转换: {input_file} -> {temp_output}")

            # 执行FFmpeg转换
            start_time = time.time()
            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                encoding='utf-8',
                errors='ignore'  # 忽略编码错误
            )
            elapsed = time.time() - start_time

            # 验证输出文件
            if not temp_output.exists():
                raise ConversionError(f"转换失败: 输出文件未生成 {temp_output}")

            file_size_mb = temp_output.stat().st_size / (1024 * 1024)

            if show_progress:
                print(f"  [转换完成] 耗时: {elapsed:.1f}s, 大小: {file_size_mb:.1f}MB")

            logger.info(f"转换成功: {temp_output}, 耗时{elapsed:.2f}秒, 大小{file_size_mb:.2f}MB")
            return temp_output

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"FFmpeg转换失败: {error_msg}")
            raise ConversionError(f"媒体转换失败: {error_msg}")

        except Exception as e:
            logger.error(f"转换过程异常: {e}")
            raise ConversionError(f"转换过程异常: {e}")

    def cleanup_temp_file(self, temp_file: Path) -> None:
        """
        清理临时文件

        Args:
            temp_file: 要删除的临时文件路径

        Note:
            会安全地删除文件,即使文件不存在也不会报错
        """
        try:
            if temp_file.exists():
                temp_file.unlink()
                logger.info(f"已删除临时文件: {temp_file}")
        except Exception as e:
            logger.warning(f"删除临时文件失败: {temp_file}, 错误: {e}")

    def cleanup_all_temp_files(self) -> int:
        """
        清理所有临时文件

        Returns:
            int: 删除的文件数量

        Note:
            会删除temp_dir目录下的所有.wav文件
        """
        count = 0
        try:
            for wav_file in self.temp_dir.glob("*.wav"):
                self.cleanup_temp_file(wav_file)
                count += 1

            if count > 0:
                logger.info(f"已清理 {count} 个临时文件")

        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

        return count
