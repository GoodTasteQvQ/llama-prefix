#!/usr/bin/env python3
"""Deterministic fixed-720 allocator for the Stage 3 v3.5-rc2 freeze.

This module is a design reference implementation. It never reads model outputs or
human labels. The eligible records passed to it must already contain frozen judge
predictions and matched-frame membership, both of which are known before gold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


VERSION = "v3.5-rc2"
DEFAULT_N = 720
DEFAULT_SEED = 42
P2_CELLS = ("P2_A_all", "P2_A_content", "P2_T_all", "P2_T_content")
QUOTA_CLASSES = ("broken", "unsafe", "refusal", "safe_helpful")
CLASS_WEIGHTS = {
    "broken": 3,
    "unsafe": 3,
    "refusal": 2,
    "safe_helpful": 2,
}
CELL_TO_MEMBER = {
    "P2_A_all": "P2-U(A)",
    "P2_A_content": "P2-U(A)",
    "P2_T_all": "P2-B(T)",
    "P2_T_content": "P2-B(T)",
}


class AllocationError(ValueError):
    """Raised when a frozen sample frame violates the allocator schema."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def quota_class(predicted_class: str) -> str:
    if predicted_class in ("safe", "helpful", "safe_helpful"):
        return "safe_helpful"
    if predicted_class not in QUOTA_CLASSES:
        raise AllocationError(f"unsupported predicted_class: {predicted_class!r}")
    return predicted_class


def stratum_key(record: Mapping[str, Any]) -> str:
    block = str(record["block"])
    logical_cell = str(record.get("logical_cell", "NA"))
    matched = bool(record.get("matched", False))
    qclass = quota_class(str(record["predicted_class"]))
    if block == "P2" and matched:
        if logical_cell not in P2_CELLS:
            raise AllocationError(f"invalid matched P2 logical_cell: {logical_cell!r}")
        return f"C|{logical_cell}|{qclass}"
    if block == "P2" and logical_cell not in P2_CELLS:
        raise AllocationError(f"invalid P2 logical_cell: {logical_cell!r}")
    match_tag = "matched" if matched else "unmatched"
    return f"N|{block}|{logical_cell}|{match_tag}|{qclass}"


def _fractional_part(value: Fraction) -> Fraction:
    return value - value.numerator // value.denominator


def capped_hamilton(
    total: int,
    capacities: Mapping[str, int],
    weights: Mapping[str, int],
) -> dict[str, int]:
    """Allocate an integer total proportionally with caps and lexical tie breaks."""
    keys = sorted(capacities)
    if total < 0:
        raise AllocationError("Hamilton total must be nonnegative")
    if any(capacities[k] < 0 for k in keys):
        raise AllocationError("Hamilton capacities must be nonnegative")
    if total > sum(capacities.values()):
        raise AllocationError("Hamilton total exceeds aggregate capacity")
    if any(weights.get(k, 0) < 0 for k in keys):
        raise AllocationError("Hamilton weights must be nonnegative")

    allocation = {k: 0 for k in keys}
    remaining = total
    while remaining:
        eligible = [k for k in keys if allocation[k] < capacities[k]]
        if not eligible:
            raise AllocationError("Hamilton allocation exhausted capacity")
        weight_sum = sum(weights.get(k, 0) for k in eligible)
        round_weights = (
            {k: weights.get(k, 0) for k in eligible}
            if weight_sum > 0
            else {k: 1 for k in eligible}
        )
        weight_sum = sum(round_weights.values())
        exact = {k: Fraction(remaining * round_weights[k], weight_sum) for k in eligible}

        placed = 0
        for key in eligible:
            floor_share = exact[key].numerator // exact[key].denominator
            add = min(capacities[key] - allocation[key], floor_share)
            allocation[key] += add
            placed += add
        remaining -= placed
        if not remaining:
            break

        ranked = sorted(
            (k for k in eligible if allocation[k] < capacities[k]),
            key=lambda k: (-_fractional_part(exact[k]), k),
        )
        for key in ranked:
            if not remaining:
                break
            allocation[key] += 1
            remaining -= 1

    return allocation


