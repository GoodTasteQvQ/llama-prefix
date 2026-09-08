# Safe-Pair Review Quality Audit

审计版本：`safe-pair-review-quality-audit-v1`
审计日期：2026-09-08（Asia/Shanghai）
工作目录：`/data/goodtaste_workspace/llama-prefix`

## 结论

**`BLOCKED_REVIEW_PROVENANCE_INCOMPLETE`**

不能把现有 194 条 executable safe pairs 当作已通过质量 gate。409 条 preliminary eligible 的
ledger/raw 映射和合并规则可以重算，但保存的证据不是请求级原始审核证据：没有每条请求实际发送的
完整 prompt、输入 frame 内容/哈希、system/developer 约束、temperature、seed、model revision、
context window，或请求级 reviewer 隔离证明。因此按任务书的优先规则，不启动 30 条诊断样本。

同时发现一个严重机制红旗：保存的 reviewer 生成脚本使用本地 regex 与 semantic-score 阈值直接
合成 verdict，没有 Codex/model API 调用；ledger 却把结果标成 Codex reviewers。这一证据若有完整
请求 provenance，应判为 `REVIEW_MECHANISM_INVALID`；在当前证据条件下，正式分类仍是上面的
`BLOCKED_REVIEW_PROVENANCE_INCOMPLETE`，不得据此恢复审核 gate。

## 取证范围与环境

- branch：`stage3/impl-candidate`；当前 HEAD：`201757a8cb1f2805bc9dbdd11e39c6dd6c13bdc7`。
- 纠偏报告：`writing/broadening design/report/paper1_public_safe_pair_forensic_correction_report.md`。
- 当前 ledger：`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-20260906T104100Z/public_pair_quality_decisions.json`，SHA256 `c0a64f2e95980d2527178c8fc2bf6cd0818644a5129170f1f46469db5b36d9b9`。
- 旧 ledger：`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-20260906T103955Z/public_pair_quality_decisions.json`；409 条，SHA256 与当前不同。
- source：`data/safe_pairs_public_semantic_v1.json`（416 条）；原始 bundle `matched_pairs.json` SHA256 `d066ddd4a8005271d21f269aacc4cc30bfb5d2f1d7004f3f37004e42f63f5225`。
- preliminary frames：`.codex-temp/public-semantic-pairs-preliminary/frames.json`，`frame_digest=d5e6a2d3b75c4c85ec5bebf89810e6a3d1c09a9948be88e22a2db99c5c6ce764`。
- 最终 prepare frames 文件 SHA256 `67a8435ce003ce1879dc5a21434f7950cd074c821b1f1527f778122011730792`；其 digest 为 `8a1ad4...`，这是审核状态写入后的整体 frames digest，不是 ledger 所引用的 preliminary evaluation digest。
- Python：`/data/goodtaste_workspace/envs/llama-prefix/bin/python` 3.10.20；离线变量按任务书设置；未加载模型。
- 审计脚本：`.codex-temp/paper1_safe_pair_review_quality_audit.py`；输出：`.codex-temp/paper1_safe_pair_review_quality_audit.json`。
- 审计 nohup：PID `374250`；日志 `logs/paper1_broadening/safe-pair-quality-audit-20260908T055118Z.log`；`.exit=0`。
- schema 测试 nohup：PID `372765`；日志 `logs/paper1_broadening/safe-pair-quality-audit-schema-tests-20260908T054635Z.log`；`.exit=0`；`7 passed in 1.23s`。

## 独立重算

从 source、preliminary frames、ledger 和 near-match queue 重新 join，而不是抄纠偏报告：

| 项目 | 重算值 |
|---|---:|
| source rows | 416 |
| exact evaluation overlap 排除 | 7 |
| preliminary eligible | 409 |
| ledger records / unique pair_id | 409 / 409 |
| reviewer A include / exclude | 371 / 38 |
| reviewer B include / exclude | 229 / 180 |
| 双方 include / A-only / B-only / 双方 exclude | 194 / 177 / 35 / 3 |
| final include / exclude | 194 / 215 |
| adjudication rule 严格匹配 | 409 / 409 |
| raw JSON 文件 | 409 A + 409 B = 818 |

双方混淆表为：

|  | B include | B exclude |
|---|---:|---:|
| A include | 194 | 177 |
| A exclude | 35 | 3 |

agreement=`197/409=0.4816625917`；边际纳入率 A=`0.9070904645`、B=`0.5599022005`；expected
agreement=`0.5487712292`；Cohen's kappa=`-0.1487241991`。

## 分歧 strata

- near-match queue：39 个 unique preliminary pairs，11 agreement、28 disagreement，agreement `0.2821`，kappa `-0.3188`。
- 非 near-match：370，186 agreement、184 disagreement，agreement `0.5027`，kappa `-0.1311`。
- source-index quartiles Q1/Q2/Q3/Q4：kappa 分别 `-0.0787/-0.1622/-0.1368/-0.1005`；不是原数据语义类别。
- semantic-score bins：`.6-.7` 为 149 条、kappa `-0.0815`；`.7-.8` 为 252 条、kappa `-0.1531`；`.8-.9` 为 8 条、kappa `0.0`。
- source 与 ledger 没有 category 字段，无法诚实地产生 category strata；报告明确记为 unavailable，而不是猜测类别。

