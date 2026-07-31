"""Logical planning, budgets, and non-overwriting output controls."""

from __future__ import annotations

import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .core import (
    ACTIVE_PROFILE,
    HUMAN_ITEMS,
    PAPER_LOGICAL_GENERATION,
    RUN_MODE_ITEM_LIMITS,
    IdentityError,
    LogicalIdentityRegistry,
    PipelineError,
    canonical_sha256,
    canonical_json,
    classify_support,
    validate_run_mode,
)
from .dose import validate_dose_binding
from .json_schema import SchemaDefinitionError, SchemaValidationError, validate_schema
from .records import (
    RecordSchemaError,
    validate_benign_materialization,
    validate_generation_record,
    validate_judge_record,
    validate_p2_materialization,
    validate_response_materialization,
    validate_support_materialization,
    validate_support_record,
)


PROMPT_FRAME_SIZES = {
    "behavior_screen": 30,
    "behavior_confirmation": 50,
    "benign_confirmation": 30,
    "p1_harmful": 100,
    "p1_benign": 100,
}
BLOCK_BUDGET = {
    "support": 900,
    "P2_A_all": 1000,
    "P2_A_content": 1000,
    "P2_T_all": 1000,
    "P2_T_content": 1000,
    "harmful_clean": 50,
    "benign_T": 600,
    "benign_clean": 30,
}


class OutputStore:
    """Write JSON outputs once below an explicit output directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise PipelineError("output root may not be a symlink")

    def _path(self, relative_path: str) -> Path:
        posix = PurePosixPath(relative_path)
        if posix.is_absolute() or ".." in posix.parts or not posix.parts:
            raise PipelineError("output path must be a relative path below the output root")
        path = self.root.joinpath(*posix.parts)
        try:
            path.resolve().relative_to(self.root)
        except ValueError as exc:
            raise PipelineError("output path escapes the output root") from exc
        return path

    def write_json_once(self, relative_path: str, document: Mapping[str, Any]) -> Path:
        path = self._path(relative_path)
        if path.exists() or path.is_symlink():
            raise PipelineError(f"refusing to overwrite output: {relative_path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            json.loads(canonical_json(dict(document))),
            ensure_ascii=True,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
        return path


def assert_budget(block_counts: Mapping[str, int]) -> dict[str, Any]:
    if dict(block_counts) != BLOCK_BUDGET:
        raise PipelineError(f"logical budget differs from the current design: {dict(block_counts)}")
    total = sum(block_counts.values())
    if total != PAPER_LOGICAL_GENERATION:
        raise PipelineError(f"logical generation total changed: {total}")
    return {
        "block_counts": dict(block_counts),
        "logical_generation": total,
        "first_pass_scheduled_judge": total,
        "k1_reuse": 0,
        "human_items": HUMAN_ITEMS,
    }


def _require_cartesian_cell(
    identities: Sequence[Mapping[str, Any]],
    *,
    prompt_count: int,
    vector_count: int,
    label: str,
) -> tuple[set[str], set[str]]:
    prompts = {identity["prompt_id"] for identity in identities}
    vectors = {identity["vector_id"] for identity in identities}
    pairs = {(identity["prompt_id"], identity["vector_id"]) for identity in identities}
    if (
        len(prompts) != prompt_count
        or len(vectors) != vector_count
        or len(pairs) != prompt_count * vector_count
        or pairs != {(prompt, vector) for prompt in prompts for vector in vectors}
    ):
        raise IdentityError(f"paper {label} identities do not form the fixed prompt/vector grid")
    return prompts, vectors


def _validate_paper_registry_shape(registry_records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Re-derive the complete paper plan shape instead of trusting its total size."""
    by_block: dict[str, list[Mapping[str, Any]]] = {block: [] for block in BLOCK_BUDGET}
    rendered_by_prompt: dict[str, str] = {}
    binding_fields = (
        "model_revision", "template_sha256", "layer", "hook_site", "phase", "use_cache",
        "generation_config_sha256", "code_sha256", "config_sha256", "environment_sha256",
    )
    binding_values: set[tuple[Any, ...]] = set()
    dose_by_cell: dict[tuple[str, str], set[tuple[str, str, str, str]]] = {}
    for row in registry_records:
        identity = row["identity"]
        block = identity["block"]
        if block not in by_block:
            raise IdentityError(f"paper registry contains an unknown block: {block}")
        by_block[block].append(identity)
        binding_values.add(tuple(identity[field] for field in binding_fields))
        previous_render = rendered_by_prompt.setdefault(
            identity["prompt_id"], identity["rendered_prompt_sha256"]
        )
        if previous_render != identity["rendered_prompt_sha256"]:
            raise IdentityError("paper registry assigns multiple rendered hashes to one prompt")
        if identity["estimator"] != "clean":
            cell = (identity["anchor"], identity["estimator"])
            dose_by_cell.setdefault(cell, set()).add(tuple(
                identity[field]
                for field in ("c_hex", "alpha_pre_dtype_hex", "alpha_post_dtype_hex", "rho_hex")
            ))
    counts = {block: len(rows) for block, rows in by_block.items()}
    assert_budget(counts)
    if len(binding_values) != 1 or any(len(values) != 1 for values in dose_by_cell.values()):
        raise IdentityError("paper registry changes bindings or dose within a scheduled cell")

    support_prompts: set[str] | None = None
    support_vectors: set[str] | None = None
    for anchor in ("A", "T", "H"):
        rows = [identity for identity in by_block["support"] if identity["anchor"] == anchor]
        prompts, vectors = _require_cartesian_cell(
            rows, prompt_count=30, vector_count=10, label=f"support-{anchor}"
        )
        if support_prompts is None:
            support_prompts, support_vectors = prompts, vectors
        elif prompts != support_prompts or vectors != support_vectors:
            raise IdentityError("paper support anchors do not share the fixed screen grid")

    confirmation_prompts: set[str] | None = None
    confirmation_vectors: set[str] | None = None
    for block in ("P2_A_all", "P2_A_content", "P2_T_all", "P2_T_content"):
        prompts, vectors = _require_cartesian_cell(
            by_block[block], prompt_count=50, vector_count=20, label=block
        )
        if confirmation_prompts is None:
            confirmation_prompts, confirmation_vectors = prompts, vectors
        elif prompts != confirmation_prompts or vectors != confirmation_vectors:
            raise IdentityError("paper P2 cells do not share the fixed confirmation grid")
    assert support_prompts is not None and support_vectors is not None
    assert confirmation_prompts is not None and confirmation_vectors is not None
    if support_prompts & confirmation_prompts or support_vectors & confirmation_vectors:
        raise IdentityError("paper screen/confirmation prompt or vector frames overlap")
    if {identity["prompt_id"] for identity in by_block["harmful_clean"]} != confirmation_prompts:
        raise IdentityError("paper harmful-clean frame differs from the P2 confirmation frame")
    benign_prompts, benign_vectors = _require_cartesian_cell(
        by_block["benign_T"], prompt_count=30, vector_count=20, label="benign-T"
    )
    if benign_vectors != confirmation_vectors:
        raise IdentityError("paper benign-T vectors differ from the P2 vector frame")
    if {identity["prompt_id"] for identity in by_block["benign_clean"]} != benign_prompts:
        raise IdentityError("paper benign-clean frame differs from the benign-T frame")
    return counts


