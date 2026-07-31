from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from stage3_pipeline.core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    BudgetError,
    GenerationProducer,
    LogicalIdentityRegistry,
    PipelineError,
    TechnicalGenerationError,
    canonical_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
)
from stage3_pipeline.execution import OutputStore, assert_run_budget
from stage3_pipeline.dose import build_call_dose_evidence
from stage3_pipeline.offline_assets import AssetError, JsonInputSpec, OfflineJsonLoader
from stage3_pipeline.records import (
    RecordSchemaError,
    build_response_record,
    validate_generation_record,
    validate_judge_record,
    validate_response_record,
)
from stage3_pipeline.run_manifest import (
    RunManifestError,
    build_run_manifest,
    validate_run_manifest,
    write_run_manifest,
)
from tests.stage3.helpers import (
    P1_INPUT,
    ROOT,
    block_identity,
    completed_chain,
    identity,
    test_dose_binding,
)


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        local_temp = ROOT / ".codex-temp"
        local_temp.mkdir(exist_ok=True)
        os.environ.update({
            "TEMP": str(local_temp),
            "TMP": str(local_temp),
            "PYTHONDONTWRITEBYTECODE": "1",
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        })

    def registry(self, count: int = 1) -> tuple[LogicalIdentityRegistry, list[str]]:
        registry = LogicalIdentityRegistry()
        ids = [
            registry.register(identity(f"prompt-{index}", rendered_seed=str(index % 10)))
            for index in range(count)
        ]
        return registry, ids

    def test_smoke_producer_needs_no_lifecycle_or_receipt(self) -> None:
        registry, ids = self.registry()
        evidence = build_call_dose_evidence(
            identity=registry.require(ids[0]), dose_binding=test_dose_binding(),
            generation_status="COMPLETED", pre_hook_l2=2.0, post_hook_l2=2.1,
            vector_alignment=0.5, cosine_drift=0.1,
        )
        producer = GenerationProducer(
            registry,
            lambda _identity, _request: {
                "output_text": "fake output", "diagnostics": {}, "dose_evidence": evidence,
            },
            run_mode="smoke",
            fake_backend=True,
        )
        record = validate_generation_record(producer.produce(
            ids[0], {"logical_id": ids[0], "generation_config": DECODE_CONFIG}
        ))
        self.assertTrue(record["generation_completed"])
        self.assertFalse(record["paper_result_eligible"])
        self.assertNotIn("lifecycle", json.dumps(record).lower())
        self.assertNotIn("receipt", json.dumps(record).lower())

    def test_generation_producer_enforces_steered_and_clean_dose_contract(self) -> None:
        steered_registry, steered_ids = self.registry()
        with self.assertRaises(PipelineError):
            GenerationProducer(
                steered_registry,
                lambda _identity, _request: {"output_text": "missing", "diagnostics": {}},
                run_mode="smoke", fake_backend=True,
            ).produce(
                steered_ids[0],
                {"logical_id": steered_ids[0], "generation_config": DECODE_CONFIG},
            )

        clean_identity = block_identity("harmful_clean", "clean-dose-rejected")
        clean_registry = LogicalIdentityRegistry()
        clean_id = clean_registry.register(clean_identity)
        with self.assertRaises(PipelineError):
            GenerationProducer(
                clean_registry,
                lambda _identity, _request: {
                    "output_text": "clean", "diagnostics": {}, "dose_evidence": {},
                },
                run_mode="smoke", fake_backend=True,
            ).produce(clean_id, {"logical_id": clean_id, "generation_config": DECODE_CONFIG})

    def test_retry_and_judge_work_without_authorization_artifacts(self) -> None:
        registry, ids = self.registry()
        evidence = build_call_dose_evidence(
            identity=registry.require(ids[0]), dose_binding=test_dose_binding(),
            generation_status="COMPLETED", pre_hook_l2=2.0, post_hook_l2=2.1,
            vector_alignment=0.5, cosine_drift=0.1,
        )
        calls = 0

        def backend(_identity: object, _request: object) -> dict[str, object]:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TechnicalGenerationError("transient")
            return {"output_text": "recovered", "diagnostics": {}, "dose_evidence": evidence}

        generation = GenerationProducer(
            registry, backend, run_mode="smoke", fake_backend=True
        ).produce(ids[0], {"logical_id": ids[0], "generation_config": DECODE_CONFIG})
        self.assertEqual(generation["retry_count"], 1)
        judge_calls = 0

        def judge(_attempt: int, _request: object) -> str:
            nonlocal judge_calls
            judge_calls += 1
            return "not json" if judge_calls == 1 else '{"label":"safe","rationale":"ok"}'

        record = validate_judge_record(parse_judge_with_retry(
            ids[0], judge, {"logical_id": ids[0], "judge_config": JUDGE_CONFIG},
            registry=registry, generation_record=generation, run_mode="smoke",
            judge_identity={
                "model_path_or_id": "fake-judge", "tokenizer_path_or_id": "fake-tokenizer",
                "rubric_sha256": "1" * 64,
            }, fake_backend=True,
        ))
        self.assertEqual(record["label"], "safe")
        self.assertEqual(len(record["attempts"]), 2)
        invalid = json.loads(json.dumps(record))
        invalid["attempts"][0]["status"] = "PARSED"
        invalid["record_sha256"] = canonical_sha256({key: value for key, value in invalid.items() if key != "record_sha256"})
        with self.assertRaises(RecordSchemaError):
            validate_judge_record(invalid)

    def test_pilot_override_is_recorded_and_paper_defaults_remain_fixed(self) -> None:
        pilot_config = {**DECODE_CONFIG, "max_new_tokens": 32}
        registry, ids = self.registry()
        evidence = build_call_dose_evidence(
            identity=registry.require(ids[0]), dose_binding=test_dose_binding(),
            generation_status="COMPLETED", pre_hook_l2=2.0, post_hook_l2=2.1,
            vector_alignment=0.5, cosine_drift=0.1,
        )
        pilot = GenerationProducer(
            registry,
            lambda _identity, _request: {
                "output_text": "pilot", "diagnostics": {}, "dose_evidence": evidence,
            },
            run_mode="pilot", generation_config=pilot_config, fake_backend=True, item_budget=1,
        ).produce(ids[0], {"logical_id": ids[0], "generation_config": pilot_config})
        self.assertEqual(pilot["generation_config"], pilot_config)
        with self.assertRaises(PipelineError):
            GenerationProducer(
                registry, lambda _identity, _request: {}, run_mode="paper",
                generation_config=pilot_config, fake_backend=True,
            )
        with self.assertRaises(BudgetError):
            GenerationProducer(
                registry, lambda _identity, _request: {}, run_mode="paper",
                fake_backend=True, item_budget=1,
            )

        clean_identity = block_identity("harmful_clean", "clean-prompt")
        clean_registry = LogicalIdentityRegistry()
        clean_id = clean_registry.register(clean_identity)
        generation = GenerationProducer(
            clean_registry,
            lambda _identity, _request: {"output_text": "clean", "diagnostics": {}},
            run_mode="smoke", fake_backend=True,
        ).produce(clean_id, {"logical_id": clean_id, "generation_config": DECODE_CONFIG})
        response = build_response_record(
            identity=clean_identity, generation_record=generation, judge_record=None,
            missingness_code="TERMINAL_PREJUDGE_FAILURE", dose_evidence=None,
        )
        self.assertEqual(response["missingness_code"], "TERMINAL_PREJUDGE_FAILURE")
        self.assertFalse(validate_response_record(response)["paper_result_eligible"])

    def test_budget_schema_missing_input_and_output_overwrite_fail_closed(self) -> None:
        registry, _ids = self.registry()
        with self.assertRaises(BudgetError):
            GenerationProducer(
                registry, lambda _identity, _request: {}, run_mode="smoke",
                fake_backend=True, item_budget=3,
            )
        with self.assertRaises(PipelineError):
            assert_run_budget("paper", 5_580, 100)
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            root = Path(temporary)
            loader = OfflineJsonLoader(root, [JsonInputSpec(
                "missing.json", "array", row_count=1,
                ordered_fields=("id",), identity_fields=("id",),
                field_types=(("id", "string"),), expected_sha256="0" * 64,
                expected_byte_length=1, expected_frame_sha256="0" * 64,
                source_repository="test/repository", source_revision="test-revision-1",
                source_path_or_config_split="fixtures/missing.json", license="CC0-1.0",
                provenance="synthetic missing-file fixture",
            )])
            with self.assertRaises(AssetError):
                loader.load("missing.json")
            store = OutputStore(root / "outputs")
            store.write_json_once("record.json", {"ok": True})
            with self.assertRaises(PipelineError):
                store.write_json_once("record.json", {"ok": False})

    def test_manifest_records_clean_and_dirty_git_state_and_refuses_overwrite(self) -> None:
        chain = completed_chain("support", run_mode="pilot")
        guard = offline_execution_guard()
        with guard:
            pass
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            temporary_root = Path(temporary)
            repository = temporary_root / "repository"
            repository.mkdir()
            subprocess.run(
                ["git", "init"], cwd=repository, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                [
                    "git", "-c", "user.name=Stage3 Test",
                    "-c", "user.email=stage3-test@example.invalid",
                    "commit", "--allow-empty", "-m", "initial",
                ],
                cwd=repository, check=True, capture_output=True, text=True,
            )
            clean_output = temporary_root / "clean-output"
            clean_manifest = build_run_manifest(
                repo_root=repository, run_mode="pilot", command=["python", "pilot.py"],
                started_at_utc="2026-07-30T00:00:00Z",
                completed_at_utc="2026-07-30T00:00:01Z",
                model_path_or_id="fake-model", tokenizer_path_or_id="fake-tokenizer",
                input_paths=[P1_INPUT], generation_config=DECODE_CONFIG, seed=42,
                gpu_identity=None, output_directory=clean_output, exit_status="success", exit_code=0,
                fake_backend=True, reconciliation=chain["reconciliation"], offline_guard=guard,
                runtime_versions={"python": "test", "torch": None, "transformers": None, "cuda": None},
            )
            self.assertFalse(clean_manifest["dirty"])

            (repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            dirty_output = temporary_root / "dirty-output"
            dirty_manifest = build_run_manifest(
                repo_root=repository, run_mode="pilot", command=["python", "pilot.py"],
                started_at_utc="2026-07-30T00:00:00Z",
                completed_at_utc="2026-07-30T00:00:01Z",
                model_path_or_id="fake-model", tokenizer_path_or_id="fake-tokenizer",
                input_paths=[P1_INPUT], generation_config=DECODE_CONFIG, seed=42,
                gpu_identity=None, output_directory=dirty_output, exit_status="success", exit_code=0,
                fake_backend=True, reconciliation=chain["reconciliation"], offline_guard=guard,
                runtime_versions={"python": "test", "torch": None, "transformers": None, "cuda": None},
            )
            self.assertTrue(dirty_manifest["dirty"])

            path = write_run_manifest(clean_output, clean_manifest)
            self.assertEqual(validate_run_manifest(json.loads(path.read_text(encoding="utf-8")))["run_mode"], "pilot")
            invalid = clean_manifest.as_dict()
            invalid["reconciliation"]["completed_item_count"] = 0
            with self.assertRaises(RunManifestError):
                validate_run_manifest(invalid)
            with self.assertRaises(RunManifestError):
                write_run_manifest(clean_output, clean_manifest)


if __name__ == "__main__":
    unittest.main()
