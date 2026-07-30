#!/usr/bin/env python3
"""Verify local Stage 3 production fidelity and generated synthetic artifacts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import (  # noqa: E402
    AppendOnlyReceipt,
    LogicalIdentityRegistry,
    canonical_sha256,
    file_sha256,
)
from stage3_pipeline.execution import (  # noqa: E402
    BLOCK_BUDGET,
    EVENT_ORDER,
    FreezeLifecycle,
    LIFECYCLE_ARTIFACT_PATHS,
    LIFECYCLE_BOUND_PATHS,
    SUPPORT_ATTEMPT_RECEIPT_PATH,
    assert_budget,
    reconcile_complete_execution,
)
from stage3_pipeline.offline_assets import ALLOWED_DISPOSITIONS  # noqa: E402
from stage3_pipeline.records import (  # noqa: E402
    BENIGN_KEYS,
    GENERATION_KEYS,
    JUDGE_KEYS,
    K1_KEYS,
    P1_KEYS,
    P2_KEYS,
    validate_generation_record,
    validate_judge_record,
    validate_p2_materialization,
)
from stage3_pipeline.references import ReferenceAdapter  # noqa: E402
from stage3_pipeline.local_temp import require_project_local_temp  # noqa: E402


EXPECTED_SOURCE_JSON_SHA256 = {
    "data/jbb_behaviors_harmful.json": "9ee1cb2aab52550f0817f036e4423e9f3cc05a6bb5a0084da404f1817d535e77",
    "data/safe_pairs.json": "822202eeed0231c17427138ced8e34ee7736c30af6937899579697d6b72e4548",
    "data/safe_pairs.example.json": "f595fd4bea108e4173efcfdbd995dc71ec3e84e356e99af589a08885da34dad3",
    "data/single_prompt_bomb.json": "fafce3334180fd493e3f64f957c946470e75965bbdbe0e9ed572b7d95942c7e4",
}
EXPECTED_TRANSPORT_DATA = {
    "data/jbb_behaviors_harmful.json": {
        "bytes": 34_556,
        "raw_sha256": "9ee1cb2aab52550f0817f036e4423e9f3cc05a6bb5a0084da404f1817d535e77",
    },
    "data/jbb_behaviors_harmful.json.meta.json": {
        "bytes": 219,
        "raw_sha256": "0f03ef1d440cd364cea3f8a15ed4d9ed08ae25dcde791666b49e282bf6d540ff",
    },
    "data/safe_pairs.json": {
        "bytes": 69_795,
        "raw_sha256": "822202eeed0231c17427138ced8e34ee7736c30af6937899579697d6b72e4548",
    },
    "data/safe_pairs.example.json": {
        "bytes": 534,
        "raw_sha256": "f595fd4bea108e4173efcfdbd995dc71ec3e84e356e99af589a08885da34dad3",
    },
    "data/single_prompt_bomb.json": {
        "bytes": 234,
        "raw_sha256": "fafce3334180fd493e3f64f957c946470e75965bbdbe0e9ed572b7d95942c7e4",
    },
}
ROUND9_PARENT_RELEASE = {
    "baseline_commit": "0efb6e8f514e0716ad92f9c4807f6c5e00b0c329",
    "inventory_sha256": "85064761a8fb377b64c4ec817a3b1203961b76030554fbbbe1dd05ae2c31fa5d",
    "path": "stage3_artifacts_final_round9/implementation_inventory.json",
    "raw_sha256": "04b5bf541a56f8f46f6e33b9fecfafd56595093e20ae70439fdf92c165d4a42d",
}
LF_ATTRIBUTES = {"diff": "unspecified", "eol": "lf", "text": "set"}
BYTE_PRESERVING_ATTRIBUTES = {"diff": "unset", "eol": "unspecified", "text": "unset"}
FORBIDDEN_PRODUCTION_TOKENS = (
    "load_dataset(",
    ".from_pretrained(",
    "requests.",
    "urllib.request",
    "http.client",
    "trust_remote_code=True",
)
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|cookie|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)
WINDOWS_ABSOLUTE = re.compile(r"(?i)(?:^|[\"'])\s*[A-Z]:\\")
EXPECTED_DRY_RUN_ARTIFACTS = {
    "dry_run_summary.json",
    "fixed720_trace.json",
    "generation_records.json",
    "judge_records.json",
    "logical_registry.json",
    "p2_record.json",
    "support_status.json",
    "synthetic_dose_binding.json",
    SUPPORT_ATTEMPT_RECEIPT_PATH,
    "synthetic_confirmation_attempt_receipt.jsonl",
    "synthetic_execution_receipt.jsonl",
    "execution_dispositions.json",
} | set(LIFECYCLE_ARTIFACT_PATHS.values()) | {
    path for paths in LIFECYCLE_BOUND_PATHS.values() for path in paths.values()
}
EXPECTED_OFFLINE_SMOKE_CHECKS = {
    "exact_bound_input_pass",
    "unbound_candidate_rejected",
    "missing_file_rejected",
    "raw_hash_mismatch_rejected",
    "schema_order_mismatch_rejected",
    "schema_field_type_mismatch_rejected",
    "nonfinite_json_constant_rejected",
    "duplicate_json_object_key_rejected",
    "duplicate_identity_rejected",
    "canonical_frame_hash_mismatch_rejected",
    "manifest_hash_mismatch_rejected",
    "freeze_bound_manifest_hash_mismatch_rejected",
    "data_symlink_rejected",
    "missing_license_material_rejected",
    "explicit_license_material_bundled",
    "deterministic_linux_portable_bundle",
    "tar_member_modes_pinned_across_umasks",
    "bundle_file_and_byte_counts_verified",
    "license_symlink_rejected",
    "preexisting_bundle_archive_rejected",
    "failed_bundle_cleans_only_new_targets",
    "unsupported_tar_member_rejected",
    "production_call_graph_no_online_download",
    "formal_socket_creation_audit_guard_blocks_backend_network",
    "formal_udp_sendto_audit_guard_blocks_backend_network",
    "formal_udp_sendmsg_audit_guard_blocks_backend_network",
    "formal_socket_bind_audit_guard_blocks_backend_network",
    "formal_socket_dns_audit_guard_blocks_backend_network",
    "formal_posix_spawn_audit_guard_blocks_backend_escape",
    "formal_fork_audit_guard_blocks_backend_escape",
    "formal_forkpty_audit_guard_blocks_backend_escape",
    "formal_subprocess_audit_guard_blocks_backend_escape",
    "formal_os_system_audit_guard_blocks_backend_escape",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def require_lf_text(path: Path) -> bytes:
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AssertionError(
            f"implementation inventory text input is not UTF-8: {path.relative_to(ROOT).as_posix()}"
        ) from error
    crlf_count = raw.count(b"\r\n")
    bare_cr_count = raw.count(b"\r") - crlf_count
    bare_lf_count = raw.count(b"\n") - crlf_count
    if crlf_count or bare_cr_count:
        if crlf_count and bare_lf_count:
            kind = "mixed EOL"
        elif crlf_count:
            kind = "CRLF"
        else:
            kind = "bare CR"
        raise AssertionError(
            "implementation inventory text input must use LF only: "
            f"{path.relative_to(ROOT).as_posix()} ({kind}; "
            f"crlf={crlf_count}, bare_cr={bare_cr_count}, bare_lf={bare_lf_count})"
        )
    return raw


def git_bytes(*args: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise AssertionError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout


def git_index_blob(relative: str) -> bytes:
    object_name = git_bytes("rev-parse", "--verify", f":{relative}").decode("ascii").strip()
    return git_bytes("cat-file", "blob", object_name)


def git_cached_attributes(relative: str) -> dict[str, str]:
    raw = git_bytes("check-attr", "--cached", "-z", "text", "eol", "diff", "--", relative)
    parts = raw.decode("utf-8").split("\0")
    if parts[-1:] == [""]:
        parts.pop()
    if len(parts) != 9:
        raise AssertionError(f"unexpected git check-attr output for {relative}")
    attributes = {}
    for index in range(0, len(parts), 3):
        path, attribute, value = parts[index:index + 3]
        if path != relative or attribute in attributes:
            raise AssertionError(f"ambiguous git attributes for {relative}")
        attributes[attribute] = value
    if set(attributes) != {"text", "eol", "diff"}:
        raise AssertionError(f"incomplete git attributes for {relative}")
    return {key: attributes[key] for key in sorted(attributes)}


def round9_parent_release() -> dict[str, object]:
    path = ROOT / str(ROUND9_PARENT_RELEASE["path"])
    if not path.is_file() or path.is_symlink():
        raise AssertionError("Round 9 parent inventory is unavailable")
    if file_sha256(path) != ROUND9_PARENT_RELEASE["raw_sha256"]:
        raise AssertionError("Round 9 parent inventory raw identity changed")
    document = load_json(path)
    if not isinstance(document, dict):
        raise AssertionError("Round 9 parent inventory must be an object")
    if document.get("inventory_sha256") != ROUND9_PARENT_RELEASE["inventory_sha256"]:
        raise AssertionError("Round 9 parent inventory content identity changed")
    return dict(ROUND9_PARENT_RELEASE)


def data_semantic_identities() -> dict[str, dict[str, object]]:
    manifest_path = ROOT / "stage3_artifacts_final_round8/offline/offline_asset_manifest.json"
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise AssertionError("Round 8 offline asset manifest must be an object")
    candidates = manifest.get("candidate_assets")
    if not isinstance(candidates, list):
        raise AssertionError("Round 8 offline candidate assets must be a list")
    identities = {}
    for item in candidates:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            raise AssertionError("Round 8 offline candidate asset is malformed")
        relative = item["relative_path"]
        identities[relative] = {
            "canonical_frame_sha256": item.get("canonical_frame_sha256"),
            "disposition": item.get("disposition"),
            "exact_ordered_field_names": item.get("exact_ordered_field_names"),
            "json_top_level_type": item.get("json_top_level_type"),
            "prompt_frame_membership": item.get("prompt_frame_membership"),
            "row_count": item.get("row_count"),
            "stable_row_identities_sha256": item.get("stable_row_identities_sha256"),
        }
    if set(identities) != set(EXPECTED_SOURCE_JSON_SHA256):
        raise AssertionError("Round 8 data semantic identity set changed")
    return identities


def implementation_inventory() -> dict[str, object]:
    candidates = list((ROOT / "stage3_pipeline").rglob("*"))
    candidates += list((ROOT / "scripts/stage3_production").rglob("*"))
    candidates += [
        ROOT / ".gitattributes",
        ROOT / ".gitignore",
        ROOT / "scripts/download_jbb_behaviors.py",
    ]
    candidates += [ROOT / relative for relative in EXPECTED_TRANSPORT_DATA]
    paths = sorted(
        {
            path.resolve()
            for path in candidates
            if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts
        },
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )
    semantic_identities = data_semantic_identities()
    files = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        checkout_raw = path.read_bytes() if relative in EXPECTED_TRANSPORT_DATA else require_lf_text(path)
        checkout_sha256 = hashlib.sha256(checkout_raw).hexdigest()
        blob_raw = git_index_blob(relative)
        blob_sha256 = hashlib.sha256(blob_raw).hexdigest()
        attributes = git_cached_attributes(relative)
        expected_attributes = (
            BYTE_PRESERVING_ATTRIBUTES if relative in EXPECTED_TRANSPORT_DATA else LF_ATTRIBUTES
        )
        if attributes != expected_attributes:
            raise AssertionError(
                f"Git attributes differ for {relative}: expected={expected_attributes}, actual={attributes}"
            )
        if blob_raw != checkout_raw:
            raise AssertionError(f"Git blob and checkout raw bytes differ: {relative}")
        entry = {
            "attributes": attributes,
            "bytes": len(checkout_raw),
            "checkout_raw_sha256": checkout_sha256,
            "eol_policy": "byte-preserving" if relative in EXPECTED_TRANSPORT_DATA else "lf-only",
            "git_blob_bytes": len(blob_raw),
            "git_blob_sha256": blob_sha256,
            "path": relative,
        }
        if relative in EXPECTED_TRANSPORT_DATA:
            frozen = EXPECTED_TRANSPORT_DATA[relative]
            if entry["bytes"] != frozen["bytes"] or checkout_sha256 != frozen["raw_sha256"]:
                raise AssertionError(f"frozen transport data identity changed: {relative}")
            entry["frozen_round8_raw_sha256"] = frozen["raw_sha256"]
            entry["semantic_identity"] = semantic_identities.get(relative)
        files.append(entry)
    producer_path = "scripts/stage3_production/verify_implementation.py"
    producer = next(entry for entry in files if entry["path"] == producer_path)
    payload = {
        "files": files,
        "parent_release": round9_parent_release(),
        "producing_script_sha256": producer["checkout_raw_sha256"],
        "schema_version": "paper1-stage3-portability-inventory-v2",
        "sort_order": "unicode-codepoint-relative-path-ascending",
    }
    return {**payload, "inventory_sha256": canonical_sha256(payload)}


def write_implementation_inventory(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    if resolved.exists() or resolved.is_symlink():
        raise AssertionError(f"refusing to overwrite implementation inventory: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    inventory = implementation_inventory()
    resolved.write_text(
        json.dumps(inventory, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return inventory


def verify_implementation_inventory(path: Path) -> dict[str, object]:
    expected = load_json(path)
    actual = implementation_inventory()
    if not isinstance(expected, dict) or set(expected) != set(actual):
        raise AssertionError("expected implementation inventory schema differs")
    rows = expected.get("files")
    if not isinstance(rows, list):
        raise AssertionError("expected implementation inventory files must be a list")
    row_paths = [row.get("path") for row in rows if isinstance(row, dict)]
    if (
        len(row_paths) != len(rows)
        or any(not isinstance(value, str) for value in row_paths)
        or row_paths != sorted(row_paths)
    ):
        raise AssertionError("expected implementation inventory is not ordinal path-sorted")
    payload = {key: value for key, value in expected.items() if key != "inventory_sha256"}
    if expected.get("inventory_sha256") != canonical_sha256(payload):
        raise AssertionError("expected implementation inventory content hash mismatch")
    if expected != actual:
        raise AssertionError("implementation source bytes differ from the expected inventory")
    return {
        "file_count": len(rows),
        "git_blob_checkout_identity": True,
        "inventory_sha256": expected["inventory_sha256"],
        "parent_release": expected["parent_release"],
        "path": path.resolve().as_posix(),
        "transport_data": [
            row for row in rows if row["path"] in EXPECTED_TRANSPORT_DATA
        ],
    }


def verify_self_hash(document: dict[str, object], label: str) -> None:
    expected = document.get("self_sha256")
    actual = canonical_sha256({key: value for key, value in document.items() if key != "self_sha256"})
    if expected != actual:
        raise AssertionError(f"{label} self hash mismatch")


def verify_schema_files() -> list[str]:
    paths = sorted((ROOT / "stage3_pipeline/schemas").glob("*.schema.json"))
    required = {
        "p1_measurement_record.schema.json",
        "p2_response_record.schema.json",
        "k1_reuse_record.schema.json",
        "benign_response_record.schema.json",
        "generation_record.schema.json",
        "judge_record.schema.json",
        "measurement_result_dose_binding.schema.json",
        "execution_disposition.schema.json",
        "lifecycle_artifact.schema.json",
    }
    if {path.name for path in paths} != required:
        raise AssertionError("production schema inventory differs")
    validator_keys = {
        "p1_measurement_record.schema.json": P1_KEYS,
        "p2_response_record.schema.json": P2_KEYS,
        "k1_reuse_record.schema.json": K1_KEYS,
        "benign_response_record.schema.json": BENIGN_KEYS,
        "generation_record.schema.json": GENERATION_KEYS,
        "judge_record.schema.json": JUDGE_KEYS,
    }
    for path in paths:
        schema = load_json(path)
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise AssertionError(f"invalid schema document: {path}")
        if path.name in validator_keys:
            if set(schema.get("properties", {})) != validator_keys[path.name]:
                raise AssertionError(f"schema properties differ from Python validator: {path}")
            if set(schema.get("required", [])) != validator_keys[path.name]:
                raise AssertionError(f"schema required fields differ from Python validator: {path}")
    return [path.relative_to(ROOT).as_posix() for path in paths]


def verify_local_download_boundary() -> dict[str, object]:
    path = ROOT / "scripts/download_jbb_behaviors.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    revision_required = False
    pinned_loader_calls = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "--revision":
                keywords = {item.arg: item.value for item in node.keywords if item.arg is not None}
                revision_required = isinstance(keywords.get("required"), ast.Constant) and (
                    keywords["required"].value is True
                )
        if isinstance(node.func, ast.Name) and node.func.id == "load_dataset":
            keywords = {item.arg: item.value for item in node.keywords if item.arg is not None}
            revision = keywords.get("revision")
            trust = keywords.get("trust_remote_code")
            if (
                isinstance(revision, ast.Name)
                and revision.id == "revision"
                and isinstance(trust, ast.Constant)
                and trust.value is False
            ):
                pinned_loader_calls += 1
    required_tokens = {
        "default_overwrite_deny": "default overwrite policy is DENY",
        "existing_hash_binding": "--expected-existing-sha256",
        "candidate_hash_approval": "--approve-replacement-sha256",
        "exact_commit_pattern": "^[0-9a-f]{40}$",
    }
    missing = [name for name, token in required_tokens.items() if token not in source]
    if not revision_required or pinned_loader_calls != 1 or missing:
        raise AssertionError(
            "local download boundary is not pinned/fail-closed: "
            f"revision_required={revision_required}, pinned_calls={pinned_loader_calls}, missing={missing}"
        )
    return {
        "production_reachable": False,
        "revision_required": True,
        "trust_remote_code": False,
        "default_overwrite": "DENY",
        "hash_change_requires_exact_approval": True,
    }


def verify_registry(path: Path) -> dict[str, object]:
    document = load_json(path)
    if not isinstance(document, dict):
        raise AssertionError("logical registry must be an object")
    verify_self_hash(document, "logical registry")
    records = document["records"]
    if not isinstance(records, list) or len(records) != 5_580:
        raise AssertionError("logical registry does not contain 5,580 records")
    logical_ids = [item["logical_id"] for item in records]
    if len(set(logical_ids)) != len(logical_ids):
        raise AssertionError("logical registry contains duplicate IDs")
    if document["registry_sha256"] != canonical_sha256(records):
        raise AssertionError("logical registry content hash mismatch")
    rebuilt = LogicalIdentityRegistry(synthetic=True)
    rebuilt_ids = [rebuilt.register(item["identity"]) for item in records]
    if rebuilt_ids != logical_ids or rebuilt.manifest()["registry_sha256"] != document["registry_sha256"]:
        raise AssertionError("logical registry IDs do not match canonical identity serialization")
    counts = Counter(item["identity"]["block"] for item in records)
    budget = assert_budget(dict(counts))
    return {"identity_count": len(records), "registry_sha256": document["registry_sha256"], "budget": budget}


def verify_artifact_inventory(directory: Path) -> dict[str, object]:
    inventory = load_json(directory / "artifact_inventory.json")
    if not isinstance(inventory, dict):
        raise AssertionError("synthetic artifact inventory must be an object")
    verify_self_hash(inventory, "synthetic artifact inventory")
    entries = inventory.get("artifacts")
    if not isinstance(entries, list):
        raise AssertionError("synthetic artifact inventory entries must be a list")
    paths = [entry.get("path") for entry in entries if isinstance(entry, dict)]
    if len(paths) != len(entries) or set(paths) != EXPECTED_DRY_RUN_ARTIFACTS:
        raise AssertionError("synthetic artifact inventory is incomplete or contains extras")
    if len(paths) != len(set(paths)):
        raise AssertionError("synthetic artifact inventory contains duplicate paths")
    for entry in entries:
        path = directory / entry["path"]
        if not path.is_file() or path.is_symlink():
            raise AssertionError(f"inventoried synthetic artifact is unavailable: {entry['path']}")
        if path.stat().st_size != entry.get("bytes") or file_sha256(path) != entry.get("sha256"):
            raise AssertionError(f"inventoried synthetic artifact hash/size mismatch: {entry['path']}")
    return {"artifact_count": len(entries), "inventory_self_sha256": inventory["self_sha256"]}


def verify_synthetic_records(directory: Path) -> dict[str, object]:
    generation = load_json(directory / "generation_records.json")
    judge = load_json(directory / "judge_records.json")
    p2 = load_json(directory / "p2_record.json")
    dispositions_document = load_json(directory / "execution_dispositions.json")
    if not all(isinstance(item, dict) for item in (
        generation, judge, p2, dispositions_document
    )):
        raise AssertionError("synthetic record artifacts must be objects")
    for document, label in (
        (generation, "generation records artifact"),
        (judge, "judge records artifact"),
        (p2, "P2 record artifact"),
        (dispositions_document, "execution dispositions artifact"),
    ):
        verify_self_hash(document, label)
        if document.get("synthetic") is not True or document.get("formal_experiment") is not False:
            raise AssertionError(f"{label} is not explicitly synthetic/non-formal")
    generation_records = generation.get("records")
    judge_records = judge.get("records")
    support_dispositions = dispositions_document.get("support_records")
    confirmation_dispositions = dispositions_document.get("confirmation_records")
    if not isinstance(generation_records, list) or len(generation_records) != 3:
        raise AssertionError("synthetic generation record count changed")
    if not isinstance(judge_records, list) or len(judge_records) != 2:
        raise AssertionError("synthetic judge record count changed")
    if not isinstance(support_dispositions, list) or len(support_dispositions) != 900:
        raise AssertionError("synthetic support dispositions do not cover 900 identities")
    if (
        not isinstance(confirmation_dispositions, list)
        or len(confirmation_dispositions) != 4_680
    ):
        raise AssertionError("synthetic confirmation dispositions do not cover 4,680 identities")
    for record in generation_records:
        validate_generation_record(record)
    for record in judge_records:
        validate_judge_record(record)
    p2_record = p2.get("record")
    if not isinstance(p2_record, dict):
        raise AssertionError("synthetic P2 artifact does not contain one production record")
    registry_document = load_json(directory / "logical_registry.json")
    if not isinstance(registry_document, dict) or not isinstance(registry_document.get("records"), list):
        raise AssertionError("synthetic logical registry is unavailable for record reconciliation")
    rebuilt = LogicalIdentityRegistry(synthetic=True)
    identity_by_id: dict[str, dict[str, object]] = {}
    for item in registry_document["records"]:
        logical_id = rebuilt.register(item["identity"])
        if logical_id != item["logical_id"]:
            raise AssertionError("synthetic registry logical ID changed during record reconciliation")
        identity_by_id[logical_id] = item["identity"]
    generation_by_id = {record["logical_id"]: record for record in generation_records}
    judge_by_id = {record["logical_id"]: record for record in judge_records}
    source_generation = generation_by_id.get(p2_record["logical_id"])
    source_judge = judge_by_id.get(p2_record["logical_id"])
    source_identity = identity_by_id.get(p2_record["logical_id"])
    if source_generation is None or source_judge is None or source_identity is None:
        raise AssertionError("synthetic P2 record lacks its generation/judge/identity source")
    measurement_result = load_json(
        directory / "protocol/measurement_result_dose_manifest.json"
    )
    if not isinstance(measurement_result, dict):
        raise AssertionError("synthetic measurement-result dose manifest is unavailable")
    dose_context = FreezeLifecycle(
        AppendOnlyReceipt(directory / "synthetic_execution_receipt.jsonl", synthetic=True),
        directory,
    ).authenticated_dose_context()
    validated_p2 = validate_p2_materialization(
        {
            key: value
            for key, value in p2_record.items()
            if key not in {"retained", "record_sha256"}
        },
        registry=rebuilt,
        generation_record=source_generation,
        judge_record=source_judge,
        measurement_result_dose_manifest=measurement_result,
        dose_context=dose_context,
    )
    if validated_p2 != p2_record:
        raise AssertionError("synthetic P2 derived fields do not match the materialized sources")
    if (
        p2_record["identity_sha256"] != source_generation["identity_sha256"]
        or p2_record["identity_sha256"] != canonical_sha256(source_identity)
        or p2_record["generation_record_sha256"] != source_generation["record_sha256"]
        or p2_record["generation_completed"] is not source_generation["generation_completed"]
    ):
        raise AssertionError("synthetic P2 provenance differs from its generation record")
    evidence = p2_record["dose_evidence"]
    if (
        evidence["nominal_c"]["binary64_hex"] != source_identity["c_hex"]
        or evidence["alpha_pre_dtype"]["binary64_hex"] != source_identity["alpha_pre_dtype_hex"]
        or evidence["alpha_post_dtype"]["binary64_hex"] != source_identity["alpha_post_dtype_hex"]
        or evidence["mu_estimator"] != source_identity["estimator"]
    ):
        raise AssertionError("synthetic P2 per-call dose evidence differs from logical identity")
    dose_artifact = load_json(directory / "synthetic_dose_binding.json")
    if not isinstance(dose_artifact, dict) or not isinstance(dose_artifact.get("dose_binding"), dict):
        raise AssertionError("synthetic dose binding evidence is unavailable")
    verify_self_hash(dose_artifact, "synthetic dose binding evidence")
    dose_binding = dose_artifact["dose_binding"]
    if evidence["measurement_result_dose_binding_sha256"] != dose_binding.get("self_sha256"):
        raise AssertionError("synthetic P2 dose evidence lost its measurement binding")

    lifecycle_receipt = AppendOnlyReceipt(
        directory / "synthetic_execution_receipt.jsonl", synthetic=True
    )
    lifecycle = FreezeLifecycle(lifecycle_receipt, directory).verify()
    if lifecycle["entry_count"] != len(EVENT_ORDER):
        raise AssertionError("synthetic lifecycle receipt entry count changed")
    lifecycle_entries = lifecycle_receipt._load()
    support_authorization = next(
        entry for entry in lifecycle_entries
        if entry["event"] == "FORMAL_SUPPORT_GENERATION_STARTED"
    )
    lifecycle_tip = lifecycle_entries[-1]
    if lifecycle_tip["event"] != "FORMAL_CONFIRMATION_GENERATION_STARTED":
        raise AssertionError("synthetic lifecycle does not authorize confirmation generation")
    if (
        dispositions_document.get("registry_sha256") != registry_document["registry_sha256"]
        or dispositions_document.get("support_authorization_entry_sha256")
        != support_authorization["entry_sha256"]
        or dispositions_document.get("confirmation_authorization_entry_sha256")
        != lifecycle_tip["entry_sha256"]
    ):
        raise AssertionError("synthetic dispositions lost registry/lifecycle binding")
    support_receipt = AppendOnlyReceipt(
        directory / Path(SUPPORT_ATTEMPT_RECEIPT_PATH), synthetic=True
    )
    confirmation_receipt = AppendOnlyReceipt(
        directory / "synthetic_confirmation_attempt_receipt.jsonl", synthetic=True
    )
    support_attempts = support_receipt.verify()
    confirmation_attempts = confirmation_receipt.verify()
    if support_attempts["entry_count"] != 1 or confirmation_attempts["entry_count"] != 11:
        raise AssertionError("synthetic phase attempt receipt entry counts changed")
    actual_calls = reconcile_complete_execution(
        rebuilt,
        lifecycle_receipt=lifecycle_receipt,
        lifecycle_artifact_root=directory,
        support_receipt=support_receipt,
        support_generation_records=[],
        support_judge_records=[],
        support_dispositions=support_dispositions,
        confirmation_receipt=confirmation_receipt,
        confirmation_generation_records=generation_records,
        confirmation_judge_records=judge_records,
        confirmation_dispositions=confirmation_dispositions,
    )
    return {
        "generation_records": len(generation_records),
        "judge_records": len(judge_records),
        "p2_records": 1,
        "lifecycle": lifecycle,
        "support_attempts": support_attempts,
        "confirmation_attempts": confirmation_attempts,
        "actual_calls": actual_calls,
    }


def verify_synthetic_summaries(directory: Path) -> dict[str, object]:
    support = load_json(directory / "support_status.json")
    quota = load_json(directory / "fixed720_trace.json")
    if not isinstance(support, dict) or not isinstance(quota, dict):
        raise AssertionError("synthetic support/quota artifacts must be objects")
    for document, label in ((support, "support status"), (quota, "fixed720 trace")):
        verify_self_hash(document, label)
        if document.get("synthetic") is not True or document.get("formal_experiment") is not False:
            raise AssertionError(f"{label} is not explicitly synthetic/non-formal")
    expected_support = {
        "A": "SUPPORTED",
        "T": "SUPPORT_LIMITED",
        "H": "SUPPORTED",
    }
    for anchor, expected in expected_support.items():
        if support.get(anchor, {}).get("support_status") != expected:
            raise AssertionError(f"synthetic support status changed for {anchor}")
    if support.get("analysis_precedence") != {
        "A": "NON_ESTIMABLE_ANALYSIS",
        "T": "ESTIMATION_ONLY_SUPPORT_LIMITED",
    }:
        raise AssertionError("synthetic analysis precedence changed")
    if quota.get("selected_n") != 720 or quota.get("fixed720_status") != "complete":
        raise AssertionError("fixed720 synthetic trace changed")
    return {
        "support_statuses": expected_support,
        "fixed720_selected": 720,
    }


def verify_offline(directory: Path) -> dict[str, object]:
    manifest = load_json(directory / "offline_asset_manifest.json")
    inventory = load_json(directory / "external_dependency_inventory.json")
    smoke = load_json(directory / "offline_smoke_receipt.json")
    build_receipt = load_json(directory / "offline_build_receipt.json")
    call_graph = load_json(directory / "production_call_graph.json")
    if not all(
        isinstance(item, dict)
        for item in (manifest, inventory, smoke, build_receipt, call_graph)
    ):
        raise AssertionError("offline artifacts must be objects")
    manifest_expected = manifest["manifest_sha256"]
    manifest_actual = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    if manifest_expected != manifest_actual:
        raise AssertionError("offline manifest hash mismatch")
    if manifest["offline_asset_status"] != "DATA_IDENTITY_BLOCKED" or manifest["formal_inputs"] != []:
        raise AssertionError("unbound candidates were promoted to FORMAL_INPUT")
    candidate_map = {entry["relative_path"]: entry for entry in manifest["candidate_assets"]}
    if set(candidate_map) != set(EXPECTED_SOURCE_JSON_SHA256) or len(candidate_map) != len(manifest["candidate_assets"]):
        raise AssertionError("offline candidate manifest paths are incomplete or duplicated")
    for relative, expected_hash in EXPECTED_SOURCE_JSON_SHA256.items():
        if candidate_map[relative].get("raw_sha256") != expected_hash:
            raise AssertionError(f"offline candidate identity changed: {relative}")
    single = candidate_map["data/single_prompt_bomb.json"]
    if single["validation_status"] != "SCHEMA_MISMATCH" or single["json_top_level_type"] != "array":
        raise AssertionError("single_prompt_bomb structure mismatch is not recorded")
    dispositions = {entry["disposition"] for entry in inventory["dependencies"]}
    if not dispositions <= ALLOWED_DISPOSITIONS:
        raise AssertionError("external inventory contains an invalid disposition")
    if inventory.get("inventory_sha256") != canonical_sha256(inventory["dependencies"]):
        raise AssertionError("external dependency inventory hash mismatch")
    if inventory.get("network_required_at_production_runtime") is not False or inventory.get("online_fallback") is not False:
        raise AssertionError("external dependency inventory permits online production behavior")
    if smoke["marker"] != "STAGE3_STRICT_OFFLINE_SMOKE_PASS" or smoke["network_attempt_count"] != 0:
        raise AssertionError("strict offline smoke evidence is missing")
    smoke_checks = smoke.get("checks")
    if (
        not isinstance(smoke_checks, list)
        or len(smoke_checks) != len(set(smoke_checks))
        or set(smoke_checks) != EXPECTED_OFFLINE_SMOKE_CHECKS
    ):
        raise AssertionError("strict offline smoke evidence is incomplete or stale")
    if not smoke["repository_json_unchanged"]:
        raise AssertionError("offline smoke changed source JSON")
    if build_receipt.get("offline_asset_status") != "DATA_IDENTITY_BLOCKED":
        raise AssertionError("offline build receipt lost the data identity blocker")
    if (
        build_receipt.get("formal_inputs") != []
        or build_receipt.get("bundle_file") is not None
        or build_receipt.get("bundle_sha256") is not None
        or build_receipt.get("bundle_bytes") is not None
        or build_receipt.get("formal_experiment_run") is not False
        or build_receipt.get("source_json_modified") is not False
    ):
        raise AssertionError("blocked offline build receipt claims unavailable outputs")
    receipt_artifacts = build_receipt.get("artifacts")
    expected_receipt_paths = {
        "candidate_checksums.sha256",
        "external_dependency_inventory.json",
        "offline_asset_manifest.json",
        "production_call_graph.json",
    }
    if not isinstance(receipt_artifacts, list) or {
        entry.get("path") for entry in receipt_artifacts if isinstance(entry, dict)
    } != expected_receipt_paths:
        raise AssertionError("offline build receipt artifact inventory changed")
    for entry in receipt_artifacts:
        path = directory / entry["path"]
        if path.stat().st_size != entry.get("bytes") or file_sha256(path) != entry.get("sha256"):
            raise AssertionError(f"offline build artifact hash/size mismatch: {entry['path']}")
    checksum_lines = (directory / "candidate_checksums.sha256").read_text(encoding="ascii").splitlines()
    expected_checksum_lines = [
        f"{entry['raw_sha256']}  {entry['relative_path']}"
        for entry in manifest["candidate_assets"]
    ]
    if checksum_lines != expected_checksum_lines:
        raise AssertionError("candidate checksum list differs from the offline manifest")
    if (
        call_graph.get("network_calls") != []
        or call_graph.get("remote_dataset_loaders") != []
        or call_graph.get("online_fallback") is not False
    ):
        raise AssertionError("production call graph contains online behavior")
    if call_graph.get("production_entrypoints") != [
        "stage3_pipeline.core.GenerationProducer",
        "stage3_pipeline.offline_assets.OfflineJsonLoader",
        "stage3_pipeline.references.ReferenceAdapter",
        "stage3_pipeline.execution.build_logical_plan",
    ]:
        raise AssertionError("production call graph entrypoints changed")
    return {
        "status": manifest["offline_asset_status"],
        "formal_inputs": 0,
        "candidate_count": len(candidate_map),
        "network_attempt_count": 0,
    }


def scan_repository_files(paths: list[Path]) -> dict[str, object]:
    absolute_path_hits = []
    secret_hits = []
    symlinks = []
    oversized = []
    for path in paths:
        if path.is_symlink():
            symlinks.append(path.relative_to(ROOT).as_posix())
            continue
        if not path.is_file():
            continue
        if path.stat().st_size > 15 * 1024 * 1024:
            oversized.append(path.relative_to(ROOT).as_posix())
        if path.suffix.lower() not in {".py", ".json", ".md", ".sha256", ".jsonl"}:
            continue
        text = path.read_text(encoding="utf-8")
        if WINDOWS_ABSOLUTE.search(text):
            absolute_path_hits.append(path.relative_to(ROOT).as_posix())
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            secret_hits.append(path.relative_to(ROOT).as_posix())
    if absolute_path_hits or secret_hits or symlinks or oversized:
        raise AssertionError(
            f"artifact hygiene failure absolute={absolute_path_hits}, secret={secret_hits}, "
            f"symlink={symlinks}, oversized={oversized}"
        )
    return {
        "absolute_windows_path_hits": 0,
        "secret_hits": 0,
        "symlink_hits": 0,
        "files_over_15mib": 0,
    }


def main() -> int:
    require_project_local_temp(ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=ROOT / "stage3_artifacts")
    parser.add_argument("--write-inventory", type=Path)
    parser.add_argument("--expected-inventory", type=Path)
    args = parser.parse_args()
    if args.write_inventory is not None:
        if args.expected_inventory is not None:
            raise AssertionError("--write-inventory and --expected-inventory are mutually exclusive")
        inventory = write_implementation_inventory(args.write_inventory)
        print(json.dumps({
            "marker": "STAGE3_IMPLEMENTATION_INVENTORY_WRITTEN",
            "path": args.write_inventory.resolve().as_posix(),
            "file_count": len(inventory["files"]),
            "inventory_sha256": inventory["inventory_sha256"],
        }, sort_keys=True))
        return 0
    artifacts = args.artifacts.resolve()
    inventory_binding = (
        verify_implementation_inventory(args.expected_inventory)
        if args.expected_inventory is not None
        else {"status": "UNBOUND_EXPECTED_INVENTORY"}
    )

    bindings = ReferenceAdapter(ROOT).binding_report()
    schemas = verify_schema_files()
    download_boundary = verify_local_download_boundary()
    synthetic_directory = artifacts / "synthetic_dry_run"
    registry = verify_registry(synthetic_directory / "logical_registry.json")
    dry_summary = load_json(synthetic_directory / "dry_run_summary.json")
    if not isinstance(dry_summary, dict):
        raise AssertionError("dry-run summary must be an object")
    verify_self_hash(dry_summary, "dry-run summary")
    if dry_summary["marker"] != "STAGE3_SYNTHETIC_PRODUCTION_DRY_RUN_PASS":
        raise AssertionError("synthetic dry-run marker missing")
    if dry_summary["formal_experiment_run"] is not False:
        raise AssertionError("dry-run is not marked non-formal")
    synthetic_records = verify_synthetic_records(synthetic_directory)
    if dry_summary["lifecycle_receipt"] != synthetic_records["lifecycle"]:
        raise AssertionError("dry-run summary lifecycle receipt differs from the append-only log")
    if dry_summary["support_attempt_receipt"] != synthetic_records["support_attempts"]:
        raise AssertionError("dry-run support receipt differs from the append-only log")
    if (
        dry_summary["confirmation_attempt_receipt"]
        != synthetic_records["confirmation_attempts"]
    ):
        raise AssertionError("dry-run confirmation receipt differs from the append-only log")
    if dry_summary["actual_calls"] != synthetic_records["actual_calls"]:
        raise AssertionError("dry-run actual call accounting differs from the attempt ledger")
    artifact_inventory = verify_artifact_inventory(synthetic_directory)
    synthetic_summaries = verify_synthetic_summaries(synthetic_directory)
    offline = verify_offline(artifacts / "offline")

    for relative, expected in EXPECTED_TRANSPORT_DATA.items():
        path = ROOT / relative
        if path.stat().st_size != expected["bytes"] or file_sha256(path) != expected["raw_sha256"]:
            raise AssertionError(f"repository source JSON changed: {relative}")

    production_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "stage3_pipeline").glob("*.py"))
    )
    found = [token for token in FORBIDDEN_PRODUCTION_TOKENS if token in production_text]
    if found:
        raise AssertionError(f"production code contains online/download call token: {found}")
    scanned = list((ROOT / "stage3_pipeline").rglob("*"))
    scanned += list((ROOT / "scripts/stage3_production").rglob("*"))
    scanned += list(artifacts.rglob("*"))
    hygiene = scan_repository_files(scanned)

    report = {
        "schema_version": "paper1-stage3-implementation-fidelity-v1",
        "marker": "STAGE3_IMPLEMENTATION_FIDELITY_PASS_WITH_EXTERNAL_BLOCKERS",
        "implementation_fidelity": "PASS",
        "final_status": "IMPLEMENTATION-BLOCKED",
        "offline_asset_status": "DATA_IDENTITY_BLOCKED",
        "formal_experiment_run": False,
        "reference_bindings": bindings,
        "schemas": schemas,
        "local_download_boundary": download_boundary,
        "registry": registry,
        "synthetic_records": synthetic_records,
        "artifact_inventory": artifact_inventory,
        "synthetic_summaries": synthetic_summaries,
        "offline": offline,
        "artifact_hygiene": hygiene,
        "implementation_inventory": inventory_binding,
        "production_network_calls": 0,
        "scope_expansion": False,
        "blocking_items": [
            "Frozen prompt-frame file and row identities are not bound.",
            "Checkpoint/tokenizer/template/anchor/vector/judge/runtime identities are SERVER_ONLY.",
        ],
    }
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
