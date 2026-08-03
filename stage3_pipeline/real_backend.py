"""Local-only behavior-model adapter for Stage 3 development smoke runs."""

from __future__ import annotations

import gc
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from activation_guard.interventions import PhaseAwareSteeringController
from activation_guard.runner import ExperimentRunner

from .core import (
    DECODE_CONFIG,
    IdentityError,
    PipelineError,
    TechnicalGenerationError,
    VerifiedBackendCapability,
    _issue_verified_backend_capability,
    canonical_sha256,
    file_sha256,
    validate_generation_config,
)
from .dose import build_call_dose_evidence, validate_dose_binding


BEHAVIOR_IDENTITY_SCHEMA = "paper1-stage3-real-behavior-identity-v1"
VECTOR_IDENTITY_SCHEMA = "paper1-stage3-real-vector-identity-v1"
HOOK_IDENTITY_SCHEMA = "paper1-stage3-real-hook-identity-v1"
_SUPPORTED_DTYPES = {
    "bfloat16": torch.bfloat16,
    "float16": torch.float16,
    "float32": torch.float32,
}


def bind_dose_post_dtype(
    dose_binding: Mapping[str, Any], *, dtype: str, torch_module: Any = torch
) -> dict[str, Any]:
    """Bind every post-dtype alpha to the behavior arithmetic dtype."""
    if dtype not in _SUPPORTED_DTYPES:
        raise PipelineError(f"unsupported dose binding dtype: {dtype}")
    validate_dose_binding(dose_binding)
    bound = json.loads(json.dumps(dict(dose_binding), allow_nan=False))
    for anchor in bound["anchors"]:
        for alpha in anchor["alpha_by_estimator"].values():
            pre_dtype = float(alpha["pre_dtype"]["value"])
            post_dtype = float(
                torch_module.tensor(
                    pre_dtype, dtype=_SUPPORTED_DTYPES[dtype], device="cpu"
                ).item()
            )
            if not math.isfinite(post_dtype) or post_dtype <= 0.0:
                raise PipelineError("post-dtype alpha is nonfinite or nonpositive")
            alpha["post_dtype"] = {
                "value": post_dtype,
                "binary64_hex": post_dtype.hex(),
            }
    validate_dose_binding(bound)
    return bound


def _local_directory(value: str | Path, field: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value):
        raise PipelineError(f"{field} must be a nonempty local path")
    text = str(value)
    if "://" in text:
        raise PipelineError(f"{field} may not be a remote identifier")
    path = Path(text).expanduser().resolve()
    if not path.is_dir():
        raise PipelineError(f"{field} is not a local directory: {path}")
    return path


