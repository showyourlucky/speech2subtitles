import sounddevice as sd
import sherpa_onnx
import numpy as np
import threading
import queue

class RealTimeVAD:
    def __init__(self, model_path="silero_vad_v5.onnx"):
        # 配置VAD
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = model_path
        config.silero_vad.min_silence_duration = 0.25
        config.silero_vad.min_speech_duration = 0.25
        config.silero_vad.threshold = 0.5
        config.sample_rate = 16000
        
        self.vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=3)
        self.sample_rate = 16000
        self.window_size = config.silero_vad.window_size
        self.audio_queue = queue.Queue()
        self.is_running = False
        
    def audio_callback(self, indata, frames, time, status):
        """音频输入回调函数"""
        if status:
            print(f"音频输入状态: {status}")
        self.audio_queue.put(indata[:, 0].copy())
    
    def process_audio(self):
        """处理音频数据"""
        buffer = np.array([])
        
        while self.is_running:
            try:
                # 获取音频数据
                audio_chunk = self.audio_queue.get(timeout=0.1)
                buffer = np.concatenate([buffer, audio_chunk])
                
                # 处理足够长度的音频
                while len(buffer) >= self.window_size:
                    self.vad.accept_waveform(buffer[:self.window_size])
                    buffer = buffer[self.window_size:]
                    
                    # 检查语音活动
                    if self.vad.is_speech_detected():
                        while not self.vad.empty():
                            segment = self.vad.front
                            start_time = segment.start / self.sample_rate
                            duration = len(segment.samples) / self.sample_rate
                            print(f"🎤 检测到语音: {start_time:.2f}s - {start_time+duration:.2f}s")
                            self.vad.pop()
                            
            except queue.Empty:
                continue
    
    def start(self):
        """开始实时VAD检测"""
        print("开始实时语音活动检测... (按Ctrl+C停止)")
        self.is_running = True
        
        # 启动音频处理线程
        process_thread = threading.Thread(target=self.process_audio)
        process_thread.start()
        
        # 启动音频输入流
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                callback=self.audio_callback
            ):
                process_thread.join()
        except KeyboardInterrupt:
            print("\n停止检测")
        finally:
            self.is_running = False
            process_thread.join()

# 使用示例
if __name__ == "__main__":
    vad_detector = RealTimeVAD("models\silero_vad\silero_vad.onnx")
    vad_detector.start()
