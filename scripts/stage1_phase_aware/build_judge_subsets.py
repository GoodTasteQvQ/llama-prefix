#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_STRENGTHS = [0.0, 1.0, 1.25, 1.5, 2.0]
DEFAULT_GROUPS = [
    ("trackA", "rogue_v1"),
    ("trackA", "decode_only"),
    ("trackA", "full"),
    ("trackB", "rogue_v1"),
    ("trackB", "decode_only"),
    ("trackB", "full"),
]


def parse_strengths(raw: str) -> list[float]:
    values = [part.strip() for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("--strengths cannot be empty")
    return [float(value) for value in values]


def parse_groups(raw: str) -> list[tuple[str, str]]:
    groups: list[tuple[str, str]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Invalid group '{item}'. Expected trackA:rogue_v1")
        track, variant = item.split(":", 1)
        if track not in {"trackA", "trackB"}:
            raise ValueError(f"Invalid track '{track}' in group '{item}'")
        groups.append((track, variant))
    if not groups:
        raise ValueError("--groups cannot be empty")
    return groups


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Paper 1 judge subsets from stage1 formal aggregate outputs.",
    )
    parser.add_argument(
        "--formal-dir",
        default="results/stage1_phase_aware/formal/qwen25",
        help="Directory containing trackA/trackB formal aggregate JSON files.",
    )
    parser.add_argument(
        "--individual-dir",
        default="results/stage1_phase_aware",
        help="Directory containing per-vector per-strength JSON outputs with records.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/stage1_phase_aware/formal/qwen25/judge_subsets",
    )
    parser.add_argument(
        "--model-key",
        default="qwen25",
        help="Model key used in stage1 filenames, e.g. qwen25 or llama31.",
    )
    parser.add_argument(
        "--groups",
        default=",".join(f"{track}:{variant}" for track, variant in DEFAULT_GROUPS),
        help="Comma-separated groups, e.g. trackA:rogue_v1,trackB:decode_only.",
    )
    parser.add_argument(
        "--strengths",
        default=",".join(str(value) for value in DEFAULT_STRENGTHS),
        help="Comma-separated alpha/c values to sample.",
    )
    parser.add_argument("--samples-per-strength", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing subset files.",
    )
    parser.add_argument(
        "--index-name",
        default="index.json",
        help="Index filename to write inside output-dir.",
    )
    return parser


def formal_path(formal_dir: Path, track: str, variant: str, model_key: str) -> Path:
    prefix = "stage1_trackA" if track == "trackA" else "stage1_trackB"
    return formal_dir / track / f"{prefix}_{model_key}_{variant}_formal_v0000_0999.json"


def strength_key(track: str) -> str:
    return "alpha" if track == "trackA" else "coefficient_c"


def individual_filename(
    track: str,
    variant: str,
    vector_index: int,
    strength: float,
    model_key: str,
) -> str:
    track_name = "trackA" if track == "trackA" else "trackB"
    strength_name = "alpha" if track == "trackA" else "c"
    return (
        f"stage1_{track_name}_{model_key}_{variant}_localdata_"
        f"vector{vector_index:04d}_{strength_name}{strength:.2f}.json"
    )


def output_filename(track: str, variant: str, strength: float, model_key: str) -> str:
    strength_name = "alpha" if track == "trackA" else "c"
    return f"stage1_{track}_{model_key}_{variant}_{strength_name}{strength:.2f}_judge_subset.json"


def float_equal(left: Any, right: float) -> bool:
    return abs(float(left) - float(right)) < 1e-9


def load_record(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in individual file {path}: {exc}") from exc
    records = payload.get("records", [])
    if not records:
        raise ValueError(f"No records found in {path}")
    record = dict(records[0])
    record["source_experiment_name"] = payload.get("experiment_name")
    record["source_file"] = str(path)
    record["source_attack_strength_summary"] = payload.get("attack_strength_summary", {})
    return record


def build_subset(
    *,
    formal_payload: dict[str, Any],
    individual_dir: Path,
    track: str,
    variant: str,
    strength: float,
    model_key: str,
    sample_count: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    key = strength_key(track)
    candidates = [
        run for run in formal_payload.get("runs", []) if float_equal(run.get(key), strength)
    ]
    if len(candidates) < sample_count:
        raise ValueError(
            f"Only {len(candidates)} candidates for {track}/{variant} {key}={strength}; "
            f"need {sample_count}."
        )

    selected = rng.sample(candidates, sample_count)
    records: list[dict[str, Any]] = []
    missing: list[str] = []
    selected_runs: list[dict[str, Any]] = []
    for run in selected:
        vector_index = int(run["vector_index"])
        filename = (
            f"{run['experiment_name']}.json"
            if run.get("experiment_name")
            else individual_filename(track, variant, vector_index, strength, model_key)
        )
        path = individual_dir / filename
        selected_runs.append(
            {
                "vector_index": vector_index,
                key: strength,
                "formal_run": run,
                "individual_file": str(path),
            }
        )
        if not path.exists():
            missing.append(str(path))
            continue
        record = load_record(path)
        record["judge_subset"] = {
            "track": track,
            "variant": variant,
            "strength_key": key,
            "strength": strength,
            "vector_index": vector_index,
        }
        records.append(record)
    return records, missing, selected_runs


def main() -> int:
    args = build_parser().parse_args()
    formal_dir = Path(args.formal_dir)
    individual_dir = Path(args.individual_dir)
    output_dir = Path(args.output_dir)
    groups = parse_groups(args.groups)
    model_key = args.model_key
    strengths = parse_strengths(args.strengths)
    rng = random.Random(args.seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_rows = []
    all_missing: list[str] = []
    for track, variant in groups:
        aggregate_path = formal_path(formal_dir, track, variant, model_key)
        if not aggregate_path.exists():
            raise FileNotFoundError(f"Missing formal aggregate: {aggregate_path}")
        formal_payload = json.loads(aggregate_path.read_text(encoding="utf-8"))
        for strength in strengths:
            records, missing, selected_runs = build_subset(
                formal_payload=formal_payload,
                individual_dir=individual_dir,
                track=track,
                variant=variant,
                strength=strength,
                model_key=model_key,
                sample_count=args.samples_per_strength,
                rng=rng,
            )
            all_missing.extend(missing)
            if missing:
                continue

            out_path = output_dir / output_filename(track, variant, strength, model_key)
            if out_path.exists() and not args.overwrite:
                raise FileExistsError(f"Refusing to overwrite {out_path}; pass --overwrite")

            payload = {
                "experiment_name": out_path.stem,
                "subset_protocol": "paper1_stage1_judge_subset",
                "mode": "harmful",
                "track": formal_payload.get("track"),
                "stage1_track": track,
                "variant": variant,
                "strength_key": strength_key(track),
                "strength": strength,
                "sample_seed": args.seed,
                "num_records": len(records),
                "source_formal_aggregate": str(aggregate_path),
                "selected_runs": selected_runs,
                "records": records,
            }
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            index_rows.append(
                {
                    "path": str(out_path),
                    "stage1_track": track,
                    "variant": variant,
                    "strength": strength,
                    "num_records": len(records),
                }
            )

    if all_missing:
        missing_path = output_dir / "missing_files.json"
        missing_path.write_text(
            json.dumps(all_missing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise FileNotFoundError(
            f"Missing {len(all_missing)} individual files. See {missing_path}"
        )

    index_path = output_dir / args.index_name
    index_path.write_text(json.dumps(index_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(index_rows)} judge subsets to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
