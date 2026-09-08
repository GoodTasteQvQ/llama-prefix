# Paper 1 Safe-Pair Forensic Correction v1

审计日期：2026-09-08（Asia/Shanghai；取证时间戳使用 UTC）。本报告是对既有
`paper1_public_safe_pair_integration_report.md` 的新增更正报告；不覆盖或删除原报告、旧
manifest、旧 run、旧 ledger 或 `data/safe_pairs.json`。

## 结论

当前任务未达到可执行状态。source bundle 的两个 LICENSE manifest mismatch 已证明只是
换行格式问题，不是 source 文本内容被改写；Git `HEAD` blob 与 Linux 工作树均为同一份 LF
字节。实际双审核 ledger 与当前 `paper1_broadening/frames.py` schema 一致，未触发
`BLOCKED_REVIEW_SCHEMA_MISMATCH`。独立计数为 source_count=416、preliminary eligible=409、
unanimous executable eligible=194，故
`actual_k=min(80,(194-100)//5)=18`，最终 gate 为
`BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`。`FORMAL_EXPERIMENTS_NOT_RUN`。

## 环境与边界证据

- 工作目录：`/data/goodtaste_workspace/llama-prefix`
- branch：`stage3/impl-candidate`
- HEAD：`4f9f48d34c207c5096816b51132010dfbc4af993`
- dirty 状态：`paper1_broadening/frames.py`、`tests/paper1_broadening/test_frames_directions.py`
  已修改；`data/external/harmbench/`、公开 safe-pair 输出、integration manifest 和转换脚本
  为未跟踪用户/既有任务产物。本审计未重置、覆盖或清理这些改动。
- 当前解释器：`/data/goodtaste_workspace/envs/miniconda3/bin/python`，Python `3.13.13`。
  既有 prepare 使用的 formal interpreter 为 `/data/goodtaste_workspace/envs/llama-prefix/bin/python`，
  Python `3.10.20`。
- 取证脚本：`.codex-temp/paper1_forensic_correction_audit.py`
- 取证汇总：`.codex-temp/paper1_forensic_correction_audit.json`
- 本次 nohup 记录：PID `312579`；日志
  `logs/paper1_broadening/forensic-correction-audit-20260908T003826Z.log`；`.exit` 同名文件，
  exit `0`。审计完成后无持续中的本任务进程。

## Source bundle 哈希核对

source 目录：`data/external/semantic_harmful_harmless_v1/source/`。每个文件均执行了 Linux
工作树字节、`git show HEAD:<path>` 字节、LF-normalized 字节和 CRLF-transcoded 字节比较。

| 文件 | manifest 声明 | 工作树 SHA256 | Git blob SHA256 | 结论 |
|---|---|---|---|---|
| `matched_pairs.json` | `d066ddd4a8005271d21f269aacc4cc30bfb5d2f1d7004f3f37004e42f63f5225` | 同左 | 同左 | 一致 |
| `semantic_harmful_README.md` | `2157ee61e1e2b180f2c8ba5c702566bb7f29b3f41155368d673b2c65d7cf87a3` | 同左 | 同左 | 一致 |
| `semantic_harmless_README.md` | `ec4c6c98e47c723d4ba73c91e2d075d50784955895c6623ab76f6d5b0ea8054c` | 同左 | 同左 | 一致 |
| `semantic_harmful_LICENSE` | `cbd5af318286b74656f145dff5091907cc23d6d8c9ad09e0291ec2497792ba41` | `9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94` | 同左 | 声明值仅匹配 CRLF 变体 |
| `semantic_harmless_LICENSE` | `cbd5af318286b74656f145dff5091907cc23d6d8c9ad09e0291ec2497792ba41` | `9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94` | 同左 | 声明值仅匹配 CRLF 变体 |
| `source_manifest.json` | 不自哈希 | `cb775c39767441440af30cbf4a017b5d696c80814eb303ca8fe8ee08fff670a7` | 同左 | 一致 |

所有 LICENSE 的实际统计为 `bytes=18656, crlf=0, lf=395, lone_cr=0`。将当前 LF 字节转为
CRLF 后，SHA256 才变为 manifest 声明的 `cbd5af...`。因此真实原因是 **manifest 录入了
CRLF/LF 换行差异**，不是内容差异，也不是工作树漂移。README 和 matched-pairs 没有此
问题。

按要求未改写 source manifest、`matched_pairs.json`、README 或 LICENSE。已生成可审阅的
LF-canonical 修复候选与补丁：

- `writing/broadening design/report/paper1_source_manifest_lf_canonical.json`
- `writing/broadening design/report/paper1_source_manifest_lf_canonical.patch`

