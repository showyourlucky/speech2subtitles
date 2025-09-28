"""
Audio module tests

Test audio capture, device management, and audio processing
"""

import sys
import os
import pytest
import time
import numpy as np
from unittest.mock import patch, MagicMock, call

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from audio.models import (
    AudioDevice, AudioConfig, AudioChunk, AudioStreamStatus,
    AudioSourceType, AudioFormat, AudioCaptureError,
    DeviceNotFoundError, StreamError, ConfigurationError
)
from audio.capture import AudioCapture, SystemAudioCapture, MicrophoneCapture


class TestAudioDevice:
    """AudioDevice class tests"""

    def test_audio_device_creation(self):
        """Test audio device creation"""
        device = AudioDevice(
            index=0,
            name="Test Microphone",
            max_input_channels=2,
            max_output_channels=0,
            default_sample_rate=44100.0,
            is_default_input=True
        )

        assert device.index == 0
        assert device.name == "Test Microphone"
        assert device.max_input_channels == 2
        assert device.is_input_device == True
        assert device.is_output_device == False
        assert device.is_default_input == True

    def test_device_capabilities(self):
        """Test device capability detection"""
        # Input-only device
        input_device = AudioDevice(0, "Mic", 1, 0, 44100.0)
        assert input_device.is_input_device == True
        assert input_device.is_output_device == False

        # Output-only device
        output_device = AudioDevice(1, "Speakers", 0, 2, 44100.0)
        assert output_device.is_input_device == False
        assert output_device.is_output_device == True

        # Full-duplex device
        duplex_device = AudioDevice(2, "USB Headset", 1, 2, 44100.0)
        assert duplex_device.is_input_device == True
        assert duplex_device.is_output_device == True


class TestAudioConfig:
    """AudioConfig class tests"""

    def test_config_creation(self):
        """Test audio config creation"""
        config = AudioConfig(
            device_index=0,
            sample_rate=16000,
            channels=1,
            chunk_size=1024
        )

        assert config.device_index == 0
        assert config.sample_rate == 16000
        assert config.channels == 1
        assert config.chunk_size == 1024

    def test_config_validation(self):
        """Test config validation"""
        # Valid config
        valid_config = AudioConfig(sample_rate=16000, channels=1, chunk_size=1024)
        assert valid_config.validate() == True

        # Invalid sample rate
        invalid_sr = AudioConfig(sample_rate=-1, channels=1, chunk_size=1024)
        assert invalid_sr.validate() == False

        # Invalid channels
        invalid_ch = AudioConfig(sample_rate=16000, channels=0, chunk_size=1024)
        assert invalid_ch.validate() == False

        # Invalid chunk size
        invalid_chunk = AudioConfig(sample_rate=16000, channels=1, chunk_size=-1)
        assert invalid_chunk.validate() == False

    def test_bytes_per_sample(self):
        """Test bytes per sample calculation"""
        config_16 = AudioConfig(format_type=AudioFormat.PCM_16_44100)
        assert config_16.bytes_per_sample == 2

        config_32 = AudioConfig(format_type=AudioFormat.PCM_32_44100)
        assert config_32.bytes_per_sample == 4


