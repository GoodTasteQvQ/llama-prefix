from __future__ import annotations

import copy
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from stage3_pipeline import p2_results
from stage3_pipeline import p2_independent_results as results


def _fixture() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    labels = {
        "P2_T_all": ("unsafe", "safe"),
        "P2_T_content": ("safe", "unsafe"),
        "P2_H_all": ("broken", "safe"),
        "P2_H_content": ("safe", "broken"),
    }
    specs = {
        "P2_T_all": ("T", "mu_all_tw", "all-token"),
        "P2_T_content": ("T", "mu_content_tw", "content-token"),
        "P2_H_all": ("H", "mu_all_tw", "all-token"),
        "P2_H_content": ("H", "mu_content_tw", "content-token"),
    }
    for cell, (anchor, estimator, arm) in specs.items():
        for index, prompt_id in enumerate(("p01", "p02")):
            logical_id = f"id-{cell}-{prompt_id}-v01"
            rows.append({
                "logical_id": logical_id,
                "identity": {
                    "block": cell,
                    "anchor": anchor,
                    "estimator": estimator,
                    "prompt_id": prompt_id,
                    "vector_id": "v01",
                },
            })
            responses.append({
                "logical_id": logical_id,
                "cell": cell,
                "anchor": anchor,
                "estimator": estimator,
                "arm": arm,
                "prompt_id": prompt_id,
                "vector_id": "v01",
                "pair_id": f"{anchor}|{prompt_id}|v01",
                "terminal_status": "COMPLETED_PARSED",
                "retained": True,
                "label": labels[cell][index],
                "identity_sha256": f"identity-{logical_id}",
                "generation_record_sha256": f"generation-{logical_id}",
                "judge_record_sha256": f"judge-{logical_id}",
                "record_sha256": f"response-{logical_id}",
                "missingness_code": None,
            })
    responses.reverse()
    return rows, responses


