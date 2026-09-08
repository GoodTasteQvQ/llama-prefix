# Safe-pair 审核纠偏后的执行顺序

## 当前结论

A 报告为 `BLOCKED_REVIEW_PROVENANCE_INCOMPLETE`，并发现旧 reviewer 生成器实际使用 regex/
semantic-score 启发式；B 报告为 `BLOCKED_IMPLEMENTATION_CONTRACT_MISMATCH`。因此旧 194 条
不能作为 construction gate。C 的 HarmBench 结果是 provisional，D 的 Gemma 结果是 runtime
probe pass；二者都没有启动正式实验。

## 会话安排

| 顺序 | 会话 | 任务书 | 当前决定 |
|---|---|---|---|
| 1 | 原 B 会话继续 | `paper1_server_codex_contract_repair_and_public_config_prompt_nohup.md` | 继续使用 B，先修复契约；完成后停止并保存报告 |
| 2 | 新 A2 会话 | `paper1_server_codex_safe_pair_re_review_prompt_nohup.md` | B2 报告通过后启动；全量真实双 subagent 重审 |
| 3 | 原 C 会话 | `paper1_server_codex_e1_overlap_preparation_prompt_nohup.md` | 当前已完成，暂不继续；source/review 固定后再重算 |
| 4 | 原 D 会话 | `paper1_server_codex_e2_gemma_runtime_probe_prompt_nohup.md` | 当前已完成，暂不继续；保留 probe 证据 |
| 5 | 原恢复会话 E | `paper1_server_codex_public_safe_pair_gate_recovery_prompt_nohup.md` | 暂停；等待 A2 新审核结果 |

## 依赖

1. B2 不能与 A2 同时写共享工作树；B2 完成后先同步报告、diff、测试证据，再启动 A2。
2. A2 若有效审核后 `executable>=250` 且 `actual_k>=30`，不执行 E，直接进入负责人对新 prepare
   和 runtime gate 的审阅。
3. A2 若有效但仍 `<250`，才允许把 E 交给服务器 Codex 执行；E 必须使用新的审核 ledger 和
   versioned public source/config，不能继续用旧 194 条。
4. A2 若再次 provenance blocked 或执行能力不足，停止所有 formal work，不能搜索更多数据集。
5. C 的 9 exact/16 near-match 结果在 safe source 最终固定后重新计算；D 的 probe 结果可以作为
   E2 资产/runtime 证据，但不能替代正式 smoke 或 E2 generation gate。

## 需要同步的证据

报告足以做当前决策；开始 B2/A2 前，服务器必须保留并可按路径读取：

- A 的 audit JSON、审计脚本、旧 ledger、A/B raw 目录和 reviewer 生成脚本；
- B 的 `.codex-temp/paper1_contract_semantic_strictness.patch`、测试建议和当前 dirty diff；
- C 的 provisional JSON、队列、exact exclusion、rotation preview 及其 SHA256；
- D 的 `gemma_runtime_probe_result.json`、探针脚本、日志、PID 和 `.exit`。

这些证据不需要全部提交 Git，但不能在服务器清理前丢失。正式论文复核前应把关键 JSON/hash
和最终代码 diff 同步回本机；不得同步模型权重或缓存。
