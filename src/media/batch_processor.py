"""
批量文件处理器

负责批量处理媒体文件,协调转换、转录和字幕生成流程
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import time
import numpy as np

from .converter import MediaConverter
from .subtitle_generator import SubtitleGenerator, Segment

# 导入scipy用于音频重采样
try:
    from scipy import signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class BatchProcessorError(Exception):
    """批量处理错误"""
    pass


class BatchProcessor:
    """
    批量文件处理器

    协调媒体转换、语音识别和字幕生成的完整流程
    支持单文件、多文件和目录批量处理

    Attributes:
        converter: 媒体转换器实例
        subtitle_gen: 字幕生成器实例
        stats: 处理统计信息

    Example:
        >>> from src.transcription.engine import TranscriptionEngine
        >>> from src.vad.detector import VoiceActivityDetector
        >>>
        >>> converter = MediaConverter()
        >>> subtitle_gen = SubtitleGenerator()
        >>> processor = BatchProcessor(converter, subtitle_gen)
        >>>
        >>> # 处理单个文件
        >>> result = processor.process_file(
        ...     Path("video.mp4"),
        ...     transcription_engine,
        ...     vad_detector,
        ...     output_dir=Path("subtitles/")
        ... )
    """

    def __init__(
        self,
        converter: MediaConverter,
        subtitle_gen: SubtitleGenerator
    ):
        """
        初始化批量处理器

        Args:
            converter: 媒体转换器实例
            subtitle_gen: 字幕生成器实例
        """
        self.converter = converter
        self.subtitle_gen = subtitle_gen
        self.stats = {
            'total_files': 0,
            'success_count': 0,
            'error_count': 0,
            'total_duration': 0.0,
            'total_time': 0.0,
        }
        logger.info("批量处理器初始化完成")

    def process_file(
        self,
        file_path: Path,
        transcription_engine,
        vad_detector,
        output_dir: Optional[Path] = None,
        subtitle_format: str = "srt",
        keep_temp: bool = False,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        处理单个媒体文件

        Args:
            file_path: 输入文件路径
            transcription_engine: 转录引擎实例
            vad_detector: VAD检测器实例
            output_dir: 输出目录,None表示与输入文件同目录
            subtitle_format: 字幕格式 (srt/vtt)
            keep_temp: 是否保留临时音频文件
            verbose: 是否显示详细信息

        Returns:
            Dict[str, Any]: 处理结果统计

        Raises:
            FileNotFoundError: 输入文件不存在
            BatchProcessorError: 处理过程错误
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 确定输出目录
        if output_dir is None:
            output_dir = file_path.parent
        else:
            output_dir.mkdir(parents=True, exist_ok=True)

        # 生成输出文件名
        subtitle_file = output_dir / f"{file_path.stem}.{subtitle_format}"

        temp_wav = None
        start_time = time.time()

        try:
            if verbose:
                print(f"\n处理文件: {file_path.name}")

            # 步骤1: 转换为WAV格式
            if verbose:
                print(f"  [1/3] 转换音频格式...")

            convert_start = time.time()
            temp_wav = self.converter.convert_to_wav(
                file_path,
                sample_rate=16000,
                show_progress=verbose
            )
            convert_time = time.time() - convert_start

            # 步骤2: VAD分段和语音识别
            if verbose:
                print(f"  [2/3] 语音识别中...")

            transcribe_start = time.time()
            segments = self._transcribe_audio(
                temp_wav,
                transcription_engine,
                vad_detector,
                verbose=verbose
            )
            transcribe_time = time.time() - transcribe_start

            # 步骤3: 生成字幕文件
            if verbose:
                print(f"  [3/3] 生成字幕文件...")

            subtitle_start = time.time()
            if subtitle_format.lower() == "srt":
                self.subtitle_gen.generate_srt(segments, subtitle_file)
            elif subtitle_format.lower() == "vtt":
                self.subtitle_gen.generate_vtt(segments, subtitle_file)
            else:
                raise BatchProcessorError(f"不支持的字幕格式: {subtitle_format}")
            subtitle_time = time.time() - subtitle_start

            # 计算总时长和RTF (Real-Time Factor)
            total_time = time.time() - start_time

            # 读取音频时长 (近似计算)
            audio_duration = self._estimate_audio_duration(temp_wav)
            rtf = total_time / audio_duration if audio_duration > 0 else 0

            # 更新统计信息
            result = {
                'file': str(file_path),
                'subtitle_file': str(subtitle_file),
                'success': True,
                'segments_count': len(segments),
                'audio_duration': audio_duration,
                'convert_time': convert_time,
                'transcribe_time': transcribe_time,
                'subtitle_time': subtitle_time,
                'total_time': total_time,
                'rtf': rtf,
                'error': None
            }

            if verbose:
                print(f"  ✓ 已保存: {subtitle_file.name}")
                print(f"    转录: {len(segments)}个片段, 时长: {audio_duration:.1f}s, RTF: {rtf:.2f}")

            logger.info(f"文件处理成功: {file_path.name}, RTF={rtf:.2f}")

            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"文件处理失败: {file_path.name}, 错误: {error_msg}")

            if verbose:
                print(f"  ✗ 处理失败: {error_msg}")

            return {
                'file': str(file_path),
                'subtitle_file': None,
                'success': False,
                'error': error_msg
            }

        finally:
            # 清理临时文件
            if temp_wav and not keep_temp:
                self.converter.cleanup_temp_file(temp_wav)

    def _transcribe_audio(
        self,
        audio_file: Path,
        transcription_engine,
        vad_detector,
        sample_rate: int = 16000,
        verbose: bool = False
    ) -> List[Segment]:
        """
        转录音频文件并生成字幕片段

        Args:
            audio_file: 音频文件路径
            transcription_engine: 转录引擎
            vad_detector: VAD检测器
            sample_rate: 采样率
            verbose: 是否显示详细信息

        Returns:
            List[Segment]: 字幕片段列表

        Note:
            参考 generate-subtitles.py line 584-643
            使用sherpa-onnx的VAD进行语音分段,然后批量转录
        """
        import soundfile as sf
        import sherpa_onnx

        # 读取音频文件
        audio_data, sr = sf.read(audio_file, dtype='float32')

        # 修复Issue #2: 采样率不匹配时自动重采样
        if sr != sample_rate:
            logger.warning(f"音频采样率 {sr} 与目标 {sample_rate} 不匹配，正在重采样...")
            if SCIPY_AVAILABLE:
                try:
                    # 使用scipy进行重采样
                    num_samples = int(len(audio_data) * sample_rate / sr)
                    audio_data = signal.resample(audio_data, num_samples)
                    logger.info(f"重采样完成: {sr}Hz -> {sample_rate}Hz")
                except Exception as e:
                    logger.error(f"重采样失败: {e}")
                    raise RuntimeError(f"音频重采样失败 ({sr}Hz -> {sample_rate}Hz): {e}")
            else:
                logger.error("scipy未安装，无法重采样。请安装: pip install scipy")
                raise RuntimeError(f"音频采样率不匹配且无法重采样 ({sr}Hz != {sample_rate}Hz)")

        # 如果是立体声,转为单声道
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)

        # 获取转录引擎的recognizer (sherpa-onnx OfflineRecognizer)
        if not hasattr(transcription_engine, '_recognizer') or transcription_engine._recognizer is None:
            raise RuntimeError("转录引擎未正确初始化,缺少_recognizer")

        recognizer = transcription_engine._recognizer

        # 创建sherpa-onnx VAD配置
        vad_config = sherpa_onnx.VadModelConfig()

        # 使用Silero VAD模型
        # 修复Issue #3: 验证VAD模型路径是否存在
        vad_model_path = vad_detector.config.effective_model_path
        if not Path(vad_model_path).exists():
            raise FileNotFoundError(f"VAD模型文件不存在: {vad_model_path}。请检查VAD配置。")

        vad_config.silero_vad.model = vad_model_path
        vad_config.silero_vad.threshold = vad_detector.config.threshold

        # 修复Issue #1: VAD配置参数单位转换 (ms -> 秒)
        # 从VadConfig读取配置并转换单位
        vad_config.silero_vad.min_silence_duration = vad_detector.config.min_silence_duration_ms / 1000.0
        vad_config.silero_vad.min_speech_duration = vad_detector.config.min_speech_duration_ms / 1000.0
        vad_config.silero_vad.max_speech_duration = vad_detector.config.max_speech_duration_ms / 1000.0
        vad_config.sample_rate = sample_rate

        # 创建VAD检测器
        vad = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=100)

        # 使用VAD处理音频数据
        window_size = vad_config.silero_vad.window_size
        buffer = []

        if verbose:
            print(f"    处理音频: 长度={len(audio_data)/sample_rate:.1f}s")

        # 逐窗口处理音频
        num_processed_samples = 0
        for i in range(0, len(audio_data), window_size):
            window = audio_data[i:i + window_size]

            # 确保窗口长度一致
            if len(window) < window_size:
                window = np.pad(window, (0, window_size - len(window)), mode='constant')

            buffer = np.concatenate([buffer, window])
            num_processed_samples += len(window)

            # 当缓冲区足够大时,送入VAD
            while len(buffer) >= window_size:
                vad.accept_waveform(buffer[:window_size])
                buffer = buffer[window_size:]

        # 处理完所有音频后,flush VAD
        vad.flush()

        # 收集VAD检测到的语音段并批量转录
        streams = []
        segments = []

        while not vad.empty():
            # 获取VAD检测到的语音段
            vad_segment = vad.front

            # 创建字幕段对象
            segment = Segment(
                start=vad_segment.start / sample_rate,
                duration=len(vad_segment.samples) / sample_rate,
                text=""  # 稍后填充
            )
            segments.append(segment)

            # 创建识别流并输入音频
            stream = recognizer.create_stream()
            stream.accept_waveform(sample_rate, vad_segment.samples)
            streams.append(stream)

            # 移除已处理的段
            vad.pop()

        if verbose:
            print(f"    VAD检测到 {len(segments)} 个语音段")

        # 批量解码所有语音段 (提升性能)
        for stream in streams:
            recognizer.decode_stream(stream)

        # 提取转录结果
        for i, (seg, stream) in enumerate(zip(segments, streams)):
            result = stream.result
            seg.text = result.text.strip() if hasattr(result, 'text') and result.text else ""

            if verbose and seg.text:
                print(f"    [{i+1}/{len(segments)}] {seg.start:.1f}s: {seg.text[:50]}...")

        # 过滤空文本的段
        segments = [seg for seg in segments if seg.text]

        logger.info(f"音频转录完成, 生成 {len(segments)} 个有效片段")
        return segments

    def _estimate_audio_duration(self, audio_file: Path) -> float:
        """
        估算音频时长

        Args:
            audio_file: 音频文件路径

        Returns:
            float: 音频时长(秒)
        """
        try:
            import soundfile as sf
            info = sf.info(audio_file)
            return info.duration
        except Exception as e:
            logger.warning(f"无法获取音频时长: {e}")
            return 0.0

    def process_files(
        self,
        file_paths: List[Path],
        transcription_engine,
        vad_detector,
        output_dir: Optional[Path] = None,
        subtitle_format: str = "srt",
        keep_temp: bool = False,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        批量处理多个文件

        Args:
            file_paths: 文件路径列表
            transcription_engine: 转录引擎实例
            vad_detector: VAD检测器实例
            output_dir: 输出目录
            subtitle_format: 字幕格式
            keep_temp: 是否保留临时文件
            verbose: 是否显示详细信息

        Returns:
            Dict[str, Any]: 批量处理统计信息
        """
        total_files = len(file_paths)
        success_count = 0
        error_count = 0
        results = []

        start_time = time.time()

        if verbose:
            print(f"\n=== 批量处理: {total_files} 个文件 ===\n")

        for i, file_path in enumerate(file_paths, start=1):
            if verbose:
                print(f"[{i}/{total_files}] 处理: {file_path.name}")

            try:
                result = self.process_file(
                    file_path,
                    transcription_engine,
                    vad_detector,
                    output_dir=output_dir,
                    subtitle_format=subtitle_format,
                    keep_temp=keep_temp,
                    verbose=verbose
                )

                results.append(result)

                if result['success']:
                    success_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"文件处理异常: {file_path.name}, {e}")
                if verbose:
                    print(f"  ✗ 异常: {e}")

        total_time = time.time() - start_time

        # 生成统计报告
        stats = {
            'total_files': total_files,
            'success_count': success_count,
            'error_count': error_count,
            'total_time': total_time,
            'results': results
        }

        if verbose:
            print(f"\n=== 处理完成 ===")
            print(f"总文件数: {total_files}")
            print(f"成功: {success_count}")
            print(f"失败: {error_count}")
            print(f"总耗时: {total_time:.1f}秒")

        return stats

    def process_directory(
        self,
        dir_path: Path,
        transcription_engine,
        vad_detector,
        output_dir: Optional[Path] = None,
        subtitle_format: str = "srt",
        recursive: bool = False,
        keep_temp: bool = False,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        处理目录下的所有媒体文件

        Args:
            dir_path: 目录路径
            transcription_engine: 转录引擎实例
            vad_detector: VAD检测器实例
            output_dir: 输出目录
            subtitle_format: 字幕格式
            recursive: 是否递归处理子目录
            keep_temp: 是否保留临时文件
            verbose: 是否显示详细信息

        Returns:
            Dict[str, Any]: 处理统计信息

        Raises:
            NotADirectoryError: 路径不是目录
        """
        if not dir_path.is_dir():
            raise NotADirectoryError(f"不是有效的目录: {dir_path}")

        # 收集所有支持的媒体文件
        media_files = []

        if recursive:
            # 递归搜索
            for ext in self.converter.SUPPORTED_VIDEO_FORMATS + self.converter.SUPPORTED_AUDIO_FORMATS:
                media_files.extend(dir_path.rglob(f"*{ext}"))
        else:
            # 仅当前目录
            for ext in self.converter.SUPPORTED_VIDEO_FORMATS + self.converter.SUPPORTED_AUDIO_FORMATS:
                media_files.extend(dir_path.glob(f"*{ext}"))

        if not media_files:
            logger.warning(f"目录中未找到支持的媒体文件: {dir_path}")
            if verbose:
                print(f"警告: 目录中未找到支持的媒体文件")

        return self.process_files(
            media_files,
            transcription_engine,
            vad_detector,
            output_dir=output_dir,
            subtitle_format=subtitle_format,
            keep_temp=keep_temp,
            verbose=verbose
        )