class IndependentP2ResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows, self.responses = _fixture()

    def test_four_cells_identity_pairing_and_fixed_endpoint_order(self) -> None:
        frame = results.build_independent_raw_members(
            self.rows, self.responses, expected_cell_count=2
        )
        self.assertEqual(
            frame["member_order"], ["P2-U(T)", "P2-B(H)"]
        )
        self.assertEqual(
            frame["endpoint_order"], [dict(item) for item in results.ENDPOINT_ORDER]
        )
        self.assertEqual(
            {cell: frame["cell_counts"][cell]["scheduled_record_count"] for cell in frame["cell_counts"]},
            {"P2_T_all": 2, "P2_T_content": 2, "P2_H_all": 2, "P2_H_content": 2},
        )
        self.assertEqual(frame["matched_counts"], {"M_T": 2, "M_H": 2})

    def test_t_h_pairing_uses_identity_not_array_position(self) -> None:
        frame = results.build_independent_raw_members(
            self.rows, self.responses, expected_cell_count=2
        )
        t_records, h_records = frame["members"][0]["records"], frame["members"][1]["records"]
        self.assertEqual([item["pair_id"] for item in t_records], ["T|p01|v01", "T|p02|v01"])
        self.assertEqual([item["difference"] for item in t_records], [1, -1])
        self.assertEqual([item["difference"] for item in h_records], [1, -1])
        self.assertEqual(t_records[0]["arms"]["all"]["logical_id"], "id-P2_T_all-p01-v01")
        self.assertEqual(t_records[0]["arms"]["content"]["logical_id"], "id-P2_T_content-p01-v01")
        self.assertEqual(t_records[0]["arms"]["all"]["identity_sha256"], "identity-id-P2_T_all-p01-v01")

    def test_terminal_failures_are_missing_not_broken(self) -> None:
        responses = copy.deepcopy(self.responses)
        failed = next(item for item in responses if item["logical_id"] == "id-P2_T_all-p01-v01")
        failed.update({"terminal_status": "TERMINAL_JUDGE_FAILURE", "retained": False, "label": None, "missingness_code": "TERMINAL_JUDGE_FAILURE"})
        frame = results.build_independent_raw_members(self.rows, responses, expected_cell_count=2)
        member = frame["members"][0]
        self.assertEqual((member["matched_pair_count"], member["missing_pair_count"]), (1, 1))
        self.assertEqual(member["missing_pairs"][0]["pair_id"], "T|p01|v01")
        self.assertFalse(any(item["pair_id"] == "T|p01|v01" for item in member["records"]))
        self.assertEqual(frame["matched_counts"]["M_T"], 1)

    def test_incomplete_pair_and_duplicate_or_mismatched_ids_fail_closed(self) -> None:
        rows = copy.deepcopy(self.rows)
        next(item for item in rows if item["logical_id"] == "id-P2_T_content-p01-v01")["identity"]["prompt_id"] = "orphan"
        with self.assertRaisesRegex(results.P2IndependentResultInputInvalid, "INCOMPLETE_CANONICAL_PAIRING"):
            results.build_independent_raw_members(rows, self.responses, expected_cell_count=2)

        duplicate = self.responses + [copy.deepcopy(self.responses[0])]
        with self.assertRaisesRegex(results.P2IndependentResultInputInvalid, "DUPLICATE_RESPONSE_LOGICAL_ID"):
            results.build_independent_raw_members(self.rows, duplicate, expected_cell_count=2)

        mismatched = copy.deepcopy(self.responses)
        mismatched[0]["anchor"] = "A"
        with self.assertRaisesRegex(results.P2IndependentResultInputInvalid, "RESPONSE_IDENTITY_MISMATCH"):
            results.build_independent_raw_members(self.rows, mismatched, expected_cell_count=2)

    def test_invalid_binary_outcome_or_difference_fails_immediately(self) -> None:
        with self.assertRaisesRegex(results.P2IndependentResultInputInvalid, "INVALID_BINARY_OUTCOME"):
            results._paired_difference(2, 0, member_id="P2-U(T)", pair_id="T|p|v")
        responses = copy.deepcopy(self.responses)
        next(item for item in responses if item["logical_id"] == "id-P2_T_all-p01-v01")["label"] = "not-a-domain-label"
        with self.assertRaisesRegex(results.P2IndependentResultInputInvalid, "ANALYZABLE_RESPONSE_INVALID"):
            results.build_independent_raw_members(self.rows, responses, expected_cell_count=2)

    def test_output_directory_non_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            output = root / "output"
            output.mkdir()
            with self.assertRaisesRegex(results.P2IndependentResultInputInvalid, "OUTPUT_DIRECTORY_EXISTS"):
                results._check_output_destination(source, output)
            with self.assertRaisesRegex(results.P2IndependentResultInputInvalid, "OUTPUT_DIRECTORY_INSIDE_SOURCE_RUN"):
                results._check_output_destination(source, source / "nested")

    def test_validate_only_writes_nothing_and_runs_no_statistics(self) -> None:
        reconciliation = {
            "terminal_partition": dict(results.EXPECTED_TERMINAL_PARTITION),
        }
        validated = SimpleNamespace(
            prepared=SimpleNamespace(rows=tuple(self.rows)),
            loaded=SimpleNamespace(
                responses=tuple(self.responses),
                generations=(),
                judges=(),
                dispositions=(),
                run_directory=Path("/tmp/amended-run"),
            ),
            reconciliation=reconciliation,
        )
        frame = {"endpoint_order": [dict(item) for item in results.ENDPOINT_ORDER], "matched_counts": {"M_T": 2, "M_H": 2}}
        with mock.patch.object(results, "validate_independent_run", return_value=validated), mock.patch.object(
            results, "build_independent_raw_members", return_value=frame
        ):
            summary = results.validate_only(Path("/tmp/amended-run"), prepared=SimpleNamespace())
        self.assertTrue(summary["statistics_not_run"])
        self.assertFalse(summary["output_written"])
        self.assertEqual(summary["M_T"], 2)
        self.assertEqual(summary["M_H"], 2)

    def test_old_p2_materializer_contract_remains_available(self) -> None:
        self.assertEqual(p2_results.OUTPUT_FILENAME, "p2_raw_result.json")
        self.assertEqual(p2_results._MEMBER_SPECS[0]["member_id"], "P2-U(A)")
        self.assertEqual(p2_results._MEMBER_SPECS[1]["member_id"], "P2-B(T)")

    def test_cli_requires_both_explicit_directories(self) -> None:
        cli = importlib.import_module("scripts.stage3_production.materialize_p2_independent_results")
        with self.assertRaises(SystemExit):
            cli._parser().parse_args(["--run-directory", "/tmp/source"])


if __name__ == "__main__":
    unittest.main()
