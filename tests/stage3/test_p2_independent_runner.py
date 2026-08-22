from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stage3_pipeline import p2_independent_runner as independent
from stage3_pipeline import p2_runner
from stage3_pipeline.core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    GenerationProducer,
    IdentityError,
    PipelineError,
    TechnicalGenerationError,
    TerminalGenerationError,
    canonical_sha256,
    parse_judge_with_retry,
)
from stage3_pipeline.dose import build_call_dose_evidence, validate_dose_binding
from stage3_pipeline.records import validate_generation_record


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/stage3/qwen25_p2_independent_th_v1.json"
OLD_CONFIG = ROOT / "configs/stage3/qwen25_p2_v1.json"
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
        prepared: independent.PreparedIndependentP2,
        vector_index: int,
        events: list[str],
        generated_by_anchor: dict[str, int],
    ) -> None:
        self.prepared = prepared
        self.vector_id = prepared.base.support.vector_ids_by_index[vector_index]
        self.vector_index = vector_index
        self.events = events
        self.generated_by_anchor = generated_by_anchor
        self.released = False
        events.append(f"behavior_load:{vector_index}")

    def __call__(
        self, identity: dict[str, object], _request: dict[str, object]
    ) -> dict[str, object]:
        if identity["vector_id"] != self.vector_id:
            raise IdentityError("fake behavior received the wrong vector")
        anchor = str(identity["anchor"])
        self.generated_by_anchor[anchor] = self.generated_by_anchor.get(anchor, 0) + 1
        evidence = build_call_dose_evidence(
            identity=identity,
            dose_binding=self.prepared.base.support.dose_binding,
            generation_status="COMPLETED",
            pre_hook_l2=100.0,
            post_hook_l2=101.0,
            vector_alignment=1.0,
            cosine_drift=0.01,
        )
        return {
            "output_text": f"fresh {anchor} independent response",
            "diagnostics": {"fake_backend": True, "anchor": anchor},
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

    def __init__(self, events: list[str], lifecycle: dict[str, object]) -> None:
        if lifecycle.get("behavior_session_count") != 20:
            raise AssertionError("judge loaded before all behavior sessions completed")
        if lifecycle.get("behavior_released") is not True:
            raise AssertionError("judge loaded before behavior release")
        self.events = events
        self.released = False
        self.calls = 0
        events.append("judge_load")

    def __call__(self, _attempt: int, request: dict[str, object]) -> str:
        self.calls += 1
        context = request["backend_request"]
        response = str(context["response"])
        label = "broken" if "fresh H" in response else "unsafe"
        return json.dumps({"label": label, "rationale": "fresh fake judgment"})

    def release(self) -> dict[str, object]:
        self.released = True
        self.events.append("judge_release")
        return {"judge_released": True, "models_concurrently_resident": False}


class IndependentP2RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = independent.prepare_independent_p2(CONFIG)
        cls.events: list[str] = []
        cls.generated_by_anchor: dict[str, int] = {}
        cls.judge_backend: FakeJudgeBackend | None = None

        def behavior_factory(
            prepared: independent.PreparedIndependentP2, vector_index: int
        ) -> FakeBehaviorBackend:
            return FakeBehaviorBackend(
                prepared, vector_index, cls.events, cls.generated_by_anchor
            )

        def judge_factory(
            _prepared: independent.PreparedIndependentP2,
            lifecycle: dict[str, object],
        ) -> FakeJudgeBackend:
            cls.judge_backend = FakeJudgeBackend(cls.events, lifecycle)
            return cls.judge_backend

        cls.artifacts = independent.execute_independent_p2(
            cls.prepared,
            behavior_backend_factory=behavior_factory,
            judge_backend_factory=judge_factory,
        )

    def test_canonical_t_h_identity_generation(self) -> None:
        rows = self.prepared.rows
        self.assertEqual(len(rows), 4_000)
        self.assertEqual(len({row["logical_id"] for row in rows}), 4_000)
        counts = {
            cell: sum(row["identity"]["block"] == cell for row in rows)
            for cell in independent.BLOCKS
        }
        self.assertEqual(counts, {cell: 1_000 for cell in independent.BLOCKS})
        for row in rows:
            identity = row["identity"]
            self.assertEqual(identity["domain"], "harmful")
            self.assertEqual(identity["split"], "D_behavior_confirm")
            self.assertIn(identity["anchor"], {"T", "H"})

    def test_h_identities_are_not_old_p2_or_support_identities(self) -> None:
        h_ids = {
            row["logical_id"] for row in self.prepared.rows
            if row["identity"]["anchor"] == "H"
        }
        old_ids = {row["logical_id"] for row in self.prepared.base.p2_rows}
        support_ids = {
            row["logical_id"] for row in self.prepared.base.support.support_rows
        }
        self.assertEqual(len(h_ids), 2_000)
        self.assertFalse(h_ids & old_ids)
        self.assertFalse(h_ids & support_ids)
        self.assertEqual(
            {row["identity"]["split"] for row in self.prepared.rows if row["logical_id"] in h_ids},
            {"D_behavior_confirm"},
        )

    def test_endpoint_order_and_anchor_local_matched_sets(self) -> None:
        self.assertEqual(
            [endpoint["member_id"] for endpoint in independent.ENDPOINT_ORDER],
            ["P2-U(T)", "P2-B(H)"],
        )
        self.assertEqual(
            independent.ENDPOINT_ORDER[0],
            {
                "member_id": "P2-U(T)",
                "outcome": "unsafe",
                "contrast": "all-minus-content",
                "anchor": "T",
                "matched_set": "M_T",
                "all_cell": "P2_T_all",
                "content_cell": "P2_T_content",
            },
        )
        self.assertEqual(self.artifacts.ledger["matched_sets"]["M_T"]["anchor"], "T")
        self.assertEqual(self.artifacts.ledger["matched_sets"]["M_H"]["anchor"], "H")
        self.assertEqual(self.artifacts.ledger["matched_sets"]["M_T"]["valid_pair_count"], 1_000)
        self.assertEqual(self.artifacts.ledger["matched_sets"]["M_H"]["valid_pair_count"], 1_000)
        for response in self.artifacts.response_records:
            self.assertTrue(response["pair_id"].startswith(response["anchor"] + "|"))

    def test_t_h_dose_binding_is_exact(self) -> None:
        doses = validate_dose_binding(self.prepared.base.support.dose_binding)
        for row in self.prepared.rows:
            identity = row["identity"]
            expected = doses[identity["anchor"]][identity["estimator"]]
            self.assertEqual(
                {field: identity[field] for field in expected}, expected
            )
        self.assertNotEqual(
            doses["T"]["mu_all_tw"]["c_hex"],
            doses["H"]["mu_all_tw"]["c_hex"],
        )

    def test_full_fake_path_generates_and_judges_real_h_identities(self) -> None:
        self.assertEqual(self.generated_by_anchor, {"T": 2_000, "H": 2_000})
        self.assertIsNotNone(self.judge_backend)
        self.assertEqual(self.judge_backend.calls, 4_000)
        self.assertEqual(
            self.artifacts.ledger["h_confirmation_generation_record_count"], 2_000
        )
        self.assertEqual(
            self.artifacts.ledger["h_confirmation_judge_record_count"], 2_000
        )
        h_responses = [
            record for record in self.artifacts.response_records
            if record["anchor"] == "H"
        ]
        self.assertEqual(len(h_responses), 2_000)
        self.assertTrue(all(record["label"] == "broken" for record in h_responses))

    def test_behavior_is_fully_released_before_judge(self) -> None:
        judge_index = self.events.index("judge_load")
        behavior_events = self.events[:judge_index]
        self.assertEqual(sum(event.startswith("behavior_load:") for event in behavior_events), 20)
        self.assertEqual(sum(event.startswith("behavior_release:") for event in behavior_events), 20)
        self.assertFalse(any(event.startswith("behavior_") for event in self.events[judge_index + 1:]))
        self.assertEqual(self.events[-1], "judge_release")

    def test_duplicate_missing_and_mismatched_records_fail_closed(self) -> None:
        generations = list(self.artifacts.generation_records)
        duplicate_missing = generations[:-1] + [generations[0]]
        with self.assertRaises(IdentityError):
            independent.reconcile_independent_stage(
                self.prepared,
                generation_records=duplicate_missing,
                judge_records=self.artifacts.judge_records,
                response_records=self.artifacts.response_records,
                dispositions=self.artifacts.dispositions,
                expected_fake_backend=True,
            )
        with self.assertRaises(IdentityError):
            independent.reconcile_independent_stage(
                self.prepared,
                generation_records=generations[:-1],
                judge_records=self.artifacts.judge_records,
                response_records=self.artifacts.response_records,
                dispositions=self.artifacts.dispositions,
                expected_fake_backend=True,
            )
        forged = copy.deepcopy(self.artifacts.response_records[0])
        forged["pair_id"] = "H|borrowed|old-array-position"
        forged["record_sha256"] = canonical_sha256({
            key: value for key, value in forged.items() if key != "record_sha256"
        })
        logical_id = forged["logical_id"]
        generation = next(
            record for record in self.artifacts.generation_records
            if record["logical_id"] == logical_id
        )
        judge = next(
            record for record in self.artifacts.judge_records
            if record["logical_id"] == logical_id
        )
        with self.assertRaises(PipelineError):
            independent.validate_independent_response(
                forged,
                registry=self.prepared.registry,
                generation_record=generation,
                judge_record=judge,
                dose_binding=self.prepared.base.support.dose_binding,
            )

    def test_registry_duplicate_identity_fails_closed(self) -> None:
        registry = independent.IndependentLogicalIdentityRegistry()
        identity = self.prepared.rows[0]["identity"]
        registry.register(identity)
        with self.assertRaises(IdentityError):
            registry.register(identity)

    def _one_generation(
        self, backend: object
    ) -> tuple[dict[str, object], dict[str, object], str]:
        row = self.prepared.rows[0]
        producer = GenerationProducer(
            self.prepared.registry,
            backend,
            run_mode="paper",
            fake_backend=True,
        )
        logical_id = row["logical_id"]
        record = producer.produce(
            logical_id,
            {"logical_id": logical_id, "generation_config": DECODE_CONFIG},
        )
        return row["identity"], validate_generation_record(record), logical_id

    def test_generation_terminal_failure_and_retry_ceiling(self) -> None:
        identity = self.prepared.rows[0]["identity"]
        calls = 0

        def technical(_identity: object, _request: object) -> dict[str, object]:
            nonlocal calls
            calls += 1
            status = (
                "TECHNICAL_FAILURE_RETRYABLE"
                if calls == 1 else "TERMINAL_TECHNICAL_FAILURE"
            )
            evidence = build_call_dose_evidence(
                identity=identity,
                dose_binding=self.prepared.base.support.dose_binding,
                generation_status=status,
                pre_hook_l2=100.0,
                post_hook_l2=101.0,
                vector_alignment=1.0,
                cosine_drift=0.01,
            )
            raise TechnicalGenerationError(
                "retry fixture", diagnostics={"dose_evidence": evidence}
            )

        _identity, record, _logical_id = self._one_generation(technical)
        self.assertEqual(calls, 2)
        self.assertEqual(record["attempt_count"], 2)
        self.assertEqual(record["retry_count"], 1)
        self.assertEqual(record["terminal_status"], "TERMINAL_TECHNICAL_FAILURE")

        deterministic_calls = 0

        def deterministic(_identity: object, _request: object) -> dict[str, object]:
            nonlocal deterministic_calls
            deterministic_calls += 1
            evidence = build_call_dose_evidence(
                identity=identity,
                dose_binding=self.prepared.base.support.dose_binding,
                generation_status="TERMINAL_FAILURE",
                pre_hook_l2=100.0,
                post_hook_l2=101.0,
                vector_alignment=1.0,
                cosine_drift=0.01,
            )
            raise TerminalGenerationError(
                "terminal fixture", diagnostics={"dose_evidence": evidence}
            )

        _identity, terminal, _logical_id = self._one_generation(deterministic)
        self.assertEqual(deterministic_calls, 1)
        self.assertEqual(terminal["attempt_count"], 1)
        self.assertEqual(terminal["retry_count"], 0)
        self.assertEqual(terminal["terminal_status"], "TERMINAL_FAILURE")

    def test_judge_terminal_failure_and_retry_ceiling(self) -> None:
        row = self.prepared.rows[0]
        identity = row["identity"]

        def completed(_identity: object, _request: object) -> dict[str, object]:
            evidence = build_call_dose_evidence(
                identity=identity,
                dose_binding=self.prepared.base.support.dose_binding,
                generation_status="COMPLETED",
                pre_hook_l2=100.0,
                post_hook_l2=101.0,
                vector_alignment=1.0,
                cosine_drift=0.01,
            )
            return {"output_text": "fixture", "diagnostics": {}, "dose_evidence": evidence}

        _identity, generation, logical_id = self._one_generation(completed)
        calls = 0

        def invalid(_attempt: int, _request: object) -> str:
            nonlocal calls
            calls += 1
            return "not-json"

        judge = parse_judge_with_retry(
            logical_id,
            invalid,
            {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
            registry=self.prepared.registry,
            generation_record=generation,
            run_mode="paper",
            judge_identity={
                "model_path_or_id": "fake",
                "tokenizer_path_or_id": "fake-tokenizer",
                "rubric_sha256": "2" * 64,
            },
            fake_backend=True,
        )
        self.assertEqual(calls, 2)
        self.assertEqual(len(judge["attempts"]), 2)
        self.assertEqual(judge["terminal_status"], "TERMINAL_PARSE_OR_INFRASTRUCTURE_FAILURE")

        terminal_calls = 0

        def unexpected(_attempt: int, _request: object) -> str:
            nonlocal terminal_calls
            terminal_calls += 1
            raise RuntimeError("terminal judge fixture")

        terminal = parse_judge_with_retry(
            logical_id,
            unexpected,
            {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
            registry=self.prepared.registry,
            generation_record=generation,
            run_mode="paper",
            judge_identity={
                "model_path_or_id": "fake",
                "tokenizer_path_or_id": "fake-tokenizer",
                "rubric_sha256": "2" * 64,
            },
            fake_backend=True,
        )
        self.assertEqual(terminal_calls, 1)
        self.assertEqual(len(terminal["attempts"]), 1)
        self.assertEqual(terminal["terminal_status"], "TERMINAL_INDETERMINATE_FAILURE")

    def test_existing_output_directory_refuses_before_execution(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            existing = Path(temporary) / "already-exists"
            existing.mkdir()
            with mock.patch.object(independent, "execute_independent_p2") as execute:
                with self.assertRaises(PipelineError):
                    independent.run_prepared_independent_p2(
                        self.prepared,
                        run_id="unit-existing-output",
                        output_directory_resolver=lambda _prepared, _run_id: existing,
                    )
                execute.assert_not_called()

    def test_existing_output_symlink_refuses_before_execution(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            target = Path(temporary) / "target"
            existing = Path(temporary) / "existing-symlink"
            existing.symlink_to(target, target_is_directory=True)
            with mock.patch.object(independent, "execute_independent_p2") as execute:
                with self.assertRaises(PipelineError):
                    independent.run_prepared_independent_p2(
                        self.prepared,
                        run_id="unit-existing-symlink",
                        output_directory_resolver=lambda _prepared, _run_id: existing,
                    )
                execute.assert_not_called()

    def test_validate_only_never_calls_model_backends(self) -> None:
        with (
            mock.patch.object(
                independent, "load_real_behavior_backend",
                side_effect=AssertionError("behavior backend loaded"),
            ) as behavior,
            mock.patch.object(
                independent, "load_real_judge_backend",
                side_effect=AssertionError("judge backend loaded"),
            ) as judge,
        ):
            result = independent.validate_only(CONFIG)
        behavior.assert_not_called()
        judge.assert_not_called()
        self.assertEqual(result["status"], "P2_INDEPENDENT_TH_VALIDATE_ONLY_PASS")
        self.assertFalse(result["model_weights_loaded"])
        self.assertFalse(result["gpu_used"])
        self.assertFalse(result["generation_run"])
        self.assertFalse(result["judge_run"])

    def test_old_p2_runner_config_and_results_remain_unchanged(self) -> None:
        old = json.loads(OLD_CONFIG.read_text(encoding="utf-8"))
        validated = p2_runner.validate_p2_config(old)
        self.assertEqual(validated["schema_version"], "paper1-stage3-qwen25-p2-runner-v1")
        immutable = independent._validate_old_p2_immutable()
        self.assertEqual(len(immutable), 6)
        self.assertEqual(
            immutable[str(ROOT / "stage3_pipeline/p2_runner.py")],
            "c29faab0f0d5edfd67725b9e24b5bcde32101f83535569cd29b9393a1f4052d9",
        )

    def test_formal_metadata_contract_is_fixed(self) -> None:
        ledger = self.artifacts.ledger
        self.assertFalse(ledger["paper_result_eligible"])
        self.assertFalse(ledger["old_p2_run"])
        self.assertFalse(ledger["p1_run"])
        self.assertFalse(ledger["support_run"])
        self.assertFalse(ledger["k1_run"])
        self.assertFalse(ledger["formal_experiment_run"])
        source = (ROOT / "stage3_pipeline/p2_independent_runner.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"formal_experiment_run": not expected_fake_backend', source)
        self.assertIn('"formal_experiment_run": artifacts.ledger["formal_experiment_run"]', source)


if __name__ == "__main__":
    unittest.main()
