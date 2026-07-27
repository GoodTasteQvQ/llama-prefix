"""Frozen logical plan, lifecycle, budget, and artifact execution controls."""

from __future__ import annotations

import json
import math
import os
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .core import (
    ACTIVE_PROFILE,
    DECODE_CONFIG,
    FORMAL_LOGICAL_GENERATION,
    AppendOnlyReceipt,
    IdentityError,
    LogicalIdentityRegistry,
    PipelineError,
    canonical_sha256,
    classify_support,
    file_sha256,
)
from .dose import validate_dose_binding
from .records import (
    AuthenticatedDoseContext,
    SUPPORT_RESPONSE_KEYS,
    _issue_authenticated_dose_context,
    validate_generation_record,
    validate_judge_record,
    validate_p1_record,
    validate_support_response_materialization,
)


EVENT_ORDER = (
    "IDENTITIES_AND_E0_VALID",
    "MEASUREMENT_SPECIFICATION_FROZEN",
    "P1_OUTCOME_VISIBLE",
    "MEASUREMENT_RESULT_DOSE_FROZEN",
    "JUDGE_DEVELOPMENT_MANUAL_COMPLETE",
    "JUDGE_FROZEN",
    "FORMAL_SUPPORT_GENERATION_STARTED",
    "SUPPORT_EXECUTION_MANIFEST_FROZEN",
    "BEHAVIOR_CONFIRMATION_FROZEN",
    "FORMAL_CONFIRMATION_GENERATION_STARTED",
)
LIFECYCLE_SCHEMA_VERSION = "paper1-stage3-lifecycle-artifact-v1"
LIFECYCLE_ARTIFACT_PATHS = {
    event: f"protocol/lifecycle/{index:02d}_{event.lower()}.json"
    for index, event in enumerate(EVENT_ORDER, 1)
}
LIFECYCLE_ARTIFACT_KINDS = {
    event: f"paper1-stage3-lifecycle-{event.lower().replace('_', '-')}"
    for event in EVENT_ORDER
}
SUPPORT_EXECUTION_SOURCE_PATH = "records/support_execution_sources.json"
SUPPORT_ATTEMPT_RECEIPT_PATH = "receipts/support_execution_attempts.jsonl"
LIFECYCLE_BOUND_PATHS = {
    "IDENTITIES_AND_E0_VALID": {
        "logical_registry": "logical_registry.json",
        "experiment_identity_manifest": "protocol/experiment_identity_manifest.json",
        "base_anchor_manifest": "protocol/base_anchor_manifest.json",
        "e0_receipt": "verification/e0_receipt.json",
    },
    "MEASUREMENT_SPECIFICATION_FROZEN": {
        "measurement_specification_freeze": "protocol/measurement_specification_freeze.json",
        "experiment_identity_manifest": "protocol/experiment_identity_manifest.json",
        "base_anchor_manifest": "protocol/base_anchor_manifest.json",
    },
    "P1_OUTCOME_VISIBLE": {
        "p1_terminal_records": "records/p1_measurement_records.json",
        "measurement_specification_freeze": "protocol/measurement_specification_freeze.json",
    },
    "MEASUREMENT_RESULT_DOSE_FROZEN": {
        "measurement_result_dose_manifest": "protocol/measurement_result_dose_manifest.json",
        "p1_terminal_records": "records/p1_measurement_records.json",
        "measurement_specification_freeze": "protocol/measurement_specification_freeze.json",
        "experiment_identity_manifest": "protocol/experiment_identity_manifest.json",
        "base_anchor_manifest": "protocol/base_anchor_manifest.json",
    },
    "JUDGE_DEVELOPMENT_MANUAL_COMPLETE": {
        "judge_development_ledger": "protocol/judge_development_ledger.json",
        "measurement_result_dose_manifest": "protocol/measurement_result_dose_manifest.json",
    },
    "JUDGE_FROZEN": {
        "judge_freeze": "protocol/judge_freeze.json",
        "judge_development_ledger": "protocol/judge_development_ledger.json",
        "measurement_result_dose_manifest": "protocol/measurement_result_dose_manifest.json",
    },
    "FORMAL_SUPPORT_GENERATION_STARTED": {
        "judge_freeze": "protocol/judge_freeze.json",
        "measurement_result_dose_manifest": "protocol/measurement_result_dose_manifest.json",
    },
    "SUPPORT_EXECUTION_MANIFEST_FROZEN": {
        "support_execution_manifest": "protocol/support_execution_manifest.json",
        "support_execution_sources": SUPPORT_EXECUTION_SOURCE_PATH,
        "judge_freeze": "protocol/judge_freeze.json",
        "measurement_result_dose_manifest": "protocol/measurement_result_dose_manifest.json",
    },
    "BEHAVIOR_CONFIRMATION_FROZEN": {
        "behavior_confirmation_freeze": "protocol/behavior_confirmation_freeze.json",
        "support_execution_manifest": "protocol/support_execution_manifest.json",
        "support_execution_sources": SUPPORT_EXECUTION_SOURCE_PATH,
        "judge_freeze": "protocol/judge_freeze.json",
        "measurement_result_dose_manifest": "protocol/measurement_result_dose_manifest.json",
        "measurement_specification_freeze": "protocol/measurement_specification_freeze.json",
        "experiment_identity_manifest": "protocol/experiment_identity_manifest.json",
    },
    "FORMAL_CONFIRMATION_GENERATION_STARTED": {
        "behavior_confirmation_freeze": "protocol/behavior_confirmation_freeze.json",
        "support_execution_manifest": "protocol/support_execution_manifest.json",
        "support_execution_sources": SUPPORT_EXECUTION_SOURCE_PATH,
    },
}
LIFECYCLE_CONTENT_KEYS = {
    "IDENTITIES_AND_E0_VALID": {"registry_sha256", "logical_identity_count", "e0_status"},
    "MEASUREMENT_SPECIFICATION_FROZEN": {"p1_forward_started"},
    "P1_OUTCOME_VISIBLE": {"p1_outcome_visible", "scheduled_p1_identities"},
    "MEASUREMENT_RESULT_DOSE_FROZEN": {"dose_status"},
    "JUDGE_DEVELOPMENT_MANUAL_COMPLETE": {
        "formal_response_identities", "generation_calls", "automated_judge_calls", "review_status",
    },
    "JUDGE_FROZEN": {"judge_model_family", "exact_json_parser", "single_retry"},
    "FORMAL_SUPPORT_GENERATION_STARTED": {"execution_phase", "authorization_status"},
    "SUPPORT_EXECUTION_MANIFEST_FROZEN": {
        "scheduled_support_identities", "terminal_dispositions_complete",
    },
    "BEHAVIOR_CONFIRMATION_FROZEN": {
        "confirmation_identity_count", "deterministic_support_mapping",
    },
    "FORMAL_CONFIRMATION_GENERATION_STARTED": {"execution_phase", "authorization_status"},
}
MEASUREMENT_SPECIFICATION_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "experiment_identity_self_sha256", "base_anchor_self_sha256",
    "prompt_frame_sha256", "rendering_rules_sha256", "span_rules_sha256",
    "complete_case_rules_sha256", "p1_estimands_sha256", "statistics_binding_sha256",
    "bootstrap_binding_sha256", "failure_rules_sha256", "producer_binding_sha256",
    "code_sha256", "config_sha256", "environment_sha256", "created_at_utc",
    "p1_forward_started", "registry_sha256", "logical_identity_count", "self_sha256",
}
LOGICAL_REGISTRY_KEYS = {
    "schema_version", "protocol_version", "synthetic", "formal_experiment",
    "identity_count", "records", "registry_sha256", "self_sha256",
}
EXPERIMENT_IDENTITY_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "terminal_status", "logical_registry_path",
    "logical_registry_self_sha256", "registry_sha256", "logical_identity_count",
    "prompt_frames", "prompt_frame_sha256", "model_identity_sha256",
    "vector_manifest_sha256", "generation_config_sha256", "code_sha256",
    "config_sha256", "environment_sha256", "created_at_utc", "self_sha256",
}
BASE_ANCHOR_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "terminal_status", "experiment_identity_self_sha256",
    "anchor_order", "rho_by_anchor", "anchor_binding_sha256", "code_sha256",
    "config_sha256", "environment_sha256", "created_at_utc", "self_sha256",
}
E0_RECEIPT_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "status", "registry_sha256", "logical_identity_count",
    "experiment_identity_self_sha256", "base_anchor_self_sha256", "checks",
    "checks_sha256", "created_at_utc", "self_sha256",
}
P1_TERMINAL_SET_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "measurement_specification_self_sha256",
    "experiment_identity_self_sha256", "scheduled_identity_count",
    "ordered_logical_ids", "ordered_logical_ids_sha256", "records",
    "terminal_status", "created_at_utc", "self_sha256",
}
MEASUREMENT_RESULT_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "registry_sha256", "logical_identity_count", "parents",
    "scheduled_p1_identity_count", "terminal_status", "dose_binding",
    "code_sha256", "config_sha256", "environment_sha256", "created_at_utc",
    "self_sha256",
}
JUDGE_DEVELOPMENT_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "measurement_result_dose_manifest_self_sha256",
    "development_mode", "formal_response_identities", "generation_calls",
    "automated_judge_calls", "review_status", "review_evidence_sha256",
    "created_at_utc", "self_sha256",
}
JUDGE_FREEZE_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "measurement_result_dose_manifest_self_sha256",
    "judge_development_ledger_self_sha256", "model_family",
    "judge_model_identity_sha256", "runner_source_sha256", "fixed_generation",
    "exact_json_parser", "single_retry", "rubric_sha256_by_domain",
    "created_at_utc", "self_sha256",
}
SUPPORT_ROW_KEYS = {
    "logical_id", "identity_sha256", "anchor", "scheduled_identity_match",
    "generation_completed", "judge_eligible", "judge_label_parsed",
    "identity_complete", "identity_collision", "dose_denominator_valid",
    "dose_geometry_finite", "post_dtype_alpha_finite",
    "generation_record_sha256", "judge_record_sha256", "label",
    "terminal_status", "retained",
}
SUPPORT_SUMMARY_KEYS = {
    "anchor", "scheduled_identities", "unique_scheduled_identities",
    "retained_identities", "identity_collisions", "unexpected_identities",
    "missing_scheduled_identities", "denominator_failures",
    "dose_geometry_failures", "post_dtype_alpha_failures", "support_status",
    "downstream_status", "execution_action", "affected",
}
SUPPORT_EXECUTION_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "registry_sha256", "logical_identity_count", "parents",
    "scheduled_identity_count", "source_bindings", "rows", "rows_sha256", "anchor_summaries",
    "actual_calls", "terminal_status", "created_at_utc", "self_sha256",
}
SUPPORT_EXECUTION_SOURCE_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "registry_sha256", "event7_lifecycle_entry_sha256",
    "event7_lifecycle_artifact_self_sha256", "support_receipt_path",
    "support_receipt_file_sha256", "support_receipt_entry_count",
    "support_receipt_tip_sha256", "support_receipt_execution_binding_sha256",
    "phase_registry_sha256", "generation_records", "generation_record_set_sha256", "judge_records",
    "judge_record_set_sha256", "dispositions", "disposition_set_sha256",
    "response_records", "response_record_set_sha256", "created_at_utc", "self_sha256",
}
SUPPORT_SOURCE_BINDING_KEYS = {
    "support_execution_sources_self_sha256", "event7_lifecycle_entry_sha256",
    "event7_lifecycle_artifact_self_sha256", "support_receipt_file_sha256",
    "support_receipt_entry_count", "support_receipt_tip_sha256",
    "support_receipt_execution_binding_sha256", "phase_registry_sha256",
    "generation_record_set_sha256", "judge_record_set_sha256",
    "disposition_set_sha256", "response_record_set_sha256",
}
CONFIRMATION_ROW_KEYS = {
    "logical_id", "identity_sha256", "block", "support_anchor_dependency",
    "support_status", "execution_disposition",
}
BEHAVIOR_CONFIRMATION_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "registry_sha256", "logical_identity_count", "parents",
    "confirmation_identity_count", "block_counts", "support_mapping",
    "confirmation_rows", "confirmation_frame_sha256", "created_at_utc",
    "self_sha256",
}
E0_REQUIRED_CHECKS = (
    "freeze_lifecycle", "identity_collision", "missing_identity", "invalid_dose",
    "nonfinite_values", "exact_judge_parser", "retry_terminal_failure",
    "retained_predicate", "support_limited", "non_estimable_identity",
    "non_estimable_analysis", "fixed720_allocator", "two_phase_correction",
    "retained_bootstrap", "budget_artifact_checks",
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


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PipelineError(f"{field} must be a lowercase SHA256")
    return value


def _require_nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PipelineError(f"{field} must be a nonnegative integer")
    return value


def _require_document_header(
    document: Mapping[str, Any],
    *,
    keys: set[str],
    schema_version: str,
    artifact_kind: str,
    synthetic: bool,
) -> None:
    if set(document) != keys:
        raise PipelineError(
            f"{artifact_kind} fields differ: "
            f"missing={sorted(keys-set(document))}, extra={sorted(set(document)-keys)}"
        )
    if (
        document["schema_version"] != schema_version
        or document["protocol_version"] != "v3.5-rc2"
        or document["artifact_kind"] != artifact_kind
    ):
        raise PipelineError(f"{artifact_kind} schema identity differs")
    if (
        document["synthetic"] is not synthetic
        or document["formal_experiment"] is not (not synthetic)
    ):
        raise PipelineError(f"{artifact_kind} mode differs from lifecycle")
    if not isinstance(document["created_at_utc"], str) or not document["created_at_utc"]:
        raise PipelineError(f"{artifact_kind} created_at_utc is invalid")


def _validate_logical_registry_document(
    document: Mapping[str, Any], *, synthetic: bool, full_identity_check: bool
) -> list[dict[str, Any]]:
    if set(document) != LOGICAL_REGISTRY_KEYS:
        raise PipelineError("logical registry fields differ")
    if (
        document["schema_version"] != "paper1-stage3-logical-registry-v1"
        or document["protocol_version"] != "v3.5-rc2"
        or document["synthetic"] is not synthetic
        or document["formal_experiment"] is not (not synthetic)
        or document["identity_count"] != FORMAL_LOGICAL_GENERATION
    ):
        raise PipelineError("logical registry identity/mode/count differs")
    records = document["records"]
    if not isinstance(records, list) or len(records) != FORMAL_LOGICAL_GENERATION:
        raise PipelineError("logical registry must contain exactly 5,580 records")
    if document["registry_sha256"] != canonical_sha256(records):
        raise PipelineError("logical registry content hash differs")
    if full_identity_check:
        rebuilt = LogicalIdentityRegistry(synthetic=synthetic)
        for item in records:
            if not isinstance(item, Mapping) or set(item) != {"logical_id", "identity"}:
                raise PipelineError("logical registry record fields differ")
            logical_id = rebuilt.register(item["identity"])
            if item["logical_id"] != logical_id:
                raise IdentityError("logical registry ID differs from its canonical identity")
        if rebuilt.manifest()["registry_sha256"] != document["registry_sha256"]:
            raise IdentityError("logical registry reconstruction differs")
    return [dict(item) for item in records]


def _validate_experiment_identity_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    registry_document: Mapping[str, Any],
) -> None:
    _require_document_header(
        document,
        keys=EXPERIMENT_IDENTITY_KEYS,
        schema_version="paper1-stage3-experiment-identity-manifest-v1",
        artifact_kind="experiment_identity_manifest",
        synthetic=synthetic,
    )
    if document["terminal_status"] not in {
        "READY", "BLOCKED_EXTERNAL_INPUT", "TERMINAL_BLOCKED_IDENTITY"
    }:
        raise PipelineError("experiment identity terminal status is invalid")
    if synthetic and document["terminal_status"] != "READY":
        raise PipelineError("synthetic identity fixture must be READY")
    if (
        document["logical_registry_path"] != "logical_registry.json"
        or document["logical_registry_self_sha256"] != registry_document["self_sha256"]
        or document["registry_sha256"] != registry_document["registry_sha256"]
        or document["logical_identity_count"] != FORMAL_LOGICAL_GENERATION
    ):
        raise IdentityError("experiment identity differs from materialized logical registry")
    frames = document["prompt_frames"]
    if not isinstance(frames, Mapping) or set(frames) != set(PROMPT_FRAME_SIZES):
        raise IdentityError("experiment prompt-frame registry differs")
    flattened: list[str] = []
    for name, expected_count in PROMPT_FRAME_SIZES.items():
        values = frames[name]
        if (
            not isinstance(values, list)
            or len(values) != expected_count
            or len(set(values)) != expected_count
            or any(not isinstance(value, str) or not value for value in values)
        ):
            raise IdentityError(f"experiment prompt frame {name} differs")
        flattened.extend(values)
    if len(set(flattened)) != len(flattened):
        raise IdentityError("experiment prompt frames overlap")
    if document["prompt_frame_sha256"] != canonical_sha256(frames):
        raise IdentityError("experiment prompt-frame hash differs")
    if document["generation_config_sha256"] != canonical_sha256(DECODE_CONFIG):
        raise IdentityError("experiment generation config differs from frozen decoder")
    for field in (
        "model_identity_sha256", "vector_manifest_sha256", "code_sha256",
        "config_sha256", "environment_sha256",
    ):
        _require_sha256(document[field], field)


