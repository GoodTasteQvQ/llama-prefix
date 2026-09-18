# Paper 1 Core Judge Protocol v2 Rescore Report

Session: `A-judge-v2`
Protocol: `core-judge-protocol-v2-rescore-v2`
Phase completed: `0`; Phase 1 executed through the second fixed input and failed

## Decision

`PROPOSAL_WRITTEN`

`JUDGE_PROTOCOL_PROBE_FAIL`

`DESIGN_CHANGE_REQUIRED`

`DESIGN_REVISION_V2.2_NOT_RUN`

`CORE_RECOVERY_V2_NOT_RUN`

`CORE_SCREEN_V2_NOT_RUN`

`FORMAL_EVALUATION_NOT_RUN`

`OLD_F2_AND_OLD_RECOVERY_IMMUTABLE`

`CORE_RECOVERY_FAILURE_CLOSURE_PASS` is a historical evidence status only. It is
not a new recovery result, probe result, screen result, or A/S decision.

This report stops after the Phase-1 probe failure. No recovery, full rescore,
behavior generation, formal evaluation, E1, E2, E3, analysis, or human review
was started. Phase 2 was not entered.

## Phase 0 Scope

The implementation changes only the four-class Judge's `max_new_tokens` lookup:

- `paper1_broadening.judge.judge_max_new_tokens()` reads
  `runtime.judge.max_new_tokens` from the run config and defaults to `1296` when
  that field is absent.
- `Qwen3JudgeRuntime` stores the validated value, passes it to `generate()`, and
  writes it to the Judge identity as `max_new_tokens`.
- The normal screen Judge and the non-evidence smoke Judge pass the run-config
  value into the runtime. Existing callers that do not pass a value retain the
  `1296` constructor/default behavior.

No parser, semantic `</think>` split, rubric text, label domain, retry rule,
binary-Judge behavior, model, endpoint, dtype, direction, layer, data, dose,
behavior decoder (`512`), or 2% missing gate was changed. No `4096` run-specific
config was created, and no v2.2 design file was created.

The phase-0 proposal is [proposal.md](../../../.codex-temp/paper1_core_judge_protocol_v2/proposal.md).
It states that `4096` is only a future, approval-gated protocol value and that
v2.1, old F2, old recovery, old ledgers, and old dose decisions remain read-only.

## Phase 1 Execution

The first approval revision was rejected before any request because one fixed
request hash had 65 characters. That `PROBE_APPROVAL_INVALID` evidence is
preserved under `phase1/approval_validation.json`. The active corrected
approval was verified before model load: status `PROBE_APPROVED`, SHA256
`f8ea173eb296f3a04f64f2d47b4466dbbcff967308625325999482c4cd385d23`.
The required llama31/rogue/layer-11/rho-0.5 binding is the approved 64-character
value `342036f7951ea28cba7792291fb5569e1ff7666d54dfa0417783f4c6cb6ed116`.
All three phase-0 code hashes matched, so `PROBE_CODE_HASH_MISMATCH` did not
occur. Corrected approval evidence is
`phase1/corrected_approval_validation.json` and
`phase1/corrected_approval_preflight_20260917T141859Z.log` (PID `2016210`,
exit `0`).

The independent probe run is
`results/paper1_broadening/core-judge-protocol-probe-20260917T141934Z-1a746872/`.
Before dispatch it read exactly the six approval-bound old-F2 completions and
prompts, with no old Judge label read. Its six `inputs/*.json` artifacts,
`request_manifest.jsonl`, `pre_request_validation.json`, and
`probe_runtime_config.json` record source, request, and payload hashes.

After explicit interactive authorization to use GPU 1, all post-authorization
Phase-1 processes used `CUDA_VISIBLE_DEVICES=1` and all three Hugging Face
offline flags. GPU preflight passed with exactly one logical GPU and 80,606 MiB
free (`phase1/probe_gpu1_final_preflight_20260917T142021Z.log`, PID `2016832`,
exit `0`). The one sequential Judge process, PID `2017192`, used
`enable_thinking=true`, `max_new_tokens=4096`, greedy decoding, one beam,
binary Judge `0`, generation retry `0`, and additional Judge retry `0`.

