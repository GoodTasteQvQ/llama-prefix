#!/usr/bin/env python3
"""Validate fixed Stage 3 development inputs without running any experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping


for _offline_variable in (
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE",
):
    os.environ[_offline_variable] = "1"

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import PipelineError, offline_execution_guard  # noqa: E402
from stage3_pipeline.dose import validate_dose_binding  # noqa: E402
from stage3_pipeline.offline_assets import strict_json_loads  # noqa: E402
from stage3_pipeline.p1_results import build_complete_case_frame  # noqa: E402
from stage3_pipeline.real_backend import inspect_local_model_assets  # noqa: E402
from stage3_pipeline.vector_pool import (  # noqa: E402
    EXPECTED_SHAPE,
    MANIFEST_RELATIVE_PATH,
    TENSOR_RELATIVE_PATH,
    load_stage3_vector_pool,
)


DEFAULT_CONFIG = ROOT / "configs/stage3/qwen25_stage3_development_inputs_v1.json"
P1_RUNS_ROOT = Path("/data/goodtaste_workspace/paper1_stage3_runs")
P1_RUN_ID = "p1-qwen25-paper-20260807T044847Z"
P1_RAW_NAME = "p1_measurement_raw.json"
P1_EXPECTED_COUNTS = {"harmful": 100, "benign": 100, "total": 200}
P1_EXPECTED_EXCLUDED_COUNTS = {"harmful": 0, "benign": 0, "total": 0}
EXPECTED_DATASETS = (
    (
        "configs/stage3/p1_harmful_do_not_answer_v1.json",
        "D_norm_confirm.harmful",
        100,
    ),
    ("configs/stage3/p1_benign_v1.json", "D_norm_confirm.benign", 100),
    ("configs/stage3/jbb_behavior_screen_v1.json", "D_behavior_screen", 30),
    ("configs/stage3/jbb_behavior_confirm_v1.json", "D_behavior_confirm", 50),
    ("configs/stage3/benign_confirm_v1.json", "D_benign_confirm", 30),
)
ANCHOR_RELATIVE_PATH = "configs/stage3/qwen25_base_anchors_v1.json"
EXPECTED_RHO = {
    "A": 0.7499471265016073,
    "T": 0.9999295020021431,
    "H": 1.249911877502679,
}
EXPECTED_RHO_HEX = {
    "A": "0x1.7ff911dc1b6eap-1",
    "T": "0x1.fff6c27acf3e3p-1",
    "H": "0x1.3ffa398cc186ep+0",
}
BEHAVIOR_PATH = "/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct"
JUDGE_PATH = "/data/goodtaste_workspace/models/Qwen3-8B"
TOP_LEVEL_FIELDS = (
    "schema_version",
    "status",
    "development_input_validation_only",
    "paper_result_eligible",
    "formal_experiment_run",
    "generation_run",
    "judge_run",
    "p1_run",
    "datasets",
    "anchors",
    "vector_pool",
    "behavior",
    "judge",
    "p1_measurement_and_dose",
)
MEASUREMENT_FIELDS = (
    "mu_all_tw_Qwen",
    "mu_content_tw_Qwen",
    "median_content_norm_Qwen",
    "c_A",
    "c_T",
    "c_H",
    "measurement_result_dose_manifest",
    "dose_binding",
)


def _require_finite_numbers(value: Any, field: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require_finite_numbers(child, f"{field}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _require_finite_numbers(child, f"{field}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise PipelineError(f"{field} contains a non-finite number")


def _strict_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = strict_json_loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PipelineError(f"unable to read strict {label}: {path}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"{label} must be a JSON object")
    _require_finite_numbers(value, label)
    return value


def _exact_fields(value: Any, expected: tuple[str, ...], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or tuple(value) != expected:
        raise PipelineError(f"{label} exact ordered fields mismatch")
    return value


def _resolve_repo_file(root: Path, relative_path: Any, field: str) -> Path:
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or "\\" in relative_path
        or "://" in relative_path
    ):
        raise PipelineError(f"{field} must be a local POSIX relative path")
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise PipelineError(f"{field} must remain below the repository root")
    path = (root / Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PipelineError(f"{field} escapes the repository root") from exc
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"required {field} file is missing: {relative_path}")
    return path


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _positive_float(value: Any, field: str) -> float:
    if type(value) is not float or not math.isfinite(value) or value <= 0.0:
        raise PipelineError(f"{field} must be a finite positive float")
    return value


def _exact_count_map(value: Any, expected: Mapping[str, int], field: str) -> None:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise PipelineError(f"{field} fields mismatch")
    for key, expected_count in expected.items():
        if type(value[key]) is not int or value[key] != expected_count:
            raise PipelineError(f"{field}.{key} mismatch")


def _formal_p1_file(path_value: Any, field: str) -> Path:
    if (
        not isinstance(path_value, str)
        or not path_value
        or "://" in path_value
        or not Path(path_value).is_absolute()
    ):
        raise PipelineError(f"{field} must be a non-empty absolute local path")
    path = Path(path_value)
    try:
        resolved_path = path.resolve()
        resolved_root = P1_RUNS_ROOT.resolve()
        resolved_path.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise PipelineError(f"{field} must remain below {P1_RUNS_ROOT}") from exc
    if path.is_symlink() or not path.is_file():
        raise PipelineError(f"{field} must name an existing regular non-symlink file")
    return resolved_path


def _result_handoff_values(result: Mapping[str, Any]) -> dict[str, float]:
    pooled = result.get("pooled_statistics")
    if not isinstance(pooled, Mapping):
        raise PipelineError("formal P1 result pooled_statistics must be an object")
    dose = result.get("dose_binding")
    if not isinstance(dose, Mapping) or not dose:
        raise PipelineError("formal P1 result dose_binding must be a non-empty object")
    validate_dose_binding(dose)

    values = {
        "mu_all_tw_Qwen": _positive_float(
            pooled.get("mu_all_tw_Qwen"),
            "formal P1 result pooled_statistics.mu_all_tw_Qwen",
        ),
        "mu_content_tw_Qwen": _positive_float(
            pooled.get("mu_content_tw_Qwen"),
            "formal P1 result pooled_statistics.mu_content_tw_Qwen",
        ),
        "median_content_norm_Qwen": _positive_float(
            result.get("median_content_norm_Qwen"),
            "formal P1 result median_content_norm_Qwen",
        ),
    }
    anchors = dose["anchors"]
    for index, anchor in enumerate(("A", "T", "H")):
        entry = anchors[index]
        values[f"c_{anchor}"] = _positive_float(
            entry["c"]["value"], f"formal P1 result dose_binding.c_{anchor}"
        )

    dose_scalar_fields = {
        "mu_all_tw_Qwen": "mu_all_tw",
        "mu_content_tw_Qwen": "mu_content_tw",
        "median_content_norm_Qwen": "median_content_norm",
    }
    for result_field, dose_field in dose_scalar_fields.items():
        dose_value = _positive_float(
            dose[dose_field]["value"], f"formal P1 result dose_binding.{dose_field}.value"
        )
        if dose_value.hex() != values[result_field].hex():
            raise PipelineError(f"formal P1 result {result_field} differs from dose binding")
    return values


def _check_environment(repo_root: Path) -> None:
    temp_root = (repo_root / ".codex-temp").resolve()
    for variable in ("TMPDIR", "TEMP", "TMP"):
        value = os.environ.get(variable)
        if not value or Path(value).resolve() != temp_root:
            raise PipelineError(f"{variable} must resolve to {temp_root}")
    required = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    }
    for variable, expected in required.items():
        if os.environ.get(variable) != expected:
            raise PipelineError(f"{variable} must equal {expected}")


def validate_static_config(config: Mapping[str, Any]) -> dict[str, Any]:
    actual = dict(_exact_fields(config, TOP_LEVEL_FIELDS, "development input config"))
    expected_flags = {
        "schema_version": "paper1-stage3-qwen25-development-inputs-v1",
        "status": "development_input_validation_only",
        "development_input_validation_only": True,
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "generation_run": False,
        "judge_run": False,
        "p1_run": False,
    }
    for field, expected in expected_flags.items():
        mismatch = (
            actual[field] is not expected
            if isinstance(expected, bool)
            else actual[field] != expected
        )
        if mismatch:
            raise PipelineError(f"development input config {field} mismatch")

    datasets = actual["datasets"]
    if not isinstance(datasets, list) or len(datasets) != len(EXPECTED_DATASETS):
        raise PipelineError("development input config must reference exactly five datasets")
    for index, (entry_path, role, row_count) in enumerate(EXPECTED_DATASETS):
        entry = _exact_fields(
            datasets[index],
            ("active_entry_relative_path", "role", "row_count"),
            f"datasets[{index}]",
        )
        expected = (entry_path, role, row_count)
        actual_values = (
            entry["active_entry_relative_path"],
            entry["role"],
            entry["row_count"],
        )
        if actual_values != expected or type(entry["row_count"]) is not int:
            raise PipelineError(f"datasets[{index}] reference/role/row_count mismatch")

    anchors = _exact_fields(actual["anchors"], ("config_relative_path",), "anchors")
    if anchors["config_relative_path"] != ANCHOR_RELATIVE_PATH:
        raise PipelineError("anchor config reference mismatch")
    vectors = _exact_fields(
        actual["vector_pool"],
        ("manifest_relative_path", "tensor_relative_path"),
        "vector_pool",
    )
    if vectors != {
        "manifest_relative_path": MANIFEST_RELATIVE_PATH,
        "tensor_relative_path": TENSOR_RELATIVE_PATH,
    }:
        raise PipelineError("vector pool references mismatch")

    behavior = _exact_fields(
        actual["behavior"],
        (
            "checkpoint_path",
            "tokenizer_path",
            "dtype",
            "device",
            "trust_remote_code",
            "trust_remote_code_reason",
            "layer",
            "hook_site",
            "phase_mode",
        ),
        "behavior",
    )
    expected_behavior = {
        "checkpoint_path": BEHAVIOR_PATH,
        "tokenizer_path": BEHAVIOR_PATH,
        "dtype": "bfloat16",
        "device": "cuda:0",
        "trust_remote_code": False,
        "trust_remote_code_reason": None,
        "layer": 9,
        "hook_site": "resid_pre",
        "phase_mode": "decode_only",
    }
    if dict(behavior) != expected_behavior or type(behavior["layer"]) is not int:
        raise PipelineError("behavior input metadata mismatch")

    judge = _exact_fields(
        actual["judge"],
        (
            "checkpoint_path",
            "tokenizer_path",
            "dtype",
            "device",
            "trust_remote_code",
            "trust_remote_code_reason",
        ),
        "judge",
    )
    expected_judge = {
        "checkpoint_path": JUDGE_PATH,
        "tokenizer_path": JUDGE_PATH,
        "dtype": "float32",
        "device": "cuda:0",
        "trust_remote_code": False,
        "trust_remote_code_reason": None,
    }
    if dict(judge) != expected_judge:
        raise PipelineError("judge input metadata mismatch")

    measurement = _exact_fields(
        actual["p1_measurement_and_dose"],
        MEASUREMENT_FIELDS,
        "p1_measurement_and_dose",
    )
    if any(measurement[field] is None for field in MEASUREMENT_FIELDS):
        raise PipelineError("P1 measurement/dose handoff must be complete")
    for field in (
        "mu_all_tw_Qwen",
        "mu_content_tw_Qwen",
        "median_content_norm_Qwen",
        "c_A",
        "c_T",
        "c_H",
    ):
        _positive_float(measurement[field], f"p1_measurement_and_dose.{field}")
    if not (
        measurement["c_A"] < measurement["c_T"] < measurement["c_H"]
    ):
        raise PipelineError("P1 dose values must satisfy 0 < c_A < c_T < c_H")
    manifest = measurement["measurement_result_dose_manifest"]
    if (
        not isinstance(manifest, str)
        or not manifest
        or "://" in manifest
        or not Path(manifest).is_absolute()
    ):
        raise PipelineError(
            "p1_measurement_and_dose.measurement_result_dose_manifest must be an absolute local path"
        )
    dose_binding = measurement["dose_binding"]
    if not isinstance(dose_binding, Mapping) or not dose_binding:
        raise PipelineError("p1_measurement_and_dose.dose_binding must be a non-empty object")
    validate_dose_binding(dose_binding)
    return actual


def validate_p1_dose_handoff(measurement: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the fixed formal result/raw lineage and exact configured handoff."""
    result_path = _formal_p1_file(
        measurement["measurement_result_dose_manifest"],
        "p1_measurement_and_dose.measurement_result_dose_manifest",
    )
    result = _strict_json_object(result_path, "formal P1 result")
    if result.get("status") != "ESTIMABLE":
        raise PipelineError("formal P1 result status must be ESTIMABLE")
    if result.get("run_mode") != "paper":
        raise PipelineError("formal P1 result run_mode must be paper")
    _exact_count_map(result.get("scheduled_counts"), P1_EXPECTED_COUNTS, "scheduled_counts")
    _exact_count_map(result.get("complete_counts"), P1_EXPECTED_COUNTS, "complete_counts")
    _exact_count_map(
        result.get("excluded_counts"),
        P1_EXPECTED_EXCLUDED_COUNTS,
        "excluded_counts",
    )
    bootstrap = result.get("bootstrap_summary")
    if not isinstance(bootstrap, Mapping):
        raise PipelineError("formal P1 result bootstrap_summary must be an object")
    for field in ("replicates_requested", "replicates_successful"):
        if type(bootstrap.get(field)) is not int or bootstrap[field] != 10_000:
            raise PipelineError(f"formal P1 result bootstrap_summary.{field} mismatch")
    if bootstrap.get("gate_delta_gt_0_10") is not True:
        raise PipelineError("formal P1 result primary gate must be true")
    pooled = result.get("pooled_statistics")
    if not isinstance(pooled, Mapping):
        raise PipelineError("formal P1 result pooled_statistics must be an object")
    delta = pooled.get("delta_select_tw")
    if type(delta) is not float or not math.isfinite(delta) or delta <= 0.10:
        raise PipelineError("formal P1 result delta_select_tw must exceed 0.10")
    result_values = _result_handoff_values(result)
    result_dose = result["dose_binding"]

    raw_path = result_path.with_name(P1_RAW_NAME)
    if raw_path.is_symlink() or not raw_path.is_file():
        raise PipelineError("formal P1 raw must be an existing regular non-symlink sibling")
    raw = _strict_json_object(raw_path, "formal P1 raw")
    if raw.get("run_id") != P1_RUN_ID or result_path.parent.name != P1_RUN_ID:
        raise PipelineError("formal P1 raw run_id/run directory mismatch")
    expected_raw_flags = {
        "run_mode": "paper",
        "formal_experiment_run": True,
        "full_p1_run": True,
        "generation_run": False,
        "judge_run": False,
    }
    for field, expected in expected_raw_flags.items():
        mismatch = (
            raw.get(field) is not expected
            if isinstance(expected, bool)
            else raw.get(field) != expected
        )
        if mismatch:
            raise PipelineError(f"formal P1 raw {field} mismatch")
    prompt_measurements = raw.get("prompt_measurements")
    terminal_records = raw.get("p1_terminal_records")
    if not isinstance(prompt_measurements, list) or len(prompt_measurements) != 200:
        raise PipelineError("formal P1 raw must contain 200 prompt measurements")
    if not isinstance(terminal_records, list) or len(terminal_records) != 200:
        raise PipelineError("formal P1 raw must contain 200 terminal records")
    frame = build_complete_case_frame(raw)
    if frame["terminal_record_count"] != 200:
        raise PipelineError("formal P1 raw terminal frame count mismatch")
    _exact_count_map(frame["scheduled_counts"], P1_EXPECTED_COUNTS, "raw scheduled_counts")
    _exact_count_map(frame["complete_counts"], P1_EXPECTED_COUNTS, "raw complete_counts")
    _exact_count_map(
        frame["excluded_counts"], P1_EXPECTED_EXCLUDED_COUNTS, "raw excluded_counts"
    )
    if frame["prompt_identities_unique"] is not True:
        raise PipelineError("formal P1 raw prompt identities must be unique")

    for field, result_value in result_values.items():
        configured_value = measurement[field]
        if configured_value.hex() != result_value.hex():
            raise PipelineError(f"configured P1 handoff {field} differs from formal result")
    if measurement["dose_binding"] != result_dose:
        raise PipelineError("configured P1 dose binding differs from formal result")
    validate_dose_binding(measurement["dose_binding"])
    return {
        "p1_dose_handoff": "VALIDATED",
        "p1_run_id": P1_RUN_ID,
        "p1_result_status": result["status"],
        "p1_primary_gate": True,
    }


