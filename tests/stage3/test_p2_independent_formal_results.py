from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stage3_pipeline import p2_independent_formal_results as formal
from stage3_pipeline.statistics import reference_statistics


def _synthetic_raw() -> dict[str, object]:
    cells = {}
    cell_completed = {
        "P2_T_all": 986,
        "P2_T_content": 990,
        "P2_H_all": 975,
        "P2_H_content": 991,
    }
    for cell, completed in cell_completed.items():
        failure = 1000 - completed
        cells[cell] = {
            "scheduled_record_count": 1000,
            "completed_parsed_record_count": completed,
            "terminal_failure_record_count": failure,
            "matched_record_count": 976 if cell.startswith("P2_T") else 966,
            "excluded_record_count": 24 if cell.startswith("P2_T") else 34,
            "terminal_status_counts": {
                "COMPLETED_PARSED": completed,
                "NON_ESTIMABLE_DOSE": 0,
                "NON_ESTIMABLE_IDENTITY": 0,
                "TERMINAL_GENERATION_DETERMINISTIC_FAILURE": 0,
                "TERMINAL_GENERATION_INDETERMINATE_FAILURE": 0,
                "TERMINAL_GENERATION_TECHNICAL_FAILURE": 0,
                "TERMINAL_JUDGE_FAILURE": failure,
                "TERMINAL_JUDGE_INDETERMINATE_FAILURE": 0,
                "TERMINAL_PREJUDGE_FAILURE": 0,
            },
        }

    members = []
    for endpoint, matched in zip(formal.EXPECTED_ENDPOINT_ORDER, (976, 966)):
        records = []
        missing = []
        for index in range(1000):
            prompt_id = f"p{index // 20:02d}"
            vector_id = f"v{index % 20:02d}"
            pair_id = f"{endpoint['anchor']}|{prompt_id}|{vector_id}"
            if index < matched:
                all_value = index % 2
                content_value = (index + 1) % 2 if index % 5 == 0 else all_value
                records.append(
                    {
                        "pair_id": pair_id,
                        "prompt_id": prompt_id,
                        "vector_id": vector_id,
                        "anchor": endpoint["anchor"],
                        "outcome": endpoint["outcome"],
                        "all_value": all_value,
                        "content_value": content_value,
                        "difference": all_value - content_value,
                    }
                )
            else:
                missing.append(
                    {
                        "pair_id": pair_id,
                        "prompt_id": prompt_id,
                        "vector_id": vector_id,
                        "anchor": endpoint["anchor"],
                        "arms": {
                            "all": {"terminal_status": "TERMINAL_JUDGE_FAILURE"},
                            "content": {"terminal_status": "COMPLETED_PARSED"},
                        },
                    }
                )
        members.append(
            {
                **{field: endpoint[field] for field in (
                    "member_id", "matched_set", "anchor", "outcome", "all_cell", "content_cell"
                )},
                "scheduled_pair_count": 1000,
                "matched_pair_count": matched,
                "missing_pair_count": 1000 - matched,
                "records": records,
                "missing_pairs": missing,
            }
        )
    return {
        "schema_version": formal.RAW_RESULT_SCHEMA_VERSION,
        "status": "RAW_MEMBERS_READY",
        "amendment_id": formal.AMENDMENT_ID,
        "endpoint_order": copy.deepcopy(formal.EXPECTED_ENDPOINT_ORDER),
        "member_order": list(formal.MEMBER_ORDER),
        "identity_count": 4000,
        "cell_identity_counts": dict(formal.EXPECTED_CELL_COUNTS),
        "cell_counts": cells,
        "terminal_partition": dict(formal.EXPECTED_TERMINAL_PARTITION),
        "M_T": 976,
        "M_H": 966,
        "members": members,
        "source_run_id": formal.SOURCE_RUN_ID,
        "paper_result_eligible": False,
        "formal_experiment_run": True,
        "fake_backend": False,
        "statistics_not_run": True,
        "amended_independent": True,
        "estimation_only": True,
        "scope": "amended_independent_estimation_only",
        "old_p2_run": False,
        "old_p2_unchanged": True,
        "generation_calls_added": 0,
        "judge_calls_added": 0,
        "source": {"run_id": formal.SOURCE_RUN_ID},
    }


