# Specification: 文件转录统一实现

## ADDED Requirements

### Requirement: 核心文件转录逻辑
系统 SHALL 在 `batch_processor.py` 中提供统一的文件转录核心逻辑,支持音频和视频文件的加载、转录和字幕生成。

#### Scenario: 处理音频文件
- **WHEN** 用户提供一个WAV/MP3/FLAC等音频文件
- **THEN** 系统应使用soundfile库加载文件
- **AND** 自动处理采样率转换(如需要)
- **AND** 自动处理立体声转单声道(如需要)
- **AND** 使用sherpa-onnx VAD进行语音分段
- **AND** 使用转录引擎生成文本
- **AND** 返回带时间戳的转录片段列表

#### Scenario: 处理视频文件
- **WHEN** 用户提供一个MP4/AVI/MKV等视频文件
- **THEN** 系统应优先使用pydub+ffmpeg提取音频
- **AND** 如果pydub不可用,回退到soundfile
- **AND** 后续处理流程与音频文件相同

#### Scenario: 批量处理多个文件
- **WHEN** 用户提供多个文件路径
- **THEN** 系统应依次处理每个文件
- **AND** 为每个文件生成独立的字幕文件
- **AND** 记录每个文件的处理统计信息(时长、RTF等)
- **AND** 提供批量处理进度回调

### Requirement: 适配层实现
系统 SHALL 在 `file_capture.py` 中提供适配层,将批量处理逻辑适配到实时流水线架构。

#### Scenario: GUI模式实时流适配
- **WHEN** GUI使用FileAudioCapture加载文件
- **THEN** 适配层应调用batch_processor的文件加载逻辑
- **AND** 将整个文件数据存储在内存中
- **AND** 在start()后,按chunk_size分块发送AudioChunk
- **AND** 通过回调函数将每个chunk传递给流水线
- **AND** 支持暂停/恢复控制

#### Scenario: 实时进度更新
- **WHEN** 文件正在处理中
- **THEN** 适配层应定期调用进度回调
- **AND** 提供已处理样本数和总样本数
- **AND** 提供已用时间和预计剩余时间
- **AND** 计算进度百分比

#### Scenario: 处理完成通知
- **WHEN** 文件所有数据已处理完毕
- **THEN** 适配层应调用completion_callback
- **AND** 停止音频块发送循环
- **AND** 更新is_running状态为False

### Requirement: 统一文件加载逻辑
系统 SHALL 提供统一的音频文件加载方法,在batch_processor和file_capture之间复用。

#### Scenario: 自动格式检测
- **WHEN** 加载未知扩展名的文件
- **THEN** 系统应首先尝试soundfile
- **AND** 如果失败且文件扩展名为视频格式,尝试pydub
- **AND** 如果都失败,抛出明确的错误信息

#### Scenario: 采样率不匹配处理
- **WHEN** 文件采样率与目标采样率不同(如44100Hz vs 16000Hz)
- **THEN** 系统应使用scipy.signal.resample进行重采样
- **AND** 如果scipy不可用,抛出明确错误提示用户安装
- **AND** 记录重采样操作到日志

#### Scenario: 多声道处理
- **WHEN** 加载立体声或多声道音频
- **THEN** 系统应自动转换为单声道
- **AND** 使用均值混合方法(mean across channels)
- **AND** 记录声道转换操作到日志

### Requirement: 向后兼容性
系统 MUST 保持现有API接口不变,确保GUI和命令行模式都能正常工作。

#### Scenario: 命令行批处理模式
- **WHEN** 通过main.py使用--input-file参数
- **THEN** 批处理器应正常加载和处理文件
- **AND** 生成字幕文件到指定目录
- **AND** 显示处理进度和统计信息
- **AND** 行为与重构前完全一致

#### Scenario: GUI实时流模式
- **WHEN** 通过gui_main.py选择文件进行转录
- **THEN** FileAudioCapture应正常初始化
- **AND** 通过流水线正常处理音频块
- **AND** 实时显示转录结果
- **AND** 进度条正常更新
- **AND** 行为与重构前完全一致

#### Scenario: 异常处理兼容性
- **WHEN** 遇到不支持的文件格式或加载失败
- **THEN** 系统应抛出与重构前相同类型的异常
- **AND** 错误信息应清晰描述问题原因
- **AND** 建议用户安装缺失的依赖(如适用)

### Requirement: 可测试性
系统 SHALL 提供清晰的接口边界,便于单元测试和集成测试。

#### Scenario: 核心逻辑单元测试
- **WHEN** 测试文件加载逻辑
- **THEN** 应能mock文件系统和音频库
- **AND** 验证采样率转换的正确性
- **AND** 验证声道转换的正确性

#### Scenario: 适配层单元测试
- **WHEN** 测试FileAudioCapture
- **THEN** 应能mock batch_processor的核心方法
- **AND** 验证回调函数被正确调用
- **AND** 验证进度计算的准确性

#### Scenario: 端到端集成测试
- **WHEN** 使用真实的测试文件
- **THEN** 应验证完整的处理流程
- **AND** 验证生成的字幕内容准确性
- **AND** 验证批量和实时模式的结果一致性

## MODIFIED Requirements

无 - 这是新增功能规范

## REMOVED Requirements

无 - 保持向后兼容
