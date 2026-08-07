from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stage3_pipeline import support_screen
from stage3_pipeline.core import GenerationProducer, IdentityError, PipelineError
from stage3_pipeline.dose import build_call_dose_evidence, validate_dose_binding
from stage3_pipeline.real_backend import RealBehaviorBackend
from stage3_pipeline.real_judge import RealJudgeBackend


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/stage3/qwen25_support_screen_v1.json"
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
        prepared: support_screen.PreparedSupportScreen,
        vector_index: int,
        events: list[str],
    ) -> None:
        self.prepared = prepared
        self.vector_index = vector_index
        self.vector_id = prepared.vector_ids_by_index[vector_index]
        self.events = events
        self.released = False
        self.events.append(f"behavior_load:{vector_index}")

    def __call__(self, identity: dict[str, object], _request: dict[str, object]) -> dict[str, object]:
        if identity["vector_id"] != self.vector_id:
            raise IdentityError("fake behavior received the wrong vector identity")
        evidence = build_call_dose_evidence(
            identity=identity,
            dose_binding=self.prepared.dose_binding,
            generation_status="COMPLETED",
            pre_hook_l2=100.0,
            post_hook_l2=101.0,
            vector_alignment=1.0,
            cosine_drift=0.01,
        )
        return {
            "output_text": "fake support response",
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
        return '{"label":"safe","rationale":"fake fixture"}'

    def release(self) -> dict[str, object]:
        self.released = True
        self.events.append("judge_release")
        return {"judge_released": True}


class SupportScreenRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = support_screen.prepare_support_screen(CONFIG)
        cls.temporary = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        cls.output = Path(cls.temporary.name) / "fake-900"
        cls.events: list[str] = []

        def behavior_factory(
            prepared: support_screen.PreparedSupportScreen, vector_index: int
        ) -> FakeBehaviorBackend:
            return FakeBehaviorBackend(prepared, vector_index, cls.events)

        def judge_factory(
            _prepared: support_screen.PreparedSupportScreen,
            lifecycle: dict[str, object],
        ) -> FakeJudgeBackend:
            if lifecycle["behavior_session_count"] != 10:
                raise AssertionError("judge loaded before all behavior sessions completed")
            return FakeJudgeBackend(cls.events)

        cls.fake_result = support_screen.run_prepared_support_screen(
            cls.prepared,
            run_id="fake-900",
            behavior_backend_factory=behavior_factory,
            judge_backend_factory=judge_factory,
            output_directory_resolver=lambda _prepared, _run_id: cls.output,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @staticmethod
    def _records(path: Path) -> list[dict[str, object]]:
        return json.loads(path.read_text(encoding="utf-8"))["records"]

    def test_canonical_plan_and_support_subset_are_fixed(self) -> None:
        self.assertEqual(len(self.prepared.registry), 5_580)
        self.assertEqual(len(self.prepared.support_rows), 900)
        by_anchor = {
            anchor: [
                row["identity"]
                for row in self.prepared.support_rows
                if row["identity"]["anchor"] == anchor
            ]
            for anchor in ("A", "T", "H")
        }
        self.assertEqual({anchor: len(rows) for anchor, rows in by_anchor.items()}, {
            "A": 300, "T": 300, "H": 300,
        })
        screen_prompts = set(self.prepared.plan_inputs["screen_prompt_ids"])
        self.assertEqual(len(screen_prompts), 30)
        expected_vectors = {
            self.prepared.vector_ids_by_index[index] for index in range(10)
        }
        doses = validate_dose_binding(self.prepared.dose_binding)
        for anchor, identities in by_anchor.items():
            self.assertEqual({item["prompt_id"] for item in identities}, screen_prompts)
            self.assertEqual({item["vector_id"] for item in identities}, expected_vectors)
            self.assertEqual({item["estimator"] for item in identities}, {"mu_all_tw"})
            self.assertEqual(
                {item["c_hex"] for item in identities},
                {doses[anchor]["mu_all_tw"]["c_hex"]},
            )
            self.assertEqual(
                {item["alpha_post_dtype_hex"] for item in identities},
                {doses[anchor]["mu_all_tw"]["alpha_post_dtype_hex"]},
            )
        observed_indices = {
            self.prepared.vector_index_by_id[row["identity"]["vector_id"]]
            for row in self.prepared.support_rows
        }
        self.assertEqual(observed_indices, set(range(10)))

    def test_consistent_false_gate_does_not_change_support_identities(self) -> None:
        false_gate_registry = support_screen.construct_plan_from_inputs(
            self.prepared.plan_inputs, p1_primary_gate=False
        )
        false_gate_rows = support_screen.select_support_identities(
            false_gate_registry,
            screen_prompt_ids=self.prepared.plan_inputs["screen_prompt_ids"],
            vector_ids_by_index=self.prepared.vector_ids_by_index,
        )
        self.assertEqual(
            [row["logical_id"] for row in false_gate_rows],
            [row["logical_id"] for row in self.prepared.support_rows],
        )
        self.assertEqual(
            false_gate_registry.manifest()["registry_sha256"],
            self.prepared.registry.manifest()["registry_sha256"],
        )

    def test_fake_900_path_materializes_all_canonical_stages(self) -> None:
        self.assertEqual(self.fake_result["status"], "SUPPORT_SCREEN_FAKE_900_PATH_PASS")
        self.assertEqual(self.fake_result["canonical_plan_count"], 5_580)
        self.assertEqual(self.fake_result["support_identity_count"], 900)
        self.assertEqual(self.fake_result["anchor_status"], {
            "A": "SUPPORTED", "T": "SUPPORTED", "H": "SUPPORTED",
        })
        self.assertTrue(self.fake_result["fake_backend"])
        self.assertFalse(self.fake_result["paper_result_eligible"])
        self.assertFalse(self.fake_result["formal_experiment_run"])
        self.assertFalse(self.fake_result["real_support_run"])
        self.assertFalse(self.fake_result["p2_run"])
        self.assertFalse(self.fake_result["complete_stage3_reconciliation"])

        generations = self._records(self.output / "generation_records.json")
        judges = self._records(self.output / "judge_records.json")
        responses = self._records(self.output / "response_records.json")
        dispositions = self._records(self.output / "execution_dispositions.json")
        self.assertEqual(
            (len(generations), len(judges), len(responses), len(dispositions)),
            (900, 900, 900, 900),
        )
        self.assertTrue(all(record["fake_backend"] for record in generations))
        self.assertTrue(all(record["fake_backend"] for record in judges))
        self.assertTrue(all(record["fake_backend"] for record in responses))
        self.assertTrue(all(record["retained"] for record in responses))
        self.assertTrue(all(record["terminal_disposition"] == "COMPLETED_PARSED" for record in dispositions))

        ledger = json.loads((self.output / "support_ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["support_terminal"], 900)
        self.assertEqual(ledger["downstream_pending_identity_count"], 4_680)
        self.assertFalse(ledger["downstream_dispositions_materialized"])
        self.assertFalse(ledger["complete_stage3_reconciliation"])
        self.assertEqual(
            set(self.events[:20]),
            {
                *(f"behavior_load:{index}" for index in range(10)),
                *(f"behavior_release:{index}" for index in range(10)),
            },
        )
        self.assertLess(
            max(index for index, event in enumerate(self.events) if event.startswith("behavior_release:")),
            self.events.index("judge_load"),
        )

    def test_identity_and_count_tampering_fail_closed(self) -> None:
        generations = self._records(self.output / "generation_records.json")
        judges = self._records(self.output / "judge_records.json")
        responses = self._records(self.output / "response_records.json")
        dispositions = self._records(self.output / "execution_dispositions.json")
        with self.assertRaises(IdentityError):
            support_screen.reconcile_support_stage(
                self.prepared,
                generation_records=generations,
                judge_records=judges,
                response_records=responses[:-1],
                dispositions=dispositions,
            )
        with self.assertRaises(IdentityError):
            support_screen.reconcile_support_stage(
                self.prepared,
                generation_records=generations + [generations[0]],
                judge_records=judges,
                response_records=responses,
                dispositions=dispositions,
            )
        forged = copy.deepcopy(dispositions)
        forged[0]["identity_sha256"] = "f" * 64
        with self.assertRaises((IdentityError, PipelineError)):
            support_screen.reconcile_support_stage(
                self.prepared,
                generation_records=generations,
                judge_records=judges,
                response_records=responses,
                dispositions=forged,
            )

    def test_validate_only_never_loads_or_executes_models(self) -> None:
        with (
            mock.patch.object(RealBehaviorBackend, "from_pretrained") as behavior_loader,
            mock.patch.object(RealJudgeBackend, "from_pretrained") as judge_loader,
            mock.patch.object(GenerationProducer, "produce") as generation,
        ):
            result = support_screen.validate_only(CONFIG)
        behavior_loader.assert_not_called()
        judge_loader.assert_not_called()
        generation.assert_not_called()
        self.assertEqual(result["status"], "SUPPORT_SCREEN_RUNNER_VALIDATE_ONLY_PASS")
        for field in (
            "model_weights_loaded",
            "forward_executed",
            "generation_run",
            "judge_run",
            "support_run",
            "p2_run",
            "formal_experiment_run",
            "paper_result_eligible",
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
            support_screen.run_prepared_support_screen(
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
