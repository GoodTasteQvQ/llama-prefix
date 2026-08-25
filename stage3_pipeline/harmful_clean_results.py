"""Descriptive result materialization for the accepted harmful-clean run."""

from __future__ import annotations

import json
import os
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from activation_guard.metrics import compute_response_metrics

from . import harmful_clean_runner as runner
from .core import PipelineError, canonical_json, canonical_sha256, file_sha256
from .execution import TERMINAL_DISPOSITIONS
from .offline_assets import strict_json_loads
from .statistics import retained_bootstrap
from .statistics.schema_validation import validate_subschema


ROOT = Path(__file__).resolve().parents[1]
FORMAL_HARMFUL_CLEAN_RUN_DIRECTORY = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "harmful-clean-qwen25-paper-20260825T071017Z"
)
OUTPUT_FILENAME = "harmful_clean_result.json"
SCHEMA_VERSION = "paper1-stage3-harmful-clean-result-materialization-v1"
HARMFUL_LABELS = ("broken", "unsafe", "refusal", "safe")
_SOURCE_FILES = (
    "canonical_registry_reference.json",
    "harmful_clean_identities.json",
    "generation_records.json",
    "judge_records.json",
    "response_records.json",
    "execution_dispositions.json",
    "harmful_clean_ledger.json",
    "execution_identity.json",
)
_RECORD_DOCUMENTS = {
    "harmful_clean_identities.json": ("paper1-stage3-harmful-clean-identity-set-v1", 50),
    "generation_records.json": ("paper1-stage3-harmful-clean-generation-set-v1", 50),
    "judge_records.json": ("paper1-stage3-harmful-clean-judge-set-v1", 50),
    "response_records.json": ("paper1-stage3-harmful-clean-response-set-v1", 50),
    "execution_dispositions.json": ("paper1-stage3-harmful-clean-disposition-set-v1", 50),
}
_ARR_COMPONENTS = (
    "empty_or_truncated",
    "special_token_leakage",
    "garbled",
    "repetition_gt_0_2",
)


class HarmfulCleanResultInputInvalid(ValueError):
    """The fixed harmful-clean run or requested output is invalid."""

    code = "HARMFUL_CLEAN_RESULT_INPUT_INVALID"


def _invalid(detail: str) -> None:
    raise HarmfulCleanResultInputInvalid(
        f"{HarmfulCleanResultInputInvalid.code}:{detail}"
    )


@dataclass(frozen=True)
class LoadedHarmfulCleanRun:
    """Strictly loaded source documents from the accepted formal run."""

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
class ValidatedHarmfulCleanRun:
    """Prepared canonical identities plus reconciled source records."""

    prepared: runner.PreparedHarmfulClean
    loaded: LoadedHarmfulCleanRun
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
    if resolved != FORMAL_HARMFUL_CLEAN_RUN_DIRECTORY.resolve():
        _invalid(f"RUN_DIRECTORY_NOT_FIXED_FORMAL_HARMFUL_CLEAN:{resolved}")
    if not resolved.is_dir():
        _invalid(f"RUN_DIRECTORY_NOT_DIRECTORY:{resolved}")
    return resolved


def load_harmful_clean_run(run_directory: Path) -> LoadedHarmfulCleanRun:
    """Load only the fixed eight-file result set as strict UTF-8 JSON."""
    source = _fixed_run_directory(run_directory)
    entries = sorted(path.name for path in source.iterdir())
    if entries != sorted(_SOURCE_FILES):
        _invalid(f"SOURCE_DIRECTORY_ENTRIES:{entries}")
    documents = {name: _strict_object(source / name) for name in _SOURCE_FILES}
    records = {
        name: _record_document(
            documents[name], schema_version=schema, count=count, label=name
        )
        for name, (schema, count) in _RECORD_DOCUMENTS.items()
    }
    return LoadedHarmfulCleanRun(
        run_directory=source,
        identities=records["harmful_clean_identities.json"],
        generations=records["generation_records.json"],
        judges=records["judge_records.json"],
        responses=records["response_records.json"],
        dispositions=records["execution_dispositions.json"],
        registry_reference=documents["canonical_registry_reference.json"],
        ledger=documents["harmful_clean_ledger.json"],
        execution_identity=documents["execution_identity.json"],
        file_sha256={name: file_sha256(source / name) for name in _SOURCE_FILES},
    )


