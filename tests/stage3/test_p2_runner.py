from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from stage3_pipeline import p2_runner, support_screen
from stage3_pipeline.core import GenerationProducer, IdentityError, PipelineError, canonical_sha256
from stage3_pipeline.dose import build_call_dose_evidence
from stage3_pipeline.real_backend import RealBehaviorBackend
from stage3_pipeline.real_judge import RealJudgeBackend


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/stage3/qwen25_p2_v1.json"
TEMP_ROOT = ROOT / ".codex-temp"

TEMP_ROOT.mkdir(parents=True, exist_ok=True)
for _variable in ("TMPDIR", "TEMP", "TMP"):
    os.environ[_variable] = str(TEMP_ROOT.resolve())
for _variable in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
    os.environ[_variable] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


class FakeBehaviorBackend:
    capability = None

    def __init__(
        self,
        prepared: p2_runner.PreparedP2Runner,
        vector_index: int,
        events: list[str],
        cells_by_vector: dict[int, list[str]],
    ) -> None:
        self.prepared = prepared
        self.vector_index = vector_index
        self.vector_id = prepared.support.vector_ids_by_index[vector_index]
        self.events = events
        self.cells_by_vector = cells_by_vector
        self.released = False
        self.events.append(f"behavior_load:{vector_index}")

    def __call__(
        self, identity: dict[str, object], _request: dict[str, object]
    ) -> dict[str, object]:
        if identity["vector_id"] != self.vector_id:
            raise IdentityError("fake P2 behavior received the wrong vector identity")
        self.cells_by_vector.setdefault(self.vector_index, []).append(str(identity["block"]))
        evidence = build_call_dose_evidence(
            identity=identity,
            dose_binding=self.prepared.support.dose_binding,
            generation_status="COMPLETED",
            pre_hook_l2=100.0,
            post_hook_l2=101.0,
            vector_alignment=1.0,
            cosine_drift=0.01,
        )
        return {
            "output_text": "fake P2 response",
            "diagnostics": {"fake_backend": True},
            "dose_evidence": evidence,
        }

    def release(self) -> dict[str, object]:
        self.released = True
        self.events.append(f"behavior_release:{self.vector_index}")
        return {
            "schema_version": "paper1-stage3-sequential-lifecycle-v1",
            "behavior_released": True,
            "behavior_hook_removed": True,
            "behavior_model_reference_cleared": True,
            "behavior_tokenizer_reference_cleared": True,
            "gc_collect_called": True,
            "gc_collected_count": 0,
            "cuda_available": False,
            "cuda_synchronize_called": False,
            "cuda_empty_cache_called": False,
            "judge_loaded_after_behavior_release": False,
            "models_concurrently_resident": False,
        }


class FakeJudgeBackend:
    capability = None
    producer_identity = {
        "model_path_or_id": "fake-qwen3-8b",
        "tokenizer_path_or_id": "fake-qwen3-tokenizer",
        "rubric_sha256": "1" * 64,
    }

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.released = False
        self.events.append("judge_load")

    def __call__(self, _attempt: int, _request: dict[str, object]) -> str:
        return '{"label":"safe","rationale":"fake P2 fixture"}'

    def release(self) -> dict[str, object]:
        self.released = True
        self.events.append("judge_release")
        return {"judge_released": True}


