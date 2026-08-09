from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts.stage3_production import materialize_k1_results as cli
from stage3_pipeline import k1_results
from stage3_pipeline.core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    GenerationProducer,
    LogicalIdentityRegistry,
    parse_judge_with_retry,
)
from stage3_pipeline.dose import build_call_dose_evidence
from stage3_pipeline.records import build_block_response_record
from stage3_pipeline.statistics import retained_bootstrap
from tests.stage3.helpers import (
    ROOT,
    block_identity,
    json_label,
    test_dose_binding,
)


FIXTURE_DIRECTORY = ROOT / "tests/stage3/fixtures/retained_bootstrap"
TEMP_ROOT = ROOT / ".codex-temp"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIRECTORY / name).read_text(encoding="utf-8"))


def _raw_members(
    m_a: list[tuple[str, str]], m_t: list[tuple[str, str]]
) -> list[dict[str, object]]:
    result = []
    for matched_set, member_id, coordinates in (
        ("M_A", "P2-U(A)", m_a),
        ("M_T", "P2-B(T)", m_t),
    ):
        result.append(
            {
                "member_id": member_id,
                "matched_set": matched_set,
                "matched_pair_count": len(coordinates),
                "records": [
                    {"prompt_id": prompt_id, "vector_id": vector_id}
                    for prompt_id, vector_id in coordinates
                ],
            }
        )
    return result


