#!/usr/bin/env python3

import argparse
import math
import os
import queue
import sys
import threading
import time
import warnings
from pathlib import Path

import numpy as np
# python tests\test_vad-system.py --output-mode transcribe --mono-method first --block-seconds 0.05

def _apply_numpy_fromstring_binary_compat() -> None:
    """
    为 soundcard 兼容新版 numpy。

    soundcard 当前版本在底层读取音频块时仍调用 `numpy.fromstring(binary_data, ...)`。
    在新版 numpy 中该二进制模式已移除，会抛出 ValueError，这里仅对该场景做兼容。
    """
    original_fromstring = np.fromstring

    try:
        original_fromstring(b"\x00\x00\x80?", dtype=np.float32)
        return
    except ValueError as exc:
        if "binary mode of fromstring is removed" not in str(exc):
            return

    def _fromstring_compat(string, dtype=float, count=-1, sep="", **kwargs):
        if sep == "":
            like = kwargs.get("like", None)
            if like is None:
                # 兼容旧版 fromstring(binary) 的拷贝语义，避免返回视图引用已释放缓冲区
                return np.frombuffer(string, dtype=dtype, count=count).copy()
            try:
                return np.frombuffer(string, dtype=dtype, count=count, like=like).copy()
            except TypeError:
                return np.frombuffer(string, dtype=dtype, count=count).copy()
        return original_fromstring(string, dtype=dtype, count=count, sep=sep, **kwargs)

    np.fromstring = _fromstring_compat


# 在导入 soundcard 前应用兼容补丁，确保其内部调用可用。
_apply_numpy_fromstring_binary_compat()

try:
    import soundcard as sc
    from soundcard import SoundcardRuntimeWarning
except ImportError:
    print("请先安装 soundcard。可执行：")
    print()
    print("  pip install soundcard")
    print()
    sys.exit(-1)

import sherpa_onnx