def assert_run_budget(run_mode: str, scheduled_items: int, item_budget: int) -> dict[str, int | str]:
    mode = validate_run_mode(run_mode)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (scheduled_items, item_budget)):
        raise PipelineError("scheduled_items and item_budget must be integers")
    if scheduled_items < 0 or item_budget < 1 or scheduled_items > item_budget:
        raise PipelineError("scheduled item count exceeds the declared run budget")
    if mode == "smoke" and item_budget > 2:
        raise PipelineError("smoke budget may not exceed two items")
    if mode == "paper" and item_budget != PAPER_LOGICAL_GENERATION:
        raise PipelineError("paper item budget must equal 5,580")
    return {"run_mode": mode, "scheduled_items": scheduled_items, "item_budget": item_budget}


def assert_actual_call_budget(
    *,
    generation_unattempted: int,
    generation_technical_retries: int,
    prejudge_terminal: int,
    judge_parse_retries: int,
) -> dict[str, int]:
    values = {
        "generation_unattempted": generation_unattempted,
        "generation_technical_retries": generation_technical_retries,
        "prejudge_terminal": prejudge_terminal,
        "judge_parse_retries": judge_parse_retries,
    }
    for field, value in values.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise PipelineError(f"{field} must be a nonnegative integer")
    generation_first_pass = PAPER_LOGICAL_GENERATION - generation_unattempted
    if generation_first_pass < 0 or generation_technical_retries > generation_first_pass:
        raise PipelineError("generation accounting exceeds the current registry")
    judge_first_pass = generation_first_pass - prejudge_terminal
    if judge_first_pass < 0 or judge_parse_retries > judge_first_pass:
        raise PipelineError("judge accounting exceeds eligible identities")
    generation_calls = generation_first_pass + generation_technical_retries
    judge_calls = judge_first_pass + judge_parse_retries
    if generation_calls > 2 * PAPER_LOGICAL_GENERATION or judge_calls > 2 * PAPER_LOGICAL_GENERATION:
        raise PipelineError("actual calls exceed one identical retry per logical identity")
    return {
        "logical_generation": PAPER_LOGICAL_GENERATION,
        "generation_first_pass_calls": generation_first_pass,
        "generation_technical_retries": generation_technical_retries,
        "generation_calls": generation_calls,
        "judge_first_pass_calls": judge_first_pass,
        "judge_parse_retries": judge_parse_retries,
        "judge_calls": judge_calls,
        "generation_unattempted": generation_unattempted,
        "prejudge_terminal": prejudge_terminal,
    }


