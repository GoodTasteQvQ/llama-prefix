#!/usr/bin/env python3
"""Validate or run the bounded Stage 3 P1 development forward smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


for _offline_variable in (
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE",
):
    os.environ[_offline_variable] = "1"

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.p1_measurement import (  # noqa: E402
    DEFAULT_CONFIG,
    P1SmokeCoreError,
    run_smoke,
    validate_only,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--run-mode")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            result = validate_only(args.config)
        else:
            if args.run_mode != "smoke":
                raise P1SmokeCoreError(
                    "unsupported P1 mode; only --validate-only or --run-mode smoke is available"
                )
            result = run_smoke(args.config)
    except (OSError, P1SmokeCoreError) as exc:
        print(
            json.dumps(
                {
                    "status": "P1_SMOKE_CORE_FAIL",
                    "error": str(exc),
                    "model_weights_loaded": False if args.validate_only else None,
                    "forward_executed": False if args.validate_only else None,
                    "generation_run": False,
                    "judge_run": False,
                    "p1_run": False,
                    "formal_experiment_run": False,
                    "paper_result_eligible": False,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
