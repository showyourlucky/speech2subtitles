# Change: 统一文件转录实现逻辑

## Why

当前系统中存在两套文件转录实现逻辑:

1. **batch_processor.py** (src/media/): 用于命令行批量文件处理,直接加载整个文件进行VAD分段和转录
2. **file_capture.py** (src/audio/): 用于GUI界面,模拟实时音频流,分块发送数据到流水线

这导致了以下问题:
- **代码重复**: 两套逻辑都包含文件加载、采样率转换、立体声转单声道等相同功能
- **维护成本高**: Bug修复和功能增强需要在两处同步
- **不一致性风险**: 两套实现可能在边界情况下表现不同
- **资源浪费**: 重复的依赖和测试代码

## What Changes

将两套实现统一为一个基于 **batch_processor** 的核心模块,并提供适配层:

1. **保留 batch_processor.py 作为核心实现** (已经过充分测试和优化)
   - 保留完整的批量处理能力
   - 保留sherpa-onnx VAD集成
   - 保留进度跟踪和统计功能

2. **重构 file_capture.py 为适配层**
   - 将其转换为 batch_processor 的轻量级封装
   - 复用 batch_processor 的文件加载和转录逻辑
   - 保留回调接口以适配GUI实时流水线架构
   - 提供进度回调适配

3. **统一配置和接口**
   - 统一音频加载逻辑(soundfile/pydub)
   - 统一重采样和声道转换
   - 统一VAD配置参数

4. **向后兼容**
   - 保持现有API签名不变
   - GUI和命令行模式都能正常工作

## Impact

### 受影响的规范
- **新增**: `file-transcription` - 文件转录统一规范

### 受影响的代码
- **核心修改**:
  - `src/audio/file_capture.py` - 重构为适配层
  - `src/media/batch_processor.py` - 提取可复用的核心逻辑
- **适配调整**:
  - `src/coordinator/pipeline.py` - 确保与新接口兼容
  - `main.py` - 验证命令行模式正常工作
  - `gui_main.py` - 验证GUI模式正常工作
- **测试更新**:
  - `tests/audio/test_file_capture.py` - 更新测试用例
  - `tests/media/test_batch_processor.py` - 添加新测试用例

### 预期收益
- **减少代码行数**: ~300行重复代码
- **提高可维护性**: 单一真实来源(Single Source of Truth)
- **统一行为**: 消除潜在的不一致性
- **简化测试**: 减少测试覆盖面积
