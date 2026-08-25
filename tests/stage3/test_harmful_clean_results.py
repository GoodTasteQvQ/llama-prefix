from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from activation_guard.metrics import compute_response_metrics

from stage3_pipeline import harmful_clean_results as results
from stage3_pipeline.core import canonical_sha256
from stage3_pipeline.execution import TERMINAL_DISPOSITIONS
from stage3_pipeline.statistics import retained_bootstrap


ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
for _variable in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
    os.environ.setdefault(_variable, "1")
for _variable in ("TMPDIR", "TEMP", "TMP"):
    os.environ[_variable] = str((ROOT / ".codex-temp").resolve())
(ROOT / ".codex-temp").mkdir(parents=True, exist_ok=True)


def _fixture() -> tuple[results.ValidatedHarmfulCleanRun, list[dict[str, object]]]:
    prompt_ids = [f"prompt-{index:02d}" for index in range(50)]
    rows = [
        {
            "logical_id": f"logical-{index:02d}",
            "identity": {"prompt_id": prompt_id},
        }
        for index, prompt_id in enumerate(prompt_ids)
    ]
    prepared = SimpleNamespace(
        clean_rows=tuple(rows),
        support=SimpleNamespace(
            plan_inputs={"confirm_prompt_ids": prompt_ids},
        ),
    )
    responses: list[dict[str, object]] = []
    dispositions: list[dict[str, object]] = []
    generations: list[dict[str, object]] = []
    labels = ("broken", "unsafe", "refusal", "safe")
    for index, row in enumerate(rows):
        logical_id = row["logical_id"]
        label = labels[index % len(labels)]
        terminal = "COMPLETED_PARSED" if index < 4 else "TERMINAL_JUDGE_FAILURE"
        response = {
            "logical_id": logical_id,
            "prompt_id": row["identity"]["prompt_id"],
            "label": label if terminal == "COMPLETED_PARSED" else None,
            "terminal_status": terminal,
        }
        responses.append(response)
        dispositions.append({
            "logical_id": logical_id,
            "terminal_disposition": terminal,
        })
        generations.append({
            "logical_id": logical_id,
            "generation_completed": True,
            "output_text": "short output repeated repeated repeated",
        })
    loaded = results.LoadedHarmfulCleanRun(
        run_directory=results.FORMAL_HARMFUL_CLEAN_RUN_DIRECTORY,
        identities=tuple(rows),
        generations=tuple(generations),
        judges=(),
        responses=tuple(responses),
        dispositions=tuple(dispositions),
        registry_reference={},
        ledger={},
        execution_identity={},
        file_sha256={},
    )
    validated = results.ValidatedHarmfulCleanRun(
        prepared=prepared,
        loaded=loaded,
        reconciliation={
            "canonical_plan_count": 5580,
            "canonical_registry_sha256": "a" * 64,
            "harmful_clean_identity_count": 50,
            "harmful_clean_identity_set_sha256": canonical_sha256(rows),
            "terminal_partition": {
                terminal: (46 if terminal == "TERMINAL_JUDGE_FAILURE" else 0)
                for terminal in TERMINAL_DISPOSITIONS
            },
        },
    )
    validated.reconciliation["terminal_partition"]["COMPLETED_PARSED"] = 4
    return validated, generations


