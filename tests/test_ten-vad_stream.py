import sherpa_onnx
import pyaudio
import numpy as np

class RealTimeTenVAD:
    def __init__(self, model_path="./ten-vad.onnx"):
        """初始化实时TEN VAD"""
        vad_config = sherpa_onnx.VadModelConfig()
        vad_config.silero_vad = sherpa_onnx.SileroVadModelConfig(
            model=model_path,
            threshold=0.5,
            min_silence_duration=0.3,
            min_speech_duration=0.2,
            window_size=512,
        )
        
        config = sherpa_onnx.VadConfig(
            model=vad_config,
            sample_rate=16000,
            num_threads=1,
            provider="cpu",
        )
        
        self.vad = sherpa_onnx.VoiceActivityDetector(config)
        self.sample_rate = 16000
        self.chunk_size = int(0.032 * self.sample_rate)  # 32ms
        
    def start_realtime_detection(self):
        """开始实时检测"""
        # 初始化PyAudio
        p = pyaudio.PyAudio()
        
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        print("开始实时语音活动检测...")
        print("按Ctrl+C停止")
        
        try:
            while True:
                # 读取音频数据
                audio_chunk = stream.read(self.chunk_size)
                audio_array = np.frombuffer(audio_chunk, dtype=np.float32)
                
                # VAD检测
                is_speech = self.vad.accept_waveform(audio_array)
                
                if is_speech:
                    print("🎤 检测到语音!")
                else:
                    print("🔇 静音或噪音")
                    
        except KeyboardInterrupt:
            print("\n停止检测")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

# 使用示例
if __name__ == "__main__":
    vad_detector = RealTimeTenVAD("./ten-vad.onnx")
    vad_detector.start_realtime_detection()
