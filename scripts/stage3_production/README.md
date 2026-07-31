# Stage 3 Development Commands

The active production helpers support normal development. They do not create release, lifecycle,
receipt, or paper-result artifacts.

- `python -B scripts/stage3_production/verify_e0.py` runs unit and statistical golden tests.
- `python -B scripts/stage3_production/offline_smoke.py` runs one fake-backend offline smoke item.

Before either command, set `TEMP` and `TMP` to the repository's `.codex-temp`, set
`PYTHONDONTWRITEBYTECODE=1`, and enable the Hugging Face/Transformers offline flags. Real model runs are
not performed by these helpers.
