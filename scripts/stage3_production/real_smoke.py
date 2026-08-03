#!/usr/bin/env python3
"""Validate or run the development-only Stage 3 real-backend smoke chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import (  # noqa: E402
    ACTIVE_PROFILE,
    DECODE_CONFIG,
    JUDGE_CONFIG,
    GenerationProducer,
    IdentityError,
    LogicalIdentityRegistry,
    PipelineError,
    canonical_sha256,
    file_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
    utc_now,
)
from stage3_pipeline.dose import build_test_dose_binding, validate_dose_binding  # noqa: E402
from stage3_pipeline.execution import (  # noqa: E402
    reconcile_execution,
    response_terminal_disposition,
)
from stage3_pipeline.offline_assets import load_p1_harmful_active_entry  # noqa: E402
from stage3_pipeline.real_backend import (  # noqa: E402
    RealBehaviorBackend,
    bind_dose_post_dtype,
    inspect_local_model_assets,
    load_candidate_vector,
)
from stage3_pipeline.real_judge import (  # noqa: E402
    RealJudgeBackend,
    judge_rubric_sha256,
    qwen3_closing_think_token_id,
)
from stage3_pipeline.records import (  # noqa: E402
    build_block_response_record,
    validate_generation_record,
    validate_judge_record,
)
from stage3_pipeline.run_manifest import (  # noqa: E402
    build_run_manifest,
    collect_runtime_versions,
    validate_run_manifest,
    write_run_manifest,
)


DEFAULT_CONFIG = ROOT / "configs/stage3/real_smoke_development_v1.json"
OUTPUT_ROOT = (ROOT / ".codex-temp/stage3_real_smoke_runs").resolve()
BEHAVIOR_MODEL_PATH = Path("/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct").resolve()
JUDGE_MODEL_PATH = Path("/data/goodtaste_workspace/models/Qwen3-8B").resolve()
CANDIDATE_VECTOR_PATH = (
    ROOT / "results/stage1_phase_aware/random_vector_pools/qwen25_stage1_vectors.pt"
).resolve()
ACTIVE_INPUT_ENTRY = "configs/stage3/p1_harmful_do_not_answer_v1.json"
SELECTED_INPUT_PATH = "data/stage3/p1_harmful_do_not_answer_v1/selected_p1_harmful_100.json"
CONFIG_FIELDS = {
    "schema_version", "run_mode", "paper_result_eligible", "fake_backend",
    "asset_status", "vector_status", "formal_experiment_run", "identity_level",
    "device", "output_root", "logical_identities", "input", "behavior", "judge",
    "vector", "development_dose", "generation_config", "judge_config",
}


def _strict_json(path: Path) -> dict[str, Any]:
    def exact_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PipelineError(f"duplicate JSON key in real smoke config: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=exact_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                PipelineError(f"non-standard JSON constant in real smoke config: {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PipelineError(f"unable to read strict real smoke config: {path}") from exc
    if not isinstance(value, dict):
        raise PipelineError("real smoke config must be an object")
    return value


def _exact_fields(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PipelineError(f"{label} fields differ")
    return dict(value)


def _validate_static_config(config: Mapping[str, Any], *, device: str) -> dict[str, Any]:
    actual = _exact_fields(config, CONFIG_FIELDS, "real smoke config")
    required_flags = {
        "schema_version": "paper1-stage3-real-smoke-development-v1",
        "run_mode": "smoke",
        "paper_result_eligible": False,
        "fake_backend": False,
        "asset_status": "development_only",
        "vector_status": "candidate_only",
        "formal_experiment_run": False,
        "identity_level": "development_candidate",
    }
    for field, expected in required_flags.items():
        if actual[field] != expected:
            raise PipelineError(f"real smoke config {field} must equal {expected!r}")
    if not isinstance(device, str) or device != "cuda:0":
        raise PipelineError("development real smoke currently requires explicit device cuda:0")
    if Path(actual["output_root"]).resolve() != OUTPUT_ROOT:
        raise PipelineError(f"real smoke output_root must resolve to {OUTPUT_ROOT}")
    identities = actual["logical_identities"]
    if (
        not isinstance(identities, list)
        or not 1 <= len(identities) <= 2
        or len(identities) != len(set(identities))
        or any(identity not in {"clean", "steered"} for identity in identities)
    ):
        raise PipelineError("real smoke requires one or two unique clean/steered identities")
    input_config = _exact_fields(
        actual["input"], {"active_entry", "selected_path", "source_ids"}, "input config"
    )
    if (
        input_config["active_entry"] != ACTIVE_INPUT_ENTRY
        or input_config["selected_path"] != SELECTED_INPUT_PATH
    ):
        raise PipelineError("real smoke input must use the authorized active P1 harmful package")
    source_ids = input_config["source_ids"]
    if (
        not isinstance(source_ids, list)
        or not 1 <= len(source_ids) <= 2
        or len(source_ids) != len(set(source_ids))
        or any(isinstance(value, bool) or not isinstance(value, int) for value in source_ids)
    ):
        raise PipelineError("real smoke input requires one or two unique integer source IDs")
    if len(source_ids) * len(identities) > 2:
        raise PipelineError("real smoke defaults may schedule at most two logical IDs")
    behavior = _exact_fields(
        actual["behavior"],
        {
            "model_path", "tokenizer_path", "dtype", "trust_remote_code",
            "trust_remote_code_reason", "layer", "hook_site", "system_prompt",
        },
        "behavior config",
    )
    if behavior["hook_site"] != "resid_pre":
        raise PipelineError(
            "development behavior hook_site must match activation_guard's layer-input resid_pre hook"
        )
    if (
        Path(behavior["model_path"]).resolve() != BEHAVIOR_MODEL_PATH
        or Path(behavior["tokenizer_path"]).resolve() != BEHAVIOR_MODEL_PATH
    ):
        raise PipelineError("real smoke behavior assets differ from the authorized local model")
    judge = _exact_fields(
        actual["judge"],
        {
            "model_path", "tokenizer_path", "dtype", "trust_remote_code",
            "trust_remote_code_reason", "thinking_enabled",
        },
        "judge config",
    )
    if (
        Path(judge["model_path"]).resolve() != JUDGE_MODEL_PATH
        or Path(judge["tokenizer_path"]).resolve() != JUDGE_MODEL_PATH
    ):
        raise PipelineError("real smoke judge assets differ from the authorized local model")
    vector_config = _exact_fields(
        actual["vector"],
        {"path", "index", "normalization", "anchor_label", "anchor_status"},
        "vector config",
    )
    if (
        vector_config["normalization"] != "none"
        or vector_config["anchor_label"] != "A"
        or vector_config["anchor_status"]
        != "development_structural_label_only_not_paper_rho_A"
    ):
        raise PipelineError("development vector/anchor status markers changed")
    if Path(vector_config["path"]).resolve() != CANDIDATE_VECTOR_PATH:
        raise PipelineError("real smoke vector differs from the authorized candidate asset")
    dose = _exact_fields(
        actual["development_dose"],
        {"status", "mu_all_tw", "mu_content_tw", "median_content_norm", "rho_by_anchor"},
        "development dose config",
    )
    if dose["status"] != "structural_smoke_only_not_paper_anchor":
        raise PipelineError("development dose may not claim paper anchor status")
    if set(dose["rho_by_anchor"]) != {"A", "T", "H"}:
        raise PipelineError("development dose must expose structural A/T/H labels")
    if actual["generation_config"] != DECODE_CONFIG or actual["judge_config"] != JUDGE_CONFIG:
        raise PipelineError("real smoke generation/judge config differs from Stage 3 constants")
    if judge["dtype"] != "float32" or judge["thinking_enabled"] is not True:
        raise PipelineError("real judge must use float32 with thinking enabled")
    return actual


def _check_temp_environment() -> None:
    required = (ROOT / ".codex-temp").resolve()
    for variable in ("TMPDIR", "TEMP", "TMP"):
        value = os.environ.get(variable)
        if not value or Path(value).resolve() != required:
            raise PipelineError(f"{variable} must resolve to {required}")
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise PipelineError("PYTHONDONTWRITEBYTECODE must equal 1")


def _messages(system_prompt: str, question: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]


def _dose_binding(config: Mapping[str, Any]) -> dict[str, Any]:
    dose = config["development_dose"]
    binding = build_test_dose_binding(
        mu_all_tw=float(dose["mu_all_tw"]),
        mu_content_tw=float(dose["mu_content_tw"]),
        median_content_norm=float(dose["median_content_norm"]),
        rho_by_anchor=dose["rho_by_anchor"],
    )
    binding = bind_dose_post_dtype(binding, dtype=config["behavior"]["dtype"])
    validate_dose_binding(binding)
    return binding


def validate_assets(config_path: Path, *, device: str) -> dict[str, Any]:
    """Read configs/tokenizers/vector metadata/input only; never load model weights."""
    _check_temp_environment()
    config_path = config_path.resolve()
    config = _validate_static_config(_strict_json(config_path), device=device)
    behavior = config["behavior"]
    judge = config["judge"]
    guard = offline_execution_guard()
    with guard:
        loaded = load_p1_harmful_active_entry(ROOT, config["input"]["active_entry"])
        if loaded["selected_relative_path"] != config["input"]["selected_path"]:
            raise PipelineError("configured selected input differs from the active P1 entry")
        by_source_id = {record["source_id"]: record for record in loaded["records"]}
        try:
            selected = [by_source_id[source_id] for source_id in config["input"]["source_ids"]]
        except KeyError as exc:
            raise PipelineError("configured source ID is absent from active P1 harmful input") from exc
        behavior_identity, behavior_tokenizer = inspect_local_model_assets(
            model_path=behavior["model_path"],
            tokenizer_path=behavior["tokenizer_path"],
            model_role="behavior",
            dtype=behavior["dtype"],
            device=device,
            trust_remote_code=behavior["trust_remote_code"],
            trust_remote_code_reason=behavior["trust_remote_code_reason"],
        )
        judge_identity, judge_tokenizer = inspect_local_model_assets(
            model_path=judge["model_path"],
            tokenizer_path=judge["tokenizer_path"],
            model_role="judge",
            dtype=judge["dtype"],
            device=device,
            trust_remote_code=judge["trust_remote_code"],
            trust_remote_code_reason=judge["trust_remote_code_reason"],
        )
        _, vector_identity = load_candidate_vector(
            vector_path=config["vector"]["path"],
            vector_index=config["vector"]["index"],
            layer=behavior["layer"],
            hook_site=behavior["hook_site"],
            hidden_size=behavior_identity["hidden_size"],
        )
        dose_binding = _dose_binding(config)
        selected_dose = validate_dose_binding(dose_binding)["A"]["mu_all_tw"]
        rendered_prompt_hashes = {}
        for record in selected:
            rendered = behavior_tokenizer.apply_chat_template(
                _messages(behavior["system_prompt"], record["question"]),
                tokenize=False,
                add_generation_prompt=True,
            )
            rendered_prompt_hashes[str(record["source_id"])] = hashlib.sha256(
                rendered.encode("utf-8")
            ).hexdigest()
        if not getattr(judge_tokenizer, "chat_template", None):
            raise PipelineError("judge tokenizer chat template is unavailable")
        closing_think_token_id = qwen3_closing_think_token_id(judge_tokenizer)
    return {
        "schema_version": "paper1-stage3-real-smoke-validation-v1",
        "status": "REAL_SMOKE_VALIDATE_ONLY_PASS",
        "validate_only": True,
        "full_model_weights_loaded": False,
        "generation_executed": False,
        "judge_executed": False,
        "run_mode": "smoke",
        "paper_result_eligible": False,
        "fake_backend": False,
        "asset_status": "development_only",
        "vector_status": "candidate_only",
        "formal_experiment_run": False,
        "configured_device": device,
        "logical_identity_count": len(config["logical_identities"]) * len(selected),
        "input_source_ids": [record["source_id"] for record in selected],
        "rendered_prompt_sha256_by_source_id": rendered_prompt_hashes,
        "behavior_identity": behavior_identity,
        "judge_identity": {
            **judge_identity,
            "rubric_sha256": judge_rubric_sha256(),
            "dtype": "float32",
            "closing_think_token_id": closing_think_token_id,
        },
        "vector_identity": vector_identity,
        "dose_binding_identity": {
            "behavior_dtype": behavior["dtype"],
            "measurement_dose_sha256": canonical_sha256(dose_binding),
            "selected_anchor": "A",
            "selected_estimator": "mu_all_tw",
            **selected_dose,
        },
        "offline_guard_report": guard.report,
        "network_attempts": guard.report["category_counts"]["network"],
    }


def create_output_directory(output_root: Path, run_id: str) -> Path:
    root = output_root.resolve()
    if root != OUTPUT_ROOT:
        raise PipelineError(f"real smoke output escaped the fixed root: {root}")
    if not isinstance(run_id, str) or not run_id or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for character in run_id
    ):
        raise PipelineError("real smoke run_id contains invalid characters")
    root.mkdir(parents=True, exist_ok=True)
    output = root / run_id
    output.mkdir(mode=0o700, exist_ok=False)
    return output


def _write_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def _gpu_identity(device: str) -> dict[str, Any]:
    import torch

    if device != "cuda:0" or not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        raise PipelineError("configured cuda:0 is unavailable for real smoke")
    properties = torch.cuda.get_device_properties(0)
    return {
        "schema_version": "paper1-stage3-gpu-identity-v1",
        "device": device,
        "device_index": 0,
        "device_name": properties.name,
        "total_memory_bytes": properties.total_memory,
        "compute_capability": f"{properties.major}.{properties.minor}",
        "device_count": torch.cuda.device_count(),
        "torch_cuda_version": torch.version.cuda,
    }


def _identity(
    *,
    kind: str,
    record: Mapping[str, Any],
    behavior_identity: Mapping[str, Any],
    vector_identity: Mapping[str, Any],
    dose_binding: Mapping[str, Any],
    config_path: Path,
    rendered_prompt_sha256: str,
) -> dict[str, Any]:
    clean = kind == "clean"
    if clean:
        dose = {
            "c_hex": 0.0.hex(),
            "alpha_pre_dtype_hex": 0.0.hex(),
            "alpha_post_dtype_hex": 0.0.hex(),
            "rho_hex": 0.0.hex(),
        }
    else:
        dose = validate_dose_binding(dose_binding)["A"]["mu_all_tw"]
    runtime = collect_runtime_versions()
    return {
        "profile": ACTIVE_PROFILE,
        "block": "harmful_clean" if clean else "support",
        "domain": "harmful",
        "split": "D_behavior_confirm" if clean else "D_behavior_screen",
        "model_revision": behavior_identity["model_revision"],
        "template_sha256": behavior_identity["chat_template_sha256"],
        "rendered_prompt_sha256": rendered_prompt_sha256,
        "prompt_id": f"p1-harmful-{record['source_id']}",
        "vector_id": None if clean else vector_identity["vector_id"],
        "estimator": "clean" if clean else "mu_all_tw",
        "anchor": "clean" if clean else "A",
        **dose,
        "layer": vector_identity["layer"],
        "hook_site": vector_identity["hook_site"],
        "phase": "decode-only",
        "use_cache": True,
        "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
        "code_sha256": canonical_sha256({
            "real_backend.py": file_sha256(ROOT / "stage3_pipeline/real_backend.py"),
            "real_judge.py": file_sha256(ROOT / "stage3_pipeline/real_judge.py"),
            "real_smoke.py": file_sha256(Path(__file__).resolve()),
        }),
        "config_sha256": file_sha256(config_path),
        "environment_sha256": canonical_sha256({"runtime_versions": runtime, "device": "cuda:0"}),
    }


def _disposition(
    identity: Mapping[str, Any], generation: Mapping[str, Any],
    judge: Mapping[str, Any] | None, response: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "paper1-stage3-execution-disposition-v2",
        "logical_id": generation["logical_id"],
        "identity_sha256": canonical_sha256(identity),
        "terminal_disposition": response_terminal_disposition(identity, response, generation, judge),
        "generation_record_sha256": generation["record_sha256"],
        "judge_record_sha256": None if judge is None else judge["record_sha256"],
        "response_record_sha256": response["record_sha256"],
        "integrity_block_reason": None,
    }


def run_real_smoke(config_path: Path, *, device: str, run_id: str | None = None) -> dict[str, Any]:
    """Execute the real chain. This function is intentionally not used by validate-only."""
    import torch

    validation = validate_assets(config_path, device=device)
    config_path = config_path.resolve()
    config = _validate_static_config(_strict_json(config_path), device=device)
    loaded = load_p1_harmful_active_entry(ROOT, config["input"]["active_entry"])
    by_source_id = {record["source_id"]: record for record in loaded["records"]}
    selected = [by_source_id[source_id] for source_id in config["input"]["source_ids"]]
    dose_binding = _dose_binding(config)
    gpu = _gpu_identity(device)
    started = utc_now()
    generation_records: list[dict[str, Any]] = []
    judge_records: list[dict[str, Any]] = []
    response_records: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    judge_call_traces: list[dict[str, Any]] = []
    identities_by_id: dict[str, dict[str, Any]] = {}
    prompts_by_id: dict[str, str] = {}
    guard = offline_execution_guard()
    with guard:
        behavior_config = config["behavior"]
        behavior_backend: RealBehaviorBackend | None = None
        judge_backend: RealJudgeBackend | None = None
        behavior_capability = None
        judge_capability = None
        try:
            behavior_backend = RealBehaviorBackend.from_pretrained(
                model_path=behavior_config["model_path"],
                tokenizer_path=behavior_config["tokenizer_path"],
                vector_path=config["vector"]["path"],
                vector_index=config["vector"]["index"],
                dose_binding=dose_binding,
                layer=behavior_config["layer"],
                hook_site=behavior_config["hook_site"],
                dtype=behavior_config["dtype"],
                device=device,
                trust_remote_code=behavior_config["trust_remote_code"],
                trust_remote_code_reason=behavior_config["trust_remote_code_reason"],
            )
            behavior_capability = behavior_backend.capability
            registry = LogicalIdentityRegistry()
            for record in selected:
                messages = _messages(behavior_config["system_prompt"], record["question"])
                rendered = behavior_backend.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                rendered_sha256 = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
                for kind in config["logical_identities"]:
                    identity = _identity(
                        kind=kind,
                        record=record,
                        behavior_identity=behavior_backend.behavior_identity,
                        vector_identity=behavior_backend.vector_identity,
                        dose_binding=dose_binding,
                        config_path=config_path,
                        rendered_prompt_sha256=rendered_sha256,
                    )
                    logical_id = registry.register(identity)
                    identities_by_id[logical_id] = identity
                    prompts_by_id[logical_id] = record["question"]
            producer = GenerationProducer(
                registry,
                behavior_backend,
                run_mode="smoke",
                generation_config=DECODE_CONFIG,
                fake_backend=False,
                capability=behavior_capability,
                item_budget=len(registry),
            )
            for logical_id in identities_by_id:
                generation = validate_generation_record(producer.produce(
                    logical_id,
                    {
                        "logical_id": logical_id,
                        "generation_config": DECODE_CONFIG,
                        "messages": _messages(
                            behavior_config["system_prompt"], prompts_by_id[logical_id]
                        ),
                    },
                ))
                generation_records.append(generation)
            behavior_identity = dict(behavior_backend.behavior_identity)
            vector_identity = dict(behavior_backend.vector_identity)
            hook_calls = [
                record["attempts"][-1]["diagnostics"] for record in generation_records
            ]
            lifecycle = behavior_backend.release()
            behavior_backend = None
            judge_config = config["judge"]
            judge_backend = RealJudgeBackend.from_pretrained(
                model_path=judge_config["model_path"],
                tokenizer_path=judge_config["tokenizer_path"],
                device=device,
                lifecycle=lifecycle,
                trust_remote_code=judge_config["trust_remote_code"],
                trust_remote_code_reason=judge_config["trust_remote_code_reason"],
            )
            judge_capability = judge_backend.capability
            judge_identity = dict(judge_backend.judge_identity)
            for generation in generation_records:
                logical_id = generation["logical_id"]
                if not generation["generation_completed"]:
                    judge = None
                else:
                    assert judge_backend is not None
                    judge = validate_judge_record(parse_judge_with_retry(
                        logical_id,
                        judge_backend,
                        {
                            "logical_id": logical_id,
                            "judge_config": JUDGE_CONFIG,
                            "backend_request": {
                                "prompt": prompts_by_id[logical_id],
                                "response": generation["output_text"],
                                "domain": "harmful",
                            },
                        },
                        registry=registry,
                        generation_record=generation,
                        run_mode="smoke",
                        judge_identity=judge_backend.producer_identity,
                        judge_config=JUDGE_CONFIG,
                        fake_backend=False,
                        capability=judge_capability,
                    ))
                    judge_records.append(judge)
                    judge_call_traces.append(dict(judge_backend.last_diagnostics))
                terminal_diagnostics = generation["attempts"][-1]["diagnostics"]
                dose_evidence = terminal_diagnostics.get("dose_evidence")
                response = build_block_response_record(
                    identity=identities_by_id[logical_id],
                    generation_record=generation,
                    judge_record=judge,
                    dose_evidence=dose_evidence,
                )
                response_records.append(response)
                dispositions.append(_disposition(
                    identities_by_id[logical_id], generation, judge, response
                ))
            lifecycle = judge_backend.release()
            judge_backend = None
        finally:
            if judge_backend is not None and not judge_backend.released:
                judge_backend.release()
            if behavior_backend is not None and not behavior_backend.released:
                behavior_backend.release()
    reconciliation = reconcile_execution(
        registry,
        run_mode="smoke",
        generation_records=generation_records,
        judge_records=judge_records,
        response_records=response_records,
        dispositions=dispositions,
        dose_binding=dose_binding,
    )
    completed = utc_now()
    selected_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_directory = create_output_directory(OUTPUT_ROOT, selected_run_id)
    _write_json(output_directory / "logical_registry.json", registry.manifest())
    _write_json(output_directory / "generation_records.json", generation_records)
    _write_json(output_directory / "judge_records.json", judge_records)
    _write_json(output_directory / "response_records.json", response_records)
    _write_json(output_directory / "execution_dispositions.json", dispositions)
    hook_identity = {
        "schema_version": "paper1-stage3-real-hook-run-identity-v1",
        "layer": config["behavior"]["layer"],
        "hook_site": config["behavior"]["hook_site"],
        "phase": "decode-only",
        "use_cache": True,
        "call_count": len(hook_calls),
        "call_diagnostics_sha256": canonical_sha256(hook_calls),
        "trace_preview": hook_calls[:2],
    }
    output_identity = {
        "registry_sha256": registry.manifest()["registry_sha256"],
        "generation_records_sha256": canonical_sha256(generation_records),
        "judge_records_sha256": canonical_sha256(judge_records),
        "response_records_sha256": canonical_sha256(response_records),
        "dispositions_sha256": canonical_sha256(dispositions),
        "judge_call_diagnostics_sha256": canonical_sha256(judge_call_traces),
    }
    backend_identity = {
        "schema_version": "paper1-stage3-real-backend-provenance-v1",
        "asset_status": "development_only",
        "identity_level": "development_candidate",
        "behavior_identity": behavior_identity,
        "judge_identity": judge_identity,
        "vector_identity": vector_identity,
        "hook_identity": hook_identity,
        "gpu_identity": gpu,
        "lifecycle": lifecycle,
        "output_identity": output_identity,
        "judge_call_trace_preview": judge_call_traces[:2],
        "development_anchor_status": config["vector"]["anchor_status"],
    }
    input_paths = [
        config_path,
        ROOT / config["input"]["active_entry"],
        ROOT / config["input"]["selected_path"],
        Path(config["vector"]["path"]),
    ]
    for section in ("behavior", "judge"):
        model_path = Path(config[section]["model_path"]).resolve()
        tokenizer_path = Path(config[section]["tokenizer_path"]).resolve()
        input_paths.extend([
            model_path / "config.json",
            model_path / "model.safetensors.index.json",
            tokenizer_path / "tokenizer.json",
            tokenizer_path / "tokenizer_config.json",
        ])
    manifest = build_run_manifest(
        repo_root=ROOT,
        run_mode="smoke",
        command=[sys.executable, "-B", str(Path(__file__).relative_to(ROOT)), "--config", str(config_path), "--device", device],
        started_at_utc=started,
        completed_at_utc=completed,
        model_path_or_id=behavior_identity["resolved_model_path"],
        tokenizer_path_or_id=behavior_identity["resolved_tokenizer_path"],
        input_paths=input_paths,
        generation_config=DECODE_CONFIG,
        seed=42,
        gpu_identity=f"{gpu['device']}:{gpu['device_name']}",
        output_directory=output_directory,
        exit_status="success",
        exit_code=0,
        fake_backend=False,
        reconciliation=reconciliation,
        offline_guard=guard,
        runtime_versions=collect_runtime_versions(),
        asset_status="development_only",
        formal_experiment_run=False,
        backend_identity=backend_identity,
        logical_registry=registry.manifest(),
        generation_records=generation_records,
        judge_records=judge_records,
        behavior_capability=behavior_capability,
        judge_capability=judge_capability,
    )
    manifest_path = write_run_manifest(output_directory, manifest)
    validated_manifest = validate_run_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    return {
        "status": "REAL_SMOKE_PASS",
        "validation": validation["status"],
        "output_directory": str(output_directory),
        "run_manifest_sha256": file_sha256(manifest_path),
        "logical_identity_count": len(registry),
        "paper_result_eligible": False,
        "fake_backend": False,
        "asset_status": "development_only",
        "formal_experiment_run": False,
        "blocked_attempts": validated_manifest["offline_guard_report"]["blocked_attempt_count"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device", default=None)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--run-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    raw_config = _strict_json(args.config.resolve())
    device = args.device or raw_config.get("device")
    if args.validate_only:
        if args.run_id is not None:
            raise PipelineError("--run-id is unavailable with --validate-only")
        result = validate_assets(args.config, device=device)
    else:
        result = run_real_smoke(args.config, device=device, run_id=args.run_id)
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
