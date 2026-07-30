"""Fail-closed validation for Stage 3 server and prompt binding inputs."""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .core import PipelineError, canonical_sha256, file_sha256


class BindingError(PipelineError):
    """A candidate or formal binding is missing, mutable, or inconsistent."""


P1_PACKAGE_RELATIVE = "data/stage3/p1_harmful_do_not_answer_v1"
P1_SOURCE = {
    "repository_id": "Libr-AI/do-not-answer",
    "revision": "460703484df354958a5e1cd7378a38fcb94a2f3e",
    "source_path": "datasets/Instruction/do_not_answer_en.csv",
    "raw_sha256": "06acfa39a06a1b33d1f264ce41b4f7a95812010c594fb733ae4717ee0a4544fc",
    "license": "CC-BY-NC-SA-4.0",
}
P1_SELECTED_RAW_SHA256 = "700c2c391c86273fca01ec9823feb66a3b1927ac39cc81d1de7567c71bebfd36"
P1_SELECTED_SELF_SHA256 = "c8cba8dc68b2087044950da681595e942ba4421c9b3479e751687ed5f0470d14"
P1_FRAME_SHA256 = "afcb3bcfe3042bf37189fc9718b53389ce0145e43b75efc3364e250e86552410"
P1_SOURCE_IDS_SHA256 = "0dd5f4a26b0be66eaf70de687c2ef795f5586f21d2571e3feb13338d29b3e6ac"
P1_SELECTION_RANKS_SHA256 = "d7abd63915c975e4f427e4647b928c199410eed56fda3480d336e4270644fb64"
P1_PACKAGE_SHA256 = {
    "auditor_a.json": "4abe5481a83e0f1a173494a3de161412c8056385f7b11e27c9fe7360f7bf787a",
    "auditor_b.json": "d522c655d8a4e9bb9eeb7d2e5b23cfa8e7c8c8bf398dd86eb3433d696caf39f4",
    "auditor_c.json": "9a98e71c86f3d837285f5b9b01bef24f7ae1bbab3cb176a0581a9523eb84e034",
    "category_registry.json": "cbc3368ad6eecd53dd48b87a48cdcee9d1e6a8bb2daba9789fcc21d2fa2209b9",
    "checksums.sha256": "4cf7e50143bde8fd71981397a6b3dd9cdd093b5fa41f50331b8fde7a7ddd9e78",
    "data_license_notice.md": "cf90c23995486ac9bdb26b6145bec0fee906201bb85ddf4fe06c988a52f98c23",
    "duplicate_leakage_review.json": "1bb5937dde7ceb131fde87c3043d5ef554cde62a7f2ff2339b43787c54f6a98f",
    "integration_receipt.json": "9fec4a67e60338e4af86907f8091f7fc99e5d52838e5e69f4009e3ee53cedffe",
    "p1_harmful_selection_manifest.json": "6382a2c331daa338a411bf1d63b348a9968b27d9375641bd90d4b307e89f4d66",
    "selected_p1_harmful_100.json": P1_SELECTED_RAW_SHA256,
    "selection_report.md": "972b3bb9af92288ab1c6b4dcdd884e7631a09b151821171977bdeee60e99ff47",
    "selection_trace.json": "16ada84309937858502b33b3577bee8197b1be8d39e0f7ea10db7d83a2205eaf",
}

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MUTABLE_REVISIONS = {
    "head", "main", "master", "latest", "current", "stable", "nightly", "dev", "develop",
}
MODEL_FILE_ROLES = {
    "config", "weights", "tokenizer_config", "special_tokens_map", "tokenizer_asset"
}
PROMPT_SPLIT_SIZES = {
    "p1_harmful": 100,
    "p1_benign": 100,
    "behavior_screen": 30,
    "behavior_confirm": 50,
    "benign_confirm": 30,
}
PROMPT_SPLIT_DOMAINS = {
    "p1_harmful": "harmful",
    "p1_benign": "benign",
    "behavior_screen": "harmful",
    "behavior_confirm": "harmful",
    "benign_confirm": "benign",
}
PROMPT_SPLIT_ROLES = {
    "p1_harmful": "D_norm_confirm",
    "p1_benign": "D_norm_confirm",
    "behavior_screen": "D_behavior_screen",
    "behavior_confirm": "D_behavior_confirm",
    "benign_confirm": "D_benign_confirm",
}


