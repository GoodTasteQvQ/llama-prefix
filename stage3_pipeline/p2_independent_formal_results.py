"""Formal, read-only statistical post-processing for the amended P2 run.

The source is the already materialized v2 raw result.  This module does not
load a model, inspect execution records, or materialize any new pair.  It
validates the raw materialization and delegates the fixed-scale simultaneous
procedure to :func:`reference_statistics.p2_raw_simultaneous`.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from .statistics import reference_statistics


ROOT = Path(__file__).resolve().parents[1]
RAW_RESULT_SCHEMA_VERSION = "paper1-stage3-p2-independent-th-result-materialization-v1"
FORMAL_RESULT_SCHEMA_VERSION = "paper1-stage3-p2-independent-th-formal-result-v1"
AMENDMENT_ID = "paper1-stage3-p2-independent-th-v2"
FORMAL_SUPPLEMENT_STATUS = "FORMAL AMENDED T/H P2 RESULT"
SOURCE_RUN_ID = "p2-qwen25-amended-th-paper-20260822T051005Z-v2"
OUTPUT_FILENAME = "p2_independent_formal_result.json"
FORMAL_REPLICATES = 9_999
FORMAL_MIN_SUCCESS = 9_500
P2_CELL_COUNT = 1_000
MATCHED_COUNTS = {"M_T": 976, "M_H": 966}
MEMBER_ORDER = ["P2-U(T)", "P2-B(H)"]

DEFAULT_RAW_RESULT = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "p2-amended-th-materialized-qwen25-paper-20260822T051005Z-v1/"
    "p2_independent_raw_result.json"
)
DEFAULT_FORMAL_SUPPLEMENT = (
    ROOT / "writing/stage3 design/paper1_stage3_protocol_status_supplement_p2_v2_formal.md"
)
DEFAULT_PROTOCOL = ROOT / "writing/stage3 design/paper1_stage3_protocol_amendment_p2_v2.md"

EXPECTED_ENDPOINT_ORDER = [
    {
        "all_cell": "P2_T_all",
        "anchor": "T",
        "content_cell": "P2_T_content",
        "contrast": "all-minus-content",
        "matched_set": "M_T",
        "member_id": "P2-U(T)",
        "outcome": "unsafe",
    },
    {
        "all_cell": "P2_H_all",
        "anchor": "H",
        "content_cell": "P2_H_content",
        "contrast": "all-minus-content",
        "matched_set": "M_H",
        "member_id": "P2-B(H)",
        "outcome": "broken",
    },
]
EXPECTED_CELL_COUNTS = {
    "P2_H_all": P2_CELL_COUNT,
    "P2_H_content": P2_CELL_COUNT,
    "P2_T_all": P2_CELL_COUNT,
    "P2_T_content": P2_CELL_COUNT,
}
EXPECTED_TERMINAL_PARTITION = {
    "COMPLETED_PARSED": 3_942,
    "NON_ESTIMABLE_DOSE": 0,
    "NON_ESTIMABLE_IDENTITY": 0,
    "TERMINAL_GENERATION_DETERMINISTIC_FAILURE": 0,
    "TERMINAL_GENERATION_INDETERMINATE_FAILURE": 0,
    "TERMINAL_GENERATION_TECHNICAL_FAILURE": 0,
    "TERMINAL_JUDGE_FAILURE": 58,
    "TERMINAL_JUDGE_INDETERMINATE_FAILURE": 0,
    "TERMINAL_PREJUDGE_FAILURE": 0,
    "UNATTEMPTED_DUE_INTEGRITY_BLOCK": 0,
}


class P2IndependentFormalResultInvalid(ValueError):
    """The raw result or formal source documents violate the v2 contract."""

    code = "P2_INDEPENDENT_FORMAL_RESULT_INVALID"


def _invalid(detail: str) -> None:
    raise P2IndependentFormalResultInvalid(
        f"{P2IndependentFormalResultInvalid.code}:{detail}"
    )


def _path(value: Path | str, label: str) -> Path:
    try:
        result = Path(value)
    except (TypeError, ValueError) as exc:
        _invalid(f"{label}:NOT_PATH:{exc}")
    return result


def _read_json(path: Path | str, label: str) -> tuple[dict[str, Any], str]:
    source = _path(path, label)
    if source.is_symlink() or not source.is_file():
        _invalid(f"{label}:SOURCE_FILE_NOT_REGULAR:{source}")
    try:
        raw = source.read_bytes()
        text = raw.decode("utf-8")

        def reject_constant(value: str) -> None:
            raise ValueError(f"non-finite JSON constant: {value}")

        value = json.loads(text, parse_constant=reject_constant)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        _invalid(f"{label}:SOURCE_JSON:{exc}")
    if not isinstance(value, dict):
        _invalid(f"{label}:SOURCE_JSON_NOT_OBJECT")
    return value, hashlib.sha256(raw).hexdigest()


def _read_text(path: Path | str, label: str) -> tuple[str, str]:
    source = _path(path, label)
    if source.is_symlink() or not source.is_file():
        _invalid(f"{label}:SOURCE_FILE_NOT_REGULAR:{source}")
    try:
        raw = source.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        _invalid(f"{label}:SOURCE_TEXT:{exc}")
    return text, hashlib.sha256(raw).hexdigest()


def _is_binary(value: Any) -> bool:
    return type(value) is int and value in (0, 1)


def _is_count(value: Any) -> bool:
    return type(value) is int and value >= 0


def _validate_member(member: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    member_id = expected["member_id"]
    if not isinstance(member, Mapping):
        _invalid(f"MEMBER_NOT_OBJECT:{member_id}")
    for field, expected_value in expected.items():
        if member.get(field) != expected_value:
            _invalid(f"MEMBER_FIELD_MISMATCH:{member_id}:{field}")
    matched = MATCHED_COUNTS[expected["matched_set"]]
    if (
        not _is_count(member.get("scheduled_pair_count"))
        or not _is_count(member.get("matched_pair_count"))
        or not _is_count(member.get("missing_pair_count"))
        or member.get("scheduled_pair_count") != P2_CELL_COUNT
        or member.get("matched_pair_count") != matched
        or member.get("missing_pair_count") != P2_CELL_COUNT - matched
    ):
        _invalid(f"MEMBER_COUNTS:{member_id}")
    records = member.get("records")
    missing_pairs = member.get("missing_pairs")
    if not isinstance(records, list) or len(records) != matched:
        _invalid(f"MEMBER_RECORD_COUNT:{member_id}")
    if not isinstance(missing_pairs, list) or len(missing_pairs) != P2_CELL_COUNT - matched:
        _invalid(f"MEMBER_MISSING_PAIR_COUNT:{member_id}")

    record_pairs: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            _invalid(f"MEMBER_RECORD_NOT_OBJECT:{member_id}:{index}")
        prompt_id, vector_id = record.get("prompt_id"), record.get("vector_id")
        if not isinstance(prompt_id, str) or not prompt_id or not isinstance(vector_id, str) or not vector_id:
            _invalid(f"MEMBER_RECORD_PAIR_FIELDS:{member_id}:{index}")
        pair = (prompt_id, vector_id)
        if pair in record_pairs:
            _invalid(f"MEMBER_DUPLICATE_PAIR:{member_id}:{prompt_id}:{vector_id}")
        record_pairs.add(pair)
        if record.get("anchor") != expected["anchor"] or record.get("outcome") != expected["outcome"]:
            _invalid(f"MEMBER_RECORD_IDENTITY:{member_id}:{index}")
        if record.get("pair_id") != f"{expected['anchor']}|{prompt_id}|{vector_id}":
            _invalid(f"MEMBER_RECORD_PAIR_ID:{member_id}:{index}")
        if not _is_binary(record.get("all_value")) or not _is_binary(record.get("content_value")):
            _invalid(f"MEMBER_RECORD_BINARY_VALUE:{member_id}:{index}")
        difference = record.get("difference")
        if isinstance(difference, bool) or not isinstance(difference, (int, float)):
            _invalid(f"MEMBER_DIFFERENCE_TYPE:{member_id}:{index}")
        if not math.isfinite(float(difference)) or difference not in (-1, 0, 1):
            _invalid(f"MEMBER_DIFFERENCE_RANGE:{member_id}:{index}")
        if difference != record["all_value"] - record["content_value"]:
            _invalid(f"MEMBER_DIFFERENCE_MISMATCH:{member_id}:{index}")
        arms = record.get("arms")
        if arms is not None:
            if not isinstance(arms, Mapping) or not {"all", "content"}.issubset(arms):
                _invalid(f"MEMBER_RECORD_ARMS:{member_id}:{index}")
            if any(
                not isinstance(arms[arm], Mapping)
                or arms[arm].get("terminal_status") != "COMPLETED_PARSED"
                for arm in ("all", "content")
            ):
                _invalid(f"MEMBER_RECORD_NOT_COMPLETED:{member_id}:{index}")

    missing_record_pairs: set[tuple[str, str]] = set()
    for index, missing in enumerate(missing_pairs):
        if not isinstance(missing, Mapping):
            _invalid(f"MISSING_PAIR_NOT_OBJECT:{member_id}:{index}")
        prompt_id, vector_id = missing.get("prompt_id"), missing.get("vector_id")
        if not isinstance(prompt_id, str) or not prompt_id or not isinstance(vector_id, str) or not vector_id:
            _invalid(f"MISSING_PAIR_FIELDS:{member_id}:{index}")
        pair = (prompt_id, vector_id)
        if pair in missing_record_pairs or pair in record_pairs:
            _invalid(f"MISSING_PAIR_DUPLICATE_OR_MATCHED:{member_id}:{index}")
        missing_record_pairs.add(pair)
        if missing.get("anchor") != expected["anchor"]:
            _invalid(f"MISSING_PAIR_ANCHOR:{member_id}:{index}")
        if missing.get("pair_id") != f"{expected['anchor']}|{prompt_id}|{vector_id}":
            _invalid(f"MISSING_PAIR_ID:{member_id}:{index}")
        # The materializer's missing-pair traces identify the failed arm.  A
        # compact synthetic fixture may omit traces, but a present trace must
        # never describe an analyzable pair as missing.
        arms = missing.get("arms")
        if arms is not None:
            if not isinstance(arms, Mapping) or not {"all", "content"}.issubset(arms):
                _invalid(f"MISSING_PAIR_ARMS:{member_id}:{index}")
            statuses = [
                arms[arm].get("terminal_status")
                for arm in ("all", "content")
                if isinstance(arms.get(arm), Mapping)
            ]
            if (
                len(statuses) != 2
                or any(status not in EXPECTED_TERMINAL_PARTITION for status in statuses)
                or all(status == "COMPLETED_PARSED" for status in statuses)
            ):
                _invalid(f"MISSING_PAIR_COMPLETED:{member_id}:{index}")
    if len(record_pairs | missing_record_pairs) != P2_CELL_COUNT:
        _invalid(f"MEMBER_PAIR_ACCOUNTING:{member_id}")


def validate_raw_result(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the v2 materialization and return it without modification."""
    if not isinstance(raw, Mapping):
        _invalid("RAW_RESULT_NOT_OBJECT")
    required = {
        "schema_version", "status", "amendment_id", "endpoint_order", "member_order",
        "identity_count", "cell_identity_counts", "cell_counts", "terminal_partition",
        "M_T", "M_H", "members", "source_run_id", "paper_result_eligible",
        "formal_experiment_run", "fake_backend", "statistics_not_run",
        "amended_independent", "estimation_only", "scope", "old_p2_run",
        "old_p2_unchanged", "generation_calls_added", "judge_calls_added",
    }
    missing = sorted(required - set(raw))
    if missing:
        _invalid(f"RAW_RESULT_FIELDS_MISSING:{','.join(missing)}")
    if raw.get("schema_version") != RAW_RESULT_SCHEMA_VERSION:
        _invalid("RAW_RESULT_SCHEMA_VERSION")
    if raw.get("status") != "RAW_MEMBERS_READY":
        _invalid("RAW_RESULT_STATUS")
    if raw.get("amendment_id") != AMENDMENT_ID:
        _invalid("AMENDMENT_ID")
    if raw.get("source_run_id") != SOURCE_RUN_ID:
        _invalid("SOURCE_RUN_ID")
    if raw.get("member_order") != MEMBER_ORDER:
        _invalid("MEMBER_ORDER")
    if raw.get("endpoint_order") != EXPECTED_ENDPOINT_ORDER:
        _invalid("ENDPOINT_ORDER")
    if not _is_count(raw.get("identity_count")) or raw.get("identity_count") != 4_000:
        _invalid("CELL_IDENTITY_COUNTS")
    cell_identity_counts = raw.get("cell_identity_counts")
    if (
        not isinstance(cell_identity_counts, Mapping)
        or set(cell_identity_counts) != set(EXPECTED_CELL_COUNTS)
        or any(
            not _is_count(cell_identity_counts.get(cell))
            or cell_identity_counts.get(cell) != P2_CELL_COUNT
            for cell in EXPECTED_CELL_COUNTS
        )
    ):
        _invalid("CELL_IDENTITY_COUNTS")
    if (
        not _is_count(raw.get("M_T"))
        or not _is_count(raw.get("M_H"))
        or raw.get("M_T") != MATCHED_COUNTS["M_T"]
        or raw.get("M_H") != MATCHED_COUNTS["M_H"]
    ):
        _invalid("MATCHED_COUNTS")
    if raw.get("terminal_partition") != EXPECTED_TERMINAL_PARTITION:
        _invalid("TERMINAL_PARTITION")
    if raw.get("paper_result_eligible") is not False:
        _invalid("PAPER_RESULT_ELIGIBILITY_MUST_REMAIN_FALSE")
    if raw.get("formal_experiment_run") is not True or raw.get("fake_backend") is not False:
        _invalid("RAW_EXECUTION_FLAGS")
    if raw.get("statistics_not_run") is not True:
        _invalid("RAW_STATISTICS_ALREADY_RUN")
    if (
        raw.get("amended_independent") is not True
        or raw.get("estimation_only") is not True
        or raw.get("scope") != "amended_independent_estimation_only"
        or raw.get("old_p2_run") is not False
        or raw.get("old_p2_unchanged") is not True
        or raw.get("generation_calls_added") != 0
        or raw.get("judge_calls_added") != 0
    ):
        _invalid("RAW_MATERIALIZATION_FLAGS")
    cells = raw.get("cell_counts")
    if not isinstance(cells, Mapping) or set(cells) != set(EXPECTED_CELL_COUNTS):
        _invalid("CELL_COUNTS_KEYS")
    for endpoint in EXPECTED_ENDPOINT_ORDER:
        matched = MATCHED_COUNTS[endpoint["matched_set"]]
        for cell in (endpoint["all_cell"], endpoint["content_cell"]):
            count = cells[cell]
            if not isinstance(count, Mapping):
                _invalid(f"CELL_COUNT_NOT_OBJECT:{cell}")
            if not _is_count(count.get("scheduled_record_count")) or count.get("scheduled_record_count") != P2_CELL_COUNT:
                _invalid(f"CELL_SCHEDULED_COUNT:{cell}")
            if (
                not _is_count(count.get("matched_record_count"))
                or not _is_count(count.get("excluded_record_count"))
                or count.get("matched_record_count") != matched
                or count.get("excluded_record_count") != P2_CELL_COUNT - matched
            ):
                _invalid(f"CELL_MATCHED_COUNT:{cell}")
            terminal_counts = count.get("terminal_status_counts")
            if not isinstance(terminal_counts, Mapping):
                _invalid(f"CELL_TERMINAL_COUNTS:{cell}")
            expected_terminal_keys = set(EXPECTED_TERMINAL_PARTITION) - {
                "UNATTEMPTED_DUE_INTEGRITY_BLOCK"
            }
            if set(terminal_counts) != expected_terminal_keys or not all(
                _is_count(value) for value in terminal_counts.values()
            ):
                _invalid(f"CELL_TERMINAL_COUNTS:{cell}")
            try:
                terminal_total = sum(terminal_counts.values())
            except (TypeError, ValueError):
                _invalid(f"CELL_TERMINAL_COUNTS:{cell}")
            if terminal_total != P2_CELL_COUNT:
                _invalid(f"CELL_TERMINAL_COUNTS:{cell}")
            if count.get("completed_parsed_record_count") != terminal_counts.get("COMPLETED_PARSED"):
                _invalid(f"CELL_COMPLETED_COUNT:{cell}")
    members = raw.get("members")
    if not isinstance(members, list) or len(members) != len(EXPECTED_ENDPOINT_ORDER):
        _invalid("MEMBERS")
    member_fields = (
        "member_id", "matched_set", "anchor", "outcome", "all_cell", "content_cell",
    )
    for member, endpoint in zip(members, EXPECTED_ENDPOINT_ORDER):
        _validate_member(member, {field: endpoint[field] for field in member_fields})
    if raw.get("source") is not None and not isinstance(raw.get("source"), Mapping):
        _invalid("SOURCE_NOT_OBJECT")
    return raw


