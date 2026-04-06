#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用 sherpa-onnx 的 SenseVoice 模型转录 MP4 文件。

默认路径：
- 输入视频：test.mp4
- 识别模型：models/sherpa-onnx-sense-voice-funasr-nano-2025-12-17/model.onnx
- 词表：models/sherpa-onnx-sense-voice-funasr-nano-2025-12-17/tokens.txt
- VAD 模型：models/silero_vad/silero_vad.onnx
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import sherpa_onnx


LOGGER = logging.getLogger("sherpa_onnx_mp4_transcribe")
DEFAULT_MODEL_DIR = Path("models/sherpa-onnx-sense-voice-funasr-nano-2025-12-17")
DEFAULT_VIDEO = Path("test3.aac")
DEFAULT_OUTPUT = Path("test.transcript.txt")
DEFAULT_SRT_OUTPUT = Path("test3.srt")
DEFAULT_SILERO_VAD_MODEL = Path("models/silero_vad/silero_vad.onnx")
DEFAULT_TEN_VAD_MODEL = Path("models/ten_vad/ten-vad.onnx")
TARGET_SAMPLE_RATE = 16000
_DLL_DIR_HANDLES = []
DEFAULT_VAD_THRESHOLD = 0.5
DEFAULT_VAD_MIN_SILENCE = 0.1
DEFAULT_VAD_MIN_SPEECH = 0.1
DEFAULT_VAD_MAX_SPEECH = 8.0
DEFAULT_VAD_BUFFER_SECONDS = 500.0
DEFAULT_VAD_START_THRESHOLD = DEFAULT_VAD_THRESHOLD
DEFAULT_VAD_END_THRESHOLD = DEFAULT_VAD_THRESHOLD
DEFAULT_VAD_MERGE_GAP = 0.20
DEFAULT_VAD_MIN_SEGMENT = 0.15
DEFAULT_VAD_PAD = 0.15
DEFAULT_VAD_SHORT_SEGMENT_THRESHOLD = 0.8

# VAD 调参速查（修改后会有什么效果）：
# - vad_start_threshold / vad_end_threshold:
#   数值越大越不容易判定为语音，误触发更少但可能漏字；数值越小更敏感，切分更积极。
# - vad_min_silence:
#   越小越容易切段（字幕更短更碎），越大越不容易切段（字幕更长更连贯）。
# - vad_min_speech:
#   越小越容易保留很短词（也更容易带入噪声），越大越能抑制噪声短脉冲。
# - vad_max_speech:
#   越小越会强制把长句拆开，越大越倾向保留长句。
# - vad_merge_gap / vad_pad（后处理）:
#   merge_gap 越大越容易把相邻段合并成长段；pad 越大越不容易截断首尾，但时间戳更“宽”。
#
# VAD 预设参数：用于快速切换常见场景。
VAD_PROFILES = {
    # custom 保持现有脚本默认行为，确保向后兼容。
    "custom": {
        "vad_threshold": DEFAULT_VAD_THRESHOLD,
        "vad_min_silence": DEFAULT_VAD_MIN_SILENCE,
        "vad_min_speech": DEFAULT_VAD_MIN_SPEECH,
        "vad_max_speech": DEFAULT_VAD_MAX_SPEECH,
        "vad_buffer_seconds": DEFAULT_VAD_BUFFER_SECONDS,
        "vad_start_threshold": DEFAULT_VAD_START_THRESHOLD,
        "vad_end_threshold": DEFAULT_VAD_END_THRESHOLD,
        "vad_merge_gap": 0.0,
        "vad_min_segment": 0.0,
        "vad_pad": 0.0,
        "vad_short_segment_threshold": DEFAULT_VAD_SHORT_SEGMENT_THRESHOLD,
    },
    # 均衡模式：字幕切分与连贯性折中。
    "balanced": {
        "vad_threshold": 0.30,
        "vad_min_silence": 0.25,
        "vad_min_speech": 0.20,
        "vad_max_speech": 10.0,
        "vad_buffer_seconds": 100.0,
        "vad_start_threshold": 0.35,
        "vad_end_threshold": 0.25,
        "vad_merge_gap": 0.12,
        "vad_min_segment": 0.18,
        "vad_pad": 0.08,
        "vad_short_segment_threshold": 0.8,
    },
    # 噪声模式：提高保守性，减少噪声误触发。
    "noisy": {
        "vad_threshold": 0.45,
        "vad_min_silence": 0.35,
        "vad_min_speech": 0.25,
        "vad_max_speech": 8.0,
        "vad_buffer_seconds": 100.0,
        "vad_start_threshold": 0.55,
        "vad_end_threshold": 0.35,
        "vad_merge_gap": 0.15,
        "vad_min_segment": 0.22,
        "vad_pad": 0.05,
        "vad_short_segment_threshold": 1.0,
    },
    # 长句模式：尽量保留连贯长句，减少切碎。
    "longform": {
        "vad_threshold": 0.25,
        "vad_min_silence": 0.45,
        "vad_min_speech": 0.20,
        "vad_max_speech": 18.0,
        "vad_buffer_seconds": 100.0,
        "vad_start_threshold": 0.30,
        "vad_end_threshold": 0.20,
        "vad_merge_gap": 0.25,
        "vad_min_segment": 0.20,
        "vad_pad": 0.12,
        "vad_short_segment_threshold": 1.2,
    },
    # 短句模式：尽可能让字幕更短（适合做逐句阅读，不追求强连贯）。
    "short": {
        "vad_threshold": 0.40,
        "vad_min_silence": 0.08,
        "vad_min_speech": 0.08,
        "vad_max_speech": 3.0,
        "vad_buffer_seconds": 100.0,
        "vad_start_threshold": 0.45,
        "vad_end_threshold": 0.38,
        "vad_merge_gap": 0.02,
        "vad_min_segment": 0.08,
        "vad_pad": 0.01,
        "vad_short_segment_threshold": 0.6,
    },
}


