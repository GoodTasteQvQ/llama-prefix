from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from paper1_broadening import pipeline
from paper1_broadening.common import atomic_write_json
from paper1_broadening.runtime import BehaviorRuntime


RELEASE_SCHEMA_KEYS = {
    "behavior_hook_removed",
    "behavior_model_reference_cleared",
    "behavior_released",
    "behavior_tokenizer_reference_cleared",
    "cuda_empty_cache_called",
    "cuda_synchronize_called",
    "gc_collect_called",
    "gc_collected_count",
    "models_concurrently_resident",
}


def _frames() -> dict[str, object]:
    records = []
    folds = []
    for fold_index in range(5):
        pair_id = f"fold:{fold_index}"
        folds.append([pair_id])
        records.append({
            "pair_id": pair_id,
            "harmful": f"harmful fold {fold_index}",
            "harmless": f"harmless fold {fold_index}",
            "executable_include": True,
        })
    development = []
    for index in range(100):
        pair_id = f"development:{index}"
        development.append(pair_id)
        records.append({
            "pair_id": pair_id,
            "harmful": f"harmful development {index}",
            "harmless": f"harmless development {index}",
            "executable_include": True,
        })
    return {
        "safe_pair_split": {
            "gate": "READY_FOR_CONSTRUCTION",
            "construction_folds": folds,
            "development": development,
            "records": records,
        },
    }


def _config() -> dict[str, object]:
    return {
        "models": {
            "qwen25": {"model_index": 1, "layer": 9, "model_path": "fixture-qwen"},
            "llama31": {"model_index": 2, "layer": 11, "model_path": "fixture-llama"},
            "gemma2_9b_it": {"model_index": 3, "layer": 14, "model_path": "fixture-gemma"},
        },
    }


def _prepare_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    atomic_write_json(
        run_dir / "run_header.json",
        {
            "run_id": "fixture-e2r",
            "loaded_identities": {"behavior": {}, "judge": None},
            "model_revision": {},
            "tokenizer_revision": {},
        },
        overwrite=False,
    )
    atomic_write_json(run_dir / "frames.json", _frames(), overwrite=False)
    return run_dir


def _fake_runtime_class(monkeypatch: pytest.MonkeyPatch, *, fail_release: set[tuple[str, int]] | None = None):
    fail_release = fail_release or set()
    release_payload = {
        "behavior_hook_removed": True,
        "behavior_model_reference_cleared": True,
        "behavior_released": True,
        "behavior_tokenizer_reference_cleared": True,
        "cuda_empty_cache_called": True,
        "cuda_synchronize_called": True,
        "gc_collect_called": True,
        "gc_collected_count": 17,
        "models_concurrently_resident": False,
    }

    class FakeRuntime:
        instances: list[FakeRuntime] = []

        def __init__(self, model_id: str, layer: int) -> None:
            self.model_id = model_id
            self.layer = layer
            self.layer_count = 42 if model_id == "gemma2_9b_it" else 28
            self.hidden_size = 4
            self.release_payload = dict(release_payload)
            FakeRuntime.instances.append(self)

        @classmethod
        def from_pretrained(cls, *, model_id: str, details: dict[str, object], layer_override: int | None = None):
            layer = int(details["layer"]) if layer_override is None else int(layer_override)
            return cls(model_id, layer)

        def identity(self) -> dict[str, object]:
            return {
                "model_id": self.model_id,
                "layer": self.layer,
                "layer_count": self.layer_count,
                "hidden_size": self.hidden_size,
                "model_revision": "UNKNOWN",
                "tokenizer_revision": "UNKNOWN",
            }

        def content_residual(self, prompt: str):
            value = 2.0 if prompt.startswith("harmful") else 1.0
            return torch.tensor([[value, 0.0, 0.0, 0.0], [value, 0.0, 0.0, 0.0]]), {}

        def release(self):
            if (self.model_id, self.layer) in fail_release:
                raise RuntimeError("fixture layer-14 release failure")
            return self.release_payload

    monkeypatch.setattr(pipeline, "BehaviorRuntime", FakeRuntime)
    return FakeRuntime, release_payload


def test_release_serialization_aligns_gemma_qwen_llama_and_e3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_runtime, release_payload = _fake_runtime_class(monkeypatch)
    run_dir = _prepare_run(tmp_path)
    result = pipeline._build_e2_assets(
        run_dir=run_dir,
        config=_config(),
        frames=_frames(),
        source_run_id="fixture-e2r",
    )

    assert result["status"] == "COMPLETED"
    gemma = result["model"]
    assert set(gemma["release"]) == RELEASE_SCHEMA_KEYS
    assert gemma["release"] == release_payload
    assert gemma["release"] is next(
        instance.release_payload
        for instance in fake_runtime.instances
        if instance.model_id == "gemma2_9b_it" and instance.layer == gemma["layer"]
    )
    assert gemma["layer"] == 14
    assert gemma["runtime_identity"]["model_revision"] == "UNKNOWN"
    assert gemma["runtime_identity"]["tokenizer_revision"] == "UNKNOWN"

    e3_core_models = {
        model_id: {"status": "COMPLETED", "layer": layer, "layer_count": 28}
        for model_id, layer in (("qwen25", 9), ("llama31", 11))
    }
    e3 = pipeline._build_e3_layer_assets(
        run_dir=run_dir,
        config=_config(),
        frames=_frames(),
        core_models=e3_core_models,
        source_run_id="fixture-e2r",
    )
    assert e3["status"] == "COMPLETED"
    for model_id in ("qwen25", "llama31"):
        layers = e3["models"][model_id]["layers"]
        assert set(layers) == {"7", "20"}
        for layer_record in layers.values():
            assert set(layer_record["release"]) == RELEASE_SCHEMA_KEYS
            assert layer_record["release"] == release_payload

    assert (run_dir / "directions_gemma2_9b_it.pt").is_file()


def test_gemma_release_failure_is_blocked_without_synthetic_pass_or_tensor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_runtime_class(monkeypatch, fail_release={("gemma2_9b_it", 14)})
    run_dir = _prepare_run(tmp_path)
    result = pipeline._build_e2_assets(
        run_dir=run_dir,
        config=_config(),
        frames=_frames(),
        source_run_id="fixture-e2r",
    )

    assert result["status"] == "BLOCKED"
    assert result["release_error"] == "RuntimeError: fixture layer-14 release failure"
    assert "model" not in result
    assert not (run_dir / "directions_gemma2_9b_it.pt").exists()


def test_missing_runtime_revisions_remain_unknown(tmp_path: Path) -> None:
    model = SimpleNamespace(
        config=SimpleNamespace(hidden_size=4, num_hidden_layers=42),
        model=SimpleNamespace(layers=[nn.Identity() for _ in range(42)]),
    )
    tokenizer = SimpleNamespace(
        chat_template=None,
        eos_token_id=1,
        pad_token_id=0,
    )
    runtime = BehaviorRuntime(
        model_id="gemma2_9b_it",
        model=model,
        tokenizer=tokenizer,
        model_path=tmp_path,
        tokenizer_path=tmp_path,
        layer=14,
        dtype="bfloat16",
        device="cpu",
        torch_module=torch,
    )
    identity = runtime.identity()
    assert identity["model_revision"] == "UNKNOWN"
    assert identity["tokenizer_revision"] == "UNKNOWN"
    runtime.release()
