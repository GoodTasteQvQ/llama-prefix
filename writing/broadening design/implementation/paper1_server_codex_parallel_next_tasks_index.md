# 补充实验并行任务索引

当前 safe-pair gate：`executable=194`、`actual_k=18`，仍为
`BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`。在审核质量取证完成前，不执行此前的 source recovery
任务书。以下任务可并行，但每个会话必须使用自己的临时输出目录并保存报告。

这些会话只负责取证、预处理或 runtime 探针；它们不授权正式实验，也不应互相修改共享的 ledger、
source 或 canonical config。各会话完成后保留报告和日志，不在服务器端 commit/push。

| 会话 | 任务书 | 是否可现在执行 | 资源 | 报告 |
|---|---|---|---|---|
| A | `paper1_server_codex_safe_pair_review_quality_audit_prompt_nohup.md` | **必须先执行**；决定 recovery 是否可继续 | CPU/只读；两个独立诊断 subagent | `writing/broadening design/report/paper1_safe_pair_review_quality_audit_report.md` |
| B | `paper1_server_codex_implementation_contract_audit_prompt_nohup.md` | 可并行 | CPU/只读；发现问题只生成补丁 | `writing/broadening design/report/paper1_implementation_contract_audit_report.md` |
| C | `paper1_server_codex_e1_overlap_preparation_prompt_nohup.md` | 可并行；仅 provisional | CPU/只读；不发布最终 E1 40 条 | `writing/broadening design/report/paper1_e1_overlap_preparation_report.md` |
| D | `paper1_server_codex_e2_gemma_runtime_probe_prompt_nohup.md` | 可并行，但 GPU0 空闲时才执行 | 单卡 GPU0；小规模探针，不是正式 E2 | `writing/broadening design/report/paper1_e2_gemma_runtime_probe_report.md` |
| E | `paper1_server_codex_public_safe_pair_gate_recovery_prompt_nohup.md` | **暂缓**，等待 A 的结论 | 数据整合/双审核/prepare；不启动模型实验 | `writing/broadening design/report/paper1_public_safe_pair_gate_recovery_report.md` |

## 依赖关系

1. A 完成后：
   - `REVIEW_MECHANISM_INVALID`：停止 recovery，先修复协议/实现并重新审核受影响 rows；
   - `REVIEW_MECHANISM_CONCERN`：停止 recovery，负责人先决定是否修订提示并重新审核；
   - `REVIEW_MECHANISM_PLAUSIBLY_VALID`：仍不能开始实验，但可以执行 E，按原门槛寻找至少
     56 条新增 executable。
2. B 的补丁不能在 A 正在读取同一 checkout 时直接应用；由后续单独会话统一处理。
3. C 的 provisional 结果在 source 扩展后必须重新计算，不能直接作为 E1 READY。
4. D 的 PASS 只说明 Gemma 资产和 runtime 探针可用，不解除 safe-pair 或正式 E2 gate。
5. 只有 E 生成 `READY_FOR_CONSTRUCTION` 且真实 runtime gate 另行通过，才可交给正式运行任务书。

所有会话完成后，将各报告同步到本机，再由实验负责人统一审阅；任何报告缺失、退出码异常或
出现 `FORMAL_EXPERIMENTS_NOT_RUN` 以外的下游运行状态，都先停止汇总。
