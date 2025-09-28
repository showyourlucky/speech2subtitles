#!/usr/bin/env python3
"""
VAD Testing Tool

Test Voice Activity Detection functionality with real audio
"""

import sys
import os
import time
import numpy as np

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vad import VoiceActivityDetector, VadConfig, VadState
from audio import MicrophoneCapture, AudioConfig


def test_vad_with_synthetic_audio():
    """Test VAD with synthetic audio data"""
    print("=" * 60)
    print("VAD Synthetic Audio Test")
    print("=" * 60)

    try:
        # Create VAD configuration
        vad_config = VadConfig(
            threshold=0.5,
            min_speech_duration_ms=250,
            min_silence_duration_ms=100,
            sample_rate=16000
        )

        print(f"VAD Config: threshold={vad_config.threshold}, "
              f"min_speech={vad_config.min_speech_duration_ms}ms")

        # Initialize VAD detector
        detector = VoiceActivityDetector(vad_config)
        print("VAD detector initialized successfully")

        # Generate test audio data
        sample_rate = 16000
        duration = 1.0  # 1 second chunks

        # Test 1: Silence
        print("\nTest 1: Silence")
        silence = np.zeros(int(sample_rate * duration), dtype=np.float32)
        result = detector.detect(silence)
        print(f"  Silence detection: speech={result.is_speech}, "
              f"confidence={result.confidence:.3f}, state={result.state.value}")

        # Test 2: Pure tone (simulated speech)
        print("\nTest 2: Pure tone (simulated speech)")
        frequency = 440  # A4 note
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = np.sin(2 * np.pi * frequency * t).astype(np.float32) * 0.5
        result = detector.detect(tone)
        print(f"  Tone detection: speech={result.is_speech}, "
              f"confidence={result.confidence:.3f}, state={result.state.value}")

        # Test 3: Random noise (simulated speech)
        print("\nTest 3: Random noise")
        noise = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.3
        result = detector.detect(noise)
        print(f"  Noise detection: speech={result.is_speech}, "
              f"confidence={result.confidence:.3f}, state={result.state.value}")

        # Test 4: Speech pattern simulation
        print("\nTest 4: Speech pattern simulation")
        # Create a pattern that looks more like speech
        envelope = np.random.randn(int(sample_rate * duration)) * 0.1
        carrier = np.sin(2 * np.pi * 200 * t + np.sin(2 * np.pi * 5 * t))
        speech_like = (envelope + carrier * 0.3).astype(np.float32)
        result = detector.detect(speech_like)
        print(f"  Speech-like detection: speech={result.is_speech}, "
              f"confidence={result.confidence:.3f}, state={result.state.value}")

        # Show statistics
        stats = detector.get_statistics()
        print(f"\nVAD Statistics:")
        print(f"  Total audio: {stats.total_audio_duration_ms:.1f}ms")
        print(f"  Speech ratio: {stats.speech_ratio:.3f}")
        print(f"  Processing RT factor: {stats.processing_real_time_factor:.3f}")

        print("\nSynthetic audio test completed successfully!")

    except Exception as e:
        print(f"Synthetic audio test failed: {e}")
        import traceback
        traceback.print_exc()