| Fixed input | Outcome | Four-class calls | Stop reason | Generated tokens |
|---|---|---:|---|---:|
| 1: qwen25/rogue/layer 9/rho 1.0 | pass | 1 | `eos_token` | 1,520 |
| 2: qwen25/contrastive/layer 9/rho 0.75 | fail | 1 | `max_new_tokens` | 4,096 |
| 3-6 | `NOT_SENT_AFTER_FAILURE` | 0 | not applicable | 0 |

The second fixed input did not emit semantic `</think>` before the approved
4,096-token limit. It therefore has `PARSE_FAILURE`, no strict final JSON, no
label, and no rationale. Its raw completion, diagnostics, hashes, 4,096-token
count, and `max_new_tokens` stop reason are retained. No OOM, hidden retry,
binary request, generation retry, or additional Judge retry occurred. The
runner immediately stopped remaining requests and released the Judge, yielding
`JUDGE_PROTOCOL_PROBE_FAIL` and `DESIGN_CHANGE_REQUIRED`. It did not increase
the limit to 8192 or any other value.

The run records `logical_identities=6`, `requests_sent=2`, `four_class_calls=2`,
`binary_calls=0`, `generation_retries=0`, and
`additional_judge_retries=0` in `terminal_accounting.json`. Runtime identity,
Judge identity/release, raw/final output, diagnostics, process PID/log/exit,
and per-record response hashes are retained in the independent run directory.
`artifact_hashes.sha256` covers its 28 non-manifest artifacts, including all
input, request, response, diagnostics, identity, release, and process evidence.

| Action | PID | Exit | Evidence |
|---|---:|---:|---|
| Original approval/code preflight | `2003149` | `0` | `phase1/approval_preflight_20260917T132401Z.log` |
| Original format check | `2007945` | `0` | `phase1/approval_request_hash_format_20260917T134302Z.log` |
| Corrected approval/code preflight | `2016210` | `0` | `phase1/corrected_approval_preflight_20260917T141859Z.log` |
| Independent probe prepare | `2016448` | `0` | `phase1/corrected_probe_prepare_20260917T141934Z.log` |
| GPU 1 final preflight | `2016832` | `0` | `phase1/probe_gpu1_final_preflight_20260917T142021Z.log` |
| Sequential probe execution | `2017192` | `20` | `probe_execute.log` and `probe_execute.exit` in the probe run |
| Failure evidence inspection | `2018900` | `0` | `phase1/probe_failure_result_inspection_20260917T142727Z.log` |

The two original no-request prepare wrappers (PIDs `2006556` and `2007368`)
remain as process evidence. The first had a login-shell import failure; the
second found the 65-character approval defect. Its only created artifact was
an independently verified empty directory, later removed with exact-path
`rmdir`. Neither wrapper loaded a model, created a Judge record, or sent a
request.

## Offline Verification

The Phase-0 offline verification commands used the required Python executable,
`CUDA_VISIBLE_DEVICES=0`, and `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`, and `HF_DATASETS_OFFLINE=1`. They were launched
through `nohup`; no Phase-0 test loads a model or sends a Judge request.

| Check | Result | Evidence |
|---|---|---|
| Focused Judge/config tests | `15 passed` | `phase0/focused_judge_config_tests.log`, PID `1981816`, exit `0` |
| Full `tests/paper1_broadening` | `60 passed` | `phase0/full_paper1_broadening_tests.log`, PID `1982111`, exit `0` |
| Python compile | pass | `phase0/python_compile.log`, PID `1982425`, exit `0` |
| `git diff --check` | pass | `phase0/git_diff_check.log`, PID `1982773`, exit `0` |

The focused tests prove all required implementation facts without a real request:

