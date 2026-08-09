#!/usr/bin/env python3
"""Materialize raw Stage 3 P2 results from the accepted formal run."""

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
from stage3_pipeline.p2_results import (  # noqa: E402
    OUTPUT_FILENAME,
    P2ResultInputInvalid,
    materialize_p2_results_directory,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = materialize_p2_results_directory(
            args.run_directory, args.output_directory
        )
    except (P2ResultInputInvalid, PipelineError, OSError) as exc:
        print(
            json.dumps(
                {"status": "P2_RESULT_INPUT_INVALID", "error": str(exc)},
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({
        "status": result["status"],
        "output": str(args.output_directory.resolve() / OUTPUT_FILENAME),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
