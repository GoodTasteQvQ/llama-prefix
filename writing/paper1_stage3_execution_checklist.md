# Paper 1 Stage 3 Execution Checklist

Updated: 2026-07-30

Current design: `writing/stage3 design/paper1_stage3_experiment_design.md`
Status: `DESIGN COMPLETE / IMPLEMENTATION IN ACTIVE DEVELOPMENT`

This checklist follows `environment -> smoke -> pilot -> paper run -> analysis -> final snapshot`.
Smoke and pilot outputs are development evidence only and must not be used as paper results.

## 0. Scientific Invariants

- [ ] Execution profile is `compact_single_gpu`; behavior scope is Qwen only.
- [ ] P1 uses 100 harmful plus 100 benign prompts.
- [ ] P2 uses `P=50`, `V=20`, A/T, and remains estimation-only.
- [ ] K1 reuses P2 and adds zero generation and zero judge calls.
- [ ] Benign uses 30 prompts; human validation uses 720 response items.
- [ ] Paper budget is 5,580 logical generations and 5,580 scheduled judges.
- [ ] Unsafe, refusal, safe/helpful, broken, ARR, and repetition remain reported.
- [ ] Missingness, survivor frames, bootstrap, two-phase correction, and fixed720 rules match the current design.
- [ ] K2, V2, attention block, rendering 2x2, stochastic decoding, phase confirmation, model-based RD/CI, and prospective power claims remain excluded.

## 1. Environment

- [ ] Read `writing/stage3 design/README.md` and the current design.
- [ ] Record Git commit and dirty state; a dirty tree is allowed during development.
- [ ] Set project-local `TEMP`/`TMP`, disable the NX daemon, and enable Python/no-network offline flags.
- [ ] Supply explicit local model, tokenizer, input, vector, anchor, and output paths.
- [ ] Verify required files, schemas, optional expected SHA256 values, budget limits, and output non-overwrite rules.
- [ ] Record Python, Torch, Transformers, CUDA, and GPU identity when available.

## 2. Smoke

- [ ] Use `run_mode=smoke` with 1-2 inputs.
- [ ] Confirm model/fake-backend loading, steering hook placement, cache/phase behavior, output writing, retry, and terminal failure.
- [ ] Confirm the runtime performs zero network attempts.
- [ ] Write one non-overwriting `run_manifest.json` with the actual configuration and counts.
- [ ] Confirm smoke records are marked non-paper and cannot be loaded as paper results.
- [ ] Fix implementation defects and repeat smoke as needed.

## 3. Pilot

- [ ] Use `run_mode=pilot` on a documented small subset.
- [ ] Record every explicit generation-config override in `run_manifest.json`.
- [ ] Inspect memory/runtime, collapse, repetition, class distribution, missingness, retries, and output recovery.
- [ ] Confirm budget checks use the pilot limit without changing paper defaults.
- [ ] Confirm pilot records are marked non-paper and cannot be loaded as paper results.
- [ ] Fix implementation defects and repeat pilot as needed.

## 4. Paper Run

- [ ] Use `run_mode=paper` and the complete current design.
- [ ] Confirm behavior generation uses `do_sample=false`, `num_beams=1`, `max_new_tokens=512`, `use_cache=true`, no custom stop strings, and seed 42.
- [ ] Confirm judge generation uses the specified deterministic Qwen3-8B settings and exact JSON parser.
- [ ] Validate the exact P1 prompt frames and P1 harmful 100 SHA256 before execution.
- [ ] Validate anchors, vectors, layer/hook, templates, prompt identities, and fixed 5,580 registry.
- [ ] Run P1, support, P2/K1, clean/benign, judge, and human allocation in the design sequence.
- [ ] Preserve every retry, terminal failure, exclusion, matched denominator, and actual-call count.
- [ ] Never overwrite an existing output or manifest.

## 5. Analysis

- [ ] Re-run statistical golden tests before analysis.
- [ ] Apply P1 complete-case, pooled-token, equal-domain, nearest-rank bootstrap, and 0.10 gate rules.
- [ ] Apply P2 matched survivor frames, raw two-way CI, retained bootstrap, fixed720, and matched two-phase rules.
- [ ] Keep P2 estimation-only; do not emit p-values, rejection decisions, or confirmation claims.
- [ ] Report all registered missingness, support, judge-quality, positivity, ESS, weight, and completion diagnostics.
- [ ] Map only observed paper-run evidence into `writing/paper1_claim_evidence_matrix.md`.

## 6. Final Snapshot

- [ ] After experiments and analysis are complete, record the final Git commit/tag.
- [ ] Snapshot configs, input SHA256 values, model/tokenizer identity, seeds, raw outputs, analysis scripts, tables, figures, and claim-evidence mapping.
- [ ] Verify every paper table and figure can be reproduced from the snapshot.
- [ ] Keep smoke and pilot directories excluded from paper evidence.

## Development Readiness

Use `DEVELOPMENT-READY`, `SMOKE-READY`, `PILOT-READY`, or
`IMPLEMENTATION-FIX-REQUIRED`. Missing inputs, schema failures, budget violations, network attempts,
output collisions, statistical mismatches, and reproducibility defects fail the affected step closed.
Resolve them through the ordinary code, data, or configuration fix and rerun the affected check.
