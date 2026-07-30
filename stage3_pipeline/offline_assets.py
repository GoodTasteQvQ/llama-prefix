"""Raw-byte preserving offline asset inspection, loading, and bundling."""

from __future__ import annotations

import json
import gzip
import os
import shutil
import stat
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .core import PipelineError, canonical_sha256, file_sha256, utc_now


ASSET_ROOT_ENV = "PAPER1_STAGE3_ASSET_ROOT"
ALLOWED_DISPOSITIONS = {
    "FORMAL_INPUT",
    "CANDIDATE_BINDING_INPUT",
    "DEVELOPMENT_ONLY",
    "EXAMPLE_ONLY",
    "HISTORICAL_STAGE1_INPUT",
    "OUT_OF_SCOPE",
    "SERVER_PREINSTALLED_ASSET",
    "LOCAL_LEGACY_INPUT",
}


class AssetError(PipelineError):
    """An offline asset was missing, mutated, ambiguous, or schema-invalid."""


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or (callable(is_junction) and is_junction())


@dataclass(frozen=True)
class JsonAssetSpec:
    relative_path: str
    top_level_type: str
    row_count: int | None
    ordered_fields: tuple[str, ...]
    stable_id_fields: tuple[str, ...]
    field_types: tuple[tuple[str, str], ...]
    disposition: str
    prompt_frame_membership: str
    source_dataset: str | None
    source_revision: str | None
    config: str | None
    split: str | None
    license: str | None
    provenance_status: str


CANDIDATE_SPECS = (
    JsonAssetSpec(
        "data/jbb_behaviors_harmful.json",
        "array",
        100,
        ("Index", "Goal", "Target", "Behavior", "Category", "Source"),
        ("Index",),
        (
            ("Index", "integer"),
            ("Goal", "string"),
            ("Target", "string"),
            ("Behavior", "string"),
            ("Category", "string"),
            ("Source", "string"),
        ),
        "LOCAL_LEGACY_INPUT",
        "UNBOUND_CANDIDATE_NOT_IN_FORMAL_PROMPT_FRAME",
        "JailbreakBench/JBB-Behaviors",
        None,
        "behaviors",
        "harmful",
        None,
        "PROVENANCE_INCOMPLETE",
    ),
    JsonAssetSpec(
        "data/safe_pairs.json",
        "array",
        500,
        ("harmful", "harmless"),
        ("harmful", "harmless"),
        (("harmful", "string"), ("harmless", "string")),
        "LOCAL_LEGACY_INPUT",
        "UNBOUND_CANDIDATE_NOT_IN_FORMAL_PROMPT_FRAME",
        None,
        None,
        None,
        None,
        None,
        "PROVENANCE_INCOMPLETE",
    ),
    JsonAssetSpec(
        "data/safe_pairs.example.json",
        "array",
        None,
        ("harmful", "harmless"),
        ("harmful", "harmless"),
        (("harmful", "string"), ("harmless", "string")),
        "EXAMPLE_ONLY",
        "EXCLUDED_EXAMPLE_ONLY",
        None,
        None,
        None,
        None,
        None,
        "PROVENANCE_INCOMPLETE",
    ),
    JsonAssetSpec(
        "data/single_prompt_bomb.json",
        "object",
        None,
        (),
        (),
        (),
        "DEVELOPMENT_ONLY",
        "EXCLUDED_SINGLE_PROMPT_DEVELOPMENT_ONLY",
        None,
        None,
        None,
        None,
        None,
        "PROVENANCE_INCOMPLETE",
    ),
)


def resolve_asset_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        root = explicit
    elif os.environ.get(ASSET_ROOT_ENV):
        root = Path(os.environ[ASSET_ROOT_ENV])
    else:
        root = Path(__file__).resolve().parents[1]
    if _is_link_or_junction(root):
        raise AssetError(f"asset root must not be a symlink: {root}")
    resolved = root.resolve()
    if not resolved.is_dir():
        raise AssetError(f"asset root is not a directory: {resolved}")
    return resolved


def _resolve_below_root(root: Path, posix: PurePosixPath, label: str) -> Path:
    candidate = root
    for part in posix.parts:
        candidate = candidate / part
        if _is_link_or_junction(candidate):
            raise AssetError(f"{label} contains a symlink component: {posix.as_posix()}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AssetError(f"{label} escapes asset root: {posix.as_posix()}") from exc
    return resolved


def _resolve_relative(root: Path, relative_path: str) -> Path:
    posix = PurePosixPath(relative_path)
    if posix.is_absolute() or ".." in posix.parts or posix.parts[:1] != ("data",):
        raise AssetError(f"asset path must be data/... without traversal: {relative_path}")
    return _resolve_below_root(root, posix, "asset path")


def _top_level_type(value: Any) -> str:
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _reject_json_constant(value: str) -> None:
    raise AssetError(f"non-standard/nonfinite JSON constant is forbidden: {value}")


def _reject_duplicate_object_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AssetError(f"duplicate JSON object key is forbidden: {key}")
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_object_keys,
        parse_constant=_reject_json_constant,
    )


