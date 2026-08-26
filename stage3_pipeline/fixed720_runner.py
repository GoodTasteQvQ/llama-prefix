"""Read-only fixed720 candidate-frame validation and deterministic allocation.

This module is deliberately downstream of the existing Stage 3 result
validators.  It materializes only allocator records and a candidate selection;
it never runs a model, judge, human workflow, or statistical procedure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import benign_integrity_results as benign_results
from . import harmful_clean_results as harmful_results
from . import p2_independent_formal_results as p2_formal
from . import p2_independent_results as p2_results
from .core import file_sha256
from .execution import TERMINAL_DISPOSITIONS
from .statistics import human_quota


IMPLEMENTATION_VERSION = "paper1-stage3-fixed720-runner-v1"
SCHEMA_VERSION = "paper1-stage3-fixed720-candidate-selection-v1"
OUTPUT_FILENAME = "fixed720_selection.json"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs/stage3/qwen25_fixed720_v1.json"

P2_SOURCE_RUN = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "p2-qwen25-amended-th-paper-20260822T051005Z-v2"
)
P2_FORMAL_RESULT = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "p2-v2-formal-qwen25-paper-20260822T051005Z-v1/p2_independent_formal_result.json"
)
HARMFUL_SOURCE_RUN = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "harmful-clean-qwen25-paper-20260825T071017Z"
)
HARMFUL_RESULT = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "harmful-clean-materialized-qwen25-paper-20260825T071017Z-v1/harmful_clean_result.json"
)
BENIGN_SOURCE_RUN = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "benign-integrity-qwen25-paper-recovery-20260825T102609Z"
)
BENIGN_RESULT = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "benign-integrity-materialized-qwen25-paper-recovery-20260825T102609Z-v2/benign_integrity_result.json"
)

ACTIVE_CELL_ORDER = tuple(human_quota.ACTIVE_P2_CELLS)
ACTIVE_MEMBER_MAPPING = dict(human_quota.ACTIVE_CELL_TO_MEMBER)
EXPECTED_ELIGIBLE = 4_621
EXPECTED_P2_PARSED = 3_942
EXPECTED_HARMFUL_PARSED = 50
EXPECTED_BENIGN_PARSED = 629
EXPECTED_P2_MATCHED_ARMS = {"T": 1_952, "H": 1_932}
EXPECTED_P2_UNMATCHED_ARMS = 58
EXPECTED_SELECTED = 720
EXPECTED_SEED = 42


class Fixed720InputInvalid(ValueError):
    """A fixed source, lineage, or allocator frame violated the contract."""

    code = "FIXED720_INPUT_INVALID"


def _invalid(detail: str) -> None:
    raise Fixed720InputInvalid(f"{Fixed720InputInvalid.code}:{detail}")


def _strict_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        _invalid(f"{label}:SOURCE_FILE_NOT_REGULAR:{path}")
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant: {token}")
            ),
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        _invalid(f"{label}:SOURCE_JSON:{exc}")
    if not isinstance(value, dict):
        _invalid(f"{label}:SOURCE_JSON_NOT_OBJECT")
    return value


def _read_config(path: Path | str) -> dict[str, Any]:
    try:
        config_path = Path(path)
    except (TypeError, ValueError) as exc:
        _invalid(f"CONFIG_PATH:{exc}")
    config = _strict_json(config_path, "CONFIG")
    if config.get("schema_version") != "paper1-stage3-qwen25-fixed720-v1":
        _invalid("CONFIG_SCHEMA_VERSION")
    return config


def _validate_formal_result(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    formal = _strict_json(path, "P2_FORMAL_RESULT")
    required = {
        "schema_version", "status", "amendment_id", "source_run_id", "M_T", "M_H",
        "cell_identity_counts", "terminal_partition", "paper_result_eligible",
        "statistics_not_run", "source", "raw_execution_fields",
    }
    if not required.issubset(formal):
        _invalid("P2_FORMAL_RESULT_FIELDS")
    if formal.get("schema_version") != p2_formal.FORMAL_RESULT_SCHEMA_VERSION:
        _invalid("P2_FORMAL_RESULT_SCHEMA_VERSION")
    if formal.get("status") != "ESTIMABLE":
        _invalid("P2_FORMAL_RESULT_STATUS")
    if formal.get("amendment_id") != p2_formal.AMENDMENT_ID:
        _invalid("P2_FORMAL_RESULT_AMENDMENT")
    if formal.get("source_run_id") != "p2-qwen25-amended-th-paper-20260822T051005Z-v2":
        _invalid("P2_FORMAL_RESULT_SOURCE_RUN")
    if formal.get("paper_result_eligible") is not False:
        _invalid("P2_FORMAL_RESULT_PAPER_ELIGIBILITY")
    if formal.get("M_T") != 976 or formal.get("M_H") != 966:
        _invalid("P2_FORMAL_RESULT_MATCHED_COUNTS")
    if formal.get("cell_identity_counts") != {
        "P2_H_all": 1_000, "P2_H_content": 1_000,
        "P2_T_all": 1_000, "P2_T_content": 1_000,
    }:
        _invalid("P2_FORMAL_RESULT_CELL_COUNTS")
    if formal.get("terminal_partition") != p2_formal.EXPECTED_TERMINAL_PARTITION:
        _invalid("P2_FORMAL_RESULT_TERMINAL_PARTITION")
    execution = formal.get("raw_execution_fields")
    if not isinstance(execution, Mapping) or any(
        execution.get(key) != value for key, value in {
            "paper_result_eligible": False, "formal_experiment_run": True,
            "fake_backend": False, "old_p2_run": False, "old_p2_unchanged": True,
            "amended_independent": True, "estimation_only": True,
            "generation_calls_added": 0, "judge_calls_added": 0,
            "statistics_not_run": True,
        }.items()
    ):
        _invalid("P2_FORMAL_RESULT_EXECUTION_FLAGS")
    source = formal.get("source")
    if not isinstance(source, Mapping) or not isinstance(source.get("raw_result"), Mapping):
        _invalid("P2_FORMAL_RESULT_SOURCE_LINEAGE")
    raw_ref = source["raw_result"]
    raw_path_value = raw_ref.get("path")
    if not isinstance(raw_path_value, str) or not raw_path_value:
        _invalid("P2_FORMAL_RESULT_RAW_PATH")
    raw_path = Path(raw_path_value)
    raw = _strict_json(raw_path, "P2_RAW_RESULT")
    try:
        p2_formal.validate_raw_result(raw)
    except p2_formal.P2IndependentFormalResultInvalid as exc:
        _invalid(f"P2_RAW_RESULT_VALIDATION:{exc}")
    if raw_ref.get("sha256") != hashlib.sha256(raw_path.read_bytes()).hexdigest():
        _invalid("P2_FORMAL_RESULT_RAW_HASH")
    return formal, raw


def _typed_p2_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        validated = p2_results.validate_independent_run(P2_SOURCE_RUN)
        raw_members = p2_results.build_independent_raw_members(
            validated.prepared.rows,
            validated.loaded.responses,
            generation_records=validated.loaded.generations,
            judge_records=validated.loaded.judges,
            dispositions=validated.loaded.dispositions,
        )
    except Exception as exc:
        if isinstance(exc, p2_results.P2IndependentResultInputInvalid):
            _invalid(f"P2_SOURCE_VALIDATION:{exc}")
        _invalid(f"P2_SOURCE_RECONCILIATION:{exc}")
    formal, raw = _validate_formal_result(P2_FORMAL_RESULT)
    if validated.loaded.run_directory != P2_SOURCE_RUN.resolve():
        _invalid("P2_SOURCE_DIRECTORY_LINEAGE")
    if validated.reconciliation.get("matched_sets", {}).get("M_T", {}).get("valid_pair_count") != formal["M_T"]:
        _invalid("P2_M_T_COUNT_DIFFERS_FORMAL")
    if validated.reconciliation.get("matched_sets", {}).get("M_H", {}).get("valid_pair_count") != formal["M_H"]:
        _invalid("P2_M_H_COUNT_DIFFERS_FORMAL")
    if raw.get("source_run_id") != formal["source_run_id"]:
        _invalid("P2_RAW_SOURCE_RUN_LINEAGE")
    raw_members_by_id = {member["member_id"]: member for member in raw.get("members", [])}
    built_members_by_id = {member["member_id"]: member for member in raw_members["members"]}
    if set(raw_members_by_id) != set(built_members_by_id):
        _invalid("P2_RAW_MEMBER_ORDER")
    for member_id in ("P2-U(T)", "P2-B(H)"):
        expected_pairs = {
            (row["prompt_id"], row["vector_id"])
            for row in raw_members_by_id[member_id].get("records", [])
        }
        actual_pairs = {
            (row["prompt_id"], row["vector_id"])
            for row in built_members_by_id[member_id].get("records", [])
        }
        if expected_pairs != actual_pairs:
            _invalid(f"P2_RAW_MEMBER_COORDINATES:{member_id}")
    matched_pairs_by_member = {
        member["member_id"]: {
            (row["prompt_id"], row["vector_id"]) for row in member["records"]
        }
        for member in raw_members["members"]
    }
    member_for_cell = {
        "P2_T_all": "P2-U(T)", "P2_T_content": "P2-U(T)",
        "P2_H_all": "P2-B(H)", "P2_H_content": "P2-B(H)",
    }
    disposition_by_id = {row["logical_id"]: row for row in validated.loaded.dispositions}
    records: list[dict[str, Any]] = []
    for response in validated.loaded.responses:
        logical_id = response.get("logical_id")
        if response.get("terminal_status") != "COMPLETED_PARSED":
            continue
        if response.get("label") not in human_quota.HARMFUL_CLASSES or response.get("retained") is not True:
            _invalid(f"P2_PARSED_RESPONSE_INVALID:{logical_id}")
        if logical_id not in disposition_by_id or disposition_by_id[logical_id].get("terminal_disposition") != "COMPLETED_PARSED":
            _invalid(f"P2_DISPOSITION_MISMATCH:{logical_id}")
        coordinate = (response.get("prompt_id"), response.get("vector_id"))
        member_id = member_for_cell.get(response.get("cell"))
        if member_id is None:
            _invalid(f"P2_CELL_MAPPING:{logical_id}")
        records.append({
            "response_id": logical_id,
            "block": "P2",
            "predicted_class": response["label"],
            "matched": coordinate in matched_pairs_by_member[member_id],
            "logical_cell": response.get("cell"),
        })
    if len(records) != EXPECTED_P2_PARSED:
        _invalid(f"P2_PARSED_COUNT:{len(records)}")
    matched_count = sum(record["matched"] for record in records)
    if matched_count != sum(EXPECTED_P2_MATCHED_ARMS.values()):
        _invalid(f"P2_MATCHED_ARM_COUNT:{matched_count}")
    if len(records) - matched_count != EXPECTED_P2_UNMATCHED_ARMS:
        _invalid("P2_UNMATCHED_ARM_COUNT")
    cell_counts = {cell: sum(row["logical_cell"] == cell for row in records) for cell in ACTIVE_CELL_ORDER}
    expected_cell_counts = {
        "P2_T_all": 986, "P2_T_content": 990,
        "P2_H_all": 975, "P2_H_content": 991,
    }
    if cell_counts != expected_cell_counts:
        _invalid(f"P2_PARSED_CELL_COUNTS:{cell_counts}")
    return records, {
        "formal_result_path": str(P2_FORMAL_RESULT.resolve()),
        "formal_result_sha256": file_sha256(P2_FORMAL_RESULT),
        "source_run_id": validated.loaded.run_directory.name,
        "source_run_directory": str(validated.loaded.run_directory),
        "source_file_sha256": dict(validated.loaded.file_sha256),
        "amendment_id": formal["amendment_id"],
        "matched_sets": {"M_T": formal["M_T"], "M_H": formal["M_H"]},
    }


def _completed_records(
    responses: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    *,
    block: str,
    labels: Sequence[str],
    cells: set[str],
) -> list[dict[str, Any]]:
    disposition_by_id: dict[str, Mapping[str, Any]] = {}
    for disposition in dispositions:
        logical_id = disposition.get("logical_id")
        if not isinstance(logical_id, str) or logical_id in disposition_by_id:
            _invalid(f"{block}:DUPLICATE_DISPOSITION:{logical_id}")
        disposition_by_id[logical_id] = disposition
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for response in responses:
        logical_id = response.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in seen:
            _invalid(f"{block}:DUPLICATE_RESPONSE:{logical_id}")
        seen.add(logical_id)
        disposition = disposition_by_id.get(logical_id)
        if disposition is None:
            _invalid(f"{block}:MISSING_DISPOSITION:{logical_id}")
        terminal = response.get("terminal_status") or disposition.get("terminal_disposition")
        if terminal == "COMPLETED_PARSED":
            if disposition.get("terminal_disposition") != "COMPLETED_PARSED":
                _invalid(f"{block}:TERMINAL_LINEAGE:{logical_id}")
            if response.get("label") not in labels:
                _invalid(f"{block}:INVALID_LABEL:{logical_id}")
            if block != "harmful_clean" and (
                response.get("retained") is not True or response.get("judge_eligible") is not True
            ):
                _invalid(f"{block}:PARSED_NOT_ELIGIBLE:{logical_id}")
            cell = response.get("cell")
            if block != "harmful_clean" and cell not in cells:
                _invalid(f"{block}:CELL_MAPPING:{logical_id}:{cell}")
            records.append({
                "response_id": logical_id,
                "block": block,
                "predicted_class": response["label"],
                "matched": False,
            })
        elif terminal in TERMINAL_DISPOSITIONS:
            if disposition.get("terminal_disposition") != terminal:
                _invalid(f"{block}:FAILED_TERMINAL_LINEAGE:{logical_id}")
            if response.get("label") is not None or response.get("retained") is not False:
                _invalid(f"{block}:FAILED_RESPONSE_RELABELED:{logical_id}")
        else:
            _invalid(f"{block}:UNKNOWN_TERMINAL:{logical_id}")
    return records


def _typed_non_p2_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        harmful_validated = harmful_results.load_and_reconcile_harmful_clean_run(HARMFUL_SOURCE_RUN)
        harmful_results.build_harmful_clean_payload(
            harmful_validated.prepared.clean_rows,
            harmful_validated.loaded.responses,
            harmful_validated.loaded.dispositions,
            expected_prompt_ids=harmful_validated.prepared.support.plan_inputs["confirm_prompt_ids"],
        )
        benign_validated = benign_results.load_and_reconcile_benign_integrity_run(BENIGN_SOURCE_RUN)
        expected_prompts = benign_validated.prepared.support.plan_inputs["benign_prompt_ids"]
        expected_vectors = [benign_validated.prepared.support.vector_ids_by_index[i] for i in range(10, 30)]
        benign_results.build_benign_broken_payload(
            benign_validated.prepared.benign_T_rows,
            benign_validated.prepared.benign_clean_rows,
            benign_validated.loaded.responses,
            benign_validated.loaded.dispositions,
            expected_prompt_ids=expected_prompts,
            expected_vector_ids=expected_vectors,
        )
    except Exception as exc:
        if isinstance(exc, (harmful_results.HarmfulCleanResultInputInvalid, benign_results.BenignIntegrityResultInputInvalid)):
            _invalid(f"NON_P2_SOURCE_VALIDATION:{exc}")
        _invalid(f"NON_P2_SOURCE_RECONCILIATION:{exc}")
    harmful_result = _strict_json(HARMFUL_RESULT, "HARMFUL_RESULT")
    benign_result = _strict_json(BENIGN_RESULT, "BENIGN_RESULT")
    _validate_accepted_clean_result(
        harmful_result,
        schema="paper1-stage3-harmful-clean-result-materialization-v1",
        source_run_id=harmful_validated.loaded.run_directory.name,
        expected_count=EXPECTED_HARMFUL_PARSED,
        label_key="harmful_clean",
    )
    _validate_accepted_clean_result(
        benign_result,
        schema="paper1-stage3-benign-integrity-result-materialization-v1",
        source_run_id=benign_validated.loaded.run_directory.name,
        expected_count=EXPECTED_BENIGN_PARSED,
        label_key="benign_integrity",
    )
    harmful = _completed_records(
        harmful_validated.loaded.responses,
        harmful_validated.loaded.dispositions,
        block="harmful_clean", labels=tuple(harmful_results.HARMFUL_LABELS), cells={"harmful_clean"},
    )
    benign_rows = list(benign_validated.loaded.responses)
    benign_dispositions = list(benign_validated.loaded.dispositions)
    benign_clean = [row for row in benign_rows if row.get("cell") == "benign_clean"]
    benign_steered = [row for row in benign_rows if row.get("cell") == "benign_T"]
    clean_ids = {row["logical_id"] for row in benign_clean}
    steered_ids = {row["logical_id"] for row in benign_steered}
    benign_clean_disp = [row for row in benign_dispositions if row.get("logical_id") in clean_ids]
    benign_steered_disp = [row for row in benign_dispositions if row.get("logical_id") in steered_ids]
    clean = _completed_records(
        benign_clean, benign_clean_disp,
        block="benign_clean", labels=tuple(benign_results.BENIGN_LABELS), cells={"benign_clean"},
    )
    steered = _completed_records(
        benign_steered, benign_steered_disp,
        block="benign_steered", labels=tuple(benign_results.BENIGN_LABELS), cells={"benign_T"},
    )
    if len(harmful) != EXPECTED_HARMFUL_PARSED or len(clean) + len(steered) != EXPECTED_BENIGN_PARSED:
        _invalid(f"NON_P2_PARSED_COUNTS:{len(harmful)},{len(clean) + len(steered)}")
    source = {
        "harmful_clean": {
            "source_run_id": harmful_validated.loaded.run_directory.name,
            "source_run_directory": str(harmful_validated.loaded.run_directory),
            "accepted_result_path": str(HARMFUL_RESULT.resolve()),
            "accepted_result_sha256": file_sha256(HARMFUL_RESULT),
            "source_file_sha256": dict(harmful_validated.loaded.file_sha256),
        },
        "benign_integrity": {
            "source_run_id": benign_validated.loaded.run_directory.name,
            "source_run_directory": str(benign_validated.loaded.run_directory),
            "accepted_result_path": str(BENIGN_RESULT.resolve()),
            "accepted_result_sha256": file_sha256(BENIGN_RESULT),
            "source_file_sha256": dict(benign_validated.loaded.file_sha256),
        },
    }
    return [*harmful, *clean, *steered], source


def _validate_accepted_clean_result(
    result: Mapping[str, Any], *, schema: str, source_run_id: str,
    expected_count: int, label_key: str,
) -> None:
    if result.get("schema_version") != schema or result.get("status") != "ESTIMABLE":
        _invalid(f"{label_key}:ACCEPTED_RESULT_STATUS")
    if result.get("paper_result_eligible") is not False:
        _invalid(f"{label_key}:ACCEPTED_RESULT_PAPER_ELIGIBILITY")
    if result.get("generation_calls_added") != 0 or result.get("judge_calls_added") != 0:
        _invalid(f"{label_key}:ACCEPTED_RESULT_CALLS")
    source = result.get("source")
    if not isinstance(source, Mapping) or source.get("run_id") != source_run_id:
        _invalid(f"{label_key}:ACCEPTED_RESULT_SOURCE_LINEAGE")
    accounting = result.get("accounting")
    if not isinstance(accounting, Mapping):
        _invalid(f"{label_key}:ACCEPTED_RESULT_ACCOUNTING")
    if label_key == "harmful_clean":
        count = accounting.get("retained_denominator")
    else:
        partition = accounting.get("terminal_partition")
        count = partition.get("COMPLETED_PARSED") if isinstance(partition, Mapping) else None
    if count != expected_count:
        _invalid(f"{label_key}:ACCEPTED_RESULT_COUNT:{count}")


def build_eligible_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load all fixed sources and return the validated allocator frame."""
    p2_records, p2_source = _typed_p2_records()
    other_records, other_source = _typed_non_p2_records()
    records = [*p2_records, *other_records]
    try:
        human_quota._validate_records(records, ACTIVE_CELL_ORDER)
    except human_quota.AllocationError as exc:
        _invalid(f"ALLOCATOR_RECORD_VALIDATION:{exc}")
    if len(records) != EXPECTED_ELIGIBLE:
        _invalid(f"ELIGIBLE_COUNT:{len(records)}")
    source = {"p2": p2_source, **other_source}
    return records, source


