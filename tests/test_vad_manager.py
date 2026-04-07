"""
VadManager 回归测试。

验证配置变化时是否会正确触发 VAD 检测器重载。
"""

import os
import sys

# 保持与现有测试风格一致
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vad.models import VadConfig, VadModel
from vad.vad_manager import VadManager


def _build_config(**overrides) -> VadConfig:
    """构建基础 VadConfig，并允许按需覆盖字段。"""
    cfg = VadConfig(
        model=VadModel.SILERO,
        model_path=None,
        threshold=0.62,
        min_speech_duration_ms=90.0,
        min_silence_duration_ms=160.0,
        max_speech_duration_ms=7000.0,
        window_size_samples=512,
        sample_rate=16000,
        use_sherpa_onnx=True,
    )
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def test_should_reload_when_max_speech_duration_changes():
    """修改 max_speech_duration_ms 时必须触发重载。"""
    manager = VadManager()
    manager._detector = object()
    manager._current_config = _build_config(max_speech_duration_ms=7000.0)

    new_config = _build_config(max_speech_duration_ms=3000.0)
    assert manager._should_reload(new_config) is True


def test_should_reload_when_min_silence_duration_changes():
    """修改 min_silence_duration_ms 时必须触发重载。"""
    manager = VadManager()
    manager._detector = object()
    manager._current_config = _build_config(min_silence_duration_ms=160.0)

    new_config = _build_config(min_silence_duration_ms=120.0)
    assert manager._should_reload(new_config) is True


def test_should_not_reload_when_configs_are_equivalent():
    """配置等价时应复用检测器。"""
    manager = VadManager()
    manager._detector = object()
    manager._current_config = _build_config()

    new_config = _build_config()
    assert manager._should_reload(new_config) is False
