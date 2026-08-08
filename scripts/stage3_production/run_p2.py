#!/usr/bin/env python3
"""Validate or run the fixed Paper 1 Stage 3 P2 production stage."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMP_ROOT = (ROOT / ".codex-temp").resolve()
for _variable in ("TMPDIR", "TEMP", "TMP"):
    os.environ[_variable] = str(TEMP_ROOT)
for _variable in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
    os.environ[_variable] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import PipelineError  # noqa: E402
from stage3_pipeline.p2_runner import DEFAULT_CONFIG, run_p2, validate_only  # noqa: E402


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
                raise PipelineError("--run-id is valid only with --run-mode paper")
            result = validate_only(args.config)
        else:
            if args.run_mode != "paper":
                raise PipelineError("P2 execution requires --run-mode paper")
            if args.run_id is None:
                raise PipelineError("--run-mode paper requires an explicit --run-id")
            result = run_p2(args.config, run_mode=args.run_mode, run_id=args.run_id)
    except (OSError, PipelineError) as exc:
        print(json.dumps({
            "status": "P2_RUNNER_FAIL",
            "error": str(exc),
            "validate_only": bool(args.validate_only),
            "model_weights_loaded": False if args.validate_only else None,
            "forward_executed": False if args.validate_only else None,
            "generation_run": False,
            "judge_run": False,
            "support_run": False,
            "p2_run": False,
            "paper_result_eligible": False,
            "formal_experiment_run": False,
        }, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