def assemble_fixed720(
    *, n_total: int = EXPECTED_SELECTED, master_seed: int = EXPECTED_SEED
) -> dict[str, Any]:
    records, source = build_eligible_records()
    if n_total != EXPECTED_SELECTED or master_seed != EXPECTED_SEED:
        _invalid("FIXED720_PARAMETERS")
    trace = human_quota.allocate_human_sample(
        records,
        n_total=n_total,
        master_seed=master_seed,
        active_cell_order=ACTIVE_CELL_ORDER,
        member_mapping=ACTIVE_MEMBER_MAPPING,
    )
    if trace.get("eligible_n") != EXPECTED_ELIGIBLE or trace.get("selected_n") != EXPECTED_SELECTED:
        _invalid("ALLOCATOR_ACCOUNTING")
    selected_ids = trace.get("selected_response_ids")
    if not isinstance(selected_ids, list) or len(selected_ids) != EXPECTED_SELECTED:
        _invalid("ALLOCATOR_SELECTED_IDS")
    records_by_id = {row["response_id"]: row for row in records}
    if set(selected_ids) - set(records_by_id):
        _invalid("ALLOCATOR_SELECTED_ID_UNKNOWN")
    selected_records = [records_by_id[response_id] for response_id in selected_ids]
    return {
        "schema_version": SCHEMA_VERSION,
        "implementation_version": IMPLEMENTATION_VERSION,
        "status": "FIXED720_CANDIDATE_SELECTION",
        "fixed720_status": trace["fixed720_status"],
        "requested_n": n_total,
        "eligible_n": len(records),
        "selected_n": len(selected_ids),
        "active_amendment_id": p2_formal.AMENDMENT_ID,
        "active_source_run_ids": {
            "p2": source["p2"]["source_run_id"],
            "harmful_clean": source["harmful_clean"]["source_run_id"],
            "benign_integrity": source["benign_integrity"]["source_run_id"],
        },
        "active_endpoint_member_mapping": {
            "cell_order": list(ACTIVE_CELL_ORDER),
            "cell_to_member": dict(ACTIVE_MEMBER_MAPPING),
            "members": ["P2-U(T)", "P2-B(H)"],
        },
        "source": source,
        "allocator_trace": trace,
        "stratum_capacities": trace["stratum_capacities"],
        "stratum_quotas": trace["stratum_quotas"],
        "selected_response_ids": selected_ids,
        "selected_records": selected_records,
        "selected_ids_sha256": trace["selected_ids_sha256"],
        "trace_sha256": trace["trace_sha256"],
        "paper_result_eligible": False,
        "gold_visible": False,
        "human_annotation_run": False,
        "two_phase_run": False,
        "model_calls": 0,
    }


