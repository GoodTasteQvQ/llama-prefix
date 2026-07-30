#!/usr/bin/env python3
"""Verify Stage 3 binding validators with blocked-real and synthetic-full fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import struct
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.binding import (  # noqa: E402
    BindingError,
    P1_PACKAGE_RELATIVE,
    PROMPT_SPLIT_DOMAINS,
    PROMPT_SPLIT_ROLES,
    PROMPT_SPLIT_SIZES,
    validate_base_anchor_manifest,
    validate_binding_set,
    validate_model_attestation,
    validate_p1_harmful_candidate,
    validate_prompt_frame_manifest,
    validate_vector_manifest,
)
from stage3_pipeline.core import canonical_sha256, file_sha256  # noqa: E402
from stage3_pipeline.local_temp import require_project_local_temp  # noqa: E402
from stage3_pipeline.offline_assets import (  # noqa: E402
    AssetError,
    OfflineJsonLoader,
    build_bundle,
    build_offline_asset_manifest,
)


HASH = "a" * 64
CREATED = "2000-01-01T00:00:00Z"


def seal(document: dict[str, Any]) -> dict[str, Any]:
    document.pop("self_sha256", None)
    document["self_sha256"] = canonical_sha256(document)
    return document


def synthetic_attestation(role: str, root: Path) -> dict[str, Any]:
    behavior = role == "behavior"
    template_text = "{% for message in messages %}{{ message['content'] }}{% endfor %}"
    revision_hash = ("1" if behavior else "2") + ("0" * 63)
    file_plan = [
        ("config.json", "config"),
        ("model-00001-of-00001.safetensors", "weights"),
        ("tokenizer_config.json", "tokenizer_config"),
        ("special_tokens_map.json", "special_tokens_map"),
        ("tokenizer.json", "tokenizer_asset"),
    ]
    files = []
    for name, artifact_role in file_plan:
        relative = f"models/{role}/{name}"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic-{role}-{artifact_role}\n".encode("ascii"))
        files.append({
            "relative_path": relative,
            "artifact_role": artifact_role,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        })
    tokenizer_files = sorted(
        [item for item in files if item["artifact_role"] in {
            "tokenizer_config", "special_tokens_map", "tokenizer_asset"
        }],
        key=lambda item: item["relative_path"],
    )
    repository_id = "Qwen/Qwen2.5-7B-Instruct" if behavior else "Qwen/Qwen3-8B"
    revision = f"sha256:{revision_hash}"
    snapshot_relative = f"manifests/{role}_snapshot.json"
    snapshot_path = root / snapshot_relative
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps({
            "schema_version": "synthetic-model-snapshot-manifest-v1",
            "source_channel": "local_snapshot",
            "repository_id": repository_id,
            "revision": revision,
            "files": files,
        }, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    return seal({
        "schema_version": (
            "paper1-stage3-checkpoint-identity-attestation-v1"
            if behavior else "paper1-stage3-judge-identity-attestation-v1"
        ),
        "protocol_version": "v3.5-rc2",
        "artifact_kind": (
            "checkpoint_identity_attestation" if behavior else "judge_identity_attestation"
        ),
        "synthetic_fixture": True,
        "formal_experiment_run": False,
        "source_channel": "local_snapshot",
        "repository_id": repository_id,
        "revision": revision,
        "revision_evidence": {
            "evidence_type": "directory_manifest_sha256",
            "manifest_sha256": revision_hash,
        },
        "files": files,
        "file_count": len(files),
        "file_inventory_complete": True,
        "snapshot_manifest": {
            "relative_path": snapshot_relative,
            "snapshot_root": f"models/{role}",
            "schema_version": "synthetic-model-snapshot-manifest-v1",
            "sha256": file_sha256(snapshot_path),
            "file_count": len(files),
        },
        "tokenizer": {
            "revision": f"sha256:{revision_hash}",
            "revision_evidence": {
                "evidence_type": "directory_manifest_sha256",
                "manifest_sha256": revision_hash,
            },
            "files_sha256": canonical_sha256(tokenizer_files),
            "tokenizer_config_sha256": next(
                item["sha256"] for item in files if item["artifact_role"] == "tokenizer_config"
            ),
            "special_tokens_map_sha256": next(
                item["sha256"] for item in files if item["artifact_role"] == "special_tokens_map"
            ),
        },
        "chat_template": {
            "text": template_text,
            "sha256": hashlib.sha256(template_text.encode("utf-8")).hexdigest(),
        },
        "config": {
            "relative_path": next(
                item["relative_path"] for item in files if item["artifact_role"] == "config"
            ),
            "sha256": next(
                item["sha256"] for item in files if item["artifact_role"] == "config"
            ),
            "model_type": "qwen2",
            "architectures": ["SyntheticQwenForCausalLM"],
            "hidden_size": 3584 if behavior else 4096,
        },
        "runtime_identity_sha256": "8" * 64,
        "created_at_utc": CREATED,
    })


def write_synthetic_vectors(root: Path, checkpoint_self_sha256: str) -> dict[str, Any]:
    vector_path = root / "synthetic_vectors.f32"
    row_bytes = 3584 * 4
    raw = bytearray(row_bytes * 30)
    one = struct.pack("<f", 1.0)
    for row in range(30):
        offset = row * row_bytes + row * 4
        raw[offset:offset + 4] = one
    vector_path.write_bytes(bytes(raw))
    row_hashes = [
        hashlib.sha256(raw[index * row_bytes:(index + 1) * row_bytes]).hexdigest()
        for index in range(30)
    ]
    pool_hash = file_sha256(vector_path)
    return seal({
        "schema_version": "paper1-stage3-vector-manifest-v1",
        "protocol_version": "v3.5-rc2",
        "artifact_kind": "stage3_vector_manifest",
        "synthetic_fixture": True,
        "formal_experiment_run": False,
        "checkpoint_attestation_self_sha256": checkpoint_self_sha256,
        "seed": 42,
        "generator": {
            "runtime": "torch-2.7.1",
            "api": "torch.Generator.manual_seed+torch.randn",
            "device": "cpu",
        },
        "hidden_dimension": 3584,
        "row_count": 30,
        "tensor_file": {
            "relative_path": "synthetic_vectors.f32",
            "bytes": len(raw),
            "sha256": pool_hash,
            "dtype": "float32",
            "shape": [30, 3584],
            "byte_order": "little",
            "layout": "row_major_contiguous",
        },
        "pool_sha256": pool_hash,
        "row_ids": [f"vector_{index:02d}" for index in range(30)],
        "row_sha256": row_hashes,
        "normalization": {
            "method": "row_l2",
            "zero_row_policy": "fail",
            "nonfinite_policy": "fail",
            "tolerance": 1e-5,
        },
        "partitions": {"screen": list(range(10)), "confirm": list(range(10, 30))},
        "created_at_utc": CREATED,
    })


def synthetic_anchors(checkpoint_self_sha256: str, root: Path) -> dict[str, Any]:
    source_path = root / "fixtures/base_anchor_source.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        json.dumps({
            "schema_version": "synthetic-base-anchor-source-v1",
            "records": [{"anchor": anchor} for anchor in ("A", "T", "H")],
        }, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    return seal({
        "schema_version": "paper1-stage3-base-anchor-binding-manifest-v1",
        "protocol_version": "v3.5-rc2",
        "artifact_kind": "base_anchor_binding_manifest",
        "synthetic_fixture": True,
        "formal_experiment_run": False,
        "checkpoint_attestation_self_sha256": checkpoint_self_sha256,
        "source_paths": {"synthetic": "fixtures/base_anchor_source.json"},
        "source_schema_versions": {"synthetic": "synthetic-base-anchor-source-v1"},
        "source_sha256": {"synthetic": file_sha256(source_path)},
        "counts": {"synthetic": 3},
        "predates_behavior_screening": True,
        "units": "rho=alpha/median_content_norm",
        "strict_order_check": "0 < rho_A < rho_T < rho_H",
        "anchor_order": ["A", "T", "H"],
        "rho_by_anchor": {
            "A": {"decimal": "0.1", "value": 0.1, "binary64_hex": float(0.1).hex()},
            "T": {"decimal": "0.2", "value": 0.2, "binary64_hex": float(0.2).hex()},
            "H": {"decimal": "0.3", "value": 0.3, "binary64_hex": float(0.3).hex()},
        },
        "producer_code_sha256": "b" * 64,
        "producer_config_sha256": "c" * 64,
        "created_at_utc": CREATED,
    })


def write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )


def synthetic_prompt_frames(root: Path) -> dict[str, Any]:
    category_relative = "fixtures/category_registry.json"
    category_path = root / category_relative
    write_json(category_path, {
        "schema_version": "synthetic-category-registry-v1",
        "categories": ["synthetic-benign", "synthetic-harmful"],
    })
    license_relative = "fixtures/SYNTHETIC_LICENSE.txt"
    license_path = root / license_relative
    license_path.write_text(
        "Synthetic fixture material; not a formal data license.\n",
        encoding="utf-8",
        newline="\n",
    )
    splits = []
    global_ids: list[str] = []
    for split_id, count in PROMPT_SPLIT_SIZES.items():
        source_rows = []
        source_relative = f"data/fixtures/{split_id}.json"
        for position in range(1, count + 1):
            source_row = {
                "source_id": f"{split_id}-{position:03d}",
                "question": f"Synthetic prompt payload {split_id} {position:03d}",
                "category_id": f"synthetic-{PROMPT_SPLIT_DOMAINS[split_id]}",
            }
            source_rows.append(source_row)
        source_path = root / source_relative
        write_json(source_path, {
            "schema_version": "synthetic-prompt-source-v1",
            "records": source_rows,
        })
        upstream_source_path = f"upstream/{split_id}.json"
        snapshot_files = [{
            "upstream_source_path": upstream_source_path,
            "bytes": source_path.stat().st_size,
            "raw_sha256": file_sha256(source_path),
        }]
        revision_hash = canonical_sha256(snapshot_files)
        revision = f"sha256:{revision_hash}"
        snapshot_relative = f"fixtures/{split_id}.source_snapshot.json"
        snapshot_path = root / snapshot_relative
        write_json(snapshot_path, {
            "schema_version": "paper1-stage3-synthetic-prompt-source-snapshot-v1",
            "source_repository_id": "synthetic/binding-ready-fixture",
            "source_revision": revision,
            "files": snapshot_files,
            "tree_sha256": revision_hash,
        })
        identities = []
        for position, source_row in enumerate(source_rows, 1):
            question_sha256 = hashlib.sha256(
                source_row["question"].encode("utf-8")
            ).hexdigest()
            row_sha = canonical_sha256(source_row)
            record_id = canonical_sha256({
                "source_repository_id": "synthetic/binding-ready-fixture",
                "source_revision": revision,
                "upstream_source_path": upstream_source_path,
                "source_id": source_row["source_id"],
                "source_row_sha256": row_sha,
                "question_sha256": question_sha256,
            })
            identities.append({
                "position": position,
                "prompt_id": f"{split_id}:{record_id}",
                "record_identity_sha256": record_id,
                "source_id": source_row["source_id"],
                "source_row_sha256": row_sha,
                "question_sha256": question_sha256,
                "category_id": source_row["category_id"],
            })
            global_ids.append(record_id)
        dedup_relative = f"fixtures/{split_id}.dedup.json"
        leakage_relative = f"fixtures/{split_id}.leakage.json"
        split_hashes = [item["record_identity_sha256"] for item in identities]
        frame_sha256 = canonical_sha256(split_hashes)
        write_json(root / dedup_relative, {
            "schema_version": "paper1-stage3-synthetic-prompt-deduplication-evidence-v1",
            "status": "COMPLETE",
            "split_id": split_id,
            "identity_count": count,
            "frame_sha256": frame_sha256,
        })
        write_json(root / leakage_relative, {
            "schema_version": "paper1-stage3-synthetic-prompt-leakage-evidence-v1",
            "status": "COMPLETE",
            "split_id": split_id,
            "identity_count": count,
            "frame_sha256": frame_sha256,
        })
        splits.append({
            "split_id": split_id,
            "domain": PROMPT_SPLIT_DOMAINS[split_id],
            "role": PROMPT_SPLIT_ROLES[split_id],
            "expected_count": count,
            "source_repository_id": "synthetic/binding-ready-fixture",
            "source_channel": "local_snapshot",
            "source_revision": revision,
            "source_revision_evidence": {
                "evidence_type": "directory_manifest_sha256",
                "manifest_sha256": revision_hash,
            },
            "source_path": source_relative,
            "upstream_source_path": upstream_source_path,
            "source_schema_version": "synthetic-prompt-source-v1",
            "source_file_sha256": file_sha256(source_path),
            "source_snapshot_manifest_path": snapshot_relative,
            "source_snapshot_manifest_sha256": file_sha256(snapshot_path),
            "source_snapshot_manifest_schema_version": "paper1-stage3-synthetic-prompt-source-snapshot-v1",
            "license": "SYNTHETIC-TEST-ONLY",
            "license_path": license_relative,
            "license_sha256": file_sha256(license_path),
            "category_registry_path": category_relative,
            "category_registry_sha256": file_sha256(category_path),
            "category_registry_schema_version": "synthetic-category-registry-v1",
            "ordered_identities": identities,
            "frame_sha256": frame_sha256,
            "deduplication_evidence_path": dedup_relative,
            "deduplication_evidence_schema_version": "paper1-stage3-synthetic-prompt-deduplication-evidence-v1",
            "deduplication_evidence_sha256": file_sha256(root / dedup_relative),
            "leakage_evidence_path": leakage_relative,
            "leakage_evidence_schema_version": "paper1-stage3-synthetic-prompt-leakage-evidence-v1",
            "leakage_evidence_sha256": file_sha256(root / leakage_relative),
        })
    global_evidence_relative = "fixtures/global_dedup_leakage.json"
    write_json(root / global_evidence_relative, {
        "schema_version": "paper1-stage3-synthetic-global-dedup-leakage-evidence-v1",
        "status": "COMPLETE",
        "identity_count": 310,
        "exact_overlap_count": 0,
        "global_identity_sha256": canonical_sha256(global_ids),
    })
    return seal({
        "schema_version": "paper1-stage3-prompt-frame-binding-manifest-v2",
        "protocol_version": "v3.5-rc2",
        "artifact_kind": "prompt_frame_binding_manifest",
        "synthetic_fixture": True,
        "formal_experiment_run": False,
        "split_order": list(PROMPT_SPLIT_SIZES),
        "splits": splits,
        "global_identity_sha256": canonical_sha256(global_ids),
        "global_deduplication_evidence": {
            "method": "frozen-priority-global-dedup-and-leakage-review",
            "exact_overlap_count": 0,
            "semantic_review_status": "COMPLETE",
            "evidence_path": global_evidence_relative,
            "evidence_schema_version": "paper1-stage3-synthetic-global-dedup-leakage-evidence-v1",
            "evidence_sha256": file_sha256(root / global_evidence_relative),
        },
        "created_at_utc": CREATED,
    })


def build_synthetic_binding_documents(root: Path) -> dict[str, dict[str, Any]]:
    checkpoint = synthetic_attestation("behavior", root)
    return {
        "checkpoint": checkpoint,
        "judge": synthetic_attestation("judge", root),
        "vectors": write_synthetic_vectors(root, checkpoint["self_sha256"]),
        "base_anchor": synthetic_anchors(checkpoint["self_sha256"], root),
        "prompt_frames": synthetic_prompt_frames(root),
    }


def expect_failure(checks: list[str], marker: str, action: Callable[[], Any]) -> None:
    try:
        action()
    except (BindingError, AssetError):
        checks.append(marker)
    else:
        raise AssertionError(f"negative binding case did not fail closed: {marker}")


def mutated(document: Mapping[str, Any], change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    change(result)
    return seal(result)


def reseal_prompt_payload_tamper(
    root: Path,
    documents: Mapping[str, Mapping[str, Any]],
    *,
    unresolved_remote_channel: str | None = None,
) -> dict[str, Any]:
    prompt = copy.deepcopy(documents["prompt_frames"])
    split = prompt["splits"][1]
    if unresolved_remote_channel in {"git", "huggingface"}:
        revision = "4" * 40
        split["source_channel"] = unresolved_remote_channel
        split["source_revision"] = revision
        split["source_revision_evidence"] = {
            "evidence_type": "git_commit",
            "commit_sha": revision,
        }
    elif unresolved_remote_channel == "object_store":
        split["source_channel"] = unresolved_remote_channel
        split["source_revision"] = "version:synthetic-version-001"
        split["source_revision_evidence"] = {
            "evidence_type": "versioned_object",
            "version_id": "synthetic-version-001",
            "etag_sha256": "5" * 64,
        }
    elif unresolved_remote_channel is not None:
        raise AssertionError(f"unsupported remote tamper channel: {unresolved_remote_channel}")
    source_path = root / split["source_path"]
    source_document = json.loads(source_path.read_text(encoding="utf-8"))
    source_document["records"][0]["question"] += " tampered"
    write_json(source_path, source_document)
    split["source_file_sha256"] = file_sha256(source_path)

    if unresolved_remote_channel is not None:
        snapshot_path = root / split["source_snapshot_manifest_path"]
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["source_revision"] = split["source_revision"]
        snapshot["files"][0]["bytes"] = source_path.stat().st_size
        snapshot["files"][0]["raw_sha256"] = split["source_file_sha256"]
        snapshot["tree_sha256"] = canonical_sha256(snapshot["files"])
        write_json(snapshot_path, snapshot)
        split["source_snapshot_manifest_sha256"] = file_sha256(snapshot_path)

    for source_row, identity in zip(
        source_document["records"], split["ordered_identities"], strict=True
    ):
        question_sha256 = hashlib.sha256(source_row["question"].encode("utf-8")).hexdigest()
        source_row_sha256 = canonical_sha256(source_row)
        record_identity = canonical_sha256({
            "source_repository_id": split["source_repository_id"],
            "source_revision": split["source_revision"],
            "upstream_source_path": split["upstream_source_path"],
            "source_id": source_row["source_id"],
            "source_row_sha256": source_row_sha256,
            "question_sha256": question_sha256,
        })
        identity.update({
            "prompt_id": f"{split['split_id']}:{record_identity}",
            "record_identity_sha256": record_identity,
            "source_row_sha256": source_row_sha256,
            "question_sha256": question_sha256,
        })
    split_ids = [item["record_identity_sha256"] for item in split["ordered_identities"]]
    split["frame_sha256"] = canonical_sha256(split_ids)
    for evidence_kind in ("deduplication", "leakage"):
        path = root / split[f"{evidence_kind}_evidence_path"]
        evidence = json.loads(path.read_text(encoding="utf-8"))
        evidence["frame_sha256"] = split["frame_sha256"]
        write_json(path, evidence)
        split[f"{evidence_kind}_evidence_sha256"] = file_sha256(path)
    global_ids = [
        item["record_identity_sha256"]
        for split_value in prompt["splits"]
        for item in split_value["ordered_identities"]
    ]
    prompt["global_identity_sha256"] = canonical_sha256(global_ids)
    global_evidence = prompt["global_deduplication_evidence"]
    global_path = root / global_evidence["evidence_path"]
    global_document = json.loads(global_path.read_text(encoding="utf-8"))
    global_document["global_identity_sha256"] = prompt["global_identity_sha256"]
    write_json(global_path, global_document)
    global_evidence["evidence_sha256"] = file_sha256(global_path)
    return seal(prompt)


def run_verification() -> dict[str, Any]:
    local_temp = require_project_local_temp(ROOT)
    checks: list[str] = []
    candidate = validate_p1_harmful_candidate(ROOT)
    if candidate["disposition"] != "CANDIDATE_BINDING_INPUT" or candidate["formal_input"] is not False:
        raise AssertionError("approved P1 package crossed the candidate/formal boundary")
    checks.append("p1_candidate_exact_package_pass")

    current = build_offline_asset_manifest(ROOT)
    if (
        current["offline_asset_status"] != "DATA_IDENTITY_BLOCKED"
        or current["formal_inputs"] != []
        or current["run_ready"] is not False
        or current["formal_experiment_run"] is not False
        or current["binding_validation"]["complete"] is not False
    ):
        raise AssertionError("current repository state is not fail-closed")
    checks.append("current_repository_blocked_pass")

    with tempfile.TemporaryDirectory(prefix="binding-ready-", dir=local_temp) as directory:
        fixture_root = Path(directory)
        shutil.copytree(ROOT / "data", fixture_root / "data")
        documents = build_synthetic_binding_documents(fixture_root)
        validation = validate_binding_set(documents, fixture_root)
        if (
            validation["synthetic_fixture"] is not True
            or validation["formal_input_claim"] is not False
            or validation["prompt_identity_count"] != 310
            or validation["vector_shape"] != [30, 3584]
            or validation["formal_experiment_run"] is not False
        ):
            raise AssertionError("synthetic full binding validation boundary differs")
        validated = build_offline_asset_manifest(
            fixture_root,
            binding_documents=documents,
            binding_root=fixture_root,
        )
        if (
            validated["offline_asset_status"] != "SYNTHETIC-BINDING-VALIDATED"
            or validated["formal_inputs"] != []
            or validated["run_ready"] is not False
            or validated["formal_experiment_run"] is not False
            or validated["binding_validation"] != validation
            or any(item.get("formal_input") is not False for item in validated["binding_inputs"])
        ):
            raise AssertionError("synthetic binding validation made a READY/formal claim")
        checks.append("synthetic_full_shaped_binding_validated_pass")

        synthetic_bundle_manifest = build_offline_asset_manifest(
            fixture_root,
            binding_documents=documents,
            binding_root=fixture_root,
            authorize_synthetic_bundle=True,
        )
        if (
            synthetic_bundle_manifest["offline_asset_status"]
            != "SYNTHETIC-OFFLINE-LOADER-READY"
            or len(synthetic_bundle_manifest["formal_inputs"]) != 5
            or any(
                entry.get("formal_input") is not False
                or entry.get("disposition") != "SYNTHETIC_FIXTURE_INPUT"
                for entry in synthetic_bundle_manifest["formal_inputs"]
            )
        ):
            raise AssertionError("full-shaped synthetic bundle authorization differs")
        synthetic_loader = OfflineJsonLoader(
            synthetic_bundle_manifest,
            fixture_root,
            expected_manifest_sha256=synthetic_bundle_manifest["manifest_sha256"],
            binding_documents=documents,
            binding_root=fixture_root,
            allow_synthetic_fixture=True,
        )
        for entry in synthetic_bundle_manifest["formal_inputs"]:
            synthetic_loader.load_formal(entry["relative_path"])
        bundle_output = fixture_root / "full-shaped-offline-bundle"
        bundle = build_bundle(
            synthetic_bundle_manifest,
            bundle_output,
            asset_root=fixture_root,
            expected_manifest_sha256=synthetic_bundle_manifest["manifest_sha256"],
            allow_synthetic_fixture=True,
            binding_documents=documents,
            binding_root=fixture_root,
        )
        archive_path = bundle_output.with_suffix(".tar.gz")
        with tarfile.open(archive_path, "r:gz") as archive:
            for entry in synthetic_bundle_manifest["formal_inputs"]:
                member = archive.getmember(f"offline_bundle/{entry['relative_path']}")
                handle = archive.extractfile(member)
                if handle is None or hashlib.sha256(handle.read()).hexdigest() != entry["raw_sha256"]:
                    raise AssertionError("full-shaped bundle member identity differs")
        if len(bundle["formal_inputs"]) != 5 or file_sha256(archive_path) != bundle["bundle_sha256"]:
            raise AssertionError("full-shaped bundle receipt differs")
        checks.append("full_shaped_bundle_positive_pass")

        empty_ready = copy.deepcopy(synthetic_bundle_manifest)
        empty_ready["offline_asset_status"] = "OFFLINE-ASSET-READY"
        empty_ready["formal_inputs"] = []
        empty_ready["manifest_sha256"] = canonical_sha256({
            key: value for key, value in empty_ready.items() if key != "manifest_sha256"
        })
        expect_failure(
            checks,
            "real_ready_empty_formal_inputs_rejected",
            lambda: OfflineJsonLoader(
                empty_ready,
                fixture_root,
                expected_manifest_sha256=empty_ready["manifest_sha256"],
                binding_documents=documents,
                binding_root=fixture_root,
            ),
        )

        relocated_prompts = copy.deepcopy(documents["prompt_frames"])
        relocated_split = relocated_prompts["splits"][1]
        original_relative = relocated_split["source_path"]
        relocated_relative = "relocated/p1_benign.json"
        relocated_path = fixture_root / relocated_relative
        relocated_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture_root / original_relative, relocated_path)
        original_global_identity = relocated_prompts["global_identity_sha256"]
        relocated_split["source_path"] = relocated_relative
        seal(relocated_prompts)
        relocated_result = validate_prompt_frame_manifest(relocated_prompts, fixture_root)
        if relocated_result["global_identity_sha256"] != original_global_identity:
            raise AssertionError("local prompt source relocation changed record identity")
        checks.append("prompt_local_path_identity_invariant_pass")

        tamper_root = fixture_root / "payload-tamper"
        tamper_documents = build_synthetic_binding_documents(tamper_root)
        tampered_prompt = reseal_prompt_payload_tamper(tamper_root, tamper_documents)
        expect_failure(
            checks,
            "prompt_payload_resealed_metadata_rejected",
            lambda: validate_prompt_frame_manifest(tampered_prompt, tamper_root),
        )
        for channel in ("git", "huggingface", "object_store"):
            remote_tamper_root = fixture_root / f"payload-tamper-{channel}"
            remote_tamper_documents = build_synthetic_binding_documents(remote_tamper_root)
            remote_tampered_prompt = reseal_prompt_payload_tamper(
                remote_tamper_root,
                remote_tamper_documents,
                unresolved_remote_channel=channel,
            )
            expect_failure(
                checks,
                f"prompt_unresolved_{channel}_reseal_rejected",
                lambda prompt=remote_tampered_prompt, root=remote_tamper_root:
                    validate_prompt_frame_manifest(prompt, root),
            )

        expect_failure(
            checks,
            "partial_binding_promotion_rejected",
            lambda: build_offline_asset_manifest(
                ROOT,
                binding_documents={"checkpoint": documents["checkpoint"]},
                binding_root=fixture_root,
            ),
        )
        forged_ready = copy.deepcopy(current)
        forged_ready["offline_asset_status"] = "OFFLINE-ASSET-READY"
        forged_ready["manifest_sha256"] = canonical_sha256({
            key: value for key, value in forged_ready.items() if key != "manifest_sha256"
        })
        expect_failure(
            checks,
            "forged_ready_status_rejected",
            lambda: OfflineJsonLoader(
                forged_ready,
                ROOT,
                expected_manifest_sha256=forged_ready["manifest_sha256"],
            ),
        )

        checkpoint = documents["checkpoint"]
        judge = documents["judge"]
        expect_failure(
            checks,
            "checkpoint_schema_extra_key_rejected",
            lambda: validate_model_attestation(
                mutated(checkpoint, lambda value: value.update({"extra": True})),
                fixture_root,
                role="behavior",
            ),
        )
        missing_checkpoint = copy.deepcopy(checkpoint)
        missing_checkpoint.pop("files")
        seal(missing_checkpoint)
        expect_failure(
            checks,
            "checkpoint_missing_provenance_rejected",
            lambda: validate_model_attestation(missing_checkpoint, fixture_root, role="behavior"),
        )
        mutable_checkpoint = copy.deepcopy(checkpoint)
        mutable_checkpoint["source_channel"] = "huggingface"
        mutable_checkpoint["revision"] = "main"
        mutable_checkpoint["revision_evidence"] = {
            "evidence_type": "git_commit", "commit_sha": "1" * 40
        }
        seal(mutable_checkpoint)
        expect_failure(
            checks,
            "mutable_checkpoint_revision_rejected",
            lambda: validate_model_attestation(mutable_checkpoint, fixture_root, role="behavior"),
        )
        mutable_judge = copy.deepcopy(judge)
        mutable_judge["source_channel"] = "git"
        mutable_judge["revision"] = "latest"
        mutable_judge["revision_evidence"] = {
            "evidence_type": "git_commit", "commit_sha": "2" * 40
        }
        seal(mutable_judge)
        expect_failure(
            checks,
            "mutable_judge_revision_rejected",
            lambda: validate_model_attestation(mutable_judge, fixture_root, role="judge"),
        )
        incomplete_files = copy.deepcopy(checkpoint)
        incomplete_files["files"] = [
            item for item in incomplete_files["files"]
            if item["artifact_role"] != "tokenizer_asset"
        ]
        incomplete_files["file_count"] = len(incomplete_files["files"])
        incomplete_files["tokenizer"]["files_sha256"] = canonical_sha256(sorted(
            [item for item in incomplete_files["files"] if item["artifact_role"] in {
                "tokenizer_config", "special_tokens_map", "tokenizer_asset"
            }],
            key=lambda item: item["relative_path"],
        ))
        seal(incomplete_files)
        expect_failure(
            checks,
            "incomplete_model_file_inventory_rejected",
            lambda: validate_model_attestation(incomplete_files, fixture_root, role="behavior"),
        )
        mutable_tokenizer = copy.deepcopy(checkpoint)
        mutable_tokenizer["tokenizer"]["revision"] = "latest"
        seal(mutable_tokenizer)
        expect_failure(
            checks,
            "mutable_tokenizer_revision_rejected",
            lambda: validate_model_attestation(mutable_tokenizer, fixture_root, role="behavior"),
        )
        installed_hash = copy.deepcopy(checkpoint)
        weights = next(
            item for item in installed_hash["files"] if item["artifact_role"] == "weights"
        )
        weights["sha256"] = HASH
        seal(installed_hash)
        expect_failure(
            checks,
            "installed_model_file_hash_rejected",
            lambda: validate_model_attestation(installed_hash, fixture_root, role="behavior"),
        )
        extra_shard = fixture_root / "models/behavior/model-00002-of-00002.safetensors"
        extra_shard.write_bytes(b"synthetic-unlisted-weight-shard\n")
        try:
            expect_failure(
                checks,
                "omitted_snapshot_shard_rejected",
                lambda: validate_model_attestation(checkpoint, fixture_root, role="behavior"),
            )
        finally:
            extra_shard.unlink()

        vectors = documents["vectors"]
        for marker, change in (
            ("vector_shape_rejected", lambda value: value["tensor_file"].update({"shape": [29, 3584]})),
            ("vector_dtype_rejected", lambda value: value["tensor_file"].update({"dtype": "float64"})),
            ("vector_partition_rejected", lambda value: value.update({"partitions": {"screen": list(range(9)), "confirm": list(range(9, 30))}})),
            ("vector_checkpoint_parent_rejected", lambda value: value.update({"checkpoint_attestation_self_sha256": HASH})),
        ):
            expect_failure(
                checks,
                marker,
                lambda change=change: validate_vector_manifest(
                    mutated(vectors, change),
                    fixture_root,
                    checkpoint_self_sha256=checkpoint["self_sha256"],
                ),
            )
        vector_path = fixture_root / "synthetic_vectors.f32"
        original_vectors = vector_path.read_bytes()
        tampered = bytearray(original_vectors)
        tampered[0:4] = struct.pack("<f", 2.0)
        vector_path.write_bytes(tampered)
        norm_manifest = copy.deepcopy(vectors)
        norm_manifest["tensor_file"]["sha256"] = file_sha256(vector_path)
        norm_manifest["pool_sha256"] = norm_manifest["tensor_file"]["sha256"]
        norm_manifest["row_sha256"][0] = hashlib.sha256(tampered[:3584 * 4]).hexdigest()
        seal(norm_manifest)
        expect_failure(
            checks,
            "vector_norm_rejected",
            lambda: validate_vector_manifest(
                norm_manifest, fixture_root, checkpoint_self_sha256=checkpoint["self_sha256"]
            ),
        )
        vector_path.write_bytes(original_vectors)
        hash_manifest = mutated(vectors, lambda value: value.update({"pool_sha256": HASH}))
        expect_failure(
            checks,
            "vector_pool_hash_mismatch_rejected",
            lambda: validate_vector_manifest(
                hash_manifest, fixture_root, checkpoint_self_sha256=checkpoint["self_sha256"]
            ),
        )

        anchors = documents["base_anchor"]
        bad_rho = copy.deepcopy(anchors)
        bad_rho["rho_by_anchor"]["T"] = copy.deepcopy(bad_rho["rho_by_anchor"]["A"])
        seal(bad_rho)
        expect_failure(
            checks,
            "rho_order_rejected",
            lambda: validate_base_anchor_manifest(
                bad_rho, fixture_root, checkpoint_self_sha256=checkpoint["self_sha256"]
            ),
        )
        missing_anchor_source = copy.deepcopy(anchors)
        missing_anchor_source.pop("source_paths")
        seal(missing_anchor_source)
        expect_failure(
            checks,
            "base_anchor_missing_provenance_rejected",
            lambda: validate_base_anchor_manifest(
                missing_anchor_source, fixture_root,
                checkpoint_self_sha256=checkpoint["self_sha256"]
            ),
        )
        bad_anchor_source_hash = copy.deepcopy(anchors)
        bad_anchor_source_hash["source_sha256"]["synthetic"] = HASH
        seal(bad_anchor_source_hash)
        expect_failure(
            checks,
            "base_anchor_source_hash_rejected",
            lambda: validate_base_anchor_manifest(
                bad_anchor_source_hash, fixture_root,
                checkpoint_self_sha256=checkpoint["self_sha256"],
            ),
        )

        prompts = documents["prompt_frames"]
        extra_prompt = mutated(prompts, lambda value: value.update({"extra": True}))
        expect_failure(
            checks,
            "prompt_schema_extra_key_rejected",
            lambda: validate_prompt_frame_manifest(extra_prompt, fixture_root),
        )
        missing_prompt = copy.deepcopy(prompts)
        missing_prompt.pop("global_deduplication_evidence")
        seal(missing_prompt)
        expect_failure(
            checks,
            "prompt_missing_provenance_rejected",
            lambda: validate_prompt_frame_manifest(missing_prompt, fixture_root),
        )
        duplicate_prompt = copy.deepcopy(prompts)
        duplicate_prompt["splits"][0]["ordered_identities"][1] = copy.deepcopy(
            duplicate_prompt["splits"][0]["ordered_identities"][0]
        )
        seal(duplicate_prompt)
        expect_failure(
            checks,
            "prompt_duplicate_id_rejected",
            lambda: validate_prompt_frame_manifest(duplicate_prompt, fixture_root),
        )
        order_prompt = copy.deepcopy(prompts)
        rows = order_prompt["splits"][0]["ordered_identities"]
        rows[0], rows[1] = rows[1], rows[0]
        seal(order_prompt)
        expect_failure(
            checks,
            "prompt_frame_order_rejected",
            lambda: validate_prompt_frame_manifest(order_prompt, fixture_root),
        )
        count_prompt = copy.deepcopy(prompts)
        count_prompt["splits"][2]["ordered_identities"].pop()
        seal(count_prompt)
        expect_failure(
            checks,
            "prompt_split_count_rejected",
            lambda: validate_prompt_frame_manifest(count_prompt, fixture_root),
        )
        duplicate_source_path = copy.deepcopy(prompts)
        duplicate_source_path["splits"][4]["source_path"] = (
            duplicate_source_path["splits"][2]["source_path"]
        )
        seal(duplicate_source_path)
        expect_failure(
            checks,
            "prompt_duplicate_source_path_rejected",
            lambda: validate_prompt_frame_manifest(duplicate_source_path, fixture_root),
        )
        overlap_prompt = copy.deepcopy(prompts)
        source_identity = overlap_prompt["splits"][0]["ordered_identities"][0]
        target_identity = overlap_prompt["splits"][1]["ordered_identities"][0]
        target_identity["record_identity_sha256"] = source_identity["record_identity_sha256"]
        target_identity["prompt_id"] = (
            "p1_benign:" + source_identity["record_identity_sha256"]
        )
        benign_ids = [
            row["record_identity_sha256"]
            for row in overlap_prompt["splits"][1]["ordered_identities"]
        ]
        overlap_prompt["splits"][1]["frame_sha256"] = canonical_sha256(benign_ids)
        all_ids = [
            row["record_identity_sha256"]
            for split in overlap_prompt["splits"]
            for row in split["ordered_identities"]
        ]
        overlap_prompt["global_identity_sha256"] = canonical_sha256(all_ids)
        seal(overlap_prompt)
        expect_failure(
            checks,
            "prompt_cross_split_overlap_rejected",
            lambda: validate_prompt_frame_manifest(overlap_prompt, fixture_root),
        )
        frame_hash_prompt = mutated(
            prompts,
            lambda value: value["splits"][0].update({"frame_sha256": HASH}),
        )
        expect_failure(
            checks,
            "prompt_frame_hash_mismatch_rejected",
            lambda: validate_prompt_frame_manifest(frame_hash_prompt, fixture_root),
        )
        mutable_prompt_source = copy.deepcopy(prompts)
        split = mutable_prompt_source["splits"][0]
        split["source_channel"] = "git"
        split["source_revision"] = "refs/heads/main"
        split["source_revision_evidence"] = {
            "evidence_type": "git_commit", "commit_sha": "1" * 40
        }
        seal(mutable_prompt_source)
        expect_failure(
            checks,
            "mutable_prompt_source_revision_rejected",
            lambda: validate_prompt_frame_manifest(mutable_prompt_source, fixture_root),
        )
        prompt_evidence_hash = copy.deepcopy(prompts)
        prompt_evidence_hash["splits"][0]["deduplication_evidence_sha256"] = HASH
        seal(prompt_evidence_hash)
        expect_failure(
            checks,
            "prompt_evidence_hash_rejected",
            lambda: validate_prompt_frame_manifest(prompt_evidence_hash, fixture_root),
        )
        prompt_evidence_schema = copy.deepcopy(prompts)
        prompt_evidence_schema["splits"][0][
            "deduplication_evidence_schema_version"
        ] = "unregistered-evidence-schema-v9"
        seal(prompt_evidence_schema)
        expect_failure(
            checks,
            "prompt_evidence_schema_rejected",
            lambda: validate_prompt_frame_manifest(prompt_evidence_schema, fixture_root),
        )
        dedup_path = fixture_root / prompts["splits"][0]["deduplication_evidence_path"]
        original_dedup = dedup_path.read_bytes()
        count_document = json.loads(original_dedup.decode("utf-8"))
        count_document["identity_count"] = 1
        write_json(dedup_path, count_document)
        prompt_evidence_count = copy.deepcopy(prompts)
        prompt_evidence_count["splits"][0]["deduplication_evidence_sha256"] = file_sha256(
            dedup_path
        )
        seal(prompt_evidence_count)
        try:
            expect_failure(
                checks,
                "prompt_evidence_count_rejected",
                lambda: validate_prompt_frame_manifest(prompt_evidence_count, fixture_root),
            )
        finally:
            dedup_path.write_bytes(original_dedup)
        global_path = fixture_root / prompts["global_deduplication_evidence"]["evidence_path"]
        original_global = global_path.read_bytes()
        global_document = json.loads(original_global.decode("utf-8"))
        global_document["global_identity_sha256"] = HASH
        write_json(global_path, global_document)
        prompt_global_identity = copy.deepcopy(prompts)
        prompt_global_identity["global_deduplication_evidence"]["evidence_sha256"] = file_sha256(
            global_path
        )
        seal(prompt_global_identity)
        try:
            expect_failure(
                checks,
                "global_evidence_identity_rejected",
                lambda: validate_prompt_frame_manifest(prompt_global_identity, fixture_root),
            )
        finally:
            global_path.write_bytes(original_global)

        forged_real = copy.deepcopy(synthetic_bundle_manifest)
        forged_real["binding_validation"]["synthetic_fixture"] = False
        forged_real["binding_validation"]["formal_input_claim"] = True
        forged_real["offline_asset_status"] = "OFFLINE-ASSET-READY"
        forged_real["manifest_sha256"] = canonical_sha256({
            key: value for key, value in forged_real.items() if key != "manifest_sha256"
        })
        expect_failure(
            checks,
            "real_bundle_missing_binding_documents_rejected",
            lambda: build_bundle(
                forged_real,
                fixture_root / "forged-real-bundle-a",
                asset_root=ROOT,
                expected_manifest_sha256=forged_real["manifest_sha256"],
            ),
        )
        expect_failure(
            checks,
            "real_bundle_revalidates_binding_documents",
            lambda: build_bundle(
                forged_real,
                fixture_root / "forged-real-bundle-b",
                asset_root=ROOT,
                expected_manifest_sha256=forged_real["manifest_sha256"],
                binding_documents=documents,
                binding_root=fixture_root,
            ),
        )

        corrupt_root = fixture_root / "corrupt-candidate-root"
        corrupt_package = corrupt_root / P1_PACKAGE_RELATIVE
        shutil.copytree(ROOT / P1_PACKAGE_RELATIVE, corrupt_package)
        selected_path = corrupt_package / "selected_p1_harmful_100.json"
        selected_path.write_bytes(selected_path.read_bytes() + b"\n")
        expect_failure(
            checks,
            "p1_candidate_raw_hash_mismatch_rejected",
            lambda: validate_p1_harmful_candidate(corrupt_root),
        )

    required = {
        "p1_candidate_exact_package_pass",
        "current_repository_blocked_pass",
        "synthetic_full_shaped_binding_validated_pass",
        "full_shaped_bundle_positive_pass",
        "real_ready_empty_formal_inputs_rejected",
        "prompt_local_path_identity_invariant_pass",
        "prompt_payload_resealed_metadata_rejected",
        "prompt_unresolved_git_reseal_rejected",
        "prompt_unresolved_huggingface_reseal_rejected",
        "prompt_unresolved_object_store_reseal_rejected",
        "partial_binding_promotion_rejected",
        "forged_ready_status_rejected",
        "checkpoint_schema_extra_key_rejected",
        "checkpoint_missing_provenance_rejected",
        "mutable_checkpoint_revision_rejected",
        "mutable_judge_revision_rejected",
        "incomplete_model_file_inventory_rejected",
        "mutable_tokenizer_revision_rejected",
        "installed_model_file_hash_rejected",
        "omitted_snapshot_shard_rejected",
        "vector_shape_rejected",
        "vector_dtype_rejected",
        "vector_partition_rejected",
        "vector_checkpoint_parent_rejected",
        "vector_norm_rejected",
        "vector_pool_hash_mismatch_rejected",
        "rho_order_rejected",
        "base_anchor_missing_provenance_rejected",
        "base_anchor_source_hash_rejected",
        "prompt_schema_extra_key_rejected",
        "prompt_missing_provenance_rejected",
        "prompt_duplicate_id_rejected",
        "prompt_frame_order_rejected",
        "prompt_split_count_rejected",
        "prompt_duplicate_source_path_rejected",
        "prompt_cross_split_overlap_rejected",
        "prompt_frame_hash_mismatch_rejected",
        "mutable_prompt_source_revision_rejected",
        "prompt_evidence_hash_rejected",
        "prompt_evidence_schema_rejected",
        "prompt_evidence_count_rejected",
        "global_evidence_identity_rejected",
        "real_bundle_missing_binding_documents_rejected",
        "real_bundle_revalidates_binding_documents",
        "p1_candidate_raw_hash_mismatch_rejected",
    }
    if set(checks) != required or len(checks) != len(set(checks)):
        raise AssertionError("binding-ready verification coverage differs")
    return {
        "schema_version": "paper1-stage3-binding-ready-closure-verification-v2",
        "marker": "STAGE3_BINDING_READY_IMPLEMENTATION_PASS",
        "checks": sorted(checks),
        "check_count": len(checks),
        "current_offline_asset_status": "DATA_IDENTITY_BLOCKED",
        "synthetic_transition_status": "SYNTHETIC-BINDING-VALIDATED",
        "synthetic_bundle_status": "SYNTHETIC-OFFLINE-LOADER-READY",
        "formal_inputs": [],
        "run_ready": False,
        "formal_experiment_run": False,
        "network_attempt_count": 0,
    }


def main() -> int:
    report = run_verification()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