class SystemAudioVadTester:
    """系统音频 VAD 测试类。"""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.sample_rate = args.sample_rate
        self.system_sample_rate = args.system_sample_rate
        self.samples_per_read = int(args.block_seconds * self.system_sample_rate)
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=args.queue_size)
        self.stop_event = threading.Event()
        self.capture_thread: threading.Thread | None = None
        self._mono_channel_index: int | None = None
        self._sos = None
        self._sos_state = None

        self.segment_index = 0
        self.detected_printed = False
        self.captured_chunks = 0
        self.processed_chunks = 0
        self.dropped_chunks = 0

        self._validate_model_path()
        self.vad = self._create_vad()
        self.resample_fn = self._build_resampler()
        self._init_filter()

    def _validate_model_path(self) -> None:
        """校验 VAD 模型文件是否存在。"""
        if not Path(self.args.silero_vad_model).is_file():
            raise RuntimeError(
                f"{self.args.silero_vad_model} 不存在。请从以下地址下载："
                "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
            )

    def _create_vad(self) -> sherpa_onnx.VoiceActivityDetector:
        """创建并返回 VAD 检测器。"""
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = self.args.silero_vad_model
        config.sample_rate = self.sample_rate
        return sherpa_onnx.VoiceActivityDetector(
            config, buffer_size_in_seconds=self.args.buffer_size_seconds
        )

    def _resolve_loopback_microphone(self):
        """
        获取系统回环设备。

        优先使用 `--speaker-name`，否则使用默认扬声器。
        """
        if self.args.speaker_name:
            speaker = sc.get_speaker(self.args.speaker_name)
            if speaker is None:
                raise RuntimeError(f"未找到指定扬声器: {self.args.speaker_name}")
        else:
            speaker = sc.default_speaker()
            if speaker is None:
                raise RuntimeError("未找到默认扬声器，无法进行系统音频回环采集")

        loopback_mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        if loopback_mic is None:
            raise RuntimeError(f"未找到扬声器 {speaker.name} 对应的回环输入设备")

        print(f"使用扬声器: {speaker.name}")
        print(f"使用回环设备: {loopback_mic.name}，声道数: {loopback_mic.channels}")
        return loopback_mic

    def _build_resampler(self):
        """构建重采样函数，避免循环中重复初始化。"""
        if self.system_sample_rate == self.sample_rate:
            return lambda x: x

        ratio = self.sample_rate / self.system_sample_rate

        # 常见场景: 48k -> 16k，直接抽取可显著降低 CPU 开销，稳定性更好。
        if self.system_sample_rate % self.sample_rate == 0:
            step = self.system_sample_rate // self.sample_rate
            return lambda x: x[::step]

        # 次选 scipy 的多相重采样。
        try:
            from scipy.signal import resample_poly

            g = math.gcd(self.sample_rate, self.system_sample_rate)
            up = self.sample_rate // g
            down = self.system_sample_rate // g
            return lambda x: resample_poly(x, up, down).astype(np.float32, copy=False)
        except Exception:
            pass

        # 最后兜底: 线性插值，质量一般但稳定可用。
        def _linear_resample(x: np.ndarray) -> np.ndarray:
            if x.size == 0:
                return x
            target_len = max(1, int(round(x.size * ratio)))
            src_index = np.arange(x.size, dtype=np.float64)
            dst_index = np.linspace(0, x.size - 1, target_len, dtype=np.float64)
            return np.interp(dst_index, src_index, x).astype(np.float32, copy=False)

        return _linear_resample

    def _init_filter(self) -> None:
        """
        初始化降噪滤波器状态。

        默认做轻量高通+低通，抑制低频电流声和高频嘶声。
        """
        self._sos = None
        self._sos_state = None

        if not self.args.enable_denoise:
            return

        nyq = self.sample_rate / 2.0
        highpass_hz = max(0.0, float(self.args.highpass_hz))
        lowpass_hz = max(0.0, float(self.args.lowpass_hz))

        if highpass_hz <= 0 and lowpass_hz <= 0:
            return

        # 截止频率边界保护
        if lowpass_hz > 0:
            lowpass_hz = min(lowpass_hz, nyq * 0.98)
        if highpass_hz > 0:
            highpass_hz = min(highpass_hz, nyq * 0.8)

        try:
            from scipy.signal import butter
        except Exception:
            print("提示: scipy 不可用，已跳过滤波步骤")
            return

        btype = None
        wn = None
        if highpass_hz > 0 and lowpass_hz > 0 and highpass_hz < lowpass_hz:
            btype = "bandpass"
            wn = [highpass_hz / nyq, lowpass_hz / nyq]
        elif highpass_hz > 0 and (lowpass_hz <= 0 or highpass_hz >= lowpass_hz):
            btype = "highpass"
            wn = highpass_hz / nyq
        elif lowpass_hz > 0:
            btype = "lowpass"
            wn = lowpass_hz / nyq

        if btype is None:
            return

        self._sos = butter(self.args.filter_order, wn, btype=btype, output="sos")
        self._sos_state = np.zeros((self._sos.shape[0], 2), dtype=np.float64)

    def _apply_noise_gate(self, samples: np.ndarray) -> np.ndarray:
        """应用轻量噪声门，压低底噪。"""
        if not self.args.enable_denoise:
            return samples
        if self.args.noise_gate_db <= -120:
            return samples

        threshold = 10 ** (self.args.noise_gate_db / 20.0)
        mask = np.abs(samples) < threshold
        if not np.any(mask):
            return samples

        # 使用比例衰减而不是硬置零，减少“断断续续”的听感。
        samples = samples.copy()
        samples[mask] *= self.args.noise_gate_ratio
        return samples

    def _post_process_samples(self, samples: np.ndarray) -> np.ndarray:
        """重采样后处理：去直流 + 滤波 + 噪声门。"""
        if not self.args.enable_denoise:
            return samples.astype(np.float32, copy=False)
        if samples.size == 0:
            return samples

        # 去直流偏置（仅在启用降噪时执行）
        samples = samples - np.mean(samples, dtype=np.float64)

        # 频段滤波
        if self._sos is not None and self._sos_state is not None:
            from scipy.signal import sosfilt

            filtered, self._sos_state = sosfilt(
                self._sos,
                samples.astype(np.float64, copy=False),
                zi=self._sos_state,
            )
            samples = filtered.astype(np.float32, copy=False)

        # 噪声门
        samples = self._apply_noise_gate(samples)

        return np.clip(samples, -1.0, 1.0).astype(np.float32, copy=False)

    def _to_mono(self, data: np.ndarray) -> np.ndarray:
        """将多声道数据转为单声道，便于 VAD 处理。"""
        if data.ndim == 1:
            return data.reshape(-1)

        if data.shape[1] == 1:
            return data[:, 0]

        # 取左声道：相位最稳定，但可能损失部分声场内容。
        if self.args.mono_method == "first":
            return data[:, 0]

        # 均值混合：保留整体内容，但极端情况下可能产生相位抵消。
        if self.args.mono_method == "mean":
            return data.mean(axis=1)

        # 自动策略：仅首次选择能量更高的声道，后续保持固定，避免声道来回切换导致失真。
        if self._mono_channel_index is None:
            rms = np.sqrt(np.mean(np.square(data), axis=0))
            self._mono_channel_index = int(np.argmax(rms))
        return data[:, self._mono_channel_index]

    def _resample_if_needed(self, samples: np.ndarray) -> np.ndarray:
        """采样率不一致时进行重采样。"""
        return self.resample_fn(samples)

    def _consume_vad_segments(self) -> None:
        """输出并保存 VAD 切分的语音段。"""
        while not self.vad.empty():
            segment_samples = self.vad.front.samples
            duration = len(segment_samples) / self.sample_rate
            filename = f"sys-seg-{self.segment_index}-{duration:.3f}-seconds.wav"
            self.segment_index += 1

            sherpa_onnx.write_wave(filename, segment_samples, self.sample_rate)
            print(f"语音段时长: {duration:.3f} 秒")
            print(f"已保存: {filename}")
            print("----------")

            self.vad.pop()

            if self.args.max_segments > 0 and self.segment_index >= self.args.max_segments:
                raise StopIteration("达到 max_segments，测试结束")

    def _capture_loop(self, recorder) -> None:
        """
        采集线程：只做“快速读取 + 入队”，不做重计算。

        这样可以避免重采样/VAD占用采集节拍，降低 data discontinuity 概率。
        """
        while not self.stop_event.is_set():
            try:
                data = recorder.record(numframes=self.samples_per_read)
                if data is None or data.size == 0:
                    continue
                self.captured_chunks += 1
                packet = data.astype(np.float32, copy=False)

                try:
                    self.audio_queue.put_nowait(packet)
                except queue.Full:
                    # 队列满时丢弃最旧块，保证采集线程不阻塞。
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.audio_queue.put_nowait(packet)
                    self.dropped_chunks += 1
            except Exception as exc:
                if not self.stop_event.is_set():
                    print(f"采集线程异常: {exc}")
                time.sleep(0.01)

    def _process_loop(self) -> None:
        """处理线程（主线程）循环。"""
        while not self.stop_event.is_set():
            try:
                data = self.audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            samples = self._to_mono(data)
            samples = self._resample_if_needed(samples).astype("float32", copy=False)
            samples = self._post_process_samples(samples)
            self.processed_chunks += 1

            self.vad.accept_waveform(samples)

            if self.vad.is_speech_detected() and not self.detected_printed:
                print("检测到语音")
                self.detected_printed = True
            elif not self.vad.is_speech_detected():
                self.detected_printed = False

            self._consume_vad_segments()

    def run(self) -> None:
        """启动系统音频 VAD 测试。"""
        # 避免同一告警刷屏，重点关注质量指标与保存结果。
        if self.args.suppress_discontinuity_warning:
            warnings.filterwarnings(
                "ignore",
                message="data discontinuity in recording",
                category=SoundcardRuntimeWarning,
            )
        else:
            warnings.filterwarnings(
                "once",
                message="data discontinuity in recording",
                category=SoundcardRuntimeWarning,
            )

        loopback_mic = self._resolve_loopback_microphone()
        print("测试开始。请播放系统音频（播放器/浏览器等），按 Ctrl+C 退出")

        start_time = time.time()
        with loopback_mic.recorder(
            samplerate=self.system_sample_rate,
            blocksize=self.samples_per_read,
        ) as recorder:
            self.capture_thread = threading.Thread(
                target=self._capture_loop,
                args=(recorder,),
                daemon=True,
            )
            self.capture_thread.start()

            try:
                self._process_loop()
            finally:
                self.stop_event.set()
                if self.capture_thread.is_alive():
                    self.capture_thread.join(timeout=2.0)

                elapsed = max(0.001, time.time() - start_time)
                print("========== 统计信息 ==========")
                print(f"运行时长: {elapsed:.2f}s")
                print(f"采集块数: {self.captured_chunks}")
                print(f"处理块数: {self.processed_chunks}")
                print(f"丢弃块数: {self.dropped_chunks}")
                print(f"采集速率: {self.captured_chunks / elapsed:.2f} chunk/s")
                print("============================")


