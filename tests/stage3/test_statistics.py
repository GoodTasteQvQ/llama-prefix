from __future__ import annotations

import json
import copy
import hashlib
import unittest
from pathlib import Path

from stage3_pipeline.statistics import (
    human_quota,
    reference_statistics,
    retained_bootstrap,
    two_phase,
    two_phase_correction,
)
from stage3_pipeline.statistics.schema_validation import InstanceValidationError, validate_subschema
from tests.stage3.helpers import ROOT


FIXTURES = ROOT / "tests/stage3/fixtures"


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class StatisticalGoldenTests(unittest.TestCase):
    def test_p1_and_raw_p2_goldens(self) -> None:
        directory = FIXTURES / "statistics"
        base = load(directory / "statistical_golden_input.json")
        expected = load(directory / "statistical_golden_expected.json")
        self.assertEqual(reference_statistics.evaluate_fixture(base), expected)
        failures = load(directory / "failure_golden_input.json")
        failure_expected = load(directory / "failure_golden_expected.json")
        self.assertEqual(
            reference_statistics.evaluate_failure_fixture(base, failures),
            failure_expected,
        )

    def test_retained_bootstrap_goldens(self) -> None:
        directory = FIXTURES / "retained_bootstrap"
        success = load(directory / "success_golden_input.json")
        expected = load(directory / "success_golden_expected.json")
        self.assertEqual(retained_bootstrap.evaluate_success_fixture(success), expected)
        failures = load(directory / "failure_golden_input.json")
        failure_expected = load(directory / "failure_golden_expected.json")
        self.assertEqual(
            retained_bootstrap.evaluate_failure_fixture(success, failures),
            failure_expected,
        )

    def test_two_phase_goldens(self) -> None:
        directory = FIXTURES / "two_phase"
        success = load(directory / "success_input.json")
        expected = load(directory / "success_expected.json")
        self.assertEqual(two_phase.evaluate_success_fixture(success), expected)
        failures = load(directory / "failure_input.json")
        failure_expected = load(directory / "failure_expected.json")
        self.assertEqual(two_phase.evaluate_failure_fixture(success, failures), failure_expected)
        schema_cases = load(directory / "schema_negative_input.json")
        schema_result = two_phase.evaluate_schema_negative_fixture(success, schema_cases)
        self.assertTrue(all(row["status"] != "UNEXPECTED_PASS" for row in schema_result["results"]))

    def test_fixed720_and_point_correction_goldens(self) -> None:
        human_quota.verify_golden(FIXTURES / "fixed720/human_quota_golden.json")
        two_phase_correction.verify_golden(
            FIXTURES / "two_phase/two_phase_correction_golden.json"
        )

    def test_fixed720_typed_universe_contract_and_full_4680_frame(self) -> None:
        records = []
        for index in range(4_000):
            records.append({
                "response_id": f"p2-{index:04d}",
                "block": "P2",
                "logical_cell": human_quota.P2_CELLS[index % len(human_quota.P2_CELLS)],
                "predicted_class": "safe",
                "matched": True,
            })
        for block, count, predicted_class in (
            ("harmful_clean", 50, "safe"),
            ("benign_clean", 30, "helpful"),
            ("benign_steered", 600, "helpful"),
        ):
            records.extend({
                "response_id": f"{block}-{index:04d}",
                "block": block,
                "predicted_class": predicted_class,
                "matched": False,
            } for index in range(count))
        result = human_quota.allocate_human_sample(records)
        self.assertEqual(result["eligible_n"], 4_680)
        self.assertEqual(result["selected_n"], 720)

        invalid_records = (
            {"response_id": "typed", "block": "P2", "logical_cell": "P2_A_all",
             "predicted_class": "safe", "matched": "false"},
            {"response_id": "support", "block": "support", "predicted_class": "safe",
             "matched": False},
            {"response_id": "k1", "block": "K1", "predicted_class": "safe",
             "matched": False},
            {"response_id": "unknown", "block": "unknown", "predicted_class": "safe",
             "matched": False},
            {"response_id": "bad-cell", "block": "P2", "logical_cell": "support",
             "predicted_class": "safe", "matched": True},
            {"response_id": "bad-clean", "block": "harmful_clean",
             "predicted_class": "safe", "matched": True},
            {"response_id": "bad-label", "block": "benign_clean",
             "predicted_class": "safe", "matched": False},
        )
        for record in invalid_records:
            with self.subTest(record=record["response_id"]):
                with self.assertRaises(human_quota.AllocationError):
                    human_quota.allocate_human_sample([record])

    def test_retained_bootstrap_partial_production_shape_and_schema_negatives(self) -> None:
        directory = FIXTURES / "retained_bootstrap"
        fixture = load(directory / "partial_harmful_production_shape_input.json")
        expected = load(directory / "partial_harmful_production_shape_expected.json")
        payload = fixture["production_schema_payload"]
        schema_path = ROOT / "stage3_pipeline/statistics/schemas/retained_bootstrap.schema.json"
        schema = load(schema_path)
        pointer = "#/$defs/harmfulClean"
        validate_subschema(schema, pointer, payload)
        controls = []
        value = copy.deepcopy(payload); value["prompt_frame"] = value["prompt_frame"][:49]; controls.append(value)
        value = copy.deepcopy(payload); value["records"] = []; controls.append(value)
        value = copy.deepcopy(payload); value["synthetic_data"] = True; controls.append(value)
        value = copy.deepcopy(payload); value["prompt_frame"] = {}; controls.append(value)
        value = copy.deepcopy(payload); del value["block_type"]; controls.append(value)
        value = copy.deepcopy(payload); value["unregistered"] = False; controls.append(value)
        value = copy.deepcopy(payload); value["prompt_frame"][0]["prompt_id"] = ""; controls.append(value)
        value = copy.deepcopy(payload); value["prompt_frame"][0]["position"] = -1; controls.append(value)
        value = copy.deepcopy(payload); value["records"][0]["label"] = "unknown"; controls.append(value)
        value = copy.deepcopy(payload)
        value["records"].extend({
            "row_id": f"schema-extra-{index}",
            "prompt_id": value["prompt_frame"][3]["prompt_id"],
            "label": "safe",
        } for index in range(48))
        controls.append(value)
        for index, invalid in enumerate(controls):
            with self.subTest(case=index):
                with self.assertRaises(InstanceValidationError):
                    validate_subschema(schema, pointer, invalid)
        output = retained_bootstrap.analyze_harmful_clean(payload, fixture_mode=False)
        witness = expected["witness"]
        self.assertEqual(expected["schema_validation"]["negative_controls_rejected"], len(controls))
        self.assertEqual(
            expected["schema_validation"]["bound_schema_sha256"],
            hashlib.sha256(schema_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(output["replicates_successful"], witness["common_successes"])
        self.assertEqual(output["replicates_failed"], witness["failed_replicates"])
        self.assertEqual(retained_bootstrap.canonical_output_sha256(output), witness["output_canonical_sha256"])


if __name__ == "__main__":
    unittest.main()
