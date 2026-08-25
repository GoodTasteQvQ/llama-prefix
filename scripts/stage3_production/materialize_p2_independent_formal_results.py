#!/usr/bin/env python3
"""Materialize formal statistics for the existing amended T/H P2 raw result."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMP_ROOT = (ROOT / ".codex-temp").resolve()
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
for _variable in ("TMPDIR", "TEMP", "TMP"):
    os.environ[_variable] = str(TEMP_ROOT)
for _variable in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
    os.environ[_variable] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.p2_independent_formal_results import (  # noqa: E402
    DEFAULT_FORMAL_SUPPLEMENT,
    DEFAULT_PROTOCOL,
    OUTPUT_FILENAME,
    P2IndependentFormalResultInvalid,
    materialize_formal_results,
    validate_only,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-result", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--formal-supplement", type=Path, default=DEFAULT_FORMAL_SUPPLEMENT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    kwargs = {
        "formal_supplement_path": args.formal_supplement,
        "protocol_path": args.protocol,
    }
    try:
        if args.validate_only:
            result = validate_only(
                args.raw_result,
                output_directory=args.output_directory,
                **kwargs,
            )
        else:
            result = materialize_formal_results(
                args.raw_result,
                args.output_directory,
                **kwargs,
            )
    except (P2IndependentFormalResultInvalid, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "P2_INDEPENDENT_FORMAL_RESULT_INVALID",
                    "error": str(exc),
                    "statistics_not_run": True,
                    "validate_only": bool(args.validate_only),
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    if args.validate_only:
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "output": str(args.output_directory.resolve() / OUTPUT_FILENAME),
                    "amendment_id": result["amendment_id"],
                    "M_T": result["M_T"],
                    "M_H": result["M_H"],
                    "replicates_requested": result["replicates_requested"],
                    "replicates_successful": result["replicates_successful"],
                    "statistics_not_run": result["statistics_not_run"],
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