def _reject_constant(value: str) -> None:
    raise BindingError(f"nonfinite JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BindingError(f"duplicate JSON object key is forbidden: {key}")
        result[key] = value
    return result


def _strict_load(path: Path) -> Any:
    try:
        text = path.read_bytes().decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BindingError(f"invalid strict JSON: {path.name}") from exc


def _exact(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BindingError(f"{label} must be an object")
    actual = set(value)
    if actual != keys:
        raise BindingError(
            f"{label} fields differ: missing={sorted(keys-actual)}, extra={sorted(actual-keys)}"
        )
    return value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise BindingError(f"{label} must be a lowercase SHA256")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BindingError(f"{label} must be a nonempty string")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise BindingError(f"{label} must be a nonnegative integer")
    return value


def _self_hash(document: Mapping[str, Any], label: str) -> str:
    expected = _hash(document.get("self_sha256"), f"{label}.self_sha256")
    actual = canonical_sha256({key: value for key, value in document.items() if key != "self_sha256"})
    if expected != actual:
        raise BindingError(f"{label} self hash mismatch")
    return expected


def _binding_header(
    document: Mapping[str, Any], *, keys: set[str], schema: str, kind: str
) -> bool:
    _exact(document, keys, kind)
    if (
        document["schema_version"] != schema
        or document["protocol_version"] != "v3.5-rc2"
        or document["artifact_kind"] != kind
    ):
        raise BindingError(f"{kind} schema identity differs")
    if not isinstance(document["synthetic_fixture"], bool):
        raise BindingError(f"{kind}.synthetic_fixture must be boolean")
    if document["formal_experiment_run"] is not False:
        raise BindingError(f"{kind} must not claim a formal experiment run")
    _nonempty(document["created_at_utc"], f"{kind}.created_at_utc")
    _self_hash(document, kind)
    return bool(document["synthetic_fixture"])


def _safe_file(root: Path, relative: str, label: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise BindingError(f"{label} is not a safe relative path")
    candidate = root.resolve()
    for part in posix.parts:
        candidate = candidate / part
        if candidate.is_symlink() or (
            callable(getattr(candidate, "is_junction", None)) and candidate.is_junction()
        ):
            raise BindingError(f"{label} contains a link component")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BindingError(f"{label} escapes binding root") from exc
    if not resolved.is_file():
        raise BindingError(f"{label} is missing")
    return resolved


def _safe_directory(root: Path, relative: str, label: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise BindingError(f"{label} is not a safe relative path")
    candidate = root.resolve()
    for part in posix.parts:
        candidate = candidate / part
        if candidate.is_symlink() or (
            callable(getattr(candidate, "is_junction", None)) and candidate.is_junction()
        ):
            raise BindingError(f"{label} contains a link component")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BindingError(f"{label} escapes binding root") from exc
    if not resolved.is_dir():
        raise BindingError(f"{label} is missing")
    return resolved


def validate_p1_harmful_candidate(root: Path) -> dict[str, Any]:
    """Validate the approved package without promoting it to formal input."""
    package = (root.resolve() / P1_PACKAGE_RELATIVE).resolve()
    if not package.is_dir() or package.is_symlink():
        raise BindingError("P1 harmful candidate package is missing or linked")
    files = {path.name: path for path in package.iterdir() if path.is_file() and not path.is_symlink()}
    if set(files) != set(P1_PACKAGE_SHA256):
        raise BindingError("P1 harmful package file set differs")
    for name, expected in P1_PACKAGE_SHA256.items():
        if file_sha256(files[name]) != expected:
            raise BindingError(f"P1 harmful package raw hash mismatch: {name}")

    expected_lines = [
        f"{P1_PACKAGE_SHA256[name]}  {name}"
        for name in sorted(P1_PACKAGE_SHA256)
        if name != "checksums.sha256"
    ]
    actual_lines = files["checksums.sha256"].read_text(encoding="ascii").splitlines()
    if actual_lines != expected_lines:
        raise BindingError("P1 harmful checksums.sha256 differs")

    json_documents: dict[str, Mapping[str, Any]] = {}
    for name in sorted(files):
        if name.endswith(".json"):
            document = _strict_load(files[name])
            if not isinstance(document, Mapping):
                raise BindingError(f"P1 harmful JSON is not an object: {name}")
            _self_hash(document, name)
            json_documents[name] = document

    selected = _exact(
        json_documents["selected_p1_harmful_100.json"],
        {
            "artifact_type", "candidate_only", "formal_input", "frame_order_rule",
            "frame_selection_ranks_sha256", "frame_sha256", "frame_source_ids_sha256",
            "record_count", "records", "schema", "selection_namespace", "self_sha256",
        },
        "selected P1 harmful document",
    )
    if (
        selected["schema"] != "paper1.stage3.p1_harmful_selection.selected.v1"
        or selected["artifact_type"] != "candidate_prompt_frame"
        or selected["candidate_only"] is not True
        or selected["formal_input"] is not False
        or selected["selection_namespace"] != "paper1-stage3-p1-harmful-selection-v1"
        or selected["frame_order_rule"]
        != ["selection_rank_sha256_ascending", "source_id_numeric_ascending"]
        or selected["record_count"] != 100
        or selected["self_sha256"] != P1_SELECTED_SELF_SHA256
    ):
        raise BindingError("selected P1 harmful boundary/schema differs")
    records = selected["records"]
    if not isinstance(records, list) or len(records) != 100:
        raise BindingError("selected P1 harmful records must contain exactly 100 rows")
    row_keys = {
        "frame_position", "question", "question_sha256", "record_identity_sha256",
        "replacement_for_source_id", "risk_area", "selection_disposition",
        "selection_rank_sha256", "source_id", "specific_harms", "types_of_harm",
    }
    source_ids: list[int] = []
    question_hashes: list[str] = []
    record_hashes: list[str] = []
    rank_hashes: list[str] = []
    categories: list[str] = []
    for index, row_value in enumerate(records, 1):
        row = _exact(row_value, row_keys, f"selected P1 harmful row {index}")
        if row["frame_position"] != index:
            raise BindingError("selected P1 harmful frame positions are not contiguous")
        source_id = row["source_id"]
        if not isinstance(source_id, int) or isinstance(source_id, bool):
            raise BindingError("selected P1 harmful source_id must be integer")
        question = _nonempty(row["question"], "selected P1 harmful question")
        question_sha = hashlib.sha256(question.encode("utf-8")).hexdigest()
        if row["question_sha256"] != question_sha:
            raise BindingError("selected P1 harmful question hash mismatch")
        identity_payload = {
            "source_commit": P1_SOURCE["revision"],
            "source_path": P1_SOURCE["source_path"],
            "source_id": source_id,
            "question_sha256": question_sha,
        }
        record_sha = canonical_sha256(identity_payload)
        if row["record_identity_sha256"] != record_sha:
            raise BindingError("selected P1 harmful record identity mismatch")
        rank_sha = canonical_sha256({
            "namespace": "paper1-stage3-p1-harmful-selection-v1",
            "record_identity_sha256": record_sha,
        })
        if row["selection_rank_sha256"] != rank_sha:
            raise BindingError("selected P1 harmful selection rank mismatch")
        if row["risk_area"] != "Malicious Uses":
            raise BindingError("selected P1 harmful risk-area provenance differs")
        if row["selection_disposition"] not in {
            "provisional_selected", "same_stratum_rank_replacement"
        }:
            raise BindingError("selected P1 harmful selection disposition differs")
        if row["replacement_for_source_id"] is not None and (
            not isinstance(row["replacement_for_source_id"], int)
            or isinstance(row["replacement_for_source_id"], bool)
        ):
            raise BindingError("selected P1 harmful replacement source ID differs")
        categories.append(_nonempty(row["types_of_harm"], "types_of_harm"))
        _nonempty(row["specific_harms"], "specific_harms")
        source_ids.append(source_id)
        question_hashes.append(question_sha)
        record_hashes.append(record_sha)
        rank_hashes.append(rank_sha)
    for values, label in (
        (source_ids, "source IDs"), (question_hashes, "question hashes"),
        (record_hashes, "record identities"), (rank_hashes, "selection ranks"),
    ):
        if len(set(values)) != 100:
            raise BindingError(f"selected P1 harmful {label} are not unique")
    if list(zip(rank_hashes, source_ids)) != sorted(zip(rank_hashes, source_ids)):
        raise BindingError("selected P1 harmful frame order differs")
    if (
        canonical_sha256(record_hashes) != P1_FRAME_SHA256
        or canonical_sha256(source_ids) != P1_SOURCE_IDS_SHA256
        or canonical_sha256(rank_hashes) != P1_SELECTION_RANKS_SHA256
        or selected["frame_sha256"] != P1_FRAME_SHA256
        or selected["frame_source_ids_sha256"] != P1_SOURCE_IDS_SHA256
        or selected["frame_selection_ranks_sha256"] != P1_SELECTION_RANKS_SHA256
    ):
        raise BindingError("selected P1 harmful frame hash differs")

    manifest = json_documents["p1_harmful_selection_manifest.json"]
    source = manifest.get("source_identity")
    license_identity = manifest.get("license_identity")
    pool = manifest.get("pool_and_selection")
    boundary = manifest.get("boundary")
    if not all(isinstance(item, Mapping) for item in (source, license_identity, pool, boundary)):
        raise BindingError("P1 harmful manifest provenance sections are missing")
    if any(source.get(key) != value for key, value in (
        ("repository_id", P1_SOURCE["repository_id"]),
        ("revision", P1_SOURCE["revision"]),
        ("source_path", P1_SOURCE["source_path"]),
        ("raw_sha256", P1_SOURCE["raw_sha256"]),
    )):
        raise BindingError("P1 harmful source provenance differs")
    if (
        license_identity.get("spdx_like_id") != P1_SOURCE["license"]
        or pool.get("final_count") != 100
        or pool.get("frame_sha256") != P1_FRAME_SHA256
        or boundary.get("candidate_only") is not True
        or boundary.get("formal_inputs") != []
        or boundary.get("formal_input_claim") is not False
        or boundary.get("formal_experiment_run") is not False
        or boundary.get("run_ready_claim") is not False
    ):
        raise BindingError("P1 harmful manifest boundary/license/frame differs")
    registry = json_documents["category_registry.json"]
    registry_categories = registry.get("categories")
    if not isinstance(registry_categories, list):
        raise BindingError("P1 harmful category registry is missing")
    expected_counts = {
        item.get("category_id"): item.get("final_selected_count")
        for item in registry_categories if isinstance(item, Mapping)
    }
    actual_counts = {category: categories.count(category) for category in set(categories)}
    if expected_counts != actual_counts or sum(actual_counts.values()) != 100:
        raise BindingError("P1 harmful category registry counts differ")
    notice = files["data_license_notice.md"].read_text(encoding="utf-8")
    if not all(token in notice for token in (
        "CC-BY-NC-SA-4.0", "Attribution", "NonCommercial", "ShareAlike"
    )):
        raise BindingError("P1 harmful license boundaries are incomplete")
    return {
        "schema_version": "paper1-stage3-p1-harmful-candidate-validation-v1",
        "disposition": "CANDIDATE_BINDING_INPUT",
        "relative_path": P1_PACKAGE_RELATIVE,
        "package_file_count": 12,
        "record_count": 100,
        "raw_sha256": P1_SELECTED_RAW_SHA256,
        "self_sha256": P1_SELECTED_SELF_SHA256,
        "frame_sha256": P1_FRAME_SHA256,
        "source_ids_sha256": P1_SOURCE_IDS_SHA256,
        "selection_ranks_sha256": P1_SELECTION_RANKS_SHA256,
        "ordered_record_identities": record_hashes,
        "source_identity": dict(P1_SOURCE),
        "formal_input": False,
        "formal_experiment_run": False,
    }


ATTESTATION_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic_fixture",
    "formal_experiment_run", "source_channel", "repository_id", "revision",
    "revision_evidence", "files", "file_count", "file_inventory_complete",
    "snapshot_manifest",
    "tokenizer", "chat_template", "config",
    "runtime_identity_sha256", "created_at_utc", "self_sha256",
}


def _validate_revision(channel: Any, revision: Any, evidence: Any) -> None:
    channel = _nonempty(channel, "source_channel")
    revision = _nonempty(revision, "revision")
    lowered = revision.lower().strip("/")
    segments = {part for part in re.split(r"[:/]", lowered) if part}
    if (
        lowered in MUTABLE_REVISIONS
        or lowered.startswith("refs/heads/")
        or bool(segments & MUTABLE_REVISIONS)
    ):
        raise BindingError("mutable revision is forbidden")
    if channel in {"huggingface", "git"}:
        item = _exact(evidence, {"evidence_type", "commit_sha"}, "git revision evidence")
        if item["evidence_type"] != "git_commit" or COMMIT_RE.fullmatch(str(item["commit_sha"])) is None:
            raise BindingError("git-like source requires immutable 40-hex commit evidence")
        if revision != item["commit_sha"]:
            raise BindingError("revision differs from immutable commit evidence")
    elif channel == "local_snapshot":
        item = _exact(
            evidence, {"evidence_type", "manifest_sha256"}, "local snapshot revision evidence"
        )
        digest = _hash(item["manifest_sha256"], "local snapshot manifest")
        if item["evidence_type"] != "directory_manifest_sha256" or revision != f"sha256:{digest}":
            raise BindingError("local snapshot revision evidence differs")
    elif channel == "object_store":
        item = _exact(
            evidence, {"evidence_type", "version_id", "etag_sha256"},
            "object-store revision evidence",
        )
        version_id = _nonempty(item["version_id"], "object-store version ID")
        _hash(item["etag_sha256"], "object-store etag SHA256")
        if item["evidence_type"] != "versioned_object" or revision != f"version:{version_id}":
            raise BindingError("object-store revision evidence differs")
    else:
        raise BindingError(f"unsupported source channel: {channel}")


def validate_model_attestation(
    document: Mapping[str, Any], root: Path, *, role: str
) -> dict[str, Any]:
    expected = {
        "behavior": (
            "paper1-stage3-checkpoint-identity-attestation-v1",
            "checkpoint_identity_attestation",
            "Qwen/Qwen2.5-7B-Instruct",
        ),
        "judge": (
            "paper1-stage3-judge-identity-attestation-v1",
            "judge_identity_attestation",
            "Qwen/Qwen3-8B",
        ),
    }
    if role not in expected:
        raise BindingError("unknown model attestation role")
    schema, kind, repository = expected[role]
    synthetic = _binding_header(document, keys=ATTESTATION_KEYS, schema=schema, kind=kind)
    if document["repository_id"] != repository:
        raise BindingError(f"{role} repository identity differs")
    _validate_revision(document["source_channel"], document["revision"], document["revision_evidence"])
    files = document["files"]
    if not isinstance(files, list) or not files:
        raise BindingError(f"{role} attestation must expose hashed files")
    if document["file_inventory_complete"] is not True:
        raise BindingError(f"{role} file inventory must explicitly be complete")
    if document["file_count"] != len(files):
        raise BindingError(f"{role} file count differs from its inventory")
    seen: set[str] = set()
    by_role: dict[str, list[Mapping[str, Any]]] = {}
    for index, value in enumerate(files):
        item = _exact(
            value, {"relative_path", "artifact_role", "bytes", "sha256"},
            f"{role} file {index}",
        )
        path = _nonempty(item["relative_path"], f"{role} file path")
        if PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts or path in seen:
            raise BindingError(f"{role} file paths are unsafe or duplicated")
        seen.add(path)
        _nonnegative_int(item["bytes"], f"{role} file bytes")
        _hash(item["sha256"], f"{role} file SHA256")
        installed = _safe_file(root, path, f"{role} installed file")
        if installed.stat().st_size != item["bytes"] or file_sha256(installed) != item["sha256"]:
            raise BindingError(f"{role} installed file identity differs: {path}")
        artifact_role = _nonempty(item["artifact_role"], f"{role} file artifact role")
        if artifact_role not in MODEL_FILE_ROLES:
            raise BindingError(f"{role} file artifact role is invalid")
        by_role.setdefault(artifact_role, []).append(item)
    if set(by_role) != MODEL_FILE_ROLES or any(
        len(by_role[name]) != 1 for name in MODEL_FILE_ROLES - {"weights", "tokenizer_asset"}
    ):
        raise BindingError(f"{role} file inventory lacks required identity roles")
    snapshot = _exact(
        document["snapshot_manifest"],
        {"relative_path", "snapshot_root", "schema_version", "sha256", "file_count"},
        f"{role} snapshot manifest binding",
    )
    snapshot_path = _safe_file(
        root, _nonempty(snapshot["relative_path"], f"{role} snapshot manifest path"),
        f"{role} snapshot manifest path",
    )
    snapshot_root = _safe_directory(
        root, _nonempty(snapshot["snapshot_root"], f"{role} snapshot root"),
        f"{role} snapshot root",
    )
    if (
        file_sha256(snapshot_path) != snapshot["sha256"]
        or snapshot["file_count"] != len(files)
    ):
        raise BindingError(f"{role} snapshot manifest raw identity/count differs")
    snapshot_document = _strict_load(snapshot_path)
    if (
        not isinstance(snapshot_document, Mapping)
        or set(snapshot_document) != {
            "schema_version", "source_channel", "repository_id", "revision", "files"
        }
        or snapshot_document.get("schema_version") != snapshot["schema_version"]
        or snapshot_document.get("source_channel") != document["source_channel"]
        or snapshot_document.get("repository_id") != document["repository_id"]
        or snapshot_document.get("revision") != document["revision"]
        or snapshot_document.get("files") != files
    ):
        raise BindingError(f"{role} snapshot manifest content differs")
    root_relative = snapshot_root.relative_to(root.resolve())
    scanned: list[str] = []
    for installed in sorted(snapshot_root.rglob("*")):
        if installed.is_symlink() or (
            callable(getattr(installed, "is_junction", None)) and installed.is_junction()
        ):
            raise BindingError(f"{role} snapshot contains a linked member")
        if installed.is_file():
            scanned.append(installed.relative_to(root.resolve()).as_posix())
    if set(scanned) != seen or len(scanned) != len(files):
        raise BindingError(f"{role} snapshot tree differs from the complete file inventory")
    if any(not PurePosixPath(path).is_relative_to(PurePosixPath(root_relative.as_posix())) for path in seen):
        raise BindingError(f"{role} attested file escapes its snapshot root")
    tokenizer = _exact(
        document["tokenizer"],
        {
            "revision", "revision_evidence", "files_sha256",
            "tokenizer_config_sha256", "special_tokens_map_sha256",
        },
        f"{role} tokenizer",
    )
    _validate_revision(document["source_channel"], tokenizer["revision"], tokenizer["revision_evidence"])
    for field in ("files_sha256", "tokenizer_config_sha256", "special_tokens_map_sha256"):
        _hash(tokenizer[field], f"{role} tokenizer {field}")
    tokenizer_files = sorted(
        [dict(item) for name in ("tokenizer_config", "special_tokens_map", "tokenizer_asset")
         for item in by_role[name]],
        key=lambda item: item["relative_path"],
    )
    if tokenizer["files_sha256"] != canonical_sha256(tokenizer_files):
        raise BindingError(f"{role} tokenizer file inventory hash differs")
    if tokenizer["tokenizer_config_sha256"] != by_role["tokenizer_config"][0]["sha256"]:
        raise BindingError(f"{role} tokenizer config hash differs from file inventory")
    if tokenizer["special_tokens_map_sha256"] != by_role["special_tokens_map"][0]["sha256"]:
        raise BindingError(f"{role} special-token hash differs from file inventory")
    template = _exact(document["chat_template"], {"text", "sha256"}, f"{role} chat template")
    template_text = _nonempty(template["text"], f"{role} chat template text")
    if hashlib.sha256(template_text.encode("utf-8")).hexdigest() != template["sha256"]:
        raise BindingError(f"{role} chat template hash mismatch")
    config = _exact(
        document["config"],
        {"relative_path", "sha256", "model_type", "architectures", "hidden_size"},
        f"{role} config",
    )
    _nonempty(config["relative_path"], f"{role} config path")
    _hash(config["sha256"], f"{role} config hash")
    if (
        config["relative_path"] != by_role["config"][0]["relative_path"]
        or config["sha256"] != by_role["config"][0]["sha256"]
    ):
        raise BindingError(f"{role} config identity differs from file inventory")
    _nonempty(config["model_type"], f"{role} model type")
    if not isinstance(config["architectures"], list) or not config["architectures"] or any(
        not isinstance(value, str) or not value for value in config["architectures"]
    ):
        raise BindingError(f"{role} architectures are invalid")
    if not isinstance(config["hidden_size"], int) or isinstance(config["hidden_size"], bool) or config["hidden_size"] <= 0:
        raise BindingError(f"{role} hidden size is invalid")
    if role == "behavior" and config["hidden_size"] != 3584:
        raise BindingError("behavior checkpoint hidden size must be 3584")
    _hash(document["runtime_identity_sha256"], f"{role} runtime identity")
    return {
        "role": role,
        "synthetic_fixture": synthetic,
        "self_sha256": document["self_sha256"],
        "repository_id": repository,
        "hidden_size": config["hidden_size"],
    }


VECTOR_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic_fixture",
    "formal_experiment_run", "checkpoint_attestation_self_sha256", "seed",
    "generator", "hidden_dimension", "row_count", "tensor_file", "pool_sha256",
    "row_ids", "row_sha256", "normalization", "partitions", "created_at_utc", "self_sha256",
}


def validate_vector_manifest(
    document: Mapping[str, Any], root: Path, *, checkpoint_self_sha256: str
) -> dict[str, Any]:
    synthetic = _binding_header(
        document,
        keys=VECTOR_KEYS,
        schema="paper1-stage3-vector-manifest-v1",
        kind="stage3_vector_manifest",
    )
    if document["checkpoint_attestation_self_sha256"] != checkpoint_self_sha256:
        raise BindingError("vector checkpoint parent differs")
    if document["seed"] != 42 or document["hidden_dimension"] != 3584 or document["row_count"] != 30:
        raise BindingError("vector seed/shape contract differs")
    generator = _exact(document["generator"], {"runtime", "api", "device"}, "vector generator")
    if (
        generator["runtime"] != "torch-2.7.1"
        or generator["api"] != "torch.Generator.manual_seed+torch.randn"
        or generator["device"] != "cpu"
    ):
        raise BindingError("vector generator identity differs")
    tensor = _exact(
        document["tensor_file"],
        {"relative_path", "bytes", "sha256", "dtype", "shape", "byte_order", "layout"},
        "vector tensor file",
    )
    if (
        tensor["dtype"] != "float32"
        or tensor["shape"] != [30, 3584]
        or tensor["byte_order"] != "little"
        or tensor["layout"] != "row_major_contiguous"
        or tensor["bytes"] != 30 * 3584 * 4
    ):
        raise BindingError("vector tensor metadata differs")
    path = _safe_file(root, _nonempty(tensor["relative_path"], "vector tensor path"), "vector tensor path")
    raw = path.read_bytes()
    if len(raw) != tensor["bytes"] or file_sha256(path) != tensor["sha256"]:
        raise BindingError("vector tensor raw identity differs")
    if document["pool_sha256"] != tensor["sha256"]:
        raise BindingError("vector pool hash differs from tensor bytes")
    row_ids = document["row_ids"]
    expected_ids = [f"vector_{index:02d}" for index in range(30)]
    row_hashes = document["row_sha256"]
    if row_ids != expected_ids or not isinstance(row_hashes, list) or len(row_hashes) != 30:
        raise BindingError("vector row identities differ")
    row_bytes = 3584 * 4
    for index in range(30):
        chunk = raw[index * row_bytes:(index + 1) * row_bytes]
        if hashlib.sha256(chunk).hexdigest() != row_hashes[index]:
            raise BindingError(f"vector row hash mismatch at {index}")
        norm_sq = 0.0
        nonzero = False
        for (value,) in struct.iter_unpack("<f", chunk):
            if not math.isfinite(value):
                raise BindingError(f"vector row {index} contains a nonfinite value")
            nonzero = nonzero or value != 0.0
            norm_sq += float(value) * float(value)
        if not nonzero:
            raise BindingError(f"vector row {index} is zero")
        if abs(math.sqrt(norm_sq) - 1.0) > 1e-5:
            raise BindingError(f"vector row {index} is not L2-normalized")
    if document["normalization"] != {
        "method": "row_l2", "zero_row_policy": "fail", "nonfinite_policy": "fail", "tolerance": 1e-5
    }:
        raise BindingError("vector normalization contract differs")
    if document["partitions"] != {"screen": list(range(10)), "confirm": list(range(10, 30))}:
        raise BindingError("vector partition differs")
    return {
        "synthetic_fixture": synthetic,
        "self_sha256": document["self_sha256"],
        "pool_sha256": document["pool_sha256"],
        "row_count": 30,
        "hidden_dimension": 3584,
    }


BASE_ANCHOR_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic_fixture",
    "formal_experiment_run", "checkpoint_attestation_self_sha256", "source_paths",
    "source_schema_versions", "source_sha256", "counts", "predates_behavior_screening",
    "units", "strict_order_check", "anchor_order", "rho_by_anchor", "producer_code_sha256",
    "producer_config_sha256", "created_at_utc", "self_sha256",
}


def validate_base_anchor_manifest(
    document: Mapping[str, Any], root: Path, *, checkpoint_self_sha256: str
) -> dict[str, Any]:
    synthetic = _binding_header(
        document,
        keys=BASE_ANCHOR_KEYS,
        schema="paper1-stage3-base-anchor-binding-manifest-v1",
        kind="base_anchor_binding_manifest",
    )
    if document["checkpoint_attestation_self_sha256"] != checkpoint_self_sha256:
        raise BindingError("base-anchor checkpoint parent differs")
    for name in ("source_paths", "source_schema_versions", "source_sha256", "counts"):
        mapping = document[name]
        if not isinstance(mapping, Mapping) or not mapping:
            raise BindingError(f"base-anchor {name} must be a nonempty object")
    keys = set(document["source_paths"])
    if any(set(document[name]) != keys for name in ("source_schema_versions", "source_sha256", "counts")):
        raise BindingError("base-anchor source maps do not have identical keys")
    for key in keys:
        relative = _nonempty(document["source_paths"][key], f"base-anchor source path {key}")
        expected_schema = _nonempty(
            document["source_schema_versions"][key], f"base-anchor source schema {key}"
        )
        expected_hash = _hash(document["source_sha256"][key], f"base-anchor source hash {key}")
        if not isinstance(document["counts"][key], int) or isinstance(document["counts"][key], bool) or document["counts"][key] <= 0:
            raise BindingError(f"base-anchor source count {key} must be positive")
        source_path = _safe_file(root, relative, f"base-anchor source path {key}")
        if file_sha256(source_path) != expected_hash:
            raise BindingError(f"base-anchor source hash differs: {key}")
        source_document = _strict_load(source_path)
        if not isinstance(source_document, Mapping) or source_document.get("schema_version") != expected_schema:
            raise BindingError(f"base-anchor source schema differs: {key}")
        records = source_document.get("records")
        actual_count = len(records) if isinstance(records, list) else 1
        if actual_count != document["counts"][key]:
            raise BindingError(f"base-anchor source count differs: {key}")
    if (
        document["predates_behavior_screening"] is not True
        or document["units"] != "rho=alpha/median_content_norm"
        or document["strict_order_check"] != "0 < rho_A < rho_T < rho_H"
        or document["anchor_order"] != ["A", "T", "H"]
    ):
        raise BindingError("base-anchor provenance/order declaration differs")
    rho_map = document["rho_by_anchor"]
    if not isinstance(rho_map, Mapping) or set(rho_map) != {"A", "T", "H"}:
        raise BindingError("base-anchor rho map differs")
    values: list[float] = []
    for anchor in ("A", "T", "H"):
        exact = _exact(rho_map[anchor], {"decimal", "value", "binary64_hex"}, f"rho_{anchor}")
        number = exact["value"]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(float(number)):
            raise BindingError(f"rho_{anchor} is not finite")
        if exact["binary64_hex"] != float(number).hex():
            raise BindingError(f"rho_{anchor} binary64 identity differs")
        try:
            decimal_value = float(_nonempty(exact["decimal"], f"rho_{anchor} decimal"))
        except ValueError as exc:
            raise BindingError(f"rho_{anchor} decimal is invalid") from exc
        if decimal_value != float(number):
            raise BindingError(f"rho_{anchor} decimal/value differ")
        values.append(float(number))
    if not 0.0 < values[0] < values[1] < values[2]:
        raise BindingError("base-anchor rho values are not strictly ordered")
    _hash(document["producer_code_sha256"], "base-anchor producer code")
    _hash(document["producer_config_sha256"], "base-anchor producer config")
    return {
        "synthetic_fixture": synthetic,
        "self_sha256": document["self_sha256"],
        "rho": dict(rho_map),
    }


PROMPT_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic_fixture",
    "formal_experiment_run", "split_order", "splits", "global_identity_sha256",
    "global_deduplication_evidence", "created_at_utc", "self_sha256",
}
PROMPT_SPLIT_KEYS = {
    "split_id", "domain", "role", "expected_count", "source_repository_id",
    "source_channel", "source_revision", "source_revision_evidence",
    "source_path", "upstream_source_path", "source_schema_version",
    "source_file_sha256", "source_snapshot_manifest_path",
    "source_snapshot_manifest_sha256", "source_snapshot_manifest_schema_version",
    "license", "license_path", "license_sha256",
    "category_registry_path", "category_registry_sha256", "category_registry_schema_version",
    "ordered_identities", "frame_sha256", "deduplication_evidence_path",
    "deduplication_evidence_schema_version", "deduplication_evidence_sha256",
    "leakage_evidence_path", "leakage_evidence_schema_version",
    "leakage_evidence_sha256",
}
PROMPT_IDENTITY_KEYS = {
    "position", "prompt_id", "record_identity_sha256", "source_id",
    "source_row_sha256", "question_sha256", "category_id",
}


