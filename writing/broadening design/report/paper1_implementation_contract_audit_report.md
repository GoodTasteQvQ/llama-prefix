# Paper 1 Implementation Contract Audit

审计日期：2026-09-08（UTC）；任务书：`broadening-implementation-contract-audit-v1`。
本次为只读审计。未修改共享实现、canonical config、旧 ledger、旧 run 或实验参数；未运行
修改后的 `prepare`，未启动模型、directions、screen、generation、Judge、analysis 或 human
packet。

## 结论

当前实现**部分兼容但未满足严格 public-semantic-pair-quality-v1 契约**。

- `frames.py` 已同时接受 `safe-pair-semantic-overlap-v1` 与
  `public-semantic-pair-quality-v1`，并保留旧 revision 的路径，因此旧 ledger 兼容性保留。
- 现有字段级 gate 会拒绝缺失 provenance、重复 agent、非法 normalized verdict、冲突
  adjudication；但不会解析并绑定两份 raw JSON 的 `pair_id`、`prompt_revision`、`verdict`，也
  不会在 split 层拒绝混用不同 `evaluation_frame_digest`。因此“严格等价接受”尚未被代码保证。
- canonical/default config 仍使用 `data/safe_pairs.json` 和旧 design revision
  `v2.1-ccf-a-target`。public source 只能通过临时 config 接入，不能视为 canonical loader 已切换。
- public 416-row 输出、整合 manifest、source bundle、LF-canonical manifest 候选/patch 和 public
  review ledger 均存在；旧 `data/safe_pairs.json` 未改。既有 public prepare 的 resolved config 指向
  public source/ledger，但其 revision 仍旧，且 source snapshot 未包含 public/new implementation
  资产。
- 本次离线测试结果为 `38 passed, 2 failed`。两项失败均由 `DESIGN_SNAPSHOT_PATHS` 引用仓库中
  不存在的旧 prompt 文件造成，不是通过放宽断言解决的问题。

结论状态：`BLOCKED_IMPLEMENTATION_CONTRACT_MISMATCH`；未报告 READY。

## Branch、HEAD 与 dirty 状态

```text
branch: stage3/impl-candidate
HEAD:   201757a8cb1f2805bc9dbdd11e39c6dd6c13bdc7
```

当前 tracked dirty diff：

| 文件 | 实际差异 |
|---|---|
| `paper1_broadening/frames.py` | `_semantic_status` 的允许 revision 从单一旧 revision 扩为旧 revision + `public-semantic-pair-quality-v1`；其余 provenance/verdict/adjudication 逻辑未变。 |
| `tests/paper1_broadening/test_frames_directions.py` | 新增 public revision 的接受/构造 gate 测试。 |

当前未跟踪相关资产：`data/safe_pairs_public_semantic_v1.json`、
`scripts/integrate_public_safe_pairs.py`、`data/external/semantic_harmful_harmless_v1/`
（含 integration manifest/source bundle）以及 `data/external/harmbench/`。本审计未覆盖、删除或
重置这些文件。

## `frames.py` semantic contract

相关位置：[frames.py](/data/goodtaste_workspace/llama-prefix/paper1_broadening/frames.py:153)
和 [frames.py](/data/goodtaste_workspace/llama-prefix/paper1_broadening/frames.py:459)。

已确认的兼容行为：

1. `review_mode == dual_codex_subagents_v1` 时要求完整 provenance 字段。
2. `review_prompt_revision` 接受 `safe-pair-semantic-overlap-v1` 和
   `public-semantic-pair-quality-v1`。
3. `adjudication_rule` 必须为 `unanimous_include_else_exclude`。
4. reviewer agent id 必须不同； normalized reviewer verdict 必须属于
   `include/exclude/uncertain`；只有双方 include 才返回 `SEMANTIC_INCLUDE`，否则按规则返回
   `SEMANTIC_EXCLUDE` 或 pending。
5. 非 dual 旧路径仍保留原 include/exclude 行为，未删除旧 revision 兼容入口。

严格性缺口：

