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
    canonical_json,
    file_sha256,
    validate_generation_config,
    validate_run_mode,
)
from .execution import BLOCK_BUDGET, TERMINAL_DISPOSITIONS, VerifiedReconciliation


RUN_MANIFEST_SCHEMA = "paper1-stage3-run-manifest-v2"
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
) -> VerifiedRunManifest:
    mode = validate_run_mode(run_mode)
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
    document = {
        "schema_version": RUN_MANIFEST_SCHEMA,
        "run_mode": mode,
        "paper_result_eligible": False,
        "fake_backend": bool(fake_backend),
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
    required = {
        "schema_version", "run_mode", "paper_result_eligible", "fake_backend",
        "git_commit", "dirty", "command", "started_at_utc", "completed_at_utc",
        "model_path_or_id", "tokenizer_path_or_id", "inputs", "generation_config",
        "seed", "runtime_versions", "gpu_identity", "output_directory", "exit_status",
        "exit_code", "offline_guard_report", "reconciliation",
    }
    if not isinstance(document, Mapping) or set(document) != required:
        raise RunManifestError("run manifest fields differ")
    if document["schema_version"] != RUN_MANIFEST_SCHEMA:
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
    return json.loads(canonical_json(dict(document)))


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
