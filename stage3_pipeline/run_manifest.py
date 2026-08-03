"""Non-overwriting run manifests bound to verified execution facts."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import (
    MASTER_SEED,
    PAPER_LOGICAL_GENERATION,
    OfflineExecutionGuard,
    PipelineError,
    VerifiedBackendCapability,
    canonical_json,
    canonical_sha256,
    file_sha256,
    validate_generation_config,
    validate_run_mode,
)
from .execution import BLOCK_BUDGET, TERMINAL_DISPOSITIONS, VerifiedReconciliation


RUN_MANIFEST_SCHEMA = "paper1-stage3-run-manifest-v3"
LEGACY_RUN_MANIFEST_SCHEMA = "paper1-stage3-run-manifest-v2"
COUNT_FIELDS = (
    "scheduled_logical_ids", "generation_first_pass_scheduled",
    "generation_first_pass_calls", "generation_completed", "generation_retry_calls",
    "generation_total_calls", "judge_first_pass_scheduled", "judge_eligible",
    "judge_first_pass_calls", "judge_parsed", "judge_retry_calls", "judge_total_calls",
    "completed_item_count", "failure_count", "unattempted_count",
    "k1_additional_generation_calls", "k1_additional_judge_calls",
)


class RunManifestError(PipelineError):
    """A run manifest is incomplete, inconsistent, or would be overwritten."""


_RUN_MANIFEST_TOKEN = object()


class VerifiedRunManifest(Mapping[str, Any]):
    """Builder-issued manifest whose nested values are returned by copy."""

    def __init__(self, document: Mapping[str, Any], token: object) -> None:
        if token is not _RUN_MANIFEST_TOKEN:
            raise RunManifestError("verified run manifests can only be issued by build_run_manifest")
        self.__canonical = canonical_json(dict(document))

    def __getitem__(self, key: str) -> Any:
        return json.loads(self.__canonical)[key]

    def __iter__(self):
        return iter(json.loads(self.__canonical))

    def __len__(self) -> int:
        return len(json.loads(self.__canonical))

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.__canonical)


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def collect_runtime_versions() -> dict[str, str | None]:
    cuda_version: str | None = None
    try:
        import torch

        cuda_version = torch.version.cuda
    except (ImportError, OSError, AttributeError):
        pass
    return {
        "python": platform.python_version(),
        "torch": _package_version("torch"),
        "transformers": _package_version("transformers"),
        "cuda": cuda_version,
    }


def git_repository_state(repo_root: Path) -> dict[str, str | bool]:
    root = repo_root.resolve()
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root,
            check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RunManifestError("unable to inspect Git repository state") from exc
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise RunManifestError("git commit is not a full lowercase SHA1")
    return {"git_commit": commit, "dirty": bool(status)}


def _input_records(input_paths: Sequence[Path]) -> list[dict[str, str]]:
    if not input_paths:
        raise RunManifestError("at least one input path is required")
    records: list[dict[str, str]] = []
    seen: set[Path] = set()
    for source in input_paths:
        if not isinstance(source, Path):
            raise RunManifestError("input paths must be pathlib.Path values")
        path = source.resolve()
        if path in seen:
            raise RunManifestError(f"duplicate input path: {path}")
        seen.add(path)
        if not path.is_file() or path.is_symlink():
            raise RunManifestError(f"input path is missing or linked: {path}")
        records.append({"path": str(path), "sha256": file_sha256(path)})
    return records


def _timestamps(started_at_utc: str, completed_at_utc: str) -> None:
    try:
        started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at_utc.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RunManifestError("run timestamps must be ISO-8601") from exc
    if started.tzinfo is None or completed.tzinfo is None or completed < started:
        raise RunManifestError("run timestamps must be ordered and timezone-aware")


def _validate_offline_report(report: Any) -> dict[str, Any]:
    required = {
        "schema_version", "scope", "guard_closed", "process_depth_after_exit",
        "category_counts", "blocked_attempt_count", "os_level_sandbox",
    }
    if not isinstance(report, Mapping) or set(report) != required:
        raise RunManifestError("offline guard report fields differ")
    if (
        report["schema_version"] != "paper1-stage3-offline-guard-report-v1"
        or report["scope"] != "python_process_asset_model_judge_only"
        or report["guard_closed"] is not True
        or report["process_depth_after_exit"] != 0
        or report["os_level_sandbox"] is not False
    ):
        raise RunManifestError("offline guard report is not a closed outermost Python scope")
    categories = report["category_counts"]
    expected_categories = {"network", "subprocess", "system", "fork", "spawn", "exec"}
    if not isinstance(categories, Mapping) or set(categories) != expected_categories:
        raise RunManifestError("offline guard report categories differ")
    for value in categories.values():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RunManifestError("offline guard category counts must be nonnegative integers")
    if report["blocked_attempt_count"] != sum(categories.values()):
        raise RunManifestError("offline guard total differs from category counts")
    return json.loads(canonical_json(dict(report)))


def _validate_reconciliation(document: Any, run_mode: str) -> dict[str, Any]:
    required = {
        "schema_version", "run_mode", "paper_result_eligible", "registry_sha256",
        "block_counts", *COUNT_FIELDS, "terminal_partition", "terminal_partition_sha256",
        "support_mapping_sha256",
    }
    if not isinstance(document, Mapping) or set(document) != required:
        raise RunManifestError("reconciliation fields differ")
    if (
        document["schema_version"] != "paper1-stage3-execution-reconciliation-v1"
        or document["run_mode"] != run_mode
        or document["paper_result_eligible"] is not False
    ):
        raise RunManifestError("reconciliation header differs from run manifest")
    for field in (*COUNT_FIELDS,):
        value = document[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RunManifestError(f"reconciliation {field} must be a nonnegative integer")
    for field in ("registry_sha256", "terminal_partition_sha256", "support_mapping_sha256"):
        value = document[field]
        if (
            not isinstance(value, str) or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise RunManifestError(f"reconciliation {field} must be a lowercase SHA256")
    block_counts = document["block_counts"]
    if not isinstance(block_counts, Mapping) or set(block_counts) != set(BLOCK_BUDGET):
        raise RunManifestError("reconciliation block-count categories differ")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in block_counts.values()
    ):
        raise RunManifestError("reconciliation block counts must be nonnegative integers")
    partition = document["terminal_partition"]
    if not isinstance(partition, Mapping) or set(partition) != set(TERMINAL_DISPOSITIONS):
        raise RunManifestError("terminal partition categories differ")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in partition.values()):
        raise RunManifestError("terminal partition counts must be nonnegative integers")
    scheduled = document["scheduled_logical_ids"]
    if sum(block_counts.values()) != scheduled:
        raise RunManifestError("reconciliation block counts do not cover the registry")
    if sum(partition.values()) != scheduled:
        raise RunManifestError("terminal partition does not cover the registry")
    if document["generation_first_pass_scheduled"] != scheduled or document["judge_first_pass_scheduled"] != scheduled:
        raise RunManifestError("first-pass schedules differ from logical registry")
    if document["generation_total_calls"] != document["generation_first_pass_calls"] + document["generation_retry_calls"]:
        raise RunManifestError("generation call accounting differs")
    if document["judge_total_calls"] != document["judge_first_pass_calls"] + document["judge_retry_calls"]:
        raise RunManifestError("judge call accounting differs")
    if document["completed_item_count"] != partition["COMPLETED_PARSED"]:
        raise RunManifestError("completed count differs from terminal partition")
    if document["failure_count"] != scheduled - document["completed_item_count"]:
        raise RunManifestError("failure count differs from terminal partition")
    if document["unattempted_count"] != partition["UNATTEMPTED_DUE_INTEGRITY_BLOCK"]:
        raise RunManifestError("unattempted count differs from terminal partition")
    if document["generation_first_pass_calls"] != scheduled - document["unattempted_count"]:
        raise RunManifestError("generation attempted count differs from unattempted partition")
    if document["judge_eligible"] != document["judge_first_pass_calls"]:
        raise RunManifestError("judge eligibility differs from actual first-pass judge calls")
    if document["judge_parsed"] < document["completed_item_count"]:
        raise RunManifestError("parsed judge count is below completed terminal count")
    if document["k1_additional_generation_calls"] or document["k1_additional_judge_calls"]:
        raise RunManifestError("K1 must add zero generation and judge calls")
    if run_mode == "paper" and scheduled != PAPER_LOGICAL_GENERATION:
        raise RunManifestError("paper reconciliation must cover exactly 5,580 logical IDs")
    if run_mode == "paper" and dict(block_counts) != BLOCK_BUDGET:
        raise RunManifestError("paper reconciliation block counts differ from the fixed design")
    if run_mode != "paper" and scheduled < 1:
        raise RunManifestError("smoke/pilot reconciliation requires its actual nonempty registry")
    return json.loads(canonical_json(dict(document)))


def _validate_backend_identity(
    identity: Any,
    *,
    fake_backend: bool,
    asset_status: str,
    run_mode: str,
    reconciliation: Mapping[str, Any] | None = None,
    require_execution_lineage: bool = True,
) -> dict[str, Any] | None:
    if identity is None:
        if asset_status == "development_only":
            raise RunManifestError("development-only real runs require backend_identity")
        return None
    if fake_backend:
        raise RunManifestError("fake backend manifests may not claim real backend identity")
    required = {
        "schema_version", "asset_status", "identity_level", "behavior_identity",
        "judge_identity", "vector_identity", "hook_identity", "gpu_identity", "lifecycle",
    }
    if not isinstance(identity, Mapping) or not required.issubset(identity):
        raise RunManifestError("real backend_identity fields are incomplete")
    try:
        normalized = json.loads(canonical_json(dict(identity)))
    except (TypeError, ValueError) as exc:
        raise RunManifestError("backend_identity is not canonical JSON") from exc
    if normalized["schema_version"] != "paper1-stage3-real-backend-provenance-v1":
        raise RunManifestError("real backend_identity schema_version mismatch")
    if normalized["asset_status"] != asset_status:
        raise RunManifestError("backend_identity asset_status differs from manifest")
    if not isinstance(normalized["identity_level"], str) or not normalized["identity_level"]:
        raise RunManifestError("backend identity_level must be nonempty")
    for field in (
        "behavior_identity", "judge_identity", "vector_identity", "hook_identity",
        "gpu_identity", "lifecycle",
    ):
        if not isinstance(normalized[field], Mapping) or not normalized[field]:
            raise RunManifestError(f"backend_identity.{field} must be a nonempty object")
    if asset_status == "development_only":
        if run_mode != "smoke" or normalized["identity_level"] != "development_candidate":
            raise RunManifestError("development-only identity must be smoke/development_candidate")
        vector = normalized["vector_identity"]
        if (
            vector.get("asset_status") != "development_only"
            or vector.get("vector_status") != "candidate_only"
        ):
            raise RunManifestError("development-only vector identity must remain candidate_only")
        lifecycle = normalized["lifecycle"]
        if (
            lifecycle.get("behavior_released") is not True
            or lifecycle.get("judge_loaded_after_behavior_release") is not True
            or lifecycle.get("models_concurrently_resident") is not False
        ):
            raise RunManifestError("real backend lifecycle is not sequential")
        lineage = normalized.get("execution_lineage")
        if require_execution_lineage:
            lineage_fields = {
                "schema_version", "generation_record_count", "judge_record_count",
                "generation_records_sha256", "judge_records_sha256", "fake_backend",
                "logical_identity_count", "registry_sha256",
            }
            if not isinstance(lineage, Mapping) or set(lineage) != lineage_fields:
                raise RunManifestError("development backend execution_lineage fields differ")
            if (
                lineage["schema_version"] != "paper1-stage3-real-execution-lineage-v1"
                or lineage["fake_backend"] is not False
            ):
                raise RunManifestError("development backend execution lineage is not real")
            for field in (
                "generation_record_count", "judge_record_count", "logical_identity_count",
            ):
                value = lineage[field]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise RunManifestError(f"execution_lineage.{field} is invalid")
            for field in (
                "generation_records_sha256", "judge_records_sha256", "registry_sha256",
            ):
                value = lineage[field]
                if (
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(character not in "0123456789abcdef" for character in value)
                ):
                    raise RunManifestError(f"execution_lineage.{field} is not a SHA256")
            output_identity = normalized.get("output_identity")
            if not isinstance(output_identity, Mapping):
                raise RunManifestError("development backend output_identity is missing")
            for field in (
                "generation_records_sha256", "judge_records_sha256", "registry_sha256",
            ):
                if output_identity.get(field) != lineage[field]:
                    raise RunManifestError(
                        f"backend output_identity differs from execution_lineage: {field}"
                    )
            capability_provenance = normalized.get("runtime_capability_provenance")
            if (
                not isinstance(capability_provenance, Mapping)
                or set(capability_provenance) != {"behavior", "judge"}
            ):
                raise RunManifestError(
                    "development backend runtime capability provenance fields differ"
                )
            capability_fields = {
                "schema_version", "role", "identity_digest",
                "issuance_source", "loader_path",
            }
            for role in ("behavior", "judge"):
                record = capability_provenance[role]
                if not isinstance(record, Mapping) or set(record) != capability_fields:
                    raise RunManifestError(
                        f"development {role} capability provenance fields differ"
                    )
                digest = record["identity_digest"]
                if (
                    record["schema_version"]
                    != "paper1-stage3-runtime-capability-provenance-v1"
                    or record["role"] != role
                    or not isinstance(digest, str)
                    or len(digest) != 64
                    or any(character not in "0123456789abcdef" for character in digest)
                    or not isinstance(record["issuance_source"], str)
                    or not record["issuance_source"]
                    or not isinstance(record["loader_path"], str)
                    or not record["loader_path"]
                ):
                    raise RunManifestError(
                        f"development {role} capability provenance is invalid"
                    )
            if reconciliation is not None and (
                lineage["generation_record_count"]
                != reconciliation["generation_first_pass_calls"]
                or lineage["judge_record_count"]
                != reconciliation["judge_first_pass_calls"]
                or lineage["logical_identity_count"]
                != reconciliation["scheduled_logical_ids"]
                or lineage["registry_sha256"] != reconciliation["registry_sha256"]
            ):
                raise RunManifestError("backend execution lineage counts differ from reconciliation")
    return normalized


def _validate_real_execution_lineage(
    *,
    backend_identity: Mapping[str, Any],
    logical_registry: Mapping[str, Any] | None,
    generation_records: Sequence[Mapping[str, Any]] | None,
    judge_records: Sequence[Mapping[str, Any]] | None,
    reconciliation: Mapping[str, Any],
) -> dict[str, Any]:
    from .core import LogicalIdentityRegistry
    from .records import validate_generation_record, validate_judge_record

    registry_fields = {
        "schema_version", "protocol_version", "identity_count", "records", "registry_sha256",
    }
    if not isinstance(logical_registry, Mapping) or set(logical_registry) != registry_fields:
        raise RunManifestError("development real manifests require an exact logical registry")
    registry_records = logical_registry["records"]
    if not isinstance(registry_records, list) or not registry_records:
        raise RunManifestError("development logical registry records must be nonempty")
    reconstructed = LogicalIdentityRegistry()
    for item in registry_records:
        if not isinstance(item, Mapping) or set(item) != {"logical_id", "identity"}:
            raise RunManifestError("development logical registry record fields differ")
        logical_id = reconstructed.register(item["identity"])
        if item["logical_id"] != logical_id:
            raise RunManifestError("development logical registry ID differs from its identity")
    normalized_registry = reconstructed.manifest()
    if json.loads(canonical_json(dict(logical_registry))) != normalized_registry:
        raise RunManifestError("development logical registry manifest is not canonical")
    if normalized_registry["registry_sha256"] != reconciliation["registry_sha256"]:
        raise RunManifestError("development logical registry differs from reconciliation")
    if (
        not isinstance(generation_records, Sequence)
        or isinstance(generation_records, (str, bytes))
        or not isinstance(judge_records, Sequence)
        or isinstance(judge_records, (str, bytes))
    ):
        raise RunManifestError(
            "development real manifests require generation_records and judge_records"
        )
    generations = [validate_generation_record(record) for record in generation_records]
    judges = [validate_judge_record(record) for record in judge_records]
    if any(
        record["run_mode"] != reconciliation["run_mode"]
        for record in (*generations, *judges)
    ):
        raise RunManifestError("development record run mode differs from reconciliation")
    if len(generations) != reconciliation["generation_first_pass_calls"]:
        raise RunManifestError("generation record count differs from reconciliation")
    if len(judges) != reconciliation["judge_first_pass_calls"]:
        raise RunManifestError("judge record count differs from reconciliation")
    if any(record["fake_backend"] is not False for record in (*generations, *judges)):
        raise RunManifestError("development real manifest contains fake backend record lineage")
    generation_by_id: dict[str, Mapping[str, Any]] = {}
    for record in generations:
        logical_id = record["logical_id"]
        if logical_id in generation_by_id:
            raise RunManifestError("development generation lineage repeats a logical ID")
        generation_by_id[logical_id] = record
    registry_by_id = {
        item["logical_id"]: item["identity"] for item in normalized_registry["records"]
    }
    if set(generation_by_id) != set(registry_by_id):
        raise RunManifestError("development generation lineage differs from logical registry")
    for logical_id, record in generation_by_id.items():
        if record["identity_sha256"] != canonical_sha256(registry_by_id[logical_id]):
            raise RunManifestError("development generation identity differs from logical registry")
    behavior = backend_identity["behavior_identity"]
    vector = backend_identity["vector_identity"]
    hook = backend_identity["hook_identity"]
    behavior_fields = {
        "model_revision": behavior.get("model_revision"),
        "template_sha256": behavior.get("chat_template_sha256"),
        "layer": vector.get("layer"),
        "hook_site": vector.get("hook_site"),
    }
    if any(value is None for value in behavior_fields.values()):
        raise RunManifestError("development behavior/vector provenance is incomplete")
    if (
        hook.get("layer") != behavior_fields["layer"]
        or hook.get("hook_site") != behavior_fields["hook_site"]
        or hook.get("phase") != "decode-only"
        or hook.get("use_cache") is not True
    ):
        raise RunManifestError("development hook provenance differs from behavior identity")
    for identity in registry_by_id.values():
        for field, value in behavior_fields.items():
            if identity.get(field) != value:
                raise RunManifestError(
                    f"development logical identity differs from backend provenance: {field}"
                )
        expected_vector_id = None if identity.get("estimator") == "clean" else vector.get("vector_id")
        if identity.get("vector_id") != expected_vector_id:
            raise RunManifestError("development logical vector differs from backend provenance")
    judge_ids: set[str] = set()
    for record in judges:
        logical_id = record["logical_id"]
        if logical_id in judge_ids:
            raise RunManifestError("development judge lineage repeats a logical ID")
        judge_ids.add(logical_id)
        generation = generation_by_id.get(logical_id)
        if (
            generation is None
            or generation["generation_completed"] is not True
            or record["generation_record_sha256"] != generation["record_sha256"]
        ):
            raise RunManifestError("development judge lineage differs from generation lineage")
        judge_identity = backend_identity["judge_identity"]
        expected_judge_identity = {
            "model_path_or_id": judge_identity.get("resolved_model_path"),
            "tokenizer_path_or_id": judge_identity.get("resolved_tokenizer_path"),
            "rubric_sha256": judge_identity.get("rubric_sha256"),
        }
        if None in expected_judge_identity.values() or record["judge_identity"] != expected_judge_identity:
            raise RunManifestError("development judge record differs from backend provenance")
    return {
        "schema_version": "paper1-stage3-real-execution-lineage-v1",
        "generation_record_count": len(generations),
        "judge_record_count": len(judges),
        "generation_records_sha256": canonical_sha256(generations),
        "judge_records_sha256": canonical_sha256(judges),
        "logical_identity_count": len(normalized_registry["records"]),
        "registry_sha256": normalized_registry["registry_sha256"],
        "fake_backend": False,
    }


def _validate_runtime_capabilities(
    *,
    backend_identity: Mapping[str, Any],
    behavior_capability: VerifiedBackendCapability | None,
    judge_capability: VerifiedBackendCapability | None,
) -> dict[str, Any]:
    if not isinstance(behavior_capability, VerifiedBackendCapability):
        raise RunManifestError(
            "development-only real manifests require a builder-issued behavior capability"
        )
    if not isinstance(judge_capability, VerifiedBackendCapability):
        raise RunManifestError(
            "development-only real manifests require a builder-issued judge capability"
        )
    if behavior_capability.role != "behavior" or judge_capability.role != "judge":
        raise RunManifestError("runtime capability roles do not match backend roles")
    if not behavior_capability.matches_backend_identity(
        behavior_identity=backend_identity["behavior_identity"],
        vector_identity=backend_identity["vector_identity"],
        hook_identity=backend_identity["hook_identity"],
        judge_identity=backend_identity["judge_identity"],
    ):
        raise RunManifestError("behavior capability does not match backend identity")
    if not judge_capability.matches_backend_identity(
        behavior_identity=backend_identity["behavior_identity"],
        vector_identity=backend_identity["vector_identity"],
        hook_identity=backend_identity["hook_identity"],
        judge_identity=backend_identity["judge_identity"],
    ):
        raise RunManifestError("judge capability does not match backend identity")
    return {
        "behavior": behavior_capability.manifest_record(),
        "judge": judge_capability.manifest_record(),
    }


def build_run_manifest(
    *,
    repo_root: Path,
    run_mode: str,
    command: Sequence[str],
    started_at_utc: str,
    completed_at_utc: str,
    model_path_or_id: str,
    tokenizer_path_or_id: str,
    input_paths: Sequence[Path],
    generation_config: Mapping[str, Any],
    seed: int,
    gpu_identity: str | None,
    output_directory: Path,
    exit_status: str,
    exit_code: int,
    fake_backend: bool,
    reconciliation: VerifiedReconciliation,
    offline_guard: OfflineExecutionGuard,
    claimed_counts: Mapping[str, int] | None = None,
    runtime_versions: Mapping[str, str | None] | None = None,
    asset_status: str = "legacy_unspecified",
    formal_experiment_run: bool = False,
    backend_identity: Mapping[str, Any] | None = None,
    logical_registry: Mapping[str, Any] | None = None,
    generation_records: Sequence[Mapping[str, Any]] | None = None,
    judge_records: Sequence[Mapping[str, Any]] | None = None,
    behavior_capability: VerifiedBackendCapability | None = None,
    judge_capability: VerifiedBackendCapability | None = None,
) -> VerifiedRunManifest:
    mode = validate_run_mode(run_mode)
    if not isinstance(fake_backend, bool):
        raise RunManifestError("fake_backend must be boolean")
    if not isinstance(reconciliation, VerifiedReconciliation):
        raise RunManifestError("build requires a VerifiedReconciliation result")
    reconciliation_document = _validate_reconciliation(reconciliation.as_dict(), mode)
    if not isinstance(offline_guard, OfflineExecutionGuard):
        raise RunManifestError("build requires the closed run-level OfflineExecutionGuard")
    offline_report = _validate_offline_report(offline_guard.report)
    if claimed_counts is not None:
        expected = {field: reconciliation_document[field] for field in COUNT_FIELDS}
        if not isinstance(claimed_counts, Mapping) or dict(claimed_counts) != expected:
            raise RunManifestError("caller count claim differs from verified reconciliation")
    config = validate_generation_config(generation_config, run_mode=mode)
    if not isinstance(command, Sequence) or isinstance(command, (str, bytes)) or not command:
        raise RunManifestError("command must be a nonempty sequence")
    if any(not isinstance(part, str) or not part for part in command):
        raise RunManifestError("command entries must be nonempty strings")
    for field, value in (
        ("model_path_or_id", model_path_or_id),
        ("tokenizer_path_or_id", tokenizer_path_or_id),
    ):
        if not isinstance(value, str) or not value:
            raise RunManifestError(f"{field} must be a nonempty string")
    _timestamps(started_at_utc, completed_at_utc)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise RunManifestError("seed must be a nonnegative integer")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise RunManifestError("exit_code must be an integer")
    if exit_status not in {"success", "failure"} or (exit_status == "success") != (exit_code == 0):
        raise RunManifestError("exit_status and exit_code disagree")
    if exit_status == "success" and offline_report["blocked_attempt_count"] != 0:
        raise RunManifestError("successful offline run contains blocked external attempts")
    if mode == "paper" and seed != MASTER_SEED:
        raise RunManifestError("paper seed differs from the current scientific design")
    versions = dict(collect_runtime_versions() if runtime_versions is None else runtime_versions)
    if set(versions) != {"python", "torch", "transformers", "cuda"}:
        raise RunManifestError("runtime_versions fields differ")
    if gpu_identity is not None and (not isinstance(gpu_identity, str) or not gpu_identity):
        raise RunManifestError("gpu_identity must be a nonempty string or null")
    if asset_status not in {"legacy_unspecified", "development_only", "paper_locked"}:
        raise RunManifestError("asset_status is invalid")
    if not isinstance(formal_experiment_run, bool):
        raise RunManifestError("formal_experiment_run must be boolean")
    if asset_status == "development_only" and (
        mode != "smoke" or formal_experiment_run or fake_backend
    ):
        raise RunManifestError(
            "development-only assets require smoke, fake_backend=false, formal_experiment_run=false"
        )
    backend = _validate_backend_identity(
        backend_identity,
        fake_backend=bool(fake_backend),
        asset_status=asset_status,
        run_mode=mode,
        reconciliation=reconciliation_document,
        require_execution_lineage=False,
    )
    if asset_status == "development_only":
        assert backend is not None
        execution_lineage = _validate_real_execution_lineage(
            backend_identity=backend,
            logical_registry=logical_registry,
            generation_records=generation_records,
            judge_records=judge_records,
            reconciliation=reconciliation_document,
        )
        capability_provenance = _validate_runtime_capabilities(
            backend_identity=backend,
            behavior_capability=behavior_capability,
            judge_capability=judge_capability,
        )
        existing_lineage = backend.get("execution_lineage")
        if existing_lineage is not None and existing_lineage != execution_lineage:
            raise RunManifestError("caller execution_lineage differs from validated records")
        backend["execution_lineage"] = execution_lineage
        existing_capabilities = backend.get("runtime_capability_provenance")
        if existing_capabilities is not None and existing_capabilities != capability_provenance:
            raise RunManifestError("caller runtime capability provenance differs from capabilities")
        backend["runtime_capability_provenance"] = capability_provenance
        _validate_backend_identity(
            backend,
            fake_backend=bool(fake_backend),
            asset_status=asset_status,
            run_mode=mode,
            reconciliation=reconciliation_document,
        )
    document = {
        "schema_version": RUN_MANIFEST_SCHEMA,
        "run_mode": mode,
        "paper_result_eligible": False,
        "fake_backend": bool(fake_backend),
        "asset_status": asset_status,
        "formal_experiment_run": formal_experiment_run,
        "backend_identity": backend,
        **git_repository_state(repo_root),
        "command": list(command),
        "started_at_utc": started_at_utc,
        "completed_at_utc": completed_at_utc,
        "model_path_or_id": model_path_or_id,
        "tokenizer_path_or_id": tokenizer_path_or_id,
        "inputs": _input_records(input_paths),
        "generation_config": config,
        "seed": seed,
        "runtime_versions": versions,
        "gpu_identity": gpu_identity,
        "output_directory": str(output_directory.resolve()),
        "exit_status": exit_status,
        "exit_code": exit_code,
        "offline_guard_report": offline_report,
        "reconciliation": reconciliation_document,
    }
    validated = validate_run_manifest(document)
    return VerifiedRunManifest(validated, _RUN_MANIFEST_TOKEN)


def validate_run_manifest(document: Mapping[str, Any]) -> dict[str, Any]:
    legacy_required = {
        "schema_version", "run_mode", "paper_result_eligible", "fake_backend",
        "git_commit", "dirty", "command", "started_at_utc", "completed_at_utc",
        "model_path_or_id", "tokenizer_path_or_id", "inputs", "generation_config",
        "seed", "runtime_versions", "gpu_identity", "output_directory", "exit_status",
        "exit_code", "offline_guard_report", "reconciliation",
    }
    current_required = legacy_required | {
        "asset_status", "formal_experiment_run", "backend_identity",
    }
    if not isinstance(document, Mapping):
        raise RunManifestError("run manifest must be an object")
    schema_version = document.get("schema_version")
    required = legacy_required if schema_version == LEGACY_RUN_MANIFEST_SCHEMA else current_required
    if set(document) != required:
        raise RunManifestError("run manifest fields differ")
    if schema_version not in {RUN_MANIFEST_SCHEMA, LEGACY_RUN_MANIFEST_SCHEMA}:
        raise RunManifestError("run manifest schema_version mismatch")
    mode = validate_run_mode(document["run_mode"])
    if document["paper_result_eligible"] is not False:
        raise RunManifestError("raw run manifests are not paper-result eligible")
    if not isinstance(document["fake_backend"], bool) or not isinstance(document["dirty"], bool):
        raise RunManifestError("fake_backend and dirty must be boolean")
    commit = document["git_commit"]
    if not isinstance(commit, str) or len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise RunManifestError("git_commit must be a full lowercase SHA1")
    command = document["command"]
    if not isinstance(command, list) or not command or any(not isinstance(part, str) or not part for part in command):
        raise RunManifestError("command must be a nonempty list of strings")
    _timestamps(document["started_at_utc"], document["completed_at_utc"])
    for field in ("model_path_or_id", "tokenizer_path_or_id", "output_directory"):
        if not isinstance(document[field], str) or not document[field]:
            raise RunManifestError(f"{field} must be a nonempty string")
    if not Path(document["output_directory"]).is_absolute():
        raise RunManifestError("output_directory must be absolute")
    validate_generation_config(document["generation_config"], run_mode=mode)
    inputs = document["inputs"]
    if not isinstance(inputs, list) or not inputs:
        raise RunManifestError("inputs must be a nonempty list")
    paths: list[str] = []
    for item in inputs:
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise RunManifestError("input manifest entry fields differ")
        if not isinstance(item["path"], str) or not Path(item["path"]).is_absolute():
            raise RunManifestError("input manifest path must be absolute")
        value = item["sha256"]
        if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise RunManifestError("input SHA256 is invalid")
        paths.append(item["path"])
    if len(paths) != len(set(paths)):
        raise RunManifestError("input paths must be unique")
    if isinstance(document["seed"], bool) or not isinstance(document["seed"], int) or document["seed"] < 0:
        raise RunManifestError("seed must be a nonnegative integer")
    if mode == "paper" and document["seed"] != MASTER_SEED:
        raise RunManifestError("paper seed differs from the current scientific design")
    if isinstance(document["exit_code"], bool) or not isinstance(document["exit_code"], int):
        raise RunManifestError("exit_code must be an integer")
    if document["exit_status"] not in {"success", "failure"} or (document["exit_status"] == "success") != (document["exit_code"] == 0):
        raise RunManifestError("exit_status and exit_code disagree")
    report = _validate_offline_report(document["offline_guard_report"])
    if document["exit_status"] == "success" and report["blocked_attempt_count"] != 0:
        raise RunManifestError("successful run contains blocked external attempts")
    _validate_reconciliation(document["reconciliation"], mode)
    versions = document["runtime_versions"]
    if not isinstance(versions, Mapping) or set(versions) != {"python", "torch", "transformers", "cuda"}:
        raise RunManifestError("runtime_versions fields differ")
    if not isinstance(versions["python"], str) or not versions["python"]:
        raise RunManifestError("runtime_versions.python must be a nonempty string")
    for field in ("torch", "transformers", "cuda"):
        if versions[field] is not None and (not isinstance(versions[field], str) or not versions[field]):
            raise RunManifestError(f"runtime_versions.{field} must be a nonempty string or null")
    gpu = document["gpu_identity"]
    if gpu is not None and (not isinstance(gpu, str) or not gpu):
        raise RunManifestError("gpu_identity must be a nonempty string or null")
    if schema_version == RUN_MANIFEST_SCHEMA:
        asset_status = document["asset_status"]
        if asset_status not in {"legacy_unspecified", "development_only", "paper_locked"}:
            raise RunManifestError("asset_status is invalid")
        formal = document["formal_experiment_run"]
        if not isinstance(formal, bool):
            raise RunManifestError("formal_experiment_run must be boolean")
        if asset_status == "development_only" and (
            mode != "smoke"
            or document["paper_result_eligible"] is not False
            or formal is not False
            or document["fake_backend"] is not False
        ):
            raise RunManifestError("development-only manifest flags are inconsistent")
        _validate_backend_identity(
            document["backend_identity"],
            fake_backend=document["fake_backend"],
            asset_status=asset_status,
            run_mode=mode,
            reconciliation=document["reconciliation"],
        )
    return json.loads(canonical_json(dict(document)))


def validate_manifest_for_paper_loader(document: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed when a raw run manifest is presented as a paper result."""
    validated = validate_run_manifest(document)
    if validated.get("asset_status") == "development_only":
        raise RunManifestError("development-only assets are excluded from the paper loader")
    raise RunManifestError(
        "raw run manifests are never paper-result eligible; a separate locked paper-result "
        "artifact is required"
    )


def write_run_manifest(output_directory: Path, document: VerifiedRunManifest) -> Path:
    if not isinstance(document, VerifiedRunManifest):
        raise RunManifestError("writer requires a builder-issued VerifiedRunManifest")
    validated = validate_run_manifest(document.as_dict())
    if not isinstance(output_directory, Path):
        raise RunManifestError("writer output_directory must be a pathlib.Path")
    output = output_directory.resolve()
    declared_output = Path(validated["output_directory"]).resolve()
    if output != declared_output:
        raise RunManifestError(
            "writer output_directory differs from the verified manifest output_directory"
        )
    output.mkdir(parents=True, exist_ok=True)
    path = output / "run_manifest.json"
    if path.exists() or path.is_symlink():
        raise RunManifestError(f"refusing to overwrite run manifest: {path}")
    payload = json.dumps(validated, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
    return path
