"""
基于soundcard库的系统音频捕获实现

使用soundcard库直接获取默认扬声器的环回音频，
避免立体声混音设备的杂音问题

优势:
- 直接从扬声器获取音频，无需立体声混音
- 更高质量的音频捕获
- 更低的延迟和噪音
- 自动适配系统默认音频设备
"""

import time
import logging
import threading
import os
from typing import Optional, List, Callable
from queue import Queue, Empty
import numpy as np

# 在导入soundcard前先应用numpy兼容补丁，避免新版numpy导致录音异常/杂音
from .soundcard_compat import apply_soundcard_numpy_compat

apply_soundcard_numpy_compat()

# 尝试导入soundcard库
try:
    import soundcard as sc
    SOUNDCARD_AVAILABLE = True
except ImportError:
    SOUNDCARD_AVAILABLE = False
    sc = None

# 导入本模块的数据模型和异常类
from .models import (
    AudioDevice, AudioConfig, AudioChunk, AudioStreamStatus,
    AudioSourceType, AudioFormat, AudioCaptureError,
    DeviceNotFoundError, StreamError, ConfigurationError
)

# 创建模块级别的日志记录器
logger = logging.getLogger(__name__)


class SoundcardLoopbackCapture:
    """
    基于soundcard库的环回音频捕获器

    直接从系统默认扬声器获取环回音频，
    提供高质量的系统音频捕获功能
    """

    def __init__(self, config: AudioConfig):
        """
        初始化环回音频捕获器

        Args:
            config: 音频配置对象

        Raises:
            ConfigurationError: soundcard库不可用或配置无效时抛出
        """
        # 检查soundcard库是否可用
        if not SOUNDCARD_AVAILABLE:
            raise ConfigurationError(
                "soundcard库不可用。请使用以下命令安装: pip install soundcard"
            )

        # 保存配置
        self.config = config
        # 系统环回采样率（默认48k，更接近系统输出设备原生采样率）
        self._loopback_sample_rate = self._resolve_loopback_sample_rate()
        # 保持“块时长”近似一致：按采样率比例换算读取块大小
        self._loopback_chunk_size = max(
            1,
            int(round(self.config.chunk_size * self._loopback_sample_rate / self.config.sample_rate))
        )
        self._resample_fn = self._build_resampler(
            self._loopback_sample_rate,
            self.config.sample_rate
        )

        # 初始化soundcard相关对象
        self._speaker = None
        self._loopback_mic = None
        self._recorder = None

        # 状态管理
        self._is_running = False
        self._capture_thread = None

        # 音频数据缓冲和回调
        self._audio_queue = Queue()
        self._callback_lock = threading.Lock()
        self._callbacks: List[Callable[[AudioChunk], None]] = []

        # 性能统计
        self._stats = {
            'chunks_captured': 0,
            'total_samples': 0,
            'start_time': None,
            'last_chunk_time': None
        }

        # 验证配置的有效性
        if not self.config.validate():
            raise ConfigurationError("音频配置无效")

        logger.info(f"已初始化SoundcardLoopbackCapture，配置: {config}")
        logger.info(
            "系统环回采样参数: loopback_rate=%sHz, target_rate=%sHz, "
            "loopback_chunk=%s, target_chunk=%s",
            self._loopback_sample_rate,
            self.config.sample_rate,
            self._loopback_chunk_size,
            self.config.chunk_size,
        )

    def _resolve_loopback_sample_rate(self) -> int:
        """
        解析系统环回采样率。

        优先读取环境变量 `SHERPA_ONNX_SYS_SAMPLE_RATE`，默认 48000Hz。
        """
        raw_value = os.environ.get("SHERPA_ONNX_SYS_SAMPLE_RATE", "48000").strip()
        try:
            loopback_sr = int(raw_value)
            if loopback_sr <= 0:
                raise ValueError
            return loopback_sr
        except Exception:
            logger.warning(
                "无效的 SHERPA_ONNX_SYS_SAMPLE_RATE=%r，回退到 48000Hz",
                raw_value,
            )
            return 48000

    def _build_resampler(self, source_sr: int, target_sr: int):
        """构建重采样函数，优先整数抽样，回退线性插值。"""
        if source_sr == target_sr:
            return lambda x: x.astype(np.float32, copy=False)

        # 常见场景：48k -> 16k，直接抽样降频，CPU开销最低
        if source_sr % target_sr == 0:
            step = source_sr // target_sr
            return lambda x: x[::step].astype(np.float32, copy=False)

        ratio = target_sr / source_sr

        def _linear_resample(x: np.ndarray) -> np.ndarray:
            if x.size == 0:
                return x.astype(np.float32, copy=False)
            new_len = max(1, int(round(len(x) * ratio)))
            if len(x) == 1:
                return np.repeat(x, new_len).astype(np.float32, copy=False)
            old_idx = np.arange(len(x), dtype=np.float64)
            new_idx = np.linspace(0, len(x) - 1, new_len, dtype=np.float64)
            return np.interp(new_idx, old_idx, x).astype(np.float32, copy=False)

        return _linear_resample

    def _resample_multichannel(self, data: np.ndarray) -> np.ndarray:
        """对多声道音频逐通道重采样，并裁齐到相同长度。"""
        if data.ndim != 2:
            return data.astype(np.float32, copy=False)

        if self._loopback_sample_rate == self.config.sample_rate:
            return data.astype(np.float32, copy=False)

        channels = data.shape[1]
        channel_arrays = []
        for channel_idx in range(channels):
            channel_arrays.append(self._resample_fn(data[:, channel_idx]))

        min_len = min(len(ch) for ch in channel_arrays)
        if min_len <= 0:
            return np.zeros((0, channels), dtype=np.float32)

        aligned = np.column_stack([ch[:min_len] for ch in channel_arrays])
        return aligned.astype(np.float32, copy=False)

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()

    def start(self) -> None:
        """启动环回音频捕获"""
        if self._is_running:
            logger.warning("环回音频捕获已在运行中")
            return

        try:
            # 1. 获取默认扬声器
            logger.info("获取系统默认扬声器...")
            self._speaker = sc.default_speaker()
            if not self._speaker:
                raise DeviceNotFoundError("未找到默认扬声器设备")

            logger.info(f"找到默认扬声器: {self._speaker.name}")

            # 2. 获取对应的环回麦克风
            logger.info("获取环回麦克风...")
            self._loopback_mic = sc.get_microphone(
                id=str(self._speaker.name),
                include_loopback=True
            )
            if not self._loopback_mic:
                raise DeviceNotFoundError("无法获取环回麦克风")

            logger.info(f"找到环回麦克风: {self._loopback_mic.name}, 通道数: {self._loopback_mic.channels}")

            # 3. 创建录制器
            logger.info("创建音频录制器...")
            self._recorder = self._loopback_mic.recorder(
                samplerate=self._loopback_sample_rate,
                blocksize=self._loopback_chunk_size
            )

            # 4. 启动捕获线程
            self._is_running = True
            self._stats['start_time'] = time.time()
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()

            logger.info("环回音频捕获已启动")

        except Exception as e:
            # 发生异常时清理资源
            self._cleanup()
            raise StreamError(f"启动环回音频捕获失败: {e}")

    def stop(self) -> None:
        """停止环回音频捕获"""
        if not self._is_running:
            return

        logger.info("正在停止环回音频捕获...")
        self._is_running = False

        try:
            # 等待捕获线程结束
            if self._capture_thread and self._capture_thread.is_alive():
                self._capture_thread.join(timeout=2.0)

            # 清空音频数据队列
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except Empty:
                    break

            logger.info("环回音频捕获已停止")

        except Exception as e:
            logger.error(f"停止环回音频捕获时发生错误: {e}")
        finally:
            # 确保总是执行清理操作
            self._cleanup()

    def add_callback(self, callback: Callable[[AudioChunk], None]) -> None:
        """
        添加音频数据回调函数

        Args:
            callback: 接收AudioChunk参数的回调函数
        """
        with self._callback_lock:
            self._callbacks.append(callback)
        logger.debug(f"已添加音频回调函数: {callback.__name__}")

    def remove_callback(self, callback: Callable[[AudioChunk], None]) -> None:
        """
        移除音频数据回调函数

        Args:
            callback: 要移除的回调函数
        """
        with self._callback_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
        logger.debug(f"已移除音频回调函数: {callback.__name__}")

    def get_audio_chunk(self, timeout: float = 1.0) -> Optional[AudioChunk]:
        """
        从队列获取下一个音频数据块

        Args:
            timeout: 超时时间（秒）

        Returns:
            AudioChunk: 音频数据块，超时则返回None
        """
        try:
            return self._audio_queue.get(timeout=timeout)
        except Empty:
            return None

    def get_stream_status(self) -> Optional[AudioStreamStatus]:
        """获取当前流状态"""
        if not self._is_running:
            return None

        try:
            current_time = time.time()
            if self._stats['start_time']:
                elapsed = current_time - self._stats['start_time']
                chunk_rate = self._stats['chunks_captured'] / elapsed if elapsed > 0 else 0
            else:
                chunk_rate = 0

            return AudioStreamStatus(
                is_active=self._is_running,
                is_stopped=not self._is_running,
                input_latency=0.01,  # soundcard通常延迟很低
                output_latency=0.0,
                sample_rate=float(self.config.sample_rate),
                cpu_load=0.1  # 估算的CPU使用率
            )
        except Exception as e:
            logger.error(f"获取流状态失败: {e}")
            return None

    @classmethod
    def list_available_devices(cls) -> List[AudioDevice]:
        """
        列出可用的音频设备

        Returns:
            List[AudioDevice]: 可用设备列表
        """
        if not SOUNDCARD_AVAILABLE:
            raise ConfigurationError("soundcard库不可用")

        devices = []

        try:
            # 获取所有扬声器
            speakers = sc.all_speakers()
            for i, speaker in enumerate(speakers):
                try:
                    device = AudioDevice(
                        index=i,
                        name=speaker.name,
                        max_input_channels=0,  # 扬声器是输出设备
                        max_output_channels=speaker.channels,
                        default_sample_rate=48000,  # soundcard常用采样率
                        is_default_input=False,
                        is_default_output=(speaker == sc.default_speaker())
                    )
                    devices.append(device)
                except Exception as e:
                    logger.warning(f"获取扬声器设备信息失败: {e}")

        except Exception as e:
            logger.error(f"列出音频设备失败: {e}")

        return devices

    @classmethod
    def find_default_loopback_device(cls) -> Optional[AudioDevice]:
        """
        查找默认的环回设备

        Returns:
            Optional[AudioDevice]: 默认环回设备信息，如果找不到则返回None
        """
        try:
            if not SOUNDCARD_AVAILABLE:
                return None

            speaker = sc.default_speaker()
            if not speaker:
                return None

            # 创建虚拟的环回设备信息
            device = AudioDevice(
                index=0,
                name=f"{speaker.name} (Loopback)",
                max_input_channels=speaker.channels,
                max_output_channels=0,
                default_sample_rate=48000,
                is_default_input=True,
                is_default_output=False
            )

            return device

        except Exception as e:
            logger.error(f"查找默认环回设备失败: {e}")
            return None

    def _capture_loop(self):
        """音频捕获循环"""
        logger.info("音频捕获循环已启动")

        try:
            with self._recorder as mic:
                while self._is_running:
                    try:
                        # 录制音频数据
                        data = mic.record(numframes=self._loopback_chunk_size)

                        if data is not None and data.size > 0:
                            # 更新统计信息
                            self._stats['chunks_captured'] += 1
                            self._stats['total_samples'] += data.size
                            self._stats['last_chunk_time'] = time.time()

                            # 确保数据是二维的 (samples, channels)
                            if data.ndim == 1:
                                # 单声道时补齐通道维度，保持后续处理一致
                                data = data.reshape(-1, 1)
                            elif data.ndim != 2:
                                logger.warning(
                                    f"捕获到异常维度音频数据 shape={data.shape}，将降级展平为单声道处理"
                                )
                                data = data.reshape(-1, 1)

                            # 将系统环回采样率重采样到目标采样率（通常 48k -> 16k）
                            data = self._resample_multichannel(data)

                            # 使用实际帧数计算持续时间，避免块大小与真实帧数不一致时统计偏差
                            frame_count = int(data.shape[0])
                            duration_ms = (frame_count / self.config.sample_rate) * 1000
                            channel_count = int(data.shape[1])

                            # soundcard 采集原本是浮点波形，这里保持 float32，减少量化损失
                            data = data.astype(np.float32, copy=False)

                            # 创建音频块（按样本主序展平，保持多声道交错顺序）
                            chunk = AudioChunk(
                                data=data.flatten(),  # 展平为一维数组
                                timestamp=time.time(),
                                sample_rate=self.config.sample_rate,
                                channels=channel_count,  # 使用实际声道数
                                duration_ms=duration_ms
                            )

                            # 添加到队列 (非阻塞)
                            try:
                                self._audio_queue.put_nowait(chunk)
                            except:
                                # 队列满，丢弃此块
                                logger.warning("音频队列已满，丢弃音频块")

                            # 调用回调函数
                            with self._callback_lock:
                                for callback in self._callbacks:
                                    try:
                                        callback(chunk)
                                    except Exception as e:
                                        logger.error(f"回调函数执行错误 {callback.__name__}: {e}")

                    except Exception as e:
                        if self._is_running:  # 只有在运行状态下才记录错误
                            logger.error(f"录制音频数据时发生错误: {e}")
                        time.sleep(0.01)  # 短暂等待后重试

        except Exception as e:
            logger.error(f"音频捕获循环异常: {e}")
        finally:
            logger.info("音频捕获循环已结束")

    def _cleanup(self) -> None:
        """清理资源"""
        self._is_running = False
        self._speaker = None
        self._loopback_mic = None
        self._recorder = None
        self._callbacks.clear()

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._is_running

    @property
    def stats(self) -> dict:
        """获取性能统计信息"""
        current_time = time.time()
        if self._stats['start_time']:
            elapsed = current_time - self._stats['start_time']
            if elapsed > 0:
                self._stats['chunk_rate'] = self._stats['chunks_captured'] / elapsed
                self._stats['samples_per_second'] = self._stats['total_samples'] / elapsed
            else:
                self._stats['chunk_rate'] = 0
                self._stats['samples_per_second'] = 0
        return self._stats.copy()


def create_soundcard_capture(config: AudioConfig) -> SoundcardLoopbackCapture:
    """
    创建soundcard环回音频捕获器

    Args:
        config: 音频配置

    Returns:
        SoundcardLoopbackCapture: 环回音频捕获器实例
    """
    return SoundcardLoopbackCapture(config)
