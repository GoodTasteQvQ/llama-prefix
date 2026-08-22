"""Fixed vector-free harmful-clean Stage 3 runner."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from scripts.stage3_production.validate_stage3_development_inputs import (
    _strict_json_object,
    validate_development_inputs,
)

from .core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    PAPER_LOGICAL_GENERATION,
    GenerationProducer,
    IdentityError,
    PipelineError,
    VerifiedBackendCapability,
    canonical_sha256,
    file_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
)
from .execution import (
    TERMINAL_DISPOSITIONS,
    OutputStore,
    response_terminal_disposition,
    validate_execution_disposition,
)
from .real_backend import RealBehaviorBackend, inspect_local_model_assets
from .real_judge import RealJudgeBackend
from .records import (
    RecordSchemaError,
    build_block_response_record,
    validate_generation_record,
    validate_judge_record,
    validate_response_materialization,
    validate_response_record,
)
from .support_screen import (
    DEFAULT_CONFIG as SUPPORT_CONFIG,
    PreparedSupportScreen,
    load_real_behavior_backend as load_support_behavior_backend,
    load_real_judge_backend as load_support_judge_backend,
    prepare_support_screen,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/stage3/qwen25_harmful_clean_v1.json"
OUTPUT_ROOT = Path("/data/goodtaste_workspace/paper1_stage3_runs")
HARMFUL_CLEAN_IDENTITY_COUNT = 50
SOURCE_ROLE = "D_behavior_confirm"
ZERO_HEX = float(0.0).hex()
# RealBehaviorBackend requires one loaded vector asset even though its clean path never
# installs or uses a steering hook. This index is not part of any clean identity/output.
BACKEND_COMPATIBILITY_VECTOR_INDEX = 10
SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

CONFIG_FIELDS = (
    "schema_version",
    "status",
    "run_mode",
    "paper_result_eligible",
    "formal_experiment_run",
    "harmful_clean_identity_count",
    "source",
    "vector_free",
    "clean_alpha",
    "generation_config",
    "judge_config",
    "output_root",
)


@dataclass(frozen=True)
class PreparedHarmfulClean:
    """Validated canonical registry and its fixed harmful-clean partition."""

    config_path: Path
    config: Mapping[str, Any]
    support: PreparedSupportScreen
    clean_rows: tuple[Mapping[str, Any], ...]
    offline_guard_report: Mapping[str, Any]


@dataclass(frozen=True)
class HarmfulCleanRunArtifacts:
    """Terminal records materialized only for the 50 harmful-clean identities."""

    generation_records: tuple[Mapping[str, Any], ...]
    judge_records: tuple[Mapping[str, Any], ...]
    response_records: tuple[Mapping[str, Any], ...]
    dispositions: tuple[Mapping[str, Any], ...]
    harmful_clean_ledger: Mapping[str, Any]
    behavior_lifecycle: Mapping[str, Any]
    judge_lifecycle: Mapping[str, Any]
    offline_guard_report: Mapping[str, Any]


def _exact_fields(value: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or tuple(value) != fields:
        raise PipelineError(f"{label} exact ordered fields mismatch")
    return dict(value)


def validate_harmful_clean_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate that the config describes only the fixed clean design."""
    actual = _exact_fields(config, CONFIG_FIELDS, "harmful-clean config")
    expected = {
        "schema_version": "paper1-stage3-qwen25-harmful-clean-v1",
        "status": "harmful_clean_runner_ready",
        "run_mode": "paper",
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "harmful_clean_identity_count": HARMFUL_CLEAN_IDENTITY_COUNT,
        "source": {"role": SOURCE_ROLE, "prompt_count": HARMFUL_CLEAN_IDENTITY_COUNT},
        "vector_free": True,
        "clean_alpha": 0.0,
        "generation_config": DECODE_CONFIG,
        "judge_config": JUDGE_CONFIG,
        "output_root": str(OUTPUT_ROOT),
    }
    for field, expected_value in expected.items():
        if actual[field] != expected_value or type(actual[field]) is not type(expected_value):
            raise PipelineError(f"harmful-clean config {field} mismatch")
    if tuple(actual["source"]) != ("role", "prompt_count"):
        raise PipelineError("harmful-clean source fields mismatch")
    return actual


