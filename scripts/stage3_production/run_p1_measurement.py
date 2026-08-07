#!/usr/bin/env python3
"""Validate or run Stage 3 P1 smoke and fixed-frame paper measurement modes."""

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
    run_paper,
    run_smoke,
    validate_only,
)
from stage3_pipeline.core import PipelineError  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--run-mode")
    parser.add_argument("--run-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            if args.run_id is not None:
                raise P1SmokeCoreError("--run-id is valid only with --run-mode paper")
            result = validate_only(args.config)
        else:
            if args.run_mode == "smoke":
                if args.run_id is not None:
                    raise P1SmokeCoreError("smoke mode does not accept --run-id")
                result = run_smoke(args.config)
            elif args.run_mode == "paper":
                if args.run_id is None:
                    raise P1SmokeCoreError("paper mode requires an explicit --run-id")
                result = run_paper(args.config, run_id=args.run_id)
            else:
                raise P1SmokeCoreError(
                    "unsupported P1 mode; use --validate-only, --run-mode smoke, or --run-mode paper"
                )
    except (OSError, PipelineError) as exc:
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
    if result.get("status") == "P1_PAPER_RUNNER_VALIDATE_ONLY_PASS":
        print(f"paper frame count = {result['paper_frame_count']}")
        print(f"harmful = {result['harmful']}")
        print(f"benign = {result['benign']}")
        print(f"identities unique = {str(result['identities_unique']).lower()}")
        for field in (
            "model_weights_loaded",
            "forward_executed",
            "generation_run",
            "judge_run",
            "full_p1_run",
        ):
            print(f"{field} = {str(result[field]).lower()}")
        print("P1_PAPER_RUNNER_VALIDATE_ONLY_PASS")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
