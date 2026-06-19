#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean


def summarize_group(payload: dict) -> dict:
    runs = payload.get("runs", [])
    if not runs:
        return {
            "num_runs": 0,
            "mean_arr": 0.0,
            "mean_repetition_rate": 0.0,
            "mean_latency_seconds": 0.0,
            "generated_steered_calls": 0,
        }
    return {
        "num_runs": len(runs),
        "mean_arr": mean(float(run.get("mean_arr", 0.0)) for run in runs),
        "mean_repetition_rate": mean(
            float(run.get("mean_repetition_rate", 0.0)) for run in runs
        ),
        "mean_latency_seconds": mean(
            float(run.get("mean_latency_seconds", 0.0)) for run in runs
        ),
        "generated_steered_calls": sum(
            int(run.get("phase_audit_summary", {}).get("generated_steered_calls", 0))
            for run in runs
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize stage1 phase-aware reproduction outputs.")
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rows = []
    for item in args.input:
        payload = json.loads(Path(item).read_text(encoding="utf-8"))
        rows.append({
            "input": item,
            "track": payload.get("track"),
            "mode": payload.get("mode"),
            "num_runs": len(payload.get("runs", [])),
            "vector_pool": payload.get("vector_pool", {}),
            "vector_start": payload.get("vector_start"),
            "vector_end": payload.get("vector_end"),
            "vector_indices": payload.get("vector_indices"),
            "grid": payload.get("alpha_grid") or payload.get("c_grid"),
            "prompt_limit": payload.get("prompt_limit"),
            "prompt_offset": payload.get("prompt_offset"),
            "group_summary": summarize_group(payload),
        })
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved stage1 summary to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
