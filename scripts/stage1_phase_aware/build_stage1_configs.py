#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = ROOT / "configs"

TRACK_A_GRID = [round(0.25 * index, 2) for index in range(0, 9)]
TRACK_B_GRID = [round(0.25 * index, 2) for index in range(0, 9)]
NUM_RANDOM_VECTORS = 1000

MODEL_PROFILES = {
    "qwen25": {
        "model_key": "qwen25",
        "model_name": "/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct",
        "layer_index": 9,
        "torch_dtype": "bfloat16",
        "padding_side": "left",
        "vector_path": "./results/stage1_phase_aware/random_vector_pools/qwen25_stage1_vectors.pt",
    },
    "llama31": {
        "model_key": "llama31",
        "model_name": "/data/goodtaste_workspace/models/Meta-Llama-3___1-8B-Instruct",
        "layer_index": 11,
        "torch_dtype": "bfloat16",
        "padding_side": "right",
        "vector_path": "./results/stage1_phase_aware/random_vector_pools/llama31_stage1_vectors.pt",
    },
}

PHASE_VARIANTS = {
    "A": {
        "name": "rogue_v1",
        "phase_mode": "rogue_v1_cache_semantics",
        "use_cache": True,
        "first_k_decode_tokens": 0,
        "decode_decay": 1.0,
    },
    "B": {
        "name": "no_cache",
        "phase_mode": "prefill_and_decode",
        "use_cache": False,
        "first_k_decode_tokens": 0,
        "decode_decay": 1.0,
    },
    "C": {
        "name": "decode_only",
        "phase_mode": "decode_only",
        "use_cache": True,
        "first_k_decode_tokens": 0,
        "decode_decay": 1.0,
    },
    "D": {
        "name": "full",
        "phase_mode": "prefill_and_decode",
        "use_cache": True,
        "first_k_decode_tokens": 0,
        "decode_decay": 1.0,
    },
    "E": {
        "name": "first_k",
        "phase_mode": "first_k_decode",
        "use_cache": True,
        "first_k_decode_tokens": 3,
        "decode_decay": 1.0,
    },
    "F": {
        "name": "decay",
        "phase_mode": "decode_only",
        "use_cache": True,
        "first_k_decode_tokens": 0,
        "decode_decay": 0.85,
    },
}


def stage1_base(local: bool, profile: dict) -> dict:
    dataset = {
        "dataset_name": "JailbreakBench/JBB-Behaviors",
        "dataset_config": "behaviors",
        "split": "harmful",
        "prompt_field": "Goal",
        "limit": 8,
        "offset": 0,
    }
    if local:
        dataset["dataset_path"] = "./data/jbb_behaviors_harmful.json"
        dataset["dataset_format"] = "json"
    return {
        "output_dir": "./results/stage1_phase_aware",
        "tags": ["paper1", "stage1", "phase-aware-reproduction"],
        "model": {
            "model_name": profile["model_name"],
            "layer_index": profile["layer_index"],
            "device_map": "auto",
            "torch_dtype": profile["torch_dtype"],
            "padding_side": profile["padding_side"],
        },
        "prompt_template": {
            "use_chat_template": True,
            "system_prompt": "",
            "add_generation_prompt": True,
            "filter_special_tokens": True,
            "filter_role_markers": False,
            "filter_newlines": False,
        },
        "dataset": dataset,
        "generation": {
            "max_new_tokens": 512,
            "do_sample": False,
            "temperature": 0.0,
            "top_p": 1.0,
            "top_k": 50,
            "repetition_penalty": 1.0,
            "use_cache": True,
            "num_beams": 1,
            "seed": 42,
        },
        "intervention": {
            "attack": {
                "enabled": True,
                "vector_source": "tensor_file",
                "vector_path": profile["vector_path"],
                "vector_index": 0,
                "normalize_vector": True,
                "coefficient": 0.0,
                "strength_mode": "fixed_alpha",
                "coefficient_c": None,
                "activation_norm_mu": None,
                "effective_alpha": None,
                "mu_source": None,
                "mu_config": {},
                "phase_mode": "rogue_v1_cache_semantics",
                "first_k_decode_tokens": 0,
                "decode_decay": 1.0,
            },
            "defense": {"enabled": False},
        },
    }


