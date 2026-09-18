#!/usr/bin/env python3
"""Deterministically materialize the HarmBench standard text subset for E1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_COLUMNS = (
    "Behavior",
    "FunctionalCategory",
    "SemanticCategory",
    "Tags",
    "ContextString",
    "BehaviorID",
)
ADAPTER_REVISION = "harmbench-e1-csv-to-json-v1"
BENCHMARK = "HarmBench_standard_text"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def materialize(*, source_csv: Path, source_metadata: Path, output_json: Path, output_metadata: Path) -> dict[str, Any]:
    metadata = _read_json(source_metadata)
    if not isinstance(metadata, dict):
        raise ValueError("HarmBench source metadata must be an object")
    revision = metadata.get("revision")
    if not isinstance(revision, str) or not revision:
        raise ValueError("HarmBench source metadata lacks revision")

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_indices: set[int] = set()
    with source_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ValueError("HarmBench CSV header differs from the registered source")
        for source_index, row in enumerate(reader):
            if any(row.get(column) is None for column in EXPECTED_COLUMNS):
                raise ValueError(f"HarmBench CSV row {source_index} is missing a registered field")
            if row["FunctionalCategory"] != "standard":
                continue
            text = row["Behavior"]
            category = row["SemanticCategory"]
            source_id = row["BehaviorID"]
            if not text or not category or not source_id:
                raise ValueError(f"HarmBench standard row {source_index} has an empty mapped field")
            if source_id in seen_ids or source_index in seen_indices:
                raise ValueError("HarmBench source identity is duplicated")
            seen_ids.add(source_id)
            seen_indices.add(source_index)
            records.append(
                {
                    "category": category,
                    "source_id": source_id,
                    "source_index": source_index,
                    "text": text,
                }
            )

    if not records:
        raise ValueError("HarmBench standard subset is empty")
    output = {
        "schema_version": "paper1-broadening-e1-source-v1",
        "benchmark": BENCHMARK,
        "records": records,
    }
    metadata_document = {
        "schema_version": "paper1-broadening-e1-source-metadata-v1",
        "benchmark": BENCHMARK,
        "revision": revision,
        "adapter_revision": ADAPTER_REVISION,
        "source_csv": str(source_csv),
        "source_csv_sha256": _sha256(source_csv),
        "source_metadata": str(source_metadata),
        "source_metadata_sha256": _sha256(source_metadata),
        "filter": "FunctionalCategory == standard",
        "source_index": "0-based CSV data-row order from the all-behaviors source",
        "mapping": {
            "Behavior": "text",
            "SemanticCategory": "category",
            "BehaviorID": "source_id",
        },
        "record_count": len(records),
        "records_sha256": None,
    }
    _write_json(output_json, output)
    metadata_document["records_sha256"] = _sha256(output_json)
    _write_json(output_metadata, metadata_document)
    return {"output": str(output_json), "metadata": str(output_metadata), "record_count": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--source-metadata", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-metadata", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(
        source_csv=args.source_csv,
        source_metadata=args.source_metadata,
        output_json=args.output_json,
        output_metadata=args.output_metadata,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
