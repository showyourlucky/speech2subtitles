"""
批量文件处理器

负责批量处理媒体文件,协调转换、转录和字幕生成流程
"""
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .converter import MediaConverter
from .subtitle_generator import Segment, SubtitleGenerator

# 回调函数类型定义
OnFileStart = Callable[[int, int, str], None]  # (file_index, total_files, filename)
OnFileProgress = Callable[[int, float], None]  # (file_index, progress_percent)
OnSegment = Callable[[Segment], None]  # (segment)
OnFileComplete = Callable[
    [str, str, float, float], None
]  # (file_path, subtitle_file, duration, rtf)

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


class BatchProcessorCancelled(BatchProcessorError):
    """批量处理被取消"""

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

    def __init__(self, converter: MediaConverter, subtitle_gen: SubtitleGenerator):
        """
        初始化批量处理器

        Args:
            converter: 媒体转换器实例
            subtitle_gen: 字幕生成器实例
        """
        self.converter = converter
        self.subtitle_gen = subtitle_gen
        self.stats = {
            "total_files": 0,
            "success_count": 0,
            "error_count": 0,
            "total_duration": 0.0,
            "total_time": 0.0,
        }
        logger.info("批量处理器初始化完成")

    def process_file(
        self,
        file_path: Path,
        transcription_engine,
        vad_detector,
        output_dir: Path | None = None,
        subtitle_format: str = "srt",
        keep_temp: bool = False,
        verbose: bool = False,
        # 新增: 回调参数用于GUI进度显示
        on_progress: OnFileProgress | None = None,
        on_segment: OnSegment | None = None,
        cancel_event: threading.Event | None = None,
        file_index: int = 0,  # 文件索引,用于进度回调
    ) -> dict[str, Any]:
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
            on_progress: 进度回调函数 (file_index, progress_percent)
            on_segment: 片段回调函数 (segment), 用于实时预览
            cancel_event: 取消事件, 设置后停止处理
            file_index: 文件索引, 用于进度回调

        Returns:
            Dict[str, Any]: 处理结果统计
                - success: bool, 是否成功
                - file: str, 输入文件路径
                - subtitle_file: str, 输出字幕文件路径
                - segments: List[Segment], 转录片段列表 (新增)
                - segments_count: int, 片段数量
                - audio_duration: float, 音频时长
                - convert_time: float, 转换耗时
                - transcribe_time: float, 转录耗时
                - subtitle_time: float, 字幕生成耗时
                - total_time: float, 总耗时
                - rtf: float, Real-Time Factor
                - error: str, 错误信息 (失败时)

        Raises:
            FileNotFoundError: 输入文件不存在
            BatchProcessorError: 处理过程错误
            BatchProcessorCancelled: 用户取消处理
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
            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                raise BatchProcessorCancelled("用户取消处理")

            if verbose:
                print(f"\n处理文件: {file_path.name}")

            # 初始进度: 0%
            if on_progress:
                on_progress(file_index, 0.0)

            # 步骤1: 转换为WAV格式
            if verbose:
                print("  [1/3] 转换音频格式...")

            convert_start = time.time()
            temp_wav = self.converter.convert_to_wav(
                file_path, sample_rate=16000, show_progress=verbose
            )
            convert_time = time.time() - convert_start

            # 转换完成: 25%
            if on_progress:
                on_progress(file_index, 25.0)

            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                raise BatchProcessorCancelled("用户取消处理")

            # 步骤2: VAD分段和语音识别
            if verbose:
                print("  [2/3] 语音识别中...")

            transcribe_start = time.time()
            segments = self._transcribe_audio(
                temp_wav,
                transcription_engine,
                vad_detector,
                verbose=verbose,
                on_segment=on_segment,  # 传递segment回调
                on_progress=lambda p: on_progress(file_index, 25.0 + p * 0.6)
                if on_progress
                else None,  # 25%-85%
                cancel_event=cancel_event,  # 传递取消事件
            )
            transcribe_time = time.time() - transcribe_start

            # 转录完成: 85%
            if on_progress:
                on_progress(file_index, 85.0)

            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                raise BatchProcessorCancelled("用户取消处理")

            # 步骤3: 生成字幕文件
            if verbose:
                print("  [3/3] 生成字幕文件...")

            subtitle_start = time.time()
            if subtitle_format.lower() == "srt":
                self.subtitle_gen.generate_srt(segments, subtitle_file)
            elif subtitle_format.lower() == "vtt":
                self.subtitle_gen.generate_vtt(segments, subtitle_file)
            else:
                raise BatchProcessorError(f"不支持的字幕格式: {subtitle_format}")
            subtitle_time = time.time() - subtitle_start

            # 字幕生成完成: 100%
            if on_progress:
                on_progress(file_index, 100.0)

            # 计算总时长和RTF (Real-Time Factor)
            total_time = time.time() - start_time

            # 读取音频时长 (近似计算)
            audio_duration = self._estimate_audio_duration(temp_wav)
            rtf = total_time / audio_duration if audio_duration > 0 else 0

            # 更新统计信息 (新增segments字段用于GUI显示)
            result = {
                "file": str(file_path),
                "subtitle_file": str(subtitle_file),
                "success": True,
                "segments": segments,  # 新增: 完整segment列表供GUI使用
                "segments_count": len(segments),
                "audio_duration": audio_duration,
                "convert_time": convert_time,
                "transcribe_time": transcribe_time,
                "subtitle_time": subtitle_time,
                "total_time": total_time,
                "rtf": rtf,
                "error": None,
            }

            if verbose:
                print(f"  ✓ 已保存: {subtitle_file.name}")
                print(
                    f"    转录: {len(segments)}个片段, "
                    f"时长: {audio_duration:.1f}s, RTF: {rtf:.2f}"
                )

            logger.info(f"文件处理成功: {file_path.name}, RTF={rtf:.2f}")

            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"文件处理失败: {file_path.name}, 错误: {error_msg}")

            if verbose:
                print(f"  ✗ 处理失败: {error_msg}")

            return {
                "file": str(file_path),
                "subtitle_file": None,
                "success": False,
                "error": error_msg,
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
        verbose: bool = False,
        on_segment: OnSegment | None = None,
        on_progress: Callable[[float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> list[Segment]:
        """
        转录音频文件并生成字幕片段

        Args:
            audio_file: 音频文件路径
            transcription_engine: 转录引擎
            vad_detector: VAD检测器（通过VadManager获取）
            sample_rate: 采样率
            verbose: 是否显示详细信息
            on_segment: Segment回调函数,用于实时预览
            on_progress: 进度回调函数 (0-100)
            cancel_event: 取消事件

        Returns:
            List[Segment]: 字幕片段列表

        Raises:
            BatchProcessorCancelled: 用户取消处理

        Note:
            参考 generate-subtitles.py line 584-643
            使用sherpa-onnx的VAD进行语音分段,然后批量转录

            此方法使用VadManager管理的VAD检测器的底层sherpa-onnx模型,
            以支持批量处理所需的特殊API (buffer_size_in_seconds=100)
        """
        import sherpa_onnx
        import soundfile as sf

        # 检查取消事件
        if cancel_event and cancel_event.is_set():
            raise BatchProcessorCancelled("用户取消处理")

        # 读取音频文件
        audio_data, sr = sf.read(audio_file, dtype="float32")

        # 初始进度
        if on_progress:
            on_progress(0.0)

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
        if (
            not hasattr(transcription_engine, "_recognizer")
            or transcription_engine._recognizer is None
        ):
            raise RuntimeError("转录引擎未正确初始化,缺少_recognizer")

        recognizer = transcription_engine._recognizer

        # 使用VadManager管理的VAD检测器的底层模型进行批量处理
        # 注意: batch_processor需要使用sherpa-onnx的批量处理API (buffer_size_in_seconds=100),
        # 这与VadManager提供的流式检测API不同。因此这里访问底层的_vad_model。
        # 但VAD配置和模型加载仍然通过VadManager统一管理,确保配置一致性。

        # 检查vad_detector是否由VadManager管理
        if not hasattr(vad_detector, "_detector"):
            raise RuntimeError("VAD检测器必须通过VadManager获取")

        # 获取底层的sherpa-onnx VAD模型
        underlying_detector = vad_detector._detector
        if (
            not hasattr(underlying_detector, "_vad_model")
            or underlying_detector._vad_model is None
        ):
            raise RuntimeError("VAD检测器未正确初始化或不支持批量处理模式")

        # 验证模型路径是否存在
        vad_model_path = vad_detector.config.effective_model_path
        if not Path(vad_model_path).exists():
            raise FileNotFoundError(f"VAD模型文件不存在: {vad_model_path}。请检查VAD配置。")

        # 创建批量处理专用的sherpa-onnx VAD配置
        vad_config = sherpa_onnx.VadModelConfig()

        # 从VadManager管理的配置中读取参数
        vad_config.silero_vad.model = vad_model_path
        vad_config.silero_vad.threshold = vad_detector.config.threshold

        # 修复Issue #1: VAD配置参数单位转换 (ms -> 秒)
        vad_config.silero_vad.min_silence_duration = (
            vad_detector.config.min_silence_duration_ms / 1000.0
        )
        vad_config.silero_vad.min_speech_duration = (
            vad_detector.config.min_speech_duration_ms / 1000.0
        )
        vad_config.silero_vad.max_speech_duration = (
            vad_detector.config.max_speech_duration_ms / 1000.0
        )
        vad_config.sample_rate = sample_rate

        # 创建批量处理专用的VAD检测器（使用特殊的buffer_size参数）
        # 虽然创建了新的实例,但配置来自VadManager,确保一致性
        vad = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=100)
        logger.info("批量处理VAD检测器创建成功 (使用VadManager配置, buffer_size=100s)")

        # 使用VAD处理音频数据
        window_size = vad_config.silero_vad.window_size
        buffer = []

        if verbose:
            print(f"    处理音频: 长度={len(audio_data)/sample_rate:.1f}s")

        # 逐窗口处理音频
        num_processed_samples = 0
        total_samples = len(audio_data)

        for i in range(0, len(audio_data), window_size):
            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                raise BatchProcessorCancelled("用户取消处理")

            window = audio_data[i : i + window_size]

            # 确保窗口长度一致
            if len(window) < window_size:
                window = np.pad(window, (0, window_size - len(window)), mode="constant")

            buffer = np.concatenate([buffer, window])
            num_processed_samples += len(window)

            # 当缓冲区足够大时,送入VAD
            while len(buffer) >= window_size:
                vad.accept_waveform(buffer[:window_size])
                buffer = buffer[window_size:]

            # 更新进度 (VAD处理占30%)
            if on_progress and total_samples > 0:
                progress = (num_processed_samples / total_samples) * 30.0
                on_progress(progress)

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
                text="",  # 稍后填充
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

        # VAD完成: 30%
        if on_progress:
            on_progress(30.0)

        # 检查取消事件
        if cancel_event and cancel_event.is_set():
            raise BatchProcessorCancelled("用户取消处理")
        # 开始时间
        start_time = time.time()
        # 批量解码所有语音段 (提升性能)
        total_streams = len(streams)
        # for idx, stream in enumerate(streams):
        #     # 检查取消事件
        #     if cancel_event and cancel_event.is_set():
        #         raise BatchProcessorCancelled("用户取消处理")

        #     recognizer.decode_stream(stream)

        #     # 更新进度 (转录占60%)
        #     if on_progress and total_streams > 0:
        #         progress = 30.0 + ((idx + 1) / total_streams) * 60.0
        #         on_progress(progress)

        # 使用sherpa-onnx的批量解码API (一次性解码所有流, 内部优化)
        recognizer.decode_streams(streams)
        # 接码耗时
        end_time = time.time()
        logger.info(f"批量解码耗时: {end_time - start_time:.2f}s")
        # # 提取转录结果
        for i, (seg, stream) in enumerate(zip(segments, streams)):
            result = stream.result
            seg.text = (
                result.text.strip() if hasattr(result, "text") and result.text else ""
            )

            # 实时segment回调 (用于GUI预览)
            if on_segment and seg.text:
                on_segment(seg)

            if verbose and seg.text:
                print(
                    f"    [{i+1}/{len(segments)}] {seg.start:.1f}s: {seg.text[:50]}..."
                )

        # 过滤空文本的段
        segments = [seg for seg in segments if seg.text]

        # 转录完成: 100%
        if on_progress:
            on_progress(100.0)

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
        file_paths: list[Path],
        transcription_engine,
        vad_detector,
        output_dir: Path | None = None,
        subtitle_format: str = "srt",
        keep_temp: bool = False,
        verbose: bool = False,
        # 新增: 批量处理回调参数
        on_file_start: OnFileStart | None = None,
        on_file_progress: OnFileProgress | None = None,
        on_segment: OnSegment | None = None,
        on_file_complete: OnFileComplete | None = None,
        cancel_event: threading.Event | None = None,
        continue_on_error: bool = True,
    ) -> dict[str, Any]:
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
            on_file_start: 文件开始回调 (file_index, total_files, filename)
            on_file_progress: 文件进度回调 (file_index, progress_percent)
            on_segment: Segment回调 (segment), 用于实时预览
            on_file_complete: 文件完成回调 (file_path, subtitle_file, duration, rtf)
                IMPORTANT: subtitle_file使用空字符串("")表示失败状态
                - 成功: subtitle_file为字幕文件路径字符串
                - 失败/异常: subtitle_file为空字符串"", duration=0.0, rtf=0.0
                - 取消: 不触发此回调，BatchProcessorCancelled异常会被抛出到调用方
            cancel_event: 取消事件
            continue_on_error: 遇到错误是否继续处理后续文件

        Returns:
            Dict[str, Any]: 批量处理统计信息
                - total_files: int, 总文件数
                - success_count: int, 成功数量
                - error_count: int, 失败数量
                - errors: List[(file, error)], 错误列表
                - total_time: float, 总耗时
                - results: List[Dict], 每个文件的处理结果
        """
        total_files = len(file_paths)
        success_count = 0
        error_count = 0
        results = []
        errors = []  # 新增: 收集错误信息

        start_time = time.time()

        if verbose:
            print(f"\n=== 批量处理: {total_files} 个文件 ===\n")

        for i, file_path in enumerate(file_paths, start=1):
            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                logger.info(f"批量处理被取消,已处理 {i-1}/{total_files} 个文件")
                break

            # 文件开始回调
            if on_file_start:
                on_file_start(i - 1, total_files, file_path.name)

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
                    verbose=verbose,
                    on_progress=on_file_progress,  # 传递进度回调
                    on_segment=on_segment,  # 传递segment回调
                    cancel_event=cancel_event,  # 传递取消事件
                    file_index=i - 1,  # 传递文件索引
                )

                results.append(result)

                if result["success"]:
                    success_count += 1

                    # 文件完成回调
                    if on_file_complete:
                        on_file_complete(
                            result["file"],
                            result["subtitle_file"],
                            result["audio_duration"],
                            result["rtf"],
                        )
                else:
                    error_count += 1
                    error_detail = result.get("error", "Unknown error")
                    errors.append((str(file_path), error_detail))

                    # 增强日志：提供更多失败上下文
                    logger.warning(
                        f"文件处理失败: {file_path.name} - {error_detail} "
                        f"(第 {i}/{total_files} 个文件)"
                    )

                    # 修复: 失败时也调用完成回调（传递空字符串和0值表示失败）
                    if on_file_complete:
                        on_file_complete(
                            result["file"],
                            "",  # 空字符串表示失败,没有字幕文件
                            0.0,  # 音频时长未知
                            0.0,  # RTF未知
                        )

            except BatchProcessorCancelled:
                # 用户取消,直接抛出
                logger.info(
                    f"批量处理被取消: {file_path.name} "
                    f"(已处理 {i}/{total_files} 个文件, "
                    f"成功 {success_count}, 失败 {error_count})"
                )
                # 取消不触发on_file_complete，由GUI Worker独立处理（见file_transcription_dialog.py Line 136-138）
                raise

            except Exception as e:
                error_count += 1
                error_msg = str(e)
                errors.append((str(file_path), error_msg))
                logger.error(
                    f"文件处理异常: {file_path.name} - {error_msg} "
                    f"(第 {i}/{total_files} 个文件)",
                    exc_info=True  # 包含完整的异常堆栈信息
                )

                if verbose:
                    print(f"  ✗ 异常: {error_msg}")

                # 修复: 异常时也调用完成回调（传递空字符串和0值表示失败）
                if on_file_complete:
                    on_file_complete(
                        str(file_path),
                        "",  # 空字符串表示异常,没有字幕文件
                        0.0,  # 音频时长未知
                        0.0,  # RTF未知
                    )

                # 如果不继续处理,则抛出异常
                if not continue_on_error:
                    raise

        total_time = time.time() - start_time

        # 生成统计报告 (新增errors字段)
        stats = {
            "total_files": total_files,
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,  # 新增: 错误详情列表
            "total_time": total_time,
            "results": results,
        }

        if verbose:
            print("\n=== 处理完成 ===")
            print(f"总文件数: {total_files}")
            print(f"成功: {success_count}")
            print(f"失败: {error_count}")
            if errors:
                print("\n错误详情:")
                for file_path, error in errors:
                    print(f"  - {file_path}: {error}")
            print(f"总耗时: {total_time:.1f}秒")

        return stats

    def process_directory(
        self,
        dir_path: Path,
        transcription_engine,
        vad_detector,
        output_dir: Path | None = None,
        subtitle_format: str = "srt",
        recursive: bool = False,
        keep_temp: bool = False,
        verbose: bool = False,
    ) -> dict[str, Any]:
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
            for ext in (
                self.converter.SUPPORTED_VIDEO_FORMATS
                + self.converter.SUPPORTED_AUDIO_FORMATS
            ):
                media_files.extend(dir_path.rglob(f"*{ext}"))
        else:
            # 仅当前目录
            for ext in (
                self.converter.SUPPORTED_VIDEO_FORMATS
                + self.converter.SUPPORTED_AUDIO_FORMATS
            ):
                media_files.extend(dir_path.glob(f"*{ext}"))

        if not media_files:
            logger.warning(f"目录中未找到支持的媒体文件: {dir_path}")
            if verbose:
                print("警告: 目录中未找到支持的媒体文件")

        return self.process_files(
            media_files,
            transcription_engine,
            vad_detector,
            output_dir=output_dir,
            subtitle_format=subtitle_format,
            keep_temp=keep_temp,
            verbose=verbose,
        )
