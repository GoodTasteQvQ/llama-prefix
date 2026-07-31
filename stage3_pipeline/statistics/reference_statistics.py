#!/usr/bin/env python3
"""Current P1 and raw P2 statistical implementation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


IMPLEMENTATION_VERSION = "paper1-stage3-statistics-v1"
RNG_NAMESPACE = "v3.5-rc2"
MASTER_SEED = 42
WEBB_WEIGHTS = (
    -math.sqrt(3.0 / 2.0),
    -1.0,
    -math.sqrt(1.0 / 2.0),
    math.sqrt(1.0 / 2.0),
    1.0,
    math.sqrt(3.0 / 2.0),
)


class NonEstimable(ValueError):
    """Raised when a specified non-estimability condition is met."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sync_unit_id(**fields: str) -> str:
    """Canonical identity shared by family members; member_id is never accepted."""
    if "member_id" in fields or "member" in fields:
        raise ValueError("member identity must not enter sync_unit_id")
    return canonical_json(fields)


def seed_payload(block_id: str, sync_unit_id: str, replicate_index: int) -> bytes:
    if replicate_index < 1:
        raise ValueError("replicate_index must start at 1")
    payload = (
        f"{RNG_NAMESPACE}|master={MASTER_SEED}|block={block_id}"
        f"|sync_unit={sync_unit_id}|rep={replicate_index:06d}"
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()[:16]


class Sha256CounterRng:
    """Version-independent counter RNG used by every reference resample."""

    def __init__(self, seed: bytes):
        if len(seed) != 16:
            raise ValueError("seed must contain exactly 16 bytes")
        self.seed = seed
        self.counter = 0

    def uint64(self) -> int:
        block = hashlib.sha256(
            self.seed + self.counter.to_bytes(8, "big", signed=False)
        ).digest()
        self.counter += 1
        return int.from_bytes(block[:8], "big", signed=False)

    def randbelow(self, upper: int) -> int:
        if upper <= 0:
            raise ValueError("upper must be positive")
        limit = (1 << 64) - ((1 << 64) % upper)
        while True:
            value = self.uint64()
            if value < limit:
                return value % upper


def nearest_rank(values: Iterable[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise NonEstimable("quantile_empty")
    if not 0.0 < probability <= 1.0:
        raise ValueError("nearest-rank probability must be in (0,1]")
    if not all(math.isfinite(value) for value in ordered):
        raise NonEstimable("quantile_nonfinite")
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def sample_sd(values: Iterable[float]) -> float:
    items = list(values)
    if len(items) < 2 or not all(math.isfinite(value) for value in items):
        raise NonEstimable("sd_requires_two_finite_values")
    mean = math.fsum(items) / len(items)
    variance = math.fsum((value - mean) ** 2 for value in items) / (len(items) - 1)
    return math.sqrt(max(0.0, variance))


def _p1_functionals(
    strata: dict[str, list[dict[str, Any]]], *, validate_unique_ids: bool = False
) -> dict[str, float]:
    required = ("harmful", "benign")
    if tuple(sorted(strata)) != tuple(sorted(required)):
        raise NonEstimable("p1_strata_must_be_harmful_and_benign")

    totals: dict[str, dict[str, float]] = {}
    for stratum in required:
        rows = strata[stratum]
        if not rows:
            raise NonEstimable(f"p1_empty_stratum:{stratum}")
        ids = [str(row["prompt_id"]) for row in rows]
        if validate_unique_ids and len(ids) != len(set(ids)):
            raise NonEstimable(f"p1_duplicate_prompt_id:{stratum}")
        for row in rows:
            for field in ("v_sum", "c_sum"):
                if not math.isfinite(float(row[field])) or float(row[field]) < 0.0:
                    raise NonEstimable(f"p1_invalid_{field}:{stratum}")
            for field in ("v_count", "c_count"):
                if int(row[field]) != row[field] or int(row[field]) <= 0:
                    raise NonEstimable(f"p1_invalid_{field}:{stratum}")
        totals[stratum] = {
            "v_sum": math.fsum(float(row["v_sum"]) for row in rows),
            "c_sum": math.fsum(float(row["c_sum"]) for row in rows),
            "v_count": float(sum(int(row["v_count"]) for row in rows)),
            "c_count": float(sum(int(row["c_count"]) for row in rows)),
        }

    v_sum = math.fsum(totals[s]["v_sum"] for s in required)
    c_sum = math.fsum(totals[s]["c_sum"] for s in required)
    v_count = math.fsum(totals[s]["v_count"] for s in required)
    c_count = math.fsum(totals[s]["c_count"] for s in required)
    mu_v = v_sum / v_count
    mu_c = c_sum / c_count
    if mu_c <= 0.0:
        raise NonEstimable("p1_mu_content_nonpositive")

    stratum_mu_v = {s: totals[s]["v_sum"] / totals[s]["v_count"] for s in required}
    stratum_mu_c = {s: totals[s]["c_sum"] / totals[s]["c_count"] for s in required}
    equal_v = 0.5 * (stratum_mu_v["harmful"] + stratum_mu_v["benign"])
    equal_c = 0.5 * (stratum_mu_c["harmful"] + stratum_mu_c["benign"])
    if equal_c <= 0.0:
        raise NonEstimable("p1_equal_domain_mu_content_nonpositive")

    result = {
        "mu_all_tw": mu_v,
        "mu_content_tw": mu_c,
        "delta_select_tw": (mu_v - mu_c) / mu_c,
        "ratio_select_tw": mu_v / mu_c,
        "w_v_harmful": totals["harmful"]["v_count"] / v_count,
        "w_v_benign": totals["benign"]["v_count"] / v_count,
        "w_c_harmful": totals["harmful"]["c_count"] / c_count,
        "w_c_benign": totals["benign"]["c_count"] / c_count,
        "mu_all_tw_equal_domain": equal_v,
        "mu_content_tw_equal_domain": equal_c,
        "delta_select_tw_equal_domain": (equal_v - equal_c) / equal_c,
    }
    if not all(math.isfinite(value) for value in result.values()):
        raise NonEstimable("p1_point_nonfinite")
    return result


def p1_interval(
    strata: dict[str, list[dict[str, Any]]],
    replicates: int = 10_000,
    min_success: int | None = None,
) -> dict[str, Any]:
    if replicates < 2:
        raise ValueError("replicates must be at least 2")
    if any(len(rows) < 2 for rows in strata.values()):
        raise NonEstimable("p1_each_complete_case_stratum_requires_at_least_two_prompts")
    required_successes = math.ceil(0.95 * replicates) if min_success is None else min_success
    point = _p1_functionals(strata, validate_unique_ids=True)
    draws: dict[str, list[float]] = {name: [] for name in point}
    failures: list[dict[str, Any]] = []

    for replicate in range(1, replicates + 1):
        sampled: dict[str, list[dict[str, Any]]] = {}
        for stratum in ("harmful", "benign"):
            rows = strata[stratum]
            rng = Sha256CounterRng(
                seed_payload(
                    "p1-inference",
                    sync_unit_id(family="p1", resample="stratified-prompt", stratum=stratum),
                    replicate,
                )
            )
            sampled[stratum] = [rows[rng.randbelow(len(rows))] for _ in rows]
        try:
            values = _p1_functionals(sampled)
        except NonEstimable as error:
            failures.append({"replicate": replicate, "reason": str(error)})
            continue
        for name, value in values.items():
            draws[name].append(value)

    successes = len(draws["delta_select_tw"])
    if successes < required_successes:
        raise NonEstimable(
            f"p1_common_successes_below_required:{successes}<{required_successes}"
        )

    intervals: dict[str, Any] = {}
    inferential_names = (
        "delta_select_tw",
        "ratio_select_tw",
        "delta_select_tw_equal_domain",
    )
    for name in inferential_names:
        values = draws[name]
        se = sample_sd(values)
        if se < 1e-8:
            raise NonEstimable(f"p1_bootstrap_se_below_1e-8:{name}")
        intervals[name] = {
            "se": se,
            "two_sided_95": [nearest_rank(values, 0.025), nearest_rank(values, 0.975)],
            "one_sided_95_lower": nearest_rank(values, 0.05),
        }

    return {
        "algorithm": "stratified_prompt_percentile_nearest_rank_v1",
        "replicates_requested": replicates,
        "replicates_successful": successes,
        "replicates_required": required_successes,
        "failures": failures,
        "point": point,
        "intervals": intervals,
        "gate_delta_gt_0_10": intervals["delta_select_tw"]["one_sided_95_lower"] > 0.10,
        "claim_ratio_gt_1_5": intervals["ratio_select_tw"]["one_sided_95_lower"] > 1.5,
    }


def _validate_p2_member(member: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
    records = member["records"]
    if not records:
        raise NonEstimable(f"p2_empty_member:{member['member_id']}")
    pair_ids: list[tuple[str, str]] = []
    differences: list[float] = []
    for record in records:
        pair = (str(record["prompt_id"]), str(record["vector_id"]))
        pair_ids.append(pair)
        difference = float(record["difference"])
        if difference not in (-1.0, 0.0, 1.0):
            raise NonEstimable(f"p2_difference_not_minus1_0_1:{member['member_id']}")
        differences.append(difference)
    if len(pair_ids) != len(set(pair_ids)):
        raise NonEstimable(f"p2_duplicate_pair:{member['member_id']}")
    if len({p for p, _ in pair_ids}) < 2:
        raise NonEstimable(f"p2_fewer_than_two_prompt_clusters:{member['member_id']}")
    if len({v for _, v in pair_ids}) < 2:
        raise NonEstimable(f"p2_fewer_than_two_vector_clusters:{member['member_id']}")
    return records, math.fsum(differences) / len(differences)


def _two_way_cr1_se(records: list[dict[str, Any]], center: float) -> float:
    residuals: list[tuple[str, str, float]] = []
    for record in records:
        residuals.append(
            (
                str(record["prompt_id"]),
                str(record["vector_id"]),
                float(record["difference"]) - center,
            )
        )
    n = len(residuals)
    prompt_ids = sorted({prompt for prompt, _, _ in residuals})
    vector_ids = sorted({vector for _, vector, _ in residuals})
    gp = len(prompt_ids)
    gv = len(vector_ids)
    if n < 2 or gp < 2 or gv < 2:
        raise NonEstimable("p2_two_way_cr1_insufficient_clusters")

    prompt_sums = {
        prompt: math.fsum(r for p, _, r in residuals if p == prompt)
        for prompt in prompt_ids
    }
    vector_sums = {
        vector: math.fsum(r for _, v, r in residuals if v == vector)
        for vector in vector_ids
    }
    meat_prompt = (gp / (gp - 1)) * math.fsum(value * value for value in prompt_sums.values())
    meat_vector = (gv / (gv - 1)) * math.fsum(value * value for value in vector_sums.values())
    meat_intersection = (n / (n - 1)) * math.fsum(r * r for _, _, r in residuals)
    variance = (meat_prompt + meat_vector - meat_intersection) / (n * n)
    if not math.isfinite(variance) or variance <= 0.0:
        raise NonEstimable("p2_two_way_cr1_variance_nonpositive_or_nonfinite")
    se = math.sqrt(variance)
    if not math.isfinite(se) or se < 1e-8:
        raise NonEstimable("p2_two_way_cr1_se_below_1e-8_or_nonfinite")
    return se


def _webb_weight(axis: str, entity_id: str, replicate: int) -> float:
    unit_id = sync_unit_id(family="p2-raw", axis=axis, entity_id=entity_id)
    rng = Sha256CounterRng(seed_payload("p2-raw-simultaneous", unit_id, replicate))
    return WEBB_WEIGHTS[rng.randbelow(6)]


def p2_raw_simultaneous(
    members: list[dict[str, Any]],
    replicates: int = 9_999,
    min_success: int | None = None,
) -> dict[str, Any]:
    expected_order = ["P2-U(A)", "P2-B(T)"]
    if [member.get("member_id") for member in members] != expected_order:
        raise NonEstimable("p2_member_order_must_be_P2-U(A)_then_P2-B(T)")
    if replicates < 2:
        raise ValueError("replicates must be at least 2")
    required_successes = math.ceil(0.95 * replicates) if min_success is None else min_success

    prepared: dict[str, dict[str, Any]] = {}
    for member in members:
        records, point = _validate_p2_member(member)
        prepared[member["member_id"]] = {
            "records": records,
            "point": point,
            "se": _two_way_cr1_se(records, point),
        }

    maxima: list[float] = []
    failures: list[dict[str, Any]] = []
    for replicate in range(1, replicates + 1):
        statistics: list[float] = []
        try:
            for member_id in expected_order:
                item = prepared[member_id]
                terms = []
                for record in item["records"]:
                    prompt_id = str(record["prompt_id"])
                    vector_id = str(record["vector_id"])
                    wp = _webb_weight("prompt", prompt_id, replicate)
                    wv = _webb_weight("vector", vector_id, replicate)
                    multiplier = wp + wv - (wp * wv)
                    residual = float(record["difference"]) - item["point"]
                    terms.append(residual * multiplier)
                centered_star = math.fsum(terms) / len(terms)
                statistic = centered_star / item["se"]
                if not math.isfinite(statistic):
                    raise NonEstimable(f"p2_replicate_statistic_nonfinite:{member_id}")
                statistics.append(statistic)
            maxima.append(max(abs(value) for value in statistics))
        except NonEstimable as error:
            failures.append({"replicate": replicate, "reason": str(error)})

    if len(maxima) < required_successes:
        raise NonEstimable(
            f"p2_joint_successes_below_required:{len(maxima)}<{required_successes}"
        )
    critical = nearest_rank(maxima, 0.95)
    intervals = {}
    for member_id in expected_order:
        item = prepared[member_id]
        half_width = critical * item["se"]
        lower = item["point"] - half_width
        upper = item["point"] + half_width
        if not all(math.isfinite(value) for value in (lower, upper)):
            raise NonEstimable(f"p2_interval_nonfinite:{member_id}")
        intervals[member_id] = {
            "point": item["point"],
            "se": item["se"],
            "simultaneous_95": [lower, upper],
        }

    return {
        "algorithm": "two_way_webb_fixed_scale_max_abs_v1",
        "member_order": expected_order,
        "replicates_requested": replicates,
        "replicates_successful": len(maxima),
        "replicates_required": required_successes,
        "failures": failures,
        "critical_value_nearest_rank_0_95": critical,
        "intervals": intervals,
    }


def rng_identity_fixture(spec: dict[str, Any]) -> dict[str, Any]:
    seeds = []
    weights = []
    for item in spec["cases"]:
        unit_id = sync_unit_id(**item["sync_fields"])
        seed = seed_payload(item["block_id"], unit_id, item["replicate"])
        seeds.append(seed.hex())
        rng = Sha256CounterRng(seed)
        weights.append(WEBB_WEIGHTS[rng.randbelow(6)])
    return {"seed_hex": seeds, "first_webb_weight": weights}


def evaluate_fixture(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_schema": "paper1-stage3-statistical-golden-v1",
        "rng_identity": rng_identity_fixture(data["rng_identity"]),
        "p1": p1_interval(
            data["p1"]["strata"],
            replicates=data["p1"]["replicates"],
            min_success=data["p1"]["min_success"],
        ),
        "p2": p2_raw_simultaneous(
            data["p2"]["members"],
            replicates=data["p2"]["replicates"],
            min_success=data["p2"]["min_success"],
        ),
    }


def evaluate_failure_fixture(base: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    results = []
    for case in spec["cases"]:
        data = copy.deepcopy(base)
        mutation = case["mutation"]
        try:
            if mutation == "p1_truncate_one_per_stratum":
                strata = {name: rows[:1] for name, rows in data["p1"]["strata"].items()}
                p1_interval(strata, replicates=20, min_success=19)
            elif mutation == "p1_make_all_rows_constant":
                for rows in data["p1"]["strata"].values():
                    for row in rows:
                        row.update({"v_sum": 2.0, "v_count": 1, "c_sum": 1.0, "c_count": 1})
                p1_interval(data["p1"]["strata"], replicates=20, min_success=19)
            elif mutation == "p2_duplicate_first_pair":
                records = data["p2"]["members"][0]["records"]
                records[1]["prompt_id"] = records[0]["prompt_id"]
                records[1]["vector_id"] = records[0]["vector_id"]
                p2_raw_simultaneous(data["p2"]["members"], replicates=20, min_success=19)
            elif mutation == "p2_reverse_member_order":
                p2_raw_simultaneous(list(reversed(data["p2"]["members"])), replicates=20, min_success=19)
            elif mutation == "p2_make_all_differences_zero":
                for member in data["p2"]["members"]:
                    for record in member["records"]:
                        record["difference"] = 0
                p2_raw_simultaneous(data["p2"]["members"], replicates=20, min_success=19)
            else:
                raise ValueError(f"unknown fixture mutation: {mutation}")
        except NonEstimable as error:
            results.append(
                {"case_id": case["case_id"], "reason": str(error), "status": "NON_ESTIMABLE"}
            )
        else:
            results.append({"case_id": case["case_id"], "reason": None, "status": "UNEXPECTED_PASS"})
    return {"fixture_schema": "paper1-stage3-statistical-failure-v1", "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = evaluate_fixture(data)
    rendered = json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
