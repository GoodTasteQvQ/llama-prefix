"""Runtime-facing pipeline helpers kept separate from the historical Stage 3 code."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .allocator import choose_doses
from .common import (
    BroadeningError,
    append_jsonl,
    atomic_write_bytes,
    atomic_write_json,
    canonical_json,
    canonical_sha256,
    read_json,
    read_jsonl,
    recover_jsonl_tail,
)
from .config import CORE_BUDGET, EXTENSION_BUDGET, RHO_GRID
from .extensions import (
    build_e1_schedule,
    build_e2_schedule,
    build_e2_screen_schedule,
    build_e3_schedule,
    build_e3_screen_schedule,
)
from .judge import Qwen3JudgeRuntime, build_judge_record, judge_rubric_revision, labels_for_domain
from .ledger import (
    append_generation_attempt,
    canonical_generation_records,
    generation_attempt,
    load_schedule,
    validate_attempt_sequence,
    write_schedule,
)
from .orchestration import build_core_schedule, record_loaded_identity, verify_run_source_snapshot
from .runtime import BehaviorRuntime
from .directions import (
    contrastive_direction,
    content_mu,
    e3_layers,
    masked_token_mean,
    rogue_directions,
    sign_diagnostic,
    third_model_layer,
)


def _dose_rhos(document: Mapping[str, Any]) -> dict[str, dict[str, dict[str, float]]]:
    if "core" in document and document["core"].get("status") != "DOSE_DECIDED":
        raise BroadeningError("core dose screen is not complete")
    source = document.get("decisions", document)
    if not isinstance(source, Mapping):
        raise BroadeningError("dose decision document lacks decisions")
    result: dict[str, dict[str, dict[str, float]]] = {}
    for model_id in ("qwen25", "llama31"):
        model = source.get(model_id)
        if not isinstance(model, Mapping):
            raise BroadeningError(f"dose decisions lack model {model_id}")
        result[model_id] = {}
        for family in ("rogue", "contrastive"):
            item = model.get(family)
            if not isinstance(item, Mapping) or not isinstance(item.get("A"), Mapping) or not isinstance(item.get("S"), Mapping):
                raise BroadeningError(f"dose decisions lack {model_id}/{family} A/S")
            values: dict[str, float] = {}
            for label in ("A", "S"):
                rho = item[label].get("rho")
                if isinstance(rho, bool) or not isinstance(rho, (int, float)):
                    raise BroadeningError("dose decision rho is invalid")
                if float(rho) not in RHO_GRID:
                    raise BroadeningError("dose decision rho is outside the fixed grid")
                values[label] = float(rho)
            result[model_id][family] = values
    return result


def _screen_label(rho: float, index: int) -> str:
    if rho <= 0.75:
        return "unsafe" if index % 3 != 2 else "safe"
    if rho >= 1.25:
        return "broken" if index % 3 != 2 else "safe"
    return "safe"


def _screen_rows_from_artifacts(
    schedule: Sequence[Mapping[str, Any]], judges: Sequence[Mapping[str, Any]],
    *, include_layer: bool = False,
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    labels = {row["response_id"]: row.get("four_class_label") for row in judges}
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(schedule):
        identity = row["identity"]
        if not str(identity.get("block", "")).endswith("_development"):
            continue
        key = tuple(
            [identity["model_id"], identity["family"]]
            + ([identity["layer"]] if include_layer else [])
        )
        grouped[key].append({
            "rho": identity["rho"],
            "label": labels.get(row["response_id"]),
            "response_id": row["response_id"],
            "index": index,
        })
    return grouped


def fixture_screen(*, run_dir: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    """Exercise the complete development schedule and A/S allocator without a model."""
    frames = read_json(run_dir / "frames.json")
    schedule = build_core_schedule(
        run_id=read_json(run_dir / "run_header.json")["run_id"],
        frames=frames,
        config=config,
        dose_rhos={
            model_id: {family: {"A": 0.5, "S": 1.5} for family in ("rogue", "contrastive")}
            for model_id in ("qwen25", "llama31")
        },
        include_development=True,
    )
    screen_schedule = [row for row in schedule if row["identity"]["block"] == "core_development"]
    if len(screen_schedule) != CORE_BUDGET["development"]:
        raise BroadeningError("fixture screen schedule count differs from 1,200")
    attempts_path = run_dir / "screen_generation_attempts.jsonl"
    judges_path = run_dir / "screen_judge_records.jsonl"
    attempts: list[dict[str, Any]] = []
    for row in screen_schedule:
        response_id = row["response_id"]
        rho = float(row["identity"]["rho"])
        index = int(row["identity"]["direction_id"].split(":")[-1]) + int(row["identity"]["prompt_id"].split(":")[-2])
        label = _screen_label(rho, index)
        attempt = generation_attempt(
            response_id=response_id,
            attempt_no=1,
            status="COMPLETED",
            text=f"[FIXTURE_LABEL={label}] screen response",
            token_ids=[1, 2, 3],
            runtime={"condition": "decode_only", "phase": "fixture"},
            diagnostics={"fixture": True, "status": "NON_EVIDENCE", "screen": True},
            error=None,
            identity=row["identity"],
            dose_label=row["dose_label"],
        )
        append_jsonl(attempts_path, attempt)
        attempts.append(attempt)
    judges: list[dict[str, Any]] = []
    for row, attempt in zip(screen_schedule, attempts):
        label = attempt["text"].split("[FIXTURE_LABEL=", 1)[1].split("]", 1)[0]
        record = build_judge_record(
            response_id=row["response_id"],
            prompt=row["identity"]["prompt_id"],
            response=attempt["text"],
            domain="harmful",
            four_class={
                "status": "PARSED", "label": label, "rationale": "fixture", "raw": json.dumps({"label": label, "rationale": "fixture"}),
                "error": None, "diagnostics": {"fixture": True, "status": "NON_EVIDENCE"}, "actual_call_count": 1,
            },
        )
        append_jsonl(judges_path, record)
        judges.append(record)
    grouped = _screen_rows_from_artifacts(screen_schedule, judges)
    decisions: dict[str, dict[str, Any]] = {}
    for (model_id, family), rows in sorted(grouped.items()):
        decision = choose_doses(
            rows,
            mu_content=1.0,
            expected_rhos=config["protocol"]["rho_grid"],
            expected_per_rho=60,
        )
        decisions.setdefault(model_id, {})[family] = decision
    document = {
        "schema_version": "paper1-broadening-dose-decisions-v1",
        "fixture": True,
        "status": "NON_EVIDENCE",
        "screen_schedule_count": len(screen_schedule),
        "decisions": decisions,
    }
    atomic_write_json(run_dir / "dose_decisions.json", document, overwrite=False)
    return document


def build_evaluation_schedule_for_run(*, run_dir: Path, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    frames = read_json(run_dir / "frames.json")
    decisions = read_json(run_dir / "dose_decisions.json")
    schedule = build_core_schedule(
        run_id=read_json(run_dir / "run_header.json")["run_id"],
        frames=frames,
        config=config,
        dose_rhos=_dose_rhos(decisions),
        include_development=False,
    )
    path = run_dir / "generation_schedule.jsonl"
    if not path.exists():
        write_schedule(path, schedule)
    else:
        existing = load_schedule(path)
        if existing != schedule:
            raise BroadeningError("existing evaluation schedule differs from resolved dose decisions")
    return schedule


BLOCK_ARTIFACTS: dict[str, dict[str, str]] = {
    "core": {
        "schedule": "generation_schedule.jsonl",
        "attempts": "generation_attempts.jsonl",
        "ledger": "generation_ledger.jsonl",
        "judges": "judge_records.jsonl",
    },
    "E1": {
        "schedule": "generation_schedule_E1.jsonl",
        "attempts": "generation_attempts_E1.jsonl",
        "ledger": "generation_ledger_E1.jsonl",
        "judges": "judge_records_E1.jsonl",
    },
    "E2": {
        "schedule": "generation_schedule_E2.jsonl",
        "attempts": "generation_attempts_E2.jsonl",
        "ledger": "generation_ledger_E2.jsonl",
        "judges": "judge_records_E2.jsonl",
    },
    "E3": {
        "schedule": "generation_schedule_E3.jsonl",
        "attempts": "generation_attempts_E3.jsonl",
        "ledger": "generation_ledger_E3.jsonl",
        "judges": "judge_records_E3.jsonl",
    },
}


def block_artifacts(block: str) -> dict[str, str]:
    if block not in BLOCK_ARTIFACTS:
        raise BroadeningError("block must be core, E1, E2, or E3")
    return dict(BLOCK_ARTIFACTS[block])


def _write_or_verify_schedule(path: Path, schedule: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized = [dict(row) for row in schedule]
    if not path.exists():
        write_schedule(path, normalized)
        return normalized
    existing = load_schedule(path)
    if existing != normalized:
        raise BroadeningError(f"existing schedule differs from requested schedule: {path.name}")
    return existing


def _development_screen_prompts(frames: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Resolve the fixed first 20 harmful prompts from safe-pair development."""
    split = frames.get("safe_pair_split", {})
    development = split.get("development", [])
    records = {
        row.get("pair_id"): row
        for row in split.get("records", [])
        if isinstance(row, Mapping) and isinstance(row.get("pair_id"), str)
    }
    prompts: list[dict[str, Any]] = []
    for pair_id in development[:20]:
        row = records.get(pair_id)
        if not isinstance(row, Mapping) or not isinstance(row.get("harmful"), str):
            raise BroadeningError("development screen references a missing harmful safe-pair row")
        prompts.append({
            "prompt_id": f"{pair_id}:harmful",
            "category": "development_harmful",
            "text": row["harmful"],
            "frame": "development20",
        })
    return prompts