def _required_file(directory: Path, name: str) -> Path:
    path = directory / name
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"required local model asset is missing or linked: {path}")
    return path


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PipelineError(f"invalid local JSON asset: {path}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"local JSON asset must be an object: {path}")
    return value


def _trust_remote_code_settings(
    trust_remote_code: bool, trust_remote_code_reason: str | None
) -> tuple[bool, str | None]:
    if not isinstance(trust_remote_code, bool):
        raise PipelineError("trust_remote_code must be boolean")
    if trust_remote_code:
        if not isinstance(trust_remote_code_reason, str) or not trust_remote_code_reason.strip():
            raise PipelineError("trust_remote_code=true requires a nonempty recorded reason")
        return True, trust_remote_code_reason.strip()
    if trust_remote_code_reason is not None:
        raise PipelineError("trust_remote_code_reason requires trust_remote_code=true")
    return False, None


def inspect_local_model_assets(
    *,
    model_path: str | Path,
    tokenizer_path: str | Path | None = None,
    model_role: str,
    dtype: str,
    device: str,
    trust_remote_code: bool = False,
    trust_remote_code_reason: str | None = None,
    tokenizer_loader: Any = AutoTokenizer,
) -> tuple[dict[str, Any], Any]:
    """Inspect config/tokenizer bytes without loading model weights."""
    if model_role not in {"behavior", "judge"}:
        raise PipelineError("model_role must be behavior or judge")
    if dtype not in _SUPPORTED_DTYPES:
        raise PipelineError(f"unsupported model dtype: {dtype}")
    if not isinstance(device, str) or not device:
        raise PipelineError("device must be a nonempty string")
    trust, reason = _trust_remote_code_settings(trust_remote_code, trust_remote_code_reason)
    model_directory = _local_directory(model_path, "model_path")
    tokenizer_directory = _local_directory(
        model_path if tokenizer_path is None else tokenizer_path, "tokenizer_path"
    )
    config_path = _required_file(model_directory, "config.json")
    index_path = _required_file(model_directory, "model.safetensors.index.json")
    tokenizer_json_path = _required_file(tokenizer_directory, "tokenizer.json")
    tokenizer_config_path = _required_file(tokenizer_directory, "tokenizer_config.json")
    config = _json_object(config_path)
    architectures = config.get("architectures")
    if (
        not isinstance(architectures, list)
        or not architectures
        or any(not isinstance(value, str) or not value for value in architectures)
    ):
        raise PipelineError("model config architectures are missing")
    hidden_size = config.get("hidden_size")
    layer_count = config.get("num_hidden_layers")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in (hidden_size, layer_count)):
        raise PipelineError("model config hidden size/layer count are invalid")
    tokenizer = tokenizer_loader.from_pretrained(
        str(tokenizer_directory),
        local_files_only=True,
        trust_remote_code=trust,
    )
    chat_template = getattr(tokenizer, "chat_template", None)
    if not isinstance(chat_template, str) or not chat_template:
        raise PipelineError("tokenizer has no nonempty chat template")
    identity = {
        "schema_version": (
            BEHAVIOR_IDENTITY_SCHEMA
            if model_role == "behavior"
            else "paper1-stage3-real-judge-model-identity-v1"
        ),
        "model_role": model_role,
        "resolved_model_path": str(model_directory),
        "resolved_tokenizer_path": str(tokenizer_directory),
        "model_config_sha256": file_sha256(config_path),
        "safetensors_index_sha256": file_sha256(index_path),
        "tokenizer_sha256": file_sha256(tokenizer_json_path),
        "tokenizer_config_sha256": file_sha256(tokenizer_config_path),
        "chat_template_sha256": hashlib.sha256(chat_template.encode("utf-8")).hexdigest(),
        "dtype": dtype,
        "device": device,
        "model_architecture": architectures[0],
        "hidden_size": hidden_size,
        "layer_count": layer_count,
        "trust_remote_code": trust,
        "trust_remote_code_reason": reason,
        "local_files_only": True,
    }
    identity["model_revision"] = canonical_sha256({
        "model_config_sha256": identity["model_config_sha256"],
        "safetensors_index_sha256": identity["safetensors_index_sha256"],
    })
    return identity, tokenizer


