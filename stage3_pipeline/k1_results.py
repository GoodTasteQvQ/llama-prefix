"""Strict K1 matched-profile materialization from the accepted P2 artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import p2_results
from .core import PipelineError, canonical_sha256, file_sha256
from .execution import OutputStore
from .offline_assets import AssetError, strict_json_loads
from .records import (
    RecordSchemaError,
    build_k1_reuse_record,
    validate_k1_materialization,
)
from .statistics import retained_bootstrap


FORMAL_P2_RAW_RESULT = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "p2-materialized-qwen25-paper-20260808T051044Z-v1/p2_raw_result.json"
)
OUTPUT_FILENAME = "k1_result.json"
SCHEMA_VERSION = "paper1-stage3-k1-result-materialization-v1"
CELL_ORDER = retained_bootstrap.K1_CELLS
PROMPT_FRAME_SIZE = 50
VECTOR_FRAME_SIZE = 20

_P2_RAW_FIELDS = {
    "schema_version",
    "status",
    "reason_detail",
    "source",
    "reconciliation",
    "member_order",
    "cell_counts",
    "members",
    "statistics_contract",
    "statistics",
}
_MATCHED_MEMBERS = {"M_A": "P2-U(A)", "M_T": "P2-B(T)"}


class K1ResultInputInvalid(ValueError):
    """The K1 source or requested destination violates the fixed contract."""

    code = "K1_RESULT_INPUT_INVALID"


def _input_invalid(detail: str) -> None:
    raise K1ResultInputInvalid(f"{K1ResultInputInvalid.code}:{detail}")


@dataclass(frozen=True)
class ValidatedK1Inputs:
    """Fully validated lineage and matched-profile input, before statistics."""

    p2_run_directory: Path
    p2_raw_result_path: Path
    p2_raw_result_sha256: str
    prepared: Any
    loaded: p2_results.LoadedP2Run
    reconciliation: Mapping[str, Any]
    p2_raw_result: Mapping[str, Any]
    profile: Mapping[str, Any]


def _nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        _input_invalid(f"{field}:NOT_NONEMPTY_TEXT")
    return value


def _fixed_p2_raw_result(path: Path) -> Path:
    if not isinstance(path, Path):
        _input_invalid("P2_RAW_RESULT_NOT_PATH")
    if path.is_symlink():
        _input_invalid(f"P2_RAW_RESULT_SYMLINK:{path}")
    resolved = path.resolve()
    if resolved != FORMAL_P2_RAW_RESULT.resolve():
        _input_invalid(f"P2_RAW_RESULT_NOT_FIXED_ACCEPTED_RESULT:{resolved}")
    if not resolved.is_file():
        _input_invalid(f"P2_RAW_RESULT_NOT_FILE:{resolved}")
    return resolved


def _load_strict_object(path: Path) -> dict[str, Any]:
    try:
        value = strict_json_loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeError, AssetError, ValueError) as exc:
        _input_invalid(f"P2_RAW_RESULT_JSON:{exc}")
    if not isinstance(value, dict):
        _input_invalid("P2_RAW_RESULT_NOT_OBJECT")
    return value


def _expected_p2_source(
    prepared: Any,
    loaded: p2_results.LoadedP2Run,
    reconciliation: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "run_directory": str(loaded.run_directory),
        "run_id": loaded.run_directory.name,
        "canonical_plan_count": reconciliation["canonical_plan_count"],
        "canonical_registry_sha256": reconciliation["canonical_registry_sha256"],
        "p2_identity_count": reconciliation["p2_identity_count"],
        "p2_identity_set_sha256": canonical_sha256(list(prepared.p2_rows)),
        "p2_ledger_sha256": canonical_sha256(dict(reconciliation)),
        "execution_identity_sha256": canonical_sha256(dict(loaded.execution_identity)),
        "source_file_sha256": dict(loaded.file_sha256),
    }


def _validate_p2_raw_result(
    document: Mapping[str, Any],
    *,
    prepared: Any,
    loaded: p2_results.LoadedP2Run,
    reconciliation: Mapping[str, Any],
) -> dict[str, Any]:
    if set(document) != _P2_RAW_FIELDS:
        _input_invalid("P2_RAW_RESULT_FIELDS")
    if (
        document.get("schema_version") != p2_results.SCHEMA_VERSION
        or document.get("status") != "ESTIMABLE"
        or document.get("reason_detail") is not None
    ):
        _input_invalid("P2_RAW_RESULT_STATUS_OR_SCHEMA")
    if document.get("source") != _expected_p2_source(prepared, loaded, reconciliation):
        _input_invalid("P2_RAW_RESULT_SOURCE_MISMATCH")
    if document.get("reconciliation") != dict(reconciliation):
        _input_invalid("P2_RAW_RESULT_RECONCILIATION_MISMATCH")

    rebuilt = p2_results.build_p2_raw_members(
        prepared.p2_rows, loaded.responses, expected_cell_count=p2_results.P2_CELL_COUNT
    )
    p2_results._add_retry_counts(  # Reuse the accepted P2 count implementation.
        rebuilt, prepared.p2_rows, loaded.generations, loaded.judges
    )
    for field in ("member_order", "cell_counts", "members"):
        if document.get(field) != rebuilt[field]:
            _input_invalid(f"P2_RAW_RESULT_REBUILT_{field.upper()}_MISMATCH")
    expected_contract = {
        "implementation_version": p2_results.reference_statistics.IMPLEMENTATION_VERSION,
        "function": "p2_raw_simultaneous",
        "rng_namespace": p2_results.reference_statistics.RNG_NAMESPACE,
        "member_order": rebuilt["member_order"],
        "replicates": p2_results.FORMAL_REPLICATES,
        "min_success": p2_results.FORMAL_MIN_SUCCESS,
    }
    if document.get("statistics_contract") != expected_contract:
        _input_invalid("P2_RAW_RESULT_STATISTICS_CONTRACT_MISMATCH")
    if not isinstance(document.get("statistics"), Mapping):
        _input_invalid("P2_RAW_RESULT_STATISTICS_NOT_OBJECT")
    return dict(document)


def _canonical_frames(prepared: Any) -> tuple[list[str], list[str]]:
    try:
        prompt_ids = list(prepared.support.plan_inputs["confirm_prompt_ids"])
        vector_indices = list(prepared.config["vector_confirm_indices"])
        vector_ids = [prepared.support.vector_ids_by_index[index] for index in vector_indices]
    except (AttributeError, KeyError, TypeError) as exc:
        _input_invalid(f"P2_CANONICAL_FRAME_SOURCE:{exc}")
    if (
        len(prompt_ids) != PROMPT_FRAME_SIZE
        or len(set(prompt_ids)) != PROMPT_FRAME_SIZE
        or any(not isinstance(value, str) or not value for value in prompt_ids)
    ):
        _input_invalid("PROMPT_FRAME_NOT_FIXED_50")
    if (
        len(vector_ids) != VECTOR_FRAME_SIZE
        or len(set(vector_ids)) != VECTOR_FRAME_SIZE
        or any(not isinstance(value, str) or not value for value in vector_ids)
    ):
        _input_invalid("VECTOR_FRAME_NOT_FIXED_20")
    return prompt_ids, vector_ids


def derive_matched_coordinates(
    members: Sequence[Mapping[str, Any]],
    *,
    prompt_ids: Sequence[str],
    vector_ids: Sequence[str],
) -> dict[str, Any]:
    """Derive M_A, M_T, and their intersection by logical coordinate."""
    if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
        _input_invalid("P2_RAW_MEMBERS_NOT_SEQUENCE")
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, member in enumerate(members):
        if not isinstance(member, Mapping):
            _input_invalid(f"P2_RAW_MEMBER_NOT_OBJECT:{index}")
        member_id = _nonempty_text(member.get("member_id"), f"members[{index}].member_id")
        if member_id in by_id:
            _input_invalid(f"DUPLICATE_P2_RAW_MEMBER:{member_id}")
        by_id[member_id] = member
    if set(by_id) != set(_MATCHED_MEMBERS.values()):
        _input_invalid("P2_RAW_MATCHED_MEMBER_SET")

    prompt_position = {value: index for index, value in enumerate(prompt_ids)}
    vector_position = {value: index for index, value in enumerate(vector_ids)}
    if len(prompt_position) != len(prompt_ids) or len(vector_position) != len(vector_ids):
        _input_invalid("CANONICAL_FRAME_IDENTITY_COLLISION")
    coordinate_sets: dict[str, set[tuple[str, str]]] = {}
    for matched_set, member_id in _MATCHED_MEMBERS.items():
        member = by_id[member_id]
        records = member.get("records")
        if member.get("matched_set") != matched_set or not isinstance(records, list):
            _input_invalid(f"P2_RAW_MEMBER_METADATA:{member_id}")
        coordinates: set[tuple[str, str]] = set()
        for row_index, record in enumerate(records):
            if not isinstance(record, Mapping):
                _input_invalid(f"P2_RAW_MEMBER_RECORD:{member_id}:{row_index}")
            coordinate = (
                _nonempty_text(record.get("prompt_id"), f"{member_id}.prompt_id"),
                _nonempty_text(record.get("vector_id"), f"{member_id}.vector_id"),
            )
            if coordinate in coordinates:
                _input_invalid(f"P2_RAW_MEMBER_DUPLICATE_COORDINATE:{member_id}:{coordinate}")
            if coordinate[0] not in prompt_position or coordinate[1] not in vector_position:
                _input_invalid(f"P2_RAW_MEMBER_COORDINATE_OUTSIDE_FRAME:{member_id}")
            coordinates.add(coordinate)
        if member.get("matched_pair_count") != len(coordinates):
            _input_invalid(f"P2_RAW_MEMBER_COUNT:{member_id}")
        coordinate_sets[matched_set] = coordinates

    intersection = coordinate_sets["M_A"] & coordinate_sets["M_T"]
    ordered = sorted(
        intersection,
        key=lambda item: (prompt_position[item[0]], vector_position[item[1]]),
    )
    if not ordered:
        _input_invalid("EMPTY_M_A_INTERSECTION_M_T")
    return {
        "M_A_count": len(coordinate_sets["M_A"]),
        "M_T_count": len(coordinate_sets["M_T"]),
        "intersection_count": len(ordered),
        "intersection_coordinates": ordered,
    }


def _index_by_logical_id(
    records: Sequence[Mapping[str, Any]], *, label: str
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            _input_invalid(f"{label}_NOT_OBJECT:{index}")
        logical_id = _nonempty_text(record.get("logical_id"), f"{label}[{index}].logical_id")
        if logical_id in result:
            _input_invalid(f"{label}_DUPLICATE_LOGICAL_ID:{logical_id}")
        result[logical_id] = record
    return result


def build_k1_matched_profile(
    *,
    canonical_rows: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    generation_records: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    registry: Any,
    dose_binding: Mapping[str, Any],
    prompt_ids: Sequence[str],
    vector_ids: Sequence[str],
    matched_coordinates: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    """Build four exact-lineage reuse cells on one canonical matched subset."""
    prompt_position = {value: index for index, value in enumerate(prompt_ids)}
    vector_position = {value: index for index, value in enumerate(vector_ids)}
    if len(prompt_position) != len(prompt_ids) or len(vector_position) != len(vector_ids):
        _input_invalid("CANONICAL_FRAME_IDENTITY_COLLISION")
    coordinates = list(matched_coordinates)
    if not coordinates or len(coordinates) != len(set(coordinates)):
        _input_invalid("MATCHED_COORDINATES_EMPTY_OR_DUPLICATE")
    for coordinate in coordinates:
        if (
            not isinstance(coordinate, tuple)
            or len(coordinate) != 2
            or coordinate[0] not in prompt_position
            or coordinate[1] not in vector_position
        ):
            _input_invalid(f"MATCHED_COORDINATE_OUTSIDE_FRAME:{coordinate}")
    canonical_coordinates = sorted(
        coordinates,
        key=lambda item: (prompt_position[item[0]], vector_position[item[1]]),
    )
    if coordinates != canonical_coordinates:
        _input_invalid("MATCHED_COORDINATES_NOT_CANONICAL")

    identity_by_coordinate: dict[tuple[str, str, str], str] = {}
    for index, row in enumerate(canonical_rows):
        if not isinstance(row, Mapping) or not isinstance(row.get("identity"), Mapping):
            _input_invalid(f"CANONICAL_ROW_INVALID:{index}")
        identity = row["identity"]
        cell = identity.get("block")
        if cell not in CELL_ORDER:
            continue
        key = (cell, identity.get("prompt_id"), identity.get("vector_id"))
        if key in identity_by_coordinate:
            _input_invalid(f"DUPLICATE_CANONICAL_K1_COORDINATE:{key}")
        identity_by_coordinate[key] = _nonempty_text(
            row.get("logical_id"), f"canonical_rows[{index}].logical_id"
        )

    responses = _index_by_logical_id(response_records, label="response_records")
    generations = _index_by_logical_id(generation_records, label="generation_records")
    judges = _index_by_logical_id(judge_records, label="judge_records")
    reuse_records: list[dict[str, Any]] = []
    statistic_cells: list[dict[str, Any]] = []
    for cell in CELL_ORDER:
        statistic_records: list[dict[str, Any]] = []
        for prompt_id, vector_id in coordinates:
            logical_id = identity_by_coordinate.get((cell, prompt_id, vector_id))
            if logical_id is None:
                _input_invalid(f"MISSING_SOURCE_COORDINATE:{cell}:{prompt_id}:{vector_id}")
            try:
                source = responses[logical_id]
                generation = generations[logical_id]
                judge = judges.get(logical_id)
            except KeyError as exc:
                _input_invalid(f"MISSING_SOURCE_LINEAGE:{logical_id}:{exc}")
            if (
                source.get("terminal_status") != "COMPLETED_PARSED"
                or source.get("retained") is not True
                or source.get("label") not in retained_bootstrap.HARMFUL_LABELS
            ):
                _input_invalid(f"K1_SOURCE_NOT_RETAINED:{logical_id}")
            reuse = build_k1_reuse_record(source)
            validated = validate_k1_materialization(
                reuse,
                registry=registry,
                source_p2_record=source,
                generation_record=generation,
                judge_record=judge,
                dose_binding=dose_binding,
            )
            reuse_records.append(validated)
            statistic_records.append(
                {
                    "row_id": validated["logical_id"],
                    "prompt_id": validated["prompt_id"],
                    "vector_id": validated["vector_id"],
                    "label": validated["label"],
                }
            )
        statistic_cells.append({"cell_id": cell, "records": statistic_records})

    expected_count = len(coordinates) * len(CELL_ORDER)
    if len(reuse_records) != expected_count:
        _input_invalid("K1_REUSE_RECORD_ACCOUNTING")
    if any(record["generation_calls_added"] != 0 for record in reuse_records):
        _input_invalid("K1_GENERATION_CALL_ACCOUNTING")
    if any(record["judge_calls_added"] != 0 for record in reuse_records):
        _input_invalid("K1_JUDGE_CALL_ACCOUNTING")
    return {
        "cell_order": list(CELL_ORDER),
        "prompt_frame": [
            {"position": index, "prompt_id": value}
            for index, value in enumerate(prompt_ids)
        ],
        "vector_frame": [
            {"position": index, "vector_id": value}
            for index, value in enumerate(vector_ids)
        ],
        "matched_coordinates": [
            {"prompt_id": prompt_id, "vector_id": vector_id}
            for prompt_id, vector_id in coordinates
        ],
        "k1_reuse_records": reuse_records,
        "statistics_input": {
            "schema_version": retained_bootstrap.SCHEMA_VERSION,
            "synthetic_data": False,
            "block_type": "k1",
            "prompt_frame": [
                {"position": index, "prompt_id": value}
                for index, value in enumerate(prompt_ids)
            ],
            "vector_frame": [
                {"position": index, "vector_id": value}
                for index, value in enumerate(vector_ids)
            ],
            "cells": statistic_cells,
        },
    }


def _destination_inside(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def check_output_destination(
    p2_run_directory: Path, p2_raw_result_path: Path, output_directory: Path
) -> Path:
    """Reject overwrite and output nesting under either input directory."""
    if not isinstance(output_directory, Path):
        _input_invalid("OUTPUT_DIRECTORY_NOT_PATH")
    output = output_directory.resolve()
    if output_directory.exists() or output_directory.is_symlink():
        _input_invalid(f"OUTPUT_DIRECTORY_EXISTS:{output_directory}")
    target = output / OUTPUT_FILENAME
    if target.exists() or target.is_symlink():
        _input_invalid(f"OUTPUT_FILE_EXISTS:{target}")
    input_directories = (
        p2_run_directory.resolve(),
        p2_raw_result_path.resolve().parent,
    )
    if any(_destination_inside(output, source) for source in input_directories):
        _input_invalid("OUTPUT_DIRECTORY_INSIDE_INPUT_DIRECTORY")
    return output


def validate_k1_results_inputs(
    p2_run_directory: Path,
    p2_raw_result_path: Path,
    output_directory: Path,
) -> ValidatedK1Inputs:
    """Validate all formal inputs and K1 lineage without running statistics or writing."""
    check_output_destination(p2_run_directory, p2_raw_result_path, output_directory)
    raw_path = _fixed_p2_raw_result(p2_raw_result_path)
    try:
        prepared, loaded, reconciliation = p2_results.load_and_reconcile_p2_run(
            p2_run_directory
        )
        raw = _validate_p2_raw_result(
            _load_strict_object(raw_path),
            prepared=prepared,
            loaded=loaded,
            reconciliation=reconciliation,
        )
        prompt_ids, vector_ids = _canonical_frames(prepared)
        matched = derive_matched_coordinates(
            raw["members"], prompt_ids=prompt_ids, vector_ids=vector_ids
        )
        profile = build_k1_matched_profile(
            canonical_rows=prepared.p2_rows,
            response_records=loaded.responses,
            generation_records=loaded.generations,
            judge_records=loaded.judges,
            registry=prepared.support.registry,
            dose_binding=prepared.support.dose_binding,
            prompt_ids=prompt_ids,
            vector_ids=vector_ids,
            matched_coordinates=matched["intersection_coordinates"],
        )
        profile = {**profile, "matched_counts": matched}
    except K1ResultInputInvalid:
        raise
    except (p2_results.P2ResultInputInvalid, RecordSchemaError, PipelineError) as exc:
        _input_invalid(f"P2_OR_K1_LINEAGE:{exc}")
    return ValidatedK1Inputs(
        p2_run_directory=loaded.run_directory,
        p2_raw_result_path=raw_path,
        p2_raw_result_sha256=file_sha256(raw_path),
        prepared=prepared,
        loaded=loaded,
        reconciliation=reconciliation,
        p2_raw_result=raw,
        profile=profile,
    )


def validation_summary(validated: ValidatedK1Inputs) -> dict[str, Any]:
    counts = validated.profile["matched_counts"]
    return {
        "status": "VALIDATED_ONLY",
        "M_A": counts["M_A_count"],
        "M_T": counts["M_T_count"],
        "M_A_intersection_M_T": counts["intersection_count"],
        "k1_reuse_record_count": len(validated.profile["k1_reuse_records"]),
        "generation_calls_added": 0,
        "judge_calls_added": 0,
        "statistics_executed": False,
        "output_written": False,
    }


def assemble_k1_result(
    validated: ValidatedK1Inputs,
    *,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the registered K1 statistic and assemble the traceable result."""
    statistic = retained_bootstrap.analyze_k1 if statistics_function is None else statistics_function
    statistics_result = statistic(validated.profile["statistics_input"], fixture_mode=False)
    counts = validated.profile["matched_counts"]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ESTIMABLE",
        "source": {
            "p2_run_directory": str(validated.p2_run_directory),
            "p2_run_id": validated.p2_run_directory.name,
            "p2_execution_identity_sha256": canonical_sha256(
                dict(validated.loaded.execution_identity)
            ),
            "p2_raw_result_path": str(validated.p2_raw_result_path),
            "p2_raw_result_sha256": validated.p2_raw_result_sha256,
            "p2_raw_result_schema_version": validated.p2_raw_result["schema_version"],
        },
        "source_cell_counts": dict(validated.p2_raw_result["cell_counts"]),
        "matched_profile_counts": {
            "M_A": counts["M_A_count"],
            "M_T": counts["M_T_count"],
            "M_A_intersection_M_T": counts["intersection_count"],
        },
        "cell_order": list(CELL_ORDER),
        "prompt_frame": validated.profile["prompt_frame"],
        "vector_frame": validated.profile["vector_frame"],
        "matched_coordinates": validated.profile["matched_coordinates"],
        "k1_reuse_record_count": len(validated.profile["k1_reuse_records"]),
        "k1_reuse_records": validated.profile["k1_reuse_records"],
        "generation_calls_added": 0,
        "judge_calls_added": 0,
        "statistics_contract": {
            "implementation_version": retained_bootstrap.IMPLEMENTATION_VERSION,
            "function": "analyze_k1",
            "rng_namespace": retained_bootstrap.RNG_NAMESPACE,
            "replicates": retained_bootstrap.PRODUCTION_REPLICATES,
            "min_success": retained_bootstrap.PRODUCTION_MIN_SUCCESS,
            "shared_draws": "one prompt draw and one vector draw reused by all four cells",
            "row_weight": "prompt_multiplicity*vector_multiplicity",
            "interval": "nearest_rank_95_percentile_no_interpolation",
        },
        "statistics_input": validated.profile["statistics_input"],
        "statistics": statistics_result,
        "scope": {
            "profile": "M_A_intersection_M_T_matched_coordinates_only",
            "coordinate_requirement": "all_four_cells_have_retained_labels",
            "unmatched_per_cell_reporting": "source_denominators_and_counts_only",
            "inferential_claim": (
                "descriptive_only_no_global_decision_p_value_or_confirmation_claim"
            ),
        },
    }


def materialize_k1_results_directory(
    p2_run_directory: Path,
    p2_raw_result_path: Path,
    output_directory: Path,
    *,
    statistics_function: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate, analyze, and write one new non-overwriting K1 result directory."""
    output = check_output_destination(
        p2_run_directory, p2_raw_result_path, output_directory
    )
    validated = validate_k1_results_inputs(
        p2_run_directory, p2_raw_result_path, output_directory
    )
    result = assemble_k1_result(validated, statistics_function=statistics_function)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError:
        _input_invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    OutputStore(output).write_json_once(OUTPUT_FILENAME, result)
    return result


__all__ = [
    "CELL_ORDER",
    "FORMAL_P2_RAW_RESULT",
    "K1ResultInputInvalid",
    "OUTPUT_FILENAME",
    "ValidatedK1Inputs",
    "assemble_k1_result",
    "build_k1_matched_profile",
    "check_output_destination",
    "derive_matched_coordinates",
    "materialize_k1_results_directory",
    "validate_k1_results_inputs",
    "validation_summary",
]
