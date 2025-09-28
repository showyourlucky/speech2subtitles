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
            config = Config(
                model_path=str(temp_model),
                input_source="microphone"
            )
            # 如果没有抛出异常，说明配置有效
            assert config.model_path == str(temp_model)
            assert config.input_source == "microphone"
        finally:
            # 清理临时文件
            temp_model.unlink(missing_ok=True)

    def test_invalid_model_path(self):
        """测试无效模型路径"""
        with pytest.raises(ValueError, match="模型文件不存在"):
            Config(
                model_path="nonexistent.onnx",
                input_source="microphone"
            )

    def test_invalid_input_source(self):
        """测试无效输入源"""
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            with pytest.raises(ValueError, match="不支持的输入源"):
                Config(
                    model_path=str(temp_model),
                    input_source="invalid_source"
                )
        finally:
            temp_model.unlink(missing_ok=True)

    def test_invalid_vad_sensitivity(self):
        """测试无效VAD敏感度"""
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            with pytest.raises(ValueError, match="VAD敏感度必须在0.0-1.0之间"):
                Config(
                    model_path=str(temp_model),
                    input_source="microphone",
                    vad_sensitivity=1.5
                )
        finally:
            temp_model.unlink(missing_ok=True)


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
                "--no-timestamp"
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
        finally:
            temp_model.unlink(missing_ok=True)

    def test_get_default_config(self):
        """测试获取默认配置"""
        manager = ConfigManager()
        config = manager.get_default_config()

        assert config.input_source == "microphone"
        assert config.use_gpu == True
        assert config.vad_sensitivity == 0.5
        assert config.sample_rate == 16000
        assert config.output_format == "text"


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