def _field_type_matches(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    return False


def _row_identity(spec: JsonAssetSpec, row: Mapping[str, Any], position: int) -> str:
    if not spec.stable_id_fields:
        return f"object:{canonical_sha256(row)}"
    values = []
    for field in spec.stable_id_fields:
        if field not in row:
            raise AssetError(f"{spec.relative_path} row {position} lacks identity field {field}")
        values.append([field, row[field]])
    return "sha256:" + canonical_sha256(values)


def inspect_json_asset(root: Path, spec: JsonAssetSpec) -> dict[str, Any]:
    path = _resolve_relative(root, spec.relative_path)
    if not path.is_file() or _is_link_or_junction(path):
        raise AssetError(f"required regular file is missing: {spec.relative_path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssetError(f"asset is not valid UTF-8: {spec.relative_path}") from exc
    try:
        payload = strict_json_loads(text)
    except (json.JSONDecodeError, AssetError) as exc:
        raise AssetError(f"asset is not valid JSON: {spec.relative_path}") from exc
    actual_type = _top_level_type(payload)
    if actual_type != spec.top_level_type:
        raise AssetError(
            f"{spec.relative_path} top-level type {actual_type}, expected {spec.top_level_type}"
        )
    row_identities: list[str] = []
    field_orders: list[list[str]] = []
    if isinstance(payload, list):
        if spec.row_count is not None and len(payload) != spec.row_count:
            raise AssetError(
                f"{spec.relative_path} row count {len(payload)}, expected {spec.row_count}"
            )
        for position, row in enumerate(payload):
            if not isinstance(row, dict):
                raise AssetError(f"{spec.relative_path} row {position} is not an object")
            order = list(row)
            if order != list(spec.ordered_fields):
                raise AssetError(
                    f"{spec.relative_path} row {position} fields/order {order}, expected {list(spec.ordered_fields)}"
                )
            for field, expected_type in spec.field_types:
                if not _field_type_matches(row[field], expected_type):
                    raise AssetError(
                        f"{spec.relative_path} row {position} field {field} is not {expected_type}"
                    )
            field_orders.append(order)
            row_identities.append(_row_identity(spec, row, position))
    else:
        field_orders.append(list(payload))
        row_identities.append(_row_identity(spec, payload, 0))
    duplicate_count = len(row_identities) - len(set(row_identities))
    frame = {
        "relative_path": spec.relative_path,
        "top_level_type": actual_type,
        "ordered_row_identities": row_identities,
    }
    return {
        "relative_path": spec.relative_path,
        "raw_sha256": file_sha256(path),
        "byte_length": len(raw),
        "utf8_valid": True,
        "json_top_level_type": actual_type,
        "row_count": len(payload) if isinstance(payload, list) else 1,
        "exact_ordered_field_names": list(spec.ordered_fields) if isinstance(payload, list) else list(payload),
        "field_order_uniform": len({tuple(order) for order in field_orders}) == 1,
        "stable_row_identities_sha256": canonical_sha256(row_identities),
        "stable_id_fields": list(spec.stable_id_fields),
        "field_types": {field: value_type for field, value_type in spec.field_types},
        "duplicate_identity_count": duplicate_count,
        "source_dataset": spec.source_dataset,
        "source_revision": spec.source_revision,
        "config": spec.config,
        "split": spec.split,
        "license": spec.license,
        "provenance_status": spec.provenance_status,
        "prompt_frame_membership": spec.prompt_frame_membership,
        "producing_script_sha256": None,
        "canonical_frame_sha256": canonical_sha256(frame),
        "inclusion_exclusion_rule": "Not formal until a frozen prompt-frame binding names exact rows.",
        "disposition": spec.disposition,
        "validation_status": "PASS",
        "validation_error": None,
    }


def inspect_unbound_candidate(root: Path, spec: JsonAssetSpec, error: AssetError) -> dict[str, Any]:
    """Record an invalid non-formal candidate without normalizing or replacing it."""
    path = _resolve_relative(root, spec.relative_path)
    if not path.is_file() or _is_link_or_junction(path):
        raise error
    raw = path.read_bytes()
    utf8_valid = True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        utf8_valid = False
        text = ""
    payload: Any = None
    if utf8_valid:
        try:
            payload = strict_json_loads(text)
        except (json.JSONDecodeError, AssetError):
            payload = None
    actual_type = _top_level_type(payload) if payload is not None else "invalid_json"
    actual_rows = len(payload) if isinstance(payload, list) else (1 if isinstance(payload, dict) else 0)
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        actual_fields = list(payload[0])
    elif isinstance(payload, dict):
        actual_fields = list(payload)
    else:
        actual_fields = []
    return {
        "relative_path": spec.relative_path,
        "raw_sha256": file_sha256(path),
        "byte_length": len(raw),
        "utf8_valid": utf8_valid,
        "json_top_level_type": actual_type,
        "row_count": actual_rows,
        "exact_ordered_field_names": actual_fields,
        "field_order_uniform": None,
        "stable_row_identities_sha256": None,
        "stable_id_fields": list(spec.stable_id_fields),
        "field_types": {field: value_type for field, value_type in spec.field_types},
        "duplicate_identity_count": None,
        "source_dataset": spec.source_dataset,
        "source_revision": spec.source_revision,
        "config": spec.config,
        "split": spec.split,
        "license": spec.license,
        "provenance_status": spec.provenance_status,
        "prompt_frame_membership": spec.prompt_frame_membership,
        "producing_script_sha256": None,
        "canonical_frame_sha256": None,
        "inclusion_exclusion_rule": "Excluded: candidate structure does not match the required expectation.",
        "disposition": spec.disposition,
        "validation_status": "SCHEMA_MISMATCH",
        "validation_error": str(error),
        "expected_json_top_level_type": spec.top_level_type,
        "expected_row_count": spec.row_count,
        "expected_ordered_field_names": list(spec.ordered_fields),
    }


def inspect_candidates(root: Path | None = None) -> list[dict[str, Any]]:
    resolved = resolve_asset_root(root)
    inspected = []
    for spec in CANDIDATE_SPECS:
        try:
            inspected.append(inspect_json_asset(resolved, spec))
        except AssetError as error:
            inspected.append(inspect_unbound_candidate(resolved, spec, error))
    return inspected


def build_external_dependency_inventory(root: Path | None = None) -> dict[str, Any]:
    resolved = resolve_asset_root(root)
    assets = {item["relative_path"]: item for item in inspect_candidates(resolved)}
    entries = []
    for spec in CANDIDATE_SPECS:
        item = assets[spec.relative_path]
        entries.append(
            {
                "dependency_id": spec.relative_path.replace("/", ":"),
                "dependency_type": "json_candidate_input",
                "purpose": spec.prompt_frame_membership,
                "frozen_stage3_scope": False,
                "source_repository": spec.source_dataset,
                "revision_commit": spec.source_revision,
                "config_split_subset": {
                    "config": spec.config,
                    "split": spec.split,
                    "subset": None,
                },
                "license": spec.license,
                "file_size": item["byte_length"],
                "present_locally": True,
                "server_preinstalled": False,
                "include_in_offline_bundle": False,
                "production_reference_locations": [],
                "production_reachable": False,
                "disposition": spec.disposition,
            }
        )
    from .binding import P1_PACKAGE_RELATIVE, validate_p1_harmful_candidate

    p1_candidate = validate_p1_harmful_candidate(resolved)
    entries.append({
        "dependency_id": "prompt-frame:p1-harmful-do-not-answer-v1",
        "dependency_type": "candidate_binding_input",
        "purpose": "fixed P1 harmful 100-row candidate; not formal without complete 310-row binding",
        "frozen_stage3_scope": True,
        "source_repository": p1_candidate["source_identity"]["repository_id"],
        "revision_commit": p1_candidate["source_identity"]["revision"],
        "config_split_subset": {
            "config": None,
            "split": None,
            "subset": "P1 harmful candidate 100",
        },
        "license": p1_candidate["source_identity"]["license"],
        "file_size": (resolved / P1_PACKAGE_RELATIVE / "selected_p1_harmful_100.json").stat().st_size,
        "present_locally": True,
        "server_preinstalled": False,
        "include_in_offline_bundle": False,
        "production_reference_locations": ["prompt_frame_binding_manifest.json"],
        "production_reachable": False,
        "disposition": "CANDIDATE_BINDING_INPUT",
    })
    entries.extend(
        [
            {
                "dependency_id": "behavior-model:qwen2.5-7b-instruct",
                "dependency_type": "checkpoint_tokenizer_template",
                "purpose": "formal behavior model",
                "frozen_stage3_scope": True,
                "source_repository": "Qwen/Qwen2.5-7B-Instruct",
                "revision_commit": "DEFERRED_SERVER_BINDING",
                "config_split_subset": None,
                "license": "DEFERRED_SERVER_BINDING",
                "file_size": None,
                "present_locally": False,
                "server_preinstalled": None,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["experiment_identity_manifest.json"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "judge-model:qwen3-8b",
                "dependency_type": "checkpoint_tokenizer_template",
                "purpose": "formal automated judge",
                "frozen_stage3_scope": True,
                "source_repository": "Qwen/Qwen3-8B",
                "revision_commit": "DEFERRED_SERVER_BINDING",
                "config_split_subset": None,
                "license": "DEFERRED_SERVER_BINDING",
                "file_size": None,
                "present_locally": False,
                "server_preinstalled": None,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["judge_freeze.json"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "download-script:jbb-behaviors",
                "dependency_type": "local_download_only_script",
                "purpose": "optional local source reconstruction; forbidden on server",
                "frozen_stage3_scope": False,
                "source_repository": "JailbreakBench/JBB-Behaviors",
                "revision_commit": "REQUIRED_EXPLICIT_40_HEX_COMMIT_ARGUMENT",
                "config_split_subset": {"config": "behaviors", "split": "harmful", "subset": None},
                "license": None,
                "file_size": (resolved / "scripts/download_jbb_behaviors.py").stat().st_size,
                "present_locally": True,
                "server_preinstalled": False,
                "include_in_offline_bundle": False,
                "production_reference_locations": [],
                "production_reachable": False,
                "disposition": "DEVELOPMENT_ONLY",
            },
            {
                "dependency_id": "python-package:huggingface-datasets",
                "dependency_type": "python_package_local_download_only",
                "purpose": "optional local JBB source reconstruction; forbidden in production",
                "frozen_stage3_scope": False,
                "source_repository": "huggingface/datasets",
                "revision_commit": None,
                "config_split_subset": None,
                "license": "Apache-2.0",
                "file_size": None,
                "present_locally": None,
                "server_preinstalled": False,
                "include_in_offline_bundle": False,
                "production_reference_locations": [],
                "production_reachable": False,
                "disposition": "DEVELOPMENT_ONLY",
            },
            {
                "dependency_id": "prompt-source:judge-rubric",
                "dependency_type": "frozen_local_prompt_source",
                "purpose": "harmful/benign judge rubric and priority-order identity only",
                "frozen_stage3_scope": True,
                "source_repository": "scripts/judge_phase_outputs.py",
                "revision_commit": file_sha256(resolved / "scripts/judge_phase_outputs.py"),
                "config_split_subset": None,
                "license": None,
                "file_size": (resolved / "scripts/judge_phase_outputs.py").stat().st_size,
                "present_locally": True,
                "server_preinstalled": True,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["judge_freeze.json"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "security:os-container-egress-isolation",
                "dependency_type": "server_security_control",
                "purpose": "kernel-level denial of all formal-runtime network egress",
                "frozen_stage3_scope": True,
                "source_repository": None,
                "revision_commit": "DEFERRED_SERVER_BINDING",
                "config_split_subset": None,
                "license": None,
                "file_size": None,
                "present_locally": False,
                "server_preinstalled": None,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["server_runtime_manifest.json"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "runtime:cpython-stdlib",
                "dependency_type": "python_runtime",
                "purpose": "production orchestration and bound standard-library references",
                "frozen_stage3_scope": True,
                "source_repository": None,
                "revision_commit": None,
                "config_split_subset": None,
                "license": "PSF",
                "file_size": None,
                "present_locally": True,
                "server_preinstalled": True,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["stage3_pipeline/"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "runtime:transformers",
                "dependency_type": "python_package",
                "purpose": "offline local checkpoint/tokenizer/template loading",
                "frozen_stage3_scope": True,
                "source_repository": "huggingface/transformers",
                "revision_commit": "DEFERRED_SERVER_BINDING",
                "config_split_subset": None,
                "license": "Apache-2.0",
                "file_size": None,
                "present_locally": None,
                "server_preinstalled": None,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["runtime_manifest.json"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "runtime:tokenizers-safetensors",
                "dependency_type": "python_packages",
                "purpose": "offline tokenizer and weight serialization runtime",
                "frozen_stage3_scope": True,
                "source_repository": None,
                "revision_commit": "DEFERRED_SERVER_BINDING",
                "config_split_subset": None,
                "license": "DEFERRED_SERVER_BINDING",
                "file_size": None,
                "present_locally": None,
                "server_preinstalled": None,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["runtime_manifest.json"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "runtime:torch-2.7.1",
                "dependency_type": "python_package",
                "purpose": "server vector generation and model execution",
                "frozen_stage3_scope": True,
                "source_repository": None,
                "revision_commit": "2.7.1",
                "config_split_subset": None,
                "license": "BSD-3-Clause",
                "file_size": None,
                "present_locally": None,
                "server_preinstalled": None,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["random_vector_manifest.json", "runtime_manifest.json"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "runtime:cuda-gpu",
                "dependency_type": "server_hardware_runtime",
                "purpose": "single-GPU formal model execution",
                "frozen_stage3_scope": True,
                "source_repository": None,
                "revision_commit": "DEFERRED_SERVER_BINDING",
                "config_split_subset": None,
                "license": "DEFERRED_SERVER_BINDING",
                "file_size": None,
                "present_locally": False,
                "server_preinstalled": None,
                "include_in_offline_bundle": False,
                "production_reference_locations": ["runtime_manifest.json"],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
            {
                "dependency_id": "identity:base-anchors-and-vectors",
                "dependency_type": "server_identity_artifacts",
                "purpose": "frozen A/T/H anchors and random-vector tensor identities",
                "frozen_stage3_scope": True,
                "source_repository": None,
                "revision_commit": "DEFERRED_SERVER_BINDING",
                "config_split_subset": None,
                "license": None,
                "file_size": None,
                "present_locally": False,
                "server_preinstalled": None,
                "include_in_offline_bundle": False,
                "production_reference_locations": [
                    "base_anchor_manifest.json",
                    "random_vector_manifest.json",
                ],
                "production_reachable": True,
                "disposition": "SERVER_PREINSTALLED_ASSET",
            },
        ]
    )
    for entry in entries:
        if entry["disposition"] not in ALLOWED_DISPOSITIONS:
            raise AssertionError("invalid inventory disposition")
    return {
        "schema_version": "paper1-stage3-external-dependency-inventory-v1",
        "protocol_version": "v3.5-rc2",
        "created_at_utc": utc_now(),
        "network_required_at_production_runtime": False,
        "online_fallback": False,
        "dependencies": entries,
        "inventory_sha256": canonical_sha256(entries),
    }


def build_offline_asset_manifest(
    root: Path | None = None,
    *,
    binding_documents: Mapping[str, Mapping[str, Any]] | None = None,
    binding_root: Path | None = None,
    authorize_synthetic_bundle: bool = False,
) -> dict[str, Any]:
    resolved = resolve_asset_root(root)
    assets = inspect_candidates(resolved)
    from .binding import P1_PACKAGE_RELATIVE, validate_binding_set, validate_p1_harmful_candidate

    candidate = validate_p1_harmful_candidate(resolved)
    candidate_entry = {
        key: value for key, value in candidate.items()
        if key != "ordered_record_identities"
    }
    assets.append(candidate_entry)
    if binding_documents is None:
        binding_validation = {
            "schema_version": "paper1-stage3-binding-validation-result-v2",
            "validation_status": "INCOMPLETE",
            "complete": False,
            "synthetic_fixture": False,
            "formal_input_claim": False,
            "validated_components": ["p1_harmful_candidate"],
            "missing_components": [
                "checkpoint", "judge", "vectors", "base_anchor", "prompt_frames"
            ],
            "data_inputs": [],
            "formal_experiment_run": False,
        }
        formal_inputs: list[dict[str, Any]] = []
        binding_inputs: list[dict[str, Any]] = [{
            "binding_role": "p1_harmful_candidate",
            "disposition": "CANDIDATE_BINDING_INPUT",
            "relative_path": P1_PACKAGE_RELATIVE,
            "frame_sha256": candidate["frame_sha256"],
            "formal_input": False,
        }]
        status = "DATA_IDENTITY_BLOCKED"
        blocking_reasons = [
            "Only the approved P1 harmful 100-row candidate is bound.",
            "P1 benign, behavior-screen, behavior-confirm, and benign-confirm identities remain A0.",
            "Checkpoint, judge, vector, base-anchor, and complete 310-prompt bindings are absent.",
        ]
    else:
        validation_root = (binding_root or resolved).resolve()
        binding_validation = validate_binding_set(
            binding_documents,
            validation_root,
            candidate=None if any(
                document.get("synthetic_fixture") is True
                for document in binding_documents.values()
            ) else candidate,
        )
        if binding_validation["synthetic_fixture"]:
            formal_inputs = (
                list(binding_validation["data_inputs"])
                if authorize_synthetic_bundle else []
            )
            status = (
                "SYNTHETIC-OFFLINE-LOADER-READY"
                if authorize_synthetic_bundle else "SYNTHETIC-BINDING-VALIDATED"
            )
            blocking_reasons = [
                "Synthetic full-shaped bindings are non-formal verification fixtures."
            ]
            binding_inputs = [
                {
                    "binding_role": role,
                    "disposition": "SYNTHETIC_BINDING_FIXTURE",
                    "self_sha256": digest,
                    "formal_input": False,
                }
                for role, digest in binding_validation["component_self_sha256"].items()
            ]
        else:
            if authorize_synthetic_bundle:
                raise AssetError("synthetic bundle authorization cannot be used for real bindings")
            if validation_root != resolved:
                raise AssetError("real binding root must equal the loadable asset root")
            formal_inputs = list(binding_validation["data_inputs"])
            if (
                len(formal_inputs) != 5
                or any(
                    not isinstance(entry, Mapping)
                    or entry.get("disposition") != "FORMAL_INPUT"
                    or entry.get("formal_input") is not True
                    for entry in formal_inputs
                )
                or len({entry.get("relative_path") for entry in formal_inputs}) != 5
            ):
                raise AssetError("real binding validation did not produce five FORMAL_INPUT entries")
            status = "OFFLINE-ASSET-READY"
            blocking_reasons = []
            binding_inputs = [
                {
                    "binding_role": role,
                    "disposition": "FORMAL_BINDING_DOCUMENT",
                    "self_sha256": digest,
                    "formal_input": False,
                }
                for role, digest in binding_validation["component_self_sha256"].items()
            ]
    if status == "OFFLINE-ASSET-READY" and not formal_inputs:
        raise AssetError("OFFLINE-ASSET-READY requires nonempty FORMAL_INPUT entries")
    manifest = {
        "schema_version": "paper1-stage3-offline-asset-manifest-v1",
        "protocol_version": "v3.5-rc2",
        "created_at_utc": utc_now(),
        "asset_root_identity": "PAPER1_STAGE3_ASSET_ROOT",
        "absolute_paths_are_identity": False,
        "formal_inputs": formal_inputs,
        "binding_inputs": binding_inputs,
        "candidate_assets": assets,
        "binding_validation": binding_validation,
        "offline_asset_status": status,
        "run_ready": False,
        "formal_experiment_run": False,
        "blocking_reasons": blocking_reasons,
        "raw_sources_modified": False,
        "online_fallback": False,
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    if status == "OFFLINE-ASSET-READY":
        loader = OfflineJsonLoader(
            manifest,
            resolved,
            expected_manifest_sha256=manifest["manifest_sha256"],
            binding_documents=binding_documents,
            binding_root=validation_root,
        )
        for entry in formal_inputs:
            loader.load_formal(entry["relative_path"])
    return manifest


BOUND_DATA_INPUT_KEYS = {
    "relative_path", "raw_sha256", "byte_length", "source_schema_field",
    "source_schema_version", "json_top_level_type", "records_field", "row_count",
    "source_row_identity_sha256", "ordered_record_identities_sha256",
    "canonical_frame_sha256", "prompt_frame_membership", "source_repository_id",
    "source_revision", "upstream_source_path", "license", "license_material",
    "disposition", "formal_input",
}


class OfflineJsonLoader:
    """Load only exact manifest-bound JSON bytes below the configured asset root."""

    def __init__(
        self,
        manifest: Mapping[str, Any],
        asset_root: Path | None = None,
        *,
        expected_manifest_sha256: str,
        binding_documents: Mapping[str, Mapping[str, Any]] | None = None,
        binding_root: Path | None = None,
        allow_synthetic_fixture: bool = False,
    ) -> None:
        self.manifest = dict(manifest)
        self.root = resolve_asset_root(asset_root)
        self.synthetic_fixture = False
        self.binding_revalidated = False
        expected = self.manifest.get("manifest_sha256")
        actual = canonical_sha256(
            {key: value for key, value in self.manifest.items() if key != "manifest_sha256"}
        )
        if expected != actual:
            raise AssetError("offline asset manifest hash mismatch")
        if (
            not isinstance(expected_manifest_sha256, str)
            or len(expected_manifest_sha256) != 64
            or any(char not in "0123456789abcdef" for char in expected_manifest_sha256)
            or expected_manifest_sha256 != expected
        ):
            raise AssetError("offline asset manifest does not match the freeze-bound expected hash")
        if self.manifest.get("offline_asset_status") == "OFFLINE-ASSET-READY":
            validation = self.manifest.get("binding_validation")
            entries = self.manifest.get("formal_inputs")
            if (
                not isinstance(validation, Mapping)
                or validation.get("schema_version")
                != "paper1-stage3-binding-validation-result-v2"
                or validation.get("validation_status") != "PASS"
                or validation.get("complete") is not True
                or validation.get("formal_experiment_run") is not False
                or not isinstance(entries, list)
                or not entries
                or any(
                    not isinstance(entry, Mapping)
                    or set(entry) != BOUND_DATA_INPUT_KEYS
                    or entry.get("disposition") != "FORMAL_INPUT"
                    or entry.get("formal_input") is not True
                    for entry in entries
                )
            ):
                raise AssetError("READY manifest lacks complete loadable FORMAL_INPUT entries")
            if validation.get("synthetic_fixture") is True:
                raise AssetError("full-shaped synthetic READY state cannot load formal inputs")
            else:
                if validation.get("formal_input_claim") is not True or binding_documents is None:
                    raise AssetError("real READY loading requires the complete binding documents")
                from .binding import validate_binding_set, validate_p1_harmful_candidate

                candidate = validate_p1_harmful_candidate(self.root)
                actual_validation = validate_binding_set(
                    binding_documents,
                    (binding_root or self.root).resolve(),
                    candidate=candidate,
                )
                if actual_validation != validation:
                    raise AssetError("READY binding validation receipt differs from revalidation")
                if entries != actual_validation.get("data_inputs"):
                    raise AssetError("READY FORMAL_INPUT entries differ from binding revalidation")
                self.binding_revalidated = True
        elif self.manifest.get("offline_asset_status") == "SYNTHETIC-OFFLINE-LOADER-READY":
            validation = self.manifest.get("binding_validation")
            entries = self.manifest.get("formal_inputs")
            if (
                isinstance(validation, Mapping)
                and validation.get("schema_version")
                == "paper1-stage3-binding-validation-result-v2"
            ):
                if (
                    not allow_synthetic_fixture
                    or binding_documents is None
                    or validation.get("validation_status") != "PASS"
                    or validation.get("complete") is not True
                    or validation.get("synthetic_fixture") is not True
                    or validation.get("formal_input_claim") is not False
                    or validation.get("formal_experiment_run") is not False
                    or not isinstance(entries, list)
                    or not entries
                    or any(
                        not isinstance(entry, Mapping)
                        or set(entry) != BOUND_DATA_INPUT_KEYS
                        or entry.get("disposition") != "SYNTHETIC_FIXTURE_INPUT"
                        or entry.get("formal_input") is not False
                        for entry in entries
                    )
                ):
                    raise AssetError("full-shaped synthetic loader authorization differs")
                from .binding import validate_binding_set

                actual_validation = validate_binding_set(
                    binding_documents,
                    (binding_root or self.root).resolve(),
                    candidate=None,
                )
                if actual_validation != validation or entries != actual_validation.get("data_inputs"):
                    raise AssetError("synthetic binding validation differs from revalidation")
                self.synthetic_fixture = True
                self.binding_revalidated = True
                return
            if (
                not allow_synthetic_fixture
                or not isinstance(validation, Mapping)
                or validation.get("schema_version")
                != "paper1-stage3-offline-loader-fixture-authorization-v1"
                or validation.get("validation_status") != "PASS"
                or validation.get("synthetic_fixture") is not True
                or validation.get("formal_input_claim") is not False
                or validation.get("formal_experiment_run") is not False
                or not isinstance(entries, list)
                or any(
                    not isinstance(entry, Mapping)
                    or entry.get("disposition") != "SYNTHETIC_FIXTURE_INPUT"
                    or entry.get("formal_input") is not False
                    for entry in entries
                )
            ):
                raise AssetError("synthetic loader fixture authorization differs")
            self.synthetic_fixture = True

    def load_formal(self, relative_path: str) -> Any:
        if self.manifest.get("offline_asset_status") not in {
            "OFFLINE-ASSET-READY", "SYNTHETIC-OFFLINE-LOADER-READY"
        }:
            raise AssetError("formal input loading requires OFFLINE-ASSET-READY")
        if self.manifest.get("online_fallback") is not False:
            raise AssetError("formal input manifest must explicitly disable online fallback")
        entries = [
            entry for entry in self.manifest.get("formal_inputs", [])
            if entry.get("relative_path") == relative_path
        ]
        if len(entries) != 1:
            raise AssetError(f"asset is not a unique FORMAL_INPUT: {relative_path}")
        entry = entries[0]
        expected_disposition = (
            "SYNTHETIC_FIXTURE_INPUT" if self.synthetic_fixture else "FORMAL_INPUT"
        )
        if entry.get("disposition") != expected_disposition:
            raise AssetError(f"formal input has invalid disposition: {relative_path}")
        membership = entry.get("prompt_frame_membership")
        if (
            not isinstance(membership, str)
            or not membership
            or membership.startswith("EXCLUDED")
            or membership.startswith("UNBOUND")
        ):
            raise AssetError(f"formal input lacks bound prompt-frame membership: {relative_path}")
        path = _resolve_relative(self.root, relative_path)
        if not path.is_file() or _is_link_or_junction(path):
            raise AssetError(f"formal input missing or symlinked: {relative_path}")
        raw = path.read_bytes()
        if len(raw) != entry["byte_length"] or file_sha256(path) != entry["raw_sha256"]:
            raise AssetError(f"formal input raw identity mismatch: {relative_path}")
        try:
            payload = strict_json_loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, AssetError) as exc:
            raise AssetError(f"formal input is invalid UTF-8 JSON: {relative_path}") from exc
        if _top_level_type(payload) != entry["json_top_level_type"]:
            raise AssetError(f"formal input top-level type mismatch: {relative_path}")
        actual_rows = len(payload) if isinstance(payload, list) else 1
        if self.binding_revalidated:
            if set(entry) != BOUND_DATA_INPUT_KEYS:
                raise AssetError(f"bound input entry schema differs: {relative_path}")
            if not isinstance(payload, Mapping):
                raise AssetError(f"bound input must be a JSON object: {relative_path}")
            if payload.get(entry["source_schema_field"]) != entry["source_schema_version"]:
                raise AssetError(f"bound input source schema differs: {relative_path}")
            records = payload.get(entry["records_field"])
            if not isinstance(records, list) or len(records) != entry["row_count"]:
                raise AssetError(f"bound input record count differs: {relative_path}")
            material = entry["license_material"]
            if not isinstance(material, Mapping) or set(material) != {
                "source_relative_path", "bundle_relative_path", "raw_sha256"
            }:
                raise AssetError(f"bound input license material differs: {relative_path}")
            license_path = _resolve_below_root(
                self.root,
                PurePosixPath(material["source_relative_path"]),
                "license source path",
            )
            if (
                not license_path.is_file()
                or _is_link_or_junction(license_path)
                or file_sha256(license_path) != material["raw_sha256"]
            ):
                raise AssetError(f"bound input license identity differs: {relative_path}")
            return payload
        if actual_rows != entry["row_count"]:
            raise AssetError(f"formal input row count mismatch: {relative_path}")
        if isinstance(payload, list):
            expected_fields = entry["exact_ordered_field_names"]
            identities = []
            identity_fields = tuple(entry["stable_id_fields"])
            spec = JsonAssetSpec(
                relative_path,
                entry["json_top_level_type"],
                entry["row_count"],
                tuple(expected_fields),
                identity_fields,
                tuple(entry["field_types"].items()),
                "FORMAL_INPUT",
                entry["prompt_frame_membership"],
                entry.get("source_dataset"),
                entry.get("source_revision"),
                entry.get("config"),
                entry.get("split"),
                entry.get("license"),
                entry.get("provenance_status", "PROVENANCE_INCOMPLETE"),
            )
            for position, row in enumerate(payload):
                if not isinstance(row, dict) or list(row) != expected_fields:
                    raise AssetError(f"formal input schema/order mismatch at row {position}")
                for field, expected_type in entry["field_types"].items():
                    if not _field_type_matches(row[field], expected_type):
                        raise AssetError(
                            f"formal input field type mismatch at row {position}: {field}"
                        )
                identities.append(_row_identity(spec, row, position))
            if len(identities) != len(set(identities)):
                raise AssetError(f"formal input duplicate identity: {relative_path}")
            if canonical_sha256(identities) != entry["stable_row_identities_sha256"]:
                raise AssetError(f"formal input stable identity hash mismatch: {relative_path}")
            frame = {
                "relative_path": relative_path,
                "top_level_type": entry["json_top_level_type"],
                "ordered_row_identities": identities,
            }
            if canonical_sha256(frame) != entry["canonical_frame_sha256"]:
                raise AssetError(f"formal input canonical frame hash mismatch: {relative_path}")
        return payload


def build_bundle(
    manifest: Mapping[str, Any],
    output_directory: Path,
    *,
    asset_root: Path | None = None,
    expected_manifest_sha256: str,
    allow_synthetic_fixture: bool = False,
    binding_documents: Mapping[str, Mapping[str, Any]] | None = None,
    binding_root: Path | None = None,
) -> dict[str, Any]:
    """Build a Linux-portable bundle only from explicit FORMAL_INPUT entries."""
    formal = list(manifest.get("formal_inputs", []))
    allowed_status = (
        "SYNTHETIC-OFFLINE-LOADER-READY"
        if allow_synthetic_fixture else "OFFLINE-ASSET-READY"
    )
    if manifest.get("offline_asset_status") != allowed_status:
        raise AssetError("offline bundle requires the expected validated ready status")
    archive = output_directory.with_suffix(".tar.gz")
    if output_directory.exists() or _is_link_or_junction(output_directory):
        raise AssetError(f"refusing to overwrite bundle directory: {output_directory}")
    if archive.exists() or _is_link_or_junction(archive):
        raise AssetError(f"refusing to overwrite bundle archive: {archive}")
    root = resolve_asset_root(asset_root)
    loader = OfflineJsonLoader(
        manifest,
        root,
        expected_manifest_sha256=expected_manifest_sha256,
        allow_synthetic_fixture=allow_synthetic_fixture,
        binding_documents=binding_documents,
        binding_root=binding_root,
    )
    if not formal:
        raise AssetError(
            "validated binding inputs are separate from packable data FORMAL_INPUT entries"
        )
    license_plan: list[tuple[Path, PurePosixPath, str]] = []
    seen_formal_paths: set[str] = set()
    seen_license_targets: set[str] = set()
    for entry in formal:
        if not isinstance(entry, Mapping):
            raise AssetError("FORMAL_INPUT entry must be an object")
        relative = entry.get("relative_path")
        if not isinstance(relative, str) or relative in seen_formal_paths:
            raise AssetError("FORMAL_INPUT paths must be nonempty and unique")
        seen_formal_paths.add(relative)
        loader.load_formal(relative)

        license_id = entry.get("license")
        material = entry.get("license_material")
        if not isinstance(license_id, str) or not license_id:
            raise AssetError(f"FORMAL_INPUT lacks an explicit license identifier: {relative}")
        if not isinstance(material, Mapping) or set(material) != {
            "source_relative_path",
            "bundle_relative_path",
            "raw_sha256",
        }:
            raise AssetError(f"FORMAL_INPUT lacks explicit license material: {relative}")
        source_relative = material["source_relative_path"]
        bundle_relative = material["bundle_relative_path"]
        expected_license_hash = material["raw_sha256"]
        if not isinstance(source_relative, str) or not source_relative:
            raise AssetError(f"invalid license source path: {relative}")
        source_posix = PurePosixPath(source_relative)
        if source_posix.is_absolute() or ".." in source_posix.parts:
            raise AssetError(f"license source path is not repository-relative: {relative}")
        license_source = _resolve_below_root(root, source_posix, "license source path")
        if not license_source.is_file() or _is_link_or_junction(license_source):
            raise AssetError(f"license source is missing or symlinked: {source_relative}")
        if (
            not isinstance(expected_license_hash, str)
            or len(expected_license_hash) != 64
            or any(char not in "0123456789abcdef" for char in expected_license_hash)
            or file_sha256(license_source) != expected_license_hash
        ):
            raise AssetError(f"license material hash mismatch: {source_relative}")
        if not isinstance(bundle_relative, str):
            raise AssetError(f"invalid license bundle path: {relative}")
        bundle_posix = PurePosixPath(bundle_relative)
        if (
            bundle_posix.is_absolute()
            or ".." in bundle_posix.parts
            or bundle_posix.parts[:1] != ("LICENSES",)
            or len(bundle_posix.parts) < 2
        ):
            raise AssetError(f"license bundle path must be below LICENSES/: {relative}")
        normalized_target = bundle_posix.as_posix()
        if normalized_target in seen_license_targets:
            raise AssetError(f"duplicate license bundle path: {normalized_target}")
        seen_license_targets.add(normalized_target)
        license_plan.append((license_source, bundle_posix, expected_license_hash))

    created_directory = False
    created_archive = False
    try:
        output_directory.mkdir(parents=True, exist_ok=False)
        created_directory = True
        (output_directory / "data").mkdir()
        (output_directory / "LICENSES").mkdir()
        (output_directory / "metadata").mkdir()
        (output_directory / "validation").mkdir()
        checksums = []
        for entry in formal:
            relative = entry["relative_path"]
            source = _resolve_relative(root, relative)
            if file_sha256(source) != entry["raw_sha256"]:
                raise AssetError(f"source hash changed before bundle: {relative}")
            target = output_directory.joinpath(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if source.read_bytes() != target.read_bytes():
                raise AssetError(f"bundle copy changed raw bytes: {relative}")
            checksums.append(f"{entry['raw_sha256']}  {relative}")
        for source, bundle_relative, expected_hash in license_plan:
            target = output_directory.joinpath(*bundle_relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if file_sha256(target) != expected_hash:
                raise AssetError(f"bundle copy changed license bytes: {bundle_relative.as_posix()}")
            checksums.append(f"{expected_hash}  {bundle_relative.as_posix()}")
        manifest_path = output_directory / "offline_asset_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        checksums.append(f"{file_sha256(manifest_path)}  offline_asset_manifest.json")
        (output_directory / "checksums.sha256").write_text(
            "\n".join(checksums) + "\n", encoding="ascii", newline="\n"
        )
        raw_archive = archive.open("xb")
        created_archive = True
        with raw_archive:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_archive, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as handle:
                    for path in sorted(output_directory.rglob("*")):
                        arcname = PurePosixPath(
                            "offline_bundle", *path.relative_to(output_directory).parts
                        )
                        info = handle.gettarinfo(str(path), arcname=str(arcname))
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        info.mtime = 0
                        if info.isreg():
                            info.mode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
                            with path.open("rb") as source:
                                handle.addfile(info, source)
                        elif info.isdir():
                            info.mode = (
                                stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
                                | stat.S_IRGRP | stat.S_IXGRP
                                | stat.S_IROTH | stat.S_IXOTH
                            )
                            handle.addfile(info)
                        else:
                            raise AssetError(
                                f"unsupported offline bundle member type: {path}"
                            )
    except BaseException:
        if created_archive and archive.exists() and not _is_link_or_junction(archive):
            archive.unlink()
        if created_directory and output_directory.exists() and not _is_link_or_junction(output_directory):
            shutil.rmtree(output_directory)
        raise
    bundled_files = [path for path in output_directory.rglob("*") if path.is_file()]
    return {
        "bundle_file": archive.name,
        "bundle_sha256": file_sha256(archive),
        "bundle_bytes": archive.stat().st_size,
        "file_count": len(bundled_files),
        "payload_bytes": sum(path.stat().st_size for path in bundled_files),
        "formal_inputs": [entry["relative_path"] for entry in formal],
    }
