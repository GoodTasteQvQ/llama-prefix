"""Local-only single-GPU behavior runtime and asset discovery."""

from __future__ import annotations

import gc
import json
import os
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from activation_guard.interventions import PhaseAwareSteeringController
from activation_guard.metrics import compute_response_metrics

from .common import BroadeningError, canonical_sha256, file_sha256
from .config import resolve_path
from .directions import content_mask, render_native_user_prompt, user_content_span, validate_unit_vector


class RuntimeGateError(BroadeningError):
    """The requested GPU/model runtime does not satisfy the single-card contract."""


def require_offline_environment() -> None:
    required = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    }
    mismatched = {key: os.environ.get(key) for key, expected in required.items() if os.environ.get(key) != expected}
    if mismatched:
        raise RuntimeGateError(f"offline environment is not set: {mismatched}")


def require_single_visible_gpu(*, torch_module: Any = torch) -> str:
    if not bool(torch_module.cuda.is_available()):
        raise RuntimeGateError("CUDA is unavailable for a requested GPU worker")
    count = int(torch_module.cuda.device_count())
    if count != 1:
        raise RuntimeGateError(
            f"GPU worker requires exactly one visible device, found {count}; set CUDA_VISIBLE_DEVICES"
        )
    return "cuda:0"


def gpu_identity() -> dict[str, Any]:
    result: dict[str, Any] = {"logical_device": "cuda:0", "physical_gpu_uuid": "UNKNOWN"}
    try:
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,uuid,name", "--format=csv,noheader"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return result
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    physical = visible.split(",")[0].strip() if visible else None
    for line in output:
        fields = [field.strip() for field in line.split(",")]
        if len(fields) == 3 and (physical is None or fields[0] == physical):
            result.update({"physical_index": fields[0], "physical_gpu_uuid": fields[1], "gpu_name": fields[2]})
            break
    return result


def _model_files(path: Path, tokenizer_path: Path | None = None) -> dict[str, Any]:
    missing = [name for name in ("config.json",) if not (path / name).is_file()]
    tokenizer_root = tokenizer_path or path
    missing.extend(
        f"tokenizer/{name}"
        for name in ("tokenizer.json", "tokenizer_config.json")
        if not (tokenizer_root / name).is_file()
    )
    index_path = path / "model.safetensors.index.json"
    declared_shards: list[str] = []
    missing_shards: list[str] = []
    index_valid = True
    if index_path.is_file():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            weight_map = index.get("weight_map") if isinstance(index, Mapping) else None
            if not isinstance(weight_map, Mapping):
                raise ValueError("missing weight_map")
            declared_shards = sorted({
                str(filename)
                for filename in weight_map.values()
                if isinstance(filename, str) and filename.strip()
            })
            if not declared_shards:
                raise ValueError("empty weight_map")
            missing_shards = [name for name in declared_shards if not (path / name).is_file()]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            index_valid = False
            missing.append("model.safetensors.index.json:invalid")
    standalone_shards = sorted(item.name for item in path.glob("*.safetensors"))
    has_weights = (
        (index_valid and not missing_shards)
        if index_path.is_file()
        else bool(standalone_shards)
    )
    missing.extend(f"weights/{name}" for name in missing_shards)
    return {
        "missing_required_files": missing,
        "has_weight_index_or_shard": has_weights,
        "declared_weight_shards": declared_shards,
        "missing_weight_shards": missing_shards,
        "standalone_weight_shards": standalone_shards,
    }


