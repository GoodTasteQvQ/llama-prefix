# E2：Gemma release 记录缺口审计

版本：`e2-release-gap-audit-v1`；交给新 E2 会话。该任务可与 F3 并行，只读，不运行 E2 实验。

先阅读 F 方向构造报告、F2 screen 报告、B6 静态交接报告、当前任务入口和原实验设计。核对 F run 中 Gemma 方向资产的实际状态，尤其是 `directions.json`、Gemma tensor、runtime identity、层 14、mu/token count、source snapshot 和现有 release 记录。

## 任务范围

- 判断 release 缺口是仅 metadata serialization 缺失，还是实际模型/hook/tokenizer 未释放或身份不完整；只能依据已有 raw、日志和 JSON。
- 对照 Qwen/Llama 已有 release schema，提出能补齐记录的最小实现位置和最小离线测试；若必须改共享源码，先写 `DESIGN_CHANGE_REQUIRED` 或 `IMPLEMENTATION_PATCH_REQUIRED`，不要直接修改或重建 F run。
- 只读检查本地 Gemma 权重路径、config/tokenizer/template hash 与 F 报告记录；不下载、不加载模型、不占 GPU、不启动 prepare/build-directions/screen/generation/Judge。

不要回填或覆盖 `directions.json`，不要伪造 release 字段，不修改 canonical config、科学设计、Core screen 产物或 E1 文件。所有脚本/临时输出写项目内 `.codex-temp/paper1_e2_release_gap_audit/`；需要批量检查时用 `nohup`，保存 PID、日志、`.exit`。

保存 `writing/broadening design/report/paper1_e2_gemma_release_gap_audit_report.md`，列实际证据、风险、最小修复建议、未修改文件，并明确 `E2_FORMAL_EXPERIMENT_NOT_RUN`、`FORMAL_EVALUATION_NOT_RUN`。完成一次边界自审后停止，不 commit/push。
