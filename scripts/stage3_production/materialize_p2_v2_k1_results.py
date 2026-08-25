#!/usr/bin/env python3
"""Materialize descriptive K1 profiles for the formal amended T/H P2 run."""

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

from stage3_pipeline.p2_v2_k1_results import (  # noqa: E402
    OUTPUT_FILENAME,
    P2V2K1ResultInputInvalid,
    materialize_p2_v2_k1_results_directory,
    validate_p2_v2_k1_inputs,
    validation_summary,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p2-run-directory", type=Path, required=True)
    parser.add_argument("--p2-raw-result", type=Path, required=True)
    parser.add_argument("--p2-formal-result", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            result = validation_summary(
                validate_p2_v2_k1_inputs(
                    args.p2_run_directory,
                    args.p2_raw_result,
                    args.p2_formal_result,
                    args.output_directory,
                )
            )
        else:
            materialized = materialize_p2_v2_k1_results_directory(
                args.p2_run_directory,
                args.p2_raw_result,
                args.p2_formal_result,
                args.output_directory,
            )
            counts = materialized["matched_profile_counts"]
            result = {
                "status": materialized["status"],
                "output": str(args.output_directory.resolve() / OUTPUT_FILENAME),
                "M_T": counts["M_T"],
                "M_H": counts["M_H"],
                "intersection": counts["intersection"],
                "reuse_records": materialized["k1_reuse_record_count"],
                "generation_calls_added": materialized["generation_calls_added"],
                "judge_calls_added": materialized["judge_calls_added"],
            }
    except (P2V2K1ResultInputInvalid, OSError, ValueError) as exc:
        print(json.dumps({"status": "P2_V2_K1_RESULT_INPUT_INVALID", "error": str(exc)}, ensure_ascii=True, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