def _validate_base_anchor_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    experiment_identity_self_sha256: str,
) -> None:
    _require_document_header(
        document,
        keys=BASE_ANCHOR_KEYS,
        schema_version="paper1-stage3-base-anchor-manifest-v1",
        artifact_kind="base_anchor_manifest",
        synthetic=synthetic,
    )
    if document["terminal_status"] not in {"READY", "BLOCKED_EXTERNAL_INPUT"}:
        raise PipelineError("base-anchor terminal status is invalid")
    if synthetic and document["terminal_status"] != "READY":
        raise PipelineError("synthetic base-anchor fixture must be READY")
    if document["experiment_identity_self_sha256"] != experiment_identity_self_sha256:
        raise PipelineError("base-anchor identity parent differs")
    if document["anchor_order"] != ["A", "T", "H"]:
        raise PipelineError("base-anchor order differs")
    rho_map = document["rho_by_anchor"]
    if not isinstance(rho_map, Mapping) or set(rho_map) != {"A", "T", "H"}:
        raise PipelineError("base-anchor rho map differs")
    rho_values: list[float] = []
    for anchor in ("A", "T", "H"):
        value = rho_map[anchor]
        if not isinstance(value, Mapping) or set(value) != {"value", "binary64_hex"}:
            raise PipelineError(f"base-anchor rho {anchor} is not exact binary64")
        number = value["value"]
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(float(number))
            or value["binary64_hex"] != float(number).hex()
        ):
            raise PipelineError(f"base-anchor rho {anchor} is invalid")
        rho_values.append(float(number))
    if not 0.0 < rho_values[0] < rho_values[1] < rho_values[2]:
        raise PipelineError("base-anchor rho values are not strictly ordered")
    if document["anchor_binding_sha256"] != canonical_sha256(rho_map):
        raise PipelineError("base-anchor binding hash differs")
    for field in ("code_sha256", "config_sha256", "environment_sha256"):
        _require_sha256(document[field], field)


def validate_judge_freeze_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    measurement_parent_sha256: str | None = None,
    development_parent_sha256: str | None = None,
) -> dict[str, str]:
    _require_document_header(
        document,
        keys=JUDGE_FREEZE_KEYS,
        schema_version="paper1-stage3-judge-freeze-v1",
        artifact_kind="judge_freeze",
        synthetic=synthetic,
    )
    if (
        measurement_parent_sha256 is not None
        and document["measurement_result_dose_manifest_self_sha256"]
        != measurement_parent_sha256
    ):
        raise PipelineError("judge freeze measurement parent differs")
    if (
        development_parent_sha256 is not None
        and document["judge_development_ledger_self_sha256"]
        != development_parent_sha256
    ):
        raise PipelineError("judge freeze development parent differs")
    if (
        document["model_family"] != "Qwen/Qwen3-8B"
        or document["fixed_generation"] != {
            "do_sample": False,
            "num_beams": 1,
            "max_new_tokens": 1296,
            "torch_dtype": "float32",
            "enable_thinking": True,
        }
        or document["exact_json_parser"] is not True
        or document["single_retry"] is not True
        or document["runner_source_sha256"]
        != "73c3d4fb9bfbe818370c172e9b19d075ab18b420ca4e5336d728dcf2474d2651"
    ):
        raise PipelineError("judge freeze model/parser/retry contract differs")
    _require_sha256(document["judge_model_identity_sha256"], "judge_model_identity_sha256")
    rubrics = document["rubric_sha256_by_domain"]
    if not isinstance(rubrics, Mapping) or set(rubrics) != {"harmful", "benign"}:
        raise PipelineError("judge freeze domain rubric map differs")
    for domain, value in rubrics.items():
        _require_sha256(value, f"rubric_sha256_by_domain.{domain}")
    return dict(rubrics)


def _validate_e0_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    registry_sha256: str,
    experiment_identity_self_sha256: str,
    base_anchor_self_sha256: str,
) -> None:
    _require_document_header(
        document,
        keys=E0_RECEIPT_KEYS,
        schema_version="paper1-stage3-e0-receipt-v1",
        artifact_kind="e0_receipt",
        synthetic=synthetic,
    )
    if (
        document["status"] != "PASS"
        or document["registry_sha256"] != registry_sha256
        or document["logical_identity_count"] != FORMAL_LOGICAL_GENERATION
        or document["experiment_identity_self_sha256"] != experiment_identity_self_sha256
        or document["base_anchor_self_sha256"] != base_anchor_self_sha256
        or document["checks"] != list(E0_REQUIRED_CHECKS)
        or document["checks_sha256"] != canonical_sha256(list(E0_REQUIRED_CHECKS))
    ):
        raise PipelineError("E0 receipt does not bind the exact registry/parents/check set")


def _validate_measurement_specification_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    experiment_identity: Mapping[str, Any],
    base_anchor: Mapping[str, Any],
) -> None:
    _require_document_header(
        document,
        keys=MEASUREMENT_SPECIFICATION_KEYS,
        schema_version="paper1-stage3-measurement-specification-freeze-v1",
        artifact_kind="measurement_specification_freeze",
        synthetic=synthetic,
    )
    if (
        document["p1_forward_started"] is not False
        or document["experiment_identity_self_sha256"] != experiment_identity["self_sha256"]
        or document["base_anchor_self_sha256"] != base_anchor["self_sha256"]
        or document["registry_sha256"] != experiment_identity["registry_sha256"]
        or document["logical_identity_count"] != FORMAL_LOGICAL_GENERATION
        or document["prompt_frame_sha256"] != experiment_identity["prompt_frame_sha256"]
    ):
        raise PipelineError("measurement specification identity/parents differ")
    for field in MEASUREMENT_SPECIFICATION_KEYS:
        if field.endswith("_sha256") and field != "self_sha256":
            _require_sha256(document[field], field)


