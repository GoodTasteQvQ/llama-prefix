#!/usr/bin/env python
"""Explicitly reconstruct a pinned JBB-Behaviors source file on a connected workstation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


DATASET_NAME = "JailbreakBench/JBB-Behaviors"
DATASET_CONFIG = "behaviors"
DEFAULT_SPLIT = "harmful"
PINNED_REVISION = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_ROW_COUNT = 100
EXPECTED_ORDERED_FIELDS = ["Index", "Goal", "Target", "Behavior", "Category", "Source"]


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "Local-only JBB source reconstruction. This command is forbidden in the "
            "Stage 3 production/server call graph."
        ),
    )
    parser.add_argument(
        "--revision",
        required=True,
        help="Exact lowercase 40-hex Hugging Face dataset commit; branches/tags are rejected.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root / "data" / "jbb_behaviors_harmful.json",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Permit replacement only after the existing and candidate hashes are bound.",
    )
    parser.add_argument(
        "--expected-existing-sha256",
        help="Required exact current hash when --replace-existing is used.",
    )
    parser.add_argument(
        "--approve-replacement-sha256",
        help=(
            "Exact candidate hash approved after a prior mismatch report; required when "
            "the candidate differs from the existing file."
        ),
    )
    return parser


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_dataset(
    revision: str,
):
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit("The local preparation environment lacks the pinned 'datasets' package.") from exc

    return load_dataset(
        DATASET_NAME,
        DATASET_CONFIG,
        split=DEFAULT_SPLIT,
        revision=revision,
        trust_remote_code=False,
    )


def _ordered_schema(rows: list[dict]) -> tuple[list[str], dict[str, list[str]]]:
    if not rows:
        return [], {}
    ordered_fields = list(rows[0])
    if any(list(row) != ordered_fields for row in rows):
        raise SystemExit("Downloaded rows do not share one exact ordered schema; refusing export.")
    field_types = {
        field: sorted({type(row[field]).__name__ for row in rows})
        for field in ordered_fields
    }
    return ordered_fields, field_types


def _write_export(output_path: Path, rows: list[dict]) -> None:
    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(rows, ensure_ascii=False, allow_nan=False, indent=2))


def _validate_sha(value: str | None, label: str) -> str:
    if value is None or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SystemExit(f"{label} must be an exact lowercase SHA256.")
    return value


def main() -> int:
    args = build_parser().parse_args()
    if not PINNED_REVISION.fullmatch(args.revision):
        raise SystemExit("--revision must be an exact lowercase 40-hex commit, never main/latest/tag.")
    output_path = args.output.expanduser().resolve()
    metadata_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    existing_hash = file_sha256(output_path) if output_path.exists() else None
    if output_path.exists() or metadata_path.exists():
        if not args.replace_existing:
            raise SystemExit("Output or metadata already exists; default overwrite policy is DENY.")
        expected_existing = _validate_sha(
            args.expected_existing_sha256,
            "--expected-existing-sha256",
        )
        if existing_hash is None or existing_hash != expected_existing:
            raise SystemExit(
                f"Existing output hash mismatch: observed={existing_hash}, expected={expected_existing}."
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    staged_output = output_path.with_name(output_path.name + ".stage3-download.tmp")
    staged_metadata = metadata_path.with_name(metadata_path.name + ".stage3-download.tmp")
    if staged_output.exists() or staged_metadata.exists():
        raise SystemExit("Staging target already exists; refusing to overwrite it.")

    dataset = _load_dataset(args.revision)
    rows = [dict(row) for row in dataset]
    ordered_fields, field_types = _ordered_schema(rows)
    if len(rows) != EXPECTED_ROW_COUNT or ordered_fields != EXPECTED_ORDERED_FIELDS:
        raise SystemExit(
            "Pinned source does not match the expected 100-row ordered JBB harmful schema; "
            "refusing export."
        )
    indices = [row["Index"] for row in rows]
    if (
        any(not isinstance(value, int) or isinstance(value, bool) for value in indices)
        or len(indices) != len(set(indices))
    ):
        raise SystemExit("Pinned source has invalid or duplicate Index identities; refusing export.")

    try:
        _write_export(staged_output, rows)
        candidate_hash = file_sha256(staged_output)
        if existing_hash is not None and candidate_hash != existing_hash:
            if args.approve_replacement_sha256 != candidate_hash:
                raise SystemExit(
                    "Candidate differs from existing output; no replacement occurred. "
                    f"existing_sha256={existing_hash} candidate_sha256={candidate_hash}. "
                    "Review first, then rerun with --approve-replacement-sha256 set to the "
                    "reported candidate hash."
                )
        elif args.approve_replacement_sha256 is not None:
            _validate_sha(args.approve_replacement_sha256, "--approve-replacement-sha256")

        metadata = {
            "schema_version": "jbb-local-source-reconstruction-v1",
            "dataset_name": DATASET_NAME,
            "dataset_config": DATASET_CONFIG,
            "split": DEFAULT_SPLIT,
            "source_revision_commit": args.revision,
            "trust_remote_code": False,
            "format": "json",
            "row_count": len(rows),
            "exact_ordered_field_names": ordered_fields,
            "observed_python_field_types": field_types,
            "stable_identity_field": "Index",
            "duplicate_identity_count": 0,
            "raw_file_sha256": candidate_hash,
            "byte_length": staged_output.stat().st_size,
            "dataset_fingerprint": getattr(dataset, "_fingerprint", None),
            "output_filename": output_path.name,
            "previous_raw_file_sha256": existing_hash,
            "production_reachable": False,
        }
        with staged_metadata.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(metadata, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
                + "\n"
            )
        staged_output.replace(output_path)
        staged_metadata.replace(metadata_path)
    finally:
        if staged_output.exists():
            staged_output.unlink()
        if staged_metadata.exists():
            staged_metadata.unlink()

    print(f"Saved {len(rows)} rows with raw SHA256 {candidate_hash}.")
    print(f"Pinned source commit: {args.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