- `reviewer_a_raw_output` / `reviewer_b_raw_output` 只被当作非空字符串，不解析 JSON，也不验证
  raw `pair_id`、raw `prompt_revision`、raw `verdict` 是否与外层 ledger 一致。
- `evaluation_frame_digest` 只检查非空字符串；没有跨 decision 的统一 digest 校验。
- 因此把 reviewer B raw JSON 的 revision、pair id 或 verdict 改掉，外层 normalized 字段不变时，
  仍可能得到 `SEMANTIC_INCLUDE`。这是代码契约缺口，不代表当前 409-row 实际 ledger 已被篡改。

实际 ledger 审计显示：409 records 的 prompt revision、adjudication rule、review mode、两侧
agent、raw/rationale/reviewed_at 和 evaluation digest 当前彼此一致；因此本次没有据实际数据报告
`BLOCKED_REVIEW_SCHEMA_MISMATCH`，但代码仍需补足 fail-closed 校验后才能证明未来 ledger 的一致性。

## Config、loader 与 prepare 路径

| 位置 | 实际值/行为 | 审计结论 |
|---|---|---|
| `paper1_broadening/config.py:69` | `safe_pairs_path = data/safe_pairs.json` | 仍指向旧 source |
| `configs/paper1_broadening/mbd_nm_v21.json:11` | `safe_pairs_path = data/safe_pairs.json` | canonical config 未切 public |
| `paper1_broadening/config.py:13` | `DESIGN_REVISION = v2.1-ccf-a-target` | 仍是旧 revision |
| `paper1_broadening/config.py:158` | `validate_config` 强制上述 revision | public design revision 不能直接加载 |
| `paper1_broadening/frames.py:464,467` | 按 config 的 `safe_pairs_path` 和 `overlap_decisions_path` 读取 | 临时 config 可接入 public source/ledger |
| `scripts/paper1_broadening.py` / `orchestration.py` | prepare 先 `load_config`/`validate_config`，再 `build_frames` | 不会自动替换 canonical path |

因此没有修改 canonical config，也没有运行 public 临时 config 的新 prepare。

既有 public run `results/paper1_broadening/public-semantic-pairs-20260906T105700Z/` 的实际记录：

- `resolved_config.json` 使用 `data/safe_pairs_public_semantic_v1.json` 和 absolute review ledger；
- `run_header.json` 的 design revision 仍为 `v2.1-ccf-a-target`，`code_commit=fdf68ca...`，
  `dirty=true`；
- frames 记录 source_count=416、unanimous executable=194、`actual_k=18`，gate 为
  `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`。

## Public source、manifest 与 LF-canonical 候选

以下文件存在且未被本次审计修改：

| 文件 | SHA256 / 内容核对 |
|---|---|
| `scripts/integrate_public_safe_pairs.py` | `4e965f7b21ff2315ffb5b132c04ecba45b1bf76999e1cadcb7c5932b8cdebbe8` |
| `data/safe_pairs_public_semantic_v1.json` | 416 rows；`009a58760b4b22b445a53b6ca52213af3ae98cb5f9dc04d0c2f70192231b3cce` |
| `data/external/semantic_harmful_harmless_v1/integration_manifest.json` | conversion output hash 与上行一致；`5129754c4b1602eb9889b250993c3a2b2ff54aacd26e2211eb770aa6da09019e` |
| `data/external/semantic_harmful_harmless_v1/source/source_manifest.json` | source manifest 存在；`cb775c39767441440af30cbf4a017b5d696c80814eb303ca8fe8ee08fff670a7` |
| `writing/broadening design/report/paper1_source_manifest_lf_canonical.json` | LF-canonical 候选存在；未替换实际 source manifest |
| `writing/broadening design/report/paper1_source_manifest_lf_canonical.patch` | 只建议把两个 LICENSE hash 从 CRLF 声明值 `cbd5af...` 改为实际 LF/Git hash `9e5f1b...` |

现有报告声明的 source manifest LICENSE hash 与工作树 LICENSE hash 仅有 CRLF/LF 换行差异；候选
manifest/patch 已保存，但本审计没有应用它们，也没有把候选当成正式 source 结果。

## Source snapshot 与 design revision

