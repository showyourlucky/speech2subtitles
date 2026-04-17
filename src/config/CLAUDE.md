# 配置管理模块 (Config Management)

[根目录](../../CLAUDE.md) > [src](../) > **config**

## 模块职责
负责系统配置的统一建模、加载合并、命令行参数解析与校验。  
当前配置体系已升级为 **schema v2**，并保留旧字段访问方式作为兼容代理。

## 核心入口
- `manager.py::ConfigManager`
  负责 CLI 参数定义、解析和转换为 v2 覆盖字典。
- `loader.py::ConfigLoader`
  负责按优先级合并配置源并构建最终 `Config`。
- `models.py::Config`（兼容导出 `AppConfig = Config`）
  配置数据模型，包含 v2 分区结构与兼容属性。

## 配置合并优先级
最终配置采用以下覆盖顺序（后者覆盖前者）：
1. 默认配置（`Config.create_default()`）
2. 配置文件（`config/gui_config.json` 或指定导入文件）
3. 环境变量（`S2S_*`）
4. CLI 参数（仅显式传入的参数会覆盖）

## schema v2 结构
配置按分区组织：
- `runtime`: 输入模式、GPU、转录语言提示、模型方案
- `audio`: 采样率、块大小、声道、设备 ID
- `vad`: VAD 方案集合与激活方案
- `output`: 输出格式、置信度/时间戳显示
- `subtitle.file`: 离线字幕输出参数
- `subtitle.display`: 实时字幕显示参数

示例：
```json
{
  "runtime": {
    "input_source": "microphone",
    "input_file": null,
    "use_gpu": true,
    "transcription_language": "auto",
    "model": {
      "active_profile_id": "default",
      "profiles": {
        "default": {
          "profile_id": "default",
          "profile_name": "默认",
          "model_path": "models/.../model.onnx"
        }
      }
    }
  },
  "audio": {
    "sample_rate": 16000,
    "chunk_size": 1024,
    "channels": 1,
    "device_id": null
  },
  "vad": {
    "active_profile_id": "default",
    "profiles": {}
  },
  "output": {
    "format": "text",
    "show_confidence": true,
    "show_timestamp": true
  },
  "subtitle": {
    "file": {
      "output_dir": null,
      "format": "srt",
      "keep_temp": false,
      "verbose": false
    },
    "display": {
      "enabled": false,
      "position": "bottom",
      "font_size": 24,
      "font_family": "Microsoft YaHei",
      "opacity": 0.8,
      "max_display_time": 5.0,
      "text_color": "#FFFFFF",
      "background_color": "#000000"
    }
  }
}
```

## 兼容策略
`Config` 仍支持旧平铺字段读写，例如：
- `model_path -> runtime.model.profiles[active].model_path`
- `input_source -> runtime.input_source`
- `use_gpu -> runtime.use_gpu`
- `vad_threshold -> active vad profile.threshold`
- `output_format -> output.format`
- `subtitle_format -> subtitle.file.format`

字典反序列化支持两类输入：
- `Config.from_dict_v2()`：v2 分区结构
- `Config.from_legacy_dict()`：旧平铺结构（自动迁移）

## CLI 显式覆盖映射
`ConfigManager` 仅在参数被显式传入时生成覆盖键，未传参数始终沿用 `config/gui_config.json`。
覆盖字段为扁平兼容键，最终由 `Config.from_dict_v2()` 应用到 v2 结构与激活方案：
- 运行参数：`--model-path`、`--input-source`、`--input-file`
- 通用参数：`--no-gpu`、`--transcription-language`
- 音频参数：`--sample-rate`、`--chunk-size`、`--device-id`
- VAD 参数：`--vad-threshold`、`--vad-window-size`
- 输出参数：`--output-format`、`--no-confidence`、`--no-timestamp`
- 字幕文件参数：`--output-dir`、`--subtitle-format`、`--keep-temp`、`--verbose`
- 字幕显示参数：`--show-subtitles`、`--subtitle-position`、`--subtitle-font-size`、`--subtitle-font-family`、`--subtitle-opacity`、`--subtitle-max-display-time`、`--subtitle-text-color`、`--subtitle-bg-color`

## 环境变量支持（S2S_*）
`ConfigLoader` 支持以下环境变量覆盖：
- 运行时：`S2S_INPUT_SOURCE`、`S2S_INPUT_FILE`、`S2S_USE_GPU`、`S2S_TRANSCRIPTION_LANGUAGE`、`S2S_MODEL_PATH`、`S2S_MODEL_PROFILE`
- 音频：`S2S_SAMPLE_RATE`、`S2S_CHUNK_SIZE`、`S2S_CHANNELS`、`S2S_DEVICE_ID`
- VAD：`S2S_VAD_PROFILE`
- 输出：`S2S_OUTPUT_FORMAT`、`S2S_SHOW_CONFIDENCE`、`S2S_SHOW_TIMESTAMP`
- 字幕文件：`S2S_SUBTITLE_FORMAT`、`S2S_OUTPUT_DIR`、`S2S_KEEP_TEMP`、`S2S_VERBOSE`
- 字幕显示：`S2S_SUBTITLE_ENABLED`、`S2S_SUBTITLE_POSITION`、`S2S_SUBTITLE_FONT_SIZE`、`S2S_SUBTITLE_FONT_FAMILY`、`S2S_SUBTITLE_OPACITY`、`S2S_SUBTITLE_MAX_DISPLAY_TIME`、`S2S_SUBTITLE_TEXT_COLOR`、`S2S_SUBTITLE_BG_COLOR`

## GUI 侧配置协作
GUI 通过 `ConfigBridge + ConfigFileManager` 使用同一套配置模型：
- 持久化文件：`config/gui_config.json`
- 文件包裹格式：`{ version: "2.0", last_modified, config }`
- 导入导出：支持 v2 结构；旧版本导入时自动迁移
- 兼容键映射：`subtitle_display.*` 自动映射到 `subtitle.display.*`

## 推荐使用方式
```python
from src.config.manager import ConfigManager
from src.config.loader import ConfigLoader

manager = ConfigManager()
cli_overrides = manager.parse_cli_overrides()
config = ConfigLoader().load(cli_overrides=cli_overrides, validate=True)
```

## 测试与验证
- 配置模型测试：`tests/test_config.py`
- 语法检查：`python -m py_compile src/config/models.py src/config/loader.py src/config/manager.py`
- 说明：`tests/test_integration.py` 当前存在与输出模块导入相关的问题，和本次配置重构逻辑无直接耦合。

## 变更记录
- **2026-04-07**: CLI 覆盖策略调整为“仅显式传参覆盖”；`Config.from_dict_v2()` 增加 flat 兼容覆盖应用，确保未传参时完整沿用 `config/gui_config.json`（含 `active_vad_profile_id` 激活方案参数）。
- **2026-04-07**: 文档同步到 schema v2，补充 ConfigLoader 优先级、CLI/ENV 对照与 GUI 配置协作说明。
