# -*- coding: utf-8 -*-
"""
文件音频捕获模块

从音频/视频文件读取音频数据，模拟实时音频流
支持多种格式：MP3, WAV, FLAC, M4A, OGG, MP4, AVI, MKV等
"""

import logging
import threading
import time
import numpy as np
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass

from src.audio.models import AudioChunk, AudioConfig

logger = logging.getLogger(__name__)


# 可选依赖检查
try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False
    logger.warning("soundfile 库未安装，文件转录功能将不可用。安装: uv pip install soundfile")

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub 库未安装，视频文件转录功能受限。安装: uv pip install pydub")


class FileAudioCaptureError(Exception):
    """文件音频捕获错误"""
    pass


@dataclass
class FileProgress:
    """文件处理进度"""
    total_samples: int      # 总采样点数
    processed_samples: int  # 已处理采样点数
    duration_seconds: float # 总时长（秒）
    elapsed_seconds: float  # 已用时长（秒）

    @property
    def progress_percent(self) -> float:
        """进度百分比"""
        if self.total_samples == 0:
            return 0.0
        return (self.processed_samples / self.total_samples) * 100.0

    @property
    def remaining_seconds(self) -> float:
        """剩余时长"""
        return max(0, self.duration_seconds - self.elapsed_seconds)