def _validate_records(records: Sequence[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    for record in records:
        missing = {"response_id", "block", "predicted_class"} - set(record)
        if missing:
            raise AllocationError(f"record missing keys: {sorted(missing)}")
        response_id = str(record["response_id"])
        if not response_id:
            raise AllocationError("response_id must be nonempty")
        if response_id in seen:
            raise AllocationError(f"duplicate response_id: {response_id}")
        seen.add(response_id)
        stratum_key(record)


def _hash_rank(master_seed: int, key: str, response_id: str) -> tuple[str, str]:
    payload = (
        f"{VERSION}|master={master_seed}|block=human-fixed720"
        f"|stratum={key}|response={response_id}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), response_id


def _critical_base(capacities: Mapping[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    base = {key: 0 for key in capacities}
    shortfalls: dict[str, int] = {}
    for cell in P2_CELLS:
        cell_keys = sorted(k for k in capacities if k.startswith(f"C|{cell}|"))
        cell_capacity = sum(capacities[k] for k in cell_keys)
        floor_target = min(30, cell_capacity)
        if cell_capacity < 30:
            shortfalls[cell] = 30 - cell_capacity
        for key in cell_keys:
            if capacities[key] > 0:
                base[key] = 1
        remaining = floor_target - sum(base[k] for k in cell_keys)
        if remaining > 0:
            residual_capacity = {k: capacities[k] - base[k] for k in cell_keys}
            extra = capped_hamilton(remaining, residual_capacity, residual_capacity)
            for key, value in extra.items():
                base[key] += value
    return base, shortfalls


def _nominal_class_targets(n_total: int) -> dict[str, int]:
    capacities = {key: n_total for key in QUOTA_CLASSES}
    weights = {key: CLASS_WEIGHTS[key] for key in QUOTA_CLASSES}
    return capped_hamilton(n_total, capacities, weights)


def allocate_human_sample(
    records: Sequence[Mapping[str, Any]],
    n_total: int = DEFAULT_N,
    master_seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Return a deterministic quota trace and selected response identities."""
    if n_total != DEFAULT_N:
        raise AllocationError(f"v3.5-rc2 fixes n_total={DEFAULT_N}")
    if master_seed != DEFAULT_SEED:
        raise AllocationError(f"v3.5-rc2 fixes master_seed={DEFAULT_SEED}")
    _validate_records(records)

    by_stratum: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    stratum_class: dict[str, str] = {}
    for record in records:
        key = stratum_key(record)
        by_stratum[key].append(record)
        stratum_class[key] = quota_class(str(record["predicted_class"]))
    capacities = {key: len(rows) for key, rows in sorted(by_stratum.items())}
    eligible_count = len(records)
    nominal_targets = _nominal_class_targets(n_total)

    if eligible_count < n_total:
        quotas = dict(capacities)
        selected_ids = sorted(str(record["response_id"]) for record in records)
        member_status = {
            "P2-U(A)": "non_estimable_fixed720_capacity",
            "P2-B(T)": "non_estimable_fixed720_capacity",
        }
        trace = {
            "allocator_version": VERSION,
            "master_seed": master_seed,
            "requested_n": n_total,
            "eligible_n": eligible_count,
            "selected_n": eligible_count,
            "fixed720_status": "incomplete_capacity",
            "nominal_class_targets": nominal_targets,
            "final_class_quotas": dict(sorted(Counter(
                stratum_class[k] for k, count in quotas.items() for _ in range(count)
            ).items())),
            "critical_cell_floor_shortfalls": {
                cell: max(0, 30 - sum(
                    count for key, count in capacities.items() if key.startswith(f"C|{cell}|")
                ))
                for cell in P2_CELLS
                if sum(count for key, count in capacities.items() if key.startswith(f"C|{cell}|")) < 30
            },
            "member_quota_status": member_status,
            "stratum_capacities": capacities,
            "stratum_quotas": quotas,
            "selected_response_ids": selected_ids,
        }
        trace["selected_ids_sha256"] = hashlib.sha256(
            ("\n".join(selected_ids) + "\n").encode("utf-8")
        ).hexdigest()
        trace["trace_sha256"] = sha256_json({k: v for k, v in trace.items() if k != "trace_sha256"})
        return trace

    base, shortfalls = _critical_base(capacities)
    class_capacity = {
        qclass: sum(capacities[k] for k in capacities if stratum_class[k] == qclass)
        for qclass in QUOTA_CLASSES
    }
    class_base = {
        qclass: sum(base[k] for k in base if stratum_class[k] == qclass)
        for qclass in QUOTA_CLASSES
    }
    class_quota = {
        qclass: max(class_base[qclass], min(nominal_targets[qclass], class_capacity[qclass]))
        for qclass in QUOTA_CLASSES
    }
    class_remaining = n_total - sum(class_quota.values())
    if class_remaining:
        class_spare = {
            qclass: class_capacity[qclass] - class_quota[qclass]
            for qclass in QUOTA_CLASSES
        }
        class_extra = capped_hamilton(class_remaining, class_spare, CLASS_WEIGHTS)
        for qclass, value in class_extra.items():
            class_quota[qclass] += value

    quotas = dict(base)
    for qclass in QUOTA_CLASSES:
        keys = sorted(k for k in capacities if stratum_class[k] == qclass)
        residual_capacity = {k: capacities[k] - quotas[k] for k in keys}
        remaining = class_quota[qclass] - sum(quotas[k] for k in keys)
        extra = capped_hamilton(remaining, residual_capacity, residual_capacity)
        for key, value in extra.items():
            quotas[key] += value

    if sum(quotas.values()) != n_total:
        raise AllocationError("internal error: quotas do not sum to fixed720")
    if any(quotas[k] > capacities[k] for k in quotas):
        raise AllocationError("internal error: quota exceeds capacity")

    selected_ids: list[str] = []
    for key in sorted(by_stratum):
        ranked = sorted(
            (str(record["response_id"]) for record in by_stratum[key]),
            key=lambda response_id: _hash_rank(master_seed, key, response_id),
        )
        selected_ids.extend(ranked[: quotas[key]])
    selected_ids.sort()

    member_status = {"P2-U(A)": "quota_complete", "P2-B(T)": "quota_complete"}
    for cell in shortfalls:
        member_status[CELL_TO_MEMBER[cell]] = "non_estimable_matched_cell_capacity"

    trace = {
        "allocator_version": VERSION,
        "master_seed": master_seed,
        "requested_n": n_total,
        "eligible_n": eligible_count,
        "selected_n": len(selected_ids),
        "fixed720_status": "complete",
        "nominal_class_targets": nominal_targets,
        "class_capacities": class_capacity,
        "critical_class_base": class_base,
        "final_class_quotas": class_quota,
        "critical_cell_floor_shortfalls": shortfalls,
        "member_quota_status": member_status,
        "stratum_capacities": capacities,
        "stratum_quotas": dict(sorted(quotas.items())),
        "selected_response_ids": selected_ids,
    }
    trace["selected_ids_sha256"] = hashlib.sha256(
        ("\n".join(selected_ids) + "\n").encode("utf-8")
    ).hexdigest()
    trace["trace_sha256"] = sha256_json({k: v for k, v in trace.items() if k != "trace_sha256"})
    return trace


def expand_synthetic_strata(case_name: str, specs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for spec_index, spec in enumerate(specs):
        count = int(spec["count"])
        if count < 0:
            raise AllocationError("synthetic stratum count must be nonnegative")
        for row_index in range(count):
            record = {
                "response_id": f"{case_name}|s{spec_index:03d}|r{row_index:05d}",
                "block": spec["block"],
                "predicted_class": spec["predicted_class"],
                "matched": bool(spec.get("matched", False)),
            }
            if "logical_cell" in spec:
                record["logical_cell"] = spec["logical_cell"]
            records.append(record)
    return records


def verify_golden(path: Path) -> None:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        records = expand_synthetic_strata(case["name"], case["strata"])
        actual = allocate_human_sample(records)
        for field, expected in case["expected"].items():
            if actual[field] != expected:
                raise AssertionError(
                    f"{case['name']} field {field}: expected {expected!r}, got {actual[field]!r}"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-golden", type=Path)
    parser.add_argument("--emit", type=Path, help="read a JSON record array and print the trace")
    args = parser.parse_args()
    if bool(args.verify_golden) == bool(args.emit):
        parser.error("provide exactly one of --verify-golden or --emit")
    if args.verify_golden:
        verify_golden(args.verify_golden)
        print(f"PASS {args.verify_golden}")
        return
    records = json.loads(args.emit.read_text(encoding="utf-8"))
    print(json.dumps(allocate_human_sample(records), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
