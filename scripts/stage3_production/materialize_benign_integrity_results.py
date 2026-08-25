#!/usr/bin/env python3
"""Materialize the benign-integrity descriptive retained-bootstrap result."""

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

from stage3_pipeline.benign_integrity_results import (  # noqa: E402
    BenignIntegrityResultInputInvalid,
    OUTPUT_FILENAME,
    materialize_benign_integrity_results_directory,
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
            materialized = materialize_benign_integrity_results_directory(
                args.run_directory, args.output_directory
            )
            result = {
                "status": materialized["status"],
                "output": str(args.output_directory.resolve() / OUTPUT_FILENAME),
                "run_id": materialized["source"]["run_id"],
                "complete_prompt_count": materialized["accounting"]["complete_prompt_count"],
                "paper_result_eligible": materialized["paper_result_eligible"],
            }
    except (BenignIntegrityResultInputInvalid, OSError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "BENIGN_INTEGRITY_RESULT_INPUT_INVALID", "error": str(exc)},
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
