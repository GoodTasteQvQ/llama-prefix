#!/usr/bin/env python3
"""Matched-frame two-phase corrected RD for the current Stage 3 design.

The caller supplies exactly the two response rows for every pair in one fixed
matched frame M_A or M_T. Rows outside that frame are rejected by construction:
an incomplete pair makes the estimator non-estimable instead of silently changing
the target to an available-arm contrast.
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence


IMPLEMENTATION_VERSION = "paper1-stage3-two-phase-point-v1"
ARMS = ("all", "content")
ANCHORS = ("A", "T")


class CorrectionError(ValueError):
    """Raised when an input cannot identify the fixed matched estimand."""


def _binary(value: Any, field: str) -> int:
    if value not in (0, 1, False, True):
        raise CorrectionError(f"{field} must be binary")
    return int(value)


def _fraction(value: Any, field: str) -> Fraction:
    try:
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise CorrectionError(f"invalid {field}: {value!r}") from exc
    if result <= 0 or result > 1:
        raise CorrectionError(f"{field} must be in (0,1]")
    return result


def _fraction_string(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def estimate_matched_two_phase(
    rows: Sequence[Mapping[str, Any]],
    anchor: str,
) -> dict[str, Any]:
    if anchor not in ANCHORS:
        raise CorrectionError(f"anchor must be one of {ANCHORS}")
    seen_response_ids: set[str] = set()
    pairs: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        missing = {"response_id", "pair_id", "anchor", "arm", "judge", "selected"} - set(row)
        if missing:
            raise CorrectionError(f"row missing keys: {sorted(missing)}")
        response_id = str(row["response_id"])
        pair_id = str(row["pair_id"])
        row_anchor = str(row["anchor"])
        arm = str(row["arm"])
        if row_anchor != anchor:
            raise CorrectionError("rows from another anchor cannot enter the matched frame")
        if arm not in ARMS:
            raise CorrectionError(f"unsupported arm: {arm!r}")
        if not response_id or not pair_id:
            raise CorrectionError("response_id and pair_id must be nonempty")
        if response_id in seen_response_ids:
            raise CorrectionError(f"duplicate response_id: {response_id}")
        seen_response_ids.add(response_id)
        if arm in pairs.setdefault(pair_id, {}):
            raise CorrectionError(f"duplicate {arm} row for pair {pair_id}")
        _binary(row["judge"], "judge")
        if not isinstance(row["selected"], bool):
            raise CorrectionError("selected must be a JSON boolean")
        selected = row["selected"]
        if selected:
            if "gold" not in row or "pi" not in row:
                raise CorrectionError("selected rows require gold and pi")
            _binary(row["gold"], "gold")
            _fraction(row["pi"], "pi")
        elif "gold" in row or "pi" in row:
            raise CorrectionError("unselected rows must not expose gold or pi")
        pairs[pair_id][arm] = row

    if not pairs:
        raise CorrectionError("matched frame is empty")
    incomplete = sorted(pair_id for pair_id, arms in pairs.items() if set(arms) != set(ARMS))
    if incomplete:
        raise CorrectionError(f"incomplete matched pairs: {incomplete}")

    arm_results: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        arm_rows = [pairs[pair_id][arm] for pair_id in sorted(pairs)]
        judge_total = sum(_binary(row["judge"], "judge") for row in arm_rows)
        p_judge = Fraction(judge_total, len(arm_rows))
        selected_rows = [row for row in arm_rows if row["selected"]]
        if not selected_rows:
            raise CorrectionError(f"no phase-two residuals in matched {arm} arm")
        residual_total = Fraction(0)
        weight_total = Fraction(0)
        for row in selected_rows:
            weight = 1 / _fraction(row["pi"], "pi")
            residual = _binary(row["gold"], "gold") - _binary(row["judge"], "judge")
            residual_total += weight * residual
            weight_total += weight
        if weight_total <= 0:
            raise CorrectionError(f"nonpositive matched {arm} residual denominator")
        residual_mean = residual_total / weight_total
        unbounded = p_judge + residual_mean
        corrected = min(Fraction(1), max(Fraction(0), unbounded))
        arm_results[arm] = {
            "matched_pair_n": len(arm_rows),
            "selected_residual_n": len(selected_rows),
            "p_judge_fraction": _fraction_string(p_judge),
            "residual_mean_fraction": _fraction_string(residual_mean),
            "unbounded_fraction": _fraction_string(unbounded),
            "corrected_fraction": _fraction_string(corrected),
            "corrected": float(corrected),
        }

    rd = Fraction(arm_results["all"]["corrected_fraction"]) - Fraction(
        arm_results["content"]["corrected_fraction"]
    )
    return {
        "estimator_version": IMPLEMENTATION_VERSION,
        "estimand_frame": f"M_{anchor}",
        "matched_pair_n": len(pairs),
        "arms": arm_results,
        "rd_fraction": _fraction_string(rd),
        "rd": float(rd),
    }


def verify_golden(path: Path) -> None:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        if "expected_error" in case:
            try:
                estimate_matched_two_phase(case["rows"], case["anchor"])
            except CorrectionError as exc:
                if str(exc) != case["expected_error"]:
                    raise AssertionError(
                        f"{case['name']}: expected error {case['expected_error']!r}, got {str(exc)!r}"
                    ) from exc
            else:
                raise AssertionError(f"{case['name']}: expected CorrectionError")
            continue
        actual = estimate_matched_two_phase(case["rows"], case["anchor"])
        if actual != case["expected"]:
            raise AssertionError(f"{case['name']}: expected {case['expected']!r}, got {actual!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-golden", type=Path)
    parser.add_argument("--emit", type=Path, help="read {anchor,rows} JSON and print the estimate")
    args = parser.parse_args()
    if bool(args.verify_golden) == bool(args.emit):
        parser.error("provide exactly one of --verify-golden or --emit")
    if args.verify_golden:
        verify_golden(args.verify_golden)
        print(f"PASS {args.verify_golden}")
        return
    payload = json.loads(args.emit.read_text(encoding="utf-8"))
    print(json.dumps(estimate_matched_two_phase(payload["rows"], payload["anchor"]), indent=2))


if __name__ == "__main__":
    main()
