# Spec Delta: file-transcription-gui

## ADDED Requirements

### Requirement: BatchProcessor进度回调接口
系统 SHALL 在 `BatchProcessor` 中提供回调接口,使GUI能够接收文件转录的进度和结果信息。

#### Scenario: 命令行模式不传回调
- **WHEN** 从命令行使用 `run_file_transcription()` 调用 `BatchProcessor`
- **THEN** 不传递任何回调参数(所有回调为None)
- **AND** 处理逻辑与重构前完全一致
- **AND** 性能不受影响

#### Scenario: GUI模式传递进度回调
- **WHEN** GUI对话框调用 `BatchProcessor.process_files()` 并传递 `on_file_start`, `on_file_progress`, `on_file_complete` 回调
- **THEN** BatchProcessor在处理每个文件时调用相应回调
- **AND** `on_file_start(file_index, total_files, filename)` 在开始处理文件时调用
- **AND** `on_file_progress(file_index, progress_percent)` 在处理进度变化时调用(至少在0%, 25%, 85%, 100%调用)
- **AND** `on_file_complete(file_path, subtitle_file, duration, rtf)` 在文件处理完成时调用

#### Scenario: GUI模式传递segment回调用于实时预览
- **WHEN** GUI对话框传递 `on_segment` 回调
- **THEN** BatchProcessor在每个转录segment生成时调用 `on_segment(segment)`
- **AND** segment包含文本、开始时间、结束时间
- **AND** 如果不传递 `on_segment`,则不产生额外开销

#### Scenario: 回调函数抛出异常
- **WHEN** 用户提供的回调函数内部抛出异常
- **THEN** BatchProcessor应捕获异常并记录到日志
- **AND** 继续处理文件,不中断批量任务
- **AND** 警告日志包含异常详情

### Requirement: BatchProcessor取消功能
系统 SHALL 支持取消正在进行的批量文件转录任务。

#### Scenario: 用户取消批量任务
- **WHEN** GUI传递 `threading.Event` 作为 `cancel_event` 参数
- **AND** 用户在处理过程中点击"取消"按钮,设置 `cancel_event.set()`
- **THEN** BatchProcessor应在下一个检查点检测到取消信号
- **AND** 抛出 `BatchProcessorCancelled` 异常
- **AND** 已完成的文件字幕保留
- **AND** 当前正在处理的文件可能不完整(可接受)

#### Scenario: 取消时清理临时文件
- **WHEN** 取消发生时存在临时音频文件
- **AND** `keep_temp=False`
- **THEN** 临时文件应被清理
- **AND** 异常包含清理状态信息

#### Scenario: 取消检查点位置
- **WHEN** 批量处理正在进行
- **THEN** 取消检查应至少在以下位置进行:
- **AND** 每个文件开始前
- **AND** MediaConverter转换完成后
- **AND** VAD分段每5秒检查一次
- **AND** 转录每个segment后

### Requirement: BatchProcessor批量处理方法
系统 SHALL 提供 `process_files()` 方法用于批量处理多个文件。

#### Scenario: 批量处理多个文件
- **WHEN** 用户提供10个媒体文件路径的列表
- **THEN** `process_files()` 应依次处理每个文件
- **AND** 为每个文件调用 `process_file()` 方法
- **AND** 每个文件生成独立的字幕文件
- **AND** 返回统计信息: `{total: 10, success: 8, failed: 2, errors: [(file1, error1), (file2, error2)]}`

#### Scenario: 单文件失败继续处理
- **WHEN** `continue_on_error=True` (默认)
- **AND** 第3个文件处理失败(如文件损坏)
- **THEN** 记录错误到errors列表
- **AND** 继续处理第4个文件
- **AND** failed计数器+1
- **AND** 所有文件处理完后返回完整统计

#### Scenario: 单文件失败中止批量
- **WHEN** `continue_on_error=False`
- **AND** 某个文件处理失败
- **THEN** 立即抛出异常
- **AND** 已完成文件的字幕保留
- **AND** 未处理文件跳过

### Requirement: GUI批量转录对话框
系统 SHALL 提供 `FileTranscriptionDialog` 对话框,用于GUI批量文件转录。

#### Scenario: 打开批量转录对话框
- **WHEN** 用户点击菜单 "文件" → "批量转录文件..." (快捷键 Ctrl+B)
- **THEN** 显示 `FileTranscriptionDialog` 对话框
- **AND** 对话框为模态(阻塞主窗口)
- **AND** 文件列表为空
- **AND** 输出目录默认为当前用户的"文档"目录
- **AND** 字幕格式默认为SRT
- **AND** "开始"按钮禁用(至少需要1个文件)

#### Scenario: 添加文件到转录列表
- **WHEN** 用户点击"添加文件"按钮
- **THEN** 显示文件选择对话框,支持多选
- **AND** 支持的格式: mp4, avi, mkv, mov, mp3, wav, flac, m4a
- **AND** 选中的文件添加到列表显示
- **AND** 显示文件名、大小、时长(如果可读取)
- **AND** "开始"按钮启用

#### Scenario: 移除文件从列表
- **WHEN** 用户选中列表中的1个或多个文件
- **AND** 点击"移除选中"按钮
- **THEN** 选中的文件从列表移除
- **AND** 如果列表为空,"开始"按钮禁用

#### Scenario: 开始批量转录
- **WHEN** 用户点击"开始"按钮
- **THEN** 创建Worker线程运行BatchProcessor
- **AND** "开始"按钮变为"取消"按钮
- **AND** 文件添加/移除按钮禁用
- **AND** 总进度条显示文件级进度
- **AND** 当前文件信息显示 "正在处理 1/10: video.mp4"
- **AND** 当前文件进度条显示单文件进度

