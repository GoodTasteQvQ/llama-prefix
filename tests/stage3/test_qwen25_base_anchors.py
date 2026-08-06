from __future__ import annotations

import json
import math
import statistics
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs/stage3/qwen25_base_anchors_v1.json"
NORM_EVIDENCE_PATH = (
    ROOT
    / "results/stage1_phase_aware/validation/qwen25_mu_trackB_rogue_v1.json"
)
ANCHORS = ("A", "T", "H")


def reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def assert_finite_numbers(test: unittest.TestCase, value: Any) -> None:
    if isinstance(value, dict):
        for child in value.values():
            assert_finite_numbers(test, child)
    elif isinstance(value, list):
        for child in value:
            assert_finite_numbers(test, child)
    elif isinstance(value, float):
        test.assertTrue(math.isfinite(value))


class Qwen25BaseAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(
            CONFIG_PATH.read_text(encoding="utf-8"),
            parse_constant=reject_nonstandard_constant,
            object_pairs_hook=reject_duplicate_keys,
        )

    def test_config_strictly_parses_and_has_design_status(self) -> None:
        assert_finite_numbers(self, self.config)
        self.assertEqual(
            self.config["schema_version"],
            "paper1-stage3-qwen25-base-anchors-v1",
        )
        self.assertEqual(self.config["status"], "design_selected")
        self.assertFalse(self.config["formal_experiment_run"])
        self.assertTrue(self.config["not_outcome_optimized"])

    def test_pooled_norm_statistics_are_recomputed_from_evidence(self) -> None:
        evidence = json.loads(NORM_EVIDENCE_PATH.read_text(encoding="utf-8"))
        norms = [
            float(value)
            for record in evidence["records"]
            for value in record["norms"]
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        ]
        mu_stage1 = sum(norms) / len(norms)
        median_stage1_norm = statistics.median(norms)

        self.assertEqual(len(norms), self.config["retained_norm_count"])
        self.assertEqual(mu_stage1, self.config["mu_stage1"])
        self.assertEqual(median_stage1_norm, self.config["median_stage1_norm"])

    def test_reference_points_and_rho_follow_binary64_operation_order(self) -> None:
        references = self.config["reference_c_by_anchor"]
        grid_step = self.config["grid_step"]
        self.assertEqual(references["T"], 1.0)
        self.assertEqual(references["A"], references["T"] - grid_step)
        self.assertEqual(references["H"], references["T"] + grid_step)

        for anchor in ANCHORS:
            tmp = references[anchor] * self.config["mu_stage1"]
            expected_rho = tmp / self.config["median_stage1_norm"]
            self.assertEqual(self.config["rho_by_anchor"][anchor], expected_rho)

    def test_decimal_hex_pairs_are_exact_and_rho_is_strictly_increasing(self) -> None:
        rho = self.config["rho_by_anchor"]
        rho_hex = self.config["rho_binary64_hex"]
        for anchor in ANCHORS:
            self.assertEqual(rho[anchor].hex(), rho_hex[anchor])
            self.assertEqual(float.fromhex(rho_hex[anchor]), rho[anchor])
        self.assertLess(0.0, rho["A"])
        self.assertLess(rho["A"], rho["T"])
        self.assertLess(rho["T"], rho["H"])

    def test_config_contains_no_readiness_or_freeze_declaration(self) -> None:
        forbidden_key_fragments = (
            "freeze",
            "frozen",
            "promotion",
            "readiness",
            "run_ready",
            "paper_run_ready",
        )

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = key.lower()
                    self.assertFalse(
                        any(fragment in normalized for fragment in forbidden_key_fragments),
                        key,
                    )
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.config)


if __name__ == "__main__":
    unittest.main()
