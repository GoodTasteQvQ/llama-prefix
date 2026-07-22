#!/usr/bin/env python3
"""Hash-check and execute all retained-bootstrap success/failure goldens."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import retained_bootstrap as reference
from draft202012_subset import (
    SUPPORTED_KEYWORDS,
    InstanceValidationError,
    SchemaDefinitionError,
    validate_subschema,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
COMPONENT_ROOT = (
    REPO_ROOT
    / "writing"
    / "stage3 design"
    / "v3_5_rc2_binding_amendment_01"
    / "retained_bootstrap"
)
MANIFEST_PATH = COMPONENT_ROOT / "retained_bootstrap_manifest.json"
SCHEMA_PATH = COMPONENT_ROOT / "retained_bootstrap_schema.json"
HARMFUL_CLEAN_SUBSCHEMA = "#/$defs/harmfulClean"
PARTIAL_INPUT_PATH = COMPONENT_ROOT / "fixtures/partial_harmful_production_shape_input.json"
PARTIAL_EXPECTED_PATH = COMPONENT_ROOT / "fixtures/partial_harmful_production_shape_expected.json"


def canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_manifest() -> dict[str, object]:
    manifest = load_json(MANIFEST_PATH)
    require(isinstance(manifest, dict), "MANIFEST_INVALID")
    recorded_self = manifest.get("self_sha256")
    without_self = {key: value for key, value in manifest.items() if key != "self_sha256"}
    actual_self = hashlib.sha256(canonical(without_self).encode("utf-8")).hexdigest()
    require(recorded_self == actual_self, f"MANIFEST_SELF_HASH_MISMATCH {actual_self}")

    expected_paths = {
        "scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap.py",
        "scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/draft202012_subset.py",
        "scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/verify_golden.py",
        "writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/README.md",
        "writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/retained_bootstrap_schema.json",
        "writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/success_golden_input.json",
        "writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/success_golden_expected.json",
        "writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/failure_golden_input.json",
        "writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/failure_golden_expected.json",
        "writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/partial_harmful_production_shape_input.json",
        "writing/stage3 design/v3_5_rc2_binding_amendment_01/retained_bootstrap/fixtures/partial_harmful_production_shape_expected.json",
    }
    artifacts = manifest.get("artifacts")
    require(isinstance(artifacts, list), "MANIFEST_ARTIFACTS_INVALID")
    actual_paths = {item.get("path") for item in artifacts if isinstance(item, dict)}
    require(actual_paths == expected_paths, "MANIFEST_ARTIFACT_SET_MISMATCH")
    for item in artifacts:
        relative = item["path"]
        path = REPO_ROOT / relative
        require(path.is_file(), f"MISSING_ARTIFACT {relative}")
        actual = sha256(path)
        require(actual == item["sha256"], f"HASH_MISMATCH {relative}: {actual}")
    dependencies = manifest.get("transitive_dependencies")
    require(isinstance(dependencies, list) and dependencies, "TRANSITIVE_DEPENDENCIES_INVALID")
    for item in dependencies:
        require(isinstance(item, dict) and set(item) == {"path", "sha256"},
                "TRANSITIVE_DEPENDENCY_ENTRY_INVALID")
        relative = item["path"]
        path = REPO_ROOT / relative
        require(path.is_file(), f"MISSING_TRANSITIVE_DEPENDENCY {relative}")
        actual = sha256(path)
        require(actual == item["sha256"], f"TRANSITIVE_HASH_MISMATCH {relative}: {actual}")
    return manifest


def verify_contract_surface(manifest: dict[str, object]) -> None:
    require(reference.PRODUCTION_REPLICATES == 10_000, "REPLICATE_CONSTANT_MISMATCH")
    require(reference.PRODUCTION_MIN_SUCCESS == 9_500, "SUCCESS_CONSTANT_MISMATCH")
    require(reference.PRODUCTION_SUCCESS_FRACTION == 0.95, "SUCCESS_FRACTION_MISMATCH")
    require(reference.MASTER_SEED == 42, "MASTER_SEED_MISMATCH")
    require(
        (reference.K1_BLOCK_ID, reference.HARMFUL_CLEAN_BLOCK_ID, reference.BENIGN_BROKEN_BLOCK_ID)
        == ("k1-profile", "harmful-clean-prompt", "benign-broken-prompt"),
        "BLOCK_ID_MISMATCH",
    )
    for name in ("analyze_k1", "analyze_harmful_clean", "analyze_benign_broken"):
        require(callable(getattr(reference, name, None)), f"PUBLIC_API_MISSING {name}")
    require(manifest.get("formal_data_used") is False, "FORMAL_DATA_FLAG_INVALID")
    require(manifest.get("no_scope_expansion") is True, "SCOPE_FLAG_INVALID")
    require(
        manifest.get("amendment_id") == "v3.5-rc2-binding-amendment-01"
        and manifest.get("status") == "DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED",
        "AMENDMENT_ID_OR_STATUS_INVALID",
    )
    production = manifest.get("production_parameters")
    require(
        isinstance(production, dict)
        and production.get("replicates") == 10_000
        and production.get("common_success_required") == 9_500,
        "MANIFEST_PRODUCTION_PARAMETERS_INVALID",
    )

    schema = load_json(SCHEMA_PATH)
    require(isinstance(schema, dict), "SCHEMA_INVALID")
    require(schema.get("$id") == reference.SCHEMA_VERSION, "SCHEMA_VERSION_MISMATCH")
    k1 = schema["$defs"]["k1"]["properties"]
    clean = schema["$defs"]["harmfulClean"]["properties"]
    benign = schema["$defs"]["benignBroken"]["properties"]
    require(
        k1["prompt_frame"]["minItems"] == k1["prompt_frame"]["maxItems"] == 50
        and k1["vector_frame"]["minItems"] == k1["vector_frame"]["maxItems"] == 20
        and clean["prompt_frame"]["minItems"] == clean["prompt_frame"]["maxItems"] == 50
        and clean["records"]["minItems"] == 1
        and clean["records"]["maxItems"] == 50
        and benign["complete_prompt_frame"]["minItems"] == 1
        and benign["complete_prompt_frame"]["maxItems"] == 30
        and benign["vector_frame"]["minItems"] == 20
        and benign["vector_frame"]["maxItems"] == 20,
        "BENIGN_SCHEMA_FRAME_BOUNDS_INVALID",
    )


def require_schema_rejection(
    schema: dict[str, object], payload: object, expected_keyword: str, case_id: str
) -> None:
    try:
        validate_subschema(schema, HARMFUL_CLEAN_SUBSCHEMA, payload)
    except InstanceValidationError as error:
        require(
            error.keyword == expected_keyword,
            f"SCHEMA_NEGATIVE_WRONG_KEYWORD {case_id}: {error.keyword}",
        )
    else:
        require(False, f"SCHEMA_NEGATIVE_UNEXPECTED_PASS {case_id}")


def verify_bound_schema_controls(schema: dict[str, object], payload: dict[str, object]) -> int:
    require(
        SUPPORTED_KEYWORDS
        == {
            "$ref", "type", "const", "enum", "required", "properties",
            "additionalProperties", "minItems", "maxItems", "items", "minLength",
            "minimum", "description",
        },
        "SCHEMA_HELPER_KEYWORD_SURFACE_CHANGED",
    )
    validate_subschema(schema, HARMFUL_CLEAN_SUBSCHEMA, payload)

    controls: list[tuple[str, dict[str, object], str]] = []

    prompt_49 = copy.deepcopy(payload)
    prompt_49["prompt_frame"] = prompt_49["prompt_frame"][:49]
    controls.append(("49_prompts", prompt_49, "minItems"))

    records_51 = copy.deepcopy(payload)
    records_51["records"].extend(
        {
            "row_id": f"synthetic-schema-negative-extra-row-{index:02d}",
            "prompt_id": payload["prompt_frame"][3]["prompt_id"],
            "label": "safe",
        }
        for index in range(4, 52)
    )
    controls.append(("51_records", records_51, "maxItems"))

    empty_records = copy.deepcopy(payload)
    empty_records["records"] = []
    controls.append(("empty_records", empty_records, "minItems"))

    synthetic_inner = copy.deepcopy(payload)
    synthetic_inner["synthetic_data"] = True
    controls.append(("inner_synthetic_true", synthetic_inner, "const"))

    wrong_type = copy.deepcopy(payload)
    wrong_type["prompt_frame"] = {}
    controls.append(("prompt_frame_wrong_type", wrong_type, "type"))

    missing_required = copy.deepcopy(payload)
    del missing_required["block_type"]
    controls.append(("missing_block_type", missing_required, "required"))

    extra_property = copy.deepcopy(payload)
    extra_property["unregistered"] = False
    controls.append(("extra_property", extra_property, "additionalProperties"))

    empty_id = copy.deepcopy(payload)
    empty_id["prompt_frame"][0]["prompt_id"] = ""
    controls.append(("empty_prompt_id", empty_id, "minLength"))

    negative_position = copy.deepcopy(payload)
    negative_position["prompt_frame"][0]["position"] = -1
    controls.append(("negative_position", negative_position, "minimum"))

    invalid_label = copy.deepcopy(payload)
    invalid_label["records"][0]["label"] = "unknown"
    controls.append(("invalid_label", invalid_label, "enum"))

    for case_id, instance, keyword in controls:
        require_schema_rejection(schema, instance, keyword, case_id)

    unknown_keyword = copy.deepcopy(schema)
    unknown_keyword["$defs"]["harmfulClean"]["unknownKeyword"] = True
    try:
        validate_subschema(unknown_keyword, HARMFUL_CLEAN_SUBSCHEMA, payload)
    except SchemaDefinitionError as error:
        require("unsupported schema keywords" in str(error), "SCHEMA_UNKNOWN_KEYWORD_NOT_FAIL_CLOSED")
    else:
        require(False, "SCHEMA_UNKNOWN_KEYWORD_UNEXPECTED_PASS")

    malformed_keyword = copy.deepcopy(schema)
    malformed_keyword["$defs"]["harmfulClean"]["required"] = "block_type"
    try:
        validate_subschema(malformed_keyword, HARMFUL_CLEAN_SUBSCHEMA, payload)
    except SchemaDefinitionError as error:
        require("required must be" in str(error), "SCHEMA_MALFORMED_KEYWORD_NOT_FAIL_CLOSED")
    else:
        require(False, "SCHEMA_MALFORMED_KEYWORD_UNEXPECTED_PASS")

    return len(controls)


def build_partial_production_receipt(
    fixture: dict[str, object], output: dict[str, object], negative_control_count: int
) -> dict[str, object]:
    payload = fixture["production_schema_payload"]
    points = {
        label: output["statistics"][label]["point"] for label in reference.HARMFUL_LABELS
    }
    return {
        "fixture_schema": "v3.5-rc2-amendment-01-partial-harmful-production-shape-receipt-v1",
        "synthetic_data": True,
        "formal_data_used": False,
        "data_origin": "SYNTHETIC_GOLDEN_ONLY",
        "purpose": "production-schema partial-record execution witness",
        "schema_validation": {
            "bound_schema_path": HARMFUL_CLEAN_SUBSCHEMA,
            "bound_schema_sha256": sha256(SCHEMA_PATH),
            "negative_controls_rejected": negative_control_count,
            "status": "PASS",
        },
        "production_entry": {
            "call": "analyze_harmful_clean(payload)",
            "fixture_mode": False,
        },
        "witness": {
            "inner_synthetic_data": payload["synthetic_data"],
            "prompt_count": len(payload["prompt_frame"]),
            "retained_count": len(payload["records"]),
            "point_denominator": len(payload["records"]),
            "point_profile": points,
            "draw_size": output["frame"]["prompt_sample_size_per_replicate"],
            "replicates_requested": output["replicates_requested"],
            "common_successes": output["replicates_successful"],
            "failed_replicates": output["replicates_failed"],
            "failure_reason_family": "INVALID_DENOMINATOR:zero_retained_denominator",
            "no_reroll": True,
            "output_canonical_sha256": canonical_sha256(output),
        },
    }


def verify_partial_production_witness() -> dict[str, object]:
    fixture = load_json(PARTIAL_INPUT_PATH)
    require(isinstance(fixture, dict), "PARTIAL_PRODUCTION_FIXTURE_INVALID")
    require(
        set(fixture)
        == {
            "fixture_schema", "synthetic_data", "formal_data_used", "data_origin",
            "purpose", "production_schema_payload",
        },
        "PARTIAL_PRODUCTION_FIXTURE_KEYS_INVALID",
    )
    require(
        fixture["fixture_schema"]
        == "v3.5-rc2-amendment-01-partial-harmful-production-shape-input-v1"
        and fixture["synthetic_data"] is True
        and fixture["formal_data_used"] is False
        and fixture["data_origin"] == "SYNTHETIC_GOLDEN_ONLY"
        and fixture["purpose"] == "production-schema partial-record execution witness",
        "PARTIAL_PRODUCTION_PROVENANCE_INVALID",
    )
    payload = fixture["production_schema_payload"]
    require(isinstance(payload, dict), "PARTIAL_PRODUCTION_PAYLOAD_INVALID")
    require(
        all(
            item["prompt_id"].startswith("synthetic-partial-harmful-prompt-")
            for item in payload["prompt_frame"]
        )
        and all(
            item["row_id"].startswith("synthetic-partial-harmful-row-")
            for item in payload["records"]
        ),
        "PARTIAL_PRODUCTION_IDENTITIES_NOT_SYNTHETIC",
    )

    schema = load_json(SCHEMA_PATH)
    require(isinstance(schema, dict), "BOUND_SCHEMA_INVALID")
    negative_control_count = verify_bound_schema_controls(schema, payload)

    expected_bytes_before = PARTIAL_EXPECTED_PATH.read_bytes()
    expected = json.loads(expected_bytes_before.decode("utf-8"))
    require(
        isinstance(expected, dict)
        and expected.get("synthetic_data") is True
        and expected.get("formal_data_used") is False,
        "PARTIAL_EXPECTED_PROVENANCE_INVALID",
    )

    # The exact schema-validated payload is passed to the production entry.
    output = reference.analyze_harmful_clean(payload)
    points = {label: output["statistics"][label]["point"] for label in reference.HARMFUL_LABELS}
    require(
        payload["synthetic_data"] is False
        and len(payload["prompt_frame"]) == 50
        and len(payload["records"]) == 3
        and output["frame"]["prompt_sample_size_per_replicate"] == 50,
        "PARTIAL_PRODUCTION_SHAPE_OR_DRAW_SIZE_MISMATCH",
    )
    require(
        points == {"broken": 1 / 3, "unsafe": 1 / 3, "refusal": 1 / 3, "safe": 0.0},
        "PARTIAL_PRODUCTION_POINT_DENOMINATOR_MISMATCH",
    )
    require(
        output["algorithm"] == "retained_percentile_nearest_rank_v1"
        and output["block_id"] == reference.HARMFUL_CLEAN_BLOCK_ID
        and output["interval"]
        == "nearest_rank_[Q_NR(0.025),Q_NR(0.975)]_no_interpolation"
        and output["failure_precedence"] == list(reference.FAILURE_PRECEDENCE)
        and output["master_seed"] == reference.MASTER_SEED
        and output["replicates_requested"] == reference.PRODUCTION_REPLICATES
        and output["replicates_required"] == reference.PRODUCTION_MIN_SUCCESS,
        "PARTIAL_PRODUCTION_CONSTANT_OR_ALGORITHM_MISMATCH",
    )
    require(
        9_500 <= output["replicates_successful"] < 10_000
        and output["replicates_failed"] == 10_000 - output["replicates_successful"]
        and output["first_failure_reasons"]
        and all(
            reason.startswith("INVALID_DENOMINATOR:replicate ")
            and reason.endswith(" denominator zero")
            for reason in output["first_failure_reasons"]
        ),
        "PARTIAL_PRODUCTION_COMPLETION_OR_FAILURE_MISMATCH",
    )

    actual = build_partial_production_receipt(fixture, output, negative_control_count)
    require(canonical(actual) == canonical(expected), "PARTIAL_PRODUCTION_EXPECTED_MISMATCH")
    require(
        PARTIAL_EXPECTED_PATH.read_bytes() == expected_bytes_before,
        "PARTIAL_EXPECTED_WAS_MODIFIED_DURING_VERIFICATION",
    )
    return actual


def verify_goldens() -> None:
    fixture_root = COMPONENT_ROOT / "fixtures"
    success_input = load_json(fixture_root / "success_golden_input.json")
    success_expected = load_json(fixture_root / "success_golden_expected.json")
    failure_input = load_json(fixture_root / "failure_golden_input.json")
    failure_expected = load_json(fixture_root / "failure_golden_expected.json")
    for name, fixture in (
        ("success_input", success_input),
        ("success_expected", success_expected),
        ("failure_input", failure_input),
        ("failure_expected", failure_expected),
    ):
        require(isinstance(fixture, dict) and fixture.get("synthetic_data") is True,
                f"SYNTHETIC_MARKER_MISSING {name}")

    success_actual = reference.evaluate_success_fixture(success_input)
    require(canonical(success_actual) == canonical(success_expected), "SUCCESS_GOLDEN_MISMATCH")
    failure_actual = reference.evaluate_failure_fixture(success_input, failure_input)
    require(canonical(failure_actual) == canonical(failure_expected), "FAILURE_GOLDEN_MISMATCH")

    full_analyzer_outputs = {
        "k1": reference.analyze_k1(success_input["k1"], fixture_mode=True),
        "harmful_clean": reference.analyze_harmful_clean(
            success_input["harmful_clean"], fixture_mode=True
        ),
        "benign_broken": reference.analyze_benign_broken(
            success_input["benign_broken"], fixture_mode=True
        ),
        "zero_sd": reference.analyze_harmful_clean(
            success_input["zero_sd"], fixture_mode=True
        ),
    }
    for block, full_output in full_analyzer_outputs.items():
        require(
            success_actual[block]["canonical_output_sha256"]
            == canonical_sha256(full_output),
            f"CANONICAL_OUTPUT_DIGEST_SEMANTICS_MISMATCH {block}",
        )

    # Schema-shaped synthetic witness for the frozen-frame missingness contract.
    partial_harmful = copy.deepcopy(success_input["harmful_clean"])
    partial_harmful["records"] = partial_harmful["records"][:3]
    partial_result = reference.analyze_harmful_clean(partial_harmful, fixture_mode=True)
    partial_points = {
        label: item["point"] for label, item in partial_result["statistics"].items()
    }
    require(
        partial_harmful["synthetic_data"] is True
        and 1 <= len(partial_harmful["records"]) <= 50
        and partial_result["frame"]["prompt_sample_size_per_replicate"] == 5,
        "HARMFUL_PARTIAL_SCHEMA_OR_FULL_FRAME_MISMATCH",
    )
    require(
        partial_points
        == {"broken": 1 / 3, "unsafe": 1 / 3, "refusal": 1 / 3, "safe": 0.0},
        "HARMFUL_PARTIAL_POINT_DENOMINATOR_MISMATCH",
    )
    require(
        9_500 <= partial_result["replicates_successful"] < 10_000
        and partial_result["replicates_failed"]
        == 10_000 - partial_result["replicates_successful"]
        and partial_result["first_failure_reasons"]
        and all(
            reason.startswith("INVALID_DENOMINATOR:replicate ")
            for reason in partial_result["first_failure_reasons"]
        ),
        "HARMFUL_PARTIAL_MISSING_PROMPT_REPLICATE_MISMATCH",
    )

    reordered_partial = copy.deepcopy(partial_harmful)
    reordered_partial["records"][0], reordered_partial["records"][1] = (
        reordered_partial["records"][1], reordered_partial["records"][0]
    )
    try:
        reference.analyze_harmful_clean(reordered_partial, fixture_mode=True)
    except reference.RetainedBootstrapError as error:
        require(error.code == "FRAME_ORDER_INVALID", "HARMFUL_PARTIAL_ORDER_CODE_MISMATCH")
    else:
        require(False, "HARMFUL_PARTIAL_ORDER_UNEXPECTED_PASS")

    empty_formal_shape = copy.deepcopy(success_input["harmful_clean"])
    empty_formal_shape["records"] = []
    try:
        reference.analyze_harmful_clean(empty_formal_shape, fixture_mode=True)
    except reference.RetainedBootstrapError as error:
        require(error.code == "INPUT_SCHEMA_INVALID", "EMPTY_RECORD_SCHEMA_PRIORITY_MISMATCH")
    else:
        require(False, "EMPTY_RECORD_SCHEMA_UNEXPECTED_PASS")

    # The formal validator must accept a complete-prompt survivor frame below 30.
    production_shortfall = copy.deepcopy(success_input["benign_broken"])
    production_shortfall["synthetic_data"] = False
    shortfall_result = reference.analyze_benign_broken(production_shortfall)
    require(
        shortfall_result["frame"]["prompt_sample_size_per_replicate"] == 3
        and shortfall_result["replicates_successful"] == 10_000,
        "BENIGN_COMPLETE_PROMPT_SHORTFALL_NOT_EXECUTABLE",
    )

    k1 = success_actual["k1"]
    witness = k1["shared_draw_witness"]
    require(
        witness["product_weight_p0_v0"]
        == witness["prompt_multiplicities"][0] * witness["vector_multiplicities"][0],
        "K1_PRODUCT_MULTIPLICITY_NOT_EXECUTED",
    )
    require(witness["shared_by_cells"] == list(reference.K1_CELLS), "K1_STREAM_NOT_SHARED")
    require("member_id" not in k1["sync_unit_id"]["prompt"], "MEMBER_ID_IN_PROMPT_SYNC")
    require("member_id" not in k1["sync_unit_id"]["vector"], "MEMBER_ID_IN_VECTOR_SYNC")
    require(
        success_actual["benign_broken"]["prompt_differences"] == [0.25, -0.5, 0.75],
        "BENIGN_VECTOR_AVERAGE_ORDER_NOT_EXECUTED",
    )
    require(
        success_actual["rng_success"]["scripted_rejection"]
        == {"draw": 7, "words_consumed": 2},
        "RNG_REJECTION_CONSUMPTION_MISMATCH",
    )
    zero_stats = success_actual["zero_sd"]["statistics"]
    require(
        all(item["degenerate_bootstrap"] is True for item in zero_stats.values())
        and zero_stats["safe"]["percentile_95"] == [1.0, 1.0],
        "ZERO_SD_CONTRACT_MISMATCH",
    )
    outcomes = {item["case_id"]: item for item in failure_actual["results"]}
    require(outcomes["common_success_9499_fails"]["status"] == "NON_ESTIMABLE",
            "9499_BOUNDARY_DID_NOT_FAIL")
    require(outcomes["common_success_9500_passes"]["status"] == "EXPECTED_PASS",
            "9500_BOUNDARY_DID_NOT_PASS")
    require(
        outcomes["identity_collision_precedes_order_and_membership"]["code"]
        == "IDENTITY_COLLISION",
        "IDENTITY_COLLISION_PRECEDENCE_MISMATCH",
    )
    require(
        outcomes["record_collision_precedes_frame_order"]["code"] == "IDENTITY_COLLISION"
        and outcomes["record_collision_precedes_frame_order"]["detail"]
        == "duplicate harmful-clean row_id",
        "CROSS_STAGE_COLLISION_PRECEDENCE_MISMATCH",
    )
    require(
        outcomes["invalid_profile_denominator"]["code"] == "INVALID_DENOMINATOR"
        and outcomes["invalid_profile_denominator"]["detail"] == "profile denominator is zero",
        "PROFILE_DENOMINATOR_UNIT_WITNESS_MISMATCH",
    )

    verify_partial_production_witness()


def main() -> int:
    manifest = verify_manifest()
    verify_contract_surface(manifest)
    verify_goldens()
    print("RETAINED_BOOTSTRAP_GOLDEN_PASS partial_schema_valid=1 partial_prompt_count=50")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
