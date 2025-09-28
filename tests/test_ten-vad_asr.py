import sherpa_onnx
import soundfile as sf

def create_vad_asr_pipeline():
    """创建VAD+ASR流水线"""
    
    # 1. 配置TEN VAD
    vad_config = sherpa_onnx.VadModelConfig()
    vad_config.silero_vad = sherpa_onnx.SileroVadModelConfig(
        model="./ten-vad.onnx",
        threshold=0.5,
        min_silence_duration=0.5,
        min_speech_duration=0.25,
        window_size=512,
    )
    
    vad_full_config = sherpa_onnx.VadConfig(
        model=vad_config,
        sample_rate=16000,
        num_threads=1,
        provider="cpu",
    )
    
    vad = sherpa_onnx.VoiceActivityDetector(vad_full_config)
    
    # 2. 配置ASR模型 (以Whisper为例)
    # 您需要下载相应的ASR模型
    recognizer_config = sherpa_onnx.OfflineRecognizerConfig(
        feat_config=sherpa_onnx.FeatureExtractorConfig(
            sampling_rate=16000,
            feature_dim=80,
        ),
        model_config=sherpa_onnx.OfflineModelConfig(
            whisper=sherpa_onnx.OfflineWhisperModelConfig(
                encoder="whisper-tiny-encoder.onnx",
                decoder="whisper-tiny-decoder.onnx",
                language="zh",  # 或 "en"
                task="transcribe",
            ),
            tokens="whisper-tiny-tokens.txt",
            num_threads=4,
            provider="cpu",
        ),
    )
    
    recognizer = sherpa_onnx.OfflineRecognizer(recognizer_config)
    
    return vad, recognizer

def transcribe_with_vad(audio_file):
    """使用VAD预处理后进行语音识别"""
    vad, recognizer = create_vad_asr_pipeline()
    
    # 读取音频
    audio, sample_rate = sf.read(audio_file)
    if sample_rate != 16000:
        import resampy
        audio = resampy.resample(audio, sample_rate, 16000)
    
    # 使用VAD分割语音
    window_size = int(0.032 * 16000)
    speech_segments = []
    current_segment = []
    
    for i in range(0, len(audio), window_size):
        chunk = audio[i:i+window_size]
        if len(chunk) < window_size:
            break
            
        is_speech = vad.accept_waveform(chunk.astype('float32'))
        
        if is_speech:
            current_segment.extend(chunk)
        else:
            if current_segment:
                speech_segments.append(np.array(current_segment))
                current_segment = []
    
    # 对每个语音片段进行识别
    results = []
    for i, segment in enumerate(speech_segments):
        if len(segment) > 0:
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, segment)
            recognizer.decode_stream(stream)
            result = recognizer.get_result(stream)
            
            if result.text.strip():
                results.append({
                    'segment': i+1,
                    'text': result.text.strip()
                })
    
    return results

# 使用示例
if __name__ == "__main__":
    audio_file = "your_audio_file.wav"
    transcripts = transcribe_with_vad(audio_file)
    
    for result in transcripts:
        print(f"片段 {result['segment']}: {result['text']}")