def validate_dataset_entries(repo_root: Path, datasets: list[Any]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for index, dataset in enumerate(datasets):
        entry_path = _resolve_repo_file(
            repo_root,
            dataset["active_entry_relative_path"],
            f"datasets[{index}].active_entry_relative_path",
        )
        entry = _strict_json_object(entry_path, f"active dataset entry {index}")
        if entry.get("schema_version") != "paper1-stage3-active-dataset-entry-v1":
            raise PipelineError(f"active dataset entry {index} schema mismatch")
        if entry.get("status") != "design_selected":
            raise PipelineError(f"active dataset entry {index} status mismatch")
        if entry.get("role") != dataset["role"]:
            raise PipelineError(f"active dataset entry {index} role mismatch")
        if type(entry.get("row_count")) is not int or entry["row_count"] != dataset["row_count"]:
            raise PipelineError(f"active dataset entry {index} row_count mismatch")
        if entry.get("formal_experiment_run") not in (None, False):
            raise PipelineError(f"active dataset entry {index} claims a formal experiment run")
        if not _valid_sha256(entry.get("selected_raw_sha256")):
            raise PipelineError(f"active dataset entry {index} selected SHA-256 is invalid")

        selected_path = _resolve_repo_file(
            repo_root, entry.get("relative_path"), f"active dataset entry {index} relative_path"
        )
        selected_raw = selected_path.read_bytes()
        if _sha256_bytes(selected_raw) != entry["selected_raw_sha256"]:
            raise PipelineError(f"active dataset entry {index} selected SHA-256 mismatch")
        selected = _strict_json_object(selected_path, f"selected dataset {index}")
        records = selected.get("records")
        if not isinstance(records, list):
            raise PipelineError(f"selected dataset {index} records must be an array")
        if type(selected.get("record_count")) is not int:
            raise PipelineError(f"selected dataset {index} record_count must be an integer")
        if selected["record_count"] != dataset["row_count"] or len(records) != dataset["row_count"]:
            raise PipelineError(f"selected dataset {index} row_count mismatch")
        if "role" in selected and selected["role"] != dataset["role"]:
            raise PipelineError(f"selected dataset {index} role mismatch")
        validated.append(
            {
                "active_entry_relative_path": dataset["active_entry_relative_path"],
                "selected_relative_path": entry["relative_path"],
                "role": dataset["role"],
                "row_count": dataset["row_count"],
                "selected_raw_sha256": entry["selected_raw_sha256"],
            }
        )
    return validated


def validate_anchor_config(
    anchor_path: Path, *, behavior: Mapping[str, Any] | None = None
) -> dict[str, float]:
    anchors = _strict_json_object(anchor_path, "anchor config")
    if anchors.get("schema_version") != "paper1-stage3-qwen25-base-anchors-v1":
        raise PipelineError("anchor config schema mismatch")
    if anchors.get("status") != "design_selected" or anchors.get("formal_experiment_run") is not False:
        raise PipelineError("anchor config status mismatch")
    rho = anchors.get("rho_by_anchor")
    rho_hex = anchors.get("rho_binary64_hex")
    if not isinstance(rho, Mapping) or tuple(rho) != ("A", "T", "H"):
        raise PipelineError("anchor rho order must be A,T,H")
    if not isinstance(rho_hex, Mapping) or tuple(rho_hex) != ("A", "T", "H"):
        raise PipelineError("anchor binary64 order must be A,T,H")
    for label in ("A", "T", "H"):
        value = rho[label]
        if type(value) is not float or value != EXPECTED_RHO[label]:
            raise PipelineError(f"anchor rho_{label} exact value mismatch")
        if rho_hex[label] != EXPECTED_RHO_HEX[label]:
            raise PipelineError(f"anchor rho_{label} binary64 representation mismatch")
        if value.hex() != rho_hex[label] or float.fromhex(rho_hex[label]) != value:
            raise PipelineError(f"anchor rho_{label} decimal/binary64 pair mismatch")
    if not (0.0 < rho["A"] < rho["T"] < rho["H"]):
        raise PipelineError("anchor rhos must satisfy 0 < A < T < H")
    if behavior is not None and (
        anchors.get("layer") != behavior["layer"]
        or anchors.get("hook_site") != behavior["hook_site"]
        or anchors.get("phase_mode") != behavior["phase_mode"]
    ):
        raise PipelineError("anchor layer/hook_site/phase_mode mismatch")
    return {label: rho[label] for label in ("A", "T", "H")}


def _validate_model_identity(
    identity: Any, *, role: str, configured_path: str
) -> Mapping[str, Any]:
    if not isinstance(identity, Mapping):
        raise PipelineError(f"{role} model inspector returned no identity")
    if identity.get("model_role") != role or identity.get("local_files_only") is not True:
        raise PipelineError(f"{role} model identity is not local-only")
    if Path(str(identity.get("resolved_model_path"))).resolve() != Path(configured_path).resolve():
        raise PipelineError(f"{role} model identity path mismatch")
    if Path(str(identity.get("resolved_tokenizer_path"))).resolve() != Path(configured_path).resolve():
        raise PipelineError(f"{role} tokenizer identity path mismatch")
    return identity


def _validate_chat_template(tokenizer: Any, role: str) -> None:
    template = getattr(tokenizer, "chat_template", None)
    if not isinstance(template, str) or not template:
        raise PipelineError(f"{role} tokenizer chat template is unavailable")
    try:
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": "Stage 3 development input validation."}],
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception as exc:
        raise PipelineError(f"{role} tokenizer chat template cannot render") from exc
    if not isinstance(rendered, str) or not rendered:
        raise PipelineError(f"{role} tokenizer chat template rendered no text")


def validate_development_inputs(
    config_path: Path,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] | None = None,
) -> dict[str, Any]:
    """Validate references and metadata only; never load model weights or run inference."""
    root = repo_root.resolve()
    _check_environment(root)
    config = validate_static_config(_strict_json_object(config_path.resolve(), "development input config"))
    p1_handoff = validate_p1_dose_handoff(config["p1_measurement_and_dose"])
    inspector = inspect_local_model_assets if model_asset_inspector is None else model_asset_inspector

    guard = offline_execution_guard()
    with guard:
        datasets = validate_dataset_entries(root, config["datasets"])
        vector_config = config["vector_pool"]
        pool = load_stage3_vector_pool(
            root,
            manifest_relative_path=vector_config["manifest_relative_path"],
            tensor_relative_path=vector_config["tensor_relative_path"],
        )
        anchor_path = _resolve_repo_file(
            root, config["anchors"]["config_relative_path"], "anchors.config_relative_path"
        )
        rho = validate_anchor_config(anchor_path, behavior=config["behavior"])

        model_results: dict[str, Mapping[str, Any]] = {}
        for role in ("behavior", "judge"):
            model = config[role]
            identity, tokenizer = inspector(
                model_path=model["checkpoint_path"],
                tokenizer_path=model["tokenizer_path"],
                model_role=role,
                dtype=model["dtype"],
                device=model["device"],
                trust_remote_code=model["trust_remote_code"],
                trust_remote_code_reason=model["trust_remote_code_reason"],
            )
            model_results[role] = _validate_model_identity(
                identity, role=role, configured_path=model["checkpoint_path"]
            )
            _validate_chat_template(tokenizer, role)
        behavior_identity = model_results["behavior"]
        if behavior_identity.get("hidden_size") != EXPECTED_SHAPE[1]:
            raise PipelineError("behavior model hidden size does not match vector width")
        layer_count = behavior_identity.get("layer_count")
        if type(layer_count) is not int or not 0 <= config["behavior"]["layer"] < layer_count:
            raise PipelineError("behavior layer is outside the local model config")

    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("validate-only attempted a forbidden offline operation")
    return {
        "status": "STAGE3_DEVELOPMENT_INPUTS_VALIDATE_ONLY_PASS",
        "development_input_validation_only": True,
        "model_weights_loaded": False,
        "generation_run": False,
        "judge_run": False,
        "p1_run": False,
        "formal_experiment_run": False,
        "paper_result_eligible": False,
        "dataset_count": len(datasets),
        "dataset_row_count_total": sum(item["row_count"] for item in datasets),
        "vector_count": pool.tensor.shape[0],
        "vector_width": pool.tensor.shape[1],
        "rho_by_anchor": rho,
        "behavior_model_revision": behavior_identity["model_revision"],
        "judge_model_revision": model_results["judge"]["model_revision"],
        "offline_guard": guard_report,
        **p1_handoff,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = validate_development_inputs(args.config)
    except (OSError, PipelineError) as exc:
        print(
            json.dumps(
                {
                    "status": "STAGE3_DEVELOPMENT_INPUTS_VALIDATE_ONLY_FAIL",
                    "error": str(exc),
                    "model_weights_loaded": False,
                    "generation_run": False,
                    "judge_run": False,
                    "p1_run": False,
                    "formal_experiment_run": False,
                    "paper_result_eligible": False,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