@dataclass
class SubtitleSegment:
    """字幕片段结构。"""

    start: float
    duration: float
    text: str

    @property
    def end(self) -> float:
        """结束时间（秒）。"""
        return self.start + self.duration


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="使用 sherpa-onnx 转录 MP4 并输出字幕")
    parser.add_argument(
        "--video",
        type=Path,
        default=DEFAULT_VIDEO,
        help="待转录的视频文件路径（默认: test.mp4）",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_DIR / "model.onnx",
        help="SenseVoice 模型文件路径",
    )
    parser.add_argument(
        "--tokens",
        type=Path,
        default=DEFAULT_MODEL_DIR / "tokens.txt",
        help="tokens.txt 路径",
    )
    parser.add_argument(
        "--provider",
        default="cuda",
        choices=["cpu", "cuda", "coreml"],
        help="推理后端（默认: cuda）",
    )
    parser.add_argument(
        "--num-threads",
        type=int,
        default=4,
        help="识别线程数（默认: 4）",
    )
    parser.add_argument(
        "--use-itn",
        dest="use_itn",
        action="store_true",
        default=True,
        help="启用 ITN（数字/日期等文本规范化）",
    )
    parser.add_argument(
        "--no-use-itn",
        dest="use_itn",
        action="store_false",
        help="禁用 ITN（默认启用）",
    )
    parser.add_argument(
        "--output-txt",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="转录文本输出路径（默认: test.transcript.txt）",
    )
    parser.add_argument(
        "--output-srt",
        type=Path,
        default=DEFAULT_SRT_OUTPUT,
        help="字幕文件输出路径（默认: test.srt）",
    )
    # VAD 调参说明（按“切分更细/更稳”来理解）：
    # 1) start/end_threshold: 迟滞阈值；start 越高越不易触发，end 越低越不易提前截断。
    # 2) min_silence: 句间静音至少持续多久才切段；越大越不容易切碎，越小越容易切成短句。
    # 3) min_speech: 最短语音段时长；越大越能过滤噪声短脉冲，但可能吞掉很短词。
    # 4) max_speech: 单段语音上限；越小越容易强制长句拆分，越大越倾向保留长段。
    # 5) merge_gap/min_segment/pad: 后处理参数；控制“合并、过滤、补边”强度。
    # 6) buffer_seconds: VAD 内部缓冲上限，仅影响内存与超长音频稳定性，通常不影响切分边界。
    parser.add_argument(
        "--vad-model",
        type=Path,
        default=DEFAULT_SILERO_VAD_MODEL,
        help="VAD 模型路径（默认: models/silero_vad/silero_vad.onnx）",
    )
    parser.add_argument(
        "--vad-model-type",
        choices=["silero", "ten"],
        default="silero",
        help="VAD 模型类型（默认: silero）",
    )
    parser.add_argument(
        "--vad-profile",
        choices=["custom", "balanced", "noisy", "longform", "short"],
        default="custom",
        help="VAD 参数预设（默认: custom；可用: balanced/noisy/longform/short）",
    )
    parser.add_argument(
        "--vad-threshold",
        type=float,
        default=None,
        help="VAD 阈值（不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-start-threshold",
        type=float,
        default=None,
        help="VAD 起始阈值（迟滞模式，高阈值；不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-end-threshold",
        type=float,
        default=None,
        help="VAD 结束阈值（迟滞模式，低阈值；不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-min-silence",
        type=float,
        default=None,
        help="VAD 最小静音时长（秒，不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-min-speech",
        type=float,
        default=None,
        help="VAD 最小语音时长（秒，不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-max-speech",
        type=float,
        default=None,
        help="VAD 最大语音时长（秒，不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-buffer-seconds",
        type=float,
        default=None,
        help="VAD 缓冲区大小（秒，不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-merge-gap",
        type=float,
        default=None,
        help="VAD后处理：相邻段合并间隔阈值（秒，不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-min-segment",
        type=float,
        default=None,
        help="VAD后处理：保留段最小时长（秒，不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-pad",
        type=float,
        default=None,
        help="VAD后处理：每段首尾补边时长（秒，不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--vad-short-segment-threshold",
        type=float,
        default=None,
        help="VAD指标：短片段阈值（秒，不传则使用 profile 对应值）",
    )
    parser.add_argument(
        "--disable-vad-post-process",
        action="store_true",
        help="禁用VAD后处理（合并/过滤/补边）",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用 sherpa-onnx 调试日志",
    )
    parser.add_argument(
        "--enable-cuda-fallback",
        action="store_true",
        help="启用 CUDA 失败时自动回退到 CPU（默认关闭）",
    )
    return parser.parse_args()


def ensure_file_exists(path: Path, display_name: str) -> None:
    """检查关键输入文件是否存在。"""
    if not path.is_file():
        raise FileNotFoundError(f"{display_name}不存在: {path}")


def resolve_vad_model_path(args: argparse.Namespace) -> Path:
    """
    解析 VAD 模型路径。

    兼容逻辑：
    - 用户未显式传入 --vad-model 且选择 ten 时，自动切换到 ten 默认模型。
    """
    if args.vad_model_type == "ten" and args.vad_model == DEFAULT_SILERO_VAD_MODEL:
        LOGGER.info(
            "检测到 --vad-model-type=ten 且未指定 --vad-model，自动使用: %s",
            DEFAULT_TEN_VAD_MODEL,
        )
        return DEFAULT_TEN_VAD_MODEL
    return args.vad_model


