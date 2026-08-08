"""Production runner for the fixed Paper 1 Stage 3 P2 identity subset."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from scripts.stage3_production.validate_stage3_development_inputs import (
    _strict_json_object,
    validate_development_inputs,
)

from .core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    PAPER_LOGICAL_GENERATION,
    GenerationProducer,
    IdentityError,
    PipelineError,
    canonical_json,
    canonical_sha256,
    file_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
)
from .dose import validate_dose_binding
from .execution import (
    OutputStore,
    TERMINAL_DISPOSITIONS,
    response_terminal_disposition,
    validate_execution_disposition,
)
from .offline_assets import strict_json_loads
from .real_backend import RealBehaviorBackend, inspect_local_model_assets
from .real_judge import RealJudgeBackend
from .records import (
    RecordSchemaError,
    build_block_response_record,
    validate_generation_record,
    validate_judge_record,
    validate_p2_materialization,
    validate_p2_record,
)
from .support_screen import (
    PreparedSupportScreen,
    load_real_behavior_backend as load_support_behavior_backend,
    load_real_judge_backend as load_support_judge_backend,
    prepare_support_screen,
    reconcile_support_stage,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/stage3/qwen25_p2_v1.json"
OUTPUT_ROOT = Path("/data/goodtaste_workspace/paper1_stage3_runs")
P1_RESULT = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "p1-qwen25-paper-20260807T044847Z/p1_measurement_result.json"
)
SUPPORT_RUN = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "support-qwen25-paper-detached-20260807T133730Z"
)
SUPPORT_CONFIG = "configs/stage3/qwen25_support_screen_v1.json"
CONFIRM_FRAME = "configs/stage3/jbb_behavior_confirm_v1.json"
P2_VECTOR_INDICES = tuple(range(10, 30))
P2_CELLS = (
    ("P2_A_all", "A", "mu_all_tw"),
    ("P2_A_content", "A", "mu_content_tw"),
    ("P2_T_all", "T", "mu_all_tw"),
    ("P2_T_content", "T", "mu_content_tw"),
)
P2_BLOCKS = tuple(cell[0] for cell in P2_CELLS)
P2_IDENTITY_COUNT = 4_000
PRIOR_SUPPORT_TERMINAL = 900
DOWNSTREAM_REMAINING = 680
SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

SUPPORT_FILE_SCHEMAS = {
    "execution_dispositions.json": "paper1-stage3-support-disposition-set-v1",
    "generation_records.json": "paper1-stage3-support-generation-set-v1",
    "judge_records.json": "paper1-stage3-support-judge-set-v1",
    "response_records.json": "paper1-stage3-support-response-set-v1",
    "support_identities.json": "paper1-stage3-support-identity-set-v1",
}
SUPPORT_FILES = (
    "execution_dispositions.json",
    "execution_identity.json",
    "generation_records.json",
    "judge_records.json",
    "logical_registry.json",
    "response_records.json",
    "support_identities.json",
    "support_ledger.json",
)
CONFIG_FIELDS = (
    "schema_version",
    "status",
    "run_mode",
    "paper_result_eligible",
    "formal_experiment_run",
    "canonical_plan_count",
    "p2_identity_count",
    "p1_measurement_result",
    "support_run_directory",
    "support_config_relative_path",
    "confirmation_prompt_frame",
    "vector_confirm_indices",
    "cells",
    "generation_config",
    "judge_config",
    "output_root",
)


@dataclass(frozen=True)
class PreparedP2Runner:
    """Validated formal inputs and the original P2 subset of the support registry."""

    config_path: Path
    config: Mapping[str, Any]
    support: PreparedSupportScreen
    support_run_directory: Path
    support_ledger: Mapping[str, Any]
    support_execution_identity: Mapping[str, Any]
    support_statuses: Mapping[str, str]
    p2_rows: tuple[Mapping[str, Any], ...]
    offline_guard_report: Mapping[str, Any]


@dataclass(frozen=True)
class P2RunArtifacts:
    """Records and metadata materialized only for the 4,000 P2 identities."""

    generation_records: tuple[Mapping[str, Any], ...]
    judge_records: tuple[Mapping[str, Any], ...]
    response_records: tuple[Mapping[str, Any], ...]
    dispositions: tuple[Mapping[str, Any], ...]
    p2_ledger: Mapping[str, Any]
    behavior_lifecycle: Mapping[str, Any]
    judge_lifecycle: Mapping[str, Any]
    offline_guard_report: Mapping[str, Any]


def _exact_fields(value: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or tuple(value) != fields:
        raise PipelineError(f"{label} exact ordered fields mismatch")
    return dict(value)


def _resolve_repo_file(repo_root: Path, relative_value: Any, field: str) -> Path:
    if (
        not isinstance(relative_value, str)
        or not relative_value
        or "\\" in relative_value
        or "://" in relative_value
    ):
        raise PipelineError(f"{field} must be a local POSIX relative path")
    relative = PurePosixPath(relative_value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise PipelineError(f"{field} must remain below the repository root")
    root = repo_root.resolve()
    path = (root / Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PipelineError(f"{field} escapes the repository root") from exc
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"{field} is not a regular local file")
    return path


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"{label} must be a regular non-symlink file")
    try:
        value = strict_json_loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PipelineError(f"unable to read strict {label}: {path}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"{label} must be an object")
    return value


def validate_p2_config(config: Mapping[str, Any]) -> dict[str, Any]:
    actual = _exact_fields(config, CONFIG_FIELDS, "P2 config")
    expected = {
        "schema_version": "paper1-stage3-qwen25-p2-runner-v1",
        "status": "p2_runner_ready",
        "run_mode": "paper",
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "canonical_plan_count": PAPER_LOGICAL_GENERATION,
        "p2_identity_count": P2_IDENTITY_COUNT,
        "p1_measurement_result": str(P1_RESULT),
        "support_run_directory": str(SUPPORT_RUN),
        "support_config_relative_path": SUPPORT_CONFIG,
        "confirmation_prompt_frame": CONFIRM_FRAME,
        "vector_confirm_indices": list(P2_VECTOR_INDICES),
        "cells": [
            {"cell": cell, "anchor": anchor, "estimator": estimator, "count": 1_000}
            for cell, anchor, estimator in P2_CELLS
        ],
        "generation_config": DECODE_CONFIG,
        "judge_config": JUDGE_CONFIG,
        "output_root": str(OUTPUT_ROOT),
    }
    for field, expected_value in expected.items():
        if actual[field] != expected_value or type(actual[field]) is not type(expected_value):
            raise PipelineError(f"P2 config {field} mismatch")
    return actual


def _record_document(
    document: Mapping[str, Any], *, schema_version: str, count: int, label: str
) -> list[dict[str, Any]]:
    if not isinstance(document, Mapping) or set(document) != {
        "schema_version", "record_count", "records"
    }:
        raise PipelineError(f"{label} document fields mismatch")
    records = document.get("records")
    if (
        document.get("schema_version") != schema_version
        or type(document.get("record_count")) is not int
        or document["record_count"] != count
        or not isinstance(records, list)
        or len(records) != count
    ):
        raise PipelineError(f"{label} document metadata mismatch")
    if any(not isinstance(record, Mapping) for record in records):
        raise PipelineError(f"{label} contains a non-object record")
    return [dict(record) for record in records]


def _load_support_documents(directory: Path) -> dict[str, dict[str, Any]]:
    resolved = directory.resolve()
    if resolved != SUPPORT_RUN.resolve() or not resolved.is_dir() or resolved.is_symlink():
        raise PipelineError("P2 must bind the one fixed successful support run")
    documents: dict[str, dict[str, Any]] = {}
    for name in SUPPORT_FILES:
        documents[name] = _read_json(resolved / name, f"support {name}")
    return documents


def _validate_support_execution_identity(
    document: Mapping[str, Any], *, registry_sha256: str, ledger: Mapping[str, Any]
) -> dict[str, Any]:
    fields = {
        "schema_version", "run_id", "run_mode", "fake_backend",
        "paper_result_eligible", "formal_experiment_run", "real_support_run", "p2_run",
        "canonical_registry_sha256", "support_ledger_sha256", "behavior_lifecycle",
        "judge_lifecycle",
    }
    if not isinstance(document, Mapping) or set(document) != fields:
        raise PipelineError("support execution identity fields mismatch")
    expected = {
        "schema_version": "paper1-stage3-support-screen-execution-v1",
        "run_id": SUPPORT_RUN.name,
        "run_mode": "paper",
        "fake_backend": False,
        "paper_result_eligible": False,
        "formal_experiment_run": True,
        "real_support_run": True,
        "p2_run": False,
        "canonical_registry_sha256": registry_sha256,
        "support_ledger_sha256": canonical_sha256(ledger),
    }
    for field, expected_value in expected.items():
        if document.get(field) != expected_value or type(document.get(field)) is not type(expected_value):
            raise PipelineError(f"support execution identity {field} mismatch")
    for field in ("behavior_lifecycle", "judge_lifecycle"):
        if not isinstance(document.get(field), Mapping):
            raise PipelineError(f"support execution identity {field} must be an object")
    return json.loads(canonical_json(dict(document)))


def select_p2_identities(
    support: PreparedSupportScreen,
) -> tuple[Mapping[str, Any], ...]:
    """Select the original four P2 cells without constructing new identities."""
    if len(support.registry) != PAPER_LOGICAL_GENERATION:
        raise IdentityError("P2 selection requires the complete 5,580-ID registry")
    rows = tuple(
        row for row in support.registry.records() if row["identity"]["block"] in P2_BLOCKS
    )
    if len(rows) != P2_IDENTITY_COUNT or len({row["logical_id"] for row in rows}) != len(rows):
        raise IdentityError("P2 selection must contain exactly 4,000 unique existing IDs")
    expected_prompts = set(support.plan_inputs["confirm_prompt_ids"])
    expected_vectors = {
        support.vector_ids_by_index[index] for index in P2_VECTOR_INDICES
    }
    if len(expected_prompts) != 50 or len(expected_vectors) != 20:
        raise IdentityError("P2 prompt/vector source frame changed")
    doses = validate_dose_binding(support.dose_binding)
    pair_cells: dict[str, set[str]] = {}
    for cell, anchor, estimator in P2_CELLS:
        identities = [row["identity"] for row in rows if row["identity"]["block"] == cell]
        pairs = {(item["prompt_id"], item["vector_id"]) for item in identities}
        if (
            len(identities) != 1_000
            or {item["prompt_id"] for item in identities} != expected_prompts
            or {item["vector_id"] for item in identities} != expected_vectors
            or pairs != {
                (prompt_id, vector_id)
                for prompt_id in expected_prompts
                for vector_id in expected_vectors
            }
            or any(
                item["anchor"] != anchor
                or item["estimator"] != estimator
                or item["split"] != "D_behavior_confirm"
                or item["domain"] != "harmful"
                or item["c_hex"] != doses[anchor][estimator]["c_hex"]
                for item in identities
            )
        ):
            raise IdentityError(f"{cell} differs from its fixed 50x20 registry cell")
        for item in identities:
            pair_id = f"{anchor}|{item['prompt_id']}|{item['vector_id']}"
            pair_cells.setdefault(pair_id, set()).add(cell)
    expected_pair_cells = {
        "A": {"P2_A_all", "P2_A_content"},
        "T": {"P2_T_all", "P2_T_content"},
    }
    if (
        len(pair_cells) != 2_000
        or any(cells != expected_pair_cells[pair_id.split("|", 1)[0]] for pair_id, cells in pair_cells.items())
    ):
        raise IdentityError("P2 paired arms do not share the fixed pair IDs")
    return rows


def prepare_p2_runner(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> PreparedP2Runner:
    """Validate formal P1/support assets and bind their canonical P2 subset."""
    root = repo_root.resolve()
    resolved_config = config_path.resolve()
    config = validate_p2_config(_strict_json_object(resolved_config, "P2 config"))
    p1_path = Path(config["p1_measurement_result"]).resolve()
    if p1_path != P1_RESULT.resolve() or not p1_path.is_file() or p1_path.is_symlink():
        raise PipelineError("P2 formal P1 result path is not the fixed regular file")
    support_config_path = _resolve_repo_file(
        root, config["support_config_relative_path"], "support config"
    )
    guard = offline_execution_guard()
    with guard:
        support = prepare_support_screen(
            support_config_path,
            repo_root=root,
            model_asset_inspector=model_asset_inspector,
            development_validator=development_validator,
        )
        configured_p1 = Path(
            support.development["p1_measurement_and_dose"]["measurement_result_dose_manifest"]
        ).resolve()
        if configured_p1 != p1_path:
            raise PipelineError("support registry dose source differs from the fixed formal P1 result")
        if support.config["prompt_frames"]["confirmation"] != config["confirmation_prompt_frame"]:
            raise PipelineError("P2 confirmation prompt frame differs from the support registry")
        documents = _load_support_documents(Path(config["support_run_directory"]))
        expected_registry = support.registry.manifest()
        if documents["logical_registry.json"] != expected_registry:
            raise IdentityError("stored support registry differs from the reconstructed 5,580-ID registry")
        support_identities = _record_document(
            documents["support_identities.json"],
            schema_version=SUPPORT_FILE_SCHEMAS["support_identities.json"],
            count=PRIOR_SUPPORT_TERMINAL,
            label="support identity set",
        )
        if support_identities != list(support.support_rows):
            raise IdentityError("stored support identities differ from the canonical registry subset")
        generations = _record_document(
            documents["generation_records.json"],
            schema_version=SUPPORT_FILE_SCHEMAS["generation_records.json"],
            count=PRIOR_SUPPORT_TERMINAL,
            label="support generation set",
        )
        judges = _record_document(
            documents["judge_records.json"],
            schema_version=SUPPORT_FILE_SCHEMAS["judge_records.json"],
            count=PRIOR_SUPPORT_TERMINAL,
            label="support judge set",
        )
        responses = _record_document(
            documents["response_records.json"],
            schema_version=SUPPORT_FILE_SCHEMAS["response_records.json"],
            count=PRIOR_SUPPORT_TERMINAL,
            label="support response set",
        )
        dispositions = _record_document(
            documents["execution_dispositions.json"],
            schema_version=SUPPORT_FILE_SCHEMAS["execution_dispositions.json"],
            count=PRIOR_SUPPORT_TERMINAL,
            label="support disposition set",
        )
        recomputed_ledger = reconcile_support_stage(
            support,
            generation_records=generations,
            judge_records=judges,
            response_records=responses,
            dispositions=dispositions,
        )
        if documents["support_ledger.json"] != recomputed_ledger:
            raise PipelineError("stored support ledger differs from independent reconciliation")
        execution_identity = _validate_support_execution_identity(
            documents["execution_identity.json"],
            registry_sha256=expected_registry["registry_sha256"],
            ledger=recomputed_ledger,
        )
        statuses = {
            anchor: recomputed_ledger["anchors"][anchor]["status"]
            for anchor in ("A", "T", "H")
        }
        if statuses["A"] != "SUPPORTED" or statuses["T"] != "SUPPORTED":
            raise PipelineError("fixed formal support run must independently rederive A/T as SUPPORTED")
        p2_rows = select_p2_identities(support)
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("P2 validation attempted a forbidden offline operation")
    return PreparedP2Runner(
        config_path=resolved_config,
        config=config,
        support=support,
        support_run_directory=SUPPORT_RUN.resolve(),
        support_ledger=recomputed_ledger,
        support_execution_identity=execution_identity,
        support_statuses=statuses,
        p2_rows=p2_rows,
        offline_guard_report=guard_report,
    )


def validate_only(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> dict[str, Any]:
    prepared = prepare_p2_runner(
        config_path,
        repo_root=repo_root,
        model_asset_inspector=model_asset_inspector,
        development_validator=development_validator,
    )
    return {
        "schema_version": "paper1-stage3-p2-runner-validation-v1",
        "status": "P2_RUNNER_VALIDATE_ONLY_PASS",
        "validate_only": True,
        "run_mode": "paper",
        "support_assets_read": len(SUPPORT_FILES),
        "support_ledger_reconciled": True,
        "stored_support_ledger_match": True,
        "canonical_registry_exact_match": True,
        "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": prepared.support.registry.manifest()["registry_sha256"],
        "p2_identity_count": len(prepared.p2_rows),
        "cell_identity_counts": {
            cell: sum(row["identity"]["block"] == cell for row in prepared.p2_rows)
            for cell in P2_BLOCKS
        },
        "confirmation_prompt_count": len(prepared.support.plan_inputs["confirm_prompt_ids"]),
        "vector_confirm_indices": list(P2_VECTOR_INDICES),
        "support_status": dict(prepared.support_statuses),
        "p1_primary_gate": prepared.support.p1_primary_gate,
        "p1_gate_changes_p2_identities": False,
        "prior_support_terminal": PRIOR_SUPPORT_TERMINAL,
        "p2_terminal": 0,
        "downstream_remaining": P2_IDENTITY_COUNT + DOWNSTREAM_REMAINING,
        "model_weights_loaded": False,
        "forward_executed": False,
        "generation_run": False,
        "judge_run": False,
        "support_run": False,
        "p2_run": False,
        "fake_backend": False,
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "complete_stage3_reconciliation": False,
        "offline_guard_report": prepared.offline_guard_report,
        "network_attempts": prepared.offline_guard_report["category_counts"]["network"],
        "blocked_attempts": prepared.offline_guard_report["blocked_attempt_count"],
    }


def _record_index(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    validator: Callable[[Mapping[str, Any]], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = validator(raw)
        logical_id = record.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in indexed:
            raise IdentityError(f"{label} contains a missing or duplicate logical ID")
        indexed[logical_id] = record
    return indexed


def _unattempted_disposition(
    logical_id: str, identity: Mapping[str, Any], support_status: str
) -> dict[str, Any]:
    if support_status != "NON_ESTIMABLE_IDENTITY":
        raise PipelineError("only non-estimable support may block a fixed P2 identity")
    reason = {
        "A": "SUPPORT_A_NON_ESTIMABLE_IDENTITY",
        "T": "SUPPORT_T_NON_ESTIMABLE_IDENTITY",
    }[identity["anchor"]]
    return validate_execution_disposition({
        "schema_version": "paper1-stage3-execution-disposition-v2",
        "logical_id": logical_id,
        "identity_sha256": canonical_sha256(identity),
        "terminal_disposition": "UNATTEMPTED_DUE_INTEGRITY_BLOCK",
        "generation_record_sha256": None,
        "judge_record_sha256": None,
        "response_record_sha256": None,
        "integrity_block_reason": reason,
    })


def _attempted_disposition(
    identity: Mapping[str, Any],
    generation: Mapping[str, Any],
    judge: Mapping[str, Any] | None,
    response: Mapping[str, Any],
) -> dict[str, Any]:
    return validate_execution_disposition({
        "schema_version": "paper1-stage3-execution-disposition-v2",
        "logical_id": generation["logical_id"],
        "identity_sha256": canonical_sha256(identity),
        "terminal_disposition": response_terminal_disposition(
            identity, response, generation, judge
        ),
        "generation_record_sha256": generation["record_sha256"],
        "judge_record_sha256": None if judge is None else judge["record_sha256"],
        "response_record_sha256": response["record_sha256"],
        "integrity_block_reason": None,
    })


def reconcile_p2_stage(
    prepared: PreparedP2Runner,
    *,
    generation_records: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    expected_fake_backend: bool | None = None,
) -> dict[str, Any]:
    """Validate the fixed P2 terminal partition without completing Stage 3."""
    if expected_fake_backend is not None and type(expected_fake_backend) is not bool:
        raise PipelineError("expected_fake_backend must be boolean or omitted")
    p2_by_id = {row["logical_id"]: row["identity"] for row in prepared.p2_rows}
    if len(p2_by_id) != P2_IDENTITY_COUNT:
        raise IdentityError("P2 reconciliation requires exactly 4,000 canonical IDs")
    statuses = dict(prepared.support_statuses)
    if set(statuses) != {"A", "T", "H"} or any(
        status not in {"SUPPORTED", "SUPPORT_LIMITED", "NON_ESTIMABLE_IDENTITY"}
        for status in statuses.values()
    ):
        raise PipelineError("P2 support statuses are invalid")
    attempted_ids = {
        logical_id
        for logical_id, identity in p2_by_id.items()
        if statuses[identity["anchor"]] != "NON_ESTIMABLE_IDENTITY"
    }
    generations = _record_index(
        generation_records, label="P2 generation set", validator=validate_generation_record
    )
    judges = _record_index(
        judge_records, label="P2 judge set", validator=validate_judge_record
    )
    responses = _record_index(
        response_records, label="P2 response set", validator=validate_p2_record
    )
    disposition_by_id = _record_index(
        dispositions, label="P2 disposition set", validator=validate_execution_disposition
    )
    for label, observed in (
        ("generation", set(generations)),
        ("response", set(responses)),
    ):
        if observed != attempted_ids:
            raise IdentityError(f"P2 {label} set must cover exactly the attempted fixed IDs")
    if set(disposition_by_id) != set(p2_by_id):
        raise IdentityError("P2 dispositions must cover exactly all 4,000 fixed IDs")
    completed_generation_ids = {
        logical_id for logical_id, record in generations.items()
        if record["generation_completed"]
    }
    if set(judges) != completed_generation_ids:
        raise IdentityError("P2 judge set must equal the completed-generation IDs")

    terminal_counts = {terminal: 0 for terminal in TERMINAL_DISPOSITIONS}
    fake_flags: set[bool] = set()
    for logical_id, identity in p2_by_id.items():
        disposition = disposition_by_id[logical_id]
        identity_sha256 = canonical_sha256(identity)
        if disposition["identity_sha256"] != identity_sha256:
            raise IdentityError("P2 disposition identity hash differs from the registry")
        if logical_id not in attempted_ids:
            expected = _unattempted_disposition(
                logical_id, identity, statuses[identity["anchor"]]
            )
            if disposition != expected:
                raise PipelineError("P2 unattempted disposition differs from support status")
            terminal_counts["UNATTEMPTED_DUE_INTEGRITY_BLOCK"] += 1
            continue
        generation = generations[logical_id]
        judge = judges.get(logical_id)
        try:
            response = validate_p2_materialization(
                responses[logical_id],
                registry=prepared.support.registry,
                generation_record=generation,
                judge_record=judge,
                dose_binding=prepared.support.dose_binding,
            )
        except RecordSchemaError as exc:
            raise PipelineError("P2 response materialization failed") from exc
        expected = _attempted_disposition(identity, generation, judge, response)
        if disposition != expected:
            raise PipelineError("P2 disposition differs from terminal record lineage")
        terminal_counts[expected["terminal_disposition"]] += 1
        fake_flags.add(generation["fake_backend"])
        fake_flags.add(response["fake_backend"])
        if judge is not None:
            fake_flags.add(judge["fake_backend"])
    if len(fake_flags) > 1:
        raise PipelineError("P2 stage mixes real and fake backend provenance")
    fake_backend = next(iter(fake_flags), False)
    if expected_fake_backend is not None and fake_backend is not expected_fake_backend:
        raise PipelineError("P2 backend provenance differs from orchestration")
    if sum(terminal_counts.values()) != P2_IDENTITY_COUNT:
        raise PipelineError("P2 terminal partition does not total 4,000")
    return {
        "schema_version": "paper1-stage3-p2-stage-ledger-v1",
        "run_mode": "paper",
        "stage": "P2",
        "paper_result_eligible": False,
        "fake_backend": fake_backend,
        "formal_experiment_run": not fake_backend,
        "p2_run": not fake_backend,
        "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": prepared.support.registry.manifest()["registry_sha256"],
        "p2_identity_count": len(prepared.p2_rows),
        "prior_support_terminal": PRIOR_SUPPORT_TERMINAL,
        "p2_terminal": len(disposition_by_id),
        "p2_attempted": len(generations),
        "p2_unattempted": P2_IDENTITY_COUNT - len(generations),
        "downstream_remaining": DOWNSTREAM_REMAINING,
        "support_records_rematerialized": 0,
        "remaining_dispositions_materialized": 0,
        "complete_stage3_reconciliation": False,
        "terminal_partition": terminal_counts,
        "cells": {
            cell: {
                "scheduled": sum(
                    identity["block"] == cell for identity in p2_by_id.values()
                ),
                "support_status": statuses[anchor],
                "estimation_only": statuses[anchor] == "SUPPORT_LIMITED",
            }
            for cell, anchor, _estimator in P2_CELLS
        },
        "k1_materialized": False,
        "k1_additional_generation_calls": 0,
        "k1_additional_judge_calls": 0,
    }


def _aggregate_behavior_lifecycle(
    lifecycles: Sequence[Mapping[str, Any]], *, expected_sessions: int
) -> dict[str, Any]:
    if len(lifecycles) != expected_sessions:
        raise PipelineError("behavior lifecycle does not cover all loaded P2 vector sessions")
    required = (
        "behavior_released", "behavior_hook_removed", "behavior_model_reference_cleared",
        "behavior_tokenizer_reference_cleared", "gc_collect_called",
    )
    if any(any(item.get(field) is not True for field in required) for item in lifecycles):
        raise PipelineError("a P2 behavior backend did not release completely")
    if any(item.get("models_concurrently_resident") is not False for item in lifecycles):
        raise PipelineError("P2 behavior lifecycle reported concurrent model residence")
    cuda_available = any(item.get("cuda_available") is True for item in lifecycles)
    return {
        "schema_version": "paper1-stage3-sequential-lifecycle-v1",
        "behavior_released": True,
        "behavior_hook_removed": True,
        "behavior_model_reference_cleared": True,
        "behavior_tokenizer_reference_cleared": True,
        "gc_collect_called": True,
        "gc_collected_count": sum(int(item.get("gc_collected_count", 0)) for item in lifecycles),
        "cuda_available": cuda_available,
        "cuda_synchronize_called": (
            all(item.get("cuda_synchronize_called") is True for item in lifecycles)
            if cuda_available else False
        ),
        "cuda_empty_cache_called": (
            all(item.get("cuda_empty_cache_called") is True for item in lifecycles)
            if cuda_available else False
        ),
        "judge_loaded_after_behavior_release": False,
        "models_concurrently_resident": False,
        "behavior_session_count": len(lifecycles),
    }


def load_real_behavior_backend(
    prepared: PreparedP2Runner, vector_index: int
) -> RealBehaviorBackend:
    return load_support_behavior_backend(prepared.support, vector_index)


def load_real_judge_backend(
    prepared: PreparedP2Runner, lifecycle: Mapping[str, Any]
) -> RealJudgeBackend:
    return load_support_judge_backend(prepared.support, lifecycle)


def execute_p2(
    prepared: PreparedP2Runner,
    *,
    behavior_backend_factory: Callable[[PreparedP2Runner, int], Any] = load_real_behavior_backend,
    judge_backend_factory: Callable[
        [PreparedP2Runner, Mapping[str, Any]], Any
    ] = load_real_judge_backend,
) -> P2RunArtifacts:
    """Run the shared real/fake P2 orchestration with sequential model residency."""
    generation_by_id: dict[str, dict[str, Any]] = {}
    behavior_lifecycles: list[Mapping[str, Any]] = []
    backend_fake_flags: set[bool] = set()
    loaded_behavior_sessions = 0
    guard = offline_execution_guard()
    with guard:
        for vector_index in P2_VECTOR_INDICES:
            expected_vector_id = prepared.support.vector_ids_by_index[vector_index]
            rows = [
                row for row in prepared.p2_rows
                if row["identity"]["vector_id"] == expected_vector_id
            ]
            if len(rows) != 200 or {
                cell: sum(row["identity"]["block"] == cell for row in rows)
                for cell in P2_BLOCKS
            } != {cell: 50 for cell in P2_BLOCKS}:
                raise IdentityError("each P2 vector must schedule the four fixed 50-prompt cells")
            attempted_rows = [
                row for row in rows
                if prepared.support_statuses[row["identity"]["anchor"]]
                != "NON_ESTIMABLE_IDENTITY"
            ]
            if not attempted_rows:
                continue
            backend = behavior_backend_factory(prepared, vector_index)
            loaded_behavior_sessions += 1
            capability = getattr(backend, "capability", None)
            backend_fake_flags.add(capability is None)
            try:
                producer = GenerationProducer(
                    prepared.support.registry,
                    backend,
                    run_mode="paper",
                    generation_config=DECODE_CONFIG,
                    fake_backend=capability is None,
                    capability=capability,
                    item_budget=PAPER_LOGICAL_GENERATION,
                )
                for row in attempted_rows:
                    logical_id = row["logical_id"]
                    identity = row["identity"]
                    if logical_id in generation_by_id:
                        raise IdentityError("P2 orchestration attempted an identity twice")
                    generation_by_id[logical_id] = validate_generation_record(
                        producer.produce(
                            logical_id,
                            {
                                "logical_id": logical_id,
                                "generation_config": DECODE_CONFIG,
                                "messages": prepared.support.messages_by_prompt_id[
                                    identity["prompt_id"]
                                ],
                            },
                        )
                    )
            finally:
                if not getattr(backend, "released", False):
                    behavior_lifecycles.append(backend.release())
        behavior_lifecycle = _aggregate_behavior_lifecycle(
            behavior_lifecycles, expected_sessions=loaded_behavior_sessions
        )

        judge_by_id: dict[str, dict[str, Any]] = {}
        if generation_by_id:
            judge_backend = judge_backend_factory(prepared, behavior_lifecycle)
            judge_capability = getattr(judge_backend, "capability", None)
            backend_fake_flags.add(judge_capability is None)
            try:
                producer_identity = getattr(judge_backend, "producer_identity", None)
                if not isinstance(producer_identity, Mapping):
                    raise PipelineError("judge backend lacks its canonical producer identity")
                for row in prepared.p2_rows:
                    logical_id = row["logical_id"]
                    generation = generation_by_id.get(logical_id)
                    if generation is None or not generation["generation_completed"]:
                        continue
                    identity = row["identity"]
                    judge_by_id[logical_id] = validate_judge_record(
                        parse_judge_with_retry(
                            logical_id,
                            judge_backend,
                            {
                                "logical_id": logical_id,
                                "judge_config": JUDGE_CONFIG,
                                "backend_request": {
                                    "prompt": prepared.support.prompt_text_by_id[
                                        identity["prompt_id"]
                                    ],
                                    "response": generation["output_text"],
                                    "domain": "harmful",
                                },
                            },
                            registry=prepared.support.registry,
                            generation_record=generation,
                            run_mode="paper",
                            judge_identity=producer_identity,
                            judge_config=JUDGE_CONFIG,
                            fake_backend=judge_capability is None,
                            capability=judge_capability,
                        )
                    )
            finally:
                judge_lifecycle = (
                    judge_backend.release()
                    if not getattr(judge_backend, "released", False)
                    else {"judge_released": True}
                )
        else:
            judge_lifecycle = {"judge_loaded": False, "judge_released": False}
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("P2 execution attempted a forbidden offline operation")
    if len(backend_fake_flags) > 1:
        raise PipelineError("P2 execution mixes real and fake backend sessions")
    fake_backend = next(iter(backend_fake_flags), False)

    generations: list[dict[str, Any]] = []
    judges: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for row in prepared.p2_rows:
        logical_id = row["logical_id"]
        identity = row["identity"]
        generation = generation_by_id.get(logical_id)
        if generation is None:
            dispositions.append(_unattempted_disposition(
                logical_id, identity, prepared.support_statuses[identity["anchor"]]
            ))
            continue
        judge = judge_by_id.get(logical_id)
        dose_evidence = generation["attempts"][-1]["diagnostics"].get("dose_evidence")
        response = build_block_response_record(
            identity=identity,
            generation_record=generation,
            judge_record=judge,
            dose_evidence=dose_evidence,
        )
        generations.append(generation)
        if judge is not None:
            judges.append(judge)
        responses.append(response)
        dispositions.append(_attempted_disposition(identity, generation, judge, response))
    ledger = reconcile_p2_stage(
        prepared,
        generation_records=generations,
        judge_records=judges,
        response_records=responses,
        dispositions=dispositions,
        expected_fake_backend=fake_backend,
    )
    return P2RunArtifacts(
        generation_records=tuple(generations),
        judge_records=tuple(judges),
        response_records=tuple(responses),
        dispositions=tuple(dispositions),
        p2_ledger=ledger,
        behavior_lifecycle=behavior_lifecycle,
        judge_lifecycle=judge_lifecycle,
        offline_guard_report=guard_report,
    )


def default_output_directory(prepared: PreparedP2Runner, run_id: str) -> Path:
    if not isinstance(run_id, str) or SAFE_RUN_ID.fullmatch(run_id) is None:
        raise PipelineError("P2 run-id contains invalid characters")
    configured_root = Path(prepared.config["output_root"]).resolve()
    if configured_root != OUTPUT_ROOT.resolve():
        raise PipelineError("P2 output root differs from the fixed paper root")
    return configured_root / run_id


def _reserve_output_directory(path: Path) -> Path:
    output = path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        raise PipelineError(f"refusing to overwrite output directory: {output}") from exc
    return output


def _output_record_document(
    schema_version: str, records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "record_count": len(records),
        "records": list(records),
    }


def run_prepared_p2(
    prepared: PreparedP2Runner,
    *,
    run_id: str,
    behavior_backend_factory: Callable[[PreparedP2Runner, int], Any] = load_real_behavior_backend,
    judge_backend_factory: Callable[
        [PreparedP2Runner, Mapping[str, Any]], Any
    ] = load_real_judge_backend,
    output_directory_resolver: Callable[
        [PreparedP2Runner, str], Path
    ] = default_output_directory,
) -> dict[str, Any]:
    output_directory = _reserve_output_directory(
        output_directory_resolver(prepared, run_id)
    )
    store = OutputStore(output_directory)
    artifacts = execute_p2(
        prepared,
        behavior_backend_factory=behavior_backend_factory,
        judge_backend_factory=judge_backend_factory,
    )
    registry_manifest = prepared.support.registry.manifest()
    registry_reference = {
        "schema_version": "paper1-stage3-canonical-registry-reference-v1",
        "source_support_run_directory": str(prepared.support_run_directory),
        "source_registry_file": "logical_registry.json",
        "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": registry_manifest["registry_sha256"],
        "p2_identity_count": len(prepared.p2_rows),
        "p2_identity_set_sha256": canonical_sha256(list(prepared.p2_rows)),
    }
    store.write_json_once("canonical_registry_reference.json", registry_reference)
    store.write_json_once(
        "p2_identities.json",
        _output_record_document("paper1-stage3-p2-identity-set-v1", prepared.p2_rows),
    )
    store.write_json_once(
        "generation_records.json",
        _output_record_document(
            "paper1-stage3-p2-generation-set-v1", artifacts.generation_records
        ),
    )
    store.write_json_once(
        "judge_records.json",
        _output_record_document("paper1-stage3-p2-judge-set-v1", artifacts.judge_records),
    )
    store.write_json_once(
        "response_records.json",
        _output_record_document("paper1-stage3-p2-response-set-v1", artifacts.response_records),
    )
    store.write_json_once(
        "execution_dispositions.json",
        _output_record_document(
            "paper1-stage3-p2-disposition-set-v1", artifacts.dispositions
        ),
    )
    store.write_json_once("p2_ledger.json", artifacts.p2_ledger)
    execution_identity = {
        "schema_version": "paper1-stage3-p2-execution-v1",
        "run_id": run_id,
        "run_mode": "paper",
        "fake_backend": artifacts.p2_ledger["fake_backend"],
        "paper_result_eligible": False,
        "formal_experiment_run": artifacts.p2_ledger["formal_experiment_run"],
        "p2_run": artifacts.p2_ledger["p2_run"],
        "support_run_id": prepared.support_execution_identity["run_id"],
        "canonical_registry_sha256": registry_manifest["registry_sha256"],
        "canonical_registry_reference_sha256": canonical_sha256(registry_reference),
        "p2_ledger_sha256": canonical_sha256(artifacts.p2_ledger),
        "p2_runner_code_sha256": file_sha256(Path(__file__).resolve()),
        "p2_config_sha256": file_sha256(prepared.config_path),
        "behavior_lifecycle": artifacts.behavior_lifecycle,
        "judge_lifecycle": artifacts.judge_lifecycle,
        "offline_guard_report": artifacts.offline_guard_report,
    }
    store.write_json_once("execution_identity.json", execution_identity)
    fake_backend = artifacts.p2_ledger["fake_backend"]
    return {
        "status": "P2_FAKE_4000_PATH_PASS" if fake_backend else "P2_REAL_RUN_PASS",
        "output_directory": str(output_directory),
        "run_id": run_id,
        "run_mode": "paper",
        "canonical_plan_count": len(prepared.support.registry),
        "p2_identity_count": len(prepared.p2_rows),
        "prior_support_terminal": PRIOR_SUPPORT_TERMINAL,
        "p2_terminal": artifacts.p2_ledger["p2_terminal"],
        "downstream_remaining": DOWNSTREAM_REMAINING,
        "support_status": dict(prepared.support_statuses),
        "fake_backend": fake_backend,
        "formal_experiment_run": not fake_backend,
        "p2_run": not fake_backend,
        "paper_result_eligible": False,
        "complete_stage3_reconciliation": False,
    }


def run_p2(config_path: Path, *, run_mode: str, run_id: str) -> dict[str, Any]:
    if run_mode != "paper":
        raise PipelineError("P2 execution supports only --run-mode paper")
    prepared = prepare_p2_runner(config_path)
    return run_prepared_p2(prepared, run_id=run_id)


__all__ = [
    "DEFAULT_CONFIG",
    "P2_CELLS",
    "P2RunArtifacts",
    "PreparedP2Runner",
    "execute_p2",
    "prepare_p2_runner",
    "reconcile_p2_stage",
    "run_p2",
    "run_prepared_p2",
    "select_p2_identities",
    "validate_only",
    "validate_p2_config",
]
