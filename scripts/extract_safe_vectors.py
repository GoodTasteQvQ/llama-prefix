#!/usr/bin/env python
"""Extract safety vectors and layer-scan statistics from harmful/harmless pairs."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from activation_guard.analysis import (
    batched,
    build_valid_token_mask,
    load_pair_records,
    masked_mean_pool,
    render_prompt,
    structure_token_ids,
)
from activation_guard.config import PromptTemplateConfig
from activation_guard.scoring import cosine_score
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract mean safety vectors and layer separation statistics.",
    )
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--pairs", required=True, help="Path to JSON/JSONL harmful/harmless pairs.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--layers", default="all", help="Comma-separated layer indices or 'all'.")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--system-prompt", default="")
    parser.add_argument("--padding-side", default="left")
    parser.add_argument("--torch-dtype", default="float32")
    parser.add_argument("--filter-role-markers", action="store_true")
    parser.add_argument("--filter-newlines", action="store_true")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--validation-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument(
        "--scales",
        default="",
        help="Comma-separated train subset sizes, e.g. 100,200,500. Empty means full train set.",
    )
    return parser


def resolve_dtype(name: str) -> torch.dtype:
    return {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[name]


def resolve_layers(model: AutoModelForCausalLM, raw: str) -> list[int]:
    if raw == "all":
        return list(range(model.config.num_hidden_layers))
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def auc_from_scores(pos_scores: list[float], neg_scores: list[float]) -> float:
    if not pos_scores or not neg_scores:
        return 0.5
    wins = 0.0
    total = 0.0
    for pos in pos_scores:
        for neg in neg_scores:
            total += 1.0
            if pos > neg:
                wins += 1.0
            elif pos == neg:
                wins += 0.5
    return wins / total if total else 0.5


def split_pairs(
    pairs,
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
    seed: int,
    shuffle: bool,
):
    if abs((train_ratio + validation_ratio + test_ratio) - 1.0) > 1e-6:
        raise ValueError("train/validation/test ratios must sum to 1.0")

    ordered = list(pairs)
    if shuffle:
        rng = random.Random(seed)
        rng.shuffle(ordered)

    total = len(ordered)
    train_end = int(total * train_ratio)
    validation_end = train_end + int(total * validation_ratio)
    return {
        "train": ordered[:train_end],
        "validation": ordered[train_end:validation_end],
        "test": ordered[validation_end:],
    }


def encode_split(
    pairs,
    tokenizer,
    model,
    prompt_template,
    layer_indices,
    batch_size,
    special_token_ids,
    role_marker_ids,
    newline_ids,
):
    harmful_prompts = [pair.harmful for pair in pairs]
    harmless_prompts = [pair.harmless for pair in pairs]
    encoded = {
        "harmful": {layer: [] for layer in layer_indices},
        "harmless": {layer: [] for layer in layer_indices},
    }

    for label, prompts in [("harmful", harmful_prompts), ("harmless", harmless_prompts)]:
        for batch in batched(prompts, batch_size):
            rendered = [render_prompt(tokenizer, prompt, prompt_template) for prompt in batch]
            inputs = tokenizer(
                rendered,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048,
                return_attention_mask=True,
            ).to(model.device)
            valid_mask = build_valid_token_mask(
                inputs.input_ids,
                inputs.attention_mask,
                special_token_ids,
                role_marker_ids,
                newline_ids,
            )
            with torch.no_grad():
                outputs = model(**inputs, output_hidden_states=True)
            for layer in layer_indices:
                hidden_states = outputs.hidden_states[layer + 1]
                pooled = masked_mean_pool(hidden_states, valid_mask).detach().cpu()
                encoded[label][layer].extend(pooled)
    return {
        label: {
            layer: torch.stack(vectors).float() if vectors else torch.empty(0)
            for layer, vectors in mapping.items()
        }
        for label, mapping in encoded.items()
    }


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_template = PromptTemplateConfig(
        system_prompt=args.system_prompt,
        filter_role_markers=args.filter_role_markers,
        filter_newlines=args.filter_newlines,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    tokenizer.padding_side = args.padding_side
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        device_map="auto",
        torch_dtype=resolve_dtype(args.torch_dtype),
    ).eval()

    layer_indices = resolve_layers(model, args.layers)
    pairs = load_pair_records(args.pairs)
    splits = split_pairs(
        pairs,
        args.train_ratio,
        args.validation_ratio,
        args.test_ratio,
        args.seed,
        args.shuffle,
    )

    role_marker_ids, newline_ids = structure_token_ids(tokenizer, prompt_template)
    special_token_ids = set(tokenizer.all_special_ids)
    encoded_splits = {
        split_name: encode_split(
            split_pairs_records,
            tokenizer,
            model,
            prompt_template,
            layer_indices,
            args.batch_size,
            special_token_ids,
            role_marker_ids,
            newline_ids,
        )
        for split_name, split_pairs_records in splits.items()
    }

    train_count = len(splits["train"])
    scales = (
        [int(part.strip()) for part in args.scales.split(",") if part.strip()]
        if args.scales.strip()
        else [train_count]
    )
    scales = [scale for scale in scales if 0 < scale <= train_count]
    if not scales:
        raise ValueError("No valid scales remain after filtering against train split size.")

    split_manifest = {
        "seed": args.seed,
        "shuffle": args.shuffle,
        "ratios": {
            "train": args.train_ratio,
            "validation": args.validation_ratio,
            "test": args.test_ratio,
        },
        "counts": {name: len(value) for name, value in splits.items()},
        "scales": scales,
    }
    (output_dir / "split_manifest.json").write_text(
        json.dumps(split_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    hidden_size = model.config.hidden_size
    scale_manifest = []
    top_level_default_scale = max(scales)

    for scale in scales:
        scale_dir = output_dir / f"scale_{scale}"
        scale_dir.mkdir(parents=True, exist_ok=True)
        vectors = []
        summary_rows = []
        vector_tensor = torch.zeros(len(layer_indices), hidden_size, dtype=torch.float32)

        for row_index, layer in enumerate(layer_indices):
            train_harmful = encoded_splits["train"]["harmful"][layer][:scale]
            train_harmless = encoded_splits["train"]["harmless"][layer][:scale]
            vector = (train_harmless.mean(dim=0) - train_harmful.mean(dim=0)).float()
            vector_tensor[row_index] = vector

            row = {
                "layer": layer,
                "vector_norm": float(vector.norm().item()),
                "train_scale": scale,
            }
            for eval_split in ["validation", "test"]:
                harmful_tensor = encoded_splits[eval_split]["harmful"][layer]
                harmless_tensor = encoded_splits[eval_split]["harmless"][layer]
                if harmful_tensor.numel() == 0 or harmless_tensor.numel() == 0:
                    continue
                harmful_scores = cosine_score(harmful_tensor, vector).tolist()
                harmless_scores = cosine_score(harmless_tensor, vector).tolist()
                projection_harmful = torch.matmul(
                    harmful_tensor, vector / vector.norm().clamp_min(1e-12)
                ).tolist()
                projection_harmless = torch.matmul(
                    harmless_tensor, vector / vector.norm().clamp_min(1e-12)
                ).tolist()
                row[f"{eval_split}_harmful_cosine_mean"] = sum(harmful_scores) / len(harmful_scores)
                row[f"{eval_split}_harmless_cosine_mean"] = sum(harmless_scores) / len(harmless_scores)
                row[f"{eval_split}_projection_gap"] = (
                    sum(projection_harmless) / len(projection_harmless)
                    - sum(projection_harmful) / len(projection_harmful)
                )
                row[f"{eval_split}_cosine_auroc"] = auc_from_scores(harmless_scores, harmful_scores)
                row[f"{eval_split}_projection_auroc"] = auc_from_scores(
                    projection_harmless, projection_harmful
                )
            summary_rows.append(row)
            vectors.append(
                {
                    "layer": layer,
                    "vector_index": row_index,
                    "train_scale": scale,
                }
            )

        torch.save(vector_tensor, scale_dir / "safe_vectors.pt")
        (scale_dir / "layer_scan_summary.json").write_text(
            json.dumps(summary_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (scale_dir / "vector_manifest.json").write_text(
            json.dumps(vectors, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        scale_manifest.append(
            {
                "train_scale": scale,
                "directory": str(scale_dir),
            }
        )

        if scale == top_level_default_scale:
            torch.save(vector_tensor, output_dir / "safe_vectors.pt")
            (output_dir / "layer_scan_summary.json").write_text(
                json.dumps(summary_rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (output_dir / "vector_manifest.json").write_text(
                json.dumps(vectors, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    (output_dir / "scale_manifest.json").write_text(
        json.dumps(scale_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved split manifest to {(output_dir / 'split_manifest.json')}")
    print(f"Saved default vectors to {(output_dir / 'safe_vectors.pt')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
