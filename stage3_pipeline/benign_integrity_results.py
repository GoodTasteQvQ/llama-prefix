"""Production result materialization for the fixed benign-integrity run.

The source run is an immutable execution asset.  This module validates its
eight documents against the canonical runner and only then builds the
retained-bootstrap production payload.  Validation-only never invokes the
statistic or creates an output directory.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import benign_integrity_runner as runner
from .core import PipelineError, canonical_json, canonical_sha256, file_sha256
from .execution import TERMINAL_DISPOSITIONS
from .offline_assets import strict_json_loads
from .statistics import retained_bootstrap
from .statistics.schema_validation import validate_subschema


ROOT = Path(__file__).resolve().parents[1]
FORMAL_BENIGN_INTEGRITY_RUN_DIRECTORY = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "benign-integrity-qwen25-paper-recovery-20260825T102609Z"
)
OUTPUT_FILENAME = "benign_integrity_result.json"
SCHEMA_VERSION = "paper1-stage3-benign-integrity-result-materialization-v1"
BENIGN_LABELS = tuple(retained_bootstrap.BENIGN_LABELS)
SOURCE_FILES = (
    "canonical_registry_reference.json",
    "benign_integrity_identities.json",
    "generation_records.json",
    "judge_records.json",
    "response_records.json",
    "execution_dispositions.json",
    "benign_integrity_ledger.json",
    "execution_identity.json",
)
RECORD_DOCUMENTS = {
    "benign_integrity_identities.json": ("paper1-stage3-benign-integrity-identity-set-v1", 630),
    "generation_records.json": ("paper1-stage3-benign-integrity-generation-set-v1", 630),
    "judge_records.json": ("paper1-stage3-benign-integrity-judge-set-v1", 630),
    "response_records.json": ("paper1-stage3-benign-integrity-response-set-v1", 630),
    "execution_dispositions.json": ("paper1-stage3-benign-integrity-disposition-set-v1", 630),
}


class BenignIntegrityResultInputInvalid(ValueError):
    """The fixed source run, payload, or requested destination is invalid."""

    code = "BENIGN_INTEGRITY_RESULT_INPUT_INVALID"


def _invalid(detail: str) -> None:
    raise BenignIntegrityResultInputInvalid(
        f"{BenignIntegrityResultInputInvalid.code}:{detail}"
    )


@dataclass(frozen=True)
class LoadedBenignIntegrityRun:
    run_directory: Path
    identities: tuple[Mapping[str, Any], ...]
    generations: tuple[Mapping[str, Any], ...]
    judges: tuple[Mapping[str, Any], ...]
    responses: tuple[Mapping[str, Any], ...]
    dispositions: tuple[Mapping[str, Any], ...]
    registry_reference: Mapping[str, Any]
    ledger: Mapping[str, Any]
    execution_identity: Mapping[str, Any]
    file_sha256: Mapping[str, str]


@dataclass(frozen=True)
class ValidatedBenignIntegrityRun:
    prepared: runner.PreparedBenignIntegrity
    loaded: LoadedBenignIntegrityRun
    reconciliation: Mapping[str, Any]


def _strict_object(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        _invalid(f"SOURCE_FILE_NOT_REGULAR:{path}")
    try:
        value = strict_json_loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        _invalid(f"SOURCE_JSON:{path.name}:{exc}")
    if not isinstance(value, dict):
        _invalid(f"SOURCE_DOCUMENT_NOT_OBJECT:{path.name}")
    return value


def _record_document(
    document: Mapping[str, Any], *, schema_version: str, count: int, label: str
) -> tuple[Mapping[str, Any], ...]:
    if set(document) != {"schema_version", "record_count", "records"}:
        _invalid(f"{label}:DOCUMENT_FIELDS")
    records = document.get("records")
    if (
        document.get("schema_version") != schema_version
        or type(document.get("record_count")) is not int
        or document["record_count"] != count
        or not isinstance(records, list)
        or len(records) != count
        or any(not isinstance(record, Mapping) for record in records)
    ):
        _invalid(f"{label}:DOCUMENT_METADATA")
    return tuple(dict(record) for record in records)


def _fixed_run_directory(run_directory: Path) -> Path:
    if not isinstance(run_directory, Path):
        _invalid("RUN_DIRECTORY_NOT_PATH")
    if run_directory.is_symlink():
        _invalid(f"RUN_DIRECTORY_SYMLINK:{run_directory}")
    resolved = run_directory.resolve()
    if resolved != FORMAL_BENIGN_INTEGRITY_RUN_DIRECTORY.resolve():
        _invalid(f"RUN_DIRECTORY_NOT_FIXED_FORMAL_BENIGN_INTEGRITY:{resolved}")
    if not resolved.is_dir():
        _invalid(f"RUN_DIRECTORY_NOT_DIRECTORY:{resolved}")
    return resolved


def load_benign_integrity_run(run_directory: Path) -> LoadedBenignIntegrityRun:
    """Strictly load exactly the eight immutable source documents."""
    source = _fixed_run_directory(run_directory)
    entries = sorted(path.name for path in source.iterdir())
    if entries != sorted(SOURCE_FILES):
        _invalid(f"SOURCE_DIRECTORY_ENTRIES:{entries}")
    documents = {name: _strict_object(source / name) for name in SOURCE_FILES}
    records = {
        name: _record_document(
            documents[name], schema_version=schema, count=count, label=name
        )
        for name, (schema, count) in RECORD_DOCUMENTS.items()
    }
    return LoadedBenignIntegrityRun(
        run_directory=source,
        identities=records["benign_integrity_identities.json"],
        generations=records["generation_records.json"],
        judges=records["judge_records.json"],
        responses=records["response_records.json"],
        dispositions=records["execution_dispositions.json"],
        registry_reference=documents["canonical_registry_reference.json"],
        ledger=documents["benign_integrity_ledger.json"],
        execution_identity=documents["execution_identity.json"],
        file_sha256={name: file_sha256(source / name) for name in SOURCE_FILES},
    )


def _expected_registry_reference(prepared: runner.PreparedBenignIntegrity) -> dict[str, Any]:
    return {
        "schema_version": "paper1-stage3-canonical-registry-reference-v1",
        "source_support_config": "configs/stage3/qwen25_support_screen_v1.json",
        "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": prepared.support.registry.manifest()["registry_sha256"],
        "benign_identity_count": runner.BENIGN_COUNT,
        "benign_T_identity_count": runner.BENIGN_T_COUNT,
        "benign_clean_identity_count": runner.BENIGN_CLEAN_COUNT,
        "support_run_path": str(prepared.config["support_run_path"]),
        "p1_dose_binding_path": str(prepared.config["p1_dose_binding_path"]),
    }


@contextmanager
def _preparation_environment():
    required = str((ROOT / ".codex-temp").resolve())
    previous = {name: os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")}
    try:
        for name in previous:
            os.environ[name] = required
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _validate_execution_identity(
    loaded: LoadedBenignIntegrityRun,
    prepared: runner.PreparedBenignIntegrity,
    registry_reference: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
) -> None:
    document = loaded.execution_identity
    fields = {
        "behavior_lifecycle", "behavior_vector_order", "benign_integrity_ledger_sha256",
        "benign_integrity_run", "canonical_registry_reference_sha256",
        "canonical_registry_sha256", "complete_stage3_reconciliation", "fake_backend",
        "formal_experiment_run", "judge_lifecycle", "judge_loaded_after_all_behavior_release",
        "k1_run", "models_concurrently_resident", "offline_guard_report",
        "p1_dose_binding_sha256", "p1_run", "p2_run", "paper_result_eligible", "run_id",
        "run_mode", "schema_version", "support_ledger_sha256", "support_run",
        "support_run_path",
    }
    if set(document) != fields:
        _invalid("EXECUTION_IDENTITY_FIELDS")
    expected = {
        "schema_version": "paper1-stage3-benign-integrity-execution-v1",
        "run_id": loaded.run_directory.name,
        "run_mode": "paper",
        "fake_backend": False,
        "paper_result_eligible": False,
        "formal_experiment_run": True,
        "benign_integrity_run": True,
        "complete_stage3_reconciliation": False,
        "p1_run": False,
        "support_run": False,
        "p2_run": False,
        "k1_run": False,
        "models_concurrently_resident": False,
        "judge_loaded_after_all_behavior_release": True,
        "canonical_registry_sha256": registry_reference["canonical_registry_sha256"],
        "canonical_registry_reference_sha256": canonical_sha256(dict(registry_reference)),
        "benign_integrity_ledger_sha256": canonical_sha256(dict(reconciliation)),
        "support_run_path": str(prepared.config["support_run_path"]),
        "support_ledger_sha256": canonical_sha256(prepared.support_validation["ledger"]),
        "p1_dose_binding_sha256": canonical_sha256(
            runner._dose_fingerprint(prepared.p1_result["dose_binding"])
        ),
        "behavior_vector_order": list(runner.VECTOR_INDICES),
    }
    for field, value in expected.items():
        if document.get(field) != value or type(document.get(field)) is not type(value):
            _invalid(f"EXECUTION_IDENTITY_MISMATCH:{field}")
    behavior = document["behavior_lifecycle"]
    judge = document["judge_lifecycle"]
    if not isinstance(behavior, Mapping) or not isinstance(judge, Mapping):
        _invalid("LIFECYCLE_NOT_OBJECT")
    for lifecycle, label in ((behavior, "BEHAVIOR"), (judge, "JUDGE")):
        if lifecycle.get("schema_version") != "paper1-stage3-sequential-lifecycle-v1":
            _invalid(f"{label}_LIFECYCLE:SCHEMA_VERSION")
        if lifecycle.get("vector_indices") != list(runner.VECTOR_INDICES):
            _invalid(f"{label}_LIFECYCLE:VECTOR_ORDER")
    for field in (
        "behavior_released", "behavior_hook_removed", "behavior_model_reference_cleared",
        "behavior_tokenizer_reference_cleared", "gc_collect_called",
    ):
        if behavior.get(field) is not True:
            _invalid(f"BEHAVIOR_LIFECYCLE:{field}")
    for field in (
        "judge_loaded_after_behavior_release", "judge_released",
        "judge_model_reference_cleared", "judge_tokenizer_reference_cleared",
    ):
        if judge.get(field) is not True:
            _invalid(f"JUDGE_LIFECYCLE:{field}")
    if behavior.get("models_concurrently_resident") is not False or judge.get(
        "models_concurrently_resident"
    ) is not False:
        _invalid("LIFECYCLE_CONCURRENT_MODEL_RESIDENCE")
    guard = document["offline_guard_report"]
    if (
        not isinstance(guard, Mapping)
        or guard.get("category_counts", {}).get("network") != 0
        or guard.get("blocked_attempt_count") != 0
        or guard.get("guard_closed") is not True
    ):
        _invalid("OFFLINE_GUARD")


def load_and_reconcile_benign_integrity_run(
    run_directory: Path,
) -> ValidatedBenignIntegrityRun:
    """Prepare canonical inputs, load all source records, and reconcile twice."""
    source = _fixed_run_directory(run_directory)
    try:
        with _preparation_environment():
            prepared = runner.prepare_benign_integrity()
        loaded = load_benign_integrity_run(source)
        expected_reference = _expected_registry_reference(prepared)
        if list(loaded.identities) != [*prepared.benign_T_rows, *prepared.benign_clean_rows]:
            _invalid("STORED_IDENTITIES_DIFFER_FROM_CANONICAL_BENIGN_FRAME")
        if dict(loaded.registry_reference) != expected_reference:
            _invalid("STORED_REGISTRY_REFERENCE_MISMATCH")
        reconciliation = runner.reconcile_benign_integrity(
            prepared,
            generation_records=loaded.generations,
            judge_records=loaded.judges,
            response_records=loaded.responses,
            dispositions=loaded.dispositions,
            expected_fake_backend=False,
        )
    except BenignIntegrityResultInputInvalid:
        raise
    except (PipelineError, KeyError, TypeError, ValueError) as exc:
        _invalid(f"BENIGN_INTEGRITY_RECONCILIATION:{exc}")
    if dict(loaded.ledger) != dict(reconciliation):
        _invalid("STORED_LEDGER_DIFFERS_FROM_RECONCILIATION")
    for field, expected in {
        "canonical_plan_count": 5580,
        "benign_identity_count": 630,
        "benign_T_identity_count": 600,
        "benign_clean_identity_count": 30,
        "fake_backend": False,
        "formal_experiment_run": True,
        "paper_result_eligible": False,
        "bootstrap_run": False,
        "paper_results_materialized": False,
        "complete_stage3_reconciliation": False,
    }.items():
        if reconciliation.get(field) != expected or type(reconciliation.get(field)) is not type(expected):
            _invalid(f"LEDGER_STATUS_MISMATCH:{field}")
    if reconciliation.get("generation_completed") != 630 or reconciliation.get("judge_eligible") != 630:
        _invalid("GENERATION_JUDGE_COMPLETION_COUNT")
    if set(reconciliation.get("terminal_partition", {})) != set(TERMINAL_DISPOSITIONS):
        _invalid("TERMINAL_PARTITION_FIELDS")
    _validate_execution_identity(loaded, prepared, expected_reference, reconciliation)
    return ValidatedBenignIntegrityRun(prepared, loaded, reconciliation)


def _index(records: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        logical_id = record.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in indexed:
            _invalid(f"{label}:MISSING_OR_DUPLICATE_LOGICAL_ID:{logical_id}")
        indexed[logical_id] = record
    return indexed


def _frames(
    canonical_t_rows: Sequence[Mapping[str, Any]],
    canonical_clean_rows: Sequence[Mapping[str, Any]],
    *,
    expected_prompt_ids: Sequence[str] | None,
    expected_vector_ids: Sequence[str] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    prompt_ids = [row["identity"]["prompt_id"] for row in canonical_clean_rows]
    t_prompt_ids = [row["identity"]["prompt_id"] for row in canonical_t_rows[::20]]
    if len(prompt_ids) != 30 or len(set(prompt_ids)) != 30 or t_prompt_ids != prompt_ids:
        _invalid("PROMPT_FRAME_NOT_EXACTLY_30_CANONICAL_ORDER")
    if expected_prompt_ids is not None and prompt_ids != list(expected_prompt_ids):
        _invalid("PROMPT_FRAME_DIFFERS_FROM_CANONICAL_CONFIRM_ORDER")
    vector_ids = [
        row["identity"]["vector_id"]
        for row in canonical_t_rows[:20]
    ]
    if len(vector_ids) != 20 or len(set(vector_ids)) != 20:
        _invalid("VECTOR_FRAME_NOT_EXACTLY_20_CANONICAL_ORDER")
    if expected_vector_ids is not None and vector_ids != list(expected_vector_ids):
        _invalid("VECTOR_FRAME_DIFFERS_FROM_CANONICAL_ORDER")
    return (
        [{"position": i, "prompt_id": prompt_id} for i, prompt_id in enumerate(prompt_ids)],
        [{"position": i, "vector_id": vector_id} for i, vector_id in enumerate(vector_ids)],
        prompt_ids,
    )


def build_benign_broken_payload(
    canonical_t_rows: Sequence[Mapping[str, Any]],
    canonical_clean_rows: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    *,
    expected_prompt_ids: Sequence[str] | None = None,
    expected_vector_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build the exact production payload, retaining only complete prompts."""
    complete_frame, vector_frame, prompt_ids = _frames(
        canonical_t_rows, canonical_clean_rows,
        expected_prompt_ids=expected_prompt_ids, expected_vector_ids=expected_vector_ids,
    )
    rows = [*canonical_t_rows, *canonical_clean_rows]
    expected_ids = {row["logical_id"] for row in rows}
    response_by_id = _index(response_records, "response_records")
    disposition_by_id = _index(dispositions, "dispositions")
    if set(response_by_id) != expected_ids or set(disposition_by_id) != expected_ids:
        _invalid("RESPONSE_OR_DISPOSITION_ID_SET_MISMATCH")
    t_by_coordinate = {
        (row["identity"]["prompt_id"], row["identity"]["vector_id"]): row
        for row in canonical_t_rows
    }
    clean_by_prompt = {row["identity"]["prompt_id"]: row for row in canonical_clean_rows}
    vector_ids = [item["vector_id"] for item in vector_frame]
    prompts: list[dict[str, Any]] = []
    for prompt_id in prompt_ids:
        clean_row = clean_by_prompt[prompt_id]
        clean_response = response_by_id[clean_row["logical_id"]]
        clean_disposition = disposition_by_id[clean_row["logical_id"]]
        steered_rows = [t_by_coordinate[(prompt_id, vector_id)] for vector_id in vector_ids]
        steered_responses = [response_by_id[row["logical_id"]] for row in steered_rows]
        steered_dispositions = [disposition_by_id[row["logical_id"]] for row in steered_rows]
        complete = (
            clean_disposition.get("terminal_disposition") == "COMPLETED_PARSED"
            and clean_response.get("judge_eligible") is True
            and clean_response.get("label") in BENIGN_LABELS
            and all(
                disposition.get("terminal_disposition") == "COMPLETED_PARSED"
                and response.get("judge_eligible") is True
                and response.get("label") in BENIGN_LABELS
                for response, disposition in zip(steered_responses, steered_dispositions)
            )
        )
        if not complete:
            continue
        prompts.append({
            "prompt_id": prompt_id,
            "clean": {
                "response_id": clean_row["logical_id"],
                "label": clean_response["label"],
            },
            "steered": [
                {
                    "response_id": row["logical_id"],
                    "vector_id": vector_id,
                    "label": response["label"],
                }
                for row, vector_id, response in zip(steered_rows, vector_ids, steered_responses)
            ],
        })
    payload = {
        "schema_version": retained_bootstrap.SCHEMA_VERSION,
        "synthetic_data": False,
        "block_type": "benign_broken",
        "complete_prompt_frame": [
            {"position": position, "prompt_id": item["prompt_id"]}
            for position, item in enumerate(
                item for item in complete_frame
                if item["prompt_id"] in {p["prompt_id"] for p in prompts}
            )
        ],
        "vector_frame": vector_frame,
        "prompts": prompts,
    }
    if [item["prompt_id"] for item in payload["complete_prompt_frame"]] != [p["prompt_id"] for p in prompts]:
        _invalid("COMPLETE_PROMPT_FRAME_ORDER")
    try:
        schema = json.loads(
            (ROOT / "stage3_pipeline/statistics/schemas/retained_bootstrap.schema.json")
            .read_text(encoding="utf-8")
        )
        validate_subschema(schema, "#/$defs/benignBroken", payload)
    except Exception as exc:
        _invalid(f"STATISTICS_PAYLOAD_SCHEMA:{exc}")
    return payload


