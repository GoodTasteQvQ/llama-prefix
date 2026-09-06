# Paper 1 Server Run Status

Date: 2026-09-06 (Asia/Shanghai)
Design: MBD-NM v2.1-ccf-a-target
Implementation: linux-single-gpu-v1

## Overall status

`PREPARE=PASS`; `SAFE_PAIR_GATE=PENDING_SEMANTIC_REVIEW`; `REAL_RUNTIME_GATE=PENDING_SERVER_VERIFICATION`.
No directions, screen, generation, Judge, analysis, or human packet stage was started. Per the run
prompt, execution stops at the human-review handoff. No Git commit or push was performed.

## Repository and runtime

- Worktree: `/data/goodtaste_workspace/llama-prefix`
- Branch: `stage3/impl-candidate`
- HEAD: `bb8e2ed7b8a3a92c7c96078fb5774c878ccdcbcd`
- `origin/stage3/impl-candidate`: same local ref at `bb8e2ed`; no pull was needed. Worktree was clean before the run; the only current untracked path is this requested status report.
- Interpreter: `/data/goodtaste_workspace/envs/llama-prefix/bin/python`
- Python/Torch/Transformers/CUDA: 3.10.20 / 2.12.0+cu126 / 4.57.6 / 12.6
- Runtime environment: offline flags enabled; `CUDA_VISIBLE_DEVICES=0`; logical device `cuda:0`; torch saw one visible GPU.
- GPU snapshot: GPU0 UUID `GPU-e7424758-25c8-291b-e80f-c1f8c677b127`, A100 80GB, 80905 MiB free at prepare; GPU1 was not used.
- Disk: `/data` 312G available (93% used) at preflight.

## Nohup stages

The task-book `launch_nohup` wrapper was used. Each stage was run serially and its log and `.exit`
were checked. The first two offline-test launches were anomalous (PID disappeared without `.exit`);
they are retained as failed handoff attempts and are not counted as passing. A foreground diagnostic
confirmed the test command itself passed. The final nohup run was kept in the same shell until exit.

| Stage | Actual command | PID | Log | Exit | Business status |
|---|---|---:|---|---:|---|
| offline-tests (final) | `/data/goodtaste_workspace/envs/llama-prefix/bin/python -m pytest tests/paper1_broadening -q -p no:cacheprovider --basetemp /data/goodtaste_workspace/llama-prefix/.codex-temp/paper1-broadening-pytest` | 4021884 | `logs/paper1_broadening/offline-tests-20260906T020725Z-4021881-18871.log` | 0 | `38 passed in 11.50s` |
| discover-assets (final) | `bash scripts/run_paper1_broadening_single_gpu.sh discover-assets --config configs/paper1_broadening/mbd_nm_v21.json --output .codex-temp/mbd-assets-20260906T020918Z-4022513.json` | 4022516 | `logs/paper1_broadening/discover-assets-20260906T020918Z-4022513-19500.log` | 0 | Asset report written; E1/E2 unavailable as below |
| prepare | `bash scripts/run_paper1_broadening_single_gpu.sh prepare --config configs/paper1_broadening/mbd_nm_v21.json` | 4022719 | `logs/paper1_broadening/prepare-20260906T020952Z-4022717-21464.log` | 0 | `run_dir` created; `PENDING_SEMANTIC_REVIEW` |

Retained anomalous attempts: offline-tests PIDs 4020784 and 4021590 had empty logs and no `.exit`;
they were not treated as success. A nohup sanity command separately verified the wrapper writes exit
code `0`.

Final exit files: `logs/paper1_broadening/offline-tests-20260906T020725Z-4021881-18871.exit`,
`logs/paper1_broadening/discover-assets-20260906T020918Z-4022513-19500.exit`, and
`logs/paper1_broadening/prepare-20260906T020952Z-4022717-21464.exit` (each contains `0`).

## Prepare run and assets

Run directory: `/data/goodtaste_workspace/llama-prefix/results/paper1_broadening/paper1-20260906T020956Z-a3343ef2c4`

Required files present: `run_header.json`, `resolved_config.json`, `frames.json`, `plan.json`,
`identity_plan.json`, and `overlap_review_queue.json`. The run header records commit, clean state,
runtime, GPU UUIDs, design snapshots, and source snapshot.

