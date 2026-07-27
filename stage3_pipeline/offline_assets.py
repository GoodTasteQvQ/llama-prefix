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


def build_offline_asset_manifest(root: Path | None = None) -> dict[str, Any]:
    resolved = resolve_asset_root(root)
    assets = inspect_candidates(resolved)
    manifest = {
        "schema_version": "paper1-stage3-offline-asset-manifest-v1",
        "protocol_version": "v3.5-rc2",
        "created_at_utc": utc_now(),
        "asset_root_identity": "PAPER1_STAGE3_ASSET_ROOT",
        "absolute_paths_are_identity": False,
        "formal_inputs": [],
        "candidate_assets": assets,
        "offline_asset_status": "DATA_IDENTITY_BLOCKED",
        "blocking_reasons": [
            "CURRENT_RELEASE and frozen v3.5-rc2 do not name data/*.json files.",
            "No frozen exact row-selection manifest binds harmful and benign prompt frames.",
            "data/single_prompt_bomb.json is an array but the required candidate expectation is one object.",
        ],
        "raw_sources_modified": False,
        "online_fallback": False,
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    return manifest


class OfflineJsonLoader:
    """Load only exact manifest-bound JSON bytes below the configured asset root."""

    def __init__(
        self,
        manifest: Mapping[str, Any],
        asset_root: Path | None = None,
        *,
        expected_manifest_sha256: str,
    ) -> None:
        self.manifest = dict(manifest)
        self.root = resolve_asset_root(asset_root)
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

    def load_formal(self, relative_path: str) -> Any:
        if self.manifest.get("offline_asset_status") != "OFFLINE-ASSET-READY":
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
        if entry.get("disposition") != "FORMAL_INPUT":
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
) -> dict[str, Any]:
    """Build a Linux-portable bundle only from explicit FORMAL_INPUT entries."""
    formal = list(manifest.get("formal_inputs", []))
    if manifest.get("offline_asset_status") != "OFFLINE-ASSET-READY" or not formal:
        raise AssetError("offline bundle requires a ready manifest with FORMAL_INPUT entries")
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
