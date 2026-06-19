# Activation Steering Paper Scaffold

This workspace now contains a small experiment scaffold for the paper direction
"when steering happens matters". The goal is not to replace the original
`Rogue/` scripts, but to give you a unified runner for:

- phase-aware attack reproduction
- prefill vs decode hook tracing
- pathological generation diagnostics
- phase-aware defense experiments

## Paper roadmap

The repository is now organized around a two-paper trajectory:

- Paper 1: `mechanism audit / reproducibility + evaluation correction`
- Paper 2: `phase-aware dynamic activation guard`

Research framing documents:

- [two_paper_roadmap.md](/D:/llama_prefix/two_paper_roadmap.md)
- [activation_steering_research_advice.md](/D:/llama_prefix/activation_steering_research_advice.md)
- [activation_steering_experiment_checklist.md](/D:/llama_prefix/activation_steering_experiment_checklist.md)

## New layout

- `activation_guard/`
  - `config.py`: experiment dataclasses and JSON config loader
  - `interventions.py`: phase-aware attack/defense hook controller
  - `metrics.py`: ARR, repetition, special-token leakage, truncation heuristics
  - `vectors.py`: random or tensor-file vector loading
  - `runner.py`: unified experiment runner
- `scripts/run_phase_experiments.py`
  - CLI entrypoint for config-driven experiments
- `scripts/stage1_phase_aware/`
  - formal stage1 entrypoints for semantic audit and Rogue-calibrated reproduction
- `scripts/extract_safe_vectors.py`
  - safety-vector extraction and layer-scan stats
- `scripts/run_score_ablation.py`
  - dot / cosine / norm / projection+ReLU ablation
- `scripts/analyze_attention_sink.py`
  - structural-token high-norm sweep across filter strategies
- `scripts/judge_phase_outputs.py`
  - optional harmful/harmless judge-based labels
- `scripts/summarize_phase_results.py`
  - aggregate ASR / UFR / FRR / ARR / leakage / repetition summaries
- `configs/local/`
  - server-safe configs that read harmful prompts from local JSON
- `configs/remote/`
  - configs for environments that can access Hugging Face / JailbreakBench directly
- `data/safe_pairs.example.json`
  - example harmful/harmless pair template for safe-vector extraction
- `ACTIVATION_PAPER_RUNBOOK.md`
  - exact command sequence for the six paper-core experiments

## Core behavior

The hook controller records the exact evidence you need for the paper:

- `prefill_calls`
- `decode_calls`
- `generated_steered_calls`
- per-call `seq_len`
- per-call `mask_sum`
- whether attack or defense was actually applied on each call
- decode-stage projection scores for gated defense

This is the direct code path for validating the claim that public Rogue-style
implementations can behave like prefill-only steering under `use_cache=True`.

The framework now distinguishes two attack-strength semantics:

- `fixed_alpha`
- `rogue_calibrated` with `alpha = c * mu`

For stage1 formal experiments, prefer the dedicated scripts under:

- [scripts/stage1_phase_aware/README.md](/D:/llama_prefix/scripts/stage1_phase_aware/README.md)

The old duplicated wrapper layout under:

- `scripts/analysis/`
- `scripts/evaluation/`
- `scripts/phase_matrix/`
- `scripts/setup/`
- `scripts/vectors/`

has been cleaned up. Use the top-level `scripts/*.py` files directly.

## Supported phase modes

Attack modes:

- `rogue_v1_cache_semantics`
- `prefill_only`
- `decode_only`
- `prefill_and_decode`
- `first_k_decode`

Defense modes:

- `prefill_only`
- `decode_only`
- `full`
- `prefill_base_decode_relu`
- `prefill_base_first_k_decode_relu`

Both attack and defense also support `decode_decay`.

## Example runs

Run a prefill-only reproduction:

```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoLogo -Command `
  'python .\scripts\run_phase_experiments.py --config .\configs\local\phase_matrix_qwen25_rogue_v1.json'
```

Run a decode-only reproduction:

```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoLogo -Command `
  'python .\scripts\run_phase_experiments.py --config .\configs\local\phase_matrix_qwen25_decode_only.json'
```

Run a phase-aware defense experiment:

```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoLogo -Command `
  'python .\scripts\run_phase_experiments.py --config .\configs\local\phase_defense_qwen25.json'
```

Extract safety vectors:

```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoLogo -Command `
  'python .\scripts\extract_safe_vectors.py --model-name Qwen/Qwen2.5-7B-Instruct --pairs .\data\safe_pairs.json --output-dir .\results\vectors\qwen25 --layers all --filter-role-markers --filter-newlines'
```

Run score ablations:

```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoLogo -Command `
  'python .\scripts\run_score_ablation.py --model-name Qwen/Qwen2.5-7B-Instruct --pairs .\data\safe_pairs.json --vector-path .\results\vectors\qwen25\safe_vectors.pt --vector-index 9 --layer 9 --output-path .\results\ablations\qwen25_layer9.json --threshold 0.5 --filter-role-markers --filter-newlines'
```

Analyze attention sink artifacts:

```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoLogo -Command `
  'python .\scripts\analyze_attention_sink.py --model-name Qwen/Qwen2.5-7B-Instruct --layer 9 --output-path .\results\sinks\qwen25_layer9.json --filter-role-markers --filter-newlines'
```

## Output fields

Each experiment writes a single JSON summary with:

- full config snapshot
- per-prompt output text
- latency
- hook-stage statistics
- response metrics

The response metrics currently include:

- `arr`
- `repetition_rate`
- `special_token_leakage`
- `garbled`
- `empty_or_truncated`
- `contains_refusal_phrase`

These are intentionally paper-facing quality checks so that you can show why
ASR alone is not enough.

The judged summary pipeline now supports:

- harmful mode: `ASR`, harmful refusal rate, safe rate, broken rate
- harmless mode: `UFR`, `FRR`, helpful rate, broken rate
- bad case export buckets: repetition, garbled, special-token leakage, empty, language-switch-like

## What this implements from the paper plan

This scaffold directly supports:

1. Rogue original cache semantics vs fixed decode-hook comparisons
2. prefill-only / decode-only / prefill+decode comparisons
3. decode-collapse diagnostics through ARR-style metrics
4. phase-aware defense runs with `prefill base + decode ReLU gated`

What still needs to be added with real experiment data:

- utility benchmark integration
  - the scripts now support harmful/harmless judged summaries, but you still need to prepare the real harmless/utility datasets and run them end-to-end

## Recommended next steps

1. Use the new runner to reproduce the phase matrix on Qwen, Llama, and Mistral.
2. Save the exact decode-hook summaries as evidence for the cache/phase claim.
3. Run both `fixed_alpha` and `rogue_calibrated` attack-strength protocols when you need Rogue-comparable numbers.
4. Add a safe-vector tensor file for each model, then run defense configs.
5. Extend the judge pipeline so each JSON also contains ASR / UFR / FRR labels.
6. Follow [ACTIVATION_PAPER_RUNBOOK.md](/D:/llama_prefix/ACTIVATION_PAPER_RUNBOOK.md) to execute the six paper-core experiments in order.
