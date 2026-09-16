# Core recovery proposal：仅恢复 13 条 Judge 解析失败

版本：`core-judge-recovery-proposal-v1`；交给新 `A-recovery` 会话。本任务只做只读取证、输入冻结和 proposal，**不发送新的 Judge 请求**。

## 背景

F2 已完成 1,200 条 generation 和 1,200 次首次 four-class Judge，另有 13 次既定 retry；13 条仍为 `PARSE_FAILURE`，导致 `CORE_DOSE_SCREEN_BLOCKED`。F3 已证明旧记录缺失 Judge raw/diagnostics，不能补标签。F4 已修复未来失败路径的证据留存，但不得改写旧 F2。

## 允许范围

- 只读 F2 run、generation ledger、schedule、Judge records、方向/frames、rubric/template/decoder 配置和 F4/F2 source snapshot。
- 只生成项目内 `.codex-temp/paper1_core_recovery_proposal/` 的 hash、输入索引和审计证据。
- 只写报告：`writing/broadening design/report/paper1_core_recovery_proposal_report.md`。
- 可写 proposal 文档，但不得修改旧 F2 文件、旧 ledger、`dose_decisions.json`、旧 directions、canonical config、E1/C3 文件或三份原实验设计。

## Proposal 必须明确

1. 新 recovery 必须是独立 run/ledger，旧 F2 全部只读；不得把新记录覆盖或合并回旧路径。
2. 输入只允许使用 13 条已有 generation completion 及其原始 prompt/frame/request hash；不得重新生成、改 prompt、改模型、改层、改 rho、改方向、改模板、改 rubric、改 decoder 或改 seed。
3. 每条最多新增 1 次 four-class Judge 请求；不调用 binary Judge，不追加 generation retry。实际请求数上限为 13，失败继续保留 `PARSE_FAILURE`。
4. 使用 F4 修复后的 observability 字段保存 raw、diagnostics、错误和 request identity；任何缺失都保持显式 missing，不推断 label。
5. 预先定义 gate：按原 F2 的模型/家庭/剂量分组和 2% missing 规则重新计算；只有所有必需分组满足原门槛，才可生成新的 A/S 和后续 evaluation readiness。否则 proposal 结果为 blocked。
6. 不得在 proposal 阶段发送请求、加载模型、使用 GPU、运行 Judge、screen、generation 或正式 evaluation。
7. 报告必须列出 13 条输入 identity/hash、预计最多 13 次请求、旧新 ledger 隔离、成功/失败后的 gate、禁止事项和所需的负责人批准。

## Linux/nohup 要求

在 `/data/goodtaste_workspace/llama-prefix` 执行；将 `TMPDIR/TMP/TEMP` 指向项目内 `.codex-temp`，启用 HF/Transformers/Datasets offline，所有检查通过 `nohup` 保存 PID、日志和 `.exit`。只使用 CPU/标准库读取 JSON 与 hash。

## 输出和停止

报告必须明确写入：

`CORE_RECOVERY_PROPOSAL_READY`

`OLD_F2_UNMODIFIED`

`NO_NEW_JUDGE_REQUESTS`

`CORE_DOSE_SCREEN_REMAINS_BLOCKED_PENDING_APPROVAL`

`FORMAL_EVALUATION_NOT_RUN`

完成一次边界自审后停止；不要 commit/push。若发现必须改变科学规则、放宽 2% 门槛、增加超过 13 次请求、重跑 generation 或改写旧 F2，立即报告 `DESIGN_CHANGE_REQUIRED` 并停止。
