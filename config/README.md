# 配置目录

此目录用于存储GUI应用程序的用户配置文件。

## 文件说明

- `gui_config.json`: GUI设置的持久化配置文件
  - 模型路径
  - 音频参数
  - VAD设置
  - 字幕显示配置
  - 等等

## 注意事项

⚠️ **配置文件不会提交到Git仓库**
- 配置文件包含用户特定的路径和设置
- 已通过 `.gitignore` 排除 `*.json` 文件
- 仅保留 `.gitkeep` 以确保目录结构被跟踪

## 配置迁移

如果您之前使用过旧版本,配置会自动从以下位置迁移:
- Windows: `%USERPROFILE%\.speech2subtitles\config.json`
- Linux/macOS: `~/.speech2subtitles/config.json`

迁移后,新配置将保存在此目录下的 `gui_config.json`。
