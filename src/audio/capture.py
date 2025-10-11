"""
音频捕获实现模块 (Audio Capture Implementation)

提供实时音频捕获功能，支持麦克风和系统音频
- 使用PyAudio库进行底层音频处理
- 支持多种音频设备和格式
- 提供异步回调机制和队列缓冲
- 包含完整的设备管理和错误处理
"""

# 标准库导入
import time                                    # 时间处理
import logging                                 # 日志记录
import threading                               # 线程同步
from typing import List, Optional, Callable, Iterator  # 类型提示
from queue import Queue, Empty                 # 队列和空队列异常
import numpy as np                             # 数值计算

# 尝试导入PyAudio音频库，检查可用性
try:
    import pyaudio                             # 跨平台音频I/O库
    PYAUDIO_AVAILABLE = True                   # PyAudio可用标志
except ImportError:
    PYAUDIO_AVAILABLE = False                  # PyAudio不可用
    pyaudio = None                             # 设置为None以避免使用

# 导入本模块的数据模型和异常类
from .models import (
    AudioDevice,           # 音频设备信息
    AudioConfig,           # 音频配置
    AudioChunk,            # 音频数据块
    AudioStreamStatus,     # 音频流状态
    AudioSourceType,       # 音频源类型枚举
    AudioFormat,           # 音频格式枚举
    AudioCaptureError,     # 基础异常
    DeviceNotFoundError,   # 设备未找到异常
    StreamError,           # 音频流异常
    ConfigurationError     # 配置异常
)

# 创建模块级别的日志记录器
logger = logging.getLogger(__name__)


