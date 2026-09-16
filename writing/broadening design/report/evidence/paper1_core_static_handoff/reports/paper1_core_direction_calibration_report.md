# Paper 1 Core Direction Calibration Report

Task: `core-directions-calibration-v1`

Date: 2026-09-15 UTC

Worktree: `/data/goodtaste_workspace/llama-prefix`

## Status

`CORE_DIRECTIONS_READY`

`FORMAL_EXPERIMENTS_NOT_RUN`

The required Core direction and calibration assets were constructed successfully. This is not an
evaluation result. No Core or extension screen, generation, Judge, analysis, sample-human, archive,
or formal evaluation schedule was run. No A/S dose was selected.

## Gates And Immutable Input

- B4 handoff records `CODE_CONTRACT_PASS` and `CORE_REAL_SMOKE_PASS/NON_EVIDENCE`; the latter
  is retained solely as a runtime-path check and is not formal experimental evidence.
- B5 is explicitly `E1_CONSUMER_PASS`; its final E1 frame is `READY_FOR_RUN`, has 40 records and
  reference digest `d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`.
- The prepared frame records safe-pair gate `READY_FOR_CONSTRUCTION`: 516 source rows, 509
  preliminary eligible rows, 300 executable rows, `actual_k=40`, five construction folds of 40,
  100 development pairs, zero unused pairs, and construction/development disjointness.
- The final input was
  `configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final.json`. Its file SHA256 is
  `606721864c4870543c63964fedd4d5a7f4001d54809cb38875ea460152d8e98a`; the canonical resolved-config
  digest recorded in the run header is
  `a0d72b0a63b54da7e81c5f34f123bb107faf65e6b113a5bc1f49218266322779`.
- Comparison with `mbd_nm_v212_public_expanded.json` found exactly one intended difference:
  `data.e1_overlap_decisions_path` points to the final C3 E1 decisions file. Model, layer,
  native-template, decoder, rho grid, seed, split, decision criterion, budget, and endpoint fields
  were unchanged. No `DESIGN_CHANGE_REQUIRED` condition occurred.

## Run Evidence

Run directory:
`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603`

Run ID: `paper1-20260915T140735Z-99331d4603`

Both commands used the final explicit config in the Linux project directory with project-local
`TMPDIR`, `TMP`, and `TEMP` set to `.codex-temp`, offline Hugging Face/Transformers/Datasets
environment variables, `CUDA_VISIBLE_DEVICES=0`, `MBD_GPU=0`, and the project Python interpreter.
They were launched through `nohup`; the recorded launcher PID, log, and exit artifact are:

| stage | CLI operation | PID | log | exit |
|---|---|---:|---|---:|
| prepare | `scripts/paper1_broadening.py prepare --config ...e1_final.json --output-dir <run-dir>` | 1382607 | `logs/paper1_broadening/core-prepare-20260915T140731Z-1382603-2365.log` | 0 |
| build directions | `scripts/paper1_broadening.py build-directions --config ...e1_final.json --run-dir <run-dir>` | 1383422 | `logs/paper1_broadening/core-build-directions-20260915T141049Z-1383420-1106.log` | 0 |

`frames.json` SHA256 is `a69a39c1f63f0fc1a9d32876e7e6663ef5bea89233917cf86972e598e0b730ef`.
`directions.json` SHA256 is `3ca9bb9eed166eefddb62552e603dcf183708e37f6f892923782ec6d46d962eb`.

## Core Assets

Both Core assets use the zero-based `resid_pre` hook
(`forward_pre_hook_on_layer_input`), native chat template, empty system prompt, and
`add_generation_prompt=true`. Content masks are derived from the native template's
sentinel/offset user-content span implementation. The reported `mu_content` is the
token-weighted development-harmless content-token residual-norm mean; JBB and benign frames were
not used for construction or calibration.

| model | core layer | directions | development harmless `mu_content` | content tokens | tensor SHA256 |
|---|---:|---|---:|---:|---|
| Qwen2.5-7B-Instruct (`qwen25`) | 9 | 8 Rogue + 5 contrastive | 56.86973966266515 | 1172 | `733d2ebf76d1097184769746f36cd2df072615366cee2aaa6341f2764eca8c49` |
| Llama-3.1-8B-Instruct (`llama31`) | 11 | 8 Rogue + 5 contrastive | 7.615247755784255 | 1170 | `5bfb6b88592d135baac9c9eb272949dba9a2670b514e9672c39d4bb6b7cd6560` |

CPU-only post-build audit loaded the saved tensors with `map_location=cpu` and verified:

- Qwen tensor `directions_qwen25.pt`: `float32`, CPU shape `[13, 3584]`, all finite, L2
  norms in `[0.9999999403953552, 1.0]`.
- Llama tensor `directions_llama31.pt`: `float32`, CPU shape `[13, 4096]`, all finite, L2
  norms in `[0.9999998807907104, 1.0000001192092896]`.
- Metadata tensor indices are contiguous, direction families are exactly 8 Rogue then 5 contrastive,
  Rogue seeds are Qwen `420001` and Llama `420002`, and each contrastive seed is `42`.

## Fold Membership And Sign Diagnostics

For both models, `contrastive:fold:i.source_fold_ids` is exactly equal, in order, to
`frames.json.safe_pair_split.construction_folds[i]`. Each fold has 40 executable pair IDs; the
five ordered membership hashes are retained below so the report binds to the exact lists stored in
`directions.json` and `frames.json` rather than duplicating 200 IDs in prose.

