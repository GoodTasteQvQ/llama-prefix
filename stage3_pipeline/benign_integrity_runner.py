"""Paper 1 Stage 3 benign integrity runner.

This module only prepares and reconciles the fixed 630 benign identities.  It
does not materialize statistics, bootstrap results, or any other Stage 3 stage.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from scripts.stage3_production.validate_stage3_development_inputs import (
    _strict_json_object,
    validate_development_inputs,
)

from .core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    JUDGE_LABELS,
    PAPER_LOGICAL_GENERATION,
    GenerationProducer,
    IdentityError,
    LogicalIdentityRegistry,
    PipelineError,
    VerifiedBackendCapability,
    canonical_sha256,
    classify_support,
    file_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
)
from .dose import validate_dose_binding
from .execution import TERMINAL_DISPOSITIONS, OutputStore, response_terminal_disposition, validate_execution_disposition
from .offline_assets import strict_json_loads
from .real_backend import RealBehaviorBackend, inspect_local_model_assets
from .real_judge import RealJudgeBackend
from .records import (
    RecordSchemaError,
    build_block_response_record,
    validate_benign_materialization,
    validate_benign_record,
    validate_generation_record,
    validate_judge_record,
)
from .support_screen import (
    DEFAULT_CONFIG as SUPPORT_CONFIG,
    PreparedSupportScreen,
    load_real_behavior_backend as load_support_behavior_backend,
    load_real_judge_backend as load_support_judge_backend,
    prepare_support_screen,
    reconcile_support_stage,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/stage3/qwen25_benign_integrity_v1.json"
OUTPUT_ROOT = Path("/data/goodtaste_workspace/paper1_stage3_runs")
P1_DOSE_PATH = Path("/data/goodtaste_workspace/paper1_stage3_runs/p1-qwen25-paper-20260807T044847Z/p1_measurement_result.json")
SUPPORT_RUN_PATH = Path("/data/goodtaste_workspace/paper1_stage3_runs/support-qwen25-paper-detached-20260807T133730Z")
VECTOR_INDICES = tuple(range(10, 30))
BENIGN_T_COUNT = 600
BENIGN_CLEAN_COUNT = 30
BENIGN_COUNT = 630
ZERO_HEX = float(0.0).hex()
SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
OUTPUT_FILES = frozenset({
    "canonical_registry_reference.json",
    "benign_integrity_identities.json",
    "generation_records.json",
    "judge_records.json",
    "response_records.json",
    "execution_dispositions.json",
    "benign_integrity_ledger.json",
    "execution_identity.json",
})
CONFIG_FIELDS = (
    "schema_version", "status", "run_mode", "paper_result_eligible", "formal_experiment_run",
    "canonical_plan_count", "benign_identity_count", "benign_T_identity_count",
    "benign_clean_identity_count", "support_config_relative_path",
    "benign_prompt_frame_relative_path", "p1_dose_binding_path", "support_run_path",
    "vector_indices", "identities", "generation_config", "judge_config", "judge_domain",
    "judge_labels", "output_root",
)


@dataclass(frozen=True)
class PreparedBenignIntegrity:
    config_path: Path
    config: Mapping[str, Any]
    support: PreparedSupportScreen
    benign_T_rows: tuple[Mapping[str, Any], ...]
    benign_clean_rows: tuple[Mapping[str, Any], ...]
    p1_result: Mapping[str, Any]
    support_validation: Mapping[str, Any]
    offline_guard_report: Mapping[str, Any]


@dataclass(frozen=True)
class BenignIntegrityRunArtifacts:
    generation_records: tuple[Mapping[str, Any], ...]
    judge_records: tuple[Mapping[str, Any], ...]
    response_records: tuple[Mapping[str, Any], ...]
    dispositions: tuple[Mapping[str, Any], ...]
    benign_integrity_ledger: Mapping[str, Any]
    behavior_lifecycle: Mapping[str, Any]
    judge_lifecycle: Mapping[str, Any]
    offline_guard_report: Mapping[str, Any]


def _exact_fields(value: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or tuple(value) != fields:
        raise PipelineError(f"{label} exact ordered fields mismatch")
    return dict(value)


def validate_benign_integrity_config(config: Mapping[str, Any]) -> dict[str, Any]:
    actual = _exact_fields(config, CONFIG_FIELDS, "benign-integrity config")
    expected = {
        "schema_version": "paper1-stage3-qwen25-benign-integrity-v1",
        "status": "benign_integrity_runner_ready", "run_mode": "paper",
        "paper_result_eligible": False, "formal_experiment_run": False,
        "canonical_plan_count": PAPER_LOGICAL_GENERATION, "benign_identity_count": BENIGN_COUNT,
        "benign_T_identity_count": BENIGN_T_COUNT, "benign_clean_identity_count": BENIGN_CLEAN_COUNT,
        "support_config_relative_path": "configs/stage3/qwen25_support_screen_v1.json",
        "benign_prompt_frame_relative_path": "configs/stage3/benign_confirm_v1.json",
        "p1_dose_binding_path": str(P1_DOSE_PATH), "support_run_path": str(SUPPORT_RUN_PATH),
        "vector_indices": list(VECTOR_INDICES), "generation_config": DECODE_CONFIG,
        "judge_config": JUDGE_CONFIG, "judge_domain": "benign",
        "judge_labels": list(JUDGE_LABELS["benign"]), "output_root": str(OUTPUT_ROOT),
    }
    for field, expected_value in expected.items():
        if actual[field] != expected_value or type(actual[field]) is not type(expected_value):
            raise PipelineError(f"benign-integrity config {field} mismatch")
    expected_identities = {
        "benign_T": {"block": "benign_T", "domain": "benign", "split": "D_benign_confirm", "prompt_count": 30, "vector_count": 20, "anchor": "T", "estimator": "mu_all_tw"},
        "benign_clean": {"block": "benign_clean", "domain": "benign", "split": "D_benign_confirm", "prompt_count": 30, "vector_count": 0, "anchor": "clean", "estimator": "clean", "vector_id": None},
    }
    if actual["identities"] != expected_identities:
        raise PipelineError("benign-integrity identity declaration mismatch")
    return actual


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = strict_json_loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PipelineError(f"unable to read strict {label}: {path}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"{label} must be an object")
    return value


def _read_document(root: Path, name: str, label: str) -> list[dict[str, Any]]:
    document = _load_json(root / name, label)
    records = document.get("records")
    if not isinstance(records, list) or document.get("record_count") != len(records):
        raise PipelineError(f"{label} record document count mismatch")
    return records


def _load_p1_dose(path: Path) -> dict[str, Any]:
    result = _load_json(path, "P1 dose binding result")
    if result.get("schema_version") != "paper1-stage3-p1-result-materialization-v1" or result.get("status") != "ESTIMABLE":
        raise PipelineError("P1 dose binding result is not the fixed ESTIMABLE asset")
    dose = result.get("dose_binding")
    validate_dose_binding(dose)
    return result


def _dose_fingerprint(value: Any) -> Any:
    """Compare JSON numeric spellings by their binary64 value, not 61 vs 61.0."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value).hex()
    if isinstance(value, Mapping):
        return {str(key): _dose_fingerprint(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_dose_fingerprint(item) for item in value]
    return value


def _validate_support_asset(
    prepared_support: PreparedSupportScreen,
    support_root: Path,
) -> dict[str, Any]:
    if not support_root.is_dir() or support_root.is_symlink():
        raise PipelineError("fixed support run directory is missing or linked")
    registry = _load_json(support_root / "logical_registry.json", "support logical registry")
    expected_manifest = prepared_support.registry.manifest()
    if registry != expected_manifest:
        raise PipelineError("fixed support run registry lineage differs from canonical registry")
    support_rows = _read_document(support_root, "support_identities.json", "support identities")
    expected_support = prepared_support.support_rows
    if support_rows != list(expected_support):
        raise PipelineError("fixed support run identity lineage differs from canonical support rows")
    generations = _read_document(support_root, "generation_records.json", "support generations")
    judges = _read_document(support_root, "judge_records.json", "support judges")
    responses = _read_document(support_root, "response_records.json", "support responses")
    dispositions = _read_document(support_root, "execution_dispositions.json", "support dispositions")
    ledger = reconcile_support_stage(
        prepared_support, generation_records=generations, judge_records=judges,
        response_records=responses, dispositions=dispositions,
    )
    stored_ledger = _load_json(support_root / "support_ledger.json", "support ledger")
    if stored_ledger != ledger:
        raise PipelineError("fixed support ledger differs from independently recomputed support ledger")
    if ledger["fake_backend"] is not False:
        raise PipelineError("fixed support run must have real backend provenance")
    execution = _load_json(support_root / "execution_identity.json", "support execution identity")
    if (
        execution.get("canonical_registry_sha256") != expected_manifest["registry_sha256"]
        or execution.get("support_ledger_sha256") != canonical_sha256(stored_ledger)
        or execution.get("fake_backend") is not False
        or execution.get("real_support_run") is not True
    ):
        raise PipelineError("fixed support execution identity registry lineage mismatch")
    return {"ledger": ledger, "execution_identity": execution}


def select_benign_identities(
    support: PreparedSupportScreen,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    if len(support.registry) != PAPER_LOGICAL_GENERATION:
        raise IdentityError("benign selection requires the complete 5,580-ID registry")
    prompts = list(support.plan_inputs["benign_prompt_ids"])
    vectors = {support.vector_ids_by_index[index] for index in VECTOR_INDICES}
    rows_by_block = {
        block: [row for row in support.registry.records() if row["identity"]["block"] == block]
        for block in ("benign_T", "benign_clean")
    }
    if len(prompts) != 30 or len(set(prompts)) != 30:
        raise IdentityError("benign prompt frame must contain 30 unique ordered prompts")
    t_by_pair = {(row["identity"]["prompt_id"], row["identity"]["vector_id"]): row for row in rows_by_block["benign_T"]}
    if len(rows_by_block["benign_T"]) != BENIGN_T_COUNT or len(t_by_pair) != BENIGN_T_COUNT:
        raise IdentityError("benign_T selection is not exactly 30x20")
    if set(t_by_pair) != {(prompt, vector) for prompt in prompts for vector in vectors}:
        raise IdentityError("benign_T identities are not the complete prompt/vector Cartesian product")
    t_rows = tuple(
        t_by_pair[(prompt, support.vector_ids_by_index[index])]
        for prompt in prompts
        for index in VECTOR_INDICES
    )
    clean_by_prompt = {row["identity"]["prompt_id"]: row for row in rows_by_block["benign_clean"]}
    if len(clean_by_prompt) != BENIGN_CLEAN_COUNT or set(clean_by_prompt) != set(prompts):
        raise IdentityError("benign_clean selection is not the same 30 prompts exactly once")
    clean_rows = tuple(clean_by_prompt[prompt] for prompt in prompts)
    doses = validate_dose_binding(support.dose_binding)
    expected_t = doses["T"]["mu_all_tw"]
    for row in t_rows:
        identity = row["identity"]
        if (identity["block"], identity["domain"], identity["split"], identity["anchor"], identity["estimator"]) != ("benign_T", "benign", "D_benign_confirm", "T", "mu_all_tw"):
            raise IdentityError("benign_T identity fields changed")
        for field in ("c_hex", "alpha_pre_dtype_hex", "alpha_post_dtype_hex", "rho_hex"):
            if identity[field] != expected_t[field]:
                raise IdentityError("benign_T identity is not bound to P1 T/mu_all_tw dose")
    for row in clean_rows:
        identity = row["identity"]
        if identity["block"] != "benign_clean" or identity["domain"] != "benign" or identity["split"] != "D_benign_confirm" or identity["vector_id"] is not None or identity["anchor"] != "clean" or identity["estimator"] != "clean":
            raise IdentityError("benign_clean identity fields changed")
        if any(identity[field] != ZERO_HEX for field in ("c_hex", "alpha_pre_dtype_hex", "alpha_post_dtype_hex", "rho_hex")):
            raise IdentityError("benign_clean identities require all-zero dose fields")
    return t_rows, clean_rows


def prepare_benign_integrity(
    config_path: Path = DEFAULT_CONFIG,
    *, repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> PreparedBenignIntegrity:
    root = repo_root.resolve()
    resolved_config = config_path.resolve()
    config = validate_benign_integrity_config(_strict_json_object(resolved_config, "benign-integrity config"))
    support_config_path = (root / Path(*PurePosixPath(config["support_config_relative_path"]).parts)).resolve()
    if not support_config_path.is_file() or support_config_path.is_symlink():
        raise PipelineError("support config is missing")
    p1_path = Path(config["p1_dose_binding_path"]).resolve()
    support_root = Path(config["support_run_path"]).resolve()
    guard = offline_execution_guard()
    with guard:
        support = prepare_support_screen(support_config_path, repo_root=root, model_asset_inspector=model_asset_inspector, development_validator=development_validator)
        p1_result = _load_p1_dose(p1_path)
        if _dose_fingerprint(p1_result["dose_binding"]) != _dose_fingerprint(support.dose_binding):
            raise PipelineError("P1 dose binding differs from canonical support preparation binding")
        support_validation = _validate_support_asset(support, support_root)
        statuses = {anchor: support_validation["ledger"]["anchors"][anchor]["status"] for anchor in ("A", "T", "H")}
        if statuses["T"] != "SUPPORTED":
            raise PipelineError("fixed support run independently recomputed T is not SUPPORTED")
        benign_T_rows, benign_clean_rows = select_benign_identities(support)
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("benign preparation attempted a forbidden offline operation")
    return PreparedBenignIntegrity(resolved_config, config, support, benign_T_rows, benign_clean_rows, p1_result, support_validation, guard_report)


def validate_only(
    config_path: Path = DEFAULT_CONFIG,
    *, repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> dict[str, Any]:
    prepared = prepare_benign_integrity(config_path, repo_root=repo_root, model_asset_inspector=model_asset_inspector, development_validator=development_validator)
    manifest = prepared.support.registry.manifest()
    return {
        "schema_version": "paper1-stage3-benign-integrity-validation-v1",
        "status": "BENIGN_INTEGRITY_RUNNER_VALIDATE_ONLY_PASS",
        "validate_only": True, "run_mode": "paper", "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": manifest["registry_sha256"], "benign_identity_count": BENIGN_COUNT,
        "benign_T_identity_count": len(prepared.benign_T_rows), "benign_clean_identity_count": len(prepared.benign_clean_rows),
        "vector_indices": list(VECTOR_INDICES), "t_support": "SUPPORTED", "dose_binding_validated": True,
        "model_weights_loaded": False, "gpu_used": False, "forward_executed": False,
        "generation_run": False, "judge_run": False, "output_written": False,
        "network_attempts": prepared.offline_guard_report["category_counts"]["network"],
        "blocked_attempts": prepared.offline_guard_report["blocked_attempt_count"],
        "formal_experiment_run": False, "paper_result_eligible": False,
        "p1_run": False, "support_run": False, "p2_run": False, "k1_run": False,
        "bootstrap_run": False, "complete_stage3_reconciliation": False,
        "offline_guard_report": prepared.offline_guard_report,
    }


def _require_capability(backend: Any, role: str) -> VerifiedBackendCapability:
    capability = getattr(backend, "capability", None)
    expected = "RealBehaviorBackend" if role == "behavior" else "RealJudgeBackend"
    if not isinstance(capability, VerifiedBackendCapability) or capability.role != role or not capability.matches_backend_instance(backend):
        raise PipelineError(f"paper benign-integrity requires {expected} capability")
    return capability


def load_real_behavior_backend(prepared: PreparedBenignIntegrity, vector_index: int) -> RealBehaviorBackend:
    return load_support_behavior_backend(prepared.support, vector_index)


def load_real_judge_backend(prepared: PreparedBenignIntegrity, lifecycle: Mapping[str, Any]) -> RealJudgeBackend:
    return load_support_judge_backend(prepared.support, lifecycle)


def _aggregate_lifecycle(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(items) != len(VECTOR_INDICES):
        raise PipelineError("behavior lifecycle must cover vector indices 10..29")
    required = ("behavior_released", "behavior_hook_removed", "behavior_model_reference_cleared", "behavior_tokenizer_reference_cleared", "gc_collect_called")
    if any(any(item.get(field) is not True for field in required) for item in items) or any(item.get("models_concurrently_resident") is not False for item in items):
        raise PipelineError("behavior lifecycle release evidence is incomplete")
    cuda = any(item.get("cuda_available") is True for item in items)
    return {
        "schema_version": "paper1-stage3-sequential-lifecycle-v1", "behavior_released": True,
        "behavior_hook_removed": True, "behavior_model_reference_cleared": True,
        "behavior_tokenizer_reference_cleared": True, "gc_collect_called": True,
        "gc_collected_count": sum(int(item.get("gc_collected_count", 0)) for item in items),
        "cuda_available": cuda,
        "cuda_synchronize_called": all(item.get("cuda_synchronize_called") is True for item in items) if cuda else False,
        "cuda_empty_cache_called": all(item.get("cuda_empty_cache_called") is True for item in items) if cuda else False,
        "judge_loaded_after_behavior_release": False, "models_concurrently_resident": False,
        "behavior_session_count": len(items), "vector_indices": list(VECTOR_INDICES),
    }


def _disposition(identity: Mapping[str, Any], generation: Mapping[str, Any], judge: Mapping[str, Any] | None, response: Mapping[str, Any]) -> dict[str, Any]:
    return validate_execution_disposition({
        "schema_version": "paper1-stage3-execution-disposition-v2", "logical_id": generation["logical_id"],
        "identity_sha256": canonical_sha256(identity),
        "terminal_disposition": response_terminal_disposition(identity, response, generation, judge),
        "generation_record_sha256": generation["record_sha256"],
        "judge_record_sha256": None if judge is None else judge["record_sha256"],
        "response_record_sha256": response["record_sha256"], "integrity_block_reason": None,
    })


def execute_benign_integrity(
    prepared: PreparedBenignIntegrity, *,
    behavior_backend_factory: Callable[[PreparedBenignIntegrity, int], Any] = load_real_behavior_backend,
    judge_backend_factory: Callable[[PreparedBenignIntegrity, Mapping[str, Any]], Any] = load_real_judge_backend,
    require_real_backend: bool = True,
) -> BenignIntegrityRunArtifacts:
    if type(require_real_backend) is not bool:
        raise PipelineError("require_real_backend must be boolean")
    generation_by_id: dict[str, dict[str, Any]] = {}
    lifecycles: list[Mapping[str, Any]] = []
    fake_flags: set[bool] = set()
    guard = offline_execution_guard()
    with guard:
        for vector_index in VECTOR_INDICES:
            backend = behavior_backend_factory(prepared, vector_index)
            capability = getattr(backend, "capability", None)
            fake_flags.add(capability is None)
            try:
                if require_real_backend:
                    capability = _require_capability(backend, "behavior")
                producer = GenerationProducer(prepared.support.registry, backend, run_mode="paper", generation_config=DECODE_CONFIG, fake_backend=capability is None, capability=capability, item_budget=PAPER_LOGICAL_GENERATION)
                rows = [row for row in prepared.benign_T_rows if prepared.support.vector_index_by_id[row["identity"]["vector_id"]] == vector_index]
                if vector_index == VECTOR_INDICES[0]:
                    rows = list(prepared.benign_clean_rows) + rows
                expected = BENIGN_CLEAN_COUNT + 30 if vector_index == VECTOR_INDICES[0] else 30
                if len(rows) != expected:
                    raise IdentityError("benign vector session row count differs from the fixed schedule")
                for row in rows:
                    logical_id, identity = row["logical_id"], row["identity"]
                    request = {"logical_id": logical_id, "generation_config": DECODE_CONFIG, "messages": prepared.support.messages_by_prompt_id[identity["prompt_id"]]}
                    generation_by_id[logical_id] = validate_generation_record(producer.produce(logical_id, request))
            finally:
                lifecycle = backend.release() if not getattr(backend, "released", False) else {"behavior_released": True, "models_concurrently_resident": False}
                lifecycles.append(lifecycle)
        behavior_lifecycle = _aggregate_lifecycle(lifecycles)
        judge_backend = judge_backend_factory(prepared, behavior_lifecycle)
        judge_capability = getattr(judge_backend, "capability", None)
        fake_flags.add(judge_capability is None)
        judge_by_id: dict[str, dict[str, Any]] = {}
        try:
            if require_real_backend:
                judge_capability = _require_capability(judge_backend, "judge")
            producer_identity = getattr(judge_backend, "producer_identity", None)
            if not isinstance(producer_identity, Mapping):
                raise PipelineError("judge backend lacks canonical producer identity")
            for row in (*prepared.benign_T_rows, *prepared.benign_clean_rows):
                logical_id, identity = row["logical_id"], row["identity"]
                generation = generation_by_id[logical_id]
                if not generation["generation_completed"]:
                    continue
                judge_by_id[logical_id] = validate_judge_record(parse_judge_with_retry(
                    logical_id, judge_backend,
                    {"logical_id": logical_id, "judge_config": JUDGE_CONFIG, "backend_request": {"prompt": prepared.support.prompt_text_by_id[identity["prompt_id"]], "response": generation["output_text"], "domain": "benign"}},
                    registry=prepared.support.registry, generation_record=generation, run_mode="paper", judge_identity=producer_identity, judge_config=JUDGE_CONFIG, fake_backend=judge_capability is None, capability=judge_capability,
                ))
        finally:
            judge_lifecycle = judge_backend.release() if not getattr(judge_backend, "released", False) else {"judge_released": True, "models_concurrently_resident": False}
        if (
            not isinstance(judge_lifecycle, Mapping)
            or judge_lifecycle.get("judge_released") is not True
            or judge_lifecycle.get("models_concurrently_resident") is not False
            or judge_lifecycle.get("judge_loaded_after_behavior_release") is not True
        ):
            raise PipelineError("judge lifecycle does not prove post-behavior loading and release")
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("benign execution attempted a forbidden offline operation")
    if len(fake_flags) != 1:
        raise PipelineError("benign execution mixes fake and real backend provenance")
    fake_backend = fake_flags.pop()
    generations, judges, responses, dispositions = [], [], [], []
    ordered_rows = (*prepared.benign_T_rows, *prepared.benign_clean_rows)
    for row in ordered_rows:
        logical_id, identity = row["logical_id"], row["identity"]
        generation, judge = generation_by_id[logical_id], judge_by_id.get(logical_id)
        dose = None if identity["block"] == "benign_clean" else generation["attempts"][-1]["diagnostics"].get("dose_evidence")
        response = build_block_response_record(identity=identity, generation_record=generation, judge_record=judge, dose_evidence=dose)
        validate_benign_materialization(response, registry=prepared.support.registry, generation_record=generation, judge_record=judge, dose_binding=prepared.support.dose_binding)
        generations.append(generation)
        if judge is not None: judges.append(judge)
        responses.append(response)
        dispositions.append(_disposition(identity, generation, judge, response))
    ledger = reconcile_benign_integrity(prepared, generation_records=generations, judge_records=judges, response_records=responses, dispositions=dispositions, expected_fake_backend=fake_backend)
    return BenignIntegrityRunArtifacts(tuple(generations), tuple(judges), tuple(responses), tuple(dispositions), ledger, behavior_lifecycle, judge_lifecycle, guard_report)


def _index(records: Sequence[Mapping[str, Any]], validator: Callable[[Mapping[str, Any]], dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = validator(raw)
        logical_id = record.get("logical_id")
        if not isinstance(logical_id, str) or logical_id in result:
            raise IdentityError(f"{label} contains a missing or duplicate logical ID")
        result[logical_id] = record
    return result


def reconcile_benign_integrity(
    prepared: PreparedBenignIntegrity, *, generation_records: Sequence[Mapping[str, Any]], judge_records: Sequence[Mapping[str, Any]], response_records: Sequence[Mapping[str, Any]], dispositions: Sequence[Mapping[str, Any]], expected_fake_backend: bool | None = None,
) -> dict[str, Any]:
    if expected_fake_backend is not None and type(expected_fake_backend) is not bool:
        raise PipelineError("expected_fake_backend must be boolean or omitted")
    rows = (*prepared.benign_T_rows, *prepared.benign_clean_rows)
    identity_by_id = {row["logical_id"]: row["identity"] for row in rows}
    if len(identity_by_id) != BENIGN_COUNT:
        raise IdentityError("benign reconciliation requires exactly 630 canonical identities")
    generations = _index(generation_records, validate_generation_record, "benign generation set")
    judges = _index(judge_records, validate_judge_record, "benign judge set")
    responses = _index(response_records, validate_benign_record, "benign response set")
    disposition_by_id = _index(dispositions, validate_execution_disposition, "benign disposition set")
    ids = set(identity_by_id)
    if set(generations) != ids or set(responses) != ids or set(disposition_by_id) != ids:
        raise IdentityError("benign generation/response/disposition sets must cover exactly 630 IDs")
    completed = {logical_id for logical_id, generation in generations.items() if generation["generation_completed"]}
    if set(judges) != completed:
        raise IdentityError("benign judges must equal completed generations")
    terminal_counts = {terminal: 0 for terminal in TERMINAL_DISPOSITIONS}
    fake_flags: set[bool] = set(); generation_retries = judge_retries = generation_completed = judge_parsed = 0
    dose_count = clean_dose_count = 0
    validated_responses: dict[str, dict[str, Any]] = {}
    for logical_id, identity in identity_by_id.items():
        generation, judge = generations[logical_id], judges.get(logical_id)
        try:
            response = validate_benign_materialization(responses[logical_id], registry=prepared.support.registry, generation_record=generation, judge_record=judge, dose_binding=prepared.support.dose_binding)
        except RecordSchemaError as exc:
            raise PipelineError("benign response materialization failed") from exc
        disposition = disposition_by_id[logical_id]
        terminal = response_terminal_disposition(identity, response, generation, judge)
        if response["identity_sha256"] != canonical_sha256(identity) or disposition["identity_sha256"] != canonical_sha256(identity) or disposition["terminal_disposition"] != terminal or disposition["generation_record_sha256"] != generation["record_sha256"] or disposition["judge_record_sha256"] != (None if judge is None else judge["record_sha256"]) or disposition["response_record_sha256"] != response["record_sha256"] or disposition["integrity_block_reason"] is not None:
            raise PipelineError("benign lineage differs across generation/judge/response/disposition")
        terminal_counts[terminal] += 1; generation_completed += int(generation["generation_completed"]); generation_retries += generation["retry_count"]
        if judge is not None: judge_parsed += int(judge["judge_label_parsed"]); judge_retries += len(judge["attempts"]) - 1
        fake_flags.update({generation["fake_backend"], response["fake_backend"]});
        if judge is not None: fake_flags.add(judge["fake_backend"])
        if identity["block"] == "benign_clean":
            if response["dose_evidence"] is not None or "dose_evidence" in generation["attempts"][-1]["diagnostics"]: raise PipelineError("benign_clean contains dose evidence")
            clean_dose_count += int(response["dose_evidence"] is not None)
        else:
            if response["dose_evidence"] is None or "dose_evidence" not in generation["attempts"][-1]["diagnostics"]: raise PipelineError("benign_T lacks dose evidence")
            dose_count += 1
        validated_responses[logical_id] = response
    if len(fake_flags) != 1: raise PipelineError("benign stage mixes fake and real backend provenance")
    fake_backend = fake_flags.pop()
    if expected_fake_backend is not None and fake_backend is not expected_fake_backend: raise PipelineError("benign backend provenance differs from execution")
    if sum(terminal_counts.values()) != BENIGN_COUNT: raise PipelineError("benign terminal partition does not total 630")
    return {
        "schema_version": "paper1-stage3-benign-integrity-ledger-v1", "run_mode": "paper", "stage": "benign_integrity",
        "paper_result_eligible": False, "formal_experiment_run": not fake_backend, "fake_backend": fake_backend,
        "canonical_plan_count": len(prepared.support.registry), "canonical_registry_sha256": prepared.support.registry.manifest()["registry_sha256"],
        "identities": BENIGN_COUNT, "benign_identity_count": BENIGN_COUNT, "benign_T_identity_count": BENIGN_T_COUNT, "benign_clean_identity_count": BENIGN_CLEAN_COUNT,
        "generation_record_count": len(generations), "generation_completed": generation_completed, "generation_retry_calls": generation_retries, "generation_total_calls": len(generations) + generation_retries,
        "generation_first_pass_scheduled": BENIGN_COUNT, "generation_first_pass_calls": len(generations),
        "generation_unattempted": BENIGN_COUNT - len(generations),
        "judge_scheduled": BENIGN_COUNT, "judge_first_pass_scheduled": BENIGN_COUNT,
        "judge_first_pass_calls": len(judges), "judge_eligible": len(judges),
        "prejudge_terminal": BENIGN_COUNT - len(judges), "judge_record_count": len(judges), "judge_parsed": judge_parsed, "judge_retry_calls": judge_retries, "judge_total_calls": len(judges) + judge_retries,
        "response_record_count": len(responses), "disposition_count": len(disposition_by_id), "terminal_partition": terminal_counts,
        "terminal_partition_sha256": canonical_sha256([disposition_by_id[row["logical_id"]] for row in rows]),
        "dose_evidence_record_count": dose_count, "clean_dose_evidence_record_count": clean_dose_count, "vector_identity_copy_count": 0,
        "benign_stage_only_reconciliation": True, "benign_integrity_only_reconciliation": True, "benign_only_reconciliation": True,
        "complete_stage3_reconciliation": False, "paper_results_materialized": False, "bootstrap_run": False,
        "p1_run": False, "support_run": False, "p2_run": False, "k1_run": False, "k1_additional_generation_calls": 0, "k1_additional_judge_calls": 0,
    }


def default_output_directory(prepared: PreparedBenignIntegrity, run_id: str) -> Path:
    if not isinstance(run_id, str) or SAFE_RUN_ID.fullmatch(run_id) is None: raise PipelineError("benign-integrity run-id contains invalid characters")
    configured = Path(prepared.config["output_root"]).resolve()
    if configured != OUTPUT_ROOT.resolve(): raise PipelineError("benign-integrity output root differs from fixed paper root")
    return configured / run_id


def _reserve_output_directory(path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_symlink():
        raise PipelineError(f"refusing to overwrite output directory symlink: {candidate}")
    output = candidate.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    try: output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc: raise PipelineError(f"refusing to overwrite output directory: {output}") from exc
    return output


def _record_document(schema_version: str, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"schema_version": schema_version, "record_count": len(records), "records": list(records)}


def run_prepared_benign_integrity(prepared: PreparedBenignIntegrity, *, run_id: str, behavior_backend_factory: Callable[[PreparedBenignIntegrity, int], Any] = load_real_behavior_backend, judge_backend_factory: Callable[[PreparedBenignIntegrity, Mapping[str, Any]], Any] = load_real_judge_backend, output_directory_resolver: Callable[[PreparedBenignIntegrity, str], Path] = default_output_directory, require_real_backend: bool = True) -> dict[str, Any]:
    output_directory = _reserve_output_directory(output_directory_resolver(prepared, run_id))
    artifacts = execute_benign_integrity(prepared, behavior_backend_factory=behavior_backend_factory, judge_backend_factory=judge_backend_factory, require_real_backend=require_real_backend)
    manifest = prepared.support.registry.manifest()
    registry_reference = {"schema_version": "paper1-stage3-canonical-registry-reference-v1", "source_support_config": str(SUPPORT_CONFIG.relative_to(ROOT)), "canonical_plan_count": len(prepared.support.registry), "canonical_registry_sha256": manifest["registry_sha256"], "benign_identity_count": BENIGN_COUNT, "benign_T_identity_count": BENIGN_T_COUNT, "benign_clean_identity_count": BENIGN_CLEAN_COUNT, "support_run_path": str(prepared.config["support_run_path"]), "p1_dose_binding_path": str(prepared.config["p1_dose_binding_path"])}
    execution_identity = {"schema_version": "paper1-stage3-benign-integrity-execution-v1", "run_id": run_id, "run_mode": "paper", "fake_backend": artifacts.benign_integrity_ledger["fake_backend"], "paper_result_eligible": False, "formal_experiment_run": artifacts.benign_integrity_ledger["formal_experiment_run"], "benign_integrity_run": True, "complete_stage3_reconciliation": False, "p1_run": False, "support_run": False, "p2_run": False, "k1_run": False, "canonical_registry_sha256": manifest["registry_sha256"], "canonical_registry_reference_sha256": canonical_sha256(registry_reference), "benign_integrity_ledger_sha256": canonical_sha256(artifacts.benign_integrity_ledger), "support_run_path": str(prepared.config["support_run_path"]), "support_ledger_sha256": canonical_sha256(prepared.support_validation["ledger"]), "p1_dose_binding_sha256": canonical_sha256(_dose_fingerprint(prepared.p1_result["dose_binding"])), "behavior_vector_order": list(VECTOR_INDICES), "behavior_lifecycle": artifacts.behavior_lifecycle, "judge_lifecycle": artifacts.judge_lifecycle, "judge_loaded_after_all_behavior_release": True, "models_concurrently_resident": False, "offline_guard_report": artifacts.offline_guard_report}
    store = OutputStore(output_directory)
    store.write_json_once("canonical_registry_reference.json", registry_reference)
    store.write_json_once("benign_integrity_identities.json", _record_document("paper1-stage3-benign-integrity-identity-set-v1", [*prepared.benign_T_rows, *prepared.benign_clean_rows]))
    store.write_json_once("generation_records.json", _record_document("paper1-stage3-benign-integrity-generation-set-v1", artifacts.generation_records))
    store.write_json_once("judge_records.json", _record_document("paper1-stage3-benign-integrity-judge-set-v1", artifacts.judge_records))
    store.write_json_once("response_records.json", _record_document("paper1-stage3-benign-integrity-response-set-v1", artifacts.response_records))
    store.write_json_once("execution_dispositions.json", _record_document("paper1-stage3-benign-integrity-disposition-set-v1", artifacts.dispositions))
    store.write_json_once("benign_integrity_ledger.json", artifacts.benign_integrity_ledger)
    store.write_json_once("execution_identity.json", execution_identity)
    fake = artifacts.benign_integrity_ledger["fake_backend"]
    return {"status": "BENIGN_INTEGRITY_FAKE_630_PATH_PASS" if fake else "BENIGN_INTEGRITY_REAL_RUN_PASS", "output_directory": str(output_directory), "run_id": run_id, "run_mode": "paper", "canonical_plan_count": len(prepared.support.registry), "benign_identity_count": BENIGN_COUNT, "benign_T_identity_count": BENIGN_T_COUNT, "benign_clean_identity_count": BENIGN_CLEAN_COUNT, "fake_backend": fake, "paper_result_eligible": False, "formal_experiment_run": not fake, "complete_stage3_reconciliation": False}


def run_benign_integrity(config_path: Path, *, run_mode: str, run_id: str) -> dict[str, Any]:
    if run_mode != "paper": raise PipelineError("benign-integrity execution supports only --run-mode paper")
    prepared = prepare_benign_integrity(config_path)
    return run_prepared_benign_integrity(prepared, run_id=run_id, require_real_backend=True)


__all__ = ["DEFAULT_CONFIG", "PreparedBenignIntegrity", "BenignIntegrityRunArtifacts", "BENIGN_COUNT", "BENIGN_T_COUNT", "BENIGN_CLEAN_COUNT", "VECTOR_INDICES", "validate_benign_integrity_config", "prepare_benign_integrity", "select_benign_identities", "validate_only", "execute_benign_integrity", "reconcile_benign_integrity", "run_prepared_benign_integrity", "run_benign_integrity", "default_output_directory", "load_real_behavior_backend", "load_real_judge_backend"]
