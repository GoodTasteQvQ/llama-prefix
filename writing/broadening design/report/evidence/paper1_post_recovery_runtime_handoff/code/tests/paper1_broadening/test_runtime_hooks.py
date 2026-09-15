from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import torch
from torch import nn

from paper1_broadening.config import default_config
from paper1_broadening.judge import Qwen3JudgeRuntime
from paper1_broadening.runtime import (
    BehaviorRuntime,
    RuntimeGateError,
    _model_files,
    discover_assets,
    local_pretrained_kwargs,
    require_single_visible_gpu,
)
from paper1_broadening.smoke import run_fixture_smoke


class FakeCuda:
    def __init__(self, count: int, available: bool = True) -> None:
        self.count = count
        self.available = available

    def is_available(self) -> bool:
        return self.available

    def device_count(self) -> int:
        return self.count

    def synchronize(self, _device: str) -> None:
        return None

    def empty_cache(self) -> None:
        return None


class FakeTorch:
    bfloat16 = "fake-bfloat16"
    float32 = "fake-float32"

    def __init__(self, count: int = 1) -> None:
        self.cuda = FakeCuda(count)


class LoaderTokenizer:
    pad_token = None
    eos_token = "<eos>"
    pad_token_id = 0
    eos_token_id = 2
    all_special_ids = [0, 2]
    name_or_path = "fixture-tokenizer"


class LoaderModel:
    def __init__(self) -> None:
        self.config = SimpleNamespace(hidden_size=4, num_hidden_layers=20)
        self.model = SimpleNamespace(layers=[nn.Identity() for _ in range(20)])

    def eval(self):
        return self


class TokenizerLoader:
    calls: list[tuple[str, dict[str, object]]] = []

    @classmethod
    def from_pretrained(cls, path: str, **kwargs):
        cls.calls.append((path, kwargs))
        return LoaderTokenizer()


class ModelLoader:
    calls: list[tuple[str, dict[str, object]]] = []

    @classmethod
    def from_pretrained(cls, path: str, **kwargs):
        cls.calls.append((path, kwargs))
        return LoaderModel()


class GenerationTokenizer:
    pad_token_id = 0
    eos_token_id = 2
    eos_token = "<eos>"
    pad_token = "<pad>"
    all_special_ids = [0, 2]
    name_or_path = "fixture-tokenizer"

    def apply_chat_template(self, messages, *, tokenize=False, add_generation_prompt=True, **_kwargs):
        assert tokenize is False
        return "<user>" + messages[0]["content"] + "</user><assistant>"

    def __call__(self, _rendered, **_kwargs):
        return {"input_ids": torch.tensor([[5, 6]], dtype=torch.long), "attention_mask": torch.tensor([[1, 1]])}

    def decode(self, ids, **_kwargs):
        return "" if len(ids) == 1 and int(ids[0]) == 2 else "fixture output"


class GenerationModel(LoaderModel):
    def __init__(self) -> None:
        super().__init__()
        self.last_generate_kwargs: dict[str, object] | None = None

    def generate(self, **kwargs):
        self.last_generate_kwargs = kwargs
        return torch.tensor([[5, 6, 2]], dtype=torch.long)


class JudgeTokenizer(GenerationTokenizer):
    def apply_chat_template(self, messages, *, tokenize=False, add_generation_prompt=True, enable_thinking=True, **_kwargs):
        assert enable_thinking is True
        return super().apply_chat_template(messages, tokenize=tokenize, add_generation_prompt=add_generation_prompt)

    def decode(self, _ids, **_kwargs):
        return "<think>fixture</think>{\"label\":\"safe\",\"rationale\":\"ok\"}"


def test_fixture_phase_smoke_covers_public_decode_zero_alpha_and_eos() -> None:
    report = run_fixture_smoke()
    assert report["status"] == "PASS"
    assert report["evidence_status"] == "NON_EVIDENCE"
    assert report["checks"] == {
        "public_cached_decode_not_steered": True,
        "decode_only_cached_decode_steered": True,
        "decode_only_prefill_recorded": True,
        "zero_alpha_no_steering": True,
        "first_token_eos_retained": True,
        "public_trace_has_decode": True,
    }


def test_real_smoke_report_does_not_pass_without_judge_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from paper1_broadening import smoke as smoke_module

    class MissingBehavior:
        @classmethod
        def from_pretrained(cls, **_kwargs):
            raise RuntimeGateError("fixture behavior unavailable")

    monkeypatch.setattr(smoke_module, "BehaviorRuntime", MissingBehavior)
    report = smoke_module.run_real_smoke(config=default_config(tmp_path), output_dir=tmp_path / "smoke")
    assert report["status"] == "RUNTIME_NOT_RUN"
    assert report["judge_status"]["status"] == "RUNTIME_NOT_RUN"