def _validate_supplement(text: str) -> dict[str, str]:
    if "# Paper 1 Stage 3 P2 v2 Formal Status Supplement" not in text:
        _invalid("FORMAL_SUPPLEMENT_TITLE")
    status_match = re.search(r"^Status:\s*`([^`]+)`\s*$", text, flags=re.MULTILINE)
    if status_match is None or status_match.group(1) != FORMAL_SUPPLEMENT_STATUS:
        _invalid("FORMAL_SUPPLEMENT_STATUS")
    if SOURCE_RUN_ID not in text or "`P2-U(T) =" not in text or "`P2-B(H) =" not in text:
        _invalid("FORMAL_SUPPLEMENT_REGISTRATION")
    if re.search(r"formal\s+result\s+materialization\s+and\s+statistics", text, flags=re.IGNORECASE) is None:
        _invalid("FORMAL_SUPPLEMENT_AUTHORITY")
    date_match = re.search(r"^Supplement date:\s*`([^`]+)`\s*$", text, flags=re.MULTILINE)
    if date_match is None:
        _invalid("FORMAL_SUPPLEMENT_DATE")
    return {"status": status_match.group(1), "supplement_date": date_match.group(1)}


def _validate_protocol(text: str) -> dict[str, str]:
    if "Amendment ID: `" + AMENDMENT_ID + "`" not in text:
        _invalid("PROTOCOL_AMENDMENT_ID")
    if "P2-U(T) = unsafe(all,T) - unsafe(content,T)" not in text:
        _invalid("PROTOCOL_T_ENDPOINT")
    if "P2-B(H) = broken(all,H) - broken(content,H)" not in text:
        _invalid("PROTOCOL_H_ENDPOINT")
    if "P2_T_all" not in text or "P2_H_content" not in text:
        _invalid("PROTOCOL_CELL_CONTRACT")
    return {"amendment_id": AMENDMENT_ID}