class P2IndependentFormalResultTests(unittest.TestCase):
    def test_t_h_order_and_result_keys_with_injected_statistic(self) -> None:
        raw = _synthetic_raw()
        observed: list[object] = []

        def fake_statistic(members, *, replicates, min_success, member_order):
            observed.append((members, replicates, min_success, member_order))
            return {
                "algorithm": "synthetic",
                "member_order": member_order,
                "replicates_requested": replicates,
                "replicates_successful": replicates,
                "replicates_required": min_success,
                "critical_value_nearest_rank_0_95": 2.1,
                "intervals": {
                    "P2-U(T)": {"point": 0.1, "se": 0.2, "simultaneous_95": [-0.3, 0.5]},
                    "P2-B(H)": {"point": -0.1, "se": 0.3, "simultaneous_95": [-0.8, 0.6]},
                },
            }

        result = formal.assemble_formal_result(
            raw,
            {"formal_supplement": {"status": formal.FORMAL_SUPPLEMENT_STATUS}},
            statistics_function=fake_statistic,
        )
        self.assertEqual(result["member_order"], ["P2-U(T)", "P2-B(H)"])
        self.assertEqual(list(result["statistics"]["intervals"]), ["P2-U(T)", "P2-B(H)"])
        self.assertEqual(
            list(result["endpoint_results"]), ["P2-U(T)", "P2-B(H)"]
        )
        self.assertEqual(
            set(result["endpoint_results"]["P2-U(T)"]),
            {"point_estimate", "two_way_cr1_se", "simultaneous_95"},
        )
        self.assertEqual(result["replicates_requested"], 9999)
        self.assertEqual(observed[0][1:], (9999, 9500, ["P2-U(T)", "P2-B(H)"]))
        self.assertEqual([len(item["records"]) for item in observed[0][0]], [976, 966])

    def test_default_old_p2_member_order_is_byte_for_byte_compatible(self) -> None:
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/statistics/statistical_golden_input.json").read_text()
        )
        members = fixture["p2"]["members"]
        implicit = reference_statistics.p2_raw_simultaneous(
            members, replicates=20, min_success=19
        )
        explicit = reference_statistics.p2_raw_simultaneous(
            members, replicates=20, min_success=19,
            member_order=["P2-U(A)", "P2-B(T)"],
        )
        self.assertEqual(implicit, explicit)
        self.assertEqual(implicit["member_order"], ["P2-U(A)", "P2-B(T)"])

    def test_missing_pairs_are_not_passed_to_statistic(self) -> None:
        raw = _synthetic_raw()
        observed = []

        def fake_statistic(members, **kwargs):
            observed.append(members)
            return {"replicates_requested": kwargs["replicates"], "replicates_successful": 9999}

        formal.assemble_formal_result(raw, {"formal_supplement": {}}, statistics_function=fake_statistic)
        self.assertEqual([[len(item["records"]) for item in observed[0]]], [[976, 966]])
        self.assertTrue(all("missing_pairs" not in member for member in observed[0]))

    def test_bad_endpoint_matched_count_schema_and_existing_output_fail_closed(self) -> None:
        for mutation in ("endpoint_order", "M_T", "schema_version"):
            raw = _synthetic_raw()
            if mutation == "endpoint_order":
                raw["endpoint_order"] = list(reversed(raw["endpoint_order"]))
            elif mutation == "M_T":
                raw["M_T"] = 975
            else:
                raw["schema_version"] = "wrong"
            with self.subTest(mutation=mutation):
                with self.assertRaises(formal.P2IndependentFormalResultInvalid):
                    formal.validate_raw_result(raw)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.mkdir()
            with self.assertRaises(formal.P2IndependentFormalResultInvalid):
                formal.materialize_formal_results(
                    _raw_path_for_test(), output, statistics_function=lambda **_: {}
                )

    def test_validate_only_writes_nothing_and_does_not_call_statistic(self) -> None:
        raw_path = _raw_path_for_test()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-output"
            with mock.patch.object(
                reference_statistics,
                "p2_raw_simultaneous",
                side_effect=AssertionError("statistics must not run"),
            ):
                result = formal.validate_only(raw_path, output_directory=output)
            self.assertTrue(result["statistics_not_run"])
            self.assertFalse(output.exists())

    def test_non_estimable_status_and_reason_are_preserved(self) -> None:
        def non_estimable(*args, **kwargs):
            raise reference_statistics.NonEstimable("synthetic_non_estimable")

        result = formal.assemble_formal_result(
            _synthetic_raw(),
            {"formal_supplement": {"status": formal.FORMAL_SUPPLEMENT_STATUS}},
            statistics_function=non_estimable,
        )
        self.assertEqual(result["status"], "P2_STATISTICS_NON_ESTIMABLE")
        self.assertEqual(result["reason_detail"], "synthetic_non_estimable")
        self.assertIsNone(result["statistics"])
        self.assertEqual(result["endpoint_results"], {})


_TEMP_FIXTURE: Path | None = None


def _raw_path_for_test() -> Path:
    global _TEMP_FIXTURE
    if _TEMP_FIXTURE is None:
        directory = Path(tempfile.mkdtemp(prefix="p2-formal-fixture-"))
        _TEMP_FIXTURE = directory / "raw.json"
        _TEMP_FIXTURE.write_text(json.dumps(_synthetic_raw()), encoding="utf-8")
    return _TEMP_FIXTURE


if __name__ == "__main__":
    unittest.main()