def _expected_registry_reference(
    prepared: runner.PreparedHarmfulClean,
) -> dict[str, Any]:
    return {
        "schema_version": "paper1-stage3-canonical-registry-reference-v1",
        "source_support_config": "configs/stage3/qwen25_support_screen_v1.json",
        "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": prepared.support.registry.manifest()[
            "registry_sha256"
        ],
        "harmful_clean_identity_count": len(prepared.clean_rows),
        "harmful_clean_identity_set_sha256": canonical_sha256(
            list(prepared.clean_rows)
        ),
        "source_role": "D_behavior_confirm",
    }


def _validate_execution_identity(
    loaded: LoadedHarmfulCleanRun,
    prepared: runner.PreparedHarmfulClean,
    registry_reference: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
) -> None:
    document = loaded.execution_identity
    expected_fields = {
        "schema_version", "run_id", "run_mode", "fake_backend",
        "paper_result_eligible", "formal_experiment_run", "harmful_clean_run",
        "p1_run", "support_run", "p2_run", "k1_run",
        "canonical_registry_sha256", "canonical_registry_reference_sha256",
        "harmful_clean_ledger_sha256", "harmful_clean_runner_code_sha256",
        "harmful_clean_config_sha256", "behavior_lifecycle", "judge_lifecycle",
        "offline_guard_report",
    }
    if set(document) != expected_fields:
        _invalid("EXECUTION_IDENTITY_FIELDS")
    expected = {
        "schema_version": "paper1-stage3-harmful-clean-execution-v1",
        "run_id": loaded.run_directory.name,
        "run_mode": "paper",
        "fake_backend": False,
        "paper_result_eligible": False,
        "formal_experiment_run": True,
        "harmful_clean_run": True,
        "p1_run": False,
        "support_run": False,
        "p2_run": False,
        "k1_run": False,
        "canonical_registry_sha256": registry_reference[
            "canonical_registry_sha256"
        ],
        "canonical_registry_reference_sha256": canonical_sha256(
            dict(registry_reference)
        ),
        "harmful_clean_ledger_sha256": canonical_sha256(dict(reconciliation)),
        "harmful_clean_runner_code_sha256": file_sha256(
            Path(runner.__file__).resolve()
        ),
        "harmful_clean_config_sha256": file_sha256(prepared.config_path),
    }
    for field, value in expected.items():
        if document.get(field) != value or type(document.get(field)) is not type(value):
            _invalid(f"EXECUTION_IDENTITY_MISMATCH:{field}")
    for field in ("behavior_lifecycle", "judge_lifecycle", "offline_guard_report"):
        if not isinstance(document.get(field), Mapping):
            _invalid(f"EXECUTION_IDENTITY_NOT_OBJECT:{field}")
    behavior = document["behavior_lifecycle"]
    judge = document["judge_lifecycle"]
    for field in (
        "behavior_released", "behavior_hook_removed",
        "behavior_model_reference_cleared", "behavior_tokenizer_reference_cleared",
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
        guard.get("category_counts", {}).get("network") != 0
        or guard.get("blocked_attempt_count") != 0
        or guard.get("guard_closed") is not True
    ):
        _invalid("OFFLINE_GUARD")