class SystemAudioVadAsrTester(SystemAudioVadTester):
    """
    系统音频 VAD + 转录测试类。

    与 SystemAudioVadTester 的差异：
    - 不再将语音段保存为 wav；
    - 对每个 VAD 语音段直接进行转录并输出文本。
    """

    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.recognizer = self._create_recognizer()
        self.transcribed_segments = 0
        self.non_empty_results = 0

    def _assert_file_exists(self, filename: str, hint: str) -> None:
        """校验模型文件是否存在。"""
        if not Path(filename).is_file():
            raise RuntimeError(f"{filename} 不存在。{hint}")

    def _create_recognizer(self):
        """创建 SenseVoice 离线识别器。"""
        self._assert_file_exists(
            self.args.sense_voice_model,
            "请检查 --sense-voice-model 路径",
        )
        self._assert_file_exists(
            self.args.tokens,
            "请检查 --tokens 路径",
        )

        if self.args.num_threads <= 0:
            raise ValueError("--num-threads 必须大于 0")

        recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=self.args.sense_voice_model,
            tokens=self.args.tokens,
            num_threads=self.args.num_threads,
            use_itn=self.args.use_itn,
            debug=False,
            provider=self.args.provider,
        )
        return recognizer

    def _transcribe_segment(self, segment_samples: np.ndarray) -> str:
        """转录单个语音段并返回文本。"""
        stream = self.recognizer.create_stream()
        stream.accept_waveform(self.sample_rate, segment_samples)
        self.recognizer.decode_stream(stream)
        return stream.result.text.strip()

    def _consume_vad_segments(self) -> None:
        """消费 VAD 语音段并直接输出转录文本。"""
        while not self.vad.empty():
            segment = self.vad.front
            segment_samples = segment.samples

            start = getattr(segment, "start", 0)
            duration = len(segment_samples) / self.sample_rate
            start_sec = start / self.sample_rate
            end_sec = start_sec + duration

            text = self._transcribe_segment(segment_samples)

            self.segment_index += 1
            self.transcribed_segments += 1
            if text:
                self.non_empty_results += 1
                print(
                    f"[{self.segment_index}] "
                    f"{start_sec:.2f}s -> {end_sec:.2f}s "
                    f"({duration:.2f}s): {text}"
                )
            else:
                print(
                    f"[{self.segment_index}] "
                    f"{start_sec:.2f}s -> {end_sec:.2f}s "
                    f"({duration:.2f}s): [空结果]"
                )
            print("----------")

            self.vad.pop()

            if self.args.max_segments > 0 and self.segment_index >= self.args.max_segments:
                raise StopIteration("达到 max_segments，测试结束")

    def run(self) -> None:
        """运行转录测试并在结束时补充转录统计。"""
        try:
            super().run()
        finally:
            print("====== 转录统计 ======")
            print(f"已转录段数: {self.transcribed_segments}")
            print(f"非空结果段数: {self.non_empty_results}")
            print("======================")


