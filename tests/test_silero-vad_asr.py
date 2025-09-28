import sherpa_onnx
import soundfile as sf
import numpy as np

def vad_with_asr_example():
    # 1. 配置VAD
    vad_config = sherpa_onnx.VadModelConfig()
    vad_config.silero_vad.model = "silero_vad_v5.onnx"
    vad_config.sample_rate = 16000
    vad = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=10)
    
    # 2. 配置ASR（需要下载相应的ASR模型）
    recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
        paraformer="sherpa-onnx-paraformer-zh-2024-03-09/model.int8.onnx",
        tokens="sherpa-onnx-paraformer-zh-2024-03-09/tokens.txt",
        num_threads=4,
    )
    
    # 3. 加载音频
    samples, sample_rate = sf.read("long_audio.wav", dtype="float32")
    if len(samples.shape) > 1:
        samples = samples[:, 0]  # 使用第一个声道
    
    # 4. VAD分割音频
    window_size = vad_config.silero_vad.window_size
    audio_buffer = samples.copy()
    
    while len(audio_buffer) > window_size:
        vad.accept_waveform(audio_buffer[:window_size])
        audio_buffer = audio_buffer[window_size:]
        
        # 处理检测到的语音片段
        while not vad.empty():
            segment = vad.front
            start_time = segment.start / sample_rate
            duration = len(segment.samples) / sample_rate
            
            # 对语音片段进行ASR识别
            stream = recognizer.create_stream()
            stream.accept_waveform(sample_rate, segment.samples)
            recognizer.decode_stream(stream)
            result = recognizer.get_result(stream)
            
            if result.text:
                print(f"[{start_time:.2f}s-{start_time+duration:.2f}s]: {result.text}")
            
            vad.pop()

if __name__ == "__main__":
    vad_with_asr_example()