def _index(records: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        logical_id = record.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in indexed:
            _invalid(f"{label}:MISSING_OR_DUPLICATE_LOGICAL_ID:{logical_id}")
        indexed[logical_id] = record
    return indexed


@contextmanager
def _preparation_environment():
    """Satisfy the existing validate-only environment contract temporarily."""
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


def load_and_reconcile_harmful_clean_run(
    run_directory: Path,
) -> ValidatedHarmfulCleanRun:
    """Prepare the canonical frame, load the source, and reconcile all chains."""
    source = _fixed_run_directory(run_directory)
    try:
        with _preparation_environment():
            prepared = runner.prepare_harmful_clean()
        loaded = load_harmful_clean_run(source)
        expected_reference = _expected_registry_reference(prepared)
        if list(loaded.identities) != list(prepared.clean_rows):
            _invalid("STORED_IDENTITIES_DIFFER_FROM_CANONICAL_CLEAN_FRAME")
        if dict(loaded.registry_reference) != expected_reference:
            _invalid("STORED_REGISTRY_REFERENCE_MISMATCH")
        reconciliation = runner.reconcile_harmful_clean(
            prepared,
            generation_records=loaded.generations,
            judge_records=loaded.judges,
            response_records=loaded.responses,
            dispositions=loaded.dispositions,
            expected_fake_backend=False,
        )
    except HarmfulCleanResultInputInvalid:
        raise
    except (PipelineError, KeyError, TypeError, ValueError) as exc:
        _invalid(f"HARMFUL_CLEAN_RECONCILIATION:{exc}")
    if dict(loaded.ledger) != dict(reconciliation):
        _invalid("STORED_LEDGER_DIFFERS_FROM_RECONCILIATION")
    if reconciliation.get("harmful_clean_identity_count") != 50:
        _invalid("IDENTITY_COUNT_NOT_50")
    if reconciliation.get("terminal_partition", {}).get("COMPLETED_PARSED") != 50:
        _invalid("COMPLETED_PARSED_COUNT_NOT_50")
    ledger = loaded.ledger
    for field, expected in {
        "paper_result_eligible": False,
        "fake_backend": False,
        "formal_experiment_run": True,
        "harmful_clean_run": True,
        "p1_run": False,
        "support_run": False,
        "p2_run": False,
        "k1_run": False,
        "harmful_clean_only_reconciliation": True,
        "complete_stage3_reconciliation": False,
        "paper_results_materialized": False,
        "bootstrap_run": False,
        "dose_evidence_record_count": 0,
        "vector_identity_copy_count": 0,
        "generation_retry_calls": 0,
        "judge_retry_calls": 0,
        "k1_additional_generation_calls": 0,
        "k1_additional_judge_calls": 0,
    }.items():
        if ledger.get(field) != expected or type(ledger.get(field)) is not type(expected):
            _invalid(f"LEDGER_STATUS_MISMATCH:{field}")
    _validate_execution_identity(
        loaded, prepared, expected_reference, reconciliation
    )
    return ValidatedHarmfulCleanRun(prepared, loaded, reconciliation)


def _prompt_frame(
    canonical_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    prompt_ids = [row["identity"]["prompt_id"] for row in canonical_rows]
    if len(prompt_ids) != 50 or len(set(prompt_ids)) != 50:
        _invalid("PROMPT_FRAME_NOT_EXACTLY_50_UNIQUE")
    return [
        {"position": position, "prompt_id": prompt_id}
        for position, prompt_id in enumerate(prompt_ids)
    ]


def _terminal_index(
    canonical_rows: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    expected = {row["logical_id"] for row in canonical_rows}
    response_by_id = _index(responses, "response_records")
    disposition_by_id = _index(dispositions, "dispositions")
    if set(response_by_id) != expected or set(disposition_by_id) != expected:
        _invalid("RESPONSE_OR_DISPOSITION_ID_SET_MISMATCH")
    return response_by_id, disposition_by_id


def build_harmful_clean_payload(
    canonical_rows: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    *,
    expected_prompt_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build the production retained-bootstrap payload without running it."""
    frame = _prompt_frame(canonical_rows)
    if expected_prompt_ids is not None and [
        item["prompt_id"] for item in frame
    ] != list(expected_prompt_ids):
        _invalid("PROMPT_FRAME_DIFFERS_FROM_CANONICAL_CONFIRM_ORDER")
    response_by_id, disposition_by_id = _terminal_index(
        canonical_rows, response_records, dispositions
    )
    records: list[dict[str, str]] = []
    for row in canonical_rows:
        logical_id = row["logical_id"]
        response = response_by_id[logical_id]
        disposition = disposition_by_id[logical_id]
        if disposition["terminal_disposition"] != "COMPLETED_PARSED":
            continue
        if response.get("label") not in HARMFUL_LABELS:
            _invalid(f"RETAINED_LABEL_INVALID:{logical_id}")
        records.append({
            "row_id": logical_id,
            "prompt_id": row["identity"]["prompt_id"],
            "label": response["label"],
        })
    payload = {
        "schema_version": retained_bootstrap.SCHEMA_VERSION,
        "synthetic_data": False,
        "block_type": "harmful_clean",
        "prompt_frame": frame,
        "records": records,
    }
    try:
        schema = json.loads(
            (ROOT / "stage3_pipeline/statistics/schemas/retained_bootstrap.schema.json")
            .read_text(encoding="utf-8")
        )
        validate_subschema(schema, "#/$defs/harmfulClean", payload)
    except Exception as exc:
        _invalid(f"STATISTICS_PAYLOAD_SCHEMA:{exc}")
    return payload


def _proportion(count: int, denominator: int) -> float:
    if denominator <= 0:
        _invalid("RETAINED_DENOMINATOR_ZERO")
    return count / denominator


def _descriptive_accounting(
    validated: ValidatedHarmfulCleanRun,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    reconciliation = validated.reconciliation
    counts = Counter(row["label"] for row in payload["records"])
    label_counts = {label: counts.get(label, 0) for label in HARMFUL_LABELS}
    retained = len(payload["records"])
    return {
        "scheduled": 50,
        "terminal": sum(reconciliation["terminal_partition"].values()),
        "retained_denominator": retained,
        "terminal_partition": {
            terminal: reconciliation["terminal_partition"].get(terminal, 0)
            for terminal in TERMINAL_DISPOSITIONS
        },
        "label_counts": label_counts,
        "label_proportions": {
            label: _proportion(count, retained)
            for label, count in label_counts.items()
        },
    }


def compute_generation_metrics(
    generation_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compute descriptive output metrics using activation_guard's definitions."""
    metrics = [
        compute_response_metrics(record["output_text"])
        for record in generation_records
        if record.get("generation_completed") is True
        and isinstance(record.get("output_text"), str)
    ]
    denominator = len(metrics)
    if denominator == 0:
        return {
            "denominator": 0,
            "mean_arr": None,
            "arr_count": 0,
            "arr_proportion": None,
            "arr_component_rates": {component: None for component in _ARR_COMPONENTS},
            "mean_3gram_repetition_rate": None,
        }
    component_values = {
        "empty_or_truncated": [bool(item["empty_or_truncated"]) for item in metrics],
        "special_token_leakage": [bool(item["special_token_leakage"]) for item in metrics],
        "garbled": [bool(item["garbled"]) for item in metrics],
        "repetition_gt_0_2": [float(item["repetition_rate"]) > 0.2 for item in metrics],
    }
    arr_count = sum(float(item["arr"]) for item in metrics)
    return {
        "denominator": denominator,
        "mean_arr": sum(float(item["arr"]) for item in metrics) / denominator,
        "arr_count": int(arr_count),
        "arr_proportion": arr_count / denominator,
        "arr_component_rates": {
            component: sum(values) / denominator
            for component, values in component_values.items()
        },
        "mean_3gram_repetition_rate": sum(
            float(item["repetition_rate"]) for item in metrics
        ) / denominator,
    }


def _source_summary(validated: ValidatedHarmfulCleanRun) -> dict[str, Any]:
    loaded = validated.loaded
    reconciliation = validated.reconciliation
    return {
        "run_directory": str(loaded.run_directory),
        "run_id": loaded.run_directory.name,
        "canonical_plan_count": reconciliation["canonical_plan_count"],
        "canonical_registry_sha256": reconciliation["canonical_registry_sha256"],
        "harmful_clean_identity_count": reconciliation[
            "harmful_clean_identity_count"
        ],
        "harmful_clean_identity_set_sha256": reconciliation[
            "harmful_clean_identity_set_sha256"
        ],
        "harmful_clean_ledger_sha256": canonical_sha256(dict(loaded.ledger)),
        "execution_identity_sha256": canonical_sha256(
            dict(loaded.execution_identity)
        ),
        "source_file_sha256": dict(loaded.file_sha256),
    }


def _statistics_contract() -> dict[str, Any]:
    return {
        "implementation_version": retained_bootstrap.IMPLEMENTATION_VERSION,
        "function": "analyze_harmful_clean",
        "rng_namespace": retained_bootstrap.RNG_NAMESPACE,
        "replicates": retained_bootstrap.PRODUCTION_REPLICATES,
        "min_success": retained_bootstrap.PRODUCTION_MIN_SUCCESS,
        "label_order": list(HARMFUL_LABELS),
        "algorithm": "retained_percentile_nearest_rank_v1",
        "interval": "nearest_rank_[Q_NR(0.025),Q_NR(0.975)]_no_interpolation",
        "inferential_claim": "descriptive_only_no_test",
    }


def assemble_harmful_clean_result(
    validated: ValidatedHarmfulCleanRun,
    *,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble one descriptive result and invoke the supplied statistic."""
    payload = build_harmful_clean_payload(
        validated.prepared.clean_rows,
        validated.loaded.responses,
        validated.loaded.dispositions,
        expected_prompt_ids=validated.prepared.support.plan_inputs[
            "confirm_prompt_ids"
        ],
    )
    accounting = _descriptive_accounting(validated, payload)
    statistic = (
        retained_bootstrap.analyze_harmful_clean
        if statistics_function is None
        else statistics_function
    )
    try:
        statistics_result = statistic(payload, fixture_mode=False)
    except retained_bootstrap.RetainedBootstrapError as exc:
        statistics_result = None
        statistics_error = {
            "code": exc.code,
            "detail": exc.detail,
            "report_status": exc.report_status,
        }
        status = "NON_ESTIMABLE"
    else:
        statistics_error = None
        status = "ESTIMABLE"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "paper_result_eligible": False,
        "descriptive_only": True,
        "no_contrast": True,
        "no_p_value": True,
        "generation_calls_added": 0,
        "judge_calls_added": 0,
        "harmful_clean_rerun": False,
        "clean_intervention_applied": False,
        "source": _source_summary(validated),
        "accounting": accounting,
        "label_order": list(HARMFUL_LABELS),
        "statistics_contract": _statistics_contract(),
        "statistics_input": payload,
        "statistics": statistics_result,
        "statistics_error": statistics_error,
        "generation_metrics": compute_generation_metrics(
            validated.loaded.generations
        ),
        "scope": {
            "frame": "all 50 ordered D_behavior_confirm prompts",
            "missing_terminal_prompts": (
                "retained in prompt_frame; omitted from records; no label imputation"
            ),
            "inferential_claim": "descriptive_only_no_contrast_no_p_value",
        },
    }


def check_output_destination(
    run_directory: Path, output_directory: Path
) -> Path:
    if not isinstance(output_directory, Path):
        _invalid("OUTPUT_DIRECTORY_NOT_PATH")
    output = output_directory.resolve()
    if output_directory.exists() or output_directory.is_symlink():
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output_directory}")
    target = output / OUTPUT_FILENAME
    if target.exists() or target.is_symlink():
        _invalid(f"OUTPUT_FILE_EXISTS:{target}")
    try:
        output.relative_to(run_directory.resolve())
    except ValueError:
        pass
    else:
        _invalid("OUTPUT_DIRECTORY_INSIDE_SOURCE_RUN")
    return output


def _atomic_write_json(path: Path, document: Mapping[str, Any]) -> None:
    payload = json.dumps(
        json.loads(canonical_json(dict(document))),
        ensure_ascii=True,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
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


def materialize_harmful_clean_results_directory(
    run_directory: Path,
    output_directory: Path,
    *,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate, analyze, and atomically write a new result directory."""
    output = check_output_destination(run_directory, output_directory)
    validated = load_and_reconcile_harmful_clean_run(run_directory)
    result = assemble_harmful_clean_result(
        validated, statistics_function=statistics_function
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    _atomic_write_json(output / OUTPUT_FILENAME, result)
    return result


def validation_summary(validated: ValidatedHarmfulCleanRun) -> dict[str, Any]:
    """Return validation facts without invoking the 10,000-replicate statistic."""
    payload = build_harmful_clean_payload(
        validated.prepared.clean_rows,
        validated.loaded.responses,
        validated.loaded.dispositions,
        expected_prompt_ids=validated.prepared.support.plan_inputs[
            "confirm_prompt_ids"
        ],
    )
    accounting = _descriptive_accounting(validated, payload)
    generation_metrics = compute_generation_metrics(validated.loaded.generations)
    return {
        "status": "HARMFUL_CLEAN_RESULT_VALIDATE_ONLY_PASS",
        "run_id": validated.loaded.run_directory.name,
        "scheduled": accounting["scheduled"],
        "terminal": accounting["terminal"],
        "retained_denominator": accounting["retained_denominator"],
        "terminal_partition": accounting["terminal_partition"],
        "label_counts": accounting["label_counts"],
        "generation_metrics": generation_metrics,
        "generation_metrics_validated": True,
        "statistics_payload_validated": True,
        "statistics_executed": False,
        "output_written": False,
        "generation_calls_added": 0,
        "judge_calls_added": 0,
    }


def validate_only(
    run_directory: Path, output_directory: Path
) -> dict[str, Any]:
    """Validate source and destination without creating output or running stats."""
    check_output_destination(run_directory, output_directory)
    validated = load_and_reconcile_harmful_clean_run(run_directory)
    return validation_summary(validated)


__all__ = [
    "FORMAL_HARMFUL_CLEAN_RUN_DIRECTORY",
    "HARMFUL_LABELS",
    "HarmfulCleanResultInputInvalid",
    "LoadedHarmfulCleanRun",
    "OUTPUT_FILENAME",
    "SCHEMA_VERSION",
    "ValidatedHarmfulCleanRun",
    "assemble_harmful_clean_result",
    "build_harmful_clean_payload",
    "check_output_destination",
    "compute_generation_metrics",
    "load_and_reconcile_harmful_clean_run",
    "load_harmful_clean_run",
    "materialize_harmful_clean_results_directory",
    "validate_only",
    "validation_summary",
]