## Rationale 抽样

已从 A-only 抽 20、B-only 抽 20、双方 include 抽 10、双方 exclude 抽全部 3；摘要和 pair 原文保存在
`.codex-temp/paper1_safe_pair_review_quality_audit.json`，未改写 raw。观察结果：

- A-only 177 条：146 条仅 B 把 `semantic_pair_is_comparable` 判为 false；31 条 B 同时判 harmless 非 benign 与 comparable false。
- B-only 35 条：35 条均为 A 把 harmless 判为非 benign，而 B 判 benign。
- 双方 include 194 条：四个布尔字段均为 true，rationale 高度模板化。
- 双方 exclude 仅 3 条：A 均记录 harmless 非 benign、comparable true；B 均记录 comparable false，其中 2 条 B 也记录 harmless 非 benign。
- 具体抽样例：`safe-pair:17`（bomb / paper plane，A include、B exclude，near-match）；`safe-pair:0`（drug-use song / poem，A exclude、B include，near-match）；`safe-pair:10`（credit-card fraud / fake card number，双方 exclude）。

这些模式显示主要争议集中在 harmless benignity 与 pair comparability，而不是 ledger 合并计算错误；但不能据此证明真实审核 prompt 曾按设计发送。

## Prompt、输入与 reviewer provenance

ledger 统一记录：`review_prompt_revision=public-semantic-pair-quality-v1`（409）、
`review_mode=dual_codex_subagents_v1`（409）、`adjudication_rule=unanimous_include_else_exclude`
（409）、evaluation digest 为上述 preliminary digest（409）；A/B agent id 分别固定为
`/root/review_a`、`/root/review_b`，model 字段均为 `gpt-5`。raw JSON 可解析，文件名与 pair_id、
verdict 一一对应；B 目录另有 manifest，A 目录没有 manifest。B manifest 明确写的是
`independent machine-assisted text review; no network, models, or repository code run`，而 ledger
却写 `dual_codex_subagents_v1`、model `gpt-5`，构成直接的 review-mode/model provenance 矛盾。
B raw manifest 时间为 `10:50:36Z`，A raw 文件时间约 `10:55:04Z`，combine 约 `10:56:03Z`。

但是 raw 文件只是模型输出 JSON，只有八个输出字段（pair_id、verdict、四个布尔判断、rationale、
prompt_revision），不包含请求 prompt 或请求参数。缺失项：

`full_prompt_text_per_request`、`request_input_frame_content_or_hash_per_request`、
`system_developer_constraints_per_request`、`temperature_per_request`、`seed_per_request`、
`model_revision_per_request`、`context_window_per_request`、`request_level_isolation_evidence`。

旧 ledger 的 reviewer models 是 `gpt-5.6-terra/gpt-5.6-terra`，当前 ledger 是 `gpt-5/gpt-5`；
该 revision/model 漂移未在请求级 provenance 中解释，进一步阻止质量确认。

## 机制实现红旗

只读检查以下既有脚本和日志：

- `.codex-temp/generate_reviewer_a.py`
- `.codex-temp/generate_public_pair_reviews.py`
- `.codex-temp/combine_public_reviews.py`
- `logs/paper1_broadening/public-pair-reviewer-a-20260906T105504Z-4118818-28527.log`
- `logs/paper1_broadening/public-pair-dual-review-20260906T105116Z-4117890-16033.log`
- `logs/paper1_broadening/public-pair-review-combine-20260906T105603Z-4119030-16706.log`

两个 generator 明确包含 regex safety 规则与 semantic-score 阈值；combine 仅读取 JSON 并写 ledger，
没有 Codex/model API 调用。日志只报告计数，不提供 thread/request/raw prompt 证据。这与 ledger 的
`dual_codex_subagents_v1`、`gpt-5` 身份声明不相称，是潜在 `REVIEW_MECHANISM_INVALID` 证据，不能被
当前 provenance 缺口掩盖或当作可接受实现。

## 有限诊断与停止

规定的 30 条诊断样本（A-only 10、B-only 10、双方 include 5、双方 exclude 5）**未启动**；没有新
Codex subagent、没有诊断 raw JSON，也没有修改旧 ledger。原因是原始审核请求 provenance 不完整，
触发 `BLOCKED_REVIEW_PROVENANCE_INCOMPLETE`。没有启动 directions、screen、generation、Judge、
analysis 或 human packet，也没有执行公开 source 恢复或正式实验。

旧 ledger、旧 run、旧 source 与 `data/safe_pairs.json` 均未改动；本审计只新增 `.codex-temp` 取证输出和
本报告。后续任何重新审核必须先保存逐请求 prompt/input/参数/isolation evidence，并使用新的 audit/review
输出目录，不能覆盖历史 ledger。

**FORMAL_EXPERIMENTS_NOT_RUN**