def _validate_prompt_source_snapshot(
    split: Mapping[str, Any],
    root: Path,
    *,
    split_id: str,
    source_path: Path,
    synthetic: bool,
) -> None:
    snapshot_relative = _nonempty(
        split["source_snapshot_manifest_path"],
        f"{split_id}.source_snapshot_manifest_path",
    )
    snapshot_hash = _hash(
        split["source_snapshot_manifest_sha256"],
        f"{split_id}.source_snapshot_manifest_sha256",
    )
    snapshot_schema = _nonempty(
        split["source_snapshot_manifest_schema_version"],
        f"{split_id}.source_snapshot_manifest_schema_version",
    )
    snapshot_path = _safe_file(root, snapshot_relative, f"{split_id} source snapshot")
    if file_sha256(snapshot_path) != snapshot_hash:
        raise BindingError(f"prompt source snapshot hash differs: {split_id}")

    if not synthetic and split_id == "p1_harmful":
        if (
            split["source_channel"] not in {"git", "huggingface"}
            or split["source_revision_evidence"] != {
                "evidence_type": "git_commit",
                "commit_sha": P1_SOURCE["revision"],
            }
            or
            snapshot_relative
            != f"{P1_PACKAGE_RELATIVE}/p1_harmful_selection_manifest.json"
            or snapshot_hash != P1_PACKAGE_SHA256["p1_harmful_selection_manifest.json"]
            or snapshot_schema != "paper1.stage3.p1_harmful_selection.manifest.v1"
        ):
            raise BindingError("formal P1 harmful snapshot provenance differs")
        return

    # A remote revision declaration is not an offline proof that revision:path
    # resolves to these bytes. The fixed P1 package is verified above.
    if split["source_channel"] != "local_snapshot":
        raise BindingError(
            f"non-P1 prompt source requires byte-addressed local_snapshot provenance: {split_id}"
        )

    snapshot = _exact(
        _strict_load(snapshot_path),
        {
            "schema_version", "source_repository_id", "source_revision",
            "files", "tree_sha256",
        },
        f"{split_id} source snapshot",
    )
    expected_schema = (
        "paper1-stage3-synthetic-prompt-source-snapshot-v1"
        if synthetic else "paper1-stage3-prompt-source-snapshot-v1"
    )
    files = snapshot["files"]
    if (
        snapshot_schema != expected_schema
        or snapshot["schema_version"] != snapshot_schema
        or snapshot["source_repository_id"] != split["source_repository_id"]
        or snapshot["source_revision"] != split["source_revision"]
        or not isinstance(files, list)
        or len(files) != 1
    ):
        raise BindingError(f"prompt source snapshot identity differs: {split_id}")
    file_entry = _exact(
        files[0], {"upstream_source_path", "bytes", "raw_sha256"},
        f"{split_id} source snapshot file",
    )
    if (
        file_entry["upstream_source_path"] != split["upstream_source_path"]
        or file_entry["bytes"] != source_path.stat().st_size
        or file_entry["raw_sha256"] != split["source_file_sha256"]
        or snapshot["tree_sha256"] != canonical_sha256(files)
    ):
        raise BindingError(f"prompt source snapshot file binding differs: {split_id}")
    if split["source_channel"] == "local_snapshot":
        tree_hash = snapshot["tree_sha256"]
        if (
            split["source_revision"] != f"sha256:{tree_hash}"
            or split["source_revision_evidence"] != {
                "evidence_type": "directory_manifest_sha256",
                "manifest_sha256": tree_hash,
            }
        ):
            raise BindingError(f"prompt local snapshot revision differs: {split_id}")


