# Paper 1 A2 evidence handoff report

版本：`a2-evidence-handoff-v2`。状态：`A2_HANDOFF_RECORDED`。日期：2026-09-14 UTC。

本次只完成既有 A2 核验结果的证据交付和有限收尾自查。没有重新执行 818 条身份检查、没有重新评判 409 条 pair、没有新增诊断样本或 reviewer request、没有运行 prepare、没有加载模型、没有启动正式实验。`FORMAL_EXPERIMENTS_NOT_RUN`。

## 1. 最终依据

完整审核 run 保留在：

`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-v2-20260908T111917Z/`

本次最终只使用以下两个文件作为结果依据：

- `rebuilt_summary.json`
- `public_pair_quality_decisions.v2.rebuilt.json`

`rebuilt_summary.json` 的 SHA256 为 `a5e284eadf437903ccb473aefd95021f374069dafbf29c7fb50a0b7409161830`；最终 rebuilt ledger 的 SHA256 为 `f5d9ce975a5214b2c8ffdd343497cf35ceb565d1904ee809d872ad284a4f34fe`，且 summary 中的 `ledger_sha256` 与之相符。

最终计数：

- source：416 rows
- exact overlap：7 rows；这些 rows 在 preliminary 阶段排除，因此无需 reviewer
- preliminary eligible：409 pairs
- request envelopes：818（每 pair A/B 各一条）
- final ledger：409 records，`COMPLETE`
- decisions：221 `include`、188 `exclude`、0 `pending`
- A verdict：293 `include`、100 `exclude`、16 `uncertain`
- B verdict：285 `include`、106 `exclude`、18 `uncertain`
- construction baseline：221 executable pairs，`actual_k=24`

旧 v1 的 194 条结果仍为 `INVALID_REVIEW_HISTORY`，没有进入本次最终输入。

## 2. 已执行核验的复用范围

本报告直接复用已经完成的 A2 专项核验：409 条 preliminary eligible pair 均有 A/B request；818 个真实 Codex thread/agent ID 全局唯一；每 pair 两侧身份不同；A/B 以严格串行方式执行；request envelope 保存独立 prompt、输入 hash、模型参数、raw event/output、隔离 workdir、read-only 和 peer-output 隔离证据。完整 raw/attempts 仍在服务器原路径，未用复制包替代它们。

实际执行脚本和证据位置：

- 审核 runner：`scripts/review_public_safe_pairs_v2.py`
- 单条 retry runner：`scripts/retry_public_safe_pair_request.py`
- rebuilt ledger：`scripts/rebuild_public_safe_pair_ledger_v2.py`
- run manifest/index：`.../manifest.json`、`.../progress.json`
- A raw：`.../raw/a/`
- B raw：`.../raw/b/`
- isolated workdirs：`.../isolated/`
- retry attempts：`.../retry_341_a/`

本次没有为了换任务名称再次逐条验证上述 818 条记录。当前新增的 bounded self-check 只验证最终 summary/ledger 的聚合计数、ledger hash、交付副本、旧 summary 标记、prepare 小文件存在性和 retry 文件存在性；脚本和日志位于：

`.codex-temp/paper1_a2_handoff_scope_check.py`

`writing/broadening design/report/evidence/paper1_a2_b2_delivery/a2/checks/a2-evidence-handoff-scope-check-20260914T140324Z.log`，对应 `.exit` 为 `0`。该检查明确标记为 `bounded handoff self-check; no per-request re-review or identity rerun`。

## 3. retry 和旧 summary 说明

原始 `summary.json` 位于 run 根目录，记录 `817 ok` / `1 pending`。这是 `safe-pair:341` 独立 retry 之前的历史统计，不是最终失败统计，也没有被改写或作为最终 ledger 输入。

`safe-pair:341` 的最终 A 结果来自独立真实 Codex retry：

`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-v2-20260908T111917Z/raw/a/safe-pair_341.a.retry.json`

对应 event 为 `retry_341_a/attempt-001.events.jsonl`。原始截断 envelope `raw/a/safe-pair_341.a.json` 仍保留，但 rebuilt ledger 使用 retry raw。7 条 exact-overlap source row 没有补审，也没有被错误写入 pending。

## 4. 固定协议和 prompt

协议修订原文件：

`writing/broadening design/review/paper1_public_safe_pair_review_protocol_revision.md`

其固定版本为 `public-semantic-pair-quality-v2`；只修复真实 Codex request provenance，不改变四项科学判定或 unanimous-include 规则。交付目录中保存了原协议副本和实际固定 prompt：

`writing/broadening design/report/evidence/paper1_a2_b2_delivery/a2/paper1_public_safe_pair_review_protocol_revision.md`

`writing/broadening design/report/evidence/paper1_a2_b2_delivery/a2/a2_review_prompt_v2.md`

固定 prompt 文件记录 system/developer/user template、对应 SHA256、实际模型 `gpt-5.6-terra`、Codex CLI `0.153.4`、reasoning `low`、read-only isolated invocation 和最多 100 次 429 retry 设置。每个具体 user prompt 的 hash 仍以原始 request envelope 为准。

## 5. 既有日志与 prepare 小文件

以下日志均为已有执行证据，本次没有重跑其中的步骤：

- rebuilt ledger：`logs/paper1_broadening/rebuild-public-safe-pair-ledger-v2-20260914T122122Z.log`，`.exit=0`
- offline tests：`logs/paper1_broadening/public-safe-pair-re-review-tests-v2-20260914T122401Z.log`，`.exit=0`，`43 passed in 11.52s`
- prior prepare：`logs/paper1_broadening/public-safe-pair-re-review-prepare-v2-20260914T122608Z.log`，`.exit=0`

此前 prepare 的小文件只作交付引用，未在本次 handoff 重新生成：

`results/paper1_broadening/public-semantic-pairs-v2-20260914T122608Z/`

交付了 `run_header.json`、`resolved_config.json`、`frames.json`、`plan.json`、`identity_plan.json` 和 `overlap_review_queue.json`。其中既有 prepare gate 为 `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`，221 executable pairs 对应 `actual_k=24`；这些文件不代表本次重新运行 prepare。

## 6. 交付目录

交付目录：

`writing/broadening design/report/evidence/paper1_a2_b2_delivery/a2/`

包含：

- `public_pair_quality_decisions.v2.rebuilt.json`
- `rebuilt_summary.json`
- `review_manifest.json`
- `review_progress.json`
- `paper1_public_safe_pair_review_protocol_revision.md`
- `a2_review_prompt_v2.md`
- `request_index.md`
- `prepare/` 下的既有 prepare 小文件
- `checks/` 下的有限收尾自查、既有 rebuild/tests/prepare 日志及 `.pid/.exit`
- `file_manifest.sha256`（SHA256：`a6760fc8361a1801ce604ba1ada75c5f41bd2b54b8eaee7d6145e9938a2c100f`）

完整 raw、attempts 和 818 个 request-level 证据没有复制或压缩，继续保留在上述原始 run 目录；`request_index.md` 列出其定位和 `safe-pair:341` retry 覆盖关系。

## 7. 有限收尾自查与停止边界

自查确认：没有误用旧 `summary.json` 作为最终统计；最终 rebuilt ledger 和 rebuilt summary 均已交付；没有改写原 source、原 ledger、原 raw 或旧 run；没有重复启动审核或 prepare；当前没有审核、prepare 或模型实验进程。没有发现需要阻断 A2 交付的证据矛盾。

当前工作树保持原有未提交 B2/A2 相关改动；本任务没有 commit/push。报告保存后停止。`FORMAL_EXPERIMENTS_NOT_RUN`。
