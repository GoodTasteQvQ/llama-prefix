"""Strict local-only Stage 3 asset loading and reproducibility inventory."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .core import PipelineError, canonical_sha256, offline_execution_guard


class AssetError(PipelineError):
    """A local asset is missing, unsafe, ambiguous, or inconsistent."""


def _is_link_or_junction(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    is_junction = getattr(path, "is_junction", None)
    return (
        stat.S_ISLNK(info.st_mode)
        or (callable(is_junction) and is_junction())
        or bool(
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    )


def resolve_asset_root(explicit: Path | None = None) -> Path:
    source = explicit
    if source is None:
        configured = os.environ.get("PAPER1_STAGE3_ASSET_ROOT")
        if not configured:
            raise AssetError("an explicit local asset root or PAPER1_STAGE3_ASSET_ROOT is required")
        source = Path(configured)
    if not isinstance(source, Path):
        raise AssetError("asset root must be a local pathlib.Path")
    absolute_source = Path(os.path.abspath(source))
    current = Path(absolute_source.anchor)
    for part in absolute_source.parts[1:]:
        current = current / part
        if _is_link_or_junction(current):
            raise AssetError("asset root path may not contain a symlink or junction")
    root = absolute_source.resolve()
    if not root.is_dir():
        raise AssetError(f"asset root is not a directory: {root}")
    return root


def _relative_path(value: Any, field: str = "relative_path") -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "://" in value:
        raise AssetError(f"{field} must be a nonempty local POSIX relative path")
    posix = PurePosixPath(value)
    if posix.is_absolute() or not posix.parts or any(part in {"", ".", ".."} for part in posix.parts):
        raise AssetError(f"{field} must stay below the explicit asset root")
    if ":" in posix.parts[0]:
        raise AssetError(f"{field} may not name a drive or URL scheme")
    return posix


def _resolve_regular_file(root: Path, relative_path: str, field: str = "relative_path") -> Path:
    posix = _relative_path(relative_path, field)
    candidate = root
    for part in posix.parts:
        candidate = candidate / part
        if _is_link_or_junction(candidate):
            raise AssetError(f"{field} contains a symlink or junction component")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AssetError(f"{field} escapes the explicit asset root") from exc
    if not resolved.is_file() or _is_link_or_junction(resolved):
        raise AssetError(f"required regular file is missing: {relative_path}")
    return resolved


def _reject_json_constant(value: str) -> None:
    raise AssetError(f"JSON contains a non-standard constant: {value}")


def _reject_duplicate_object_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AssetError(f"JSON contains a duplicate object key: {key}")
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise AssetError("asset is not strict JSON") from exc


def _read_strict_json(path: Path) -> tuple[bytes, Any]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssetError(f"asset is not strict UTF-8: {path}") from exc
    return raw, strict_json_loads(text)


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AssetError(f"{field} must be a lowercase SHA256")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AssetError(f"{field} must be a nonnegative integer")
    return value


def _field_type_matches(value: Any, expected: str) -> bool:
    return {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
    }.get(expected, False)


@dataclass(frozen=True)
class JsonInputSpec:
    relative_path: str
    top_level_type: str
    row_count: int | None = None
    ordered_fields: tuple[str, ...] = ()
    identity_fields: tuple[str, ...] = ()
    field_types: tuple[tuple[str, str], ...] = ()
    expected_sha256: str | None = None
    expected_byte_length: int | None = None
    expected_frame_sha256: str | None = None
    source_repository: str | None = None
    source_revision: str | None = None
    source_path_or_config_split: str | None = None
    license: str | None = None
    provenance: str | None = None

    def validate(self) -> None:
        _relative_path(self.relative_path)
        if self.top_level_type not in {"array", "object"}:
            raise AssetError("top_level_type must be array or object")
        if self.row_count is None:
            raise AssetError("row_count is required for every offline JSON input")
        _nonnegative_int(self.row_count, "row_count")
        for label, values in (
            ("ordered_fields", self.ordered_fields),
            ("identity_fields", self.identity_fields),
        ):
            if any(not isinstance(value, str) or not value for value in values):
                raise AssetError(f"{label} must contain nonempty strings")
            if len(values) != len(set(values)):
                raise AssetError(f"{label} must be unique")
            if not values:
                raise AssetError(f"{label} must be explicitly nonempty")
        type_fields = [field for field, _ in self.field_types]
        if len(type_fields) != len(set(type_fields)):
            raise AssetError("field_types may not repeat fields")
        if any(expected not in {"string", "integer", "boolean", "null", "object", "array"} for _, expected in self.field_types):
            raise AssetError("field_types contains an unsupported type")
        if tuple(type_fields) != self.ordered_fields:
            raise AssetError("field_types must exactly cover ordered_fields in order")
        if any(field not in self.ordered_fields for field in self.identity_fields):
            raise AssetError("identity_fields must be a subset of ordered_fields")
        if self.expected_sha256 is None or self.expected_frame_sha256 is None:
            raise AssetError("raw and canonical frame SHA256 values are required")
        _sha(self.expected_sha256, "expected_sha256")
        _sha(self.expected_frame_sha256, "expected_frame_sha256")
        if self.expected_byte_length is None:
            raise AssetError("expected_byte_length is required")
        _nonnegative_int(self.expected_byte_length, "expected_byte_length")
        provenance = (
            self.source_repository,
            self.source_revision,
            self.source_path_or_config_split,
            self.license,
            self.provenance,
        )
        if any(
            not isinstance(value, str) or not value for value in provenance
        ):
            raise AssetError("source, revision, path/config/split, license, and provenance are all required")


class OfflineJsonLoader:
    """Load only explicitly registered local JSON assets without fallback behavior."""

    def __init__(self, asset_root: Path, specs: Sequence[JsonInputSpec]) -> None:
        self.root = resolve_asset_root(asset_root)
        self.specs: dict[str, JsonInputSpec] = {}
        for spec in specs:
            if not isinstance(spec, JsonInputSpec):
                raise AssetError("every input specification must be JsonInputSpec")
            spec.validate()
            if spec.relative_path in self.specs:
                raise AssetError(f"duplicate input specification: {spec.relative_path}")
            self.specs[spec.relative_path] = spec
        if not self.specs:
            raise AssetError("at least one explicit input specification is required")

    def _inspect(self, relative_path: str) -> tuple[Any, dict[str, Any]]:
        try:
            spec = self.specs[relative_path]
        except KeyError as exc:
            raise AssetError(f"input is not registered; fallback is forbidden: {relative_path}") from exc
        path = _resolve_regular_file(self.root, spec.relative_path)
        raw, payload = _read_strict_json(path)
        raw_sha256 = _sha256_bytes(raw)
        if spec.expected_sha256 is not None and raw_sha256 != spec.expected_sha256:
            raise AssetError(f"raw SHA256 mismatch: {relative_path}")
        if spec.expected_byte_length is not None and len(raw) != spec.expected_byte_length:
            raise AssetError(f"raw byte length mismatch: {relative_path}")
        expected_type = list if spec.top_level_type == "array" else dict
        if not isinstance(payload, expected_type):
            raise AssetError(f"JSON top-level type mismatch: {relative_path}")
        rows = payload if isinstance(payload, list) else [payload]
        if spec.row_count is not None and len(rows) != spec.row_count:
            raise AssetError(f"row count mismatch: {relative_path}")
        identities: list[str] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise AssetError(f"row {index} is not an object: {relative_path}")
            if spec.ordered_fields and list(row) != list(spec.ordered_fields):
                raise AssetError(f"row {index} exact ordered fields mismatch: {relative_path}")
            for field, expected_type_name in spec.field_types:
                if field not in row or not _field_type_matches(row[field], expected_type_name):
                    raise AssetError(f"row {index} field type mismatch for {field}: {relative_path}")
            if spec.identity_fields:
                if any(field not in row for field in spec.identity_fields):
                    raise AssetError(f"row {index} lacks a stable identity field: {relative_path}")
                identities.append(canonical_sha256([[field, row[field]] for field in spec.identity_fields]))
            else:
                identities.append(canonical_sha256(row))
        duplicate_count = len(identities) - len(set(identities))
        if duplicate_count:
            raise AssetError(f"duplicate stable identity count is {duplicate_count}: {relative_path}")
        frame_sha256 = canonical_sha256(identities)
        if spec.expected_frame_sha256 is not None and frame_sha256 != spec.expected_frame_sha256:
            raise AssetError(f"canonical ordered frame SHA256 mismatch: {relative_path}")
        inventory = {
            "relative_path": relative_path,
            "raw_byte_length": len(raw),
            "raw_sha256": raw_sha256,
            "json_top_level_type": spec.top_level_type,
            "row_count": len(rows),
            "exact_ordered_fields": list(spec.ordered_fields),
            "stable_identity_fields": list(spec.identity_fields),
            "duplicate_identity_count": duplicate_count,
            "canonical_ordered_frame_sha256": frame_sha256,
            "source_repository": spec.source_repository,
            "source_revision": spec.source_revision,
            "source_path_or_config_split": spec.source_path_or_config_split,
            "license": spec.license,
            "provenance": spec.provenance,
        }
        return payload, inventory

    def load(self, relative_path: str) -> Any:
        with offline_execution_guard():
            payload, _ = self._inspect(relative_path)
        return payload

    def inventory(self) -> list[dict[str, Any]]:
        with offline_execution_guard():
            return [self._inspect(relative_path)[1] for relative_path in sorted(self.specs)]


ACTIVE_ENTRY_FIELDS = (
    "schema_version", "role", "status", "relative_path", "raw_byte_length", "row_count",
    "selected_top_level_ordered_fields", "selected_record_ordered_fields",
    "selected_identity_field", "selected_source_id_field", "selected_raw_sha256",
    "canonical_ordered_frame_sha256", "source_repository", "source_revision", "source_path",
    "source_prompt_field", "upstream_source_id_field", "upstream_raw_sha256",
    "source_row_count", "selection_filter", "eligible_count", "category_quotas", "license",
    "selection_manifest_relative_path", "category_registry_relative_path",
    "license_notice_relative_path", "license_notice_raw_sha256",
)
P1_HARMFUL_ACTIVE_ENTRY_PATH = "configs/stage3/p1_harmful_do_not_answer_v1.json"
P1_HARMFUL_PACKAGE_PATHS = {
    "relative_path": "data/stage3/p1_harmful_do_not_answer_v1/selected_p1_harmful_100.json",
    "selection_manifest_relative_path": (
        "data/stage3/p1_harmful_do_not_answer_v1/p1_harmful_selection_manifest.json"
    ),
    "category_registry_relative_path": (
        "data/stage3/p1_harmful_do_not_answer_v1/category_registry.json"
    ),
    "license_notice_relative_path": (
        "data/stage3/p1_harmful_do_not_answer_v1/data_license_notice.md"
    ),
}
P1_HARMFUL_LICENSE_NOTICE_RAW_SHA256 = (
    "cf90c23995486ac9bdb26b6145bec0fee906201bb85ddf4fe06c988a52f98c23"
)


def _exact_fields(value: Any, expected: Sequence[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or list(value) != list(expected):
        raise AssetError(f"{label} exact ordered fields mismatch")
    return value


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AssetError(f"{field} must be a nonempty string")
    return value


def _same_package_path(selected: PurePosixPath, other: PurePosixPath, field: str) -> None:
    if selected.parent != other.parent:
        raise AssetError(f"{field} must name the selected asset's provenance package")


def _validate_historical_self_hash(document: Mapping[str, Any], label: str) -> str:
    recorded = _sha(document.get("self_sha256"), f"{label}.self_sha256")
    expected = canonical_sha256({key: value for key, value in document.items() if key != "self_sha256"})
    if recorded != expected:
        raise AssetError(f"{label} historical self SHA256 mismatch")
    return recorded


def load_p1_harmful_active_entry(
    asset_root: Path,
    active_entry_relative_path: str,
) -> dict[str, Any]:
    """Validate the active entry, selected frame, and historical provenance together."""
    root = resolve_asset_root(asset_root)
    with offline_execution_guard():
        active_entry_rel = _relative_path(active_entry_relative_path, "active_entry_relative_path")
        if active_entry_rel.as_posix() != P1_HARMFUL_ACTIVE_ENTRY_PATH:
            raise AssetError("P1 harmful loader requires the current design's sole active entry")
        entry_path = _resolve_regular_file(root, active_entry_rel.as_posix(), "active_entry_relative_path")
        entry_raw, entry_value = _read_strict_json(entry_path)
        entry = _exact_fields(entry_value, ACTIVE_ENTRY_FIELDS, "active dataset entry")
        if entry["schema_version"] != "paper1-stage3-active-dataset-entry-v1":
            raise AssetError("active entry schema_version mismatch")
        if entry["role"] != "D_norm_confirm.harmful" or entry["status"] != "design_selected":
            raise AssetError("active entry role/status mismatch")

        selected_rel = _relative_path(entry["relative_path"], "relative_path")
        manifest_rel = _relative_path(
            entry["selection_manifest_relative_path"], "selection_manifest_relative_path"
        )
        category_rel = _relative_path(
            entry["category_registry_relative_path"], "category_registry_relative_path"
        )
        license_rel = _relative_path(
            entry["license_notice_relative_path"], "license_notice_relative_path"
        )
        actual_paths = {
            "relative_path": selected_rel.as_posix(),
            "selection_manifest_relative_path": manifest_rel.as_posix(),
            "category_registry_relative_path": category_rel.as_posix(),
            "license_notice_relative_path": license_rel.as_posix(),
        }
        if actual_paths != P1_HARMFUL_PACKAGE_PATHS or len(set(actual_paths.values())) != 4:
            raise AssetError("active entry provenance paths are not the canonical distinct package paths")
        for other, field in (
            (manifest_rel, "selection_manifest_relative_path"),
            (category_rel, "category_registry_relative_path"),
            (license_rel, "license_notice_relative_path"),
        ):
            _same_package_path(selected_rel, other, field)

        selected_path = _resolve_regular_file(root, selected_rel.as_posix())
        manifest_path = _resolve_regular_file(root, manifest_rel.as_posix())
        category_path = _resolve_regular_file(root, category_rel.as_posix())
        license_path = _resolve_regular_file(root, license_rel.as_posix())
        selected_raw, selected_value = _read_strict_json(selected_path)
        _, manifest_value = _read_strict_json(manifest_path)
        _, category_value = _read_strict_json(category_path)
        license_raw = license_path.read_bytes()
        try:
            license_text = license_raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AssetError("license notice is not strict UTF-8") from exc

        selected = _exact_fields(
            selected_value, entry["selected_top_level_ordered_fields"], "selected JSON"
        )
        manifest = manifest_value
        category = category_value
        if not isinstance(manifest, Mapping) or not isinstance(category, Mapping):
            raise AssetError("historical provenance documents must be JSON objects")
        if (
            selected.get("artifact_type") != "candidate_prompt_frame"
            or selected.get("candidate_only") is not True
            or selected.get("formal_input") is not False
            or category.get("candidate_only") is not True
        ):
            raise AssetError("historical candidate boundary differs from the audited package")
        selected_self_sha256 = _validate_historical_self_hash(selected, "selected JSON")
        manifest_self_sha256 = _validate_historical_self_hash(manifest, "selection manifest")
        category_self_sha256 = _validate_historical_self_hash(category, "category registry")
        if manifest.get("self_hash_rule") != "SHA256(canonical JSON after removing top-level self_sha256)":
            raise AssetError("selection manifest historical self-hash rule differs")
        _nonnegative_int(entry["raw_byte_length"], "raw_byte_length")
        _nonnegative_int(entry["row_count"], "row_count")
        _sha(entry["selected_raw_sha256"], "selected_raw_sha256")
        _sha(entry["canonical_ordered_frame_sha256"], "canonical_ordered_frame_sha256")
        _sha(entry["upstream_raw_sha256"], "upstream_raw_sha256")
        _sha(entry["license_notice_raw_sha256"], "license_notice_raw_sha256")
        if (
            entry["license_notice_raw_sha256"] != P1_HARMFUL_LICENSE_NOTICE_RAW_SHA256
            or _sha256_bytes(license_raw) != entry["license_notice_raw_sha256"]
        ):
            raise AssetError("license notice raw SHA256 differs from the canonical active package")
        if len(selected_raw) != entry["raw_byte_length"]:
            raise AssetError("active entry raw_byte_length differs from selected JSON")
        if _sha256_bytes(selected_raw) != entry["selected_raw_sha256"]:
            raise AssetError("active entry selected_raw_sha256 differs from selected JSON")
        if not isinstance(selected.get("records"), list):
            raise AssetError("selected JSON records must be an array")
        records = selected["records"]
        if len(records) != entry["row_count"] or selected.get("record_count") != entry["row_count"]:
            raise AssetError("active entry row_count differs from selected JSON")
        ordered_record_fields = entry["selected_record_ordered_fields"]
        if not isinstance(ordered_record_fields, list) or not ordered_record_fields:
            raise AssetError("selected_record_ordered_fields must be a nonempty array")
        for index, record in enumerate(records):
            if not isinstance(record, Mapping) or list(record) != ordered_record_fields:
                raise AssetError(f"selected record {index} ordered fields mismatch")
            expected_types = {
                "frame_position": "integer",
                "question": "string",
                "question_sha256": "string",
                "record_identity_sha256": "string",
                "risk_area": "string",
                "selection_disposition": "string",
                "selection_rank_sha256": "string",
                "source_id": "integer",
                "specific_harms": "string",
                "types_of_harm": "string",
            }
            if any(not _field_type_matches(record.get(field), expected) for field, expected in expected_types.items()):
                raise AssetError(f"selected record {index} field type mismatch")
            replacement = record.get("replacement_for_source_id")
            if replacement is not None and not _field_type_matches(replacement, "integer"):
                raise AssetError(f"selected record {index} replacement source-ID type mismatch")
            if record["frame_position"] != index + 1:
                raise AssetError("selected frame positions must be contiguous one-based order")
            _sha(record["question_sha256"], f"records[{index}].question_sha256")
            _sha(record["selection_rank_sha256"], f"records[{index}].selection_rank_sha256")
            if _sha256_bytes(record["question"].encode("utf-8")) != record["question_sha256"]:
                raise AssetError(f"selected record {index} question SHA256 mismatch")
        if entry["selected_identity_field"] != "record_identity_sha256":
            raise AssetError("selected_identity_field semantic mismatch")
        if entry["selected_source_id_field"] != "source_id":
            raise AssetError("selected_source_id_field semantic mismatch")
        if entry["upstream_source_id_field"] != "id":
            raise AssetError("upstream_source_id_field semantic mismatch")
        identities = [record[entry["selected_identity_field"]] for record in records]
        source_ids = [record[entry["selected_source_id_field"]] for record in records]
        ranks = [record["selection_rank_sha256"] for record in records]
        for index, identity in enumerate(identities):
            _sha(identity, f"records[{index}].record_identity_sha256")
        if len(identities) != len(set(identities)):
            raise AssetError("selected JSON contains duplicate record identities")
        if len(source_ids) != len(set(source_ids)):
            raise AssetError("selected JSON contains duplicate source IDs")
        if len(ranks) != len(set(ranks)):
            raise AssetError("selected JSON contains duplicate selection ranks")
        frame_sha256 = canonical_sha256(identities)
        source_ids_sha256 = canonical_sha256(source_ids)
        ranks_sha256 = canonical_sha256(ranks)
        if frame_sha256 != entry["canonical_ordered_frame_sha256"] or selected.get("frame_sha256") != frame_sha256:
            raise AssetError("canonical ordered identity frame mismatch")
        if selected.get("frame_source_ids_sha256") != source_ids_sha256:
            raise AssetError("selected source-ID frame mismatch")
        if selected.get("frame_selection_ranks_sha256") != ranks_sha256:
            raise AssetError("selected selection-rank frame mismatch")

        source_identity = manifest.get("source_identity")
        pool = manifest.get("pool_and_selection")
        license_identity = manifest.get("license_identity")
        if not all(isinstance(value, Mapping) for value in (source_identity, pool, license_identity)):
            raise AssetError("selection manifest source/pool/license provenance is incomplete")
        if (
            manifest.get("schema") != "paper1.stage3.p1_harmful_selection.manifest.v1"
            or manifest.get("artifact_type") != "nonformal_candidate_binding_manifest"
            or category.get("schema") != "paper1.stage3.p1_harmful_selection.category_registry.v1"
        ):
            raise AssetError("historical provenance schema identity differs")
        expected_source = {
            "source_repository": source_identity.get("repository_id"),
            "source_revision": source_identity.get("revision"),
            "source_path": source_identity.get("source_path"),
            "source_prompt_field": source_identity.get("prompt_field"),
            "upstream_source_id_field": source_identity.get("source_id_field"),
            "upstream_raw_sha256": source_identity.get("raw_sha256"),
            "source_row_count": pool.get("source_rows"),
            "eligible_count": pool.get("eligible_count"),
            "category_quotas": pool.get("quotas"),
            "license": license_identity.get("spdx_like_id"),
        }
        for field, expected in expected_source.items():
            if entry[field] != expected:
                raise AssetError(f"active entry differs from selection manifest: {field}")
        active_quotas = entry["category_quotas"]
        if not isinstance(active_quotas, Mapping) or any(
            not isinstance(category_id, str)
            or not category_id
            or isinstance(quota, bool)
            or not isinstance(quota, int)
            or quota < 0
            for category_id, quota in active_quotas.items()
        ):
            raise AssetError("active entry category_quotas are invalid")
        if (
            pool.get("final_count") != entry["row_count"]
            or pool.get("provisional_count") != entry["row_count"]
            or sum(active_quotas.values()) != entry["row_count"]
        ):
            raise AssetError("historical selection counts differ from the active frame")
        selection_filter = entry["selection_filter"]
        if not isinstance(selection_filter, Mapping) or list(selection_filter) != ["field", "operator", "value"]:
            raise AssetError("active entry selection_filter fields mismatch")
        if selection_filter != category.get("risk_area_filter"):
            raise AssetError("active entry selection filter differs from category registry")
        if selection_filter != {
            "field": manifest.get("taxonomy", {}).get("top_level_filter_field"),
            "operator": "strict_string_equality",
            "value": manifest.get("taxonomy", {}).get("top_level_filter_value"),
        }:
            raise AssetError("selection filter differs from selection manifest")
        categories = category.get("categories")
        if not isinstance(categories, list):
            raise AssetError("category registry categories are missing")
        registry_quotas: dict[str, int] = {}
        eligible_by_category = 0
        for item in categories:
            if not isinstance(item, Mapping):
                raise AssetError("category registry contains a non-object category")
            category_id = _require_text(item.get("category_id"), "category_id")
            if category_id in registry_quotas:
                raise AssetError("category registry contains a duplicate category")
            quota = _nonnegative_int(item.get("quota"), f"quota[{category_id}]")
            eligible = _nonnegative_int(item.get("eligible_count"), f"eligible_count[{category_id}]")
            final_selected = _nonnegative_int(
                item.get("final_selected_count"), f"final_selected_count[{category_id}]"
            )
            if final_selected != quota or item.get("taxonomy_field") != "types_of_harm":
                raise AssetError("category registry selected count or taxonomy field differs")
            registry_quotas[category_id] = quota
            eligible_by_category += eligible
        if (
            entry["category_quotas"] != registry_quotas
            or category.get("eligible_total") != entry["eligible_count"]
            or category.get("target_total") != entry["row_count"]
            or eligible_by_category != entry["eligible_count"]
        ):
            raise AssetError("active entry quotas/counts differ from category registry")
        selected_quotas: dict[str, int] = {}
        for record in records:
            if record["risk_area"] != selection_filter["value"]:
                raise AssetError("selected record is outside the active strict filter")
            category_id = record["types_of_harm"]
            selected_quotas[category_id] = selected_quotas.get(category_id, 0) + 1
        if selected_quotas != entry["category_quotas"]:
            raise AssetError("selected record category counts differ from active quotas")
        if manifest.get("pool_and_selection", {}).get("frame_sha256") != frame_sha256:
            raise AssetError("selection manifest frame differs from selected JSON")
        if manifest.get("pool_and_selection", {}).get("frame_source_ids_sha256") != source_ids_sha256:
            raise AssetError("selection manifest source-ID frame differs from selected JSON")
        if manifest.get("pool_and_selection", {}).get("frame_selection_ranks_sha256") != ranks_sha256:
            raise AssetError("selection manifest rank frame differs from selected JSON")
        expected_files = manifest.get("expected_package_files")
        if not isinstance(expected_files, list) or any(
            path.name not in expected_files for path in (selected_rel, manifest_rel, category_rel, license_rel)
        ):
            raise AssetError("active entry provenance paths differ from historical package inventory")
        core_hashes = manifest.get("core_artifact_self_hashes")
        if not isinstance(core_hashes, Mapping) or core_hashes.get(selected_rel.name) != selected_self_sha256:
            raise AssetError("selection manifest does not identify the selected JSON")
        if core_hashes.get(category_rel.name) != category_self_sha256:
            raise AssetError("selection manifest does not identify the category registry")
        for token in (
            entry["source_repository"], entry["source_revision"], entry["source_path"], entry["license"]
        ):
            if token not in license_text:
                raise AssetError("license notice differs from active provenance")

        return {
            "schema_version": "paper1-stage3-active-dataset-load-v1",
            "active_entry_relative_path": active_entry_rel.as_posix(),
            "active_entry_raw_sha256": _sha256_bytes(entry_raw),
            "role": entry["role"],
            "status": entry["status"],
            "selected_relative_path": selected_rel.as_posix(),
            "selected_raw_sha256": _sha256_bytes(selected_raw),
            "row_count": len(records),
            "ordered_record_identities": identities,
            "ordered_source_ids": source_ids,
            "canonical_ordered_frame_sha256": frame_sha256,
            "source_repository": entry["source_repository"],
            "source_revision": entry["source_revision"],
            "source_path": entry["source_path"],
            "license": entry["license"],
            "selection_manifest_self_sha256": manifest_self_sha256,
            "license_notice_raw_sha256": _sha256_bytes(license_raw),
            "records": records,
        }


def build_offline_asset_inventory(
    asset_root: Path,
    specs: Sequence[JsonInputSpec],
) -> dict[str, Any]:
    loader = OfflineJsonLoader(asset_root, specs)
    assets = loader.inventory()
    return {
        "schema_version": "paper1-stage3-offline-asset-inventory-v1",
        "asset_root": str(loader.root),
        "asset_count": len(assets),
        "assets": assets,
        "fallbacks_allowed": False,
        "network_retrieval_allowed": False,
        "hf_cache_fallback_allowed": False,
    }
