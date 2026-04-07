# 配置体系重构 - 进度记录

## 背景
- 目标：统一配置结构，消除默认值分裂，明确优先级（CLI > ENV > 文件 > 默认）。
- 范围：配置模型、加载器、CLI 解析、GUI 持久化与流水线读取。

## 关键决策
- 配置主格式：JSON（schema v2）。
- 优先级：CLI > ENV > 文件 > 默认。
- 保持旧字段访问方式，仅作为兼容代理，不再独立存储。

## TODO 清单
- [x] 重建配置模型（AppConfig + 分区结构 + 兼容属性）。
- [x] 新增配置加载器（ConfigLoader）。
- [x] CLI 解析输出 v2 结构。
- [x] 配置文件持久化支持 v2（读/写/迁移）。
- [x] Pipeline 使用统一语言解析逻辑（移除 env 直读）。
- [x] 调整与补充单元测试（Config/Integration）。
- [x] 更新配置与 GUI 文档说明。
- [ ] 运行完整测试（可选）。

## 文档更新范围（2026-04-07）
- 配置文档：同步为 schema v2 分区结构，补充 ConfigLoader 合并优先级、CLI/ENV 对照、兼容策略。
- GUI 文档：补充 GUI 配置持久化路径 `config/gui_config.json`、导入导出格式、旧键映射逻辑（`subtitle_display.* -> subtitle.display.*`）。

## 验证状态
- 已通过：`python -m py_compile`（配置链路相关文件）。
- 已通过：`pytest tests/test_config.py -q`。
- 未完成：完整测试回归（`tests/test_integration.py` 当前存在与本次重构无关的导入问题，待单独修复后再跑全量）。

## 变更记录（最新）
- 2026-04-07：完成配置模型重建、加载器与持久化链路升级；修正 CLI 覆盖逻辑；调整基础测试适配新 schema。
- 2026-04-07：完成配置与 GUI 文档更新，明确 v2 结构、兼容映射和使用说明。
