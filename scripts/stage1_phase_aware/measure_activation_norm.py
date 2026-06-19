#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from activation_guard import ExperimentConfig, ExperimentRunner

import torch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure Rogue-style activation norm mu for stage1.")
    parser.add_argument("--config", required=True, help="Stage1 experiment config.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--drop-first-k-valid", type=int, default=5)
    parser.add_argument("--max-prompts", type=int, default=None)
    return parser


def effective_token_positions(attention_mask: torch.Tensor) -> list[int]:
    return [idx for idx, value in enumerate(attention_mask.tolist()) if int(value) == 1]


def measure_one_prompt(
    runner: ExperimentRunner,
    prompt: str,
    drop_first_k_valid: int,
) -> dict[str, object]:
    rendered = runner._render_prompt(prompt)
    inputs = runner.tokenizer(
        rendered,
        return_tensors="pt",
        padding=True,
        truncation=True,
        return_attention_mask=True,
    ).to(runner.model.device)

    with torch.no_grad():
        outputs = runner.model(**inputs, output_hidden_states=True)

    hidden_states = outputs.hidden_states[runner.config.model.layer_index + 1][0]
    input_ids = inputs.input_ids[0]
    attention_mask = inputs.attention_mask[0]
    special_ids = set(runner.tokenizer.all_special_ids)

    valid_positions = effective_token_positions(attention_mask)
    kept_positions = []
    norms = []
    effective_seen = 0
    for pos in valid_positions:
        token_id = int(input_ids[pos].item())
        if token_id in special_ids:
            continue
        if effective_seen < drop_first_k_valid:
            effective_seen += 1
            continue
        effective_seen += 1
        kept_positions.append(pos)
        norms.append(float(torch.norm(hidden_states[pos], p=2).item()))

    return {
        "prompt": prompt,
        "rendered_prompt": rendered,
        "valid_token_count": len(valid_positions),
        "kept_token_count": len(kept_positions),
        "kept_positions": kept_positions,
        "mean_norm": (sum(norms) / len(norms)) if norms else 0.0,
        "norms": norms,
    }


def main() -> int:
    args = build_parser().parse_args()
    config = ExperimentConfig.from_json(args.config)
    runner = ExperimentRunner(config)
    try:
        prompts = runner.get_prompts()
        if args.max_prompts is not None:
            prompts = prompts[: args.max_prompts]
        records = [measure_one_prompt(runner, prompt, args.drop_first_k_valid) for prompt in prompts]
    finally:
        runner.close()

    all_norms = [norm for record in records for norm in record["norms"]]
    payload = {
        "config": config.to_dict(),
        "mu": (sum(all_norms) / len(all_norms)) if all_norms else 0.0,
        "drop_first_k_valid_tokens": args.drop_first_k_valid,
        "filter_special_tokens": True,
        "filter_role_markers": False,
        "filter_newlines": False,
        "padding_side": config.model.padding_side,
        "torch_dtype": config.model.torch_dtype,
        "records": records,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved mu measurement to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
