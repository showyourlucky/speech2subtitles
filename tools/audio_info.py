#!/usr/bin/env python3
"""
Audio Information Tool

Display audio devices and test audio capture functionality
"""

import sys
import os
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from audio import (
    AudioCapture, SystemAudioCapture, MicrophoneCapture,
    AudioConfig, AudioSourceType, create_audio_capture
)


def print_devices():
    """Print all available audio devices"""
    print("=" * 60)
    print("Available Audio Devices")
    print("=" * 60)

    try:
        devices = AudioCapture.list_devices()

        if not devices:
            print("No audio devices found")
            return

        print(f"Found {len(devices)} audio device(s):")
        print()

        for device in devices:
            status_info = []

            if device.is_default_input:
                status_info.append("DEFAULT INPUT")
            if device.is_default_output:
                status_info.append("DEFAULT OUTPUT")

            status = f" ({', '.join(status_info)})" if status_info else ""

            print(f"[{device.index:2d}] {device.name}{status}")
            print(f"     Input channels: {device.max_input_channels}")
            print(f"     Output channels: {device.max_output_channels}")
            print(f"     Sample rate: {device.default_sample_rate} Hz")
            print(f"     Input capable: {device.is_input_device}")
            print()

    except Exception as e:
        print(f"Error listing devices: {e}")


def test_microphone_capture():
    """Test microphone capture"""
    print("=" * 60)
    print("Microphone Capture Test")
    print("=" * 60)

    try:
        # Find default microphone
        mic_device = MicrophoneCapture.find_microphone_device()
        if not mic_device:
            print("No microphone device found")
            return

        print(f"Using microphone: {mic_device.name}")

        # Create configuration
        config = AudioConfig(
            device_index=mic_device.index,
            sample_rate=16000,
            channels=1,
            chunk_size=1024
        )

        print(f"Configuration: {config.sample_rate}Hz, {config.channels} channel(s)")
        print("Starting 5-second capture test...")

        # Test capture
        with MicrophoneCapture(config) as capture:
            start_time = time.time()
            chunk_count = 0

            while time.time() - start_time < 5.0:
                chunk = capture.get_audio_chunk(timeout=1.0)
                if chunk:
                    chunk_count += 1
                    # Print status every second
                    if chunk_count % 16 == 0:  # ~16 chunks per second at 1024 samples/16kHz
                        elapsed = time.time() - start_time
                        status = capture.get_stream_status()
                        print(f"[{elapsed:.1f}s] Chunks: {chunk_count}, "
                              f"Latency: {status.total_latency*1000:.1f}ms" if status else "")

            print(f"Capture completed. Total chunks: {chunk_count}")

            # Show final status
            status = capture.get_stream_status()
            if status:
                print(f"Final status:")
                print(f"  Active: {status.is_active}")
                print(f"  Healthy: {status.is_healthy}")
                print(f"  CPU Load: {status.cpu_load:.2f}")
                print(f"  Total Latency: {status.total_latency*1000:.1f}ms")

    except Exception as e:
        print(f"Microphone test failed: {e}")
        import traceback
        traceback.print_exc()


def test_system_audio_capture():
    """Test system audio capture"""
    print("=" * 60)
    print("System Audio Capture Test")
    print("=" * 60)

    try:
        # Find system audio device
        sys_device = SystemAudioCapture.find_system_audio_device()
        if not sys_device:
            print("No system audio device found")
            print("Note: On Windows, you may need to enable 'Stereo Mix' in recording devices")
            return

        print(f"Using system audio device: {sys_device.name}")

        # Create configuration
        config = AudioConfig(
            device_index=sys_device.index,
            sample_rate=16000,
            channels=1,
            chunk_size=1024
        )

        print(f"Configuration: {config.sample_rate}Hz, {config.channels} channel(s)")
        print("Starting 3-second system audio test...")
        print("(Play some audio to see capture data)")

        # Test capture
        with SystemAudioCapture(config) as capture:
            start_time = time.time()
            chunk_count = 0
            max_amplitude = 0

            while time.time() - start_time < 3.0:
                chunk = capture.get_audio_chunk(timeout=1.0)
                if chunk:
                    chunk_count += 1
                    # Track maximum amplitude
                    chunk_max = abs(chunk.data).max()
                    if chunk_max > max_amplitude:
                        max_amplitude = chunk_max

                    # Print status every second
                    if chunk_count % 16 == 0:
                        elapsed = time.time() - start_time
                        print(f"[{elapsed:.1f}s] Chunks: {chunk_count}, Max amplitude: {max_amplitude}")

            print(f"System audio test completed. Total chunks: {chunk_count}")
            print(f"Maximum amplitude detected: {max_amplitude}")

    except Exception as e:
        print(f"System audio test failed: {e}")
        import traceback
        traceback.print_exc()


def test_audio_processing():
    """Test audio processing features"""
    print("=" * 60)
    print("Audio Processing Test")
    print("=" * 60)

    try:
        # Create a sample audio chunk for testing
        import numpy as np

        # Generate test audio data (sine wave)
        sample_rate = 16000
        duration = 1.0  # 1 second
        frequency = 440  # A4 note
        samples = int(sample_rate * duration)

        # Generate stereo sine wave
        t = np.linspace(0, duration, samples, False)
        sine_wave = np.sin(2 * np.pi * frequency * t)
        stereo_data = np.column_stack([sine_wave, sine_wave * 0.5]).flatten()
        stereo_data = (stereo_data * 32767).astype(np.int16)

        from audio.models import AudioChunk

        chunk = AudioChunk(
            data=stereo_data,
            timestamp=time.time(),
            sample_rate=sample_rate,
            channels=2,
            duration_ms=duration * 1000
        )

        print(f"Original chunk: {chunk.channels} channels, {chunk.length_samples} samples")
        print(f"Duration: {chunk.duration_ms:.1f}ms")

        # Test mono conversion
        mono_chunk = chunk.to_mono()
        print(f"Mono chunk: {mono_chunk.channels} channels, {mono_chunk.length_samples} samples")

        # Test normalization
        normalized_chunk = chunk.normalize()
        print(f"Normalized data type: {normalized_chunk.data.dtype}")
        print(f"Data range: [{normalized_chunk.data.min():.3f}, {normalized_chunk.data.max():.3f}]")

        print("Audio processing tests completed successfully")

    except Exception as e:
        print(f"Audio processing test failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    print("=" * 60)
    print("Audio Information Tool")
    print("=" * 60)

    # Check PyAudio availability
    try:
        import pyaudio
        print("[+] PyAudio: Available")
    except ImportError:
        print("[-] PyAudio: Not available")
        print("    Install with: pip install PyAudio")
        return 1

    print("[+] Numpy: Available")
    print()

    # Print device information
    print_devices()

    # Test audio processing
    test_audio_processing()

    # Test microphone capture
    test_microphone_capture()

    # Test system audio capture
    test_system_audio_capture()

    print("=" * 60)
    print("Audio tests completed")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())