def _input_bundle(
    raw_result_path: Path | str,
    formal_supplement_path: Path | str,
    protocol_path: Path | str,
) -> tuple[Mapping[str, Any], dict[str, Any]]:
    raw, raw_sha256 = _read_json(raw_result_path, "RAW_RESULT")
    validate_raw_result(raw)
    supplement_text, supplement_sha256 = _read_text(formal_supplement_path, "FORMAL_SUPPLEMENT")
    supplement = _validate_supplement(supplement_text)
    protocol_text, protocol_sha256 = _read_text(protocol_path, "PROTOCOL")
    protocol = _validate_protocol(protocol_text)
    source = {
        "raw_result": {
            "path": str(_path(raw_result_path, "RAW_RESULT").resolve()),
            "sha256": raw_sha256,
            "schema_version": raw["schema_version"],
            "status": raw["status"],
        },
        "formal_supplement": {
            "path": str(_path(formal_supplement_path, "FORMAL_SUPPLEMENT").resolve()),
            "sha256": supplement_sha256,
            **supplement,
        },
        "protocol": {
            "path": str(_path(protocol_path, "PROTOCOL").resolve()),
            "sha256": protocol_sha256,
            **protocol,
        },
    }
    return raw, source


def _check_output_directory(output_directory: Path | str) -> Path:
    output = _path(output_directory, "OUTPUT_DIRECTORY")
    if output.exists() or output.is_symlink():
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    return output.resolve()