def _validate_p1_terminal_set_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    measurement_specification_self_sha256: str,
    experiment_identity: Mapping[str, Any],
) -> None:
    _require_document_header(
        document,
        keys=P1_TERMINAL_SET_KEYS,
        schema_version="paper1-stage3-p1-terminal-record-set-v1",
        artifact_kind="p1_terminal_record_set",
        synthetic=synthetic,
    )
    ordered_ids = document["ordered_logical_ids"]
    records = document["records"]
    if (
        document["measurement_specification_self_sha256"]
        != measurement_specification_self_sha256
        or document["experiment_identity_self_sha256"] != experiment_identity["self_sha256"]
        or document["scheduled_identity_count"] != 200
        or not isinstance(ordered_ids, list)
        or len(ordered_ids) != 200
        or len(set(ordered_ids)) != 200
        or document["ordered_logical_ids_sha256"] != canonical_sha256(ordered_ids)
        or not isinstance(records, list)
        or len(records) != 200
        or document["terminal_status"] != "COMPLETE"
    ):
        raise PipelineError("P1 terminal record set identity/count/hash differs")
    validated_ids: list[str] = []
    prompt_ids: list[str] = []
    for raw_record in records:
        if not isinstance(raw_record, Mapping):
            raise PipelineError("P1 terminal set contains a non-object record")
        validated = validate_p1_record(raw_record)
        if validated["synthetic"] is not synthetic:
            raise PipelineError("P1 record mode differs from its terminal set")
        validated_ids.append(validated["logical_id"])
        prompt_ids.append(validated["prompt_id"])
    expected_prompts = (
        experiment_identity["prompt_frames"]["p1_harmful"]
        + experiment_identity["prompt_frames"]["p1_benign"]
    )
    if validated_ids != ordered_ids or prompt_ids != expected_prompts:
        raise IdentityError("P1 terminal rows differ from the frozen 200-prompt frame")


def _validate_measurement_result_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    registry_sha256: str,
    experiment_identity_self_sha256: str,
    base_anchor_self_sha256: str,
    measurement_specification_self_sha256: str,
    p1_terminal_records_self_sha256: str,
) -> None:
    _require_document_header(
        document,
        keys=MEASUREMENT_RESULT_KEYS,
        schema_version="paper1-stage3-measurement-result-dose-manifest-v1",
        artifact_kind="measurement_result_dose_manifest",
        synthetic=synthetic,
    )
    expected_parents = {
        "measurement_specification_freeze": measurement_specification_self_sha256,
        "experiment_identity_manifest": experiment_identity_self_sha256,
        "base_anchor_manifest": base_anchor_self_sha256,
        "p1_terminal_records": p1_terminal_records_self_sha256,
    }
    if (
        document["registry_sha256"] != registry_sha256
        or document["logical_identity_count"] != FORMAL_LOGICAL_GENERATION
        or document["parents"] != expected_parents
        or document["scheduled_p1_identity_count"] != 200
        or document["terminal_status"] not in {"ESTIMABLE", "P1_DOSE_NON_ESTIMABLE"}
    ):
        raise PipelineError("measurement result/dose identity/parents/status differ")
    if document["terminal_status"] == "ESTIMABLE":
        dose_binding = document["dose_binding"]
        if not isinstance(dose_binding, Mapping):
            raise PipelineError("estimable measurement result lacks its dose binding")
        validate_dose_binding(dose_binding)
        if (
            dose_binding["synthetic"] is not synthetic
            or dose_binding["parent_self_sha256"]
            != {
                "measurement_specification_freeze": measurement_specification_self_sha256,
                "experiment_identity_manifest": experiment_identity_self_sha256,
                "base_anchor_manifest": base_anchor_self_sha256,
            }
        ):
            raise PipelineError("dose binding mode/parents differ from measurement result")
    elif document["dose_binding"] is not None:
        raise PipelineError("non-estimable P1 dose manifest cannot contain a substitute dose")
    for field in ("code_sha256", "config_sha256", "environment_sha256"):
        _require_sha256(document[field], field)


def _validate_judge_development_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    measurement_result_self_sha256: str,
) -> None:
    _require_document_header(
        document,
        keys=JUDGE_DEVELOPMENT_KEYS,
        schema_version="paper1-stage3-judge-development-ledger-v1",
        artifact_kind="judge_development_ledger",
        synthetic=synthetic,
    )
    if (
        document["measurement_result_dose_manifest_self_sha256"]
        != measurement_result_self_sha256
        or document["development_mode"] != "manual_document_only_rubric_review"
        or document["formal_response_identities"] != 0
        or document["generation_calls"] != 0
        or document["automated_judge_calls"] != 0
        or document["review_status"] != "COMPLETE"
    ):
        raise PipelineError("judge development ledger violates manual-only zero-call contract")
    _require_sha256(document["review_evidence_sha256"], "review_evidence_sha256")


def _registry_records_by_phase(
    registry_document: Mapping[str, Any], phase: str
) -> list[Mapping[str, Any]]:
    records = registry_document["records"]
    if phase == "support":
        return [record for record in records if record["identity"]["block"] == "support"]
    if phase == "confirmation":
        return [record for record in records if record["identity"]["block"] != "support"]
    raise PipelineError(f"unknown execution phase: {phase}")