- JBB100/JBB40/benign30: `100 / 40 / 30`
- Safe-pair source rows: `500`
- Preliminary eligible rows: `498`
- Preliminary construction fold size `k`: `79` (may change after human decisions)
- Overlap candidate queue: `86` rows; this is not the total number of pairs requiring review.
- Core logical generation plan: `12,640`; extension plan: `0` until its independent gates pass; total design budget remains `20,480`.
- Role separation and first-20 development screen allocation are recorded in the prepared plan.

Asset report: `.codex-temp/mbd-assets-20260906T020918Z-4022513.json`.

- Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct, and Qwen3-8B Judge have complete declared shards and local realpaths. They are only `READY_FOR_RUNTIME_CHECK`; no formal model load occurred in this run.
- E1: `NOT_RUN`, independent HarmBench text and metadata missing (`HARM_BENCH_ASSET_OR_METADATA_MISSING`). JBB source labels were not substituted.
- E2: `NOT_RUN`, Gemma-2-9B-it path is not configured (`MODEL_PATH_NOT_CONFIGURED`).
- E3: `NOT_RUN_UNTIL_CORE_LAYER_GATE`.

## Existing smoke review

Existing file `.codex-temp/paper1_broadening_smoke-final/smoke_report.json` reports `PASS` with
`evidence_status=NON_EVIDENCE`, 24 generation calls and 4 Judge calls, both direction families,
zero-alpha/clean token-id equality, and model/Judge release lifecycle checks passing. The expected
standalone trace/environment files were not present. This report is therefore retained as an already
used implementation smoke record, not a new formal evidence gate; it cannot replace the required
safe-pair human review or a reproducible current-run A100 verification.

The JSON `cases` array has 28 entries because the four Judge records are appended to the 24 generation
records. They are distinguished by generation entries containing `runtime_counters` and Judge entries
containing `judge`; no retry or additional generation is represented. The original smoke log contains
one run and no retry accounting.

## Stage status and accounting

| Stage | Status | Logical / physical complete | Failure / retry / Judge calls | Gate |
|---|---|---|---|---|
| Offline tests | PASS | 38 tests / no model generations | 0 retries; no Judge | Passed |
| Asset discovery | PASS | JSON report written | E1/E2 unavailable | Runtime checks still pending |
| Prepare | PASS | 12,640 core identities planned; 0 executed | no generation/Judge | Safe-pair semantic review pending |
| Safe-pair review | PENDING | 498 preliminary eligible; 86 candidate rows listed | 0 human decisions | Must be completed by two human reviewers |
| Real smoke | PENDING | Existing NON_EVIDENCE report only | 24 prior generation + 4 prior Judge (28 combined `cases` entries) | Recheck raw trace/environment before formal run |
| Directions | NOT_RUN | 0 / 0 | 0 | Blocked by safe-pair and runtime gates |
| Core screen | NOT_RUN | 0 / 0 | 0 | Must follow human review and smoke gate |
| Core schedule/generation | NOT_RUN | 0 / 0 | 0 | Dose decisions required first |
| Core Judge (four-class/binary) | NOT_RUN | 0 / 0 | 0 | Generation/release required |
| Core analysis | NOT_RUN | 0 / 0 | 0 | Requires closed generation/Judge ledgers |
| Core human packet | NOT_RUN | 0 / 0 | 0 | Only after core analysis; no fabricated labels |
| E1 | NOT_RUN | 0 / 2,320 planned | 0 | HarmBench asset/metadata and overlap gate |
| E2 | NOT_RUN | 0 / 1,160 planned | 0 | Gemma checkpoint/runtime gate |
| E3 | NOT_RUN | 0 / 2,560 planned | 0 | Core directions and extra-layer gate |

No `run_dir` contains generation, Judge, analysis, or human-label results. No release files were
required for the stopped prepare-only run.

## Human handoff and next step

Researchers must review every preliminary eligible safe-pair decision required by the frames, while
also recording both the full preliminary eligible count and the 86-row candidate queue. Decision JSON
must preserve two reviewer identities, rationale/time, and `include`/`exclude` decisions; Codex has
not supplied or inferred any human decisions. If reviewers disagree, retain both opinions and use the
documented adjudication path rather than rewriting reviewer fields.

After a real decision file exists, create a new prepare run with that path, confirm
`READY_FOR_CONSTRUCTION` and actual `k >= 30`, then independently recheck the existing smoke trace
and environment. Only if both gates pass may the core stages be submitted one at a time. E1/E2/E3
remain separately gated and are not automatically launched. Current handoff state is therefore
`PENDING_SEMANTIC_REVIEW`; it is not permission to start the full experiment.
