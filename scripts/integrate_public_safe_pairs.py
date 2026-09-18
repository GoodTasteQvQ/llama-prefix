#!/usr/bin/env python3
"""Validate and deterministically convert the public semantic pair snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


DATASET = "heretic-org/Semantic-Harmful + Semantic-Harmless"
HARMFUL_REVISION = "001ca2ceaef94a748235e0ba1366aee48436e286"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--integration-manifest", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    metadata = source.get("metadata")
    pairs = source.get("pairs")
    if not isinstance(metadata, dict) or not isinstance(pairs, list):
        raise SystemExit("source must contain metadata and pairs")
    if len(pairs) != 416 or metadata.get("num_matched_pairs") != 416:
        raise SystemExit("pair count or metadata count is not 416")
    if metadata.get("threshold") != 0.6 or metadata.get("matching_strategy") != "hungarian":
        raise SystemExit("unexpected matching metadata")

    harmful_texts: set[str] = set()
    harmless_texts: set[str] = set()
    harmful_indices: set[int] = set()
    harmless_indices: set[int] = set()
    converted: list[dict[str, object]] = []
    for row in pairs:
        if not isinstance(row, dict):
            raise SystemExit("pair is not an object")
        harmful, harmless = row.get("harmful"), row.get("harmless")
        score = row.get("score")
        harmful_index, harmless_index = row.get("harmful_index"), row.get("harmless_index")
        if not isinstance(harmful, str) or not harmful.strip() or not isinstance(harmless, str) or not harmless.strip():
            raise SystemExit("pair text is empty or not a string")
        if harmful in harmful_texts or harmless in harmless_texts:
            raise SystemExit("pair text is not unique")
        if isinstance(harmful_index, bool) or not isinstance(harmful_index, int) or harmful_index < 0:
            raise SystemExit("harmful index is invalid")
        if isinstance(harmless_index, bool) or not isinstance(harmless_index, int) or harmless_index < 0:
            raise SystemExit("harmless index is invalid")
        if harmful_index in harmful_indices or harmless_index in harmless_indices:
            raise SystemExit("pair indices are not unique")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)) or float(score) < 0.6:
            raise SystemExit("pair score is invalid")
        harmful_texts.add(harmful)
        harmless_texts.add(harmless)
        harmful_indices.add(harmful_index)
        harmless_indices.add(harmless_index)
        converted.append({
            "pair_id": f"semantic-pair:{harmful_index}:{harmless_index}",
            "harmful": harmful,
            "harmless": harmless,
            "semantic_score": float(score),
            "harmful_index": harmful_index,
            "harmless_index": harmless_index,
            "source_revision": HARMFUL_REVISION,
            "source_dataset": DATASET,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(converted))
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "UNKNOWN"
    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    manifest["integration_schema"] = "public-safe-pairs-semantic-v1"
    manifest["conversion"] = {
        "script": "scripts/integrate_public_safe_pairs.py",
        "conversion_code_commit": commit,
        "output_path": str(args.output),
        "output_sha256": sha256(args.output),
        "output_count": len(converted),
        "input_sha256": sha256(args.source),
    }
    args.integration_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.integration_manifest.write_bytes(canonical(manifest))
    print(json.dumps({"output": str(args.output), "count": len(converted), "output_sha256": manifest["conversion"]["output_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
