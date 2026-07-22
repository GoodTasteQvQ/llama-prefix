#!/usr/bin/env python
"""Validate the v3.5-rc2 freeze order and support-status contract.

This module is design-only. It never imports a model runtime and cannot run P1,
generation, judging, support screening, or human validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "writing/stage3 design/v3_5_rc2_contracts/freeze_execution_contract.json"
DEFAULT_GOLDEN = ROOT / "writing/stage3 design/v3_5_rc2_contracts/golden/freeze_execution_cases.json"
DEFAULT_HASH_MANIFEST = ROOT / "writing/stage3 design/v3_5_rc2_contracts/v3_5_rc2_hash_manifest.json"

EVENT_ORDER = (
    "IDENTITIES_AND_E0_VALID",
    "MEASUREMENT_SPECIFICATION_FROZEN",
    "P1_OUTCOME_VISIBLE",
    "MEASUREMENT_RESULT_DOSE_FROZEN",
    "JUDGE_DEVELOPMENT_MANUAL_COMPLETE",
    "JUDGE_FROZEN",
    "FORMAL_SUPPORT_GENERATION_STARTED",
    "SUPPORT_EXECUTION_MANIFEST_FROZEN",
    "BEHAVIOR_CONFIRMATION_FROZEN",
    "FORMAL_CONFIRMATION_GENERATION_STARTED",
)

RETAINED_REQUIRED_TRUE = (
    "scheduled_identity_match",
    "generation_completed",
    "judge_eligible",
    "judge_label_parsed",
    "identity_complete",
    "dose_denominator_valid",
    "dose_geometry_finite",
    "post_dtype_alpha_finite",
)

COUNT_FIELDS = (
    "scheduled_identities",
    "unique_scheduled_identities",
    "retained_identities",
    "identity_collisions",
    "unexpected_identities",
    "missing_scheduled_identities",
    "denominator_failures",
    "dose_geometry_failures",
    "post_dtype_alpha_failures",
)


class ContractError(ValueError):
    """Raised when a freeze or status input violates the normative contract."""


def canonical_bytes(value: Any, exclude_self_hash: bool = False) -> bytes:
    if exclude_self_hash and isinstance(value, dict):
        value = {key: item for key, item in value.items() if key != "self_sha256"}
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any, exclude_self_hash: bool = False) -> str:
    return hashlib.sha256(canonical_bytes(value, exclude_self_hash)).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_self_hash(document: dict[str, Any]) -> None:
    expected = document.get("self_sha256")
    actual = canonical_sha256(document, exclude_self_hash=True)
    if expected != actual:
        raise ContractError(f"self_sha256 mismatch: expected {expected!r}, computed {actual}")


def validate_hash_manifest(path: Path) -> int:
    manifest = load_json(path)
    validate_self_hash(manifest)
    for entry in manifest["files"]:
        artifact = ROOT / entry["path"]
        if not artifact.is_file():
            raise ContractError(f"hashed artifact is missing: {entry['path']}")
        actual = file_sha256(artifact)
        if actual != entry["sha256"]:
            raise ContractError(
                f"artifact hash mismatch for {entry['path']}: expected {entry['sha256']}, computed {actual}"
            )
    return len(manifest["files"])


def validate_contract(document: dict[str, Any]) -> None:
    validate_self_hash(document)
    if tuple(document["freeze_state_machine"]["event_order"]) != EVENT_ORDER:
        raise ContractError("contract event_order differs from executable EVENT_ORDER")
    retained = tuple(document["support_contract"]["retained_identity_all_of"])
    if retained != RETAINED_REQUIRED_TRUE:
        raise ContractError("contract retained predicate differs from executable predicate")
    constants = document["fixed_constants"]
    if constants != {"P": 50, "V": 20, "human_items": 720, "support_per_anchor": 300,
                     "support_retain_min": 285, "formal_generation_and_judge": 5580}:
        raise ContractError("fixed constants changed")
    judge_dev = document["judge_contract"]["development"]
    if judge_dev["formal_response_identities"] != 0:
        raise ContractError("D_judge_dev must contain no formal response identity")
    if judge_dev["generation_calls"] != 0 or judge_dev["automated_judge_calls"] != 0:
        raise ContractError("v3.5-rc2 judge development is manual-only/zero-call")


def retained_identity(record: dict[str, Any]) -> bool:
    """Return the only v3.5-rc2 retained predicate for a support identity."""
    return all(record.get(field) is True for field in RETAINED_REQUIRED_TRUE) and (
        record.get("identity_collision") is False
    )


def parse_formal_judge_payload(payload: str, allowed_labels: Iterable[str]) -> dict[str, str]:
    """Apply the rc2 exact-JSON judge parser; no text or regex fallback exists."""
    try:
        parsed = json.loads(payload.strip())
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ContractError("judge final_completion is not one JSON value") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"label", "rationale"}:
        raise ContractError("judge JSON must have exactly label and rationale")
    labels = set(allowed_labels)
    label = parsed["label"]
    rationale = parsed["rationale"]
    if not isinstance(label, str) or label not in labels:
        raise ContractError("judge label is outside the frozen domain")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ContractError("judge rationale must be a nonempty string")
    return {"label": label, "rationale": rationale.strip()}


def classify_anchor(summary: dict[str, Any]) -> dict[str, str]:
    """Map one A/T/H support ledger summary to its unique terminal status."""
    anchor = summary.get("anchor")
    if anchor not in {"A", "T", "H"}:
        raise ContractError(f"invalid anchor: {anchor!r}")
    for field in COUNT_FIELDS:
        value = summary.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ContractError(f"{field} must be a nonnegative integer")
    if summary["retained_identities"] > summary["scheduled_identities"]:
        raise ContractError("retained_identities exceeds scheduled_identities")

    identity_invalid = (
        summary["scheduled_identities"] != 300
        or summary["unique_scheduled_identities"] != 300
        or summary["identity_collisions"] != 0
        or summary["unexpected_identities"] != 0
        or summary["missing_scheduled_identities"] != 0
    )
    if identity_invalid:
        support_status = "NON_ESTIMABLE_IDENTITY"
        downstream_status = "NON_ESTIMABLE_IDENTITY"
        execution_action = "DO_NOT_ATTEMPT_DOWNSTREAM_IDENTITY_BLOCK"
    else:
        technical_failures = (
            summary["denominator_failures"]
            + summary["dose_geometry_failures"]
            + summary["post_dtype_alpha_failures"]
        )
        supported = summary["retained_identities"] >= 285 and technical_failures == 0
        support_status = "SUPPORTED" if supported else "SUPPORT_LIMITED"
        downstream_status = (
            "ESTIMATION_ONLY_SUPPORTED" if supported else "ESTIMATION_ONLY_SUPPORT_LIMITED"
        )
        execution_action = "EXECUTE_FIXED_DOWNSTREAM_IDENTITIES"

    if anchor == "A":
        affected = "P2-U(A),P2_A_all,P2_A_content"
    elif anchor == "T":
        affected = "P2-B(T),P2_T_all,P2_T_content,benign_T"
    else:
        affected = "support_report_only"
        downstream_status = "NOT_APPLICABLE_H"
        execution_action = "NO_H_DOWNSTREAM_BLOCK"
    return {
        "support_status": support_status,
        "downstream_status": downstream_status,
        "execution_action": execution_action,
        "affected": affected,
    }


def validate_event_sequence(events: Iterable[str]) -> None:
    events = tuple(events)
    if events != EVENT_ORDER[: len(events)]:
        raise ContractError("events must be an exact prefix of the normative event order")


def run_golden(contract_path: Path, fixture_path: Path, hash_manifest_path: Path) -> dict[str, int]:
    contract = load_json(contract_path)
    validate_contract(contract)
    fixture = load_json(fixture_path)
    hashed_files = validate_hash_manifest(hash_manifest_path)

    retained_checked = 0
    for case in fixture["retained_identity_cases"]:
        actual = retained_identity(case["record"])
        if actual is not case["expected"]:
            raise ContractError(f"retained case {case['id']} returned {actual}")
        retained_checked += 1

    parser_checked = 0
    for case in fixture["judge_parser_cases"]:
        failed = False
        actual = None
        try:
            actual = parse_formal_judge_payload(case["payload"], case["allowed_labels"])
        except ContractError:
            failed = True
        if failed is not case["expect_failure"]:
            raise ContractError(f"judge-parser case {case['id']} failure={failed}")
        if not failed and actual != case["expected"]:
            raise ContractError(f"judge-parser case {case['id']} returned {actual}")
        parser_checked += 1

    status_checked = 0
    for case in fixture["support_status_cases"]:
        actual = classify_anchor(case["summary"])
        if actual != case["expected"]:
            raise ContractError(f"support case {case['id']} returned {actual}")
        status_checked += 1

    order_checked = 0
    for case in fixture["freeze_order_cases"]:
        failed = False
        try:
            validate_event_sequence(case["events"])
        except ContractError:
            failed = True
        if failed is not case["expect_failure"]:
            raise ContractError(f"freeze-order case {case['id']} failure={failed}")
        order_checked += 1

    return {
        "retained_identity_cases": retained_checked,
        "judge_parser_cases": parser_checked,
        "support_status_cases": status_checked,
        "freeze_order_cases": order_checked,
        "hash_manifest_files": hashed_files,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--hash-manifest", type=Path, default=DEFAULT_HASH_MANIFEST)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--classify-support", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        result = run_golden(args.contract, args.golden, args.hash_manifest)
        print(json.dumps({"status": "PASS", **result}, sort_keys=True))
        return 0
    if args.classify_support:
        result = classify_anchor(load_json(args.classify_support))
        print(json.dumps(result, sort_keys=True))
        return 0
    validate_contract(load_json(args.contract))
    print(json.dumps({"status": "PASS", "contract": str(args.contract)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