| fold | ordered membership SHA256 |
|---:|---|
| 0 | `ef415892f4d71e248c48b6ea74f5c8e72584553f8d56af0c44bb2a6d54cb1230` |
| 1 | `5d0809cbd4b8b6329fedb94667720c190e12840a403e207c4777bd8e1f185947` |
| 2 | `c45cdf1363af0618e27423dc84709871fb988e3215fabafde77703fba99d650e` |
| 3 | `03e9adca8e2e8ecd9e8542bf0c5adad71d0585cd0d542e1a2283f2ded2459271` |
| 4 | `9daa56e16f192f2f554474d0118e41fd6a5ad980a13c2e0601d6a0b9e07e66fe` |

The aggregate ordered fold hash is
`f44e089aced85fdfd704a0371b31c2e3df3299ce33e151c96c96f0c51cf89bcd`; the ordered development
membership hash is `29d2423c27f6a6d38c38f40c87f721ce4649c8d84e6f27bef41756b46e979c4d`.

All ten contrastive diagnostics are finite, nonzero, unflipped, and `SIGN_VALIDATED`:

| model | fold 0 | fold 1 | fold 2 | fold 3 | fold 4 |
|---|---:|---:|---:|---:|---:|
| Qwen mean harmful-minus-harmless projection | 5.330296930670738 | 5.178705508708954 | 5.420832800865173 | 5.4185299891233445 | 5.652281229794025 |
| Llama mean harmful-minus-harmless projection | 0.9660534863173962 | 0.9517157518863678 | 0.9571751530840993 | 0.9462846690416336 | 0.982317917495966 |

## Runtime Identity And Release

The run header records exactly one visible worker device: `CUDA_VISIBLE_DEVICES=0`,
`visible_gpu_count=1`, logical device `cuda:0`, and project-local temp paths. It records Python
`3.10.20` at `/data/goodtaste_workspace/envs/llama-prefix/bin/python`, PyTorch `2.12.0+cu126`,
CUDA runtime `12.6`, Transformers `4.57.6`, and the offline environment. The behavior runtime
identity for both Core models records physical GPU 0, NVIDIA A100 80GB PCIe,
`GPU-e7424758-25c8-291b-e80f-c1f8c677b127`; a post-run `nvidia-smi` audit reported driver
`565.57.01` for that same UUID.

| model | model/tokenizer realpath | runtime dtype | native template SHA256 | release result |
|---|---|---|---|---|
| Qwen | `/data/goodtaste_workspace/models/Qwen2___5-7B-Instruct` | `bfloat16` | `2e2d2512cfe46af53dc1eed45368ecaab26ac4461c480e6b69fe571cf0ceaa75` | hook/model/tokenizer references cleared; synchronize, empty-cache, and GC all recorded; `gc_collected_count=61`; `models_concurrently_resident=false` |
| Llama | `/data/goodtaste_workspace/models/Meta-Llama-3___1-8B-Instruct` | `bfloat16` | `ca5b86f15c19b53c24ff18228849e06ffb677b952d85171c66d9b720d924f9bb` | hook/model/tokenizer references cleared; synchronize, empty-cache, and GC all recorded; `gc_collected_count=42`; `models_concurrently_resident=false` |

Each runtime identity additionally records model/tokenizer config hashes, model/tokenizer revision
`UNKNOWN` rather than inventing a revision, layer count (Qwen 28; Llama 32), token IDs, hook
semantics, local-only loading, physical index, and GPU name. The release records establish the
sequential one-model-at-a-time construction boundary.

## Automatic Extension Assets

`build-directions` automatically attempted the implementation-provided extension asset construction
after Core completion. These are direction/calibration assets only, not completed E2/E3 experiments.

- E2 Gemma asset: top-level status `COMPLETED`; Gemma 2 9B IT at layer 14 of 42 (the recorded
  third-layer formula result), 4 Rogue plus 5 contrastive directions, `mu_content=215.28572219322467`,
  1160 development-harmless content tokens, and tensor SHA256
  `34e3696a55da7c6bd7c54787e6f7d4046d64707859c13ce2c01703c2b78bb4fd`.
  Its runtime identity and direction metadata are serialized. The current implementation does not
  serialize the Gemma `release` return into `directions.json`; this is explicitly recorded as a
  release-recording gap, not treated as a formal E2 pass or fabricated release evidence.
- E3 assets: top-level status `COMPLETED`, with vector source `core_rogue_indices_0_to_3`.
  The fixed quarter/three-quarter formula produced Qwen layers 7 and 20, and Llama layers 8 and 23.
  Qwen layer 7/20 `mu_content` values are 41.76629936817156/103.98859577374246 (1172 tokens each);
  Llama layer 8/23 values are 6.3610816922962155/21.470473134619557 (1170 tokens each).
  Each E3 layer records a runtime identity and a complete release record with
  `models_concurrently_resident=false`.
- No E2 or E3 screen, dose decision, evaluation schedule, generation, judging, analysis, or archive
  artifact was created.

## Boundary Check

The run directory contains only prepare/direction assets: run header, resolved config, frames,
plan, identity plan, overlap queue, `directions.json`, and the three direction tensors. It contains
no `dose_decisions.json`, generation schedule, generation attempt/ledger, Judge record, analysis,
human, or archive artifact. The plan's `core_schedule_count=12640` is planning metadata only and is
not a materialized formal evaluation schedule.

No `screen`, `generate`, `judge`, `analyze`, `sample-human`, or `archive` command was started for
this run. No A/S dose was selected. No scientific design file or canonical scientific field was
modified. Existing dirty worktree changes were preserved. No commit or push was performed.

Final bounded self-audit: Core status, E1/safe-pair gates, final config binding, fold memberships,
development disjointness, seeds, tensor dtype/shape/finiteness/norms, sign diagnostics, runtime
identity, Core release records, extension status, and absence of formal-experiment artifacts all
passed. The only extension-specific caveat is the explicit E2 release serialization gap above.
