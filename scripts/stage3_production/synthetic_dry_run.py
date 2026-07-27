#!/usr/bin/env python3
"""Materialize a synthetic/non-formal Stage 3 plan and exercise failure paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import (  # noqa: E402
    DECODE_CONFIG,
    JUDGE_CONFIG,
    AppendOnlyReceipt,
    GenerationProducer,
    LogicalIdentityRegistry,
    TechnicalGenerationError,
    canonical_sha256,
    classify_support,
    parse_judge_with_retry,
    utc_now,
)
from stage3_pipeline.execution import (  # noqa: E402
    ArtifactStore,
    FreezeLifecycle,
    EVENT_ORDER,
    LIFECYCLE_ARTIFACT_KINDS,
    LIFECYCLE_ARTIFACT_PATHS,
    LIFECYCLE_BOUND_PATHS,
    LIFECYCLE_SCHEMA_VERSION,
    SUPPORT_ATTEMPT_RECEIPT_PATH,
    SUPPORT_EXECUTION_SOURCE_PATH,
    assert_actual_call_budget,
    assert_budget,
    build_logical_plan,
    materialize_support_execution_document,
    materialize_support_execution_sources,
    reconcile_complete_execution,
    status_with_analysis_precedence,
)
from stage3_pipeline.dose import (  # noqa: E402
    build_call_dose_evidence,
    build_synthetic_dose_binding,
)
from stage3_pipeline.records import (  # noqa: E402
    validate_generation_record,
    validate_judge_record,
    validate_p2_materialization,
)
from stage3_pipeline.references import ReferenceAdapter  # noqa: E402
from stage3_pipeline.local_temp import require_project_local_temp  # noqa: E402


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_plan() -> tuple[object, dict[str, object]]:
    screen = [f"synthetic-screen-{index:03d}" for index in range(30)]
    confirm = [f"synthetic-confirm-{index:03d}" for index in range(50)]
    benign = [f"synthetic-benign-{index:03d}" for index in range(30)]
    prompts = screen + confirm + benign
    bindings = {
        "model_revision": "synthetic-no-checkpoint",
        "template_sha256": digest("synthetic-template"),
        "rendered_prompt_sha256_by_id": {item: digest("rendered:" + item) for item in prompts},
        "layer": 1,
        "hook_site": "residual_post",
        "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
        "code_sha256": digest("synthetic-code"),
        "config_sha256": digest("synthetic-config"),
        "environment_sha256": digest("synthetic-environment"),
    }
    dose_binding = build_synthetic_dose_binding(
        mu_all_tw=4.0,
        mu_content_tw=3.2,
        median_content_norm=10.0,
        rho_by_anchor={"A": 0.10, "T": 0.20, "H": 0.30},
        parent_hash=digest("synthetic-parent"),
    )
    registry = build_logical_plan(
        bindings=bindings,
        screen_prompt_ids=screen,
        confirm_prompt_ids=confirm,
        benign_prompt_ids=benign,
        vector_ids_by_index={index: f"synthetic-vector-{index:02d}" for index in range(30)},
        dose_binding=dose_binding,
        synthetic=True,
    )
    return registry, dose_binding


def build_synthetic_lifecycle(
    store: ArtifactStore,
    plan_manifest: dict[str, object],
    dose_binding: dict[str, object],
    *,
    measurement_specification_extra: dict[str, object] | None = None,
    backing_overrides: dict[str, dict[str, object]] | None = None,
    support_identity_failure_anchor: str | None = None,
    forged_previous_event: str | None = None,
    stop_after_event: str | None = None,
    support_execution_callback: Callable[
        [LogicalIdentityRegistry, FreezeLifecycle, AppendOnlyReceipt, Mapping[str, object]],
        Mapping[str, object],
    ] | None = None,
) -> tuple[FreezeLifecycle, dict[str, object], dict[str, dict[str, object]]]:
    overrides = backing_overrides or {}

    def write_backing(path: str, payload: dict[str, object]) -> dict[str, object]:
        materialized = dict(payload)
        if path == "protocol/measurement_specification_freeze.json" and measurement_specification_extra:
            materialized.update(measurement_specification_extra)
        materialized.update(overrides.get(path, {}))
        return store.write_json_once(path, materialized)

    logical_registry = write_backing("logical_registry.json", dict(plan_manifest))
    registry_records = plan_manifest["records"]
    assert isinstance(registry_records, list)

    def ordered_prompt_ids(block: str) -> list[str]:
        ordered: list[str] = []
        for item in registry_records:
            identity = item["identity"]
            if identity["block"] == block and identity["prompt_id"] not in ordered:
                ordered.append(identity["prompt_id"])
        return ordered

    prompt_frames = {
        "behavior_screen": ordered_prompt_ids("support"),
        "behavior_confirmation": ordered_prompt_ids("P2_A_all"),
        "benign_confirmation": ordered_prompt_ids("benign_T"),
        "p1_harmful": [f"synthetic-p1-harmful-{index:03d}" for index in range(100)],
        "p1_benign": [f"synthetic-p1-benign-{index:03d}" for index in range(100)],
    }
    experiment_identity = write_backing(
        "protocol/experiment_identity_manifest.json",
        {
            "schema_version": "paper1-stage3-experiment-identity-manifest-v1",
            "protocol_version": "v3.5-rc2",
            "artifact_kind": "experiment_identity_manifest",
            "terminal_status": "READY",
            "logical_registry_path": "logical_registry.json",
            "logical_registry_self_sha256": logical_registry["self_sha256"],
            "registry_sha256": plan_manifest["registry_sha256"],
            "logical_identity_count": 5_580,
            "prompt_frames": prompt_frames,
            "prompt_frame_sha256": canonical_sha256(prompt_frames),
            "model_identity_sha256": digest("synthetic-behavior-model-identity"),
            "vector_manifest_sha256": digest("synthetic-vector-manifest"),
            "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
            "code_sha256": digest("synthetic-code"),
            "config_sha256": digest("synthetic-config"),
            "environment_sha256": digest("synthetic-environment"),
            "created_at_utc": utc_now(),
        },
    )
    rho_by_anchor = {
        entry["anchor"]: entry["rho"] for entry in dose_binding["anchors"]
    }
    base_anchor = write_backing(
        "protocol/base_anchor_manifest.json",
        {
            "schema_version": "paper1-stage3-base-anchor-manifest-v1",
            "protocol_version": "v3.5-rc2",
            "artifact_kind": "base_anchor_manifest",
            "terminal_status": "READY",
            "experiment_identity_self_sha256": experiment_identity["self_sha256"],
            "anchor_order": ["A", "T", "H"],
            "rho_by_anchor": rho_by_anchor,
            "anchor_binding_sha256": canonical_sha256(rho_by_anchor),
            "code_sha256": digest("synthetic-anchor-code"),
            "config_sha256": digest("synthetic-anchor-config"),
            "environment_sha256": digest("synthetic-anchor-environment"),
            "created_at_utc": utc_now(),
        },
    )
    e0_receipt = write_backing(
        "verification/e0_receipt.json",
        {
            "schema_version": "paper1-stage3-e0-receipt-v1",
            "protocol_version": "v3.5-rc2",
            "artifact_kind": "e0_receipt",
            "status": "PASS",
            "registry_sha256": plan_manifest["registry_sha256"],
            "logical_identity_count": 5_580,
            "experiment_identity_self_sha256": experiment_identity["self_sha256"],
            "base_anchor_self_sha256": base_anchor["self_sha256"],
            "checks": [
                "freeze_lifecycle", "identity_collision", "missing_identity", "invalid_dose",
                "nonfinite_values", "exact_judge_parser", "retry_terminal_failure",
                "retained_predicate", "support_limited", "non_estimable_identity",
                "non_estimable_analysis", "fixed720_allocator", "two_phase_correction",
                "retained_bootstrap", "budget_artifact_checks",
            ],
            "checks_sha256": canonical_sha256([
                "freeze_lifecycle", "identity_collision", "missing_identity", "invalid_dose",
                "nonfinite_values", "exact_judge_parser", "retry_terminal_failure",
                "retained_predicate", "support_limited", "non_estimable_identity",
                "non_estimable_analysis", "fixed720_allocator", "two_phase_correction",
                "retained_bootstrap", "budget_artifact_checks",
            ]),
            "created_at_utc": utc_now(),
        },
    )
    measurement_specification = write_backing(
        "protocol/measurement_specification_freeze.json",
        {
            "schema_version": "paper1-stage3-measurement-specification-freeze-v1",
            "protocol_version": "v3.5-rc2",
            "artifact_kind": "measurement_specification_freeze",
            "experiment_identity_self_sha256": experiment_identity["self_sha256"],
            "base_anchor_self_sha256": base_anchor["self_sha256"],
            "prompt_frame_sha256": experiment_identity["prompt_frame_sha256"],
            "rendering_rules_sha256": digest("synthetic-rendering-rules"),
            "span_rules_sha256": digest("synthetic-span-rules"),
            "complete_case_rules_sha256": digest("synthetic-complete-case-rules"),
            "p1_estimands_sha256": digest("synthetic-p1-estimands"),
            "statistics_binding_sha256": digest("synthetic-statistics-binding"),
            "bootstrap_binding_sha256": digest("synthetic-bootstrap-binding"),
            "failure_rules_sha256": digest("synthetic-failure-rules"),
            "producer_binding_sha256": digest("synthetic-producer-binding"),
            "code_sha256": digest("synthetic-measurement-code"),
            "config_sha256": digest("synthetic-measurement-config"),
            "environment_sha256": digest("synthetic-measurement-environment"),
            "created_at_utc": utc_now(),
            "p1_forward_started": False,
            "registry_sha256": plan_manifest["registry_sha256"],
            "logical_identity_count": 5_580,
        },
    )
    p1_records = []
    for index, prompt_id in enumerate(
        prompt_frames["p1_harmful"] + prompt_frames["p1_benign"]
    ):
        p1_records.append({
            "schema_version": "paper1-stage3-p1-measurement-record-v1",
            "protocol_version": "v3.5-rc2",
            "synthetic": True,
            "logical_id": "sha256:" + digest("synthetic-p1:" + prompt_id),
            "prompt_id": prompt_id,
            "stratum": "harmful" if index < 100 else "benign",
            "identity_complete": True,
            "render_complete": True,
            "valid_mask_complete": True,
            "forward_complete": True,
            "identity_collision": False,
            "valid_token_count": 10,
            "content_token_count": 8,
            "unresolved_valid_token_count": 0,
            "required_norms_finite": True,
            "v_sum": 40.0,
            "c_sum": 25.6,
            "terminal_status": "COMPLETE_CASE",
            "exclusion_reason": None,
        })
    p1_ids = [record["logical_id"] for record in p1_records]
    p1_terminal = write_backing(
        "records/p1_measurement_records.json",
        {
            "schema_version": "paper1-stage3-p1-terminal-record-set-v1",
            "protocol_version": "v3.5-rc2",
            "artifact_kind": "p1_terminal_record_set",
            "measurement_specification_self_sha256": measurement_specification["self_sha256"],
            "experiment_identity_self_sha256": experiment_identity["self_sha256"],
            "scheduled_identity_count": 200,
            "ordered_logical_ids": p1_ids,
            "ordered_logical_ids_sha256": canonical_sha256(p1_ids),
            "records": p1_records,
            "terminal_status": "COMPLETE",
            "created_at_utc": utc_now(),
        },
    )
    rebound_dose = dict(dose_binding)
    rebound_dose.pop("self_sha256", None)
    rebound_dose["parent_self_sha256"] = {
        "measurement_specification_freeze": measurement_specification["self_sha256"],
        "experiment_identity_manifest": experiment_identity["self_sha256"],
        "base_anchor_manifest": base_anchor["self_sha256"],
    }
    rebound_dose["self_sha256"] = canonical_sha256(rebound_dose)
    dose_binding.clear()
    dose_binding.update(rebound_dose)
    measurement_result = write_backing(
        "protocol/measurement_result_dose_manifest.json",
        {
            "schema_version": "paper1-stage3-measurement-result-dose-manifest-v1",
            "protocol_version": "v3.5-rc2",
            "artifact_kind": "measurement_result_dose_manifest",
            "registry_sha256": plan_manifest["registry_sha256"],
            "logical_identity_count": 5_580,
            "parents": {
                "measurement_specification_freeze": measurement_specification["self_sha256"],
                "experiment_identity_manifest": experiment_identity["self_sha256"],
                "base_anchor_manifest": base_anchor["self_sha256"],
                "p1_terminal_records": p1_terminal["self_sha256"],
            },
            "scheduled_p1_identity_count": 200,
            "terminal_status": "ESTIMABLE",
            "dose_binding": rebound_dose,
            "code_sha256": digest("synthetic-dose-code"),
            "config_sha256": digest("synthetic-dose-config"),
            "environment_sha256": digest("synthetic-dose-environment"),
            "created_at_utc": utc_now(),
        },
    )
    judge_development = write_backing(
        "protocol/judge_development_ledger.json",
        {
            "schema_version": "paper1-stage3-judge-development-ledger-v1",
            "protocol_version": "v3.5-rc2",
            "artifact_kind": "judge_development_ledger",
            "measurement_result_dose_manifest_self_sha256": measurement_result["self_sha256"],
            "development_mode": "manual_document_only_rubric_review",
            "formal_response_identities": 0,
            "generation_calls": 0,
            "automated_judge_calls": 0,
            "review_status": "COMPLETE",
            "review_evidence_sha256": digest("synthetic-manual-review-evidence"),
            "created_at_utc": utc_now(),
        },
    )
    judge_freeze = write_backing(
        "protocol/judge_freeze.json",
        {
            "schema_version": "paper1-stage3-judge-freeze-v1",
            "protocol_version": "v3.5-rc2",
            "artifact_kind": "judge_freeze",
            "measurement_result_dose_manifest_self_sha256": measurement_result["self_sha256"],
            "judge_development_ledger_self_sha256": judge_development["self_sha256"],
            "model_family": "Qwen/Qwen3-8B",
            "judge_model_identity_sha256": digest("synthetic-judge-model-identity"),
            "runner_source_sha256": "73c3d4fb9bfbe818370c172e9b19d075ab18b420ca4e5336d728dcf2474d2651",
            "fixed_generation": JUDGE_CONFIG,
            "exact_json_parser": True,
            "single_retry": True,
            "rubric_sha256_by_domain": {
                "harmful": digest("synthetic-harmful-rubric"),
                "benign": digest("synthetic-benign-rubric"),
            },
            "created_at_utc": utc_now(),
        },
    )
    support_registry_rows = [
        item for item in registry_records if item["identity"]["block"] == "support"
    ]
    support_response_records = [{
        "logical_id": item["logical_id"],
        "identity_sha256": canonical_sha256(item["identity"]),
        "synthetic": True,
        "anchor": item["identity"]["anchor"],
        "scheduled_identity_match": True,
        "generation_completed": False,
        "judge_eligible": False,
        "judge_label_parsed": False,
        "identity_complete": True,
        "identity_collision": False,
        "dose_denominator_valid": True,
        "dose_geometry_finite": True,
        "post_dtype_alpha_finite": True,
        "dose_evidence": None,
        "generation_record_sha256": None,
        "judge_record_sha256": None,
        "label": None,
        "terminal_status": "SYNTHETIC_NOT_EXECUTED",
        "retained": False,
    } for item in support_registry_rows]
    if support_identity_failure_anchor is not None:
        if support_identity_failure_anchor not in {"A", "T", "H"}:
            raise ValueError("support_identity_failure_anchor must be A, T, or H")
        failed_row = next(
            row for row in support_response_records
            if row["anchor"] == support_identity_failure_anchor
        )
        failed_row["identity_collision"] = True
        failed_row["terminal_status"] = "NON_ESTIMABLE_IDENTITY"
    backing = {
        "logical_registry.json": logical_registry,
        "protocol/experiment_identity_manifest.json": experiment_identity,
        "protocol/base_anchor_manifest.json": base_anchor,
        "verification/e0_receipt.json": e0_receipt,
        "protocol/measurement_specification_freeze.json": measurement_specification,
        "records/p1_measurement_records.json": p1_terminal,
        "protocol/measurement_result_dose_manifest.json": measurement_result,
        "protocol/judge_development_ledger.json": judge_development,
        "protocol/judge_freeze.json": judge_freeze,
    }
    contents: dict[str, dict[str, object]] = {
        "IDENTITIES_AND_E0_VALID": {
            "registry_sha256": plan_manifest["registry_sha256"],
            "logical_identity_count": 5_580,
            "e0_status": "PASS",
        },
        "MEASUREMENT_SPECIFICATION_FROZEN": {"p1_forward_started": False},
        "P1_OUTCOME_VISIBLE": {"p1_outcome_visible": True, "scheduled_p1_identities": 200},
        "MEASUREMENT_RESULT_DOSE_FROZEN": {"dose_status": "ESTIMABLE"},
        "JUDGE_DEVELOPMENT_MANUAL_COMPLETE": {
            "formal_response_identities": 0,
            "generation_calls": 0,
            "automated_judge_calls": 0,
            "review_status": "COMPLETE",
        },
        "JUDGE_FROZEN": {
            "judge_model_family": "Qwen/Qwen3-8B",
            "exact_json_parser": True,
            "single_retry": True,
        },
        "FORMAL_SUPPORT_GENERATION_STARTED": {
            "execution_phase": "support",
            "authorization_status": "AUTHORIZED",
        },
        "SUPPORT_EXECUTION_MANIFEST_FROZEN": {
            "scheduled_support_identities": 900,
            "terminal_dispositions_complete": True,
        },
        "BEHAVIOR_CONFIRMATION_FROZEN": {
            "confirmation_identity_count": 4_680,
            "deterministic_support_mapping": True,
        },
        "FORMAL_CONFIRMATION_GENERATION_STARTED": {
            "execution_phase": "confirmation",
            "authorization_status": "AUTHORIZED",
        },
    }
    event_receipt = AppendOnlyReceipt(
        store.root / "synthetic_execution_receipt.jsonl", synthetic=True
    )
    lifecycle = FreezeLifecycle(event_receipt, store.root)
    execution_registry = LogicalIdentityRegistry(synthetic=True)
    for item in registry_records:
        if execution_registry.register(item["identity"]) != item["logical_id"]:
            raise AssertionError("synthetic lifecycle registry reconstruction changed logical IDs")
    previous_artifact_self_sha256: str | None = None
    lifecycle_documents: dict[str, dict[str, object]] = {}
    for event in EVENT_ORDER:
        if event == "SUPPORT_EXECUTION_MANIFEST_FROZEN":
            authorization = event_receipt._load()[-1]
            support_receipt = AppendOnlyReceipt(
                store.root / Path(SUPPORT_ATTEMPT_RECEIPT_PATH), synthetic=True
            )
            support_receipt.bind_execution_registry(
                registry_sha256=plan_manifest["registry_sha256"],
                parent_self_sha256=authorization["payload"]["artifact_self_sha256"],
                lifecycle_event="FORMAL_SUPPORT_GENERATION_STARTED",
                lifecycle_tip_sha256=authorization["entry_sha256"],
            )
            execution_payload = (
                support_execution_callback(
                    execution_registry,
                    lifecycle,
                    support_receipt,
                    measurement_result,
                )
                if support_execution_callback is not None
                else {
                    "generation_records": [],
                    "judge_records": [],
                    "response_records": support_response_records,
                }
            )
            generation_records = list(execution_payload["generation_records"])
            judge_records = list(execution_payload["judge_records"])
            response_records = list(execution_payload["response_records"])
            generation_by_id = {
                record["logical_id"]: record for record in generation_records
            }
            judge_by_id = {record["logical_id"]: record for record in judge_records}
            support_dispositions = []
            for item in support_registry_rows:
                logical_id = item["logical_id"]
                generation_record = generation_by_id.get(logical_id)
                judge_record = judge_by_id.get(logical_id)
                support_dispositions.append({
                    "logical_id": logical_id,
                    "identity_sha256": canonical_sha256(item["identity"]),
                    "disposition": (
                        "EXECUTED" if generation_record is not None
                        else "SYNTHETIC_NOT_EXECUTED"
                    ),
                    "generation_record_sha256": (
                        generation_record["record_sha256"]
                        if generation_record is not None else None
                    ),
                    "judge_record_sha256": (
                        canonical_sha256(judge_record) if judge_record is not None else None
                    ),
                    "parent_status": (
                        None if generation_record is not None else "SYNTHETIC_DRY_RUN_SCOPE"
                    ),
                    "parent_self_sha256": (
                        None if generation_record is not None
                        else authorization["payload"]["artifact_self_sha256"]
                    ),
                })
            source_document = materialize_support_execution_sources(
                registry=execution_registry,
                lifecycle_receipt=event_receipt,
                lifecycle_artifact_root=store.root,
                support_receipt=support_receipt,
                generation_records=generation_records,
                judge_records=judge_records,
                dispositions=support_dispositions,
                response_records=response_records,
                measurement_result_dose_manifest=measurement_result,
                created_at_utc=utc_now(),
            )
            source_payload = {
                key: value for key, value in source_document.items() if key != "self_sha256"
            }
            support_sources = write_backing(SUPPORT_EXECUTION_SOURCE_PATH, source_payload)
            support_document = materialize_support_execution_document(
                source_document=support_sources,
                registry_document=logical_registry,
                lifecycle_receipt=event_receipt,
                lifecycle_artifact_root=store.root,
                judge_freeze_self_sha256=judge_freeze["self_sha256"],
                measurement_result_dose_manifest=measurement_result,
                created_at_utc=utc_now(),
            )
            support_payload = {
                key: value for key, value in support_document.items() if key != "self_sha256"
            }
            support_execution = write_backing(
                "protocol/support_execution_manifest.json", support_payload
            )
            summary_by_anchor = {
                summary["anchor"]: summary
                for summary in support_execution["anchor_summaries"]
            }
            support_mapping = {
                anchor: {
                    key: summary_by_anchor[anchor][key]
                    for key in (
                        "support_status", "downstream_status", "execution_action", "affected"
                    )
                }
                for anchor in ("A", "T", "H")
            }
            confirmation_rows = []
            for item in registry_records:
                identity = item["identity"]
                if identity["block"] == "support":
                    continue
                block = identity["block"]
                dependency = (
                    "A" if block in {"P2_A_all", "P2_A_content"}
                    else "T" if block in {"P2_T_all", "P2_T_content", "benign_T"}
                    else None
                )
                support_status = (
                    summary_by_anchor[dependency]["support_status"]
                    if dependency is not None else "NOT_APPLICABLE"
                )
                confirmation_rows.append({
                    "logical_id": item["logical_id"],
                    "identity_sha256": canonical_sha256(identity),
                    "block": block,
                    "support_anchor_dependency": dependency,
                    "support_status": support_status,
                    "execution_disposition": (
                        "UNATTEMPTED_DUE_INTEGRITY_BLOCK"
                        if support_status == "NON_ESTIMABLE_IDENTITY" else "AUTHORIZED"
                    ),
                })
            behavior_confirmation = write_backing(
                "protocol/behavior_confirmation_freeze.json",
                {
                    "schema_version": "paper1-stage3-behavior-confirmation-freeze-v1",
                    "protocol_version": "v3.5-rc2",
                    "artifact_kind": "behavior_confirmation_freeze",
                    "registry_sha256": plan_manifest["registry_sha256"],
                    "logical_identity_count": 5_580,
                    "parents": {
                        "experiment_identity_manifest": experiment_identity["self_sha256"],
                        "measurement_specification_freeze": measurement_specification["self_sha256"],
                        "measurement_result_dose_manifest": measurement_result["self_sha256"],
                        "judge_freeze": judge_freeze["self_sha256"],
                        "support_execution_manifest": support_execution["self_sha256"],
                    },
                    "confirmation_identity_count": 4_680,
                    "block_counts": {
                        "P2_A_all": 1_000,
                        "P2_A_content": 1_000,
                        "P2_T_all": 1_000,
                        "P2_T_content": 1_000,
                        "harmful_clean": 50,
                        "benign_T": 600,
                        "benign_clean": 30,
                    },
                    "support_mapping": support_mapping,
                    "confirmation_rows": confirmation_rows,
                    "confirmation_frame_sha256": canonical_sha256(confirmation_rows),
                    "created_at_utc": utc_now(),
                },
            )
            backing[SUPPORT_EXECUTION_SOURCE_PATH] = support_sources
            backing["protocol/support_execution_manifest.json"] = support_execution
            backing["protocol/behavior_confirmation_freeze.json"] = behavior_confirmation
        bound_artifacts = {
            alias: {
                "path": path,
                "self_sha256": backing[path]["self_sha256"],
            }
            for alias, path in LIFECYCLE_BOUND_PATHS[event].items()
        }
        document = store.write_json_once(
            LIFECYCLE_ARTIFACT_PATHS[event],
            {
                "schema_version": LIFECYCLE_SCHEMA_VERSION,
                "protocol_version": "v3.5-rc2",
                "artifact_kind": LIFECYCLE_ARTIFACT_KINDS[event],
                "lifecycle_event": event,
                "previous_lifecycle_artifact_self_sha256": (
                    ("0" * 64) if event == forged_previous_event else previous_artifact_self_sha256
                ),
                "bound_artifacts": bound_artifacts,
                "content": contents[event],
                "created_at_utc": utc_now(),
            },
        )
        lifecycle_documents[event] = document
        lifecycle.advance(event, LIFECYCLE_ARTIFACT_PATHS[event])
        previous_artifact_self_sha256 = document["self_sha256"]  # type: ignore[assignment]
        if event == stop_after_event:
            break
    return lifecycle, lifecycle.verify(), lifecycle_documents


def main() -> int:
    require_project_local_temp(ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite synthetic output: {output}")
    output.mkdir(parents=True)
    store = ArtifactStore(output, synthetic=True)

    registry, dose_binding = build_plan()
    records = registry.records()  # type: ignore[union-attr]
    block_counts = Counter(item["identity"]["block"] for item in records)
    budget = assert_budget(dict(block_counts))
    plan_manifest = registry.manifest()  # type: ignore[union-attr]
    lifecycle, lifecycle_receipt, lifecycle_documents = build_synthetic_lifecycle(
        store, plan_manifest, dose_binding
    )
    measurement_result_manifest = lifecycle.read_validated_document(
        "protocol/measurement_result_dose_manifest.json"
    )
    dose_context = lifecycle.authenticated_dose_context()
    dose_artifact = store.write_json_once(
        "synthetic_dose_binding.json",
        {
            "schema_version": "paper1-stage3-synthetic-dose-evidence-v1",
            "dose_binding": dose_binding,
        },
    )
    lifecycle_entries = lifecycle.receipt._load()
    support_authorization = next(
        entry for entry in lifecycle_entries
        if entry["event"] == "FORMAL_SUPPORT_GENERATION_STARTED"
    )
    confirmation_authorization = lifecycle_entries[-1]
    support_parent_self_sha256 = lifecycle_documents[
        "FORMAL_SUPPORT_GENERATION_STARTED"
    ]["self_sha256"]
    confirmation_parent_self_sha256 = lifecycle_documents[
        "FORMAL_CONFIRMATION_GENERATION_STARTED"
    ]["self_sha256"]

    p2_items = [item for item in records if item["identity"]["block"].startswith("P2_")]
    selected = p2_items[:3]
    backend_calls: dict[str, int] = Counter()

    def backend(identity: object, request: object) -> dict[str, object]:
        logical_id = request["logical_id"]  # type: ignore[index]
        backend_calls[logical_id] += 1
        if logical_id == selected[0]["logical_id"] and backend_calls[logical_id] == 1:
            raise TechnicalGenerationError("synthetic first-attempt infrastructure failure")
        if logical_id == selected[1]["logical_id"]:
            raise TechnicalGenerationError("synthetic terminal infrastructure failure")
        evidence = build_call_dose_evidence(
            identity=identity,  # type: ignore[arg-type]
            dose_binding=dose_binding,
            generation_status="COMPLETED",
            pre_hook_l2=10.0,
            post_hook_l2=10.5,
            vector_alignment=0.95,
            cosine_drift=0.05,
        )
        return {
            "output_text": "synthetic output",
            "diagnostics": {
                "synthetic": True,
                "dose_evidence_sha256": canonical_sha256(evidence),
                "measurement_result_dose_manifest_self_sha256": (
                    measurement_result_manifest["self_sha256"]
                ),
            },
        }

    support_attempt_receipt = AppendOnlyReceipt(
        output / Path(SUPPORT_ATTEMPT_RECEIPT_PATH), synthetic=True
    )
    support_attempt_receipt.require_execution_registry(
        plan_manifest["registry_sha256"],
        expected_lifecycle_event="FORMAL_SUPPORT_GENERATION_STARTED",
        expected_lifecycle_tip_sha256=support_authorization["entry_sha256"],
        expected_parent_self_sha256=support_parent_self_sha256,
    )
    confirmation_attempt_receipt = AppendOnlyReceipt(
        output / "synthetic_confirmation_attempt_receipt.jsonl", synthetic=True
    )
    confirmation_attempt_receipt.bind_execution_registry(
        registry_sha256=plan_manifest["registry_sha256"],
        parent_self_sha256=confirmation_parent_self_sha256,
        lifecycle_event="FORMAL_CONFIRMATION_GENERATION_STARTED",
        lifecycle_tip_sha256=confirmation_authorization["entry_sha256"],
    )
    producer = GenerationProducer(  # type: ignore[arg-type]
        registry,
        backend,
        synthetic=True,
        execution_receipt=confirmation_attempt_receipt,
        lifecycle_receipt=lifecycle.receipt,
        lifecycle_artifact_root=output,
    )
    generation_records = []
    for item in selected:
        request = {"logical_id": item["logical_id"], "decode_config": DECODE_CONFIG}
        generation_records.append(
            validate_generation_record(producer.produce(item["logical_id"], request))
        )
    if generation_records[0]["retry_count"] != 1:
        raise AssertionError("synthetic retry path did not consume exactly one retry")
    if generation_records[1]["terminal_status"] != "TERMINAL_TECHNICAL_FAILURE":
        raise AssertionError("synthetic terminal failure was silently lost")
    store.write_json_once(
        "generation_records.json",
        {"records": generation_records, "failure_path_preserved": True},
    )

    judge_payloads = ["not-json", '{"label":"safe","rationale":"synthetic rationale"}']
    judge_record = parse_judge_with_retry(
        selected[0]["logical_id"],
        lambda attempt, _request: judge_payloads[attempt - 1],
        {
            "logical_id": selected[0]["logical_id"],
            "judge_config": JUDGE_CONFIG,
        },
        registry=registry,  # type: ignore[arg-type]
        generation_record=generation_records[0],
        synthetic=True,
        execution_receipt=confirmation_attempt_receipt,
        lifecycle_receipt=lifecycle.receipt,
        lifecycle_artifact_root=output,
    )
    validate_judge_record(judge_record)
    terminal_judge = parse_judge_with_retry(
        selected[2]["logical_id"],
        lambda _attempt, _request: "not-json",
        {
            "logical_id": selected[2]["logical_id"],
            "judge_config": JUDGE_CONFIG,
        },
        registry=registry,  # type: ignore[arg-type]
        generation_record=generation_records[2],
        synthetic=True,
        execution_receipt=confirmation_attempt_receipt,
        lifecycle_receipt=lifecycle.receipt,
        lifecycle_artifact_root=output,
    )
    validate_judge_record(terminal_judge)
    store.write_json_once("judge_records.json", {"records": [judge_record, terminal_judge]})
    generation_by_id = {record["logical_id"]: record for record in generation_records}
    judge_by_id = {
        record["logical_id"]: record for record in (judge_record, terminal_judge)
    }
    support_dispositions = []
    confirmation_dispositions = []
    for item in records:
        logical_id = item["logical_id"]
        identity_sha256 = canonical_sha256(item["identity"])
        generation_record = generation_by_id.get(logical_id)
        judge_materialized = judge_by_id.get(logical_id)
        phase_dispositions = (
            support_dispositions
            if item["identity"]["block"] == "support"
            else confirmation_dispositions
        )
        phase_parent = (
            support_parent_self_sha256
            if item["identity"]["block"] == "support"
            else confirmation_parent_self_sha256
        )
        if generation_record is not None:
            phase_dispositions.append(
                {
                    "logical_id": logical_id,
                    "identity_sha256": identity_sha256,
                    "disposition": "EXECUTED",
                    "generation_record_sha256": generation_record["record_sha256"],
                    "judge_record_sha256": (
                        canonical_sha256(judge_materialized)
                        if judge_materialized is not None
                        else None
                    ),
                    "parent_status": None,
                    "parent_self_sha256": None,
                }
            )
        else:
            phase_dispositions.append(
                {
                    "logical_id": logical_id,
                    "identity_sha256": identity_sha256,
                    "disposition": "SYNTHETIC_NOT_EXECUTED",
                    "generation_record_sha256": None,
                    "judge_record_sha256": None,
                    "parent_status": "SYNTHETIC_DRY_RUN_SCOPE",
                    "parent_self_sha256": phase_parent,
                }
            )
    store.write_json_once(
        "execution_dispositions.json",
        {
            "schema_version": "paper1-stage3-execution-disposition-set-v2",
            "registry_sha256": plan_manifest["registry_sha256"],
            "support_authorization_entry_sha256": support_authorization["entry_sha256"],
            "confirmation_authorization_entry_sha256": confirmation_authorization["entry_sha256"],
            "support_records": support_dispositions,
            "confirmation_records": confirmation_dispositions,
        },
    )

    first_identity = selected[0]["identity"]
    p2_record = validate_p2_materialization(
        {
            "schema_version": "paper1-stage3-p2-response-record-v1",
            "protocol_version": "v3.5-rc2",
            "synthetic": True,
            "logical_id": selected[0]["logical_id"],
            "identity_sha256": generation_records[0]["identity_sha256"],
            "generation_record_sha256": generation_records[0]["record_sha256"],
            "judge_record_sha256": canonical_sha256(judge_record),
            "cell": first_identity["block"],
            "prompt_id": first_identity["prompt_id"],
            "vector_id": first_identity["vector_id"],
            "pair_id": f"{first_identity['anchor']}|{first_identity['prompt_id']}|{first_identity['vector_id']}",
            "arm": "all-token",
            "anchor": first_identity["anchor"],
            "estimator": first_identity["estimator"],
            "scheduled_identity_match": True,
            "generation_completed": True,
            "judge_eligible": True,
            "judge_label_parsed": True,
            "identity_complete": True,
            "identity_collision": False,
            "dose_denominator_valid": True,
            "dose_geometry_finite": True,
            "post_dtype_alpha_finite": True,
            "dose_evidence": build_call_dose_evidence(
                identity=first_identity,
                dose_binding=dose_binding,
                generation_status=generation_records[0]["terminal_status"],
                pre_hook_l2=10.0,
                post_hook_l2=10.5,
                vector_alignment=0.95,
                cosine_drift=0.05,
            ),
            "label": judge_record["label"],
            "terminal_status": "COMPLETED_PARSED",
        },
        registry=registry,  # type: ignore[arg-type]
        generation_record=generation_records[0],
        judge_record=judge_record,
        measurement_result_dose_manifest=measurement_result_manifest,
        dose_context=dose_context,
    )
    # Keep artifact provenance outside the schema-validated production record.
    store.write_json_once("p2_record.json", {"record": p2_record})

    support = {}
    for anchor, retained in (("A", 285), ("T", 284), ("H", 285)):
        support[anchor] = classify_support(
            {
                "anchor": anchor,
                "scheduled_identities": 300,
                "unique_scheduled_identities": 300,
                "retained_identities": retained,
                "identity_collisions": 0,
                "unexpected_identities": 0,
                "missing_scheduled_identities": 0,
                "denominator_failures": 0,
                "dose_geometry_failures": 0,
                "post_dtype_alpha_failures": 0,
            }
        )
    support["analysis_precedence"] = {
        "A": status_with_analysis_precedence("SUPPORTED", False),
        "T": status_with_analysis_precedence("SUPPORT_LIMITED", True),
    }
    store.write_json_once("support_status.json", support)

    quota_records = [
        {
            "response_id": f"synthetic-quota-{index:04d}",
            "block": "harmful_clean",
            "predicted_class": ("broken", "unsafe", "refusal", "safe")[index % 4],
            "matched": False,
        }
        for index in range(720)
    ]
    quota = ReferenceAdapter(ROOT).fixed720(quota_records)
    if quota["selected_n"] != 720 or quota["fixed720_status"] != "complete":
        raise AssertionError("fixed720 reference changed the exact human budget")
    store.write_json_once("fixed720_trace.json", quota)

    support_attempt_summary = support_attempt_receipt.verify()
    confirmation_attempt_summary = confirmation_attempt_receipt.verify()
    if support_attempt_summary["entry_count"] != 1:
        raise AssertionError("synthetic support phase ledger lost its event-7 binding")
    if confirmation_attempt_summary["entry_count"] != 11:
        raise AssertionError("synthetic confirmation generation/judge ledger is incomplete")
    actual_calls = reconcile_complete_execution(  # type: ignore[arg-type]
        registry,
        lifecycle_receipt=lifecycle.receipt,
        lifecycle_artifact_root=output,
        support_receipt=support_attempt_receipt,
        support_generation_records=[],
        support_judge_records=[],
        support_dispositions=support_dispositions,
        confirmation_receipt=confirmation_attempt_receipt,
        confirmation_generation_records=generation_records,
        confirmation_judge_records=[judge_record, terminal_judge],
        confirmation_dispositions=confirmation_dispositions,
    )
    budget_upper_bound = assert_actual_call_budget(
        generation_unattempted=0,
        generation_technical_retries=5_580,
        prejudge_terminal=0,
        judge_parse_retries=5_580,
    )

    summary = {
        "schema_version": "paper1-stage3-synthetic-dry-run-v1",
        "marker": "STAGE3_SYNTHETIC_PRODUCTION_DRY_RUN_PASS",
        "synthetic_only": True,
        "formal_experiment_run": False,
        "logical_registry": {
            "identity_count": len(records),
            "registry_sha256": plan_manifest["registry_sha256"],
            "block_counts": dict(sorted(block_counts.items())),
        },
        "budget": budget,
        "executed_synthetic_generation_identities": len(generation_records),
        "retry_preserved_logical_id": generation_records[0]["logical_id"] == selected[0]["logical_id"],
        "terminal_failure_preserved": True,
        "judge_exact_parser_retry": len(judge_record["attempts"]) == 2,
        "manifest_generated": True,
        "artifact_hashes_reproducible": True,
        "hidden_experiment_branches": 0,
        "automatic_budget_expansion": False,
        "lifecycle_receipt": lifecycle_receipt,
        "support_attempt_receipt": support_attempt_summary,
        "confirmation_attempt_receipt": confirmation_attempt_summary,
        "actual_calls": actual_calls,
        "formal_call_upper_bound": budget_upper_bound,
    }
    store.write_json_once("dry_run_summary.json", summary)

    artifacts = []
    for path in sorted(output.rglob("*"), key=lambda value: value.relative_to(output).as_posix()):
        if path.is_file() and path.name != "artifact_inventory.json":
            artifacts.append({
                "path": path.relative_to(output).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    store.write_json_once("artifact_inventory.json", {"artifacts": artifacts})
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
