"""
VAD 检测器回归测试。

覆盖 SherpaOnnxVAD 在 TRANSITION_TO_SPEECH 阶段的音频选择逻辑，
避免“只保留暂停前短片段”问题再次出现。
"""

import os
import sys
from unittest.mock import patch

import numpy as np

# 添加 src 目录到路径，保持与现有测试风格一致
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vad.detector import SherpaOnnxVAD
from vad.models import VadConfig, VadModel, VadState


class _FakeSegment:
    """模拟 sherpa-onnx 的语音段对象。"""

    def __init__(self, samples: np.ndarray):
        self.samples = samples


class _FakeSherpaVadModel:
    """模拟 sherpa-onnx VoiceActivityDetector 的最小行为。"""

    def __init__(self, segment_samples: np.ndarray):
        self._segment = _FakeSegment(segment_samples)
        self._is_empty = False

    def accept_waveform(self, _audio: np.ndarray) -> None:
        """模拟接收音频数据。"""
        return None

    def empty(self) -> bool:
        """模拟是否存在可消费语音段。"""
        return self._is_empty

    @property
    def front(self) -> _FakeSegment:
        """返回当前语音段。"""
        return self._segment

    def pop(self) -> None:
        """消费语音段。"""
        self._is_empty = True


def _build_detector_with_fake_model(segment_samples: np.ndarray) -> SherpaOnnxVAD:
    """构造注入假 VAD 模型的 SherpaOnnxVAD 实例。"""
    fake_model = _FakeSherpaVadModel(segment_samples.astype(np.float32, copy=False))

    def _mock_load_model(self):
        self._vad_model = fake_model

    config = VadConfig(
        model=VadModel.SILERO,
        threshold=0.45,
        min_speech_duration_ms=100.0,
        min_silence_duration_ms=300.0,
        max_speech_duration_ms=15000.0,
        sample_rate=16000,
        use_sherpa_onnx=True,
    )

    with patch.object(SherpaOnnxVAD, "_load_model", _mock_load_model):
        detector = SherpaOnnxVAD(config)

    return detector


def test_sherpa_detect_should_use_full_segment_when_segment_is_longer_than_buffer():
    """
    当 sherpa 返回完整分段比缓冲更长时，应优先使用完整分段。

    这可以避免“仅保留暂停前短时间音频”的回归。
    """
    full_segment = np.ones(48000, dtype=np.float32)  # 约 3 秒 @16k
    detector = _build_detector_with_fake_model(full_segment)

    # 触发 TRANSITION_TO_SPEECH：输入长度 > min_speech_samples(1600)
    chunk = np.ones(3200, dtype=np.float32)
    result = detector.detect(chunk)

    assert result.state == VadState.TRANSITION_TO_SPEECH
    assert result.audio_data is not None
    assert len(result.audio_data) == len(full_segment)


def test_sherpa_detect_should_keep_buffer_when_segment_is_shorter_than_buffer():
    """
    当 sherpa 返回分段更短时，仍保留起始缓冲，避免首字被截断。
    """
    short_segment = np.ones(800, dtype=np.float32)
    detector = _build_detector_with_fake_model(short_segment)

    chunk = np.ones(3200, dtype=np.float32)
    result = detector.detect(chunk)

    assert result.state == VadState.TRANSITION_TO_SPEECH
    assert result.audio_data is not None
    assert len(result.audio_data) == len(chunk)
