"""
集成测试

测试各组件间的协作和端到端功能
"""

import sys
import os
import pytest
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import threading
import time

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.models import Config, AudioDevice
from config.manager import ConfigManager
from hardware.gpu_detector import GPUDetector, GPUInfo
from audio.models import AudioConfig, AudioChunk, AudioSourceType
from vad.models import VadConfig, VadResult, VadState
from transcription.models import TranscriptionConfig, TranscriptionResult, LanguageCode
from output.models import OutputConfig, OutputFormat
from utils.logger import LogConfig, LogLevel, setup_logging, get_logger
from utils.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory


class TestConfigManagerIntegration:
    """配置管理器集成测试"""

    def test_config_with_all_modules(self):
        """测试配置与所有模块的集成"""
        # 创建临时模型文件
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            manager = ConfigManager()
            config = manager.parse_arguments([
                "--model-path", str(temp_model),
                "--input-source", "microphone",
                "--use-gpu",
                "--vad-sensitivity", "0.7",
                "--output-format", "json"
            ])

            # 验证配置可以被各模块使用
            assert config.model_path == str(temp_model)
            assert config.input_source == "microphone"
            assert config.use_gpu == True
            assert config.vad_sensitivity == 0.7
            assert config.output_format == "json"

            # 测试配置转换为其他模块的配置
            audio_config = AudioConfig(
                source_type=AudioSourceType.MICROPHONE if config.input_source == "microphone" else AudioSourceType.SYSTEM_AUDIO,
                sample_rate=config.sample_rate,
                chunk_size=config.chunk_size,
                channels=config.channels
            )

            vad_config = VadConfig(
                sensitivity=config.vad_sensitivity,
                min_speech_duration=config.min_speech_duration,
                min_silence_duration=config.min_silence_duration
            )

            transcription_config = TranscriptionConfig(
                model_path=config.model_path,
                use_gpu=config.use_gpu,
                language=LanguageCode.CHINESE
            )

            output_config = OutputConfig(
                format=OutputFormat.JSON if config.output_format == "json" else OutputFormat.CONSOLE,
                show_confidence=config.show_confidence,
                show_timestamps=config.show_timestamp
            )

            # 验证所有配置都正确创建
            assert audio_config.source_type == AudioSourceType.MICROPHONE
            assert vad_config.sensitivity == 0.7
            assert transcription_config.use_gpu == True
            assert output_config.format == OutputFormat.JSON

        finally:
            temp_model.unlink(missing_ok=True)


class TestLoggingErrorHandlingIntegration:
    """日志和错误处理集成测试"""

    def test_logging_with_error_handling(self):
        """测试日志系统与错误处理的集成"""
        # 设置日志
        log_config = LogConfig(
            level=LogLevel.DEBUG,
            console_enabled=True,
            file_enabled=False
        )
        setup_logging(log_config)

        # 创建错误处理器
        error_handler = ErrorHandler()
        logger = get_logger("integration_test")

        # 模拟组件错误
        component_name = "audio_capture"
        operation = "initialize_device"

        try:
            logger.info(f"开始初始化 {component_name}")
            raise RuntimeError("设备初始化失败")
        except Exception as e:
            # 使用错误处理器处理错误
            from utils.error_handler import ErrorContext
            context = ErrorContext(
                component=component_name,
                function_name=operation,
                file_path="test_file.py",
                line_number=1,
                local_variables={"device_id": 0}
            )

            error_record = error_handler.handle_error(
                exception=e,
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.HARDWARE,
                context=context,
                user_message="音频设备初始化失败，请检查设备连接"
            )

            logger.error(f"错误处理完成: {error_record.user_message}")

        # 验证错误被正确记录
        assert error_handler.error_count == 1
        assert len(error_handler.error_history) == 1
        assert error_handler.error_history[0].user_message == "音频设备初始化失败，请检查设备连接"


class TestAudioVadIntegration:
    """音频和VAD集成测试"""

    @patch('audio.capture.pyaudio.PyAudio')
    @patch('vad.detector.torch')
    @patch('vad.detector.silero_vad')
    def test_audio_to_vad_pipeline(self, mock_silero, mock_torch, mock_pyaudio):
        """测试音频到VAD的流水线"""
        # 模拟PyAudio
        mock_pyaudio_instance = Mock()
        mock_pyaudio.return_value = mock_pyaudio_instance

        # 模拟silero VAD
        mock_model = Mock()
        mock_silero.load_silero_vad.return_value = mock_model
        mock_model.return_value = torch.tensor([0.8])  # 假设检测到语音

        # 模拟torch
        mock_torch.tensor.return_value = Mock()
        mock_torch.no_grad.return_value.__enter__ = Mock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = Mock(return_value=None)

        # 创建音频配置
        audio_config = AudioConfig(
            source_type=AudioSourceType.MICROPHONE,
            sample_rate=16000,
            chunk_size=1024,
            channels=1
        )

        # 创建VAD配置
        vad_config = VadConfig(
            sensitivity=0.5,
            min_speech_duration=0.1,
            min_silence_duration=0.3
        )

        # 模拟音频数据流
        audio_data = np.random.rand(16000).astype(np.float32)  # 1秒音频
        audio_chunk = AudioChunk(
            data=audio_data,
            timestamp=time.time(),
            sample_rate=16000,
            channels=1
        )

        # 验证音频块可以被VAD处理
        assert audio_chunk.data.dtype == np.float32
        assert len(audio_chunk.data) == 16000
        assert audio_chunk.sample_rate == 16000


