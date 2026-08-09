from __future__ import annotations

import copy
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from stage3_pipeline import p2_results
from stage3_pipeline.statistics import reference_statistics


ROOT = Path(__file__).resolve().parents[2]
TEMP_ROOT = ROOT / ".codex-temp"
CLI = importlib.import_module(
    "scripts.stage3_production.materialize_p2_results"
)

TEMP_ROOT.mkdir(parents=True, exist_ok=True)
for _variable in ("TMPDIR", "TEMP", "TMP"):
    os.environ[_variable] = str(TEMP_ROOT.resolve())
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


CELL_SPECS = {
    "P2_A_all": ("A", "mu_all_tw", "all-token"),
    "P2_A_content": ("A", "mu_content_tw", "content-token"),
    "P2_T_all": ("T", "mu_all_tw", "all-token"),
    "P2_T_content": ("T", "mu_content_tw", "content-token"),
}


def _fixture() -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    labels = {
        "P2_A_all": ("unsafe", "safe", "unsafe", "safe"),
        "P2_A_content": ("safe", "unsafe", "unsafe", "safe"),
        "P2_T_all": ("broken", "safe", "safe", "broken"),
        "P2_T_content": ("safe", "safe", "broken", "broken"),
    }
    rows: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    generations: list[dict[str, object]] = []
    judges: list[dict[str, object]] = []
    pairs = [(prompt, vector) for prompt in ("p01", "p02") for vector in ("v01", "v02")]
    for cell, (anchor, estimator, arm) in CELL_SPECS.items():
        for index, (prompt_id, vector_id) in enumerate(pairs):
            logical_id = f"logical-{cell}-{prompt_id}-{vector_id}"
            rows.append({
                "logical_id": logical_id,
                "identity": {
                    "block": cell,
                    "anchor": anchor,
                    "estimator": estimator,
                    "prompt_id": prompt_id,
                    "vector_id": vector_id,
                },
            })
            responses.append({
                "logical_id": logical_id,
                "cell": cell,
                "anchor": anchor,
                "estimator": estimator,
                "arm": arm,
                "prompt_id": prompt_id,
                "vector_id": vector_id,
                "pair_id": f"{anchor}|{prompt_id}|{vector_id}",
                "generation_completed": True,
                "judge_eligible": True,
                "judge_label_parsed": True,
                "terminal_status": "COMPLETED_PARSED",
                "missingness_code": None,
                "retained": True,
                "label": labels[cell][index],
            })
            generations.append({"logical_id": logical_id, "attempts": [{"attempt": 1}]})
            judges.append({"logical_id": logical_id, "attempts": [{"attempt": 1}]})
    responses.reverse()
    return rows, responses, generations, judges


def _fake_reconciliation() -> dict[str, object]:
    return {
        "canonical_plan_count": 5_580,
        "canonical_registry_sha256": "a" * 64,
        "p2_identity_count": 4_000,
    }


