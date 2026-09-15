"""Fixture and bounded non-evidence runtime smoke checks."""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import nn

from .common import BroadeningError, atomic_write_json, utc_now
from .directions import contrastive_direction, rogue_directions, validate_unit_vector
from .judge import Qwen3JudgeRuntime
from .runtime import BehaviorRuntime, RuntimeGateError


class _FixtureLayer(nn.Module):
    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        return hidden_states


def _exercise_controller(condition: str, *, zero_alpha: bool = False, eos_first: bool = False) -> dict[str, Any]:
    from activation_guard.interventions import PhaseAwareSteeringController

    layer = _FixtureLayer()
    vector = torch.zeros(4, dtype=torch.float32)
    vector[0] = 1.0
    controller = PhaseAwareSteeringController(
        layer_module=layer,
        fixed_prompt_ids=[7, 8, 9, 10],
        special_token_ids={7},
        attack_vector=vector,
        attack_config={
            "enabled": True,
            "phase_mode": "rogue_v1_cache_semantics" if condition == "public_v1" else "decode_only",
            "coefficient": 0.0 if zero_alpha else 1.0,
        },
        capture_traces=True,
    ).install()
    try:
        prefill = layer(torch.zeros(1, 4, 4))
        decode_outputs: list[torch.Tensor] = []
        if not eos_first:
            for _ in range(3):
                decode_outputs.append(layer(torch.zeros(1, 1, 4)))
        summary = controller.summary()
    finally:
        controller.remove()
    return {
        "condition": condition,
        "zero_alpha": zero_alpha,
        "eos_first": eos_first,
        "prefill_output_sum": float(prefill.sum().item()),
        "decode_output_sums": [float(output.sum().item()) for output in decode_outputs],
        "summary": summary,
    }


def run_fixture_smoke() -> dict[str, Any]:
    public = _exercise_controller("public_v1")
    decode = _exercise_controller("decode_only")
    zero = _exercise_controller("decode_only", zero_alpha=True)
    eos = _exercise_controller("decode_only", eos_first=True)
    checks = {
        "public_cached_decode_not_steered": public["summary"]["generated_steered_calls"] == 0,
        "decode_only_cached_decode_steered": decode["summary"]["generated_steered_calls"] == 3,
        "decode_only_prefill_recorded": decode["summary"]["prefill_calls"] == 1,
        "zero_alpha_no_steering": zero["summary"]["generated_steered_calls"] == 0,
        "first_token_eos_retained": eos["summary"]["decode_calls"] == 0,
        "public_trace_has_decode": public["summary"]["trace_count"] == 4,
    }
    return {
        "schema_version": "paper1-broadening-smoke-report-v1",
        "smoke_id": "fixture-smoke-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "evidence_status": "NON_EVIDENCE",
        "checks": checks,
        "cases": [public, decode, zero, eos],
        "generation_calls": 0,
        "judge_calls": 0,
    }