def load_candidate_vector(
    *,
    vector_path: str | Path,
    vector_index: int,
    layer: int,
    hook_site: str,
    hidden_size: int,
    torch_module: Any = torch,
) -> tuple[Any, dict[str, Any]]:
    """Load one exact CPU vector with safe torch deserialization and no mutation."""
    path = Path(vector_path).expanduser().resolve()
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"candidate vector file is missing or linked: {path}")
    if isinstance(vector_index, bool) or not isinstance(vector_index, int) or vector_index < 0:
        raise PipelineError("vector_index must be a nonnegative integer")
    if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0:
        raise PipelineError("vector layer must be a nonnegative integer")
    if hook_site != "resid_pre":
        raise PipelineError(
            "the reused activation_guard controller installs a layer-input resid_pre hook"
        )
    tensor = torch_module.load(path, map_location="cpu", weights_only=True)
    if not isinstance(tensor, torch_module.Tensor):
        raise PipelineError("candidate vector asset must contain exactly one tensor")
    source_shape = list(tensor.shape)
    if tensor.ndim == 1:
        if vector_index != 0:
            raise PipelineError("a rank-one vector only permits vector_index=0")
        selected = tensor
    elif tensor.ndim == 2:
        if vector_index >= tensor.shape[0]:
            raise PipelineError("vector_index is outside the candidate pool")
        selected = tensor[vector_index]
    else:
        raise PipelineError("candidate vector tensor must have rank one or two")
    if list(selected.shape) != [hidden_size]:
        raise PipelineError(
            f"candidate vector shape {list(selected.shape)} differs from hidden size {hidden_size}"
        )
    if not selected.dtype.is_floating_point:
        raise PipelineError("candidate vector dtype must be floating point")
    if selected.device.type != "cpu":
        raise PipelineError("candidate vector must first load on CPU")
    if not bool(torch_module.isfinite(selected).all().item()):
        raise PipelineError("candidate vector contains nonfinite values")
    selected = selected.detach().clone()
    norm = float(selected.float().norm().item())
    if not math.isfinite(norm) or norm <= 0.0:
        raise PipelineError("candidate vector norm must be finite and positive")
    identity = {
        "schema_version": VECTOR_IDENTITY_SCHEMA,
        "asset_status": "development_only",
        "vector_status": "candidate_only",
        "resolved_vector_path": str(path),
        "vector_file_sha256": file_sha256(path),
        "vector_index": vector_index,
        "layer": layer,
        "hook_site": hook_site,
        "source_shape": source_shape,
        "selected_shape": list(selected.shape),
        "source_dtype": str(tensor.dtype).replace("torch.", ""),
        "selected_dtype": str(selected.dtype).replace("torch.", ""),
        "load_device": str(selected.device),
        "finite": True,
        "normalization": "none",
        "reordered": False,
        "resampled": False,
        "selected_l2_norm": norm,
    }
    identity["vector_id"] = "sha256:" + canonical_sha256({
        "vector_file_sha256": identity["vector_file_sha256"],
        "vector_index": vector_index,
        "layer": layer,
        "hook_site": hook_site,
    })
    return selected, identity


def resolve_layer_module(model: Any, layer: int) -> Any:
    """Invoke activation_guard's existing layer resolver without constructing its runner."""
    proxy = SimpleNamespace(
        model=model,
        config=SimpleNamespace(model=SimpleNamespace(layer_index=layer)),
    )
    try:
        return ExperimentRunner._layer_module(proxy)
    except (AttributeError, IndexError, ValueError) as exc:
        raise PipelineError("configured hook layer cannot be resolved by activation_guard") from exc