def validate_args(args: argparse.Namespace) -> None:
    """校验参数合法性。"""
    if args.num_threads <= 0:
        raise ValueError("--num-threads 必须大于 0")
    if not 0.0 <= args.vad_threshold <= 1.0:
        raise ValueError("--vad-threshold 必须位于 [0, 1]")
    if args.vad_min_silence < 0:
        raise ValueError("--vad-min-silence 不能小于 0")
    if args.vad_min_speech < 0:
        raise ValueError("--vad-min-speech 不能小于 0")
    if args.vad_max_speech <= 0:
        raise ValueError("--vad-max-speech 必须大于 0")
    if args.vad_buffer_seconds <= 0:
        raise ValueError("--vad-buffer-seconds 必须大于 0")
    if not 0.0 <= args.vad_start_threshold <= 1.0:
        raise ValueError("--vad-start-threshold 必须位于 [0, 1]")
    if not 0.0 <= args.vad_end_threshold <= 1.0:
        raise ValueError("--vad-end-threshold 必须位于 [0, 1]")
    if args.vad_merge_gap < 0:
        raise ValueError("--vad-merge-gap 不能小于 0")
    if args.vad_min_segment < 0:
        raise ValueError("--vad-min-segment 不能小于 0")
    if args.vad_pad < 0:
        raise ValueError("--vad-pad 不能小于 0")
    if args.vad_short_segment_threshold <= 0:
        raise ValueError("--vad-short-segment-threshold 必须大于 0")
    if args.vad_start_threshold < args.vad_end_threshold:
        LOGGER.warning(
            "当前参数中 vad_start_threshold(%.3f) < vad_end_threshold(%.3f)，"
            "不符合常见迟滞配置（通常 start >= end）。",
            args.vad_start_threshold,
            args.vad_end_threshold,
        )


def apply_vad_profile(args: argparse.Namespace) -> None:
    """
    应用 VAD 预设参数。

    规则：
    - 未显式传入的参数使用 profile 值。
    - 显式传入的参数优先级更高（可覆盖 profile）。
    """
    profile = VAD_PROFILES.get(args.vad_profile)
    if profile is None:
        raise ValueError(
            f"不支持的 --vad-profile: {args.vad_profile}，可选: {list(VAD_PROFILES.keys())}"
        )

    # 兼容策略：custom 模式下若用户没有显式设置后处理参数，则默认关闭后处理，
    # 保持此前脚本“仅做原始VAD分段”的行为。
    custom_should_disable_post = (
        args.vad_profile == "custom"
        and args.vad_merge_gap is None
        and args.vad_min_segment is None
        and args.vad_pad is None
        and not args.disable_vad_post_process
    )
    if custom_should_disable_post:
        args.disable_vad_post_process = True

    if args.vad_threshold is None:
        args.vad_threshold = profile["vad_threshold"]
    if args.vad_min_silence is None:
        args.vad_min_silence = profile["vad_min_silence"]
    if args.vad_min_speech is None:
        args.vad_min_speech = profile["vad_min_speech"]
    if args.vad_max_speech is None:
        args.vad_max_speech = profile["vad_max_speech"]
    if args.vad_buffer_seconds is None:
        args.vad_buffer_seconds = profile["vad_buffer_seconds"]
    if args.vad_start_threshold is None:
        args.vad_start_threshold = profile["vad_start_threshold"]
    if args.vad_end_threshold is None:
        args.vad_end_threshold = profile["vad_end_threshold"]
    if args.vad_merge_gap is None:
        args.vad_merge_gap = profile["vad_merge_gap"]
    if args.vad_min_segment is None:
        args.vad_min_segment = profile["vad_min_segment"]
    if args.vad_pad is None:
        args.vad_pad = profile["vad_pad"]
    if args.vad_short_segment_threshold is None:
        args.vad_short_segment_threshold = profile["vad_short_segment_threshold"]

    # 若 profile 未设置迟滞阈值，则回退到单阈值。
    if args.vad_start_threshold is None:
        args.vad_start_threshold = args.vad_threshold
    if args.vad_end_threshold is None:
        args.vad_end_threshold = args.vad_threshold

    LOGGER.info(
        "VAD参数生效: profile=%s, threshold=%.3f, start_threshold=%.3f, end_threshold=%.3f, "
        "min_silence=%.3f, min_speech=%.3f, max_speech=%.3f, buffer=%.1f, "
        "merge_gap=%.3f, min_segment=%.3f, pad=%.3f, short_threshold=%.3f, post_process=%s",
        args.vad_profile,
        args.vad_threshold,
        args.vad_start_threshold,
        args.vad_end_threshold,
        args.vad_min_silence,
        args.vad_min_speech,
        args.vad_max_speech,
        args.vad_buffer_seconds,
        args.vad_merge_gap,
        args.vad_min_segment,
        args.vad_pad,
        args.vad_short_segment_threshold,
        "off" if args.disable_vad_post_process else "on",
    )