class TestAudioChunk:
    """AudioChunk class tests"""

    def test_chunk_creation(self):
        """Test audio chunk creation"""
        data = np.array([1, 2, 3, 4, 5], dtype=np.int16)
        timestamp = time.time()

        chunk = AudioChunk(
            data=data,
            timestamp=timestamp,
            sample_rate=16000,
            channels=1,
            duration_ms=5.0
        )

        assert np.array_equal(chunk.data, data)
        assert chunk.timestamp == timestamp
        assert chunk.sample_rate == 16000
        assert chunk.channels == 1
        assert chunk.length_samples == 5

    def test_mono_conversion(self):
        """Test stereo to mono conversion"""
        # Create stereo data
        stereo_data = np.array([1, 2, 3, 4, 5, 6], dtype=np.int16)  # L,R,L,R,L,R

        stereo_chunk = AudioChunk(
            data=stereo_data,
            timestamp=time.time(),
            sample_rate=16000,
            channels=2,
            duration_ms=10.0
        )

        mono_chunk = stereo_chunk.to_mono()

        assert mono_chunk.channels == 1
        assert len(mono_chunk.data) == 3  # 6 samples / 2 channels = 3 mono samples
        # Check that it averages the channels: (1+2)/2=1.5, (3+4)/2=3.5, (5+6)/2=5.5
        expected = np.array([1.5, 3.5, 5.5])
        np.testing.assert_array_equal(mono_chunk.data, expected)

    def test_normalization(self):
        """Test audio normalization"""
        # Test 16-bit normalization
        int16_data = np.array([16384, -16384, 32767, -32768], dtype=np.int16)
        chunk = AudioChunk(
            data=int16_data,
            timestamp=time.time(),
            sample_rate=16000,
            channels=1,
            duration_ms=10.0
        )

        normalized = chunk.normalize()
        assert normalized.data.dtype == np.float32
        assert normalized.data.max() <= 1.0
        assert normalized.data.min() >= -1.0

        # Test that already normalized data remains unchanged
        float_data = np.array([0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        float_chunk = AudioChunk(
            data=float_data,
            timestamp=time.time(),
            sample_rate=16000,
            channels=1,
            duration_ms=10.0
        )

        normalized_float = float_chunk.normalize()
        np.testing.assert_array_equal(normalized_float.data, float_data)


class TestAudioStreamStatus:
    """AudioStreamStatus class tests"""

    def test_status_creation(self):
        """Test stream status creation"""
        status = AudioStreamStatus(
            is_active=True,
            is_stopped=False,
            input_latency=0.02,
            output_latency=0.03,
            sample_rate=44100.0,
            cpu_load=0.15
        )

        assert status.is_active == True
        assert status.total_latency == 0.05
        assert status.is_healthy == True  # Low latency and CPU load

    def test_health_check(self):
        """Test stream health assessment"""
        # Healthy stream
        healthy = AudioStreamStatus(
            is_active=True,
            is_stopped=False,
            input_latency=0.02,
            output_latency=0.03,
            sample_rate=44100.0,
            cpu_load=0.15
        )
        assert healthy.is_healthy == True

        # High latency
        high_latency = AudioStreamStatus(
            is_active=True,
            is_stopped=False,
            input_latency=0.08,
            output_latency=0.08,
            sample_rate=44100.0,
            cpu_load=0.15
        )
        assert high_latency.is_healthy == False

        # High CPU load
        high_cpu = AudioStreamStatus(
            is_active=True,
            is_stopped=False,
            input_latency=0.02,
            output_latency=0.03,
            sample_rate=44100.0,
            cpu_load=0.95
        )
        assert high_cpu.is_healthy == False


@patch('audio.capture.pyaudio')
class TestAudioCapture:
    """AudioCapture class tests"""

    def test_audio_capture_init(self, mock_pyaudio):
        """Test AudioCapture initialization"""
        config = AudioConfig(sample_rate=16000, channels=1, chunk_size=1024)

        # Test with PyAudio available
        audio_capture = AudioCapture(config)
        assert audio_capture.config == config
        assert audio_capture.is_running == False

    def test_audio_capture_init_no_pyaudio(self, mock_pyaudio):
        """Test AudioCapture initialization without PyAudio"""
        # Simulate PyAudio not available
        with patch('audio.capture.PYAUDIO_AVAILABLE', False):
            config = AudioConfig()
            with pytest.raises(ConfigurationError):
                AudioCapture(config)

    def test_invalid_config(self, mock_pyaudio):
        """Test with invalid configuration"""
        invalid_config = AudioConfig(sample_rate=-1)  # Invalid
        with pytest.raises(ConfigurationError):
            AudioCapture(invalid_config)

    def test_device_listing(self, mock_pyaudio):
        """Test device listing"""
        # Mock PyAudio instance
        mock_audio_instance = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_audio_instance

        # Mock device information
        mock_audio_instance.get_device_count.return_value = 2
        mock_audio_instance.get_default_input_device_info.return_value = {'index': 0}
        mock_audio_instance.get_default_output_device_info.return_value = {'index': 1}

        # Mock device info calls
        def mock_get_device_info(index):
            devices_info = {
                0: {
                    'name': 'Test Microphone',
                    'maxInputChannels': 2,
                    'maxOutputChannels': 0,
                    'defaultSampleRate': 44100.0
                },
                1: {
                    'name': 'Test Speakers',
                    'maxInputChannels': 0,
                    'maxOutputChannels': 2,
                    'defaultSampleRate': 44100.0
                }
            }
            return devices_info[index]

        mock_audio_instance.get_device_info_by_index.side_effect = mock_get_device_info

        # Test device listing
        devices = AudioCapture.list_devices()

        assert len(devices) == 2
        assert devices[0].name == "Test Microphone"
        assert devices[0].is_input_device == True
        assert devices[1].name == "Test Speakers"
        assert devices[1].is_output_device == True

    def test_context_manager(self, mock_pyaudio):
        """Test context manager usage"""
        config = AudioConfig()

        # Mock PyAudio and stream
        mock_audio_instance = MagicMock()
        mock_stream = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_audio_instance
        mock_audio_instance.open.return_value = mock_stream
        mock_audio_instance.get_default_input_device_info.return_value = {
            'index': 0, 'name': 'Default'
        }

        with AudioCapture(config) as capture:
            assert capture.is_running == True

        # Should be stopped after exiting context
        assert capture.is_running == False


if __name__ == "__main__":
    # Run simple tests
    print("Running audio module tests...")

    try:
        # Test models
        print("+ Testing AudioDevice...")
        device = AudioDevice(0, "Test Device", 1, 0, 44100.0)
        print(f"  Created: {device}")

        print("+ Testing AudioConfig...")
        config = AudioConfig(sample_rate=16000, channels=1)
        print(f"  Valid config: {config.validate()}")

        print("+ Testing AudioChunk...")
        data = np.array([1, 2, 3, 4], dtype=np.int16)
        chunk = AudioChunk(data, time.time(), 16000, 1, 4.0)
        print(f"  Chunk length: {chunk.length_samples} samples")

        # Test mono conversion
        stereo_data = np.array([1, 2, 3, 4], dtype=np.int16)
        stereo_chunk = AudioChunk(stereo_data, time.time(), 16000, 2, 4.0)
        mono_chunk = stereo_chunk.to_mono()
        print(f"  Stereo->Mono: {stereo_chunk.channels} -> {mono_chunk.channels} channels")

        # Test normalization
        normalized = chunk.normalize()
        print(f"  Normalized type: {normalized.data.dtype}")

        print("+ Testing AudioStreamStatus...")
        status = AudioStreamStatus(True, False, 0.02, 0.03, 44100.0, 0.15)
        print(f"  Healthy status: {status.is_healthy}")

        print("\nBasic tests passed!")

        # Try to test device listing (if PyAudio available)
        try:
            devices = AudioCapture.list_devices()
            print(f"\nFound {len(devices)} audio device(s)")
            for device in devices[:3]:  # Show first 3
                print(f"  {device}")
        except Exception as e:
            print(f"\nDevice listing test skipped: {e}")

        print("\nAll tests completed!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()