class P2ResultMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows, self.responses, self.generations, self.judges = _fixture()

    def test_four_cells_and_identity_pairing_build_m_a_and_m_t(self) -> None:
        frame = p2_results.build_p2_raw_members(
            self.rows, self.responses, expected_cell_count=4
        )
        self.assertEqual(set(frame["cell_counts"]), set(CELL_SPECS))
        self.assertEqual(frame["member_order"], ["P2-U(A)", "P2-B(T)"])
        unsafe, broken = frame["members"]
        self.assertEqual((unsafe["matched_set"], unsafe["anchor"]), ("M_A", "A"))
        self.assertEqual((broken["matched_set"], broken["anchor"]), ("M_T", "T"))
        self.assertEqual(unsafe["matched_pair_count"], 4)
        self.assertEqual(broken["matched_pair_count"], 4)
        self.assertEqual(unsafe["missing_pair_count"], 0)
        self.assertEqual(
            [record["difference"] for record in unsafe["records"]],
            [1, -1, 0, 0],
        )
        self.assertEqual(
            [record["difference"] for record in broken["records"]],
            [1, 0, -1, 0],
        )
        first = unsafe["records"][0]
        self.assertEqual(first["pair_id"], "A|p01|v01")
        self.assertEqual(first["arms"]["all"]["cell"], "P2_A_all")
        self.assertEqual(first["arms"]["content"]["cell"], "P2_A_content")
        self.assertIn("logical-P2_A_all-p01-v01", first["arms"]["all"]["logical_id"])

    def test_terminal_failure_is_excluded_without_becoming_broken(self) -> None:
        failed = next(
            record
            for record in self.responses
            if record["cell"] == "P2_T_all"
            and record["prompt_id"] == "p01"
            and record["vector_id"] == "v01"
        )
        failed.update({
            "judge_label_parsed": False,
            "terminal_status": "TERMINAL_JUDGE_FAILURE",
            "missingness_code": "TERMINAL_JUDGE_FAILURE",
            "retained": False,
            "label": None,
        })
        frame = p2_results.build_p2_raw_members(
            self.rows, self.responses, expected_cell_count=4
        )
        broken = frame["members"][1]
        self.assertEqual(broken["matched_pair_count"], 3)
        self.assertEqual(broken["missing_pair_count"], 1)
        self.assertEqual(broken["missing_pairs"][0]["pair_id"], "T|p01|v01")
        self.assertIsNone(broken["missing_pairs"][0]["arms"]["all"]["label"])
        self.assertFalse(any(
            record["pair_id"] == "T|p01|v01" for record in broken["records"]
        ))
        self.assertEqual(
            frame["cell_counts"]["P2_T_all"]["terminal_failure_record_count"],
            1,
        )
        self.assertEqual(
            frame["cell_counts"]["P2_T_content"]["terminal_failure_record_count"],
            0,
        )
        self.assertEqual(
            frame["cell_counts"]["P2_T_content"]["excluded_record_count"], 1
        )
        self.assertEqual(
            frame["cell_counts"]["P2_T_content"][
                "unmatched_completed_record_count"
            ],
            1,
        )

    def test_missing_response_and_incomplete_canonical_pair_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            p2_results.P2ResultInputInvalid, "RESPONSE_ID_PARTITION"
        ):
            p2_results.build_p2_raw_members(
                self.rows, self.responses[:-1], expected_cell_count=4
            )

        rows = copy.deepcopy(self.rows)
        row = next(
            item
            for item in rows
            if item["identity"]["block"] == "P2_A_content"
            and item["identity"]["prompt_id"] == "p01"
            and item["identity"]["vector_id"] == "v01"
        )
        row["identity"]["prompt_id"] = "orphan-prompt"
        with self.assertRaisesRegex(
            p2_results.P2ResultInputInvalid, "INCOMPLETE_CANONICAL_PAIRING"
        ):
            p2_results.build_p2_raw_members(
                rows, self.responses, expected_cell_count=4
            )

    def test_duplicate_and_mismatched_logical_identity_fail_closed(self) -> None:
        duplicate = self.responses + [copy.deepcopy(self.responses[0])]
        with self.assertRaisesRegex(
            p2_results.P2ResultInputInvalid, "DUPLICATE_RESPONSE_LOGICAL_ID"
        ):
            p2_results.build_p2_raw_members(
                self.rows, duplicate, expected_cell_count=4
            )

        mismatched = copy.deepcopy(self.responses)
        mismatched[0]["anchor"] = "A" if mismatched[0]["anchor"] == "T" else "T"
        with self.assertRaisesRegex(
            p2_results.P2ResultInputInvalid, "RESPONSE_IDENTITY_MISMATCH"
        ):
            p2_results.build_p2_raw_members(
                self.rows, mismatched, expected_cell_count=4
            )

        duplicate_rows = copy.deepcopy(self.rows)
        duplicate_rows[1]["logical_id"] = duplicate_rows[0]["logical_id"]
        with self.assertRaisesRegex(
            p2_results.P2ResultInputInvalid, "DUPLICATE_CANONICAL_LOGICAL_ID"
        ):
            p2_results.build_p2_raw_members(
                duplicate_rows, self.responses, expected_cell_count=4
            )

    def test_difference_range_is_checked_immediately(self) -> None:
        self.assertEqual(
            p2_results._paired_difference(
                1, 0, member_id="P2-U(A)", pair_id="A|p|v"
            ),
            1,
        )
        with self.assertRaisesRegex(
            p2_results.P2ResultInputInvalid, "INVALID_BINARY_OUTCOME"
        ):
            p2_results._paired_difference(
                2, 0, member_id="P2-U(A)", pair_id="A|p|v"
            )

    def test_existing_statistic_accepts_traceable_member_records(self) -> None:
        frame = p2_results.build_p2_raw_members(
            self.rows, self.responses, expected_cell_count=4
        )
        result = reference_statistics.p2_raw_simultaneous(
            frame["members"], replicates=3, min_success=2
        )
        self.assertEqual(result["member_order"], ["P2-U(A)", "P2-B(T)"])

    def test_assembly_injects_only_fixed_production_statistic_contract(self) -> None:
        calls: list[tuple[object, int, int]] = []

        def fake_statistic(
            members: list[dict[str, object]], *, replicates: int, min_success: int
        ) -> dict[str, object]:
            calls.append((members, replicates, min_success))
            return {"algorithm": "fake-small-fixture"}

        self.generations[0]["attempts"].append({"attempt": 2})
        result = p2_results.assemble_p2_result(
            canonical_rows=self.rows,
            generation_records=self.generations,
            judge_records=self.judges,
            response_records=self.responses,
            source={"fixture": True},
            reconciliation=_fake_reconciliation(),
            statistics_function=fake_statistic,
            expected_cell_count=4,
        )
        self.assertEqual(result["status"], "ESTIMABLE")
        self.assertEqual(result["statistics"], {"algorithm": "fake-small-fixture"})
        self.assertEqual(calls[0][1:], (9_999, 9_500))
        self.assertEqual(
            [member["member_id"] for member in calls[0][0]],
            ["P2-U(A)", "P2-B(T)"],
        )
        retried_cell = self.rows[0]["identity"]["block"]
        self.assertEqual(
            result["cell_counts"][retried_cell]["generation_retry_call_count"],
            1,
        )
        self.assertEqual(
            result["statistics_contract"]["rng_namespace"],
            reference_statistics.RNG_NAMESPACE,
        )

    def test_formal_loader_calls_existing_reconciliation(self) -> None:
        prepared = SimpleNamespace(
            p2_rows=tuple(self.rows),
            support_execution_identity={"run_id": "support-run"},
        )
        registry_reference = {"canonical_registry_sha256": "a" * 64}
        reconciliation = {
            "canonical_plan_count": 5_580,
            "p2_identity_count": 4_000,
            "terminal_partition": p2_results._expected_terminal_partition(),
            "cells": {cell: {"scheduled": 1_000} for cell in CELL_SPECS},
        }
        loaded = SimpleNamespace(
            identities=tuple(self.rows),
            registry_reference=registry_reference,
            generations=tuple(self.generations),
            judges=tuple(self.judges),
            responses=tuple(self.responses),
            dispositions=tuple({"logical_id": row["logical_id"]} for row in self.rows),
            ledger=reconciliation,
        )
        with (
            mock.patch.object(p2_results, "_prepare_p2_runner", return_value=prepared),
            mock.patch.object(
                p2_results, "_fixed_run_directory", return_value=Path("explicit-run")
            ),
            mock.patch.object(p2_results, "_validate_prepared_registry", return_value=registry_reference),
            mock.patch.object(p2_results, "load_p2_run", return_value=loaded),
            mock.patch.object(
                p2_results,
                "_reconcile_p2_stage",
                return_value=reconciliation,
            ) as reconcile,
            mock.patch.object(p2_results, "_validate_execution_identity") as execution,
        ):
            actual_prepared, actual_loaded, actual_reconciliation = (
                p2_results.load_and_reconcile_p2_run(Path("explicit-run"))
            )
        self.assertIs(actual_prepared, prepared)
        self.assertIs(actual_loaded, loaded)
        self.assertEqual(actual_reconciliation, reconciliation)
        self.assertIs(reconcile.call_args.args[0], prepared)
        self.assertFalse(reconcile.call_args.kwargs["expected_fake_backend"])
        execution.assert_called_once()

    def test_output_directory_is_created_once_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            source_run = root / "source-run"
            source_run.mkdir()
            output = root / "result"
            prepared = SimpleNamespace(p2_rows=tuple(self.rows))
            loaded = SimpleNamespace(
                run_directory=source_run.resolve(),
                generations=tuple(self.generations),
                judges=tuple(self.judges),
                responses=tuple(self.responses),
                execution_identity={"run_id": source_run.name},
                file_sha256={"response_records.json": "b" * 64},
            )

            def fake_statistic(
                _members: object, *, replicates: int, min_success: int
            ) -> dict[str, object]:
                return {"replicates_requested": replicates, "required": min_success}

            written_result = {
                "schema_version": p2_results.SCHEMA_VERSION,
                "status": "ESTIMABLE",
            }
            with (
                mock.patch.object(
                    p2_results,
                    "load_and_reconcile_p2_run",
                    return_value=(prepared, loaded, _fake_reconciliation()),
                ) as loader,
                mock.patch.object(
                    p2_results, "assemble_p2_result", return_value=written_result
                ) as assemble,
            ):
                result = p2_results.materialize_p2_results_directory(
                    source_run, output, statistics_function=fake_statistic
                )
            target = output / p2_results.OUTPUT_FILENAME
            self.assertTrue(target.is_file())
            self.assertTrue(target.read_bytes().endswith(b"\n"))
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), result)
            loader.assert_called_once_with(source_run)
            self.assertIs(
                assemble.call_args.kwargs["statistics_function"], fake_statistic
            )

            with mock.patch.object(
                p2_results, "load_and_reconcile_p2_run"
            ) as forbidden_loader:
                with self.assertRaisesRegex(
                    p2_results.P2ResultInputInvalid, "OUTPUT_DIRECTORY_EXISTS"
                ):
                    p2_results.materialize_p2_results_directory(
                        source_run, output, statistics_function=fake_statistic
                    )
            forbidden_loader.assert_not_called()

            with self.assertRaisesRegex(
                p2_results.P2ResultInputInvalid, "OUTPUT_DIRECTORY_INSIDE_SOURCE_RUN"
            ):
                p2_results._check_output_destination(
                    source_run, source_run / "new-result"
                )

    def test_cli_requires_explicit_directories(self) -> None:
        expected = {"status": "ESTIMABLE"}
        with (
            mock.patch.object(
                CLI, "materialize_p2_results_directory", return_value=expected
            ) as materialize,
            mock.patch("builtins.print"),
        ):
            status = CLI.main([
                "--run-directory",
                "/tmp/source-p2",
                "--output-directory",
                "/tmp/output-p2",
            ])
        self.assertEqual(status, 0)
        materialize.assert_called_once_with(
            Path("/tmp/source-p2"), Path("/tmp/output-p2")
        )


if __name__ == "__main__":
    unittest.main()
