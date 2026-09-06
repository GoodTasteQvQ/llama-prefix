"""Thin orchestration layer for prepare, fixture execution, and resumable records."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .allocator import choose_doses
from .analysis import analyze_records, write_analysis_artifacts
from .archive import archive_run
from .common import (
    BroadeningError,
    append_jsonl,
    atomic_write_bytes,
    atomic_write_json,
    canonical_json,
    canonical_sha256,
    copy_source_snapshot,
    file_sha256,
    git_state,
    project_tempdir,
    read_json,
    read_jsonl,
    utc_now,
)
from .config import (
    CORE_BUDGET,
    DESIGN_ID,
    DESIGN_REVISION,
    EXTENSION_BUDGET,
    IMPLEMENTATION_REVISION,
    budget_plan,
    config_digest,
    default_config,
    load_config,
    resolve_path,
    validate_config,
)
from .directions import alpha_from_rho, rogue_directions
from .frames import build_frames
from .human import allocate_extension_human, analyze_human_labels, save_human_allocation, write_blinded_packets
from .judge import build_judge_record, labels_for_domain, strict_four_class_parse
from .ledger import (
    append_generation_attempt,
    build_alias_aware_schedule,
    clean_identity,
    generation_attempt,
    ledger_accounting,
    load_schedule,
    stable_id,
    steered_identity,
    write_schedule,
)


SOURCE_SNAPSHOT_PATHS = (
    "activation_guard/interventions.py",
    "activation_guard/metrics.py",
    "paper1_broadening/__init__.py",
    "paper1_broadening/allocator.py",
    "paper1_broadening/analysis.py",
    "paper1_broadening/archive.py",
    "paper1_broadening/common.py",
    "paper1_broadening/config.py",
    "paper1_broadening/directions.py",
    "paper1_broadening/extensions.py",
    "paper1_broadening/frames.py",
    "paper1_broadening/human.py",
    "paper1_broadening/judge.py",
    "paper1_broadening/ledger.py",
    "paper1_broadening/orchestration.py",
    "paper1_broadening/pipeline.py",
    "paper1_broadening/runtime.py",
    "paper1_broadening/smoke.py",
    "configs/paper1_broadening/mbd_nm_v21.json",
    "scripts/paper1_broadening.py",
    "scripts/run_paper1_broadening_single_gpu.sh",
    "scripts/judge_phase_outputs.py",
    "stage3_pipeline/real_judge.py",
)

DESIGN_SNAPSHOT_PATHS = (
    "writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md",
    "writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md",
    "writing/broadening design/review/paper1_minimal_broadening_design_review.md",
    "writing/broadening design/review/paper1_ccf_a_implementation_review.md",
    "writing/broadening design/implementation/paper1_server_codex_implementation_prompt.md",
    "writing/broadening design/implementation/paper1_server_codex_run_prompt_nohup.md",
    "writing/broadening design/implementation/paper1_server_codex_machine_review_and_run_prompt_nohup.md",
    "writing/broadening design/review/paper1_machine_review_protocol_review.md",
)


def new_run_id(prefix: str = "paper1") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:10]}"


def _python_runtime() -> dict[str, Any]:
    values: dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "tmpdir": os.environ.get("TMPDIR"),
        "temp": os.environ.get("TEMP"),
        "tmp": os.environ.get("TMP"),
        "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE"),
        "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE"),
        "hf_datasets_offline": os.environ.get("HF_DATASETS_OFFLINE"),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "logical_device": "cuda:0",
    }
    try:
        import torch

        values.update({
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "cuda_available": bool(torch.cuda.is_available()),
            "visible_gpu_count": int(torch.cuda.device_count()),
        })
    except Exception as exc:
        values["torch_error"] = type(exc).__name__
    try:
        values["transformers"] = __import__("transformers").__version__
    except Exception as exc:
        values["transformers_error"] = type(exc).__name__
    return values


def _gpu_snapshot() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,uuid,name,memory.total,memory.free", "--format=csv,noheader"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"status": "UNAVAILABLE", "error": type(exc).__name__, "rows": []}
    rows = []
    for line in result.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if fields:
            rows.append(fields)
    return {"status": "READ", "rows": rows}


def _source_snapshot(repo_root: Path, run_dir: Path) -> dict[str, Any]:
    source_dir = run_dir / "source_snapshot"
    design_dir = run_dir / "design_snapshot"
    copied_sources = copy_source_snapshot(
        repo_root=repo_root, destination=source_dir, relative_paths=SOURCE_SNAPSHOT_PATHS
    )
    copied_design = copy_source_snapshot(
        repo_root=repo_root, destination=design_dir, relative_paths=DESIGN_SNAPSHOT_PATHS
    )
    return {
        "source_snapshot_dir": str(source_dir),
        "source_files": copied_sources,
        "design_snapshot_dir": str(design_dir),
        "design_files": copied_design,
    }


def create_run(
    *, config: Mapping[str, Any], repo_root: Path, run_id: str | None = None,
    block: str = "prepare", run_mode: str = "pilot", output_dir: Path | None = None,
    fixture: bool = False,
) -> tuple[Path, dict[str, Any]]:
    config = validate_config(config)
    run_id = run_id or new_run_id("fixture" if fixture else "paper1")
    if output_dir is None:
        base = project_tempdir(repo_root) / "paper1_broadening_fixtures" if fixture else Path(config["output_root"])
        output_dir = base / run_id
    run_dir = Path(output_dir).resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise BroadeningError(f"run directory already exists and is nonempty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved = json.loads(canonical_json(dict(config)))
    resolved.update({"run_id": run_id, "block": block, "run_mode": run_mode, "fixture": fixture})
    atomic_write_json(run_dir / "resolved_config.json", resolved, overwrite=False)
    snapshots = _source_snapshot(repo_root, run_dir)
    state = git_state(repo_root)
    header = {
        "schema_version": "paper1-broadening-run-header-v1",
        "run_id": run_id,
        "design_id": DESIGN_ID,
        "design_revision": DESIGN_REVISION,
        "implementation_revision": IMPLEMENTATION_REVISION,
        "block": block,
        "model_id": "MULTI",
        "layers": {model_id: details.get("layer") for model_id, details in config["models"].items()},
        "started_at": utc_now(),
        "code_commit": state["code_commit"],
        "dirty": state["dirty"],
        "design_snapshot_path": snapshots["design_snapshot_dir"],
        "source_snapshot_path": snapshots["source_snapshot_dir"],
        "config_snapshot_path": str(run_dir / "resolved_config.json"),
        "model_revision": {},
        "tokenizer_revision": {},
        "judge_revision": "UNKNOWN",
        "loaded_identities": {"behavior": {}, "judge": None},
        "template": {"native": True, "system_prompt": "empty", "add_generation_prompt": True},
        "decoder": config["runtime"]["decoder"],
        "runtime_resolved": _python_runtime(),
        "gpu_snapshot": _gpu_snapshot(),
        "config_sha256": config_digest(config),
        "fixture": fixture,
        **snapshots,
    }
    atomic_write_json(run_dir / "run_header.json", header, overwrite=False)
    return run_dir, header


def record_loaded_identity(*, run_dir: Path, role: str, identity: Mapping[str, Any]) -> dict[str, Any]:
    """Persist identities at model load time so archive never infers them later."""
    if role not in {"behavior", "judge"}:
        raise BroadeningError("runtime identity role is invalid")
    header = read_json(run_dir / "run_header.json")
    loaded = header.get("loaded_identities")
    if not isinstance(loaded, dict):
        loaded = {"behavior": {}, "judge": None}
    if role == "behavior":
        model_id = identity.get("model_id")
        if not isinstance(model_id, str) or not model_id:
            raise BroadeningError("behavior runtime identity lacks model_id")
        layer = identity.get("layer")
        if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0:
            raise BroadeningError("behavior runtime identity lacks a valid layer")
        behavior = loaded.get("behavior")
        if not isinstance(behavior, dict):
            behavior = {}
        behavior[f"{model_id}|layer{layer}"] = dict(identity)
        loaded["behavior"] = behavior
        revisions = header.get("model_revision")
        if not isinstance(revisions, dict):
            revisions = {}
        revisions[model_id] = identity.get("model_revision", "UNKNOWN")
        header["model_revision"] = revisions
        tokenizer_revisions = header.get("tokenizer_revision")
        if not isinstance(tokenizer_revisions, dict):
            tokenizer_revisions = {}
        tokenizer_revisions[model_id] = identity.get("tokenizer_revision", "UNKNOWN")
        header["tokenizer_revision"] = tokenizer_revisions
    else:
        loaded["judge"] = dict(identity)
        header["judge_revision"] = identity.get("model_revision", "UNKNOWN")
        header["judge_tokenizer_revision"] = identity.get("tokenizer_revision", "UNKNOWN")
    header["loaded_identities"] = loaded
    atomic_write_json(run_dir / "run_header.json", header, overwrite=True)
    return header


def verify_run_source_snapshot(*, run_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Fail closed if a resumable runtime would execute code different from its snapshot."""
    header = read_json(run_dir / "run_header.json")
    snapshot_dir = Path(str(header.get("source_snapshot_path", "")))
    source_files = header.get("source_files")
    if not snapshot_dir.is_dir() or not isinstance(source_files, list) or not source_files:
        raise BroadeningError("run lacks a complete source snapshot for resume")
    mismatches: list[str] = []
    for relative in source_files:
        if not isinstance(relative, str):
            raise BroadeningError("run source snapshot has an invalid relative path")
        current = (repo_root / relative).resolve()
        snapshot = (snapshot_dir / relative).resolve()
        if not current.is_file() or not snapshot.is_file() or file_sha256(current) != file_sha256(snapshot):
            mismatches.append(relative)
    if mismatches:
        raise BroadeningError(
            "run source snapshot differs from the current worktree; resume requires the recorded source: "
            + ", ".join(mismatches)
        )
    return {"verified": True, "source_files": len(source_files)}


