from __future__ import annotations

import copy
import hashlib
import json
import os
import pickle
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

import torch
from torch import nn

from stage3_pipeline.core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    GenerationProducer,
    IdentityError,
    LogicalIdentityRegistry,
    PipelineError,
    TechnicalGenerationError,
    canonical_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
)
from stage3_pipeline.dose import (
    build_call_dose_evidence,
    build_test_dose_binding,
    validate_dose_binding,
)
from stage3_pipeline.execution import reconcile_execution
from stage3_pipeline.real_backend import (
    RealBehaviorBackend,
    bind_dose_post_dtype,
    inspect_local_model_assets,
    load_candidate_vector,
)
from stage3_pipeline.real_judge import (
    RealJudgeBackend,
    split_qwen3_thinking_final,
)
from stage3_pipeline.records import build_block_response_record
from stage3_pipeline.run_manifest import (
    RunManifestError,
    build_run_manifest,
    validate_manifest_for_paper_loader,
)
from tests.stage3.helpers import P1_INPUT, block_identity, completed_chain, test_dose_binding


ROOT = Path(__file__).resolve().parents[2]


class TinyTokenizer:
    chat_template = "{{ messages[0]['content'] }}|{{ messages[1]['content'] }}"
    all_special_ids = [0]
    pad_token_id = 0
    eos_token_id = 0
    unk_token_id = 98

    def __init__(self, *, judge: bool = False) -> None:
        self.judge = judge

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True, **kwargs):
        if not tokenize:
            return "\n".join(message["role"] + ":" + message["content"] for message in messages)
        return self(messages, return_tensors="pt")

    def __call__(self, _rendered, return_tensors="pt"):
        return {
            "input_ids": torch.tensor([[1, 2, 3]], dtype=torch.long),
            "attention_mask": torch.ones((1, 3), dtype=torch.long),
        }

    def decode(self, ids, skip_special_tokens=True):
        values = ids.tolist() if hasattr(ids, "tolist") else list(ids)
        if self.judge:
            if values == [9, 10]:
                return '{"label":"safe","rationale":"ok"}'
            return {9: "{", 10: '"label":"safe","rationale":"ok"}', 11: "thinking"}.get(
                values[0] if values else -1, ""
            )
        return "tiny output"

    def convert_tokens_to_ids(self, token):
        return 99 if token == "</think>" else -1

    def convert_ids_to_tokens(self, token_id):
        return "</think>" if token_id == 99 else "<unk>"


class TinyLayer(nn.Module):
    def forward(self, hidden):
        return hidden


class TinyBehaviorModel(nn.Module):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__()
        self.model = nn.Module()
        self.model.layers = nn.ModuleList([TinyLayer() for _ in range(10)])
        self.config = type("Config", (), {"hidden_size": 4})()
        self.fail = fail
        self.generate_calls = 0

    def generate(self, input_ids, attention_mask=None, **kwargs):
        self.generate_calls += 1
        hidden = torch.ones((1, 3, 4), dtype=torch.float32)
        self.model.layers[1](hidden)
        if self.fail:
            raise RuntimeError("fixture generation failure")
        self.model.layers[1](torch.ones((1, 1, 4), dtype=torch.float32))
        self.model.layers[1](torch.ones((1, 1, 4), dtype=torch.float32))
        return torch.tensor([[1, 2, 3, 4, 5]], dtype=torch.long)

    def to(self, _device):
        return self


class TinyJudgeModel(nn.Module):
    config = type("Config", (), {"hidden_size": 4})()

    def generate(self, input_ids, attention_mask=None, **kwargs):
        # 11 is thinking, 99 is semantic </think>, 9/10 are the final JSON chunks.
        return torch.tensor([[1, 2, 3, 11, 99, 9, 10]], dtype=torch.long)

    def to(self, _device):
        return self