class HarmfulCleanResultTests(unittest.TestCase):
    def test_prompt_order_and_terminal_missingness_stay_in_fixed_frame(self) -> None:
        validated, _ = _fixture()
        payload = results.build_harmful_clean_payload(
            validated.prepared.clean_rows,
            validated.loaded.responses,
            validated.loaded.dispositions,
        )
        self.assertEqual(
            [item["prompt_id"] for item in payload["prompt_frame"]],
            validated.prepared.support.plan_inputs["confirm_prompt_ids"],
        )
        self.assertEqual(len(payload["prompt_frame"]), 50)
        self.assertEqual(len(payload["records"]), 4)
        self.assertNotIn(
            validated.loaded.responses[4]["prompt_id"],
            {record["prompt_id"] for record in payload["records"]},
        )

    def test_label_counts_and_proportions_are_independently_recomputed(self) -> None:
        validated, _ = _fixture()
        result = results.assemble_harmful_clean_result(
            validated, statistics_function=lambda payload, fixture_mode: {"ok": True}
        )
        self.assertEqual(result["accounting"]["label_counts"], {
            "broken": 1, "unsafe": 1, "refusal": 1, "safe": 1,
        })
        self.assertEqual(result["accounting"]["retained_denominator"], 4)
        self.assertEqual(result["accounting"]["label_proportions"]["safe"], 0.25)

    def test_statistics_function_receives_production_payload(self) -> None:
        validated, _ = _fixture()
        calls: list[tuple[dict[str, object], bool]] = []

        def statistic(payload: dict[str, object], *, fixture_mode: bool) -> dict[str, object]:
            calls.append((payload, fixture_mode))
            return {"replicates_requested": 10_000, "replicates_required": 9_500}

        result = results.assemble_harmful_clean_result(
            validated, statistics_function=statistic
        )
        self.assertEqual(result["status"], "ESTIMABLE")
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0][1])
        self.assertEqual(calls[0][0]["synthetic_data"], False)
        self.assertEqual(len(calls[0][0]["prompt_frame"]), 50)

    def test_non_estimable_uses_existing_error_semantics_without_fallback(self) -> None:
        validated, _ = _fixture()
        error = retained_bootstrap.RetainedBootstrapError(
            "INSUFFICIENT_RESAMPLING_UNITS", "fixture"
        )
        result = results.assemble_harmful_clean_result(
            validated, statistics_function=mock.Mock(side_effect=error)
        )
        self.assertEqual(result["status"], "NON_ESTIMABLE")
        self.assertIsNone(result["statistics"])
        self.assertEqual(result["statistics_error"]["code"], "INSUFFICIENT_RESAMPLING_UNITS")
        self.assertEqual(result["statistics_error"]["report_status"], error.report_status)

    def test_generation_metrics_use_existing_arr_and_repetition_definitions(self) -> None:
        validated, generations = _fixture()
        metrics = results.compute_generation_metrics(generations[:2])
        expected = [compute_response_metrics(item["output_text"]) for item in generations[:2]]
        self.assertEqual(metrics["denominator"], 2)
        self.assertEqual(metrics["mean_arr"], sum(item["arr"] for item in expected) / 2)
        self.assertEqual(
            metrics["mean_3gram_repetition_rate"],
            sum(item["repetition_rate"] for item in expected) / 2,
        )
        self.assertEqual(
            metrics["arr_component_rates"]["repetition_gt_0_2"],
            sum(item["repetition_rate"] > 0.2 for item in expected) / 2,
        )

    def test_validate_only_does_not_run_statistics_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            validated, _ = _fixture()
            with (
                mock.patch.object(results, "check_output_destination"),
                mock.patch.object(results, "load_and_reconcile_harmful_clean_run", return_value=validated),
                mock.patch.object(results, "assemble_harmful_clean_result") as assemble,
                mock.patch.object(retained_bootstrap, "analyze_harmful_clean") as analyze,
            ):
                summary = results.validate_only(Path("fixed"), output)
            self.assertFalse(output.exists())
            self.assertFalse(assemble.called)
            self.assertFalse(analyze.called)
            self.assertFalse(summary["statistics_executed"])

    def test_materializer_writes_one_atomic_result_and_refuses_overwrite(self) -> None:
        validated, _ = _fixture()
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as directory:
            output = Path(directory) / "materialized"
            statistic = lambda payload, fixture_mode: {"status": "fixture"}
            with mock.patch.object(
                results,
                "load_and_reconcile_harmful_clean_run",
                return_value=validated,
            ) as load:
                materialized = results.materialize_harmful_clean_results_directory(
                    Path("source"), output, statistics_function=statistic
                )
                with self.assertRaises(results.HarmfulCleanResultInputInvalid):
                    results.materialize_harmful_clean_results_directory(
                        Path("source"), output, statistics_function=statistic
                    )
            self.assertEqual(load.call_count, 1)
            self.assertEqual(materialized["status"], "ESTIMABLE")
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {results.OUTPUT_FILENAME},
            )
            written = json.loads(
                (output / results.OUTPUT_FILENAME).read_text(encoding="utf-8")
            )
            self.assertEqual(written, materialized)

    def test_destination_and_nonfixed_input_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            output = source / "nested"
            source.mkdir()
            with self.assertRaises(results.HarmfulCleanResultInputInvalid):
                results.check_output_destination(source, output)
            existing = Path(directory) / "existing"
            existing.mkdir()
            with self.assertRaises(results.HarmfulCleanResultInputInvalid):
                results.check_output_destination(source, existing)
        with self.assertRaises(results.HarmfulCleanResultInputInvalid):
            results.load_harmful_clean_run(Path("not-the-fixed-run"))

    def test_tampered_lineage_and_duplicate_identity_fail_closed(self) -> None:
        validated, _ = _fixture()
        duplicate = list(validated.loaded.responses)
        duplicate.append(copy.deepcopy(duplicate[0]))
        with self.assertRaises(results.HarmfulCleanResultInputInvalid):
            results.build_harmful_clean_payload(
                validated.prepared.clean_rows,
                duplicate,
                validated.loaded.dispositions,
            )
        tampered = list(validated.loaded.dispositions)
        tampered[0] = dict(tampered[0], logical_id="forged")
        with self.assertRaises(results.HarmfulCleanResultInputInvalid):
            results.build_harmful_clean_payload(
                validated.prepared.clean_rows,
                validated.loaded.responses,
                tampered,
            )


if __name__ == "__main__":
    unittest.main()
