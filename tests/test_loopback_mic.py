# 需要安装: pip install soundcard soundfile numpy
import soundcard as sc
import soundfile as sf

# 定义录制参数
SAMPLE_RATE = 48000
RECORD_SEC = 10
BLOCK_SIZE = 1024
OUTPUT_FILE_CORRECTED = "output_corrected.wav"

print("启动修正后的录制脚本...")

try:
    # 步骤 1: 获取默认扬声器，并由此找到对应的环回麦克风对象
    # 这个 'loopback_mic' 对象持有设备的元数据（如通道数）
    speaker = sc.default_speaker()
    loopback_mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    
    print(f"已定位环回设备: '{loopback_mic.name}'，通道数: {loopback_mic.channels}")

    # 步骤 2: 使用 'with' 语句同时管理录制器和文件写入器
    # - loopback_mic.recorder(...) 创建一个录制器实例 'mic'
    # - sf.SoundFile(...) 使用从 'loopback_mic' 获取的通道数 'loopback_mic.channels'
    with loopback_mic.recorder(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE) as mic, \
         sf.SoundFile(OUTPUT_FILE_CORRECTED, 'w', samplerate=SAMPLE_RATE, channels=loopback_mic.channels, subtype='FLOAT') as wav_file:
        
        print(f"录制已开始，将持续 {RECORD_SEC} 秒...")
        
        total_frames_to_record = SAMPLE_RATE * RECORD_SEC
        frames_recorded = 0
        
        # 循环录制和写入，直到达到指定时长
        while frames_recorded < total_frames_to_record:
            data = mic.record(numframes=BLOCK_SIZE)
            wav_file.write(data)
            frames_recorded += data.shape[0]

except IndexError:
    print("错误：无法找到默认音频输出设备。请确保耳机已连接且被系统识别。")
except Exception as e:
    print(f"录制过程中发生意外错误: {e}")

finally:
    print(f"录制流程结束。音频已保存至 {OUTPUT_FILE_CORRECTED}")

