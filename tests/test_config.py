"""
配置管理模块测试

测试ConfigManager和Config类的功能
"""

import sys
import os
import pytest
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.manager import ConfigManager
from config.models import Config, AudioDevice


class TestConfig:
    """Config类测试"""

    def test_valid_config(self):
        """测试有效配置"""
        # 创建临时模型文件用于测试
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            config = Config()
            config.model_path = str(temp_model)
            config.input_source = "microphone"
            # 如果没有抛出异常，说明配置有效
            assert config.model_path == str(temp_model)
            assert config.input_source == "microphone"
        finally:
            # 清理临时文件
            temp_model.unlink(missing_ok=True)

    def test_invalid_model_path(self):
        """测试无效模型路径"""
        with pytest.raises(ValueError, match="模型路径不存在"):
            config = Config()
            config.model_path = "nonexistent.onnx"
            config.input_source = "microphone"
            config.validate()

    def test_invalid_input_source(self):
        """测试无效输入源"""
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            with pytest.raises(ValueError, match="不支持的输入源"):
                config = Config()
                config.model_path = str(temp_model)
                config.input_source = "invalid_source"
                config.validate()
        finally:
            temp_model.unlink(missing_ok=True)

    def test_invalid_vad_sensitivity(self):
        """测试无效VAD敏感度"""
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            with pytest.raises(ValueError, match="VAD阈值必须在0.0-1.0之间"):
                config = Config()
                config.model_path = str(temp_model)
                config.input_source = "microphone"
                config.vad_sensitivity = 1.5
                config.validate()
        finally:
            temp_model.unlink(missing_ok=True)

    def test_from_dict_v2_should_apply_flat_overrides_to_active_vad_profile(self):
        """测试v2结构中混用flat覆盖键时，覆盖会作用于激活VAD方案"""
        config = Config.from_dict_v2({
            "runtime": {
                "input_source": "microphone",
                "model": {
                    "active_profile_id": "default",
                    "profiles": {
                        "default": {
                            "profile_id": "default",
                            "profile_name": "默认",
                            "model_path": "test_model.onnx"
                        }
                    }
                }
            },
            "audio": {
                "sample_rate": 16000,
                "chunk_size": 1024,
                "channels": 1
            },
            "vad": {
                "active_profile_id": "profile_custom",
                "profiles": {
                    "default": {
                        "profile_name": "默认",
                        "profile_id": "default",
                        "threshold": 0.2
                    },
                    "profile_custom": {
                        "profile_name": "自定义",
                        "profile_id": "profile_custom",
                        "threshold": 0.3
                    }
                }
            },
            "subtitle": {
                "file": {},
                "display": {}
            },
            "vad_threshold": 0.85,
            "vad_window_size": 0.256
        })

        assert config.active_vad_profile_id == "profile_custom"
        assert config.vad_profiles["profile_custom"].threshold == 0.85
        assert config.vad_profiles["profile_custom"].window_size_samples == int(0.256 * 16000)
        assert config.vad_profiles["default"].threshold == 0.2

    def test_from_dict_v2_should_apply_flat_subtitle_stream_overrides(self):
        """测试v2结构中混用flat覆盖键时，字幕流合并参数覆盖生效"""
        config = Config.from_dict_v2({
            "runtime": {
                "input_source": "microphone",
                "model": {
                    "active_profile_id": "default",
                    "profiles": {
                        "default": {
                            "profile_id": "default",
                            "profile_name": "默认",
                            "model_path": "test_model.onnx"
                        }
                    }
                }
            },
            "audio": {
                "sample_rate": 16000,
                "chunk_size": 1024,
                "channels": 1
            },
            "vad": {
                "active_profile_id": "default",
                "profiles": {
                    "default": {
                        "profile_name": "默认",
                        "profile_id": "default",
                        "threshold": 0.3
                    }
                }
            },
            "subtitle": {
                "file": {},
                "display": {}
            },
            "stream_merge_target_duration": 12.5,
            "stream_long_segment_threshold": 7.2,
            "stream_merge_max_gap": 0.45,
            "max_subtitle_duration": 4.0,
        })

        assert config.stream_merge_target_duration == 12.5
        assert config.stream_long_segment_threshold == 7.2
        assert config.stream_merge_max_gap == 0.45
        assert config.max_subtitle_duration == 4.0