class FakeLoader:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def from_pretrained(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return self.value


class RealBackendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update({
            "TMPDIR": str(ROOT / ".codex-temp"),
            "TEMP": str(ROOT / ".codex-temp"),
            "TMP": str(ROOT / ".codex-temp"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        })

    def _asset_dir(self):
        temp = tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp")
        path = Path(temp.name)
        (path / "config.json").write_text(json.dumps({
            "architectures": ["TinyForCausalLM"],
            "hidden_size": 4,
            "num_hidden_layers": 2,
        }), encoding="utf-8")
        (path / "model.safetensors.index.json").write_text("{}", encoding="utf-8")
        (path / "tokenizer.json").write_text("{}", encoding="utf-8")
        (path / "tokenizer_config.json").write_text("{}", encoding="utf-8")
        return temp, path

    def _backend(self, *, fail=False):
        tokenizer = TinyTokenizer()
        behavior_identity = {
            "model_revision": "a" * 64,
            "chat_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
            "hidden_size": 4,
            "dtype": "float32",
        }
        vector = torch.tensor([1.0, 0.0, 0.0, 0.0])
        vector_identity = {
            "vector_id": "vector-fixture",
            "vector_file_sha256": "b" * 64,
            "vector_index": 0,
            "layer": 1,
            "hook_site": "resid_pre",
            "selected_dtype": "float32",
            "load_device": "cpu",
            "normalization": "none",
        }
        return RealBehaviorBackend(
            model=TinyBehaviorModel(fail=fail),
            tokenizer=tokenizer,
            behavior_identity=behavior_identity,
            vector=vector,
            vector_identity=vector_identity,
            dose_binding=bind_dose_post_dtype(test_dose_binding(), dtype="float32"),
            layer=1,
            hook_site="resid_pre",
            device="cpu",
        )

    def _loaded_behavior_backend(self, *, fail: bool = False):
        temp, path = self._asset_dir()
        self.addCleanup(temp.cleanup)
        vector_path = path / "vector.pt"
        torch.save(torch.tensor([[1.0, 0.0, 0.0, 0.0]]), vector_path)
        return RealBehaviorBackend.from_pretrained(
            model_path=path,
            tokenizer_path=path,
            vector_path=vector_path,
            vector_index=0,
            dose_binding=bind_dose_post_dtype(test_dose_binding(), dtype="float32"),
            layer=1,
            hook_site="resid_pre",
            dtype="float32",
            device="cpu",
            tokenizer_loader=FakeLoader(TinyTokenizer()),
            model_loader=FakeLoader(TinyBehaviorModel(fail=fail)),
        )

    def _loaded_judge_backend(self, lifecycle):
        temp, path = self._asset_dir()
        self.addCleanup(temp.cleanup)
        return RealJudgeBackend.from_pretrained(
            model_path=path,
            tokenizer_path=path,
            device="cpu",
            lifecycle=lifecycle,
            tokenizer_loader=FakeLoader(TinyTokenizer(judge=True)),
            model_loader=FakeLoader(TinyJudgeModel()),
        )

    def _identity(self, clean=False):
        value = block_identity("harmful_clean" if clean else "support", "tiny")
        tokenizer = TinyTokenizer()
        value["model_revision"] = "a" * 64
        value["template_sha256"] = hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()
        value["rendered_prompt_sha256"] = hashlib.sha256(
            "system:hello\nuser:question".encode()
        ).hexdigest()
        value["generation_config_sha256"] = canonical_sha256(DECODE_CONFIG)
        value["hook_site"] = "resid_pre"
        if not clean:
            value["vector_id"] = "vector-fixture"
            value.update(
                validate_dose_binding(
                    bind_dose_post_dtype(test_dose_binding(), dtype="float32")
                )["A"]["mu_all_tw"]
            )
        return value

    def _request(self, logical_id="unused"):
        return {
            "logical_id": logical_id,
            "generation_config": DECODE_CONFIG,
            "messages": [
                {"role": "system", "content": "hello"},
                {"role": "user", "content": "question"},
            ],
        }

    def _real_completed_chain(self, prompt_id="real-manifest"):
        backend = self._loaded_behavior_backend()
        identity = self._identity(clean=False)
        identity["model_revision"] = backend.behavior_identity["model_revision"]
        identity["template_sha256"] = backend.behavior_identity["chat_template_sha256"]
        identity["vector_id"] = backend.vector_identity["vector_id"]
        identity["prompt_id"] = prompt_id
        registry = LogicalIdentityRegistry()
        logical_id = registry.register(identity)
        generation = GenerationProducer(
            registry,
            backend,
            run_mode="smoke",
            fake_backend=False,
            capability=backend.capability,
            item_budget=1,
        ).produce(logical_id, self._request(logical_id))
        lifecycle = backend.release()
        judge_backend = self._loaded_judge_backend(lifecycle)
        judge = parse_judge_with_retry(
            logical_id,
            judge_backend,
            {
                "logical_id": logical_id,
                "judge_config": JUDGE_CONFIG,
                "backend_request": {
                    "prompt": "question",
                    "response": generation["output_text"],
                    "domain": "harmful",
                },
            },
            registry=registry,
            generation_record=generation,
            run_mode="smoke",
            judge_identity=judge_backend.producer_identity,
            fake_backend=False,
            capability=judge_backend.capability,
        )
        response = build_block_response_record(
            identity=identity,
            generation_record=generation,
            judge_record=judge,
            dose_evidence=generation["attempts"][-1]["diagnostics"]["dose_evidence"],
        )
        disposition = {
            "schema_version": "paper1-stage3-execution-disposition-v2",
            "logical_id": logical_id,
            "identity_sha256": canonical_sha256(identity),
            "terminal_disposition": response["terminal_status"],
            "generation_record_sha256": generation["record_sha256"],
            "judge_record_sha256": judge["record_sha256"],
            "response_record_sha256": response["record_sha256"],
            "integrity_block_reason": None,
        }
        reconciliation = reconcile_execution(
            registry,
            run_mode="smoke",
            generation_records=[generation],
            judge_records=[judge],
            response_records=[response],
            dispositions=[disposition],
            dose_binding=backend.dose_binding,
        )
        lifecycle = judge_backend.release()
        backend_identity = {
            "schema_version": "paper1-stage3-real-backend-provenance-v1",
            "asset_status": "development_only",
            "identity_level": "development_candidate",
            "behavior_identity": dict(backend.behavior_identity),
            "judge_identity": dict(judge_backend.judge_identity),
            "vector_identity": dict(backend.vector_identity),
            "hook_identity": {
                "schema_version": "hook",
                "layer": 1,
                "hook_site": "resid_pre",
                "phase": "decode-only",
                "use_cache": True,
            },
            "gpu_identity": {"device": "cuda:0"},
            "lifecycle": lifecycle,
            "output_identity": {
                "registry_sha256": registry.manifest()["registry_sha256"],
                "generation_records_sha256": canonical_sha256([generation]),
                "judge_records_sha256": canonical_sha256([judge]),
            },
        }
        return {
            "generation": generation,
            "judge": judge,
            "reconciliation": reconciliation,
            "registry_manifest": registry.manifest(),
            "backend_identity": backend_identity,
            "behavior_capability": backend.capability,
            "judge_capability": judge_backend.capability,
        }

    def test_local_only_and_identity_recording(self):
        temp, path = self._asset_dir()
        self.addCleanup(temp.cleanup)
        tokenizer_loader = FakeLoader(TinyTokenizer())
        model_loader = FakeLoader(TinyBehaviorModel())
        temp_vector = path / "vector.pt"
        torch.save(torch.ones((2, 4)), temp_vector)
        identity, _ = inspect_local_model_assets(
            model_path=path,
            tokenizer_path=path,
            model_role="behavior",
            dtype="bfloat16",
            device="cpu",
            tokenizer_loader=tokenizer_loader,
        )
        self.assertTrue(identity["local_files_only"])
        self.assertEqual(identity["model_role"], "behavior")
        self.assertEqual(identity["hidden_size"], 4)
        self.assertEqual(identity["layer_count"], 2)
        backend = RealBehaviorBackend.from_pretrained(
            model_path=path, tokenizer_path=path,
            vector_path=path / "vector.pt", vector_index=0,
            dose_binding=bind_dose_post_dtype(test_dose_binding(), dtype="bfloat16"),
            layer=1, hook_site="resid_pre",
            dtype="bfloat16", device="cpu", tokenizer_loader=tokenizer_loader,
            model_loader=model_loader,
        )
        self.assertTrue(model_loader.calls[0][1]["local_files_only"])
        self.assertFalse(model_loader.calls[0][1]["trust_remote_code"])
        self.assertEqual(backend.behavior_identity["model_architecture"], "TinyForCausalLM")
        self.assertEqual(backend.behavior_identity["hook_site"], "resid_pre")
        self.assertEqual(
            backend.behavior_identity["hook_semantics"], "forward_pre_hook_on_layer_input"
        )
        with self.assertRaises(PipelineError):
            load_candidate_vector(
                vector_path=temp_vector, vector_index=0, layer=1,
                hook_site="resid_post", hidden_size=4,
            )

    def test_unverified_callables_default_fake_and_declared_real_fails_pre_call(self):
        identity = self._identity(clean=False)
        registry = LogicalIdentityRegistry()
        logical_id = registry.register(identity)
        dose_binding = bind_dose_post_dtype(test_dose_binding(), dtype="float32")
        evidence = build_call_dose_evidence(
            identity=identity,
            dose_binding=dose_binding,
            generation_status="COMPLETED",
            pre_hook_l2=2.0,
            post_hook_l2=2.1,
            vector_alignment=0.5,
            cosine_drift=0.1,
        )
        generation_calls = []

        def fake_behavior(_identity, _request):
            generation_calls.append("called")
            return {
                "output_text": "fake output",
                "diagnostics": {},
                "dose_evidence": evidence,
            }

        generation = GenerationProducer(
            registry, fake_behavior, run_mode="smoke", item_budget=1
        ).produce(logical_id, self._request(logical_id))
        self.assertTrue(generation["fake_backend"])
        self.assertEqual(generation_calls, ["called"])

        rejected_behavior_calls = []

        def rejected_behavior(_identity, _request):
            rejected_behavior_calls.append("called")
            return {}

        with self.assertRaisesRegex(PipelineError, "verified behavior capability"):
            GenerationProducer(
                registry,
                rejected_behavior,
                run_mode="smoke",
                fake_backend=False,
                item_budget=1,
            )
        self.assertEqual(rejected_behavior_calls, [])

        judge_calls = []

        def rejected_judge(_attempt, _request):
            judge_calls.append("called")
            return '{"label":"safe","rationale":"should not run"}'

        with self.assertRaisesRegex(PipelineError, "verified judge capability"):
            parse_judge_with_retry(
                logical_id,
                rejected_judge,
                {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
                registry=registry,
                generation_record=generation,
                run_mode="smoke",
                judge_identity={
                    "model_path_or_id": "fake-judge",
                    "tokenizer_path_or_id": "fake-tokenizer",
                    "rubric_sha256": "1" * 64,
                },
                fake_backend=False,
            )
        self.assertEqual(judge_calls, [])

    def test_capabilities_are_loader_issued_role_bound_and_nonserializable(self):
        direct = self._backend()
        self.assertIsNone(direct.capability)
        chain = self._real_completed_chain("capability-positive")
        behavior_capability = chain["behavior_capability"]
        judge_capability = chain["judge_capability"]
        self.assertEqual(behavior_capability.role, "behavior")
        self.assertEqual(judge_capability.role, "judge")
        self.assertEqual(len(behavior_capability.identity_digest), 64)
        self.assertEqual(len(judge_capability.identity_digest), 64)
        self.assertFalse(chain["generation"]["fake_backend"])
        self.assertFalse(chain["judge"]["fake_backend"])
        with self.assertRaises(TypeError):
            pickle.dumps(behavior_capability)

        forged = behavior_capability.manifest_record()
        with self.assertRaisesRegex(PipelineError, "builder-issued"):
            GenerationProducer(
                LogicalIdentityRegistry(),
                lambda _identity, _request: {},
                run_mode="smoke",
                fake_backend=False,
                capability=forged,
            )

        with self.assertRaisesRegex(PipelineError, "behavior capability"):
            GenerationProducer(
                LogicalIdentityRegistry(),
                lambda _identity, _request: {},
                run_mode="smoke",
                fake_backend=False,
                capability=judge_capability,
            )

    def test_capability_backend_identity_and_role_mismatches_fail_closed(self):
        backend = self._loaded_behavior_backend()
        identity = self._identity(clean=False)
        identity["model_revision"] = backend.behavior_identity["model_revision"]
        identity["template_sha256"] = backend.behavior_identity["chat_template_sha256"]
        identity["vector_id"] = "mismatched-vector"
        registry = LogicalIdentityRegistry()
        logical_id = registry.register(identity)
        producer = GenerationProducer(
            registry,
            backend,
            run_mode="smoke",
            fake_backend=False,
            capability=backend.capability,
            item_budget=1,
        )
        with self.assertRaisesRegex(IdentityError, "does not match logical identity"):
            producer.produce(logical_id, self._request(logical_id))
        self.assertEqual(backend.model.generate_calls, 0)

        lambda_calls = []

        def substituted_backend(_identity, _request):
            lambda_calls.append("called")
            return {}

        with self.assertRaisesRegex(PipelineError, "not bound to the supplied backend"):
            GenerationProducer(
                registry,
                substituted_backend,
                run_mode="smoke",
                fake_backend=False,
                capability=backend.capability,
                item_budget=1,
            )
        self.assertEqual(lambda_calls, [])

        lifecycle = backend.release()
        judge_backend = self._loaded_judge_backend(lifecycle)
        with self.assertRaisesRegex(PipelineError, "judge capability"):
            parse_judge_with_retry(
                logical_id,
                judge_backend,
                {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
                registry=registry,
                generation_record=completed_chain()["generation"],
                run_mode="smoke",
                judge_identity=judge_backend.producer_identity,
                fake_backend=False,
                capability=backend.capability,
            )

        judge_calls = []

        def substituted_judge(_attempt, _request):
            judge_calls.append("called")
            return '{"label":"safe","rationale":"should not run"}'

        with self.assertRaisesRegex(PipelineError, "not bound to the supplied backend"):
            parse_judge_with_retry(
                logical_id,
                substituted_judge,
                {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
                registry=registry,
                generation_record=completed_chain()["generation"],
                run_mode="smoke",
                judge_identity=judge_backend.producer_identity,
                fake_backend=False,
                capability=judge_backend.capability,
            )
        self.assertEqual(judge_calls, [])

    def test_cuda_device_map_targets_the_complete_model(self):
        temp, path = self._asset_dir()
        self.addCleanup(temp.cleanup)
        vector_path = path / "vector.pt"
        torch.save(torch.ones((2, 4)), vector_path)
        tokenizer_loader = FakeLoader(TinyTokenizer())
        behavior_loader = FakeLoader(TinyBehaviorModel())
        backend = RealBehaviorBackend.from_pretrained(
            model_path=path, tokenizer_path=path, vector_path=vector_path, vector_index=0,
            dose_binding=bind_dose_post_dtype(test_dose_binding(), dtype="bfloat16"),
            layer=1, hook_site="resid_pre",
            dtype="bfloat16", device="cuda:0", tokenizer_loader=tokenizer_loader,
            model_loader=behavior_loader,
        )
        self.assertEqual(behavior_loader.calls[0][1]["device_map"], {"": "cuda:0"})
        lifecycle = {
            "behavior_released": True, "behavior_hook_removed": True,
            "behavior_model_reference_cleared": True,
            "behavior_tokenizer_reference_cleared": True, "gc_collect_called": True,
            "cuda_available": False, "models_concurrently_resident": False,
        }
        judge_loader = FakeLoader(TinyJudgeModel())
        RealJudgeBackend.from_pretrained(
            model_path=path, tokenizer_path=path, device="cuda:0", lifecycle=lifecycle,
            tokenizer_loader=FakeLoader(TinyTokenizer(judge=True)), model_loader=judge_loader,
        )
        self.assertEqual(judge_loader.calls[0][1]["device_map"], {"": "cuda:0"})

    def test_vector_shape_dtype_finite_and_metadata(self):
        temp, path = self._asset_dir()
        self.addCleanup(temp.cleanup)
        vector_path = path / "vector.pt"
        torch.save(torch.ones((2, 4), dtype=torch.float32), vector_path)
        vector, identity = load_candidate_vector(
            vector_path=vector_path, vector_index=1, layer=1,
            hook_site="resid_pre", hidden_size=4,
        )
        self.assertEqual(tuple(vector.shape), (4,))
        self.assertEqual(identity["normalization"], "none")
        self.assertTrue(identity["finite"])
        torch.save(torch.ones((2, 5)), vector_path)
        with self.assertRaises(PipelineError):
            load_candidate_vector(
                vector_path=vector_path, vector_index=0, layer=1,
                hook_site="resid_pre", hidden_size=4,
            )
        torch.save(torch.ones((2, 4), dtype=torch.int64), vector_path)
        with self.assertRaises(PipelineError):
            load_candidate_vector(
                vector_path=vector_path, vector_index=0, layer=1,
                hook_site="resid_pre", hidden_size=4,
            )
        invalid = torch.ones((2, 4), dtype=torch.float32)
        invalid[0, 0] = float("nan")
        torch.save(invalid, vector_path)
        with self.assertRaises(PipelineError):
            load_candidate_vector(
                vector_path=vector_path, vector_index=0, layer=1,
                hook_site="resid_pre", hidden_size=4,
            )

    def test_post_dtype_alpha_is_explicitly_bound_before_identity(self):
        source = test_dose_binding()
        bound = bind_dose_post_dtype(source, dtype="bfloat16")
        source_post = source["anchors"][0]["alpha_by_estimator"]["mu_all_tw"]["post_dtype"]
        bound_post = bound["anchors"][0]["alpha_by_estimator"]["mu_all_tw"]["post_dtype"]
        self.assertEqual(source_post["value"], 0.02)
        self.assertEqual(bound_post["value"], 0.02001953125)
        self.assertEqual(bound_post["binary64_hex"], (0.02001953125).hex())
        self.assertNotEqual(canonical_sha256(source), canonical_sha256(bound))

    def test_hook_decode_only_cleanup_and_producer_dose_lineage(self):
        backend = self._backend()
        clean_identity = self._identity(clean=True)
        steered_identity = self._identity(clean=False)
        clean_result = backend(clean_identity, self._request())
        self.assertNotIn("dose_evidence", clean_result)
        self.assertFalse(clean_result["diagnostics"]["hook_installed"])
        steered_result = backend(steered_identity, self._request())
        self.assertIn("dose_evidence", steered_result)
        self.assertTrue(steered_result["diagnostics"]["hook_removed"])
        self.assertGreater(steered_result["diagnostics"]["decode_cached_calls"], 0)
        registry = LogicalIdentityRegistry()
        logical_id = registry.register(steered_identity)
        producer = GenerationProducer(registry, backend, run_mode="smoke", item_budget=1)
        record = producer.produce(logical_id, self._request(logical_id))
        self.assertTrue(record["generation_completed"])
        self.assertIn("dose_evidence", record["attempts"][-1]["diagnostics"])

    def test_identity_mismatch_and_exception_remove_hook(self):
        backend = self._backend(fail=True)
        identity = self._identity(clean=False)
        broken = copy.deepcopy(identity)
        broken["model_revision"] = "c" * 64
        with self.assertRaises(IdentityError):
            backend(broken, self._request())
        self.assertEqual(backend.model.generate_calls, 0)
        broken_dose = copy.deepcopy(identity)
        broken_dose["alpha_post_dtype_hex"] = (0.03).hex()
        with self.assertRaises(IdentityError):
            backend(broken_dose, self._request())
        self.assertEqual(backend.model.generate_calls, 0)
        with self.assertRaises(TechnicalGenerationError):
            backend(identity, self._request())
        self.assertTrue(backend.last_diagnostics["hook_removed"])
        registry = LogicalIdentityRegistry()
        logical_id = registry.register(identity)
        terminal = GenerationProducer(
            registry, backend, run_mode="smoke", item_budget=1
        ).produce(logical_id, self._request(logical_id))
        self.assertEqual(terminal["terminal_status"], "TERMINAL_TECHNICAL_FAILURE")
        self.assertTrue(terminal["attempts"][-1]["diagnostics"]["hook_removed"])
        evidence = terminal["attempts"][-1]["diagnostics"]["dose_evidence"]
        self.assertEqual(evidence["generation_status"], "TERMINAL_TECHNICAL_FAILURE")
        self.assertEqual(evidence["failure_code"], "INVALID_DOSE_GEOMETRY")

    def test_qwen3_token_semantic_split(self):
        result = split_qwen3_thinking_final(torch.tensor([11, 99, 9, 10]), TinyTokenizer(judge=True))
        self.assertEqual(result["closing_think_token_id"], 99)
        self.assertEqual(result["final_completion"], '{"label":"safe","rationale":"ok"}')
        with self.assertRaises(TechnicalGenerationError):
            split_qwen3_thinking_final(torch.tensor([11, 9]), TinyTokenizer(judge=True))

        lifecycle = {
            "behavior_released": True,
            "behavior_hook_removed": True,
            "behavior_model_reference_cleared": True,
            "behavior_tokenizer_reference_cleared": True,
            "gc_collect_called": True,
            "cuda_available": False,
            "models_concurrently_resident": False,
            "judge_loaded_after_behavior_release": True,
        }
        backend = RealJudgeBackend(
            model=TinyJudgeModel(), tokenizer=TinyTokenizer(judge=True),
            model_identity={"resolved_model_path": "judge", "resolved_tokenizer_path": "judge"},
            lifecycle=lifecycle, device="cpu",
        )
        completion = backend.complete(prompt="question", response="answer", domain="harmful")
        self.assertEqual(completion, '{"label":"safe","rationale":"ok"}')
        self.assertTrue(backend.last_diagnostics["thinking_enabled"])
        self.assertFalse(backend.last_diagnostics["regex_fallback_used"])

    def test_judge_exact_json_and_one_retry(self):
        # Use the established helper for a valid upstream record, then exercise exact parser retry.
        chain = completed_chain("support", prompt_id="judge")
        calls = []

        def call(attempt, request):
            calls.append((attempt, canonical_sha256(request)))
            return "not-json" if attempt == 1 else '{"label":"safe","rationale":"ok"}'

        judge = parse_judge_with_retry(
            chain["logical_id"], call,
            {"logical_id": chain["logical_id"], "judge_config": JUDGE_CONFIG},
            registry=chain["registry"], generation_record=chain["generation"],
            run_mode="smoke",
            judge_identity={
                "model_path_or_id": "local-judge", "tokenizer_path_or_id": "local-tokenizer",
                "rubric_sha256": "1" * 64,
            },
        )
        self.assertTrue(judge["judge_label_parsed"])
        self.assertEqual([value[0] for value in calls], [1, 2])
        self.assertEqual(calls[0][1], calls[1][1])
        real_chain = self._real_completed_chain("loader-issued-judge")
        self.assertFalse(real_chain["generation"]["fake_backend"])
        self.assertFalse(real_chain["judge"]["fake_backend"])

    def test_sequential_lifecycle_and_output_overwrite(self):
        lifecycle = {
            "behavior_released": True,
            "behavior_hook_removed": True,
            "behavior_model_reference_cleared": True,
            "behavior_tokenizer_reference_cleared": True,
            "gc_collect_called": True,
            "cuda_available": False,
            "models_concurrently_resident": False,
        }
        backend = RealJudgeBackend(
            model=TinyJudgeModel(), tokenizer=TinyTokenizer(judge=True),
            model_identity={"resolved_model_path": "judge", "resolved_tokenizer_path": "judge"},
            lifecycle={**lifecycle, "judge_loaded_after_behavior_release": True},
            device="cpu",
        )
        self.assertTrue(backend.judge_identity["thinking_enabled"])
        released = backend.release()
        self.assertTrue(released["judge_released"])
        from scripts.stage3_production.real_smoke import create_output_directory
        output_root = ROOT / ".codex-temp/stage3_real_smoke_runs"
        run_id = "contract-overwrite"
        output = create_output_directory(output_root, run_id)
        self.addCleanup(lambda: output.rmdir())
        with self.assertRaises(FileExistsError):
            create_output_directory(output_root, run_id)

    def test_development_manifest_cannot_enter_paper_loader(self):
        chain = self._real_completed_chain()
        guard = offline_execution_guard()
        with guard:
            pass
        backend_identity = chain["backend_identity"]
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            manifest_kwargs = {
                "repo_root": ROOT, "run_mode": "smoke",
                "command": ["python", "real_smoke.py"],
                "started_at_utc": "2026-07-31T00:00:00Z",
                "completed_at_utc": "2026-07-31T00:00:01Z",
                "model_path_or_id": "local-model",
                "tokenizer_path_or_id": "local-tokenizer",
                "input_paths": [P1_INPUT], "generation_config": DECODE_CONFIG,
                "seed": 42, "gpu_identity": "cuda:0",
                "output_directory": Path(temporary) / "output",
                "exit_status": "success", "exit_code": 0, "fake_backend": False,
                "reconciliation": chain["reconciliation"], "offline_guard": guard,
                "runtime_versions": {
                    "python": "test", "torch": "test",
                    "transformers": "test", "cuda": "test",
                },
                "asset_status": "development_only", "formal_experiment_run": False,
                "backend_identity": backend_identity,
                "logical_registry": chain["registry_manifest"],
                "generation_records": [chain["generation"]],
                "judge_records": [chain["judge"]],
            }
            manifest = build_run_manifest(
                **manifest_kwargs,
                behavior_capability=chain["behavior_capability"],
                judge_capability=chain["judge_capability"],
            )
            with self.assertRaisesRegex(RunManifestError, "builder-issued behavior"):
                build_run_manifest(
                    **manifest_kwargs,
                    behavior_capability=chain["behavior_capability"].manifest_record(),
                    judge_capability=chain["judge_capability"],
                )
        execution_lineage = manifest["backend_identity"]["execution_lineage"]
        self.assertFalse(execution_lineage["fake_backend"])
        self.assertEqual(execution_lineage["generation_record_count"], 1)
        self.assertEqual(execution_lineage["judge_record_count"], 1)
        capability_provenance = manifest["backend_identity"]["runtime_capability_provenance"]
        self.assertEqual(capability_provenance["behavior"]["role"], "behavior")
        self.assertEqual(capability_provenance["judge"]["role"], "judge")
        self.assertNotIn("token", json.dumps(capability_provenance).lower())
        with self.assertRaises(RunManifestError):
            validate_manifest_for_paper_loader(manifest)

        fake_chain = completed_chain("support", prompt_id="fake-manifest-lineage")
        fake_identity = copy.deepcopy(backend_identity)
        fake_identity["output_identity"] = {
            "registry_sha256": fake_chain["registry"].manifest()["registry_sha256"],
            "generation_records_sha256": canonical_sha256([fake_chain["generation"]]),
            "judge_records_sha256": canonical_sha256([fake_chain["judge"]]),
        }
        with self.assertRaises(RunManifestError):
            build_run_manifest(
                repo_root=ROOT, run_mode="smoke", command=["python", "real_smoke.py"],
                started_at_utc="2026-07-31T00:00:00Z",
                completed_at_utc="2026-07-31T00:00:01Z",
                model_path_or_id="local-model", tokenizer_path_or_id="local-tokenizer",
                input_paths=[P1_INPUT], generation_config=DECODE_CONFIG, seed=42,
                gpu_identity="cuda:0", output_directory=ROOT / ".codex-temp/fake-lineage",
                exit_status="success", exit_code=0, fake_backend=False,
                reconciliation=fake_chain["reconciliation"], offline_guard=guard,
                runtime_versions={"python": "test", "torch": "test", "transformers": "test", "cuda": "test"},
                asset_status="development_only", formal_experiment_run=False,
                backend_identity=fake_identity,
                logical_registry=fake_chain["registry"].manifest(),
                generation_records=[fake_chain["generation"]],
                judge_records=[fake_chain["judge"]],
                behavior_capability=chain["behavior_capability"],
                judge_capability=chain["judge_capability"],
            )

        other_chain = self._real_completed_chain(prompt_id="other-real-manifest")
        other_identity = copy.deepcopy(backend_identity)
        other_identity["output_identity"] = {
            "registry_sha256": other_chain["registry_manifest"]["registry_sha256"],
            "generation_records_sha256": canonical_sha256([other_chain["generation"]]),
            "judge_records_sha256": canonical_sha256([other_chain["judge"]]),
        }
        with self.assertRaises(RunManifestError):
            build_run_manifest(
                repo_root=ROOT, run_mode="smoke", command=["python", "real_smoke.py"],
                started_at_utc="2026-07-31T00:00:00Z",
                completed_at_utc="2026-07-31T00:00:01Z",
                model_path_or_id="local-model", tokenizer_path_or_id="local-tokenizer",
                input_paths=[P1_INPUT], generation_config=DECODE_CONFIG, seed=42,
                gpu_identity="cuda:0", output_directory=ROOT / ".codex-temp/mixed-lineage",
                exit_status="success", exit_code=0, fake_backend=False,
                reconciliation=chain["reconciliation"], offline_guard=guard,
                runtime_versions={"python": "test", "torch": "test", "transformers": "test", "cuda": "test"},
                asset_status="development_only", formal_experiment_run=False,
                backend_identity=other_identity,
                logical_registry=chain["registry_manifest"],
                generation_records=[other_chain["generation"]],
                judge_records=[other_chain["judge"]],
                behavior_capability=chain["behavior_capability"],
                judge_capability=chain["judge_capability"],
            )

    def test_offline_network_and_subprocess_rejection(self):
        guard = offline_execution_guard()
        with guard:
            with self.assertRaises(Exception):
                socket.socket()
            with self.assertRaises(Exception):
                subprocess.run(["true"], check=True)
        self.assertEqual(guard.report["category_counts"]["network"], 1)
        self.assertEqual(guard.report["category_counts"]["subprocess"], 1)


if __name__ == "__main__":
    unittest.main()
