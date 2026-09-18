# Core Judge protocol v3 independent recovery proposal and approval gate

执行会话：`A-core-recovery-v3-proposal`
协议：`core-judge-protocol-v3-direct-json`

R2 direct-JSON compatibility probe 已通过，v2.3 direct-JSON 设计副本和
run-specific config 已完成。当前任务只冻结旧 Core screen 中的 13 条解析失败
输入并形成独立 recovery proposal；不加载模型、不发送 Judge 请求、不运行 recovery。

## 读取和保护

只读读取：

- `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.3_direct_json.md`
- `configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json`
- `writing/broadening design/report/paper1_core_judge_protocol_v3_design_revision_report.md`
- R2 probe report/run and its final boundary audit;
- old Core F2 run: `results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`;
- old F2 screen Judge records, generation records, request manifests and source snapshots.

旧 F2、旧 recovery、R2 probe、v2.1/v2.3 design、canonical config、safe-pair
source/ledger、directions、dose decisions 和全部历史结果只读。不得覆盖、合并、
删除、重命名或回写任何旧文件。不要创建 active approval 文件。

## 数据 overlay 一致性预检

记录 v2.3 正文仍描述的 v2.1.1 base source，以及当前 expanded config 实际绑定的
authorized v2.1.2 overlay。必须把以下事实写入 proposal：

- expanded source=516；preliminary=509；executable=300；
- construction folds=5 x 40；development=100；unused=0；`actual_k=40`；
- overlay 只影响 contrastive direction construction inputs，不改变本 recovery 的
  13 条旧 F2 generation/Judge inputs、Judge protocol 或 formal generation budget。

这项记录用于防止后续把 416 和 516 混写。若发现 expanded config、source manifest、
ledger 或 frame digest 与上述已批准事实不一致，写 `DATA_OVERLAY_MISMATCH` 并停止；
不要自行改设计或数据。

## Recovery 输入冻结

从旧 F2 的最终 screen Judge records 中筛选且只筛选 13 条真实
`PARSE_FAILURE` logical identities。逐条核对：

- response/logical identity、prompt id、model、family、layer、rho、direction、phase、dose；
- 原始 generation completion、prompt hash、completion hash、request hash；
- 原 Judge attempt/call count、parse error 和缺失状态；
- 输入顺序与旧 F2 报告/ledger一致。

生成独立 proposal 目录：
`.codex-temp/paper1_core_judge_protocol_v3/recovery_proposal/`。
其中保存冻结的 13-row input manifest、每行 hash、source path、v2.3 config hash、
R2 reference hash、old-F2 protection hash、数据 overlay check、code/runtime
预期身份以及完整 artifact hash manifest。不要复制或重写旧 raw；只保存必要的
冻结索引和 hash 引用。

## 拟议 recovery 范围（只写入 proposal，不执行）

proposal 必须固定下列未来批准内容：

- 独立 run：`results/paper1_broadening/core-judge-protocol-v3-direct-json-recovery-<UTC>-<shortid>/`；
- 最多 13 次 four-class Judge request，每条输入最多 1 次；
- `enable_thinking=false`、`max_new_tokens=1296`、`strict_direct_json_v1`；
- 使用旧 F2 的原 prompt、generation completion、rubric、domain、Qwen3 Judge、
  tokenizer/chat template、float32、greedy、one beam；
- binary Judge=0、generation retry=0、additional Judge retry=0；
- 保持原 2% missing gate；不把 recovery 标签与旧 1,187 个成功标签合并；
- 任一请求失败、缺证据、身份不一致或隐藏 retry 时立即停止并标记失败；
- old F2 和 old recovery 不覆盖、不合并、不回写。

## 离线执行和输出

所有检查通过实验室 Python、offline Hugging Face 变量、单卡变量和 `nohup` 执行，
证据保存于 proposal 目录，包含 PID、log、`.exit`、代码/config/design hash、
输入 manifest 和最终边界审计。不得加载模型，不发送 Judge 请求。

保存：

- `writing/broadening design/report/paper1_core_judge_protocol_v3_recovery_proposal_report.md`；
- proposal 目录中的冻结 manifest、overlay check、hash 清单和 boundary audit。

报告必须写入：

- `RECOVERY_PROPOSAL_WRITTEN`；
- `DATA_OVERLAY_RECORDED`；
- `CORE_RECOVERY_V3_NOT_RUN`、`CORE_SCREEN_V3_NOT_RUN`、
  `FORMAL_EVALUATION_NOT_RUN`；
- `RECOVERY_APPROVAL_REQUIRED`；
- logical/request/retry 预期计数（实际请求计数必须为 0）；
- 旧 F2、旧 recovery、R2、设计和 config protection 结果。

若 13 条无法唯一冻结，或任何旧资产发生变化，写 `RECOVERY_PROPOSAL_BLOCKED`，不
创建 approval，不发请求。任务不 commit/push，完成后停止，等待负责人审查 proposal
并另行提供完整 recovery approval。