def test_single_gpu_gate_and_local_loader_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for count in (0, 2):
        with pytest.raises(RuntimeGateError):
            require_single_visible_gpu(torch_module=FakeTorch(count))
    assert require_single_visible_gpu(torch_module=FakeTorch(1)) == "cuda:0"
    kwargs = local_pretrained_kwargs(dtype="bfloat16", device="cuda:0", torch_module=FakeTorch())
    assert kwargs["local_files_only"] is True
    assert kwargs["device_map"] == {"": "cuda:0"}
    with pytest.raises(RuntimeGateError):
        local_pretrained_kwargs(dtype="bfloat16", device="cuda:1", torch_module=FakeTorch())

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "1")
    model_path = tmp_path / "model"
    model_path.mkdir()
    tokenizer_path = tmp_path / "tokenizer"
    tokenizer_path.mkdir()
    TokenizerLoader.calls.clear()
    ModelLoader.calls.clear()
    runtime = BehaviorRuntime.from_pretrained(
        model_id="fixture",
        details={
            "model_path": str(model_path), "tokenizer_path": str(tokenizer_path),
            "layer": 9, "dtype": "bfloat16",
        },
        torch_module=FakeTorch(), tokenizer_loader=TokenizerLoader, model_loader=ModelLoader,
    )
    assert TokenizerLoader.calls[0][1]["local_files_only"] is True
    assert ModelLoader.calls[0][1]["local_files_only"] is True
    assert ModelLoader.calls[0][1]["device_map"] == {"": "cuda:0"}
    released = runtime.release()
    assert released["models_concurrently_resident"] is False
    assert runtime.layer_module is None


def test_discover_assets_resolves_relative_paths_without_fabricating_missing_assets(tmp_path: Path) -> None:
    config = default_config(tmp_path)
    for model_id in ("qwen25", "llama31", "judge"):
        directory = tmp_path / model_id
        directory.mkdir()
        config["models"][model_id]["model_path"] = model_id
        config["models"][model_id]["tokenizer_path"] = model_id
    external = tmp_path / "external.json"
    metadata = tmp_path / "metadata.json"
    external.write_text("[]", encoding="utf-8")
    metadata.write_text("{}", encoding="utf-8")
    config["data"]["e1_harmbench_path"] = "external.json"
    config["data"]["e1_metadata_path"] = "metadata.json"
    report = discover_assets(config)
    assert report["assets"]["e1_external"]["status"] == "READY_FOR_OVERLAP_GATE"
    assert report["assets"]["e1_external"]["path"] == str(external)
    assert report["assets"]["gemma2_9b_it"]["status"] == "NOT_RUN"
    assert report["assets"]["qwen25"]["model_path"] == str(tmp_path / "qwen25")


def test_model_file_index_requires_every_declared_safetensors_shard(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    tokenizer = tmp_path / "tokenizer"
    tokenizer.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    for name in ("tokenizer.json", "tokenizer_config.json"):
        (tokenizer / name).write_text("{}", encoding="utf-8")
    (model / "model.safetensors.index.json").write_text(
        '{"weight_map":{"layer0":"model-00001-of-00002.safetensors","layer1":"model-00002-of-00002.safetensors"}}',
        encoding="utf-8",
    )
    (model / "model-00001-of-00002.safetensors").write_bytes(b"fixture")
    report = _model_files(model, tokenizer)
    assert report["declared_weight_shards"] == [
        "model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"
    ]
    assert report["missing_weight_shards"] == ["model-00002-of-00002.safetensors"]
    assert report["has_weight_index_or_shard"] is False
    assert "weights/model-00002-of-00002.safetensors" in report["missing_required_files"]


def test_behavior_and_judge_preserve_zero_pad_id_and_judge_is_loaded_after_release(tmp_path: Path) -> None:
    model = GenerationModel()
    runtime = BehaviorRuntime(
        model_id="fixture", model=model, tokenizer=GenerationTokenizer(), model_path=tmp_path,
        layer=9, dtype="float32", device="cpu", torch_module=torch,
    )
    result = runtime.generate(
        prompt="safe", condition="clean", vector=None, alpha=None,
        max_new_tokens=1, seed=42, capture_trace=False,
    )
    assert model.last_generate_kwargs is not None
    assert model.last_generate_kwargs["pad_token_id"] == 0
    lifecycle = runtime.release()
    assert lifecycle["behavior_released"] is True

    judge_model = GenerationModel()
    judge = Qwen3JudgeRuntime(
        model=judge_model, tokenizer=JudgeTokenizer(), model_path=tmp_path,
        device="cpu", lifecycle=lifecycle, torch_module=torch,
    )
    with patch("paper1_broadening.judge.split_qwen3_thinking_final", return_value={"final_completion": "{\"label\":\"safe\",\"rationale\":\"ok\"}", "thinking": "fixture"}):
        final, _diagnostics = judge._final_completion("judge prompt")
    assert final.startswith("{")
    assert judge_model.last_generate_kwargs is not None
    assert judge_model.last_generate_kwargs["pad_token_id"] == 0
    judge.release()
