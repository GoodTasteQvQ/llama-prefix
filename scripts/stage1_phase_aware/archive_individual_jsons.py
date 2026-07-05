#!/usr/bin/env python
"""Archive individual experiment JSON files from flat root into structured layout.

Moves files matching stage1_*_localdata_vector*.json from the root of
--root (default results/stage1_phase_aware) into:
  individual_json/model={model}/{track}/{method}/{strength_key}{strength}/

Supports --dry-run (default), --execute, and --restore.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

# stage1_{track}_{model}_{method}_localdata_vector{XXXX}_{alpha_or_c}{X.XX}.json
# method can contain underscores (e.g. decode_only, rogue_v1, first_k, no_cache)
FILENAME_RE = re.compile(
    r"^stage1_(?P<track>track[AB])_(?P<model>[a-z0-9]+)_(?P<method>[a-z0-9_]+)"
    r"_localdata_vector(?P<vector>\d{4})_(?P<sk>alpha|c)(?P<strength>\d+\.\d+)\.json$"
)

METHODS = {"rogue_v1", "decode_only", "full", "decay", "first_k", "no_cache"}


def parse_filename(name: str) -> dict[str, Any] | None:
    m = FILENAME_RE.match(name)
    if not m:
        return None
    d = m.groupdict()
    method = d["method"]
    if method not in METHODS:
        return None
    return {
        "track": d["track"],
        "model": d["model"],
        "method": method,
        "vector_index": int(d["vector"]),
        "strength_key": d["sk"],
        "strength": d["strength"],
    }


def dest_path(root: Path, info: dict[str, Any], filename: str) -> Path:
    return (
        root
        / "individual_json"
        / f"model={info['model']}"
        / info["track"]
        / info["method"]
        / f"{info['strength_key']}{info['strength']}"
        / filename
    )


def build_manifest(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for f in sorted(root.iterdir()):
        if not f.is_file():
            continue
        info = parse_filename(f.name)
        if info is None:
            continue
        dp = dest_path(root, info, f.name)
        entries.append(
            {
                "source_path": str(f),
                "dest_path": str(dp),
                "size_bytes": f.stat().st_size,
                **info,
            }
        )
    return entries


def print_summary(entries: list[dict[str, Any]], label: str = "dry-run") -> None:
    by_model: dict[str, int] = {}
    by_group: dict[str, int] = {}
    for e in entries:
        by_model[e["model"]] = by_model.get(e["model"], 0) + 1
        g = f"{e['model']}/{e['track']}/{e['method']}"
        by_group[g] = by_group.get(g, 0) + 1

    print(f"\n=== {label} summary ===")
    print(f"Total files: {len(entries)}")
    print("\nBy model:")
    for m, c in sorted(by_model.items()):
        print(f"  {m}: {c}")
    print("\nBy group (top 10):")
    for g, c in sorted(by_group.items(), key=lambda x: -x[1])[:10]:
        print(f"  {g}: {c}")


def execute_move(
    entries: list[dict[str, Any]], root: Path, manifest_path: Path
) -> dict[str, int]:
    stats = {"moved": 0, "already_exists": 0, "skipped": 0}
    manifest_lines: list[str] = []

    for e in entries:
        src = Path(e["source_path"])
        dst = Path(e["dest_path"])

        if dst.exists():
            dst_size = dst.stat().st_size
            if dst_size == e["size_bytes"]:
                stats["already_exists"] += 1
                manifest_lines.append(json.dumps({**e, "status": "already_exists"}))
                continue
            else:
                print(f"ERROR: dest exists with different size: {dst}")
                print(f"  expected {e['size_bytes']}, got {dst_size}")
                sys.exit(1)

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        stats["moved"] += 1
        manifest_lines.append(json.dumps({**e, "status": "moved"}))

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return stats


def restore(root: Path, manifest_path: Path) -> dict[str, int]:
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}")
        sys.exit(1)

    stats = {"restored": 0, "already_exists": 0, "skipped": 0}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("status") not in ("moved", "already_exists"):
            continue
        src = Path(e["dest_path"])
        dst = Path(e["source_path"])
        if not src.exists():
            stats["skipped"] += 1
            continue
        if dst.exists():
            stats["already_exists"] += 1
            continue
        shutil.move(str(src), str(dst))
        stats["restored"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="results/stage1_phase_aware", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    # Default to dry-run if no mode specified
    if not args.execute and not args.restore:
        args.dry_run = True

    root = args.root.resolve()
    manifest_path = root / "individual_json_manifest.jsonl"

    if args.restore:
        print("Restoring files from manifest...")
        stats = restore(root, manifest_path)
        print(f"Restored: {stats['restored']}, "
              f"already_exists: {stats['already_exists']}, "
              f"skipped: {stats['skipped']}")
        return 0

    print(f"Scanning {root} for individual JSON files...")
    t0 = time.time()
    entries = build_manifest(root)
    print(f"Found {len(entries)} files in {time.time() - t0:.1f}s")

    if not entries:
        print("Nothing to do.")
        return 0

    if args.dry_run:
        print_summary(entries, label="dry-run")
        print("\nRun with --execute to perform the move.")
        return 0

    # --execute
    print("Executing move...")
    t0 = time.time()
    stats = execute_move(entries, root, manifest_path)
    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  moved: {stats['moved']}")
    print(f"  already_exists: {stats['already_exists']}")

    # Write summary
    summary_path = root / "individual_json_summary.json"
    summary = {
        "total_files": len(entries),
        "moved": stats["moved"],
        "already_exists": stats["already_exists"],
        "manifest": str(manifest_path),
        "elapsed_seconds": round(elapsed, 1),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary written to {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