`paper1_broadening/orchestration.py:63-87` 的 `SOURCE_SNAPSHOT_PATHS` 只列出固定 tracked
模块、canonical config、运行脚本和 `stage3_pipeline/real_judge.py`，不包含：

- `scripts/integrate_public_safe_pairs.py`；
- `data/safe_pairs_public_semantic_v1.json`；
- public `integration_manifest.json`、source bundle、review ledger；
- 当前 public audit prompt/report。

因此 snapshot 不能包含实际 dirty/new public implementation 文件。更直接的失败证据是
`DESIGN_SNAPSHOT_PATHS` 仍引用以下不存在文件：

- `writing/broadening design/implementation/paper1_server_codex_implementation_prompt.md`
- `writing/broadening design/implementation/paper1_server_codex_run_prompt_nohup.md`
- `writing/broadening design/implementation/paper1_server_codex_machine_review_and_run_prompt_nohup.md`

这会在 `copy_source_snapshot()` 阶段 fail closed，阻止 fixture/source-snapshot 流程。

## Nohup 验证记录

环境：`/data/goodtaste_workspace/envs/llama-prefix/bin/python`；HF/Transformers/Datasets
offline；`TMPDIR/TMP/TEMP=$PWD/.codex-temp`；无模型调用。

| 检查 | PID | 日志 | `.exit` | 结果 |
|---|---:|---|---|---|
| `bash -n`（`scripts/**/*.sh`） | 367709 | `logs/paper1_broadening/bash-n-20260908T053041Z.log` | 同名 `.exit` | `0` |
| Python compile（`paper1_broadening scripts`，pycache 指向 `.codex-temp`） | 367806 | `logs/paper1_broadening/python-compile-20260908T053104Z.log` | 同名 `.exit` | `0` |
| `python -m pytest tests/paper1_broadening -q -p no:cacheprovider --basetemp .codex-temp/...` | 368511 | `logs/paper1_broadening/offline-tests-20260908T053349Z.log` | 同名 `.exit` | `1` |

测试日志末尾实际结果：`2 failed, 38 passed in 8.88s`。失败测试为：

- `test_fixture_e2e_runs_real_artifact_flow_and_stays_non_evidence`
- `test_run_source_snapshot_verification_fails_closed_on_worktree_change`

两者均因缺失 `DESIGN_SNAPSHOT_PATHS` 文件而在 `copy_source_snapshot()` 抛出
`BroadeningError`。未删测试、未放宽断言、未运行修改后的 prepare。

## 最小建议补丁（未应用）

建议补丁已保存于 `.codex-temp/paper1_contract_semantic_strictness.patch`，测试建议已保存于
`.codex-temp/paper1_contract_semantic_strictness_tests.txt`。内容仅建议：

1. 解析两份 raw JSON，要求 raw `pair_id`、`prompt_revision`、`verdict` 分别等于外层 ledger；
2. 在 split/build 层增加统一 `evaluation_frame_digest` 校验或明确 pending/fail-closed API；
3. 保留 legacy 和 public revision 两条接受路径，并保留重复 agent、非法 verdict、冲突裁决测试；
4. 另行修正/更新 `DESIGN_SNAPSHOT_PATHS`，并把 public source/manifest/ledger 纳入 snapshot
   contract；该部分本次未生成共享树补丁。

建议测试不得在本会话运行修改后的 prepare；只有显式批准并应用补丁后才运行。

## 剩余阻塞

1. **Config contract mismatch**：canonical/default loader 仍旧 source path 和旧 design revision。
2. **Semantic strictness gap**：raw provenance binding 与 cross-record digest 校验缺失。
3. **Snapshot contract failure**：design snapshot 引用了不存在文件，且未覆盖 public/new assets。
4. **Public construction gate blocked**：当前 public prepare 只有 194 executable pairs，`k=18<30`。
5. **LF-canonical manifest 未正式采用**：候选 patch 尚未应用或重新核验。
6. 测试套件当前不是全绿：`38 passed, 2 failed`，失败原因见上。

`FORMAL_EXPERIMENTS_NOT_RUN`
