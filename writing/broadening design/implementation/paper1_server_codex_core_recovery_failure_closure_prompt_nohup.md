# Core recovery failure closure：只读取证与变更决策记录

版本：`core-recovery-failure-closure-v1`；执行会话：`A-closure`。

## 目的

对已结束的 `paper1-core-fourclass-recovery-20260916-r13-a5a5936` 做一次独立、只读的失败收尾审计。确认 recovery 预算、请求身份、raw/diagnostics、计数、2% gate 和旧 F2 不变性均有证据支持，并给出下一步决策记录。该任务不恢复标签，也不开始任何正式实验。

## 必读输入

- `writing/broadening design/report/paper1_core_recovery_execution_report.md`
- `writing/broadening design/report/paper1_core_recovery_proposal_report.md`
- `writing/broadening design/report/paper1_core_screen_parse_forensic_report.md`
- `writing/broadening design/report/paper1_judge_observability_patch_report.md`
- `results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/recovery_judge_records.jsonl`
- `results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/recovery_request_manifest.jsonl`
- `results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/recovery_gate_result.json`
- 同一 run 的 `run_header.json`、`recovery_runtime_status.json`、`provenance_hash_manifest.json`、`judge_runtime_identity.json`、`judge_runtime_release.json`
- 旧 F2：`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`
- 三份原实验设计：
  - `writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md`
  - `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.1_readable.md`
  - `writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md`

## 不可违反的边界

1. 不发送任何 Judge 请求；不加载模型或 GPU；不运行 generation、screen、formal evaluation、analysis 或 human audit。
2. 不追加 recovery 请求，不使用 binary Judge，不重试，不改变 `strict_final_json_v1`、rubric、thinking/decoder、endpoint 或原 2% missing gate。
3. 不手工补标签，不从 generation completion 推断标签，不把 `PARSE_FAILURE` 改成任何有效类别。
4. 旧 F2 的全部文件只读，不覆盖、不合并、不回写；三份原实验设计和已批准科学 revision 只读。发现任何差异时只记录，不修复。
5. 不删除、重命名或重写既有结果、ledger、provenance 或报告；只新增本任务报告和 `.codex-temp/paper1_core_recovery_failure_closure/` 下的审计小文件。
6. 不 commit/push。保留工作树中其他会话和用户的既有修改。

## 审计内容

在项目目录执行前记录 `git status --short --branch`，并保存原实验设计相对当前 HEAD 的已有 diff/哈希。所有脚本、测试和汇总通过项目内 `.codex-temp` 运行，并使用 `nohup` 保存 PID、日志和 `.exit`；退出码为 0 仍需核对业务结果。

只读核对以下事实：

- recovery 恰好 13 行记录、13/13 请求完成、每条最多 1 次 four-class、binary/generation/additional retry 均为 0；
- 每条记录的 `request_sha256`、prompt/generation hash、response identity、schedule identity 与 manifest 和旧 F2 对应输入一致；无重复、隐藏 retry、漏记或跨 run 混入；
- 13/13 为 `PARSE_FAILURE`/`missing=true`，raw 与 diagnostics 均存在；raw 是否均含 `<think>`、均无 `</think>`/合法 JSON，并记录实际长度和 hash，不截取或改写 raw；
- `recovery_gate_result.json` 的 scheduled/parsed/missing 与逐行记录一致，明确列出超过 2% 的三个 cell；
- Judge runtime identity/release 与 run header 一致，旧 F2 保护哈希仍一致；
- 三份原实验设计相对执行前未被本任务修改。既有工作树差异必须在报告中单列为 pre-existing。

## 决策输出

报告必须明确写出：

- `CORE_RECOVERY_FAILURE_CLOSURE_PASS`（仅表示取证闭合）；
- `CORE_RECOVERY_BLOCKED`、`FORMAL_EVALUATION_NOT_RUN`、`OLD_F2_UNMODIFIED`；
- recovery 预算已耗尽，不能追加请求；
- 若证据确认是统一 semantic closing boundary 缺失，则写 `DESIGN_CHANGE_REQUIRED`，仅提出未来 proposal 必须回答的最小问题：是否调整 Qwen3 thinking/decoder 或输出协议、如何在新独立 run 验证、如何保持旧 run 不变。不得实现该变更、不得给旧 raw 重新解析、不得承诺 gate 通过；
- 若发现证据矛盾，只记录 `FORENSIC_INCONSISTENCY_FOUND` 及最小复核建议，不得自行修复结果。

## 交付

保存报告：`writing/broadening design/report/paper1_core_recovery_failure_closure_report.md`。

报告列出实际命令、审计脚本/输出、PID/log/exit、逐项结论、输入和输出 hash、保护文件 hash，以及本任务实际新增文件。完成边界自审后停止，并在报告中确认未发送请求、未加载模型、未修改代码/设计/结果。

## 完成标准

只有在所有只读核对完成、报告结论与证据一致、边界自审通过时才算完成；否则报告 `CLOSURE_INCOMPLETE` 并停止。不得以“审计通过”替代 Core gate，也不得启动任何后续实验。
