from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from stage3_pipeline import benign_integrity_runner as runner
from stage3_pipeline.core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    LogicalIdentityRegistry,
    PipelineError,
    canonical_sha256,
)
from stage3_pipeline.dose import build_call_dose_evidence, build_test_dose_binding
from stage3_pipeline.execution import build_logical_plan


ROOT = Path(__file__).resolve().parents[2]
TEMP_ROOT = ROOT / ".codex-temp"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
for _variable in ("TMPDIR", "TEMP", "TMP"):
    os.environ[_variable] = str(TEMP_ROOT.resolve())
for _variable in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
    os.environ[_variable] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def _fixture_prepared() -> runner.PreparedBenignIntegrity:
    dose = build_test_dose_binding(
        mu_all_tw=4.0,
        mu_content_tw=2.0,
        median_content_norm=8.0,
        rho_by_anchor={"A": 0.5, "T": 1.0, "H": 1.5},
    )
    screen = [f"screen:{index}" for index in range(30)]
    confirm = [f"confirm:{index}" for index in range(50)]
    benign = [f"benign:{index}" for index in range(30)]
    vectors = {index: f"vector:{index}" for index in range(30)}
    prompt_ids = screen + confirm + benign
    bindings = {
        "model_revision": "fake-behavior-revision",
        "template_sha256": "1" * 64,
        "rendered_prompt_sha256_by_id": {prompt: canonical_sha256(prompt) for prompt in prompt_ids},
        "layer": 3,
        "hook_site": "resid_pre",
        "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
        "code_sha256": "2" * 64,
        "config_sha256": "3" * 64,
        "environment_sha256": "4" * 64,
    }
    registry = build_logical_plan(
        bindings=bindings,
        screen_prompt_ids=screen,
        confirm_prompt_ids=confirm,
        benign_prompt_ids=benign,
        vector_ids_by_index=vectors,
        dose_binding=dose,
    )
    records = registry.records()
    support_rows = tuple(row for row in records if row["identity"]["block"] == "support")
    messages = {prompt: [{"role": "user", "content": prompt}] for prompt in prompt_ids}
    support = SimpleNamespace(
        config={"generation_config": DECODE_CONFIG, "judge_config": JUDGE_CONFIG},
        registry=registry,
        support_rows=support_rows,
        plan_inputs={"benign_prompt_ids": benign},
        vector_ids_by_index=vectors,
        vector_index_by_id={value: key for key, value in vectors.items()},
        dose_binding=dose,
        messages_by_prompt_id=messages,
        prompt_text_by_id={prompt: prompt for prompt in prompt_ids},
    )
    t_rows, clean_rows = runner.select_benign_identities(support)
    return runner.PreparedBenignIntegrity(
        config={"output_root": str(ROOT / ".codex-temp"), "support_run_path": "fixture", "p1_dose_binding_path": "fixture"},
        config_path=ROOT / "fixture.json",
        support=support,
        benign_T_rows=t_rows,
        benign_clean_rows=clean_rows,
        p1_result={"dose_binding": dose},
        support_validation={"ledger": {"anchors": {"T": {"status": "SUPPORTED"}}}},
        offline_guard_report={"category_counts": {"network": 0}, "blocked_attempt_count": 0},
    )


class FakeBehavior:
    capability = None

    def __init__(self, prepared: runner.PreparedBenignIntegrity, index: int, events: list[str]):
        self.index = index
        self.prepared = prepared
        self.events = events
        self.released = False
        self.calls: dict[str, int] = {}
        events.append(f"behavior_load:{index}")

    def __call__(self, identity: dict[str, object], request: dict[str, object]) -> dict[str, object]:
        logical_id = str(request["logical_id"])
        self.calls[logical_id] = self.calls.get(logical_id, 0) + 1
        if identity["block"] == "benign_T":
            if self.prepared.support.vector_index_by_id[identity["vector_id"]] != self.index:
                raise AssertionError("T identity was sent to the wrong vector session")
            evidence = build_call_dose_evidence(
                identity=identity,
                dose_binding=self.prepared.support.dose_binding,
                generation_status="COMPLETED",
                pre_hook_l2=1.0,
                post_hook_l2=1.0,
                vector_alignment=1.0,
                cosine_drift=0.0,
            )
            return {"output_text": "steered benign response", "diagnostics": {"hook_installed": True}, "dose_evidence": evidence}
        if identity["block"] != "benign_clean" or identity["vector_id"] is not None:
            raise AssertionError("clean row identity was changed")
        return {"output_text": "clean benign response", "diagnostics": {"hook_installed": False, "clean_identity": True}}

    def release(self) -> dict[str, object]:
        self.released = True
        self.events.append(f"behavior_release:{self.index}")
        return {"schema_version": "paper1-stage3-sequential-lifecycle-v1", "behavior_released": True, "behavior_hook_removed": True, "behavior_model_reference_cleared": True, "behavior_tokenizer_reference_cleared": True, "gc_collect_called": True, "gc_collected_count": 0, "cuda_available": False, "cuda_synchronize_called": False, "cuda_empty_cache_called": False, "models_concurrently_resident": False}


