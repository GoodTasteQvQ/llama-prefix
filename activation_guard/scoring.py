from __future__ import annotations

import torch


def normalize(vector: torch.Tensor) -> torch.Tensor:
    norm = vector.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    return vector / norm


def cosine_score(hidden_states: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
    hidden_norm = normalize(hidden_states)
    vector_norm = normalize(vector)
    return torch.matmul(hidden_norm, vector_norm)


def projection_score(hidden_states: torch.Tensor, vector: torch.Tensor) -> torch.Tensor:
    vector_norm = normalize(vector)
    return torch.matmul(hidden_states, vector_norm)


def norm_score(hidden_states: torch.Tensor) -> torch.Tensor:
    return hidden_states.norm(dim=-1)


def projection_relu_score(
    hidden_states: torch.Tensor,
    vector: torch.Tensor,
    threshold: float = 0.0,
) -> torch.Tensor:
    return torch.relu(projection_score(hidden_states, vector) - threshold)