def status_with_analysis_precedence(support_status: str, analysis_estimable: bool) -> str:
    if support_status == "NON_ESTIMABLE_IDENTITY":
        return "NON_ESTIMABLE_IDENTITY"
    if not analysis_estimable:
        return "NON_ESTIMABLE_ANALYSIS"
    if support_status == "SUPPORTED":
        return "ESTIMATION_ONLY_SUPPORTED"
    if support_status == "SUPPORT_LIMITED":
        return "ESTIMATION_ONLY_SUPPORT_LIMITED"
    raise PipelineError(f"unknown support status: {support_status}")


def _require_exact_ids(values: Sequence[str], expected_count: int, field: str) -> list[str]:
    items = list(values)
    if len(items) != expected_count or len(set(items)) != expected_count:
        raise IdentityError(f"{field} requires exactly {expected_count} unique ordered IDs")
    if any(not isinstance(value, str) or not value for value in items):
        raise IdentityError(f"{field} contains an invalid ID")
    return items


def _finite_hex(value: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise IdentityError(f"{field} must be a float.hex string")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise IdentityError(f"{field} is not a float.hex string") from exc
    if not math.isfinite(parsed) or value != parsed.hex():
        raise IdentityError(f"{field} is not a canonical finite float.hex string")
    return value


def _common_identity(
    bindings: Mapping[str, Any],
    *,
    block: str,
    domain: str,
    split: str,
    prompt_id: str,
    vector_id: str | None,
    estimator: str,
    anchor: str,
    dose: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "profile": ACTIVE_PROFILE,
        "block": block,
        "domain": domain,
        "split": split,
        "model_revision": bindings["model_revision"],
        "template_sha256": bindings["template_sha256"],
        "rendered_prompt_sha256": bindings["rendered_prompt_sha256_by_id"][prompt_id],
        "prompt_id": prompt_id,
        "vector_id": vector_id,
        "estimator": estimator,
        "anchor": anchor,
        "c_hex": _finite_hex(dose["c_hex"], "c_hex"),
        "alpha_pre_dtype_hex": _finite_hex(dose["alpha_pre_dtype_hex"], "alpha_pre_dtype_hex"),
        "alpha_post_dtype_hex": _finite_hex(dose["alpha_post_dtype_hex"], "alpha_post_dtype_hex"),
        "rho_hex": _finite_hex(dose["rho_hex"], "rho_hex"),
        "layer": bindings["layer"],
        "hook_site": bindings["hook_site"],
        "phase": "decode-only",
        "use_cache": True,
        "generation_config_sha256": bindings["generation_config_sha256"],
        "code_sha256": bindings["code_sha256"],
        "config_sha256": bindings["config_sha256"],
        "environment_sha256": bindings["environment_sha256"],
    }


def build_logical_plan(
    *,
    bindings: Mapping[str, Any],
    screen_prompt_ids: Sequence[str],
    confirm_prompt_ids: Sequence[str],
    benign_prompt_ids: Sequence[str],
    vector_ids_by_index: Mapping[int, str],
    dose_binding: Mapping[str, Any],
) -> LogicalIdentityRegistry:
    """Build exactly the current paper design's 5,580 response identities."""
    screen = _require_exact_ids(screen_prompt_ids, 30, "screen_prompt_ids")
    confirm = _require_exact_ids(confirm_prompt_ids, 50, "confirm_prompt_ids")
    benign = _require_exact_ids(benign_prompt_ids, 30, "benign_prompt_ids")
    if set(screen) & set(confirm):
        raise IdentityError("screen and confirmation harmful prompt IDs must be disjoint")
    if set(vector_ids_by_index) != set(range(30)):
        raise IdentityError("vector index registry must be exactly 0..29")
    vectors = list(vector_ids_by_index.values())
    if len(set(vectors)) != 30 or any(not isinstance(value, str) or not value for value in vectors):
        raise IdentityError("vector identities must be 30 unique nonempty strings")
    required_rendered = set(screen) | set(confirm) | set(benign)
    if set(bindings.get("rendered_prompt_sha256_by_id", {})) != required_rendered:
        raise IdentityError("rendered prompt hash registry must exactly cover the three prompt frames")

    doses = validate_dose_binding(dose_binding)
    registry = LogicalIdentityRegistry()
    for anchor in ("A", "T", "H"):
        for prompt_id in screen:
            for vector_index in range(10):
                registry.register(_common_identity(
                    bindings,
                    block="support",
                    domain="harmful",
                    split="D_behavior_screen",
                    prompt_id=prompt_id,
                    vector_id=vector_ids_by_index[vector_index],
                    estimator="mu_all_tw",
                    anchor=anchor,
                    dose=doses[anchor]["mu_all_tw"],
                ))

    cells = (
        ("P2_A_all", "A", "mu_all_tw"),
        ("P2_A_content", "A", "mu_content_tw"),
        ("P2_T_all", "T", "mu_all_tw"),
        ("P2_T_content", "T", "mu_content_tw"),
    )
    for block, anchor, estimator in cells:
        for prompt_id in confirm:
            for vector_index in range(10, 30):
                registry.register(_common_identity(
                    bindings,
                    block=block,
                    domain="harmful",
                    split="D_behavior_confirm",
                    prompt_id=prompt_id,
                    vector_id=vector_ids_by_index[vector_index],
                    estimator=estimator,
                    anchor=anchor,
                    dose=doses[anchor][estimator],
                ))

    clean_dose = {
        "c_hex": float(0.0).hex(),
        "alpha_pre_dtype_hex": float(0.0).hex(),
        "alpha_post_dtype_hex": float(0.0).hex(),
        "rho_hex": float(0.0).hex(),
    }
    for prompt_id in confirm:
        registry.register(_common_identity(
            bindings,
            block="harmful_clean",
            domain="harmful",
            split="D_behavior_confirm",
            prompt_id=prompt_id,
            vector_id=None,
            estimator="clean",
            anchor="clean",
            dose=clean_dose,
        ))
    for prompt_id in benign:
        for vector_index in range(10, 30):
            registry.register(_common_identity(
                bindings,
                block="benign_T",
                domain="benign",
                split="D_benign_confirm",
                prompt_id=prompt_id,
                vector_id=vector_ids_by_index[vector_index],
                estimator="mu_all_tw",
                anchor="T",
                dose=doses["T"]["mu_all_tw"],
            ))
        registry.register(_common_identity(
            bindings,
            block="benign_clean",
            domain="benign",
            split="D_benign_confirm",
            prompt_id=prompt_id,
            vector_id=None,
            estimator="clean",
            anchor="clean",
            dose=clean_dose,
        ))

    counts = {block: 0 for block in BLOCK_BUDGET}
    for item in registry.records():
        counts[item["identity"]["block"]] += 1
    assert_budget(counts)
    if len(registry) != PAPER_LOGICAL_GENERATION:
        raise AssertionError("current plan did not produce 5,580 identities")
    return registry


TERMINAL_DISPOSITIONS = (
    "COMPLETED_PARSED",
    "NON_ESTIMABLE_IDENTITY",
    "NON_ESTIMABLE_DOSE",
    "TERMINAL_GENERATION_TECHNICAL_FAILURE",
    "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
    "TERMINAL_GENERATION_INDETERMINATE_FAILURE",
    "TERMINAL_PREJUDGE_FAILURE",
    "TERMINAL_JUDGE_FAILURE",
    "TERMINAL_JUDGE_INDETERMINATE_FAILURE",
    "UNATTEMPTED_DUE_INTEGRITY_BLOCK",
)
_RECONCILIATION_TOKEN = object()


class VerifiedReconciliation(Mapping[str, Any]):
    """Read-only result that can only be issued by reconciliation in this module."""

    def __init__(self, document: Mapping[str, Any], token: object) -> None:
        if token is not _RECONCILIATION_TOKEN:
            raise PipelineError("verified reconciliation can only be issued by reconcile_execution")
        self.__canonical = canonical_json(dict(document))

    def __getitem__(self, key: str) -> Any:
        return json.loads(self.__canonical)[key]

    def __iter__(self):
        return iter(json.loads(self.__canonical))

    def __len__(self) -> int:
        return len(json.loads(self.__canonical))

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.__canonical)
INTEGRITY_BLOCK_REASONS = (
    "SUPPORT_A_NON_ESTIMABLE_IDENTITY",
    "SUPPORT_T_NON_ESTIMABLE_IDENTITY",
    "EXTERNAL_INPUT_INTEGRITY",
    "P1_DOSE_NON_ESTIMABLE",
)
DISPOSITION_FIELDS = {
    "schema_version", "logical_id", "identity_sha256", "terminal_disposition",
    "generation_record_sha256", "judge_record_sha256", "response_record_sha256",
    "integrity_block_reason",
}