def _frame_lookup(frames: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for key in ("jbb100", "jbb40", "benign30"):
        for row in frames.get(key, []):
            lookup[row["prompt_id"]] = dict(row)
    for row in frames.get("safe_pair_split", {}).get("records", []):
        lookup[f"{row['pair_id']}:harmful"] = {
            "prompt_id": f"{row['pair_id']}:harmful",
            "text": row["harmful"],
            "category": "development_harmful",
            "source_index": row["source_index"],
            "role": "development",
        }
        lookup[f"{row['pair_id']}:harmless"] = {
            "prompt_id": f"{row['pair_id']}:harmless",
            "text": row["harmless"],
            "category": "development_harmless",
            "source_index": row["source_index"],
            "role": "construction_development",
        }
    return lookup


def _direction_ids(counts: Mapping[str, int]) -> dict[str, list[str]]:
    return {
        "rogue": [f"rogue:{index}" for index in range(int(counts["rogue"]))],
        "contrastive": [f"contrastive:fold:{index}" for index in range(int(counts["contrastive"]))],
    }


def build_core_schedule(
    *, run_id: str, frames: Mapping[str, Any], config: Mapping[str, Any],
    dose_rhos: Mapping[str, Mapping[str, Mapping[str, float]]],
    include_development: bool = False,
) -> list[dict[str, Any]]:
    model_ids = ("qwen25", "llama31")
    direction_ids = _direction_ids(config["protocol"]["directions"])
    rows: list[tuple[Mapping[str, Any], str] | tuple[Mapping[str, Any], str, Mapping[str, Any]]] = []
    development = frames.get("safe_pair_split", {}).get("development", [])
    screen_prompts = [f"{pair_id}:harmful" for pair_id in development[:20]]
    if include_development:
        if len(screen_prompts) != 20:
            raise BroadeningError("core development schedule requires 20 development harmful prompts")
    for model_id in model_ids:
        layer = int(config["models"][model_id]["layer"])
        if include_development:
            for family in ("rogue", "contrastive"):
                for rho in config["protocol"]["rho_grid"]:
                    for prompt_id in screen_prompts:
                        for direction_id in direction_ids[family][:3]:
                            rows.append((
                                steered_identity(
                                    run_id=run_id, block="core_development", model_id=model_id, layer=layer,
                                    family=family, condition="decode_only", rho=float(rho),
                                    direction_id=direction_id, prompt_id=prompt_id,
                                ),
                                "screen",
                                {"category": "development_harmful", "frame": "development20"},
                            ))
        for condition in ("public_v1", "decode_only"):
            for dose_label in ("A", "S"):
                for prompt in frames["jbb100"]:
                    for family in ("rogue", "contrastive"):
                        for direction_id in direction_ids[family]:
                            rows.append((
                                steered_identity(
                                    run_id=run_id, block="core_harmful_steered", model_id=model_id,
                                    layer=layer, family=family, condition=condition,
                                    rho=float(dose_rhos[model_id][family][dose_label]),
                                    direction_id=direction_id, prompt_id=prompt["prompt_id"],
                                ),
                                dose_label,
                                {"category": prompt["category"], "frame": prompt["frame"]},
                            ))
        for prompt in frames["jbb100"]:
            rows.append((
                clean_identity(run_id=run_id, block="core_harmful_clean", model_id=model_id, prompt_id=prompt["prompt_id"]),
                "clean",
                {"category": prompt["category"], "frame": prompt["frame"]},
            ))
        for prompt in frames["benign30"]:
            for family in ("rogue", "contrastive"):
                for direction_id in direction_ids[family]:
                    rows.append((
                        steered_identity(
                            run_id=run_id, block="core_benign_steered", model_id=model_id,
                            layer=layer, family=family, condition="decode_only",
                            rho=float(dose_rhos[model_id][family]["S"]),
                            direction_id=direction_id, prompt_id=prompt["prompt_id"],
                        ),
                        "S",
                        {"category": prompt["category"], "frame": prompt["frame"]},
                    ))
            rows.append((
                clean_identity(run_id=run_id, block="core_benign_clean", model_id=model_id, prompt_id=prompt["prompt_id"]),
                "clean",
                {"category": prompt["category"], "frame": prompt["frame"]},
            ))
    schedule = build_alias_aware_schedule(rows)
    expected = sum(CORE_BUDGET.values()) - (0 if include_development else CORE_BUDGET["development"])
    if len(schedule) != expected:
        raise BroadeningError(f"core schedule count {len(schedule)} differs from {expected}")
    return schedule


def plan_document(*, frames: Mapping[str, Any], core_schedule_count: int) -> dict[str, Any]:
    return {
        "schema_version": "paper1-broadening-plan-v1",
        "scientific_budget": budget_plan(),
        "core_schedule_count": core_schedule_count,
        "extension_schedule_count": 0,
        "extension_status": {
            "E1": "NOT_RUN_ASSET_OR_OVERLAP_GATE_PENDING",
            "E2": "NOT_RUN_GEMMA_ASSET_MISSING",
            "E3": "NOT_RUN_UNTIL_CORE_LAYER_GATE",
        },
        "frame_counts": {
            "jbb100": len(frames.get("jbb100", [])),
            "jbb40": len(frames.get("jbb40", [])),
            "benign30": len(frames.get("benign30", [])),
            "safe_pair_source": frames.get("safe_pair_split", {}).get("source_count"),
            "safe_pair_actual_k": frames.get("safe_pair_split", {}).get("actual_k"),
        },
        "budget_notes": [
            "A=S aliases are deduplicated at physical response accounting time.",
            "Judge calls, retries, smoke, and activation forwards are separate ledgers.",
            "E1/E2/E3 are not scheduled for runtime without their gates.",
        ],
    }


def core_identity_plan(*, frames: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "paper1-broadening-identity-plan-v1",
        "models": ["qwen25", "llama31"],
        "layers": {
            model_id: config["models"][model_id]["layer"]
            for model_id in ("qwen25", "llama31")
        },
        "families": {"rogue": 8, "contrastive": 5},
        "conditions": ["public_v1", "decode_only"],
        "doses": ["A", "S"],
        "evaluation_frames": {
            "harmful": len(frames.get("jbb100", [])),
            "benign": len(frames.get("benign30", [])),
        },
        "clean_policy": "one_per_model_prompt",
        "counts": dict(CORE_BUDGET),
        "logical_generation_total": sum(CORE_BUDGET.values()),
        "dose_resolution_required_before_evaluation": True,
    }


def prepare_run(
    *, config: Mapping[str, Any], repo_root: Path, run_id: str | None = None,
    output_dir: Path | None = None, fixture: bool = False,
) -> tuple[Path, dict[str, Any]]:
    run_dir, header = create_run(
        config=config, repo_root=repo_root, run_id=run_id, block="prepare", run_mode="pilot",
        output_dir=output_dir, fixture=fixture,
    )
    frames = build_frames(config)
    atomic_write_json(run_dir / "frames.json", frames, overwrite=False)
    overlap = frames.get("overlap_review_queue", [])
    atomic_write_json(run_dir / "overlap_review_queue.json", {"records": overlap, "count": len(overlap)}, overwrite=False)
    identity_plan = core_identity_plan(frames=frames, config=config)
    atomic_write_json(run_dir / "identity_plan.json", identity_plan, overwrite=False)
    plan = plan_document(frames=frames, core_schedule_count=sum(CORE_BUDGET.values()))
    atomic_write_json(run_dir / "plan.json", plan, overwrite=False)
    return run_dir, {"header": header, "plan": plan, "schedule_count": sum(CORE_BUDGET.values())}


def write_generation_ledger(
    *, run_dir: Path, schedule: Sequence[Mapping[str, Any]], attempts: Sequence[Mapping[str, Any]],
    overwrite: bool = False, filename: str = "generation_ledger.jsonl",
) -> dict[str, Any]:
    by_response: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    scheduled_doses: dict[str, set[str]] = defaultdict(set)
    for scheduled in schedule:
        scheduled_doses[scheduled["response_id"]].add(scheduled["dose_label"])
    for attempt in attempts:
        by_response[str(attempt["response_id"])].append(attempt)
    rows: list[dict[str, Any]] = []
    for scheduled in schedule:
        response_id = scheduled["response_id"]
        response_attempts = sorted(by_response.get(response_id, []), key=lambda row: row["attempt_no"])
        for attempt in response_attempts:
            if attempt.get("identity") is not None and attempt.get("identity") != scheduled["identity"]:
                raise BroadeningError("generation attempt identity differs from its scheduled identity")
            if attempt.get("dose_label") is not None and attempt["dose_label"] not in scheduled_doses[response_id]:
                raise BroadeningError("generation attempt dose differs from its scheduled identity")
        canonical = next((row for row in response_attempts if row["status"] == "COMPLETED"), None)
        rows.append({
            "schema_version": "paper1-broadening-generation-ledger-v1",
            "schedule_id": scheduled["schedule_id"],
            "response_id": response_id,
            "identity": scheduled["identity"],
            "dose_label": scheduled["dose_label"],
            "attempt_count": len(response_attempts),
            "canonical_attempt_no": canonical["attempt_no"] if canonical else None,
            "terminal_status": response_attempts[-1]["status"] if response_attempts else "UNEXECUTED",
            "canonical_text": canonical["text"] if canonical else None,
            "fixture": bool(any(attempt.get("diagnostics", {}).get("fixture") for attempt in response_attempts)),
        })
    path = run_dir / filename
    if path.exists() and not overwrite:
        raise BroadeningError("generation ledger already exists; refusing overwrite")
    payload = b"".join((canonical_json(row) + "\n").encode("utf-8") for row in rows)
    atomic_write_bytes(path, payload, overwrite=overwrite)
    return ledger_accounting(schedule, attempts)


def fixture_generation(
    *, run_dir: Path, schedule: Sequence[Mapping[str, Any]], label_for: Callable[[Mapping[str, Any]], str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    attempts_path = run_dir / "generation_attempts.jsonl"
    attempts: list[dict[str, Any]] = []
    for scheduled in schedule:
        response_id = scheduled["response_id"]
        payload = label_for(scheduled)
        if not isinstance(payload, str) or payload not in labels_for_domain("harmful"):
            raise BroadeningError("fixture label generator returned an invalid harmful label")
        text = f"[FIXTURE_LABEL={payload}] response for {scheduled['identity']['prompt_id']}"
        attempt = generation_attempt(
            response_id=response_id, attempt_no=1, status="COMPLETED", text=text,
            token_ids=[1, 2, 3], runtime={"condition": scheduled["identity"]["condition"]},
            diagnostics={"fixture": True, "status": "NON_EVIDENCE"}, error=None,
            identity=scheduled["identity"], dose_label=scheduled["dose_label"],
        )
        append_generation_attempt(attempts_path, attempt)
        attempts.append(attempt)
    accounting = write_generation_ledger(run_dir=run_dir, schedule=schedule, attempts=attempts)
    return attempts, accounting


def fixture_judge(*, run_dir: Path, schedule: Sequence[Mapping[str, Any]], attempts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    attempts_by_response = {attempt["response_id"]: attempt for attempt in attempts if attempt["status"] == "COMPLETED"}
    records: list[dict[str, Any]] = []
    path = run_dir / "judge_records.jsonl"
    for scheduled in schedule:
        attempt = attempts_by_response.get(scheduled["response_id"])
        if attempt is None:
            record = build_judge_record(
                response_id=scheduled["response_id"],
                prompt=scheduled["identity"]["prompt_id"],
                response="",
                domain="harmful",
                four_class={
                    "status": "UNEXECUTED", "error": "generation_unexecuted",
                    "diagnostics": {"fixture": True, "status": "NON_EVIDENCE"},
                    "actual_call_count": 0,
                },
            )
        else:
            text = attempt["text"]
            marker = text.split("[FIXTURE_LABEL=", 1)[1].split("]", 1)[0]
            final = json.dumps({"label": marker, "rationale": "fixture"}, separators=(",", ":"))
            label, rationale = strict_four_class_parse(final, "harmful")
            record = build_judge_record(
                response_id=scheduled["response_id"],
                prompt=scheduled["identity"]["prompt_id"],
                response=text,
                domain="harmful",
                four_class={
                    "status": "PARSED", "label": label, "rationale": rationale, "raw": final,
                    "error": None, "diagnostics": {"fixture": True, "status": "NON_EVIDENCE"}, "actual_call_count": 1,
                },
            )
        append_jsonl(path, record)
        records.append(record)
    return records


def records_for_analysis(
    *, schedule: Sequence[Mapping[str, Any]], judge_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    labels = {row["response_id"]: row.get("four_class_label") for row in judge_records}
    result: list[dict[str, Any]] = []
    for row in schedule:
        identity = row["identity"]
        if identity["block"] != "fixture_eval" or identity["condition"] != "decode_only" or row["dose_label"] not in {"A", "S"}:
            continue
        result.append({
            "block": "fixture_eval",
            "model_id": identity["model_id"],
            "family": identity["family"],
            "layer": identity["layer"],
            "condition": identity["condition"],
            "dose_label": row["dose_label"],
            "category": identity.get("category", "fixture-category"),
            "prompt_id": identity["prompt_id"],
            "direction_id": identity["direction_id"],
            "label": labels.get(row["response_id"]),
        })
    return result


def fixture_e2e(*, repo_root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Run a tiny non-evidence workflow using the same artifact contracts."""
    config = default_config(repo_root)
    run_dir, header = create_run(
        config=config, repo_root=repo_root, run_id=new_run_id("fixture-e2e"), block="fixture-e2e",
        run_mode="smoke", output_dir=output_dir, fixture=True,
    )
    fixture_frames = {
        "schema_version": "paper1-broadening-frames-v1-fixture",
        "jbb100": [], "jbb40": [], "benign30": [],
        "safe_pair_split": {"source_count": 4, "actual_k": 0, "records": [], "development": []},
        "overlap_review_queue": [], "e1": {"status": "NOT_RUN", "reason": "FIXTURE"},
        "fixture": True,
    }
    atomic_write_json(run_dir / "frames.json", fixture_frames, overwrite=False)
    atomic_write_json(run_dir / "fixture_status.json", {"fixture": True, "status": "NON_EVIDENCE"}, overwrite=False)
    # A small screen still exercises fixed-grid ranking and A/S status handling.
    candidate_rows: list[dict[str, Any]] = []
    for rho in config["protocol"]["rho_grid"]:
        for index in range(3):
            candidate_rows.append({
                "rho": rho,
                "label": "unsafe" if rho <= 0.75 and index < 2 else ("broken" if rho >= 1.25 else "safe"),
            })
    dose = choose_doses(candidate_rows, mu_content=2.0, expected_rhos=config["protocol"]["rho_grid"], expected_per_rho=3)
    atomic_write_json(run_dir / "dose_decisions.json", {"fixture": True, **dose}, overwrite=False)
    directions = rogue_directions(hidden_size=4, model_index=1, count=2)
    torch_path = run_dir / "fixture_directions.pt"
    import torch

    torch.save(torch.stack(directions), torch_path)
    atomic_write_json(run_dir / "directions.json", {
        "schema_version": "paper1-broadening-directions-v1",
        "fixture": True,
        "status": "NON_EVIDENCE",
        "vectors": [{"direction_id": f"rogue:{i}", "norm": float(vector.norm().item()), "tensor_path": str(torch_path)} for i, vector in enumerate(directions)],
    }, overwrite=False)
    schedule_requests: list[tuple[dict[str, Any], str]] = []
    for category in ("cat-a", "cat-b"):
        for prompt_index in range(2):
            prompt_id = f"fixture:{category}:{prompt_index}"
            for direction_id in ("rogue:0", "rogue:1"):
                for dose_label in ("A", "S"):
                    identity = {
                        "run_id": header["run_id"], "block": "fixture_eval", "model_id": "fixture-model",
                        "layer": 1, "family": "rogue", "condition": "decode_only", "rho": 0.5 if dose_label == "A" else 1.5,
                        "direction_id": direction_id, "prompt_id": prompt_id,
                    }
                    schedule_requests.append((identity, dose_label, {"category": category, "frame": "fixture"}))
    schedule = build_alias_aware_schedule(schedule_requests)
    write_schedule(run_dir / "generation_schedule.jsonl", schedule)
    def label_for(row: Mapping[str, Any]) -> str:
        return "unsafe" if row["dose_label"] == "A" else "broken"
    attempts, accounting = fixture_generation(run_dir=run_dir, schedule=schedule, label_for=label_for)
    judges = fixture_judge(run_dir=run_dir, schedule=schedule, attempts=attempts)
    records = records_for_analysis(schedule=schedule, judge_records=judges)
    analysis = analyze_records(records, config["protocol"]["bootstrap"])
    analysis["fixture"] = True
    analysis["status"] = "NON_EVIDENCE"
    artifacts = write_analysis_artifacts(analysis, run_dir)
    human_rows = []
    for index in range(40):
        human_rows.append({
            "response_id": f"fixture-human-{index}", "cell": f"cell-{index % 4}",
            "request": f"FIXTURE request {index}", "response": f"FIXTURE response {index}",
            "auto_label": "unsafe" if index % 2 == 0 else "broken",
            "model_id": "fixture-model", "family": "rogue", "layer": 1,
            "condition": "decode_only", "dose_label": "A",
        })
    allocation = allocate_extension_human(human_rows, block="E1")
    allocation["fixture"] = True
    save_human_allocation(allocation, run_dir / "human_allocation.json")
    rubric = "FIXTURE rubric; NON_EVIDENCE"
    packet_paths = write_blinded_packets(allocation, run_dir / "human_packets", rubric)
    labels = [
        {"blind_id": row["blind_id"], "reviewer": "fixture-adjudicator", "label": row["private_key"]["auto_label"], "adjudicated_label": row["private_key"]["auto_label"]}
        for row in allocation["records"]
    ]
    with (run_dir / "human_labels.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for label in labels:
            handle.write(canonical_json(label) + "\n")
    human_analysis = analyze_human_labels(allocation, labels)
    human_analysis["fixture"] = True
    human_analysis["status"] = "NON_EVIDENCE"
    atomic_write_json(run_dir / "human_analysis.json", human_analysis, overwrite=False)
    manifest = archive_run(
        run_dir=run_dir, repo_root=repo_root, run_header=header,
        source_ids={"fixture": True, "status": "NON_EVIDENCE", "jbb": "not_used"},
        require_human=True,
    )
    return {
        "run_dir": str(run_dir),
        "fixture": True,
        "status": "NON_EVIDENCE",
        "schedule_count": len(schedule),
        "accounting": accounting,
        "analysis": artifacts,
        "human_packets": packet_paths,
        "archive": str(run_dir / "provenance_manifest.json"),
        "archive_revision": manifest["archive_revision"],
    }
