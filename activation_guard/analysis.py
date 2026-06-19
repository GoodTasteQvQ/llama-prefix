from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json

import torch

from .config import PromptTemplateConfig


@dataclass
class PairRecord:
    harmful: str
    harmless: str


def load_pair_records(path: str | Path) -> list[PairRecord]:
    input_path = Path(path)
    if input_path.suffix.lower() == ".jsonl":
        records = [
            json.loads(line)
            for line in input_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        records = json.loads(input_path.read_text(encoding="utf-8"))

    pairs: list[PairRecord] = []
    for record in records:
        harmful = record.get("harmful") or record.get("positive") or record.get("unsafe")
        harmless = record.get("harmless") or record.get("negative") or record.get("safe")
        if harmful is None or harmless is None:
            raise ValueError(
                "Each pair record must contain harmful/harmless texts or their aliases."
            )
        pairs.append(PairRecord(harmful=harmful, harmless=harmless))
    return pairs


def build_messages(
    prompt: str,
    prompt_template: PromptTemplateConfig,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if prompt_template.system_prompt:
        messages.append({"role": "system", "content": prompt_template.system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


def render_prompt(
    tokenizer: Any,
    prompt: str,
    prompt_template: PromptTemplateConfig,
) -> str:
    messages = build_messages(prompt, prompt_template)
    if prompt_template.use_chat_template:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=prompt_template.add_generation_prompt,
        )
    return prompt_template.fallback_template.format(prompt=prompt)


def structure_token_ids(
    tokenizer: Any,
    prompt_template: PromptTemplateConfig,
) -> tuple[set[int], set[int]]:
    role_marker_ids: set[int] = set()
    newline_ids: set[int] = set()

    if prompt_template.filter_role_markers:
        for marker in prompt_template.role_markers:
            role_marker_ids.update(tokenizer.encode(marker, add_special_tokens=False))

    if prompt_template.filter_newlines:
        newline_ids.update(tokenizer.encode("\n", add_special_tokens=False))

    return role_marker_ids, newline_ids


def build_valid_token_mask(
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    special_token_ids: set[int],
    role_marker_ids: set[int],
    newline_ids: set[int],
) -> torch.Tensor:
    valid = attention_mask.bool().clone()
    special_mask = torch.zeros_like(valid)

    for token_id in special_token_ids:
        special_mask |= input_ids.eq(token_id)
    for token_id in role_marker_ids:
        special_mask |= input_ids.eq(token_id)
    for token_id in newline_ids:
        special_mask |= input_ids.eq(token_id)

    valid &= ~special_mask
    return valid


def masked_mean_pool(hidden_states: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
    pooled: list[torch.Tensor] = []
    for batch_index in range(hidden_states.shape[0]):
        item_mask = valid_mask[batch_index]
        if item_mask.any():
            pooled.append(hidden_states[batch_index][item_mask].mean(dim=0))
        else:
            pooled.append(hidden_states[batch_index, -1, :])
    return torch.stack(pooled, dim=0)


def batched(iterable: Iterable[str], batch_size: int) -> Iterable[list[str]]:
    bucket: list[str] = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) == batch_size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket
