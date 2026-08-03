# Stage 3 Development Commands

The active production helpers support normal development. They do not create release, lifecycle,
receipt, or paper-result artifacts.

- `python -B scripts/stage3_production/verify_e0.py` runs unit and statistical golden tests.
- `python -B scripts/stage3_production/offline_smoke.py` runs one fake-backend offline smoke item.
- `python -B scripts/stage3_production/real_smoke.py --config
  configs/stage3/real_smoke_development_v1.json --validate-only` validates the local Qwen behavior
  and judge metadata, tokenizer templates, candidate vector, and active harmful input without loading
  model weights or executing generation.

Before these commands, set `TMPDIR`, `TEMP`, and `TMP` to the repository's `.codex-temp`, set
`PYTHONDONTWRITEBYTECODE=1`, and enable the Hugging Face/Transformers offline flags. Real model runs are
not performed by `verify_e0.py`, `offline_smoke.py`, or the `--validate-only` path.

Running `real_smoke.py` without `--validate-only` loads the configured models sequentially and writes
a non-overwriting development-only run below `.codex-temp/stage3_real_smoke_runs/`. That path is limited
to one or two logical identities, is never paper-result eligible, and must not be used as a pilot or
paper run. The configured candidate vector and structural `A` label are smoke assets, not paper vector
or anchor provenance.