class InstrumentedPhaseAwareSteeringController(PhaseAwareSteeringController):
    """Legacy phase controller plus per-decode geometry observations."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.hook_installed = False
        self.hook_removed = False
        self.geometry: list[dict[str, float | str]] = []

    def _hook(self, module: Any, input_args: tuple[Any, ...]) -> tuple[Any, ...]:
        before = input_args[0].detach().float()
        output = super()._hook(module, input_args)
        trace = self.traces[-1]
        if trace.phase != "prefill" and trace.attack_applied:
            after = output[0].detach().float()
            delta = after - before
            vector = self.attack_vector.detach().float().to(delta.device)
            expanded = vector.reshape(1, 1, -1).expand_as(delta)
            delta_flat = delta.reshape(-1)
            vector_flat = expanded.reshape(-1)
            before_flat = before.reshape(-1)
            after_flat = after.reshape(-1)
            alignment = torch.nn.functional.cosine_similarity(
                delta_flat.reshape(1, -1), vector_flat.reshape(1, -1), dim=1
            ).item()
            similarity = torch.nn.functional.cosine_similarity(
                before_flat.reshape(1, -1), after_flat.reshape(1, -1), dim=1
            ).item()
            self.geometry.append({
                "phase": trace.phase,
                "pre_hook_l2": float(before_flat.norm().item()),
                "post_hook_l2": float(after_flat.norm().item()),
                "vector_alignment": float(max(-1.0, min(1.0, alignment))),
                "cosine_drift": float(max(0.0, min(2.0, 1.0 - similarity))),
            })
        return output

    def install(self) -> "InstrumentedPhaseAwareSteeringController":
        super().install()
        self.hook_installed = True
        return self

    def remove(self) -> None:
        super().remove()
        if self.hook_installed:
            self.hook_removed = True

    def diagnostic_summary(self) -> dict[str, Any]:
        summary = self.summary()
        summary.update({
            "schema_version": HOOK_IDENTITY_SCHEMA,
            "hook_installed": self.hook_installed,
            "hook_removed": self.hook_removed,
            "phase": "decode-only",
            "use_cache": True,
            "geometry_preview": self.geometry[:32],
        })
        if self.geometry:
            summary.update(self.geometry[-1])
        return summary


class RealBehaviorBackend:
    """Callable GenerationProducer backend around a loaded local behavior model."""

    def __init__(
        self,
        *,
        model: Any,
        tokenizer: Any,
        behavior_identity: Mapping[str, Any],
        vector: Any,
        vector_identity: Mapping[str, Any],
        dose_binding: Mapping[str, Any],
        layer: int,
        hook_site: str,
        device: str,
        torch_module: Any = torch,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.behavior_identity = dict(behavior_identity)
        self.vector = vector
        self.vector_identity = dict(vector_identity)
        expected_dose_binding = bind_dose_post_dtype(
            dose_binding, dtype=self.behavior_identity["dtype"], torch_module=torch_module
        )
        if canonical_sha256(dose_binding) != canonical_sha256(expected_dose_binding):
            raise PipelineError(
                "dose binding alpha_post_dtype is not bound to the behavior dtype"
            )
        self.dose_binding = expected_dose_binding
        self.layer = layer
        self.hook_site = hook_site
        self.device = device
        self._torch = torch_module
        self._active_controller: InstrumentedPhaseAwareSteeringController | None = None
        self.last_diagnostics: dict[str, Any] = {}
        self.released = False
        self._attempts_by_logical_id: dict[str, int] = {}
        self.capability: VerifiedBackendCapability | None = None
        validate_generation_config(DECODE_CONFIG, run_mode="smoke")
        if hook_site != "resid_pre":
            raise PipelineError(
                "the reused activation_guard controller supports only the truthful resid_pre hook site"
            )

    @classmethod
    def from_pretrained(
        cls,
        *,
        model_path: str | Path,
        tokenizer_path: str | Path | None,
        vector_path: str | Path,
        vector_index: int,
        dose_binding: Mapping[str, Any],
        layer: int,
        hook_site: str,
        dtype: str,
        device: str,
        trust_remote_code: bool = False,
        trust_remote_code_reason: str | None = None,
        model_loader: Any = AutoModelForCausalLM,
        tokenizer_loader: Any = AutoTokenizer,
        torch_module: Any = torch,
    ) -> "RealBehaviorBackend":
        identity, tokenizer = inspect_local_model_assets(
            model_path=model_path,
            tokenizer_path=tokenizer_path,
            model_role="behavior",
            dtype=dtype,
            device=device,
            trust_remote_code=trust_remote_code,
            trust_remote_code_reason=trust_remote_code_reason,
            tokenizer_loader=tokenizer_loader,
        )
        if layer >= identity["layer_count"]:
            raise PipelineError("behavior layer is outside the model config")
        vector, vector_identity = load_candidate_vector(
            vector_path=vector_path,
            vector_index=vector_index,
            layer=layer,
            hook_site=hook_site,
            hidden_size=identity["hidden_size"],
            torch_module=torch_module,
        )
        model_kwargs = {
            "local_files_only": True,
            "trust_remote_code": trust_remote_code,
            "dtype": _SUPPORTED_DTYPES[dtype],
        }
        if device.startswith("cuda:"):
            model_kwargs["device_map"] = {"": device}
        try:
            model = model_loader.from_pretrained(str(Path(model_path).resolve()), **model_kwargs)
        except TypeError:
            model_kwargs["torch_dtype"] = model_kwargs.pop("dtype")
            model = model_loader.from_pretrained(str(Path(model_path).resolve()), **model_kwargs)
        if not device.startswith("cuda:") and hasattr(model, "to"):
            model = model.to(device)
        model = model.eval()
        resolved_layer = resolve_layer_module(model, layer)
        runtime_hidden_size = getattr(getattr(model, "config", None), "hidden_size", None)
        if runtime_hidden_size is not None and runtime_hidden_size != identity["hidden_size"]:
            raise PipelineError("loaded behavior model hidden size differs from inspected config")
        identity["resolved_layer_module_class"] = type(resolved_layer).__name__
        identity["hook_site"] = hook_site
        identity["hook_semantics"] = "forward_pre_hook_on_layer_input"
        backend = cls(
            model=model,
            tokenizer=tokenizer,
            behavior_identity=identity,
            vector=vector,
            vector_identity=vector_identity,
            dose_binding=dose_binding,
            layer=layer,
            hook_site=hook_site,
            device=device,
            torch_module=torch_module,
        )
        backend.capability = _issue_verified_backend_capability(
            role="behavior",
            binding={
                "lineage_identity": {
                    "model_revision": identity["model_revision"],
                    "template_sha256": identity["chat_template_sha256"],
                    "vector_id": vector_identity["vector_id"],
                    "layer": layer,
                    "hook_site": hook_site,
                    "phase": "decode-only",
                    "use_cache": True,
                    "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
                },
                "backend_identity": {
                    "behavior_identity": dict(backend.behavior_identity),
                    "vector_identity": dict(backend.vector_identity),
                    "hook_identity": {
                        "layer": layer,
                        "hook_site": hook_site,
                        "phase": "decode-only",
                        "use_cache": True,
                    },
                },
            },
            issuance_source="RealBehaviorBackend.from_pretrained",
            loader_path=(
                getattr(model_loader, "__module__", type(model_loader).__module__)
                + "."
                + getattr(model_loader, "__qualname__", type(model_loader).__qualname__)
            ),
            backend=backend,
        )
        return backend

    def _validate_identity(self, identity: Mapping[str, Any]) -> bool:
        expected = {
            "model_revision": self.behavior_identity["model_revision"],
            "template_sha256": self.behavior_identity["chat_template_sha256"],
            "layer": self.layer,
            "hook_site": self.hook_site,
            "phase": "decode-only",
            "use_cache": True,
            "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
        }
        for field, value in expected.items():
            if identity.get(field) != value:
                raise IdentityError(f"behavior backend identity mismatch: {field}")
        clean = identity.get("estimator") == "clean"
        expected_vector_id = None if clean else self.vector_identity["vector_id"]
        if identity.get("vector_id") != expected_vector_id:
            raise IdentityError("behavior backend vector identity mismatch")
        if clean:
            expected_dose = {
                "c_hex": 0.0.hex(),
                "alpha_pre_dtype_hex": 0.0.hex(),
                "alpha_post_dtype_hex": 0.0.hex(),
                "rho_hex": 0.0.hex(),
            }
        else:
            anchor = identity.get("anchor")
            estimator = identity.get("estimator")
            doses = validate_dose_binding(self.dose_binding)
            if anchor not in doses or estimator not in doses[anchor]:
                raise IdentityError("behavior backend dose selector mismatch")
            expected_dose = doses[anchor][estimator]
        for field, value in expected_dose.items():
            if identity.get(field) != value:
                raise IdentityError(f"behavior backend identity mismatch: {field}")
        return clean

    @staticmethod
    def _messages(request: Mapping[str, Any]) -> list[dict[str, str]]:
        messages = request.get("messages")
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)) or not messages:
            raise PipelineError("real behavior request requires nonempty chat messages")
        normalized: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, Mapping) or set(message) != {"role", "content"}:
                raise PipelineError("behavior chat messages require exactly role/content")
            if message["role"] not in {"system", "user", "assistant"}:
                raise PipelineError("behavior chat message role is invalid")
            if not isinstance(message["content"], str) or not message["content"]:
                raise PipelineError("behavior chat message content must be nonempty")
            normalized.append(dict(message))
        return normalized

    def _invalid_dose_evidence(
        self, identity: Mapping[str, Any], *, generation_status: str
    ) -> dict[str, Any]:
        evidence = build_call_dose_evidence(
            identity=identity,
            dose_binding=self.dose_binding,
            generation_status=generation_status,
            pre_hook_l2=1.0,
            post_hook_l2=1.0,
            vector_alignment=0.0,
            cosine_drift=0.0,
        )
        evidence["status"] = "INVALID"
        evidence["failure_code"] = "INVALID_DOSE_GEOMETRY"
        for field in (
            "nominal_c", "mu_value", "alpha_pre_dtype", "alpha_post_dtype",
            "pre_hook_l2", "post_hook_l2", "relative_dose", "norm_ratio",
            "vector_alignment", "cosine_drift",
        ):
            evidence[field] = None
        return evidence

    def __call__(self, identity: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
        if self.released or self.model is None or self.tokenizer is None:
            raise PipelineError("behavior backend has already been released")
        clean = self._validate_identity(identity)
        if request.get("generation_config") != DECODE_CONFIG:
            raise IdentityError("behavior request generation config mismatch")
        messages = self._messages(request)
        logical_id = request.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id:
            raise IdentityError("behavior request logical_id is missing")
        attempt_number = self._attempts_by_logical_id.get(logical_id, 0) + 1
        self._attempts_by_logical_id[logical_id] = attempt_number
        failure_status = (
            "TECHNICAL_FAILURE_RETRYABLE"
            if attempt_number == 1
            else "TERMINAL_TECHNICAL_FAILURE"
        )
        rendered = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        if not isinstance(rendered, str) or not rendered:
            raise PipelineError("behavior tokenizer returned an invalid rendered prompt")
        rendered_sha256 = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        if identity.get("rendered_prompt_sha256") != rendered_sha256:
            raise IdentityError("rendered behavior prompt differs from logical identity")
        encoded = self.tokenizer(rendered, return_tensors="pt")
        inputs = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in dict(encoded).items()
        }
        input_ids = inputs.get("input_ids")
        if input_ids is None or getattr(input_ids, "ndim", None) != 2:
            raise PipelineError("behavior tokenizer did not return rank-two input_ids")
        prompt_length = int(input_ids.shape[1])
        controller: InstrumentedPhaseAwareSteeringController | None = None
        generation_exception: Exception | None = None
        diagnostics: dict[str, Any] = {
            "backend": "real_local_behavior",
            "rendered_prompt_sha256": rendered_sha256,
            "prompt_token_count": prompt_length,
            "hook_installed": False,
            "hook_removed": False,
            "clean_identity": clean,
            "vector_load_dtype": self.vector_identity["selected_dtype"],
            "vector_load_device": self.vector_identity["load_device"],
            "vector_runtime_dtype": self.behavior_identity["dtype"],
            "vector_runtime_device": self.device,
            "vector_dtype_conversion_recorded": (
                self.vector_identity["selected_dtype"] != self.behavior_identity["dtype"]
            ),
            "vector_normalization": self.vector_identity["normalization"],
        }
        try:
            if not clean:
                controller = InstrumentedPhaseAwareSteeringController(
                    layer_module=resolve_layer_module(self.model, self.layer),
                    fixed_prompt_ids=input_ids[0].tolist(),
                    special_token_ids=set(self.tokenizer.all_special_ids),
                    attack_vector=self.vector,
                    attack_config={
                        "enabled": True,
                        "phase_mode": "decode_only",
                        "strength_mode": "fixed_alpha",
                        "coefficient": float.fromhex(identity["alpha_post_dtype_hex"]),
                        "effective_alpha": float.fromhex(identity["alpha_post_dtype_hex"]),
                        "decode_decay": 1.0,
                        "first_k_decode_tokens": 0,
                    },
                ).install()
                self._active_controller = controller
                diagnostics["hook_installed"] = True
            self._torch.manual_seed(DECODE_CONFIG["decode_seed"])
            if self.device.startswith("cuda:") and self._torch.cuda.is_available():
                self._torch.cuda.manual_seed_all(DECODE_CONFIG["decode_seed"])
            pad_token_id = self.tokenizer.pad_token_id
            if pad_token_id is None:
                pad_token_id = self.tokenizer.eos_token_id
            generate_kwargs = {
                **inputs,
                "do_sample": DECODE_CONFIG["do_sample"],
                "num_beams": DECODE_CONFIG["num_beams"],
                "max_new_tokens": DECODE_CONFIG["max_new_tokens"],
                "use_cache": DECODE_CONFIG["use_cache"],
                "pad_token_id": pad_token_id,
            }
            with self._torch.inference_mode():
                sequences = self.model.generate(**generate_kwargs)
        except (IdentityError, PipelineError):
            raise
        except Exception as exc:
            if not clean:
                diagnostics["dose_evidence"] = self._invalid_dose_evidence(
                    identity, generation_status=failure_status
                )
            generation_exception = exc
        finally:
            if controller is not None:
                controller.remove()
                diagnostics.update(controller.diagnostic_summary())
            diagnostics["hook_removed"] = bool(controller and controller.hook_removed)
            self.last_diagnostics = json.loads(json.dumps(diagnostics, allow_nan=False))
            self._active_controller = None
        if generation_exception is not None:
            raise TechnicalGenerationError(
                "real behavior model generation failed", diagnostics=diagnostics
            ) from generation_exception
        generated = sequences[0, prompt_length:]
        output_text = self.tokenizer.decode(generated, skip_special_tokens=True)
        diagnostics["generated_token_count"] = int(generated.shape[0])
        diagnostics["returned_new_tokens_only"] = True
        if clean:
            self.last_diagnostics = json.loads(json.dumps(diagnostics, allow_nan=False))
            return {"output_text": output_text, "diagnostics": diagnostics}
        if controller is None or not controller.geometry or controller.generated_steered_calls < 1:
            diagnostics["dose_evidence"] = self._invalid_dose_evidence(
                identity, generation_status=failure_status
            )
            self.last_diagnostics = json.loads(json.dumps(diagnostics, allow_nan=False))
            raise TechnicalGenerationError(
                "decode-only steering did not affect a generated decode call",
                diagnostics=diagnostics,
            )
        geometry = controller.geometry[-1]
        dose_evidence = build_call_dose_evidence(
            identity=identity,
            dose_binding=self.dose_binding,
            generation_status="COMPLETED",
            pre_hook_l2=float(geometry["pre_hook_l2"]),
            post_hook_l2=float(geometry["post_hook_l2"]),
            vector_alignment=float(geometry["vector_alignment"]),
            cosine_drift=float(geometry["cosine_drift"]),
        )
        self.last_diagnostics = json.loads(json.dumps(diagnostics, allow_nan=False))
        return {
            "output_text": output_text,
            "diagnostics": diagnostics,
            "dose_evidence": dose_evidence,
        }

    def release(self) -> dict[str, Any]:
        if self.released:
            raise PipelineError("behavior backend release may only occur once")
        hook_removed = True
        if self._active_controller is not None:
            self._active_controller.remove()
            hook_removed = self._active_controller.hook_removed
            self._active_controller = None
        self.model = None
        self.tokenizer = None
        self.vector = None
        collected = gc.collect()
        cuda_available = bool(self._torch.cuda.is_available())
        synchronized = False
        emptied = False
        if cuda_available and self.device.startswith("cuda:"):
            self._torch.cuda.synchronize(self.device)
            synchronized = True
            self._torch.cuda.empty_cache()
            emptied = True
        self.released = True
        return {
            "schema_version": "paper1-stage3-sequential-lifecycle-v1",
            "behavior_released": True,
            "behavior_hook_removed": hook_removed,
            "behavior_model_reference_cleared": self.model is None,
            "behavior_tokenizer_reference_cleared": self.tokenizer is None,
            "gc_collect_called": True,
            "gc_collected_count": collected,
            "cuda_available": cuda_available,
            "cuda_synchronize_called": synchronized,
            "cuda_empty_cache_called": emptied,
            "judge_loaded_after_behavior_release": False,
            "models_concurrently_resident": False,
        }