def _output_path(output_directory: Path | str) -> Path:
    try:
        output = Path(output_directory)
    except (TypeError, ValueError) as exc:
        _invalid(f"OUTPUT_DIRECTORY:{exc}")
    if output.exists() or output.is_symlink():
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    target = output / OUTPUT_FILENAME
    if target.exists() or target.is_symlink():
        _invalid(f"OUTPUT_FILE_EXISTS:{target}")
    return output.resolve()


def _atomic_write(path: Path, document: Mapping[str, Any]) -> None:
    payload = json.dumps(document, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
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


def validate_only(config_path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    """Validate fixed sources and frame without creating output or selecting."""
    config = _read_config(Path(config_path))
    _validate_config_contract(config)
    records, source = build_eligible_records()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "FIXED720_VALIDATE_ONLY_PASS",
        "validate_only": True,
        "eligible_n": len(records),
        "requested_n": int(config.get("requested_n", EXPECTED_SELECTED)),
        "selected_n": None,
        "active_amendment_id": p2_formal.AMENDMENT_ID,
        "active_source_run_ids": {key: value["source_run_id"] for key, value in source.items() if isinstance(value, Mapping) and "source_run_id" in value},
        "active_endpoint_member_mapping": {
            "cell_order": list(ACTIVE_CELL_ORDER), "cell_to_member": dict(ACTIVE_MEMBER_MAPPING),
        },
        "statistics_not_run": True,
        "output_written": False,
        "paper_result_eligible": False,
        "gold_visible": False,
        "human_annotation_run": False,
        "two_phase_run": False,
        "model_calls": 0,
    }


def _validate_config_contract(config: Mapping[str, Any]) -> None:
    if config.get("requested_n") != EXPECTED_SELECTED or config.get("master_seed") != EXPECTED_SEED:
        _invalid("CONFIG_FIXED_PARAMETERS")
    paths = {
        "p2_source_run": P2_SOURCE_RUN,
        "p2_formal_result": P2_FORMAL_RESULT,
        "harmful_source_run": HARMFUL_SOURCE_RUN,
        "harmful_result": HARMFUL_RESULT,
        "benign_source_run": BENIGN_SOURCE_RUN,
        "benign_result": BENIGN_RESULT,
    }
    for key, expected in paths.items():
        configured = Path(config.get(key, expected))
        if configured.resolve() != expected.resolve():
            _invalid(f"CONFIG_ACTIVE_PATH:{key}")
    if tuple(config.get("active_cell_order", ())) != ACTIVE_CELL_ORDER:
        _invalid("CONFIG_ACTIVE_CELL_ORDER")
    if config.get("active_member_mapping") != ACTIVE_MEMBER_MAPPING:
        _invalid("CONFIG_ACTIVE_MEMBER_MAPPING")


def run_fixed720(
    config_path: Path | str = DEFAULT_CONFIG, *, output_directory: Path | str | None = None
) -> dict[str, Any]:
    """Perform deterministic allocation and write exactly one selection JSON."""
    config = _read_config(Path(config_path))
    _validate_config_contract(config)
    target = output_directory if output_directory is not None else config.get("output_directory")
    if not isinstance(target, (str, Path)) or not str(target):
        _invalid("OUTPUT_DIRECTORY_REQUIRED")
    output = _output_path(target)
    selection = assemble_fixed720(
        n_total=int(config["requested_n"]), master_seed=int(config["master_seed"])
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError as exc:
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    _atomic_write(output / OUTPUT_FILENAME, selection)
    return selection


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or allocate Paper 1 Stage 3 fixed720 candidates")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = validate_only(args.config) if args.validate_only else run_fixed720(args.config, output_directory=args.output_directory)
    except Fixed720InputInvalid as exc:
        print(f"FIXED720-RUNNER-IMPLEMENTATION-FAIL\n{exc}")
        return 2
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


__all__ = [
    "ACTIVE_CELL_ORDER", "ACTIVE_MEMBER_MAPPING", "BENIGN_RESULT", "BENIGN_SOURCE_RUN",
    "Fixed720InputInvalid", "HARMFUL_RESULT", "HARMFUL_SOURCE_RUN", "OUTPUT_FILENAME",
    "P2_FORMAL_RESULT", "P2_SOURCE_RUN", "assemble_fixed720", "build_eligible_records",
    "run_fixed720", "validate_only",
]


if __name__ == "__main__":
    raise SystemExit(main())