#### Scenario: 实时显示转录结果
- **WHEN** BatchProcessor生成新的转录segment
- **THEN** 预览区域追加显示文本
- **AND** 格式: `[00:01:23] 这是转录的文本内容`
- **AND** 只保留最近50条segment
- **AND** 超过50条时自动移除最旧的条目

#### Scenario: 文件转录完成
- **WHEN** 某个文件转录完成
- **THEN** 统计信息更新: "成功: 3, 失败: 0, 剩余: 7"
- **AND** 列表中该文件显示 ✅ 标记
- **AND** 如果有失败,显示 ❌ 标记

#### Scenario: 所有文件完成
- **WHEN** 批量任务全部完成(无论成功或失败)
- **THEN** 显示完成对话框,包含统计信息
- **AND** "取消"按钮变为"关闭"按钮
- **AND** 预览区域显示摘要: "处理完成! 成功8个,失败2个"

#### Scenario: 用户取消批量任务
- **WHEN** 用户点击"取消"按钮
- **THEN** 设置cancel_event信号
- **AND** "取消"按钮禁用,显示 "正在取消..."
- **AND** Worker线程接收取消信号并停止
- **AND** 显示对话框: "任务已取消。已完成X个文件,剩余Y个文件未处理。"

### Requirement: GUI对话框输入验证
系统 SHALL 验证用户输入,防止无效配置。

#### Scenario: 输出目录不可写
- **WHEN** 用户选择一个只读目录作为输出目录
- **AND** 点击"开始"
- **THEN** 显示错误提示: "输出目录不可写,请选择其他目录"
- **AND** 不启动处理

#### Scenario: 模型文件未配置
- **WHEN** 系统配置中模型文件路径为空或文件不存在
- **AND** 用户尝试打开批量转录对话框
- **THEN** 显示警告对话框: "请先在设置中配置模型文件"
- **AND** 不打开批量转录对话框

#### Scenario: 文件格式不支持
- **WHEN** 用户添加了 .txt 或其他非媒体文件
- **THEN** 文件选择对话框过滤器阻止选择
- **OR** 如果通过其他方式添加,显示警告并跳过该文件

### Requirement: 进度计算准确性
系统 SHALL 提供合理准确的进度估算。

#### Scenario: 文件级总进度
- **WHEN** 批量处理10个文件
- **AND** 已完成3个,正在处理第4个(50%)
- **THEN** 总进度应为: `(3 + 0.5) / 10 * 100 = 35%`

#### Scenario: 单文件进度估算
- **WHEN** 正在处理单个文件
- **THEN** 进度权重分配:
- **AND** 音频转换: 25%
- **AND** VAD+转录: 60%
- **AND** 字幕生成: 15%
- **AND** 总进度 = 0.25 * convert_done + 0.60 * transcription_progress + 0.15 * subtitle_done

#### Scenario: 进度回调频率
- **WHEN** 处理大文件(如2小时视频)
- **THEN** `on_file_progress` 回调至少每5秒调用一次
- **AND** 避免过于频繁的回调导致UI卡顿

### Requirement: 资源管理和清理
系统 SHALL 正确管理资源,避免内存泄漏。

#### Scenario: 对话框关闭时清理Worker线程
- **WHEN** 用户在任务运行中关闭对话框
- **THEN** 设置cancel_event停止Worker
- **AND** 等待Worker线程最多5秒
- **AND** 如果超时,记录警告日志
- **AND** 释放BatchProcessor资源

#### Scenario: 预览区域内存限制
- **WHEN** 转录了超过50条segment
- **THEN** 自动移除最旧的segment
- **AND** 内存占用保持恒定
- **AND** 不因长时间运行导致内存增长

### Requirement: 错误处理和用户反馈
系统 SHALL 提供清晰的错误信息和恢复建议。

#### Scenario: FFmpeg未安装
- **WHEN** 处理视频文件但ffmpeg不可用
- **THEN** 显示错误: "FFmpeg未安装或不在PATH中。请安装FFmpeg以处理视频文件。"
- **AND** 提供安装指南链接(可选)

#### Scenario: 磁盘空间不足
- **WHEN** 处理过程中磁盘空间耗尽
- **THEN** 捕获异常并显示: "磁盘空间不足,无法继续处理。"
- **AND** 已完成文件保留
- **AND** 临时文件清理

#### Scenario: 模型加载失败
- **WHEN** TranscriptionEngine初始化失败
- **THEN** 在Worker启动时捕获异常
- **AND** 显示错误对话框: "转录引擎初始化失败: [错误详情]"
- **AND** 不启动批量处理

### Requirement: 向后兼容性保证
系统 MUST 保证现有功能不受影响。

#### Scenario: 命令行批量模式不受影响
- **WHEN** 使用命令行: `python main.py --input-file a.mp4 b.mp4 --output-dir out/`
- **THEN** 功能与添加GUI对话框前完全一致
- **AND** 不加载任何GUI模块
- **AND** 性能不变

#### Scenario: GUI实时转录不受影响
- **WHEN** 在GUI中选择麦克风或系统音频进行实时转录
- **THEN** 继续使用FileAudioCapture + TranscriptionPipeline
- **AND** 功能和性能不受影响

#### Scenario: BatchProcessor单文件API兼容
- **WHEN** 现有代码调用 `BatchProcessor.process_file()` 不传递回调参数
- **THEN** 所有回调参数默认为None
- **AND** 行为与之前完全一致
- **AND** 不产生额外开销
