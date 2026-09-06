"""Content-span measurement, deterministic directions, and dose geometry."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import torch

from .common import BroadeningError


class ContentSpanError(BroadeningError):
    """A user-content token span cannot be demonstrated reliably."""


class DirectionError(BroadeningError):
    """A direction or calibration calculation violates the protocol."""


@dataclass(frozen=True)
class ContentSpan:
    rendered: str
    char_start: int
    char_end: int
    token_indices: tuple[int, ...]
    token_count: int


def render_native_user_prompt(tokenizer: Any, user_text: str) -> str:
    if not isinstance(user_text, str) or not user_text:
        raise ContentSpanError("user text must be a nonempty string")
    try:
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": user_text}],
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception as exc:
        raise ContentSpanError("native chat template could not render a user prompt") from exc
    if not isinstance(rendered, str) or not rendered:
        raise ContentSpanError("native chat template returned an invalid prompt")
    return rendered


def user_content_span(tokenizer: Any, user_text: str) -> ContentSpan:
    """Locate the actual user instance with sentinels, never a first text match."""
    rendered = render_native_user_prompt(tokenizer, user_text)
    digest = hashlib.sha256(("MBD-SPAN|" + user_text).encode("utf-8")).hexdigest()[:20]
    start_marker = f"[[MBD_USER_START_{digest}]]"
    end_marker = f"[[MBD_USER_END_{digest}]]"
    if start_marker in user_text or end_marker in user_text:
        raise ContentSpanError("user text collides with content-span sentinel")
    marked_text = start_marker + user_text + end_marker
    try:
        rendered_marked = tokenizer.apply_chat_template(
            [{"role": "user", "content": marked_text}],
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception as exc:
        raise ContentSpanError("native template could not render content-span sentinels") from exc
    if not isinstance(rendered_marked, str):
        raise ContentSpanError("marked native template render is invalid")
    if rendered_marked.count(start_marker) != 1 or rendered_marked.count(end_marker) != 1:
        raise ContentSpanError("template did not preserve a unique user-content sentinel")
    start_at = rendered_marked.index(start_marker)
    end_at = rendered_marked.index(end_marker)
    if end_at < start_at + len(start_marker):
        raise ContentSpanError("content-span sentinels are out of order")
    unmarked = rendered_marked.replace(start_marker, "", 1).replace(end_marker, "", 1)
    if unmarked != rendered:
        raise ContentSpanError(
            "marked template render does not reproduce the actual native prompt exactly"
        )
    # The marker occupies the original user-text start in the marked render;
    # removing it shifts the user text left to that same character index.
    char_start = start_at
    char_end = char_start + len(user_text)
    if rendered[char_start:char_end] != user_text:
        raise ContentSpanError("sentinel-derived user span does not match the supplied user text")
    try:
        encoded = tokenizer(
            rendered,
            add_special_tokens=False,
            return_offsets_mapping=True,
        )
        offsets = encoded["offset_mapping"]
    except Exception as exc:
        raise ContentSpanError("tokenizer lacks reliable offset mapping for user-content span") from exc
    if hasattr(offsets, "tolist"):
        offsets = offsets.tolist()
    if offsets and isinstance(offsets[0], list) and len(offsets) == 1 and isinstance(offsets[0][0], list):
        offsets = offsets[0]
    if not isinstance(offsets, list):
        raise ContentSpanError("tokenizer offset mapping has an unsupported shape")
    token_indices: list[int] = []
    for index, offset in enumerate(offsets):
        if not isinstance(offset, (list, tuple)) or len(offset) != 2:
            raise ContentSpanError("tokenizer emitted an invalid offset mapping entry")
        start, end = offset
        if not isinstance(start, int) or not isinstance(end, int) or end < start:
            raise ContentSpanError("tokenizer emitted non-integer offsets")
        if start < char_end and end > char_start and not (start >= char_start and end <= char_end):
            raise ContentSpanError("tokenizer emitted a token crossing the user-content boundary")
        # Boundary-crossing tokens are excluded; guessing would include template material.
        if start >= char_start and end <= char_end and end > start:
            token_indices.append(index)
    if not token_indices:
        raise ContentSpanError("user-content span contains no fully attributable tokens")
    return ContentSpan(
        rendered=rendered,
        char_start=char_start,
        char_end=char_end,
        token_indices=tuple(token_indices),
        token_count=len(token_indices),
    )


def content_mask(sequence_length: int, span: ContentSpan, *, device: Any = None) -> torch.Tensor:
    if (
        sequence_length < 1
        or min(span.token_indices, default=0) < 0
        or max(span.token_indices, default=-1) >= sequence_length
    ):
        raise DirectionError("content span cannot index the residual sequence")
    mask = torch.zeros(sequence_length, dtype=torch.bool, device=device)
    mask[list(span.token_indices)] = True
    return mask


def _finite_float32(vector: torch.Tensor, name: str) -> torch.Tensor:
    if not isinstance(vector, torch.Tensor) or not vector.dtype.is_floating_point:
        raise DirectionError(f"{name} must be a floating tensor")
    value = vector.detach().to(device="cpu", dtype=torch.float32)
    if not bool(torch.isfinite(value).all().item()):
        raise DirectionError(f"{name} contains nonfinite values")
    return value


def masked_token_mean(residual: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    residual = _finite_float32(residual, "residual")
    if residual.ndim != 2:
        raise DirectionError("residual must have shape [tokens, hidden]")
    if not isinstance(mask, torch.Tensor) or mask.ndim != 1 or mask.shape[0] != residual.shape[0]:
        raise DirectionError("content mask must align with residual tokens")
    active = mask.to(dtype=torch.bool, device=residual.device)
    if int(active.sum().item()) < 1:
        raise DirectionError("content mask has no selected tokens")
    return residual[active].mean(dim=0, dtype=torch.float32)


def contrastive_direction(pair_residuals: Sequence[tuple[torch.Tensor, torch.Tensor]]) -> torch.Tensor:
    """Equal-weight pair means in a single resid_pre coordinate system."""
    if not pair_residuals:
        raise DirectionError("contrastive direction requires at least one pair")
    differences: list[torch.Tensor] = []
    hidden_size: int | None = None
    for harmful, harmless in pair_residuals:
        harmful = _finite_float32(harmful, "harmful content mean")
        harmless = _finite_float32(harmless, "harmless content mean")
        if harmful.ndim != 1 or harmless.ndim != 1 or harmful.shape != harmless.shape:
            raise DirectionError("pair content means must be equal-width vectors")
        if hidden_size is None:
            hidden_size = int(harmful.shape[0])
        if harmful.shape[0] != hidden_size:
            raise DirectionError("contrastive pairs use inconsistent hidden dimensions")
        differences.append(harmful - harmless)
    direction = torch.stack(differences).mean(dim=0, dtype=torch.float32)
    norm = float(torch.linalg.vector_norm(direction).item())
    if not math.isfinite(norm) or norm <= 0.0:
        raise DirectionError("contrastive direction has zero or nonfinite norm")
    return (direction / norm).contiguous()


def content_mu(development_harmless_residuals: Iterable[torch.Tensor]) -> tuple[float, int]:
    """Token-weighted mean of content-token residual norms, not mean per prompt."""
    total = 0.0
    tokens = 0
    for residual in development_harmless_residuals:
        value = _finite_float32(residual, "development harmless residual")
        if value.ndim != 2:
            raise DirectionError("development residual must have shape [tokens, hidden]")
        if value.shape[0] == 0:
            continue
        norms = torch.linalg.vector_norm(value, dim=1)
        total += float(norms.sum().item())
        tokens += int(value.shape[0])
    if tokens < 1:
        raise DirectionError("mu_content has a zero content-token denominator")
    mu = total / tokens
    if not math.isfinite(mu) or mu <= 0.0:
        raise DirectionError("mu_content is nonfinite or nonpositive")
    return mu, tokens


def rogue_directions(*, hidden_size: int, model_index: int, count: int) -> list[torch.Tensor]:
    if hidden_size < 1 or model_index not in {1, 2, 3} or count < 1:
        raise DirectionError("rogue direction arguments are invalid")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(420_000 + model_index)
    result: list[torch.Tensor] = []
    for _ in range(count):
        value = torch.randn(hidden_size, generator=generator, dtype=torch.float32, device="cpu")
        norm = float(torch.linalg.vector_norm(value).item())
        if not math.isfinite(norm) or norm <= 0.0:
            raise DirectionError("rogue random vector has an invalid norm")
        result.append((value / norm).contiguous())
    return result


def validate_unit_vector(vector: torch.Tensor, *, hidden_size: int | None = None) -> float:
    value = _finite_float32(vector, "direction")
    if value.ndim != 1 or (hidden_size is not None and value.shape[0] != hidden_size):
        raise DirectionError("direction shape differs from expected hidden size")
    norm = float(torch.linalg.vector_norm(value).item())
    if not math.isfinite(norm) or abs(norm - 1.0) > 1e-5:
        raise DirectionError("direction must have unit L2 norm")
    return norm


def sign_diagnostic(
    development_harmful_means: Sequence[torch.Tensor], development_harmless_means: Sequence[torch.Tensor],
    direction: torch.Tensor,
) -> dict[str, Any]:
    if len(development_harmful_means) != len(development_harmless_means) or not development_harmful_means:
        raise DirectionError("sign diagnostic requires aligned nonempty development means")
    direction = _finite_float32(direction, "direction")
    values: list[float] = []
    for harmful, harmless in zip(development_harmful_means, development_harmless_means):
        delta = _finite_float32(harmful, "development harmful mean") - _finite_float32(
            harmless, "development harmless mean"
        )
        if delta.shape != direction.shape:
            raise DirectionError("sign diagnostic shape differs from direction")
        values.append(float(torch.dot(delta, direction).item()))
    projection = sum(values) / len(values)
    if not math.isfinite(projection):
        raise DirectionError("sign diagnostic projection is nonfinite")
    return {
        "mean_harmful_minus_harmless_projection": projection,
        "sign_check": "SIGN_VALIDATED" if projection > 0.0 else "SIGN_NOT_VALIDATED",
        "vector_flipped": False,
    }


def alpha_from_rho(rho: float, mu: float) -> float:
    if not isinstance(rho, (int, float)) or not isinstance(mu, (int, float)):
        raise DirectionError("rho and mu must be numeric")
    alpha = float(rho) * float(mu)
    if not math.isfinite(alpha) or alpha < 0.0:
        raise DirectionError("alpha is nonfinite or negative")
    return alpha


def third_model_layer(layer_count: int) -> int:
    if layer_count < 1:
        raise DirectionError("layer count must be positive")
    return math.floor((layer_count - 1) / 3 + 0.5)


def e3_layers(layer_count: int) -> tuple[int, int]:
    if layer_count < 1:
        raise DirectionError("layer count must be positive")
    return (
        math.floor(0.25 * (layer_count - 1) + 0.5),
        math.floor(0.75 * (layer_count - 1) + 0.5),
    )
