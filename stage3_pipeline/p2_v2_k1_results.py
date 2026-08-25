"""Descriptive K1 materialization for the formal amended T/H P2 run.

The source run is immutable.  This module only validates its already parsed
responses and assembles a four-cell descriptive profile on the logical
intersection of ``M_T`` and ``M_H``.  No generation, judge, or model code is
reachable from this module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import canonical_json, canonical_sha256, file_sha256
from .execution import OutputStore
from .p2_independent_formal_results import (
    EXPECTED_ENDPOINT_ORDER,
    EXPECTED_TERMINAL_PARTITION,
    FORMAL_SUPPLEMENT_STATUS,
    FORMAL_RESULT_SCHEMA_VERSION,
    MATCHED_COUNTS,
    validate_raw_result,
)
from .p2_independent_results import (
    FORMAL_AMENDED_RUN_DIRECTORY,
    P2IndependentResultInputInvalid,
    build_independent_raw_members,
    validate_independent_run,
)
from .p2_independent_runner import CELLS, DEFAULT_CONFIG, PreparedIndependentP2, prepare_independent_p2
from .statistics import retained_bootstrap


P2_V2_K1_CELLS = ("P2_T_all", "P2_T_content", "P2_H_all", "P2_H_content")
CELL_ORDER = P2_V2_K1_CELLS
OUTPUT_FILENAME = "p2_v2_k1_result.json"
SCHEMA_VERSION = "paper1-stage3-p2-v2-k1-result-v1"
RAW_RESULT_PATH = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "p2-amended-th-materialized-qwen25-paper-20260822T051005Z-v1/"
    "p2_independent_raw_result.json"
)
FORMAL_RESULT_PATH = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "p2-v2-formal-qwen25-paper-20260822T051005Z-v1/"
    "p2_independent_formal_result.json"
)
FORMAL_SUPPLEMENT = Path(
    "writing/stage3 design/paper1_stage3_protocol_status_supplement_p2_v2_formal.md"
).resolve()
EXPECTED_SOURCE_RUN_ID = FORMAL_AMENDED_RUN_DIRECTORY.name


class P2V2K1ResultInputInvalid(ValueError):
    code = "P2_V2_K1_RESULT_INPUT_INVALID"


def _invalid(detail: str) -> None:
    raise P2V2K1ResultInputInvalid(f"{P2V2K1ResultInputInvalid.code}:{detail}")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        _invalid(f"{label}_NOT_REGULAR_FILE:{path}")
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        _invalid(f"{label}_JSON:{exc}")
    if not isinstance(value, dict):
        _invalid(f"{label}_NOT_OBJECT")
    return value


def _fixed_file(value: Path, expected: Path, label: str) -> Path:
    if not isinstance(value, Path):
        _invalid(f"{label}_NOT_PATH")
    resolved = value.resolve()
    if resolved != expected.resolve():
        _invalid(f"{label}_NOT_FIXED_INPUT:{resolved}")
    if value.is_symlink() or not resolved.is_file():
        _invalid(f"{label}_NOT_REGULAR_FILE:{resolved}")
    return resolved


def _check_output_directory(output: Path, inputs: Sequence[Path]) -> Path:
    if not isinstance(output, Path):
        _invalid("OUTPUT_DIRECTORY_NOT_PATH")
    if output.exists() or output.is_symlink():
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    resolved = output.resolve()
    for source in inputs:
        source = source.resolve()
        try:
            resolved.relative_to(source if source.is_dir() else source.parent)
        except ValueError:
            continue
        _invalid("OUTPUT_DIRECTORY_INSIDE_INPUT")
    return resolved


def _source_summary(raw_path: Path, formal_path: Path, raw: Mapping[str, Any], formal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "raw_result": {"path": str(raw_path), "sha256": file_sha256(raw_path), "schema_version": raw["schema_version"]},
        "formal_result": {"path": str(formal_path), "sha256": file_sha256(formal_path), "schema_version": formal["schema_version"]},
    }


def _validate_formal_result(formal: Mapping[str, Any], *, raw_path: Path, raw: Mapping[str, Any]) -> None:
    required = {
        "schema_version", "status", "reason_detail", "formal_status", "amendment_id", "source_run_id",
        "raw_result_status", "raw_result_schema_version", "endpoint_order", "member_order", "M_T", "M_H",
        "cell_identity_counts", "terminal_partition", "raw_execution_fields", "paper_result_eligible",
        "formal_status_source", "statistics_contract", "replicates_requested", "replicates_successful",
        "replicates_required", "critical_value_nearest_rank_0_95", "endpoint_results", "statistics", "statistics_not_run",
        "source",
    }
    if set(formal) != required:
        _invalid("FORMAL_RESULT_FIELDS")
    if formal["schema_version"] != FORMAL_RESULT_SCHEMA_VERSION or formal["status"] != "ESTIMABLE" or formal["reason_detail"] is not None or formal["formal_status"] != FORMAL_SUPPLEMENT_STATUS:
        _invalid("FORMAL_RESULT_STATUS")
    if formal["source_run_id"] != EXPECTED_SOURCE_RUN_ID or formal["amendment_id"] != raw["amendment_id"]:
        _invalid("FORMAL_RESULT_LINEAGE")
    if formal["raw_result_status"] != raw["status"] or formal["raw_result_schema_version"] != raw["schema_version"]:
        _invalid("FORMAL_RESULT_RAW_LINEAGE")
    if formal["endpoint_order"] != [dict(item) for item in EXPECTED_ENDPOINT_ORDER] or formal["member_order"] != ["P2-U(T)", "P2-B(H)"]:
        _invalid("FORMAL_RESULT_ENDPOINT_ORDER")
    if formal["M_T"] != 976 or formal["M_H"] != 966 or formal["cell_identity_counts"] != raw["cell_identity_counts"]:
        _invalid("FORMAL_RESULT_COUNTS")
    if formal["terminal_partition"] != EXPECTED_TERMINAL_PARTITION or formal["paper_result_eligible"] is not False:
        _invalid("FORMAL_RESULT_EXECUTION_FIELDS")
    expected_execution = {
        "paper_result_eligible": False,
        "formal_experiment_run": True,
        "fake_backend": False,
        "old_p2_run": False,
        "old_p2_unchanged": True,
        "amended_independent": True,
        "estimation_only": True,
        "generation_calls_added": 0,
        "judge_calls_added": 0,
        "statistics_not_run": True,
    }
    if formal["raw_execution_fields"] != expected_execution:
        _invalid("FORMAL_RESULT_RAW_EXECUTION_FIELDS")
    if formal["replicates_requested"] != 9_999 or formal["replicates_successful"] != 9_999 or formal["replicates_required"] != 9_500:
        _invalid("FORMAL_RESULT_REPLICATES")
    if not isinstance(formal["formal_status_source"], Mapping) or formal["formal_status_source"].get("status") != FORMAL_SUPPLEMENT_STATUS:
        _invalid("FORMAL_RESULT_STATUS_SOURCE")
    statistics = formal["statistics"]
    if not isinstance(statistics, Mapping) or statistics.get("replicates_requested") != 9_999 or statistics.get("replicates_successful") != 9_999 or statistics.get("replicates_required") != 9_500:
        _invalid("FORMAL_RESULT_STATISTICS")
    source = formal["source"]
    raw_source = source.get("raw_result") if isinstance(source, Mapping) else None
    if not isinstance(raw_source, Mapping) or raw_source.get("path") != str(raw_path) or raw_source.get("sha256") != file_sha256(raw_path):
        _invalid("FORMAL_RESULT_RAW_SOURCE")


def _frames(prepared: PreparedIndependentP2) -> tuple[list[str], list[str]]:
    try:
        prompts = list(prepared.base.support.plan_inputs["confirm_prompt_ids"])
        indices = list(prepared.config["vector_confirm_indices"])
        vectors = [prepared.base.support.vector_ids_by_index[index] for index in indices]
    except (AttributeError, KeyError, TypeError, IndexError) as exc:
        _invalid(f"FRAME_SOURCE:{exc}")
    if len(prompts) != 50 or len(set(prompts)) != 50 or len(vectors) != 20 or len(set(vectors)) != 20:
        _invalid("FRAME_SHAPE")
    return prompts, vectors


def _members_by_set(raw: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    members = raw.get("members")
    if not isinstance(members, list) or len(members) != 2:
        _invalid("RAW_MEMBERS")
    result: dict[str, Mapping[str, Any]] = {}
    for member in members:
        if not isinstance(member, Mapping) or member.get("matched_set") not in {"M_T", "M_H"}:
            _invalid("RAW_MEMBER_IDENTITY")
        key = str(member["matched_set"])
        if key in result:
            _invalid("RAW_MEMBER_DUPLICATE")
        result[key] = member
    if set(result) != {"M_T", "M_H"}:
        _invalid("RAW_MEMBER_SET")
    return result


def derive_common_coordinates(raw: Mapping[str, Any], *, prompt_ids: Sequence[str], vector_ids: Sequence[str]) -> dict[str, Any]:
    members = _members_by_set(raw)
    positions = ({value: index for index, value in enumerate(prompt_ids)}, {value: index for index, value in enumerate(vector_ids)})
    sets: dict[str, set[tuple[str, str]]] = {}
    for key, member in members.items():
        records = member.get("records")
        if not isinstance(records, list) or member.get("matched_pair_count") != len(records):
            _invalid(f"{key}_RECORDS")
        coords: set[tuple[str, str]] = set()
        for record in records:
            if not isinstance(record, Mapping):
                _invalid(f"{key}_RECORD_NOT_OBJECT")
            coordinate = (record.get("prompt_id"), record.get("vector_id"))
            if any(not isinstance(value, str) or not value for value in coordinate) or coordinate in coords:
                _invalid(f"{key}_COORDINATE")
            if coordinate[0] not in positions[0] or coordinate[1] not in positions[1]:
                _invalid(f"{key}_COORDINATE_OUTSIDE_FRAME")
            coords.add(coordinate)
        sets[key] = coords
    if len(sets["M_T"]) != MATCHED_COUNTS["M_T"] or len(sets["M_H"]) != MATCHED_COUNTS["M_H"]:
        _invalid("MATCHED_COUNTS")
    intersection = sets["M_T"] & sets["M_H"]
    if len(intersection) != 946:
        _invalid("COMMON_INTERSECTION_COUNT")
    ordered = sorted(intersection, key=lambda item: (positions[0][item[0]], positions[1][item[1]]))
    return {"M_T_count": len(sets["M_T"]), "M_H_count": len(sets["M_H"]), "intersection_count": len(ordered), "intersection_coordinates": ordered}


def _response_indexes(validated: Any) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]], dict[tuple[str, str, str], str]]:
    responses = {row["logical_id"]: row for row in validated.loaded.responses}
    generations = {row["logical_id"]: row for row in validated.loaded.generations}
    judges = {row["logical_id"]: row for row in validated.loaded.judges}
    identities: dict[tuple[str, str, str], str] = {}
    for row in validated.prepared.rows:
        identity = row["identity"]
        key = (identity.get("block"), identity.get("prompt_id"), identity.get("vector_id"))
        if key in identities:
            _invalid("DUPLICATE_SOURCE_COORDINATE")
        identities[key] = row["logical_id"]
    return responses, generations, judges, identities


def build_k1_profile(validated: Any, coordinates: Sequence[tuple[str, str]], *, prompt_ids: Sequence[str], vector_ids: Sequence[str]) -> dict[str, Any]:
    responses, generations, judges, identities = _response_indexes(validated)
    cells: list[dict[str, Any]] = []
    reuse: list[dict[str, Any]] = []
    for cell in CELL_ORDER:
        records: list[dict[str, Any]] = []
        for prompt_id, vector_id in coordinates:
            logical_id = identities.get((cell, prompt_id, vector_id))
            if logical_id is None or logical_id not in responses or logical_id not in generations or logical_id not in judges:
                _invalid(f"MISSING_SOURCE_LINEAGE:{cell}:{prompt_id}:{vector_id}")
            source, generation, judge = responses[logical_id], generations[logical_id], judges[logical_id]
            if source.get("terminal_status") != "COMPLETED_PARSED" or source.get("retained") is not True or source.get("label") not in retained_bootstrap.HARMFUL_LABELS:
                _invalid(f"TERMINAL_OR_UNPARSED_SOURCE:{logical_id}")
            if source.get("generation_record_sha256") != generation.get("record_sha256") or source.get("judge_record_sha256") != judge.get("record_sha256"):
                _invalid(f"LINEAGE_MISMATCH:{logical_id}")
            identity = validated.prepared.registry.require(logical_id)
            record = {
                "schema_version": "paper1-stage3-p2-v2-k1-reuse-record-v1",
                "logical_id": logical_id,
                "source_p2_logical_id": logical_id,
                "source_p2_record_sha256": source["record_sha256"],
                "source_response_record_sha256": source["record_sha256"],
                "identity_sha256": source["identity_sha256"],
                "cell": cell,
                "prompt_id": prompt_id,
                "vector_id": vector_id,
                "pair_id": f"{identity['anchor']}|{prompt_id}|{vector_id}",
                "arm": source["arm"],
                "anchor": source["anchor"],
                "estimator": source["estimator"],
                "label": source["label"],
                "retained": True,
                "generation_record_sha256": generation["record_sha256"],
                "judge_record_sha256": judge["record_sha256"],
                "generation_lineage": {
                    "logical_id": generation.get("logical_id"),
                    "identity_sha256": generation.get("identity_sha256"),
                    "record_sha256": generation.get("record_sha256"),
                    "terminal_status": generation.get("terminal_status"),
                },
                "judge_lineage": {
                    "logical_id": judge.get("logical_id"),
                    "identity_sha256": judge.get("identity_sha256"),
                    "generation_record_sha256": judge.get("generation_record_sha256"),
                    "record_sha256": judge.get("record_sha256"),
                    "terminal_status": judge.get("terminal_status"),
                },
                "generation_calls_added": 0,
                "judge_calls_added": 0,
            }
            record["record_sha256"] = canonical_sha256(record)
            reuse.append(record)
            records.append({"row_id": logical_id, "prompt_id": prompt_id, "vector_id": vector_id, "label": source["label"]})
        cells.append({"cell_id": cell, "records": records})
    payload = {
        "schema_version": retained_bootstrap.SCHEMA_VERSION,
        "synthetic_data": False,
        "block_type": "k1",
        "prompt_frame": [{"position": index, "prompt_id": value} for index, value in enumerate(prompt_ids)],
        "vector_frame": [{"position": index, "vector_id": value} for index, value in enumerate(vector_ids)],
        "cells": cells,
    }
    return {"cell_order": list(CELL_ORDER), "prompt_frame": payload["prompt_frame"], "vector_frame": payload["vector_frame"], "matched_coordinates": [{"prompt_id": p, "vector_id": v} for p, v in coordinates], "k1_reuse_records": reuse, "statistics_input": payload}


@dataclass(frozen=True)
class ValidatedP2V2K1Inputs:
    p2_run_directory: Path
    p2_raw_result_path: Path
    p2_formal_result_path: Path
    p2_raw_result_sha256: str
    p2_formal_result_sha256: str
    prepared: PreparedIndependentP2
    validated_run: Any
    raw_result: Mapping[str, Any]
    formal_result: Mapping[str, Any]
    profile: Mapping[str, Any]


def validate_p2_v2_k1_inputs(p2_run_directory: Path, p2_raw_result: Path, p2_formal_result: Path, output_directory: Path, *, config_path: Path = DEFAULT_CONFIG) -> ValidatedP2V2K1Inputs:
    output = _check_output_directory(output_directory, [p2_run_directory, p2_raw_result, p2_formal_result])
    if p2_run_directory.resolve() != FORMAL_AMENDED_RUN_DIRECTORY.resolve():
        _invalid("P2_RUN_DIRECTORY_NOT_FIXED")
    raw_path = _fixed_file(p2_raw_result, RAW_RESULT_PATH, "P2_RAW_RESULT")
    formal_path = _fixed_file(p2_formal_result, FORMAL_RESULT_PATH, "P2_FORMAL_RESULT")
    try:
        validated_run = validate_independent_run(p2_run_directory, config_path=config_path)
        prepared = validated_run.prepared
    except (P2IndependentResultInputInvalid, ValueError, KeyError, TypeError) as exc:
        _invalid(f"P2_RUN_VALIDATION:{exc}")
    raw = _read_json(raw_path, "P2_RAW_RESULT")
    try:
        validate_raw_result(raw)
    except ValueError as exc:
        _invalid(f"P2_RAW_RESULT_VALIDATION:{exc}")
    rebuilt = build_independent_raw_members(prepared.rows, validated_run.loaded.responses, generation_records=validated_run.loaded.generations, judge_records=validated_run.loaded.judges, dispositions=validated_run.loaded.dispositions)
    for field in ("endpoint_order", "member_order", "cell_counts", "members"):
        if raw.get(field) != rebuilt.get(field):
            _invalid(f"P2_RAW_RESULT_REBUILT_{field.upper()}")
    if raw.get("M_T") != rebuilt["matched_counts"]["M_T"] or raw.get("M_H") != rebuilt["matched_counts"]["M_H"]:
        _invalid("P2_RAW_RESULT_REBUILT_MATCHED_COUNTS")
    if raw.get("source_run_id") != EXPECTED_SOURCE_RUN_ID or raw.get("paper_result_eligible") is not False or raw.get("generation_calls_added") != 0 or raw.get("judge_calls_added") != 0:
        _invalid("P2_RAW_RESULT_LINEAGE_FLAGS")
    formal = _read_json(formal_path, "P2_FORMAL_RESULT")
    _validate_formal_result(formal, raw_path=raw_path, raw=raw)
    prompts, vectors = _frames(prepared)
    matched = derive_common_coordinates(raw, prompt_ids=prompts, vector_ids=vectors)
    profile = build_k1_profile(validated_run, matched["intersection_coordinates"], prompt_ids=prompts, vector_ids=vectors)
    if len(profile["k1_reuse_records"]) != 3_784:
        _invalid(f"REUSE_RECORD_COUNT:{len(profile['k1_reuse_records'])}")
    return ValidatedP2V2K1Inputs(validated_run.loaded.run_directory, raw_path, formal_path, file_sha256(raw_path), file_sha256(formal_path), prepared, validated_run, raw, formal, {**profile, "matched_counts": matched})


def validation_summary(validated: ValidatedP2V2K1Inputs) -> dict[str, Any]:
    counts = validated.profile["matched_counts"]
    return {"status": "P2_V2_K1_VALIDATE_ONLY_PASS", "M_T": counts["M_T_count"], "M_H": counts["M_H_count"], "intersection": counts["intersection_count"], "reuse_records": len(validated.profile["k1_reuse_records"]), "generation_calls_added": 0, "judge_calls_added": 0, "statistics_executed": False, "output_written": False}


def assemble_p2_v2_k1_result(validated: ValidatedP2V2K1Inputs, *, statistics_function: Callable[..., dict[str, Any]] | None = None) -> dict[str, Any]:
    statistic = retained_bootstrap.analyze_k1 if statistics_function is None else statistics_function
    statistics = statistic(validated.profile["statistics_input"], fixture_mode=False, cell_order=list(CELL_ORDER))
    counts = validated.profile["matched_counts"]
    return {"schema_version": SCHEMA_VERSION, "status": "ESTIMABLE", "paper_result_eligible": False, "raw_result_status": validated.raw_result["status"], "formal_result_status": validated.formal_result["status"], "formal_status": validated.formal_result["formal_status"], "terminal_partition": dict(validated.raw_result["terminal_partition"]), "source": {**_source_summary(validated.p2_raw_result_path, validated.p2_formal_result_path, validated.raw_result, validated.formal_result), "p2_run_directory": str(validated.p2_run_directory), "p2_run_id": validated.p2_run_directory.name}, "cell_order": list(CELL_ORDER), "label_order": list(retained_bootstrap.HARMFUL_LABELS), "matched_profile_counts": {"M_T": counts["M_T_count"], "M_H": counts["M_H_count"], "intersection": counts["intersection_count"]}, "prompt_frame": validated.profile["prompt_frame"], "vector_frame": validated.profile["vector_frame"], "matched_coordinates": validated.profile["matched_coordinates"], "k1_reuse_record_count": len(validated.profile["k1_reuse_records"]), "k1_reuse_records": validated.profile["k1_reuse_records"], "generation_calls_added": 0, "judge_calls_added": 0, "statistics_contract": {"implementation_version": retained_bootstrap.IMPLEMENTATION_VERSION, "function": "analyze_k1", "algorithm": "retained_percentile_nearest_rank_v1", "rng_namespace": retained_bootstrap.RNG_NAMESPACE, "replicates": 10_000, "min_success": 9_500, "cell_order": list(CELL_ORDER), "label_order": list(retained_bootstrap.HARMFUL_LABELS), "shared_draws": "one prompt draw and one vector draw reused by all four cells", "interval": "nearest_rank_95_percentile_no_interpolation", "inferential_claim": "descriptive_only_no_test"}, "statistics_input": validated.profile["statistics_input"], "statistics": statistics, "scope": {"profile": "M_T_intersection_M_H_matched_coordinates_only", "coordinate_requirement": "all_four_cells_have_retained_labels", "inferential_claim": "cell-wise descriptive profiles only; no P2 contrast, p value, global test, or confirmatory conclusion"}}


def materialize_p2_v2_k1_results_directory(p2_run_directory: Path, p2_raw_result: Path, p2_formal_result: Path, output_directory: Path, *, statistics_function: Callable[..., dict[str, Any]] | None = None, config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    output = _check_output_directory(output_directory, [p2_run_directory, p2_raw_result, p2_formal_result])
    validated = validate_p2_v2_k1_inputs(p2_run_directory, p2_raw_result, p2_formal_result, output_directory, config_path=config_path)
    result = assemble_p2_v2_k1_result(validated, statistics_function=statistics_function)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError:
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    OutputStore(output).write_json_once(OUTPUT_FILENAME, result)
    return result


__all__ = ["CELL_ORDER", "FORMAL_RESULT_PATH", "OUTPUT_FILENAME", "P2V2K1ResultInputInvalid", "ValidatedP2V2K1Inputs", "assemble_p2_v2_k1_result", "build_k1_profile", "derive_common_coordinates", "materialize_p2_v2_k1_results_directory", "validate_p2_v2_k1_inputs", "validation_summary"]
