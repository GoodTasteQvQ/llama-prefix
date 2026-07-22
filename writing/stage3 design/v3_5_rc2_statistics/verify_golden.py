#!/usr/bin/env python3
"""Verify code/input/expected hashes and exact golden output."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from reference_statistics import evaluate_failure_fixture, evaluate_fixture


ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest_path = ROOT / "statistical_reference_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative, expected_hash in manifest["sha256"].items():
        actual_hash = sha256(ROOT / relative)
        if actual_hash != expected_hash:
            raise SystemExit(f"HASH_MISMATCH {relative}: {actual_hash} != {expected_hash}")

    input_data = json.loads((ROOT / "fixtures/statistical_golden_input.json").read_text(encoding="utf-8"))
    expected = json.loads((ROOT / "fixtures/statistical_golden_expected.json").read_text(encoding="utf-8"))
    actual = evaluate_fixture(input_data)
    if canonical(actual) != canonical(expected):
        raise SystemExit("GOLDEN_MISMATCH")
    failure_spec = json.loads((ROOT / "fixtures/failure_golden_input.json").read_text(encoding="utf-8"))
    failure_expected = json.loads((ROOT / "fixtures/failure_golden_expected.json").read_text(encoding="utf-8"))
    failure_actual = evaluate_failure_fixture(input_data, failure_spec)
    if canonical(failure_actual) != canonical(failure_expected):
        raise SystemExit("FAILURE_GOLDEN_MISMATCH")
    print("STATISTICAL_GOLDEN_PASS")
    return 0


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
