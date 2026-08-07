"""Fixed Qwen support-screen planning and staged execution."""

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
    PAPER_LOGICAL_GENERATION,
    GenerationProducer,
    IdentityError,
    LogicalIdentityRegistry,
    PipelineError,
    canonical_sha256,
    classify_support,
    file_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
)
from .dose import validate_dose_binding
from .execution import (
    BLOCK_BUDGET,
    TERMINAL_DISPOSITIONS,
    OutputStore,
    build_logical_plan,
    response_terminal_disposition,
    validate_execution_disposition,
)
from .offline_assets import strict_json_loads
from .real_backend import RealBehaviorBackend, inspect_local_model_assets
from .real_judge import RealJudgeBackend, judge_rubric_sha256
from .records import (
    RecordSchemaError,
    build_block_response_record,
    validate_generation_record,
    validate_judge_record,
    validate_support_materialization,
    validate_support_record,
)
from .run_manifest import collect_runtime_versions
from .vector_pool import MANIFEST_RELATIVE_PATH, TENSOR_RELATIVE_PATH


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/stage3/qwen25_support_screen_v1.json"
DEVELOPMENT_INPUT = "configs/stage3/qwen25_stage3_development_inputs_v1.json"
SCREEN_ENTRY = "configs/stage3/jbb_behavior_screen_v1.json"
CONFIRM_ENTRY = "configs/stage3/jbb_behavior_confirm_v1.json"
BENIGN_ENTRY = "configs/stage3/benign_confirm_v1.json"
OUTPUT_ROOT = Path("/data/goodtaste_workspace/paper1_stage3_runs")
SUPPORT_ANCHORS = ("A", "T", "H")
SCREEN_VECTOR_INDICES = tuple(range(10))
SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

CONFIG_FIELDS = (
    "schema_version",
    "status",
    "run_mode",
    "development_input_config_relative_path",
    "paper_result_eligible",
    "formal_experiment_run",
    "canonical_plan_count",
    "support_identity_count",
    "prompt_frames",
    "vector_pool",
    "anchors",
    "estimator",
    "message_format",
    "generation_config",
    "judge_config",
    "output_root",
)


@dataclass(frozen=True)
class PreparedSupportScreen:
    """Validated assets and the complete canonical logical plan."""

    config_path: Path
    config: Mapping[str, Any]
    development: Mapping[str, Any]
    development_validation: Mapping[str, Any]
    registry: LogicalIdentityRegistry
    support_rows: tuple[Mapping[str, Any], ...]
    prompt_text_by_id: Mapping[str, str]
    messages_by_prompt_id: Mapping[str, list[dict[str, str]]]
    vector_ids_by_index: Mapping[int, str]
    vector_index_by_id: Mapping[str, int]
    dose_binding: Mapping[str, Any]
    behavior_identity: Mapping[str, Any]
    judge_model_identity: Mapping[str, Any]
    p1_primary_gate: bool
    plan_inputs: Mapping[str, Any]
    offline_guard_report: Mapping[str, Any]


@dataclass(frozen=True)
class SupportRunArtifacts:
    """Canonical records materialized for the support stage only."""

    generation_records: tuple[Mapping[str, Any], ...]
    judge_records: tuple[Mapping[str, Any], ...]
    response_records: tuple[Mapping[str, Any], ...]
    dispositions: tuple[Mapping[str, Any], ...]
    support_ledger: Mapping[str, Any]
    behavior_lifecycle: Mapping[str, Any]
    judge_lifecycle: Mapping[str, Any]