def _support_summary_from_rows(anchor: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary_input = {
        "anchor": anchor,
        "scheduled_identities": len(rows),
        "unique_scheduled_identities": len({row["logical_id"] for row in rows}),
        "retained_identities": sum(row["retained"] is True for row in rows),
        "identity_collisions": sum(row["identity_collision"] is True for row in rows),
        "unexpected_identities": sum(row["scheduled_identity_match"] is not True for row in rows),
        "missing_scheduled_identities": sum(row["scheduled_identity_match"] is not True for row in rows),
        "denominator_failures": sum(row["dose_denominator_valid"] is not True for row in rows),
        "dose_geometry_failures": sum(row["dose_geometry_finite"] is not True for row in rows),
        "post_dtype_alpha_failures": sum(
            row["post_dtype_alpha_finite"] is not True for row in rows
        ),
    }
    return {**summary_input, **classify_support(summary_input)}


def _registry_from_document(document: Mapping[str, Any]) -> LogicalIdentityRegistry:
    registry = LogicalIdentityRegistry(synthetic=document["synthetic"])
    for item in document["records"]:
        if registry.register(item["identity"]) != item["logical_id"]:
            raise IdentityError("logical registry document contains a forged logical ID")
    if registry.manifest()["registry_sha256"] != document["registry_sha256"]:
        raise IdentityError("logical registry reconstruction hash differs")
    return registry


def _support_receipt_at(root: Path, *, synthetic: bool) -> AppendOnlyReceipt:
    candidate = root.resolve()
    for part in PurePosixPath(SUPPORT_ATTEMPT_RECEIPT_PATH).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise PipelineError("support attempt receipt path contains a symlink")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise PipelineError("support attempt receipt escapes the lifecycle artifact root") from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise PipelineError("support attempt receipt is not a materialized regular file")
    return AppendOnlyReceipt(resolved, synthetic=synthetic)


def _validate_support_execution_sources(
    document: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    lifecycle_receipt: AppendOnlyReceipt,
    lifecycle_artifact_root: Path,
    measurement_result_dose_manifest: Mapping[str, Any],
    dose_context: AuthenticatedDoseContext,
) -> dict[str, Any]:
    _require_document_header(
        document,
        keys=SUPPORT_EXECUTION_SOURCE_KEYS,
        schema_version="paper1-stage3-support-execution-sources-v1",
        artifact_kind="support_execution_sources",
        synthetic=registry.synthetic,
    )
    registry_manifest = registry.manifest()
    if document["registry_sha256"] != registry_manifest["registry_sha256"]:
        raise IdentityError("support execution sources registry hash differs")
    authorizations = [
        entry for entry in lifecycle_receipt._load()
        if entry["event"] == "FORMAL_SUPPORT_GENERATION_STARTED"
    ]
    if len(authorizations) != 1:
        raise PipelineError("support execution sources lack their unique event-7 authorization")
    authorization = authorizations[0]
    context_authorizations = [
        entry for entry in lifecycle_receipt._load()
        if entry["entry_sha256"] == dose_context.authorized_tip_sha256
        and entry["event"] == dose_context.authorized_event
    ]
    if len(context_authorizations) != 1:
        raise PipelineError("dose context authorization is outside the lifecycle receipt")
    if (
        document["event7_lifecycle_entry_sha256"] != authorization["entry_sha256"]
        or document["event7_lifecycle_artifact_self_sha256"]
        != authorization["payload"]["artifact_self_sha256"]
        or document["support_receipt_path"] != SUPPORT_ATTEMPT_RECEIPT_PATH
    ):
        raise PipelineError("support execution sources event-7 binding differs")
    receipt = _support_receipt_at(lifecycle_artifact_root, synthetic=registry.synthetic)
    binding = receipt.require_execution_registry(
        registry_manifest["registry_sha256"],
        expected_lifecycle_event="FORMAL_SUPPORT_GENERATION_STARTED",
        expected_lifecycle_tip_sha256=authorization["entry_sha256"],
        expected_parent_self_sha256=authorization["payload"]["artifact_self_sha256"],
    )
    receipt_summary = receipt.verify()
    if (
        document["support_receipt_file_sha256"] != file_sha256(receipt.path)
        or document["support_receipt_entry_count"] != receipt_summary["entry_count"]
        or document["support_receipt_tip_sha256"] != receipt_summary["tip_sha256"]
        or document["support_receipt_execution_binding_sha256"]
        != binding["execution_binding_sha256"]
    ):
        raise PipelineError("support execution sources receipt materialization differs")
    set_fields = (
        ("generation_records", "generation_record_set_sha256"),
        ("judge_records", "judge_record_set_sha256"),
        ("dispositions", "disposition_set_sha256"),
        ("response_records", "response_record_set_sha256"),
    )
    for records_field, hash_field in set_fields:
        records = document[records_field]
        if not isinstance(records, list) or document[hash_field] != canonical_sha256(records):
            raise PipelineError(f"support execution sources {records_field} hash differs")
    reconciliation = reconcile_phase_execution_attempts(
        registry,
        receipt,
        document["generation_records"],
        document["judge_records"],
        document["dispositions"],
        phase="support",
        lifecycle_receipt=lifecycle_receipt,
        lifecycle_artifact_root=lifecycle_artifact_root,
        _skip_lifecycle_verification=True,
    )
    if document["phase_registry_sha256"] != reconciliation["phase_logical_id_sha256"]:
        raise IdentityError("support source phase-registry hash differs")
    generation_by_id = {
        record["logical_id"]: record for record in document["generation_records"]
    }
    judge_by_id = {record["logical_id"]: record for record in document["judge_records"]}
    disposition_by_id = {
        record["logical_id"]: record for record in document["dispositions"]
    }
    expected_registry_rows = [
        item for item in registry.records() if item["identity"]["block"] == "support"
    ]
    response_records = document["response_records"]
    if len(response_records) != 900:
        raise PipelineError("support response source set must contain all 900 terminal rows")
    rows: list[dict[str, Any]] = []
    for raw_response, registry_row in zip(response_records, expected_registry_rows, strict=True):
        if not isinstance(raw_response, Mapping) or set(raw_response) != SUPPORT_RESPONSE_KEYS:
            raise PipelineError("support response source fields differ")
        logical_id = registry_row["logical_id"]
        if raw_response["logical_id"] != logical_id:
            raise IdentityError("support response sources differ from registry order")
        disposition = disposition_by_id[logical_id]
        validated = validate_support_response_materialization(
            raw_response,
            registry=registry,
            generation_record=generation_by_id.get(logical_id),
            judge_record=judge_by_id.get(logical_id),
            measurement_result_dose_manifest=measurement_result_dose_manifest,
            dose_context=dose_context,
            unattempted_parent_status=(
                disposition["parent_status"]
                if disposition["disposition"] == "UNATTEMPTED_DUE_INTEGRITY_BLOCK"
                else None
            ),
        )
        rows.append({key: validated[key] for key in SUPPORT_ROW_KEYS})
    call_keys = (
        "generation_first_pass_calls", "generation_technical_retries", "generation_calls",
        "judge_first_pass_calls", "judge_parse_retries", "judge_calls",
    )
    return {
        "rows": rows,
        "actual_calls": {key: reconciliation[key] for key in call_keys},
        "reconciliation": reconciliation,
        "receipt_binding": binding,
    }


def materialize_support_execution_sources(
    *,
    registry: LogicalIdentityRegistry,
    lifecycle_receipt: AppendOnlyReceipt,
    lifecycle_artifact_root: Path,
    support_receipt: AppendOnlyReceipt,
    generation_records: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    measurement_result_dose_manifest: Mapping[str, Any],
    created_at_utc: str,
    dose_context: AuthenticatedDoseContext | None = None,
) -> dict[str, Any]:
    """Materialize the only accepted source-set document for event 8."""
    expected_receipt_path = (lifecycle_artifact_root / Path(SUPPORT_ATTEMPT_RECEIPT_PATH)).resolve()
    if support_receipt.path.resolve() != expected_receipt_path:
        raise PipelineError("support attempt receipt does not use its canonical artifact path")
    authorizations = [
        entry for entry in lifecycle_receipt._load()
        if entry["event"] == "FORMAL_SUPPORT_GENERATION_STARTED"
    ]
    if len(authorizations) != 1:
        raise PipelineError("support source materialization requires unique event-7 authorization")
    authorization = authorizations[0]
    registry_manifest = registry.manifest()
    binding = support_receipt.require_execution_registry(
        registry_manifest["registry_sha256"],
        expected_lifecycle_event="FORMAL_SUPPORT_GENERATION_STARTED",
        expected_lifecycle_tip_sha256=authorization["entry_sha256"],
        expected_parent_self_sha256=authorization["payload"]["artifact_self_sha256"],
    )
    receipt_summary = support_receipt.verify()
    phase_ids = [
        record["logical_id"]
        for record in registry.records()
        if record["identity"]["block"] == "support"
    ]
    materialized_sets = {
        "generation_records": [dict(record) for record in generation_records],
        "judge_records": [dict(record) for record in judge_records],
        "dispositions": [dict(record) for record in dispositions],
        "response_records": [dict(record) for record in response_records],
    }
    document = {
        "schema_version": "paper1-stage3-support-execution-sources-v1",
        "protocol_version": "v3.5-rc2",
        "artifact_kind": "support_execution_sources",
        "synthetic": registry.synthetic,
        "formal_experiment": not registry.synthetic,
        "registry_sha256": registry_manifest["registry_sha256"],
        "event7_lifecycle_entry_sha256": authorization["entry_sha256"],
        "event7_lifecycle_artifact_self_sha256": authorization["payload"][
            "artifact_self_sha256"
        ],
        "support_receipt_path": SUPPORT_ATTEMPT_RECEIPT_PATH,
        "support_receipt_file_sha256": file_sha256(support_receipt.path),
        "support_receipt_entry_count": receipt_summary["entry_count"],
        "support_receipt_tip_sha256": receipt_summary["tip_sha256"],
        "support_receipt_execution_binding_sha256": binding["execution_binding_sha256"],
        "phase_registry_sha256": canonical_sha256(phase_ids),
        **materialized_sets,
        "generation_record_set_sha256": canonical_sha256(materialized_sets["generation_records"]),
        "judge_record_set_sha256": canonical_sha256(materialized_sets["judge_records"]),
        "disposition_set_sha256": canonical_sha256(materialized_sets["dispositions"]),
        "response_record_set_sha256": canonical_sha256(materialized_sets["response_records"]),
        "created_at_utc": created_at_utc,
    }
    document["self_sha256"] = canonical_sha256(document)
    if dose_context is None:
        dose_context = FreezeLifecycle(
            lifecycle_receipt, lifecycle_artifact_root
        ).authenticated_dose_context(
            expected_event="FORMAL_SUPPORT_GENERATION_STARTED"
        )
    _validate_support_execution_sources(
        document,
        registry=registry,
        lifecycle_receipt=lifecycle_receipt,
        lifecycle_artifact_root=lifecycle_artifact_root,
        measurement_result_dose_manifest=measurement_result_dose_manifest,
        dose_context=dose_context,
    )
    return document


def materialize_support_execution_document(
    *,
    source_document: Mapping[str, Any],
    registry_document: Mapping[str, Any],
    lifecycle_receipt: AppendOnlyReceipt,
    lifecycle_artifact_root: Path,
    judge_freeze_self_sha256: str,
    measurement_result_dose_manifest: Mapping[str, Any],
    created_at_utc: str,
    dose_context: AuthenticatedDoseContext | None = None,
) -> dict[str, Any]:
    """Uniquely derive the event-8 manifest from authenticated event-7 sources."""
    registry = _registry_from_document(registry_document)
    if dose_context is None:
        dose_context = FreezeLifecycle(
            lifecycle_receipt, lifecycle_artifact_root
        ).authenticated_dose_context()
    materialized = _validate_support_execution_sources(
        source_document,
        registry=registry,
        lifecycle_receipt=lifecycle_receipt,
        lifecycle_artifact_root=lifecycle_artifact_root,
        measurement_result_dose_manifest=measurement_result_dose_manifest,
        dose_context=dose_context,
    )
    rows = materialized["rows"]
    summaries = [
        _support_summary_from_rows(anchor, [row for row in rows if row["anchor"] == anchor])
        for anchor in ("A", "T", "H")
    ]
    source_bindings = {
        "support_execution_sources_self_sha256": source_document["self_sha256"],
        "event7_lifecycle_entry_sha256": source_document["event7_lifecycle_entry_sha256"],
        "event7_lifecycle_artifact_self_sha256": source_document[
            "event7_lifecycle_artifact_self_sha256"
        ],
        "support_receipt_file_sha256": source_document["support_receipt_file_sha256"],
        "support_receipt_entry_count": source_document["support_receipt_entry_count"],
        "support_receipt_tip_sha256": source_document["support_receipt_tip_sha256"],
        "support_receipt_execution_binding_sha256": source_document[
            "support_receipt_execution_binding_sha256"
        ],
        "phase_registry_sha256": source_document["phase_registry_sha256"],
        "generation_record_set_sha256": source_document["generation_record_set_sha256"],
        "judge_record_set_sha256": source_document["judge_record_set_sha256"],
        "disposition_set_sha256": source_document["disposition_set_sha256"],
        "response_record_set_sha256": source_document["response_record_set_sha256"],
    }
    if set(source_bindings) != SUPPORT_SOURCE_BINDING_KEYS:
        raise PipelineError("support execution source binding fields differ")
    document = {
        "schema_version": "paper1-stage3-support-execution-manifest-v1",
        "protocol_version": "v3.5-rc2",
        "artifact_kind": "support_execution_manifest",
        "synthetic": registry.synthetic,
        "formal_experiment": not registry.synthetic,
        "registry_sha256": registry_document["registry_sha256"],
        "logical_identity_count": FORMAL_LOGICAL_GENERATION,
        "parents": {
            "judge_freeze": judge_freeze_self_sha256,
            "measurement_result_dose_manifest": measurement_result_dose_manifest["self_sha256"],
        },
        "scheduled_identity_count": 900,
        "source_bindings": source_bindings,
        "rows": rows,
        "rows_sha256": canonical_sha256(rows),
        "anchor_summaries": summaries,
        "actual_calls": materialized["actual_calls"],
        "terminal_status": "COMPLETE",
        "created_at_utc": created_at_utc,
    }
    document["self_sha256"] = canonical_sha256(document)
    return document


def validate_support_execution_document(
    document: Mapping[str, Any],
    *,
    source_document: Mapping[str, Any],
    registry_document: Mapping[str, Any],
    lifecycle_receipt: AppendOnlyReceipt,
    lifecycle_artifact_root: Path,
    judge_freeze_self_sha256: str,
    measurement_result_dose_manifest: Mapping[str, Any],
    dose_context: AuthenticatedDoseContext | None = None,
) -> list[dict[str, Any]]:
    _require_document_header(
        document,
        keys=SUPPORT_EXECUTION_KEYS,
        schema_version="paper1-stage3-support-execution-manifest-v1",
        artifact_kind="support_execution_manifest",
        synthetic=registry_document["synthetic"],
    )
    expected = materialize_support_execution_document(
        source_document=source_document,
        registry_document=registry_document,
        lifecycle_receipt=lifecycle_receipt,
        lifecycle_artifact_root=lifecycle_artifact_root,
        judge_freeze_self_sha256=judge_freeze_self_sha256,
        measurement_result_dose_manifest=measurement_result_dose_manifest,
        created_at_utc=document["created_at_utc"],
        dose_context=dose_context,
    )
    if document != expected:
        raise PipelineError("support execution manifest is not uniquely derived from event-7 sources")
    return list(document["anchor_summaries"])


def _support_dependency(block: str) -> str | None:
    if block in {"P2_A_all", "P2_A_content"}:
        return "A"
    if block in {"P2_T_all", "P2_T_content", "benign_T"}:
        return "T"
    return None


def _validate_behavior_confirmation_document(
    document: Mapping[str, Any],
    *,
    synthetic: bool,
    registry_document: Mapping[str, Any],
    experiment_identity_self_sha256: str,
    measurement_specification_self_sha256: str,
    measurement_result_self_sha256: str,
    judge_freeze_self_sha256: str,
    support_execution_document: Mapping[str, Any],
) -> None:
    _require_document_header(
        document,
        keys=BEHAVIOR_CONFIRMATION_KEYS,
        schema_version="paper1-stage3-behavior-confirmation-freeze-v1",
        artifact_kind="behavior_confirmation_freeze",
        synthetic=synthetic,
    )
    expected_parents = {
        "experiment_identity_manifest": experiment_identity_self_sha256,
        "measurement_specification_freeze": measurement_specification_self_sha256,
        "measurement_result_dose_manifest": measurement_result_self_sha256,
        "judge_freeze": judge_freeze_self_sha256,
        "support_execution_manifest": support_execution_document["self_sha256"],
    }
    if (
        document["registry_sha256"] != registry_document["registry_sha256"]
        or document["logical_identity_count"] != FORMAL_LOGICAL_GENERATION
        or document["parents"] != expected_parents
        or document["confirmation_identity_count"] != 4_680
    ):
        raise PipelineError("behavior confirmation identity/parents/count differ")
    expected_block_counts = {
        block: count for block, count in BLOCK_BUDGET.items() if block != "support"
    }
    if document["block_counts"] != expected_block_counts:
        raise PipelineError("behavior confirmation block counts differ")
    summaries = support_execution_document["anchor_summaries"]
    summary_by_anchor = {summary["anchor"]: summary for summary in summaries}
    expected_mapping = {
        anchor: {
            field: summary_by_anchor[anchor][field]
            for field in (
                "support_status", "downstream_status", "execution_action", "affected"
            )
        }
        for anchor in ("A", "T", "H")
    }
    if document["support_mapping"] != expected_mapping:
        raise PipelineError("behavior confirmation support mapping is not derived")
    expected_registry_rows = _registry_records_by_phase(registry_document, "confirmation")
    rows = document["confirmation_rows"]
    if (
        not isinstance(rows, list)
        or len(rows) != 4_680
        or document["confirmation_frame_sha256"] != canonical_sha256(rows)
    ):
        raise PipelineError("behavior confirmation must bind a hashed 4,680-row frame")
    for row, registry_row in zip(rows, expected_registry_rows, strict=True):
        if not isinstance(row, Mapping) or set(row) != CONFIRMATION_ROW_KEYS:
            raise PipelineError("behavior confirmation row fields differ")
        identity = registry_row["identity"]
        dependency = _support_dependency(identity["block"])
        support_status = (
            summary_by_anchor[dependency]["support_status"]
            if dependency is not None
            else "NOT_APPLICABLE"
        )
        disposition = (
            "UNATTEMPTED_DUE_INTEGRITY_BLOCK"
            if dependency is not None and support_status == "NON_ESTIMABLE_IDENTITY"
            else "AUTHORIZED"
        )
        expected = {
            "logical_id": registry_row["logical_id"],
            "identity_sha256": canonical_sha256(identity),
            "block": identity["block"],
            "support_anchor_dependency": dependency,
            "support_status": support_status,
            "execution_disposition": disposition,
        }
        if row != expected:
            raise IdentityError("behavior confirmation row differs from registry/support mapping")


def validate_event_sequence(events: Sequence[str]) -> None:
    if tuple(events) != EVENT_ORDER[: len(events)]:
        raise PipelineError("lifecycle events must be an exact prefix of the ten-event order")


class FreezeLifecycle:
    """Append lifecycle events only in the frozen order."""

    def __init__(self, receipt: AppendOnlyReceipt, artifact_root: Path | None = None) -> None:
        self.receipt = receipt
        self.artifact_root = (artifact_root or receipt.path.parent).resolve()

    def events(self) -> list[str]:
        return [record["event"] for record in self.receipt._load()]

    def _read_artifact(self, relative_path: str) -> tuple[Path, dict[str, Any]]:
        pure = PurePosixPath(relative_path)
        if pure.is_absolute() or ".." in pure.parts or pure.suffix != ".json":
            raise PipelineError("lifecycle artifact reference must be a relative JSON path")
        candidate = self.artifact_root
        for part in pure.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise PipelineError("lifecycle artifact reference contains a symlink")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.artifact_root)
        except ValueError as exc:
            raise PipelineError("lifecycle artifact reference escapes its root") from exc
        if not resolved.is_file() or resolved.is_symlink():
            raise PipelineError("lifecycle artifact reference is not a materialized regular file")

        def exact_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            parsed: dict[str, Any] = {}
            for key, value in pairs:
                if key in parsed:
                    raise PipelineError(f"lifecycle artifact contains duplicate key: {key}")
                parsed[key] = value
            return parsed

        try:
            document = json.loads(
                resolved.read_text(encoding="utf-8"),
                object_pairs_hook=exact_object,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    PipelineError(f"lifecycle artifact contains non-standard constant: {value}")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, PipelineError) as exc:
            raise PipelineError("lifecycle artifact is not valid UTF-8 JSON") from exc
        if not isinstance(document, dict):
            raise PipelineError("lifecycle artifact must be a JSON object")
        expected_self_hash = canonical_sha256(
            {key: value for key, value in document.items() if key != "self_sha256"}
        )
        if document.get("self_sha256") != expected_self_hash:
            raise PipelineError("lifecycle artifact self hash mismatch")
        return resolved, document

    def read_validated_document(self, relative_path: str) -> dict[str, Any]:
        """Read one canonical self-hashed lifecycle backing document."""
        return self._read_artifact(relative_path)[1]

    def _canonical_document(self, relative_path: str) -> dict[str, Any]:
        return self._read_artifact(relative_path)[1]

    def _issue_dose_context_from_validated_documents(
        self,
        *,
        registry_document: Mapping[str, Any],
        measurement_result: Mapping[str, Any],
        expected_event: str | None = None,
    ) -> AuthenticatedDoseContext:
        records = self.receipt._load()
        if not records:
            raise PipelineError("dose context requires a materialized lifecycle authorization")
        tip = records[-1]
        event = tip["event"]
        if expected_event is not None and event != expected_event:
            raise PipelineError(f"dose context requires exact lifecycle tip {expected_event}")
        if event not in EVENT_ORDER[6:]:
            raise PipelineError("dose context cannot precede formal support authorization")
        parents = measurement_result.get("parents")
        if not isinstance(parents, Mapping):
            raise PipelineError("dose context source lacks canonical measurement parents")
        return _issue_authenticated_dose_context(
            synthetic=self.receipt.synthetic,
            registry_sha256=registry_document["registry_sha256"],
            measurement_result_self_sha256=measurement_result["self_sha256"],
            parent_self_sha256=parents,
            authorized_event=event,
            authorized_tip_sha256=tip["entry_sha256"],
        )

    def authenticated_dose_context(
        self, *, expected_event: str | None = None
    ) -> AuthenticatedDoseContext:
        """Verify the lifecycle prefix and issue its dose materialization context."""
        self.verify()
        return self._issue_dose_context_from_validated_documents(
            registry_document=self._canonical_document("logical_registry.json"),
            measurement_result=self._canonical_document(
                "protocol/measurement_result_dose_manifest.json"
            ),
            expected_event=expected_event,
        )

    def _validate_bound_artifacts(
        self,
        event: str,
        documents: Mapping[str, Mapping[str, Any]],
        content: Mapping[str, Any],
    ) -> None:
        synthetic = self.receipt.synthetic
        registry = self._canonical_document("logical_registry.json")
        _validate_logical_registry_document(
            registry,
            synthetic=synthetic,
            full_identity_check=event == "IDENTITIES_AND_E0_VALID",
        )
        experiment_identity = self._canonical_document(
            "protocol/experiment_identity_manifest.json"
        )
        _validate_experiment_identity_document(
            experiment_identity,
            synthetic=synthetic,
            registry_document=registry,
        )
        base_anchor = self._canonical_document("protocol/base_anchor_manifest.json")
        _validate_base_anchor_document(
            base_anchor,
            synthetic=synthetic,
            experiment_identity_self_sha256=experiment_identity["self_sha256"],
        )

        if event == "IDENTITIES_AND_E0_VALID":
            if (
                experiment_identity["terminal_status"] != "READY"
                or base_anchor["terminal_status"] != "READY"
            ):
                raise PipelineError("identity/E0 event cannot authorize blocked identity parents")
            if documents["logical_registry"] != registry:
                raise PipelineError("identity event does not bind the canonical logical registry")
            _validate_e0_document(
                documents["e0_receipt"],
                synthetic=synthetic,
                registry_sha256=registry["registry_sha256"],
                experiment_identity_self_sha256=experiment_identity["self_sha256"],
                base_anchor_self_sha256=base_anchor["self_sha256"],
            )
            if content["registry_sha256"] != registry["registry_sha256"]:
                raise PipelineError("identity lifecycle content differs from registry")
            return

        measurement_specification = self._canonical_document(
            "protocol/measurement_specification_freeze.json"
        )
        _validate_measurement_specification_document(
            measurement_specification,
            synthetic=synthetic,
            experiment_identity=experiment_identity,
            base_anchor=base_anchor,
        )
        if event == "MEASUREMENT_SPECIFICATION_FROZEN":
            return

        p1_terminal = self._canonical_document("records/p1_measurement_records.json")
        _validate_p1_terminal_set_document(
            p1_terminal,
            synthetic=synthetic,
            measurement_specification_self_sha256=measurement_specification["self_sha256"],
            experiment_identity=experiment_identity,
        )
        if event == "P1_OUTCOME_VISIBLE":
            return

        measurement_result = self._canonical_document(
            "protocol/measurement_result_dose_manifest.json"
        )
        _validate_measurement_result_document(
            measurement_result,
            synthetic=synthetic,
            registry_sha256=registry["registry_sha256"],
            experiment_identity_self_sha256=experiment_identity["self_sha256"],
            base_anchor_self_sha256=base_anchor["self_sha256"],
            measurement_specification_self_sha256=measurement_specification["self_sha256"],
            p1_terminal_records_self_sha256=p1_terminal["self_sha256"],
        )
        if event == "MEASUREMENT_RESULT_DOSE_FROZEN":
            if content["dose_status"] != measurement_result["terminal_status"]:
                raise PipelineError("dose lifecycle content differs from measurement result")
            return

        judge_development = self._canonical_document("protocol/judge_development_ledger.json")
        _validate_judge_development_document(
            judge_development,
            synthetic=synthetic,
            measurement_result_self_sha256=measurement_result["self_sha256"],
        )
        if event == "JUDGE_DEVELOPMENT_MANUAL_COMPLETE":
            return

        judge_freeze = self._canonical_document("protocol/judge_freeze.json")
        validate_judge_freeze_document(
            judge_freeze,
            synthetic=synthetic,
            measurement_parent_sha256=measurement_result["self_sha256"],
            development_parent_sha256=judge_development["self_sha256"],
        )
        if event in {"JUDGE_FROZEN", "FORMAL_SUPPORT_GENERATION_STARTED"}:
            if (
                event == "FORMAL_SUPPORT_GENERATION_STARTED"
                and measurement_result["terminal_status"] != "ESTIMABLE"
            ):
                raise PipelineError("support generation cannot start after non-estimable P1 dose")
            return

        dose_context = self._issue_dose_context_from_validated_documents(
            registry_document=registry,
            measurement_result=measurement_result,
        )
        support_execution_sources = self._canonical_document(SUPPORT_EXECUTION_SOURCE_PATH)
        support_execution = self._canonical_document("protocol/support_execution_manifest.json")
        validate_support_execution_document(
            support_execution,
            source_document=support_execution_sources,
            registry_document=registry,
            lifecycle_receipt=self.receipt,
            lifecycle_artifact_root=self.artifact_root,
            judge_freeze_self_sha256=judge_freeze["self_sha256"],
            measurement_result_dose_manifest=measurement_result,
            dose_context=dose_context,
        )
        if event == "SUPPORT_EXECUTION_MANIFEST_FROZEN":
            return

        behavior_confirmation = self._canonical_document(
            "protocol/behavior_confirmation_freeze.json"
        )
        _validate_behavior_confirmation_document(
            behavior_confirmation,
            synthetic=synthetic,
            registry_document=registry,
            experiment_identity_self_sha256=experiment_identity["self_sha256"],
            measurement_specification_self_sha256=measurement_specification["self_sha256"],
            measurement_result_self_sha256=measurement_result["self_sha256"],
            judge_freeze_self_sha256=judge_freeze["self_sha256"],
            support_execution_document=support_execution,
        )

    def _artifact_payload(
        self,
        event: str,
        artifact_path: str,
        parent_entry_sha256: str | None,
        previous_artifact_self_sha256: str | None,
    ) -> dict[str, Any]:
        expected_path = LIFECYCLE_ARTIFACT_PATHS[event]
        if artifact_path != expected_path:
            raise PipelineError(f"{event} requires canonical artifact path {expected_path}")
        pure = PurePosixPath(artifact_path)
        resolved, document = self._read_artifact(artifact_path)
        artifact_self_sha256 = document["self_sha256"]
        expected_keys = {
            "schema_version", "protocol_version", "artifact_kind", "lifecycle_event",
            "synthetic", "formal_experiment", "previous_lifecycle_artifact_self_sha256",
            "bound_artifacts", "content", "created_at_utc", "self_sha256",
        }
        if set(document) != expected_keys:
            raise PipelineError("lifecycle artifact fields differ from the event contract")
        if (
            document["schema_version"] != LIFECYCLE_SCHEMA_VERSION
            or document["protocol_version"] != "v3.5-rc2"
            or document["artifact_kind"] != LIFECYCLE_ARTIFACT_KINDS[event]
            or document["lifecycle_event"] != event
        ):
            raise PipelineError("lifecycle artifact schema/event identity mismatch")
        if document.get("synthetic") is not self.receipt.synthetic:
            raise PipelineError("lifecycle artifact synthetic mode mismatch")
        if document.get("formal_experiment") is not (not self.receipt.synthetic):
            raise PipelineError("lifecycle artifact formal mode mismatch")
        if document["previous_lifecycle_artifact_self_sha256"] != previous_artifact_self_sha256:
            raise PipelineError("lifecycle artifact parent self hash is forged or stale")
        if not isinstance(document["created_at_utc"], str) or not document["created_at_utc"]:
            raise PipelineError("lifecycle artifact created_at_utc is invalid")
        content = document["content"]
        if not isinstance(content, Mapping) or set(content) != LIFECYCLE_CONTENT_KEYS[event]:
            raise PipelineError("lifecycle event content fields differ")
        bound = document["bound_artifacts"]
        expected_bound = LIFECYCLE_BOUND_PATHS[event]
        if not isinstance(bound, Mapping) or set(bound) != set(expected_bound):
            raise PipelineError("lifecycle event bound-artifact aliases differ")
        bound_documents: dict[str, dict[str, Any]] = {}
        for alias, expected_bound_path in expected_bound.items():
            reference = bound[alias]
            if not isinstance(reference, Mapping) or set(reference) != {"path", "self_sha256"}:
                raise PipelineError("lifecycle bound-artifact reference fields differ")
            if reference["path"] != expected_bound_path:
                raise PipelineError(f"lifecycle bound artifact path changed for {alias}")
            _, bound_document = self._read_artifact(expected_bound_path)
            if reference["self_sha256"] != bound_document["self_sha256"]:
                raise PipelineError(f"lifecycle bound artifact parent hash mismatch for {alias}")
            bound_documents[alias] = bound_document
        self._validate_bound_artifacts(event, bound_documents, content)
        self._validate_content(event, content)
        return {
            "artifact_path": pure.as_posix(),
            "artifact_file_sha256": file_sha256(resolved),
            "artifact_self_sha256": artifact_self_sha256,
            "parent_entry_sha256": parent_entry_sha256,
        }

    @staticmethod
    def _validate_content(event: str, content: Mapping[str, Any]) -> None:
        if event == "IDENTITIES_AND_E0_VALID":
            registry_hash = content["registry_sha256"]
            if not isinstance(registry_hash, str) or len(registry_hash) != 64:
                raise PipelineError("identity lifecycle content registry hash is invalid")
            if content["logical_identity_count"] != 5_580 or content["e0_status"] != "PASS":
                raise PipelineError("identity lifecycle content does not close E0 and 5,580 IDs")
        elif event == "MEASUREMENT_SPECIFICATION_FROZEN":
            if content["p1_forward_started"] is not False:
                raise PipelineError("measurement specification was not frozen pre-outcome")
        elif event == "P1_OUTCOME_VISIBLE":
            if content != {"p1_outcome_visible": True, "scheduled_p1_identities": 200}:
                raise PipelineError("P1 outcome event content changed")
        elif event == "MEASUREMENT_RESULT_DOSE_FROZEN":
            if content["dose_status"] not in {"ESTIMABLE", "P1_DOSE_NON_ESTIMABLE"}:
                raise PipelineError("measurement-result dose status is invalid")
        elif event == "JUDGE_DEVELOPMENT_MANUAL_COMPLETE":
            if any(content[field] != 0 for field in (
                "formal_response_identities", "generation_calls", "automated_judge_calls"
            )) or content["review_status"] != "COMPLETE":
                raise PipelineError("judge development must remain manual-only and zero-call")
        elif event == "JUDGE_FROZEN":
            if content != {
                "judge_model_family": "Qwen/Qwen3-8B",
                "exact_json_parser": True,
                "single_retry": True,
            }:
                raise PipelineError("judge freeze content changed")
        elif event in {
            "FORMAL_SUPPORT_GENERATION_STARTED", "FORMAL_CONFIRMATION_GENERATION_STARTED"
        }:
            expected_phase = "support" if event.startswith("FORMAL_SUPPORT") else "confirmation"
            if content != {"execution_phase": expected_phase, "authorization_status": "AUTHORIZED"}:
                raise PipelineError("generation-start authorization content changed")
        elif event == "SUPPORT_EXECUTION_MANIFEST_FROZEN":
            if content != {
                "scheduled_support_identities": 900,
                "terminal_dispositions_complete": True,
            }:
                raise PipelineError("support execution manifest lifecycle content changed")
        elif event == "BEHAVIOR_CONFIRMATION_FROZEN":
            if content != {
                "confirmation_identity_count": 4_680,
                "deterministic_support_mapping": True,
            }:
                raise PipelineError("behavior confirmation freeze content changed")

    def advance(self, event: str, artifact_path: str) -> dict[str, Any]:
        current = self.events()
        validate_event_sequence(current)
        if len(current) >= len(EVENT_ORDER) or event != EVENT_ORDER[len(current)]:
            raise PipelineError("lifecycle event is skipped, reordered, or repeated")
        records = self.receipt._load()
        parent = records[-1]["entry_sha256"] if records else None
        previous_artifact = records[-1]["payload"]["artifact_self_sha256"] if records else None
        payload = self._artifact_payload(event, artifact_path, parent, previous_artifact)
        entry = self.receipt.append(event, payload)
        self.verify()
        return entry

    def verify(self) -> dict[str, Any]:
        records = self.receipt._load()
        validate_event_sequence([record["event"] for record in records])
        parent = None
        previous_artifact = None
        for record in records:
            payload = record["payload"]
            if set(payload) != {
                "artifact_path", "artifact_file_sha256", "artifact_self_sha256",
                "parent_entry_sha256",
            }:
                raise PipelineError("lifecycle receipt payload fields differ")
            expected = self._artifact_payload(
                record["event"], payload["artifact_path"], parent, previous_artifact
            )
            if payload != expected:
                raise PipelineError("lifecycle receipt artifact binding mismatch")
            parent = record["entry_sha256"]
            previous_artifact = payload["artifact_self_sha256"]
        summary = self.receipt.verify()
        summary["event_prefix_length"] = len(records)
        summary["materialized_artifacts_valid"] = True
        return summary