def validate_prompt_frame_manifest(
    document: Mapping[str, Any], root: Path, *, candidate: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    synthetic = _binding_header(
        document,
        keys=PROMPT_KEYS,
        schema="paper1-stage3-prompt-frame-binding-manifest-v2",
        kind="prompt_frame_binding_manifest",
    )
    expected_order = list(PROMPT_SPLIT_SIZES)
    if document["split_order"] != expected_order:
        raise BindingError("prompt-frame split order differs")
    splits = document["splits"]
    if not isinstance(splits, list) or len(splits) != 5:
        raise BindingError("prompt-frame manifest must contain exactly five splits")
    global_ids: list[str] = []
    split_summary: dict[str, int] = {}
    p1_harmful_ids: list[str] = []
    data_inputs: list[dict[str, Any]] = []
    seen_local_source_paths: set[str] = set()
    for split_index, value in enumerate(splits):
        split = _exact(value, PROMPT_SPLIT_KEYS, f"prompt split {split_index}")
        split_id = expected_order[split_index]
        if (
            split["split_id"] != split_id
            or split["domain"] != PROMPT_SPLIT_DOMAINS[split_id]
            or split["role"] != PROMPT_SPLIT_ROLES[split_id]
            or split["expected_count"] != PROMPT_SPLIT_SIZES[split_id]
        ):
            raise BindingError(f"prompt split contract differs: {split_id}")
        for field in (
            "source_repository_id", "source_revision", "source_path", "upstream_source_path",
            "source_schema_version", "source_snapshot_manifest_path",
            "source_snapshot_manifest_schema_version", "license", "license_path",
            "deduplication_evidence_path",
            "deduplication_evidence_schema_version", "leakage_evidence_path",
            "leakage_evidence_schema_version",
            "category_registry_path", "category_registry_schema_version",
        ):
            _nonempty(split[field], f"{split_id}.{field}")
        for field in (
            "source_file_sha256", "category_registry_sha256",
            "source_snapshot_manifest_sha256", "license_sha256",
            "deduplication_evidence_sha256", "leakage_evidence_sha256",
        ):
            _hash(split[field], f"{split_id}.{field}")
        _validate_revision(
            split["source_channel"], split["source_revision"], split["source_revision_evidence"]
        )
        local_source_path = _nonempty(split["source_path"], f"{split_id}.source_path")
        if local_source_path in seen_local_source_paths:
            raise BindingError(f"prompt source paths must be unique: {local_source_path}")
        seen_local_source_paths.add(local_source_path)
        identities = split["ordered_identities"]
        expected_count = PROMPT_SPLIT_SIZES[split_id]
        if not isinstance(identities, list) or len(identities) != expected_count:
            raise BindingError(f"prompt split count differs: {split_id}")
        source_path = _safe_file(root, local_source_path, f"{split_id} source path")
        if file_sha256(source_path) != split["source_file_sha256"]:
            raise BindingError(f"prompt source file hash differs: {split_id}")
        _validate_prompt_source_snapshot(
            split, root, split_id=split_id, source_path=source_path, synthetic=synthetic
        )
        license_path = _safe_file(root, split["license_path"], f"{split_id} license path")
        if file_sha256(license_path) != split["license_sha256"]:
            raise BindingError(f"prompt license material hash differs: {split_id}")
        category_path = _safe_file(
            root, split["category_registry_path"], f"{split_id} category registry path"
        )
        if file_sha256(category_path) != split["category_registry_sha256"]:
            raise BindingError(f"prompt category registry hash differs: {split_id}")
        category_document = _strict_load(category_path)
        if (
            not isinstance(category_document, Mapping)
            or category_document.get("schema_version") != split["category_registry_schema_version"]
            or not isinstance(category_document.get("categories"), list)
            or any(not isinstance(value, str) or not value for value in category_document["categories"])
        ):
            raise BindingError(f"prompt category registry schema differs: {split_id}")
        category_ids = set(category_document["categories"])
        for evidence_kind in ("deduplication", "leakage"):
            evidence_path = _safe_file(
                root,
                split[f"{evidence_kind}_evidence_path"],
                f"{split_id} {evidence_kind} evidence path",
            )
            if file_sha256(evidence_path) != split[f"{evidence_kind}_evidence_sha256"]:
                raise BindingError(f"prompt {evidence_kind} evidence hash differs: {split_id}")
            evidence_document = _strict_load(evidence_path)
            evidence_schema = split[f"{evidence_kind}_evidence_schema_version"]
            expected_evidence_schema = (
                f"paper1-stage3-synthetic-prompt-{evidence_kind}-evidence-v1"
                if synthetic
                else f"paper1-stage3-prompt-{evidence_kind}-evidence-v1"
            )
            if (
                not isinstance(evidence_document, Mapping)
                or set(evidence_document) != {
                    "schema_version", "status", "split_id", "identity_count", "frame_sha256"
                }
                or evidence_schema != expected_evidence_schema
                or evidence_document.get("schema_version") != evidence_schema
                or evidence_document.get("status") != "COMPLETE"
                or evidence_document.get("split_id") != split_id
                or evidence_document.get("identity_count") != expected_count
                or evidence_document.get("frame_sha256")
                != canonical_sha256([
                    item["record_identity_sha256"] for item in split["ordered_identities"]
                ])
            ):
                raise BindingError(f"prompt {evidence_kind} evidence differs: {split_id}")
        split_ids: list[str] = []
        for position, identity_value in enumerate(identities, 1):
            identity = _exact(identity_value, PROMPT_IDENTITY_KEYS, f"{split_id} row {position}")
            if identity["position"] != position:
                raise BindingError(f"prompt split order differs: {split_id}")
            prompt_id = _nonempty(identity["prompt_id"], f"{split_id} prompt_id")
            record_id = _hash(identity["record_identity_sha256"], f"{split_id} record identity")
            _hash(identity["source_row_sha256"], f"{split_id} source row")
            _hash(identity["question_sha256"], f"{split_id} question")
            _nonempty(identity["category_id"], f"{split_id} category")
            if identity["category_id"] not in category_ids:
                raise BindingError(f"{split_id} category is absent from its registry")
            if not isinstance(identity["source_id"], (str, int)) or isinstance(identity["source_id"], bool):
                raise BindingError(f"{split_id} source ID is invalid")
            if not str(identity["source_id"]):
                raise BindingError(f"{split_id} source ID is empty")
            if prompt_id != f"{split_id}:{record_id}":
                raise BindingError(f"{split_id} prompt ID is not bound to record identity")
            split_ids.append(record_id)
            global_ids.append(record_id)
        if len(set(split_ids)) != expected_count:
            raise BindingError(f"duplicate record identity within split: {split_id}")
        if split["frame_sha256"] != canonical_sha256(split_ids):
            raise BindingError(f"prompt split frame hash differs: {split_id}")
        if split_id == "p1_harmful":
            p1_harmful_ids = split_ids
        source_document = _strict_load(source_path)
        if synthetic or split_id != "p1_harmful":
            source_document = _strict_load(source_path)
            if (
                not isinstance(source_document, Mapping)
                or source_document.get("schema_version") != split["source_schema_version"]
                or not isinstance(source_document.get("records"), list)
                or len(source_document["records"]) != expected_count
            ):
                raise BindingError(f"prompt source schema/count differs: {split_id}")
            for position, (source_row, identity) in enumerate(
                zip(source_document["records"], identities), 1
            ):
                row = _exact(
                    source_row, {"source_id", "question", "category_id"},
                    f"{split_id} source row {position}",
                )
                question = _nonempty(row["question"], f"{split_id} source question {position}")
                question_sha256 = hashlib.sha256(question.encode("utf-8")).hexdigest()
                row_sha = canonical_sha256(row)
                record_sha = canonical_sha256({
                    "source_repository_id": split["source_repository_id"],
                    "source_revision": split["source_revision"],
                    "upstream_source_path": split["upstream_source_path"],
                    "source_id": row["source_id"],
                    "source_row_sha256": row_sha,
                    "question_sha256": question_sha256,
                })
                if (
                    identity["source_id"] != row["source_id"]
                    or identity["question_sha256"] != question_sha256
                    or identity["category_id"] != row["category_id"]
                    or identity["source_row_sha256"] != row_sha
                    or identity["record_identity_sha256"] != record_sha
                ):
                    raise BindingError(f"prompt source row binding differs: {split_id}:{position}")
        if not isinstance(source_document, Mapping):
            raise BindingError(f"prompt source document is not an object: {split_id}")
        schema_field = "schema" if (not synthetic and split_id == "p1_harmful") else "schema_version"
        records = source_document.get("records")
        if (
            source_document.get(schema_field) != split["source_schema_version"]
            or not isinstance(records, list)
            or len(records) != expected_count
        ):
            raise BindingError(f"prompt packable source schema/count differs: {split_id}")
        data_inputs.append({
            "relative_path": split["source_path"],
            "raw_sha256": split["source_file_sha256"],
            "byte_length": source_path.stat().st_size,
            "source_schema_field": schema_field,
            "source_schema_version": split["source_schema_version"],
            "json_top_level_type": "object",
            "records_field": "records",
            "row_count": expected_count,
            "source_row_identity_sha256": canonical_sha256([
                identity["source_row_sha256"] for identity in identities
            ]),
            "ordered_record_identities_sha256": canonical_sha256(split_ids),
            "canonical_frame_sha256": split["frame_sha256"],
            "prompt_frame_membership": f"BOUND:{split_id}",
            "source_repository_id": split["source_repository_id"],
            "source_revision": split["source_revision"],
            "upstream_source_path": split["upstream_source_path"],
            "license": split["license"],
            "license_material": {
                "source_relative_path": split["license_path"],
                "bundle_relative_path": f"LICENSES/{split_id}.license",
                "raw_sha256": split["license_sha256"],
            },
            "disposition": (
                "SYNTHETIC_FIXTURE_INPUT" if synthetic else "FORMAL_INPUT"
            ),
            "formal_input": not synthetic,
        })
        split_summary[split_id] = len(split_ids)
    if len(global_ids) != 310 or len(set(global_ids)) != 310:
        raise BindingError("prompt identities must be 310 and globally unique")
    if document["global_identity_sha256"] != canonical_sha256(global_ids):
        raise BindingError("prompt global identity hash differs")
    evidence = _exact(
        document["global_deduplication_evidence"],
        {
            "method", "exact_overlap_count", "semantic_review_status", "evidence_path",
            "evidence_schema_version", "evidence_sha256",
        },
        "global deduplication evidence",
    )
    if (
        evidence["method"] != "frozen-priority-global-dedup-and-leakage-review"
        or evidence["exact_overlap_count"] != 0
        or evidence["semantic_review_status"] != "COMPLETE"
    ):
        raise BindingError("prompt global deduplication/leakage evidence differs")
    _hash(evidence["evidence_sha256"], "global deduplication evidence")
    global_evidence_path = _safe_file(
        root, evidence["evidence_path"], "global deduplication evidence path"
    )
    if file_sha256(global_evidence_path) != evidence["evidence_sha256"]:
        raise BindingError("global deduplication evidence file hash differs")
    global_document = _strict_load(global_evidence_path)
    expected_global_schema = (
        "paper1-stage3-synthetic-global-dedup-leakage-evidence-v1"
        if synthetic else "paper1-stage3-global-dedup-leakage-evidence-v1"
    )
    if (
        not isinstance(global_document, Mapping)
        or set(global_document) != {
            "schema_version", "status", "identity_count", "exact_overlap_count",
            "global_identity_sha256",
        }
        or evidence["evidence_schema_version"] != expected_global_schema
        or global_document.get("schema_version") != evidence["evidence_schema_version"]
        or global_document.get("status") != "COMPLETE"
        or global_document.get("identity_count") != 310
        or global_document.get("exact_overlap_count") != 0
        or global_document.get("global_identity_sha256") != document["global_identity_sha256"]
    ):
        raise BindingError("global deduplication evidence content differs")
    if synthetic:
        if candidate is not None:
            raise BindingError("synthetic prompt fixture must not claim the real P1 candidate")
    else:
        if candidate is None or p1_harmful_ids != candidate.get("ordered_record_identities"):
            raise BindingError("formal P1 harmful split does not bind the approved candidate frame")
        first_split = splits[0]
        if (
            first_split["source_repository_id"] != P1_SOURCE["repository_id"]
            or first_split["source_revision"] != P1_SOURCE["revision"]
            or first_split["upstream_source_path"] != P1_SOURCE["source_path"]
            or first_split["source_path"]
            != f"{P1_PACKAGE_RELATIVE}/selected_p1_harmful_100.json"
            or first_split["source_file_sha256"] != P1_SELECTED_RAW_SHA256
            or first_split["source_schema_version"]
            != "paper1.stage3.p1_harmful_selection.selected.v1"
            or first_split["license"] != P1_SOURCE["license"]
            or first_split["license_path"]
            != f"{P1_PACKAGE_RELATIVE}/data_license_notice.md"
            or first_split["license_sha256"]
            != P1_PACKAGE_SHA256["data_license_notice.md"]
            or first_split["source_snapshot_manifest_path"]
            != f"{P1_PACKAGE_RELATIVE}/p1_harmful_selection_manifest.json"
            or first_split["source_snapshot_manifest_sha256"]
            != P1_PACKAGE_SHA256["p1_harmful_selection_manifest.json"]
        ):
            raise BindingError("formal P1 harmful split provenance differs from approved candidate")
    return {
        "synthetic_fixture": synthetic,
        "self_sha256": document["self_sha256"],
        "identity_count": 310,
        "split_counts": split_summary,
        "global_identity_sha256": document["global_identity_sha256"],
        "data_inputs": data_inputs,
    }


def validate_binding_set(
    documents: Mapping[str, Mapping[str, Any]], root: Path, *, candidate: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    required = {"checkpoint", "judge", "vectors", "base_anchor", "prompt_frames"}
    if set(documents) != required:
        raise BindingError(
            f"binding document set differs: missing={sorted(required-set(documents))}, "
            f"extra={sorted(set(documents)-required)}"
        )
    checkpoint = validate_model_attestation(documents["checkpoint"], root, role="behavior")
    judge = validate_model_attestation(documents["judge"], root, role="judge")
    vectors = validate_vector_manifest(
        documents["vectors"], root, checkpoint_self_sha256=checkpoint["self_sha256"]
    )
    anchors = validate_base_anchor_manifest(
        documents["base_anchor"], root, checkpoint_self_sha256=checkpoint["self_sha256"]
    )
    prompts = validate_prompt_frame_manifest(documents["prompt_frames"], root, candidate=candidate)
    modes = {
        checkpoint["synthetic_fixture"], judge["synthetic_fixture"],
        vectors["synthetic_fixture"], anchors["synthetic_fixture"], prompts["synthetic_fixture"],
    }
    if len(modes) != 1:
        raise BindingError("binding set mixes synthetic and real inputs")
    synthetic = modes.pop()
    components = {
        "checkpoint": checkpoint["self_sha256"],
        "judge": judge["self_sha256"],
        "vectors": vectors["self_sha256"],
        "base_anchor": anchors["self_sha256"],
        "prompt_frames": prompts["self_sha256"],
    }
    return {
        "schema_version": "paper1-stage3-binding-validation-result-v2",
        "validation_status": "PASS",
        "complete": True,
        "synthetic_fixture": synthetic,
        "formal_input_claim": not synthetic,
        "component_self_sha256": components,
        "binding_set_sha256": canonical_sha256(components),
        "prompt_identity_count": prompts["identity_count"],
        "vector_shape": [vectors["row_count"], vectors["hidden_dimension"]],
        "data_inputs": prompts["data_inputs"],
        "formal_experiment_run": False,
    }