- omitted Judge configuration yields `1296`;
- explicit in-memory run configuration yields `4096`;
- mocked `generate()` receives the selected value;
- the parsed four-class result retains valid label/rationale and one call;
- mocked screen execution passes `4096` to Judge construction and records it in
  `run_header.json.loaded_identities.judge`;
- strict parser and Judge identity fields remain `strict_final_json_v1` and
  `thinking_enabled=true`.

`phase0_raw=NOT_APPLICABLE_NO_JUDGE_REQUEST`,
`phase0_release=NOT_APPLICABLE_NO_RUNTIME_LOAD`, and diagnostics are limited to
offline-test and boundary evidence. See
`phase0/phase0_nonrequest_accounting.txt` and `phase0/runtime_identity.json`.

## Approval Gate

At Phase 0, the following fixed approval files were absent:

| File | State |
|---|---|
| `.codex-temp/paper1_core_judge_protocol_v2/PROBE_APPROVAL.md` | `NOT_PRESENT` |
| `.codex-temp/paper1_core_judge_protocol_v2/RECOVERY_APPROVAL.md` | `NOT_PRESENT` |
| `.codex-temp/paper1_core_judge_protocol_v2/FULL_RESCORE_APPROVAL.md` | `NOT_PRESENT` |

Their checked state is saved in
`phase0/approval_gate_status.txt`. Therefore no four-class probe request was
issued, no fixed six-input manifest was selected, and no later phase is allowed.

The original Phase-1 approval artifact remains preserved as historical
format-validation evidence. Its corrected replacement, SHA256
`f8ea173eb296f3a04f64f2d47b4466dbbcff967308625325999482c4cd385d23`,
passed all pre-request checks and authorized the actual probe. The probe failed
on fixed input 2; therefore no Phase-2 design/config or recovery approval state
may be created.

## Hashes And Immutability

Pre-existing worktree state, staged/unstaged diffs, untracked path hashes, Git
HEAD, and all historical target hashes were saved before implementation under
`.codex-temp/paper1_core_judge_protocol_v2/phase0/preexisting_state/`.

The final comparison is `MATCH` for all protected targets:

| Protected target | Files | Result |
|---|---:|---|
| Three original designs | 3 | `MATCH` |
| Old F2 | 92 | `MATCH` |
| Old recovery | 9 | `MATCH` |

Authoritative comparison evidence is
`phase0/immutable_hash_comparison_v3.txt`, with per-file before/after manifests
and empty diffs adjacent to it. The protected v2.1 design hash is
`398eda7172eab16cfd4fe899292f87079d474c5262c7dd7361892c70785d23d0`.

Relevant post-change hashes are:

| File | SHA256 |
|---|---|
| `paper1_broadening/judge.py` | `5cc901bb3a9453f85d7acc42a3981cf6f47216313522371a840008c8d709b86d` |
| `paper1_broadening/pipeline.py` | `336979978f91dae36143b247255604b51417d79edfdad601e75717401f2c6813` |
| `paper1_broadening/smoke.py` | `67d8a72d865864f75e8d4f709da3d274d71b5506142fca0fc24dc7e7ed7aa051` |
| `tests/paper1_broadening/test_run_readiness.py` | `edb7a48f0c92c6301ffc0ebf3b4098c76a23154e28a21877bf8cbd0434636d28` |
| `tests/paper1_broadening/test_judge_max_new_tokens_config.py` | `9e389207d1394b6221db376e43aecad87e4898787fd0489fb3ec85557f6bdcd5` |
| phase-0 proposal | `6fe52b5a8f21d31e020421efdb567a5212df5da1989bdf96ff783b478e6370d7` |

The complete hash lists are under `phase0/`.

## Worktree Boundary

The pre-existing dirty worktree was preserved as captured in
`phase0/preexisting_state/preexisting_git_status.txt` and its exact patches.
It includes unrelated modifications to `config.py`, `frames.py`,
`orchestration.py`, `test_frames_directions.py`, source-manifest reports, and
the pre-existing untracked data/config/script/report set. None was reverted or
edited by this phase.