def write_config(config: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def build_track_a(local: bool, profile: dict) -> None:
    model_key = profile["model_key"]
    base = stage1_base(local=local, profile=profile)
    env_dir = CONFIGS_DIR / ("local" if local else "remote")
    for label, variant in PHASE_VARIANTS.items():
        config = deepcopy(base)
        config["experiment_name"] = (
            f"stage1_trackA_{model_key}_{variant['name']}" + ("_localdata" if local else "")
        )
        config["tags"] = config["tags"] + ["track-a", "fixed-alpha", f"group-{label}"]
        config["generation"]["use_cache"] = variant["use_cache"]
        config["intervention"]["attack"]["phase_mode"] = variant["phase_mode"]
        config["intervention"]["attack"]["first_k_decode_tokens"] = variant["first_k_decode_tokens"]
        config["intervention"]["attack"]["decode_decay"] = variant["decode_decay"]
        config["intervention"]["attack"]["strength_mode"] = "fixed_alpha"
        config["intervention"]["attack"]["coefficient"] = 1.25 if label == "A" else 1.0
        output_path = env_dir / f"stage1_trackA_{model_key}_{variant['name']}.json"
        write_config(config, output_path)


def build_track_b(local: bool, profile: dict) -> None:
    model_key = profile["model_key"]
    base = stage1_base(local=local, profile=profile)
    env_dir = CONFIGS_DIR / ("local" if local else "remote")
    for label, variant in PHASE_VARIANTS.items():
        config = deepcopy(base)
        config["experiment_name"] = (
            f"stage1_trackB_{model_key}_{variant['name']}" + ("_localdata" if local else "")
        )
        config["tags"] = config["tags"] + ["track-b", "rogue-calibrated", f"group-{label}"]
        config["generation"]["use_cache"] = variant["use_cache"]
        config["intervention"]["attack"]["phase_mode"] = variant["phase_mode"]
        config["intervention"]["attack"]["first_k_decode_tokens"] = variant["first_k_decode_tokens"]
        config["intervention"]["attack"]["decode_decay"] = variant["decode_decay"]
        config["intervention"]["attack"]["strength_mode"] = "rogue_calibrated"
        config["intervention"]["attack"]["coefficient"] = 0.0
        config["intervention"]["attack"]["coefficient_c"] = 1.0
        config["intervention"]["attack"]["activation_norm_mu"] = None
        config["intervention"]["attack"]["effective_alpha"] = None
        config["intervention"]["attack"]["mu_source"] = "stage1_measure_activation_norm"
        config["intervention"]["attack"]["mu_config"] = {
            "filter_special_tokens": True,
            "filter_role_markers": False,
            "filter_newlines": False,
            "drop_first_k_valid_tokens": 5,
            "padding_side": profile["padding_side"],
            "torch_dtype": profile["torch_dtype"],
            "max_new_tokens": 512,
            "do_sample": False,
            "num_random_vectors": NUM_RANDOM_VECTORS,
        }
        output_path = env_dir / f"stage1_trackB_{model_key}_{variant['name']}.json"
        write_config(config, output_path)


def parse_models(raw: str) -> list[str]:
    if raw == "all":
        return list(MODEL_PROFILES)
    models = [item.strip() for item in raw.split(",") if item.strip()]
    if not models:
        raise ValueError("--models cannot be empty")
    unknown = sorted(set(models) - set(MODEL_PROFILES))
    if unknown:
        raise ValueError(f"Unknown model profile(s): {', '.join(unknown)}")
    return models


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate stage1 phase-aware configs.")
    parser.add_argument(
        "--models",
        default="qwen25",
        help="Comma-separated model profiles to generate, or 'all'. Choices: qwen25,llama31.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    models = parse_models(args.models)
    for model_key in models:
        profile = MODEL_PROFILES[model_key]
        for local in (True, False):
            build_track_a(local=local, profile=profile)
            build_track_b(local=local, profile=profile)
    print(f"Generated stage1 configs for: {', '.join(models)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
