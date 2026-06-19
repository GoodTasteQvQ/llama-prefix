#!/usr/bin/env python
"""Download and export JailbreakBench JBB-Behaviors to local files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


DATASET_NAME = "JailbreakBench/JBB-Behaviors"
DATASET_CONFIG = "behaviors"
DEFAULT_SPLIT = "harmful"


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Download JBB-Behaviors from Hugging Face and export to a local file.",
    )
    parser.add_argument(
        "--dataset-name",
        default=DATASET_NAME,
        help=f"Hugging Face dataset name. Default: {DATASET_NAME}",
    )
    parser.add_argument(
        "--dataset-config",
        default=DATASET_CONFIG,
        help=f"Hugging Face dataset config. Default: {DATASET_CONFIG}",
    )
    parser.add_argument(
        "--split",
        default=DEFAULT_SPLIT,
        help=f"Dataset split to download. Default: {DEFAULT_SPLIT}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root / "data" / "jbb_behaviors_harmful.json",
        help="Where to save the exported dataset.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "jsonl", "csv"],
        default="json",
        help="Export format. Default: json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of rows to keep after download.",
    )
    return parser


def _load_dataset(dataset_name: str, dataset_config: str, split: str):
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "The 'datasets' package is required. Install it with:\n"
            "  python -m pip install -U datasets"
        ) from exc

    return load_dataset(dataset_name, dataset_config, split=split)


def _write_json(output_path: Path, rows: list[dict]) -> None:
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(output_path: Path, rows: list[dict]) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_csv(output_path: Path, rows: list[dict]) -> None:
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = build_parser().parse_args()
    dataset = _load_dataset(args.dataset_name, args.dataset_config, args.split)
    rows = [dict(row) for row in dataset]
    if args.limit is not None:
        rows = rows[: args.limit]

    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        _write_json(output_path, rows)
    elif args.format == "jsonl":
        _write_jsonl(output_path, rows)
    else:
        _write_csv(output_path, rows)

    metadata_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    metadata = {
        "dataset_name": args.dataset_name,
        "dataset_config": args.dataset_config,
        "split": args.split,
        "format": args.format,
        "num_rows": len(rows),
        "output": str(output_path),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(rows)} rows to {output_path}")
    print(f"Saved metadata to {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