class TestConfigManager:
    """ConfigManager类测试"""

    def test_parse_minimal_args(self):
        """测试最小参数解析"""
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            manager = ConfigManager()
            config = manager.parse_arguments([
                "--model-path", str(temp_model),
                "--input-source", "microphone"
            ])

            assert config.model_path == str(temp_model)
            assert config.input_source == "microphone"
            assert config.use_gpu == True  # 默认启用GPU
            assert config.vad_sensitivity == 0.5  # 默认值
        finally:
            temp_model.unlink(missing_ok=True)

    def test_parse_full_args(self):
        """测试完整参数解析"""
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            manager = ConfigManager()
            config = manager.parse_arguments([
                "--model-path", str(temp_model),
                "--input-source", "system",
                "--no-gpu",
                "--vad-sensitivity", "0.8",
                "--sample-rate", "22050",
                "--chunk-size", "2048",
                "--output-format", "json",
                "--no-confidence",
                "--no-timestamp",
                "--stream-merge-target-duration", "12.0",
                "--stream-long-segment-threshold", "7.0",
                "--stream-merge-max-gap", "0.4",
                "--max-subtitle-duration", "4.5",
            ])

            assert config.model_path == str(temp_model)
            assert config.input_source == "system"
            assert config.use_gpu == False  # 禁用GPU
            assert config.vad_sensitivity == 0.8
            assert config.sample_rate == 22050
            assert config.chunk_size == 2048
            assert config.output_format == "json"
            assert config.show_confidence == False
            assert config.show_timestamp == False
            assert config.stream_merge_target_duration == 12.0
            assert config.stream_long_segment_threshold == 7.0
            assert config.stream_merge_max_gap == 0.4
            assert config.max_subtitle_duration == 4.5
        finally:
            temp_model.unlink(missing_ok=True)

    def test_get_default_config(self):
        """测试获取默认配置"""
        manager = ConfigManager()
        config = manager.get_default_config()

        assert config.input_source == ""
        assert config.use_gpu == True
        assert config.vad_sensitivity == 0.5
        assert config.sample_rate == 16000
        assert config.output_format == "text"

    def test_parse_cli_overrides_without_explicit_args_returns_empty_dict(self):
        """测试未显式传参时，不生成任何CLI覆盖字段"""
        manager = ConfigManager()
        cli_dict = manager.parse_arguments_to_dict([])
        assert cli_dict == {}

    def test_cli_overrides_without_vad_args_should_not_include_vad_fields(self):
        """测试未显式传入VAD参数时，不生成VAD覆盖字段"""
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            manager = ConfigManager()
            cli_dict = manager.parse_arguments_to_dict([
                "--model-path", str(temp_model),
                "--input-source", "microphone"
            ])

            assert cli_dict["model_path"] == str(temp_model)
            assert cli_dict["input_source"] == "microphone"
            assert "vad_threshold" not in cli_dict
            assert "vad_window_size" not in cli_dict
        finally:
            temp_model.unlink(missing_ok=True)

    def test_cli_overrides_with_vad_args_should_include_vad_fields(self):
        """测试显式传入VAD参数时，应生成VAD flat覆盖字段"""
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            manager = ConfigManager()
            cli_dict = manager.parse_arguments_to_dict([
                "--model-path", str(temp_model),
                "--input-source", "microphone",
                "--vad-sensitivity", "0.8",
                "--vad-window-size", "0.256"
            ])

            assert cli_dict["vad_threshold"] == 0.8
            assert cli_dict["vad_window_size"] == 0.256
        finally:
            temp_model.unlink(missing_ok=True)

    def test_cli_overrides_with_subtitle_stream_args_should_include_fields(self):
        """测试显式传入字幕流参数时，应生成对应flat覆盖字段"""
        manager = ConfigManager()
        cli_dict = manager.parse_arguments_to_dict([
            "--stream-merge-target-duration", "11.0",
            "--stream-long-segment-threshold", "6.5",
            "--stream-merge-max-gap", "0.35",
            "--max-subtitle-duration", "4.2",
        ])

        assert cli_dict["stream_merge_target_duration"] == 11.0
        assert cli_dict["stream_long_segment_threshold"] == 6.5
        assert cli_dict["stream_merge_max_gap"] == 0.35
        assert cli_dict["max_subtitle_duration"] == 4.2


class TestAudioDevice:
    """AudioDevice类测试"""

    def test_audio_device_str(self):
        """测试音频设备字符串表示"""
        device = AudioDevice(
            id=0,
            name="内置麦克风",
            channels=2,
            sample_rate=44100,
            is_input=True,
            is_default=True
        )

        str_repr = str(device)
        assert "ID:0" in str_repr
        assert "内置麦克风" in str_repr
        assert "输入" in str_repr
        assert "2声道" in str_repr
        assert "44100Hz" in str_repr
        assert "[默认]" in str_repr


if __name__ == "__main__":
    # Run simple tests
    print("Running configuration management module tests...")

    # Create temporary model file
    temp_model = Path("test_model.onnx")
    temp_model.touch()

    try:
        # Test configuration manager
        manager = ConfigManager()
        print("+ ConfigManager created successfully")

        # Test argument parsing
        config = manager.parse_arguments([
            "--model-path", str(temp_model),
            "--input-source", "microphone",
            "--vad-sensitivity", "0.7"
        ])
        print("+ Argument parsing successful")

        # Print configuration
        print("\nConfiguration info:")
        manager.print_config(config)

        # Test audio device
        device = AudioDevice(0, "Test Device", 2, 16000, True, True)
        print(f"\n+ Audio device: {device}")

        print("\nAll tests passed!")

    finally:
        temp_model.unlink(missing_ok=True)