def select_harmful_clean_identities(
    support: PreparedSupportScreen,
) -> tuple[Mapping[str, Any], ...]:
    """Select the canonical clean rows by identity fields, never by array position."""
    if len(support.registry) != PAPER_LOGICAL_GENERATION:
        raise IdentityError("harmful-clean selection requires the complete 5,580-ID registry")
    rows = tuple(
        row
        for row in support.registry.records()
        if row["identity"]["block"] == "harmful_clean"
    )
    expected_prompts = list(support.plan_inputs["confirm_prompt_ids"])
    expected_prompt_set = set(expected_prompts)
    logical_ids = [row["logical_id"] for row in rows]
    prompt_ids = [row["identity"]["prompt_id"] for row in rows]
    if (
        len(rows) != HARMFUL_CLEAN_IDENTITY_COUNT
        or len(set(logical_ids)) != HARMFUL_CLEAN_IDENTITY_COUNT
        or len(expected_prompts) != HARMFUL_CLEAN_IDENTITY_COUNT
        or len(expected_prompt_set) != HARMFUL_CLEAN_IDENTITY_COUNT
        or set(prompt_ids) != expected_prompt_set
        or len(set(prompt_ids)) != HARMFUL_CLEAN_IDENTITY_COUNT
    ):
        raise IdentityError("harmful-clean selection must be the fixed 50-prompt partition")
    required = {
        "block": "harmful_clean",
        "domain": "harmful",
        "split": SOURCE_ROLE,
        "anchor": "clean",
        "estimator": "clean",
        "vector_id": None,
        "c_hex": ZERO_HEX,
        "alpha_pre_dtype_hex": ZERO_HEX,
        "alpha_post_dtype_hex": ZERO_HEX,
        "rho_hex": ZERO_HEX,
    }
    for row in rows:
        logical_id = row["logical_id"]
        identity = row["identity"]
        if support.registry.require(logical_id) != identity:
            raise IdentityError("harmful-clean row differs from its canonical registry identity")
        for field, expected in required.items():
            if identity.get(field) != expected or type(identity.get(field)) is not type(expected):
                raise IdentityError(f"harmful-clean identity {field} differs from clean design")
        messages = support.messages_by_prompt_id.get(identity["prompt_id"])
        prompt = support.prompt_text_by_id.get(identity["prompt_id"])
        if messages != [{"role": "user", "content": prompt}] or not isinstance(prompt, str):
            raise IdentityError("harmful-clean prompt differs from the canonical native frame")
    return rows