def _declared_revision(path: Path, runtime_object: Any) -> str:
    """Read a declared checkpoint revision without treating a directory name as one."""
    candidates = [
        getattr(runtime_object, "_commit_hash", None),
        getattr(runtime_object, "commit_hash", None),
        getattr(runtime_object, "revision", None),
    ]
    init_kwargs = getattr(runtime_object, "init_kwargs", None)
    if isinstance(init_kwargs, Mapping):
        candidates.append(init_kwargs.get("revision"))
    config_path = path / "config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            config = {}
        if isinstance(config, Mapping):
            candidates.extend(config.get(key) for key in ("_commit_hash", "commit_hash", "revision"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip() and candidate.strip() != "None":
            return candidate.strip()
    return "UNKNOWN"


def _template_identity(tokenizer: Any) -> dict[str, Any]:
    template = getattr(tokenizer, "chat_template", None)
    try:
        digest = canonical_sha256(template)
    except (TypeError, ValueError):
        digest = "UNKNOWN"
    return {"chat_template": template, "chat_template_sha256": digest}


def discover_assets(config: Mapping[str, Any]) -> dict[str, Any]:
    assets: dict[str, Any] = {}
    for model_id, details in config["models"].items():
        model_path = details.get("model_path")
        tokenizer_path = details.get("tokenizer_path")
        if model_path is None:
            assets[model_id] = {
                "status": "NOT_RUN",
                "reason": "MODEL_PATH_NOT_CONFIGURED",
                "model_path": None,
                "tokenizer_path": None,
            }
            continue
        model = resolve_path(config, str(model_path))
        tokenizer = resolve_path(config, str(tokenizer_path or model_path))
        if model is None or tokenizer is None:
            raise RuntimeGateError(f"asset path resolution failed for {model_id}")
        model_exists, tokenizer_exists = model.is_dir(), tokenizer.is_dir()
        model_files = _model_files(model, tokenizer) if model_exists else None
        complete_files = bool(
            model_files
            and not model_files["missing_required_files"]
            and model_files["has_weight_index_or_shard"]
        )
        status = "READY_FOR_RUNTIME_CHECK" if model_exists and tokenizer_exists and complete_files else "NOT_RUN"
        if not model_exists or not tokenizer_exists:
            reason = "LOCAL_MODEL_OR_TOKENIZER_MISSING"
        elif not complete_files:
            reason = "LOCAL_MODEL_FILES_INCOMPLETE"
        else:
            reason = None
        assets[model_id] = {
            "status": status,
            "reason": reason,
            "model_path": str(model),
            "model_realpath": str(model.resolve()) if model_exists else None,
            "tokenizer_path": str(tokenizer),
            "tokenizer_realpath": str(tokenizer.resolve()) if tokenizer_exists else None,
            "model_files": model_files,
        }
    data = config["data"]
    e1_path = resolve_path(config, data.get("e1_harmbench_path"))
    e1_metadata = resolve_path(config, data.get("e1_metadata_path"))
    assets["e1_external"] = {
        "status": "READY_FOR_OVERLAP_GATE" if e1_path is not None and e1_path.is_file() and e1_metadata is not None and e1_metadata.is_file() else "NOT_RUN",
        "reason": None if e1_path is not None and e1_path.is_file() and e1_metadata is not None and e1_metadata.is_file() else "HARM_BENCH_ASSET_OR_METADATA_MISSING",
        "path": str(e1_path) if e1_path is not None else None,
        "metadata_path": str(e1_metadata) if e1_metadata is not None else None,
    }
    return {
        "schema_version": "paper1-broadening-asset-report-v1",
        "local_files_only_required": True,
        "assets": assets,
        "runtime_gate": {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "offline_environment_set": all(
                os.environ.get(key) == "1"
                for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE")
            ),
        },
    }


def _dtype(name: str, torch_module: Any = torch) -> Any:
    values = {"bfloat16": torch_module.bfloat16, "float32": torch_module.float32}
    if name not in values:
        raise RuntimeGateError(f"unsupported runtime dtype: {name}")
    return values[name]


def local_pretrained_kwargs(*, dtype: str, device: str, trust_remote_code: bool = False, torch_module: Any = torch) -> dict[str, Any]:
    if device != "cuda:0":
        raise RuntimeGateError("GPU workers may only use logical device cuda:0")
    if trust_remote_code:
        raise RuntimeGateError("trust_remote_code is disabled for this protocol")
    return {
        "local_files_only": True,
        "trust_remote_code": False,
        "dtype": _dtype(dtype, torch_module),
        "device_map": {"": "cuda:0"},
    }


def _load_model_local(
    *, model_path: Path, dtype: str, device: str, model_loader: Any, torch_module: Any
) -> Any:
    kwargs = local_pretrained_kwargs(dtype=dtype, device=device, torch_module=torch_module)
    try:
        model = model_loader.from_pretrained(str(model_path.resolve()), **kwargs)
    except TypeError:
        kwargs["torch_dtype"] = kwargs.pop("dtype")
        model = model_loader.from_pretrained(str(model_path.resolve()), **kwargs)
    return model.eval()


def _resolve_layer(model: Any, layer: int) -> Any:
    if hasattr(model, "model") and hasattr(model.model, "layers"):
        return model.model.layers[layer]
    if hasattr(model, "transformer") and hasattr(model.transformer, "h"):
        return model.transformer.h[layer]
    raise RuntimeGateError("unsupported architecture for resid_pre layer-input hook")


class BehaviorRuntime:
    """One local behavior model. Call release before loading a Judge runtime."""

    def __init__(
        self,
        *, model_id: str, model: Any, tokenizer: Any, model_path: Path,
        layer: int, dtype: str, device: str, tokenizer_path: Path | None = None,
        torch_module: Any = torch,
    ) -> None:
        self.model_id = model_id
        self.model = model
        self.tokenizer = tokenizer
        self.model_path = model_path.resolve()
        self.tokenizer_path = (tokenizer_path or model_path).resolve()
        self.layer = layer
        self.dtype = dtype
        self.device = device
        self._torch = torch_module
        self.released = False
        self._active_controller: PhaseAwareSteeringController | None = None
        hidden_size = getattr(getattr(model, "config", None), "hidden_size", None)
        layers = getattr(getattr(model, "config", None), "num_hidden_layers", None)
        if not isinstance(hidden_size, int) or hidden_size < 1 or not isinstance(layers, int):
            raise RuntimeGateError("loaded model config lacks hidden_size/layer count")
        if layer < 0 or layer >= layers:
            raise RuntimeGateError("configured layer is outside loaded model")
        self.hidden_size = hidden_size
        self.layer_count = layers
        self.layer_module = _resolve_layer(model, layer)

    @classmethod
    def from_pretrained(
        cls,
        *, model_id: str, details: Mapping[str, Any], torch_module: Any = torch,
        tokenizer_loader: Any = AutoTokenizer, model_loader: Any = AutoModelForCausalLM,
        layer_override: int | None = None,
    ) -> "BehaviorRuntime":
        require_offline_environment()
        device = require_single_visible_gpu(torch_module=torch_module)
        model_path = Path(str(details.get("model_path", ""))).expanduser()
        tokenizer_path = Path(str(details.get("tokenizer_path") or model_path)).expanduser()
        if not model_path.is_dir() or not tokenizer_path.is_dir():
            raise RuntimeGateError("behavior local model/tokenizer path is unavailable")
        tokenizer = tokenizer_loader.from_pretrained(
            str(tokenizer_path.resolve()), local_files_only=True, trust_remote_code=False, use_fast=True
        )
        if getattr(tokenizer, "pad_token", None) is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = _load_model_local(
            model_path=model_path,
            dtype=str(details.get("dtype")),
            device=device,
            model_loader=model_loader,
            torch_module=torch_module,
        )
        configured_layer = details.get("layer") if layer_override is None else layer_override
        if isinstance(configured_layer, bool) or not isinstance(configured_layer, int):
            raise RuntimeGateError("behavior layer is not configured or resolved")
        return cls(
            model_id=model_id,
            model=model,
            tokenizer=tokenizer,
            model_path=model_path,
            tokenizer_path=tokenizer_path,
            layer=configured_layer,
            dtype=str(details["dtype"]),
            device=device,
            torch_module=torch_module,
        )

    def identity(self) -> dict[str, Any]:
        config_path = self.model_path / "config.json"
        template = _template_identity(self.tokenizer)
        try:
            transformers_version = __import__("transformers").__version__
        except Exception:
            transformers_version = "UNKNOWN"
        return {
            "model_id": self.model_id,
            "model_path": str(self.model_path),
            "model_realpath": str(self.model_path.resolve()),
            "model_config_sha256": file_sha256(config_path) if config_path.is_file() else "UNKNOWN",
            "model_revision": _declared_revision(self.model_path, getattr(self.model, "config", None)),
            "tokenizer_path": str(self.tokenizer_path),
            "tokenizer_realpath": str(self.tokenizer_path.resolve()),
            "tokenizer_revision": _declared_revision(self.tokenizer_path, self.tokenizer),
            "tokenizer_config_sha256": (
                file_sha256(self.tokenizer_path / "tokenizer_config.json")
                if (self.tokenizer_path / "tokenizer_config.json").is_file()
                else "UNKNOWN"
            ),
            "layer": self.layer,
            "layer_count": self.layer_count,
            "hidden_size": self.hidden_size,
            "dtype": self.dtype,
            "hook_site": "resid_pre",
            "hook_semantics": "forward_pre_hook_on_layer_input",
            "local_files_only": True,
            "device": self.device,
            "eos_token_id": getattr(self.tokenizer, "eos_token_id", None),
            "pad_token_id": getattr(self.tokenizer, "pad_token_id", None),
            "transformers_version": transformers_version,
            **template,
            **gpu_identity(),
        }

    def _inputs(self, rendered: str) -> dict[str, Any]:
        encoded = self.tokenizer(rendered, add_special_tokens=False, return_tensors="pt")
        return {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in dict(encoded).items()
        }

    def content_residual(self, prompt: str) -> tuple[Any, dict[str, Any]]:
        if self.released:
            raise RuntimeGateError("behavior runtime has been released")
        span = user_content_span(self.tokenizer, prompt)
        inputs = self._inputs(span.rendered)
        captured: list[Any] = []

        def capture(_module: Any, input_args: tuple[Any, ...]) -> None:
            hidden = input_args[0]
            captured.append(hidden.detach().float().cpu()[0])

        handle = self.layer_module.register_forward_pre_hook(capture)
        try:
            with self._torch.inference_mode():
                self.model(**inputs, use_cache=True)
        finally:
            handle.remove()
        if len(captured) != 1:
            raise RuntimeGateError("resid_pre extraction expected exactly one prefill hook call")
        mask = content_mask(captured[0].shape[0], span)
        residual = captured[0][mask]
        return residual, {
            "rendered_prompt": span.rendered,
            "content_char_start": span.char_start,
            "content_char_end": span.char_end,
            "content_token_count": span.token_count,
            "hook_site": "resid_pre",
        }

    def generate(
        self,
        *, prompt: str, condition: str, vector: Any | None, alpha: float | None,
        max_new_tokens: int, seed: int = 42, capture_trace: bool = False,
    ) -> dict[str, Any]:
        if self.released:
            raise RuntimeGateError("behavior runtime has been released")
        if condition not in {"clean", "public_v1", "decode_only"}:
            raise RuntimeGateError("unknown generation condition")
        if condition == "clean":
            if vector is not None or alpha is not None:
                raise RuntimeGateError("clean generation cannot carry a vector or alpha")
        else:
            if vector is None or alpha is None:
                raise RuntimeGateError("steered generation requires vector and alpha")
            validate_unit_vector(vector, hidden_size=self.hidden_size)
        rendered = render_native_user_prompt(self.tokenizer, prompt)
        inputs = self._inputs(rendered)
        input_ids = inputs.get("input_ids")
        if input_ids is None or input_ids.ndim != 2 or input_ids.shape[0] != 1:
            raise RuntimeGateError("behavior tokenizer did not emit a batch-one input_ids tensor")
        if hasattr(self._torch, "manual_seed"):
            self._torch.manual_seed(seed)
            if bool(self._torch.cuda.is_available()):
                self._torch.cuda.manual_seed_all(seed)
        controller: PhaseAwareSteeringController | None = None
        if condition != "clean":
            phase_mode = "rogue_v1_cache_semantics" if condition == "public_v1" else "decode_only"
            controller = PhaseAwareSteeringController(
                layer_module=self.layer_module,
                fixed_prompt_ids=input_ids[0].tolist(),
                special_token_ids=set(self.tokenizer.all_special_ids),
                attack_vector=vector,
                attack_config={
                    "enabled": True,
                    "phase_mode": phase_mode,
                    "strength_mode": "fixed_alpha",
                    "coefficient": float(alpha),
                    "decode_decay": 1.0,
                },
                capture_traces=capture_trace,
            ).install()
            self._active_controller = controller
        started = perf_counter()
        try:
            with self._torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    do_sample=False,
                    num_beams=1,
                    max_new_tokens=max_new_tokens,
                    use_cache=True,
                    repetition_penalty=1.0,
                    pad_token_id=(
                        self.tokenizer.pad_token_id
                        if self.tokenizer.pad_token_id is not None
                        else self.tokenizer.eos_token_id
                    ),
                )
        finally:
            if controller is not None:
                controller.remove()
            self._active_controller = None
        generated_ids = outputs[0, input_ids.shape[1] :].detach().cpu().tolist()
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        summary = controller.summary() if controller is not None else {
            "prefill_calls": 0,
            "decode_cached_calls": 0,
            "decode_full_calls": 0,
            "decode_calls": 0,
            "generated_steered_calls": 0,
            "trace_count": 0,
            "clean_no_steering": True,
        }
        return {
            "text": text,
            "token_ids": generated_ids,
            "latency_seconds": perf_counter() - started,
            "runtime_counters": summary,
            "metrics": compute_response_metrics(text),
            "actual_alpha": float(alpha) if alpha is not None else None,
            "condition": condition,
            "eos_first": len(generated_ids) <= 1 and (
                not generated_ids or generated_ids[0] == self.tokenizer.eos_token_id
            ),
        }

    def release(self) -> dict[str, Any]:
        if self.released:
            raise RuntimeGateError("behavior runtime may only be released once")
        if self._active_controller is not None:
            self._active_controller.remove()
            self._active_controller = None
        self.model = None
        self.tokenizer = None
        self.layer_module = None
        collected = gc.collect()
        synchronized = False
        emptied = False
        if bool(self._torch.cuda.is_available()) and self.device.startswith("cuda:"):
            self._torch.cuda.synchronize(self.device)
            synchronized = True
            self._torch.cuda.empty_cache()
            emptied = True
        self.released = True
        return {
            "behavior_released": True,
            "behavior_hook_removed": True,
            "behavior_model_reference_cleared": True,
            "behavior_tokenizer_reference_cleared": True,
            "gc_collect_called": True,
            "gc_collected_count": collected,
            "cuda_synchronize_called": synchronized,
            "cuda_empty_cache_called": emptied,
            "models_concurrently_resident": False,
        }