补丁仅把两个 LICENSE 的旧哈希 `cbd5af...` 替换为 Git/LF canonical 哈希 `9e5f1b...`，
并在本报告中记录换行原因；未静默覆盖旧 manifest，也未 commit/push。

## Review ledger 与 schema

实际 ledger：`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-20260906T104100Z/public_pair_quality_decisions.json`
，SHA256=`c0a64f2e95980d2527178c8fc2bf6cd0818644a5129170f1f46469db5b36d9b9`。

- records：409，pair_id 唯一；prompt revision：`public-semantic-pair-quality-v1`（409）。
- adjudication rule：`unanimous_include_else_exclude`（409）；review mode：
  `dual_codex_subagents_v1`（409）。
- reviewer A：`/root/review_a`，model `gpt-5`，include 371、exclude 38。
- reviewer B：`/root/review_b`，model `gpt-5`，include 229、exclude 180。
- 固定裁决：include 194、exclude 215；uncertain 0、失败 0。
- evaluation frame digest：`d5e6a2d3b75c4c85ec5bebf89810e6a3d1c09a9948be88e22a2db99c5c6ce764`（409）。
- raw output、rationale、reviewed_at 均为 409/409；A/B raw 文件分别 409 个，共 818 个，
  位于 `reviewer_a/subagent_raw/` 和 `reviewer_b/subagent_raw/`，无 unexpected raw 文件。

当前 [frames.py](../../../paper1_broadening/frames.py) 的 `_semantic_status` 同时接受
`safe-pair-semantic-overlap-v1` 与 `public-semantic-pair-quality-v1`，并要求完整 provenance、
不同 agent id、固定 adjudication rule。因此本 ledger 的 revision/schema **一致**；不报告
`BLOCKED_REVIEW_SCHEMA_MISMATCH`，也没有修改 ledger 伪造兼容。

## 独立重算与 prepare

逐条读取最终 frames 记录并按 exact-evaluation-overlap 标记独立重算：

| 计数 | 值 |
|---|---:|
| source_count | 416 |
| preliminary eligible（无 exact duplicate reason） | 409 |
| unanimous executable eligible | 194 |
| actual_k | `min(80,(194-100)//5)=18` |
| safe_pair_split.gate | `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS` |

最终 prepare 目录：`results/paper1_broadening/public-semantic-pairs-20260906T105700Z/`；
`frames.json` SHA256=`67a8435ce003ce1879dc5a21434f7950cd074c821b1f1527f778122011730792`。
该 prepare 的实际 safe-pair split 记录了 416 source rows 和 194 executable rows；其
`preliminary_eligible_count` 字段按 post-review split 写成 194，不能替代上表按逐条
exact-overlap 的 preliminary=409 独立重算。prepare 日志显示 exit `0`，但 gate 被阻塞，
没有 construction folds 或 development 分配，不能降级为 READY。

相关既有 nohup 证据：最终 prepare PID `4119141`，日志
`logs/paper1_broadening/public-pair-prepare-20260906T105642Z-4119138-13106.log`，`.exit=0`；
双审核合并 PID `4119033`，日志 `logs/paper1_broadening/public-pair-review-combine-20260906T105603Z-4119030-16706.log`，
`.exit=0`；离线测试 PID `4115427`，日志
`logs/paper1_broadening/public-pair-tests-20260906T104320Z-4115424-4921.log`，`.exit=0`，
`40 passed in 9.15s`。

## 未运行项目与后续修订

`FORMAL_EXPERIMENTS_NOT_RUN`。本次没有启动 GPU 模型加载、directions、screen、generation、
Judge、analysis 或 human packet；没有重新审核 pair，没有改变 safe-pair 数据，没有使用旧
`data/safe_pairs.json` 回退，也没有用 JBB、HarmBench 或新生成文本补齐。

后续要获得可执行 construction gate，至少需要：

1. 由数据维护者确认并正式采用 `paper1_source_manifest_lf_canonical.json`（或提供与旧声明
   `cbd5af...` 真正对应的原始 CRLF 文件），然后重新记录 source-manifest provenance；
2. 保持 `public-semantic-pair-quality-v1` ledger 和当前完整 schema，不修改历史 ledger；
3. 重新 prepare 后仍须有至少 250 个 executable pairs 才能满足 `k>=30`（本次只有 194，
   因而 actual_k=18），并在报告中记录新的 frames digest、resolved config 和 run 证据；
4. 如需改变计数或构造设计，必须先提交明确的设计/任务书修订，不能降低 `actual_k` 门槛、
   混用旧 AI safe-pair 数据，或在 gate 阻塞时启动正式实验。
