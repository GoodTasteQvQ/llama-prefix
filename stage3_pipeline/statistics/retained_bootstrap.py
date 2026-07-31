#!/usr/bin/env python3
"""Current retained-bootstrap implementation for Stage 3."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


IMPLEMENTATION_VERSION = "paper1-stage3-retained-bootstrap-v1"
RNG_NAMESPACE = "v3.5-rc2"
SCHEMA_VERSION = "paper1-stage3-retained-bootstrap-input-v1"
MASTER_SEED = 42
PRODUCTION_REPLICATES = 10_000
PRODUCTION_MIN_SUCCESS = 9_500
PRODUCTION_SUCCESS_FRACTION = 0.95

K1_BLOCK_ID = "k1-profile"
HARMFUL_CLEAN_BLOCK_ID = "harmful-clean-prompt"
BENIGN_BROKEN_BLOCK_ID = "benign-broken-prompt"

K1_CELLS = ("P2_A_all", "P2_A_content", "P2_T_all", "P2_T_content")
HARMFUL_LABELS = ("broken", "unsafe", "refusal", "safe")
BENIGN_LABELS = ("broken", "unsafe", "refusal", "helpful")

FAILURE_PRECEDENCE = (
    "INPUT_SCHEMA_INVALID",
    "IDENTITY_COLLISION",
    "FRAME_ORDER_INVALID",
    "INVALID_DENOMINATOR",
    "NONFINITE_INPUT",
    "INSUFFICIENT_RESAMPLING_UNITS",
    "RESAMPLING_COMPLETION_INSUFFICIENT",
    "NONFINITE_INTERVAL",
    "RNG_IDENTITY_INVALID",
)

REPORT_STATUS = {
    "INPUT_SCHEMA_INVALID": "INPUT_INVALID_NON_ESTIMABLE",
    "IDENTITY_COLLISION": "INPUT_INVALID_NON_ESTIMABLE",
    "FRAME_ORDER_INVALID": "INPUT_INVALID_NON_ESTIMABLE",
    "INVALID_DENOMINATOR": "INPUT_INVALID_NON_ESTIMABLE",
    "NONFINITE_INPUT": "INPUT_INVALID_NON_ESTIMABLE",
    "INSUFFICIENT_RESAMPLING_UNITS": "INSUFFICIENT_CLUSTERS_NON_ESTIMABLE",
    "RESAMPLING_COMPLETION_INSUFFICIENT": "RESAMPLING_COMPLETION_NON_ESTIMABLE",
    "NONFINITE_INTERVAL": "NONFINITE_INTERVAL_NON_ESTIMABLE",
    "RNG_IDENTITY_INVALID": "IMPLEMENTATION_FIX_REQUIRED",
}


class RetainedBootstrapError(ValueError):
    """A first-precedence non-estimability or implementation failure."""

    def __init__(self, code: str, detail: str):
        if code not in FAILURE_PRECEDENCE:
            raise ValueError(f"unknown retained-bootstrap failure code: {code}")
        self.code = code
        self.detail = detail
        self.report_status = REPORT_STATUS[code]
        super().__init__(f"{code}:{detail}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_output_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _identity_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", f"{field} must be a nonempty string")
    return value


def _exact_keys(value: Any, required: set[str], where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", f"{where} must be an object")
    actual = set(value)
    if actual != required:
        missing = sorted(required - actual)
        extra = sorted(actual - required)
        raise RetainedBootstrapError(
            "INPUT_SCHEMA_INVALID", f"{where} keys missing={missing} extra={extra}"
        )
    return value


def _validate_header(payload: Mapping[str, Any], block_type: str, fixture_mode: bool) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "schema_version mismatch")
    if payload.get("block_type") != block_type:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", f"block_type must be {block_type}")
    if not isinstance(payload.get("synthetic_data"), bool):
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "synthetic_data must be boolean")
    if bool(payload["synthetic_data"]) != fixture_mode:
        raise RetainedBootstrapError(
            "INPUT_SCHEMA_INVALID",
            "fixture_mode requires synthetic_data=true and production requires false",
        )


def frame_sha256(axis: str, ordered_ids: Sequence[str]) -> str:
    payload = {"axis": axis, "ordered_ids": list(ordered_ids)}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def sync_unit_id(*, family: str, axis: str, frame_hash: str, **forbidden: Any) -> str:
    if forbidden:
        if "member_id" in forbidden or "member" in forbidden:
            raise RetainedBootstrapError(
                "RNG_IDENTITY_INVALID", "member identity must not enter sync_unit_id"
            )
        raise RetainedBootstrapError(
            "RNG_IDENTITY_INVALID", f"unexpected sync identity fields: {sorted(forbidden)}"
        )
    allowed = {
        ("k1-profile", "prompt"),
        ("k1-profile", "vector"),
        ("harmful-clean", "prompt"),
        ("benign-broken", "prompt"),
    }
    if (family, axis) not in allowed:
        raise RetainedBootstrapError(
            "RNG_IDENTITY_INVALID", f"unregistered family/axis combination: {family}/{axis}"
        )
    if not isinstance(frame_hash, str) or re.fullmatch(r"[0-9a-f]{64}", frame_hash) is None:
        raise RetainedBootstrapError(
            "RNG_IDENTITY_INVALID", "frame_hash must be 64 lowercase hexadecimal characters"
        )
    return canonical_json(
        {"axis": axis, "entity_id": f"sha256:{frame_hash}", "family": family}
    )


def seed_bytes(block_id: str, unit_id: str, replicate_index: int) -> bytes:
    if replicate_index < 1:
        raise RetainedBootstrapError(
            "RNG_IDENTITY_INVALID", "replicate_index must start at one"
        )
    try:
        identity = json.loads(unit_id)
    except (json.JSONDecodeError, TypeError) as error:
        raise RetainedBootstrapError("RNG_IDENTITY_INVALID", "sync_unit_id is not JSON") from error
    if not isinstance(identity, dict) or set(identity) != {"axis", "entity_id", "family"}:
        raise RetainedBootstrapError("RNG_IDENTITY_INVALID", "sync_unit_id keys are not exact")
    if canonical_json(identity) != unit_id:
        raise RetainedBootstrapError("RNG_IDENTITY_INVALID", "sync_unit_id is not canonical JSON")
    expected = {
        K1_BLOCK_ID: {("k1-profile", "prompt"), ("k1-profile", "vector")},
        HARMFUL_CLEAN_BLOCK_ID: {("harmful-clean", "prompt")},
        BENIGN_BROKEN_BLOCK_ID: {("benign-broken", "prompt")},
    }
    if block_id not in expected or (identity["family"], identity["axis"]) not in expected[block_id]:
        raise RetainedBootstrapError(
            "RNG_IDENTITY_INVALID", "block/family/axis combination is not registered"
        )
    entity_id = identity["entity_id"]
    if not isinstance(entity_id, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", entity_id) is None:
        raise RetainedBootstrapError("RNG_IDENTITY_INVALID", "entity_id is not sha256:<lower-hex>")
    payload = (
        f"{RNG_NAMESPACE}|master={MASTER_SEED}|block={block_id}"
        f"|sync_unit={unit_id}|rep={replicate_index:06d}"
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()[:16]


class Sha256CounterRng:
    """SHA256(seed || uint64_be(counter)); first uint64_be word; rejection sampling."""

    def __init__(self, seed: bytes):
        if len(seed) != 16:
            raise RetainedBootstrapError("RNG_IDENTITY_INVALID", "seed must be 16 bytes")
        self.seed = seed
        self.counter = 0

    def uint64(self) -> int:
        digest = hashlib.sha256(
            self.seed + self.counter.to_bytes(8, "big", signed=False)
        ).digest()
        self.counter += 1
        return int.from_bytes(digest[:8], "big", signed=False)

    def randbelow(self, upper: int) -> int:
        value, _ = rejection_sample(self.uint64, upper)
        return value


def rejection_sample(next_word: Any, upper: int) -> tuple[int, int]:
    """Return (draw, words consumed); shared by production and scripted golden."""
    if not isinstance(upper, int) or isinstance(upper, bool) or upper <= 0:
        raise RetainedBootstrapError("RNG_IDENTITY_INVALID", "upper must be a positive integer")
    limit = (1 << 64) - ((1 << 64) % upper)
    consumed = 0
    while True:
        word = next_word()
        consumed += 1
        if not isinstance(word, int) or isinstance(word, bool) or not 0 <= word < (1 << 64):
            raise RetainedBootstrapError("RNG_IDENTITY_INVALID", "uint64 source emitted invalid word")
        if word < limit:
            return word % upper, consumed


def nearest_rank(values: Iterable[float], probability: float) -> float:
    items = sorted(values)
    if not items:
        raise RetainedBootstrapError("NONFINITE_INTERVAL", "nearest-rank input is empty")
    if not 0.0 < probability <= 1.0:
        raise RetainedBootstrapError("NONFINITE_INTERVAL", "invalid nearest-rank probability")
    if not all(math.isfinite(value) for value in items):
        raise RetainedBootstrapError("NONFINITE_INTERVAL", "nearest-rank input is nonfinite")
    rank = max(1, math.ceil(probability * len(items)))
    return items[rank - 1]


def sample_sd(values: Iterable[float]) -> float:
    items = list(values)
    if len(items) < 2 or not all(math.isfinite(value) for value in items):
        raise RetainedBootstrapError("NONFINITE_INTERVAL", "bootstrap SD input invalid")
    center = math.fsum(items) / len(items)
    variance = math.fsum((value - center) ** 2 for value in items) / (len(items) - 1)
    if not math.isfinite(variance) or variance < 0.0:
        raise RetainedBootstrapError("NONFINITE_INTERVAL", "bootstrap variance invalid")
    return math.sqrt(variance)


def _validate_frame(
    frame: Any,
    *,
    axis: str,
    id_field: str,
    production_size: int,
    fixture_mode: bool,
    production_min_size: int | None = None,
    defer_order: bool = False,
) -> tuple[list[str], dict[str, int]]:
    if not isinstance(frame, list) or not frame:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", f"{axis}_frame must be nonempty array")
    ids: list[str] = []
    positions: list[int] = []
    for index, raw in enumerate(frame):
        item = _exact_keys(raw, {"position", id_field}, f"{axis}_frame[{index}]")
        ids.append(_identity_text(item[id_field], f"{axis}_frame[{index}].{id_field}"))
        position = item["position"]
        if not isinstance(position, int) or isinstance(position, bool):
            raise RetainedBootstrapError(
                "INPUT_SCHEMA_INVALID", f"{axis}_frame[{index}].position must be integer"
            )
        positions.append(position)

    # Collision precedes all ordering and value/denominator checks.
    if len(ids) != len(set(ids)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", f"duplicate {id_field}")
    if len(positions) != len(set(positions)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", f"duplicate {axis} frame position")
    if not defer_order and positions != list(range(len(frame))):
        raise RetainedBootstrapError(
            "FRAME_ORDER_INVALID", f"{axis} positions must be contiguous zero-based input order"
        )
    minimum = production_size if production_min_size is None else production_min_size
    if not fixture_mode and not minimum <= len(frame) <= production_size:
        raise RetainedBootstrapError(
            "INPUT_SCHEMA_INVALID",
            f"production {axis} frame requires between {minimum} and {production_size} units",
        )
    return ids, {identity: position for identity, position in zip(ids, positions)}


def _validate_frame_order(frame: Any, axis: str) -> None:
    positions = [item["position"] for item in frame]
    if positions != list(range(len(frame))):
        raise RetainedBootstrapError(
            "FRAME_ORDER_INVALID", f"{axis} positions must be contiguous zero-based input order"
        )


def _draw_multiplicities(
    block_id: str, unit_id: str, replicate: int, frame_size: int
) -> tuple[list[int], list[int]]:
    rng = Sha256CounterRng(seed_bytes(block_id, unit_id, replicate))
    draws = [rng.randbelow(frame_size) for _ in range(frame_size)]
    counts = Counter(draws)
    return draws, [counts.get(index, 0) for index in range(frame_size)]


def _finalize(
    point: Mapping[str, float],
    draws: Mapping[str, list[float]],
    *,
    failures: Sequence[str],
    replicates_requested: int = PRODUCTION_REPLICATES,
    min_success: int = PRODUCTION_MIN_SUCCESS,
) -> dict[str, Any]:
    if not point or set(point) != set(draws):
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "point/draw statistic keys differ")
    if not all(math.isfinite(float(value)) for value in point.values()):
        raise RetainedBootstrapError("NONFINITE_INPUT", "point statistic is nonfinite")
    lengths = {len(values) for values in draws.values()}
    if len(lengths) != 1:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "statistics do not share success set")
    successes = next(iter(lengths))
    if successes < min_success:
        raise RetainedBootstrapError(
            "RESAMPLING_COMPLETION_INSUFFICIENT", f"{successes}<{min_success}"
        )

    intervals: dict[str, Any] = {}
    for statistic_id in sorted(point):
        values = draws[statistic_id]
        sd = sample_sd(values)
        if sd == 0.0:
            bounds = [float(point[statistic_id]), float(point[statistic_id])]
            degenerate = True
        else:
            bounds = [nearest_rank(values, 0.025), nearest_rank(values, 0.975)]
            degenerate = False
        if not all(math.isfinite(value) for value in bounds):
            raise RetainedBootstrapError(
                "NONFINITE_INTERVAL", f"nonfinite bounds for {statistic_id}"
            )
        intervals[statistic_id] = {
            "bootstrap_sd": sd,
            "degenerate_bootstrap": degenerate,
            "percentile_95": bounds,
            "point": float(point[statistic_id]),
        }
    return {
        "replicates_requested": replicates_requested,
        "replicates_required": min_success,
        "replicates_successful": successes,
        "replicates_failed": replicates_requested - successes,
        "first_failure_reasons": list(failures[:5]),
        "statistics": intervals,
    }


def _result_header(block_id: str) -> dict[str, Any]:
    return {
        "algorithm": "retained_percentile_nearest_rank_v1",
        "block_id": block_id,
        "failure_precedence": list(FAILURE_PRECEDENCE),
        "inferential_claim": "descriptive_or_ci_only_no_test",
        "interval": "nearest_rank_[Q_NR(0.025),Q_NR(0.975)]_no_interpolation",
        "master_seed": MASTER_SEED,
        "status": "ESTIMABLE",
    }


def _profile_point(records: Sequence[Mapping[str, Any]], labels: Sequence[str]) -> dict[str, float]:
    denominator = len(records)
    if denominator <= 0:
        raise RetainedBootstrapError("INVALID_DENOMINATOR", "profile denominator is zero")
    return {
        label: sum(1 for row in records if row["label"] == label) / denominator
        for label in labels
    }


def analyze_k1(payload: Mapping[str, Any], *, fixture_mode: bool = False) -> dict[str, Any]:
    required = {"schema_version", "synthetic_data", "block_type", "prompt_frame", "vector_frame", "cells"}
    _exact_keys(payload, required, "k1 payload")
    _validate_header(payload, "k1", fixture_mode)
    prompt_ids, prompt_position = _validate_frame(
        payload["prompt_frame"], axis="prompt", id_field="prompt_id", production_size=50,
        fixture_mode=fixture_mode, defer_order=True,
    )
    vector_ids, vector_position = _validate_frame(
        payload["vector_frame"], axis="vector", id_field="vector_id", production_size=20,
        fixture_mode=fixture_mode, defer_order=True,
    )
    cells_raw = payload["cells"]
    if not isinstance(cells_raw, list) or len(cells_raw) != 4:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "K1 requires exactly four cells")

    cells: dict[str, list[Mapping[str, Any]]] = {}
    cell_ids: list[str] = []
    row_ids: list[str] = []
    coordinates: list[tuple[str, str, str]] = []
    for cell_index, raw_cell in enumerate(cells_raw):
        cell = _exact_keys(raw_cell, {"cell_id", "records"}, f"cells[{cell_index}]")
        cell_id = _identity_text(cell["cell_id"], f"cells[{cell_index}].cell_id")
        cell_ids.append(cell_id)
        records = cell["records"]
        if not isinstance(records, list):
            raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", f"{cell_id}.records must be array")
        parsed: list[Mapping[str, Any]] = []
        for row_index, raw_row in enumerate(records):
            row = _exact_keys(
                raw_row, {"row_id", "prompt_id", "vector_id", "label"},
                f"{cell_id}.records[{row_index}]",
            )
            row_id = _identity_text(row["row_id"], f"{cell_id}.row_id")
            prompt_id = _identity_text(row["prompt_id"], f"{cell_id}.prompt_id")
            vector_id = _identity_text(row["vector_id"], f"{cell_id}.vector_id")
            row_ids.append(row_id)
            coordinates.append((cell_id, prompt_id, vector_id))
            parsed.append(row)
        cells[cell_id] = parsed

    # Cell, row, and per-cell logical coordinates are separate collision domains.
    if len(cell_ids) != len(set(cell_ids)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", "duplicate K1 cell_id")
    if len(row_ids) != len(set(row_ids)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", "duplicate K1 row_id")
    if len(coordinates) != len(set(coordinates)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", "duplicate K1 cell/prompt/vector coordinate")
    _validate_frame_order(payload["prompt_frame"], "prompt")
    _validate_frame_order(payload["vector_frame"], "vector")
    if cell_ids != list(K1_CELLS) or set(cells) != set(K1_CELLS):
        raise RetainedBootstrapError("FRAME_ORDER_INVALID", "K1 cell order is not canonical")

    for cell_id in K1_CELLS:
        records = cells[cell_id]
        for row in records:
            if row["prompt_id"] not in prompt_position or row["vector_id"] not in vector_position:
                raise RetainedBootstrapError(
                    "INPUT_SCHEMA_INVALID", f"{cell_id} row references identity outside fixed frame"
                )
            if row["label"] not in HARMFUL_LABELS:
                raise RetainedBootstrapError(
                    "INPUT_SCHEMA_INVALID", f"{cell_id} has invalid harmful label"
                )
        actual_coordinates = [(row["prompt_id"], row["vector_id"]) for row in records]
        expected_coordinates = [
            (prompt_id, vector_id)
            for prompt_id in prompt_ids
            for vector_id in vector_ids
        ]
        if set(actual_coordinates) != set(expected_coordinates):
            raise RetainedBootstrapError(
                "INPUT_SCHEMA_INVALID",
                f"{cell_id} must contain each fixed prompt/vector coordinate exactly once",
            )
        if actual_coordinates != expected_coordinates:
            raise RetainedBootstrapError("FRAME_ORDER_INVALID", f"{cell_id} rows are not canonical")

    points_by_cell = {cell_id: _profile_point(cells[cell_id], HARMFUL_LABELS) for cell_id in K1_CELLS}
    if len(prompt_ids) < 2 or len(vector_ids) < 2:
        raise RetainedBootstrapError(
            "INSUFFICIENT_RESAMPLING_UNITS", "K1 requires at least two prompt and vector units"
        )

    prompt_hash = frame_sha256("prompt", prompt_ids)
    vector_hash = frame_sha256("vector", vector_ids)
    prompt_sync = sync_unit_id(family="k1-profile", axis="prompt", frame_hash=prompt_hash)
    vector_sync = sync_unit_id(family="k1-profile", axis="vector", frame_hash=vector_hash)
    flat_point = {
        f"{cell_id}|{label}": points_by_cell[cell_id][label]
        for cell_id in K1_CELLS for label in HARMFUL_LABELS
    }
    successful = {key: [] for key in flat_point}
    failures: list[str] = []
    replicate_audit: list[dict[str, Any]] = []

    for replicate in range(1, PRODUCTION_REPLICATES + 1):
        prompt_draws, prompt_mult = _draw_multiplicities(
            K1_BLOCK_ID, prompt_sync, replicate, len(prompt_ids)
        )
        vector_draws, vector_mult = _draw_multiplicities(
            K1_BLOCK_ID, vector_sync, replicate, len(vector_ids)
        )
        values: dict[str, float] = {}
        denominators: dict[str, int] = {}
        try:
            for cell_id in K1_CELLS:
                weighted_rows: list[tuple[Mapping[str, Any], int]] = []
                for row in cells[cell_id]:
                    weight = (
                        prompt_mult[prompt_position[row["prompt_id"]]]
                        * vector_mult[vector_position[row["vector_id"]]]
                    )
                    weighted_rows.append((row, weight))
                denominator = sum(weight for _, weight in weighted_rows)
                if denominator <= 0:
                    raise RetainedBootstrapError(
                        "INVALID_DENOMINATOR", f"replicate {replicate} {cell_id} denominator zero"
                    )
                denominators[cell_id] = denominator
                for label in HARMFUL_LABELS:
                    numerator = sum(weight for row, weight in weighted_rows if row["label"] == label)
                    value = numerator / denominator
                    if not math.isfinite(value):
                        raise RetainedBootstrapError(
                            "NONFINITE_INPUT", f"replicate {replicate} {cell_id}|{label} nonfinite"
                        )
                    values[f"{cell_id}|{label}"] = value
        except RetainedBootstrapError as error:
            failures.append(str(error))
            continue
        for key in successful:
            successful[key].append(values[key])
        if replicate <= 3:
            p0v0_weight = prompt_mult[0] * vector_mult[0]
            replicate_audit.append(
                {
                    "cell_denominators": denominators,
                    "product_weight_p0_v0": p0v0_weight,
                    "prompt_draw_indices": prompt_draws,
                    "prompt_multiplicities": prompt_mult,
                    "replicate": replicate,
                    "shared_by_cells": list(K1_CELLS),
                    "vector_draw_indices": vector_draws,
                    "vector_multiplicities": vector_mult,
                }
            )

    result = _result_header(K1_BLOCK_ID)
    result.update(
        {
            "block_type": "k1",
            "cell_order": list(K1_CELLS),
            "frame": {
                "prompt_frame_sha256": prompt_hash,
                "prompt_order": prompt_ids,
                "prompt_sample_size_per_replicate": len(prompt_ids),
                "vector_frame_sha256": vector_hash,
                "vector_order": vector_ids,
                "vector_sample_size_per_replicate": len(vector_ids),
            },
            "replicate_audit_first_three": replicate_audit,
            "row_weight": "prompt_multiplicity*vector_multiplicity",
            "shared_draws": "one prompt draw and one vector draw reused by all four cells",
            "sync_unit_id": {"prompt": prompt_sync, "vector": vector_sync},
        }
    )
    result.update(_finalize(flat_point, successful, failures=failures))
    return result


def analyze_harmful_clean(
    payload: Mapping[str, Any], *, fixture_mode: bool = False
) -> dict[str, Any]:
    required = {"schema_version", "synthetic_data", "block_type", "prompt_frame", "records"}
    _exact_keys(payload, required, "harmful-clean payload")
    _validate_header(payload, "harmful_clean", fixture_mode)
    prompt_ids, prompt_position = _validate_frame(
        payload["prompt_frame"], axis="prompt", id_field="prompt_id", production_size=50,
        fixture_mode=fixture_mode, defer_order=True,
    )
    records_raw = payload["records"]
    if not isinstance(records_raw, list) or not records_raw:
        raise RetainedBootstrapError(
            "INPUT_SCHEMA_INVALID", "harmful-clean records must be nonempty array"
        )
    records: list[Mapping[str, Any]] = []
    row_ids: list[str] = []
    coordinates: list[str] = []
    for index, raw_row in enumerate(records_raw):
        row = _exact_keys(raw_row, {"row_id", "prompt_id", "label"}, f"records[{index}]")
        row_ids.append(_identity_text(row["row_id"], f"records[{index}].row_id"))
        coordinates.append(_identity_text(row["prompt_id"], f"records[{index}].prompt_id"))
        records.append(row)
    if len(row_ids) != len(set(row_ids)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", "duplicate harmful-clean row_id")
    if len(coordinates) != len(set(coordinates)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", "duplicate harmful-clean prompt coordinate")
    _validate_frame_order(payload["prompt_frame"], "prompt")
    for row in records:
        if row["prompt_id"] not in prompt_position:
            raise RetainedBootstrapError(
                "INPUT_SCHEMA_INVALID", "harmful-clean row outside fixed prompt frame"
            )
        if row["label"] not in HARMFUL_LABELS:
            raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "invalid harmful-clean label")
    retained_coordinates = set(coordinates)
    canonical_retained_order = [
        prompt_id for prompt_id in prompt_ids if prompt_id in retained_coordinates
    ]
    if coordinates != canonical_retained_order:
        raise RetainedBootstrapError("FRAME_ORDER_INVALID", "harmful-clean rows are not canonical")
    point = _profile_point(records, HARMFUL_LABELS)
    if len(prompt_ids) < 2:
        raise RetainedBootstrapError(
            "INSUFFICIENT_RESAMPLING_UNITS", "harmful clean requires at least two prompts"
        )

    prompt_hash = frame_sha256("prompt", prompt_ids)
    prompt_sync = sync_unit_id(family="harmful-clean", axis="prompt", frame_hash=prompt_hash)
    successful = {label: [] for label in HARMFUL_LABELS}
    failures: list[str] = []
    first_draws: list[dict[str, Any]] = []
    for replicate in range(1, PRODUCTION_REPLICATES + 1):
        draw_indices, multiplicities = _draw_multiplicities(
            HARMFUL_CLEAN_BLOCK_ID, prompt_sync, replicate, len(prompt_ids)
        )
        weighted = [
            (row, multiplicities[prompt_position[row["prompt_id"]]]) for row in records
        ]
        denominator = sum(weight for _, weight in weighted)
        if denominator <= 0:
            failures.append(f"INVALID_DENOMINATOR:replicate {replicate} denominator zero")
            continue
        for label in HARMFUL_LABELS:
            numerator = sum(weight for row, weight in weighted if row["label"] == label)
            successful[label].append(numerator / denominator)
        if replicate <= 3:
            first_draws.append(
                {
                    "draw_indices": draw_indices,
                    "multiplicities": multiplicities,
                    "replicate": replicate,
                }
            )

    result = _result_header(HARMFUL_CLEAN_BLOCK_ID)
    result.update(
        {
            "block_type": "harmful_clean",
            "frame": {
                "prompt_frame_sha256": prompt_hash,
                "prompt_order": prompt_ids,
                "prompt_sample_size_per_replicate": len(prompt_ids),
            },
            "replicate_audit_first_three": first_draws,
            "sync_unit_id": {"prompt": prompt_sync},
        }
    )
    result.update(_finalize(point, successful, failures=failures))
    return result


def analyze_benign_broken(
    payload: Mapping[str, Any], *, fixture_mode: bool = False
) -> dict[str, Any]:
    required = {
        "schema_version", "synthetic_data", "block_type", "complete_prompt_frame",
        "vector_frame", "prompts",
    }
    _exact_keys(payload, required, "benign-broken payload")
    _validate_header(payload, "benign_broken", fixture_mode)
    prompt_ids, prompt_position = _validate_frame(
        payload["complete_prompt_frame"], axis="complete-prompt", id_field="prompt_id",
        production_size=30, production_min_size=1, fixture_mode=fixture_mode, defer_order=True,
    )
    vector_ids, vector_position = _validate_frame(
        payload["vector_frame"], axis="vector", id_field="vector_id", production_size=20,
        fixture_mode=fixture_mode, defer_order=True,
    )
    if len(vector_ids) != 20:
        raise RetainedBootstrapError(
            "INPUT_SCHEMA_INVALID", "benign complete prompts require exactly 20 vectors"
        )
    prompts_raw = payload["prompts"]
    if not isinstance(prompts_raw, list):
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "benign prompts must be array")

    prompts: list[Mapping[str, Any]] = []
    response_ids: list[str] = []
    prompt_record_ids: list[str] = []
    coordinates: list[tuple[str, str]] = []
    for prompt_index, raw_prompt in enumerate(prompts_raw):
        prompt = _exact_keys(
            raw_prompt, {"prompt_id", "clean", "steered"}, f"prompts[{prompt_index}]"
        )
        prompt_id = _identity_text(prompt["prompt_id"], f"prompts[{prompt_index}].prompt_id")
        prompt_record_ids.append(prompt_id)
        clean = _exact_keys(
            prompt["clean"], {"response_id", "label"}, f"prompts[{prompt_index}].clean"
        )
        response_ids.append(_identity_text(clean["response_id"], "clean.response_id"))
        steered = prompt["steered"]
        if not isinstance(steered, list):
            raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "steered must be array")
        for vector_index, raw_row in enumerate(steered):
            row = _exact_keys(
                raw_row, {"response_id", "vector_id", "label"},
                f"prompts[{prompt_index}].steered[{vector_index}]",
            )
            vector_id = _identity_text(row["vector_id"], "steered.vector_id")
            response_ids.append(_identity_text(row["response_id"], "steered.response_id"))
            coordinates.append((prompt_id, vector_id))
        prompts.append(prompt)

    if len(prompt_record_ids) != len(set(prompt_record_ids)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", "duplicate benign prompt record")
    if len(response_ids) != len(set(response_ids)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", "duplicate benign response_id")
    if len(coordinates) != len(set(coordinates)):
        raise RetainedBootstrapError("IDENTITY_COLLISION", "duplicate benign prompt/vector coordinate")
    _validate_frame_order(payload["complete_prompt_frame"], "complete-prompt")
    _validate_frame_order(payload["vector_frame"], "vector")
    if prompt_record_ids != prompt_ids:
        raise RetainedBootstrapError(
            "FRAME_ORDER_INVALID", "benign prompt records must exactly match complete-prompt frame"
        )

    prompt_differences: list[float] = []
    for prompt in prompts:
        if prompt["clean"]["label"] not in BENIGN_LABELS:
            raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "invalid benign clean label")
        steered = prompt["steered"]
        if len(steered) != 20 or [row["vector_id"] for row in steered] != vector_ids:
            raise RetainedBootstrapError(
                "FRAME_ORDER_INVALID", "each benign prompt must contain all 20 vectors in frame order"
            )
        if any(row["label"] not in BENIGN_LABELS for row in steered):
            raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "invalid benign steered label")
        vector_average = math.fsum(1.0 if row["label"] == "broken" else 0.0 for row in steered) / 20.0
        clean_broken = 1.0 if prompt["clean"]["label"] == "broken" else 0.0
        difference = vector_average - clean_broken
        if not math.isfinite(difference):
            raise RetainedBootstrapError("NONFINITE_INPUT", "benign prompt difference is nonfinite")
        prompt_differences.append(difference)
    if not prompt_differences:
        raise RetainedBootstrapError("INVALID_DENOMINATOR", "benign complete-prompt denominator zero")
    if len(prompt_ids) < 2:
        raise RetainedBootstrapError(
            "INSUFFICIENT_RESAMPLING_UNITS", "benign broken RD requires at least two complete prompts"
        )

    point = {"RD_benign_broken": math.fsum(prompt_differences) / len(prompt_differences)}
    prompt_hash = frame_sha256("complete-prompt", prompt_ids)
    prompt_sync = sync_unit_id(family="benign-broken", axis="prompt", frame_hash=prompt_hash)
    successful = {"RD_benign_broken": []}
    first_draws: list[dict[str, Any]] = []
    for replicate in range(1, PRODUCTION_REPLICATES + 1):
        draw_indices, multiplicities = _draw_multiplicities(
            BENIGN_BROKEN_BLOCK_ID, prompt_sync, replicate, len(prompt_ids)
        )
        value = math.fsum(prompt_differences[index] for index in draw_indices) / len(prompt_ids)
        if not math.isfinite(value):
            continue
        successful["RD_benign_broken"].append(value)
        if replicate <= 3:
            first_draws.append(
                {
                    "draw_indices": draw_indices,
                    "multiplicities": multiplicities,
                    "replicate": replicate,
                }
            )

    result = _result_header(BENIGN_BROKEN_BLOCK_ID)
    result.update(
        {
            "block_type": "benign_broken",
            "frame": {
                "complete_prompt_frame_sha256": prompt_hash,
                "complete_prompt_order": prompt_ids,
                "prompt_sample_size_per_replicate": len(prompt_ids),
                "vector_average_size": 20,
                "vector_order": vector_ids,
            },
            "operation_order": "20-vector average within complete prompt, then prompt bootstrap",
            "prompt_differences": prompt_differences,
            "replicate_audit_first_three": first_draws,
            "sync_unit_id": {"prompt": prompt_sync},
        }
    )
    result.update(_finalize(point, successful, failures=[]))
    return result


def rng_success_golden(spec: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(spec, {"cases", "scripted_rejection"}, "rng_success")
    if not isinstance(spec["cases"], list) or not spec["cases"]:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "rng_success.cases must be nonempty")
    results: list[dict[str, Any]] = []
    for index, raw_case in enumerate(spec["cases"]):
        case = _exact_keys(
            raw_case,
            {"case_id", "family", "axis", "frame_hash", "block_id", "replicate", "upper", "draw_count"},
            f"rng_success.cases[{index}]",
        )
        _identity_text(case["case_id"], f"rng_success.cases[{index}].case_id")
        if not isinstance(case["replicate"], int) or isinstance(case["replicate"], bool):
            raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "rng replicate must be integer")
        if not isinstance(case["upper"], int) or isinstance(case["upper"], bool):
            raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "rng upper must be integer")
        if not isinstance(case["draw_count"], int) or isinstance(case["draw_count"], bool) or case["draw_count"] <= 0:
            raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "rng draw_count must be positive integer")
        unit_id = sync_unit_id(
            family=case["family"], axis=case["axis"], frame_hash=case["frame_hash"]
        )
        seed = seed_bytes(case["block_id"], unit_id, case["replicate"])
        rng = Sha256CounterRng(seed)
        words: list[str] = []
        draws: list[int] = []
        upper = case["upper"]
        limit = (1 << 64) - ((1 << 64) % upper)
        while len(draws) < case["draw_count"]:
            word = rng.uint64()
            words.append(f"{word:016x}")
            if word < limit:
                draws.append(word % upper)
        results.append(
            {
                "case_id": case["case_id"],
                "draws": draws,
                "seed_hex": seed.hex(),
                "sync_unit_id": unit_id,
                "uint64_words_consumed_hex": words,
            }
        )
    scripted_spec = _exact_keys(
        spec["scripted_rejection"], {"words", "upper"}, "rng_success.scripted_rejection"
    )
    if not isinstance(scripted_spec["words"], list) or not scripted_spec["words"]:
        raise RetainedBootstrapError(
            "INPUT_SCHEMA_INVALID", "scripted_rejection.words must be nonempty"
        )
    scripted = iter(scripted_spec["words"])
    draw, consumed = rejection_sample(
        lambda: next(scripted), scripted_spec["upper"]
    )
    return {
        "cases": results,
        "scripted_rejection": {"draw": draw, "words_consumed": consumed},
    }


def evaluate_success_fixture(data: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(
        data,
        {
            "fixture_schema", "synthetic_data", "rng_success", "k1",
            "harmful_clean", "benign_broken", "zero_sd",
        },
        "success fixture",
    )
    if data.get("fixture_schema") != "paper1-stage3-retained-bootstrap-success-input-v1":
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "success fixture schema mismatch")
    if data.get("synthetic_data") is not True:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "success fixture must be synthetic")
    k1 = analyze_k1(data["k1"], fixture_mode=True)
    harmful = analyze_harmful_clean(data["harmful_clean"], fixture_mode=True)
    benign = analyze_benign_broken(data["benign_broken"], fixture_mode=True)
    zero_sd = analyze_harmful_clean(data["zero_sd"], fixture_mode=True)

    return {
        "fixture_schema": "paper1-stage3-retained-bootstrap-success-v1",
        "synthetic_data": True,
        "rng_success": rng_success_golden(data["rng_success"]),
        "k1": {
            "block_id": k1["block_id"],
            "canonical_output_sha256": canonical_output_sha256(k1),
            "replicates": [k1["replicates_successful"], k1["replicates_required"]],
            "row_weight": k1["row_weight"],
            "shared_draw_witness": k1["replicate_audit_first_three"][0],
            "statistics": k1["statistics"],
            "sync_unit_id": k1["sync_unit_id"],
        },
        "harmful_clean": {
            "block_id": harmful["block_id"],
            "canonical_output_sha256": canonical_output_sha256(harmful),
            "replicates": [harmful["replicates_successful"], harmful["replicates_required"]],
            "statistics": harmful["statistics"],
            "sync_unit_id": harmful["sync_unit_id"],
        },
        "benign_broken": {
            "block_id": benign["block_id"],
            "canonical_output_sha256": canonical_output_sha256(benign),
            "operation_order": benign["operation_order"],
            "prompt_differences": benign["prompt_differences"],
            "replicates": [benign["replicates_successful"], benign["replicates_required"]],
            "statistics": benign["statistics"],
            "sync_unit_id": benign["sync_unit_id"],
        },
        "zero_sd": {
            "canonical_output_sha256": canonical_output_sha256(zero_sd),
            "statistics": zero_sd["statistics"],
        },
    }


def _captured_failure(callable_object: Any) -> dict[str, Any]:
    try:
        callable_object()
    except RetainedBootstrapError as error:
        return {
            "code": error.code,
            "detail": error.detail,
            "report_status": error.report_status,
            "status": "NON_ESTIMABLE",
        }
    return {"code": None, "detail": None, "report_status": None, "status": "UNEXPECTED_PASS"}


def evaluate_failure_fixture(
    success_data: Mapping[str, Any], failure_data: Mapping[str, Any]
) -> dict[str, Any]:
    _exact_keys(failure_data, {"fixture_schema", "synthetic_data", "cases"}, "failure fixture")
    if failure_data.get("fixture_schema") != "paper1-stage3-retained-bootstrap-failure-input-v1":
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "failure fixture schema mismatch")
    if failure_data.get("synthetic_data") is not True:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "failure fixture must be synthetic")
    if not isinstance(failure_data["cases"], list) or not failure_data["cases"]:
        raise RetainedBootstrapError("INPUT_SCHEMA_INVALID", "failure fixture cases must be nonempty")
    results: list[dict[str, Any]] = []
    for case_index, raw_case in enumerate(failure_data["cases"]):
        case = _exact_keys(raw_case, {"case_id", "mutation"}, f"failure cases[{case_index}]")
        _identity_text(case["case_id"], f"failure cases[{case_index}].case_id")
        mutation = case["mutation"]
        if mutation == "k1_duplicate_prompt_identity":
            payload = copy.deepcopy(success_data["k1"])
            payload["prompt_frame"][1]["prompt_id"] = payload["prompt_frame"][0]["prompt_id"]
            call = lambda payload=payload: analyze_k1(payload, fixture_mode=True)
        elif mutation == "harmful_compound_order_and_row_collision":
            payload = copy.deepcopy(success_data["harmful_clean"])
            payload["prompt_frame"][0]["position"] = 1
            payload["prompt_frame"][1]["position"] = 0
            payload["records"][1]["row_id"] = payload["records"][0]["row_id"]
            call = lambda payload=payload: analyze_harmful_clean(payload, fixture_mode=True)
        elif mutation == "harmful_insufficient_units":
            payload = copy.deepcopy(success_data["harmful_clean"])
            keep = payload["prompt_frame"][0]["prompt_id"]
            payload["prompt_frame"] = payload["prompt_frame"][:1]
            payload["records"] = [row for row in payload["records"] if row["prompt_id"] == keep]
            call = lambda payload=payload: analyze_harmful_clean(payload, fixture_mode=True)
        elif mutation == "k1_missing_coordinate":
            payload = copy.deepcopy(success_data["k1"])
            payload["cells"][0]["records"].pop()
            call = lambda payload=payload: analyze_k1(payload, fixture_mode=True)
        elif mutation == "harmful_missing_prompt_coverage":
            payload = copy.deepcopy(success_data["harmful_clean"])
            payload["records"].pop()
            call = lambda payload=payload: analyze_harmful_clean(payload, fixture_mode=True)
        elif mutation == "harmful_invalid_denominator":
            # Internal failure-case check. Empty records remain invalid paper input.
            call = lambda: _profile_point([], HARMFUL_LABELS)
        elif mutation == "completion_9499":
            call = lambda: _finalize(
                {"synthetic_stat": 0.0}, {"synthetic_stat": [0.0] * 9_499},
                failures=["synthetic_nonfinite"] * 501,
            )
        elif mutation == "completion_9500":
            try:
                actual = _finalize(
                    {"synthetic_stat": 0.0}, {"synthetic_stat": [0.0] * 9_500},
                    failures=["synthetic_nonfinite"] * 500,
                )
            except RetainedBootstrapError as error:
                outcome = {
                    "code": error.code, "detail": error.detail,
                    "report_status": error.report_status, "status": "UNEXPECTED_FAILURE",
                }
            else:
                outcome = {
                    "code": None,
                    "detail": "9500 common successes accepted; degenerate interval retained",
                    "report_status": None,
                    "status": "EXPECTED_PASS",
                    "replicates_successful": actual["replicates_successful"],
                    "degenerate_bootstrap": actual["statistics"]["synthetic_stat"]["degenerate_bootstrap"],
                }
            results.append({"case_id": case["case_id"], **outcome})
            continue
        elif mutation == "nonfinite_point":
            call = lambda: _finalize(
                {"synthetic_stat": float("nan")},
                {"synthetic_stat": [0.0] * PRODUCTION_REPLICATES}, failures=[],
            )
        elif mutation == "benign_insufficient_complete_prompts":
            payload = copy.deepcopy(success_data["benign_broken"])
            payload["complete_prompt_frame"] = payload["complete_prompt_frame"][:1]
            payload["prompts"] = payload["prompts"][:1]
            call = lambda payload=payload: analyze_benign_broken(payload, fixture_mode=True)
        elif mutation == "benign_incomplete_vector_set":
            payload = copy.deepcopy(success_data["benign_broken"])
            payload["prompts"][0]["steered"].pop()
            call = lambda payload=payload: analyze_benign_broken(payload, fixture_mode=True)
        elif mutation == "benign_duplicate_response_identity":
            payload = copy.deepcopy(success_data["benign_broken"])
            payload["prompts"][0]["steered"][0]["response_id"] = payload["prompts"][0]["clean"]["response_id"]
            call = lambda payload=payload: analyze_benign_broken(payload, fixture_mode=True)
        elif mutation == "rng_member_id_forbidden":
            call = lambda: sync_unit_id(
                family="k1-profile", axis="prompt", frame_hash="00" * 32,
                member_id="P2_A_all",
            )
        elif mutation == "rng_replicate_zero":
            unit_id = sync_unit_id(
                family="harmful-clean", axis="prompt", frame_hash="11" * 32
            )
            call = lambda unit_id=unit_id: seed_bytes(HARMFUL_CLEAN_BLOCK_ID, unit_id, 0)
        elif mutation == "rng_wrong_block_family":
            unit_id = sync_unit_id(
                family="k1-profile", axis="prompt", frame_hash="22" * 32
            )
            call = lambda unit_id=unit_id: seed_bytes(BENIGN_BROKEN_BLOCK_ID, unit_id, 1)
        else:
            raise ValueError(f"unknown failure mutation: {mutation}")
        results.append({"case_id": case["case_id"], **_captured_failure(call)})
    return {
        "fixture_schema": "paper1-stage3-retained-bootstrap-failure-v1",
        "synthetic_data": True,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--block", choices=("k1", "harmful_clean", "benign_broken"), required=True)
    parser.add_argument("--synthetic-fixture", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    analyzers = {
        "k1": analyze_k1,
        "harmful_clean": analyze_harmful_clean,
        "benign_broken": analyze_benign_broken,
    }
    result = analyzers[args.block](payload, fixture_mode=args.synthetic_fixture)
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
