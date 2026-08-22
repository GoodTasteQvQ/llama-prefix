from __future__ import annotations

import copy
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stage3_pipeline import harmful_clean_runner as runner
from stage3_pipeline.core import (
    GenerationProducer,
    IdentityError,
    PipelineError,
    TechnicalGenerationError,
    canonical_sha256,
    normalize_identity,
)
from stage3_pipeline.real_backend import RealBehaviorBackend
from stage3_pipeline.real_judge import RealJudgeBackend


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/stage3/qwen25_harmful_clean_v1.json"
TEMP_ROOT = ROOT / ".codex-temp"
RUN_SCRIPT = importlib.import_module("scripts.stage3_production.run_harmful_clean")

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
        events: list[str],
        *,
        technical_failure_ids: set[str] | None = None,
    ) -> None:
        self.events = events
        self.technical_failure_ids = technical_failure_ids or set()
        self.calls: dict[str, int] = {}
        self.released = False
        events.append("behavior_load")

    def __call__(
        self, identity: dict[str, object], request: dict[str, object]
    ) -> dict[str, object]:
        logical_id = str(request["logical_id"])
        self.calls[logical_id] = self.calls.get(logical_id, 0) + 1
        self.events.append(f"generation:{logical_id}")
        if identity["vector_id"] is not None or identity["estimator"] != "clean":
            raise AssertionError("fake clean backend received a steered identity")
        if logical_id in self.technical_failure_ids:
            raise TechnicalGenerationError("fixture technical failure")
        return {
            "output_text": f"clean response for {identity['prompt_id']}",
            "diagnostics": {
                "fake_backend": True,
                "hook_installed": False,
                "clean_identity": True,
            },
        }

    def release(self) -> dict[str, object]:
        self.released = True
        self.events.append("behavior_release")
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

    def __init__(
        self,
        events: list[str],
        *,
        parse_failure_ids: set[str] | None = None,
        broken_ids: set[str] | None = None,
    ) -> None:
        self.events = events
        self.parse_failure_ids = parse_failure_ids or set()
        self.broken_ids = broken_ids or set()
        self.calls: dict[str, int] = {}
        self.released = False
        events.append("judge_load")

    def __call__(self, _attempt: int, request: dict[str, object]) -> str:
        logical_id = str(request["logical_id"])
        self.calls[logical_id] = self.calls.get(logical_id, 0) + 1
        self.events.append(f"judge:{logical_id}")
        if logical_id in self.parse_failure_ids:
            return "not-json"
        label = "broken" if logical_id in self.broken_ids else "safe"
        return json.dumps({"label": label, "rationale": "fixed fake fixture"})

    def release(self) -> dict[str, object]:
        self.released = True
        self.events.append("judge_release")
        return {
            "judge_released": True,
            "judge_loaded_after_behavior_release": True,
            "models_concurrently_resident": False,
        }


class HarmfulCleanRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = runner.prepare_harmful_clean(CONFIG)
        cls.temporary = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        cls.output = Path(cls.temporary.name) / "fake-50"
        cls.events: list[str] = []
        cls.behavior: FakeBehaviorBackend | None = None
        cls.judge: FakeJudgeBackend | None = None

        def behavior_factory(
            _prepared: runner.PreparedHarmfulClean,
        ) -> FakeBehaviorBackend:
            cls.behavior = FakeBehaviorBackend(cls.events)
            return cls.behavior

        def judge_factory(
            _prepared: runner.PreparedHarmfulClean,
            lifecycle: dict[str, object],
        ) -> FakeJudgeBackend:
            if lifecycle["behavior_released"] is not True:
                raise AssertionError("judge loaded before behavior release")
            cls.judge = FakeJudgeBackend(cls.events)
            return cls.judge

        cls.fake_result = runner.run_prepared_harmful_clean(
            cls.prepared,
            run_id="fake-50",
            behavior_backend_factory=behavior_factory,
            judge_backend_factory=judge_factory,
            output_directory_resolver=lambda _prepared, _run_id: cls.output,
            require_real_backend=False,
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

    def test_selects_exact_50_canonical_clean_identities(self) -> None:
        rows = runner.select_harmful_clean_identities(self.prepared.support)
        self.assertEqual(rows, self.prepared.clean_rows)
        self.assertEqual(len(rows), 50)
        registry = {
            row["logical_id"]: row["identity"]
            for row in self.prepared.support.registry.records()
        }
        self.assertEqual(
            {row["logical_id"] for row in rows},
            {
                logical_id
                for logical_id, identity in registry.items()
                if identity["block"] == "harmful_clean"
            },
        )
        for row in rows:
            self.assertEqual(row["identity"], registry[row["logical_id"]])

    def test_clean_identity_has_null_vector_and_all_zero_dose_fields(self) -> None:
        prompts = set(self.prepared.support.plan_inputs["confirm_prompt_ids"])
        self.assertEqual(
            {row["identity"]["prompt_id"] for row in self.prepared.clean_rows}, prompts
        )
        for row in self.prepared.clean_rows:
            identity = row["identity"]
            self.assertEqual(identity["block"], "harmful_clean")
            self.assertEqual(identity["domain"], "harmful")
            self.assertEqual(identity["split"], "D_behavior_confirm")
            self.assertEqual(identity["anchor"], "clean")
            self.assertEqual(identity["estimator"], "clean")
            self.assertIsNone(identity["vector_id"])
            for field in (
                "c_hex",
                "alpha_pre_dtype_hex",
                "alpha_post_dtype_hex",
                "rho_hex",
            ):
                self.assertEqual(identity[field], float(0.0).hex())

    def test_clean_identity_cannot_forge_anchor_vector_or_p2_dose(self) -> None:
        identity = copy.deepcopy(self.prepared.clean_rows[0]["identity"])
        for field, value in (
            ("anchor", "A"),
            ("estimator", "mu_all_tw"),
            ("vector_id", "sha256:" + "a" * 64),
            ("c_hex", float(1.0).hex()),
            ("alpha_pre_dtype_hex", float(1.0).hex()),
            ("alpha_post_dtype_hex", float(1.0).hex()),
            ("rho_hex", float(1.0).hex()),
        ):
            forged = copy.deepcopy(identity)
            forged[field] = value
            with self.assertRaises(IdentityError, msg=field):
                normalize_identity(forged)

    def test_fake_fixture_completes_50_item_accounting_and_lineage(self) -> None:
        self.assertEqual(self.fake_result["status"], "HARMFUL_CLEAN_FAKE_50_PATH_PASS")
        self.assertEqual(
            (len(self.generations), len(self.judges), len(self.responses), len(self.dispositions)),
            (50, 50, 50, 50),
        )
        generation_by_id = {record["logical_id"]: record for record in self.generations}
        judge_by_id = {record["logical_id"]: record for record in self.judges}
        response_by_id = {record["logical_id"]: record for record in self.responses}
        for logical_id, generation in generation_by_id.items():
            judge = judge_by_id[logical_id]
            response = response_by_id[logical_id]
            self.assertEqual(
                judge["generation_record_sha256"], generation["record_sha256"]
            )
            self.assertEqual(
                response["generation_record_sha256"], generation["record_sha256"]
            )
            self.assertEqual(response["judge_record_sha256"], judge["record_sha256"])
            self.assertIsNone(response["dose_evidence"])
        self.assertLess(
            self.events.index("behavior_release"), self.events.index("judge_load")
        )
        self.assertEqual(self.events.count("behavior_load"), 1)
        self.assertEqual(self.events.count("judge_load"), 1)

    def test_generation_and_judge_failures_preserve_terminal_missingness(self) -> None:
        events: list[str] = []
        generation_failure_id = self.prepared.clean_rows[0]["logical_id"]
        judge_failure_id = self.prepared.clean_rows[1]["logical_id"]
        broken_id = self.prepared.clean_rows[2]["logical_id"]
        behavior = FakeBehaviorBackend(
            events, technical_failure_ids={generation_failure_id}
        )
        judge = FakeJudgeBackend(
            events,
            parse_failure_ids={judge_failure_id},
            broken_ids={broken_id},
        )
        artifacts = runner.execute_harmful_clean(
            self.prepared,
            behavior_backend_factory=lambda _prepared: behavior,
            judge_backend_factory=lambda _prepared, _lifecycle: judge,
            require_real_backend=False,
        )
        responses = {record["logical_id"]: record for record in artifacts.response_records}
        dispositions = {
            record["logical_id"]: record for record in artifacts.dispositions
        }
        self.assertEqual(behavior.calls[generation_failure_id], 2)
        self.assertNotIn(generation_failure_id, judge.calls)
        self.assertEqual(
            responses[generation_failure_id]["missingness_code"],
            "TERMINAL_GENERATION_TECHNICAL_FAILURE",
        )
        self.assertEqual(
            dispositions[generation_failure_id]["terminal_disposition"],
            "TERMINAL_GENERATION_TECHNICAL_FAILURE",
        )
        self.assertEqual(judge.calls[judge_failure_id], 2)
        self.assertEqual(
            responses[judge_failure_id]["missingness_code"],
            "TERMINAL_JUDGE_FAILURE",
        )
        self.assertEqual(
            dispositions[judge_failure_id]["terminal_disposition"],
            "TERMINAL_JUDGE_FAILURE",
        )
        self.assertEqual(judge.calls[broken_id], 1)
        self.assertEqual(responses[broken_id]["label"], "broken")
        self.assertEqual(max(behavior.calls.values()), 2)
        self.assertEqual(max(judge.calls.values()), 2)

    def test_paper_mode_rejects_ordinary_callable_backend_before_generation(self) -> None:
        events: list[str] = []
        behavior = FakeBehaviorBackend(events)
        judge_factory = mock.Mock()
        with self.assertRaisesRegex(PipelineError, "RealBehaviorBackend capability"):
            runner.execute_harmful_clean(
                self.prepared,
                behavior_backend_factory=lambda _prepared: behavior,
                judge_backend_factory=judge_factory,
            )
        self.assertEqual(events, ["behavior_load", "behavior_release"])
        self.assertEqual(behavior.calls, {})
        judge_factory.assert_not_called()

    def test_duplicate_missing_and_mismatched_ids_fail_closed(self) -> None:
        arguments = {
            "generation_records": self.generations,
            "judge_records": self.judges,
            "response_records": self.responses,
            "dispositions": self.dispositions,
            "expected_fake_backend": True,
        }
        for field, value in (
            ("generation_records", self.generations + [self.generations[0]]),
            ("judge_records", self.judges[:-1]),
            ("response_records", self.responses[:-1]),
            ("dispositions", self.dispositions[:-1]),
        ):
            forged = dict(arguments)
            forged[field] = value
            with self.assertRaises((IdentityError, PipelineError), msg=field):
                runner.reconcile_harmful_clean(self.prepared, **forged)

        forged_judges = copy.deepcopy(self.judges)
        forged_judges[0]["generation_record_sha256"] = "f" * 64
        forged_judges[0]["record_sha256"] = canonical_sha256({
            key: value
            for key, value in forged_judges[0].items()
            if key != "record_sha256"
        })
        forged = dict(arguments)
        forged["judge_records"] = forged_judges
        with self.assertRaises(PipelineError):
            runner.reconcile_harmful_clean(self.prepared, **forged)

    def test_response_set_has_no_dose_evidence_or_vector_copy(self) -> None:
        self.assertTrue(all(record["dose_evidence"] is None for record in self.responses))
        self.assertTrue(all(record["vector_id"] is None for record in self.responses))
        self.assertTrue(all(
            "dose_evidence" not in generation["attempts"][-1]["diagnostics"]
            for generation in self.generations
        ))
        output_names = {path.name for path in self.output.iterdir()}
        self.assertEqual(output_names, {
            "canonical_registry_reference.json",
            "harmful_clean_identities.json",
            "generation_records.json",
            "judge_records.json",
            "response_records.json",
            "execution_dispositions.json",
            "harmful_clean_ledger.json",
            "execution_identity.json",
        })
        self.assertFalse(any(
            marker in name.lower()
            for name in output_names
            for marker in ("p1", "support", "p2", "k1", "benign", "bootstrap")
        ))

    def test_ledger_is_clean_only_and_does_not_claim_full_reconciliation(self) -> None:
        ledger = json.loads(
            (self.output / "harmful_clean_ledger.json").read_text(encoding="utf-8")
        )
        self.assertEqual(ledger["harmful_clean_identity_count"], 50)
        self.assertEqual(ledger["disposition_count"], 50)
        self.assertTrue(ledger["harmful_clean_only_reconciliation"])
        self.assertFalse(ledger["complete_stage3_reconciliation"])
        self.assertFalse(ledger["paper_result_eligible"])
        self.assertFalse(ledger["formal_experiment_run"])
        self.assertEqual(ledger["dose_evidence_record_count"], 0)
        self.assertEqual(ledger["vector_identity_copy_count"], 0)
        for field in ("p1_run", "support_run", "p2_run", "k1_run"):
            self.assertFalse(ledger[field])
        self.assertEqual(ledger["k1_additional_generation_calls"], 0)
        self.assertEqual(ledger["k1_additional_judge_calls"], 0)

    def test_existing_output_directory_is_rejected_before_backends(self) -> None:
        existing = Path(self.temporary.name) / "existing"
        existing.mkdir()
        behavior_factory = mock.Mock()
        judge_factory = mock.Mock()
        with self.assertRaisesRegex(PipelineError, "refusing to overwrite"):
            runner.run_prepared_harmful_clean(
                self.prepared,
                run_id="existing",
                behavior_backend_factory=behavior_factory,
                judge_backend_factory=judge_factory,
                output_directory_resolver=lambda _prepared, _run_id: existing,
            )
        behavior_factory.assert_not_called()
        judge_factory.assert_not_called()

    def test_validate_only_never_loads_or_executes_models(self) -> None:
        with (
            mock.patch.object(RealBehaviorBackend, "from_pretrained") as behavior_loader,
            mock.patch.object(RealJudgeBackend, "from_pretrained") as judge_loader,
            mock.patch.object(GenerationProducer, "produce") as generation,
            mock.patch.object(runner, "parse_judge_with_retry") as judge,
        ):
            result = runner.validate_only(CONFIG)
        behavior_loader.assert_not_called()
        judge_loader.assert_not_called()
        generation.assert_not_called()
        judge.assert_not_called()
        self.assertEqual(result["status"], "HARMFUL_CLEAN_RUNNER_VALIDATE_ONLY_PASS")
        self.assertEqual(result["harmful_clean_identity_count"], 50)
        self.assertEqual(result["prompt_count"], 50)
        for field in (
            "model_weights_loaded",
            "gpu_used",
            "forward_executed",
            "generation_run",
            "judge_run",
            "harmful_clean_run",
            "p1_run",
            "support_run",
            "p2_run",
            "k1_run",
            "formal_experiment_run",
            "paper_result_eligible",
        ):
            self.assertFalse(result[field])
        self.assertEqual(result["network_attempts"], 0)
        self.assertEqual(result["blocked_attempts"], 0)

    def test_public_paper_entry_is_bound_to_real_backends(self) -> None:
        with (
            mock.patch.object(
                runner, "prepare_harmful_clean", return_value=self.prepared
            ) as prepare,
            mock.patch.object(
                runner,
                "run_prepared_harmful_clean",
                return_value={"status": "sentinel"},
            ) as run_prepared,
        ):
            result = runner.run_harmful_clean(
                CONFIG, run_mode="paper", run_id="formal-run"
            )
        self.assertEqual(result, {"status": "sentinel"})
        prepare.assert_called_once_with(CONFIG)
        kwargs = run_prepared.call_args.kwargs
        self.assertIs(kwargs["behavior_backend_factory"], runner.load_real_behavior_backend)
        self.assertIs(kwargs["judge_backend_factory"], runner.load_real_judge_backend)
        self.assertTrue(kwargs["require_real_backend"])

    def test_cli_validate_only_routes_without_a_run_id(self) -> None:
        expected = {
            "status": "HARMFUL_CLEAN_RUNNER_VALIDATE_ONLY_PASS",
            "paper_result_eligible": False,
            "formal_experiment_run": False,
        }
        with (
            mock.patch.object(RUN_SCRIPT, "validate_only", return_value=expected) as validate,
            mock.patch("builtins.print") as output,
        ):
            return_code = RUN_SCRIPT.main(["--config", str(CONFIG), "--validate-only"])
        self.assertEqual(return_code, 0)
        validate.assert_called_once_with(CONFIG)
        self.assertEqual(json.loads(output.call_args.args[0]), expected)


if __name__ == "__main__":
    unittest.main()