def _arm_accounting(
    rows: Sequence[Mapping[str, Any]], responses: Mapping[str, Mapping[str, Any]], dispositions: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    partition = {terminal: 0 for terminal in TERMINAL_DISPOSITIONS}
    retained = 0
    labels = Counter()
    for row in rows:
        logical_id = row["logical_id"]
        terminal = dispositions[logical_id]["terminal_disposition"]
        partition[terminal] += 1
        if terminal == "COMPLETED_PARSED" and responses[logical_id].get("judge_eligible") is True:
            retained += 1
            if responses[logical_id].get("label") in BENIGN_LABELS:
                labels[responses[logical_id]["label"]] += 1
    return {
        "scheduled": len(rows),
        "completed_parsed_judge_eligible": retained,
        "retained_denominator": retained,
        "terminal_partition": partition,
        "label_counts": {label: labels.get(label, 0) for label in BENIGN_LABELS},
    }


def _descriptive_accounting(validated: ValidatedBenignIntegrityRun, payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = [*validated.prepared.benign_T_rows, *validated.prepared.benign_clean_rows]
    responses = _index(validated.loaded.responses, "responses")
    dispositions = _index(validated.loaded.dispositions, "dispositions")
    prompt_ids = [item["prompt_id"] for item in payload["complete_prompt_frame"]]
    all_prompt_ids = [row["identity"]["prompt_id"] for row in validated.prepared.benign_clean_rows]
    incomplete = [prompt_id for prompt_id in all_prompt_ids if prompt_id not in set(prompt_ids)]
    clean_rows = validated.prepared.benign_clean_rows
    t_rows = validated.prepared.benign_T_rows
    complete_prompt_set = set(prompt_ids)

    def arm_accounting(arm_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        arm = _arm_accounting(arm_rows, responses, dispositions)
        arm["complete_case_denominator"] = sum(
            1 for row in arm_rows if row["identity"]["prompt_id"] in complete_prompt_set
            and dispositions[row["logical_id"]]["terminal_disposition"] == "COMPLETED_PARSED"
            and responses[row["logical_id"]].get("judge_eligible") is True
        )
        arm["missing_record_count"] = arm["retained_denominator"] - arm["complete_case_denominator"]
        return arm

    return {
        "scheduled": 630,
        "terminal": sum(validated.reconciliation["terminal_partition"].values()),
        "complete_prompt_count": len(prompt_ids),
        "incomplete_prompt_count": len(incomplete),
        "incomplete_prompt_ids": incomplete,
        "retained_denominator": len(prompt_ids),
        "benign_clean": arm_accounting(clean_rows),
        "benign_T": arm_accounting(t_rows),
        "terminal_partition": dict(validated.reconciliation["terminal_partition"]),
    }


def _source_summary(validated: ValidatedBenignIntegrityRun) -> dict[str, Any]:
    loaded = validated.loaded
    reconciliation = validated.reconciliation
    return {
        "run_directory": str(loaded.run_directory),
        "run_id": loaded.run_directory.name,
        "canonical_plan_count": reconciliation["canonical_plan_count"],
        "canonical_registry_sha256": reconciliation["canonical_registry_sha256"],
        "benign_identity_count": reconciliation["benign_identity_count"],
        "benign_integrity_ledger_sha256": canonical_sha256(dict(loaded.ledger)),
        "execution_identity_sha256": canonical_sha256(dict(loaded.execution_identity)),
        "source_file_sha256": dict(loaded.file_sha256),
    }


def _statistics_contract() -> dict[str, Any]:
    return {
        "implementation_version": retained_bootstrap.IMPLEMENTATION_VERSION,
        "function": "analyze_benign_broken",
        "statistic_id": "RD_benign_broken",
        "rng_namespace": retained_bootstrap.RNG_NAMESPACE,
        "replicates": retained_bootstrap.PRODUCTION_REPLICATES,
        "min_success": retained_bootstrap.PRODUCTION_MIN_SUCCESS,
        "replicates_requested": retained_bootstrap.PRODUCTION_REPLICATES,
        "required_successful": retained_bootstrap.PRODUCTION_MIN_SUCCESS,
        "algorithm": "retained_percentile_nearest_rank_v1",
        "interval": "nearest_rank_[Q_NR(0.025),Q_NR(0.975)]_no_interpolation",
        "inferential_claim": "CI-only/descriptive-only; no safety, harmlessness, equivalence, or generalizable domain-effect claim",
    }


def assemble_benign_integrity_result(
    validated: ValidatedBenignIntegrityRun,
    *,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected_prompts = validated.prepared.support.plan_inputs["benign_prompt_ids"]
    expected_vectors = [validated.prepared.support.vector_ids_by_index[i] for i in runner.VECTOR_INDICES]
    payload = build_benign_broken_payload(
        validated.prepared.benign_T_rows,
        validated.prepared.benign_clean_rows,
        validated.loaded.responses,
        validated.loaded.dispositions,
        expected_prompt_ids=expected_prompts,
        expected_vector_ids=expected_vectors,
    )
    statistic = retained_bootstrap.analyze_benign_broken if statistics_function is None else statistics_function
    try:
        statistics_result = statistic(payload, fixture_mode=False)
    except retained_bootstrap.RetainedBootstrapError as exc:
        statistics_result = None
        statistics_error = {"code": exc.code, "detail": exc.detail, "report_status": exc.report_status}
        status = "NON_ESTIMABLE"
    else:
        statistics_error = None
        status = "ESTIMABLE"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "paper_result_eligible": False,
        "descriptive_only": True,
        "ci_only": True,
        "safety_claim": False,
        "harmlessness_claim": False,
        "equivalence_claim": False,
        "generalizable_domain_effect_claim": False,
        "generation_calls_added": 0,
        "judge_calls_added": 0,
        "benign_integrity_rerun": False,
        "source": _source_summary(validated),
        "accounting": _descriptive_accounting(validated, payload),
        "label_order": list(BENIGN_LABELS),
        "statistics_contract": _statistics_contract(),
        "statistics_input": payload,
        "statistics": statistics_result,
        "statistics_error": statistics_error,
        "scope": {
            "frame": "complete D_benign_confirm prompts in canonical order; vector indices 10..29",
            "missing_terminal_prompts": "excluded from complete-case bootstrap and retained in arm accounting; no label imputation",
        "operation": "20-vector average within complete prompt, then prompt-level RD_benign_broken bootstrap",
            "inferential_claim": "CI-only/descriptive-only; no safety, harmlessness, equivalence, or generalizable domain-effect claim",
        },
    }


def check_output_destination(run_directory: Path, output_directory: Path) -> Path:
    if not isinstance(output_directory, Path):
        _invalid("OUTPUT_DIRECTORY_NOT_PATH")
    if not isinstance(run_directory, Path):
        _invalid("RUN_DIRECTORY_NOT_PATH")
    if run_directory.is_symlink():
        _invalid(f"RUN_DIRECTORY_SYMLINK:{run_directory}")
    source = run_directory.resolve()
    output = output_directory.resolve()
    if output_directory.exists() or output_directory.is_symlink():
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output_directory}")
    target = output / OUTPUT_FILENAME
    if target.exists() or target.is_symlink():
        _invalid(f"OUTPUT_FILE_EXISTS:{target}")
    try:
        output.relative_to(source)
    except ValueError:
        pass
    else:
        _invalid("OUTPUT_DIRECTORY_INSIDE_SOURCE_RUN")
    return output


def _atomic_write_json(path: Path, document: Mapping[str, Any]) -> None:
    payload = json.dumps(json.loads(canonical_json(dict(document))), ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def materialize_benign_integrity_results_directory(
    run_directory: Path,
    output_directory: Path,
    *,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    output = check_output_destination(run_directory, output_directory)
    validated = load_and_reconcile_benign_integrity_run(run_directory)
    result = assemble_benign_integrity_result(validated, statistics_function=statistics_function)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    _atomic_write_json(output / OUTPUT_FILENAME, result)
    return result


def validation_summary(
    validated: ValidatedBenignIntegrityRun, output_directory: Path | None = None
) -> dict[str, Any]:
    expected_prompts = validated.prepared.support.plan_inputs["benign_prompt_ids"]
    expected_vectors = [validated.prepared.support.vector_ids_by_index[i] for i in runner.VECTOR_INDICES]
    payload = build_benign_broken_payload(
        validated.prepared.benign_T_rows, validated.prepared.benign_clean_rows,
        validated.loaded.responses, validated.loaded.dispositions,
        expected_prompt_ids=expected_prompts, expected_vector_ids=expected_vectors,
    )
    accounting = _descriptive_accounting(validated, payload)
    return {
        "status": "BENIGN_INTEGRITY_RESULT_VALIDATE_ONLY_PASS",
        "run_id": validated.loaded.run_directory.name,
        "canonical_plan_count": 5580,
        "benign_identity_count": 630,
        "complete_prompt_count": accounting["complete_prompt_count"],
        "incomplete_prompt_count": accounting["incomplete_prompt_count"],
        "incomplete_prompt_ids": accounting["incomplete_prompt_ids"],
        "terminal": accounting["terminal"],
        "terminal_partition": accounting["terminal_partition"],
        "accounting": accounting,
        "statistics_payload_validated": True,
        "statistics_executed": False,
        "bootstrap_run": False,
        "output_written": False,
        "output_directory": None if output_directory is None else str(output_directory.resolve()),
        "model_weights_loaded": False,
        "gpu_used": False,
        "generation_run": False,
        "judge_run": False,
    }


def validate_only(run_directory: Path, output_directory: Path) -> dict[str, Any]:
    check_output_destination(run_directory, output_directory)
    validated = load_and_reconcile_benign_integrity_run(run_directory)
    return validation_summary(validated, output_directory)


__all__ = [
    "FORMAL_BENIGN_INTEGRITY_RUN_DIRECTORY", "OUTPUT_FILENAME", "SCHEMA_VERSION",
    "BENIGN_LABELS", "BenignIntegrityResultInputInvalid", "LoadedBenignIntegrityRun",
    "ValidatedBenignIntegrityRun", "load_benign_integrity_run",
    "load_and_reconcile_benign_integrity_run", "build_benign_broken_payload",
    "assemble_benign_integrity_result", "check_output_destination",
    "materialize_benign_integrity_results_directory", "validation_summary", "validate_only",
]
