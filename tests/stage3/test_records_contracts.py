from __future__ import annotations

import copy
import os
import unittest

from stage3_pipeline.core import DECODE_CONFIG, GenerationProducer, LogicalIdentityRegistry, TerminalGenerationError, canonical_sha256
from stage3_pipeline.json_schema import SchemaValidationError, validate_schema
from stage3_pipeline.records import (
    RecordSchemaError,
    SCHEMA_DIRECTORY,
    build_block_response_record,
    build_k1_reuse_record,
    validate_benign_materialization,
    validate_benign_record,
    validate_generation_record,
    validate_k1_materialization,
    validate_p1_record,
    validate_p2_materialization,
    validate_p2_record,
    validate_support_materialization,
    validate_support_record,
    build_response_record,
    validate_response_materialization,
    validate_response_record,
)
from stage3_pipeline.execution import reconcile_execution
from tests.stage3.helpers import ROOT, block_identity, completed_chain


def rehash(record: dict[str, object]) -> dict[str, object]:
    record["record_sha256"] = canonical_sha256(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )
    return record


def valid_p1() -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": "paper1-stage3-p1-measurement-record-v3",
        "protocol_version": "paper1-stage3-current-v1",
        "run_mode": "paper",
        "paper_result_eligible": False,
        "logical_id": "p1:test",
        "identity_sha256": "0" * 64,
        "prompt_id": "p1-prompt",
        "domain": "harmful",
        "identity_complete": True,
        "render_complete": True,
        "valid_mask_complete": True,
        "forward_complete": True,
        "identity_collision": False,
        "valid_token_count": 10,
        "content_token_count": 8,
        "unresolved_valid_token_count": 0,
        "required_norms_finite": True,
        "all_norm_sum": 12.0,
        "content_norm_sum": 9.0,
        "complete_case": True,
        "terminal_status": "COMPLETE_CASE",
        "exclusion_reason": None,
    }
    return rehash(record)


DOSE_NUMERIC_FIELDS = (
    "nominal_c", "mu_value", "alpha_pre_dtype", "alpha_post_dtype", "pre_hook_l2",
    "post_hook_l2", "relative_dose", "norm_ratio", "vector_alignment", "cosine_drift",
)


def mark_invalid_dose(
    record: dict[str, object], *, flag: str, failure_code: str
) -> dict[str, object]:
    record[flag] = False
    evidence = copy.deepcopy(record["dose_evidence"])
    assert isinstance(evidence, dict)
    evidence["status"] = "INVALID"
    evidence["failure_code"] = failure_code
    for field in DOSE_NUMERIC_FIELDS:
        evidence[field] = None
    record["dose_evidence"] = evidence
    record["terminal_status"] = "NON_ESTIMABLE_DOSE"
    record["missingness_code"] = "NON_ESTIMABLE_DOSE"
    record["retained"] = False
    return rehash(record)


class RecordContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.update({
            "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "TEMP": str(ROOT / ".codex-temp"), "TMP": str(ROOT / ".codex-temp"),
        })

    def test_p1_complete_case_and_negative_norm_fail_closed(self) -> None:
        self.assertTrue(validate_p1_record(valid_p1())["complete_case"])
        negative = copy.deepcopy(valid_p1())
        negative["all_norm_sum"] = -0.01
        rehash(negative)
        with self.assertRaises(SchemaValidationError):
            validate_schema(negative, SCHEMA_DIRECTORY / "p1_measurement_record.schema.json")
        with self.assertRaises(RecordSchemaError):
            validate_p1_record(negative)

    def test_p1_subset_norm_and_zero_denominator_sums_fail_closed(self) -> None:
        subset = copy.deepcopy(valid_p1())
        subset["all_norm_sum"] = 1.0
        subset["content_norm_sum"] = 2.0
        rehash(subset)
        with self.assertRaises(RecordSchemaError):
            validate_p1_record(subset)

        zero_denominator = copy.deepcopy(valid_p1())
        zero_denominator.update({
            "valid_token_count": 0,
            "content_token_count": 0,
            "all_norm_sum": 1.0,
            "content_norm_sum": 0.0,
            "complete_case": False,
            "terminal_status": "EXCLUDED_ZERO_DENOMINATOR",
            "exclusion_reason": "EXCLUDED_ZERO_DENOMINATOR",
        })
        rehash(zero_denominator)
        with self.assertRaises(RecordSchemaError):
            validate_p1_record(zero_denominator)

        overlapping_classes = copy.deepcopy(valid_p1())
        overlapping_classes.update({
            "content_token_count": 8,
            "unresolved_valid_token_count": 5,
            "complete_case": False,
            "terminal_status": "EXCLUDED_UNRESOLVED",
            "exclusion_reason": "EXCLUDED_UNRESOLVED",
        })
        rehash(overlapping_classes)
        validate_schema(
            overlapping_classes, SCHEMA_DIRECTORY / "p1_measurement_record.schema.json"
        )
        with self.assertRaises(RecordSchemaError):
            validate_p1_record(overlapping_classes)

    def test_p1_first_failure_precedence_is_unique(self) -> None:
        invalid = copy.deepcopy(valid_p1())
        invalid["identity_complete"] = False
        invalid["complete_case"] = False
        invalid["terminal_status"] = "EXCLUDED_FORWARD"
        invalid["exclusion_reason"] = "EXCLUDED_FORWARD"
        rehash(invalid)
        with self.assertRaises(RecordSchemaError):
            validate_p1_record(invalid)
        finite_flag = copy.deepcopy(valid_p1())
        finite_flag["required_norms_finite"] = False
        finite_flag["complete_case"] = False
        finite_flag["terminal_status"] = "EXCLUDED_NONFINITE"
        finite_flag["exclusion_reason"] = "EXCLUDED_NONFINITE"
        rehash(finite_flag)
        with self.assertRaises(RecordSchemaError):
            validate_p1_record(finite_flag)

    def test_lone_retryable_generation_terminal_is_rejected(self) -> None:
        generation = copy.deepcopy(completed_chain()["generation"])
        generation["attempts"] = [{
            "attempt_index": 1,
            "status": "TECHNICAL_FAILURE_RETRYABLE",
            "output_text": None,
            "failure_code": "TechnicalGenerationError",
            "diagnostics": {},
        }]
        generation["attempt_count"] = 1
        generation["retry_count"] = 0
        generation["terminal_status"] = "TERMINAL_FAILURE"
        generation["generation_completed"] = False
        generation["output_text"] = None
        rehash(generation)
        with self.assertRaises(RecordSchemaError):
            validate_generation_record(generation)

    def test_generation_false_judge_eligible_true_is_schema_and_semantic_error(self) -> None:
        response = copy.deepcopy(completed_chain("P2_A_all")["response"])
        response["generation_completed"] = False
        rehash(response)
        with self.assertRaises(SchemaValidationError):
            validate_schema(response, SCHEMA_DIRECTORY / "p2_response_record.schema.json")
        with self.assertRaises(RecordSchemaError):
            validate_p2_record(response)

    def test_p2_cell_arm_anchor_estimator_and_lineage_mismatch_fail(self) -> None:
        chain = completed_chain("P2_A_content")
        for field, value in (
            ("arm", "all-token"), ("anchor", "T"), ("estimator", "mu_all_tw")
        ):
            invalid = copy.deepcopy(chain["response"])
            invalid[field] = value
            rehash(invalid)
            with self.subTest(field=field):
                with self.assertRaises(RecordSchemaError):
                    validate_p2_record(invalid)
        forged = copy.deepcopy(chain["response"])
        forged["generation_record_sha256"] = "f" * 64
        rehash(forged)
        with self.assertRaises(RecordSchemaError):
            validate_p2_materialization(
                forged, registry=chain["registry"], generation_record=chain["generation"],
                judge_record=chain["judge"], dose_binding=chain["dose_binding"],
            )

    def test_k1_exact_reuse_rejects_forged_source_lineage(self) -> None:
        chain = completed_chain("P2_T_all")
        k1 = build_k1_reuse_record(chain["response"])
        validated = validate_k1_materialization(
            k1, registry=chain["registry"], source_p2_record=chain["response"],
            generation_record=chain["generation"], judge_record=chain["judge"],
            dose_binding=chain["dose_binding"],
        )
        self.assertEqual(validated["generation_calls_added"], 0)
        forged = copy.deepcopy(k1)
        forged["source_p2_record_sha256"] = "f" * 64
        rehash(forged)
        with self.assertRaises(RecordSchemaError):
            validate_k1_materialization(
                forged, registry=chain["registry"], source_p2_record=chain["response"],
                generation_record=chain["generation"], judge_record=chain["judge"],
                dose_binding=chain["dose_binding"],
            )

    def test_benign_clean_t_mismatch_and_failure_precedence_fail(self) -> None:
        clean = completed_chain("benign_clean")
        invalid = copy.deepcopy(clean["response"])
        invalid["cell"] = "benign_T"
        invalid["anchor"] = "T"
        invalid["estimator"] = "mu_all_tw"
        invalid["vector_id"] = "forged-vector"
        rehash(invalid)
        with self.assertRaises(RecordSchemaError):
            validate_benign_record(invalid)
        steered = completed_chain("benign_T")
        precedence = copy.deepcopy(steered["response"])
        precedence["terminal_status"] = "TERMINAL_JUDGE_FAILURE"
        precedence["missingness_code"] = "TERMINAL_JUDGE_FAILURE"
        precedence["retained"] = False
        rehash(precedence)
        with self.assertRaises(RecordSchemaError):
            validate_benign_record(precedence)
        with self.assertRaises(RecordSchemaError):
            validate_benign_materialization(
                invalid, registry=clean["registry"], generation_record=clean["generation"],
                judge_record=clean["judge"], dose_binding=clean["dose_binding"],
            )

    def test_judge_parsed_flag_and_terminal_status_are_biconditional(self) -> None:
        cases = (
            ("P2_A_all", validate_p2_record),
            ("benign_T", validate_benign_record),
            ("support", validate_support_record),
        )
        for block, validator in cases:
            invalid = copy.deepcopy(completed_chain(block)["response"])
            invalid["judge_terminal_status"] = "TERMINAL_PARSE_OR_INFRASTRUCTURE_FAILURE"
            rehash(invalid)
            with self.subTest(block=block):
                with self.assertRaises(RecordSchemaError):
                    validator(invalid)

    def test_steered_dose_failure_requires_exact_provenance_and_precedence(self) -> None:
        validators = {
            "P2_A_all": (validate_p2_record, validate_p2_materialization),
            "benign_T": (validate_benign_record, validate_benign_materialization),
            "support": (validate_support_record, validate_support_materialization),
        }
        failures = (
            ("dose_denominator_valid", "INVALID_DOSE_DENOMINATOR"),
            ("dose_geometry_finite", "INVALID_DOSE_GEOMETRY"),
            ("post_dtype_alpha_finite", "INVALID_POST_DTYPE_ALPHA"),
        )
        for block, (validator, materializer) in validators.items():
            for false_flag, code in failures:
                chain = completed_chain(block, dose_failure_code=code)
                response = chain["response"]
                with self.subTest(block=block, failure_code=code):
                    self.assertFalse(response[false_flag])
                    self.assertEqual(validator(response)["terminal_status"], "NON_ESTIMABLE_DOSE")
                    self.assertEqual(materializer(
                        response,
                        registry=chain["registry"],
                        generation_record=chain["generation"],
                        judge_record=chain["judge"],
                        dose_binding=chain["dose_binding"],
                    )["terminal_status"], "NON_ESTIMABLE_DOSE")
                    self.assertEqual(
                        chain["reconciliation"]["terminal_partition"]["NON_ESTIMABLE_DOSE"], 1
                    )

            valid_chain = completed_chain(block)
            fabricated = mark_invalid_dose(
                copy.deepcopy(valid_chain["response"]),
                flag="dose_denominator_valid",
                failure_code="INVALID_DOSE_DENOMINATOR",
            )
            self.assertEqual(validator(fabricated)["terminal_status"], "NON_ESTIMABLE_DOSE")
            with self.assertRaises(RecordSchemaError):
                materializer(
                    fabricated,
                    registry=valid_chain["registry"],
                    generation_record=valid_chain["generation"],
                    judge_record=valid_chain["judge"],
                    dose_binding=valid_chain["dose_binding"],
                )

    def test_response_dose_geometry_is_exactly_bound_to_terminal_producer(self) -> None:
        chain = completed_chain("P2_A_all")
        forged = copy.deepcopy(chain["response"])
        evidence = forged["dose_evidence"]
        alpha = evidence["alpha_post_dtype"]["value"]
        replacements = {
            "pre_hook_l2": 4.0,
            "post_hook_l2": 4.4,
            "relative_dose": alpha / 4.0,
            "norm_ratio": 4.4 / 4.0,
            "vector_alignment": 0.25,
            "cosine_drift": 0.2,
        }
        for field, value in replacements.items():
            evidence[field] = {"value": value, "binary64_hex": value.hex()}
        rehash(forged)
        self.assertTrue(validate_p2_record(forged)["retained"])
        with self.assertRaises(RecordSchemaError):
            build_block_response_record(
                identity=chain["identity"], generation_record=chain["generation"],
                judge_record=chain["judge"], dose_evidence=evidence,
            )
        with self.assertRaises(RecordSchemaError):
            validate_p2_materialization(
                forged, registry=chain["registry"], generation_record=chain["generation"],
                judge_record=chain["judge"], dose_binding=chain["dose_binding"],
            )
        disposition = copy.deepcopy(chain["disposition"])
        disposition["response_record_sha256"] = forged["record_sha256"]
        with self.assertRaises(RecordSchemaError):
            reconcile_execution(
                chain["registry"], run_mode="smoke",
                generation_records=[chain["generation"]], judge_records=[chain["judge"]],
                response_records=[forged], dispositions=[disposition],
                dose_binding=chain["dose_binding"],
            )

    def test_support_schema_and_source_materialization_are_dedicated(self) -> None:
        chain = completed_chain("support")
        self.assertTrue(validate_support_record(chain["response"])["retained"])
        self.assertTrue(validate_support_materialization(
            chain["response"], registry=chain["registry"],
            generation_record=chain["generation"], judge_record=chain["judge"],
            dose_binding=chain["dose_binding"],
        )["retained"])

    def test_harmful_clean_missingness_matches_actual_generation_terminal(self) -> None:
        item_identity = block_identity("harmful_clean", "failed-clean")
        registry = LogicalIdentityRegistry()
        logical_id = registry.register(item_identity)

        def fail(_identity: object, _request: object) -> dict[str, object]:
            raise TerminalGenerationError("deterministic fixture")

        generation = GenerationProducer(
            registry, fail, run_mode="smoke", fake_backend=True
        ).produce(logical_id, {"logical_id": logical_id, "generation_config": DECODE_CONFIG})
        response = build_response_record(
            identity=item_identity, generation_record=generation, judge_record=None,
            missingness_code="TERMINAL_GENERATION_DETERMINISTIC_FAILURE", dose_evidence=None,
        )
        forged = copy.deepcopy(response)
        forged["missingness_code"] = "TERMINAL_GENERATION_TECHNICAL_FAILURE"
        rehash(forged)
        with self.assertRaises(RecordSchemaError):
            validate_response_materialization(
                forged, registry=registry, generation_record=generation, judge_record=None
            )

    def test_harmful_clean_forged_identity_fails_materialization_and_reconciliation(self) -> None:
        chain = completed_chain("harmful_clean")
        forged = copy.deepcopy(chain["response"])
        forged["identity_sha256"] = "f" * 64
        rehash(forged)
        with self.assertRaises(RecordSchemaError):
            validate_response_materialization(
                forged, registry=chain["registry"], generation_record=chain["generation"],
                judge_record=chain["judge"],
            )
        disposition = copy.deepcopy(chain["disposition"])
        disposition["response_record_sha256"] = forged["record_sha256"]
        with self.assertRaises(RecordSchemaError):
            reconcile_execution(
                chain["registry"], run_mode="smoke",
                generation_records=[chain["generation"]], judge_records=[chain["judge"]],
                response_records=[forged], dispositions=[disposition],
                dose_binding=chain["dose_binding"],
            )

    def test_harmful_clean_source_fields_are_bound_to_common_lineage(self) -> None:
        chain = completed_chain("harmful_clean")
        with self.assertRaises(RecordSchemaError):
            build_response_record(
                identity=chain["identity"], generation_record=chain["generation"],
                judge_record=chain["judge"], missingness_code=None, dose_evidence={},
            )
        cases = (
            ("run_mode", "pilot"),
            ("generation_fake_backend", False),
            ("label", "unsafe"),
        )
        for field, value in cases:
            forged = copy.deepcopy(chain["response"])
            forged[field] = value
            rehash(forged)
            with self.subTest(field=field):
                validate_response_record(forged)
                with self.assertRaises(RecordSchemaError):
                    validate_response_materialization(
                        forged, registry=chain["registry"],
                        generation_record=chain["generation"], judge_record=chain["judge"],
                    )


if __name__ == "__main__":
    unittest.main()
