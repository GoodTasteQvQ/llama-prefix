# Paper 1 Core Judge Protocol v3 Direct JSON Report

Session: `A-judge-v3`
Protocol: `core-judge-protocol-v3-direct-json`
Completed phase: `0` only

## Result

`PROPOSAL_WRITTEN`

`DIRECT_JSON_IMPLEMENTATION_OFFLINE_PASS`

`DIRECT_JSON_PROBE_NOT_RUN`

`DESIGN_REVISION_V2.3_NOT_RUN`

`CORE_RECOVERY_V3_NOT_RUN`

`CORE_SCREEN_V3_NOT_RUN`

`FORMAL_EVALUATION_NOT_RUN`

`JUDGE_PROTOCOL_PROBE_FAIL`

`DESIGN_CHANGE_REQUIRED`

`OLD_F2_AND_OLD_RECOVERY_IMMUTABLE`

`READY_FOR_DIRECT_JSON_PROBE_APPROVAL`

`JUDGE_PROTOCOL_PROBE_FAIL` and `DESIGN_CHANGE_REQUIRED` describe the
historical v2 compatibility probe. They are not a v3 direct-JSON probe result.
No v3 probe, recovery, full rescore, screen, formal evaluation, E1, E2, E3,
analysis, human review, model load, or Judge request was started in this phase.

## Phase 0 Change

The proposal is retained at
`.codex-temp/paper1_core_judge_protocol_v3/proposal.md`.

`paper1_broadening.judge` now resolves the Judge protocol from
`runtime.judge` and keeps omitted-field behavior at
`enable_thinking=true`, `max_new_tokens=1296`, semantic
`</think>` splitting, and `strict_final_json_v1`. The only direct protocol is
an explicit three-field combination:

- `enable_thinking=false`
- `max_new_tokens=512`
- `parser` or `parser_mode` equal to `strict_direct_json_v1`

Mixed, partial, or implicit direct settings fail before runtime use. The normal
Judge and bounded non-evidence smoke path pass the resolved mode into
`Qwen3JudgeRuntime`.

In direct mode, the Qwen3 chat template receives `enable_thinking=false`; the
completion is parsed as one complete JSON object after surrounding whitespace
is trimmed. It must contain exactly `label` and `rationale`, use a domain-valid
label, and contain a nonempty rationale. Markdown, surrounding prose, malformed
JSON, duplicate/extra/missing keys, thinking markers (including semantic token
markers hidden by special-token decoding), invalid labels, and empty rationales
are rejected. The direct path does not use regex repair, substring extraction,
manual labels, semantic splitting, or the legacy parser fallback.

Judge identity and per-call diagnostics record `thinking_enabled`,
`thinking_final_split`, `parser`, and `max_new_tokens`. Direct-mode values are
`false`, `disabled_direct_final_json`, `strict_direct_json_v1`, and `512`.

## Offline Verification

All checks ran through `nohup` with
`CUDA_VISIBLE_DEVICES=0`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and
`HF_DATASETS_OFFLINE=1`, using
`/data/goodtaste_workspace/envs/llama-prefix/bin/python`. The runtime identity
is recorded at
`.codex-temp/paper1_core_judge_protocol_v3/phase0/runtime_identity.json`.

| Check | Result | PID / evidence |
| --- | --- | --- |
| Focused direct-Judge tests | `45 passed` | `2135290`; `phase0/focused_judge_direct_json_tests_v2.log/.pid/.exit` |
| Full `tests/paper1_broadening` | `85 passed` | `2135567`; `phase0/full_paper1_broadening_tests_v2.log/.pid/.exit` |
| Python compile | pass | `2135791`; `phase0/python_compile_v2.log/.pid/.exit` |
| `git diff --check` | pass | `2135848`; `phase0/git_diff_check_v2.log/.pid/.exit` |
| Runtime identity | pass | `2133774`; `phase0/runtime_identity_and_hashes.log/.pid/.exit` |
| Final implementation hashes | pass | `2135880`; `phase0/implementation_hashes_v2.log/.pid/.exit` |

The tests use recording tokenizer/model doubles. No check invokes a real model
loader or Judge endpoint, loads a model, or sends a Judge request.

## Accounting And Gate

`logical_identities=0`, `generation_requests=0`, `four_class_requests=0`,
`binary_requests=0`, `generation_retries=0`, and
`additional_judge_retries=0` for this phase. No run directory or direct-mode
run-specific config was created. The approval file
`.codex-temp/paper1_core_judge_protocol_v3/DIRECT_JSON_PROBE_APPROVAL.md` was
not used and remains required before Phase 1.

No conditional v2.3 design or config was created. The old behavior decoder,
rubric wording, labels, model, tokenizer, dtype, endpoint, directions, layers,
rho, seed, retry semantics, and missingness gate were not changed.

## Hashes And Boundary

Post-implementation source hashes are retained in
`.codex-temp/paper1_core_judge_protocol_v3/phase0/implementation_sha256.pre_report_v2.txt`:

| File | SHA-256 |
| --- | --- |
| `paper1_broadening/judge.py` | `76886c259a89102c6fbfeee86f8e94d00d0f20f5277fb1f391b77307c710b71f` |
| `paper1_broadening/config.py` | `f55fc81d073d45395e1b8a56cfa81c0dcdab7ad501e2955f1e739d2671e2c950` |
| `paper1_broadening/pipeline.py` | `5e1c2397efecfa42780c524b76bdd552544d9f14e01772cb68004a2738493954` |
| `paper1_broadening/smoke.py` | `5f2d674346d76d8cf1bb27112446bb2b54434952e7c4a367f7f6ccf79d5c3e4e` |
| `tests/paper1_broadening/test_judge_direct_json_protocol.py` | `ce3b90597cb55323b8ccbf377f32b56429015f324fe077837a73cfa9ce6c40c6` |

The unchanged canonical config
`configs/paper1_broadening/mbd_nm_v21.json` is
`3eed887051ad77f5e8b960f5c4d29973e4c0738c80e1b105714e6c5ce24d66c5`.
No v3 direct-mode run config exists, so no such config hash or run ID exists;
the direct-probe approval file is absent and therefore has no hash.

| Protected design | SHA-256 |
| --- | --- |
| `paper1_minimal_broadening_experiment_design_no_mistral.md` | `efaf55d7df2265bb68bca702c385e4ba1b9584415bb37a234dd16e0c1ffb51ad` |
| `paper1_minimal_broadening_experiment_design_v2.1_readable.md` | `398eda7172eab16cfd4fe899292f87079d474c5262c7dd7361892c70785d23d0` |
| `paper1_ccf_a_experiment_implementation_spec_gpt56.md` | `9cae99db1ff9ec91dc4222672f8bf643d35139f5d1b9af9d1606a26a003da2ee` |

Before edits, Phase 0 captured the dirty worktree and SHA-256 manifests for
three historical designs, 92 old-F2 files, nine old-recovery files, and 29 v2
probe files under
`.codex-temp/paper1_core_judge_protocol_v3/phase0/`. The final comparison and
boundary self-audit are retained alongside those manifests. Existing unrelated
worktree changes were preserved; no commit or push was made.