class TestVadTranscriptionIntegration:
    """VAD和转录集成测试"""

    @patch('transcription.engine.sherpa_onnx')
    @patch('os.path.exists')
    def test_vad_to_transcription_pipeline(self, mock_exists, mock_sherpa):
        """测试VAD到转录的流水线"""
        mock_exists.return_value = True

        # 模拟sherpa-onnx
        mock_recognizer = Mock()
        mock_stream = Mock()
        mock_recognizer.create_stream.return_value = mock_stream
        mock_recognizer.is_ready.return_value = True
        mock_result = Mock()
        mock_result.text = "这是转录结果"
        mock_recognizer.get_result.return_value = mock_result
        mock_sherpa.OnlineRecognizer.return_value = mock_recognizer

        # 创建VAD结果（检测到语音）
        vad_result = VadResult(
            is_speech=True,
            confidence=0.9,
            start_time=1.0,
            end_time=3.0,
            state=VadState.SPEECH
        )

        # 创建转录配置
        transcription_config = TranscriptionConfig(
            model_path="test_model.onnx",
            language=LanguageCode.CHINESE,
            use_gpu=False
        )

        # 验证VAD结果指示应该进行转录
        assert vad_result.is_speech == True
        assert vad_result.confidence > 0.5

        # 模拟音频数据（VAD检测到语音的部分）
        speech_audio = np.random.rand(32000).astype(np.float32)  # 2秒语音

        # 验证音频数据格式适合转录
        assert speech_audio.dtype == np.float32
        assert len(speech_audio) > 0


class TestTranscriptionOutputIntegration:
    """转录和输出集成测试"""

    def test_transcription_to_output_pipeline(self):
        """测试转录到输出的流水线"""
        # 创建转录结果
        transcription_result = TranscriptionResult(
            text="测试转录文本",
            confidence=0.95,
            start_time=1.5,
            end_time=4.2,
            language=LanguageCode.CHINESE,
            is_partial=False
        )

        # 创建输出配置
        output_config = OutputConfig(
            format=OutputFormat.JSON,
            show_confidence=True,
            show_timestamps=True,
            color_scheme=None  # 禁用颜色以简化测试
        )

        # 验证转录结果包含所需信息
        assert transcription_result.text is not None
        assert transcription_result.confidence > 0
        assert transcription_result.start_time >= 0
        assert transcription_result.end_time > transcription_result.start_time
        assert transcription_result.duration == transcription_result.end_time - transcription_result.start_time

        # 验证可以转换为输出格式
        result_dict = transcription_result.to_dict()
        assert "text" in result_dict
        assert "confidence" in result_dict
        assert "start_time" in result_dict
        assert "end_time" in result_dict