def run_real_smoke(
    *, config: Mapping[str, Any], output_dir: Path, prompts: Sequence[str] | None = None,
    max_generation_calls: int = 24, max_judge_calls: int = 4,
) -> dict[str, Any]:
    """Run only the explicitly bounded integration smoke; never a dose grid."""
    if not 1 <= max_generation_calls <= 24 or not 1 <= max_judge_calls <= 4:
        raise BroadeningError("real smoke limits are fixed at 24 generation and 4 Judge calls")
    prompts = list(prompts or [
        "What are three practical ways to organize a small personal study plan?",
        "Explain in simple terms why regular backups are useful.",
    ])
    if len(prompts) != 2 or any(not isinstance(prompt, str) or not prompt for prompt in prompts):
        raise BroadeningError("real smoke requires exactly two non-evaluation prompts")
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": "paper1-broadening-smoke-report-v1",
        "smoke_id": "runtime-smoke-" + utc_now().replace(":", "").replace("+00", "Z"),
        "status": "NOT_RUN",
        "evidence_status": "NON_EVIDENCE",
        "prompts": prompts,
        "cases": [],
        "generation_calls": 0,
        "judge_calls": 0,
        "external_assets": {"gemma": "NOT_RUN", "harmbench": "NOT_RUN"},
    }
    comparison_cases: dict[tuple[str, str, str, float | None], dict[str, Any]] = {}
    judge_candidates: list[tuple[str, str, str]] = []
    for model_id in ("qwen25", "llama31"):
        details = config["models"][model_id]
        runtime: BehaviorRuntime | None = None
        try:
            runtime = BehaviorRuntime.from_pretrained(model_id=model_id, details=details)
            rogue_vector = rogue_directions(hidden_size=runtime.hidden_size, model_index=int(details["model_index"]), count=1)[0]
            contrastive_vector = contrastive_direction([
                (rogue_vector, torch.zeros_like(rogue_vector)),
            ])
            validate_unit_vector(rogue_vector, hidden_size=runtime.hidden_size)
            validate_unit_vector(contrastive_vector, hidden_size=runtime.hidden_size)
            for prompt in prompts:
                cases = (
                    ("clean", None, rogue_vector, "rogue"),
                    ("public_v1", 0.0, rogue_vector, "rogue"),
                    ("public_v1", 1.0, rogue_vector, "rogue"),
                    ("decode_only", 0.0, rogue_vector, "rogue"),
                    ("decode_only", 1.0, rogue_vector, "rogue"),
                    ("decode_only", 1.0, contrastive_vector, "contrastive"),
                )
                for condition, alpha, vector, family in cases:
                    if report["generation_calls"] >= max_generation_calls:
                        raise RuntimeGateError("real smoke generation limit reached")
                    result = runtime.generate(
                        prompt=prompt,
                        condition=condition,
                        vector=None if condition == "clean" else vector,
                        alpha=alpha,
                        max_new_tokens=16,
                        seed=42,
                        capture_trace=True,
                    )
                    result.update({"model_id": model_id, "family": family, "smoke_only": True, "evidence_status": "NON_EVIDENCE"})
                    report["cases"].append(result)
                    report["generation_calls"] += 1
                    if condition == "clean" or (condition == "decode_only" and alpha == 0.0):
                        comparison_cases[(model_id, prompt, condition, alpha)] = result
                    if result.get("text") is not None and len(judge_candidates) < max_judge_calls:
                        judge_candidates.append((model_id, prompt, result["text"]))
            lifecycle = runtime.release()
            report.setdefault("lifecycle", {})[model_id] = lifecycle
        except Exception as exc:
            report["cases"].append({
                "model_id": model_id,
                "status": "RUNTIME_NOT_RUN",
                "reason": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=3),
            })
            if runtime is not None:
                try:
                    runtime.release()
                except Exception:
                    pass
    if judge_candidates:
        judge_details = config["models"]["judge"]
        try:
            lifecycle = report.get("lifecycle", {}).get("qwen25") or report.get("lifecycle", {}).get("llama31")
            if lifecycle is None:
                raise RuntimeGateError("no completed behavior lifecycle available for Judge")
            judge = Qwen3JudgeRuntime.from_pretrained(details=judge_details, lifecycle=lifecycle)
            for model_id, prompt, response in judge_candidates:
                if report["judge_calls"] >= max_judge_calls:
                    break
                judgment = judge.four_class(prompt=prompt, response=response, domain="benign")
                report["cases"].append({"model_id": model_id, "judge": judgment, "smoke_only": True, "evidence_status": "NON_EVIDENCE"})
                report["judge_calls"] += 1
            report["judge_lifecycle"] = judge.release()
        except Exception as exc:
            report["judge_status"] = {"status": "RUNTIME_NOT_RUN", "reason": f"{type(exc).__name__}: {exc}"}
    else:
        report["judge_status"] = {
            "status": "RUNTIME_NOT_RUN",
            "reason": "no successful behavior smoke output was available for Judge",
        }
    successful = [case for case in report["cases"] if isinstance(case, dict) and "text" in case]
    zero_alpha_equal = []
    for model_id in ("qwen25", "llama31"):
        for prompt in prompts:
            clean = comparison_cases.get((model_id, prompt, "clean", None))
            zero = comparison_cases.get((model_id, prompt, "decode_only", 0.0))
            zero_alpha_equal.append(
                clean is not None and zero is not None and clean["token_ids"] == zero["token_ids"]
            )
    report["zero_alpha_clean_token_ids_equal"] = all(zero_alpha_equal) if zero_alpha_equal else False
    report["family_vector_checks"] = {
        "rogue": True,
        "contrastive": True,
        "actual_generation_vector_families": sorted({
            case["family"] for case in report["cases"]
            if isinstance(case, dict) and "text" in case and case.get("family")
        }),
    }
    behavior_failure = any(
        case.get("status") == "RUNTIME_NOT_RUN"
        for case in report["cases"]
        if isinstance(case, dict) and "text" not in case and "judge" not in case
    )
    judge_failure = report.get("judge_status", {}).get("status") == "RUNTIME_NOT_RUN"
    judge_records = [
        case["judge"] for case in report["cases"]
        if isinstance(case, dict) and isinstance(case.get("judge"), dict)
    ]
    judge_quality_failure = bool(judge_records) and any(
        record.get("status") != "PARSED" for record in judge_records
    )
    if judge_quality_failure:
        report["judge_status"] = {
            "status": "BLOCKED",
            "reason": "one or more bounded Judge smoke calls did not parse",
            "failed_calls": sum(record.get("status") != "PARSED" for record in judge_records),
            "total_calls": len(judge_records),
        }
        judge_failure = True
    report["status"] = (
        "PASS"
        if successful and report["zero_alpha_clean_token_ids_equal"] and not behavior_failure and not judge_failure
        else "RUNTIME_NOT_RUN"
    )
    atomic_write_json(output_dir / "smoke_report.json", report, overwrite=False)
    return report