class ArtifactStore:
    """Content-addressed JSON writer that refuses overwrite and traversal."""

    def __init__(self, root: Path, *, synthetic: bool = False) -> None:
        self.root = root.resolve()
        self.synthetic = synthetic
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, relative_path: str) -> Path:
        pure = PurePosixPath(relative_path)
        if pure.is_absolute() or ".." in pure.parts:
            raise PipelineError("artifact path must be relative without traversal")
        path = self.root.joinpath(*pure.parts).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise PipelineError("artifact path escapes store root") from exc
        return path

    def write_json_once(self, relative_path: str, document: Mapping[str, Any]) -> dict[str, Any]:
        path = self._path(relative_path)
        if path.exists() or path.is_symlink():
            raise PipelineError(f"append-only artifact already exists: {relative_path}")
        materialized = dict(document)
        if "self_sha256" in materialized:
            raise PipelineError("caller must not supply self_sha256")
        expected_formal = not self.synthetic
        if materialized.get("synthetic", self.synthetic) is not self.synthetic:
            raise PipelineError("artifact synthetic flag differs from store mode")
        if materialized.get("formal_experiment", expected_formal) is not expected_formal:
            raise PipelineError("artifact formal_experiment flag differs from store mode")
        materialized["synthetic"] = self.synthetic
        materialized["formal_experiment"] = expected_formal
        materialized["self_sha256"] = canonical_sha256(materialized)
        encoded = (
            json.dumps(materialized, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        descriptor = os.open(path, flags, 0o600)
        try:
            written = 0
            while written < len(encoded):
                count = os.write(descriptor, encoded[written:])
                if count <= 0:
                    raise OSError("artifact write made no forward progress")
                written += count
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        reread = json.loads(path.read_text(encoding="utf-8"))
        stored_hash = reread.pop("self_sha256", None)
        if stored_hash != canonical_sha256(reread):
            raise PipelineError(f"artifact self hash verification failed: {relative_path}")
        return materialized


def assert_budget(block_counts: Mapping[str, int]) -> dict[str, Any]:
    if dict(block_counts) != BLOCK_BUDGET:
        raise PipelineError(f"logical budget differs from fixed registry: {dict(block_counts)}")
    total = sum(block_counts.values())
    if total != FORMAL_LOGICAL_GENERATION:
        raise PipelineError(f"logical generation total changed: {total}")
    return {
        "block_counts": dict(block_counts),
        "logical_generation": total,
        "first_pass_scheduled_judge": total,
        "k1_reuse": 0,
        "human_items": 720,
    }


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
    generation_first_pass = FORMAL_LOGICAL_GENERATION - generation_unattempted
    if generation_first_pass < 0 or generation_technical_retries > generation_first_pass:
        raise PipelineError("generation retry/unattempted accounting exceeds the frozen registry")
    judge_first_pass = generation_first_pass - prejudge_terminal
    if judge_first_pass < 0 or judge_parse_retries > judge_first_pass:
        raise PipelineError("judge retry/prejudge accounting exceeds eligible identities")
    generation_calls = generation_first_pass + generation_technical_retries
    judge_calls = judge_first_pass + judge_parse_retries
    if generation_calls > 2 * FORMAL_LOGICAL_GENERATION or judge_calls > 2 * FORMAL_LOGICAL_GENERATION:
        raise PipelineError("actual calls exceed one identical retry per logical identity")
    return {
        "logical_generation": FORMAL_LOGICAL_GENERATION,
        "generation_first_pass_calls": generation_first_pass,
        "generation_technical_retries": generation_technical_retries,
        "generation_calls": generation_calls,
        "judge_first_pass_calls": judge_first_pass,
        "judge_parse_retries": judge_parse_retries,
        "judge_calls": judge_calls,
        "generation_unattempted": generation_unattempted,
        "prejudge_terminal": prejudge_terminal,
    }


def _derive_integrity_block_scopes(
    registry: LogicalIdentityRegistry,
    lifecycle: FreezeLifecycle,
    *,
    phase: str,
) -> dict[str, tuple[str, set[str]]]:
    """Derive blocked-ID scopes only from canonical lifecycle artifacts."""
    phase_records = [
        record for record in registry.records()
        if (record["identity"]["block"] == "support") == (phase == "support")
    ]
    phase_ids = {record["logical_id"] for record in phase_records}
    scopes: dict[str, tuple[str, set[str]]] = {}
    experiment_identity = lifecycle.read_validated_document(
        "protocol/experiment_identity_manifest.json"
    )
    identity_status = experiment_identity["terminal_status"]
    if identity_status in {"BLOCKED_EXTERNAL_INPUT", "TERMINAL_BLOCKED_IDENTITY"}:
        scopes[experiment_identity["self_sha256"]] = (identity_status, set(phase_ids))
    measurement_result = lifecycle.read_validated_document(
        "protocol/measurement_result_dose_manifest.json"
    )
    if measurement_result["terminal_status"] == "P1_DOSE_NON_ESTIMABLE":
        scopes[measurement_result["self_sha256"]] = (
            "P1_DOSE_NON_ESTIMABLE", set(phase_ids)
        )
    if phase == "confirmation":
        support_execution = lifecycle.read_validated_document(
            "protocol/support_execution_manifest.json"
        )
        affected: set[str] = set()
        for summary in support_execution["anchor_summaries"]:
            anchor = summary["anchor"]
            if summary["support_status"] != "NON_ESTIMABLE_IDENTITY" or anchor == "H":
                continue
            allowed_blocks = (
                {"P2_A_all", "P2_A_content"}
                if anchor == "A"
                else {"P2_T_all", "P2_T_content", "benign_T"}
            )
            affected.update(
                record["logical_id"]
                for record in phase_records
                if record["identity"]["block"] in allowed_blocks
            )
        if affected:
            scopes[support_execution["self_sha256"]] = (
                "NON_ESTIMABLE_IDENTITY", affected
            )
    return scopes


def reconcile_phase_execution_attempts(
    registry: LogicalIdentityRegistry,
    receipt: AppendOnlyReceipt,
    generation_records: Sequence[Mapping[str, Any]],
    judge_records: Sequence[Mapping[str, Any]],
    dispositions: Sequence[Mapping[str, Any]],
    *,
    phase: str,
    lifecycle_receipt: AppendOnlyReceipt,
    lifecycle_artifact_root: Path,
    _skip_lifecycle_verification: bool = False,
) -> dict[str, Any]:
    """Reconcile one registry-derived execution phase against its historical authorization."""
    if registry.synthetic is not receipt.synthetic:
        raise PipelineError("attempt ledger mode differs from logical registry mode")
    if lifecycle_receipt.synthetic is not registry.synthetic:
        raise PipelineError("lifecycle mode differs from logical registry mode")
    expected_lifecycle_event = {
        "support": "FORMAL_SUPPORT_GENERATION_STARTED",
        "confirmation": "FORMAL_CONFIRMATION_GENERATION_STARTED",
    }.get(phase)
    if expected_lifecycle_event is None:
        raise PipelineError("execution reconciliation phase must be support or confirmation")
    lifecycle = FreezeLifecycle(lifecycle_receipt, lifecycle_artifact_root)
    if not _skip_lifecycle_verification:
        lifecycle.verify()
    authorization_entries = [
        entry for entry in lifecycle_receipt._load()
        if entry["event"] == expected_lifecycle_event
    ]
    if len(authorization_entries) != 1:
        raise PipelineError("phase reconciliation lacks its unique lifecycle authorization")
    authorization = authorization_entries[0]
    expected_lifecycle_tip_sha256 = authorization["entry_sha256"]
    expected_parent_self_sha256 = authorization["payload"]["artifact_self_sha256"]
    registry_manifest = registry.manifest()
    if registry_manifest["identity_count"] != FORMAL_LOGICAL_GENERATION:
        raise IdentityError("execution reconciliation requires the complete 5,580-ID registry")
    receipt.require_execution_registry(
        registry_manifest["registry_sha256"],
        expected_lifecycle_event=expected_lifecycle_event,
        expected_lifecycle_tip_sha256=expected_lifecycle_tip_sha256,
        expected_parent_self_sha256=expected_parent_self_sha256,
    )
    records = receipt._load()
    allowed = {
        "EXECUTION_LEDGER_BOUND",
        "GENERATION_STARTED",
        "GENERATION_TERMINATED",
        "JUDGE_STARTED",
        "JUDGE_TERMINATED",
    }
    states: dict[str, dict[str, Mapping[str, Any]]] = {}
    phase_registry_records = [
        record for record in registry_manifest["records"]
        if (record["identity"]["block"] == "support") == (phase == "support")
    ]
    expected_phase_count = 900 if phase == "support" else 4_680
    if len(phase_registry_records) != expected_phase_count:
        raise IdentityError("registry-derived execution phase count differs")
    identity_by_id = {
        record["logical_id"]: record["identity"] for record in phase_registry_records
    }
    valid_ids = set(identity_by_id)

    generation_by_id: dict[str, dict[str, Any]] = {}
    for raw_record in generation_records:
        record = validate_generation_record(raw_record)
        logical_id = record["logical_id"]
        if logical_id not in valid_ids or logical_id in generation_by_id:
            raise IdentityError("generation record set has an unexpected or duplicate logical identity")
        if record["synthetic"] is not registry.synthetic:
            raise PipelineError("generation record mode differs from logical registry")
        if record["identity_sha256"] != canonical_sha256(identity_by_id[logical_id]):
            raise IdentityError("generation record identity hash differs from fixed registry")
        generation_by_id[logical_id] = record

    judge_by_id: dict[str, dict[str, Any]] = {}
    for raw_record in judge_records:
        record = validate_judge_record(raw_record)
        logical_id = record["logical_id"]
        if logical_id not in valid_ids or logical_id in judge_by_id:
            raise IdentityError("judge record set has an unexpected or duplicate logical identity")
        if record["synthetic"] is not registry.synthetic:
            raise PipelineError("judge record mode differs from logical registry")
        generation_record = generation_by_id.get(logical_id)
        if generation_record is None or not generation_record["generation_completed"]:
            raise PipelineError("judge record lacks its completed materialized generation")
        identity = identity_by_id[logical_id]
        if (
            record["identity_sha256"] != generation_record["identity_sha256"]
            or record["generation_record_sha256"] != generation_record["record_sha256"]
            or record["domain"] != identity["domain"]
        ):
            raise PipelineError("judge record provenance differs from registry/generation")
        judge_by_id[logical_id] = record
    for entry in records[1:]:
        event = entry["event"]
        payload = entry["payload"]
        if event not in allowed or event == "EXECUTION_LEDGER_BOUND":
            raise PipelineError(f"unexpected execution attempt event: {event}")
        logical_id = payload.get("logical_id")
        if logical_id not in valid_ids:
            raise IdentityError("execution ledger contains an identity outside the fixed registry")
        state = states.setdefault(logical_id, {})
        if event in state:
            raise IdentityError(f"duplicate execution event for logical identity: {event}")
        if event == "GENERATION_STARTED":
            if set(payload) != {"logical_id", "request_sha256"}:
                raise PipelineError("generation start payload fields differ")
            if state:
                raise PipelineError("generation start is not the first identity event")
        elif event == "GENERATION_TERMINATED":
            if set(payload) != {
                "logical_id", "request_sha256", "terminal_status", "attempt_count",
                "record_sha256",
            }:
                raise PipelineError("generation terminal payload fields differ")
            started = state.get("GENERATION_STARTED")
            if started is None or any(key.startswith("JUDGE_") for key in state):
                raise PipelineError("generation terminal event is out of order")
            if payload["request_sha256"] != started["request_sha256"]:
                raise IdentityError("generation retry ledger changed request identity")
            if payload["attempt_count"] not in {1, 2}:
                raise PipelineError("generation attempt count exceeds exact retry rule")
            if payload["terminal_status"] not in {
                "COMPLETED", "TERMINAL_TECHNICAL_FAILURE", "TERMINAL_FAILURE",
                "TERMINAL_INDETERMINATE_FAILURE",
            }:
                raise PipelineError("generation terminal status is not registered")
        elif event == "JUDGE_STARTED":
            if set(payload) != {
                "logical_id", "request_sha256", "generation_record_sha256",
                "judge_freeze_self_sha256", "rubric_sha256", "domain",
            }:
                raise PipelineError("judge start payload fields differ")
            generated = state.get("GENERATION_TERMINATED")
            if generated is None or generated["terminal_status"] != "COMPLETED":
                raise PipelineError("judge started without a completed generation")
        else:
            if set(payload) != {
                "logical_id", "request_sha256", "terminal_status", "attempt_count",
                "record_sha256",
            }:
                raise PipelineError("judge terminal payload fields differ")
            started = state.get("JUDGE_STARTED")
            if started is None or payload["request_sha256"] != started["request_sha256"]:
                raise PipelineError("judge terminal event is missing or changed its request")
            if payload["attempt_count"] not in {1, 2}:
                raise PipelineError("judge attempt count exceeds exact retry rule")
            if payload["terminal_status"] not in {
                "PARSED", "TERMINAL_PARSE_OR_INFRASTRUCTURE_FAILURE",
                "TERMINAL_INDETERMINATE_FAILURE",
            }:
                raise PipelineError("judge terminal status is not registered")
        state[event] = payload

    generation_started = 0
    generation_retries = 0
    prejudge_terminal = 0
    judge_started = 0
    judge_retries = 0
    for logical_id, state in states.items():
        if "GENERATION_STARTED" not in state or "GENERATION_TERMINATED" not in state:
            raise PipelineError("execution ledger contains an unterminated generation")
        generation_started += 1
        generation_terminal = state["GENERATION_TERMINATED"]
        generation_record = generation_by_id.get(logical_id)
        if generation_record is None:
            raise PipelineError("generation terminal event lacks its materialized record")
        if generation_terminal != {
            "logical_id": logical_id,
            "request_sha256": generation_record["request_sha256"],
            "terminal_status": generation_record["terminal_status"],
            "attempt_count": generation_record["attempt_count"],
            "record_sha256": generation_record["record_sha256"],
        }:
            raise PipelineError("generation terminal summary differs from its materialized record")
        generation_retries += generation_record["attempt_count"] - 1
        if "JUDGE_STARTED" in state:
            if "JUDGE_TERMINATED" not in state:
                raise PipelineError("execution ledger contains an unterminated judge call")
            judge_started += 1
            judge_record = judge_by_id.get(logical_id)
            if judge_record is None:
                raise PipelineError("judge terminal event lacks its materialized record")
            if state["JUDGE_STARTED"] != {
                "logical_id": logical_id,
                "request_sha256": judge_record["request_sha256"],
                "generation_record_sha256": judge_record["generation_record_sha256"],
                "judge_freeze_self_sha256": judge_record["judge_freeze_self_sha256"],
                "rubric_sha256": judge_record["rubric_sha256"],
                "domain": judge_record["domain"],
            }:
                raise PipelineError("judge start binding differs from its materialized record")
            judge_terminal = state["JUDGE_TERMINATED"]
            if judge_terminal != {
                "logical_id": logical_id,
                "request_sha256": judge_record["request_sha256"],
                "terminal_status": judge_record["terminal_status"],
                "attempt_count": len(judge_record["attempts"]),
                "record_sha256": canonical_sha256(judge_record),
            }:
                raise PipelineError("judge terminal summary differs from its materialized record")
            judge_retries += len(judge_record["attempts"]) - 1
        else:
            if "JUDGE_TERMINATED" in state:
                raise PipelineError("judge terminal event lacks a start")
            if state["GENERATION_TERMINATED"]["terminal_status"] == "COMPLETED":
                raise PipelineError("completed generation is silently missing its scheduled judge")
            prejudge_terminal += 1

    if set(generation_by_id) != set(states):
        raise PipelineError("generation materialized-record set differs from attempt ledger")
    if set(judge_by_id) != {
        logical_id for logical_id, state in states.items() if "JUDGE_STARTED" in state
    }:
        raise PipelineError("judge materialized-record set differs from attempt ledger")

    integrity_scopes = _derive_integrity_block_scopes(registry, lifecycle, phase=phase)
    blocked_ids = set().union(*(scope[1] for scope in integrity_scopes.values()))
    if set(generation_by_id) & blocked_ids:
        raise PipelineError("integrity-blocked identity has a materialized generation record")

    disposition_by_id: dict[str, Mapping[str, Any]] = {}
    disposition_keys = {
        "logical_id", "identity_sha256", "disposition", "generation_record_sha256",
        "judge_record_sha256", "parent_status", "parent_self_sha256",
    }
    for disposition in dispositions:
        if not isinstance(disposition, Mapping) or set(disposition) != disposition_keys:
            raise PipelineError("execution disposition fields differ")
        logical_id = disposition["logical_id"]
        if logical_id not in valid_ids or logical_id in disposition_by_id:
            raise IdentityError("execution disposition has an unexpected or duplicate logical identity")
        expected_identity_hash = canonical_sha256(identity_by_id[logical_id])
        if disposition["identity_sha256"] != expected_identity_hash:
            raise IdentityError("execution disposition identity hash differs from fixed registry")
        generation_record = generation_by_id.get(logical_id)
        judge_record = judge_by_id.get(logical_id)
        if generation_record is not None:
            if (
                logical_id in blocked_ids
                or
                disposition["disposition"] != "EXECUTED"
                or disposition["generation_record_sha256"] != generation_record["record_sha256"]
                or disposition["judge_record_sha256"] != (
                    canonical_sha256(judge_record) if judge_record is not None else None
                )
                or disposition["parent_status"] is not None
                or disposition["parent_self_sha256"] is not None
            ):
                raise PipelineError("executed identity disposition differs from materialized records")
        elif registry.synthetic:
            if disposition != {
                "logical_id": logical_id,
                "identity_sha256": expected_identity_hash,
                "disposition": "SYNTHETIC_NOT_EXECUTED",
                "generation_record_sha256": None,
                "judge_record_sha256": None,
                "parent_status": "SYNTHETIC_DRY_RUN_SCOPE",
                "parent_self_sha256": expected_parent_self_sha256,
            }:
                raise PipelineError("synthetic unexecuted disposition is not explicit and bound")
        else:
            parent_hash = disposition["parent_self_sha256"]
            scope = integrity_scopes.get(parent_hash) if isinstance(parent_hash, str) else None
            if (
                disposition["disposition"] != "UNATTEMPTED_DUE_INTEGRITY_BLOCK"
                or disposition["generation_record_sha256"] is not None
                or disposition["judge_record_sha256"] is not None
                or scope is None
                or scope[0] != disposition["parent_status"]
                or logical_id not in scope[1]
            ):
                raise PipelineError(
                    "formal unattempted identity is outside its normative integrity-block scope"
                )
        disposition_by_id[logical_id] = disposition
    if set(disposition_by_id) != valid_ids:
        raise PipelineError("execution dispositions do not partition the complete phase registry")

    if generation_retries > generation_started or judge_retries > judge_started:
        raise PipelineError("phase retry counts exceed one retry per started identity")
    if generation_started - prejudge_terminal != judge_started:
        raise PipelineError("derived judge eligibility differs from attempt ledger")
    return {
        "phase": phase,
        "phase_logical_id_sha256": canonical_sha256(list(identity_by_id)),
        "logical_generation": expected_phase_count,
        "generation_first_pass_calls": generation_started,
        "generation_technical_retries": generation_retries,
        "generation_calls": generation_started + generation_retries,
        "judge_first_pass_calls": judge_started,
        "judge_parse_retries": judge_retries,
        "judge_calls": judge_started + judge_retries,
        "generation_unattempted": expected_phase_count - generation_started,
        "prejudge_terminal": prejudge_terminal,
        "terminal_dispositions": len(disposition_by_id),
        "executed_dispositions": generation_started,
        "unattempted_dispositions": len(disposition_by_id) - generation_started,
    }


def reconcile_complete_execution(
    registry: LogicalIdentityRegistry,
    *,
    lifecycle_receipt: AppendOnlyReceipt,
    lifecycle_artifact_root: Path,
    support_receipt: AppendOnlyReceipt,
    support_generation_records: Sequence[Mapping[str, Any]],
    support_judge_records: Sequence[Mapping[str, Any]],
    support_dispositions: Sequence[Mapping[str, Any]],
    confirmation_receipt: AppendOnlyReceipt,
    confirmation_generation_records: Sequence[Mapping[str, Any]],
    confirmation_judge_records: Sequence[Mapping[str, Any]],
    confirmation_dispositions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate disjoint event-7/event-10 ledgers into the fixed 5,580 partition."""
    if support_receipt.path.resolve() == confirmation_receipt.path.resolve():
        raise PipelineError("support and confirmation require separate append-only ledgers")
    support = reconcile_phase_execution_attempts(
        registry,
        support_receipt,
        support_generation_records,
        support_judge_records,
        support_dispositions,
        phase="support",
        lifecycle_receipt=lifecycle_receipt,
        lifecycle_artifact_root=lifecycle_artifact_root,
    )
    confirmation = reconcile_phase_execution_attempts(
        registry,
        confirmation_receipt,
        confirmation_generation_records,
        confirmation_judge_records,
        confirmation_dispositions,
        phase="confirmation",
        lifecycle_receipt=lifecycle_receipt,
        lifecycle_artifact_root=lifecycle_artifact_root,
    )
    support_ids = {record["logical_id"] for record in support_dispositions}
    confirmation_ids = {record["logical_id"] for record in confirmation_dispositions}
    registry_ids = {record["logical_id"] for record in registry.records()}
    if support_ids & confirmation_ids or support_ids | confirmation_ids != registry_ids:
        raise IdentityError("phase dispositions are not a disjoint complete 5,580-ID partition")
    total_unattempted = (
        support["generation_unattempted"] + confirmation["generation_unattempted"]
    )
    total_generation_retries = (
        support["generation_technical_retries"]
        + confirmation["generation_technical_retries"]
    )
    total_prejudge = support["prejudge_terminal"] + confirmation["prejudge_terminal"]
    total_judge_retries = support["judge_parse_retries"] + confirmation["judge_parse_retries"]
    totals = assert_actual_call_budget(
        generation_unattempted=total_unattempted,
        generation_technical_retries=total_generation_retries,
        prejudge_terminal=total_prejudge,
        judge_parse_retries=total_judge_retries,
    )
    for field in (
        "generation_first_pass_calls", "generation_technical_retries", "generation_calls",
        "judge_first_pass_calls", "judge_parse_retries", "judge_calls",
        "generation_unattempted", "prejudge_terminal",
    ):
        if totals[field] != support[field] + confirmation[field]:
            raise PipelineError(f"global {field} differs from phase ledgers")
    return {
        **totals,
        "terminal_dispositions": FORMAL_LOGICAL_GENERATION,
        "executed_dispositions": (
            support["executed_dispositions"] + confirmation["executed_dispositions"]
        ),
        "unattempted_dispositions": (
            support["unattempted_dispositions"] + confirmation["unattempted_dispositions"]
        ),
        "support": support,
        "confirmation": confirmation,
        "phase_ledgers_disjoint": True,
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
    if not math.isfinite(parsed):
        raise IdentityError(f"{field} is nonfinite")
    if value != parsed.hex():
        raise IdentityError(f"{field} is not canonical float.hex")
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
    synthetic: bool = False,
) -> LogicalIdentityRegistry:
    """Build exactly the frozen 5,580 response identities without executing them."""
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

    if dose_binding.get("synthetic") is not synthetic:
        raise IdentityError("dose binding synthetic/formal mode differs from logical plan")
    doses = validate_dose_binding(dose_binding)
    registry = LogicalIdentityRegistry(synthetic=synthetic)
    for anchor in ("A", "T", "H"):
        dose = doses[anchor]["mu_all_tw"]
        for prompt_id in screen:
            for vector_index in range(10):
                registry.register(
                    _common_identity(
                        bindings,
                        block="support",
                        domain="harmful",
                        split="D_behavior_screen",
                        prompt_id=prompt_id,
                        vector_id=vector_ids_by_index[vector_index],
                        estimator="mu_all_tw",
                        anchor=anchor,
                        dose=dose,
                    )
                )

    cells = (
        ("P2_A_all", "A", "mu_all_tw"),
        ("P2_A_content", "A", "mu_content_tw"),
        ("P2_T_all", "T", "mu_all_tw"),
        ("P2_T_content", "T", "mu_content_tw"),
    )
    for block, anchor, estimator in cells:
        for prompt_id in confirm:
            for vector_index in range(10, 30):
                registry.register(
                    _common_identity(
                        bindings,
                        block=block,
                        domain="harmful",
                        split="D_behavior_confirm",
                        prompt_id=prompt_id,
                        vector_id=vector_ids_by_index[vector_index],
                        estimator=estimator,
                        anchor=anchor,
                        dose=doses[anchor][estimator],
                    )
                )

    clean_dose = {
        "c_hex": float(0.0).hex(),
        "alpha_pre_dtype_hex": float(0.0).hex(),
        "alpha_post_dtype_hex": float(0.0).hex(),
        "rho_hex": float(0.0).hex(),
    }
    for prompt_id in confirm:
        registry.register(
            _common_identity(
                bindings,
                block="harmful_clean",
                domain="harmful",
                split="D_behavior_confirm",
                prompt_id=prompt_id,
                vector_id=None,
                estimator="clean",
                anchor="clean",
                dose=clean_dose,
            )
        )
    for prompt_id in benign:
        for vector_index in range(10, 30):
            registry.register(
                _common_identity(
                    bindings,
                    block="benign_T",
                    domain="benign",
                    split="D_benign_confirm",
                    prompt_id=prompt_id,
                    vector_id=vector_ids_by_index[vector_index],
                    estimator="mu_all_tw",
                    anchor="T",
                    dose=doses["T"]["mu_all_tw"],
                )
            )
        registry.register(
            _common_identity(
                bindings,
                block="benign_clean",
                domain="benign",
                split="D_benign_confirm",
                prompt_id=prompt_id,
                vector_id=None,
                estimator="clean",
                anchor="clean",
                dose=clean_dose,
            )
        )

    counts: dict[str, int] = {block: 0 for block in BLOCK_BUDGET}
    for item in registry.records():
        counts[item["identity"]["block"]] += 1
    assert_budget(counts)
    if len(registry) != FORMAL_LOGICAL_GENERATION:
        raise AssertionError("fixed plan did not produce 5,580 identities")
    return registry
