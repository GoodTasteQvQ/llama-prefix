#!/usr/bin/env python3
"""Materialize the accepted harmful-clean descriptive result."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

for _name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
    os.environ[_name] = "1"

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.harmful_clean_results import (  # noqa: E402
    HarmfulCleanResultInputInvalid,
    materialize_harmful_clean_results_directory,
    validate_only,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            result = validate_only(args.run_directory, args.output_directory)
        else:
            materialized = materialize_harmful_clean_results_directory(
                args.run_directory, args.output_directory
            )
            result = {
                "status": materialized["status"],
                "output": str(args.output_directory.resolve() / "harmful_clean_result.json"),
                "run_id": materialized["source"]["run_id"],
                "retained_denominator": materialized["accounting"]["retained_denominator"],
                "generation_calls_added": materialized["generation_calls_added"],
                "judge_calls_added": materialized["judge_calls_added"],
            }
    except (HarmfulCleanResultInputInvalid, OSError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "HARMFUL_CLEAN_RESULT_INPUT_INVALID", "error": str(exc)},
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