def test_vad_with_microphone():
    """Test VAD with real microphone input"""
    print("=" * 60)
    print("VAD Microphone Test")
    print("=" * 60)

    try:
        # Check dependencies
        print("Checking dependencies...")
        try:
            import torch
            print("[+] PyTorch: Available")
        except ImportError:
            print("[-] PyTorch: Not available")
            print("    Install with: pip install torch")
            return

        try:
            import silero_vad
            print("[+] silero_vad: Available")
        except ImportError:
            print("[-] silero_vad: Not available")
            print("    Install with: pip install silero-vad")
            return

        # Find microphone
        from audio import MicrophoneCapture
        mic_device = MicrophoneCapture.find_microphone_device()
        if not mic_device:
            print("No microphone device found")
            return

        print(f"Using microphone: {mic_device.name}")

        # Create configurations
        audio_config = AudioConfig(
            device_index=mic_device.index,
            sample_rate=16000,
            channels=1,
            chunk_size=512
        )

        vad_config = VadConfig(
            threshold=0.5,
            min_speech_duration_ms=250,
            min_silence_duration_ms=100,
            sample_rate=16000
        )

        # Initialize VAD
        detector = VoiceActivityDetector(vad_config)
        print("VAD detector loaded successfully")

        # Add callback to show results
        def vad_callback(result):
            if result.is_speech_start:
                print(f"[{time.time():.1f}] SPEECH START (confidence: {result.confidence:.3f})")
            elif result.is_speech_end:
                print(f"[{time.time():.1f}] SPEECH END")
            elif result.is_stable_speech:
                print(f"[{time.time():.1f}] SPEECH ACTIVE (confidence: {result.confidence:.3f})")

        detector.add_callback(vad_callback)

        print("\nStarting 10-second microphone VAD test...")
        print("Please speak into the microphone to test detection")
        print("(Watch for SPEECH START/END messages)")

        # Start audio capture and VAD
        with MicrophoneCapture(audio_config) as capture:
            start_time = time.time()
            chunk_count = 0

            while time.time() - start_time < 10.0:
                chunk = capture.get_audio_chunk(timeout=1.0)
                if chunk:
                    chunk_count += 1

                    # Convert to mono and normalize
                    audio_data = chunk.to_mono().normalize().data

                    # Run VAD detection
                    detector.detect(audio_data)

            print(f"\nMicrophone test completed. Processed {chunk_count} chunks")

            # Show final statistics
            stats = detector.get_statistics()
            segments = detector.get_completed_segments()

            print(f"\nFinal Statistics:")
            print(f"  Total audio: {stats.total_audio_duration_ms/1000:.1f}s")
            print(f"  Speech segments: {stats.speech_segments_count}")
            print(f"  Speech ratio: {stats.speech_ratio:.3f}")
            print(f"  Avg segment duration: {stats.average_segment_duration_ms:.1f}ms")

            if segments:
                print(f"\nDetected speech segments:")
                for i, segment in enumerate(segments[-5:]):  # Show last 5
                    print(f"  {i+1}: {segment.duration_ms:.1f}ms, "
                          f"confidence: {segment.average_confidence:.3f}")

    except Exception as e:
        print(f"Microphone VAD test failed: {e}")
        import traceback
        traceback.print_exc()


def test_vad_states():
    """Test VAD state machine"""
    print("=" * 60)
    print("VAD State Machine Test")
    print("=" * 60)

    try:
        vad_config = VadConfig(
            threshold=0.5,
            min_speech_duration_ms=100,  # Shorter for testing
            min_silence_duration_ms=50,
            sample_rate=16000
        )

        detector = VoiceActivityDetector(vad_config)

        # Track state changes
        states = []

        def state_callback(result):
            if result.state != VadState.SPEECH and result.state != VadState.SILENCE:
                states.append((result.state, result.timestamp, result.confidence))

        detector.add_callback(state_callback)

        # Simulate speech pattern: silence -> speech -> silence
        sample_rate = 16000
        chunk_duration = 0.1  # 100ms chunks
        chunk_samples = int(sample_rate * chunk_duration)

        print("Simulating: silence -> speech -> silence pattern")

        # 1. Silence phase
        for i in range(5):  # 500ms silence
            silence = np.zeros(chunk_samples, dtype=np.float32)
            result = detector.detect(silence)
            print(f"  Chunk {i+1}: {result.state.value} (confidence: {result.confidence:.3f})")

        # 2. Speech phase
        for i in range(10):  # 1000ms speech
            # Generate speech-like signal
            t = np.linspace(0, chunk_duration, chunk_samples, False)
            speech = np.sin(2 * np.pi * 200 * t + np.random.randn(chunk_samples) * 0.1)
            speech = speech.astype(np.float32) * 0.5

            result = detector.detect(speech)
            print(f"  Chunk {i+6}: {result.state.value} (confidence: {result.confidence:.3f})")

        # 3. Silence phase again
        for i in range(5):  # 500ms silence
            silence = np.zeros(chunk_samples, dtype=np.float32)
            result = detector.detect(silence)
            print(f"  Chunk {i+16}: {result.state.value} (confidence: {result.confidence:.3f})")

        print(f"\nState transitions detected: {len(states)}")
        for state, timestamp, confidence in states:
            print(f"  {state.value} at {timestamp:.3f} (confidence: {confidence:.3f})")

        # Show segments
        segments = detector.get_completed_segments()
        print(f"\nCompleted speech segments: {len(segments)}")
        for i, segment in enumerate(segments):
            print(f"  Segment {i+1}: {segment.duration_ms:.1f}ms, "
                  f"confidence: {segment.average_confidence:.3f}")

    except Exception as e:
        print(f"State machine test failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    print("=" * 60)
    print("VAD Testing Tool")
    print("=" * 60)

    # Test 1: Synthetic audio
    test_vad_with_synthetic_audio()

    # Test 2: State machine
    test_vad_states()

    # Test 3: Real microphone (if available)
    test_vad_with_microphone()

    print("=" * 60)
    print("All VAD tests completed")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())