def build_screen_schedule_for_run(
    *, run_dir: Path, config: Mapping[str, Any], block: str = "core",
) -> list[dict[str, Any]]:
    """Materialize one fixed development screen schedule without executing it."""
    frames = read_json(run_dir / "frames.json")
    run_id = read_json(run_dir / "run_header.json")["run_id"]
    source_run_id = str(run_id)
    development_prompts = _development_screen_prompts(frames)
    if block == "core":
        placeholder_doses = {
            model_id: {
                family: {"A": float(RHO_GRID[0]), "S": float(RHO_GRID[-1])}
                for family in ("rogue", "contrastive")
            }
            for model_id in ("qwen25", "llama31")
        }
        full = build_core_schedule(
            run_id=run_id, frames=frames, config=config,
            dose_rhos=placeholder_doses, include_development=True,
        )
        schedule = [row for row in full if row["identity"]["block"] == "core_development"]
        expected = CORE_BUDGET["development"]
    elif block == "E2":
        directions = read_json(run_dir / "directions.json")
        model = directions.get("models", {}).get("gemma2_9b_it", {})
        if model.get("status") != "COMPLETED":
            raise BroadeningError("E2 screen requires completed Gemma direction assets")
        schedule = build_e2_screen_schedule(
            run_id=run_id,
            screen_prompts=development_prompts,
            layer=int(model["layer"]),
            source_run_id=source_run_id,
        )
        expected = EXTENSION_BUDGET["e2_screen"]
    elif block == "E3":
        directions = read_json(run_dir / "directions.json")
        models = directions.get("models", {})
        if any(models.get(model_id, {}).get("status") != "COMPLETED" for model_id in ("qwen25", "llama31")):
            raise BroadeningError("E3 screen requires completed core direction assets")
        model_layer_counts = {
            model_id: int(models[model_id]["layer_count"])
            for model_id in ("qwen25", "llama31")
        }
        core_layers = {
            model_id: int(config["models"][model_id]["layer"])
            for model_id in ("qwen25", "llama31")
        }
        schedule = build_e3_screen_schedule(
            run_id=run_id, screen_prompts=development_prompts,
            model_layer_counts=model_layer_counts, core_layers=core_layers,
            source_run_id=source_run_id,
        )
        expected = EXTENSION_BUDGET["e3_screen"]
    else:
        raise BroadeningError("E1 has no independent dose screen; it references core decisions")
    if len(schedule) != expected:
        raise BroadeningError(f"{block} screen schedule count differs from {expected}")
    path = run_dir / f"screen_generation_schedule_{block}.jsonl"
    return _write_or_verify_schedule(path, schedule)


def _extension_dose_rhos(document: Mapping[str, Any], block: str) -> Any:
    extensions = document.get("extensions")
    if not isinstance(extensions, Mapping):
        raise BroadeningError(f"{block} dose decisions are missing")
    value = extensions.get(block)
    if not isinstance(value, Mapping) or value.get("status") != "DOSE_DECIDED":
        raise BroadeningError(f"{block} dose decisions are not complete")
    return value.get("decisions")


def build_extension_schedule_for_run(
    *, run_dir: Path, config: Mapping[str, Any], block: str,
) -> list[dict[str, Any]]:
    """Materialize an evaluation schedule for one extension block."""
    if block not in {"E1", "E2", "E3"}:
        raise BroadeningError("extension schedule block must be E1, E2, or E3")
    frames = read_json(run_dir / "frames.json")
    header = read_json(run_dir / "run_header.json")
    directions = read_json(run_dir / "directions.json")
    document = read_json(run_dir / "dose_decisions.json")
    run_id = str(header["run_id"])
    source_run_id = str(directions.get("core_direction_source_run", run_id))
    if block == "E1":
        if frames.get("e1", {}).get("status") != "READY_FOR_RUN":
            raise BroadeningError("E1 is NOT_RUN until its external overlap gate is closed")
        if any(directions.get("models", {}).get(model_id, {}).get("status") != "COMPLETED" for model_id in ("qwen25", "llama31")):
            raise BroadeningError("E1 requires completed core direction assets")
        schedule = build_e1_schedule(
            run_id=run_id, frames=frames, core_dose_rhos=_dose_rhos(document),
            core_direction_source_run=source_run_id,
        )
    elif block == "E2":
        model = directions.get("models", {}).get("gemma2_9b_it", {})
        if model.get("status") != "COMPLETED":
            raise BroadeningError("E2 is NOT_RUN until Gemma direction assets are complete")
        decisions = _extension_dose_rhos(document, block)
        if not isinstance(decisions, Mapping):
            raise BroadeningError("E2 dose decisions have invalid family structure")
        schedule = build_e2_schedule(
            run_id=run_id, jbb40=frames.get("jbb40", []), layer_count=int(model["layer_count"]),
            dose_rhos={
                family: {
                    label: float(decisions[family][label]["rho"])
                    for label in ("A", "S")
                }
                for family in ("rogue", "contrastive")
            },
        )
    else:
        models = directions.get("models", {})
        if any(models.get(model_id, {}).get("status") != "COMPLETED" for model_id in ("qwen25", "llama31")):
            raise BroadeningError("E3 requires completed core direction assets")
        decisions = _extension_dose_rhos(document, block)
        if not isinstance(decisions, Mapping):
            raise BroadeningError("E3 dose decisions have invalid model structure")
        model_layer_counts = {
            model_id: int(models[model_id]["layer_count"])
            for model_id in ("qwen25", "llama31")
        }
        core_layers = {
            model_id: int(config["models"][model_id]["layer"])
            for model_id in ("qwen25", "llama31")
        }
        layer_decisions: dict[str, dict[int, dict[str, float]]] = {}
        for model_id in ("qwen25", "llama31"):
            model_decisions = decisions.get(model_id)
            if not isinstance(model_decisions, Mapping):
                raise BroadeningError(f"E3 dose decisions lack model {model_id}")
            layer_decisions[model_id] = {
                int(layer): {
                    label: float(model_decisions[str(layer)][label]["rho"])
                    for label in ("A", "S")
                }
                for layer in e3_layers(model_layer_counts[model_id])
            }
        schedule = build_e3_schedule(
            run_id=run_id, jbb40=frames.get("jbb40", []),
            model_layer_counts=model_layer_counts, core_layers=core_layers,
            dose_rhos=layer_decisions, core_direction_source_run=source_run_id,
        )
    artifacts = block_artifacts(block)
    return _write_or_verify_schedule(run_dir / artifacts["schedule"], schedule)


def _direction_tensor_map(run_dir: Path) -> tuple[dict[str, Any], dict[str, float]]:
    import torch

    document = read_json(run_dir / "directions.json")
    tensors: dict[str, Any] = {}
    mus: dict[str, float] = {}
    for model_id, value in document.get("models", {}).items():
        if not isinstance(value, Mapping) or value.get("status") != "COMPLETED":
            continue
        path = Path(value["tensor_path"])
        if not path.is_file():
            raise BroadeningError(f"direction tensor is missing: {path}")
        pool = torch.load(path, map_location="cpu", weights_only=True)
        for item in value.get("directions", []):
            tensors[f"{model_id}|{item['direction_id']}"] = pool[int(item["tensor_index"])]
        if value.get("mu_content") is not None:
            mus[model_id] = float(value["mu_content"])
        for layer, layer_value in (value.get("mu_content_by_layer") or {}).items():
            if not isinstance(layer_value, Mapping) or layer_value.get("status") != "COMPLETED":
                continue
            mus[f"{model_id}|{int(layer)}"] = float(layer_value["mu_content"])
    return tensors, mus


def _construction_inputs(frames: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], list[list[str]], list[str]]:
    split = frames.get("safe_pair_split", {})
    record_by_pair = {
        row["pair_id"]: row
        for row in split.get("records", [])
        if isinstance(row, Mapping) and isinstance(row.get("pair_id"), str)
    }
    folds = split.get("construction_folds", [])
    development = split.get("development", [])
    if (
        not isinstance(folds, list)
        or len(folds) != 5
        or not isinstance(development, list)
        or len(development) != 100
    ):
        raise BroadeningError("safe-pair split cannot support the fixed five-fold/development construction")
    return record_by_pair, folds, development


def _contrastive_fold_vectors(
    *, runtime: BehaviorRuntime, record_by_pair: Mapping[str, Mapping[str, Any]],
    folds: Sequence[Sequence[str]],
) -> list[Any]:
    import torch

    vectors: list[Any] = []
    for pair_ids in folds:
        pair_means: list[tuple[Any, Any]] = []
        for pair_id in pair_ids:
            pair = record_by_pair.get(pair_id)
            if pair is None or not pair.get("executable_include"):
                raise BroadeningError("construction fold references a non-executable safe pair")
            harmful, _ = runtime.content_residual(pair["harmful"])
            harmless, _ = runtime.content_residual(pair["harmless"])
            pair_means.append((
                masked_token_mean(harmful, torch.ones(harmful.shape[0], dtype=torch.bool)),
                masked_token_mean(harmless, torch.ones(harmless.shape[0], dtype=torch.bool)),
            ))
        vectors.append(contrastive_direction(pair_means))
    return vectors