def get_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--silero-vad-model",
        type=str,
        default="models/silero_vad/silero_vad.onnx",
        help="silero_vad.onnx 的路径",
    )

    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="VAD 输入采样率",
    )

    parser.add_argument(
        "--system-sample-rate",
        type=int,
        default=int(os.environ.get("SHERPA_ONNX_SYS_SAMPLE_RATE", "48000")),
        help="系统音频回环采样率",
    )

    parser.add_argument(
        "--block-seconds",
        type=float,
        default=0.05,
        help="每次读取的音频时长（秒）",
    )

    parser.add_argument(
        "--buffer-size-seconds",
        type=float,
        default=30,
        help="VAD 内部缓存时长（秒）",
    )

    parser.add_argument(
        "--speaker-name",
        type=str,
        default=None,
        help="指定扬声器名称；为空时使用默认扬声器",
    )

    parser.add_argument(
        "--max-segments",
        type=int,
        default=0,
        help="最多保存的语音段数量，0 表示不限制",
    )

    parser.add_argument(
        "--output-mode",
        type=str,
        choices=["wav", "transcribe"],
        default="wav",
        help="输出模式：wav(保存语音段) 或 transcribe(直接转录输出)",
    )

    parser.add_argument(
        "--queue-size",
        type=int,
        default=128,
        help="采集队列长度；过小会丢块，过大可能增加延迟",
    )

    parser.add_argument(
        "--mono-method",
        type=str,
        choices=["auto", "first", "mean"],
        default="first",
        help="多声道转单声道策略",
    )

    parser.add_argument(
        "--enable-denoise",
        action="store_true",
        help="启用降噪后处理（默认关闭）",
    )

    parser.add_argument(
        "--highpass-hz",
        type=float,
        default=0.0,
        help="高通截止频率(Hz)，用于抑制低频电流声，<=0 表示关闭",
    )

    parser.add_argument(
        "--lowpass-hz",
        type=float,
        default=0.0,
        help="低通截止频率(Hz)，用于抑制高频嘶声，<=0 表示关闭",
    )

    parser.add_argument(
        "--filter-order",
        type=int,
        default=4,
        help="巴特沃斯滤波器阶数",
    )

    parser.add_argument(
        "--noise-gate-db",
        type=float,
        default=-120.0,
        help="噪声门阈值(dBFS)，更高(如-52)会更强力降噪",
    )

    parser.add_argument(
        "--noise-gate-ratio",
        type=float,
        default=1.0,
        help="噪声门衰减比例(0~1)，越小降噪越强",
    )

    parser.add_argument(
        "--sense-voice-model",
        type=str,
        default="models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx",
        help="SenseVoice model.onnx 路径（transcribe 模式必需）",
    )

    parser.add_argument(
        "--tokens",
        type=str,
        default="models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/tokens.txt",
        help="tokens.txt 路径（transcribe 模式必需）",
    )

    parser.add_argument(
        "--num-threads",
        type=int,
        default=2,
        help="识别器线程数（transcribe 模式）",
    )

    parser.add_argument(
        "--provider",
        type=str,
        default="cpu",
        help="识别器推理后端，如 cpu/cuda（transcribe 模式）",
    )

    parser.add_argument(
        "--use-itn",
        action="store_true",
        help="转录后启用 ITN（数字/时间等文本规范化）",
    )

    parser.add_argument(
        "--suppress-discontinuity-warning",
        action="store_true",
        help="忽略 soundcard 的 data discontinuity 警告刷屏",
    )

    args = parser.parse_args()
    if args.sample_rate <= 0:
        raise ValueError("--sample-rate 必须大于 0")
    if args.system_sample_rate <= 0:
        raise ValueError("--system-sample-rate 必须大于 0")
    if args.block_seconds <= 0:
        raise ValueError("--block-seconds 必须大于 0")
    if args.buffer_size_seconds <= 0:
        raise ValueError("--buffer-size-seconds 必须大于 0")
    if args.max_segments < 0:
        raise ValueError("--max-segments 不能小于 0")
    if args.queue_size <= 0:
        raise ValueError("--queue-size 必须大于 0")
    if args.filter_order <= 0:
        raise ValueError("--filter-order 必须大于 0")
    if not 0 <= args.noise_gate_ratio <= 1:
        raise ValueError("--noise-gate-ratio 必须在 0 到 1 之间")
    if args.num_threads <= 0:
        raise ValueError("--num-threads 必须大于 0")
    return args


def main():
    args = get_args()
    if args.output_mode == "transcribe":
        tester = SystemAudioVadAsrTester(args)
        print("当前模式: transcribe（语音段将直接转录输出）")
    else:
        tester = SystemAudioVadTester(args)
        print("当前模式: wav（语音段将保存为 wav 文件）")

    try:
        tester.run()
    except StopIteration as stop_exc:
        print(str(stop_exc))
    except KeyboardInterrupt:
        print("\n捕获到 Ctrl+C，退出测试")
        tester.stop_event.set()


if __name__ == "__main__":
    main()