def read_audio_via_ffmpeg(video_path: Path) -> np.ndarray:
    """
    使用 ffmpeg 读取视频音轨并转为 16k 单声道 float32 PCM。

    返回值：
    - numpy.ndarray: 归一化到 [-1, 1] 的 float32 音频
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise FileNotFoundError("未找到 ffmpeg。请先安装 ffmpeg 并确保已加入 PATH。")

    cmd = [
        ffmpeg_path,
        "-nostdin",
        "-i",
        str(video_path),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-",
    ]
    LOGGER.info("开始通过 ffmpeg 提取音频: %s", video_path)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_data, stderr_data = process.communicate()
    if process.returncode != 0:
        stderr_text = stderr_data.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"ffmpeg 提取音频失败（退出码={process.returncode}）: {stderr_text}")

    if not stdout_data:
        raise RuntimeError("ffmpeg 未输出任何音频数据，请检查输入文件是否包含音轨。")

    audio_int16 = np.frombuffer(stdout_data, dtype=np.int16)
    audio_float32 = (audio_int16.astype(np.float32)) / 32768.0
    LOGGER.info("音频提取完成，采样点数量: %d", audio_float32.shape[0])
    return audio_float32


def create_recognizer(
    model_path: Path,
    tokens_path: Path,
    num_threads: int,
    provider: str,
    use_itn: bool,
    debug: bool,
) -> sherpa_onnx.OfflineRecognizer:
    """创建 sherpa-onnx SenseVoice 离线识别器。"""
    LOGGER.info("加载模型: %s", model_path)
    recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=str(model_path),
        tokens=str(tokens_path),
        num_threads=num_threads,
        use_itn=use_itn,
        debug=debug,
        provider=provider,
    )
    LOGGER.info("模型加载完成")
    return recognizer


def preload_cuda_runtime_dlls(provider: str) -> None:
    """
    在 Windows 下为 CUDA provider 预加载依赖 DLL。

    说明：
    - error 126 通常表示依赖 DLL 未被加载到进程搜索路径中。
    - 优先复用 PyTorch 自带的 CUDA/cuDNN 运行库，避免手工替换 DLL。
    """
    if provider.lower() != "cuda":
        return

    torch_lib_dir: Path | None = None
    LOGGER.info("检测到 CUDA provider，开始预加载运行库")

    # 1) 将 torch\lib 加入 DLL 搜索路径（Python 3.8+）
    try:
        import torch

        torch_lib_dir = Path(torch.__file__).resolve().parent / "lib"
        if torch_lib_dir.is_dir() and hasattr(os, "add_dll_directory"):
            handle = os.add_dll_directory(str(torch_lib_dir))
            _DLL_DIR_HANDLES.append(handle)
            LOGGER.info("已添加 DLL 搜索目录: %s", torch_lib_dir)
        else:
            LOGGER.warning("未找到 torch\\lib 或当前环境不支持 add_dll_directory")
    except Exception as exc:
        LOGGER.warning("预加载 torch CUDA 运行库失败: %s", exc)

    # 2) 若安装了 onnxruntime Python 包，调用其 preload_dlls（官方推荐）
    try:
        import onnxruntime as ort

        if hasattr(ort, "preload_dlls"):
            if torch_lib_dir and torch_lib_dir.is_dir():
                ort.preload_dlls(directory=str(torch_lib_dir))
            else:
                ort.preload_dlls()
            LOGGER.info("onnxruntime.preload_dlls 执行完成")
    except Exception as exc:
        LOGGER.warning("onnxruntime.preload_dlls 执行失败（可忽略）: %s", exc)


def create_vad_detector(
    vad_model_path: Path,
    vad_model_type: str,
    sample_rate: int,
    threshold: float,
    min_silence_duration: float,
    min_speech_duration: float,
    max_speech_duration: float,
    buffer_size_in_seconds: float,
) -> Tuple[sherpa_onnx.VoiceActivityDetector, int]:
    """
    创建 VAD 检测器并返回窗口大小。

    返回值：
    - vad: sherpa_onnx.VoiceActivityDetector
    - window_size: VAD 单次处理窗口采样点数

    调参影响：
    - threshold 决定“多敏感”；
    - min_silence/min_speech 决定“多容易切段”；
    - max_speech 决定“长句是否被强制拆分”。
    """
    LOGGER.info(
        "初始化 VAD（type=%s, model=%s, threshold=%.3f）",
        vad_model_type,
        vad_model_path,
        threshold,
    )

    vad_config = sherpa_onnx.VadModelConfig()
    if vad_model_type == "silero":
        vad_config.silero_vad.model = str(vad_model_path)
        # 阈值：低=更敏感(召回高)，高=更保守(精度高)。
        vad_config.silero_vad.threshold = threshold
        # 最小静音：决定“静音达到多久才判定句子结束”。
        vad_config.silero_vad.min_silence_duration = min_silence_duration
        # 最小语音：过滤过短噪声段，值越大越不容易出现碎片段。
        vad_config.silero_vad.min_speech_duration = min_speech_duration
        if hasattr(vad_config.silero_vad, "max_speech_duration"):
            # 最大语音：限制单段最长时长，防止超长语句一直不切段。
            vad_config.silero_vad.max_speech_duration = max_speech_duration
        window_size = vad_config.silero_vad.window_size
    else:
        # ten-vad 在不同版本 sherpa-onnx 的配置结构有差异，这里做兼容处理。
        if hasattr(vad_config, "ten_vad"):
            vad_config.ten_vad.model = str(vad_model_path)
            # 与 silero 同义：同一套调参逻辑。
            vad_config.ten_vad.threshold = threshold
            vad_config.ten_vad.min_silence_duration = min_silence_duration
            vad_config.ten_vad.min_speech_duration = min_speech_duration
            if hasattr(vad_config.ten_vad, "max_speech_duration"):
                vad_config.ten_vad.max_speech_duration = max_speech_duration
            window_size = vad_config.ten_vad.window_size
        else:
            LOGGER.warning(
                "当前 sherpa-onnx 版本未提供 ten_vad 字段，改用 silero_vad 配置结构加载 ten 模型。"
            )
            vad_config.silero_vad.model = str(vad_model_path)
            vad_config.silero_vad.threshold = threshold
            vad_config.silero_vad.min_silence_duration = min_silence_duration
            vad_config.silero_vad.min_speech_duration = min_speech_duration
            if hasattr(vad_config.silero_vad, "max_speech_duration"):
                vad_config.silero_vad.max_speech_duration = max_speech_duration
            window_size = vad_config.silero_vad.window_size

    vad_config.sample_rate = sample_rate
    vad = sherpa_onnx.VoiceActivityDetector(
        vad_config, buffer_size_in_seconds=buffer_size_in_seconds
    )
    LOGGER.info("VAD 初始化完成，window_size=%d", window_size)
    return vad, int(window_size)


def split_audio_by_vad(
    vad: sherpa_onnx.VoiceActivityDetector,
    audio_samples: np.ndarray,
    window_size: int,
    sample_rate: int,
) -> List[Tuple[int, np.ndarray]]:
    """
    使用 VAD 对音频进行分段。

    返回值：
    - List[(start_sample, segment_samples)]
    """
    LOGGER.info("开始 VAD 分段")
    total_windows = (len(audio_samples) + window_size - 1) // window_size

    for index in range(total_windows):
        start = index * window_size
        end = start + window_size
        window = audio_samples[start:end]

        # 对最后一个窗口补零，确保窗口长度满足模型要求。
        if len(window) < window_size:
            window = np.pad(window, (0, window_size - len(window)), mode="constant")

        vad.accept_waveform(window.astype(np.float32))

        if (index + 1) % 300 == 0 or (index + 1) == total_windows:
            LOGGER.info(
                "VAD 进度: %.1f%% (%d/%d)",
                (index + 1) / total_windows * 100.0,
                index + 1,
                total_windows,
            )

    vad.flush()

    segments: List[Tuple[int, np.ndarray]] = []
    while not vad.empty():
        segment_start = int(vad.front.start)
        segment_samples = np.asarray(vad.front.samples, dtype=np.float32).copy()
        segments.append((segment_start, segment_samples))
        vad.pop()

    total_duration = len(audio_samples) / float(sample_rate)
    LOGGER.info(
        "VAD 分段完成：共 %d 段（音频时长 %.2f 秒）",
        len(segments),
        total_duration,
    )
    return segments


def run_vad_segmentation(
    audio_samples: np.ndarray,
    sample_rate: int,
    vad_model_path: Path,
    vad_model_type: str,
    threshold: float,
    min_silence_duration: float,
    min_speech_duration: float,
    max_speech_duration: float,
    buffer_size_in_seconds: float,
) -> List[Tuple[int, np.ndarray]]:
    """执行一次 VAD 分段（便于单阈值与迟滞双阈值复用）。"""
    vad, window_size = create_vad_detector(
        vad_model_path=vad_model_path,
        vad_model_type=vad_model_type,
        sample_rate=sample_rate,
        threshold=threshold,
        min_silence_duration=min_silence_duration,
        min_speech_duration=min_speech_duration,
        max_speech_duration=max_speech_duration,
        buffer_size_in_seconds=buffer_size_in_seconds,
    )
    return split_audio_by_vad(
        vad=vad,
        audio_samples=audio_samples,
        window_size=window_size,
        sample_rate=sample_rate,
    )


def segments_to_ranges(segments: List[Tuple[int, np.ndarray]]) -> List[Tuple[int, int]]:
    """将 (start_sample, samples) 形式的分段转换为 [start, end) 采样点区间。"""
    ranges: List[Tuple[int, int]] = []
    for start, samples in segments:
        end = int(start) + int(len(samples))
        if end > start:
            ranges.append((int(start), end))
    ranges.sort(key=lambda item: item[0])
    return ranges


def ranges_to_segments(
    ranges: List[Tuple[int, int]],
    audio_samples: np.ndarray,
) -> List[Tuple[int, np.ndarray]]:
    """将采样点区间转换回识别所需的分段样本。"""
    total_samples = len(audio_samples)
    segments: List[Tuple[int, np.ndarray]] = []
    for start, end in ranges:
        safe_start = max(0, min(int(start), total_samples))
        safe_end = max(safe_start, min(int(end), total_samples))
        if safe_end <= safe_start:
            continue
        segment = np.asarray(audio_samples[safe_start:safe_end], dtype=np.float32).copy()
        segments.append((safe_start, segment))
    return segments


def merge_ranges(ranges: List[Tuple[int, int]], max_gap_samples: int) -> List[Tuple[int, int]]:
    """合并相邻间隔不超过 max_gap_samples 的分段。"""
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda item: item[0])
    merged: List[List[int]] = [[sorted_ranges[0][0], sorted_ranges[0][1]]]
    for start, end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if start - last_end <= max_gap_samples:
            merged[-1][1] = max(last_end, end)
        else:
            merged.append([start, end])

    return [(item[0], item[1]) for item in merged]


def filter_short_ranges(
    ranges: List[Tuple[int, int]], min_segment_samples: int
) -> List[Tuple[int, int]]:
    """过滤过短分段。"""
    return [(start, end) for start, end in ranges if (end - start) >= min_segment_samples]


def pad_ranges(
    ranges: List[Tuple[int, int]],
    pad_samples: int,
    total_samples: int,
) -> List[Tuple[int, int]]:
    """对每个分段前后补边，并裁剪到音频总长度范围。"""
    padded: List[Tuple[int, int]] = []
    for start, end in ranges:
        padded_start = max(0, start - pad_samples)
        padded_end = min(total_samples, end + pad_samples)
        if padded_end > padded_start:
            padded.append((padded_start, padded_end))
    return merge_ranges(padded, max_gap_samples=0)


def apply_hysteresis_ranges(
    low_ranges: List[Tuple[int, int]],
    high_ranges: List[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    """
    迟滞双阈值融合策略：
    - 低阈值段提供更完整边界（更宽松）；
    - 高阈值段提供可信语音核心（更保守）；
    - 仅保留“与高阈值核心有重叠”的低阈值段。
    """
    if not low_ranges:
        return []
    if not high_ranges:
        return []

    selected: List[Tuple[int, int]] = []
    high_idx = 0
    for low_start, low_end in low_ranges:
        while high_idx < len(high_ranges) and high_ranges[high_idx][1] < low_start:
            high_idx += 1

        probe_idx = high_idx
        keep = False
        while probe_idx < len(high_ranges):
            high_start, high_end = high_ranges[probe_idx]
            if high_start > low_end:
                break
            if high_end >= low_start and high_start <= low_end:
                keep = True
                break
            probe_idx += 1

        if keep:
            selected.append((low_start, low_end))

    return merge_ranges(selected, max_gap_samples=0)


def post_process_vad_ranges(
    ranges: List[Tuple[int, int]],
    sample_rate: int,
    total_samples: int,
    merge_gap_seconds: float,
    min_segment_seconds: float,
    pad_seconds: float,
) -> List[Tuple[int, int]]:
    """
    VAD 后处理：
    1. 合并近邻分段
    2. 过滤极短分段
    3. 前后补边并再次去重合并
    """
    merge_gap_samples = int(round(merge_gap_seconds * sample_rate))
    min_segment_samples = int(round(min_segment_seconds * sample_rate))
    pad_samples = int(round(pad_seconds * sample_rate))

    raw_count = len(ranges)
    merged_ranges = merge_ranges(ranges, max_gap_samples=merge_gap_samples)
    merged_count = len(merged_ranges)

    filtered_ranges = filter_short_ranges(merged_ranges, min_segment_samples=min_segment_samples)
    filtered_count = len(filtered_ranges)

    padded_ranges = pad_ranges(filtered_ranges, pad_samples=pad_samples, total_samples=total_samples)
    final_count = len(padded_ranges)

    LOGGER.info(
        "VAD后处理统计: raw=%d, after_merge=%d, after_filter=%d, final=%d "
        "(merge_gap=%.3fs, min_segment=%.3fs, pad=%.3fs)",
        raw_count,
        merged_count,
        filtered_count,
        final_count,
        merge_gap_seconds,
        min_segment_seconds,
        pad_seconds,
    )
    return padded_ranges


def log_vad_metrics(
    ranges: List[Tuple[int, int]],
    sample_rate: int,
    stage: str,
    short_segment_threshold: float,
) -> None:
    """输出 VAD 分段质量指标，便于调参回归。"""
    if not ranges:
        LOGGER.info("VAD指标[%s]: segments=0", stage)
        return

    durations = np.array(
        [(end - start) / float(sample_rate) for start, end in ranges],
        dtype=np.float64,
    )
    short_ratio = float(np.mean(durations < short_segment_threshold)) if durations.size else 0.0

    LOGGER.info(
        "VAD指标[%s]: segments=%d, total=%.2fs, avg=%.2fs, p50=%.2fs, p90=%.2fs, "
        "short_ratio(<%.2fs)=%.2f%%",
        stage,
        len(ranges),
        float(np.sum(durations)),
        float(np.mean(durations)),
        float(np.percentile(durations, 50)),
        float(np.percentile(durations, 90)),
        short_segment_threshold,
        short_ratio * 100.0,
    )


def _extract_result(
    recognizer: sherpa_onnx.OfflineRecognizer,
    stream,
) -> Tuple[str, str, str, str]:
    """提取单段识别结果文本和附加信息。"""
    if hasattr(recognizer, "get_result"):
        result = recognizer.get_result(stream)
    else:
        result = stream.result

    text = getattr(result, "text", "")
    if not isinstance(text, str):
        text = str(text)
    # 仅当结果对象没有 text 字段时，才回退到整体字符串，避免把空结果对象文本化写入字幕。
    if not text.strip() and not hasattr(result, "text"):
        text = str(result)

    lang = getattr(result, "lang", "")
    emotion = getattr(result, "emotion", "")
    event = getattr(result, "event", "")
    return text.strip(), str(lang or "").strip(), str(emotion or "").strip(), str(event or "").strip()


def decode_vad_segments(
    recognizer: sherpa_onnx.OfflineRecognizer,
    vad_segments: List[Tuple[int, np.ndarray]],
    sample_rate: int = TARGET_SAMPLE_RATE,
) -> Tuple[List[SubtitleSegment], str, str, str, int]:
    """
    对 VAD 分段逐段识别，输出字幕段列表。

    返回值：
    - subtitles: 字幕段列表
    - lang/emotion/event: 从识别结果中抽取到的附加信息（首个非空值）
    - empty_count: 空转写片段数量（用于统计 empty_asr_ratio）
    """
    subtitles: List[SubtitleSegment] = []
    lang = ""
    emotion = ""
    event = ""
    empty_count = 0

    for index, (start_sample, segment_samples) in enumerate(vad_segments, start=1):
        stream = recognizer.create_stream()
        stream.accept_waveform(sample_rate=sample_rate, waveform=segment_samples)
        recognizer.decode_stream(stream)
        text, seg_lang, seg_emotion, seg_event = _extract_result(recognizer, stream)

        if seg_lang and not lang:
            lang = seg_lang
        if seg_emotion and not emotion:
            emotion = seg_emotion
        if seg_event and not event:
            event = seg_event

        if text:
            subtitles.append(
                SubtitleSegment(
                    start=start_sample / sample_rate,
                    duration=len(segment_samples) / sample_rate,
                    text=text,
                )
            )
        else:
            empty_count += 1

        if index % 50 == 0 or index == len(vad_segments):
            LOGGER.info(
                "识别进度: %.1f%% (%d/%d)",
                index / max(1, len(vad_segments)) * 100.0,
                index,
                len(vad_segments),
            )

    LOGGER.info(
        "分段识别完成：有效字幕段 %d / VAD 段 %d，空转写=%d",
        len(subtitles),
        len(vad_segments),
        empty_count,
    )
    return subtitles, lang, emotion, event, empty_count


def _format_srt_timestamp(seconds: float) -> str:
    """格式化 SRT 时间戳：HH:MM:SS,mmm。"""
    total_ms = max(0, int(round(seconds * 1000.0)))
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def save_srt(output_path: Path, subtitles: List[SubtitleSegment]) -> None:
    """写出 SRT 字幕文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for index, seg in enumerate(subtitles, start=1):
            if not seg.text.strip():
                continue
            start_text = _format_srt_timestamp(seg.start)
            end_text = _format_srt_timestamp(max(seg.end, seg.start + 0.01))
            f.write(f"{index}\n")
            f.write(f"{start_text} --> {end_text}\n")
            f.write(f"{seg.text.strip()}\n\n")
    LOGGER.info("字幕文件已写入: %s", output_path)