This phase added or modified only:

- `paper1_broadening/judge.py`
- `paper1_broadening/pipeline.py`
- `paper1_broadening/smoke.py`
- `tests/paper1_broadening/test_run_readiness.py`
- `tests/paper1_broadening/test_judge_max_new_tokens_config.py`
- this report and `.codex-temp/paper1_core_judge_protocol_v2/` evidence

Phase 1 additionally created only its temporary runner/audit evidence and the
independent non-formal probe run described above. It did not change project
source, a canonical configuration, a v2.1 design, old F2, old recovery, or an
old ledger.

No canonical config, old run, old recovery, historical design, or result ledger
was changed.

## Runtime And Process Evidence

Runtime identity is recorded in `phase0/runtime_identity.json`: Python is
`/data/goodtaste_workspace/envs/llama-prefix/bin/python`, Python `3.10.20`,
`CUDA_VISIBLE_DEVICES=0`, and all three Hugging Face offline flags are `1`.

The Phase-1 runtime/release identity is instead in the independent probe run:
`runtime_identity.json`, `judge_identity.json`, and `judge_release.json` record
the required Python, offline environment, physical GPU 1/logical `cuda:0`,
float32 Qwen3 Judge, `enable_thinking=true`, `max_new_tokens=4096`, and complete
Judge release. Phase-1 PID/log/exit triples are retained under `phase1/` and in
the probe run itself.

Every phase-0 command has a PID, log, and `.exit` entry in
`phase0/process_evidence_manifest.tsv`. It includes read-only preflight/hash
commands, test commands, corrected evidence collection, and the retained failed
wrappers. Two bounded wrapper defects are explicitly retained there:

- `postimplementation_evidence` exited `1` while serializing runtime JSON due to
  shell quoting; it wrote only `.codex-temp` evidence and made no experiment
  request or historical-file write.
- `postimplementation_evidence_v2` used the wrong base directory for its first
  comparison display. `immutable_hash_comparison_v3` corrected that path and is
  the authoritative `MATCH` result.

These process exits are not treated as scientific or protocol outcomes. The
successful checks and the final boundary audit determine the phase result.

## Boundary Self-Audit Requirement

Before handoff, the final no-request self-audit must confirm the protected hash
matches, approval-file absence, no v2.2/config creation, no active task process,
and the required `NOT_RUN` statuses above. Its JSON, PID, log, and `.exit` are
stored under `.codex-temp/paper1_core_judge_protocol_v2/phase0/` and are the
final phase-0 boundary evidence.

The completed final audit is `BOUNDARY_SELF_AUDIT_PASS` (PID `1990304`, exit
`0`). It supersedes the earlier audit evidence while retaining it unchanged.
Its JSON records protected-hash matches for 3 designs, 92 F2 files, and 9
recovery files; all three approval files absent; no 4096 config, v2.2 design,
or unapproved run directory; no active task process; all required check exits
`0`; and `git diff --check` exit `0`. The authoritative artifact is
`phase0/final_boundary_self_audit.json`, with log
`phase0/final_boundary_self_audit_final.log`, PID
`phase0/final_boundary_self_audit_final.pid`, and exit file
`phase0/final_boundary_self_audit_final.exit`.

The Phase-1 final boundary audit is
`phase1/phase1_probe_fail_boundary_audit.json`. It verifies the corrected
approval SHA, phase-0 code hashes, protected historical hashes, source-input
binding, the exact two-request failure accounting, raw/diagnostic/identity/
release evidence, artifact hash manifest, no active task process, and absence
of v2.2/recovery/full-rescore artifacts. Its successful PID/log/exit evidence
is retained in `phase1/`.

Stop condition: `JUDGE_PROTOCOL_PROBE_FAIL` and `DESIGN_CHANGE_REQUIRED`.
No v2.2 design/config, recovery, full rescore, dose decision, A/S selection,
or formal evaluation was started.