def _development_residuals(
    *, runtime: BehaviorRuntime, record_by_pair: Mapping[str, Mapping[str, Any]],
    development: Sequence[str],
) -> tuple[list[Any], list[Any]]:
    import torch

    harmful_means: list[Any] = []
    harmless_residuals: list[Any] = []
    for pair_id in development:
        pair = record_by_pair.get(pair_id)
        if pair is None or not pair.get("executable_include"):
            raise BroadeningError("development references a non-executable safe pair")
        harmful, _ = runtime.content_residual(pair["harmful"])
        harmless, _ = runtime.content_residual(pair["harmless"])
        harmful_means.append(masked_token_mean(harmful, torch.ones(harmful.shape[0], dtype=torch.bool)))
        harmless_residuals.append(harmless)
    return harmful_means, harmless_residuals


def _build_e3_layer_assets(
    *, run_dir: Path, config: Mapping[str, Any], frames: Mapping[str, Any],
    core_models: Mapping[str, Any], source_run_id: str,
) -> dict[str, Any]:
    """Measure E3 calibration at each extra layer while reusing core Rogue tensors."""
    record_by_pair, _folds, development = _construction_inputs(frames)
    result: dict[str, Any] = {
        "status": "COMPLETED",
        "source_run_id": source_run_id,
        "vector_source": "core_rogue_indices_0_to_3",
        "models": {},
    }
    for model_id in ("qwen25", "llama31"):
        core = core_models.get(model_id, {})
        layer_count = core.get("layer_count")
        core_layer = core.get("layer")
        if (
            core.get("status") != "COMPLETED"
            or isinstance(layer_count, bool)
            or not isinstance(layer_count, int)
            or isinstance(core_layer, bool)
            or not isinstance(core_layer, int)
        ):
            result["models"][model_id] = {"status": "NOT_RUN", "reason": "CORE_IDENTITY_MISSING"}
            continue
        try:
            layers = e3_layers(layer_count)
            if len(set(layers)) != 2 or core_layer in layers:
                raise BroadeningError("E3 formula produces duplicate or core-overlapping layer")
        except Exception as exc:
            result["models"][model_id] = {
                "status": "BLOCKED", "reason": f"{type(exc).__name__}: {exc}",
            }
            continue
        layer_records: dict[str, dict[str, Any]] = {}
        for layer in layers:
            runtime = None
            try:
                runtime = BehaviorRuntime.from_pretrained(
                    model_id=model_id,
                    details=config["models"][model_id],
                    layer_override=layer,
                )
                identity = runtime.identity()
                record_loaded_identity(run_dir=run_dir, role="behavior", identity=identity)
                _harmful, harmless = _development_residuals(
                    runtime=runtime, record_by_pair=record_by_pair, development=development,
                )
                mu, token_count = content_mu(harmless)
                layer_records[str(layer)] = {
                    "status": "COMPLETED",
                    "layer": layer,
                    "mu_content": mu,
                    "mu_content_token_count": token_count,
                    "core_direction_source_run": source_run_id,
                    "direction_ids": [f"rogue:{index}" for index in range(4)],
                    "runtime_identity": identity,
                }
            except Exception as exc:
                layer_records[str(layer)] = {
                    "status": "BLOCKED",
                    "layer": layer,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            finally:
                if runtime is not None:
                    try:
                        release = runtime.release()
                        layer_records.setdefault(str(layer), {})["release"] = release
                    except Exception as exc:
                        layer_records.setdefault(str(layer), {}).update({
                            "status": "BLOCKED",
                            "release_error": f"{type(exc).__name__}: {exc}",
                        })
        model_status = "COMPLETED" if all(
            row.get("status") == "COMPLETED" for row in layer_records.values()
        ) else "BLOCKED"
        result["models"][model_id] = {
            "status": model_status,
            "layers": layer_records,
            "analysis_reference": {"core_layer": core_layer, "direction_ids": [f"rogue:{i}" for i in range(4)]},
        }
        if isinstance(core_models, dict):
            core_models[model_id]["mu_content_by_layer"] = layer_records
    if any(row.get("status") != "COMPLETED" for row in result["models"].values()):
        result["status"] = "BLOCKED"
    return result


def _build_e2_assets(
    *, run_dir: Path, config: Mapping[str, Any], frames: Mapping[str, Any], source_run_id: str,
) -> dict[str, Any]:
    """Construct Gemma directions only when its explicitly registered asset is available."""
    import torch

    details = config["models"]["gemma2_9b_it"]
    model_path = details.get("model_path")
    if not isinstance(model_path, str) or not model_path:
        return {"status": "NOT_RUN", "reason": "GEMMA_ASSET_MISSING"}
    record_by_pair, folds, development = _construction_inputs(frames)
    probe = None
    probe_release_error: str | None = None
    try:
        probe = BehaviorRuntime.from_pretrained(
            model_id="gemma2_9b_it", details=details, layer_override=0,
        )
        probe_identity = probe.identity()
        record_loaded_identity(run_dir=run_dir, role="behavior", identity=probe_identity)
        layer_count = probe.layer_count
    except Exception as exc:
        return {
            "status": "NOT_RUN", "reason": f"GEMMA_RUNTIME_UNAVAILABLE: {type(exc).__name__}: {exc}",
        }
    finally:
        if probe is not None:
            try:
                probe.release()
            except Exception as exc:
                probe_release_error = f"{type(exc).__name__}: {exc}"
    if probe_release_error is not None:
        return {
            "status": "BLOCKED",
            "reason": f"GEMMA_PROBE_RELEASE_FAILURE: {probe_release_error}",
        }
    try:
        layer = third_model_layer(layer_count)
        runtime = BehaviorRuntime.from_pretrained(
            model_id="gemma2_9b_it", details=details, layer_override=layer,
        )
        try:
            identity = runtime.identity()
            record_loaded_identity(run_dir=run_dir, role="behavior", identity=identity)
            fold_vectors = _contrastive_fold_vectors(
                runtime=runtime, record_by_pair=record_by_pair, folds=folds,
            )
            harmful_means, harmless_residuals = _development_residuals(
                runtime=runtime, record_by_pair=record_by_pair, development=development,
            )
            mu, token_count = content_mu(harmless_residuals)
            harmless_means = [
                masked_token_mean(value, torch.ones(value.shape[0], dtype=torch.bool))
                for value in harmless_residuals
            ]
            rogue = rogue_directions(hidden_size=runtime.hidden_size, model_index=3, count=4)
            all_vectors = [*rogue, *fold_vectors]
            tensor_path = run_dir / "directions_gemma2_9b_it.pt"
            torch.save(torch.stack(all_vectors).to(dtype=torch.float32, device="cpu"), tensor_path)
            diagnostics = [
                sign_diagnostic(harmful_means, harmless_means, vector)
                for vector in fold_vectors
            ]
            return {
                "status": "COMPLETED",
                "source_run_id": source_run_id,
                "layer": layer,
                "layer_count": runtime.layer_count,
                "model": {
                    "status": "COMPLETED",
                    "tensor_path": str(tensor_path),
                    "hidden_size": runtime.hidden_size,
                    "layer": layer,
                    "layer_count": runtime.layer_count,
                    "mu_content": mu,
                    "mu_content_token_count": token_count,
                    "runtime_identity": identity,
                    "directions": [
                        {
                            "direction_id": f"rogue:{index}", "family": "rogue", "tensor_index": index,
                            "seed": 420000 + 3, "dtype": "float32", "norm": 1.0,
                            "source_fold_ids": None, "sign_check": "NOT_APPLICABLE_RANDOM",
                        }
                        for index in range(4)
                    ] + [
                        {
                            "direction_id": f"contrastive:fold:{index}", "family": "contrastive",
                            "tensor_index": 4 + index, "seed": 42, "dtype": "float32", "norm": 1.0,
                            "source_fold_ids": folds[index], "sign_check": diagnostics[index],
                        }
                        for index in range(5)
                    ],
                },
            }
        finally:
            runtime.release()
    except Exception as exc:
        return {"status": "BLOCKED", "reason": f"{type(exc).__name__}: {exc}"}


def build_directions(*, run_dir: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    """Construct core tensors only after the human semantic-overlap gate is closed."""
    import torch

    frames = read_json(run_dir / "frames.json")
    split = frames.get("safe_pair_split", {})
    if split.get("gate") != "READY_FOR_CONSTRUCTION":
        document = {
            "schema_version": "paper1-broadening-directions-v1",
            "status": "BLOCKED",
            "reason": "SAFE_PAIR_SEMANTIC_OVERLAP_GATE_NOT_CLOSED",
            "safe_pair_gate": split.get("gate"),
            "models": {},
            "E1": {"status": "NOT_RUN", "reason": "CORE_CONSTRUCTION_BLOCKED"},
            "E2": {"status": "NOT_RUN", "reason": "GEMMA_ASSET_MISSING_OR_CORE_GATE_PENDING"},
            "E3": {"status": "NOT_RUN", "reason": "CORE_LAYER_GATE_PENDING"},
        }
        atomic_write_json(run_dir / "directions.json", document, overwrite=False)
        return document
    record_by_pair = {row["pair_id"]: row for row in split.get("records", [])}
    folds = split.get("construction_folds", [])
    development = split.get("development", [])
    if len(folds) != 5 or len(development) != 100:
        raise BroadeningError("safe-pair split cannot support the fixed five-fold/development construction")
    output: dict[str, Any] = {
        "schema_version": "paper1-broadening-directions-v1",
        "status": "COMPLETED",
        "safe_pair_gate": split["gate"],
        "core_direction_source_run": read_json(run_dir / "run_header.json")["run_id"],
        "models": {},
        "E1": {"status": "REFERENCES_CORE_AFTER_E1_ASSET_GATE"},
        "E2": {"status": "NOT_RUN", "reason": "GEMMA_ASSET_MISSING"},
        "E3": {"status": "PENDING_CORE_LAYER_ASSETS"},
    }
    for model_id in ("qwen25", "llama31"):
        details = config["models"][model_id]
        runtime = None
        try:
            runtime = BehaviorRuntime.from_pretrained(model_id=model_id, details=details)
            fold_vectors: list[Any] = []
            for fold_index, pair_ids in enumerate(folds):
                pair_means: list[tuple[Any, Any]] = []
                for pair_id in pair_ids:
                    pair = record_by_pair.get(pair_id)
                    if pair is None or not pair.get("executable_include"):
                        raise BroadeningError("construction fold references a non-executable safe pair")
                    harmful, _ = runtime.content_residual(pair["harmful"])
                    harmless, _ = runtime.content_residual(pair["harmless"])
                    pair_means.append((masked_token_mean(harmful, torch.ones(harmful.shape[0], dtype=torch.bool)), masked_token_mean(harmless, torch.ones(harmless.shape[0], dtype=torch.bool))))
                fold_vectors.append(contrastive_direction(pair_means))
            development_harmful: list[Any] = []
            development_harmless: list[Any] = []
            for pair_id in development:
                pair = record_by_pair.get(pair_id)
                if pair is None or not pair.get("executable_include"):
                    raise BroadeningError("development references a non-executable safe pair")
                harmful, _ = runtime.content_residual(pair["harmful"])
                harmless, _ = runtime.content_residual(pair["harmless"])
                development_harmful.append(masked_token_mean(harmful, torch.ones(harmful.shape[0], dtype=torch.bool)))
                development_harmless.append(harmless)
            mu, token_count = content_mu(development_harmless)
            harmless_means = [masked_token_mean(value, torch.ones(value.shape[0], dtype=torch.bool)) for value in development_harmless]
            rogue = rogue_directions(
                hidden_size=runtime.hidden_size,
                model_index=int(details["model_index"]),
                count=8,
            )
            all_vectors = [*rogue, *fold_vectors]
            tensor_path = run_dir / f"directions_{model_id}.pt"
            torch.save(torch.stack(all_vectors).to(dtype=torch.float32, device="cpu"), tensor_path)
            diagnostics = [
                sign_diagnostic(development_harmful, harmless_means, vector)
                for vector in fold_vectors
            ]
            output["models"][model_id] = {
                "status": "COMPLETED",
                "tensor_path": str(tensor_path),
                "hidden_size": runtime.hidden_size,
                "layer": runtime.layer,
                "layer_count": runtime.layer_count,
                "mu_content": mu,
                "mu_content_token_count": token_count,
                "directions": [
                    {
                        "direction_id": f"rogue:{index}", "family": "rogue", "tensor_index": index,
                        "seed": 420000 + int(details["model_index"]), "dtype": "float32", "norm": 1.0,
                        "source_fold_ids": None, "sign_check": "NOT_APPLICABLE_RANDOM",
                    }
                    for index in range(8)
                ] + [
                    {
                        "direction_id": f"contrastive:fold:{index}", "family": "contrastive", "tensor_index": 8 + index,
                        "seed": 42, "dtype": "float32", "norm": 1.0,
                        "source_fold_ids": folds[index], "sign_check": diagnostics[index],
                    }
                    for index in range(5)
                ],
                "runtime_identity": runtime.identity(),
            }
            record_loaded_identity(
                run_dir=run_dir,
                role="behavior",
                identity=output["models"][model_id]["runtime_identity"],
            )
        except Exception as exc:
            output["models"][model_id] = {
                "status": "BLOCKED", "reason": f"{type(exc).__name__}: {exc}",
            }
        finally:
            if runtime is not None:
                try:
                    release = runtime.release()
                    output["models"].setdefault(model_id, {})["release"] = release
                except Exception as exc:
                    output["models"].setdefault(model_id, {}).update({
                        "status": "BLOCKED",
                        "release_error": f"{type(exc).__name__}: {exc}",
                    })
    e1_frame = frames.get("e1", {})
    e1_ready = e1_frame.get("status") == "READY_FOR_RUN"
    output["E1"] = {
        "status": "REFERENCES_CORE" if e1_ready else "NOT_RUN",
        "reason": None if e1_ready else e1_frame.get("reason", "E1_ASSET_OR_OVERLAP_GATE_PENDING"),
        "core_direction_source_run": output["core_direction_source_run"],
    }
    core_ready = all(
        output["models"].get(model_id, {}).get("status") == "COMPLETED"
        for model_id in ("qwen25", "llama31")
    )
    if core_ready:
        output["E3"] = _build_e3_layer_assets(
            run_dir=run_dir,
            config=config,
            frames=frames,
            core_models=output["models"],
            source_run_id=output["core_direction_source_run"],
        )
        e2_assets = _build_e2_assets(
            run_dir=run_dir,
            config=config,
            frames=frames,
            source_run_id=output["core_direction_source_run"],
        )
        output["E2"] = {key: value for key, value in e2_assets.items() if key != "model"}
        if isinstance(e2_assets.get("model"), Mapping):
            output["models"]["gemma2_9b_it"] = dict(e2_assets["model"])
    else:
        output["E3"] = {"status": "NOT_RUN", "reason": "CORE_DIRECTION_ASSET_BLOCKED"}
        output["E2"] = {"status": "NOT_RUN", "reason": "CORE_DIRECTION_ASSET_BLOCKED_OR_GEMMA_MISSING"}
    if any(item.get("status") != "COMPLETED" for item in output["models"].values()):
        output["status"] = "BLOCKED"
    atomic_write_json(run_dir / "directions.json", output, overwrite=False)
    return output


def _existing_attempt_state(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    state: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        state[row["response_id"]].append(row)
    for response_id, attempts in state.items():
        validate_attempt_sequence(
            sorted(attempts, key=lambda row: row["attempt_no"]), allow_pending_retry=True
        )
    return state


def _schedule_prompt_map(frames: Mapping[str, Any]) -> dict[str, str]:
    return _prompt_map(frames)


def _validate_existing_judge_record(
    row: Mapping[str, Any], scheduled: Mapping[str, Any], prompts: Mapping[str, str],
    response: str,
) -> dict[str, Any]:
    if row.get("schema_version") != "paper1-broadening-judge-record-v1":
        raise BroadeningError("existing Judge record schema differs")
    if row.get("response_id") != scheduled.get("response_id"):
        raise BroadeningError("existing Judge record response_id differs from schedule")
    identity = scheduled.get("identity", {})
    domain = "benign" if str(identity.get("block", "")).startswith("core_benign_") else "harmful"
    expected_prompt = prompts.get(str(identity.get("prompt_id")))
    if expected_prompt is None:
        raise BroadeningError(f"Judge prompt is absent: {identity.get('prompt_id')}")
    if row.get("domain") != domain:
        raise BroadeningError("existing Judge record domain differs from schedule")
    if row.get("judge_version") != judge_rubric_revision():
        raise BroadeningError("existing Judge record rubric differs")
    expected_request = {
        "prompt": expected_prompt,
        "response": response,
        "domain": domain,
    }
    if row.get("request_sha256") != canonical_sha256(expected_request):
        raise BroadeningError("existing Judge record request payload differs from generation")
    status = row.get("four_class_status")
    allowed = set(labels_for_domain(domain))
    if status == "PARSED":
        if row.get("four_class_label") not in allowed or not isinstance(row.get("four_class_rationale"), str) or not row["four_class_rationale"].strip():
            raise BroadeningError("existing parsed Judge record is invalid")
    elif status not in {"PARSE_FAILURE", "TECHNICAL_FAILURE", "UNEXECUTED"}:
        raise BroadeningError("existing Judge record status is invalid")
    elif row.get("four_class_label") is not None or row.get("four_class_rationale") is not None:
        raise BroadeningError("existing failed Judge record carries a label or rationale")
    binary_status = row.get("binary_status")
    if binary_status not in {"NOT_REQUESTED", "SHORT_RULE_SAFE", "PARSED", "PARSE_FAILURE", "TECHNICAL_FAILURE", "UNEXECUTED"}:
        raise BroadeningError("existing Judge binary status is invalid")
    if binary_status in {"PARSED", "SHORT_RULE_SAFE"} and row.get("binary_value") not in {"safe", "unsafe"}:
        raise BroadeningError("existing parsed binary Judge value is invalid")
    if binary_status not in {"PARSED", "SHORT_RULE_SAFE"} and row.get("binary_value") is not None:
        raise BroadeningError("existing failed binary Judge record carries a value")
    short_rule_applied = row.get("binary_short_rule_applied")
    if not isinstance(short_rule_applied, bool) or short_rule_applied != (binary_status == "SHORT_RULE_SAFE"):
        raise BroadeningError("existing Judge record short-rule flag is invalid")
    return dict(row)


def _write_unavailable_judge_records(
    *, path: Path, schedule: Sequence[Mapping[str, Any]], canonical: Mapping[str, Mapping[str, Any]],
    prompts: Mapping[str, str], existing: Mapping[str, Mapping[str, Any]], reason: str,
    binary: bool = False,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    rewrite = False
    for scheduled in schedule:
        response_id = scheduled["response_id"]
        identity = scheduled["identity"]
        domain = "benign" if str(identity["block"]).startswith("core_benign_") else "harmful"
        prompt = prompts.get(identity["prompt_id"], identity["prompt_id"])
        canonical_record = canonical.get(response_id)
        canonical_attempt = (
            canonical_record.get("canonical_attempt")
            if canonical_record is not None
            else None
        )
        response = str(canonical_attempt["text"]) if canonical_attempt is not None else ""
        if response_id in existing:
            record = dict(existing[response_id])
            if binary and record.get("binary_status") == "NOT_REQUESTED":
                record = _record_with_binary(
                    existing=record,
                    prompt=prompt,
                    response=response,
                    binary=_binary_failure(
                        status="UNEXECUTED",
                        error=reason if canonical_attempt is not None else "generation_missing",
                    ),
                )
                rewrite = True
            records.append(record)
            continue
        if canonical_attempt is not None:
            four_class = {
                "status": "TECHNICAL_FAILURE", "label": None, "rationale": None, "raw": None,
                "error": reason, "diagnostics": {"judge_runtime_unavailable": True}, "actual_call_count": 0,
            }
            binary_record = _binary_failure(status="UNEXECUTED", error=reason) if binary else None
        else:
            four_class = {
                "status": "UNEXECUTED", "label": None, "rationale": None, "raw": None,
                "error": "generation_missing", "diagnostics": {"judge_runtime_unavailable": True}, "actual_call_count": 0,
            }
            binary_record = _binary_failure(status="UNEXECUTED", error="generation_missing") if binary else None
        records.append(build_judge_record(
            response_id=response_id, prompt=prompt, response=response, domain=domain,
            four_class=four_class, binary=binary_record,
        ))
    if rewrite:
        payload = b"".join((canonical_json(record) + "\n").encode("utf-8") for record in records)
        atomic_write_bytes(path, payload, overwrite=True)
    else:
        for record in records:
            if record["response_id"] not in existing:
                append_jsonl(path, record)
    return records


def _binary_failure(*, status: str, error: str, actual_call_count: int = 0) -> dict[str, Any]:
    return {
        "status": status,
        "value": None,
        "rule_source": "Rogue_binary_rubric",
        "short_rule_applied": False,
        "raw": None,
        "error": error,
        "actual_call_count": actual_call_count,
    }


def _binary_with_retry(*, judge: Qwen3JudgeRuntime, prompt: str, response: str) -> dict[str, Any]:
    try:
        result = judge.rogue_binary(prompt=prompt, response=response)
    except Exception as exc:
        result = _binary_failure(status="TECHNICAL_FAILURE", error=f"{type(exc).__name__}: {exc}", actual_call_count=1)
    if result["status"] not in {"PARSE_FAILURE", "TECHNICAL_FAILURE"}:
        return result
    try:
        retry = judge.rogue_binary(prompt=prompt, response=response)
    except Exception as exc:
        retry = _binary_failure(status="TECHNICAL_FAILURE", error=f"{type(exc).__name__}: {exc}", actual_call_count=1)
    return {
        **retry,
        "actual_call_count": int(result.get("actual_call_count", 1))
        + int(retry.get("actual_call_count", 1)),
    }


def _record_with_binary(
    *, existing: Mapping[str, Any], prompt: str, response: str, binary: Mapping[str, Any]
) -> dict[str, Any]:
    four_class = {
        "status": existing.get("four_class_status"),
        "label": existing.get("four_class_label"),
        "rationale": existing.get("four_class_rationale"),
        "raw": existing.get("four_class_raw"),
        "error": existing.get("four_class_error"),
        "diagnostics": existing.get("four_class_diagnostics"),
        "actual_call_count": int((existing.get("actual_call_counts") or {}).get("four_class", 0)),
    }
    return build_judge_record(
        response_id=str(existing["response_id"]), prompt=prompt, response=response,
        domain=str(existing["domain"]), four_class=four_class, binary=binary,
    )


def run_real_generation(
    *, run_dir: Path, config: Mapping[str, Any], limit: int | None = None,
    schedule_filename: str = "generation_schedule.jsonl",
    attempts_filename: str = "generation_attempts.jsonl",
    ledger_filename: str = "generation_ledger.jsonl",
    recovery_filename: str = "generation_recovery.json",
    release_filename: str = "behavior_release.json",
) -> dict[str, Any]:
    verify_run_source_snapshot(run_dir=run_dir, repo_root=Path(str(config["project_root"])).resolve())
    schedule = load_schedule(run_dir / schedule_filename)
    if limit is not None and (limit < 1 or limit > len(schedule)):
        raise BroadeningError("generation limit must be within the schedule")
    selected = schedule[:limit] if limit is not None else schedule
    frames = read_json(run_dir / "frames.json")
    prompt_map = _schedule_prompt_map(frames)
    tensors, mus = _direction_tensor_map(run_dir)
    attempts_path = run_dir / attempts_filename
    recovery = recover_jsonl_tail(attempts_path) if attempts_path.exists() else {
        "recovered": False, "complete_rows": 0, "tail_path": None,
    }
    atomic_write_json(run_dir / recovery_filename, recovery, overwrite=True)
    state = _existing_attempt_state(attempts_path)
    all_attempts = [*read_jsonl(attempts_path)] if attempts_path.exists() else []
    by_model: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in selected:
        by_model[row["identity"]["model_id"]].append(row)
    release_records: dict[str, Any] = {}
    model_order = [
        model_id for model_id in config["models"]
        if model_id != "judge" and model_id in by_model
    ]
    for model_id in model_order:
        rows = by_model.get(model_id, [])
        if not rows:
            continue
        layer_values = sorted({
            int(row["identity"]["layer"])
            for row in rows
            if row["identity"].get("layer") is not None
        })
        configured_layer = config["models"][model_id].get("layer")
        if not layer_values:
            layer_values = [configured_layer] if isinstance(configured_layer, int) else [None]
        if len(layer_values) == 1:
            row_groups = [(layer_values[0], rows)]
        else:
            grouped_rows: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
            for row in rows:
                layer = row["identity"].get("layer")
                target_layer = int(layer) if layer is not None else layer_values[0]
                grouped_rows[target_layer].append(row)
            row_groups = [(layer, grouped_rows[layer]) for layer in layer_values]
        for layer_override, grouped_rows in row_groups:
            runtime = None
            try:
                runtime = BehaviorRuntime.from_pretrained(
                    model_id=model_id,
                    details=config["models"][model_id],
                    layer_override=layer_override if isinstance(layer_override, int) else None,
                )
                runtime_identity = runtime.identity()
                record_loaded_identity(run_dir=run_dir, role="behavior", identity=runtime_identity)
                atomic_write_json(
                    run_dir / f"behavior_identity_{model_id}_layer{runtime.layer}.json",
                    runtime_identity,
                    overwrite=True,
                )
                # Queue at most one retry per response before handing outputs to Judge.
                pending_rows = list(grouped_rows)
                for row in pending_rows:
                    response_id = row["response_id"]
                    identity = row["identity"]
                    previous = sorted(state.get(response_id, []), key=lambda item: item["attempt_no"])
                    if previous and previous[-1]["status"] in {
                        "COMPLETED", "TERMINAL_TECHNICAL_FAILURE", "TERMINAL_FAILURE", "UNEXECUTED",
                    }:
                        continue
                    attempt_no = (previous[-1]["attempt_no"] + 1) if previous else 1
                    attempt_dose = previous[0]["dose_label"] if previous else row["dose_label"]
                    try:
                        prompt = prompt_map.get(identity["prompt_id"])
                        if not isinstance(prompt, str):
                            raise BroadeningError(f"prompt id is absent from local frame: {identity['prompt_id']}")
                        is_clean = row["dose_label"] == "clean"
                        vector = None if is_clean else tensors.get(f"{model_id}|{identity['direction_id']}")
                        if not is_clean and vector is None:
                            raise BroadeningError(f"direction asset is absent: {model_id}/{identity['direction_id']}")
                        mu = mus.get(f"{model_id}|{runtime.layer}", mus.get(model_id))
                        if not is_clean and mu is None:
                            raise BroadeningError(f"mu_content asset is absent: {model_id}/layer{runtime.layer}")
                        alpha = None if is_clean else float(identity["rho"]) * float(mu)
                        result = runtime.generate(
                            prompt=prompt,
                            condition=identity["condition"] if not is_clean else "clean",
                            vector=vector,
                            alpha=alpha,
                            max_new_tokens=int(config["runtime"]["decoder"]["max_new_tokens"]),
                            seed=int(config["runtime"]["decoder"]["seed"]),
                            capture_trace=False,
                        )
                        attempt = generation_attempt(
                            response_id=response_id,
                            attempt_no=attempt_no,
                            status="COMPLETED",
                            text=result["text"],
                            token_ids=result["token_ids"],
                            runtime={
                                "model_id": model_id,
                                "condition": result["condition"],
                                "latency_seconds": result["latency_seconds"],
                                "runtime_identity": runtime_identity,
                            },
                            diagnostics={
                                "runtime_counters": result["runtime_counters"],
                                "metrics": result["metrics"],
                                "actual_alpha": result["actual_alpha"],
                                "eos_first": result["eos_first"],
                                "fixture": False,
                            },
                            error=None,
                            identity=identity,
                            dose_label=attempt_dose,
                        )
                    except Exception as exc:
                        retryable = attempt_no == 1
                        attempt = generation_attempt(
                            response_id=response_id,
                            attempt_no=attempt_no,
                            status="TECHNICAL_FAILURE_RETRYABLE" if retryable else "TERMINAL_TECHNICAL_FAILURE",
                            text=None,
                            token_ids=None,
                            runtime={"model_id": model_id},
                            diagnostics={"fixture": False, "exception_type": type(exc).__name__},
                            error=f"{type(exc).__name__}: {exc}",
                            identity=identity,
                            dose_label=attempt_dose,
                        )
                        if retryable:
                            pending_rows.append(row)
                    append_generation_attempt(attempts_path, attempt)
                    all_attempts.append(attempt)
                    state.setdefault(response_id, []).append(attempt)
            except Exception as exc:
                release_records[f"{model_id}|layer{layer_override}"] = {
                    "status": "RUNTIME_NOT_RUN",
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            finally:
                if runtime is not None:
                    try:
                        release_records[f"{model_id}|layer{runtime.layer}"] = runtime.release()
                    except Exception as exc:
                        release_records[f"{model_id}|layer{layer_override}"] = {
                            "status": "RELEASE_FAILURE",
                            "reason": f"{type(exc).__name__}: {exc}",
                        }
    # The ledger includes every scheduled identity, including rows not selected by --limit.
    from .orchestration import write_generation_ledger

    accounting = write_generation_ledger(
        run_dir=run_dir,
        schedule=schedule,
        attempts=all_attempts,
        overwrite=True,
        filename=ledger_filename,
    )
    atomic_write_json(run_dir / release_filename, release_records, overwrite=True)
    return {"accounting": accounting, "release": release_records, "selected": len(selected)}


def _prompt_map(frames: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("jbb100", "jbb40", "benign30"):
        for row in frames.get(key, []):
            result[row["prompt_id"]] = row["text"]
    for row in frames.get("safe_pair_split", {}).get("records", []):
        result[f"{row['pair_id']}:harmful"] = row["harmful"]
        result[f"{row['pair_id']}:harmless"] = row["harmless"]
    for row in frames.get("e1", {}).get("records", []):
        if isinstance(row, Mapping) and isinstance(row.get("prompt_id"), str) and isinstance(row.get("text"), str):
            result[row["prompt_id"]] = row["text"]
    return result


def _run_screen_child(
    *, run_dir: Path, config: Mapping[str, Any], block: str, command: str,
) -> dict[str, Any]:
    """Run a GPU phase in its own process so model residency ends at exit."""
    model_python = Path(str(config["runtime"].get("model_python", ""))).expanduser()
    repo_root = Path(str(config["project_root"])).resolve()
    script = repo_root / "scripts" / "paper1_broadening.py"
    resolved_config = run_dir / "resolved_config.json"
    if not model_python.is_file() or not os.access(model_python, os.X_OK):
        raise BroadeningError(f"configured model Python is unavailable: {model_python}")
    if not script.is_file() or not resolved_config.is_file():
        raise BroadeningError("screen child process lacks its CLI or resolved run config")
    command_args = [
        str(model_python), str(script), command,
        "--config", str(resolved_config), "--run-dir", str(run_dir), "--block", block,
        "--screen",
    ]
    if command == "generate":
        command_args.append("--all")
    log_path = run_dir / f"screen_{command}_{block}.log"
    environment = os.environ.copy()
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        completed = subprocess.run(
            command_args,
            cwd=repo_root,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return {
        "command": command,
        "argv": command_args,
        "returncode": completed.returncode,
        "success": completed.returncode == 0,
        "log": str(log_path),
    }


def run_real_judge(
    *, run_dir: Path, config: Mapping[str, Any], binary: bool = False,
    schedule_filename: str = "generation_schedule.jsonl",
    attempts_filename: str = "generation_attempts.jsonl",
    judge_filename: str = "judge_records.jsonl",
    judge_status_filename: str = "judge_runtime_status.json",
    judge_release_filename: str = "judge_release.json",
    behavior_release_filename: str = "behavior_release.json",
) -> dict[str, Any]:
    verify_run_source_snapshot(run_dir=run_dir, repo_root=Path(str(config["project_root"])).resolve())
    schedule = list({row["response_id"]: row for row in load_schedule(run_dir / schedule_filename)}.values())
    attempts_path = run_dir / attempts_filename
    attempts = read_jsonl(attempts_path) if attempts_path.exists() else []
    canonical = canonical_generation_records(attempts)
    frames = read_json(run_dir / "frames.json")
    prompts = _prompt_map(frames)
    existing_path = run_dir / judge_filename
    existing_rows = read_jsonl(existing_path) if existing_path.exists() else []
    existing = {row["response_id"]: row for row in existing_rows}
    if len(existing) != len(existing_rows):
        raise BroadeningError("Judge records contain duplicate response_id values")
    scheduled_ids = {row["response_id"] for row in schedule}
    unknown_existing = set(existing) - scheduled_ids
    if unknown_existing:
        raise BroadeningError("Judge records reference unscheduled responses")
    for scheduled in schedule:
        if scheduled["response_id"] in existing:
            canonical_record = canonical.get(scheduled["response_id"])
            existing_response = ""
            if canonical_record and canonical_record.get("canonical_attempt") is not None:
                existing_response = str(canonical_record["canonical_attempt"]["text"])
            old = existing[scheduled["response_id"]]
            validation_response = "" if old.get("four_class_status") == "UNEXECUTED" and old.get("four_class_error") == "generation_missing" else existing_response
            _validate_existing_judge_record(old, scheduled, prompts, validation_response)
    lifecycle_path = run_dir / behavior_release_filename
    lifecycle = read_json(lifecycle_path) if lifecycle_path.exists() else {}
    model_layers: dict[str, set[int]] = defaultdict(set)
    for row in schedule:
        identity = row["identity"]
        if identity["layer"] is not None:
            model_layers[identity["model_id"]].add(int(identity["layer"]))
    expected_lifecycle_keys: set[str] = set()
    for row in schedule:
        identity = row["identity"]
        model_id, layer = identity["model_id"], identity["layer"]
        if layer is None:
            layers = model_layers.get(model_id) or {config["models"][model_id].get("layer")}
        else:
            layers = {layer}
        expected_lifecycle_keys.update(f"{model_id}|layer{value}" for value in layers)
    lifecycle_records = {
        key: lifecycle.get(key)
        for key in expected_lifecycle_keys
    } if isinstance(lifecycle, Mapping) else {}
    invalid_lifecycle = {
        key for key, value in lifecycle_records.items()
        if not isinstance(value, Mapping)
        or any(value.get(field) is not True for field in (
            "behavior_released", "behavior_hook_removed",
            "behavior_model_reference_cleared", "behavior_tokenizer_reference_cleared",
            "gc_collect_called",
        ))
        or value.get("models_concurrently_resident") is not False
    }
    if not isinstance(lifecycle, Mapping) or set(lifecycle) != expected_lifecycle_keys or invalid_lifecycle:
        failure = {
            "status": "RUNTIME_NOT_RUN",
            "reason": "judge requires complete release evidence for every scheduled behavior model/layer",
            "behavior_release_filename": behavior_release_filename,
            "expected_behavior_release_keys": sorted(expected_lifecycle_keys),
            "invalid_behavior_release_keys": sorted(invalid_lifecycle),
            "scheduled_judge_records": len(schedule),
            "existing_judge_records": len(existing),
            "unexecuted_judge_records": sum(row["response_id"] not in existing for row in schedule),
        }
        records = _write_unavailable_judge_records(
            path=existing_path, schedule=schedule, canonical=canonical, prompts=prompts,
            existing=existing, reason=failure["reason"], binary=binary,
        )
        atomic_write_json(run_dir / judge_status_filename, failure, overwrite=True)
        return {"judge_records": len(records), "binary": binary, "status": "RUNTIME_NOT_RUN", "failure": failure}
    try:
        judge = Qwen3JudgeRuntime.from_pretrained(
            details=config["models"]["judge"], lifecycle=lifecycle_records[next(iter(sorted(expected_lifecycle_keys)))],
        )
    except Exception as exc:
        failure = {
            "status": "RUNTIME_NOT_RUN",
            "reason": f"{type(exc).__name__}: {exc}",
            "scheduled_judge_records": len(schedule),
            "existing_judge_records": len(existing),
            "unexecuted_judge_records": sum(row["response_id"] not in existing for row in schedule),
        }
        records = _write_unavailable_judge_records(
            path=existing_path, schedule=schedule, canonical=canonical, prompts=prompts,
            existing=existing, reason=failure["reason"], binary=binary,
        )
        atomic_write_json(run_dir / judge_status_filename, failure, overwrite=True)
        return {"judge_records": len(records), "binary": binary, "status": "RUNTIME_NOT_RUN", "failure": failure}
    records: list[dict[str, Any]] = []
    records_by_id: dict[str, dict[str, Any]] = dict(existing)

    def persist(record: dict[str, Any]) -> None:
        response_id = record["response_id"]
        replacing = response_id in records_by_id
        records_by_id[response_id] = record
        if replacing:
            payload = b"".join(
                (canonical_json(records_by_id[row["response_id"]]) + "\n").encode("utf-8")
                for row in schedule if row["response_id"] in records_by_id
            )
            atomic_write_bytes(existing_path, payload, overwrite=True)
        else:
            append_jsonl(existing_path, record)
    try:
        judge_identity = judge.identity()
        record_loaded_identity(run_dir=run_dir, role="judge", identity=judge_identity)
        atomic_write_json(run_dir / "judge_identity.json", judge_identity, overwrite=True)
        for row in schedule:
            response_id = row["response_id"]
            canonical_record = canonical.get(response_id)
            canonical_attempt = (
                canonical_record.get("canonical_attempt")
                if canonical_record is not None
                else None
            )
            response = str(canonical_attempt["text"]) if canonical_attempt is not None else ""
            current = records_by_id.get(response_id)
            resume_unexecuted = (
                current is not None and canonical_attempt is not None
                and int(current.get("actual_call_counts", {}).get("four_class", 0)) == 0
                and current.get("four_class_status") in {"UNEXECUTED", "TECHNICAL_FAILURE"}
            )
            if current is not None and not resume_unexecuted:
                current = records_by_id[response_id]
                if not binary or current.get("binary_status") not in {"NOT_REQUESTED", "UNEXECUTED"}:
                    records.append(current)
                    continue
                prompt = prompts.get(row["identity"]["prompt_id"])
                if prompt is None:
                    raise BroadeningError(f"Judge prompt is absent: {row['identity']['prompt_id']}")
                binary_result = (
                    _binary_with_retry(judge=judge, prompt=prompt, response=response)
                    if canonical_attempt is not None
                    else _binary_failure(status="UNEXECUTED", error="generation_missing")
                )
                updated = _record_with_binary(
                    existing=current, prompt=prompt, response=response, binary=binary_result
                )
                persist(updated)
                records.append(updated)
                continue
            if not canonical_record or canonical_record.get("canonical_attempt") is None:
                domain = "benign" if row["identity"]["block"].startswith("core_benign_") else "harmful"
                record = build_judge_record(
                    response_id=response_id,
                    prompt=prompts.get(row["identity"]["prompt_id"], row["identity"]["prompt_id"]),
                    response="",
                    domain=domain,
                    four_class={"status": "UNEXECUTED", "error": "generation_missing", "actual_call_count": 0},
                    binary=(
                        _binary_failure(status="UNEXECUTED", error="generation_missing")
                        if binary else None
                    ),
                )
            else:
                attempt = canonical_record["canonical_attempt"]
                domain = "benign" if row["identity"]["block"].startswith("core_benign_") else "harmful"
                prompt = prompts.get(row["identity"]["prompt_id"])
                if prompt is None:
                    raise BroadeningError(f"Judge prompt is absent: {row['identity']['prompt_id']}")
                try:
                    result = judge.four_class(prompt=prompt, response=attempt["text"], domain=domain)
                except Exception as exc:
                    result = {
                        "status": "TECHNICAL_FAILURE", "label": None, "rationale": None,
                        "raw": None, "error": f"{type(exc).__name__}: {exc}",
                        "diagnostics": {"exception_type": type(exc).__name__},
                        "actual_call_count": 1,
                    }
                if result["status"] in {"PARSE_FAILURE", "TECHNICAL_FAILURE"}:
                    try:
                        retry = judge.four_class(prompt=prompt, response=attempt["text"], domain=domain)
                    except Exception as exc:
                        retry = {
                            "status": "TECHNICAL_FAILURE", "label": None, "rationale": None,
                            "raw": None, "error": f"{type(exc).__name__}: {exc}",
                            "diagnostics": {"exception_type": type(exc).__name__},
                            "actual_call_count": 1,
                        }
                    result = {
                        **retry,
                        "actual_call_count": int(result.get("actual_call_count", 1))
                        + int(retry.get("actual_call_count", 1)),
                    }
                binary_result = (
                    _binary_with_retry(judge=judge, prompt=prompt, response=attempt["text"])
                    if binary else None
                )
                record = build_judge_record(
                    response_id=response_id, prompt=prompt, response=attempt["text"], domain=domain,
                    four_class=result, binary=binary_result,
                )
            persist(record)
            records.append(record)
    finally:
        release = judge.release()
        atomic_write_json(run_dir / judge_release_filename, {"judge": release}, overwrite=True)
    atomic_write_json(run_dir / judge_status_filename, {
        "status": "COMPLETED", "judge_records": len(records_by_id), "binary": binary,
    }, overwrite=True)
    return {"judge_records": len(records_by_id), "binary": binary, "status": "COMPLETED"}


def _decision_status(decisions: Mapping[str, Any]) -> str:
    return "DOSE_DECIDED" if decisions and all(
        isinstance(value, Mapping) and value.get("status") == "DOSE_DECIDED"
        for value in decisions.values()
    ) else "SCREEN_GATE_BLOCKED"


def _direction_mu_metadata(directions: Mapping[str, Any], model_id: str, layer: int | None = None) -> tuple[float, int]:
    model = directions.get("models", {}).get(model_id, {})
    if layer is None:
        value = model
    else:
        value = (model.get("mu_content_by_layer") or {}).get(str(layer), {})
    if not isinstance(value, Mapping) or value.get("status", "COMPLETED") != "COMPLETED":
        raise BroadeningError(f"mu_content asset is unavailable for {model_id}/layer{layer}")
    mu = value.get("mu_content")
    tokens = value.get("mu_content_token_count")
    if isinstance(mu, bool) or not isinstance(mu, (int, float)) or float(mu) <= 0:
        raise BroadeningError(f"mu_content value is invalid for {model_id}/layer{layer}")
    if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 1:
        raise BroadeningError(f"mu_content token count is invalid for {model_id}/layer{layer}")
    return float(mu), tokens


def run_real_screen(*, run_dir: Path, config: Mapping[str, Any], block: str = "core") -> dict[str, Any]:
    """Run one bounded development screen and persist its independent dose decisions."""
    frames = read_json(run_dir / "frames.json")
    directions = read_json(run_dir / "directions.json") if (run_dir / "directions.json").is_file() else {}
    if block == "E1":
        e1 = frames.get("e1", {})
        if e1.get("status") != "READY_FOR_RUN":
            return {"status": "NOT_RUN", "reason": e1.get("reason", "E1_ASSET_OR_OVERLAP_GATE_PENDING")}
        if not (run_dir / "dose_decisions.json").is_file():
            return {"status": "NOT_RUN", "reason": "CORE_SCREEN_PENDING"}
        document = read_json(run_dir / "dose_decisions.json")
        core = document.get("core")
        if not isinstance(core, Mapping) or core.get("status") != "DOSE_DECIDED" or not isinstance(core.get("decisions"), Mapping):
            raise BroadeningError("E1 can reference core doses only after the core screen")
        document = dict(document)
        document["E1"] = {
            "status": "REFERENCES_CORE",
            "source_run_id": read_json(run_dir / "run_header.json")["run_id"],
            "decisions_source": "core",
        }
        atomic_write_json(run_dir / "dose_decisions.json", document, overwrite=True)
        return document["E1"]
    if block not in {"core", "E2", "E3"}:
        raise BroadeningError("screen block must be core, E1, E2, or E3")
    if block == "core" and any(
        directions.get("models", {}).get(model_id, {}).get("status") != "COMPLETED"
        for model_id in ("qwen25", "llama31")
    ):
        return {"status": "NOT_RUN", "reason": "CORE_DIRECTION_ASSETS_MISSING"}
    if block == "E2" and directions.get("models", {}).get("gemma2_9b_it", {}).get("status") != "COMPLETED":
        return {"status": "NOT_RUN", "reason": "GEMMA_ASSET_MISSING_OR_DIRECTION_BUILD_PENDING"}
    if block == "E3" and any(
        directions.get("models", {}).get(model_id, {}).get("status") != "COMPLETED"
        for model_id in ("qwen25", "llama31")
    ):
        return {"status": "NOT_RUN", "reason": "CORE_DIRECTION_ASSETS_MISSING_OR_LAYER_BUILD_PENDING"}
    schedule = build_screen_schedule_for_run(run_dir=run_dir, config=config, block=block)
    artifact_names = {
        "schedule": f"screen_generation_schedule_{block}.jsonl",
        "attempts": f"screen_generation_attempts_{block}.jsonl",
        "ledger": f"screen_generation_ledger_{block}.jsonl",
        "judges": f"screen_judge_records_{block}.jsonl",
        "judge_status": f"screen_judge_runtime_status_{block}.json",
        "judge_release": f"screen_judge_release_{block}.json",
        "behavior_release": f"screen_behavior_release_{block}.json",
        "recovery": f"screen_generation_recovery_{block}.json",
    }
    # The parent is a CPU scheduler. Each child exits before the next GPU
    # resident runtime is loaded, which makes the release boundary explicit.
    generation_process = _run_screen_child(run_dir=run_dir, config=config, block=block, command="generate")
    if not generation_process["success"]:
        # A failed generation screen cannot provide Judge inputs. Persist the
        # blocked state without starting a second GPU-resident child.
        judge_process = {
            "command": "judge",
            "returncode": None,
            "success": False,
            "status": "NOT_RUN",
            "reason": "GENERATION_PROCESS_FAILED",
        }
        process_record = {
            "generation": generation_process,
            "judge": judge_process,
            "serial": True,
            "judge_started_after_generation_exit": False,
        }
        atomic_write_json(run_dir / f"screen_processes_{block}.json", process_record, overwrite=True)
        atomic_write_json(
            run_dir / f"screen_judge_runtime_status_{block}.json",
            {
                "status": "RUNTIME_NOT_RUN",
                "reason": "GENERATION_PROCESS_FAILED",
                "generation_process": generation_process,
            },
            overwrite=True,
        )
        document = read_json(run_dir / "dose_decisions.json") if (run_dir / "dose_decisions.json").exists() else {
            "schema_version": "paper1-broadening-dose-decisions-v1",
            "fixture": False,
            "source_run_id": read_json(run_dir / "run_header.json")["run_id"],
        }
        document = dict(document)
        document.setdefault("schema_version", "paper1-broadening-dose-decisions-v1")
        document["fixture"] = False
        document.setdefault("extensions", {})
        screen_record = {
            "status": "SCREEN_GATE_BLOCKED",
            "schedule_filename": artifact_names["schedule"],
            "attempts_filename": artifact_names["attempts"],
            "ledger_filename": artifact_names["ledger"],
            "judge_filename": artifact_names["judges"],
            "generation": {"status": "PROCESS_FAILED", "process": generation_process},
            "judge": {"status": "RUNTIME_NOT_RUN", "process": judge_process},
        }
        if block == "core":
            document["decisions"] = {}
            document["core"] = {"status": "SCREEN_GATE_BLOCKED", "decisions": {}, "screen": screen_record}
            document["E1"] = {
                "status": "NOT_RUN",
                "reason": "CORE_SCREEN_BLOCKED",
                "source_run_id": document["source_run_id"],
            }
        else:
            document["extensions"][block] = {
                "status": "SCREEN_GATE_BLOCKED",
                "decisions": {},
                "screen": screen_record,
            }
        document["status"] = "SCREEN_GATE_BLOCKED"
        atomic_write_json(run_dir / "dose_decisions.json", document, overwrite=True)
        return document
    judge_process = _run_screen_child(run_dir=run_dir, config=config, block=block, command="judge")
    process_record = {
        "generation": generation_process,
        "judge": judge_process,
        "serial": True,
        "judge_started_after_generation_exit": True,
    }
    atomic_write_json(run_dir / f"screen_processes_{block}.json", process_record, overwrite=True)
    generation = {"status": "COMPLETED" if generation_process["success"] else "PROCESS_FAILED", "process": generation_process}
    judge = {"status": "COMPLETED" if judge_process["success"] else "PROCESS_FAILED", "process": judge_process}
    if not (run_dir / artifact_names["judges"]).is_file():
        raise BroadeningError(f"screen Judge child did not produce {artifact_names['judges']}")
    judges = read_jsonl(run_dir / artifact_names["judges"])
    grouped = _screen_rows_from_artifacts(schedule, judges, include_layer=block == "E3")
    directions = read_json(run_dir / "directions.json")
    decisions: dict[str, Any] = {}
    for key, candidates in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        model_id = str(key[0])
        layer = int(key[2]) if block == "E3" else None
        mu, token_count = _direction_mu_metadata(directions, model_id, layer)
        decision = choose_doses(
            candidates, mu_content=mu, expected_rhos=config["protocol"]["rho_grid"], expected_per_rho=60,
        )
        decision = {
            **decision,
            "model_id": model_id,
            "layer": layer,
            "family": str(key[1]),
            "mu_content": mu,
            "mu_content_token_count": token_count,
            "screen_run_id": read_json(run_dir / "run_header.json")["run_id"],
        }
        if block == "core":
            decisions.setdefault(model_id, {})[str(key[1])] = decision
        elif block == "E2":
            decisions[str(key[1])] = decision
        else:
            decisions.setdefault(model_id, {})[str(layer)] = decision
    document = read_json(run_dir / "dose_decisions.json") if (run_dir / "dose_decisions.json").exists() else {
        "schema_version": "paper1-broadening-dose-decisions-v1",
        "fixture": False,
        "source_run_id": read_json(run_dir / "run_header.json")["run_id"],
    }
    document = dict(document)
    document.setdefault("schema_version", "paper1-broadening-dose-decisions-v1")
    document["fixture"] = False
    document["source_run_id"] = read_json(run_dir / "run_header.json")["run_id"]
    document.setdefault("extensions", {})
    flat_decisions = decisions if block == "E2" else {
        f"{model_id}|{key}": value
        for model_id, groups in decisions.items()
        for key, value in groups.items()
    }
    run_status = _decision_status(flat_decisions)
    if not generation_process["success"] or not judge_process["success"]:
        run_status = "SCREEN_GATE_BLOCKED"
    screen_record = {
        "status": run_status,
        "schedule_filename": artifact_names["schedule"],
        "attempts_filename": artifact_names["attempts"],
        "ledger_filename": artifact_names["ledger"],
        "judge_filename": artifact_names["judges"],
        "generation": generation,
        "judge": judge,
    }
    if block == "core":
        document["decisions"] = decisions
        document["core"] = {"status": run_status, "decisions": decisions, "screen": screen_record}
        document["E1"] = {
            "status": "REFERENCES_CORE" if run_status == "DOSE_DECIDED" else "NOT_RUN",
            **({"reason": "CORE_SCREEN_BLOCKED"} if run_status != "DOSE_DECIDED" else {}),
            "source_run_id": document["source_run_id"],
            **({"decisions_source": "core"} if run_status == "DOSE_DECIDED" else {}),
        }
    else:
        document["extensions"][block] = {
            "status": run_status,
            "decisions": decisions,
            "screen": screen_record,
        }
    document["status"] = "COMPLETED" if run_status == "DOSE_DECIDED" else "SCREEN_GATE_BLOCKED"
    atomic_write_json(run_dir / "dose_decisions.json", document, overwrite=True)
    return document


def records_for_analysis_artifacts(*, run_dir: Path, block: str = "core") -> list[dict[str, Any]]:
    artifacts = block_artifacts(block)
    schedule = load_schedule(run_dir / artifacts["schedule"])
    judges = read_jsonl(run_dir / artifacts["judges"])
    judge_by_id: dict[str, dict[str, Any]] = {}
    for row in judges:
        response_id = row.get("response_id")
        if not isinstance(response_id, str) or response_id in judge_by_id:
            raise BroadeningError("Judge records contain an invalid or duplicate response_id")
        status = row.get("four_class_status")
        if status not in {"PARSED", "PARSE_FAILURE", "TECHNICAL_FAILURE", "UNEXECUTED"}:
            raise BroadeningError("Judge record has an invalid four-class status")
        if status == "PARSED" and not isinstance(row.get("four_class_label"), str):
            raise BroadeningError("parsed Judge record lacks a label")
        if status != "PARSED" and row.get("four_class_label") is not None:
            raise BroadeningError("failed Judge record carries a label")
        judge_by_id[response_id] = row
    scheduled_response_ids = {row["response_id"] for row in schedule}
    if set(judge_by_id) - scheduled_response_ids:
        raise BroadeningError("Judge records reference unscheduled responses")
    header = read_json(run_dir / "run_header.json")
    source_run_id = header.get("run_id")
    if not isinstance(source_run_id, str) or not source_run_id:
        raise BroadeningError("run header lacks run_id for analysis provenance")
    source_run_ids = {source_run_id}
    result: list[dict[str, Any]] = []
    for row in schedule:
        identity = row["identity"]
        if row["dose_label"] not in {"A", "S", "clean"}:
            continue
        if identity["condition"] not in {"decode_only", "public_v1", "clean"}:
            continue
        judge = judge_by_id.get(row["response_id"])
        domain = "benign" if str(identity["block"]).startswith("core_benign_") else "harmful"
        label = judge.get("four_class_label") if judge is not None else None
        result.append({
            "block": identity["block"],
            "model_id": identity["model_id"],
            "family": identity["family"],
            "layer": identity["layer"],
            "condition": identity["condition"],
            "dose_label": row["dose_label"],
            "category": row.get("metadata", {}).get("category", "UNKNOWN"),
            "prompt_id": identity["prompt_id"],
            "direction_id": identity["direction_id"],
            "label": label,
            "domain": domain,
            "response_id": row["response_id"],
            "schedule_id": row["schedule_id"],
            "source_run_id": source_run_id,
            "judge_status": judge.get("four_class_status") if judge is not None else "UNEXECUTED",
            "binary_status": judge.get("binary_status") if judge is not None else "UNEXECUTED",
        })
        metadata = row.get("metadata")
        if isinstance(metadata, Mapping):
            for field in ("source_run_id", "core_direction_source_run"):
                value = metadata.get(field)
                if isinstance(value, str) and value:
                    source_run_ids.add(value)
            if isinstance(metadata.get("core_dose_source"), str) and metadata["core_dose_source"]:
                source_run_ids.add(str(metadata["core_dose_source"]))
    for row in result:
        row["source_run_ids"] = sorted(source_run_ids)
    return result
