#!/usr/bin/env python3
"""Verify amendment-01 two-phase hashes and execute all synthetic goldens."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
CODE_DIR = Path(__file__).resolve().parent
WRITING_DIR = ROOT / "writing/stage3 design/v3_5_rc2_binding_amendment_01/two_phase"
MANIFEST_PATH = WRITING_DIR / "two_phase_binding_manifest.json"
SCHEMA_PATH = WRITING_DIR / "two_phase_input.schema.json"
SUCCESS_INPUT = WRITING_DIR / "fixtures/success_input.json"
SUCCESS_EXPECTED = WRITING_DIR / "fixtures/success_expected.json"
FAILURE_INPUT = WRITING_DIR / "fixtures/failure_input.json"
FAILURE_EXPECTED = WRITING_DIR / "fixtures/failure_expected.json"
SCHEMA_NEGATIVE_INPUT = WRITING_DIR / "fixtures/schema_negative_input.json"

sys.path.insert(0, str(CODE_DIR))
import two_phase_reference as reference  # noqa: E402


class VerificationError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any, *, exclude_self: bool = False) -> bytes:
    if exclude_self and isinstance(value, dict):
        value = {key: item for key, item in value.items() if key != "self_sha256"}
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def verify_manifest() -> int:
    manifest = load_json(MANIFEST_PATH)
    if manifest.get("amendment_id") != "v3.5-rc2-binding-amendment-01":
        raise VerificationError("amendment_id mismatch")
    if manifest.get("status") != "DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED":
        raise VerificationError("forbidden or missing component status")
    if manifest.get("formal_data_used") is not False or manifest.get("no_scope_expansion") is not True:
        raise VerificationError("scope/data declaration mismatch")
    expected_self = manifest.get("self_sha256")
    actual_self = hashlib.sha256(canonical_bytes(manifest, exclude_self=True)).hexdigest()
    if expected_self != actual_self:
        raise VerificationError(f"manifest self hash mismatch: {actual_self}")
    for artifact in manifest["artifacts"]:
        path = ROOT / artifact["path"]
        if not path.is_file():
            raise VerificationError(f"missing artifact: {artifact['path']}")
        if path.stat().st_size != artifact["length"]:
            raise VerificationError(f"length mismatch: {artifact['path']}")
        if file_sha256(path) != artifact["sha256"]:
            raise VerificationError(f"hash mismatch: {artifact['path']}")
    for dependency in manifest["transitive_dependencies"]:
        path = ROOT / dependency["path"]
        if not path.is_file() or file_sha256(path) != dependency["sha256"]:
            raise VerificationError(f"transitive dependency mismatch: {dependency['path']}")
    return len(manifest["artifacts"])


def verify_schema_and_frames(success: dict[str, Any]) -> None:
    schema = load_json(SCHEMA_PATH)
    if schema["$id"] != "urn:paper1-stage3:v3.5-rc2:binding-amendment-01:two-phase-input-v1":
        raise VerificationError("schema $id mismatch")
    if schema["properties"]["master_seed"].get("const") != 42:
        raise VerificationError("schema master seed is not fixed to 42")
    vector_schema = schema["$defs"]["vectorFrame"]["properties"]["vector_ids"]
    if vector_schema.get("minItems") != 20 or vector_schema.get("maxItems") != 20:
        raise VerificationError("schema does not fix the vector frame to 20")
    if "phase2_stratum_id" not in schema["$defs"]["row"]["required"]:
        raise VerificationError("schema does not assign every row to a phase-two stratum")
    phase_required = schema["$defs"]["phaseTwoStratum"]["required"]
    if "population_response_ids" not in phase_required or "sampled_response_ids" not in phase_required:
        raise VerificationError("schema does not close phase-two population/sample frames")
    member_schema = schema["properties"]["members"]
    if member_schema.get("prefixItems") != [
        {"$ref": "#/$defs/memberA"},
        {"$ref": "#/$defs/memberT"},
    ] or member_schema.get("items") is not False:
        raise VerificationError("schema does not bind ordered members with prefixItems/items:false")
    payload = success["input"]
    reference.validate_input(payload)
    computed = reference.computed_frame_hashes(payload)
    if computed["prompt_frame_sha256"] != payload["prompt_frame"]["frame_sha256"]:
        raise VerificationError("prompt frame hash is not canonical")
    if computed["vector_frame_sha256"] != payload["vector_frame"]["frame_sha256"]:
        raise VerificationError("vector frame hash is not canonical")
    if computed["phase_two_frame_sha256"] != payload["phase_two_frame"]["frame_sha256"]:
        raise VerificationError("phase-two frame hash is not canonical")
    for member in payload["members"]:
        if computed["member_frame_sha256"][member["member_id"]] != member["frame_sha256"]:
            raise VerificationError(f"member frame hash mismatch: {member['member_id']}")


def verify_prefix_items_behavior(success: dict[str, Any], schema_negative: dict[str, Any]) -> None:
    probe_schema = {
        "type": "array",
        "prefixItems": [{"const": "member-a"}, {"type": "integer"}],
        "items": False,
    }
    reference._validate_schema_node(["member-a", 2], probe_schema, probe_schema, "$.probe")
    probes = [
        (["wrong", 2], "$.probe[0]:const"),
        (["member-a", "wrong"], "$.probe[1]:type"),
        (["member-a", 2, 3], "$.probe:items[2]"),
    ]
    for value, expected_detail in probes:
        try:
            reference._validate_schema_node(value, probe_schema, probe_schema, "$.probe")
        except reference.NonEstimable as error:
            if error.reason_code != "SCHEMA_VALIDATION" or error.detail != expected_detail:
                raise VerificationError(f"prefixItems probe changed: {error}") from error
        else:
            raise VerificationError(f"prefixItems probe unexpectedly passed: {value!r}")

    all_of_schema = {
        "allOf": [
            {"type": "object"},
            {"properties": {"member_id": {"const": "member-a"}}},
        ]
    }
    reference._validate_schema_node(
        {"member_id": "member-a"}, all_of_schema, all_of_schema, "$.allOfProbe"
    )
    try:
        reference._validate_schema_node(
            {"member_id": "member-b"}, all_of_schema, all_of_schema, "$.allOfProbe"
        )
    except reference.NonEstimable as error:
        if error.reason_code != "SCHEMA_VALIDATION" or error.detail != "$.allOfProbe.member_id:const":
            raise VerificationError(f"allOf validation probe changed: {error}") from error
    else:
        raise VerificationError("allOf validation probe unexpectedly passed")
    for invalid_all_of in (None, [], [True]):
        invalid_schema = {"allOf": invalid_all_of}
        try:
            reference._validate_schema_node({}, invalid_schema, invalid_schema, "$.allOfProbe")
        except reference.NonEstimable as error:
            if error.reason_code != "SCHEMA_INVALID" or error.detail != "$.allOfProbe:allOf":
                raise VerificationError(f"invalid allOf did not fail closed: {error}") from error
        else:
            raise VerificationError(f"invalid allOf unexpectedly passed: {invalid_all_of!r}")

    actual = reference.evaluate_schema_negative_fixture(success, schema_negative)
    observed = {
        item["case_id"]: (item["status"], item["reason_code"], item.get("detail"))
        for item in actual["results"]
    }
    expected = {
        "third_member_forbidden": (
            "INPUT_INVALID_NON_ESTIMABLE", "SCHEMA_VALIDATION", "$.members:maxItems"
        ),
        "wrong_member_order": (
            "INPUT_INVALID_NON_ESTIMABLE", "SCHEMA_VALIDATION", "$.members[0].member_id:const"
        ),
        "wrong_member_type": (
            "INPUT_INVALID_NON_ESTIMABLE", "SCHEMA_VALIDATION", "$.members[0]:type"
        ),
    }
    if observed != expected:
        raise VerificationError(f"schema-negative witnesses changed: {observed}")


def verify_contract_surface(success: dict[str, Any], actual: dict[str, Any]) -> None:
    if reference.REPLICATES != 9_999 or reference.COMMON_SUCCESS_REQUIRED != 9_500:
        raise VerificationError("production replicate/completion constants changed")
    if tuple(reference.MEMBER_ORDER) != ("P2-U(A)", "P2-B(T)"):
        raise VerificationError("member order changed")
    if reference.BLOCKS != {
        "prompt": "p2-two-phase-prompt",
        "vector": "p2-two-phase-vector",
    }:
        raise VerificationError("block IDs changed")
    payload = success["input"]
    first_prompt_stratum = payload["prompt_frame"]["strata"][0]["stratum_id"]
    expected_prompt_sync = reference.canonical_json({
        "axis": "prompt-stratum",
        "family": "p2-two-phase-prompt",
        "frame_sha256": payload["prompt_frame"]["frame_sha256"],
        "stratum_id": first_prompt_stratum,
    })
    if reference.prompt_sync_unit(
        "p2-two-phase-prompt", payload["prompt_frame"]["frame_sha256"], first_prompt_stratum
    ) != expected_prompt_sync:
        raise VerificationError("exact prompt sync JSON mismatch")
    expected_phase_sync = reference.canonical_json({
        "axis": "phase2-stratum",
        "family": "p2-two-phase-prompt",
        "frame_sha256": payload["phase_two_frame"]["frame_sha256"],
        "stratum_id": "h-A-all",
    })
    if reference.phase_two_sync_unit(
        "p2-two-phase-prompt", payload["phase_two_frame"]["frame_sha256"], "h-A-all"
    ) != expected_phase_sync:
        raise VerificationError("exact phase-two sync JSON mismatch")
    expected_vector_sync = reference.canonical_json({
        "axis": "vector",
        "entity_id": "V_confirm",
        "family": "p2-two-phase-vector",
        "frame_sha256": payload["vector_frame"]["frame_sha256"],
    })
    if reference.vector_sync_unit(
        "p2-two-phase-vector", payload["vector_frame"]["frame_sha256"], "V_confirm"
    ) != expected_vector_sync:
        raise VerificationError("exact vector sync JSON mismatch")
    try:
        reference.sync_unit_id({"axis": "prompt-stratum", "member_id": "P2-U(A)"})
    except reference.NonEstimable as error:
        if error.reason_code != "MEMBER_ID_IN_SYNC_UNIT":
            raise VerificationError("member sync failure reason changed") from error
    else:
        raise VerificationError("member_id entered a shared stream")

    prompt_order = reference.draw_consumption_order(payload, "p2-two-phase-prompt")
    vector_order = reference.draw_consumption_order(payload, "p2-two-phase-vector")
    if [item["axis"] for item in prompt_order] != [
        "prompt-stratum", "prompt-stratum", "prompt-stratum",
        "phase2-stratum", "phase2-stratum", "phase2-stratum", "phase2-stratum",
    ]:
        raise VerificationError("prompt/phase-two draw order changed")
    if [item["axis"] for item in vector_order] != [item["axis"] for item in prompt_order] + ["vector"]:
        raise VerificationError("vector draw is not last")
    census = next(item for item in prompt_order if item["entity_or_stratum_id"] == "h-A-content")
    if census.get("census") is not True or census["draws_per_replicate"] != 0:
        raise VerificationError("census stratum consumed RNG")
    if vector_order[-1]["draws_per_replicate"] != 20:
        raise VerificationError("vector stream does not consume 20 draws")
    rejection = actual["rng_byte_golden"]["scripted_rejection"]
    if rejection != {
        "upper": 10,
        "limit": 18446744073709551610,
        "word_hex": ["fffffffffffffffa", "ffffffffffffffff", "000000000000007b"],
        "accepted_draw": 3,
        "words_consumed": 3,
        "rejected_word_count": 2,
    }:
        raise VerificationError("scripted rejection consumption changed")
    if actual["completion_boundary"] != {"9499": "FAIL", "9500": "PASS"}:
        raise VerificationError("9,499/9,500 boundary changed")
    if actual["armwise_clipping_point"]["arms"]["all-token"]["clipped"] is not True:
        raise VerificationError("armwise clipping is not exercised")
    if actual["prompt_phase_two"]["block_id"] != "p2-two-phase-prompt":
        raise VerificationError("prompt x phase-two family not executed")
    if actual["vector_aware"]["block_id"] != "p2-two-phase-vector":
        raise VerificationError("vector-aware family not executed")
    if len(actual["vector_aware"]["first_replicate_multiplicity"]["vector"]) != 20:
        raise VerificationError("vector-aware multiplicity does not cover 20 vectors")
    diagnostics = actual["prompt_phase_two"]["positivity_diagnostics"]
    if diagnostics["P2-U(A)"]["kish_ess"] < 20 or diagnostics["P2-B(T)"]["kish_ess"] < 20:
        raise VerificationError("Kish ESS production gate is not enforced")
    if any(item["max_normalized_weight"] > 0.20 for item in diagnostics.values()):
        raise VerificationError("maximum normalized weight production gate is not enforced")


def main() -> int:
    try:
        success = load_json(SUCCESS_INPUT)
        failure = load_json(FAILURE_INPUT)
        schema_negative = load_json(SCHEMA_NEGATIVE_INPUT)
        success_expected = load_json(SUCCESS_EXPECTED)
        failure_expected = load_json(FAILURE_EXPECTED)
        for path, value in (
            (SUCCESS_INPUT, success),
            (SUCCESS_EXPECTED, success_expected),
            (FAILURE_INPUT, failure),
            (FAILURE_EXPECTED, failure_expected),
            (SCHEMA_NEGATIVE_INPUT, schema_negative),
        ):
            if value.get("synthetic_data") is not True:
                raise VerificationError(f"fixture is not boolean-marked synthetic: {path}")
        artifact_count = verify_manifest()
        verify_schema_and_frames(success)
        verify_prefix_items_behavior(success, schema_negative)
        success_actual = reference.evaluate_success_fixture(success)
        if canonical_bytes(success_actual) != canonical_bytes(success_expected):
            raise VerificationError("SUCCESS_GOLDEN_MISMATCH")
        failure_actual = reference.evaluate_failure_fixture(success, failure)
        if canonical_bytes(failure_actual) != canonical_bytes(failure_expected):
            raise VerificationError("FAILURE_GOLDEN_MISMATCH")
        failure_reasons = {item["reason_code"] for item in failure_actual["results"]}
        if not {"KISH_ESS_BELOW_20", "MAX_NORMALIZED_WEIGHT_ABOVE_0_20"}.issubset(failure_reasons):
            raise VerificationError("weight-diagnostic failure goldens are absent")
        verify_contract_surface(success, success_actual)
        print(
            "TWO_PHASE_AMENDMENT_GOLDEN_PASS "
            f"artifacts={artifact_count} prompt_success={success_actual['prompt_phase_two']['common_successful']} "
            f"vector_success={success_actual['vector_aware']['common_successful']} failure_cases={len(failure_actual['results'])}"
        )
        return 0
    except (OSError, KeyError, TypeError, ValueError, VerificationError) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