def _exact_fields(value: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or tuple(value) != fields:
        raise PipelineError(f"{label} exact ordered fields mismatch")
    return dict(value)


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


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


def validate_support_config(config: Mapping[str, Any]) -> dict[str, Any]:
    actual = _exact_fields(config, CONFIG_FIELDS, "support-screen config")
    expected = {
        "schema_version": "paper1-stage3-qwen25-support-screen-v1",
        "status": "support_screen_runner_ready",
        "run_mode": "paper",
        "development_input_config_relative_path": DEVELOPMENT_INPUT,
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "canonical_plan_count": PAPER_LOGICAL_GENERATION,
        "support_identity_count": 900,
        "anchors": list(SUPPORT_ANCHORS),
        "estimator": "mu_all_tw",
        "message_format": "native_user_only",
        "generation_config": DECODE_CONFIG,
        "judge_config": JUDGE_CONFIG,
        "output_root": str(OUTPUT_ROOT),
    }
    for field, expected_value in expected.items():
        if actual[field] != expected_value or type(actual[field]) is not type(expected_value):
            raise PipelineError(f"support-screen config {field} mismatch")
    if actual["prompt_frames"] != {
        "screen": SCREEN_ENTRY,
        "confirmation": CONFIRM_ENTRY,
        "benign_confirmation": BENIGN_ENTRY,
    }:
        raise PipelineError("support-screen prompt frame references mismatch")
    if actual["vector_pool"] != {
        "manifest_relative_path": MANIFEST_RELATIVE_PATH,
        "tensor_relative_path": TENSOR_RELATIVE_PATH,
        "screen_indices": list(SCREEN_VECTOR_INDICES),
    }:
        raise PipelineError("support-screen vector pool references mismatch")
    return actual


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = strict_json_loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PipelineError(f"unable to read strict {label}: {path}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"{label} must be an object")
    return value


def _load_frame(
    repo_root: Path,
    development: Mapping[str, Any],
    active_relative_path: str,
    *,
    role: str,
    row_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    declaration = [
        item
        for item in development["datasets"]
        if item["active_entry_relative_path"] == active_relative_path
    ]
    if len(declaration) != 1 or declaration[0] != {
        "active_entry_relative_path": active_relative_path,
        "role": role,
        "row_count": row_count,
    }:
        raise PipelineError(f"development declaration for {role} mismatch")
    active_path = _resolve_repo_file(repo_root, active_relative_path, f"{role} active entry")
    active = _read_json(active_path, f"{role} active entry")
    if (
        active.get("schema_version") != "paper1-stage3-active-dataset-entry-v1"
        or active.get("role") != role
        or active.get("status") != "design_selected"
        or active.get("row_count") != row_count
        or active.get("formal_experiment_run") is not False
        or not _valid_sha256(active.get("selected_raw_sha256"))
    ):
        raise PipelineError(f"{role} active entry metadata mismatch")
    selected_path = _resolve_repo_file(repo_root, active.get("relative_path"), f"{role} selected")
    selected_raw = selected_path.read_bytes()
    if hashlib.sha256(selected_raw).hexdigest() != active["selected_raw_sha256"]:
        raise PipelineError(f"{role} selected frame SHA-256 mismatch")
    selected = _read_json(selected_path, f"{role} selected frame")
    if (
        selected.get("role") != role
        or selected.get("formal_experiment_run") is not False
        or selected.get("record_count") != row_count
        or not isinstance(selected.get("records"), list)
        or len(selected["records"]) != row_count
    ):
        raise PipelineError(f"{role} selected frame metadata mismatch")
    return active, selected


def _harmful_prompts(frame: Mapping[str, Any], *, split: str) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    source_indices: set[int] = set()
    source_identities: set[str] = set()
    for index, raw in enumerate(frame["records"]):
        if not isinstance(raw, Mapping):
            raise PipelineError(f"{split} records[{index}] must be an object")
        source_index = raw.get("source_index")
        prompt = raw.get("prompt")
        source_identity = raw.get("source_record_identity_sha256")
        if (
            isinstance(source_index, bool)
            or not isinstance(source_index, int)
            or source_index < 0
            or source_index in source_indices
            or not isinstance(prompt, str)
            or not prompt
            or not _valid_sha256(source_identity)
            or source_identity in source_identities
            or raw.get("split_membership") != split
        ):
            raise PipelineError(f"{split} records[{index}] identity/content mismatch")
        source_indices.add(source_index)
        source_identities.add(source_identity)
        prompt_id = f"jbb-{split}:{source_identity}"
        prompts.append({
            "prompt_id": prompt_id,
            "content": prompt,
            "messages": [{"role": "user", "content": prompt}],
            "source_identity": source_identity,
        })
    return prompts


def _benign_prompts(frame: Mapping[str, Any]) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    identities: set[str] = set()
    for index, raw in enumerate(frame["records"]):
        if not isinstance(raw, Mapping):
            raise PipelineError(f"benign records[{index}] must be an object")
        source_id = raw.get("source_id")
        prompt = raw.get("prompt")
        prompt_identity = raw.get("prompt_identity_sha256")
        messages = raw.get("messages")
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id in source_ids
            or not isinstance(prompt, str)
            or not prompt
            or messages != [{"role": "user", "content": prompt}]
            or hashlib.sha256(prompt.encode("utf-8")).hexdigest() != raw.get("prompt_sha256")
            or not _valid_sha256(prompt_identity)
            or prompt_identity in identities
            or raw.get("split_membership") != "benign_confirm"
        ):
            raise PipelineError(f"benign records[{index}] identity/content mismatch")
        source_ids.add(source_id)
        identities.add(prompt_identity)
        prompts.append({
            "prompt_id": f"benign-confirm:{prompt_identity}",
            "content": prompt,
            "messages": [{"role": "user", "content": prompt}],
            "source_identity": prompt_identity,
        })
    return prompts


def _render_prompt_hashes(
    tokenizer: Any, prompts: Sequence[Mapping[str, Any]]
) -> dict[str, str]:
    rendered_by_id: dict[str, str] = {}
    for prompt in prompts:
        try:
            rendered = tokenizer.apply_chat_template(
                prompt["messages"], tokenize=False, add_generation_prompt=True
            )
        except Exception as exc:
            raise PipelineError("behavior tokenizer could not render a fixed prompt") from exc
        if not isinstance(rendered, str) or not rendered:
            raise PipelineError("behavior tokenizer rendered an empty prompt")
        prompt_id = prompt["prompt_id"]
        if prompt_id in rendered_by_id:
            raise IdentityError("prompt frame contains a duplicate prompt ID")
        rendered_by_id[prompt_id] = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    return rendered_by_id


def _vector_ids(
    repo_root: Path,
    development: Mapping[str, Any],
) -> tuple[dict[int, str], dict[str, int]]:
    manifest_path = _resolve_repo_file(
        repo_root,
        development["vector_pool"]["manifest_relative_path"],
        "vector manifest",
    )
    manifest = _read_json(manifest_path, "vector manifest")
    vector_file_sha256 = manifest.get("pt_file_sha256")
    if (
        not _valid_sha256(vector_file_sha256)
        or manifest.get("V_screen") != [0, 9]
        or manifest.get("V_confirm") != [10, 29]
        or manifest.get("num_vectors") != 30
    ):
        raise PipelineError("validated vector manifest partition metadata mismatch")
    behavior = development["behavior"]
    by_index = {
        index: "sha256:" + canonical_sha256({
            "vector_file_sha256": vector_file_sha256,
            "vector_index": index,
            "layer": behavior["layer"],
            "hook_site": behavior["hook_site"],
        })
        for index in range(30)
    }
    return by_index, {vector_id: index for index, vector_id in by_index.items()}


def construct_plan_from_inputs(
    plan_inputs: Mapping[str, Any], *, p1_primary_gate: bool
) -> LogicalIdentityRegistry:
    """Build the full plan; the validated P1 gate is deliberately non-gating."""
    if type(p1_primary_gate) is not bool:
        raise PipelineError("P1 primary gate must be a boolean")
    return build_logical_plan(
        bindings=plan_inputs["bindings"],
        screen_prompt_ids=plan_inputs["screen_prompt_ids"],
        confirm_prompt_ids=plan_inputs["confirm_prompt_ids"],
        benign_prompt_ids=plan_inputs["benign_prompt_ids"],
        vector_ids_by_index=plan_inputs["vector_ids_by_index"],
        dose_binding=plan_inputs["dose_binding"],
    )


def select_support_identities(
    registry: LogicalIdentityRegistry,
    *,
    screen_prompt_ids: Sequence[str],
    vector_ids_by_index: Mapping[int, str],
) -> tuple[Mapping[str, Any], ...]:
    rows = tuple(
        row for row in registry.records() if row["identity"]["block"] == "support"
    )
    if len(registry) != PAPER_LOGICAL_GENERATION or len(rows) != 900:
        raise IdentityError("support selection requires a 5,580-ID plan with 900 support IDs")
    logical_ids = [row["logical_id"] for row in rows]
    if len(set(logical_ids)) != 900:
        raise IdentityError("support selection contains a logical-ID collision")
    expected_prompts = set(screen_prompt_ids)
    expected_vectors = {vector_ids_by_index[index] for index in SCREEN_VECTOR_INDICES}
    for anchor in SUPPORT_ANCHORS:
        identities = [row["identity"] for row in rows if row["identity"]["anchor"] == anchor]
        pairs = {(item["prompt_id"], item["vector_id"]) for item in identities}
        if (
            len(identities) != 300
            or {item["prompt_id"] for item in identities} != expected_prompts
            or {item["vector_id"] for item in identities} != expected_vectors
            or pairs != {(prompt_id, vector_id) for prompt_id in expected_prompts for vector_id in expected_vectors}
            or any(item["estimator"] != "mu_all_tw" for item in identities)
        ):
            raise IdentityError(f"support {anchor} selection differs from the fixed 30x10 grid")
    if any(row["identity"]["anchor"] not in SUPPORT_ANCHORS for row in rows):
        raise IdentityError("support selection contains an unexpected anchor")
    return rows


def prepare_support_screen(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> PreparedSupportScreen:
    """Validate local assets and deterministically construct all 5,580 IDs."""
    root = repo_root.resolve()
    resolved_config = config_path.resolve()
    config = validate_support_config(
        _strict_json_object(resolved_config, "support-screen config")
    )
    development_path = _resolve_repo_file(
        root,
        config["development_input_config_relative_path"],
        "development input config",
    )
    development = _strict_json_object(development_path, "development input config")
    inspected: dict[str, tuple[dict[str, Any], Any]] = {}

    def capturing_inspector(**kwargs: Any) -> tuple[dict[str, Any], Any]:
        role = kwargs.get("model_role")
        if role in inspected:
            raise PipelineError(f"duplicate {role} model asset inspection")
        result = model_asset_inspector(**kwargs)
        if role not in {"behavior", "judge"}:
            raise PipelineError("model asset inspector returned an unexpected role")
        inspected[role] = result
        return result

    guard = offline_execution_guard()
    with guard:
        development_validation = development_validator(
            development_path,
            repo_root=root,
            model_asset_inspector=capturing_inspector,
        )
        if development_validation.get("status") != "STAGE3_DEVELOPMENT_INPUTS_VALIDATE_ONLY_PASS":
            raise PipelineError("development input validation did not pass")
        if set(inspected) != {"behavior", "judge"}:
            raise PipelineError("development validation did not inspect behavior and judge assets")

        screen_active, screen_frame = _load_frame(
            root, development, config["prompt_frames"]["screen"],
            role="D_behavior_screen", row_count=30,
        )
        _, confirm_frame = _load_frame(
            root, development, config["prompt_frames"]["confirmation"],
            role="D_behavior_confirm", row_count=50,
        )
        benign_active, benign_frame = _load_frame(
            root, development, config["prompt_frames"]["benign_confirmation"],
            role="D_benign_confirm", row_count=30,
        )
        screen_prompts = _harmful_prompts(screen_frame, split="screen")
        confirm_prompts = _harmful_prompts(confirm_frame, split="confirm")
        benign_prompts = _benign_prompts(benign_frame)
        if {
            prompt["source_identity"] for prompt in screen_prompts
        } & {prompt["source_identity"] for prompt in confirm_prompts}:
            raise IdentityError("screen and confirmation source identities overlap")

        behavior_identity, behavior_tokenizer = inspected["behavior"]
        judge_identity, _ = inspected["judge"]
        if behavior_identity.get("chat_template_sha256") != benign_active.get("chat_template_sha256"):
            raise PipelineError("behavior chat template differs from the pinned benign frame")
        if screen_active.get("role") != "D_behavior_screen":
            raise PipelineError("screen active entry role changed")
        all_prompts = screen_prompts + confirm_prompts + benign_prompts
        rendered_hashes = _render_prompt_hashes(behavior_tokenizer, all_prompts)
        vector_ids_by_index, vector_index_by_id = _vector_ids(root, development)

        dose_binding = development["p1_measurement_and_dose"]["dose_binding"]
        validate_dose_binding(dose_binding)
        code_paths = (
            root / "stage3_pipeline/support_screen.py",
            root / "stage3_pipeline/core.py",
            root / "stage3_pipeline/execution.py",
            root / "stage3_pipeline/records.py",
            root / "stage3_pipeline/real_backend.py",
            root / "stage3_pipeline/real_judge.py",
            root / "scripts/stage3_production/run_support_screen.py",
        )
        bindings = {
            "model_revision": behavior_identity["model_revision"],
            "template_sha256": behavior_identity["chat_template_sha256"],
            "rendered_prompt_sha256_by_id": rendered_hashes,
            "layer": development["behavior"]["layer"],
            "hook_site": development["behavior"]["hook_site"],
            "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
            "code_sha256": canonical_sha256({
                str(path.relative_to(root)): file_sha256(path) for path in code_paths
            }),
            "config_sha256": file_sha256(resolved_config),
            "environment_sha256": canonical_sha256({
                "runtime_versions": collect_runtime_versions(),
                "device": development["behavior"]["device"],
            }),
        }
        plan_inputs = {
            "bindings": bindings,
            "screen_prompt_ids": [prompt["prompt_id"] for prompt in screen_prompts],
            "confirm_prompt_ids": [prompt["prompt_id"] for prompt in confirm_prompts],
            "benign_prompt_ids": [prompt["prompt_id"] for prompt in benign_prompts],
            "vector_ids_by_index": vector_ids_by_index,
            "dose_binding": dose_binding,
        }
        p1_primary_gate = development_validation.get("p1_primary_gate")
        registry = construct_plan_from_inputs(
            plan_inputs, p1_primary_gate=p1_primary_gate
        )
        support_rows = select_support_identities(
            registry,
            screen_prompt_ids=plan_inputs["screen_prompt_ids"],
            vector_ids_by_index=vector_ids_by_index,
        )
    guard_report = guard.report
    if guard_report["blocked_attempt_count"] != 0:
        raise PipelineError("support validate-only attempted a forbidden offline operation")

    prompt_text_by_id = {prompt["prompt_id"]: prompt["content"] for prompt in all_prompts}
    messages_by_prompt_id = {prompt["prompt_id"]: prompt["messages"] for prompt in all_prompts}
    return PreparedSupportScreen(
        config_path=resolved_config,
        config=config,
        development=development,
        development_validation=development_validation,
        registry=registry,
        support_rows=support_rows,
        prompt_text_by_id=prompt_text_by_id,
        messages_by_prompt_id=messages_by_prompt_id,
        vector_ids_by_index=vector_ids_by_index,
        vector_index_by_id=vector_index_by_id,
        dose_binding=dose_binding,
        behavior_identity=behavior_identity,
        judge_model_identity=judge_identity,
        p1_primary_gate=p1_primary_gate,
        plan_inputs=plan_inputs,
        offline_guard_report=guard_report,
    )


def validate_only(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> dict[str, Any]:
    prepared = prepare_support_screen(
        config_path,
        repo_root=repo_root,
        model_asset_inspector=model_asset_inspector,
        development_validator=development_validator,
    )
    counts = {
        anchor: sum(
            row["identity"]["anchor"] == anchor for row in prepared.support_rows
        )
        for anchor in SUPPORT_ANCHORS
    }
    doses = validate_dose_binding(prepared.dose_binding)
    return {
        "schema_version": "paper1-stage3-support-screen-validation-v1",
        "status": "SUPPORT_SCREEN_RUNNER_VALIDATE_ONLY_PASS",
        "validate_only": True,
        "run_mode": "paper",
        "canonical_plan_count": len(prepared.registry),
        "support_identity_count": len(prepared.support_rows),
        "downstream_pending_identity_count": len(prepared.registry) - len(prepared.support_rows),
        "anchor_identity_counts": counts,
        "screen_prompt_count": len(prepared.plan_inputs["screen_prompt_ids"]),
        "screen_vector_indices": list(SCREEN_VECTOR_INDICES),
        "estimator": "mu_all_tw",
        "c_by_anchor": {
            anchor: float.fromhex(doses[anchor]["mu_all_tw"]["c_hex"])
            for anchor in SUPPORT_ANCHORS
        },
        "p1_primary_gate": prepared.p1_primary_gate,
        "p1_gate_changes_support_identities": False,
        "model_weights_loaded": False,
        "forward_executed": False,
        "generation_run": False,
        "judge_run": False,
        "support_run": False,
        "p2_run": False,
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


def reconcile_support_stage(
    prepared: PreparedSupportScreen,
    *,
    generation_records: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate exactly the 900 terminal support chains, leaving downstream pending."""
    support_by_id = {
        row["logical_id"]: row["identity"] for row in prepared.support_rows
    }
    support_ids = set(support_by_id)
    generations = _record_index(
        generation_records, label="support generation set", validator=validate_generation_record
    )
    judges = _record_index(
        judge_records, label="support judge set", validator=validate_judge_record
    )
    responses = _record_index(
        response_records, label="support response set", validator=validate_support_record
    )
    disposition_by_id = _record_index(
        dispositions,
        label="support disposition set",
        validator=validate_execution_disposition,
    )
    for label, observed_ids in (
        ("generation", set(generations)),
        ("response", set(responses)),
        ("disposition", set(disposition_by_id)),
    ):
        if observed_ids != support_ids:
            raise IdentityError(f"support {label} set must cover exactly the 900 scheduled IDs")
    completed_generation_ids = {
        logical_id
        for logical_id, record in generations.items()
        if record["generation_completed"]
    }
    if set(judges) != completed_generation_ids:
        raise IdentityError("support judge set must equal the completed-generation IDs")

    terminal_counts = {terminal: 0 for terminal in TERMINAL_DISPOSITIONS}
    fake_flags: set[bool] = set()
    validated_responses: dict[str, dict[str, Any]] = {}
    for logical_id, identity in support_by_id.items():
        generation = generations[logical_id]
        judge = judges.get(logical_id)
        try:
            response = validate_support_materialization(
                responses[logical_id],
                registry=prepared.registry,
                generation_record=generation,
                judge_record=judge,
                dose_binding=prepared.dose_binding,
            )
        except RecordSchemaError as exc:
            raise PipelineError("support response materialization failed") from exc
        disposition = disposition_by_id[logical_id]
        terminal = response_terminal_disposition(identity, response, generation, judge)
        if (
            disposition["identity_sha256"] != canonical_sha256(identity)
            or disposition["terminal_disposition"] != terminal
            or disposition["generation_record_sha256"] != generation["record_sha256"]
            or disposition["judge_record_sha256"] != (
                None if judge is None else judge["record_sha256"]
            )
            or disposition["response_record_sha256"] != response["record_sha256"]
            or disposition["integrity_block_reason"] is not None
        ):
            raise PipelineError("support disposition differs from terminal record lineage")
        terminal_counts[terminal] += 1
        fake_flags.add(generation["fake_backend"])
        fake_flags.add(response["fake_backend"])
        if judge is not None:
            fake_flags.add(judge["fake_backend"])
        validated_responses[logical_id] = response
    if len(fake_flags) != 1:
        raise PipelineError("support stage mixes real and fake backend provenance")
    fake_backend = fake_flags.pop()

    anchor_rows: dict[str, dict[str, int]] = {}
    for anchor in SUPPORT_ANCHORS:
        scheduled_ids = {
            logical_id
            for logical_id, identity in support_by_id.items()
            if identity["anchor"] == anchor
        }
        observed = [validated_responses[logical_id] for logical_id in scheduled_ids]
        row = {
            "scheduled": len(scheduled_ids),
            "unique_scheduled": len(scheduled_ids),
            "observed": len(observed),
            "retained": sum(record["retained"] is True for record in observed),
            "identity_collisions": 0,
            "missing_scheduled": len(scheduled_ids - set(validated_responses)),
            "unexpected": len(set(validated_responses) - support_ids),
            "denominator_failures": sum(
                record["dose_denominator_valid"] is False for record in observed
            ),
            "dose_geometry_failures": sum(
                record["dose_geometry_finite"] is False for record in observed
            ),
            "post_dtype_alpha_failures": sum(
                record["post_dtype_alpha_finite"] is False for record in observed
            ),
        }
        row["dose_failures"] = (
            row["denominator_failures"]
            + row["dose_geometry_failures"]
            + row["post_dtype_alpha_failures"]
        )
        anchor_rows[anchor] = row
    statuses = classify_support({"anchors": anchor_rows})

    all_rows = prepared.registry.records()
    block_counts = {block: 0 for block in BLOCK_BUDGET}
    for registry_row in all_rows:
        block_counts[registry_row["identity"]["block"]] += 1
    if block_counts != BLOCK_BUDGET:
        raise IdentityError("canonical plan block counts changed before support ledger creation")
    downstream_by_anchor = {
        "A": block_counts["P2_A_all"] + block_counts["P2_A_content"],
        "T": (
            block_counts["P2_T_all"]
            + block_counts["P2_T_content"]
            + block_counts["benign_T"]
        ),
        "H": 0,
    }
    downstream_pending = len(prepared.registry) - len(prepared.support_rows)
    return {
        "schema_version": "paper1-stage3-support-screen-ledger-v1",
        "run_mode": "paper",
        "stage": "support_screen",
        "paper_result_eligible": False,
        "fake_backend": fake_backend,
        "formal_experiment_run": not fake_backend,
        "canonical_plan_count": len(prepared.registry),
        "canonical_registry_sha256": prepared.registry.manifest()["registry_sha256"],
        "support_scheduled": len(prepared.support_rows),
        "support_terminal": len(disposition_by_id),
        "support_only_reconciliation": True,
        "complete_stage3_reconciliation": False,
        "downstream_pending_identity_count": downstream_pending,
        "downstream_dispositions_materialized": False,
        "p1_primary_gate": prepared.p1_primary_gate,
        "p1_gate_changes_support_identities": False,
        "terminal_partition": terminal_counts,
        "anchors": {
            anchor: {
                **anchor_rows[anchor],
                "status": statuses[anchor],
                "downstream_logical_ids_pending": downstream_by_anchor[anchor],
                "estimation_only": (
                    anchor in {"A", "T"} and statuses[anchor] == "SUPPORT_LIMITED"
                ),
            }
            for anchor in SUPPORT_ANCHORS
        },
        "k1_additional_generation_calls": 0,
        "k1_additional_judge_calls": 0,
    }


def _aggregate_behavior_lifecycle(
    lifecycles: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if len(lifecycles) != len(SCREEN_VECTOR_INDICES):
        raise PipelineError("behavior lifecycle must cover all ten screen vectors")
    required = (
        "behavior_released",
        "behavior_hook_removed",
        "behavior_model_reference_cleared",
        "behavior_tokenizer_reference_cleared",
        "gc_collect_called",
    )
    if any(any(item.get(field) is not True for field in required) for item in lifecycles):
        raise PipelineError("a behavior backend did not release completely")
    if any(item.get("models_concurrently_resident") is not False for item in lifecycles):
        raise PipelineError("behavior lifecycle reported concurrent model residence")
    cuda_available = any(item.get("cuda_available") is True for item in lifecycles)
    return {
        "schema_version": "paper1-stage3-sequential-lifecycle-v1",
        "behavior_released": True,
        "behavior_hook_removed": True,
        "behavior_model_reference_cleared": True,
        "behavior_tokenizer_reference_cleared": True,
        "gc_collect_called": True,
        "gc_collected_count": sum(
            int(item.get("gc_collected_count", 0)) for item in lifecycles
        ),
        "cuda_available": cuda_available,
        "cuda_synchronize_called": (
            all(item.get("cuda_synchronize_called") is True for item in lifecycles)
            if cuda_available
            else False
        ),
        "cuda_empty_cache_called": (
            all(item.get("cuda_empty_cache_called") is True for item in lifecycles)
            if cuda_available
            else False
        ),
        "judge_loaded_after_behavior_release": False,
        "models_concurrently_resident": False,
        "behavior_session_count": len(lifecycles),
    }


def load_real_behavior_backend(
    prepared: PreparedSupportScreen, vector_index: int
) -> RealBehaviorBackend:
    behavior = prepared.development["behavior"]
    vector_path = _resolve_repo_file(
        ROOT,
        prepared.development["vector_pool"]["tensor_relative_path"],
        "vector tensor",
    )
    return RealBehaviorBackend.from_pretrained(
        model_path=behavior["checkpoint_path"],
        tokenizer_path=behavior["tokenizer_path"],
        vector_path=vector_path,
        vector_index=vector_index,
        dose_binding=prepared.dose_binding,
        layer=behavior["layer"],
        hook_site=behavior["hook_site"],
        dtype=behavior["dtype"],
        device=behavior["device"],
        trust_remote_code=behavior["trust_remote_code"],
        trust_remote_code_reason=behavior["trust_remote_code_reason"],
    )


def load_real_judge_backend(
    prepared: PreparedSupportScreen, lifecycle: Mapping[str, Any]
) -> RealJudgeBackend:
    judge = prepared.development["judge"]
    return RealJudgeBackend.from_pretrained(
        model_path=judge["checkpoint_path"],
        tokenizer_path=judge["tokenizer_path"],
        device=judge["device"],
        lifecycle=lifecycle,
        trust_remote_code=judge["trust_remote_code"],
        trust_remote_code_reason=judge["trust_remote_code_reason"],
    )


def _disposition(
    identity: Mapping[str, Any],
    generation: Mapping[str, Any],
    judge: Mapping[str, Any] | None,
    response: Mapping[str, Any],
) -> dict[str, Any]:
    record = {
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
    }
    return validate_execution_disposition(record)


def execute_support_screen(
    prepared: PreparedSupportScreen,
    *,
    behavior_backend_factory: Callable[
        [PreparedSupportScreen, int], Any
    ] = load_real_behavior_backend,
    judge_backend_factory: Callable[
        [PreparedSupportScreen, Mapping[str, Any]], Any
    ] = load_real_judge_backend,
) -> SupportRunArtifacts:
    """Run the same 900-chain orchestration for real or injected fake backends."""
    generation_by_id: dict[str, dict[str, Any]] = {}
    behavior_lifecycles: list[Mapping[str, Any]] = []
    backend_fake_flags: set[bool] = set()
    guard = offline_execution_guard()
    with guard:
        for vector_index in SCREEN_VECTOR_INDICES:
            backend = behavior_backend_factory(prepared, vector_index)
            capability = getattr(backend, "capability", None)
            backend_fake_flags.add(capability is None)
            try:
                producer = GenerationProducer(
                    prepared.registry,
                    backend,
                    run_mode="paper",
                    generation_config=DECODE_CONFIG,
                    fake_backend=capability is None,
                    capability=capability,
                    item_budget=PAPER_LOGICAL_GENERATION,
                )
                expected_vector_id = prepared.vector_ids_by_index[vector_index]
                rows = [
                    row
                    for row in prepared.support_rows
                    if row["identity"]["vector_id"] == expected_vector_id
                ]
                if len(rows) != 90:
                    raise IdentityError("each screen vector must schedule exactly 90 identities")
                for row in rows:
                    logical_id = row["logical_id"]
                    identity = row["identity"]
                    generation_by_id[logical_id] = validate_generation_record(
                        producer.produce(
                            logical_id,
                            {
                                "logical_id": logical_id,
                                "generation_config": DECODE_CONFIG,
                                "messages": prepared.messages_by_prompt_id[
                                    identity["prompt_id"]
                                ],
                            },
                        )
                    )
            finally:
                if not getattr(backend, "released", False):
                    behavior_lifecycles.append(backend.release())
        behavior_lifecycle = _aggregate_behavior_lifecycle(behavior_lifecycles)

        judge_backend = judge_backend_factory(prepared, behavior_lifecycle)
        judge_capability = getattr(judge_backend, "capability", None)
        backend_fake_flags.add(judge_capability is None)
        judge_by_id: dict[str, dict[str, Any]] = {}
        try:
            producer_identity = getattr(judge_backend, "producer_identity", None)
            if not isinstance(producer_identity, Mapping):
                raise PipelineError("judge backend lacks its canonical producer identity")
            for row in prepared.support_rows:
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
                                "prompt": prepared.prompt_text_by_id[identity["prompt_id"]],
                                "response": generation["output_text"],
                                "domain": "harmful",
                            },
                        },
                        registry=prepared.registry,
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
    if guard.report["blocked_attempt_count"] != 0:
        raise PipelineError("support execution attempted a forbidden offline operation")
    if len(backend_fake_flags) != 1:
        raise PipelineError("support execution mixes real and fake backend sessions")

    generations: list[dict[str, Any]] = []
    judges: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for row in prepared.support_rows:
        logical_id = row["logical_id"]
        identity = row["identity"]
        generation = generation_by_id[logical_id]
        judge = judge_by_id.get(logical_id)
        dose_evidence = generation["attempts"][-1]["diagnostics"].get("dose_evidence")
        response = build_block_response_record(
            identity=identity,
            generation_record=generation,
            judge_record=judge,
            dose_evidence=dose_evidence,
        )
        generations.append(generation)
        if judge is not None:
            judges.append(judge)
        responses.append(response)
        dispositions.append(_disposition(identity, generation, judge, response))
    ledger = reconcile_support_stage(
        prepared,
        generation_records=generations,
        judge_records=judges,
        response_records=responses,
        dispositions=dispositions,
    )
    return SupportRunArtifacts(
        generation_records=tuple(generations),
        judge_records=tuple(judges),
        response_records=tuple(responses),
        dispositions=tuple(dispositions),
        support_ledger=ledger,
        behavior_lifecycle=behavior_lifecycle,
        judge_lifecycle=judge_lifecycle,
    )


def default_output_directory(
    prepared: PreparedSupportScreen, run_id: str
) -> Path:
    if not isinstance(run_id, str) or SAFE_RUN_ID.fullmatch(run_id) is None:
        raise PipelineError("support-screen run-id contains invalid characters")
    configured_root = Path(prepared.config["output_root"]).resolve()
    if configured_root != OUTPUT_ROOT.resolve():
        raise PipelineError("support-screen output root differs from the fixed paper root")
    return configured_root / run_id


def _reserve_output_directory(path: Path) -> Path:
    output = path.resolve()
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


def run_prepared_support_screen(
    prepared: PreparedSupportScreen,
    *,
    run_id: str,
    behavior_backend_factory: Callable[
        [PreparedSupportScreen, int], Any
    ] = load_real_behavior_backend,
    judge_backend_factory: Callable[
        [PreparedSupportScreen, Mapping[str, Any]], Any
    ] = load_real_judge_backend,
    output_directory_resolver: Callable[
        [PreparedSupportScreen, str], Path
    ] = default_output_directory,
) -> dict[str, Any]:
    output_directory = _reserve_output_directory(
        output_directory_resolver(prepared, run_id)
    )
    store = OutputStore(output_directory)
    artifacts = execute_support_screen(
        prepared,
        behavior_backend_factory=behavior_backend_factory,
        judge_backend_factory=judge_backend_factory,
    )
    store.write_json_once("logical_registry.json", prepared.registry.manifest())
    store.write_json_once(
        "support_identities.json",
        _record_document(
            "paper1-stage3-support-identity-set-v1", prepared.support_rows
        ),
    )
    store.write_json_once(
        "generation_records.json",
        _record_document(
            "paper1-stage3-support-generation-set-v1", artifacts.generation_records
        ),
    )
    store.write_json_once(
        "judge_records.json",
        _record_document("paper1-stage3-support-judge-set-v1", artifacts.judge_records),
    )
    store.write_json_once(
        "response_records.json",
        _record_document(
            "paper1-stage3-support-response-set-v1", artifacts.response_records
        ),
    )
    store.write_json_once(
        "execution_dispositions.json",
        _record_document(
            "paper1-stage3-support-disposition-set-v1", artifacts.dispositions
        ),
    )
    store.write_json_once("support_ledger.json", artifacts.support_ledger)
    execution_identity = {
        "schema_version": "paper1-stage3-support-screen-execution-v1",
        "run_id": run_id,
        "run_mode": "paper",
        "fake_backend": artifacts.support_ledger["fake_backend"],
        "paper_result_eligible": False,
        "formal_experiment_run": artifacts.support_ledger["formal_experiment_run"],
        "real_support_run": not artifacts.support_ledger["fake_backend"],
        "p2_run": False,
        "canonical_registry_sha256": prepared.registry.manifest()["registry_sha256"],
        "support_ledger_sha256": canonical_sha256(artifacts.support_ledger),
        "behavior_lifecycle": artifacts.behavior_lifecycle,
        "judge_lifecycle": artifacts.judge_lifecycle,
    }
    store.write_json_once("execution_identity.json", execution_identity)
    fake_backend = artifacts.support_ledger["fake_backend"]
    return {
        "status": (
            "SUPPORT_SCREEN_FAKE_900_PATH_PASS"
            if fake_backend
            else "SUPPORT_SCREEN_REAL_RUN_PASS"
        ),
        "output_directory": str(output_directory),
        "run_id": run_id,
        "run_mode": "paper",
        "canonical_plan_count": len(prepared.registry),
        "support_identity_count": len(prepared.support_rows),
        "anchor_status": {
            anchor: artifacts.support_ledger["anchors"][anchor]["status"]
            for anchor in SUPPORT_ANCHORS
        },
        "fake_backend": fake_backend,
        "paper_result_eligible": False,
        "formal_experiment_run": not fake_backend,
        "real_support_run": not fake_backend,
        "p2_run": False,
        "complete_stage3_reconciliation": False,
    }


def run_support_screen(
    config_path: Path,
    *,
    run_mode: str,
    run_id: str,
) -> dict[str, Any]:
    if run_mode != "paper":
        raise PipelineError("support-screen execution supports only --run-mode paper")
    prepared = prepare_support_screen(config_path)
    return run_prepared_support_screen(prepared, run_id=run_id)


__all__ = [
    "DEFAULT_CONFIG",
    "PreparedSupportScreen",
    "SupportRunArtifacts",
    "construct_plan_from_inputs",
    "execute_support_screen",
    "prepare_support_screen",
    "reconcile_support_stage",
    "run_prepared_support_screen",
    "run_support_screen",
    "select_support_identities",
    "validate_only",
    "validate_support_config",
]