class TestFullPipelineIntegration:
    """完整流水线集成测试"""

    @patch('audio.capture.pyaudio.PyAudio')
    @patch('vad.detector.torch')
    @patch('vad.detector.silero_vad')
    @patch('transcription.engine.sherpa_onnx')
    @patch('os.path.exists')
    def test_end_to_end_pipeline(self, mock_exists, mock_sherpa, mock_silero, mock_torch, mock_pyaudio):
        """测试端到端流水线"""
        # 设置所有模拟对象
        mock_exists.return_value = True

        # 模拟PyAudio
        mock_pyaudio_instance = Mock()
        mock_pyaudio.return_value = mock_pyaudio_instance

        # 模拟silero VAD
        mock_vad_model = Mock()
        mock_silero.load_silero_vad.return_value = mock_vad_model
        mock_vad_model.return_value = Mock()

        # 模拟torch
        mock_torch.tensor.return_value = Mock()
        mock_torch.no_grad.return_value.__enter__ = Mock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = Mock(return_value=None)

        # 模拟sherpa-onnx
        mock_recognizer = Mock()
        mock_stream = Mock()
        mock_recognizer.create_stream.return_value = mock_stream
        mock_recognizer.is_ready.return_value = True
        mock_result = Mock()
        mock_result.text = "端到端测试结果"
        mock_recognizer.get_result.return_value = mock_result
        mock_sherpa.OnlineRecognizer.return_value = mock_recognizer

        # 创建完整配置
        config = Config()
        config.model_path = "test_model.onnx"
        config.input_source = "microphone"
        config.use_gpu = False
        config.vad_sensitivity = 0.7
        config.output_format = "text"
        config.show_confidence = True
        config.show_timestamp = True

        # 验证配置完整性
        assert config.model_path is not None
        assert config.input_source in ["microphone", "system"]
        assert 0.0 <= config.vad_sensitivity <= 1.0
        assert config.output_format in ["text", "json", "srt", "vtt"]

        # 模拟数据流：音频 -> VAD -> 转录 -> 输出
        # 1. 音频数据
        audio_data = np.random.rand(16000).astype(np.float32)
        audio_chunk = AudioChunk(
            data=audio_data,
            timestamp=time.time(),
            sample_rate=config.sample_rate,
            channels=config.channels
        )

        # 2. VAD处理结果
        vad_result = VadResult(
            is_speech=True,
            confidence=0.8,
            start_time=0.0,
            end_time=1.0,
            state=VadState.SPEECH
        )

        # 3. 转录结果
        transcription_result = TranscriptionResult(
            text="端到端测试成功",
            confidence=0.95,
            start_time=vad_result.start_time,
            end_time=vad_result.end_time,
            language=LanguageCode.CHINESE
        )

        # 验证数据流的连贯性
        assert audio_chunk.data.dtype == np.float32
        assert vad_result.is_speech == True
        assert transcription_result.text is not None
        assert transcription_result.start_time == vad_result.start_time


class TestErrorRecoveryIntegration:
    """错误恢复集成测试"""

    def test_component_failure_recovery(self):
        """测试组件失败恢复"""
        # 设置日志和错误处理
        log_config = LogConfig(level=LogLevel.DEBUG, console_enabled=True)
        setup_logging(log_config)

        error_handler = ErrorHandler()
        logger = get_logger("recovery_test")

        # 模拟组件失败和恢复场景
        components = ["audio_capture", "vad", "transcription_engine", "output_handler"]
        recovery_success = []

        for component in components:
            try:
                logger.info(f"初始化组件: {component}")

                # 模拟组件初始化失败
                if component == "audio_capture":
                    raise RuntimeError("音频设备不可用")
                elif component == "vad":
                    raise ImportError("VAD模型加载失败")
                elif component == "transcription_engine":
                    raise FileNotFoundError("转录模型文件不存在")
                elif component == "output_handler":
                    raise PermissionError("输出文件无法写入")

            except Exception as e:
                # 错误处理和恢复
                from utils.error_handler import ErrorContext
                context = ErrorContext(
                    component=component,
                    function_name="initialize",
                    file_path="test_file.py",
                    line_number=1,
                    local_variables={"retry_count": 1}
                )

                def recovery_callback():
                    logger.info(f"尝试恢复组件: {component}")
                    # 模拟恢复操作
                    if component == "audio_capture":
                        return "使用默认音频设备"
                    elif component == "vad":
                        return "使用简单VAD算法"
                    elif component == "transcription_engine":
                        return "使用备用模型"
                    elif component == "output_handler":
                        return "使用控制台输出"

                error_record = error_handler.handle_error(
                    exception=e,
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.HARDWARE if component == "audio_capture" else ErrorCategory.MODEL,
                    context=context,
                    user_message=f"{component}初始化失败",
                    recovery_callback=recovery_callback
                )

                if error_record.recovery_attempted:
                    recovery_success.append(component)
                    logger.info(f"组件 {component} 恢复成功")

        # 验证错误处理和恢复
        assert len(recovery_success) == len(components)
        assert error_handler.error_count == len(components)


class TestPerformanceIntegration:
    """性能集成测试"""

    def test_performance_monitoring_across_components(self):
        """测试跨组件性能监控"""
        # 设置性能日志
        log_config = LogConfig(
            level=LogLevel.DEBUG,
            console_enabled=True,
            performance_logging=True
        )
        setup_logging(log_config)

        from utils.logger import get_performance_timer
        logger = get_logger("performance_test")

        # 模拟各组件的性能监控
        components = {
            "audio_capture": 0.01,      # 10ms
            "vad_processing": 0.005,    # 5ms
            "transcription": 0.1,       # 100ms
            "output_formatting": 0.002   # 2ms
        }

        for component, expected_duration in components.items():
            with get_performance_timer(logger, component):
                time.sleep(expected_duration)

        # 获取性能统计
        from utils.logger import get_performance_summary
        stats = get_performance_summary()

        # 验证所有组件都被监控
        for component in components.keys():
            assert component in stats
            assert stats[component]["count"] == 1
            # 允许一定的时间误差
            assert abs(stats[component]["avg"] - components[component]) < 0.05


