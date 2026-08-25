from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from stage3_pipeline import benign_integrity_results as results
from stage3_pipeline.execution import TERMINAL_DISPOSITIONS
from stage3_pipeline.statistics import retained_bootstrap


def _fixture() -> tuple[SimpleNamespace, list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    prompts = [f"prompt-{index:02d}" for index in range(30)]
    vectors = [f"vector-{index:02d}" for index in range(20)]
    t_rows: list[dict[str, object]] = []
    clean_rows: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    dispositions: list[dict[str, object]] = []
    for prompt_index, prompt_id in enumerate(prompts):
        clean_id = f"clean-{prompt_index:02d}"
        clean_rows.append({"logical_id": clean_id, "identity": {"prompt_id": prompt_id}})
        responses.append({
            "logical_id": clean_id,
            "prompt_id": prompt_id,
            "label": "helpful",
            "judge_eligible": True,
        })
        dispositions.append({"logical_id": clean_id, "terminal_disposition": "COMPLETED_PARSED"})
        for vector_index, vector_id in enumerate(vectors):
            logical_id = f"steered-{prompt_index:02d}-{vector_index:02d}"
            t_rows.append({
                "logical_id": logical_id,
                "identity": {"prompt_id": prompt_id, "vector_id": vector_id},
            })
            responses.append({
                "logical_id": logical_id,
                "prompt_id": prompt_id,
                "vector_id": vector_id,
                "label": "broken" if vector_index == 0 else "helpful",
                "judge_eligible": True,
            })
            dispositions.append({"logical_id": logical_id, "terminal_disposition": "COMPLETED_PARSED"})
    # A terminal judge failure makes this prompt incomplete without inventing a label.
    failed_id = "steered-05-07"
    responses[[r["logical_id"] for r in responses].index(failed_id)].update(
        {"label": None, "judge_eligible": False}
    )
    dispositions[[r["logical_id"] for r in dispositions].index(failed_id)][
        "terminal_disposition"
    ] = "TERMINAL_JUDGE_FAILURE"
    prepared = SimpleNamespace(
        benign_T_rows=tuple(t_rows),
        benign_clean_rows=tuple(clean_rows),
        support=SimpleNamespace(
            plan_inputs={"benign_prompt_ids": prompts},
            vector_ids_by_index={index + 10: vector_id for index, vector_id in enumerate(vectors)},
            registry=SimpleNamespace(manifest=lambda: {"registry_sha256": "a" * 64}),
        ),
        config={"support_run_path": "support", "p1_dose_binding_path": "dose"},
        p1_result={"dose_binding": {}},
        support_validation={"ledger": {}},
    )
    reconciliation = {
        "canonical_plan_count": 5580,
        "canonical_registry_sha256": "a" * 64,
        "benign_identity_count": 630,
        "terminal_partition": {terminal: 0 for terminal in TERMINAL_DISPOSITIONS},
    }
    reconciliation["terminal_partition"]["COMPLETED_PARSED"] = 629
    reconciliation["terminal_partition"]["TERMINAL_JUDGE_FAILURE"] = 1
    loaded = SimpleNamespace(
        run_directory=Path("/tmp/benign-integrity-qwen25-paper-recovery-20260825T102609Z"),
        responses=tuple(responses),
        dispositions=tuple(dispositions),
        generations=tuple({"logical_id": row["logical_id"], "generation_completed": True} for row in (*t_rows, *clean_rows)),
        ledger={},
        execution_identity={},
        file_sha256={},
    )
    validated = SimpleNamespace(prepared=prepared, loaded=loaded, reconciliation=reconciliation)
    return validated, t_rows, clean_rows, responses


class BenignIntegrityResultTests(unittest.TestCase):
    def test_complete_case_exclusion_fixed_order_and_no_imputation(self) -> None:
        validated, t_rows, clean_rows, responses = _fixture()
        dispositions = [
            {"logical_id": row["logical_id"], "terminal_disposition": "COMPLETED_PARSED"}
            for row in [*t_rows, *clean_rows]
        ]
        failed = next(item for item in dispositions if item["logical_id"] == "steered-05-07")
        failed["terminal_disposition"] = "TERMINAL_JUDGE_FAILURE"
        payload = results.build_benign_broken_payload(
            t_rows,
            clean_rows,
            responses,
            dispositions,
            expected_prompt_ids=validated.prepared.support.plan_inputs["benign_prompt_ids"],
            expected_vector_ids=list(validated.prepared.support.vector_ids_by_index.values()),
        )
        self.assertEqual(len(payload["complete_prompt_frame"]), 29)
        self.assertEqual(
            [item["position"] for item in payload["complete_prompt_frame"]],
            list(range(29)),
        )
        self.assertEqual(
            [item["prompt_id"] for item in payload["complete_prompt_frame"]],
            [f"prompt-{index:02d}" for index in range(30) if index != 5],
        )
        self.assertEqual(len(payload["vector_frame"]), 20)
        self.assertNotIn("prompt-05", {item["prompt_id"] for item in payload["prompts"]})
        response_ids = {
            response_id
            for prompt in payload["prompts"]
            for response_id in [prompt["clean"]["response_id"], *(row["response_id"] for row in prompt["steered"])]
        }
        self.assertTrue(all(not response_id.startswith(("clean-05", "steered-05-")) for response_id in response_ids))
        self.assertTrue(all(row["label"] in results.BENIGN_LABELS for prompt in payload["prompts"] for row in [prompt["clean"], *prompt["steered"]]))

    def test_payload_preserves_twenty_vector_average_and_prompt_rd_inputs(self) -> None:
        validated, t_rows, clean_rows, responses = _fixture()
        dispositions = [
            {"logical_id": row["logical_id"], "terminal_disposition": "COMPLETED_PARSED"}
            for row in [*t_rows, *clean_rows]
        ]
        payload = results.build_benign_broken_payload(t_rows, clean_rows, responses, dispositions)
        prompt = payload["prompts"][0]
        self.assertEqual(len(prompt["steered"]), 20)
        vector_average = sum(row["label"] == "broken" for row in prompt["steered"]) / 20
        clean_broken = prompt["clean"]["label"] == "broken"
        self.assertEqual(vector_average - clean_broken, 0.05)
        self.assertEqual(payload["prompts"][0]["steered"][0]["vector_id"], "vector-00")

    def test_statistics_function_is_production_and_non_estimable_error_is_preserved(self) -> None:
        validated, *_ = _fixture()
        calls: list[tuple[dict[str, object], bool]] = []

        def statistic(payload: dict[str, object], *, fixture_mode: bool) -> dict[str, object]:
            calls.append((payload, fixture_mode))
            return {"replicates_requested": 10000, "replicates_required": 9500}

        assembled = results.assemble_benign_integrity_result(validated, statistics_function=statistic)
        self.assertFalse(calls[0][1])
        self.assertFalse(calls[0][0]["synthetic_data"])
        self.assertEqual(assembled["statistics_contract"]["function"], "analyze_benign_broken")
        self.assertEqual(assembled["statistics"]["replicates_requested"], 10000)
        error = retained_bootstrap.RetainedBootstrapError("INSUFFICIENT_RESAMPLING_UNITS", "fixture")
        non_estimable = results.assemble_benign_integrity_result(
            validated, statistics_function=mock.Mock(side_effect=error)
        )
        self.assertEqual(non_estimable["status"], "NON_ESTIMABLE")
        self.assertEqual(non_estimable["statistics_error"]["report_status"], error.report_status)

    def test_validate_only_does_not_call_statistics_or_write(self) -> None:
        validated, *_ = _fixture()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            output = Path(directory) / "output"
            with (
                mock.patch.object(results, "load_and_reconcile_benign_integrity_run", return_value=validated),
                mock.patch.object(results, "assemble_benign_integrity_result") as assemble,
                mock.patch.object(retained_bootstrap, "analyze_benign_broken") as analyze,
            ):
                summary = results.validate_only(source, output)
            self.assertFalse(output.exists())
            self.assertFalse(assemble.called)
            self.assertFalse(analyze.called)
            self.assertFalse(summary["statistics_executed"])

    def test_destination_source_child_and_repeat_materialization_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            with self.assertRaises(results.BenignIntegrityResultInputInvalid):
                results.check_output_destination(source, source / "nested")
            existing = Path(directory) / "existing"
            existing.mkdir()
            with self.assertRaises(results.BenignIntegrityResultInputInvalid):
                results.check_output_destination(source, existing)

        validated, *_ = _fixture()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "materialized"
            with mock.patch.object(results, "load_and_reconcile_benign_integrity_run", return_value=validated):
                results.materialize_benign_integrity_results_directory(
                    Path("/tmp/source"), output,
                    statistics_function=lambda payload, fixture_mode: {"ok": True},
                )
                with self.assertRaises(results.BenignIntegrityResultInputInvalid):
                    results.materialize_benign_integrity_results_directory(
                        Path("/tmp/source"), output,
                        statistics_function=lambda payload, fixture_mode: {"ok": True},
                    )
            self.assertEqual({item.name for item in output.iterdir()}, {results.OUTPUT_FILENAME})

    def test_duplicate_identity_and_lineage_tampering_fail_closed(self) -> None:
        validated, t_rows, clean_rows, responses = _fixture()
        dispositions = [
            {"logical_id": row["logical_id"], "terminal_disposition": "COMPLETED_PARSED"}
            for row in [*t_rows, *clean_rows]
        ]
        duplicate = copy.deepcopy(responses)
        duplicate.append(copy.deepcopy(duplicate[0]))
        with self.assertRaises(results.BenignIntegrityResultInputInvalid):
            results.build_benign_broken_payload(t_rows, clean_rows, duplicate, dispositions)
        tampered = copy.deepcopy(dispositions)
        tampered[0]["logical_id"] = "forged"
        with self.assertRaises(results.BenignIntegrityResultInputInvalid):
            results.build_benign_broken_payload(t_rows, clean_rows, responses, tampered)


if __name__ == "__main__":
    unittest.main()
