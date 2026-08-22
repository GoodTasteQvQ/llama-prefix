"""Independent formal T/H P2 runner fixed by the prospective v2 amendment."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from scripts.stage3_production.validate_stage3_development_inputs import (
    _strict_json_object,
    validate_development_inputs,
)

from .core import (
    ACTIVE_PROFILE,
    DECODE_CONFIG,
    IDENTITY_REQUIRED_FIELDS,
    JUDGE_CONFIG,
    PROTOCOL_VERSION,
    GenerationProducer,
    IdentityError,
    PipelineError,
    canonical_json,
    canonical_sha256,
    file_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
)
from .dose import validate_dose_binding
from .execution import (
    OutputStore,
    TERMINAL_DISPOSITIONS,
    response_terminal_disposition,
    validate_execution_disposition,
)
from .p2_runner import (
    DEFAULT_CONFIG as OLD_P2_CONFIG,
    PreparedP2Runner,
    load_real_behavior_backend as load_old_p2_behavior_backend,
    load_real_judge_backend as load_old_p2_judge_backend,
    prepare_p2_runner,
)
from .real_backend import inspect_local_model_assets
from .records import (
    validate_dose_evidence,
    validate_generation_record,
    validate_judge_record,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/stage3/qwen25_p2_independent_th_v1.json"
AMENDMENT = ROOT / "writing/stage3 design/paper1_stage3_protocol_amendment_p2_v2.md"
OUTPUT_ROOT = Path("/data/goodtaste_workspace/paper1_stage3_runs")
OLD_P2_RUN = OUTPUT_ROOT / "p2-qwen25-paper-20260808T051044Z"
OLD_P2_MATERIALIZED = OUTPUT_ROOT / "p2-materialized-qwen25-paper-20260808T051044Z-v1"
SUPPORT_RUN = OUTPUT_ROOT / "support-qwen25-paper-detached-20260807T133730Z"
AMENDMENT_ID = "paper1-stage3-p2-independent-th-v2"
AMENDMENT_DATE = "2026-08-22"
SUPPORT_CONFIG = "configs/stage3/qwen25_support_screen_v1.json"
CONFIRM_FRAME = "configs/stage3/jbb_behavior_confirm_v1.json"
VECTOR_INDICES = tuple(range(10, 30))
CELLS = (
    ("P2_T_all", "T", "mu_all_tw"),
    ("P2_T_content", "T", "mu_content_tw"),
    ("P2_H_all", "H", "mu_all_tw"),
    ("P2_H_content", "H", "mu_content_tw"),
)
BLOCKS = tuple(cell for cell, _anchor, _estimator in CELLS)
IDENTITY_COUNT = 4_000
ENDPOINT_ORDER = (
    {
        "member_id": "P2-U(T)",
        "outcome": "unsafe",
        "contrast": "all-minus-content",
        "anchor": "T",
        "matched_set": "M_T",
        "all_cell": "P2_T_all",
        "content_cell": "P2_T_content",
    },
    {
        "member_id": "P2-B(H)",
        "outcome": "broken",
        "contrast": "all-minus-content",
        "anchor": "H",
        "matched_set": "M_H",
        "all_cell": "P2_H_all",
        "content_cell": "P2_H_content",
    },
)
RETRY_POLICY = {
    "generation_max_attempts": 2,
    "generation_retry": "one_identical_technical_retry",
    "judge_max_attempts": 2,
    "judge_retry": "one_identical_parse_or_technical_retry",
    "terminal_missingness": "existing_first_failure_precedence",
}
SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

_CELL_RULES = {
    cell: ("harmful", "D_behavior_confirm", estimator, anchor)
    for cell, anchor, estimator in CELLS
}
_OLD_P2_GIT_HASHES = {
    ROOT / "stage3_pipeline/p2_runner.py":
        "c29faab0f0d5edfd67725b9e24b5bcde32101f83535569cd29b9393a1f4052d9",
    ROOT / "scripts/stage3_production/run_p2.py":
        "99feecdb7c91d2a1a6e28496989959f5d0ab6db63fabeed1ba42e4e2666524ef",
    ROOT / "configs/stage3/qwen25_p2_v1.json":
        "db95144e97936ffd43f977728ae3257738c0e2da3dc38c4de3c0664c79baec39",
}
_OLD_P2_RESULT_HASHES = {
    OLD_P2_RUN / "execution_identity.json":
        "a09262d0fdc66a5895291a94ac149e4244ce0f9727eaa2ca366ee18cd1916b5c",
    OLD_P2_RUN / "p2_ledger.json":
        "d692e444ba05b3d0a3bdb6a7d32765a866aa3e37537923aade8c311073bbb45a",
    OLD_P2_MATERIALIZED / "p2_raw_result.json":
        "c4306780b9911ef12ad5b49d04af1b1f4d934ba17cc5e246c735a75282188412",
}
CONFIG_FIELDS = (
    "schema_version",
    "amendment_id",
    "amendment_date",
    "status",
    "run_mode",
    "paper_result_eligible",
    "formal_experiment_run",
    "old_p2_run",
    "p1_run",
    "support_run",
    "k1_run",
    "protocol_amendment_relative_path",
    "old_p2_run_directory",
    "old_p2_immutable",
    "support_run_directory",
    "support_config_relative_path",
    "confirmation_prompt_frame",
    "vector_confirm_indices",
    "cells",
    "identity_count",
    "endpoint_order",
    "retry_policy",
    "generation_config",
    "judge_config",
    "output_root",
)
RESPONSE_FIELDS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible",
    "fake_backend", "logical_id", "identity_sha256", "generation_record_sha256",
    "judge_record_sha256", "cell", "prompt_id", "vector_id", "pair_id", "arm",
    "anchor", "estimator", "scheduled_identity_match", "generation_completed",
    "judge_eligible", "judge_label_parsed", "identity_complete", "identity_collision",
    "dose_denominator_valid", "dose_geometry_finite", "post_dtype_alpha_finite",
    "generation_terminal_status", "judge_terminal_status", "dose_evidence", "label",
    "terminal_status", "missingness_code", "retained", "record_sha256",
}


@dataclass(frozen=True)
class PreparedIndependentP2:
    """Validated amendment inputs and a new canonical 4,000-ID registry."""

    config_path: Path
    config: Mapping[str, Any]
    base: PreparedP2Runner
    registry: "IndependentLogicalIdentityRegistry"
    rows: tuple[Mapping[str, Any], ...]
    support_statuses: Mapping[str, str]
    offline_guard_report: Mapping[str, Any]


@dataclass(frozen=True)
class IndependentP2Artifacts:
    generation_records: tuple[Mapping[str, Any], ...]
    judge_records: tuple[Mapping[str, Any], ...]
    response_records: tuple[Mapping[str, Any], ...]
    dispositions: tuple[Mapping[str, Any], ...]
    ledger: Mapping[str, Any]
    behavior_lifecycle: Mapping[str, Any]
    judge_lifecycle: Mapping[str, Any]
    offline_guard_report: Mapping[str, Any]


def _exact_fields(value: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or tuple(value) != fields:
        raise PipelineError(f"{label} exact ordered fields mismatch")
    return dict(value)


def _resolve_repo_file(repo_root: Path, relative_value: Any, field: str) -> Path:
    if (
        not isinstance(relative_value, str)
        or not relative_value
        or "\\" in relative_value
        or "://" in relative_value
    ):
        raise PipelineError(f"{field} must be a local POSIX relative path")
    relative = PurePosixPath(relative_value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise PipelineError(f"{field} must remain below the repository root")
    root = repo_root.resolve()
    path = (root / Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PipelineError(f"{field} escapes the repository root") from exc
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"{field} is not a regular local file")
    return path


def validate_independent_config(config: Mapping[str, Any]) -> dict[str, Any]:
    actual = _exact_fields(config, CONFIG_FIELDS, "independent P2 config")
    expected = {
        "schema_version": "paper1-stage3-qwen25-p2-independent-th-v1",
        "amendment_id": AMENDMENT_ID,
        "amendment_date": AMENDMENT_DATE,
        "status": "independent_p2_runner_ready",
        "run_mode": "paper",
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "old_p2_run": False,
        "p1_run": False,
        "support_run": False,
        "k1_run": False,
        "protocol_amendment_relative_path": str(AMENDMENT.relative_to(ROOT)),
        "old_p2_run_directory": str(OLD_P2_RUN),
        "old_p2_immutable": True,
        "support_run_directory": str(SUPPORT_RUN),
        "support_config_relative_path": SUPPORT_CONFIG,
        "confirmation_prompt_frame": CONFIRM_FRAME,
        "vector_confirm_indices": list(VECTOR_INDICES),
        "cells": [
            {"cell": cell, "anchor": anchor, "estimator": estimator, "count": 1_000}
            for cell, anchor, estimator in CELLS
        ],
        "identity_count": IDENTITY_COUNT,
        "endpoint_order": [dict(endpoint) for endpoint in ENDPOINT_ORDER],
        "retry_policy": RETRY_POLICY,
        "generation_config": DECODE_CONFIG,
        "judge_config": JUDGE_CONFIG,
        "output_root": str(OUTPUT_ROOT),
    }
    for field, expected_value in expected.items():
        if actual[field] != expected_value or type(actual[field]) is not type(expected_value):
            raise PipelineError(f"independent P2 config {field} mismatch")
    return actual


def _validate_amendment(path: Path) -> None:
    if path.resolve() != AMENDMENT.resolve() or not path.is_file() or path.is_symlink():
        raise PipelineError("the fixed independent P2 amendment is missing")
    text = path.read_text(encoding="utf-8")
    required = (
        f"Amendment ID: `{AMENDMENT_ID}`",
        f"Amendment date: `{AMENDMENT_DATE}`",
        "FIXED PROSPECTIVELY BEFORE THE NEW RUN",
        "P2-U(T) = unsafe(all,T) - unsafe(content,T)",
        "P2-B(H) = broken(all,H) - broken(content,H)",
        str(OLD_P2_RUN) + "/",
    )
    if any(fragment not in text for fragment in required):
        raise PipelineError("the fixed independent P2 amendment content mismatch")


def _validate_old_p2_immutable() -> dict[str, str]:
    hashes = {**_OLD_P2_GIT_HASHES, **_OLD_P2_RESULT_HASHES}
    for path, expected in hashes.items():
        if not path.is_file() or path.is_symlink() or file_sha256(path) != expected:
            raise PipelineError(f"immutable old P2 file changed: {path}")
    return {str(path): expected for path, expected in hashes.items()}


def _canonical_float_hex(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise IdentityError(f"{field} must be a canonical finite float.hex value")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise IdentityError(f"{field} must be a canonical finite float.hex value") from exc
    if not math.isfinite(parsed) or parsed <= 0.0 or parsed.hex() != value:
        raise IdentityError(f"{field} must be a positive canonical float.hex value")
    return value


def normalize_independent_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(identity, Mapping) or set(identity) != set(IDENTITY_REQUIRED_FIELDS):
        raise IdentityError("independent P2 logical identity fields differ")
    actual = dict(identity)
    if actual["profile"] != ACTIVE_PROFILE or actual["block"] not in _CELL_RULES:
        raise IdentityError("independent P2 profile or cell is invalid")
    domain, split, estimator, anchor = _CELL_RULES[actual["block"]]
    if (
        actual["domain"], actual["split"], actual["estimator"], actual["anchor"]
    ) != (domain, split, estimator, anchor):
        raise IdentityError("independent P2 block/domain/split/estimator/anchor mapping changed")
    for field in (
        "model_revision", "prompt_id", "vector_id", "hook_site", "phase",
    ):
        if not isinstance(actual[field], str) or not actual[field]:
            raise IdentityError(f"independent P2 {field} must be nonempty")
    for field in (
        "template_sha256", "rendered_prompt_sha256", "generation_config_sha256",
        "code_sha256", "config_sha256", "environment_sha256",
    ):
        value = actual[field]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise IdentityError(f"independent P2 {field} must be lowercase SHA256")
    if (
        isinstance(actual["layer"], bool)
        or not isinstance(actual["layer"], int)
        or actual["layer"] < 0
        or actual["phase"] != "decode-only"
        or actual["use_cache"] is not True
    ):
        raise IdentityError("independent P2 runtime identity binding changed")
    for field in ("c_hex", "alpha_pre_dtype_hex", "alpha_post_dtype_hex", "rho_hex"):
        _canonical_float_hex(actual[field], field)
    return json.loads(canonical_json(actual))


class IndependentLogicalIdentityRegistry:
    """Collision-detecting canonical registry in a distinct amendment namespace."""

    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        self._canonical: set[str] = set()

    def register(self, identity: Mapping[str, Any]) -> str:
        normalized = normalize_independent_identity(identity)
        canonical = canonical_json(normalized)
        logical_id = "sha256:" + hashlib.sha256(
            ("paper1-stage3-p2-independent-th-logical-id-v1\n" + canonical).encode("utf-8")
        ).hexdigest()
        if canonical in self._canonical:
            raise IdentityError(f"duplicate independent P2 logical identity: {logical_id}")
        if logical_id in self._by_id:
            raise IdentityError(f"independent P2 logical identity hash collision: {logical_id}")
        self._canonical.add(canonical)
        self._by_id[logical_id] = normalized
        return logical_id

    def require(self, logical_id: str) -> dict[str, Any]:
        try:
            return dict(self._by_id[logical_id])
        except KeyError as exc:
            raise IdentityError(f"missing independent P2 logical identity: {logical_id}") from exc

    def records(self) -> list[dict[str, Any]]:
        return [
            {"logical_id": logical_id, "identity": dict(identity)}
            for logical_id, identity in self._by_id.items()
        ]

    def manifest(self) -> dict[str, Any]:
        records = self.records()
        return {
            "schema_version": "paper1-stage3-p2-independent-logical-registry-v1",
            "protocol_version": PROTOCOL_VERSION,
            "amendment_id": AMENDMENT_ID,
            "identity_count": len(records),
            "records": records,
            "registry_sha256": canonical_sha256(records),
        }

    def __len__(self) -> int:
        return len(self._by_id)


def build_independent_registry(
    base: PreparedP2Runner,
    *,
    config_path: Path,
    repo_root: Path = ROOT,
) -> IndependentLogicalIdentityRegistry:
    """Build T/H cells from canonical prompt, vector, binding, and dose inputs."""
    root = repo_root.resolve()
    bindings = dict(base.support.plan_inputs["bindings"])
    code_paths = (
        root / "stage3_pipeline/p2_independent_runner.py",
        root / "scripts/stage3_production/run_p2_independent.py",
    )
    if any(not path.is_file() or path.is_symlink() for path in code_paths):
        raise PipelineError("independent P2 runner code path is missing")
    bindings["code_sha256"] = canonical_sha256({
        str(path.relative_to(root)): file_sha256(path) for path in code_paths
    })
    bindings["config_sha256"] = file_sha256(config_path)
    prompts = list(base.support.plan_inputs["confirm_prompt_ids"])
    if len(prompts) != 50 or len(set(prompts)) != 50:
        raise IdentityError("independent P2 requires 50 canonical confirmation prompts")
    vector_ids = base.support.vector_ids_by_index
    if set(vector_ids) != set(range(30)):
        raise IdentityError("canonical vector registry must remain exactly 0..29")
    doses = validate_dose_binding(base.support.dose_binding)
    rendered = bindings["rendered_prompt_sha256_by_id"]
    registry = IndependentLogicalIdentityRegistry()
    for cell, anchor, estimator in CELLS:
        dose = doses[anchor][estimator]
        for prompt_id in prompts:
            if prompt_id not in rendered:
                raise IdentityError("canonical confirmation prompt lacks rendered identity")
            for vector_index in VECTOR_INDICES:
                identity = {
                    "profile": ACTIVE_PROFILE,
                    "block": cell,
                    "domain": "harmful",
                    "split": "D_behavior_confirm",
                    "model_revision": bindings["model_revision"],
                    "template_sha256": bindings["template_sha256"],
                    "rendered_prompt_sha256": rendered[prompt_id],
                    "prompt_id": prompt_id,
                    "vector_id": vector_ids[vector_index],
                    "estimator": estimator,
                    "anchor": anchor,
                    **dose,
                    "layer": bindings["layer"],
                    "hook_site": bindings["hook_site"],
                    "phase": "decode-only",
                    "use_cache": True,
                    "generation_config_sha256": bindings["generation_config_sha256"],
                    "code_sha256": bindings["code_sha256"],
                    "config_sha256": bindings["config_sha256"],
                    "environment_sha256": bindings["environment_sha256"],
                }
                registry.register(identity)
    validate_independent_registry(registry, base=base)
    return registry


def validate_independent_registry(
    registry: IndependentLogicalIdentityRegistry,
    *,
    base: PreparedP2Runner,
) -> dict[str, Any]:
    rows = registry.records()
    if len(registry) != IDENTITY_COUNT or len(rows) != IDENTITY_COUNT:
        raise IdentityError("independent P2 registry must contain exactly 4,000 identities")
    if len({row["logical_id"] for row in rows}) != IDENTITY_COUNT:
        raise IdentityError("independent P2 registry logical IDs are not unique")
    prompts = set(base.support.plan_inputs["confirm_prompt_ids"])
    vectors = {base.support.vector_ids_by_index[index] for index in VECTOR_INDICES}
    doses = validate_dose_binding(base.support.dose_binding)
    counts: dict[str, int] = {}
    matched_keys: dict[str, set[tuple[str, str]]] = {}
    for cell, anchor, estimator in CELLS:
        identities = [row["identity"] for row in rows if row["identity"]["block"] == cell]
        counts[cell] = len(identities)
        pairs = {(item["prompt_id"], item["vector_id"]) for item in identities}
        if (
            len(identities) != 1_000
            or {item["prompt_id"] for item in identities} != prompts
            or {item["vector_id"] for item in identities} != vectors
            or pairs != {(prompt, vector) for prompt in prompts for vector in vectors}
        ):
            raise IdentityError(f"{cell} differs from the fixed canonical 50x20 grid")
        expected_dose = doses[anchor][estimator]
        for identity in identities:
            if (
                identity["domain"] != "harmful"
                or identity["split"] != "D_behavior_confirm"
                or identity["anchor"] != anchor
                or identity["estimator"] != estimator
                or any(identity[field] != expected_dose[field] for field in expected_dose)
            ):
                raise IdentityError(f"{cell} identity or dose binding mismatch")
        matched_keys[cell] = pairs
    if counts != {cell: 1_000 for cell in BLOCKS}:
        raise IdentityError("independent P2 cell counts mismatch")
    if matched_keys["P2_T_all"] != matched_keys["P2_T_content"]:
        raise IdentityError("M_T arms do not share exact T prompt/vector keys")
    if matched_keys["P2_H_all"] != matched_keys["P2_H_content"]:
        raise IdentityError("M_H arms do not share exact H prompt/vector keys")
    old_ids = {row["logical_id"] for row in base.p2_rows}
    support_ids = {row["logical_id"] for row in base.support.support_rows}
    new_ids = {row["logical_id"] for row in rows}
    if new_ids & old_ids or new_ids & support_ids:
        raise IdentityError("independent identities collide with old P2 or support identities")
    h_vectors = {
        row["identity"]["vector_id"]
        for row in rows if row["identity"]["anchor"] == "H"
    }
    support_h_vectors = {
        row["identity"]["vector_id"]
        for row in base.support.support_rows if row["identity"]["anchor"] == "H"
    }
    if h_vectors & support_h_vectors:
        raise IdentityError("H confirmation vectors overlap the H support-screen vector frame")
    return {
        "identity_count": len(rows),
        "cell_identity_counts": counts,
        "endpoint_order": [dict(endpoint) for endpoint in ENDPOINT_ORDER],
        "matched_sets": {
            "M_T": {"anchor": "T", "pair_count": len(matched_keys["P2_T_all"])},
            "M_H": {"anchor": "H", "pair_count": len(matched_keys["P2_H_all"])},
        },
        "old_p2_logical_id_overlap": 0,
        "support_logical_id_overlap": 0,
    }


def prepare_independent_p2(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
    base_preparer: Callable[..., PreparedP2Runner] = prepare_p2_runner,
) -> PreparedIndependentP2:
    root = repo_root.resolve()
    resolved_config = config_path.resolve()
    config = validate_independent_config(
        _strict_json_object(resolved_config, "independent P2 config")
    )
    amendment = _resolve_repo_file(
        root, config["protocol_amendment_relative_path"], "protocol amendment"
    )
    _validate_amendment(amendment)
    _validate_old_p2_immutable()
    if (
        Path(config["old_p2_run_directory"]).resolve() != OLD_P2_RUN.resolve()
        or Path(config["support_run_directory"]).resolve() != SUPPORT_RUN.resolve()
        or config["support_config_relative_path"] != SUPPORT_CONFIG
        or config["confirmation_prompt_frame"] != CONFIRM_FRAME
    ):
        raise PipelineError("independent P2 fixed historical input binding mismatch")
    base = base_preparer(
        OLD_P2_CONFIG,
        repo_root=root,
        model_asset_inspector=model_asset_inspector,
        development_validator=development_validator,
    )
    statuses = {anchor: base.support_statuses[anchor] for anchor in ("T", "H")}
    if statuses != {"T": "SUPPORTED", "H": "SUPPORTED"}:
        raise PipelineError("fixed support run does not satisfy the T/H downstream prerequisite")
    guard = offline_execution_guard()
    with guard:
        registry = build_independent_registry(base, config_path=resolved_config, repo_root=root)
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("independent P2 validation attempted a forbidden offline operation")
    return PreparedIndependentP2(
        config_path=resolved_config,
        config=config,
        base=base,
        registry=registry,
        rows=tuple(registry.records()),
        support_statuses=statuses,
        offline_guard_report=guard_report,
    )


def validate_only(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    prepared = prepare_independent_p2(config_path)
    validation = validate_independent_registry(prepared.registry, base=prepared.base)
    immutable = _validate_old_p2_immutable()
    return {
        "status": "P2_INDEPENDENT_TH_VALIDATE_ONLY_PASS",
        "validate_only": True,
        "amendment_id": AMENDMENT_ID,
        "amendment_date": AMENDMENT_DATE,
        "model_weights_loaded": False,
        "gpu_used": False,
        "forward_executed": False,
        "generation_run": False,
        "judge_run": False,
        "formal_experiment_run": False,
        "paper_result_eligible": False,
        "old_p2_run": False,
        "p1_run": False,
        "support_run": False,
        "k1_run": False,
        "identity_count": validation["identity_count"],
        "cell_identity_counts": validation["cell_identity_counts"],
        "support_status": dict(prepared.support_statuses),
        "vector_confirm_indices": list(VECTOR_INDICES),
        "endpoint_order": validation["endpoint_order"],
        "matched_sets": validation["matched_sets"],
        "dose_binding_validated": True,
        "old_p2_logical_id_overlap": validation["old_p2_logical_id_overlap"],
        "support_logical_id_overlap": validation["support_logical_id_overlap"],
        "old_p2_immutable_files": immutable,
        "old_p2_write_target_count": 0,
        "output_root": str(OUTPUT_ROOT),
        "offline_guard_report": prepared.offline_guard_report,
    }


def _record_index(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    validator: Callable[[Mapping[str, Any]], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = validator(raw)
        logical_id = record.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in indexed:
            raise IdentityError(f"{label} contains a missing or duplicate logical ID")
        indexed[logical_id] = record
    return indexed


def _dose_flags(evidence: Mapping[str, Any]) -> dict[str, bool]:
    if evidence.get("status") == "VALIDATED" and evidence.get("failure_code") is None:
        return {
            "dose_denominator_valid": True,
            "dose_geometry_finite": True,
            "post_dtype_alpha_finite": True,
        }
    mapping = {
        "INVALID_DOSE_DENOMINATOR": (False, True, True),
        "INVALID_DOSE_GEOMETRY": (True, False, True),
        "INVALID_POST_DTYPE_ALPHA": (True, True, False),
    }
    try:
        denominator, geometry, alpha = mapping[evidence.get("failure_code")]
    except KeyError as exc:
        raise PipelineError("independent P2 dose evidence status is not canonical") from exc
    if evidence.get("status") != "INVALID":
        raise PipelineError("independent P2 invalid dose evidence lacks INVALID status")
    return {
        "dose_denominator_valid": denominator,
        "dose_geometry_finite": geometry,
        "post_dtype_alpha_finite": alpha,
    }


def _generation_terminal(status: str) -> str:
    try:
        return {
            "TERMINAL_TECHNICAL_FAILURE": "TERMINAL_GENERATION_TECHNICAL_FAILURE",
            "TERMINAL_FAILURE": "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
            "TERMINAL_INDETERMINATE_FAILURE": "TERMINAL_GENERATION_INDETERMINATE_FAILURE",
        }[status]
    except KeyError as exc:
        raise PipelineError("independent P2 generation terminal is invalid") from exc


def build_independent_response(
    *,
    identity: Mapping[str, Any],
    generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None,
    dose_binding: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = normalize_independent_identity(identity)
    generation = validate_generation_record(generation_record)
    identity_sha = canonical_sha256(normalized)
    if generation["identity_sha256"] != identity_sha:
        raise PipelineError("independent P2 generation identity lineage mismatch")
    judge = validate_judge_record(judge_record) if judge_record is not None else None
    if judge is not None and (
        not generation["generation_completed"]
        or judge["logical_id"] != generation["logical_id"]
        or judge["identity_sha256"] != identity_sha
        or judge["generation_record_sha256"] != generation["record_sha256"]
        or judge["domain"] != "harmful"
        or judge["run_mode"] != generation["run_mode"]
    ):
        raise PipelineError("independent P2 judge lineage mismatch")
    evidence = generation["attempts"][-1]["diagnostics"].get("dose_evidence")
    if not isinstance(evidence, Mapping):
        raise PipelineError("independent P2 terminal generation lacks dose evidence")
    flags = _dose_flags(evidence)
    dose_valid = all(flags.values())
    expected_failure = next((
        code for field, code in (
            ("dose_denominator_valid", "INVALID_DOSE_DENOMINATOR"),
            ("dose_geometry_finite", "INVALID_DOSE_GEOMETRY"),
            ("post_dtype_alpha_finite", "INVALID_POST_DTYPE_ALPHA"),
        ) if not flags[field]
    ), None)
    validate_dose_evidence(
        evidence,
        estimator=normalized["estimator"],
        generation_status=generation["terminal_status"],
        dose_valid=dose_valid,
        expected_failure_code=expected_failure,
    )
    doses = validate_dose_binding(dose_binding)
    expected_dose = doses[normalized["anchor"]][normalized["estimator"]]
    if any(normalized[field] != expected_dose[field] for field in expected_dose):
        raise PipelineError("independent P2 identity differs from bound dose")
    if (
        evidence["measurement_dose_sha256"] != canonical_sha256(dose_binding)
        or evidence["mu_estimator"] != normalized["estimator"]
        or evidence["mu_source_sha256"] != canonical_sha256(
            dose_binding[normalized["estimator"]]
        )
    ):
        raise PipelineError("independent P2 dose evidence provenance mismatch")
    parsed = judge is not None and judge["judge_label_parsed"]
    if not dose_valid:
        terminal = "NON_ESTIMABLE_DOSE"
    elif not generation["generation_completed"]:
        terminal = _generation_terminal(generation["terminal_status"])
    elif judge is None:
        terminal = "TERMINAL_PREJUDGE_FAILURE"
    elif not parsed:
        terminal = (
            "TERMINAL_JUDGE_INDETERMINATE_FAILURE"
            if judge["terminal_status"] == "TERMINAL_INDETERMINATE_FAILURE"
            else "TERMINAL_JUDGE_FAILURE"
        )
    else:
        terminal = "COMPLETED_PARSED"
    block = normalized["block"]
    record = {
        "schema_version": "paper1-stage3-p2-independent-response-v1",
        "protocol_version": PROTOCOL_VERSION,
        "run_mode": generation["run_mode"],
        "paper_result_eligible": False,
        "fake_backend": generation["fake_backend"] or (
            judge is not None and judge["fake_backend"]
        ),
        "logical_id": generation["logical_id"],
        "identity_sha256": identity_sha,
        "generation_record_sha256": generation["record_sha256"],
        "judge_record_sha256": None if judge is None else judge["record_sha256"],
        "cell": block,
        "prompt_id": normalized["prompt_id"],
        "vector_id": normalized["vector_id"],
        "pair_id": f"{normalized['anchor']}|{normalized['prompt_id']}|{normalized['vector_id']}",
        "arm": "all-token" if block.endswith("_all") else "content-token",
        "anchor": normalized["anchor"],
        "estimator": normalized["estimator"],
        "scheduled_identity_match": True,
        "generation_completed": generation["generation_completed"],
        "judge_eligible": judge is not None,
        "judge_label_parsed": parsed,
        "identity_complete": True,
        "identity_collision": False,
        **flags,
        "generation_terminal_status": generation["terminal_status"],
        "judge_terminal_status": None if judge is None else judge["terminal_status"],
        "dose_evidence": dict(evidence),
        "label": None if judge is None else judge["label"],
        "terminal_status": terminal,
        "missingness_code": None if terminal == "COMPLETED_PARSED" else terminal,
        "retained": terminal == "COMPLETED_PARSED",
    }
    record["record_sha256"] = canonical_sha256(record)
    return record


def validate_independent_response(
    record: Mapping[str, Any],
    *,
    registry: IndependentLogicalIdentityRegistry,
    generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None,
    dose_binding: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(record, Mapping) or set(record) != RESPONSE_FIELDS:
        raise PipelineError("independent P2 response fields differ")
    logical_id = record.get("logical_id")
    if not isinstance(logical_id, str) or not logical_id:
        raise IdentityError("independent P2 response lacks logical ID")
    identity = registry.require(logical_id)
    expected = build_independent_response(
        identity=identity,
        generation_record=generation_record,
        judge_record=judge_record,
        dose_binding=dose_binding,
    )
    if dict(record) != expected:
        raise PipelineError("independent P2 response differs from canonical lineage")
    return dict(record)


def _attempted_disposition(
    identity: Mapping[str, Any],
    generation: Mapping[str, Any],
    judge: Mapping[str, Any] | None,
    response: Mapping[str, Any],
) -> dict[str, Any]:
    return validate_execution_disposition({
        "schema_version": "paper1-stage3-execution-disposition-v2",
        "logical_id": generation["logical_id"],
        "identity_sha256": canonical_sha256(identity),
        "terminal_disposition": response_terminal_disposition(
            identity, response, generation, judge
        ),
        "generation_record_sha256": generation["record_sha256"],
        "judge_record_sha256": None if judge is None else judge["record_sha256"],
        "response_record_sha256": response["record_sha256"],
        "integrity_block_reason": None,
    })


def _aggregate_behavior_lifecycle(
    lifecycles: Sequence[Mapping[str, Any]], *, expected_sessions: int
) -> dict[str, Any]:
    if len(lifecycles) != expected_sessions:
        raise PipelineError("behavior lifecycle does not cover all independent P2 sessions")
    required = (
        "behavior_released", "behavior_hook_removed", "behavior_model_reference_cleared",
        "behavior_tokenizer_reference_cleared", "gc_collect_called",
    )
    if any(any(item.get(field) is not True for field in required) for item in lifecycles):
        raise PipelineError("an independent P2 behavior backend did not release completely")
    if any(item.get("models_concurrently_resident") is not False for item in lifecycles):
        raise PipelineError("independent P2 reported concurrent model residence")
    cuda_available = any(item.get("cuda_available") is True for item in lifecycles)
    return {
        "schema_version": "paper1-stage3-sequential-lifecycle-v1",
        "behavior_released": True,
        "behavior_hook_removed": True,
        "behavior_model_reference_cleared": True,
        "behavior_tokenizer_reference_cleared": True,
        "gc_collect_called": True,
        "gc_collected_count": sum(int(item.get("gc_collected_count", 0)) for item in lifecycles),
        "cuda_available": cuda_available,
        "cuda_synchronize_called": (
            all(item.get("cuda_synchronize_called") is True for item in lifecycles)
            if cuda_available else False
        ),
        "cuda_empty_cache_called": (
            all(item.get("cuda_empty_cache_called") is True for item in lifecycles)
            if cuda_available else False
        ),
        "judge_loaded_after_behavior_release": False,
        "models_concurrently_resident": False,
        "behavior_session_count": len(lifecycles),
    }


def load_real_behavior_backend(
    prepared: PreparedIndependentP2, vector_index: int
) -> Any:
    return load_old_p2_behavior_backend(prepared.base, vector_index)


def load_real_judge_backend(
    prepared: PreparedIndependentP2, lifecycle: Mapping[str, Any]
) -> Any:
    return load_old_p2_judge_backend(prepared.base, lifecycle)


def reconcile_independent_stage(
    prepared: PreparedIndependentP2,
    *,
    generation_records: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    expected_fake_backend: bool,
) -> dict[str, Any]:
    validate_independent_registry(prepared.registry, base=prepared.base)
    identities = {row["logical_id"]: row["identity"] for row in prepared.rows}
    if len(identities) != IDENTITY_COUNT:
        raise IdentityError("independent P2 prepared identity set is incomplete")
    generations = _record_index(
        generation_records, label="independent P2 generations", validator=validate_generation_record
    )
    judges = _record_index(
        judge_records, label="independent P2 judges", validator=validate_judge_record
    )
    responses = _record_index(
        response_records,
        label="independent P2 responses",
        validator=lambda record: dict(record) if isinstance(record, Mapping) else {},
    )
    disposition_by_id = _record_index(
        dispositions,
        label="independent P2 dispositions",
        validator=validate_execution_disposition,
    )
    identity_ids = set(identities)
    if set(generations) != identity_ids or set(responses) != identity_ids or set(disposition_by_id) != identity_ids:
        raise IdentityError("independent P2 generation/response/disposition identity set mismatch")
    expected_judges = {
        logical_id for logical_id, generation in generations.items()
        if generation["generation_completed"]
    }
    if set(judges) != expected_judges:
        raise IdentityError("independent P2 judge identity set mismatch")
    terminal_counts = {terminal: 0 for terminal in TERMINAL_DISPOSITIONS}
    retained_by_cell: dict[str, set[str]] = {cell: set() for cell in BLOCKS}
    for logical_id, identity in identities.items():
        generation = generations[logical_id]
        judge = judges.get(logical_id)
        response = validate_independent_response(
            responses[logical_id],
            registry=prepared.registry,
            generation_record=generation,
            judge_record=judge,
            dose_binding=prepared.base.support.dose_binding,
        )
        if (
            generation["logical_id"] != logical_id
            or generation["identity_sha256"] != canonical_sha256(identity)
            or generation["fake_backend"] is not expected_fake_backend
        ):
            raise IdentityError("independent P2 generation identity/backend mismatch")
        if judge is not None and judge["fake_backend"] is not expected_fake_backend:
            raise PipelineError("independent P2 judge backend mode mismatch")
        expected_disposition = _attempted_disposition(identity, generation, judge, response)
        if disposition_by_id[logical_id] != expected_disposition:
            raise PipelineError("independent P2 disposition differs from terminal lineage")
        terminal_counts[expected_disposition["terminal_disposition"]] += 1
        if response["retained"]:
            retained_by_cell[identity["block"]].add(response["pair_id"])
    if sum(terminal_counts.values()) != IDENTITY_COUNT:
        raise PipelineError("independent P2 terminal partition does not total 4,000")
    matched_sets = {
        "M_T": {
            "anchor": "T",
            "all_cell": "P2_T_all",
            "content_cell": "P2_T_content",
            "valid_pair_count": len(
                retained_by_cell["P2_T_all"] & retained_by_cell["P2_T_content"]
            ),
        },
        "M_H": {
            "anchor": "H",
            "all_cell": "P2_H_all",
            "content_cell": "P2_H_content",
            "valid_pair_count": len(
                retained_by_cell["P2_H_all"] & retained_by_cell["P2_H_content"]
            ),
        },
    }
    return {
        "schema_version": "paper1-stage3-p2-independent-th-ledger-v1",
        "amendment_id": AMENDMENT_ID,
        "stage": "P2_AMENDED_INDEPENDENT_TH",
        "run_mode": "paper",
        "fake_backend": expected_fake_backend,
        "paper_result_eligible": False,
        "formal_experiment_run": not expected_fake_backend,
        "old_p2_run": False,
        "p1_run": False,
        "support_run": False,
        "k1_run": False,
        "identity_count": IDENTITY_COUNT,
        "terminal_count": len(disposition_by_id),
        "cell_identity_counts": {cell: 1_000 for cell in BLOCKS},
        "endpoint_order": [dict(endpoint) for endpoint in ENDPOINT_ORDER],
        "matched_sets": matched_sets,
        "h_confirmation_generation_record_count": sum(
            identity["anchor"] == "H" for identity in identities.values()
        ),
        "h_confirmation_judge_record_count": sum(
            identities[logical_id]["anchor"] == "H" for logical_id in judges
        ),
        "generation_retry_count": sum(record["retry_count"] for record in generations.values()),
        "judge_retry_count": sum(len(record["attempts"]) - 1 for record in judges.values()),
        "terminal_partition": terminal_counts,
    }


def execute_independent_p2(
    prepared: PreparedIndependentP2,
    *,
    behavior_backend_factory: Callable[[PreparedIndependentP2, int], Any] = load_real_behavior_backend,
    judge_backend_factory: Callable[
        [PreparedIndependentP2, Mapping[str, Any]], Any
    ] = load_real_judge_backend,
) -> IndependentP2Artifacts:
    generation_by_id: dict[str, dict[str, Any]] = {}
    behavior_lifecycles: list[Mapping[str, Any]] = []
    backend_fake_flags: set[bool] = set()
    guard = offline_execution_guard()
    with guard:
        for vector_index in VECTOR_INDICES:
            expected_vector = prepared.base.support.vector_ids_by_index[vector_index]
            rows = [
                row for row in prepared.rows
                if row["identity"]["vector_id"] == expected_vector
            ]
            if len(rows) != 200 or {
                cell: sum(row["identity"]["block"] == cell for row in rows)
                for cell in BLOCKS
            } != {cell: 50 for cell in BLOCKS}:
                raise IdentityError("each independent P2 vector requires four 50-prompt cells")
            backend = behavior_backend_factory(prepared, vector_index)
            capability = getattr(backend, "capability", None)
            backend_fake_flags.add(capability is None)
            try:
                producer = GenerationProducer(
                    prepared.registry,  # type: ignore[arg-type]
                    backend,
                    run_mode="paper",
                    generation_config=DECODE_CONFIG,
                    fake_backend=capability is None,
                    capability=capability,
                )
                for row in rows:
                    logical_id = row["logical_id"]
                    identity = row["identity"]
                    if logical_id in generation_by_id:
                        raise IdentityError("independent P2 attempted an identity twice")
                    generation_by_id[logical_id] = validate_generation_record(
                        producer.produce(
                            logical_id,
                            {
                                "logical_id": logical_id,
                                "generation_config": DECODE_CONFIG,
                                "messages": prepared.base.support.messages_by_prompt_id[
                                    identity["prompt_id"]
                                ],
                            },
                        )
                    )
            finally:
                if not getattr(backend, "released", False):
                    behavior_lifecycles.append(backend.release())
        behavior_lifecycle = _aggregate_behavior_lifecycle(
            behavior_lifecycles, expected_sessions=len(VECTOR_INDICES)
        )
        if len(generation_by_id) != IDENTITY_COUNT:
            raise IdentityError("independent P2 behavior phase did not produce 4,000 records")

        judge_by_id: dict[str, dict[str, Any]] = {}
        judge_backend = judge_backend_factory(prepared, behavior_lifecycle)
        judge_capability = getattr(judge_backend, "capability", None)
        backend_fake_flags.add(judge_capability is None)
        try:
            producer_identity = getattr(judge_backend, "producer_identity", None)
            if not isinstance(producer_identity, Mapping):
                raise PipelineError("independent P2 judge lacks canonical producer identity")
            for row in prepared.rows:
                logical_id = row["logical_id"]
                generation = generation_by_id[logical_id]
                if not generation["generation_completed"]:
                    continue
                identity = row["identity"]
                judge_by_id[logical_id] = validate_judge_record(
                    parse_judge_with_retry(
                        logical_id,
                        judge_backend,
                        {
                            "logical_id": logical_id,
                            "judge_config": JUDGE_CONFIG,
                            "backend_request": {
                                "prompt": prepared.base.support.prompt_text_by_id[
                                    identity["prompt_id"]
                                ],
                                "response": generation["output_text"],
                                "domain": "harmful",
                            },
                        },
                        registry=prepared.registry,  # type: ignore[arg-type]
                        generation_record=generation,
                        run_mode="paper",
                        judge_identity=producer_identity,
                        judge_config=JUDGE_CONFIG,
                        fake_backend=judge_capability is None,
                        capability=judge_capability,
                    )
                )
        finally:
            judge_lifecycle = (
                judge_backend.release()
                if not getattr(judge_backend, "released", False)
                else {"judge_released": True}
            )
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("independent P2 execution attempted a forbidden offline operation")
    if len(backend_fake_flags) != 1:
        raise PipelineError("independent P2 mixes real and fake backend sessions")
    fake_backend = next(iter(backend_fake_flags))

    generations: list[dict[str, Any]] = []
    judges: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for row in prepared.rows:
        logical_id = row["logical_id"]
        identity = row["identity"]
        generation = generation_by_id[logical_id]
        judge = judge_by_id.get(logical_id)
        response = build_independent_response(
            identity=identity,
            generation_record=generation,
            judge_record=judge,
            dose_binding=prepared.base.support.dose_binding,
        )
        generations.append(generation)
        if judge is not None:
            judges.append(judge)
        responses.append(response)
        dispositions.append(_attempted_disposition(identity, generation, judge, response))
    ledger = reconcile_independent_stage(
        prepared,
        generation_records=generations,
        judge_records=judges,
        response_records=responses,
        dispositions=dispositions,
        expected_fake_backend=fake_backend,
    )
    return IndependentP2Artifacts(
        generation_records=tuple(generations),
        judge_records=tuple(judges),
        response_records=tuple(responses),
        dispositions=tuple(dispositions),
        ledger=ledger,
        behavior_lifecycle=behavior_lifecycle,
        judge_lifecycle=judge_lifecycle,
        offline_guard_report=guard_report,
    )


def default_output_directory(prepared: PreparedIndependentP2, run_id: str) -> Path:
    if not isinstance(run_id, str) or SAFE_RUN_ID.fullmatch(run_id) is None:
        raise PipelineError("independent P2 run-id contains invalid characters")
    configured_root = Path(prepared.config["output_root"]).resolve()
    if configured_root != OUTPUT_ROOT.resolve():
        raise PipelineError("independent P2 output root differs from the fixed paper root")
    output = configured_root / run_id
    if output.resolve() in {
        OLD_P2_RUN.resolve(), OLD_P2_MATERIALIZED.resolve(), SUPPORT_RUN.resolve()
    }:
        raise PipelineError("independent P2 output would overwrite a protected historical run")
    return output


def _reserve_output_directory(path: Path) -> Path:
    if path.exists() or path.is_symlink():
        raise PipelineError(f"refusing to overwrite output directory: {path}")
    output = path.resolve()
    for protected in (OLD_P2_RUN.resolve(), OLD_P2_MATERIALIZED.resolve(), SUPPORT_RUN.resolve()):
        if output == protected or protected in output.parents:
            raise PipelineError("independent P2 output resolves inside a protected historical run")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        raise PipelineError(f"refusing to overwrite output directory: {output}") from exc
    return output


def _record_document(schema_version: str, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "record_count": len(records),
        "records": list(records),
    }


def run_prepared_independent_p2(
    prepared: PreparedIndependentP2,
    *,
    run_id: str,
    behavior_backend_factory: Callable[[PreparedIndependentP2, int], Any] = load_real_behavior_backend,
    judge_backend_factory: Callable[
        [PreparedIndependentP2, Mapping[str, Any]], Any
    ] = load_real_judge_backend,
    output_directory_resolver: Callable[
        [PreparedIndependentP2, str], Path
    ] = default_output_directory,
) -> dict[str, Any]:
    output_directory = _reserve_output_directory(
        output_directory_resolver(prepared, run_id)
    )
    artifacts = execute_independent_p2(
        prepared,
        behavior_backend_factory=behavior_backend_factory,
        judge_backend_factory=judge_backend_factory,
    )
    store = OutputStore(output_directory)
    manifest = prepared.registry.manifest()
    store.write_json_once("logical_registry.json", manifest)
    store.write_json_once(
        "p2_independent_identities.json",
        _record_document("paper1-stage3-p2-independent-identity-set-v1", prepared.rows),
    )
    store.write_json_once(
        "generation_records.json",
        _record_document(
            "paper1-stage3-p2-independent-generation-set-v1", artifacts.generation_records
        ),
    )
    store.write_json_once(
        "judge_records.json",
        _record_document(
            "paper1-stage3-p2-independent-judge-set-v1", artifacts.judge_records
        ),
    )
    store.write_json_once(
        "response_records.json",
        _record_document(
            "paper1-stage3-p2-independent-response-set-v1", artifacts.response_records
        ),
    )
    store.write_json_once(
        "execution_dispositions.json",
        _record_document(
            "paper1-stage3-p2-independent-disposition-set-v1", artifacts.dispositions
        ),
    )
    store.write_json_once("p2_independent_ledger.json", artifacts.ledger)
    execution_identity = {
        "schema_version": "paper1-stage3-p2-independent-execution-v1",
        "amendment_id": AMENDMENT_ID,
        "run_id": run_id,
        "run_mode": "paper",
        "fake_backend": artifacts.ledger["fake_backend"],
        "paper_result_eligible": False,
        "formal_experiment_run": artifacts.ledger["formal_experiment_run"],
        "old_p2_run": False,
        "p1_run": False,
        "support_run": False,
        "k1_run": False,
        "support_run_id": prepared.base.support_execution_identity["run_id"],
        "old_p2_run_directory": str(OLD_P2_RUN),
        "canonical_registry_sha256": manifest["registry_sha256"],
        "ledger_sha256": canonical_sha256(artifacts.ledger),
        "runner_code_sha256": file_sha256(Path(__file__).resolve()),
        "config_sha256": file_sha256(prepared.config_path),
        "amendment_sha256": file_sha256(AMENDMENT),
        "behavior_lifecycle": artifacts.behavior_lifecycle,
        "judge_lifecycle": artifacts.judge_lifecycle,
        "offline_guard_report": artifacts.offline_guard_report,
    }
    store.write_json_once("execution_identity.json", execution_identity)
    fake_backend = artifacts.ledger["fake_backend"]
    return {
        "status": (
            "P2_INDEPENDENT_TH_FAKE_PATH_PASS"
            if fake_backend else "P2_INDEPENDENT_TH_REAL_RUN_PASS"
        ),
        "output_directory": str(output_directory),
        "run_id": run_id,
        "run_mode": "paper",
        "identity_count": IDENTITY_COUNT,
        "terminal_count": artifacts.ledger["terminal_count"],
        "support_status": dict(prepared.support_statuses),
        "endpoint_order": [dict(endpoint) for endpoint in ENDPOINT_ORDER],
        "fake_backend": fake_backend,
        "formal_experiment_run": not fake_backend,
        "paper_result_eligible": False,
        "old_p2_run": False,
        "p1_run": False,
        "support_run": False,
        "k1_run": False,
    }


def run_independent_p2(
    config_path: Path,
    *,
    run_mode: str,
    run_id: str,
) -> dict[str, Any]:
    if run_mode != "paper":
        raise PipelineError("independent P2 execution requires run_mode=paper")
    prepared = prepare_independent_p2(config_path)
    return run_prepared_independent_p2(prepared, run_id=run_id)


__all__ = [
    "AMENDMENT_ID",
    "BLOCKS",
    "CELLS",
    "DEFAULT_CONFIG",
    "ENDPOINT_ORDER",
    "IDENTITY_COUNT",
    "IndependentLogicalIdentityRegistry",
    "PreparedIndependentP2",
    "build_independent_registry",
    "build_independent_response",
    "default_output_directory",
    "execute_independent_p2",
    "prepare_independent_p2",
    "reconcile_independent_stage",
    "run_independent_p2",
    "run_prepared_independent_p2",
    "validate_independent_config",
    "validate_independent_registry",
    "validate_independent_response",
    "validate_only",
]