class AudioCapture:
    """
    音频捕获管理器 (Audio Capture Manager)

    处理麦克风和系统音频捕获，包含设备管理功能

    主要功能：
    - 管理PyAudio音频流的生命周期
    - 提供音频数据的回调机制
    - 支持设备检测和选择
    - 处理音频数据的队列缓冲
    - 监控音频流状态和性能
    """

    def __init__(self, config: AudioConfig):
        """
        初始化音频捕获器

        Args:
            config: 音频配置对象，包含采样率、声道数等参数

        Raises:
            ConfigurationError: PyAudio不可用或配置无效时抛出
        """
        # 检查PyAudio是否可用
        if not PYAUDIO_AVAILABLE:
            raise ConfigurationError(
                "PyAudio不可用。请使用以下命令安装: pip install PyAudio"
            )

        # 保存配置
        self.config = config

        # 初始化PyAudio相关对象
        self._audio = None                      # PyAudio实例
        self._stream = None                     # 音频流对象

        # 状态管理
        self._is_running = False                # 运行状态标志

        # 音频数据缓冲和回调
        self._audio_queue = Queue()             # 音频数据队列
        self._callback_lock = threading.Lock()  # 回调函数锁
        self._callbacks: List[Callable[[AudioChunk], None]] = []  # 回调函数列表

        # 验证配置的有效性
        if not self.config.validate():
            raise ConfigurationError("音频配置无效")

        logger.info(f"已初始化AudioCapture，配置: {config}")

    def __enter__(self):
        """上下文管理器入口

        自动启动音频捕获，支持with语句使用

        Returns:
            AudioCapture: 当前实例
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口

        自动停止音频捕获并清理资源

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪信息
        """
        self.stop()

    def start(self) -> None:
        """启动音频捕获

        初始化PyAudio，获取设备信息，创建并启动音频流

        Raises:
            StreamError: 音频流启动失败时抛出
        """
        if self._is_running:
            logger.warning("音频捕获已在运行中")
            return

        try:
            # 创建PyAudio实例
            self._audio = pyaudio.PyAudio()

            # 查找并验证音频设备
            device_info = self._get_device_info()

            # 配置音频流参数
            stream_params = self._get_stream_parameters(device_info)

            # 创建并启动音频流，设置回调函数
            self._stream = self._audio.open(
                stream_callback=self._audio_callback,  # 音频数据回调
                **stream_params                        # 流参数
            )

            self._is_running = True
            logger.info(f"已在设备上启动音频捕获: {device_info['name']}")

        except Exception as e:
            # 发生异常时清理资源
            self._cleanup()
            raise StreamError(f"启动音频捕获失败: {e}")

    def stop(self) -> None:
        """停止音频捕获

        安全地停止音频流，释放PyAudio资源，清空队列
        """
        if not self._is_running:
            return

        self._is_running = False

        try:
            # 停止并关闭音频流
            if self._stream:
                self._stream.stop_stream()     # 停止流
                self._stream.close()           # 关闭流
                self._stream = None

            # 终止PyAudio实例
            if self._audio:
                self._audio.terminate()        # 释放PyAudio资源
                self._audio = None

            # 清空音频数据队列，防止内存泄漏
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except Empty:
                    break

            logger.info("已停止音频捕获")

        except Exception as e:
            logger.error(f"停止音频捕获时发生错误: {e}")
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
        """Get current stream status"""
        if not self._stream or not self._is_running:
            return None

        try:
            return AudioStreamStatus(
                is_active=self._stream.is_active(),
                is_stopped=self._stream.is_stopped(),
                input_latency=getattr(self._stream, 'input_latency', 0.0),
                output_latency=getattr(self._stream, 'output_latency', 0.0),
                sample_rate=float(self.config.sample_rate),
                cpu_load=getattr(self._stream, 'cpu_load', 0.0)
            )
        except Exception as e:
            logger.error(f"Failed to get stream status: {e}")
            return None

    @classmethod
    def list_devices(cls) -> List[AudioDevice]:
        """
        List available audio devices

        Returns:
            List of AudioDevice objects
        """
        if not PYAUDIO_AVAILABLE:
            raise ConfigurationError("PyAudio is not available")

        devices = []
        audio = pyaudio.PyAudio()

        try:
            device_count = audio.get_device_count()
            default_input = audio.get_default_input_device_info()
            default_output = audio.get_default_output_device_info()

            for i in range(device_count):
                try:
                    info = audio.get_device_info_by_index(i)

                    device = AudioDevice(
                        index=i,
                        name=info['name'],
                        max_input_channels=info['maxInputChannels'],
                        max_output_channels=info['maxOutputChannels'],
                        default_sample_rate=info['defaultSampleRate'],
                        is_default_input=(i == default_input['index']),
                        is_default_output=(i == default_output['index'])
                    )
                    devices.append(device)

                except Exception as e:
                    logger.warning(f"Failed to get info for device {i}: {e}")

        finally:
            audio.terminate()

        return devices

    @classmethod
    def find_device_by_name(cls, name: str) -> Optional[AudioDevice]:
        """
        Find device by name

        Args:
            name: Device name to search for

        Returns:
            AudioDevice or None if not found
        """
        devices = cls.list_devices()
        for device in devices:
            if name.lower() in device.name.lower():
                return device
        return None

    @classmethod
    def get_default_input_device(cls) -> Optional[AudioDevice]:
        """Get default input device"""
        devices = cls.list_devices()
        for device in devices:
            if device.is_default_input:
                return device
        return None

    def _get_device_info(self) -> dict:
        """Get device information for current configuration"""
        if self.config.device_index is not None:
            try:
                return self._audio.get_device_info_by_index(self.config.device_index)
            except Exception as e:
                raise DeviceNotFoundError(f"Device index {self.config.device_index} not found: {e}")
        else:
            # Use default input device
            try:
                return self._audio.get_default_input_device_info()
            except Exception as e:
                raise DeviceNotFoundError(f"No default input device found: {e}")

    def _get_stream_parameters(self, device_info: dict) -> dict:
        """Get stream parameters for PyAudio"""
        # Determine format
        if "16" in self.config.format_type.value:
            format_type = pyaudio.paInt16
        elif "32" in self.config.format_type.value:
            format_type = pyaudio.paInt32
        else:
            format_type = pyaudio.paInt16

        return {
            'format': format_type,
            'channels': self.config.channels,
            'rate': self.config.sample_rate,
            'input': True,
            'output': False,
            'input_device_index': device_info['index'],
            'frames_per_buffer': self.config.frames_per_buffer,
            'start': True
        }

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio stream callback"""
        if not self._is_running:
            return (None, pyaudio.paComplete)

        try:
            # Convert audio data to numpy array
            if "16" in self.config.format_type.value:
                audio_data = np.frombuffer(in_data, dtype=np.int16)
            elif "32" in self.config.format_type.value:
                audio_data = np.frombuffer(in_data, dtype=np.int32)
            else:
                audio_data = np.frombuffer(in_data, dtype=np.int16)

            # Calculate duration
            duration_ms = (frame_count / self.config.sample_rate) * 1000

            # Create audio chunk
            chunk = AudioChunk(
                data=audio_data,
                timestamp=time.time(),
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                duration_ms=duration_ms
            )

            # Add to queue (non-blocking)
            try:
                self._audio_queue.put_nowait(chunk)
            except:
                # Queue full, skip this chunk
                logger.warning("Audio queue full, dropping chunk")

            # Call callbacks
            with self._callback_lock:
                for callback in self._callbacks:
                    try:
                        callback(chunk)
                    except Exception as e:
                        logger.error(f"Error in audio callback {callback.__name__}: {e}")

        except Exception as e:
            logger.error(f"Error in audio callback: {e}")

        return (None, pyaudio.paContinue)

    def _cleanup(self) -> None:
        """Cleanup resources"""
        self._is_running = False
        self._callbacks.clear()

    @property
    def is_running(self) -> bool:
        """Check if audio capture is running"""
        return self._is_running


class SystemAudioCapture(AudioCapture):
    """
    System audio capture implementation

    优先使用soundcard库直接从扬声器获取环回音频，
    如果不可用则回退到PyAudio立体声混音方案
    """

    def __init__(self, config: AudioConfig):
        """Initialize system audio capture"""
        # 检查是否使用soundcard方案
        self._use_soundcard = self._should_use_soundcard()

        if self._use_soundcard:
            # 使用soundcard方案
            try:
                from .soundcard_capture import SoundcardLoopbackCapture
                self._soundcard_capture = SoundcardLoopbackCapture(config)
                self._pyaudio_capture = None
                logger.info("Initialized SystemAudioCapture with soundcard backend")
            except Exception as e:
                logger.warning(f"Failed to initialize soundcard backend: {e}, falling back to PyAudio")
                self._use_soundcard = False
                self._soundcard_capture = None
                super().__init__(config)
                self._pyaudio_capture = self  # PyAudio capture is self
                logger.info("Initialized SystemAudioCapture with PyAudio backend (fallback)")
        else:
            # 使用PyAudio方案
            super().__init__(config)
            self._soundcard_capture = None
            self._pyaudio_capture = self
            logger.info("Initialized SystemAudioCapture with PyAudio backend")

    def _should_use_soundcard(self) -> bool:
        """判断是否应该使用soundcard方案"""
        try:
            import soundcard as sc
            # 检查是否有默认扬声器
            speaker = sc.default_speaker()
            if speaker:
                logger.info(f"Found default speaker: {speaker.name}, preferring soundcard backend")
                return True
        except ImportError:
            logger.info("soundcard library not available, using PyAudio backend")
        except Exception as e:
            logger.warning(f"Error checking soundcard availability: {e}, using PyAudio backend")

        return False

    def start(self) -> None:
        """启动音频捕获"""
        if self._use_soundcard and self._soundcard_capture:
            self._soundcard_capture.start()
            # 更新父类状态
            self._is_running = True
        else:
            super().start()

    def stop(self) -> None:
        """停止音频捕获"""
        if self._use_soundcard and self._soundcard_capture:
            self._soundcard_capture.stop()
            # 更新父类状态
            self._is_running = False
        else:
            super().stop()

    def add_callback(self, callback: Callable[[AudioChunk], None]) -> None:
        """添加音频数据回调函数"""
        if self._use_soundcard and self._soundcard_capture:
            self._soundcard_capture.add_callback(callback)
        else:
            super().add_callback(callback)

    def remove_callback(self, callback: Callable[[AudioChunk], None]) -> None:
        """移除音频数据回调函数"""
        if self._use_soundcard and self._soundcard_capture:
            self._soundcard_capture.remove_callback(callback)
        else:
            super().remove_callback(callback)

    def get_audio_chunk(self, timeout: float = 1.0) -> Optional[AudioChunk]:
        """从队列获取下一个音频数据块"""
        if self._use_soundcard and self._soundcard_capture:
            return self._soundcard_capture.get_audio_chunk(timeout)
        else:
            return super().get_audio_chunk(timeout)

    def get_stream_status(self) -> Optional[AudioStreamStatus]:
        """获取当前流状态"""
        if self._use_soundcard and self._soundcard_capture:
            return self._soundcard_capture.get_stream_status()
        else:
            return super().get_stream_status()

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        if self._use_soundcard and self._soundcard_capture:
            return self._soundcard_capture.is_running
        else:
            return super().is_running

    @property
    def backend_type(self) -> str:
        """获取当前使用的后端类型"""
        return "soundcard" if self._use_soundcard else "pyaudio"

    @property
    def stats(self) -> dict:
        """获取性能统计信息"""
        if self._use_soundcard and self._soundcard_capture:
            return self._soundcard_capture.stats
        else:
            return {
                'chunks_captured': 0,  # PyAudio版本暂不提供统计
                'total_samples': 0,
                'chunk_rate': 0,
                'samples_per_second': 0
            }

    @classmethod
    def find_system_audio_device(cls) -> Optional[AudioDevice]:
        """
        查找系统音频设备

        优先尝试soundcard环回设备，如果不可用则查找PyAudio立体声混音设备
        """
        # 首先尝试soundcard方案
        try:
            from .soundcard_capture import SoundcardLoopbackCapture
            loopback_device = SoundcardLoopbackCapture.find_default_loopback_device()
            if loopback_device:
                logger.info(f"Found soundcard loopback device: {loopback_device.name}")
                return loopback_device
        except Exception as e:
            logger.debug(f"Soundcard device search failed: {e}")

        # 回退到PyAudio立体声混音方案
        logger.info("Falling back to PyAudio stereo mix search")
        devices = cls.list_devices()

        # Common system audio device names (English and Chinese)
        system_audio_names = [
            "stereo mix", "what u hear", "wave out mix",
            "speakers", "system audio", "loopback",
            "立体声混音", "立体混音", "混音", "loopback",
            "what u hear", "wave out", "录音混音"
        ]

        for device in devices:
            if device.is_input_device:
                device_name_lower = device.name.lower()
                device_name_original = device.name

                for sys_name in system_audio_names:
                    # 检查英文匹配（不区分大小写）
                    if sys_name.isascii() and sys_name in device_name_lower:
                        logger.info(f"Found PyAudio system audio device: {device.name}")
                        return device
                    # 检查中文匹配（区分大小写）
                    elif not sys_name.isascii() and sys_name in device_name_original:
                        logger.info(f"Found PyAudio system audio device: {device.name}")
                        return device

        return None

    @classmethod
    def get_available_backends(cls) -> List[str]:
        """
        获取可用的音频捕获后端列表

        Returns:
            List[str]: 可用的后端列表
        """
        backends = []

        # 检查soundcard
        try:
            import soundcard as sc
            speaker = sc.default_speaker()
            if speaker:
                backends.append("soundcard")
        except:
            pass

        # 检查PyAudio
        try:
            import pyaudio
            backends.append("pyaudio")
        except:
            pass

        return backends

    @classmethod
    def list_system_audio_devices(cls) -> List[AudioDevice]:
        """
        列出所有可用的系统音频捕获设备

        Returns:
            List[AudioDevice]: 系统音频设备列表
        """
        devices = []

        # 添加soundcard环回设备
        try:
            from .soundcard_capture import SoundcardLoopbackCapture
            loopback_device = SoundcardLoopbackCapture.find_default_loopback_device()
            if loopback_device:
                loopback_device.name = f"{loopback_device.name} (Soundcard)"
                devices.append(loopback_device)
        except Exception as e:
            logger.debug(f"Failed to get soundcard devices: {e}")

        # 添加PyAudio立体声混音设备
        try:
            stereo_device = cls.find_system_audio_device()
            if stereo_device:
                # 检查是否已经在列表中（避免重复）
                if not any(device.name == stereo_device.name for device in devices):
                    stereo_device.name = f"{stereo_device.name} (PyAudio)"
                    devices.append(stereo_device)
        except Exception as e:
            logger.debug(f"Failed to get PyAudio devices: {e}")

        return devices


class MicrophoneCapture(AudioCapture):
    """
    Microphone capture implementation

    Captures audio from microphone input
    """

    def __init__(self, config: AudioConfig):
        """Initialize microphone capture"""
        super().__init__(config)
        logger.info("Initialized MicrophoneCapture")

    @classmethod
    def find_microphone_device(cls) -> Optional[AudioDevice]:
        """Find default microphone device"""
        return cls.get_default_input_device()


def create_audio_capture(
    source_type: AudioSourceType,
    config: AudioConfig
) -> AudioCapture:
    """
    Factory function to create appropriate audio capture

    Args:
        source_type: Type of audio source
        config: Audio configuration

    Returns:
        AudioCapture instance
    """
    if source_type == AudioSourceType.MICROPHONE:
        return MicrophoneCapture(config)
    elif source_type == AudioSourceType.SYSTEM_AUDIO:
        return SystemAudioCapture(config)
    else:
        raise ValueError(f"Unknown audio source type: {source_type}")