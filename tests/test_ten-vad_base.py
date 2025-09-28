import numpy as np
import sherpa_onnx
import soundfile as sf
import os
from typing import Tuple
from pathlib import Path

def get_model_path():
    """获取模型文件路径"""
    # 获取当前脚本所在目录
    current_dir = Path(__file__).parent
    # 向上一级到项目根目录，然后进入models/ten-vad/
    model_dir = current_dir.parent / "models" / "ten_vad"
    model_path = model_dir / "ten-vad.onnx"
    
    if not model_path.exists():
        # 如果标准模型不存在，尝试量化版本
        model_path = model_dir / "ten-vad.int8.onnx"
        if not model_path.exists():
            raise FileNotFoundError(f"找不到模型文件，请确保以下任一文件存在:\n"
                                  f"  - {model_dir / 'ten-vad.onnx'}\n"
                                  f"  - {model_dir / 'ten-vad.int8.onnx'}")
    
    print(f"使用模型: {model_path}")
    return str(model_path)

def load_audio(filename: str) -> Tuple[np.ndarray, int]:
    """加载音频文件"""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"音频文件不存在: {filename}")
    
    data, sample_rate = sf.read(filename, always_2d=True, dtype="float32")
    data = data[:, 0]  # 使用第一个声道
    samples = np.ascontiguousarray(data)
    return samples, sample_rate

def basic_vad_example():
    """基本VAD检测示例"""
    try:
        print("=== Sherpa-ONNX ten-VAD 基础测试 ===\n")
        
        # 1. 获取模型路径
        model_path = get_model_path()
        
        # 2. 配置VAD模型
        print("配置VAD模型...")
        config = sherpa_onnx.VadModelConfig()
        config.ten_vad.model = model_path
        config.ten_vad.min_silence_duration = 0.1  # 最小静音持续时间（秒）
        config.ten_vad.min_speech_duration = 0.1   # 最小语音持续时间（秒）
        config.ten_vad.threshold = 0.5               # 检测阈值
        config.ten_vad.max_speech_duration = 30
        config.sample_rate = 16000
        
        print(f"  - 模型路径: {model_path}")
        print(f"  - 采样率: {config.sample_rate}Hz")
        print(f"  - 检测阈值: {config.ten_vad.threshold}")
        print(f"  - 最小语音持续时间: {config.ten_vad.min_speech_duration}s")
        print(f"  - 最小静音持续时间: {config.ten_vad.min_silence_duration}s")
        
        # 3. 创建VAD检测器
        print("\n创建VAD检测器...")
        vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=3)
        print("VAD检测器创建成功!")
        
        # 4. 准备测试音频
        print("\n准备测试音频...")
        
        audio_file = "L:/声音/VoxCPM/workspace/飘飘欲仙1188狼太郎www.xitxt.net/line_005.wav"
        # 5. 加载音频
        print(f"加载音频文件: {audio_file}")
        samples, sample_rate = load_audio(audio_file)
        
        audio_duration = len(samples) / sample_rate
        print(f"音频时长: {audio_duration:.2f}秒")
        print(f"音频采样率: {sample_rate}Hz")
        print(f"音频样本数: {len(samples)}")
        
        # 如果采样率不匹配，进行重采样
        if sample_rate != config.sample_rate:
            print(f"重采样音频从 {sample_rate}Hz 到 {config.sample_rate}Hz...")
            try:
                import librosa
                samples = librosa.resample(samples, orig_sr=sample_rate, target_sr=config.sample_rate)
                sample_rate = config.sample_rate
                print("重采样完成")
            except ImportError:
                print("警告: 采样率不匹配，但未安装librosa库，可能影响检测效果")
        
        # 6. 处理音频
        print(f"\n开始VAD检测...")
        window_size = config.ten_vad.window_size
        print(f"处理窗口大小: {window_size} 样本 ({window_size/config.sample_rate*1000:.1f}ms)")
        
        audio_buffer = samples.copy()
        segment_count = 0
        total_speech_duration = 0
        
        while len(audio_buffer) > window_size:
            vad.accept_waveform(audio_buffer[:window_size])
            audio_buffer = audio_buffer[window_size:]
            
            # 检查是否检测到语音片段
            if vad.is_speech_detected():
                while not vad.empty():
                    segment = vad.front
                    start_time = segment.start / sample_rate
                    duration = len(segment.samples) / sample_rate
                    end_time = start_time + duration
                    
                    segment_count += 1
                    total_speech_duration += duration
                    
                    print(f"  语音片段 #{segment_count}:")
                    print(f"    开始时间: {start_time:.3f}s")
                    print(f"    结束时间: {end_time:.3f}s")
                    print(f"    持续时间: {duration:.3f}s")
                    print(f"    样本数量: {len(segment.samples)}")
                    
                    vad.pop()
        
        # 7. 显示统计信息
        print(f"\n=== 检测结果统计 ===")
        print(f"总音频时长: {audio_duration:.3f}s")
        print(f"检测到语音片段数量: {segment_count}")
        print(f"总语音时长: {total_speech_duration:.3f}s")
        print(f"语音占比: {total_speech_duration/audio_duration*100:.1f}%")
        print(f"静音时长: {audio_duration-total_speech_duration:.3f}s")
        
        if segment_count == 0:
            print("\n注意: 未检测到任何语音片段")
            print("可能的原因:")
            print("  1. 音频文件确实没有语音内容")
            print("  2. 检测阈值设置过高")
            print("  3. 音频质量较差或音量过低")
            print("  4. 采样率不匹配")
            print("\n建议:")
            print("  - 尝试降低阈值 (如 config.ten_vad.threshold = 0.3)")
            print("  - 检查音频文件是否包含可听见的语音")
            print("  - 确保音频采样率为16kHz")
        
    except FileNotFoundError as e:
        print(f"文件错误: {e}")
        print("\n请确保:")
        print("  1. 模型文件存在于 models/ten-vad/ 目录下")
        print("  2. 测试音频文件存在")
        
    except Exception as e:
        print(f"程序执行出错: {e}")
        print(f"错误类型: {type(e).__name__}")
        
        # 提供调试信息
        import traceback
        print(f"\n详细错误信息:")
        traceback.print_exc()

def check_dependencies():
    """检查依赖项是否正确安装"""
    # print("=== 依赖项检查 ===")
    
    dependencies = {
        'sherpa_onnx': 'sherpa-onnx',
        'numpy': 'numpy',
        'soundfile': 'soundfile',
    }
    
    optional_dependencies = {
        'librosa': 'librosa (用于音频重采样)'
    }
    
    all_ok = True
    
    for module, package in dependencies.items():
        try:
            __import__(module)
            # print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - 请运行: pip install {package}")
            all_ok = False
    
    for module, desc in optional_dependencies.items():
        try:
            __import__(module)
            # print(f"✓ {desc}")
        except ImportError:
            print(f"○ {desc} - 可选，建议安装: pip install {module}")
    
    return all_ok

if __name__ == "__main__":
    print("Sherpa-ONNX ten-VAD 测试程序\n")
    
    # 检查依赖项
    if check_dependencies():
        print()
        basic_vad_example()
    else:
        print("\n请先安装缺失的依赖项后再运行测试。")
