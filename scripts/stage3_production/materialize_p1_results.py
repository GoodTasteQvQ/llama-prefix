#!/usr/bin/env python3
"""Materialize Stage 3 P1 statistics and the fixed measurement dose manifest."""

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

from stage3_pipeline.p1_results import (  # noqa: E402
    P1ResultInputInvalid,
    materialize_p1_results_file,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = materialize_p1_results_file(args.input, args.output)
    except (P1ResultInputInvalid, OSError) as exc:
        print(
            json.dumps(
                {"status": "P1_RESULT_INPUT_INVALID", "error": str(exc)},
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"status": result["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