def prepare_harmful_clean(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> PreparedHarmfulClean:
    """Rebuild the existing canonical registry without loading model weights."""
    root = repo_root.resolve()
    resolved_config = config_path.resolve()
    config = validate_harmful_clean_config(
        _strict_json_object(resolved_config, "harmful-clean config")
    )
    support_config = (root / SUPPORT_CONFIG.relative_to(ROOT)).resolve()
    guard = offline_execution_guard()
    with guard:
        support = prepare_support_screen(
            support_config,
            repo_root=root,
            model_asset_inspector=model_asset_inspector,
            development_validator=development_validator,
        )
        clean_rows = select_harmful_clean_identities(support)
        if config["generation_config"] != support.config["generation_config"]:
            raise PipelineError("harmful-clean generation config differs from canonical Stage 3")
        if config["judge_config"] != support.config["judge_config"]:
            raise PipelineError("harmful-clean judge config differs from canonical Stage 3")
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("harmful-clean preparation attempted a forbidden offline operation")
    return PreparedHarmfulClean(
        config_path=resolved_config,
        config=config,
        support=support,
        clean_rows=clean_rows,
        offline_guard_report=guard_report,
    )


def validate_only(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> dict[str, Any]:
    """Validate identities, prompt frame, zero dose, and output policy without execution."""
    prepared = prepare_harmful_clean(
        config_path,
        repo_root=repo_root,
        model_asset_inspector=model_asset_inspector,
        development_validator=development_validator,
    )
    output_probe = default_output_directory(prepared, "harmful-clean-validate-only")
    registry_manifest = prepared.support.registry.manifest()
    return {
        "schema_version": "paper1-stage3-harmful-clean-validation-v1",
        "status": "HARMFUL_CLEAN_RUNNER_VALIDATE_ONLY_PASS",
        "validate_only": True,
        "run_mode": "paper",
        "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": registry_manifest["registry_sha256"],
        "harmful_clean_identity_count": len(prepared.clean_rows),
        "harmful_clean_identity_set_sha256": canonical_sha256(list(prepared.clean_rows)),
        "source_role": SOURCE_ROLE,
        "prompt_count": len(prepared.support.plan_inputs["confirm_prompt_ids"]),
        "vector_free": True,
        "clean_alpha": 0.0,
        "clean_dose_hex": ZERO_HEX,
        "native_prompt_frame_validated": True,
        "output_root": str(output_probe.parent),
        "output_non_overwrite_policy_validated": True,
        "model_weights_loaded": False,
        "gpu_used": False,
        "forward_executed": False,
        "generation_run": False,
        "judge_run": False,
        "harmful_clean_run": False,
        "p1_run": False,
        "support_run": False,
        "p2_run": False,
        "k1_run": False,
        "fake_backend": False,
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "complete_stage3_reconciliation": False,
        "offline_guard_report": prepared.offline_guard_report,
        "network_attempts": prepared.offline_guard_report["category_counts"]["network"],
        "blocked_attempts": prepared.offline_guard_report["blocked_attempt_count"],
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


def _disposition(
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


def reconcile_harmful_clean(
    prepared: PreparedHarmfulClean,
    *,
    generation_records: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    expected_fake_backend: bool | None = None,
) -> dict[str, Any]:
    """Reconcile exactly 50 clean chains, never the complete Stage 3 registry."""
    if expected_fake_backend is not None and type(expected_fake_backend) is not bool:
        raise PipelineError("expected_fake_backend must be boolean or omitted")
    clean_by_id = {row["logical_id"]: row["identity"] for row in prepared.clean_rows}
    clean_ids = set(clean_by_id)
    if len(clean_by_id) != HARMFUL_CLEAN_IDENTITY_COUNT:
        raise IdentityError("harmful-clean reconciliation requires exactly 50 canonical IDs")
    generations = _record_index(
        generation_records,
        label="harmful-clean generation set",
        validator=validate_generation_record,
    )
    judges = _record_index(
        judge_records,
        label="harmful-clean judge set",
        validator=validate_judge_record,
    )
    responses = _record_index(
        response_records,
        label="harmful-clean response set",
        validator=validate_response_record,
    )
    disposition_by_id = _record_index(
        dispositions,
        label="harmful-clean disposition set",
        validator=validate_execution_disposition,
    )
    for label, observed in (
        ("generation", set(generations)),
        ("response", set(responses)),
        ("disposition", set(disposition_by_id)),
    ):
        if observed != clean_ids:
            raise IdentityError(f"harmful-clean {label} set must cover exactly the 50 clean IDs")
    completed_ids = {
        logical_id
        for logical_id, generation in generations.items()
        if generation["generation_completed"]
    }
    if set(judges) != completed_ids:
        raise IdentityError("harmful-clean judge set must equal completed-generation IDs")

    terminal_counts = {terminal: 0 for terminal in TERMINAL_DISPOSITIONS}
    fake_flags: set[bool] = set()
    generation_completed = 0
    judge_parsed = 0
    generation_retries = 0
    judge_retries = 0
    for logical_id, identity in clean_by_id.items():
        generation = generations[logical_id]
        judge = judges.get(logical_id)
        if (
            generation["logical_id"] != logical_id
            or generation["identity_sha256"] != canonical_sha256(identity)
            or generation["run_mode"] != "paper"
        ):
            raise IdentityError("harmful-clean generation lineage differs from registry")
        if judge is not None and (
            judge["logical_id"] != logical_id
            or judge["identity_sha256"] != canonical_sha256(identity)
            or judge["generation_record_sha256"] != generation["record_sha256"]
            or judge["domain"] != "harmful"
            or judge["run_mode"] != "paper"
        ):
            raise PipelineError("harmful-clean judge lineage differs from generation")
        try:
            response = validate_response_materialization(
                responses[logical_id],
                registry=prepared.support.registry,
                generation_record=generation,
                judge_record=judge,
            )
        except RecordSchemaError as exc:
            raise PipelineError("harmful-clean response materialization failed") from exc
        disposition = disposition_by_id[logical_id]
        terminal = response_terminal_disposition(identity, response, generation, judge)
        if (
            disposition["identity_sha256"] != canonical_sha256(identity)
            or disposition["terminal_disposition"] != terminal
            or disposition["generation_record_sha256"] != generation["record_sha256"]
            or disposition["judge_record_sha256"]
            != (None if judge is None else judge["record_sha256"])
            or disposition["response_record_sha256"] != response["record_sha256"]
            or disposition["integrity_block_reason"] is not None
        ):
            raise PipelineError("harmful-clean disposition differs from terminal record lineage")
        if response["dose_evidence"] is not None:
            raise PipelineError("harmful-clean reconciliation found dose evidence")
        terminal_counts[terminal] += 1
        generation_completed += int(generation["generation_completed"])
        generation_retries += generation["retry_count"]
        judge_parsed += int(judge is not None and judge["judge_label_parsed"])
        judge_retries += 0 if judge is None else len(judge["attempts"]) - 1
        fake_flags.update({generation["fake_backend"], response["fake_backend"]})
        if judge is not None:
            fake_flags.add(judge["fake_backend"])
    if len(fake_flags) != 1:
        raise PipelineError("harmful-clean stage mixes real and fake backend provenance")
    fake_backend = fake_flags.pop()
    if expected_fake_backend is not None and fake_backend is not expected_fake_backend:
        raise PipelineError("harmful-clean backend provenance differs from execution")
    if sum(terminal_counts.values()) != HARMFUL_CLEAN_IDENTITY_COUNT:
        raise PipelineError("harmful-clean terminal partition does not total 50")
    return {
        "schema_version": "paper1-stage3-harmful-clean-ledger-v1",
        "run_mode": "paper",
        "stage": "harmful_clean",
        "paper_result_eligible": False,
        "fake_backend": fake_backend,
        "formal_experiment_run": not fake_backend,
        "harmful_clean_run": not fake_backend,
        "p1_run": False,
        "support_run": False,
        "p2_run": False,
        "k1_run": False,
        "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": prepared.support.registry.manifest()["registry_sha256"],
        "harmful_clean_identity_count": HARMFUL_CLEAN_IDENTITY_COUNT,
        "harmful_clean_identity_set_sha256": canonical_sha256(list(prepared.clean_rows)),
        "generation_record_count": len(generations),
        "generation_completed": generation_completed,
        "generation_retry_calls": generation_retries,
        "generation_total_calls": len(generations) + generation_retries,
        "judge_scheduled": HARMFUL_CLEAN_IDENTITY_COUNT,
        "judge_record_count": len(judges),
        "judge_parsed": judge_parsed,
        "judge_retry_calls": judge_retries,
        "judge_total_calls": len(judges) + judge_retries,
        "response_record_count": len(responses),
        "disposition_count": len(disposition_by_id),
        "terminal_partition": terminal_counts,
        "terminal_partition_sha256": canonical_sha256(
            [disposition_by_id[row["logical_id"]] for row in prepared.clean_rows]
        ),
        "dose_evidence_record_count": 0,
        "vector_identity_copy_count": 0,
        "harmful_clean_only_reconciliation": True,
        "complete_stage3_reconciliation": False,
        "paper_results_materialized": False,
        "bootstrap_run": False,
        "k1_additional_generation_calls": 0,
        "k1_additional_judge_calls": 0,
    }


def load_real_behavior_backend(prepared: PreparedHarmfulClean) -> RealBehaviorBackend:
    """Load the existing real adapter once; clean calls install no steering hook."""
    return load_support_behavior_backend(
        prepared.support, BACKEND_COMPATIBILITY_VECTOR_INDEX
    )


def load_real_judge_backend(
    prepared: PreparedHarmfulClean, lifecycle: Mapping[str, Any]
) -> RealJudgeBackend:
    return load_support_judge_backend(prepared.support, lifecycle)


def _require_real_capability(backend: Any, role: str) -> VerifiedBackendCapability:
    capability = getattr(backend, "capability", None)
    class_name = "RealBehaviorBackend" if role == "behavior" else "RealJudgeBackend"
    if (
        not isinstance(capability, VerifiedBackendCapability)
        or capability.role != role
        or not capability.matches_backend_instance(backend)
    ):
        raise PipelineError(f"paper harmful-clean requires {class_name} capability")
    return capability


def execute_harmful_clean(
    prepared: PreparedHarmfulClean,
    *,
    behavior_backend_factory: Callable[[PreparedHarmfulClean], Any] = load_real_behavior_backend,
    judge_backend_factory: Callable[
        [PreparedHarmfulClean, Mapping[str, Any]], Any
    ] = load_real_judge_backend,
    require_real_backend: bool = True,
) -> HarmfulCleanRunArtifacts:
    """Generate all clean responses, release behavior, then judge completed rows."""
    if type(require_real_backend) is not bool:
        raise PipelineError("require_real_backend must be boolean")
    generation_by_id: dict[str, dict[str, Any]] = {}
    judge_by_id: dict[str, dict[str, Any]] = {}
    guard = offline_execution_guard()
    with guard:
        behavior_backend = behavior_backend_factory(prepared)
        behavior_capability = getattr(behavior_backend, "capability", None)
        try:
            if require_real_backend:
                behavior_capability = _require_real_capability(
                    behavior_backend, "behavior"
                )
            producer = GenerationProducer(
                prepared.support.registry,
                behavior_backend,
                run_mode="paper",
                generation_config=DECODE_CONFIG,
                fake_backend=behavior_capability is None,
                capability=behavior_capability,
                item_budget=PAPER_LOGICAL_GENERATION,
            )
            for row in prepared.clean_rows:
                logical_id = row["logical_id"]
                identity = row["identity"]
                generation_by_id[logical_id] = validate_generation_record(
                    producer.produce(
                        logical_id,
                        {
                            "logical_id": logical_id,
                            "generation_config": DECODE_CONFIG,
                            "messages": prepared.support.messages_by_prompt_id[
                                identity["prompt_id"]
                            ],
                        },
                    )
                )
        finally:
            behavior_lifecycle = (
                behavior_backend.release()
                if not getattr(behavior_backend, "released", False)
                else {"behavior_released": True, "models_concurrently_resident": False}
            )
        if (
            not isinstance(behavior_lifecycle, Mapping)
            or behavior_lifecycle.get("behavior_released") is not True
            or behavior_lifecycle.get("models_concurrently_resident") is not False
        ):
            raise PipelineError("harmful-clean behavior release evidence is incomplete")

        judge_backend = judge_backend_factory(prepared, behavior_lifecycle)
        judge_capability = getattr(judge_backend, "capability", None)
        try:
            if require_real_backend:
                judge_capability = _require_real_capability(judge_backend, "judge")
            producer_identity = getattr(judge_backend, "producer_identity", None)
            if not isinstance(producer_identity, Mapping):
                raise PipelineError("judge backend lacks its canonical producer identity")
            for row in prepared.clean_rows:
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
                                "prompt": prepared.support.prompt_text_by_id[
                                    identity["prompt_id"]
                                ],
                                "response": generation["output_text"],
                                "domain": "harmful",
                            },
                        },
                        registry=prepared.support.registry,
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
                else {"judge_released": True, "models_concurrently_resident": False}
            )
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("harmful-clean execution attempted a forbidden offline operation")
    behavior_fake = behavior_capability is None
    judge_fake = judge_capability is None
    if behavior_fake is not judge_fake:
        raise PipelineError("harmful-clean execution mixes real and fake backend sessions")

    generations: list[dict[str, Any]] = []
    judges: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for row in prepared.clean_rows:
        logical_id = row["logical_id"]
        identity = row["identity"]
        generation = generation_by_id[logical_id]
        judge = judge_by_id.get(logical_id)
        response = build_block_response_record(
            identity=identity,
            generation_record=generation,
            judge_record=judge,
            dose_evidence=None,
        )
        validate_response_materialization(
            response,
            registry=prepared.support.registry,
            generation_record=generation,
            judge_record=judge,
        )
        generations.append(generation)
        if judge is not None:
            judges.append(judge)
        responses.append(response)
        dispositions.append(_disposition(identity, generation, judge, response))
    ledger = reconcile_harmful_clean(
        prepared,
        generation_records=generations,
        judge_records=judges,
        response_records=responses,
        dispositions=dispositions,
        expected_fake_backend=behavior_fake,
    )
    return HarmfulCleanRunArtifacts(
        generation_records=tuple(generations),
        judge_records=tuple(judges),
        response_records=tuple(responses),
        dispositions=tuple(dispositions),
        harmful_clean_ledger=ledger,
        behavior_lifecycle=dict(behavior_lifecycle),
        judge_lifecycle=dict(judge_lifecycle),
        offline_guard_report=guard_report,
    )


def default_output_directory(prepared: PreparedHarmfulClean, run_id: str) -> Path:
    if not isinstance(run_id, str) or SAFE_RUN_ID.fullmatch(run_id) is None:
        raise PipelineError("harmful-clean run-id contains invalid characters")
    configured_root = Path(prepared.config["output_root"]).resolve()
    if configured_root != OUTPUT_ROOT.resolve():
        raise PipelineError("harmful-clean output root differs from the fixed paper root")
    return configured_root / run_id


def _reserve_output_directory(path: Path) -> Path:
    output = path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        raise PipelineError(f"refusing to overwrite output directory: {output}") from exc
    return output


def _record_document(
    schema_version: str, records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "record_count": len(records),
        "records": list(records),
    }


def run_prepared_harmful_clean(
    prepared: PreparedHarmfulClean,
    *,
    run_id: str,
    behavior_backend_factory: Callable[[PreparedHarmfulClean], Any] = load_real_behavior_backend,
    judge_backend_factory: Callable[
        [PreparedHarmfulClean, Mapping[str, Any]], Any
    ] = load_real_judge_backend,
    output_directory_resolver: Callable[
        [PreparedHarmfulClean, str], Path
    ] = default_output_directory,
    require_real_backend: bool = True,
) -> dict[str, Any]:
    output_directory = _reserve_output_directory(
        output_directory_resolver(prepared, run_id)
    )
    artifacts = execute_harmful_clean(
        prepared,
        behavior_backend_factory=behavior_backend_factory,
        judge_backend_factory=judge_backend_factory,
        require_real_backend=require_real_backend,
    )
    registry_manifest = prepared.support.registry.manifest()
    registry_reference = {
        "schema_version": "paper1-stage3-canonical-registry-reference-v1",
        "source_support_config": str(SUPPORT_CONFIG.relative_to(ROOT)),
        "canonical_plan_count": len(prepared.support.registry),
        "canonical_registry_sha256": registry_manifest["registry_sha256"],
        "harmful_clean_identity_count": len(prepared.clean_rows),
        "harmful_clean_identity_set_sha256": canonical_sha256(list(prepared.clean_rows)),
        "source_role": SOURCE_ROLE,
    }
    execution_identity = {
        "schema_version": "paper1-stage3-harmful-clean-execution-v1",
        "run_id": run_id,
        "run_mode": "paper",
        "fake_backend": artifacts.harmful_clean_ledger["fake_backend"],
        "paper_result_eligible": False,
        "formal_experiment_run": artifacts.harmful_clean_ledger[
            "formal_experiment_run"
        ],
        "harmful_clean_run": artifacts.harmful_clean_ledger["harmful_clean_run"],
        "p1_run": False,
        "support_run": False,
        "p2_run": False,
        "k1_run": False,
        "canonical_registry_sha256": registry_manifest["registry_sha256"],
        "canonical_registry_reference_sha256": canonical_sha256(registry_reference),
        "harmful_clean_ledger_sha256": canonical_sha256(
            artifacts.harmful_clean_ledger
        ),
        "harmful_clean_runner_code_sha256": file_sha256(Path(__file__).resolve()),
        "harmful_clean_config_sha256": file_sha256(prepared.config_path),
        "behavior_lifecycle": artifacts.behavior_lifecycle,
        "judge_lifecycle": artifacts.judge_lifecycle,
        "offline_guard_report": artifacts.offline_guard_report,
    }
    store = OutputStore(output_directory)
    store.write_json_once("canonical_registry_reference.json", registry_reference)
    store.write_json_once(
        "harmful_clean_identities.json",
        _record_document(
            "paper1-stage3-harmful-clean-identity-set-v1", prepared.clean_rows
        ),
    )
    store.write_json_once(
        "generation_records.json",
        _record_document(
            "paper1-stage3-harmful-clean-generation-set-v1",
            artifacts.generation_records,
        ),
    )
    store.write_json_once(
        "judge_records.json",
        _record_document(
            "paper1-stage3-harmful-clean-judge-set-v1", artifacts.judge_records
        ),
    )
    store.write_json_once(
        "response_records.json",
        _record_document(
            "paper1-stage3-harmful-clean-response-set-v1",
            artifacts.response_records,
        ),
    )
    store.write_json_once(
        "execution_dispositions.json",
        _record_document(
            "paper1-stage3-harmful-clean-disposition-set-v1",
            artifacts.dispositions,
        ),
    )
    store.write_json_once(
        "harmful_clean_ledger.json", artifacts.harmful_clean_ledger
    )
    store.write_json_once("execution_identity.json", execution_identity)
    fake_backend = artifacts.harmful_clean_ledger["fake_backend"]
    return {
        "status": (
            "HARMFUL_CLEAN_FAKE_50_PATH_PASS"
            if fake_backend
            else "HARMFUL_CLEAN_REAL_RUN_PASS"
        ),
        "output_directory": str(output_directory),
        "run_id": run_id,
        "run_mode": "paper",
        "canonical_plan_count": len(prepared.support.registry),
        "harmful_clean_identity_count": len(prepared.clean_rows),
        "harmful_clean_terminal": len(artifacts.dispositions),
        "fake_backend": fake_backend,
        "paper_result_eligible": False,
        "formal_experiment_run": not fake_backend,
        "harmful_clean_run": not fake_backend,
        "p1_run": False,
        "support_run": False,
        "p2_run": False,
        "k1_run": False,
        "complete_stage3_reconciliation": False,
    }


def run_harmful_clean(config_path: Path, *, run_mode: str, run_id: str) -> dict[str, Any]:
    if run_mode != "paper":
        raise PipelineError("harmful-clean execution supports only --run-mode paper")
    prepared = prepare_harmful_clean(config_path)
    return run_prepared_harmful_clean(
        prepared,
        run_id=run_id,
        behavior_backend_factory=load_real_behavior_backend,
        judge_backend_factory=load_real_judge_backend,
        output_directory_resolver=default_output_directory,
        require_real_backend=True,
    )


__all__ = [
    "DEFAULT_CONFIG",
    "HARMFUL_CLEAN_IDENTITY_COUNT",
    "HarmfulCleanRunArtifacts",
    "PreparedHarmfulClean",
    "default_output_directory",
    "execute_harmful_clean",
    "prepare_harmful_clean",
    "reconcile_harmful_clean",
    "run_harmful_clean",
    "run_prepared_harmful_clean",
    "select_harmful_clean_identities",
    "validate_harmful_clean_config",
    "validate_only",
]