class FakeJudge:
    capability = None
    producer_identity = {"model_path_or_id": "fake-judge", "tokenizer_path_or_id": "fake-judge-tokenizer", "rubric_sha256": "5" * 64}

    def __init__(self, events: list[str]):
        self.events = events
        self.calls: dict[str, int] = {}
        self.released = False
        events.append("judge_load")

    def __call__(self, _attempt: int, request: dict[str, object]) -> str:
        logical_id = str(request["logical_id"])
        self.calls[logical_id] = self.calls.get(logical_id, 0) + 1
        context = request["backend_request"]
        if context["domain"] != "benign":
            raise AssertionError("judge domain is not benign")
        return json.dumps({"label": "helpful", "rationale": "fixed benign fixture"})

    def release(self) -> dict[str, object]:
        self.released = True
        self.events.append("judge_release")
        return {"judge_released": True, "judge_loaded_after_behavior_release": True, "models_concurrently_resident": False}


class BenignIntegrityRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prepared = _fixture_prepared()

    def test_selects_exact_ordered_cartesian_partition(self) -> None:
        t_rows, clean_rows = runner.select_benign_identities(self.prepared.support)
        self.assertEqual((len(t_rows), len(clean_rows)), (600, 30))
        prompts = list(self.prepared.support.plan_inputs["benign_prompt_ids"])
        vectors = [self.prepared.support.vector_ids_by_index[index] for index in runner.VECTOR_INDICES]
        self.assertEqual([(row["identity"]["prompt_id"], row["identity"]["vector_id"]) for row in t_rows], [(prompt, vector) for prompt in prompts for vector in vectors])
        self.assertEqual([row["identity"]["prompt_id"] for row in clean_rows], prompts)

    def test_identity_dose_and_clean_boundaries(self) -> None:
        for row in self.prepared.benign_T_rows:
            identity = row["identity"]
            self.assertEqual((identity["anchor"], identity["estimator"]), ("T", "mu_all_tw"))
            self.assertIsNotNone(identity["vector_id"])
        for row in self.prepared.benign_clean_rows:
            identity = row["identity"]
            self.assertEqual((identity["anchor"], identity["estimator"], identity["vector_id"]), ("clean", "clean", None))
            self.assertTrue(all(identity[field] == float(0.0).hex() for field in ("c_hex", "alpha_pre_dtype_hex", "alpha_post_dtype_hex", "rho_hex")))

    def test_fake_630_execution_lineage_and_sequential_release(self) -> None:
        events: list[str] = []
        behavior_instances: list[FakeBehavior] = []
        judge_instances: list[FakeJudge] = []
        def behavior_factory(prepared: runner.PreparedBenignIntegrity, index: int) -> FakeBehavior:
            backend = FakeBehavior(prepared, index, events); behavior_instances.append(backend); return backend
        def judge_factory(_prepared: runner.PreparedBenignIntegrity, lifecycle: dict[str, object]) -> FakeJudge:
            self.assertTrue(lifecycle["behavior_released"])
            backend = FakeJudge(events); judge_instances.append(backend); return backend
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            result = runner.run_prepared_benign_integrity(self.prepared, run_id="fake", behavior_backend_factory=behavior_factory, judge_backend_factory=judge_factory, output_directory_resolver=lambda _p, _id: Path(directory) / "run", require_real_backend=False)
            self.assertEqual(result["status"], "BENIGN_INTEGRITY_FAKE_630_PATH_PASS")
            self.assertEqual(len(json.loads((Path(directory) / "run" / "generation_records.json").read_text())["records"]), 630)
            self.assertEqual(events.index("behavior_release:29") < events.index("judge_load"), True)
            self.assertEqual({int(item.index) for item in behavior_instances}, set(runner.VECTOR_INDICES))
            files = {path.name for path in (Path(directory) / "run").iterdir()}
            self.assertEqual(files, runner.OUTPUT_FILES)

    def test_judge_label_domain_and_lineage_tamper_fail_closed(self) -> None:
        events: list[str] = []
        def behavior_factory(prepared: runner.PreparedBenignIntegrity, index: int) -> FakeBehavior:
            return FakeBehavior(prepared, index, events)
        def judge_factory(_prepared: runner.PreparedBenignIntegrity, _lifecycle: dict[str, object]) -> FakeJudge:
            return FakeJudge(events)
        artifacts = runner.execute_benign_integrity(self.prepared, behavior_backend_factory=behavior_factory, judge_backend_factory=judge_factory, require_real_backend=False)
        forged = copy.deepcopy(list(artifacts.judge_records)); forged[0]["domain"] = "harmful"
        with self.assertRaises(PipelineError):
            runner.reconcile_benign_integrity(self.prepared, generation_records=artifacts.generation_records, judge_records=forged, response_records=artifacts.response_records, dispositions=artifacts.dispositions)

    def test_real_capability_is_required_for_paper_execution(self) -> None:
        with self.assertRaisesRegex(PipelineError, "RealBehaviorBackend capability"):
            runner.execute_benign_integrity(self.prepared, behavior_backend_factory=lambda p, i: FakeBehavior(p, i, []), judge_backend_factory=lambda p, l: FakeJudge([]))

    def test_validate_only_does_not_load_or_write(self) -> None:
        config = ROOT / "configs/stage3/qwen25_benign_integrity_v1.json"
        with mock.patch.object(runner, "prepare_benign_integrity", return_value=self.prepared), mock.patch.object(runner.RealBehaviorBackend, "from_pretrained") as behavior, mock.patch.object(runner.RealJudgeBackend, "from_pretrained") as judge:
            result = runner.validate_only(config)
        behavior.assert_not_called(); judge.assert_not_called()
        self.assertFalse(result["model_weights_loaded"]); self.assertFalse(result["gpu_used"]); self.assertFalse(result["generation_run"]); self.assertFalse(result["judge_run"]); self.assertFalse(result["output_written"])


if __name__ == "__main__":
    unittest.main()
