# Implementation Tasks: 统一文件转录实现

## 1. 准备工作
- [ ] 1.1 创建feature分支: `git checkout -b feature/unify-file-transcription`
- [ ] 1.2 备份当前实现: 复制 `file_capture.py` 和 `batch_processor.py` 到临时目录
- [ ] 1.3 分析现有测试用例,确保理解预期行为

## 2. 提取batch_processor核心逻辑
- [ ] 2.1 在 `batch_processor.py` 中提取 `_load_audio_file()` 方法
  - 支持soundfile和pydub两种加载方式
  - 统一采样率转换逻辑
  - 统一立体声转单声道逻辑
- [ ] 2.2 提取 `_resample_audio()` 方法(使用scipy)
- [ ] 2.3 提取 `_convert_to_mono()` 方法
- [ ] 2.4 添加详细的日志记录和错误处理
- [ ] 2.5 为核心方法添加类型注解

## 3. 重构file_capture为适配层
- [ ] 3.1 修改 `FileAudioCapture.__init__()`:
  - 移除重复的文件加载逻辑
  - 添加对batch_processor核心方法的引用
- [ ] 3.2 修改 `load_audio()` 方法:
  - 调用batch_processor的 `_load_audio_file()`
  - 保留进度初始化逻辑
  - 保持返回值和异常类型不变
- [ ] 3.3 移除 `_load_with_pydub()` 和 `_resample()` 方法(使用共享实现)
- [ ] 3.4 保留 `_process_loop()` 方法(分块发送逻辑)
- [ ] 3.5 保留所有回调接口(callbacks, progress_callbacks, completion_callbacks)

## 4. 统一配置和错误处理
- [ ] 4.1 确保两个模块使用一致的依赖检查逻辑
- [ ] 4.2 统一错误消息格式和建议
- [ ] 4.3 统一日志记录级别和格式
- [ ] 4.4 添加详细的文档字符串(包含示例)

## 5. 更新测试用例
- [ ] 5.1 更新 `tests/audio/test_file_capture.py`:
  - 验证适配层正确调用核心逻辑
  - 验证回调函数正常工作
  - 验证进度跟踪准确性
- [ ] 5.2 更新 `tests/media/test_batch_processor.py`:
  - 添加文件加载逻辑的单元测试
  - 测试采样率转换边界情况
  - 测试多声道转换
- [ ] 5.3 添加集成测试验证一致性:
  - 使用相同文件分别通过批处理和实时流处理
  - 验证生成的字幕内容一致(允许时间戳微小差异)

## 6. 验证向后兼容性
- [ ] 6.1 运行命令行批处理模式:
  ```bash
  python main.py --model-path models/... --input-file test.mp4
  ```
- [ ] 6.2 运行GUI模式,测试文件选择和转录
- [ ] 6.3 测试多种文件格式(MP3, WAV, MP4, MKV等)
- [ ] 6.4 测试异常情况(不支持的格式、缺失依赖等)

## 7. 性能优化和验证
- [ ] 7.1 使用性能分析工具对比重构前后的性能
- [ ] 7.2 验证内存使用没有显著增加
- [ ] 7.3 验证RTF(Real-Time Factor)保持在可接受范围

## 8. 文档更新
- [ ] 8.1 更新 `src/audio/CLAUDE.md`:
  - 说明file_capture现在是适配层
  - 记录与batch_processor的依赖关系
- [ ] 8.2 更新 `src/media/CLAUDE.md`:
  - 说明batch_processor提供核心文件处理逻辑
  - 记录被file_capture复用的方法
- [ ] 8.3 更新根目录 `CLAUDE.md` 的架构图和模块说明
- [ ] 8.4 如有必要,更新用户文档和README

## 9. 代码审查和清理
- [ ] 9.1 检查是否有未使用的导入和方法
- [ ] 9.2 运行代码格式化: `black src/`
- [ ] 9.3 运行代码检查: `flake8 src/`
- [ ] 9.4 确保所有类型注解正确

## 10. 提交和归档
- [ ] 10.1 提交变更: `git commit -m "refactor: 统一文件转录实现逻辑"`
- [ ] 10.2 运行完整测试套件: `pytest tests/ --cov=src`
- [ ] 10.3 创建PR并请求代码审查
- [ ] 10.4 合并到主分支后,归档OpenSpec变更:
  ```bash
  openspec archive unify-file-transcription --skip-specs --yes
  ```

## 依赖关系说明
- 任务2必须在任务3之前完成(先提取核心逻辑再重构适配层)
- 任务5依赖任务2-4完成(代码变更后才能测试)
- 任务6依赖任务5完成(单元测试通过后再进行集成测试)
- 任务10依赖所有前序任务完成

## 验收标准
✅ 所有现有测试通过
✅ 命令行和GUI模式功能正常
✅ 代码行数减少~300行
✅ 测试覆盖率不低于原水平
✅ 文档完整更新
