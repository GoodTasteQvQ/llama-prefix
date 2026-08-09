#!/usr/bin/env python3
"""Materialize the K1 four-cell matched profile from accepted P2 artifacts."""

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

from stage3_pipeline.core import PipelineError  # noqa: E402
from stage3_pipeline.k1_results import (  # noqa: E402
    K1ResultInputInvalid,
    OUTPUT_FILENAME,
    materialize_k1_results_directory,
    validate_k1_results_inputs,
    validation_summary,
)
from stage3_pipeline.statistics.retained_bootstrap import (  # noqa: E402
    RetainedBootstrapError,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p2-run-directory", type=Path, required=True)
    parser.add_argument("--p2-raw-result", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            validated = validate_k1_results_inputs(
                args.p2_run_directory,
                args.p2_raw_result,
                args.output_directory,
            )
            result = validation_summary(validated)
        else:
            materialized = materialize_k1_results_directory(
                args.p2_run_directory,
                args.p2_raw_result,
                args.output_directory,
            )
            result = {
                "status": materialized["status"],
                "output": str(args.output_directory.resolve() / OUTPUT_FILENAME),
                "M_A": materialized["matched_profile_counts"]["M_A"],
                "M_T": materialized["matched_profile_counts"]["M_T"],
                "M_A_intersection_M_T": materialized["matched_profile_counts"][
                    "M_A_intersection_M_T"
                ],
                "generation_calls_added": materialized["generation_calls_added"],
                "judge_calls_added": materialized["judge_calls_added"],
            }
    except (K1ResultInputInvalid, PipelineError, RetainedBootstrapError, OSError) as exc:
        print(
            json.dumps(
                {"status": "K1_RESULT_INPUT_INVALID", "error": str(exc)},
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