def validate_execution_disposition(document: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validate_schema(
            document,
            Path(__file__).with_name("schemas") / "execution_disposition.schema.json",
        )
    except (SchemaDefinitionError, SchemaValidationError) as exc:
        raise PipelineError(f"execution disposition schema rejected document: {exc}") from exc
    if not isinstance(document, Mapping) or set(document) != DISPOSITION_FIELDS:
        raise PipelineError("execution disposition fields differ")
    if document["schema_version"] != "paper1-stage3-execution-disposition-v2":
        raise PipelineError("execution disposition schema_version mismatch")
    terminal = document["terminal_disposition"]
    if terminal not in TERMINAL_DISPOSITIONS:
        raise PipelineError("execution disposition terminal is not registered")
    hashes = (
        document["identity_sha256"],
        document["generation_record_sha256"],
        document["judge_record_sha256"],
        document["response_record_sha256"],
    )
    for index, value in enumerate(hashes):
        if value is None and index > 0:
            continue
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise PipelineError("execution disposition contains an invalid SHA256")
    reason = document["integrity_block_reason"]
    if terminal == "UNATTEMPTED_DUE_INTEGRITY_BLOCK":
        if reason not in INTEGRITY_BLOCK_REASONS or any(value is not None for value in hashes[1:]):
            raise PipelineError("unattempted disposition lacks an allowed integrity block")
    elif reason is not None or document["generation_record_sha256"] is None or document["response_record_sha256"] is None:
        raise PipelineError("attempted disposition lineage is incomplete")
    return json.loads(canonical_json(dict(document)))


def _unique_records(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    validator: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = validator(raw)
        logical_id = record.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in result:
            raise IdentityError(f"{label} contains a missing or duplicate logical ID")
        result[logical_id] = record
    return result


def _response_terminal(
    identity: Mapping[str, Any],
    response: Mapping[str, Any],
    generation: Mapping[str, Any],
    judge: Mapping[str, Any] | None,
) -> str:
    if identity["block"] != "harmful_clean":
        terminal = response.get("terminal_status")
        if terminal not in TERMINAL_DISPOSITIONS:
            raise PipelineError("response terminal disposition is not registered")
        return terminal
    if not generation["generation_completed"]:
        return {
            "TERMINAL_TECHNICAL_FAILURE": "TERMINAL_GENERATION_TECHNICAL_FAILURE",
            "TERMINAL_FAILURE": "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
            "TERMINAL_INDETERMINATE_FAILURE": "TERMINAL_GENERATION_INDETERMINATE_FAILURE",
        }[generation["terminal_status"]]
    if judge is None:
        return "TERMINAL_PREJUDGE_FAILURE"
    if judge["terminal_status"] == "PARSED":
        return "COMPLETED_PARSED"
    if judge["terminal_status"] == "TERMINAL_INDETERMINATE_FAILURE":
        return "TERMINAL_JUDGE_INDETERMINATE_FAILURE"
    return "TERMINAL_JUDGE_FAILURE"


def _validate_materialized_response(
    raw: Mapping[str, Any],
    *,
    identity: Mapping[str, Any],
    registry: LogicalIdentityRegistry,
    generation: Mapping[str, Any],
    judge: Mapping[str, Any] | None,
    dose_binding: Mapping[str, Any] | None,
) -> dict[str, Any]:
    block = identity["block"]
    if block == "support":
        if dose_binding is None:
            raise PipelineError("support reconciliation requires dose evidence")
        return validate_support_materialization(
            raw, registry=registry, generation_record=generation,
            judge_record=judge, dose_binding=dose_binding,
        )
    if block.startswith("P2_"):
        if dose_binding is None:
            raise PipelineError("P2 reconciliation requires dose evidence")
        return validate_p2_materialization(
            raw, registry=registry, generation_record=generation,
            judge_record=judge, dose_binding=dose_binding,
        )
    if block in {"benign_T", "benign_clean"}:
        if dose_binding is None:
            raise PipelineError("benign reconciliation requires dose evidence")
        return validate_benign_materialization(
            raw, registry=registry, generation_record=generation,
            judge_record=judge, dose_binding=dose_binding,
        )
    if block == "harmful_clean":
        return validate_response_materialization(
            raw, registry=registry, generation_record=generation, judge_record=judge,
        )
    raise IdentityError(f"no response validator for block: {block}")


def reconcile_execution(
    registry: LogicalIdentityRegistry,
    *,
    run_mode: str,
    generation_records: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    dose_binding: Mapping[str, Any] | None = None,
) -> VerifiedReconciliation:
    """Derive one complete, mutually exclusive terminal partition from source records."""
    mode = validate_run_mode(run_mode)
    registry_records = registry.records()
    scheduled = len(registry_records)
    block_counts = {block: 0 for block in BLOCK_BUDGET}
    for row in registry_records:
        block_counts[row["identity"]["block"]] += 1
    if mode == "paper":
        if scheduled != PAPER_LOGICAL_GENERATION:
            raise IdentityError("paper reconciliation requires the complete 5,580-ID registry")
        block_counts = _validate_paper_registry_shape(registry_records)
    if mode != "paper" and (scheduled < 1 or scheduled > RUN_MODE_ITEM_LIMITS[mode]):
        raise IdentityError(f"{mode} registry exceeds its actual run scope")
    identity_by_id = {record["logical_id"]: record["identity"] for record in registry_records}
    registry_ids = set(identity_by_id)
    if len(registry_ids) != scheduled:
        raise IdentityError("logical registry contains a collision")

    generation_by_id = _unique_records(
        generation_records, label="generation record set", validator=validate_generation_record
    )
    judge_by_id = _unique_records(
        judge_records, label="judge record set", validator=validate_judge_record
    )
    raw_response_by_id: dict[str, Mapping[str, Any]] = {}
    for raw in response_records:
        if not isinstance(raw, Mapping):
            raise PipelineError("response record must be an object")
        logical_id = raw.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in raw_response_by_id:
            raise IdentityError("response record set contains a missing or duplicate logical ID")
        raw_response_by_id[logical_id] = raw
    disposition_by_id = _unique_records(
        dispositions, label="execution disposition set", validator=validate_execution_disposition
    )
    for label, ids in (
        ("generation", set(generation_by_id)),
        ("judge", set(judge_by_id)),
        ("response", set(raw_response_by_id)),
        ("disposition", set(disposition_by_id)),
    ):
        unexpected = ids - registry_ids
        if unexpected:
            raise IdentityError(f"{label} set contains unexpected logical IDs")
    if set(disposition_by_id) != registry_ids:
        raise IdentityError("execution dispositions do not completely partition the registry")

    terminal_counts = {terminal: 0 for terminal in TERMINAL_DISPOSITIONS}
    materialized_response_by_id: dict[str, dict[str, Any]] = {}
    generation_completed = 0
    judge_parsed = 0
    generation_retries = 0
    judge_retries = 0
    for logical_id, identity in identity_by_id.items():
        identity_sha256 = canonical_sha256(identity)
        disposition = disposition_by_id[logical_id]
        if disposition["identity_sha256"] != identity_sha256:
            raise IdentityError("disposition identity hash differs from registry")
        generation = generation_by_id.get(logical_id)
        judge = judge_by_id.get(logical_id)
        raw_response = raw_response_by_id.get(logical_id)
        if disposition["terminal_disposition"] == "UNATTEMPTED_DUE_INTEGRITY_BLOCK":
            if generation is not None or judge is not None or raw_response is not None:
                raise PipelineError("integrity-blocked identity contains attempted records")
            reason = disposition["integrity_block_reason"]
            block = identity["block"]
            if reason == "SUPPORT_A_NON_ESTIMABLE_IDENTITY" and block not in {"P2_A_all", "P2_A_content"}:
                raise PipelineError("support A integrity block targets an unrelated identity")
            if reason == "SUPPORT_T_NON_ESTIMABLE_IDENTITY" and block not in {"P2_T_all", "P2_T_content", "benign_T"}:
                raise PipelineError("support T integrity block targets an unrelated identity")
            terminal_counts["UNATTEMPTED_DUE_INTEGRITY_BLOCK"] += 1
            continue
        if generation is None or raw_response is None:
            raise PipelineError("attempted identity lacks generation or terminal response")
        if (
            generation["logical_id"] != logical_id
            or generation["identity_sha256"] != identity_sha256
            or generation["run_mode"] != mode
        ):
            raise IdentityError("generation record differs from registry or run mode")
        if judge is not None:
            if (
                not generation["generation_completed"]
                or judge["identity_sha256"] != identity_sha256
                or judge["generation_record_sha256"] != generation["record_sha256"]
                or judge["domain"] != identity["domain"]
                or judge["run_mode"] != mode
            ):
                raise PipelineError("judge record lacks matching completed generation provenance")
        response = _validate_materialized_response(
            raw_response, identity=identity, registry=registry, generation=generation,
            judge=judge, dose_binding=dose_binding,
        )
        materialized_response_by_id[logical_id] = response
        terminal = _response_terminal(identity, response, generation, judge)
        if (
            disposition["terminal_disposition"] != terminal
            or disposition["generation_record_sha256"] != generation["record_sha256"]
            or disposition["judge_record_sha256"] != (
                None if judge is None else judge["record_sha256"]
            )
            or disposition["response_record_sha256"] != response["record_sha256"]
        ):
            raise PipelineError("execution disposition differs from materialized terminal lineage")
        generation_completed += int(generation["generation_completed"])
        generation_retries += generation["retry_count"]
        if judge is not None:
            judge_parsed += int(judge["judge_label_parsed"])
            judge_retries += len(judge["attempts"]) - 1
        terminal_counts[terminal] += 1

    if set(judge_by_id) - set(generation_by_id) or set(raw_response_by_id) - set(generation_by_id):
        raise PipelineError("orphan judge or response records remain after reconciliation")
    if sum(terminal_counts.values()) != scheduled:
        raise PipelineError("terminal partition count differs from registry")
    attempted = len(generation_by_id)
    judged = len(judge_by_id)
    completed_items = terminal_counts["COMPLETED_PARSED"]
    support_mapping = reconcile_support_mapping(
        registry,
        run_mode=mode,
        support_records=[
            materialized_response_by_id[logical_id]
            for logical_id, identity in identity_by_id.items()
            if identity["block"] == "support" and logical_id in materialized_response_by_id
        ],
        dispositions=dispositions,
    )
    document = {
        "schema_version": "paper1-stage3-execution-reconciliation-v1",
        "run_mode": mode,
        "paper_result_eligible": False,
        "registry_sha256": registry.manifest()["registry_sha256"],
        "block_counts": block_counts,
        "scheduled_logical_ids": scheduled,
        "generation_first_pass_scheduled": scheduled,
        "generation_first_pass_calls": attempted,
        "generation_completed": generation_completed,
        "generation_retry_calls": generation_retries,
        "generation_total_calls": attempted + generation_retries,
        "judge_first_pass_scheduled": scheduled,
        "judge_eligible": judged,
        "judge_first_pass_calls": judged,
        "judge_parsed": judge_parsed,
        "judge_retry_calls": judge_retries,
        "judge_total_calls": judged + judge_retries,
        "completed_item_count": completed_items,
        "failure_count": scheduled - completed_items,
        "unattempted_count": terminal_counts["UNATTEMPTED_DUE_INTEGRITY_BLOCK"],
        "terminal_partition": terminal_counts,
        "terminal_partition_sha256": canonical_sha256(
            [disposition_by_id[logical_id] for logical_id in identity_by_id]
        ),
        "support_mapping_sha256": canonical_sha256(support_mapping),
        "k1_additional_generation_calls": 0,
        "k1_additional_judge_calls": 0,
    }
    return VerifiedReconciliation(document, _RECONCILIATION_TOKEN)


def reconcile_support_mapping(
    registry: LogicalIdentityRegistry,
    *,
    run_mode: str,
    support_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive paper A/T/H support status and validate its fixed downstream mapping."""
    mode = validate_run_mode(run_mode)
    registry_rows = registry.records()
    if mode == "paper":
        if len(registry_rows) != PAPER_LOGICAL_GENERATION:
            raise IdentityError("paper support mapping requires the complete 5,580-ID registry")
        _validate_paper_registry_shape(registry_rows)
    support_identity_by_id = {
        row["logical_id"]: row["identity"]
        for row in registry_rows
        if row["identity"]["block"] == "support"
    }
    by_anchor: dict[str, set[str]] = {anchor: set() for anchor in ("A", "T", "H")}
    for logical_id, identity in support_identity_by_id.items():
        by_anchor[identity["anchor"]].add(logical_id)
    if mode == "paper" and any(len(by_anchor[anchor]) != 300 for anchor in by_anchor):
        raise IdentityError("paper support registry must schedule exactly 300 unique IDs per anchor")

    records_by_id: dict[str, Mapping[str, Any]] = {}
    duplicate_by_anchor = {anchor: 0 for anchor in by_anchor}
    unexpected_by_anchor = {anchor: 0 for anchor in by_anchor}
    for record in support_records:
        if not isinstance(record, Mapping):
            raise PipelineError("support response must be an object")
        try:
            validated = validate_support_record(record)
        except RecordSchemaError as exc:
            raise PipelineError("support mapping requires dedicated validated response records") from exc
        logical_id = validated["logical_id"]
        anchor = validated["anchor"]
        if logical_id not in support_identity_by_id:
            raise IdentityError("support response contains an unexpected logical ID")
        if logical_id in records_by_id:
            raise IdentityError("support response contains a duplicate logical ID")
        identity = support_identity_by_id[logical_id]
        if (
            validated["identity_sha256"] != canonical_sha256(identity)
            or validated["prompt_id"] != identity["prompt_id"]
            or validated["vector_id"] != identity["vector_id"]
            or validated["anchor"] != identity["anchor"]
            or validated["estimator"] != identity["estimator"]
        ):
            raise IdentityError("support response fields differ from the scheduled registry identity")
        records_by_id[logical_id] = validated

    summary_rows: dict[str, dict[str, int]] = {}
    for anchor in ("A", "T", "H"):
        scheduled_ids = by_anchor[anchor]
        observed = [records_by_id[logical_id] for logical_id in scheduled_ids if logical_id in records_by_id]
        summary_rows[anchor] = {
            "scheduled": len(scheduled_ids),
            "unique_scheduled": len(scheduled_ids),
            "observed": len(observed),
            "retained": sum(record.get("retained") is True for record in observed),
            "identity_collisions": duplicate_by_anchor[anchor],
            "missing_scheduled": len(scheduled_ids - set(records_by_id)),
            "unexpected": unexpected_by_anchor[anchor],
            "denominator_failures": sum(record.get("dose_denominator_valid") is False for record in observed),
            "dose_geometry_failures": sum(record.get("dose_geometry_finite") is False for record in observed),
            "post_dtype_alpha_failures": sum(record.get("post_dtype_alpha_finite") is False for record in observed),
        }
        summary_rows[anchor]["dose_failures"] = (
            summary_rows[anchor]["denominator_failures"]
            + summary_rows[anchor]["dose_geometry_failures"]
            + summary_rows[anchor]["post_dtype_alpha_failures"]
        )
    if mode == "paper":
        statuses = classify_support({"anchors": summary_rows})
    else:
        statuses = {
            anchor: (
                "NON_ESTIMABLE_IDENTITY"
                if summary_rows[anchor]["missing_scheduled"]
                or summary_rows[anchor]["identity_collisions"]
                or summary_rows[anchor]["unexpected"]
                else "SUPPORTED"
            )
            for anchor in ("A", "T", "H")
        }

    disposition_by_id = _unique_records(
        dispositions, label="support mapping disposition set",
        validator=validate_execution_disposition,
    )
    all_registry_ids = {row["logical_id"] for row in registry_rows}
    if set(disposition_by_id) != all_registry_ids:
        raise IdentityError("support mapping requires the complete disposition partition")
    identity_by_id = {row["logical_id"]: row["identity"] for row in registry_rows}
    support_reason_blocks = {
        "SUPPORT_A_NON_ESTIMABLE_IDENTITY": {"P2_A_all", "P2_A_content"},
        "SUPPORT_T_NON_ESTIMABLE_IDENTITY": {"P2_T_all", "P2_T_content", "benign_T"},
    }
    for logical_id, disposition in disposition_by_id.items():
        identity = identity_by_id[logical_id]
        if disposition["identity_sha256"] != canonical_sha256(identity):
            raise IdentityError("support mapping disposition identity differs from registry")
        reason = disposition["integrity_block_reason"]
        if reason in support_reason_blocks and identity["block"] not in support_reason_blocks[reason]:
            raise PipelineError("support integrity reason targets an unrelated registry identity")
    for logical_id in support_identity_by_id:
        disposition = disposition_by_id[logical_id]
        record = records_by_id.get(logical_id)
        if record is None:
            if disposition["terminal_disposition"] != "UNATTEMPTED_DUE_INTEGRITY_BLOCK":
                raise PipelineError("missing support response is not marked unattempted")
            continue
        if (
            disposition["terminal_disposition"] != record["terminal_status"]
            or disposition["generation_record_sha256"] != record["generation_record_sha256"]
            or disposition["judge_record_sha256"] != record["judge_record_sha256"]
            or disposition["response_record_sha256"] != record["record_sha256"]
            or disposition["integrity_block_reason"] is not None
        ):
            raise PipelineError("support disposition differs from its response lineage")
    downstream_blocks = {
        "A": {"P2_A_all", "P2_A_content"},
        "T": {"P2_T_all", "P2_T_content", "benign_T"},
        "H": set(),
    }
    downstream: dict[str, dict[str, Any]] = {}
    for anchor in ("A", "T", "H"):
        affected = {
            row["logical_id"]
            for row in registry_rows
            if row["identity"]["block"] in downstream_blocks[anchor]
        }
        expected_reason = f"SUPPORT_{anchor}_NON_ESTIMABLE_IDENTITY"
        mapped = {
            logical_id
            for logical_id in affected
            if disposition_by_id[logical_id]["terminal_disposition"]
            == "UNATTEMPTED_DUE_INTEGRITY_BLOCK"
            and disposition_by_id[logical_id]["integrity_block_reason"] == expected_reason
        }
        if anchor == "H" and affected:
            raise AssertionError("H must not have downstream confirmation identities")
        if statuses[anchor] == "NON_ESTIMABLE_IDENTITY":
            if anchor in {"A", "T"} and mapped != affected:
                raise PipelineError(f"support {anchor} non-estimable mapping is incomplete")
        elif mapped:
            raise PipelineError(f"support {anchor} executable mapping was incorrectly blocked")
        downstream[anchor] = {
            "status": statuses[anchor],
            "downstream_logical_ids": len(affected),
            "unattempted_due_integrity_block": len(mapped),
            "estimation_only": anchor in {"A", "T"} and statuses[anchor] == "SUPPORT_LIMITED",
        }
    return {
        "schema_version": "paper1-stage3-support-mapping-v1",
        "run_mode": mode,
        "anchors": {
            anchor: {**summary_rows[anchor], **downstream[anchor]}
            for anchor in ("A", "T", "H")
        },
        "k1_additional_generation_calls": 0,
        "k1_additional_judge_calls": 0,
    }