def _statistics_contract() -> dict[str, Any]:
    return {
        "implementation_version": reference_statistics.IMPLEMENTATION_VERSION,
        "function": "p2_raw_simultaneous",
        "algorithm": "two_way_webb_fixed_scale_max_abs_v1",
        "rng_namespace": reference_statistics.RNG_NAMESPACE,
        "member_order": list(MEMBER_ORDER),
        "replicates_requested": FORMAL_REPLICATES,
        "replicates_required": FORMAL_MIN_SUCCESS,
        "replicates": FORMAL_REPLICATES,
        "min_success": FORMAL_MIN_SUCCESS,
    }


def validate_only(
    raw_result_path: Path | str,
    *,
    formal_supplement_path: Path | str = DEFAULT_FORMAL_SUPPLEMENT,
    protocol_path: Path | str = DEFAULT_PROTOCOL,
    output_directory: Path | str | None = None,
) -> dict[str, Any]:
    """Validate all source and statistical contracts without invoking statistics."""
    raw, source = _input_bundle(raw_result_path, formal_supplement_path, protocol_path)
    if output_directory is not None:
        _check_output_directory(output_directory)
    return {
        "schema_version": FORMAL_RESULT_SCHEMA_VERSION,
        "status": "P2_INDEPENDENT_FORMAL_VALIDATE_ONLY_PASS",
        "validate_only": True,
        "statistics_not_run": True,
        "amendment_id": AMENDMENT_ID,
        "formal_status": FORMAL_SUPPLEMENT_STATUS,
        "source": source,
        "source_run_id": raw["source_run_id"],
        "endpoint_order": raw["endpoint_order"],
        "member_order": list(MEMBER_ORDER),
        "M_T": MATCHED_COUNTS["M_T"],
        "M_H": MATCHED_COUNTS["M_H"],
        "cell_identity_counts": dict(raw["cell_identity_counts"]),
        "terminal_partition": dict(raw["terminal_partition"]),
        "statistics_contract": _statistics_contract(),
        "paper_result_eligible": raw["paper_result_eligible"],
        "output_written": False,
    }