class FileAudioCapture:
    """
    文件音频捕获器

    从音频/视频文件读取音频数据，分块发送模拟实时流

    Features:
    - 支持多种音频格式 (WAV, MP3, FLAC, M4A, OGG)
    - 支持视频文件音频提取 (MP4, AVI, MKV, MOV)
    - 自动采样率转换
    - 自动声道转换（立体声→单声道）
    - 进度跟踪
    - 速度控制（可选实时/快速模式）
    """

    def __init__(self, config: AudioConfig, file_path: str):
        """
        初始化文件音频捕获器

        Args:
            config: 音频配置
            file_path: 音频/视频文件路径

        Raises:
            FileAudioCaptureError: 文件不存在或格式不支持
        """
        if not SOUNDFILE_AVAILABLE:
            raise FileAudioCaptureError(
                "soundfile 库未安装，无法使用文件转录功能。\n"
                "请安装: uv pip install soundfile"
            )

        self.config = config
        self.file_path = Path(file_path)

        # 验证文件
        if not self.file_path.exists():
            raise FileAudioCaptureError(f"文件不存在: {self.file_path}")

        # 音频数据和状态
        self.audio_data: Optional[np.ndarray] = None
        self.original_sample_rate: Optional[int] = None
        self.is_running = False
        self.is_paused = False

        # 回调函数列表
        self.callbacks: List[Callable[[AudioChunk], None]] = []
        self.completion_callbacks: List[Callable[[], None]] = []  # 新增：完成回调

        # 处理线程
        self.process_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # 进度跟踪
        self.progress: Optional[FileProgress] = None
        self.progress_callbacks: List[Callable[[FileProgress], None]] = []

        # 性能选项
        self.realtime_simulation = False  # False=快速处理，True=模拟实时速度

        logger.info(f"FileAudioCapture initialized for: {self.file_path.name}")

    def _is_video_file(self) -> bool:
        """判断是否为视频文件"""
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.flv', '.webm']
        return self.file_path.suffix.lower() in video_extensions

    def _load_with_pydub(self) -> tuple:
        """
        使用 pydub 加载视频/音频文件（支持更多格式）

        Returns:
            tuple: (audio_data, sample_rate)
        """
        if not PYDUB_AVAILABLE:
            raise FileAudioCaptureError(
                "pydub 库未安装，无法处理视频文件。\n"
                "请安装: uv pip install pydub\n"
                "注意：还需要安装 ffmpeg"
            )

        logger.info(f"Using pydub to extract audio from: {self.file_path.name}")

        # 使用 pydub 加载文件
        audio_segment = AudioSegment.from_file(str(self.file_path))

        # 获取采样率和声道数
        sample_rate = audio_segment.frame_rate
        channels = audio_segment.channels

        logger.info(f"Pydub loaded: sr={sample_rate}Hz, channels={channels}")

        # 转换为 numpy 数组
        samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)

        # 归一化到 [-1, 1] 范围
        if audio_segment.sample_width == 1:  # 8-bit
            samples = samples / 128.0 - 1.0
        elif audio_segment.sample_width == 2:  # 16-bit
            samples = samples / 32768.0
        elif audio_segment.sample_width == 4:  # 32-bit
            samples = samples / 2147483648.0

        # 如果是立体声，重塑数组
        if channels == 2:
            samples = samples.reshape((-1, 2))
        elif channels > 2:
            samples = samples.reshape((-1, channels))

        return samples, sample_rate

    def load_audio(self) -> None:
        """
        加载音频文件到内存

        Raises:
            FileAudioCaptureError: 加载失败
        """
        try:
            logger.info(f"Loading audio file: {self.file_path}")

            # 判断文件类型并选择加载方法
            is_video = self._is_video_file()

            if is_video:
                # 视频文件：优先使用 pydub
                try:
                    audio_data, sample_rate = self._load_with_pydub()
                    logger.info(f"Loaded via pydub: sr={sample_rate}Hz, shape={audio_data.shape}")
                except Exception as e:
                    logger.warning(f"Pydub failed, trying soundfile: {e}")
                    # 回退到 soundfile
                    audio_data, sample_rate = sf.read(self.file_path, dtype='float32')
            else:
                # 音频文件：直接使用 soundfile
                audio_data, sample_rate = sf.read(self.file_path, dtype='float32')
                logger.info(f"Loaded via soundfile: sr={sample_rate}Hz, shape={audio_data.shape}")

            self.original_sample_rate = sample_rate

            # 转换为单声道（如果是立体声）
            if len(audio_data.shape) > 1:
                logger.info(f"Converting stereo ({audio_data.shape[1]} channels) to mono")
                audio_data = np.mean(audio_data, axis=1)

            # 重采样（如果需要）
            if sample_rate != self.config.sample_rate:
                logger.info(f"Resampling from {sample_rate}Hz to {self.config.sample_rate}Hz")
                audio_data = self._resample(audio_data, sample_rate, self.config.sample_rate)

            # 转换为 int16 格式（与实时捕获一致）
            if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                audio_data = (audio_data * 32767).astype(np.int16)

            self.audio_data = audio_data

            # 初始化进度
            total_samples = len(audio_data)
            duration = total_samples / self.config.sample_rate
            self.progress = FileProgress(
                total_samples=total_samples,
                processed_samples=0,
                duration_seconds=duration,
                elapsed_seconds=0.0
            )

            logger.info(f"Audio loaded successfully: {total_samples} samples, {duration:.2f}s")

        except Exception as e:
            raise FileAudioCaptureError(f"Failed to load audio file: {e}")

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """
        简单重采样（线性插值）

        Note: 对于更高质量的重采样，可以使用 librosa.resample
        """
        if orig_sr == target_sr:
            return audio

        # 计算重采样比例
        ratio = target_sr / orig_sr
        new_length = int(len(audio) * ratio)

        # 线性插值重采样
        indices = np.linspace(0, len(audio) - 1, new_length)
        resampled = np.interp(indices, np.arange(len(audio)), audio)

        return resampled.astype(audio.dtype)

    def start(self) -> None:
        """启动音频捕获（开始发送音频块）"""
        if self.is_running:
            logger.warning("FileAudioCapture is already running")
            return

        if self.audio_data is None:
            self.load_audio()

        self.is_running = True
        self.stop_event.clear()

        # 启动处理线程
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()

        logger.info("FileAudioCapture started")

    def stop(self) -> None:
        """停止音频捕获"""
        if not self.is_running:
            return

        logger.info("Stopping FileAudioCapture...")
        self.is_running = False
        self.stop_event.set()

        # 等待处理线程结束
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=2.0)

        logger.info("FileAudioCapture stopped")

    def pause(self) -> None:
        """暂停音频捕获"""
        self.is_paused = True
        logger.info("FileAudioCapture paused")

    def resume(self) -> None:
        """恢复音频捕获"""
        self.is_paused = False
        logger.info("FileAudioCapture resumed")

    def _process_loop(self) -> None:
        """处理循环：分块发送音频数据"""
        try:
            chunk_size = self.config.chunk_size
            total_samples = len(self.audio_data)
            position = 0
            start_time = time.time()

            logger.info(f"Processing loop started: chunk_size={chunk_size}, total={total_samples}")

            while position < total_samples and not self.stop_event.is_set():
                # 处理暂停
                while self.is_paused and not self.stop_event.is_set():
                    time.sleep(0.1)

                if self.stop_event.is_set():
                    break

                # 提取当前块
                end_position = min(position + chunk_size, total_samples)
                chunk_data = self.audio_data[position:end_position]

                # 创建音频块
                # 计算持续时间（毫秒）
                duration_ms = (len(chunk_data) / self.config.sample_rate) * 1000.0

                audio_chunk = AudioChunk(
                    data=chunk_data,
                    timestamp=time.time(),
                    sample_rate=self.config.sample_rate,
                    channels=1,
                    duration_ms=duration_ms
                )

                # 调用回调函数
                for callback in self.callbacks:
                    try:
                        callback(audio_chunk)
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")

                # 更新进度
                position = end_position
                elapsed = time.time() - start_time
                self.progress = FileProgress(
                    total_samples=total_samples,
                    processed_samples=position,
                    duration_seconds=self.progress.duration_seconds,
                    elapsed_seconds=elapsed
                )

                # 调用进度回调
                for callback in self.progress_callbacks:
                    try:
                        callback(self.progress)
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")

                # 速度控制（可选模拟实时）
                if self.realtime_simulation:
                    # 计算应该等待的时间
                    expected_time = position / self.config.sample_rate
                    actual_time = time.time() - start_time
                    sleep_time = expected_time - actual_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                else:
                    # 快速模式：稍微延迟避免CPU占用过高
                    time.sleep(0.001)

            # 处理完成
            if position >= total_samples:
                logger.info(f"File processing completed: {total_samples} samples in {elapsed:.2f}s")
                # 调用完成回调
                for callback in self.completion_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Error in completion callback: {e}")

        except Exception as e:
            logger.error(f"Error in processing loop: {e}", exc_info=True)
        finally:
            self.is_running = False

    def add_callback(self, callback: Callable[[AudioChunk], None]) -> None:
        """
        添加音频数据回调函数

        Args:
            callback: 回调函数，接收 AudioChunk 参数
        """
        self.callbacks.append(callback)
        logger.debug(f"Callback added, total: {len(self.callbacks)}")

    def add_progress_callback(self, callback: Callable[[FileProgress], None]) -> None:
        """
        添加进度回调函数

        Args:
            callback: 回调函数，接收 FileProgress 参数
        """
        self.progress_callbacks.append(callback)

    def add_completion_callback(self, callback: Callable[[], None]) -> None:
        """
        添加完成回调函数

        Args:
            callback: 回调函数，在文件处理完成时调用
        """
        self.completion_callbacks.append(callback)
        logger.debug(f"Completion callback added, total: {len(self.completion_callbacks)}")

    def get_progress(self) -> Optional[FileProgress]:
        """获取当前进度"""
        return self.progress

    def set_realtime_simulation(self, enabled: bool) -> None:
        """
        设置是否模拟实时速度

        Args:
            enabled: True=模拟实时速度，False=快速处理
        """
        self.realtime_simulation = enabled
        logger.info(f"Realtime simulation: {enabled}")


# 工具函数
def is_file_supported(file_path: str) -> bool:
    """
    检查文件格式是否支持

    Args:
        file_path: 文件路径

    Returns:
        bool: 是否支持
    """
    if not SOUNDFILE_AVAILABLE:
        return False

    supported_extensions = [
        '.wav', '.mp3', '.flac', '.m4a', '.ogg',
        '.mp4', '.avi', '.mkv', '.mov', '.webm'
    ]

    path = Path(file_path)
    return path.suffix.lower() in supported_extensions


def get_file_info(file_path: str) -> dict:
    """
    获取音频文件信息

    Args:
        file_path: 文件路径

    Returns:
        dict: 文件信息（采样率、时长、声道数等）
    """
    if not SOUNDFILE_AVAILABLE:
        return {}

    try:
        info = sf.info(file_path)
        return {
            'sample_rate': info.samplerate,
            'channels': info.channels,
            'duration': info.duration,
            'frames': info.frames,
            'format': info.format,
            'subtype': info.subtype
        }
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        return {}
