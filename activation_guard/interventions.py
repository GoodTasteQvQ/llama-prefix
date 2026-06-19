from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import torch


@dataclass
class HookTrace:
    phase: str
    seq_len: int
    mask_sum: float
    attack_applied: bool
    defense_applied: bool
    attack_strength: float
    defense_strength: float
    projection_score: float | None


class PhaseAwareSteeringController:
    """Attach a single phase-aware hook for attack and defense experiments."""

    def __init__(
        self,
        layer_module: Any,
        fixed_prompt_ids: list[int],
        special_token_ids: set[int],
        attack_vector: torch.Tensor | None = None,
        attack_config: dict[str, Any] | None = None,
        defense_vector: torch.Tensor | None = None,
        defense_config: dict[str, Any] | None = None,
        filter_role_marker_ids: set[int] | None = None,
        filter_newline_ids: set[int] | None = None,
    ) -> None:
        self.layer_module = layer_module
        self.fixed_prompt_ids = fixed_prompt_ids
        self.fixed_prompt_length = len(fixed_prompt_ids)
        self.special_token_ids = special_token_ids
        self.attack_vector = attack_vector
        self.attack_config = attack_config or {}
        self.defense_vector = defense_vector
        self.defense_config = defense_config or {}
        self.filter_role_marker_ids = filter_role_marker_ids or set()
        self.filter_newline_ids = filter_newline_ids or set()

        self.prefill_calls = 0
        self.decode_cached_calls = 0
        self.decode_full_calls = 0
        self.decode_calls = 0
        self.generated_steered_calls = 0
        self.decode_step_index = 0
        self.total_calls = 0
        self.traces: list[HookTrace] = []
        self._handle = None

        self.mask_fixed = self._build_prompt_mask()

    def _vector_like(
        self,
        hidden_states: torch.Tensor,
        vector: torch.Tensor | None,
    ) -> torch.Tensor | None:
        if vector is None:
            return None
        return vector.to(device=hidden_states.device, dtype=hidden_states.dtype)

    def _build_prompt_mask(self) -> list[int]:
        mask: list[int] = []
        for token_id in self.fixed_prompt_ids:
            masked = token_id in self.special_token_ids
            masked = masked or token_id in self.filter_role_marker_ids
            masked = masked or token_id in self.filter_newline_ids
            mask.append(0 if masked else 1)
        return mask

    def _phase_for_call(self, seq_len: int) -> str:
        if self.total_calls == 0:
            return "prefill"
        if seq_len == 1:
            return "decode_cached"
        return "decode_full"

    def _decode_gate(self, phase_mode: str, decode_step_index: int, decay: float, first_k: int) -> float:
        if phase_mode in {"decode_only", "prefill_and_decode", "prefill_base_decode_relu"}:
            return decay ** decode_step_index
        if phase_mode == "first_k_decode":
            return 1.0 if decode_step_index < first_k else 0.0
        if phase_mode == "prefill_only":
            return 0.0
        if phase_mode == "off":
            return 0.0
        return decay ** decode_step_index

    def _attack_strength(self, phase: str) -> float:
        if self.attack_vector is None or not self.attack_config.get("enabled", False):
            return 0.0

        mode = self.attack_config.get("phase_mode", "prefill_only")
        strength_mode = self.attack_config.get("strength_mode", "fixed_alpha")
        coefficient_c = self.attack_config.get("coefficient_c")
        activation_norm_mu = self.attack_config.get("activation_norm_mu")
        effective_alpha = self.attack_config.get("effective_alpha")

        if strength_mode == "rogue_calibrated":
            if effective_alpha is not None:
                coefficient = float(effective_alpha)
            elif coefficient_c is not None and activation_norm_mu is not None:
                coefficient = float(coefficient_c) * float(activation_norm_mu)
            else:
                coefficient = float(self.attack_config.get("coefficient", 0.0))
        else:
            coefficient = float(self.attack_config.get("coefficient", 0.0))
        first_k = int(self.attack_config.get("first_k_decode_tokens", 0))
        decay = float(self.attack_config.get("decode_decay", 1.0))

        if phase == "prefill":
            return (
                coefficient
                if mode in {
                    "prefill_only",
                    "prefill_and_decode",
                    "rogue_v1_cache_semantics",
                }
                else 0.0
            )

        gate = self._decode_gate(mode, self.decode_step_index, decay, first_k)
        return coefficient * gate

    def _projection_score(self, hidden_states: torch.Tensor) -> float | None:
        if self.defense_vector is None:
            return None
        defense_vector = self._vector_like(hidden_states, self.defense_vector)
        last_token = hidden_states[:, -1, :]
        return torch.matmul(last_token, defense_vector).mean().item()

    def _defense_strength(self, phase: str, projection_score: float | None) -> float:
        if self.defense_vector is None or not self.defense_config.get("enabled", False):
            return 0.0

        mode = self.defense_config.get("phase_mode", "prefill_base_decode_relu")
        base = float(self.defense_config.get("base_coefficient", 0.0))
        relu_scale = float(self.defense_config.get("relu_scale", 0.0))
        threshold = float(self.defense_config.get("threshold", 0.0))
        first_k = int(self.defense_config.get("first_k_decode_tokens", 0))
        decay = float(self.defense_config.get("decode_decay", 1.0))

        if phase == "prefill":
            if mode in {"prefill_only", "prefill_base_decode_relu", "full"}:
                return base
            return 0.0

        if mode == "decode_only":
            gate = self._decode_gate("decode_only", self.decode_step_index, decay, first_k)
            return base * gate

        if mode == "full":
            gate = self._decode_gate("decode_only", self.decode_step_index, decay, first_k)
            extra = max((projection_score or 0.0) - threshold, 0.0) * relu_scale
            return (base + extra) * gate

        if mode == "prefill_base_decode_relu":
            gate = self._decode_gate("decode_only", self.decode_step_index, decay, first_k)
            return max((projection_score or 0.0) - threshold, 0.0) * relu_scale * gate

        if mode == "prefill_base_first_k_decode_relu":
            gate = self._decode_gate("first_k_decode", self.decode_step_index, decay, first_k)
            return max((projection_score or 0.0) - threshold, 0.0) * relu_scale * gate

        return 0.0

    def _mask_tensor(self, hidden_states: torch.Tensor, phase: str) -> torch.Tensor:
        batch_size, seq_len, _ = hidden_states.shape
        attack_mode = self.attack_config.get("phase_mode", "prefill_only")
        if phase == "prefill":
            current_mask = self.mask_fixed[:seq_len]
        elif phase == "decode_full":
            if attack_mode == "rogue_v1_cache_semantics":
                current_mask = self.mask_fixed[: min(seq_len, self.fixed_prompt_length)]
                if seq_len > self.fixed_prompt_length:
                    current_mask += [1] * (seq_len - self.fixed_prompt_length)
            else:
                current_mask = self.mask_fixed[: min(seq_len, self.fixed_prompt_length)]
                if seq_len > self.fixed_prompt_length:
                    current_mask += [1] * (seq_len - self.fixed_prompt_length)
        elif attack_mode == "rogue_v1_cache_semantics":
            # Reproduce the public Rogue v1 behavior under use_cache=True:
            # on decode steps seq_len is typically 1, so the mask collapses to
            # the first prompt token rather than newly generated tokens.
            current_mask = self.mask_fixed[:seq_len]
        else:
            current_mask = [1] * seq_len
        return torch.tensor(
            current_mask,
            dtype=hidden_states.dtype,
            device=hidden_states.device,
        ).view(batch_size, seq_len, 1)

    def _hook(self, _module: Any, input_args: tuple[Any, ...]) -> tuple[Any, ...]:
        hidden_states = input_args[0].clone()
        attack_vector = self._vector_like(hidden_states, self.attack_vector)
        defense_vector = self._vector_like(hidden_states, self.defense_vector)
        seq_len = hidden_states.shape[1]
        phase = self._phase_for_call(seq_len)

        if phase == "prefill":
            self.prefill_calls += 1
        elif phase == "decode_cached":
            self.decode_cached_calls += 1
            self.decode_calls += 1
        else:
            self.decode_full_calls += 1
            self.decode_calls += 1

        mask = self._mask_tensor(hidden_states, phase)
        projection_score = self._projection_score(hidden_states)
        attack_strength = self._attack_strength(phase)
        defense_strength = self._defense_strength(phase, projection_score)

        if attack_strength:
            hidden_states = hidden_states + attack_strength * attack_vector * mask
            if phase != "prefill" and float(mask.sum().item()) > 0:
                self.generated_steered_calls += 1

        if defense_strength:
            hidden_states = hidden_states - defense_strength * defense_vector * mask

        self.traces.append(
            HookTrace(
                phase=phase,
                seq_len=seq_len,
                mask_sum=float(mask.sum().item()),
                attack_applied=bool(attack_strength),
                defense_applied=bool(defense_strength),
                attack_strength=float(attack_strength),
                defense_strength=float(defense_strength),
                projection_score=projection_score,
            )
        )

        if phase != "prefill":
            self.decode_step_index += 1
        self.total_calls += 1

        return (hidden_states, *input_args[1:])

    def install(self) -> "PhaseAwareSteeringController":
        self._handle = self.layer_module.register_forward_pre_hook(self._hook)
        return self

    def remove(self) -> None:
        if self._handle is not None:
            self._handle.remove()
            self._handle = None

    def summary(self) -> dict[str, Any]:
        strength_mode = self.attack_config.get("strength_mode", "fixed_alpha")
        return {
            "prefill_calls": self.prefill_calls,
            "decode_cached_calls": self.decode_cached_calls,
            "decode_full_calls": self.decode_full_calls,
            "decode_calls": self.decode_calls,
            "generated_steered_calls": self.generated_steered_calls,
            "attack_strength_mode": strength_mode,
            "attack_coefficient": self.attack_config.get("coefficient"),
            "attack_coefficient_c": self.attack_config.get("coefficient_c"),
            "attack_activation_norm_mu": self.attack_config.get("activation_norm_mu"),
            "attack_effective_alpha": self.attack_config.get("effective_alpha"),
            "attack_mu_source": self.attack_config.get("mu_source"),
            "attack_mu_config": self.attack_config.get("mu_config", {}),
            "trace_count": len(self.traces),
            "decode_mask_sums": [
                trace.mask_sum for trace in self.traces if trace.phase != "prefill"
            ],
            "trace_preview": [
                {
                    "phase": trace.phase,
                    "seq_len": trace.seq_len,
                    "mask_sum": trace.mask_sum,
                    "attack_applied": trace.attack_applied,
                    "defense_applied": trace.defense_applied,
                    "attack_strength": trace.attack_strength,
                    "defense_strength": trace.defense_strength,
                    "projection_score": trace.projection_score,
                }
                for trace in self.traces[:32]
            ],
        }