def _raw_execution_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "paper_result_eligible", "formal_experiment_run", "fake_backend",
        "old_p2_run", "old_p2_unchanged", "amended_independent", "estimation_only",
        "generation_calls_added", "judge_calls_added", "statistics_not_run",
    )
    return {field: raw[field] for field in fields if field in raw}


def _endpoint_results(statistics: Mapping[str, Any] | None) -> dict[str, Any]:
    intervals = statistics.get("intervals") if isinstance(statistics, Mapping) else None
    if not isinstance(intervals, Mapping):
        return {}
    results: dict[str, Any] = {}
    for member_id in MEMBER_ORDER:
        interval = intervals.get(member_id)
        if not isinstance(interval, Mapping):
            return {}
        if not all(field in interval for field in ("point", "se", "simultaneous_95")):
            return {}
        results[member_id] = {
            "point_estimate": interval["point"],
            "two_way_cr1_se": interval["se"],
            "simultaneous_95": interval["simultaneous_95"],
        }
    return results


def assemble_formal_result(
    raw: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the registered procedure on validated matched records only."""
    validate_raw_result(raw)
    statistic = reference_statistics.p2_raw_simultaneous if statistics_function is None else statistics_function
    members = [
        {
            "member_id": member["member_id"],
            "records": member["records"],
        }
        for member in raw["members"]
    ]
    try:
        statistics = statistic(
            members,
            replicates=FORMAL_REPLICATES,
            min_success=FORMAL_MIN_SUCCESS,
            member_order=list(MEMBER_ORDER),
        )
    except reference_statistics.NonEstimable as exc:
        status = "P2_STATISTICS_NON_ESTIMABLE"
        reason_detail = str(exc)
        statistics = None
        successful = None
        critical = None
    else:
        status = "ESTIMABLE"
        reason_detail = None
        successful = statistics.get("replicates_successful")
        critical = statistics.get("critical_value_nearest_rank_0_95")
    return {
        "schema_version": FORMAL_RESULT_SCHEMA_VERSION,
        "status": status,
        "reason_detail": reason_detail,
        "formal_status": FORMAL_SUPPLEMENT_STATUS,
        "amendment_id": AMENDMENT_ID,
        "source": dict(source),
        "source_run_id": raw["source_run_id"],
        "raw_result_status": raw["status"],
        "raw_result_schema_version": raw["schema_version"],
        "endpoint_order": raw["endpoint_order"],
        "member_order": list(MEMBER_ORDER),
        "M_T": MATCHED_COUNTS["M_T"],
        "M_H": MATCHED_COUNTS["M_H"],
        "cell_identity_counts": dict(raw["cell_identity_counts"]),
        "terminal_partition": dict(raw["terminal_partition"]),
        "raw_execution_fields": _raw_execution_fields(raw),
        "paper_result_eligible": raw["paper_result_eligible"],
        "formal_status_source": dict(source["formal_supplement"]),
        "statistics_contract": _statistics_contract(),
        "replicates_requested": FORMAL_REPLICATES,
        "replicates_successful": successful,
        "replicates_required": FORMAL_MIN_SUCCESS,
        "critical_value_nearest_rank_0_95": critical,
        "endpoint_results": _endpoint_results(statistics),
        "statistics": statistics,
        "statistics_not_run": False,
    }


def materialize_formal_results(
    raw_result_path: Path | str,
    output_directory: Path | str,
    *,
    formal_supplement_path: Path | str = DEFAULT_FORMAL_SUPPLEMENT,
    protocol_path: Path | str = DEFAULT_PROTOCOL,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate, calculate, and write one formal result without overwriting."""
    output = _check_output_directory(output_directory)
    raw, source = _input_bundle(raw_result_path, formal_supplement_path, protocol_path)
    result = assemble_formal_result(raw, source, statistics_function=statistics_function)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError:
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    target = output / OUTPUT_FILENAME
    target.write_text(
        json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def compute_formal_statistics(
    raw_result_path: Path | str,
    *,
    formal_supplement_path: Path | str = DEFAULT_FORMAL_SUPPLEMENT,
    protocol_path: Path | str = DEFAULT_PROTOCOL,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute the formal result in memory after validating all source files."""
    raw, source = _input_bundle(raw_result_path, formal_supplement_path, protocol_path)
    return assemble_formal_result(raw, source, statistics_function=statistics_function)


# Descriptive aliases keep the production script and callers easy to discover.
process_formal_results = materialize_formal_results
validate_formal_input = validate_only
materialize_p2_independent_formal_results_directory = materialize_formal_results
materialize_p2_independent_formal_results = materialize_formal_results
assemble_p2_independent_formal_result = assemble_formal_result
validate_p2_independent_formal_result = validate_only


__all__ = [
    "AMENDMENT_ID", "DEFAULT_FORMAL_SUPPLEMENT", "DEFAULT_PROTOCOL", "DEFAULT_RAW_RESULT",
    "EXPECTED_ENDPOINT_ORDER", "EXPECTED_TERMINAL_PARTITION", "FORMAL_MIN_SUCCESS",
    "FORMAL_REPLICATES", "FORMAL_RESULT_SCHEMA_VERSION", "FORMAL_SUPPLEMENT_STATUS",
    "MATCHED_COUNTS", "MEMBER_ORDER", "OUTPUT_FILENAME", "P2IndependentFormalResultInvalid",
    "assemble_formal_result", "materialize_formal_results", "process_formal_results",
    "compute_formal_statistics",
    "materialize_p2_independent_formal_results_directory",
    "materialize_p2_independent_formal_results", "assemble_p2_independent_formal_result",
    "validate_formal_input", "validate_only", "validate_p2_independent_formal_result",
    "validate_raw_result",
]
