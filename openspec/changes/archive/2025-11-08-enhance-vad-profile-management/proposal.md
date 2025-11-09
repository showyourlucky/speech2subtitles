# Change: 增强VAD配置方案管理 (Enhance VAD Profile Management)

## Why

当前VAD配置在GUI中只支持单一配置编辑,用户无法保存和切换不同的VAD配置方案。实际使用中,用户可能需要针对不同场景(如安静环境、嘈杂环境、视频会议等)使用不同的VAD参数组合。此外,GUI设置界面仅提供了简化的参数(敏感度、阈值、窗口大小),而实际的VAD检测器初始化使用了更丰富的参数(见`detector.py:228-240`),两者存在gap。

**问题现状：**
1. GUI的VAD设置页面参数不完整 - 缺少`min_silence_duration_ms`、`min_speech_duration_ms`、`max_speech_duration_ms`等关键参数
2. 无法保存和管理多个VAD配置方案
3. 缺少方案的增删改功能
4. 主界面无法快速切换使用的VAD方案
5. Config模型中存在冗余字段(`vad_sensitivity`、`vad_window_size`)与`VadConfig`模型参数不一致

## What Changes

本提案将实现完整的VAD配置方案管理系统:

1. **扩展VadConfig参数支持** - GUI支持所有sherpa-onnx VAD初始化参数
2. **引入VAD Profile概念** - 允许用户创建、保存和命名多个VAD配置方案
3. **增强设置对话框** - 添加方案管理UI(新增、删除、重命名、复制)
4. **主界面集成** - 在主窗口添加VAD方案选择下拉框,支持快速切换
5. **持久化存储** - 将VAD方案保存到配置文件中
6. **向后兼容** - 保持现有API不变,渐进式迁移

**涉及的关键参数映射(detector.py:228-263)：**
```python
# VadProfile需包含的所有参数
vad_config.silero_vad.model = config.effective_model_path  # model_path字段
vad_config.silero_vad.threshold = config.threshold
vad_config.silero_vad.min_silence_duration = config.min_silence_duration_ms / 1000.0
vad_config.silero_vad.min_speech_duration = config.min_speech_duration_ms / 1000.0
vad_config.silero_vad.max_speech_duration = config.max_speech_duration_ms / 1000.0
vad_config.sample_rate = config.sample_rate
vad_config.num_threads = 1
vad_config.provider = "cpu"
```

## Impact

**Affected specs:**
- `vad` - 新增VAD方案管理requirements

**Affected code:**
- `src/gui/dialogs/settings_dialog.py:434-498` - `_create_vad_page()`方法需重构
- `src/gui/main_window.py:92-146` - 主窗口需添加方案选择器
- `src/config/models.py:108-144` - Config模型需添加vad_profiles字段
- `src/vad/models.py:61-174` - VadConfig已包含所需参数,但需确认完整性
- `src/gui/storage/config_file_manager.py` - 配置持久化需支持profiles

**Breaking changes:**
- 无破坏性变更,完全向后兼容
- 现有单一VAD配置将自动迁移为"默认"方案

**Migration path:**
- 首次启动时,从现有`Config`中提取VAD参数创建"默认"profile
- 旧配置文件中的`vad_sensitivity`、`vad_threshold`等字段映射到"默认"profile
- GUI平滑过渡,无需用户手动迁移