def _lineage_fixture() -> dict[str, object]:
    registry = LogicalIdentityRegistry()
    rows: list[dict[str, object]] = []
    generations: list[dict[str, object]] = []
    judges: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    coordinates = [("p01", "v01"), ("p02", "v02")]
    labels = {
        "P2_A_all": ("broken", "unsafe"),
        "P2_A_content": ("refusal", "safe"),
        "P2_T_all": ("unsafe", "broken"),
        "P2_T_content": ("safe", "refusal"),
    }
    for cell in k1_results.CELL_ORDER:
        for coordinate_index, (prompt_id, vector_id) in enumerate(coordinates):
            identity = block_identity(cell, prompt_id, vector_id=vector_id)
            logical_id = registry.register(identity)
            dose_evidence = build_call_dose_evidence(
                identity=identity,
                dose_binding=test_dose_binding(),
                generation_status="COMPLETED",
                pre_hook_l2=2.0,
                post_hook_l2=2.1,
                vector_alignment=0.5,
                cosine_drift=0.1,
            )
            generation = GenerationProducer(
                registry,
                lambda _identity, _request, evidence=dose_evidence: {
                    "output_text": "fake output",
                    "diagnostics": {},
                    "dose_evidence": evidence,
                },
                run_mode="smoke",
                fake_backend=True,
            ).produce(
                logical_id,
                {"logical_id": logical_id, "generation_config": DECODE_CONFIG},
            )
            label = labels[cell][coordinate_index]
            judge = parse_judge_with_retry(
                logical_id,
                lambda _attempt, _request, value=label: json_label(value),
                {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
                registry=registry,
                generation_record=generation,
                run_mode="smoke",
                judge_identity={
                    "model_path_or_id": "fake-judge",
                    "tokenizer_path_or_id": "fake-tokenizer",
                    "rubric_sha256": "1" * 64,
                },
                fake_backend=True,
            )
            response = build_block_response_record(
                identity=identity,
                generation_record=generation,
                judge_record=judge,
                dose_evidence=dose_evidence,
            )
            rows.append({"logical_id": logical_id, "identity": identity})
            generations.append(generation)
            judges.append(judge)
            responses.append(response)
    return {
        "registry": registry,
        "rows": rows,
        "generations": generations,
        "judges": judges,
        "responses": responses,
        "coordinates": coordinates,
    }


def _build_profile(
    fixture: dict[str, object], coordinates: list[tuple[str, str]] | None = None
) -> dict[str, object]:
    return k1_results.build_k1_matched_profile(
        canonical_rows=fixture["rows"],
        response_records=fixture["responses"],
        generation_records=fixture["generations"],
        judge_records=fixture["judges"],
        registry=fixture["registry"],
        dose_binding=test_dose_binding(),
        prompt_ids=["p01", "p02"],
        vector_ids=["v01", "v02"],
        matched_coordinates=fixture["coordinates"] if coordinates is None else coordinates,
    )


class K1ResultTests(unittest.TestCase):
    def test_intersection_is_computed_by_prompt_and_vector_identity(self) -> None:
        members = _raw_members(
            [("p02", "v02"), ("p01", "v01"), ("p01", "v02")],
            [("p02", "v01"), ("p01", "v02"), ("p02", "v02")],
        )
        members.reverse()
        result = k1_results.derive_matched_coordinates(
            members,
            prompt_ids=["p01", "p02"],
            vector_ids=["v01", "v02"],
        )
        self.assertEqual(result["M_A_count"], 3)
        self.assertEqual(result["M_T_count"], 3)
        self.assertEqual(result["intersection_count"], 2)
        self.assertEqual(
            result["intersection_coordinates"],
            [("p01", "v02"), ("p02", "v02")],
        )

    def test_terminal_failure_coordinate_is_excluded_without_a_label(self) -> None:
        fixture = _lineage_fixture()
        failed = next(
            record
            for record in fixture["responses"]
            if record["cell"] == "P2_T_content" and record["prompt_id"] == "p02"
        )
        failed.update(
            {
                "judge_label_parsed": False,
                "judge_terminal_status": "TERMINAL_PARSE_OR_INFRASTRUCTURE_FAILURE",
                "label": None,
                "terminal_status": "TERMINAL_JUDGE_FAILURE",
                "missingness_code": "TERMINAL_JUDGE_FAILURE",
                "retained": False,
            }
        )
        members = _raw_members(
            [("p01", "v01"), ("p02", "v02")], [("p01", "v01")]
        )
        matched = k1_results.derive_matched_coordinates(
            members,
            prompt_ids=["p01", "p02"],
            vector_ids=["v01", "v02"],
        )
        profile = _build_profile(fixture, matched["intersection_coordinates"])
        self.assertEqual(matched["intersection_count"], 1)
        self.assertEqual(len(profile["k1_reuse_records"]), 4)
        self.assertFalse(
            any(record["prompt_id"] == "p02" for record in profile["k1_reuse_records"])
        )
        self.assertTrue(all(record["label"] is not None for record in profile["k1_reuse_records"]))

    def test_four_cells_reuse_exact_validated_source_lineage(self) -> None:
        fixture = _lineage_fixture()
        profile = _build_profile(fixture)
        source_by_id = {record["logical_id"]: record for record in fixture["responses"]}
        self.assertEqual(profile["cell_order"], list(k1_results.CELL_ORDER))
        self.assertEqual(len(profile["k1_reuse_records"]), 8)
        for record in profile["k1_reuse_records"]:
            source = source_by_id[record["logical_id"]]
            self.assertEqual(record["source_p2_logical_id"], source["logical_id"])
            self.assertEqual(record["source_p2_record_sha256"], source["record_sha256"])
            self.assertEqual(record["identity_sha256"], source["identity_sha256"])
            self.assertEqual(record["label"], source["label"])
            self.assertEqual(record["generation_calls_added"], 0)
            self.assertEqual(record["judge_calls_added"], 0)

    def test_analyze_k1_accepts_shared_sparse_matched_subset(self) -> None:
        payload = copy.deepcopy(_load("success_golden_input.json")["k1"])
        for cell in payload["cells"]:
            cell["records"].pop()
        result = retained_bootstrap.analyze_k1(payload, fixture_mode=True)
        self.assertEqual(result["status"], "ESTIMABLE")
        self.assertEqual(result["replicates_requested"], 10_000)
        self.assertGreaterEqual(result["replicates_successful"], 9_500)

    def test_analyze_k1_rejects_mismatched_duplicate_outside_and_noncanonical(self) -> None:
        base = _load("success_golden_input.json")["k1"]

        mismatched = copy.deepcopy(base)
        mismatched["cells"][1]["records"].pop()
        with self.assertRaisesRegex(
            retained_bootstrap.RetainedBootstrapError, "shared K1 matched subset"
        ):
            retained_bootstrap.analyze_k1(mismatched, fixture_mode=True)

        duplicate = copy.deepcopy(base)
        repeated = copy.deepcopy(duplicate["cells"][0]["records"][0])
        repeated["row_id"] = "unique-row-id-for-duplicate-coordinate"
        duplicate["cells"][0]["records"].append(repeated)
        with self.assertRaisesRegex(
            retained_bootstrap.RetainedBootstrapError, "duplicate K1 cell/prompt/vector"
        ):
            retained_bootstrap.analyze_k1(duplicate, fixture_mode=True)

        outside = copy.deepcopy(base)
        outside["cells"][0]["records"][0]["prompt_id"] = "outside-frame"
        with self.assertRaisesRegex(
            retained_bootstrap.RetainedBootstrapError, "outside fixed frame"
        ):
            retained_bootstrap.analyze_k1(outside, fixture_mode=True)

        noncanonical = copy.deepcopy(base)
        records = noncanonical["cells"][0]["records"]
        records[0], records[1] = records[1], records[0]
        with self.assertRaisesRegex(
            retained_bootstrap.RetainedBootstrapError, "rows are not canonical"
        ):
            retained_bootstrap.analyze_k1(noncanonical, fixture_mode=True)

    def test_existing_complete_k1_golden_is_unchanged(self) -> None:
        success = _load("success_golden_input.json")
        expected = _load("success_golden_expected.json")
        actual = retained_bootstrap.evaluate_success_fixture(success)
        self.assertEqual(actual["k1"], expected["k1"])

    def test_assembly_reports_zero_calls_and_descriptive_scope(self) -> None:
        fixture = _lineage_fixture()
        profile = _build_profile(fixture)
        profile["matched_counts"] = {
            "M_A_count": 2,
            "M_T_count": 2,
            "intersection_count": 2,
            "intersection_coordinates": fixture["coordinates"],
        }
        raw_path = Path("/accepted/p2_raw_result.json")
        validated = k1_results.ValidatedK1Inputs(
            p2_run_directory=Path("/accepted/p2-run"),
            p2_raw_result_path=raw_path,
            p2_raw_result_sha256="a" * 64,
            prepared=SimpleNamespace(),
            loaded=SimpleNamespace(execution_identity={"run_id": "p2-run"}),
            reconciliation={},
            p2_raw_result={
                "schema_version": k1_results.p2_results.SCHEMA_VERSION,
                "cell_counts": {cell: {"scheduled_record_count": 2} for cell in k1_results.CELL_ORDER},
            },
            profile=profile,
        )
        calls: list[tuple[object, bool]] = []

        def fake_statistic(payload: object, *, fixture_mode: bool) -> dict[str, object]:
            calls.append((payload, fixture_mode))
            return {"status": "ESTIMABLE", "replicates_requested": 10_000}

        result = k1_results.assemble_k1_result(
            validated, statistics_function=fake_statistic
        )
        self.assertEqual(calls, [(profile["statistics_input"], False)])
        self.assertEqual(result["generation_calls_added"], 0)
        self.assertEqual(result["judge_calls_added"], 0)
        self.assertEqual(result["k1_reuse_record_count"], 8)
        self.assertIn("descriptive_only", result["scope"]["inferential_claim"])
        self.assertEqual(result["statistics_contract"]["replicates"], 10_000)
        self.assertEqual(result["statistics_contract"]["min_success"], 9_500)

    def test_materializer_creates_once_and_refuses_overwrite(self) -> None:
        fixture = _lineage_fixture()
        profile = _build_profile(fixture)
        profile["matched_counts"] = {
            "M_A_count": 2,
            "M_T_count": 2,
            "intersection_count": 2,
            "intersection_coordinates": fixture["coordinates"],
        }
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            p2_run = root / "p2-run"
            raw_directory = root / "p2-raw"
            raw_path = raw_directory / "p2_raw_result.json"
            p2_run.mkdir()
            raw_directory.mkdir()
            raw_path.write_text("{}\n", encoding="utf-8")
            output = root / "k1-output"
            validated = k1_results.ValidatedK1Inputs(
                p2_run_directory=p2_run,
                p2_raw_result_path=raw_path,
                p2_raw_result_sha256="a" * 64,
                prepared=SimpleNamespace(),
                loaded=SimpleNamespace(execution_identity={"run_id": "p2-run"}),
                reconciliation={},
                p2_raw_result={
                    "schema_version": k1_results.p2_results.SCHEMA_VERSION,
                    "cell_counts": {cell: {} for cell in k1_results.CELL_ORDER},
                },
                profile=profile,
            )
            with mock.patch.object(
                k1_results, "validate_k1_results_inputs", return_value=validated
            ):
                result = k1_results.materialize_k1_results_directory(
                    p2_run,
                    raw_path,
                    output,
                    statistics_function=lambda _payload, fixture_mode: {"status": "ESTIMABLE"},
                )
            self.assertEqual(result["status"], "ESTIMABLE")
            self.assertTrue((output / k1_results.OUTPUT_FILENAME).is_file())
            with self.assertRaisesRegex(
                k1_results.K1ResultInputInvalid, "OUTPUT_DIRECTORY_EXISTS"
            ):
                k1_results.materialize_k1_results_directory(
                    p2_run, raw_path, output, statistics_function=mock.Mock()
                )

    def test_validate_only_does_not_run_statistics_or_write(self) -> None:
        summary = {
            "status": "VALIDATED_ONLY",
            "M_A": 974,
            "M_T": 976,
            "M_A_intersection_M_T": 951,
            "statistics_executed": False,
            "output_written": False,
        }
        with (
            mock.patch.object(cli, "validate_k1_results_inputs", return_value=mock.sentinel.validated),
            mock.patch.object(cli, "validation_summary", return_value=summary),
            mock.patch.object(cli, "materialize_k1_results_directory") as materialize,
            mock.patch.object(k1_results.retained_bootstrap, "analyze_k1") as analyze,
            mock.patch("builtins.print"),
        ):
            status = cli.main(
                [
                    "--p2-run-directory",
                    "/explicit/p2-run",
                    "--p2-raw-result",
                    "/explicit/p2-raw/p2_raw_result.json",
                    "--output-directory",
                    "/explicit/k1-output",
                    "--validate-only",
                ]
            )
        self.assertEqual(status, 0)
        materialize.assert_not_called()
        analyze.assert_not_called()


if __name__ == "__main__":
    unittest.main()