def build_transcript_text(subtitles: List[SubtitleSegment]) -> str:
    """将字幕段拼接为纯文本转录。"""
    parts = [seg.text.strip() for seg in subtitles if seg.text.strip()]
    return "\n".join(parts).strip()


def save_text(output_path: Path, text: str) -> None:
    """保存识别结果到文本文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text + "\n", encoding="utf-8")
    LOGGER.info("转录文本已写入: %s", output_path)


def should_cuda_fallback(
    decode_error: str, current_provider: str, fallback_enabled: bool
) -> bool:
    """判断是否应从 CUDA 回退到 CPU。"""
    return (
        current_provider == "cuda"
        and fallback_enabled
        and (
            "cudaErrorNoKernelImageForDevice" in decode_error
            or (
                "LoadLibrary failed with error 126" in decode_error
                and "onnxruntime_providers_cuda.dll" in decode_error
            )
        )
    )


def main() -> int:
    """脚本入口。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    args = parse_args()

    try:
        apply_vad_profile(args)
        validate_args(args)

        ensure_file_exists(args.video, "视频文件")
        ensure_file_exists(args.model, "模型文件")
        ensure_file_exists(args.tokens, "tokens 文件")
        vad_model_path = resolve_vad_model_path(args)
        ensure_file_exists(vad_model_path, "VAD 模型文件")

        # provider=cuda 时先尝试预加载运行时依赖，避免 onnxruntime error 126
        preload_cuda_runtime_dlls(args.provider)

        audio_samples = read_audio_via_ffmpeg(args.video)
        # 1) 原始分段：支持单阈值与迟滞双阈值。
        hysteresis_enabled = abs(args.vad_start_threshold - args.vad_end_threshold) > 1e-6
        if hysteresis_enabled:
            LOGGER.info(
                "启用VAD迟滞模式: start_threshold=%.3f, end_threshold=%.3f",
                args.vad_start_threshold,
                args.vad_end_threshold,
            )
            high_segments = run_vad_segmentation(
                audio_samples=audio_samples,
                sample_rate=TARGET_SAMPLE_RATE,
                vad_model_path=vad_model_path,
                vad_model_type=args.vad_model_type,
                threshold=args.vad_start_threshold,
                min_silence_duration=args.vad_min_silence,
                min_speech_duration=args.vad_min_speech,
                max_speech_duration=args.vad_max_speech,
                buffer_size_in_seconds=args.vad_buffer_seconds,
            )
            low_segments = run_vad_segmentation(
                audio_samples=audio_samples,
                sample_rate=TARGET_SAMPLE_RATE,
                vad_model_path=vad_model_path,
                vad_model_type=args.vad_model_type,
                threshold=args.vad_end_threshold,
                min_silence_duration=args.vad_min_silence,
                min_speech_duration=args.vad_min_speech,
                max_speech_duration=args.vad_max_speech,
                buffer_size_in_seconds=args.vad_buffer_seconds,
            )
            high_ranges = segments_to_ranges(high_segments)
            low_ranges = segments_to_ranges(low_segments)
            log_vad_metrics(
                high_ranges,
                sample_rate=TARGET_SAMPLE_RATE,
                stage="raw-high-threshold",
                short_segment_threshold=args.vad_short_segment_threshold,
            )
            log_vad_metrics(
                low_ranges,
                sample_rate=TARGET_SAMPLE_RATE,
                stage="raw-low-threshold",
                short_segment_threshold=args.vad_short_segment_threshold,
            )
            vad_ranges = apply_hysteresis_ranges(
                low_ranges=low_ranges,
                high_ranges=high_ranges,
            )
            log_vad_metrics(
                vad_ranges,
                sample_rate=TARGET_SAMPLE_RATE,
                stage="hysteresis-fused",
                short_segment_threshold=args.vad_short_segment_threshold,
            )
        else:
            raw_segments = run_vad_segmentation(
                audio_samples=audio_samples,
                sample_rate=TARGET_SAMPLE_RATE,
                vad_model_path=vad_model_path,
                vad_model_type=args.vad_model_type,
                threshold=args.vad_threshold,
                min_silence_duration=args.vad_min_silence,
                min_speech_duration=args.vad_min_speech,
                max_speech_duration=args.vad_max_speech,
                buffer_size_in_seconds=args.vad_buffer_seconds,
            )
            vad_ranges = segments_to_ranges(raw_segments)
            log_vad_metrics(
                vad_ranges,
                sample_rate=TARGET_SAMPLE_RATE,
                stage="raw-single-threshold",
                short_segment_threshold=args.vad_short_segment_threshold,
            )

        # 2) 后处理：合并近邻段、过滤极短段、补边。
        if not args.disable_vad_post_process:
            vad_ranges = post_process_vad_ranges(
                ranges=vad_ranges,
                sample_rate=TARGET_SAMPLE_RATE,
                total_samples=len(audio_samples),
                merge_gap_seconds=args.vad_merge_gap,
                min_segment_seconds=args.vad_min_segment,
                pad_seconds=args.vad_pad,
            )
            log_vad_metrics(
                vad_ranges,
                sample_rate=TARGET_SAMPLE_RATE,
                stage="post-processed",
                short_segment_threshold=args.vad_short_segment_threshold,
            )
        else:
            LOGGER.info("已禁用VAD后处理，直接使用原始分段结果。")

        vad_segments = ranges_to_segments(vad_ranges, audio_samples=audio_samples)
        LOGGER.info("最终送入ASR的分段数量: %d", len(vad_segments))

        current_provider = args.provider
        recognizer = create_recognizer(
            model_path=args.model,
            tokens_path=args.tokens,
            num_threads=args.num_threads,
            provider=current_provider,
            use_itn=args.use_itn,
            debug=args.debug,
        )

        LOGGER.info("开始分段识别（provider=%s）", current_provider)
        try:
            subtitles, lang, emotion, event, empty_count = decode_vad_segments(
                recognizer, vad_segments, TARGET_SAMPLE_RATE
            )
        except Exception as decode_exc:
            decode_error = str(decode_exc)
            if not should_cuda_fallback(
                decode_error=decode_error,
                current_provider=current_provider,
                fallback_enabled=args.enable_cuda_fallback,
            ):
                raise

            LOGGER.warning("CUDA 推理失败（%s），自动回退到 CPU 继续转录。", decode_error)
            current_provider = "cpu"
            recognizer = create_recognizer(
                model_path=args.model,
                tokens_path=args.tokens,
                num_threads=args.num_threads,
                provider=current_provider,
                use_itn=args.use_itn,
                debug=args.debug,
            )
            subtitles, lang, emotion, event, empty_count = decode_vad_segments(
                recognizer, vad_segments, TARGET_SAMPLE_RATE
            )

        # 某些版本在 CUDA 内核不兼容时不会抛异常，而是返回空结果并在 stderr 打印错误。
        # 为避免“看似成功但实际无文本”，这里对空结果做一次 CPU 兜底重试。
        if current_provider == "cuda" and args.enable_cuda_fallback and not subtitles:
            LOGGER.warning("CUDA 返回空转录结果，自动回退到 CPU 进行重试。")
            current_provider = "cpu"
            recognizer = create_recognizer(
                model_path=args.model,
                tokens_path=args.tokens,
                num_threads=args.num_threads,
                provider=current_provider,
                use_itn=args.use_itn,
                debug=args.debug,
            )
            subtitles, lang, emotion, event, empty_count = decode_vad_segments(
                recognizer, vad_segments, TARGET_SAMPLE_RATE
            )

        if current_provider == "cuda" and not args.enable_cuda_fallback and not subtitles:
            raise RuntimeError(
                "CUDA 推理返回空结果。若日志中包含 `cudaErrorNoKernelImageForDevice`，通常表示当前 "
                "onnxruntime CUDA 内核未包含本机显卡所需架构（如 GTX 1050 Ti 的 sm_61）。"
            )

        transcript = build_transcript_text(subtitles)
        LOGGER.info("离线转录完成")
        if vad_segments:
            empty_asr_ratio = empty_count / float(len(vad_segments))
            LOGGER.info(
                "ASR分段指标: input_segments=%d, empty_segments=%d, empty_asr_ratio=%.2f%%",
                len(vad_segments),
                empty_count,
                empty_asr_ratio * 100.0,
            )
        if lang:
            LOGGER.info("识别语言: %s", lang)
        if emotion:
            LOGGER.info("情绪标签: %s", emotion)
        if event:
            LOGGER.info("事件标签: %s", event)

        if transcript:
            print(transcript)
        else:
            print("[提示] 未识别到文本内容。")

        save_text(args.output_txt, transcript)
        save_srt(args.output_srt, subtitles)
        return 0
    except Exception as exc:
        error_text = str(exc)
        if (
            "LoadLibrary failed with error 126" in error_text
            and "onnxruntime_providers_cuda.dll" in error_text
        ):
            LOGGER.error(
                "检测到 CUDA provider 依赖缺失（error 126）。请确保 sherpa-onnx wheel 与 CUDA/cuDNN 主版本一致："
                "`+cuda` 对应 CUDA 11.8 + cuDNN 8；`+cuda12.cudnn9` 对应 CUDA 12.x + cuDNN 9。"
            )
        LOGGER.exception("转录失败: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
