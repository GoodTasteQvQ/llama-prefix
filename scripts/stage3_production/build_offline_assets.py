#!/usr/bin/env python3
"""Generate blocked offline inventory/manifest without rewriting source JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import file_sha256  # noqa: E402
from stage3_pipeline.offline_assets import (  # noqa: E402
    build_external_dependency_inventory,
    build_offline_asset_manifest,
)
from stage3_pipeline.local_temp import require_project_local_temp  # noqa: E402


def write_once(path: Path, document: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(
        json.dumps(document, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    require_project_local_temp(ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite output directory: {output}")
    output.mkdir(parents=True)

    inventory = build_external_dependency_inventory(ROOT)
    manifest = build_offline_asset_manifest(ROOT)
    call_graph = {
        "schema_version": "paper1-stage3-production-call-graph-v1",
        "production_entrypoints": [
            "stage3_pipeline.core.GenerationProducer",
            "stage3_pipeline.offline_assets.OfflineJsonLoader",
            "stage3_pipeline.references.ReferenceAdapter",
            "stage3_pipeline.execution.build_logical_plan",
        ],
        "network_calls": [],
        "remote_dataset_loaders": [],
        "online_fallback": False,
        "local_download_only": ["scripts/download_jbb_behaviors.py"],
        "normative_reference_only": ["scripts/judge_phase_outputs.py"],
        "out_of_scope_historical": ["activation_guard/runner.py"],
        "server_runtime_requirements": [
            "HF_HUB_OFFLINE=1",
            "HF_DATASETS_OFFLINE=1",
            "TRANSFORMERS_OFFLINE=1",
            "checkpoint/tokenizer/template resolved from preinstalled local paths",
            "trust_remote_code=false",
            "OS/container egress denied and independently verified before formal calls",
        ],
    }
    write_once(output / "external_dependency_inventory.json", inventory)
    write_once(output / "offline_asset_manifest.json", manifest)
    write_once(output / "production_call_graph.json", call_graph)
    checksums = []
    for asset in manifest["candidate_assets"]:
        checksums.append(f"{asset['raw_sha256']}  {asset['relative_path']}")
    (output / "candidate_checksums.sha256").write_text(
        "\n".join(checksums) + "\n", encoding="ascii", newline="\n"
    )
    artifacts = []
    for path in sorted(output.iterdir()):
        artifacts.append({
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        })
    receipt = {
        "schema_version": "paper1-stage3-offline-build-receipt-v1",
        "offline_asset_status": manifest["offline_asset_status"],
        "formal_inputs": [],
        "bundle_file": None,
        "bundle_sha256": None,
        "bundle_bytes": None,
        "artifacts": artifacts,
        "source_json_modified": False,
        "formal_experiment_run": False,
        "reason_bundle_not_generated": "DATA_IDENTITY_BLOCKED: no frozen FORMAL_INPUT row binding",
    }
    write_once(output / "offline_build_receipt.json", receipt)
    print(json.dumps({
        "marker": "STAGE3_OFFLINE_INVENTORY_BUILT",
        "offline_asset_status": manifest["offline_asset_status"],
        "formal_inputs": 0,
        "bundle_generated": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