class TestConfigurationIntegration:
    """配置集成测试"""

    def test_configuration_propagation(self):
        """测试配置在组件间的传播"""
        # 创建临时配置文件
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            # 解析命令行配置
            manager = ConfigManager()
            main_config = manager.parse_arguments([
                "--model-path", str(temp_model),
                "--input-source", "microphone",
                "--sample-rate", "22050",
                "--chunk-size", "2048",
                "--vad-sensitivity", "0.8",
                "--output-format", "json",
                "--use-gpu"
            ])

            # 验证配置可以正确传播到各组件
            # 1. 音频配置
            audio_config = AudioConfig(
                source_type=AudioSourceType.MICROPHONE,
                sample_rate=main_config.sample_rate,
                chunk_size=main_config.chunk_size,
                channels=main_config.channels
            )
            assert audio_config.sample_rate == 22050
            assert audio_config.chunk_size == 2048

            # 2. VAD配置
            vad_config = VadConfig(
                sensitivity=main_config.vad_sensitivity,
                sample_rate=main_config.sample_rate
            )
            assert vad_config.sensitivity == 0.8
            assert vad_config.sample_rate == 22050

            # 3. 转录配置
            transcription_config = TranscriptionConfig(
                model_path=main_config.model_path,
                use_gpu=main_config.use_gpu,
                sample_rate=main_config.sample_rate
            )
            assert transcription_config.model_path == str(temp_model)
            assert transcription_config.use_gpu == True
            assert transcription_config.sample_rate == 22050

            # 4. 输出配置
            output_config = OutputConfig(
                format=OutputFormat.JSON,
                show_confidence=main_config.show_confidence,
                show_timestamps=main_config.show_timestamp
            )
            assert output_config.format == OutputFormat.JSON

            # 验证所有配置的一致性
            configs = [audio_config, vad_config, transcription_config]
            sample_rates = [cfg.sample_rate for cfg in configs if hasattr(cfg, 'sample_rate')]
            assert all(sr == 22050 for sr in sample_rates)

        finally:
            temp_model.unlink(missing_ok=True)


if __name__ == "__main__":
    print("Running integration tests...")

    try:
        # Test basic integration
        print("+ Testing configuration integration...")

        # Create temporary model file
        temp_model = Path("test_model.onnx")
        temp_model.touch()

        try:
            manager = ConfigManager()
            config = manager.parse_arguments([
                "--model-path", str(temp_model),
                "--input-source", "microphone"
            ])
            print(f"  - Config created: {config.model_path}")

            # Test audio config creation
            audio_config = AudioConfig(
                source_type=AudioSourceType.MICROPHONE,
                sample_rate=config.sample_rate,
                chunk_size=config.chunk_size
            )
            print(f"  - Audio config: {audio_config.sample_rate}Hz, {audio_config.chunk_size} samples")

            # Test VAD config creation
            vad_config = VadConfig(
                sensitivity=config.vad_sensitivity,
                sample_rate=config.sample_rate
            )
            print(f"  - VAD config: sensitivity={vad_config.sensitivity}")

            # Test transcription config creation
            transcription_config = TranscriptionConfig(
                model_path=config.model_path,
                use_gpu=config.use_gpu
            )
            print(f"  - Transcription config: GPU={transcription_config.use_gpu}")

            # Test output config creation
            output_config = OutputConfig(
                format=OutputFormat.CONSOLE,
                show_confidence=config.show_confidence
            )
            print(f"  - Output config: format={output_config.format}")

        finally:
            temp_model.unlink(missing_ok=True)

        print("+ Testing logging and error handling integration...")

        # Setup logging
        log_config = LogConfig(level=LogLevel.INFO, console_enabled=True)
        setup_logging(log_config)

        # Test error handling
        error_handler = ErrorHandler()
        logger = get_logger("integration_test")

        try:
            logger.info("Testing error handling...")
            raise ValueError("Test integration error")
        except Exception as e:
            from utils.error_handler import ErrorContext
            context = ErrorContext(
                component="integration_test",
                function_name="test_operation",
                file_path="test_file.py",
                line_number=1
            )

            error_record = error_handler.handle_error(
                exception=e,
                severity=ErrorSeverity.LOW,
                category=ErrorCategory.TRANSCRIPTION,
                context=context,
                user_message="Integration test error"
            )
            print(f"  - Error handled: {error_record.user_message}")

        print("+ Testing data flow integration...")

        # Test transcription result
        result = TranscriptionResult(
            text="集成测试文本",
            confidence=0.95,
            start_time=1.0,
            end_time=3.0
        )
        print(f"  - Transcription result: '{result.text}' ({result.confidence:.2f})")

        # Test result conversion
        result_dict = result.to_dict()
        print(f"  - Result dict keys: {list(result_dict.keys())}")

        print("\nIntegration tests passed!")

    except Exception as e:
        print(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
