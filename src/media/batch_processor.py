"""
批量文件处理器

负责批量处理媒体文件,协调转换、转录和字幕生成流程
"""
import json
import logging
import os
import re
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

# 核心处理链路(便于快速理解):
# 1) process_file/process_files 负责文件级生命周期管理(进度、异常、统计、回调)
# 2) _prepare_merged_mode_context 完成“音频读取 + VAD喂数”阶段
# 3) _transcribe_merged_vad_segments 负责“VAD段分组 + 批量解码 + 文本回填”
# 4) _normalize_segments 负责最终字幕的时间轴清理


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

    def __init__(
        self,
        converter: MediaConverter,
        subtitle_gen: SubtitleGenerator,
        transcribe_per_vad_segment: bool = True,
        stream_merge_target_duration: float = 15.0,
        stream_long_segment_threshold: float = 8.0,
        stream_merge_max_gap: float = 0.6,
        max_subtitle_duration: float = 5.0,
        debug_dump_vad_segments: bool | None = None,
        debug_dump_dir: Path | str | None = None,
    ):
        """
        初始化批量处理器

        Args:
            converter: 媒体转换器实例
            subtitle_gen: 字幕生成器实例
            transcribe_per_vad_segment: 是否逐VAD片段独立识别
            stream_merge_target_duration: 短语音段合并目标时长(秒)
            stream_long_segment_threshold: 长语音段阈值(秒)
            stream_merge_max_gap: 允许合并的最大静音间隔(秒)
            max_subtitle_duration: 单条字幕最大时长(秒)
            debug_dump_vad_segments: 是否导出VAD调试信息(默认关闭,可通过环境变量开启)
            debug_dump_dir: VAD调试输出目录(默认: temp/vad_debug)
        """
        self.converter = converter
        self.subtitle_gen = subtitle_gen
        # 以下阈值统一在初始化时做边界保护，避免运行期出现非法参数导致流程中断。
        # 说明:
        # - merge_target_duration: 短语音分组后的目标总时长(包含组内静音)
        # - long_segment_threshold: 超过该阈值的段单独成组，不与其它段合并
        # - merge_max_gap: 相邻段静音超过该值则强制断组
        # - max_subtitle_duration: 单条输出字幕最大时长，超出后进入拆分策略
        self.transcribe_per_vad_segment = bool(transcribe_per_vad_segment)
        self.stream_merge_target_duration = max(0.1, float(stream_merge_target_duration))
        self.stream_long_segment_threshold = max(0.1, float(stream_long_segment_threshold))
        self.stream_merge_max_gap = max(0.0, float(stream_merge_max_gap))
        self.max_subtitle_duration = max(0.1, float(max_subtitle_duration))
        # 配置优先级: 显式参数 > 环境变量 > 默认值。
        # 这样可以兼顾代码调用侧、CLI/GUI环境配置和开箱默认行为。
        env_debug_enabled = self._parse_bool_env(os.getenv("S2S_DEBUG_DUMP_VAD_SEGMENTS"))
        self.debug_dump_vad_segments = (
            env_debug_enabled if debug_dump_vad_segments is None else bool(debug_dump_vad_segments)
        )
        env_debug_dir = os.getenv("S2S_DEBUG_DUMP_DIR")
        resolved_debug_dir = debug_dump_dir or env_debug_dir or Path("temp") / "vad_debug"
        self.debug_dump_dir = Path(resolved_debug_dir)
        self.stats = {
            "total_files": 0,
            "success_count": 0,
            "error_count": 0,
            "total_duration": 0.0,
            "total_time": 0.0,
        }
        logger.info(
            (
                "批量处理器初始化完成: transcribe_per_vad_segment=%s, "
                "debug_dump_vad_segments=%s, debug_dump_dir=%s"
            ),
            self.transcribe_per_vad_segment,
            self.debug_dump_vad_segments,
            self.debug_dump_dir,
        )

    @staticmethod
    def _parse_bool_env(value: str | None) -> bool:
        """解析环境变量布尔值。"""
        if value is None:
            return False
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    def _create_debug_session(self, audio_file: Path) -> dict[str, Any] | None:
        """
        创建本次转录的调试会话目录。

        Note:
            调试导出为可选能力，任何导出失败都不应中断主流程。
        """
        if not self.debug_dump_vad_segments:
            return None

        try:
            timestamp_ms = int(time.time() * 1000)
            run_dir = self.debug_dump_dir / f"{audio_file.stem}_{timestamp_ms}"
            segments_dir = run_dir / "segments"
            segments_dir.mkdir(parents=True, exist_ok=True)
            return {
                "enabled": True,
                "run_dir": run_dir,
                "segments_dir": segments_dir,
                "audio_file": str(audio_file),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            logger.warning("创建VAD调试目录失败，已降级关闭导出: %s", e)
            return None

    def _dump_debug_json(
        self,
        debug_session: dict[str, Any] | None,
        filename: str,
        payload: dict[str, Any],
    ) -> None:
        """写入调试JSON文件(失败仅记录日志)。"""
        if not debug_session:
            return
        try:
            output_file = debug_session["run_dir"] / filename
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("写入调试文件失败(%s): %s", filename, e)

    def _dump_vad_segment_audio(
        self,
        debug_session: dict[str, Any] | None,
        segment_index: int,
        sample_rate: int,
        segment_data: np.ndarray,
        start_s: float,
        end_s: float,
    ) -> None:
        """导出单个VAD段音频。"""
        if not debug_session:
            return
        try:
            import soundfile as sf

            seg_name = (
                f"seg_{segment_index:05d}_"
                f"{start_s:.3f}_{end_s:.3f}.wav"
            )
            output_file = debug_session["segments_dir"] / seg_name
            sf.write(output_file, segment_data, sample_rate, subtype="PCM_16")
        except Exception as e:
            logger.warning(
                "导出VAD段音频失败(seg=%s, %.3f-%.3f): %s",
                segment_index,
                start_s,
                end_s,
                e,
            )

    def _load_audio_for_transcription(
        self,
        audio_file: Path,
        sample_rate: int,
    ) -> np.ndarray:
        """
        读取并预处理音频数据（重采样 + 单声道化）。

        Args:
            audio_file: 音频文件路径
            sample_rate: 目标采样率

        Returns:
            np.ndarray: float32单声道音频数据
        """
        import soundfile as sf

        audio_data, sr = sf.read(audio_file, dtype="float32")

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

        return np.asarray(audio_data, dtype=np.float32)

    def _get_offline_recognizer(self, transcription_engine):
        """
        获取离线识别器实例。

        Args:
            transcription_engine: 转录引擎实例

        Returns:
            sherpa-onnx OfflineRecognizer实例
        """
        # 获取转录引擎的recognizer (sherpa-onnx OfflineRecognizer)
        if (
            not hasattr(transcription_engine, "_recognizer")
            or transcription_engine._recognizer is None
        ):
            raise RuntimeError("转录引擎未正确初始化,缺少_recognizer")

        return transcription_engine._recognizer

    def _create_batch_vad_detector(
        self,
        vad_detector,
        sample_rate: int,
    ) -> tuple[Any, int]:
        """
        基于VadManager配置创建批量处理专用VAD检测器。

        Args:
            vad_detector: 由VadManager管理的检测器包装对象
            sample_rate: 目标采样率

        Returns:
            tuple[Any, int]: (批量VAD实例, window_size)
        """
        import sherpa_onnx

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
        return vad, vad_config.silero_vad.window_size

    def _feed_audio_to_vad(
        self,
        audio_data: np.ndarray,
        vad,
        window_size: int,
        on_progress: Callable[[float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """
        按固定窗口将音频送入VAD。

        Args:
            audio_data: 预处理后的音频数据
            vad: 批量VAD检测器
            window_size: VAD窗口大小
            on_progress: 进度回调（0~30）
            cancel_event: 取消事件
        """
        # 逐窗口处理音频
        total_samples = len(audio_data)
        for i in range(0, len(audio_data), window_size):
            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                raise BatchProcessorCancelled("用户取消处理")

            window = audio_data[i : i + window_size]
            current_window_size = len(window)

            # 确保窗口长度一致
            if len(window) < window_size:
                window = np.pad(window, (0, window_size - len(window)), mode="constant")

            # 直接送入固定窗口，避免反复拼接数组导致额外拷贝
            vad.accept_waveform(window)

            # 更新进度 (VAD处理占30%)
            if on_progress and total_samples > 0:
                num_processed_samples = min(i + current_window_size, total_samples)
                progress = (num_processed_samples / total_samples) * 30.0
                on_progress(progress)

    # ------------------------------------------------------------------
    # 文本拆分 / 分配 辅助方法（从 _transcribe_merged_vad_segments 提升）
    # ------------------------------------------------------------------

    _SENTENCE_PATTERN = re.compile(r'[。！？.!?]')
    _CLAUSE_PATTERN = re.compile(r'[，、；：,;:]')

    def _split_text_by_punctuation(self, text: str, pattern: re.Pattern) -> list[str]:
        """按标点符号拆分文本,保留标点在前一段末尾"""
        parts = []
        last = 0
        for m in pattern.finditer(text):
            parts.append(text[last:m.end()])
            last = m.end()
        if last < len(text):
            parts.append(text[last:])
        return [p.strip() for p in parts if p.strip()]

    def _build_subtitle_segments(
        self,
        text_parts: list[str],
        start: float,
        duration: float,
        split_boundaries: list[float] | None = None,
    ) -> list[Segment]:
        """
        根据文本拆分结果生成字幕段。

        优先使用 split_boundaries（相对起点的分界秒数）进行时间切分，
        否则退化为按字符数比例分配时间。
        """
        if not text_parts:
            return []
        result: list[Segment] = []

        # 优先使用"音频对齐后的切分点"，降低字幕提前/延后
        if split_boundaries and len(split_boundaries) == len(text_parts) - 1:
            points = [0.0]
            for boundary in split_boundaries:
                points.append(max(points[-1], min(float(boundary), duration)))
            points.append(max(points[-1], duration))

            for i, part in enumerate(text_parts):
                seg_start = start + points[i]
                seg_duration = max(0.01, points[i + 1] - points[i])
                result.append(
                    Segment(
                        start=seg_start,
                        duration=seg_duration,
                        text=part,
                    )
                )
            return result

        total_chars = sum(len(p) for p in text_parts)
        if total_chars == 0:
            return []

        elapsed = 0.0
        for part in text_parts:
            ratio = len(part) / total_chars
            seg_duration = duration * ratio
            result.append(
                Segment(
                    start=start + elapsed,
                    duration=seg_duration,
                    text=part,
                )
            )
            elapsed += seg_duration
        return result

    def _find_audio_aligned_boundaries(
        self,
        segment_samples: np.ndarray | None,
        sample_rate_hz: int,
        duration_s: float,
        target_ratios: list[float],
    ) -> list[float]:
        """
        在理想切分比例附近寻找音频低能量点，作为字幕分界。

        说明：
        - 该策略不依赖 ASR token 时间戳，适用于 qwen_asr 等"无时间戳"结果。
        - 若音频能量无法提供有效信息，则返回空列表，由上层回退到比例切分。
        """
        if (
            segment_samples is None
            or sample_rate_hz <= 0
            or duration_s <= 0
            or not target_ratios
        ):
            # 入参不满足“可计算切分点”的最小条件时，直接回退到上层默认策略。
            return []

        samples = np.asarray(segment_samples, dtype=np.float32).reshape(-1)
        if samples.size < 16:
            # 样本太短时，能量曲线没有统计意义，继续计算只会引入噪声。
            return []

        # 30ms 帧 + 10ms 帧移，兼顾时间分辨率与稳定性
        frame_size = max(64, int(sample_rate_hz * 0.03))
        hop_size = max(32, int(sample_rate_hz * 0.01))
        if samples.size <= frame_size:
            # 少于一帧时无法形成“可比较的多帧能量”，直接放弃音频对齐。
            return []

        frame_count = 1 + (samples.size - frame_size) // hop_size
        if frame_count <= 1:
            # 仅有一帧同样无法做“低能量点搜索”。
            return []

        # 使用前缀和计算每帧均方能量，减少重复求和开销
        sq = np.square(samples, dtype=np.float32)
        prefix = np.concatenate(([0.0], np.cumsum(sq, dtype=np.float64)))
        energies = np.empty(frame_count, dtype=np.float64)
        for frame_idx in range(frame_count):
            left = frame_idx * hop_size
            right = left + frame_size
            energies[frame_idx] = (prefix[right] - prefix[left]) / frame_size

        # 轻微平滑，降低单帧抖动
        if frame_count >= 5:
            kernel = np.ones(5, dtype=np.float64) / 5.0
            energies = np.convolve(energies, kernel, mode="same")

        # frame_times 与 energies 一一对应，后续会用它在目标窗口内搜索最佳切分点。
        frame_times = (
            np.arange(frame_count, dtype=np.float64) * hop_size + frame_size / 2.0
        ) / float(sample_rate_hz)

        # 时长以"VAD段标注时长"和"样本时长"较小值为准，避免越界
        sample_duration_s = samples.size / float(sample_rate_hz)
        effective_duration_s = max(0.01, min(float(duration_s), sample_duration_s))

        boundaries: list[float] = []
        prev_boundary_s = 0.0
        min_gap_s = 0.08  # 避免切分点过于密集导致闪屏/抖动
        search_half_window_s = 0.8

        for ratio in target_ratios:
            # ratio 是累计文本比例(0~1)，ideal_s 是“理想切点时间”。
            ideal_s = float(ratio) * effective_duration_s

            # 实际搜索窗口围绕理想切点展开，同时保证:
            # 1) 不越过前一个切点(保持时间单调递增)
            # 2) 不贴到段首/段尾(给字幕留出最小展示时长)
            low_s = max(prev_boundary_s + min_gap_s, ideal_s - search_half_window_s)
            high_s = min(
                effective_duration_s - min_gap_s,
                ideal_s + search_half_window_s,
            )

            if high_s <= low_s:
                # 窗口无效时采用保守回退: 直接使用裁剪后的理想点。
                aligned_s = max(
                    prev_boundary_s + min_gap_s,
                    min(ideal_s, effective_duration_s - min_gap_s),
                )
                boundaries.append(aligned_s)
                prev_boundary_s = aligned_s
                continue

            frame_indices = np.where((frame_times >= low_s) & (frame_times <= high_s))[0]
            if frame_indices.size == 0:
                # 没找到可用帧时与上面一致，回退到理想点。
                aligned_s = max(
                    prev_boundary_s + min_gap_s,
                    min(ideal_s, effective_duration_s - min_gap_s),
                )
                boundaries.append(aligned_s)
                prev_boundary_s = aligned_s
                continue

            local_times = frame_times[frame_indices]
            local_energies = energies[frame_indices]

            # 归一化到0~1，便于把“能量项”和“距离项”组合成统一评分。
            energy_min = float(np.min(local_energies))
            energy_max = float(np.max(local_energies))
            if energy_max > energy_min:
                norm_energy = (local_energies - energy_min) / (energy_max - energy_min)
            else:
                norm_energy = np.zeros_like(local_energies)

            dist = np.abs(local_times - ideal_s)
            dist_max = max(float(np.max(dist)), 1e-6)
            norm_dist = dist / dist_max

            # 以"低能量优先"为主，距离理想点为辅
            score = norm_energy * 0.75 + norm_dist * 0.25
            best_local_idx = int(np.argmin(score))
            aligned_s = float(local_times[best_local_idx])
            aligned_s = max(
                prev_boundary_s + min_gap_s,
                min(aligned_s, effective_duration_s - min_gap_s),
            )
            boundaries.append(aligned_s)
            prev_boundary_s = aligned_s

        return boundaries

    def _split_fine_by_nearest_break(
        self, text: str, num_parts: int
    ) -> list[str]:
        """按字符数等分,但在标点或空格附近切分,避免截断词语"""
        if num_parts <= 1 or not text:
            return [text]
        # 收集所有可能的切分点(标点后一位)
        break_positions = set()
        for m in re.finditer(r'[。！？，、；：,.!?;:\s]', text):
            break_positions.add(m.end())

        total_len = len(text)
        target_len = total_len / num_parts
        parts = []
        last = 0
        for i in range(1, num_parts):
            # 预留 remaining_slots 个字符位给后续分段，避免前段吃光文本。
            remaining_slots = num_parts - i
            min_pos = last + 1
            max_pos = max(min_pos, total_len - remaining_slots)
            ideal_pos = max(min_pos, min(int(target_len * i), max_pos))
            # 在理想位置附近找最近的标点断点
            best = ideal_pos
            best_dist = total_len
            for bp in break_positions:
                if bp < min_pos or bp > max_pos:
                    continue
                d = abs(bp - ideal_pos)
                if d < best_dist:
                    best_dist = d
                    best = bp
            # 如果附近没有断点,使用理想位置
            if best_dist > max(4, int(target_len * 0.6)):
                # 偏离过大宁可按理想位置切，也不强行追求标点。
                best = ideal_pos
            if best <= last:
                best = ideal_pos
            parts.append(text[last:best])
            last = best
        if last < total_len:
            parts.append(text[last:])
        return [p for p in parts if p.strip()]

    def _split_text_to_subtitles(
        self,
        text: str,
        start: float,
        duration: float,
        sample_rate: int,
        segment_samples: np.ndarray | None = None,
    ) -> list[Segment]:
        """
        将一段文本拆分为 ≤max_subtitle_duration 的字幕段。

        时间切分策略：
        1) 先按标点拆文本；
        2) 再用"音频低能量点"对齐分界（可用时）；
        3) 最后回退到字符比例切分。
        """
        max_subtitle_duration = self.max_subtitle_duration
        if not text or duration <= max_subtitle_duration:
            # 为空或本身足够短时，不做拆分，避免不必要的时间轴扰动。
            return [Segment(start=start, duration=duration, text=text)]

        # 这里是“最少需要拆成几段”而不是“最多几段”。
        # 例如时长11秒且max=5秒，会得到3段(而不是2段)。
        num_parts = max(2, int(duration / max_subtitle_duration) + 1)
        # 第一层: 尝试按句级标点拆分
        parts = self._split_text_by_punctuation(text, self._SENTENCE_PATTERN)

        # 如果句级拆分不够细,继续按子句标点拆分
        if len(parts) < num_parts:
            expanded = []
            for p in parts:
                sub_parts = self._split_text_by_punctuation(p, self._CLAUSE_PATTERN)
                expanded.extend(sub_parts if sub_parts else [p])
            parts = expanded

        # 如果仍然不够细,在标点附近智能等分
        if len(parts) < num_parts:
            fine_parts = self._split_fine_by_nearest_break(
                text, num_parts
            )
            if len(fine_parts) > len(parts):
                parts = fine_parts

        total_chars = sum(len(part) for part in parts)
        split_boundaries: list[float] | None = None
        if total_chars > 0 and len(parts) > 1:
            # 先按字符占比给出“理想切分比例”，再交给音频对齐逻辑寻找低能量边界。
            # 这样可以同时兼顾语义完整性(文本)与听感边界(音频)。
            cumulative_chars = 0
            target_ratios: list[float] = []
            for part in parts[:-1]:
                cumulative_chars += len(part)
                target_ratios.append(cumulative_chars / total_chars)

            aligned_boundaries = self._find_audio_aligned_boundaries(
                segment_samples=segment_samples,
                sample_rate_hz=sample_rate,
                duration_s=duration,
                target_ratios=target_ratios,
            )
            if len(aligned_boundaries) == len(parts) - 1:
                # 只有数量完全匹配才采用，避免“部分对齐 + 部分比例”带来的时间跳变。
                split_boundaries = aligned_boundaries

        return self._build_subtitle_segments(
            parts,
            start,
            duration,
            split_boundaries=split_boundaries,
        )

    def _distribute_text_by_punctuation(
        self, full_text: str, weights: list[float]
    ) -> list[str]:
        """
        按标点将完整文本分配到多个目标段。

        参数 weights 通常是时长权重，也可来自 token 时间戳权重。
        """
        if not weights or not full_text:
            return [full_text] if full_text else []

        # 先按所有标点拆分为最小片段
        all_parts = self._split_text_by_punctuation(
            full_text, self._SENTENCE_PATTERN
        )
        refined = []
        for p in all_parts:
            sub = self._split_text_by_punctuation(p, self._CLAUSE_PATTERN)
            refined.extend(sub if sub else [p])
        all_parts = refined

        normalized_weights = [max(0.0, w) for w in weights]
        total_weight = sum(normalized_weights)
        total_chars = len(full_text)
        if not all_parts or total_chars == 0 or total_weight <= 0:
            # 退化为按字符数分配
            return self._distribute_text_by_ratio(
                full_text, weights
            )

        # 将片段按目标权重分组
        result_texts = []
        part_idx = 0
        accumulated_text = ""
        accumulated_ratio = 0.0

        for i, weight in enumerate(normalized_weights):
            target_ratio = weight / total_weight
            if i == len(normalized_weights) - 1:
                # 最后一段: 分配剩余所有文本
                remaining = "".join(all_parts[part_idx:])
                result_texts.append(
                    (accumulated_text + remaining).strip()
                )
                accumulated_text = ""
                break

            # 累加片段直到达到目标比例
            while part_idx < len(all_parts):
                part_ratio = len(all_parts[part_idx]) / total_chars
                if accumulated_ratio + part_ratio <= target_ratio * 1.15 or not accumulated_text:
                    # 加入该片段(允许15%超出,避免切断)
                    accumulated_text += all_parts[part_idx]
                    accumulated_ratio += part_ratio
                    part_idx += 1
                else:
                    break

            result_texts.append(accumulated_text.strip())
            accumulated_text = ""
            accumulated_ratio = 0.0

        while len(result_texts) < len(weights):
            # 与目标段数量对齐，防止上游按索引读取时越界。
            result_texts.append("")

        # 若标点分配产生较多空段，自动回退到比例分配，降低漏字幕概率
        empty_count = sum(1 for text_item in result_texts if not text_item.strip())
        if empty_count > 0:
            fallback = self._distribute_text_by_ratio(full_text, weights)
            fallback_empty_count = sum(
                1 for text_item in fallback if not text_item.strip()
            )
            if fallback_empty_count < empty_count:
                return fallback

        return result_texts

    def _distribute_text_by_ratio(
        self, full_text: str, weights: list[float]
    ) -> list[str]:
        """按权重比例按字符数分配文本(最后兜底)"""
        total_weight = sum(weights)
        total_chars = len(full_text)
        if total_chars == 0 or total_weight <= 0:
            # 权重异常时保持“每段都有文本”的保守行为，避免上游空指针或越界。
            return [full_text] * len(weights)

        result = []
        remaining = full_text
        # 近似每段字符数,用于控制"就近标点切分"的最大偏移
        avg_target_len = max(1, int(total_chars / max(1, len(weights))))
        for i, weight in enumerate(weights):
            if i < len(weights) - 1:
                ratio = max(0.0, weight) / total_weight
                # 为后续段预留最小字符数，避免前段过量吃掉文本导致后段空分配
                remaining_slots = len(weights) - i - 1
                remaining_chars = len(remaining)
                desired_count = max(1, int(total_chars * ratio))
                if remaining_chars <= 0:
                    char_count = 0
                elif remaining_chars > remaining_slots:
                    # 至少给后续每段保留1个字符配额，防止后续全空。
                    max_allowed = max(1, remaining_chars - remaining_slots)
                    char_count = min(max_allowed, desired_count)
                else:
                    # 字符不足以覆盖所有后续段，当前段尽量少拿，给后续留机会
                    char_count = 1
                if 0 < char_count < remaining_chars:
                    # 质量修复: 回退到字符比例分配时，优先对齐到附近标点/空白，降低断词概率
                    min_cut = 1
                    max_cut = max(1, remaining_chars - remaining_slots)
                    ideal_cut = max(min_cut, min(char_count, max_cut))
                    best_cut = ideal_cut
                    best_dist = remaining_chars
                    for m in re.finditer(r'[。！？，、；：,.!?;:\s]', remaining):
                        bp = m.end()
                        if bp < min_cut or bp > max_cut:
                            continue
                        d = abs(bp - ideal_cut)
                        if d < best_dist:
                            best_dist = d
                            best_cut = bp
                    max_offset = max(4, int(avg_target_len * 0.6))
                    char_count = best_cut if best_dist <= max_offset else ideal_cut
                result.append(remaining[:char_count])
                remaining = remaining[char_count:]
            else:
                result.append(remaining)
        return result

    def _extract_timestamp_weights(
        self,
        result_obj: Any,
        timeline: list[dict[str, Any]],
    ) -> list[float] | None:
        """
        从识别结果中提取 token 时间戳权重。

        返回每个原始 VAD 段对应的 token 数量(平滑后)；若不可用则返回 None。
        """
        token_timestamps = getattr(result_obj, "timestamps", None)
        if not isinstance(token_timestamps, list) or not token_timestamps:
            # 不同ASR实现可能没有timestamps字段，直接回退时长权重。
            return None

        valid_timestamps = []
        for ts in token_timestamps:
            try:
                valid_timestamps.append(float(ts))
            except Exception:
                # 单个异常时间戳不影响整体，按“尽量可用”策略跳过。
                continue

        if not valid_timestamps:
            return None

        raw_weights: list[float] = []
        for i, item in enumerate(timeline):
            start_s = item["merged_start"]
            end_s = item["merged_end"]
            if i == len(timeline) - 1:
                # 最后一段使用闭区间，避免尾部token因浮点误差被丢失。
                count = sum(1 for ts in valid_timestamps if start_s <= ts <= end_s)
            else:
                count = sum(1 for ts in valid_timestamps if start_s <= ts < end_s)
            raw_weights.append(float(count))

        if sum(raw_weights) <= 0:
            return None

        # 平滑: 避免某段 token 为 0 时被完全分不到文本
        return [w + 0.05 for w in raw_weights]

    # ------------------------------------------------------------------
    # VAD段收集 / 分组 辅助方法
    # ------------------------------------------------------------------

    def _collect_vad_segments(
        self,
        vad,
        sample_rate: int,
        debug_session: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """从VAD队列中收集所有语音段信息，返回段列表。"""
        vad_segments: list[dict[str, Any]] = []
        while not vad.empty():
            vs = vad.front
            # vs.start/vs.samples 都在“采样点坐标系”，这里统一换算到秒，
            # 方便后续字幕时间轴与日志诊断统一口径。
            start_s = vs.start / sample_rate
            duration_s = len(vs.samples) / sample_rate
            end_s = start_s + duration_s
            # rms/peak 主要用于调试和质量诊断，不参与业务分配逻辑。
            seg_rms = (
                float(np.sqrt(np.mean(np.square(vs.samples))))
                if len(vs.samples) > 0
                else 0.0
            )
            seg_peak = (
                float(np.max(np.abs(vs.samples)))
                if len(vs.samples) > 0
                else 0.0
            )
            segment_index = len(vad_segments)
            vad_segments.append(
                {
                    "segment_index": segment_index,
                    "start": start_s,
                    "duration": duration_s,
                    "end": end_s,
                    "rms": seg_rms,
                    "peak": seg_peak,
                    "samples": vs.samples,
                }
            )
            self._dump_vad_segment_audio(
                debug_session=debug_session,
                segment_index=segment_index,
                sample_rate=sample_rate,
                segment_data=vs.samples,
                start_s=start_s,
                end_s=end_s,
            )
            vad.pop()
        return vad_segments

    def _group_vad_segments(
        self, vad_segments: list[dict[str, Any]]
    ) -> list[list[int]]:
        """
        智能分组: 长段单独成组, 短段合并到目标时长。

        返回分组列表，每个分组是 VAD段索引的列表。
        """
        merge_target_duration = self.stream_merge_target_duration
        long_segment_threshold = self.stream_long_segment_threshold
        merge_max_gap = self.stream_merge_max_gap

        groups: list[list[int]] = []
        current_group: list[int] = []
        # group_span 包含语音时长和组内静音间隔，用于更准确地控制合并规模
        current_group_span = 0.0
        for idx, seg in enumerate(vad_segments):
            duration_s = seg["duration"]

            if duration_s > long_segment_threshold:
                # 长段优先“独占一组”: 避免长段和短段混合后造成时间分配失真。
                if current_group:
                    groups.append(current_group)
                    current_group = []
                    current_group_span = 0.0
                groups.append([idx])
                continue

            if not current_group:
                current_group = [idx]
                current_group_span = duration_s
                continue

            prev_seg = vad_segments[current_group[-1]]
            gap_s = max(0.0, seg["start"] - prev_seg["end"])
            predicted_span = current_group_span + gap_s + duration_s
            # 仅在“间隔可接受 + 预计总跨度可接受”时继续并组。
            # 注意这里使用 group span(语音+静音)而非纯语音时长，
            # 目的是让“感知到的句子时长”更接近真实播放体验。
            if gap_s > merge_max_gap or predicted_span > merge_target_duration:
                groups.append(current_group)
                current_group = [idx]
                current_group_span = duration_s
            else:
                current_group.append(idx)
                current_group_span = predicted_span

        if current_group:
            groups.append(current_group)

        # 标记分组信息
        for group_id, group_indices in enumerate(groups):
            for position_in_group, seg_idx in enumerate(group_indices):
                vad_segments[seg_idx]["group_id"] = group_id
                vad_segments[seg_idx]["position_in_group"] = position_in_group

        return groups

    def _build_streams_for_groups(
        self,
        vad_segments: list[dict[str, Any]],
        groups: list[list[int]],
        recognizer,
        sample_rate: int,
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        """
        为每个分组创建识别流。

        返回 (streams, group_info)。
        """
        long_segment_threshold = self.stream_long_segment_threshold

        def _build_stream_for_group(group_indices: list[int]) -> tuple[Any, list[dict[str, Any]], float]:
            """为分组创建识别流，并返回每段在合并音频中的时间轴映射。"""
            chunk_list = []
            timeline: list[dict[str, Any]] = []
            # merged_cursor 表示“拼接后音频”的游标时间，
            # 后续 token 时间戳会基于这条时间轴再映射回原始VAD段。
            merged_cursor = 0.0
            prev_end = None

            for seg_idx in group_indices:
                seg = vad_segments[seg_idx]

                if prev_end is not None:
                    gap_s = max(0.0, seg["start"] - prev_end)
                    if gap_s > 0:
                        # 在合并音频中保留组内静音，避免模型把相邻语句过度粘连
                        gap_samples = int(round(gap_s * sample_rate))
                        if gap_samples > 0:
                            chunk_list.append(np.zeros(gap_samples, dtype=np.float32))
                            merged_cursor += gap_samples / sample_rate

                merged_start = merged_cursor
                chunk_list.append(seg["samples"])
                merged_cursor += seg["duration"]
                timeline.append(
                    {
                        # segment_index 用于把解码结果反查到原始VAD段。
                        "segment_index": seg_idx,
                        # merged_start/merged_end 是“合并流坐标系”时间。
                        "merged_start": merged_start,
                        "merged_end": merged_cursor,
                    }
                )
                prev_end = seg["end"]

            merged_samples = (
                np.concatenate(chunk_list) if chunk_list else np.array([], dtype=np.float32)
            )
            stream = recognizer.create_stream()
            stream.accept_waveform(sample_rate, merged_samples)
            return stream, timeline, merged_cursor

        streams: list[Any] = []
        group_info: list[dict[str, Any]] = []
        total_groups = len(groups)
        for group_id, group_indices in enumerate(groups):
            is_long = (
                len(group_indices) == 1
                and vad_segments[group_indices[0]]["duration"] > long_segment_threshold
            )
            stream, timeline, merged_duration = _build_stream_for_group(group_indices)
            group_start = vad_segments[group_indices[0]]["start"]
            group_end = vad_segments[group_indices[-1]]["end"]
            # speech_duration 只统计语音内容，gap_duration 统计组内补的静音。
            # 两者拆开记录后，遇到“文本明显偏短/偏长”更容易判断问题在VAD还是ASR。
            speech_duration = sum(vad_segments[idx]["duration"] for idx in group_indices)
            gap_duration = max(0.0, merged_duration - speech_duration)
            streams.append(stream)
            group_info.append(
                {
                    "group_id": group_id,
                    "group_indices": group_indices,
                    "is_long_segment": is_long,
                    "timeline": timeline,
                    "merged_duration": merged_duration,
                }
            )
            # 打印每个合并stream时长，便于定位时长异常或文本截断
            logger.info(
                "合并stream[%s/%s]: group=%s, 段数=%s, 覆盖范围=%.3f-%.3f, 语音时长=%.3fs, 组内静音=%.3fs, 合并后时长=%.3fs",
                group_id + 1,
                total_groups,
                group_id,
                len(group_indices),
                group_start,
                group_end,
                speech_duration,
                gap_duration,
                merged_duration,
            )

        return streams, group_info

    def _extract_and_split_group_results(
        self,
        streams: list[Any],
        group_info: list[dict[str, Any]],
        vad_segments: list[dict[str, Any]],
        sample_rate: int,
        on_segment: OnSegment | None = None,
    ) -> tuple[list[Segment], list[dict[str, Any]], dict[str, int]]:
        """
        遍历分组，提取识别结果并拆分为字幕段。

        返回 (segments, group_diagnostics, stats)。
        stats 包含: total_multi_groups, token_weight_groups,
                    empty_distribution_group/segment/absorbed/dropped_count,
                    short_decode_warning_count
        """
        max_subtitle_duration = self.max_subtitle_duration
        segments: list[Segment] = []

        total_multi_groups = 0
        token_weight_groups = 0
        empty_distribution_group_count = 0
        empty_distribution_segment_count = 0
        empty_distribution_absorbed_count = 0
        empty_distribution_dropped_count = 0
        short_decode_warning_count = 0
        group_diagnostics: list[dict[str, Any]] = []

        for group_id, (meta, stream) in enumerate(zip(group_info, streams)):
            # 说明:
            # - group_info 描述分组元数据与时间轴映射
            # - stream.result 是批量解码后的文本/token信息
            # 二者结合后才能把“合并解码结果”正确回填到每个VAD段。
            group_indices = meta["group_indices"]
            is_long = meta["is_long_segment"]
            timeline = meta["timeline"]
            merged_duration = float(meta.get("merged_duration", 0.0))
            result = stream.result
            text = (
                result.text.strip() if hasattr(result, "text") and result.text else ""
            )
            group_start = vad_segments[group_indices[0]]["start"]
            group_end = vad_segments[group_indices[-1]]["end"]

            # 批量解码异常告警: 组时长较长但文本极短,可能存在截断
            text_len = len(text)
            if merged_duration >= 2.5 and text_len <= 3:
                short_decode_warning_count += 1
                logger.warning(
                    "批量解码文本疑似截断: group=%s, range=%.3f-%.3f, merged_duration=%.3fs, text=%r",
                    group_id,
                    group_start,
                    group_end,
                    merged_duration,
                    text,
                )

            group_diag: dict[str, Any] = {
                "group_id": group_id,
                "group_indices": group_indices,
                "group_start": group_start,
                "group_end": group_end,
                "group_size": len(group_indices),
                "is_long_segment": is_long,
                "merged_duration": merged_duration,
                "decode_text": text,
                "decode_text_length": text_len,
                "timeline": timeline,
                "distribution_mode": "none",
                "segments": [],
            }

            if not text:
                # 解码为空时保留诊断信息，但不输出字幕段。
                group_diag["status"] = "decode_empty"
                group_diagnostics.append(group_diag)
                continue

            new_segments: list[Segment] = []
            if is_long:
                # 长段: 需要深度拆分
                idx = group_indices[0]
                start_s = vad_segments[idx]["start"]
                duration_s = vad_segments[idx]["duration"]
                sub_segs = self._split_text_to_subtitles(
                    text,
                    start_s,
                    duration_s,
                    sample_rate,
                    segment_samples=vad_segments[idx]["samples"],
                )
                new_segments.extend(sub_segs)
                group_diag["distribution_mode"] = "long_segment_split"
            elif len(group_indices) == 1:
                # 单个短/中段: 直接使用,超2秒则拆分
                idx = group_indices[0]
                start_s = vad_segments[idx]["start"]
                duration_s = vad_segments[idx]["duration"]
                if duration_s > max_subtitle_duration:
                    sub_segs = self._split_text_to_subtitles(
                        text,
                        start_s,
                        duration_s,
                        sample_rate,
                        segment_samples=vad_segments[idx]["samples"],
                    )
                    new_segments.extend(sub_segs)
                    group_diag["distribution_mode"] = "single_split"
                else:
                    new_segments.append(Segment(start=start_s, duration=duration_s, text=text))
                    group_diag["distribution_mode"] = "single_direct"
            else:
                # 合并组: 按时间戳权重/时长权重分配文本，并保留每个VAD段的真实起点
                total_multi_groups += 1
                durations = [vad_segments[idx]["duration"] for idx in group_indices]
                timestamp_weights = self._extract_timestamp_weights(result, timeline)
                if timestamp_weights is not None:
                    # token时间戳可用时优先使用，通常比纯时长分配更贴近真实语速。
                    token_weight_groups += 1
                    distribution_weights = timestamp_weights
                    group_diag["distribution_mode"] = "timestamp_weights"
                else:
                    # 无token时间戳时退回时长权重，确保所有模型都可运行。
                    distribution_weights = durations
                    group_diag["distribution_mode"] = "duration_weights"
                distributed = self._distribute_text_by_punctuation(
                    text,
                    distribution_weights,
                )

                # 空分配处理策略:
                # 1) 优先并入上一条字幕(尾部延展)
                # 2) 若发生在组首，则暂存并等待下一条非空字幕吸收
                # 3) 若整组都无法吸收，才记为 dropped
                empty_in_group = 0
                absorbed_in_group = 0
                dropped_in_group = 0
                leading_empty_start: float | None = None
                leading_empty_count = 0
                leading_empty_diag_indices: list[int] = []
                for i, seg_idx in enumerate(group_indices):
                    seg_duration = durations[i]
                    seg_end = vad_segments[seg_idx]["end"]
                    seg_text = (distributed[i] if i < len(distributed) else "").strip()
                    # 使用原始 VAD 起点，避免"合并后按累计时长回填"导致时间戳前移
                    actual_start = vad_segments[seg_idx]["start"]
                    segment_diag = {
                        "segment_index": seg_idx,
                        "start": actual_start,
                        "end": vad_segments[seg_idx]["end"],
                        "duration": seg_duration,
                        "assigned_text": seg_text,
                        "assigned_text_length": len(seg_text),
                        "dropped": False,
                    }

                    if not seg_text:
                        empty_in_group += 1
                        empty_distribution_segment_count += 1
                        segment_diag["dropped"] = True
                        segment_diag["drop_reason"] = "empty_distribution_text"

                        if new_segments:
                            # 质量修复: 空分配段不直接丢弃，优先吸收到上一条字幕的尾部
                            prev_seg = new_segments[-1]
                            if seg_end > prev_seg.end:
                                new_segments[-1] = Segment(
                                    start=prev_seg.start,
                                    duration=seg_end - prev_seg.start,
                                    text=prev_seg.text,
                                )
                            absorbed_in_group += 1
                            empty_distribution_absorbed_count += 1
                            segment_diag["dropped"] = False
                            segment_diag["drop_reason"] = "empty_distribution_absorbed_to_previous"
                            segment_diag["absorbed_to"] = "previous"
                        else:
                            # 组内前导空分配：等待下一条非空字幕出现后整体前移吸收
                            if leading_empty_start is None:
                                leading_empty_start = actual_start
                            leading_empty_count += 1
                            segment_diag["drop_reason"] = "empty_distribution_pending_leading"
                            leading_empty_diag_indices.append(len(group_diag["segments"]))

                        group_diag["segments"].append(segment_diag)
                        continue

                    if leading_empty_start is not None:
                        # 前导空分配由首条非空字幕吸收，避免开头出现字幕空洞
                        actual_start = leading_empty_start
                        seg_duration = max(0.01, seg_end - actual_start)
                        absorbed_in_group += leading_empty_count
                        empty_distribution_absorbed_count += leading_empty_count
                        for diag_idx in leading_empty_diag_indices:
                            if 0 <= diag_idx < len(group_diag["segments"]):
                                group_diag["segments"][diag_idx]["dropped"] = False
                                group_diag["segments"][diag_idx]["drop_reason"] = (
                                    "empty_distribution_absorbed_to_next"
                                )
                                group_diag["segments"][diag_idx]["absorbed_to"] = "next"
                        leading_empty_start = None
                        leading_empty_count = 0
                        leading_empty_diag_indices.clear()

                    segment_diag["output_start"] = actual_start
                    segment_diag["output_duration"] = seg_duration
                    if seg_duration > max_subtitle_duration:
                        # 即使已经分配到具体VAD段，仍可能超长，需要二次拆分。
                        sub_segs = self._split_text_to_subtitles(
                            seg_text,
                            actual_start,
                            seg_duration,
                            sample_rate,
                            segment_samples=vad_segments[seg_idx]["samples"],
                        )
                        new_segments.extend(sub_segs)
                        segment_diag["split_subtitle_count"] = len(sub_segs)
                    else:
                        new_segments.append(
                            Segment(
                                start=actual_start,
                                duration=seg_duration,
                                text=seg_text,
                            )
                        )
                    group_diag["segments"].append(segment_diag)

                if leading_empty_count > 0:
                    # 整组都没有可承接文本，前导空分配无法吸收，仍会被丢弃
                    dropped_in_group += leading_empty_count
                    empty_distribution_dropped_count += leading_empty_count
                    for diag_idx in leading_empty_diag_indices:
                        if 0 <= diag_idx < len(group_diag["segments"]):
                            group_diag["segments"][diag_idx]["drop_reason"] = (
                                "empty_distribution_unresolved_leading"
                            )
                    logger.warning(
                        "分配文本为空且无法吸收，VAD段将被跳过: group=%s, dropped=%s, range=%.3f-%.3f",
                        group_id,
                        leading_empty_count,
                        leading_empty_start if leading_empty_start is not None else group_start,
                        group_end,
                    )

                if empty_in_group > 0:
                    empty_distribution_group_count += 1
                    group_diag["empty_assigned_segments"] = empty_in_group
                    group_diag["empty_absorbed_segments"] = absorbed_in_group
                    group_diag["empty_dropped_segments"] = dropped_in_group

            if new_segments:
                segments.extend(new_segments)
                group_diag["output_segment_count"] = len(new_segments)
                group_diag["status"] = "ok"
            else:
                # 允许“有解码文本但最终无输出”的情况留痕，方便排查分配策略问题。
                group_diag["output_segment_count"] = 0
                group_diag["status"] = "no_output"
            group_diagnostics.append(group_diag)

            # 实时segment回调 (用于GUI预览)
            if on_segment and new_segments:
                for seg in new_segments:
                    if seg.text.strip():
                        on_segment(seg)

        stats = {
            # 这些统计字段仅用于观测与调试，不影响上游业务契约。
            "total_multi_groups": total_multi_groups,
            "token_weight_groups": token_weight_groups,
            "empty_distribution_group_count": empty_distribution_group_count,
            "empty_distribution_segment_count": empty_distribution_segment_count,
            "empty_distribution_absorbed_count": empty_distribution_absorbed_count,
            "empty_distribution_dropped_count": empty_distribution_dropped_count,
            "short_decode_warning_count": short_decode_warning_count,
        }
        return segments, group_diagnostics, stats

    @staticmethod
    def _normalize_segments(segments: list[Segment]) -> list[Segment]:
        """最终规整：去空文本、排序、修正轻微重叠与无效时长。"""
        normalized_segments: list[Segment] = []
        for seg in sorted(segments, key=lambda x: (x.start, x.duration)):
            seg_text = seg.text.strip()
            if not seg_text:
                continue

            start_s = max(0.0, float(seg.start))
            duration_s = float(seg.duration)
            if duration_s <= 0:
                continue

            if normalized_segments:
                prev_end = normalized_segments[-1].end
                overlap = prev_end - start_s
                # 仅修正非常小的数值级重叠，避免改变真实语义边界
                if overlap > 0 and overlap < 0.02:
                    start_s = prev_end

            normalized_segments.append(
                Segment(start=start_s, duration=duration_s, text=seg_text)
            )
        return normalized_segments

    def _transcribe_each_vad_segment(
        self,
        vad,
        recognizer,
        sample_rate: int,
        verbose: bool = False,
        on_segment: OnSegment | None = None,
        on_progress: Callable[[float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> list[Segment]:
        """
        逐VAD片段识别模式：每个VAD段单独建流并批量解码。

        Args:
            vad: 批量VAD检测器（已flush）
            recognizer: 离线识别器
            sample_rate: 采样率
            verbose: 是否打印详细日志
            on_segment: 实时片段回调
            on_progress: 进度回调
            cancel_event: 取消事件

        Returns:
            list[Segment]: 过滤后的字幕片段
        """
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
        # 注意: 这里是“每个VAD段单独建流，再统一并行解码”。
        # 好处是简单直观，代价是跨段上下文信息较少。
        recognizer.decode_streams(streams)
        # 接码耗时
        end_time = time.time()
        logger.info(f"批量解码耗时: {end_time - start_time:.2f}s")

        # 提取转录结果
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
        return [seg for seg in segments if seg.text]

    def _transcribe_merged_vad_segments(
        self,
        vad,
        recognizer,
        sample_rate: int,
        verbose: bool = False,
        on_segment: OnSegment | None = None,
        on_progress: Callable[[float], None] | None = None,
        cancel_event: threading.Event | None = None,
        audio_file: Path | None = None,
        debug_session: dict[str, Any] | None = None,
    ) -> list[Segment]:
        """
        合并VAD段识别模式：短段合并建流，批量解码后按权重分配文本。

        流程：
        1. 收集VAD段 + 智能分组
        2. 为分组创建识别流 + 批量解码
        3. 拆分识别结果 → 生成 ≤max_subtitle_duration 的字幕段
        4. 规整 + 调试导出

        Args:
            vad: 批量VAD检测器（已flush）
            recognizer: 离线识别器
            sample_rate: 采样率
            verbose: 是否打印详细日志
            on_segment: 实时片段回调
            on_progress: 进度回调
            cancel_event: 取消事件
            audio_file: 音频文件路径（用于调试导出）
            debug_session: 调试会话

        Returns:
            list[Segment]: 字幕片段列表
        """
        # ============================================================
        # 阶段1: 收集VAD语音段 + 智能分组(合并短段,减少stream数量)
        # ============================================================
        vad_segments = self._collect_vad_segments(vad, sample_rate, debug_session)

        if verbose:
            print(f"    VAD检测到 {len(vad_segments)} 个语音段")

        if not vad_segments:
            if on_progress:
                on_progress(100.0)
            logger.info("音频转录完成, VAD未检测到有效语音段")
            return []

        groups = self._group_vad_segments(vad_segments)

        avg_group_size = sum(len(g) for g in groups) / len(groups) if groups else 0.0
        logger.info(
            "stream分组完成: 原始VAD段=%s, 合并stream=%s, 平均每组段数=%.2f",
            len(vad_segments),
            len(groups),
            avg_group_size,
        )

        # 导出VAD段和分组元数据，便于测试阶段定位"漏字幕/时间漂移"
        self._dump_debug_json(
            debug_session=debug_session,
            filename="vad_segments.json",
            payload={
                "audio_file": str(audio_file) if audio_file else "",
                "sample_rate": sample_rate,
                "vad_segment_count": len(vad_segments),
                "group_count": len(groups),
                "segments": [
                    {
                        "segment_index": seg["segment_index"],
                        "start": seg["start"],
                        "end": seg["end"],
                        "duration": seg["duration"],
                        "rms": seg["rms"],
                        "peak": seg["peak"],
                        "group_id": seg.get("group_id"),
                        "position_in_group": seg.get("position_in_group"),
                    }
                    for seg in vad_segments
                ],
            },
        )

        # ============================================================
        # 阶段1.5: 为每个分组创建识别流
        # ============================================================
        streams, group_info = self._build_streams_for_groups(
            vad_segments, groups, recognizer, sample_rate,
        )

        # VAD完成: 30%
        if on_progress:
            on_progress(30.0)

        # 检查取消事件
        if cancel_event and cancel_event.is_set():
            raise BatchProcessorCancelled("用户取消处理")

        # ============================================================
        # 阶段2: 批量解码
        # ============================================================
        start_time = time.time()
        if streams:
            # 解码完成后，每个stream.result里会写入 text/timestamps 等字段。
            recognizer.decode_streams(streams)
        end_time = time.time()
        logger.info(f"批量解码耗时: {end_time - start_time:.2f}s")

        # ============================================================
        # 阶段3: 拆分识别结果 → 生成字幕段
        # ============================================================
        segments, group_diagnostics, stats = self._extract_and_split_group_results(
            streams, group_info, vad_segments, sample_rate, on_segment,
        )

        # 日志汇总
        total_multi_groups = stats["total_multi_groups"]
        token_weight_groups = stats["token_weight_groups"]
        empty_distribution_group_count = stats["empty_distribution_group_count"]
        empty_distribution_segment_count = stats["empty_distribution_segment_count"]
        empty_distribution_absorbed_count = stats["empty_distribution_absorbed_count"]
        empty_distribution_dropped_count = stats["empty_distribution_dropped_count"]
        short_decode_warning_count = stats["short_decode_warning_count"]

        logger.info(
            "时间戳策略命中: token时间戳=%s/%s(合并组)",
            token_weight_groups,
            total_multi_groups,
        )
        # 下述告警仅用于观测质量，不中断流程，避免影响批处理可用性。
        if total_multi_groups > 0 and token_weight_groups == 0:
            logger.warning(
                "合并组全部回退到时长权重分配: 0/%s 命中token时间戳，建议结合调试导出检查时间对齐质量",
                total_multi_groups,
            )
        if empty_distribution_segment_count > 0:
            if empty_distribution_dropped_count > 0:
                logger.warning(
                    "文本分配阶段出现空分配: 组数=%s, 总段数=%s, 已吸收=%s, 仍丢弃=%s",
                    empty_distribution_group_count,
                    empty_distribution_segment_count,
                    empty_distribution_absorbed_count,
                    empty_distribution_dropped_count,
                )
            else:
                logger.info(
                    "文本分配阶段空分配已被吸收: 组数=%s, 段数=%s",
                    empty_distribution_group_count,
                    empty_distribution_segment_count,
                )
        if short_decode_warning_count > 0:
            logger.warning(
                "批量解码疑似截断告警组数: %s",
                short_decode_warning_count,
            )

        # 最终规整
        segments = self._normalize_segments(segments)

        # 调试导出
        self._dump_debug_json(
            debug_session=debug_session,
            filename="group_diagnostics.json",
            payload={
                "audio_file": str(audio_file) if audio_file else "",
                "total_group_count": len(group_info),
                "multi_group_count": total_multi_groups,
                "token_weight_group_count": token_weight_groups,
                "empty_distribution_group_count": empty_distribution_group_count,
                "empty_distribution_segment_count": empty_distribution_segment_count,
                "empty_distribution_absorbed_count": empty_distribution_absorbed_count,
                "empty_distribution_dropped_count": empty_distribution_dropped_count,
                "short_decode_warning_count": short_decode_warning_count,
                "group_diagnostics": group_diagnostics,
                "output_segment_count": len(segments),
                "output_segments": [
                    {
                        "start": seg.start,
                        "end": seg.end,
                        "duration": seg.duration,
                        "text": seg.text,
                    }
                    for seg in segments
                ],
            },
        )

        if verbose:
            for i, seg in enumerate(segments):
                if seg.text:
                    print(
                        f"    [{i+1}/{len(segments)}] {seg.start:.1f}s({seg.duration:.1f}s): {seg.text[:50]}..."
                    )

        return segments

    def _prepare_merged_mode_context(
        self,
        audio_file: Path,
        transcription_engine,
        vad_detector,
        sample_rate: int,
        verbose: bool = False,
        on_progress: Callable[[float], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> tuple[Any, Any, dict[str, Any] | None]:
        """
        准备拼接识别模式上下文。

        包括取消检查、初始化调试会话、读取音频、构建识别器/VAD并完成VAD喂数。
        """
        # 检查取消事件
        if cancel_event and cancel_event.is_set():
            raise BatchProcessorCancelled("用户取消处理")

        debug_session = self._create_debug_session(audio_file)

        # 初始进度
        if on_progress:
            on_progress(0.0)

        # 先准备音频数据，再取 recognizer / vad，
        # 保证后续失败时日志能明确定位到“读音频失败”还是“模型构建失败”。
        audio_data = self._load_audio_for_transcription(
            audio_file=audio_file,
            sample_rate=sample_rate,
        )
        recognizer = self._get_offline_recognizer(transcription_engine)
        vad, window_size = self._create_batch_vad_detector(
            vad_detector=vad_detector,
            sample_rate=sample_rate,
        )

        if verbose:
            print(f"    处理音频: 长度={len(audio_data)/sample_rate:.1f}s")

        self._feed_audio_to_vad(
            audio_data=audio_data,
            vad=vad,
            window_size=window_size,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

        # flush 触发VAD输出尾段，否则末尾语音可能滞留在内部缓冲。
        vad.flush()
        return vad, recognizer, debug_session

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
            # 统一转换到16k wav，简化后续VAD/ASR输入约束。
            # 这样不同来源媒体文件都走同一条可控处理链路。
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
                # 单文件总体进度映射:
                # - 0~25: 音频转换
                # - 25~85: 转录(内部0~100折算到60%)
                # - 85~100: 字幕写盘
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
            # finally 块无论成功/失败都会执行，避免临时wav长期堆积。
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


        vad, recognizer, debug_session = self._prepare_merged_mode_context(
            audio_file=audio_file,
            transcription_engine=transcription_engine,
            vad_detector=vad_detector,
            sample_rate=sample_rate,
            verbose=verbose,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

        if self.transcribe_per_vad_segment:
            # 模式A: 每段独立识别。适合追求实现简单、问题定位直接的场景。
            segments = self._transcribe_each_vad_segment(
                vad=vad,
                recognizer=recognizer,
                sample_rate=sample_rate,
                verbose=verbose,
                on_segment=on_segment,
                on_progress=on_progress,
                cancel_event=cancel_event,
            )
        else:
            # 模式B: 短段合并后识别。通常能提升上下文连贯性和吞吐表现。
            segments = self._transcribe_merged_vad_segments(
                vad=vad,
                recognizer=recognizer,
                sample_rate=sample_rate,
                verbose=verbose,
                on_segment=on_segment,
                on_progress=on_progress,
                cancel_event=cancel_event,
                audio_file=audio_file,
                debug_session=debug_session,
            )

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
                    # process_file 内部已捕获异常并返回失败结果时，走该分支统计失败。
                    error_count += 1
                    error_detail = result.get("error", "Unknown error")
                    errors.append((str(file_path), error_detail))

                    # 增强日志：提供更多失败上下文
                    logger.warning(
                        f"文件处理失败: {file_path.name} - {error_detail} "
                        f"(第 {i}/{total_files} 个文件)"
                    )

                    # 修复: 失败时也调用完成回调（传递空字符串和0值表示失败）
                    # 约定统一后，GUI层可以不分“失败来源”直接复用同一回调通道。
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
                # 兜底异常分支: 覆盖 process_file 外层的意外错误，保证批处理可控。
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
                # 这样调用方不需要区分“业务失败”和“异常失败”两种分支。
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
