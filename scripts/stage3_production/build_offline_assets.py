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
    build_bundle,
    build_external_dependency_inventory,
    build_offline_asset_manifest,
    strict_json_loads,
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


BINDING_DOCUMENT_FILES = {
    "checkpoint": "checkpoint_identity_attestation.json",
    "judge": "judge_identity_attestation.json",
    "vectors": "stage3_vector_manifest.json",
    "base_anchor": "base_anchor_binding_manifest.json",
    "prompt_frames": "prompt_frame_binding_manifest.json",
}


def load_binding_documents(root: Path) -> dict[str, dict[str, object]]:
    resolved = root.resolve()
    if not resolved.is_dir() or resolved.is_symlink():
        raise RuntimeError(f"binding root is missing or linked: {resolved}")
    documents = {}
    for role, name in BINDING_DOCUMENT_FILES.items():
        path = resolved / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"binding document is missing or linked: {name}")
        document = strict_json_loads(path.read_bytes().decode("utf-8"))
        if not isinstance(document, dict):
            raise RuntimeError(f"binding document must be an object: {name}")
        documents[role] = document
    return documents


def main() -> int:
    require_project_local_temp(ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, default=ROOT)
    parser.add_argument("--binding-root", type=Path)
    parser.add_argument("--bundle-output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite output directory: {output}")
    output.mkdir(parents=True)

    asset_root = args.asset_root.resolve()
    binding_root = args.binding_root.resolve() if args.binding_root is not None else None
    if (binding_root is None) != (args.bundle_output is None):
        raise SystemExit("--binding-root and --bundle-output must be supplied together")
    binding_documents = load_binding_documents(binding_root) if binding_root is not None else None
    inventory = build_external_dependency_inventory(asset_root)
    manifest = build_offline_asset_manifest(
        asset_root,
        binding_documents=binding_documents,
        binding_root=binding_root,
    )
    call_graph = {
        "schema_version": "paper1-stage3-production-call-graph-v1",
        "production_entrypoints": [
            "stage3_pipeline.core.GenerationProducer",
            "stage3_pipeline.offline_assets.OfflineJsonLoader",
            "stage3_pipeline.binding.validate_p1_harmful_candidate",
            "stage3_pipeline.binding.validate_binding_set",
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
    bundle = None
    if binding_documents is not None:
        if manifest["offline_asset_status"] != "OFFLINE-ASSET-READY":
            raise RuntimeError("complete real bindings did not produce OFFLINE-ASSET-READY")
        bundle = build_bundle(
            manifest,
            args.bundle_output.resolve(),
            asset_root=asset_root,
            expected_manifest_sha256=manifest["manifest_sha256"],
            binding_documents=binding_documents,
            binding_root=binding_root,
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
        "formal_inputs": manifest["formal_inputs"],
        "run_ready": manifest["run_ready"],
        "binding_validation": manifest["binding_validation"],
        "bundle_file": bundle["bundle_file"] if bundle is not None else None,
        "bundle_sha256": bundle["bundle_sha256"] if bundle is not None else None,
        "bundle_bytes": bundle["bundle_bytes"] if bundle is not None else None,
        "artifacts": artifacts,
        "source_json_modified": False,
        "formal_experiment_run": False,
        "reason_bundle_not_generated": None if bundle is not None else (
            "DATA_IDENTITY_BLOCKED: P1 harmful is candidate-only and the other formal bindings are A0"
        ),
    }
    write_once(output / "offline_build_receipt.json", receipt)
    print(json.dumps({
        "marker": (
            "STAGE3_OFFLINE_BUNDLE_BUILT"
            if bundle is not None else "STAGE3_OFFLINE_INVENTORY_BUILT"
        ),
        "offline_asset_status": manifest["offline_asset_status"],
        "formal_inputs": len(manifest["formal_inputs"]),
        "bundle_generated": bundle is not None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
