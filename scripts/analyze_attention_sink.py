#!/usr/bin/env python
"""Inspect high-norm structural tokens and attention-sink-like artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from activation_guard.analysis import (
    batched,
    build_valid_token_mask,
    render_prompt,
    structure_token_ids,
)
from activation_guard.config import PromptTemplateConfig
from datasets import load_dataset
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze structural-token norm explosions.")
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--dataset-name", default="JailbreakBench/JBB-Behaviors")
    parser.add_argument("--dataset-config", default="behaviors")
    parser.add_argument("--split", default="harmful")
    parser.add_argument("--prompt-field", default="Goal")
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--padding-side", default="left")
    parser.add_argument("--torch-dtype", default="float32")
    parser.add_argument("--top-k", type=int, default=16)
    parser.add_argument(
        "--strategies",
        default="no_filter,special_only,role_markers,newline,role_and_newline,all_structural",
        help="Comma-separated filtering strategies.",
    )
    parser.add_argument(
        "--aggregators",
        default="mean,trimmed_mean,median",
        help="Comma-separated aggregators to compare.",
    )
    return parser


def resolve_dtype(name: str) -> torch.dtype:
    return {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[name]


def aggregate_values(values: list[float], method: str) -> float:
    if not values:
        return 0.0
    if method == "mean":
        return sum(values) / len(values)
    if method == "median":
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 0:
            return (ordered[mid - 1] + ordered[mid]) / 2.0
        return ordered[mid]
    if method == "trimmed_mean":
        ordered = sorted(values)
        trim = max(1, math.floor(len(ordered) * 0.1)) if len(ordered) >= 10 else 0
        trimmed = ordered[trim : len(ordered) - trim] if trim else ordered
        return sum(trimmed) / len(trimmed)
    raise ValueError(f"Unsupported aggregator: {method}")


def strategy_mask(
    strategy: str,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    special_token_ids: set[int],
    role_marker_ids: set[int],
    newline_ids: set[int],
) -> torch.Tensor:
    valid = attention_mask.bool().clone()
    if strategy == "no_filter":
        return valid

    remove_mask = torch.zeros_like(valid)
    if strategy in {"special_only", "role_markers", "newline", "role_and_newline", "all_structural"}:
        for token_id in special_token_ids:
            remove_mask |= input_ids.eq(token_id)
    if strategy in {"role_markers", "role_and_newline", "all_structural"}:
        for token_id in role_marker_ids:
            remove_mask |= input_ids.eq(token_id)
    if strategy in {"newline", "role_and_newline", "all_structural"}:
        for token_id in newline_ids:
            remove_mask |= input_ids.eq(token_id)
    return valid & ~remove_mask


def main() -> int:
    args = build_parser().parse_args()
    prompt_template = PromptTemplateConfig()

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    tokenizer.padding_side = args.padding_side
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        device_map="auto",
        torch_dtype=resolve_dtype(args.torch_dtype),
    ).eval()

    dataset = load_dataset(
        args.dataset_name,
        args.dataset_config,
        split=args.split,
    )
    prompts = [row[args.prompt_field] for row in dataset][: args.limit]

    prompt_template.filter_role_markers = True
    prompt_template.filter_newlines = True
    role_marker_ids, newline_ids = structure_token_ids(tokenizer, prompt_template)
    special_token_ids = set(tokenizer.all_special_ids)
    strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
    aggregators = [item.strip() for item in args.aggregators.split(",") if item.strip()]

    token_rows: dict[str, list[dict[str, object]]] = {strategy: [] for strategy in strategies}
    norms_by_strategy: dict[str, list[float]] = {strategy: [] for strategy in strategies}

    for batch in batched(prompts, args.batch_size):
        rendered = [render_prompt(tokenizer, prompt, prompt_template) for prompt in batch]
        inputs = tokenizer(
            rendered,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=2048,
            return_attention_mask=True,
        ).to(model.device)
        with torch.no_grad():
            outputs = model(**inputs, output_hidden_states=True)
        hidden_states = outputs.hidden_states[args.layer + 1]
        norms = hidden_states.norm(dim=-1).detach().cpu()
        input_ids = inputs.input_ids.detach().cpu()
        attention_mask = inputs.attention_mask.detach().cpu()
        valid_mask_cpu = valid_mask.detach().cpu()

        for batch_index in range(input_ids.shape[0]):
            seq_len = int(attention_mask[batch_index].sum().item())
            prompt_norms = norms[batch_index, :seq_len]
            prompt_ids = input_ids[batch_index, :seq_len]
            for strategy in strategies:
                valid_mask = strategy_mask(
                    strategy,
                    input_ids[batch_index : batch_index + 1, :seq_len],
                    attention_mask[batch_index : batch_index + 1, :seq_len],
                    special_token_ids,
                    role_marker_ids,
                    newline_ids,
                )[0]
                selected_norms = prompt_norms[valid_mask]
                norms_by_strategy[strategy].extend(selected_norms.tolist())
                if selected_norms.numel() == 0:
                    continue
                top_values, top_indices_local = torch.topk(
                    selected_norms,
                    k=min(args.top_k, selected_norms.shape[0]),
                )
                original_positions = torch.nonzero(valid_mask, as_tuple=False).squeeze(-1)
                for value, local_index in zip(top_values.tolist(), top_indices_local.tolist()):
                    position = int(original_positions[local_index].item())
                    token_id = int(prompt_ids[position].item())
                    token_text = tokenizer.decode([token_id], skip_special_tokens=False)
                    token_rows[strategy].append(
                        {
                            "position": position,
                            "token_id": token_id,
                            "token_text": token_text,
                            "norm": float(value),
                            "is_special": token_id in special_token_ids,
                            "is_role_marker": token_id in role_marker_ids,
                            "is_newline": token_id in newline_ids,
                        }
                    )

    strategy_summaries = []
    for strategy in strategies:
        token_rows[strategy].sort(key=lambda row: row["norm"], reverse=True)
        aggregate_summary = {
            aggregator: aggregate_values(norms_by_strategy[strategy], aggregator)
            for aggregator in aggregators
        }
        strategy_summaries.append(
            {
                "strategy": strategy,
                "count": len(norms_by_strategy[strategy]),
                "aggregates": aggregate_summary,
                "top_tokens": token_rows[strategy][: args.top_k],
            }
        )

    output = {
        "model_name": args.model_name,
        "layer": args.layer,
        "num_prompts": len(prompts),
        "strategies": strategy_summaries,
    }

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved attention-sink analysis to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