class P2RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = p2_runner.prepare_p2_runner(CONFIG)
        cls.temporary = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        cls.output = Path(cls.temporary.name) / "fake-4000"
        cls.events: list[str] = []
        cls.cells_by_vector: dict[int, list[str]] = {}

        def behavior_factory(
            prepared: p2_runner.PreparedP2Runner, vector_index: int
        ) -> FakeBehaviorBackend:
            return FakeBehaviorBackend(
                prepared, vector_index, cls.events, cls.cells_by_vector
            )

        def judge_factory(
            _prepared: p2_runner.PreparedP2Runner,
            lifecycle: dict[str, object],
        ) -> FakeJudgeBackend:
            if lifecycle["behavior_session_count"] != 20:
                raise AssertionError("judge loaded before all P2 behavior sessions completed")
            return FakeJudgeBackend(cls.events)

        cls.fake_result = p2_runner.run_prepared_p2(
            cls.prepared,
            run_id="fake-4000",
            behavior_backend_factory=behavior_factory,
            judge_backend_factory=judge_factory,
            output_directory_resolver=lambda _prepared, _run_id: cls.output,
        )
        cls.generations = cls._records(cls.output / "generation_records.json")
        cls.judges = cls._records(cls.output / "judge_records.json")
        cls.responses = cls._records(cls.output / "response_records.json")
        cls.dispositions = cls._records(cls.output / "execution_dispositions.json")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @staticmethod
    def _records(path: Path) -> list[dict[str, object]]:
        return json.loads(path.read_text(encoding="utf-8"))["records"]

    def test_formal_assets_and_original_p2_subset_are_fixed(self) -> None:
        self.assertEqual(len(self.prepared.support.registry), 5_580)
        self.assertEqual(len(self.prepared.p2_rows), 4_000)
        self.assertEqual(self.prepared.support_statuses["A"], "SUPPORTED")
        self.assertEqual(self.prepared.support_statuses["T"], "SUPPORTED")
        by_cell = {
            cell: [
                row["identity"] for row in self.prepared.p2_rows
                if row["identity"]["block"] == cell
            ]
            for cell, _anchor, _estimator in p2_runner.P2_CELLS
        }
        self.assertEqual({cell: len(rows) for cell, rows in by_cell.items()}, {
            cell: 1_000 for cell, _anchor, _estimator in p2_runner.P2_CELLS
        })
        prompts = set(self.prepared.support.plan_inputs["confirm_prompt_ids"])
        vectors = {
            self.prepared.support.vector_ids_by_index[index] for index in range(10, 30)
        }
        self.assertEqual(len(prompts), 50)
        self.assertEqual(len(vectors), 20)
        for rows in by_cell.values():
            self.assertEqual({row["prompt_id"] for row in rows}, prompts)
            self.assertEqual({row["vector_id"] for row in rows}, vectors)
        for anchor in ("A", "T"):
            paired: dict[tuple[str, str], set[str]] = {}
            for row in self.prepared.p2_rows:
                identity = row["identity"]
                if identity["anchor"] == anchor:
                    paired.setdefault(
                        (identity["prompt_id"], identity["vector_id"]), set()
                    ).add(identity["block"])
            self.assertEqual(len(paired), 1_000)
            self.assertTrue(all(len(cells) == 2 for cells in paired.values()))

    def test_false_p1_gate_does_not_change_p2_identities(self) -> None:
        false_registry = support_screen.construct_plan_from_inputs(
            self.prepared.support.plan_inputs, p1_primary_gate=False
        )
        false_support = replace(
            self.prepared.support, registry=false_registry, p1_primary_gate=False
        )
        false_rows = p2_runner.select_p2_identities(false_support)
        self.assertEqual(
            [row["logical_id"] for row in false_rows],
            [row["logical_id"] for row in self.prepared.p2_rows],
        )
        self.assertEqual(
            false_registry.manifest(), self.prepared.support.registry.manifest()
        )

    def test_fake_4000_path_uses_shared_orchestration_and_stage_only_outputs(self) -> None:
        self.assertEqual(self.fake_result["status"], "P2_FAKE_4000_PATH_PASS")
        self.assertEqual(self.fake_result["canonical_plan_count"], 5_580)
        self.assertEqual(self.fake_result["p2_identity_count"], 4_000)
        self.assertEqual(self.fake_result["prior_support_terminal"], 900)
        self.assertEqual(self.fake_result["p2_terminal"], 4_000)
        self.assertEqual(self.fake_result["downstream_remaining"], 680)
        self.assertTrue(self.fake_result["fake_backend"])
        self.assertFalse(self.fake_result["formal_experiment_run"])
        self.assertFalse(self.fake_result["p2_run"])
        self.assertFalse(self.fake_result["paper_result_eligible"])
        self.assertFalse(self.fake_result["complete_stage3_reconciliation"])
        self.assertEqual(
            (len(self.generations), len(self.judges), len(self.responses), len(self.dispositions)),
            (4_000, 4_000, 4_000, 4_000),
        )
        self.assertTrue(all(record["fake_backend"] for record in self.generations))
        self.assertTrue(all(record["fake_backend"] for record in self.judges))
        self.assertTrue(all(record["fake_backend"] for record in self.responses))
        self.assertTrue(all(record["retained"] for record in self.responses))
        self.assertTrue(all(
            record["terminal_disposition"] == "COMPLETED_PARSED"
            for record in self.dispositions
        ))
        self.assertEqual(
            {path.name for path in self.output.iterdir()},
            {
                "canonical_registry_reference.json", "p2_identities.json",
                "generation_records.json", "judge_records.json", "response_records.json",
                "execution_dispositions.json", "p2_ledger.json", "execution_identity.json",
            },
        )
        reference = json.loads(
            (self.output / "canonical_registry_reference.json").read_text(encoding="utf-8")
        )
        self.assertEqual(reference["canonical_plan_count"], 5_580)
        self.assertNotIn("records", reference)
        ledger = json.loads((self.output / "p2_ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["support_records_rematerialized"], 0)
        self.assertEqual(ledger["remaining_dispositions_materialized"], 0)
        self.assertFalse(ledger["complete_stage3_reconciliation"])
        for forbidden in ("M_A", "M_T", "RD", "CI", "bootstrap", "K1"):
            self.assertNotIn(forbidden, ledger)

    def test_behavior_sessions_cover_four_cells_then_release_before_judge(self) -> None:
        expected_cells = [
            *("P2_A_all" for _ in range(50)),
            *("P2_A_content" for _ in range(50)),
            *("P2_T_all" for _ in range(50)),
            *("P2_T_content" for _ in range(50)),
        ]
        self.assertEqual(set(self.cells_by_vector), set(range(10, 30)))
        for vector_index in range(10, 30):
            self.assertEqual(self.cells_by_vector[vector_index], expected_cells)
        self.assertLess(
            max(
                index for index, event in enumerate(self.events)
                if event.startswith("behavior_release:")
            ),
            self.events.index("judge_load"),
        )

    def test_support_and_remaining_identities_are_not_materialized(self) -> None:
        p2_ids = {row["logical_id"] for row in self.prepared.p2_rows}
        support_ids = {
            row["logical_id"] for row in self.prepared.support.support_rows
        }
        disposition_ids = {record["logical_id"] for record in self.dispositions}
        registry_ids = {
            row["logical_id"] for row in self.prepared.support.registry.records()
        }
        self.assertEqual(disposition_ids, p2_ids)
        self.assertTrue(disposition_ids.isdisjoint(support_ids))
        self.assertEqual(len(registry_ids - support_ids - disposition_ids), 680)

    def test_support_limited_fixture_preserves_ids_and_marks_estimation_only(self) -> None:
        limited = replace(
            self.prepared,
            support_statuses={"A": "SUPPORT_LIMITED", "T": "SUPPORTED", "H": "SUPPORTED"},
        )
        self.assertEqual(
            [row["logical_id"] for row in limited.p2_rows],
            [row["logical_id"] for row in self.prepared.p2_rows],
        )
        ledger = p2_runner.reconcile_p2_stage(
            limited,
            generation_records=self.generations,
            judge_records=self.judges,
            response_records=self.responses,
            dispositions=self.dispositions,
            expected_fake_backend=True,
        )
        self.assertTrue(ledger["cells"]["P2_A_all"]["estimation_only"])
        self.assertTrue(ledger["cells"]["P2_A_content"]["estimation_only"])
        self.assertFalse(ledger["cells"]["P2_T_all"]["estimation_only"])
        self.assertEqual(ledger["p2_terminal"], 4_000)

    def test_non_estimable_fixture_preserves_fixed_ids_as_unattempted(self) -> None:
        blocked = replace(
            self.prepared,
            support_statuses={
                "A": "NON_ESTIMABLE_IDENTITY", "T": "SUPPORTED", "H": "SUPPORTED"
            },
        )
        identity_by_id = {
            row["logical_id"]: row["identity"] for row in blocked.p2_rows
        }
        attempted_ids = {
            logical_id for logical_id, identity in identity_by_id.items()
            if identity["anchor"] == "T"
        }
        dispositions = []
        existing = {record["logical_id"]: record for record in self.dispositions}
        for logical_id, identity in identity_by_id.items():
            dispositions.append(
                existing[logical_id]
                if logical_id in attempted_ids
                else p2_runner._unattempted_disposition(  # noqa: SLF001
                    logical_id, identity, "NON_ESTIMABLE_IDENTITY"
                )
            )
        ledger = p2_runner.reconcile_p2_stage(
            blocked,
            generation_records=[
                record for record in self.generations if record["logical_id"] in attempted_ids
            ],
            judge_records=[
                record for record in self.judges if record["logical_id"] in attempted_ids
            ],
            response_records=[
                record for record in self.responses if record["logical_id"] in attempted_ids
            ],
            dispositions=dispositions,
            expected_fake_backend=True,
        )
        self.assertEqual(len(dispositions), 4_000)
        self.assertEqual(ledger["p2_attempted"], 2_000)
        self.assertEqual(ledger["p2_unattempted"], 2_000)
        self.assertEqual(
            ledger["terminal_partition"]["UNATTEMPTED_DUE_INTEGRITY_BLOCK"], 2_000
        )
        self.assertEqual(ledger["p2_terminal"], 4_000)

    def test_identity_count_and_pair_tampering_fail_closed(self) -> None:
        with self.assertRaises(IdentityError):
            p2_runner.reconcile_p2_stage(
                self.prepared,
                generation_records=self.generations,
                judge_records=self.judges,
                response_records=self.responses[:-1],
                dispositions=self.dispositions,
            )
        forged_dispositions = copy.deepcopy(self.dispositions)
        forged_dispositions[0]["identity_sha256"] = "f" * 64
        with self.assertRaises((IdentityError, PipelineError)):
            p2_runner.reconcile_p2_stage(
                self.prepared,
                generation_records=self.generations,
                judge_records=self.judges,
                response_records=self.responses,
                dispositions=forged_dispositions,
            )
        forged_pair = copy.deepcopy(self.responses)
        forged_pair[0]["pair_id"] = "forged|pair|id"
        forged_pair[0]["record_sha256"] = canonical_sha256({
            key: value for key, value in forged_pair[0].items() if key != "record_sha256"
        })
        with self.assertRaises(PipelineError):
            p2_runner.reconcile_p2_stage(
                self.prepared,
                generation_records=self.generations,
                judge_records=self.judges,
                response_records=forged_pair,
                dispositions=self.dispositions,
            )

    def test_validate_only_never_loads_or_executes_models(self) -> None:
        with (
            mock.patch.object(RealBehaviorBackend, "from_pretrained") as behavior_loader,
            mock.patch.object(RealJudgeBackend, "from_pretrained") as judge_loader,
            mock.patch.object(GenerationProducer, "produce") as generation,
        ):
            result = p2_runner.validate_only(CONFIG)
        behavior_loader.assert_not_called()
        judge_loader.assert_not_called()
        generation.assert_not_called()
        self.assertEqual(result["status"], "P2_RUNNER_VALIDATE_ONLY_PASS")
        self.assertEqual(result["support_assets_read"], 8)
        self.assertTrue(result["stored_support_ledger_match"])
        self.assertTrue(result["canonical_registry_exact_match"])
        for field in (
            "model_weights_loaded", "forward_executed", "generation_run", "judge_run",
            "support_run", "p2_run", "formal_experiment_run", "paper_result_eligible",
        ):
            self.assertFalse(result[field])
        self.assertEqual(result["network_attempts"], 0)
        self.assertEqual(result["blocked_attempts"], 0)

    def test_existing_output_directory_is_rejected_before_backends(self) -> None:
        existing = Path(self.temporary.name) / "existing"
        existing.mkdir()
        behavior_factory = mock.Mock()
        judge_factory = mock.Mock()
        with self.assertRaisesRegex(PipelineError, "refusing to overwrite"):
            p2_runner.run_prepared_p2(
                self.prepared,
                run_id="existing",
                behavior_backend_factory=behavior_factory,
                judge_backend_factory=judge_factory,
                output_directory_resolver=lambda _prepared, _run_id: existing,
            )
        behavior_factory.assert_not_called()
        judge_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
