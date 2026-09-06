"""Configuration and fixed budget contract for MBD-NM v2.1."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from .common import BroadeningError, canonical_sha256, read_json


DESIGN_ID = "MBD-NM"
DESIGN_REVISION = "v2.1-ccf-a-target"
IMPLEMENTATION_REVISION = "linux-single-gpu-v1"
CONFIG_SCHEMA_VERSION = "paper1-broadening-config-v1"
RHO_GRID = [0.50, 0.75, 1.00, 1.25, 1.50]

CORE_BUDGET = {
    "development": 1_200,
    "harmful_steered": 10_400,
    "harmful_clean": 200,
    "benign_steered": 780,
    "benign_clean": 60,
}
EXTENSION_BUDGET = {
    "e1_steered": 2_240,
    "e1_clean": 80,
    "e2_steered": 1_120,
    "e2_clean": 40,
    "e3_steered": 2_560,
    "e2_screen": 600,
    "e3_screen": 1_200,
}


def budget_plan() -> dict[str, Any]:
    core_total = sum(CORE_BUDGET.values())
    extension_total = sum(EXTENSION_BUDGET.values())
    return {
        "core": dict(CORE_BUDGET),
        "extension": dict(EXTENSION_BUDGET),
        "core_total": core_total,
        "extension_total": extension_total,
        "logical_generation_total": core_total + extension_total,
        "excluded_from_logical_generation_budget": [
            "A_equals_S_alias_deduplication",
            "generation_technical_retries",
            "judge_calls",
            "judge_retries",
            "smoke_generation_calls",
            "smoke_judge_calls",
            "activation_measurement_forwards",
        ],
    }


def default_config(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "design_id": DESIGN_ID,
        "design_revision": DESIGN_REVISION,
        "implementation_revision": IMPLEMENTATION_REVISION,
        "project_root": str(root),
        "output_root": str(root / "results" / "paper1_broadening"),
        "data": {
            "jbb_path": "data/jbb_behaviors_harmful.json",
            "jbb_source_revision": "local-jbb-behaviors-v1",
            "safe_pairs_path": "data/safe_pairs.json",
            "benign_path": "data/stage3/benign_prompt_frames_v1/selected_benign_confirm_30.json",
            "e1_harmbench_path": None,
            "e1_metadata_path": None,
            "e1_overlap_decisions_path": None,
            "overlap_decisions_path": None,
        },
        "models": {
            "qwen25": {
                "model_path": "/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct",
                "tokenizer_path": "/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct",
                "layer": 9,
                "model_index": 1,
                "dtype": "bfloat16",
            },
            "llama31": {
                "model_path": "/data/goodtaste_workspace/models/Meta-Llama-3.1-8B-Instruct",
                "tokenizer_path": "/data/goodtaste_workspace/models/Meta-Llama-3.1-8B-Instruct",
                "layer": 11,
                "model_index": 2,
                "dtype": "bfloat16",
            },
            "gemma2_9b_it": {
                "model_path": None,
                "tokenizer_path": None,
                "layer": None,
                "model_index": 3,
                "dtype": "bfloat16",
            },
            "judge": {
                "model_path": "/data/goodtaste_workspace/models/Qwen3-8B",
                "tokenizer_path": "/data/goodtaste_workspace/models/Qwen3-8B",
                "dtype": "float32",
            },
        },
        "runtime": {
            "model_python": "/data/goodtaste_workspace/envs/llama-prefix/bin/python",
            "gpu": 0,
            "device": "cuda:0",
            "batch_size": 1,
            "local_files_only": True,
            "trust_remote_code": False,
            "decoder": {
                "do_sample": False,
                "num_beams": 1,
                "max_new_tokens": 512,
                "use_cache": True,
                "repetition_penalty": 1.0,
                "seed": 42,
            },
            "judge": {
                "do_sample": False,
                "num_beams": 1,
                "max_new_tokens": 1296,
                "enable_thinking": True,
            },
        },
        "protocol": {
            "hook_site": "resid_pre",
            "conditions": ["public_v1", "decode_only"],
            "rho_grid": list(RHO_GRID),
            "master_seed": 42,
            "folds": 5,
            "max_fold_size": 80,
            "min_fold_size": 30,
            "development_count": 100,
            "screen_prompt_count": 20,
            "screen_direction_indices": [0, 1, 2],
            "directions": {"rogue": 8, "contrastive": 5},
            "bootstrap": {
                "replicates": 10_000,
                "minimum_successes": 9_500,
                "lower": 0.0125,
                "upper": 0.9875,
            },
        },
        "budget": budget_plan(),
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BroadeningError(message)


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(config))
    _require(value.get("schema_version") == CONFIG_SCHEMA_VERSION, "config schema version differs")
    _require(value.get("design_id") == DESIGN_ID, "config design_id differs")
    _require(value.get("design_revision") == DESIGN_REVISION, "config design revision differs")
    _require(
        value.get("implementation_revision") == IMPLEMENTATION_REVISION,
        "config implementation revision differs",
    )
    for field in ("project_root", "output_root"):
        _require(isinstance(value.get(field), str) and value[field], f"config {field} is invalid")
    models = value.get("models")
    _require(isinstance(models, dict) and set(models) == {"qwen25", "llama31", "gemma2_9b_it", "judge"}, "model registry differs")
    for model_id in ("qwen25", "llama31"):
        model = models[model_id]
        _require(isinstance(model, dict), f"{model_id} config is invalid")
        expected_layer = {"qwen25": 9, "llama31": 11}[model_id]
        _require(model.get("layer") == expected_layer, f"{model_id} core layer differs")
        _require(isinstance(model.get("model_path"), str) and model["model_path"], f"{model_id} model path is invalid")
        _require(isinstance(model.get("tokenizer_path"), str) and model["tokenizer_path"], f"{model_id} tokenizer path is invalid")
        _require(model.get("model_index") == {"qwen25": 1, "llama31": 2}[model_id], f"{model_id} model index differs")
        _require(model.get("dtype") == "bfloat16", f"{model_id} dtype differs")
    gemma = models["gemma2_9b_it"]
    _require(gemma.get("model_index") == 3, "Gemma model index differs")
    _require(gemma.get("layer") is None, "Gemma core layer must be resolved at runtime")
    _require(gemma.get("dtype") == "bfloat16", "Gemma dtype differs")
    judge = models["judge"]
    _require(isinstance(judge, dict), "Judge config is invalid")
    _require(judge.get("dtype") == "float32", "Judge dtype differs")
    protocol = value.get("protocol")
    _require(isinstance(protocol, dict), "protocol configuration is missing")
    _require(protocol.get("hook_site") == "resid_pre", "hook site must be resid_pre")
    _require(protocol.get("conditions") == ["public_v1", "decode_only"], "phase conditions differ")
    _require(protocol.get("rho_grid") == RHO_GRID, "rho grid differs")
    _require(protocol.get("master_seed") == 42, "master seed differs")
    _require(protocol.get("directions") == {"rogue": 8, "contrastive": 5}, "direction counts differ")
    _require(protocol.get("folds") == 5, "fold count differs")
    _require(protocol.get("max_fold_size") == 80, "maximum fold size differs")
    _require(protocol.get("min_fold_size") == 30, "minimum fold size differs")
    _require(protocol.get("development_count") == 100, "development count differs")
    _require(protocol.get("screen_prompt_count") == 20, "screen prompt count differs")
    _require(protocol.get("screen_direction_indices") == [0, 1, 2], "screen direction indices differ")
    bootstrap = protocol.get("bootstrap")
    _require(
        isinstance(bootstrap, dict)
        and bootstrap.get("replicates") == 10_000
        and bootstrap.get("minimum_successes") == 9_500
        and bootstrap.get("lower") == 0.0125
        and bootstrap.get("upper") == 0.9875,
        "bootstrap configuration differs",
    )
    runtime = value.get("runtime")
    _require(isinstance(runtime, dict), "runtime configuration is missing")
    _require(runtime.get("device") == "cuda:0", "runtime device differs")
    _require(runtime.get("batch_size") == 1, "runtime batch size differs")
    _require(runtime.get("local_files_only") is True, "runtime must be local-files-only")
    _require(runtime.get("trust_remote_code") is False, "remote code must be disabled")
    decoder = runtime.get("decoder")
    _require(
        isinstance(decoder, dict)
        and decoder.get("do_sample") is False
        and decoder.get("num_beams") == 1
        and decoder.get("max_new_tokens") == 512
        and decoder.get("use_cache") is True
        and decoder.get("repetition_penalty") == 1.0
        and decoder.get("seed") == 42,
        "decoder configuration differs",
    )
    _require(value.get("budget") == budget_plan(), "logical generation budget differs")
    return value


def resolve_path(config: Mapping[str, Any], value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(config["project_root"]) / path


def load_config(path: Path) -> dict[str, Any]:
    return validate_config(read_json(path))


def config_digest(config: Mapping[str, Any]) -> str:
    return canonical_sha256(validate_config(config))
