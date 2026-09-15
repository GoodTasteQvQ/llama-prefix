"""Fixed E1/E2/E3 schedule constructors; no unregistered fallback assets."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .common import BroadeningError
from .config import EXTENSION_BUDGET, RHO_GRID
from .directions import e3_layers, third_model_layer
from .ledger import build_alias_aware_schedule, clean_identity, steered_identity


def extension_prerequisites(frames: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    e1 = frames.get("e1", {})
    gemma = config["models"]["gemma2_9b_it"]
    e1_status = e1.get("status")
    if e1_status == "READY_FOR_RUN":
        e1_result = {"status": "READY_FOR_RUN", "reason": None}
    elif e1_status == "READY_FOR_OVERLAP_GATE":
        e1_result = {"status": "READY_FOR_OVERLAP_GATE", "reason": "EXTERNAL_OVERLAP_GATE_REQUIRED"}
    else:
        e1_result = {"status": "NOT_RUN", "reason": e1.get("reason") or "EXTERNAL_OVERLAP_GATE_REQUIRED"}
    from .runtime import discover_assets

    gemma_asset = discover_assets(config)["assets"]["gemma2_9b_it"]
    gemma_ready = gemma_asset.get("status") == "READY_FOR_RUNTIME_CHECK"
    return {
        "E1": {
            **e1_result,
            "record_count": len(e1.get("records", [])),
        },
        "E2": {
            "status": "READY_FOR_RUNTIME_GATE" if gemma_ready else "NOT_RUN",
            "reason": None if gemma_ready else (gemma_asset.get("reason") or "GEMMA_2_9B_IT_ASSET_MISSING"),
            "asset": gemma_asset,
        },
        "E3": {
            "status": "PENDING_CORE_DIRECTIONS_AND_LAYER_GATES",
            "reason": "REQUIRES_CORE_ROGUE_0_TO_3_AND_PER_LAYER_SCREEN",
        },
    }


def _e1_allowed(frames: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    e1 = frames.get("e1", {})
    if e1.get("status") != "READY_FOR_RUN":
        raise BroadeningError("E1 requires registered source and closed external overlap gate")
    rows = e1.get("records")
    if not isinstance(rows, list) or len(rows) != 40:
        raise BroadeningError("E1 requires exactly 40 selected external records")
    if len({row.get("category") for row in rows}) < 4:
        raise BroadeningError("E1 requires at least four native source categories")
    return rows


def build_e1_schedule(
    *, run_id: str, frames: Mapping[str, Any], core_dose_rhos: Mapping[str, Mapping[str, Mapping[str, float]]],
    core_direction_source_run: str,
) -> list[dict[str, Any]]:
    rows: list[Any] = []
    prompts = _e1_allowed(frames)
    for model_id, layer in (("qwen25", 9), ("llama31", 11)):
        for condition in ("public_v1", "decode_only"):
            for dose_label in ("A", "S"):
                for prompt in prompts:
                    for family, direction_ids in (
                        ("rogue", [f"rogue:{index}" for index in range(4)]),
                        ("contrastive", [f"contrastive:fold:{index}" for index in range(3)]),
                    ):
                        for direction_id in direction_ids:
                            rows.append((
                                steered_identity(
                                    run_id=run_id, block="E1_steered", model_id=model_id, layer=layer,
                                    family=family, condition=condition,
                                    rho=float(core_dose_rhos[model_id][family][dose_label]),
                                    direction_id=direction_id, prompt_id=prompt["prompt_id"],
                                ),
                                dose_label,
                                {
                                    "category": prompt["category"], "frame": "E1-HarmBench40",
                                    "core_direction_source_run": core_direction_source_run,
                                    "core_dose_source": core_direction_source_run,
                                },
                            ))
        for prompt in prompts:
            rows.append((
                clean_identity(run_id=run_id, block="E1_clean", model_id=model_id, prompt_id=prompt["prompt_id"]),
                "clean",
                {"category": prompt["category"], "frame": "E1-HarmBench40", "core_source": core_direction_source_run},
            ))
    schedule = build_alias_aware_schedule(rows)
    expected = EXTENSION_BUDGET["e1_steered"] + EXTENSION_BUDGET["e1_clean"]
    if len(schedule) != expected:
        raise BroadeningError("E1 logical schedule differs from the fixed 2,320 budget")
    return schedule


def build_e2_schedule(
    *, run_id: str, jbb40: Sequence[Mapping[str, Any]], layer_count: int,
    dose_rhos: Mapping[str, Mapping[str, float]],
) -> list[dict[str, Any]]:
    if len(jbb40) != 40:
        raise BroadeningError("E2 requires JBB40")
    layer = third_model_layer(layer_count)
    rows: list[Any] = []
    for condition in ("public_v1", "decode_only"):
        for dose_label in ("A", "S"):
            for prompt in jbb40:
                for family, direction_ids in (
                    ("rogue", [f"rogue:{index}" for index in range(4)]),
                    ("contrastive", [f"contrastive:fold:{index}" for index in range(3)]),
                ):
                    for direction_id in direction_ids:
                        rows.append((
                            steered_identity(
                                run_id=run_id, block="E2_steered", model_id="gemma2_9b_it", layer=layer,
                                family=family, condition=condition, rho=float(dose_rhos[family][dose_label]),
                                direction_id=direction_id, prompt_id=prompt["prompt_id"],
                            ),
                            dose_label,
                            {"category": prompt["category"], "frame": "JBB40", "layer_formula": "floor((L-1)/3+0.5)"},
                        ))
    for prompt in jbb40:
        rows.append((
            clean_identity(run_id=run_id, block="E2_clean", model_id="gemma2_9b_it", prompt_id=prompt["prompt_id"]),
            "clean",
            {"category": prompt["category"], "frame": "JBB40"},
        ))
    schedule = build_alias_aware_schedule(rows)
    expected = EXTENSION_BUDGET["e2_steered"] + EXTENSION_BUDGET["e2_clean"]
    if len(schedule) != expected:
        raise BroadeningError("E2 logical schedule differs from the fixed 1,160 budget")
    return schedule


def build_e3_schedule(
    *, run_id: str, jbb40: Sequence[Mapping[str, Any]], model_layer_counts: Mapping[str, int],
    core_layers: Mapping[str, int], dose_rhos: Mapping[str, Mapping[int, Mapping[str, float]]],
    core_direction_source_run: str,
) -> list[dict[str, Any]]:
    if len(jbb40) != 40:
        raise BroadeningError("E3 requires JBB40")
    rows: list[Any] = []
    for model_id in ("qwen25", "llama31"):
        layers = e3_layers(int(model_layer_counts[model_id]))
        if len(set(layers)) != 2 or int(core_layers[model_id]) in layers:
            raise BroadeningError("E3 formula produces duplicate or core-overlapping layer")
        for layer in layers:
            decisions = dose_rhos.get(model_id, {}).get(layer)
            if not isinstance(decisions, Mapping):
                raise BroadeningError("E3 requires independent A/S decisions per model/layer")
            for condition in ("public_v1", "decode_only"):
                for dose_label in ("A", "S"):
                    for prompt in jbb40:
                        for direction_index in range(4):
                            rows.append((
                                steered_identity(
                                    run_id=run_id, block="E3_steered", model_id=model_id, layer=layer,
                                    family="rogue", condition=condition,
                                    rho=float(decisions[dose_label]), direction_id=f"rogue:{direction_index}",
                                    prompt_id=prompt["prompt_id"],
                                ),
                                dose_label,
                                {
                                    "category": prompt["category"], "frame": "JBB40",
                                    "vector_source": f"{core_direction_source_run}:rogue:{direction_index}",
                                    "layer_formula": "floor(0.25*(L-1)+0.5) / floor(0.75*(L-1)+0.5)",
                                },
                            ))
    schedule = build_alias_aware_schedule(rows)
    if len(schedule) != EXTENSION_BUDGET["e3_steered"]:
        raise BroadeningError("E3 logical schedule differs from the fixed 2,560 budget")
    return schedule


def _screen_prompt_rows(screen_prompts: Sequence[Mapping[str, Any]], *, block: str) -> list[Mapping[str, Any]]:
    if len(screen_prompts) < 20:
        raise BroadeningError(f"{block} screen requires at least 20 development harmful prompts")
    selected = list(screen_prompts[:20])
    for row in selected:
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get("prompt_id"), str)
            or not isinstance(row.get("category"), str)
        ):
            raise BroadeningError(f"{block} screen prompt row is invalid")
    return selected


def build_e2_screen_schedule(
    *, run_id: str, screen_prompts: Sequence[Mapping[str, Any]], layer: int,
    source_run_id: str,
) -> list[dict[str, Any]]:
    """Build the fixed E2 screen; dose labels remain ``screen`` until allocation."""
    prompts = _screen_prompt_rows(screen_prompts, block="E2")
    if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0:
        raise BroadeningError("E2 screen layer is invalid")
    rows: list[Any] = []
    for family, direction_ids in (
        ("rogue", [f"rogue:{index}" for index in range(3)]),
        ("contrastive", [f"contrastive:fold:{index}" for index in range(3)]),
    ):
        for rho in RHO_GRID:
            for prompt in prompts:
                for direction_id in direction_ids:
                    rows.append((
                        steered_identity(
                            run_id=run_id, block="E2_development", model_id="gemma2_9b_it", layer=layer,
                            family=family, condition="decode_only", rho=float(rho),
                            direction_id=direction_id, prompt_id=prompt["prompt_id"],
                        ),
                        "screen",
                        {
                            "category": prompt["category"], "frame": "development20",
                            "source_run_id": source_run_id, "screen_prompt_count": 20,
                        },
                    ))
    schedule = build_alias_aware_schedule(rows)
    if len(schedule) != EXTENSION_BUDGET["e2_screen"]:
        raise BroadeningError("E2 screen logical schedule differs from the fixed 600 budget")
    return schedule


def build_e3_screen_schedule(
    *, run_id: str, screen_prompts: Sequence[Mapping[str, Any]], model_layer_counts: Mapping[str, int],
    core_layers: Mapping[str, int], source_run_id: str,
) -> list[dict[str, Any]]:
    """Build one independent fixed-grid E3 screen for each additional layer."""
    prompts = _screen_prompt_rows(screen_prompts, block="E3")
    rows: list[Any] = []
    for model_id in ("qwen25", "llama31"):
        layers = e3_layers(int(model_layer_counts[model_id]))
        if len(set(layers)) != 2 or int(core_layers[model_id]) in layers:
            raise BroadeningError("E3 screen formula produces duplicate or core-overlapping layer")
        for layer in layers:
            for rho in RHO_GRID:
                for prompt in prompts:
                    for direction_index in range(3):
                        rows.append((
                            steered_identity(
                                run_id=run_id, block="E3_development", model_id=model_id, layer=layer,
                                family="rogue", condition="decode_only", rho=float(rho),
                                direction_id=f"rogue:{direction_index}", prompt_id=prompt["prompt_id"],
                            ),
                            "screen",
                            {
                                "category": prompt["category"], "frame": "development20",
                                "source_run_id": source_run_id, "screen_prompt_count": 20,
                                "core_direction_source_run": source_run_id,
                            },
                        ))
    schedule = build_alias_aware_schedule(rows)
    if len(schedule) != EXTENSION_BUDGET["e3_screen"]:
        raise BroadeningError("E3 screen logical schedule differs from the fixed 1,200 budget")
    return schedule


def extension_screen_plan() -> dict[str, int]:
    return {
        "E2": EXTENSION_BUDGET["e2_screen"],
        "E3": EXTENSION_BUDGET["e3_screen"],
        "total": EXTENSION_BUDGET["e2_screen"] + EXTENSION_BUDGET["e3_screen"],
    }
