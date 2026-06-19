#!/usr/bin/env python
"""Compare cosine, norm, projection, and projection+ReLU scores."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from activation_guard.analysis import (
    build_valid_token_mask,
    load_pair_records,
    masked_mean_pool,
    render_prompt,
    structure_token_ids,
)
from activation_guard.config import PromptTemplateConfig
from activation_guard.scoring import (
    cosine_score,
    norm_score,
    projection_relu_score,
    projection_score,
)
from activation_guard.vectors import resolve_vector_index
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run score ablations over harmful/harmless pairs.")
    parser.add_argument("--config", default=None, help="Optional JSON config file for ablation arguments.")
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--vector-path", required=True)
    parser.add_argument("--vector-index", type=int, default=0)
    parser.add_argument("--vector-layer", type=int, default=None)
    parser.add_argument("--vector-manifest", default=None)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--threshold", type=float, default=0.0)
    parser.add_argument("--target-tpr", type=float, default=0.9)
    parser.add_argument("--target-fpr", type=float, default=0.1)
    parser.add_argument("--padding-side", default="left")
    parser.add_argument("--torch-dtype", default="float32")
    parser.add_argument("--filter-role-markers", action="store_true")
    parser.add_argument("--filter-newlines", action="store_true")
    parser.add_argument("--judged-harmful", nargs="*", default=None)
    parser.add_argument("--judged-harmless", nargs="*", default=None)
    return parser


def apply_config_overrides(parser: argparse.ArgumentParser, argv: list[str] | None = None):
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", default=None)
    pre_args, _ = pre_parser.parse_known_args(argv)
    if not pre_args.config:
        return parser.parse_args(argv)

    config_path = Path(pre_args.config)
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    defaults = {"config": str(config_path)}
    defaults.update(config_data)
    normalized_argv = []
    for key, value in defaults.items():
        if key == "config" or value is None:
            continue
        option = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                normalized_argv.append(option)
        elif isinstance(value, list):
            normalized_argv.append(option)
            normalized_argv.extend(str(item) for item in value)
        else:
            normalized_argv.extend([option, str(value)])
    return parser.parse_args(normalized_argv)


def resolve_dtype(name: str) -> torch.dtype:
    return {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[name]


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


def summarize_method(
    harmless_scores: torch.Tensor,
    harmful_scores: torch.Tensor,
    target_tpr: float,
    target_fpr: float,
) -> dict[str, float]:
    harmless_values = harmless_scores.tolist()
    harmful_values = harmful_scores.tolist()
    fpr_at_tpr = compute_fpr_at_tpr(harmful_values, harmless_values, target_tpr)
    tpr_at_fpr = compute_tpr_at_fpr(harmful_values, harmless_values, target_fpr)
    return {
        "harmless_mean": float(harmless_scores.mean().item()),
        "harmful_mean": float(harmful_scores.mean().item()),
        "gap": float(harmless_scores.mean().item() - harmful_scores.mean().item()),
        "auroc": auc_from_scores(harmless_values, harmful_values),
        f"fpr_at_tpr_{int(target_tpr * 100)}": fpr_at_tpr,
        f"tpr_at_fpr_{int(target_fpr * 100)}": tpr_at_fpr,
    }


def compute_fpr_at_tpr(
    positive_scores: list[float],
    negative_scores: list[float],
    target_tpr: float,
) -> float:
    thresholds = sorted(set(positive_scores + negative_scores), reverse=True)
    best_fpr = 1.0
    for threshold in thresholds:
        tpr = sum(score >= threshold for score in positive_scores) / max(len(positive_scores), 1)
        fpr = sum(score >= threshold for score in negative_scores) / max(len(negative_scores), 1)
        if tpr >= target_tpr:
            best_fpr = min(best_fpr, fpr)
    return best_fpr


def compute_tpr_at_fpr(
    positive_scores: list[float],
    negative_scores: list[float],
    target_fpr: float,
) -> float:
    thresholds = sorted(set(positive_scores + negative_scores), reverse=True)
    best_tpr = 0.0
    for threshold in thresholds:
        tpr = sum(score >= threshold for score in positive_scores) / max(len(positive_scores), 1)
        fpr = sum(score >= threshold for score in negative_scores) / max(len(negative_scores), 1)
        if fpr <= target_fpr:
            best_tpr = max(best_tpr, tpr)
    return best_tpr


def summarize_judged_file(path: str | Path) -> dict[str, float]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.get("records", [])
    labels: dict[str, int] = {}
    arr = 0.0
    for record in records:
        label = record.get("judge", {}).get("judgment", "unknown")
        labels[label] = labels.get(label, 0) + 1
        arr += float(record.get("response_metrics", {}).get("arr", 0.0))
    n = len(records)
    summary = {
        "num_records": n,
        "mean_arr": arr / n if n else 0.0,
    }
    for key, value in labels.items():
        summary[f"{key}_rate"] = value / n if n else 0.0
    if payload.get("judge_summary", {}).get("mode") == "harmful":
        summary["asr"] = labels.get("unsafe", 0) / n if n else 0.0
    else:
        summary["ufr"] = labels.get("unsafe", 0) / n if n else 0.0
        summary["frr"] = labels.get("refusal", 0) / n if n else 0.0
    return summary


def main() -> int:
    args = apply_config_overrides(build_parser())
    prompt_template = PromptTemplateConfig(
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

    vector_index = args.vector_index
    if args.vector_layer is not None and args.vector_manifest:
        vector_index = resolve_vector_index(args.vector_manifest, args.vector_layer)
    vector_tensor = torch.load(args.vector_path, map_location=model.device)
    vector = vector_tensor[vector_index] if vector_tensor.ndim > 1 else vector_tensor

    pairs = load_pair_records(args.pairs)
    harmful_prompts = [pair.harmful for pair in pairs]
    harmless_prompts = [pair.harmless for pair in pairs]

    role_marker_ids, newline_ids = structure_token_ids(tokenizer, prompt_template)
    special_token_ids = set(tokenizer.all_special_ids)

    pooled_by_label: dict[str, list[torch.Tensor]] = {"harmful": [], "harmless": []}
    for label, prompts in [("harmful", harmful_prompts), ("harmless", harmless_prompts)]:
        for start in range(0, len(prompts), args.batch_size):
            batch = prompts[start : start + args.batch_size]
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
            pooled = masked_mean_pool(outputs.hidden_states[args.layer + 1], valid_mask).detach().cpu()
            pooled_by_label[label].extend(pooled)

    harmful_tensor = torch.stack(pooled_by_label["harmful"]).float()
    harmless_tensor = torch.stack(pooled_by_label["harmless"]).float()
    vector = vector.float().cpu()

    results = {
        "model_name": args.model_name,
        "layer": args.layer,
        "vector_path": args.vector_path,
        "vector_index": vector_index,
        "vector_layer": args.vector_layer,
        "vector_manifest": args.vector_manifest,
        "methods": {
            "cosine_only": summarize_method(
                cosine_score(harmless_tensor, vector),
                cosine_score(harmful_tensor, vector),
                args.target_tpr,
                args.target_fpr,
            ),
            "norm_only": summarize_method(
                norm_score(harmless_tensor),
                norm_score(harmful_tensor),
                args.target_tpr,
                args.target_fpr,
            ),
            "projection_only": summarize_method(
                projection_score(harmless_tensor, vector),
                projection_score(harmful_tensor, vector),
                args.target_tpr,
                args.target_fpr,
            ),
            "projection_relu": summarize_method(
                projection_relu_score(harmless_tensor, vector, args.threshold),
                projection_relu_score(harmful_tensor, vector, args.threshold),
                args.target_tpr,
                args.target_fpr,
            ),
        },
    }
    post_defense_metrics: dict[str, dict[str, float]] = {}
    if args.judged_harmful:
        post_defense_metrics["harmful"] = {
            Path(path).stem: summarize_judged_file(path) for path in args.judged_harmful
        }
    if args.judged_harmless:
        post_defense_metrics["harmless"] = {
            Path(path).stem: summarize_judged_file(path) for path in args.judged_harmless
        }
    if post_defense_metrics:
        results["post_defense_metrics"] = post_defense_metrics

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved ablation results to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
