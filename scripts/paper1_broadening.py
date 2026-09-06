#!/usr/bin/env python3
"""Bounded CLI for the MBD-NM v2.1 Paper 1 broadening implementation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paper1_broadening.analysis import analyze_records, write_analysis_artifacts
from paper1_broadening.archive import archive_run
from paper1_broadening.common import BroadeningError, atomic_write_json, read_json, read_jsonl
from paper1_broadening.config import default_config, load_config, validate_config
from paper1_broadening.extensions import extension_prerequisites
from paper1_broadening.human import (
    allocate_core_human,
    allocate_extension_human,
    analyze_human_labels,
    save_human_allocation,
    write_blinded_packets,
)
from paper1_broadening.orchestration import fixture_e2e, prepare_run
from paper1_broadening.pipeline import (
    build_directions,
    build_extension_schedule_for_run,
    build_evaluation_schedule_for_run,
    build_screen_schedule_for_run,
    block_artifacts,
    fixture_screen,
    records_for_analysis_artifacts,
    run_real_generation,
    run_real_judge,
    run_real_screen,
)
from paper1_broadening.runtime import discover_assets
from paper1_broadening.smoke import run_fixture_smoke, run_real_smoke


def _config_path(value: str | None) -> Path:
    if value is None:
        return ROOT / "configs" / "paper1_broadening" / "mbd_nm_v21.json"
    return Path(value).resolve()


def _config(value: str | None) -> dict[str, Any]:
    return load_config(_config_path(value))


def _run_dir(args: argparse.Namespace) -> Path:
    if getattr(args, "run_dir", None):
        return Path(args.run_dir).resolve()
    if getattr(args, "config", None):
        candidate = Path(args.config).resolve().parent
        if (candidate / "run_header.json").is_file():
            return candidate
    raise BroadeningError("provide --run-dir or a run-local resolved_config.json with --config")


def _print(value: Mapping[str, Any]) -> None:
    print(json.dumps(dict(value), ensure_ascii=True, indent=2, sort_keys=True))


def _assert_run_not_fixture(run_dir: Path) -> None:
    header = read_json(run_dir / "run_header.json")
    if header.get("fixture") is True:
        raise BroadeningError("fixture run cannot be used for a non-fixture command")


def _human_candidates(run_dir: Path, block: str = "core") -> list[dict[str, Any]]:
    artifacts = block_artifacts(block)
    ledger = read_jsonl(run_dir / artifacts["ledger"])
    judges = {row["response_id"]: row for row in read_jsonl(run_dir / artifacts["judges"])}
    frames = read_json(run_dir / "frames.json")
    prompt_text = {
        row["prompt_id"]: row["text"]
        for frame in ("jbb100", "jbb40", "benign30")
        for row in frames.get(frame, [])
    }
    prompt_text.update({
        row["prompt_id"]: row["text"]
        for row in frames.get("e1", {}).get("records", [])
        if isinstance(row, Mapping) and isinstance(row.get("prompt_id"), str) and isinstance(row.get("text"), str)
    })
    rows: list[dict[str, Any]] = []
    for record in ledger:
        if record.get("terminal_status") != "COMPLETED" or not isinstance(record.get("canonical_text"), str):
            continue
        identity = record["identity"]
        judge = judges.get(record["response_id"])
        if not judge or judge.get("four_class_status") != "PARSED":
            continue
        if record.get("dose_label") not in {"A", "S"}:
            continue
        block = identity["block"]
        if block == "core_harmful_steered":
            cell = "|".join(
                (identity["model_id"], identity["family"], identity["condition"], record["dose_label"])
            )
            audit_block = "core"
        elif block.startswith("E1"):
            cell = "|".join((identity["model_id"], identity["family"], identity["condition"], record["dose_label"]))
            audit_block = "E1"
        elif block.startswith("E2"):
            cell = "|".join((identity["model_id"], identity["family"], identity["condition"], record["dose_label"]))
            audit_block = "E2"
        elif block.startswith("E3"):
            cell = "|".join((identity["model_id"], str(identity["layer"]), identity["condition"], record["dose_label"]))
            audit_block = "E3"
        else:
            continue
        rows.append({
            "response_id": record["response_id"],
            "cell": cell,
            "request": prompt_text.get(identity["prompt_id"], identity["prompt_id"]),
            "response": record["canonical_text"],
            "auto_label": judge["four_class_label"],
            "model_id": identity["model_id"],
            "family": identity["family"],
            "layer": identity["layer"],
            "condition": identity["condition"],
            "dose_label": record["dose_label"],
            "audit_block": audit_block,
        })
    return rows


def command_discover_assets(args: argparse.Namespace) -> dict[str, Any]:
    config = _config(args.config)
    result = discover_assets(config)
    if args.output:
        atomic_write_json(Path(args.output).resolve(), result, overwrite=False)
    return result


def command_prepare(args: argparse.Namespace) -> dict[str, Any]:
    config = _config(args.config)
    run_dir, result = prepare_run(
        config=config,
        repo_root=ROOT,
        run_id=args.run_id,
        output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
    )
    return {"run_dir": str(run_dir), **result, "extension_prerequisites": extension_prerequisites(read_json(run_dir / "frames.json"), config)}


def command_build_directions(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = _run_dir(args)
    _assert_run_not_fixture(run_dir)
    return build_directions(run_dir=run_dir, config=_config(args.config))


def command_smoke(args: argparse.Namespace) -> dict[str, Any]:
    if args.real:
        output_dir = Path(args.output_dir).resolve() if args.output_dir else ROOT / ".codex-temp" / "paper1_broadening_smoke"
        return run_real_smoke(config=_config(args.config), output_dir=output_dir)
    return run_fixture_smoke()


def command_screen(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = _run_dir(args)
    if args.fixture:
        if args.block != "core":
            raise BroadeningError("fixture screen supports only the core block")
        return fixture_screen(run_dir=run_dir, config=_config(args.config))
    _assert_run_not_fixture(run_dir)
    return run_real_screen(run_dir=run_dir, config=_config(args.config), block=args.block)


def command_generate(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = _run_dir(args)
    _assert_run_not_fixture(run_dir)
    config = _config(args.config)
    is_screen = bool(getattr(args, "screen", False))
    if args.build_evaluation_schedule:
        if is_screen:
            raise BroadeningError("screen generation uses the screen command to materialize its schedule")
        if args.block == "core":
            schedule = build_evaluation_schedule_for_run(run_dir=run_dir, config=config)
        else:
            schedule = build_extension_schedule_for_run(
                run_dir=run_dir, config=config, block=args.block,
            )
        return {
            "status": "SCHEDULE_READY", "block": args.block,
            "schedule_count": len(schedule), "run_dir": str(run_dir),
        }
    if args.limit is None and not args.all:
        raise BroadeningError("generation requires --limit N for a bounded job or --all after explicit user authorization")
    if is_screen:
        artifacts = {
            "schedule": f"screen_generation_schedule_{args.block}.jsonl",
            "attempts": f"screen_generation_attempts_{args.block}.jsonl",
            "ledger": f"screen_generation_ledger_{args.block}.jsonl",
            "recovery": f"screen_generation_recovery_{args.block}.json",
            "release": f"screen_behavior_release_{args.block}.json",
        }
    elif args.block == "core":
        artifacts = block_artifacts("core")
    else:
        artifacts = block_artifacts(args.block)
    schedule_path = run_dir / artifacts["schedule"]
    if not schedule_path.is_file():
        phase = "screen" if is_screen else "evaluation"
        raise BroadeningError(
            f"{args.block} {phase} schedule is missing"
        )
    return run_real_generation(
        run_dir=run_dir, config=config, limit=args.limit,
        schedule_filename=artifacts["schedule"],
        attempts_filename=artifacts["attempts"],
        ledger_filename=artifacts["ledger"],
        recovery_filename=artifacts.get("recovery", "generation_recovery.json"),
        release_filename=artifacts.get("release", "behavior_release.json" if args.block == "core" else f"behavior_release_{args.block}.json"),
    )


def command_judge(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = _run_dir(args)
    _assert_run_not_fixture(run_dir)
    if getattr(args, "screen", False):
        artifacts = {
            "schedule": f"screen_generation_schedule_{args.block}.jsonl",
            "attempts": f"screen_generation_attempts_{args.block}.jsonl",
            "judges": f"screen_judge_records_{args.block}.jsonl",
            "behavior_release": f"screen_behavior_release_{args.block}.json",
            "judge_status": f"screen_judge_runtime_status_{args.block}.json",
            "judge_release": f"screen_judge_release_{args.block}.json",
        }
    else:
        artifacts = block_artifacts(args.block)
    if not (run_dir / artifacts["schedule"]).is_file():
        phase = "screen" if getattr(args, "screen", False) else "evaluation"
        raise BroadeningError(f"{args.block} {phase} schedule is missing")
    return run_real_judge(
        run_dir=run_dir, config=_config(args.config), binary=args.binary,
        schedule_filename=artifacts["schedule"],
        attempts_filename=artifacts["attempts"],
        judge_filename=artifacts["judges"],
        judge_status_filename=artifacts.get("judge_status", "judge_runtime_status.json" if args.block == "core" else f"judge_runtime_status_{args.block}.json"),
        judge_release_filename=artifacts.get("judge_release", "judge_release.json" if args.block == "core" else f"judge_release_{args.block}.json"),
        behavior_release_filename=artifacts.get("behavior_release", "behavior_release.json" if args.block == "core" else f"behavior_release_{args.block}.json"),
    )


def command_analyze(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = _run_dir(args)
    suffix = "" if args.block == "core" else f"_{args.block}"
    if args.human:
        allocation = read_json(run_dir / f"human_allocation{suffix}.json")
        labels_path = run_dir / f"human_labels{suffix}.jsonl"
        if not labels_path.is_file():
            return {"status": "HUMAN_LABELS_PENDING", "run_dir": str(run_dir)}
        result = analyze_human_labels(allocation, read_jsonl(labels_path))
        atomic_write_json(run_dir / f"human_analysis{suffix}.json", result, overwrite=True)
        return result
    records = records_for_analysis_artifacts(run_dir=run_dir, block=args.block)
    result = analyze_records(records, _config(args.config)["protocol"]["bootstrap"])
    analysis_dir = run_dir if args.block == "core" else run_dir / f"analysis_{args.block}"
    artifacts = write_analysis_artifacts(result, analysis_dir)
    result = {**result, "analysis_revision": artifacts["analysis_revision"]}
    return {"analysis": result, "artifacts": artifacts}


def command_sample_human(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = _run_dir(args)
    rows = _human_candidates(run_dir, args.block)
    if args.block == "core":
        allocation = allocate_core_human([row for row in rows if row["audit_block"] == "core"])
    else:
        allocation = allocate_extension_human(
            [row for row in rows if row["audit_block"] == args.block], block=args.block
        )
    suffix = "" if args.block == "core" else f"_{args.block}"
    save_human_allocation(allocation, run_dir / f"human_allocation{suffix}.json")
    packet_paths = write_blinded_packets(
        allocation,
        run_dir / f"human_packets{suffix}",
        "Apply the supplied four-class rubric. Do not infer experiment metadata.",
    )
    return {"allocation": allocation, "packet_paths": packet_paths}


def command_archive(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = _run_dir(args)
    header = read_json(run_dir / "run_header.json")
    frames = read_json(run_dir / "frames.json")
    manifest = archive_run(
        run_dir=run_dir,
        repo_root=ROOT,
        run_header=header,
        source_ids={
            "frame_digest": frames.get("frame_digest"),
            "jbb_source_revisions": sorted({row.get("source_revision") for row in frames.get("jbb100", [])}),
            "fixture": header.get("fixture", False),
        },
        require_human=args.require_human,
    )
    return manifest


def command_fixture_e2e(_args: argparse.Namespace) -> dict[str, Any]:
    return fixture_e2e(repo_root=ROOT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover-assets")
    discover.add_argument("--config")
    discover.add_argument("--output")
    discover.set_defaults(handler=command_discover_assets)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--config")
    prepare.add_argument("--run-id")
    prepare.add_argument("--output-dir")
    prepare.set_defaults(handler=command_prepare)

    directions = subparsers.add_parser("build-directions")
    directions.add_argument("--config", required=True)
    directions.add_argument("--run-dir")
    directions.set_defaults(handler=command_build_directions)

    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("--config")
    smoke.add_argument("--real", action="store_true")
    smoke.add_argument("--output-dir")
    smoke.set_defaults(handler=command_smoke)

    screen = subparsers.add_parser("screen")
    screen.add_argument("--config", required=True)
    screen.add_argument("--run-dir")
    screen.add_argument("--block", choices=["core", "E1", "E2", "E3"], default="core")
    screen.add_argument("--fixture", action="store_true")
    screen.set_defaults(handler=command_screen)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--config", required=True)
    generate.add_argument("--run-dir")
    generate.add_argument("--block", choices=["core", "E1", "E2", "E3"], default="core")
    generate.add_argument("--limit", type=int)
    generate.add_argument("--all", action="store_true")
    generate.add_argument("--build-evaluation-schedule", action="store_true")
    generate.add_argument("--screen", action="store_true", help=argparse.SUPPRESS)
    generate.set_defaults(handler=command_generate)

    judge = subparsers.add_parser("judge")
    judge.add_argument("--config", required=True)
    judge.add_argument("--run-dir")
    judge.add_argument("--block", choices=["core", "E1", "E2", "E3"], default="core")
    judge.add_argument("--binary", action="store_true")
    judge.add_argument("--screen", action="store_true", help=argparse.SUPPRESS)
    judge.set_defaults(handler=command_judge)

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--config", required=True)
    analyze.add_argument("--run-dir")
    analyze.add_argument("--block", choices=["core", "E1", "E2", "E3"], default="core")
    analyze.add_argument("--human", action="store_true")
    analyze.set_defaults(handler=command_analyze)

    human = subparsers.add_parser("sample-human")
    human.add_argument("--config", required=True)
    human.add_argument("--run-dir")
    human.add_argument("--block", choices=["core", "E1", "E2", "E3"], required=True)
    human.set_defaults(handler=command_sample_human)

    archive = subparsers.add_parser("archive")
    archive.add_argument("--config", required=True)
    archive.add_argument("--run-dir")
    archive.add_argument("--require-human", action="store_true")
    archive.set_defaults(handler=command_archive)

    fixture = subparsers.add_parser("fixture-e2e")
    fixture.set_defaults(handler=command_fixture_e2e)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        _print(args.handler(args))
    except BroadeningError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
