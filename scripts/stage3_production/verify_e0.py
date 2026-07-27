#!/usr/bin/env python3
"""Run local synthetic E0 tests without model, judge, or formal data calls."""

from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import (  # noqa: E402
    DECODE_CONFIG,
    JUDGE_CONFIG,
    AppendOnlyReceipt,
    GenerationProducer,
    IdentityError,
    LogicalIdentityRegistry,
    PipelineError,
    TechnicalGenerationError,
    TerminalGenerationError,
    canonical_sha256,
    classify_support,
    parse_formal_judge_payload,
    parse_judge_with_retry,
    retained_identity,
    validate_dose,
)
from stage3_pipeline.execution import (  # noqa: E402
    ArtifactStore,
    BLOCK_BUDGET,
    FreezeLifecycle,
    SUPPORT_EXECUTION_SOURCE_PATH,
    assert_actual_call_budget,
    assert_budget,
    reconcile_complete_execution,
    reconcile_phase_execution_attempts,
    status_with_analysis_precedence,
    validate_support_execution_document,
    validate_event_sequence,
)
from stage3_pipeline.dose import (  # noqa: E402
    P1DoseNonEstimable,
    build_call_dose_evidence,
    build_synthetic_dose_binding,
    validate_dose_binding,
)
from stage3_pipeline.records import (  # noqa: E402
    RecordSchemaError,
    validate_benign_record,
    validate_benign_materialization,
    validate_generation_record,
    validate_judge_record,
    validate_k1_materialization,
    validate_k1_record,
    validate_p1_record,
    validate_p2_materialization,
    validate_p2_record,
    validate_support_response_materialization,
)
from stage3_pipeline.references import ReferenceAdapter  # noqa: E402
from stage3_pipeline.local_temp import require_project_local_temp  # noqa: E402
from synthetic_dry_run import build_plan, build_synthetic_lifecycle  # noqa: E402


HASH = "a" * 64


def binary64(value: float) -> dict[str, object]:
    return {"value": value, "binary64_hex": value.hex()}


def synthetic_dose_evidence(
    *,
    estimator: str = "mu_all_tw",
    generation_status: str = "COMPLETED",
) -> dict[str, object]:
    mu = 4.0 if estimator == "mu_all_tw" else 3.0
    nominal_c = 0.25
    alpha = nominal_c * mu
    pre_hook = 10.0
    post_hook = 11.0
    return {
        "status": "VALIDATED",
        "failure_code": None,
        "nominal_c": binary64(nominal_c),
        "mu_estimator": estimator,
        "mu_value": binary64(mu),
        "mu_source_sha256": HASH,
        "alpha_pre_dtype": binary64(alpha),
        "alpha_post_dtype": binary64(alpha),
        "pre_hook_l2": binary64(pre_hook),
        "post_hook_l2": binary64(post_hook),
        "relative_dose": binary64(alpha / pre_hook),
        "norm_ratio": binary64(post_hook / pre_hook),
        "vector_alignment": binary64(0.95),
        "cosine_drift": binary64(0.05),
        "measurement_result_dose_binding_sha256": HASH,
        "generation_status": generation_status,
        "phase": "decode-only",
        "use_cache": True,
    }


def synthetic_identity(prompt: str = "p0") -> dict[str, object]:
    return {
        "profile": "compact_single_gpu",
        "block": "P2_A_all",
        "domain": "harmful",
        "split": "D_behavior_confirm",
        "model_revision": "synthetic-revision",
        "template_sha256": HASH,
        "rendered_prompt_sha256": HASH,
        "prompt_id": prompt,
        "vector_id": "v10",
        "estimator": "mu_all_tw",
        "anchor": "A",
        "c_hex": float(0.25).hex(),
        "alpha_pre_dtype_hex": float(1.0).hex(),
        "alpha_post_dtype_hex": float(1.0).hex(),
        "rho_hex": float(0.1).hex(),
        "layer": 1,
        "hook_site": "residual_post",
        "phase": "decode-only",
        "use_cache": True,
        "generation_config_sha256": HASH,
        "code_sha256": HASH,
        "config_sha256": HASH,
        "environment_sha256": HASH,
    }


def synthetic_measurement_result(
    registry: LogicalIdentityRegistry,
    dose_binding: dict[str, object],
) -> dict[str, object]:
    parents = dose_binding["parent_self_sha256"]
    assert isinstance(parents, dict)
    document = {
        "schema_version": "paper1-stage3-measurement-result-dose-manifest-v1",
        "protocol_version": "v3.5-rc2",
        "artifact_kind": "measurement_result_dose_manifest",
        "synthetic": True,
        "formal_experiment": False,
        "registry_sha256": registry.manifest()["registry_sha256"],
        "logical_identity_count": 5_580,
        "parents": {
            "measurement_specification_freeze": parents["measurement_specification_freeze"],
            "experiment_identity_manifest": parents["experiment_identity_manifest"],
            "base_anchor_manifest": parents["base_anchor_manifest"],
            "p1_terminal_records": HASH,
        },
        "scheduled_p1_identity_count": 200,
        "terminal_status": "ESTIMABLE",
        "dose_binding": dose_binding,
        "code_sha256": HASH,
        "config_sha256": HASH,
        "environment_sha256": HASH,
        "created_at_utc": "synthetic-e0",
    }
    document["self_sha256"] = canonical_sha256(document)
    return document


def execution_dispositions(
    registry: LogicalIdentityRegistry,
    generation_records: list[dict[str, object]],
    judge_records: list[dict[str, object]],
    parent_self_sha256: str,
    *,
    phase: str,
) -> list[dict[str, object]]:
    generation_by_id = {record["logical_id"]: record for record in generation_records}
    judge_by_id = {record["logical_id"]: record for record in judge_records}
    result = []
    for item in registry.records():
        if (item["identity"]["block"] == "support") != (phase == "support"):
            continue
        logical_id = item["logical_id"]
        identity_hash = canonical_sha256(item["identity"])
        generation = generation_by_id.get(logical_id)
        judge = judge_by_id.get(logical_id)
        if generation is None:
            result.append({
                "logical_id": logical_id,
                "identity_sha256": identity_hash,
                "disposition": "SYNTHETIC_NOT_EXECUTED",
                "generation_record_sha256": None,
                "judge_record_sha256": None,
                "parent_status": "SYNTHETIC_DRY_RUN_SCOPE",
                "parent_self_sha256": parent_self_sha256,
            })
        else:
            result.append({
                "logical_id": logical_id,
                "identity_sha256": identity_hash,
                "disposition": "EXECUTED",
                "generation_record_sha256": generation["record_sha256"],
                "judge_record_sha256": canonical_sha256(judge) if judge is not None else None,
                "parent_status": None,
                "parent_self_sha256": None,
            })
    return result


class E0Tests(unittest.TestCase):
    def test_freeze_lifecycle_exact_prefix_and_append_only(self) -> None:
        validate_event_sequence(["IDENTITIES_AND_E0_VALID"])
        with self.assertRaises(PipelineError):
            validate_event_sequence(["P1_OUTCOME_VISIBLE"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStore(root, synthetic=True)
            registry, dose_binding = build_plan()
            lifecycle, summary, _ = build_synthetic_lifecycle(
                store,
                registry.manifest(),
                dose_binding,
                stop_after_event="MEASUREMENT_SPECIFICATION_FROZEN",
            )
            self.assertEqual(summary["event_prefix_length"], 2)
            with self.assertRaises(PipelineError):
                lifecycle.advance(
                    "MEASUREMENT_RESULT_DOSE_FROZEN",
                    "protocol/lifecycle/04_measurement_result_dose_frozen.json",
                )
            self.assertTrue(lifecycle.verify()["append_only_chain_valid"])
        for forbidden in (
            {"mu_all_tw_Qwen": 1.0},
            {"nested": {"medianContentNormQwen": 1.0}},
        ):
            with tempfile.TemporaryDirectory() as directory:
                store = ArtifactStore(Path(directory), synthetic=True)
                registry, dose_binding = build_plan()
                with self.assertRaises(PipelineError):
                    build_synthetic_lifecycle(
                        store,
                        registry.manifest(),
                        dose_binding,
                        measurement_specification_extra=forbidden,
                        stop_after_event="MEASUREMENT_SPECIFICATION_FROZEN",
                    )
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory), synthetic=True)
            registry, dose_binding = build_plan()
            with self.assertRaises(PipelineError):
                lifecycle, _, lifecycle_documents = build_synthetic_lifecycle(
                    store,
                    registry.manifest(),
                    dose_binding,
                    forged_previous_event="MEASUREMENT_SPECIFICATION_FROZEN",
                    stop_after_event="MEASUREMENT_SPECIFICATION_FROZEN",
                )
        forged_parents = (
            (
                "protocol/experiment_identity_manifest.json",
                {"logical_identity_count": 5_579},
                "IDENTITIES_AND_E0_VALID",
            ),
            (
                "protocol/base_anchor_manifest.json",
                {"anchor_order": ["A", "H", "T"]},
                "IDENTITIES_AND_E0_VALID",
            ),
            ("verification/e0_receipt.json", {"status": "FAIL"}, "IDENTITIES_AND_E0_VALID"),
            (
                "protocol/measurement_specification_freeze.json",
                {"registry_sha256": "0" * 64},
                "MEASUREMENT_SPECIFICATION_FROZEN",
            ),
            (
                "records/p1_measurement_records.json",
                {"scheduled_identity_count": 199},
                "P1_OUTCOME_VISIBLE",
            ),
            (
                "protocol/measurement_result_dose_manifest.json",
                {"terminal_status": "P1_DOSE_NON_ESTIMABLE"},
                "MEASUREMENT_RESULT_DOSE_FROZEN",
            ),
            (
                "protocol/judge_development_ledger.json",
                {"automated_judge_calls": 1},
                "JUDGE_DEVELOPMENT_MANUAL_COMPLETE",
            ),
            (
                "protocol/judge_freeze.json",
                {"model_family": "forged-model"},
                "JUDGE_FROZEN",
            ),
            (
                "protocol/support_execution_manifest.json",
                {"scheduled_identity_count": 899},
                "SUPPORT_EXECUTION_MANIFEST_FROZEN",
            ),
            (
                "protocol/behavior_confirmation_freeze.json",
                {"confirmation_identity_count": 4_679},
                "BEHAVIOR_CONFIRMATION_FROZEN",
            ),
        )
        for path, override, stop_event in forged_parents:
            with tempfile.TemporaryDirectory() as directory:
                store = ArtifactStore(Path(directory), synthetic=True)
                registry, dose_binding = build_plan()
                with self.assertRaises(PipelineError, msg=path):
                    build_synthetic_lifecycle(
                        store,
                        registry.manifest(),
                        dose_binding,
                        backing_overrides={path: override},
                        stop_after_event=stop_event,
                    )

    def test_support_manifest_is_uniquely_materialized_from_event7_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStore(root, synthetic=True)
            registry, dose_binding = build_plan()
            lifecycle, _, _ = build_synthetic_lifecycle(
                store, registry.manifest(), dose_binding
            )
            registry_document = lifecycle.read_validated_document("logical_registry.json")
            source_document = lifecycle.read_validated_document(SUPPORT_EXECUTION_SOURCE_PATH)
            measurement_result = lifecycle.read_validated_document(
                "protocol/measurement_result_dose_manifest.json"
            )
            dose_context = lifecycle.authenticated_dose_context()
            judge_freeze = lifecycle.read_validated_document("protocol/judge_freeze.json")
            support = lifecycle.read_validated_document(
                "protocol/support_execution_manifest.json"
            )

            def rehash(document: dict[str, object]) -> dict[str, object]:
                document.pop("self_sha256", None)
                document["self_sha256"] = canonical_sha256(document)
                return document

            def rejected(document: dict[str, object], source: dict[str, object]) -> None:
                with self.assertRaises(PipelineError):
                    validate_support_execution_document(
                        document,
                        source_document=source,
                        registry_document=registry_document,
                        lifecycle_receipt=lifecycle.receipt,
                        lifecycle_artifact_root=root,
                        judge_freeze_self_sha256=judge_freeze["self_sha256"],
                        measurement_result_dose_manifest=measurement_result,
                        dose_context=dose_context,
                    )

            manifest_mutations = []
            forged_completed = copy.deepcopy(support)
            completed_row = forged_completed["rows"][0]
            completed_row.update({
                "generation_completed": True,
                "judge_eligible": True,
                "judge_label_parsed": True,
                "generation_record_sha256": HASH,
                "judge_record_sha256": HASH,
                "label": "safe",
                "terminal_status": "COMPLETED_PARSED",
                "retained": True,
            })
            manifest_mutations.append(forged_completed)
            for field, value in (
                ("generation_record_sha256", HASH),
                ("label", "safe"),
                ("dose_geometry_finite", False),
                ("retained", True),
            ):
                tampered = copy.deepcopy(support)
                tampered["rows"][0][field] = value
                manifest_mutations.append(tampered)
            calls = copy.deepcopy(support)
            calls["actual_calls"].update({
                "generation_first_pass_calls": 1,
                "generation_calls": 1,
            })
            manifest_mutations.append(calls)
            anchor_status = copy.deepcopy(support)
            anchor_status["anchor_summaries"][0]["support_status"] = "SUPPORTED"
            manifest_mutations.append(anchor_status)
            for tampered in manifest_mutations:
                tampered["rows_sha256"] = canonical_sha256(tampered["rows"])
                rejected(rehash(tampered), source_document)

            forged_source = copy.deepcopy(source_document)
            source_row = forged_source["response_records"][0]
            source_row.update({
                "generation_completed": True,
                "judge_eligible": True,
                "judge_label_parsed": True,
                "generation_record_sha256": HASH,
                "judge_record_sha256": HASH,
                "label": "safe",
                "terminal_status": "COMPLETED_PARSED",
                "retained": True,
            })
            forged_source["response_record_set_sha256"] = canonical_sha256(
                forged_source["response_records"]
            )
            rejected(support, rehash(forged_source))

            forged_receipt_binding = copy.deepcopy(source_document)
            forged_receipt_binding["support_receipt_tip_sha256"] = HASH
            rejected(support, rehash(forged_receipt_binding))

    def test_identity_collision_duplicate_and_missing(self) -> None:
        registry = LogicalIdentityRegistry(synthetic=True)
        logical_id = registry.register(synthetic_identity())
        self.assertTrue(logical_id.startswith("sha256:"))
        with self.assertRaises(IdentityError):
            registry.register(synthetic_identity())
        with self.assertRaises(IdentityError):
            registry.require("sha256:" + "0" * 64)
        wrong_cell_mapping = synthetic_identity()
        wrong_cell_mapping["estimator"] = "mu_content_tw"
        with self.assertRaises(IdentityError):
            LogicalIdentityRegistry(synthetic=True).register(wrong_cell_mapping)
        noncanonical_dose = synthetic_identity()
        noncanonical_dose["c_hex"] = "0X1.0000000000000P-2"
        with self.assertRaises(IdentityError):
            LogicalIdentityRegistry(synthetic=True).register(noncanonical_dose)
        nonfinite_identity = synthetic_identity()
        nonfinite_identity["rho_hex"] = "nan"
        with self.assertRaises(IdentityError):
            LogicalIdentityRegistry(synthetic=True).register(nonfinite_identity)

    def test_invalid_and_nonfinite_dose(self) -> None:
        with self.assertRaises(PipelineError):
            validate_dose(
                clean=False,
                c=1.0,
                alpha_pre_dtype=1.0,
                alpha_post_dtype=1.0,
                rho=0.1,
                pre_hook_l2=0.0,
            )

    def test_measurement_result_dose_formula_and_anchor_order(self) -> None:
        binding = build_synthetic_dose_binding(
            mu_all_tw=4.0,
            mu_content_tw=3.0,
            median_content_norm=10.0,
            rho_by_anchor={"A": 0.1, "T": 0.2, "H": 0.3},
            parent_hash="b" * 64,
        )
        doses = validate_dose_binding(binding)
        self.assertEqual(doses["A"]["mu_all_tw"]["c_hex"], (0.1 * 10.0 / 4.0).hex())
        self.assertEqual(doses["A"]["mu_all_tw"]["rho_hex"], (0.1).hex())
        expected_c = 0.1 * 10.0 / 4.0
        expected_content_alpha = expected_c * 3.0
        self.assertEqual(
            doses["A"]["mu_content_tw"]["rho_hex"],
            (expected_content_alpha / 10.0).hex(),
        )
        invalid_formula = copy.deepcopy(binding)
        invalid_formula["anchors"][0]["c"] = {"value": 0.5, "binary64_hex": (0.5).hex()}
        invalid_formula["self_sha256"] = canonical_sha256(
            {key: value for key, value in invalid_formula.items() if key != "self_sha256"}
        )
        with self.assertRaises(P1DoseNonEstimable):
            validate_dose_binding(invalid_formula)
        invalid_order = build_synthetic_dose_binding(
            mu_all_tw=4.0,
            mu_content_tw=3.0,
            median_content_norm=10.0,
            rho_by_anchor={"A": 0.2, "T": 0.2, "H": 0.3},
            parent_hash="b" * 64,
        )
        with self.assertRaises(P1DoseNonEstimable):
            validate_dose_binding(invalid_order)
        with self.assertRaises(PipelineError):
            validate_dose(
                clean=False,
                c=1.0,
                alpha_pre_dtype=math.inf,
                alpha_post_dtype=1.0,
                rho=0.1,
                pre_hook_l2=2.0,
            )

    def test_exact_judge_parser_and_retry(self) -> None:
        parsed = parse_formal_judge_payload(
            '{"label":"unsafe","rationale":"synthetic"}', "harmful"
        )
        self.assertEqual(parsed["label"], "unsafe")
        for invalid in (
            "unsafe",
            '{"label":"unsafe","rationale":""}',
            '{"label":"unsafe","rationale":"x","score":1}',
            '{"label":"safe","label":"unsafe","rationale":"x"}',
            '<think>x</think>{"label":"unsafe","rationale":"x"}',
        ):
            with self.assertRaises(PipelineError):
                parse_formal_judge_payload(invalid, "harmful")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStore(root, synthetic=True)
            registry, dose_binding = build_plan()
            lifecycle, _, lifecycle_documents = build_synthetic_lifecycle(
                store, registry.manifest(), dose_binding
            )
            authorization = lifecycle.receipt._load()[-1]
            receipt = AppendOnlyReceipt(root / "judge-attempts.jsonl", synthetic=True)
            receipt.bind_execution_registry(
                registry_sha256=registry.manifest()["registry_sha256"],
                parent_self_sha256=lifecycle_documents[
                    "FORMAL_CONFIRMATION_GENERATION_STARTED"
                ]["self_sha256"],
                lifecycle_event="FORMAL_CONFIRMATION_GENERATION_STARTED",
                lifecycle_tip_sha256=authorization["entry_sha256"],
            )
            selected = [
                item for item in registry.records()
                if item["identity"]["block"] == "P2_A_all"
            ][:3]
            producer = GenerationProducer(
                registry,
                lambda _identity, _request: {"output_text": "ok", "diagnostics": {}},
                synthetic=True,
                execution_receipt=receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=root,
            )
            generations = [
                producer.produce(
                    item["logical_id"],
                    {"logical_id": item["logical_id"], "decode_config": DECODE_CONFIG},
                )
                for item in selected[:2]
            ]
            calls: list[int] = []
            observed_requests: list[object] = []

            def judge(attempt: int, request: object) -> str:
                calls.append(attempt)
                observed_requests.append(request)
                return "bad" if attempt == 1 else '{"label":"safe","rationale":"synthetic"}'

            request = {"logical_id": selected[0]["logical_id"], "judge_config": JUDGE_CONFIG}
            result = parse_judge_with_retry(
                selected[0]["logical_id"],
                judge,
                request,
                registry=registry,
                generation_record=generations[0],
                synthetic=True,
                execution_receipt=receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=root,
            )
            terminal = parse_judge_with_retry(
                selected[1]["logical_id"],
                lambda _attempt, _request: "bad",
                {"logical_id": selected[1]["logical_id"], "judge_config": JUDGE_CONFIG},
                registry=registry,
                generation_record=generations[1],
                synthetic=True,
                execution_receipt=receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=root,
            )
            self.assertEqual(calls, [1, 2])
            self.assertEqual(observed_requests[0], observed_requests[1])
            self.assertTrue(result["judge_label_parsed"])
            self.assertEqual(len(terminal["attempts"]), 2)
            self.assertFalse(terminal["judge_label_parsed"])
            invalid_retry = copy.deepcopy(result)
            invalid_retry["attempts"][0] = copy.deepcopy(invalid_retry["attempts"][1])
            invalid_retry["attempts"][0]["attempt_index"] = 1
            with self.assertRaises(RecordSchemaError):
                validate_judge_record(invalid_retry)
            wrong_request = copy.deepcopy(result)
            wrong_request["attempts"][1]["request_sha256"] = "0" * 64
            with self.assertRaises(RecordSchemaError):
                validate_judge_record(wrong_request)
            missing_payload_hash = copy.deepcopy(result)
            missing_payload_hash["attempts"][1]["payload_sha256"] = None
            with self.assertRaises(RecordSchemaError):
                validate_judge_record(missing_payload_hash)
            empty_failure_code = copy.deepcopy(terminal)
            empty_failure_code["attempts"][0]["failure_code"] = ""
            with self.assertRaises(RecordSchemaError):
                validate_judge_record(empty_failure_code)
            forbidden_calls = []
            with self.assertRaises(IdentityError):
                parse_judge_with_retry(
                    selected[2]["logical_id"],
                    lambda *_args: forbidden_calls.append(True) or "bad",
                    {
                        "logical_id": selected[2]["logical_id"],
                        "judge_config": JUDGE_CONFIG,
                        "rubric_sha256": HASH,
                    },
                    registry=registry,
                    generation_record=generations[0],
                    synthetic=True,
                    execution_receipt=receipt,
                    lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )
            self.assertEqual(forbidden_calls, [])
            failed_generation = GenerationProducer(
                registry,
                lambda _identity, _request: (_ for _ in ()).throw(
                    TechnicalGenerationError("synthetic terminal")
                ),
                synthetic=True,
            ).produce(
                selected[2]["logical_id"],
                {"logical_id": selected[2]["logical_id"], "decode_config": DECODE_CONFIG},
            )
            with self.assertRaises(PipelineError):
                parse_judge_with_retry(
                    selected[2]["logical_id"],
                    lambda *_args: forbidden_calls.append(True) or "bad",
                    {"logical_id": selected[2]["logical_id"], "judge_config": JUDGE_CONFIG},
                    registry=registry,
                    generation_record=failed_generation,
                    synthetic=True,
                    execution_receipt=receipt,
                    lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )
            support_item = next(
                item for item in registry.records() if item["identity"]["block"] == "support"
            )
            support_generation = GenerationProducer(
                registry,
                lambda _identity, _request: {"output_text": "support", "diagnostics": {}},
                synthetic=True,
            ).produce(
                support_item["logical_id"],
                {"logical_id": support_item["logical_id"], "decode_config": DECODE_CONFIG},
            )
            support_event = next(
                entry for entry in lifecycle.receipt._load()
                if entry["event"] == "FORMAL_SUPPORT_GENERATION_STARTED"
            )
            support_receipt = AppendOnlyReceipt(root / "late-support.jsonl", synthetic=True)
            support_receipt.bind_execution_registry(
                registry_sha256=registry.manifest()["registry_sha256"],
                parent_self_sha256=support_event["payload"]["artifact_self_sha256"],
                lifecycle_event="FORMAL_SUPPORT_GENERATION_STARTED",
                lifecycle_tip_sha256=support_event["entry_sha256"],
            )
            support_receipt.append("GENERATION_STARTED", {
                "logical_id": support_item["logical_id"],
                "request_sha256": support_generation["request_sha256"],
            })
            support_receipt.append("GENERATION_TERMINATED", {
                "logical_id": support_item["logical_id"],
                "request_sha256": support_generation["request_sha256"],
                "terminal_status": support_generation["terminal_status"],
                "attempt_count": support_generation["attempt_count"],
                "record_sha256": support_generation["record_sha256"],
            })
            with self.assertRaises(PipelineError):
                parse_judge_with_retry(
                    support_item["logical_id"],
                    lambda *_args: forbidden_calls.append(True) or "bad",
                    {
                        "logical_id": support_item["logical_id"],
                        "judge_config": JUDGE_CONFIG,
                    },
                    registry=registry,
                    generation_record=support_generation,
                    synthetic=True,
                    execution_receipt=support_receipt,
                    lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )
            self.assertEqual(forbidden_calls, [])

    def test_generation_retry_preserves_identity_and_terminal_failure(self) -> None:
        registry = LogicalIdentityRegistry(synthetic=True)
        logical_id = registry.register(synthetic_identity())
        calls = []

        def backend(identity: object, request: object) -> dict[str, object]:
            calls.append((copy.deepcopy(identity), copy.deepcopy(request)))
            if len(calls) == 1:
                raise TechnicalGenerationError("synthetic transient")
            return {"output_text": "synthetic output", "diagnostics": {"fixture": True}}

        request = {"logical_id": logical_id, "decode_config": DECODE_CONFIG}
        producer = GenerationProducer(registry, backend, synthetic=True)
        result = producer.produce(logical_id, request)
        validate_generation_record(result)
        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(calls[0], calls[1])
        terminal = GenerationProducer(
            registry,
            lambda _identity, _request: (_ for _ in ()).throw(TechnicalGenerationError("down")),
            synthetic=True,
        ).produce(logical_id, request)
        validate_generation_record(terminal)
        self.assertEqual(terminal["terminal_status"], "TERMINAL_TECHNICAL_FAILURE")
        self.assertEqual(terminal["attempt_count"], 2)
        for exception in (
            RuntimeError("unexpected runtime"),
            OSError("unexpected device I/O"),
            KeyboardInterrupt("synthetic interruption"),
        ):
            indeterminate = GenerationProducer(
                registry,
                lambda _identity, _request, failure=exception: (_ for _ in ()).throw(failure),
                synthetic=True,
            ).produce(logical_id, request)
            validate_generation_record(indeterminate)
            self.assertEqual(
                indeterminate["terminal_status"], "TERMINAL_INDETERMINATE_FAILURE"
            )
            self.assertEqual(indeterminate["attempt_count"], 1)
        invalid_generation_retry = copy.deepcopy(result)
        invalid_generation_retry["attempts"][1]["status"] = "TECHNICAL_FAILURE_RETRYABLE"
        invalid_generation_retry["terminal_status"] = "TECHNICAL_FAILURE_RETRYABLE"
        invalid_generation_retry["generation_completed"] = False
        invalid_generation_retry["output_text"] = None
        invalid_generation_retry["attempts"][1]["output_text"] = None
        invalid_generation_retry["attempts"][1]["failure_code"] = "TechnicalGenerationError"
        invalid_generation_retry["record_sha256"] = canonical_sha256({
            key: value for key, value in invalid_generation_retry.items()
            if key != "record_sha256"
        })
        with self.assertRaises(RecordSchemaError):
            validate_generation_record(invalid_generation_retry)
        tampered_output = copy.deepcopy(result)
        tampered_output["output_text"] = "forged-output"
        tampered_output["attempts"][-1]["output_text"] = "forged-output"
        with self.assertRaises(RecordSchemaError):
            validate_generation_record(tampered_output)
        noncanonical_diagnostics = GenerationProducer(
            registry,
            lambda _identity, _request: {
                "output_text": "must-be-terminalized",
                "diagnostics": {"nonfinite": math.nan},
            },
            synthetic=True,
        ).produce(logical_id, request)
        validate_generation_record(noncanonical_diagnostics)
        self.assertEqual(
            noncanonical_diagnostics["terminal_status"],
            "TERMINAL_FAILURE",
        )
        noncanonical_exception_diagnostics = GenerationProducer(
            registry,
            lambda _identity, _request: (_ for _ in ()).throw(
                TechnicalGenerationError(
                    "noncanonical exception diagnostics",
                    diagnostics={"not_json": {"set-value"}},
                )
            ),
            synthetic=True,
        ).produce(logical_id, request)
        validate_generation_record(noncanonical_exception_diagnostics)
        self.assertEqual(
            noncanonical_exception_diagnostics["terminal_status"],
            "TERMINAL_FAILURE",
        )
        self.assertEqual(noncanonical_exception_diagnostics["attempt_count"], 1)

        mutating_calls = []

        def mutating_backend(identity: dict[str, object], attempt_request: dict[str, object]) -> dict[str, object]:
            mutating_calls.append((copy.deepcopy(identity), copy.deepcopy(attempt_request)))
            identity["prompt_id"] = "mutated"
            attempt_request["logical_id"] = "mutated"
            attempt_request["decode_config"] = {"do_sample": True}
            if len(mutating_calls) == 1:
                raise TechnicalGenerationError("synthetic mutation probe")
            return {"output_text": "stable retry", "diagnostics": {"fixture": True}}

        mutation_result = GenerationProducer(
            registry,
            mutating_backend,
            synthetic=True,
        ).produce(logical_id, request)
        validate_generation_record(mutation_result)
        self.assertEqual(mutating_calls[0], mutating_calls[1])
        self.assertEqual(request, {"logical_id": logical_id, "decode_config": DECODE_CONFIG})
        self.assertEqual(registry.require(logical_id), synthetic_identity())
        with self.assertRaises(IdentityError):
            producer.produce(logical_id, request)
        with tempfile.TemporaryDirectory() as directory:
            generation_receipt = AppendOnlyReceipt(
                Path(directory) / "generation-attempts.jsonl",
                synthetic=True,
            )
            generation_receipt.bind_execution_registry(
                registry_sha256=registry.manifest()["registry_sha256"],
                parent_self_sha256=HASH,
                lifecycle_event="FORMAL_CONFIRMATION_GENERATION_STARTED",
                lifecycle_tip_sha256=HASH,
            )
            receipt_producer = GenerationProducer(
                registry,
                lambda _identity, _request: {
                    "output_text": "once",
                    "diagnostics": {"fixture": True},
                },
                synthetic=True,
                execution_receipt=generation_receipt,
            )
            receipt_producer.produce(logical_id, request)
            recovered_producer = GenerationProducer(
                registry,
                lambda _identity, _request: {
                    "output_text": "must-not-run",
                    "diagnostics": {},
                },
                synthetic=True,
                execution_receipt=generation_receipt,
            )
            with self.assertRaises(IdentityError):
                recovered_producer.produce(logical_id, request)
            self.assertEqual(generation_receipt.verify()["entry_count"], 3)

    def test_attempt_reconciliation_materialized_records_and_full_dispositions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStore(root, synthetic=True)
            registry, dose_binding = build_plan()
            manifest = registry.manifest()
            lifecycle, _, lifecycle_documents = build_synthetic_lifecycle(
                store, manifest, dose_binding
            )
            lifecycle_entries = lifecycle.receipt._load()
            support_authorization = next(
                entry for entry in lifecycle_entries
                if entry["event"] == "FORMAL_SUPPORT_GENERATION_STARTED"
            )
            confirmation_authorization = lifecycle_entries[-1]
            support_parent = lifecycle_documents[
                "FORMAL_SUPPORT_GENERATION_STARTED"
            ]["self_sha256"]
            confirmation_parent = lifecycle_documents[
                "FORMAL_CONFIRMATION_GENERATION_STARTED"
            ]["self_sha256"]
            selected = next(
                item for item in registry.records() if item["identity"]["block"] == "P2_A_all"
            )
            logical_id = selected["logical_id"]
            identity = selected["identity"]
            call_dose_evidence = build_call_dose_evidence(
                identity=identity,
                dose_binding=dose_binding,
                generation_status="COMPLETED",
                pre_hook_l2=10.0,
                post_hook_l2=10.5,
                vector_alignment=0.95,
                cosine_drift=0.05,
            )
            support_receipt = AppendOnlyReceipt(root / "support-attempts.jsonl", synthetic=True)
            support_receipt.bind_execution_registry(
                registry_sha256=manifest["registry_sha256"],
                parent_self_sha256=support_parent,
                lifecycle_event="FORMAL_SUPPORT_GENERATION_STARTED",
                lifecycle_tip_sha256=support_authorization["entry_sha256"],
            )
            receipt = AppendOnlyReceipt(root / "confirmation-attempts.jsonl", synthetic=True)
            receipt.bind_execution_registry(
                registry_sha256=manifest["registry_sha256"],
                parent_self_sha256=confirmation_parent,
                lifecycle_event="FORMAL_CONFIRMATION_GENERATION_STARTED",
                lifecycle_tip_sha256=confirmation_authorization["entry_sha256"],
            )
            measurement_result = lifecycle.read_validated_document(
                "protocol/measurement_result_dose_manifest.json"
            )
            dose_context = lifecycle.authenticated_dose_context()
            with self.assertRaises(AttributeError):
                dose_context.measurement_result_self_sha256 = "0" * 64
            producer = GenerationProducer(
                registry,
                lambda _identity, _request: {
                    "output_text": "ok",
                    "diagnostics": {
                        "dose_evidence_sha256": canonical_sha256(call_dose_evidence),
                        "measurement_result_dose_manifest_self_sha256": (
                            measurement_result["self_sha256"]
                        ),
                    },
                },
                synthetic=True,
                execution_receipt=receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=root,
            )
            generation = validate_generation_record(producer.produce(
                logical_id, {"logical_id": logical_id, "decode_config": DECODE_CONFIG}
            ))
            judge = validate_judge_record(parse_judge_with_retry(
                logical_id,
                lambda _attempt, _request: '{"label":"safe","rationale":"ok"}',
                {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
                registry=registry,
                generation_record=generation,
                synthetic=True,
                execution_receipt=receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=root,
            ))
            raw_p2 = {
                "schema_version": "paper1-stage3-p2-response-record-v1",
                "protocol_version": "v3.5-rc2",
                "synthetic": True,
                "logical_id": logical_id,
                "identity_sha256": generation["identity_sha256"],
                "generation_record_sha256": generation["record_sha256"],
                "judge_record_sha256": canonical_sha256(judge),
                "cell": identity["block"],
                "prompt_id": identity["prompt_id"],
                "vector_id": identity["vector_id"],
                "pair_id": f"{identity['anchor']}|{identity['prompt_id']}|{identity['vector_id']}",
                "arm": "all-token",
                "anchor": identity["anchor"],
                "estimator": identity["estimator"],
                "scheduled_identity_match": True,
                "generation_completed": True,
                "judge_eligible": True,
                "judge_label_parsed": True,
                "identity_complete": True,
                "identity_collision": False,
                "dose_denominator_valid": True,
                "dose_geometry_finite": True,
                "post_dtype_alpha_finite": True,
                "dose_evidence": call_dose_evidence,
                "label": judge["label"],
                "terminal_status": "COMPLETED_PARSED",
            }
            validated_p2 = validate_p2_materialization(
                raw_p2,
                registry=registry,
                generation_record=generation,
                judge_record=judge,
                measurement_result_dose_manifest=measurement_result,
                dose_context=dose_context,
            )
            for tampered in (
                dict(raw_p2, prompt_id="wrong-prompt"),
                dict(raw_p2, pair_id="wrong-pair"),
                dict(raw_p2, generation_record_sha256="0" * 64),
                dict(raw_p2, label="unsafe"),
            ):
                with self.assertRaises(RecordSchemaError):
                    validate_p2_materialization(
                        tampered,
                        registry=registry,
                        generation_record=generation,
                        judge_record=judge,
                        measurement_result_dose_manifest=measurement_result,
                        dose_context=dose_context,
                    )
            forged_judge = dict(judge, identity_sha256="0" * 64)
            with self.assertRaises(RecordSchemaError):
                validate_p2_materialization(
                    raw_p2,
                    registry=registry,
                    generation_record=generation,
                    judge_record=forged_judge,
                    measurement_result_dose_manifest=measurement_result,
                    dose_context=dose_context,
                )
            dose_mutations = []
            wrong_mu_source = copy.deepcopy(raw_p2)
            wrong_mu_source["dose_evidence"]["mu_source_sha256"] = "0" * 64
            dose_mutations.append(wrong_mu_source)
            wrong_binding = copy.deepcopy(raw_p2)
            wrong_binding["dose_evidence"][
                "measurement_result_dose_binding_sha256"
            ] = "0" * 64
            dose_mutations.append(wrong_binding)
            wrong_c = copy.deepcopy(raw_p2)
            wrong_c_evidence = wrong_c["dose_evidence"]
            wrong_c_evidence["nominal_c"] = binary64(0.5)
            wrong_c_evidence["alpha_pre_dtype"] = binary64(2.0)
            wrong_c_evidence["alpha_post_dtype"] = binary64(2.0)
            wrong_c_evidence["relative_dose"] = binary64(2.0 / 10.0)
            dose_mutations.append(wrong_c)
            wrong_mu = copy.deepcopy(raw_p2)
            wrong_mu_evidence = wrong_mu["dose_evidence"]
            wrong_mu_evidence["mu_value"] = binary64(8.0)
            wrong_mu_evidence["alpha_pre_dtype"] = binary64(2.0)
            wrong_mu_evidence["alpha_post_dtype"] = binary64(2.0)
            wrong_mu_evidence["relative_dose"] = binary64(2.0 / 10.0)
            dose_mutations.append(wrong_mu)
            wrong_geometry = copy.deepcopy(raw_p2)
            wrong_geometry_evidence = wrong_geometry["dose_evidence"]
            wrong_geometry_evidence["pre_hook_l2"] = binary64(20.0)
            wrong_geometry_evidence["post_hook_l2"] = binary64(21.0)
            wrong_geometry_evidence["relative_dose"] = binary64(1.0 / 20.0)
            wrong_geometry_evidence["norm_ratio"] = binary64(21.0 / 20.0)
            dose_mutations.append(wrong_geometry)
            for tampered in dose_mutations:
                with self.assertRaises(RecordSchemaError):
                    validate_p2_materialization(
                        tampered,
                        registry=registry,
                        generation_record=generation,
                        judge_record=judge,
                        measurement_result_dose_manifest=measurement_result,
                        dose_context=dose_context,
                    )

            wrong_parent_manifest = copy.deepcopy(measurement_result)
            wrong_parent_manifest["parents"]["measurement_specification_freeze"] = "0" * 64
            rebound = wrong_parent_manifest["dose_binding"]
            rebound["parent_self_sha256"]["measurement_specification_freeze"] = "0" * 64
            rebound.pop("self_sha256")
            rebound["self_sha256"] = canonical_sha256(rebound)
            wrong_parent_manifest.pop("self_sha256")
            wrong_parent_manifest["self_sha256"] = canonical_sha256(wrong_parent_manifest)
            forged_evidence = copy.deepcopy(raw_p2["dose_evidence"])
            forged_evidence[
                "measurement_result_dose_binding_sha256"
            ] = rebound["self_sha256"]
            forged_generation = copy.deepcopy(generation)
            forged_generation["attempts"][-1]["diagnostics"].update({
                "measurement_result_dose_manifest_self_sha256": (
                    wrong_parent_manifest["self_sha256"]
                ),
                "dose_evidence_sha256": canonical_sha256(forged_evidence),
            })
            forged_generation["record_sha256"] = canonical_sha256({
                key: value for key, value in forged_generation.items()
                if key != "record_sha256"
            })
            rechained_judge = copy.deepcopy(judge)
            rechained_judge["generation_record_sha256"] = forged_generation[
                "record_sha256"
            ]
            rechained_p2 = dict(
                raw_p2,
                generation_record_sha256=forged_generation["record_sha256"],
                judge_record_sha256=canonical_sha256(rechained_judge),
                dose_evidence=forged_evidence,
            )
            with self.assertRaises(RecordSchemaError):
                validate_p2_materialization(
                    rechained_p2,
                    registry=registry,
                    generation_record=forged_generation,
                    judge_record=rechained_judge,
                    measurement_result_dose_manifest=wrong_parent_manifest,
                    dose_context=dose_context,
                )
            k1 = {
                "schema_version": "paper1-stage3-k1-reuse-record-v1",
                "protocol_version": "v3.5-rc2",
                "synthetic": True,
                "logical_id": logical_id,
                "source_p2_logical_id": logical_id,
                "source_p2_record_sha256": validated_p2["record_sha256"],
                "cell": raw_p2["cell"],
                "prompt_id": raw_p2["prompt_id"],
                "vector_id": raw_p2["vector_id"],
                "label": raw_p2["label"],
                "generation_calls_added": 0,
                "judge_calls_added": 0,
            }
            validate_k1_materialization(
                k1,
                registry=registry,
                source_p2_record=raw_p2,
                generation_record=generation,
                judge_record=judge,
                measurement_result_dose_manifest=measurement_result,
                dose_context=dose_context,
            )
            with self.assertRaises(RecordSchemaError):
                validate_k1_materialization(
                    dict(k1, source_p2_record_sha256="0" * 64),
                    registry=registry,
                    source_p2_record=raw_p2,
                    generation_record=generation,
                    judge_record=judge,
                    measurement_result_dose_manifest=measurement_result,
                    dose_context=dose_context,
                )
            support_dispositions = execution_dispositions(
                registry, [], [], support_parent, phase="support"
            )
            confirmation_dispositions = execution_dispositions(
                registry, [generation], [judge], confirmation_parent, phase="confirmation"
            )
            actual = reconcile_complete_execution(
                registry,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=root,
                support_receipt=support_receipt,
                support_generation_records=[],
                support_judge_records=[],
                support_dispositions=support_dispositions,
                confirmation_receipt=receipt,
                confirmation_generation_records=[generation],
                confirmation_judge_records=[judge],
                confirmation_dispositions=confirmation_dispositions,
            )
            self.assertEqual(actual["terminal_dispositions"], 5_580)
            self.assertEqual(actual["executed_dispositions"], 1)
            self.assertEqual(actual["unattempted_dispositions"], 5_579)
            self.assertEqual(actual["support"]["terminal_dispositions"], 900)
            self.assertEqual(actual["confirmation"]["terminal_dispositions"], 4_680)

            tampered_generation = dict(generation, identity_sha256="0" * 64)
            with self.assertRaises((PipelineError, RecordSchemaError, IdentityError)):
                reconcile_phase_execution_attempts(
                    registry, receipt, [tampered_generation], [judge],
                    confirmation_dispositions, phase="confirmation",
                    lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )
            with self.assertRaises(PipelineError):
                reconcile_phase_execution_attempts(
                    registry, receipt, [generation], [judge], confirmation_dispositions[:-1],
                    phase="confirmation", lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )
            forged_dispositions = copy.deepcopy(confirmation_dispositions)
            unexecuted = next(
                item for item in forged_dispositions
                if item["disposition"] == "SYNTHETIC_NOT_EXECUTED"
            )
            unexecuted["parent_self_sha256"] = "0" * 64
            with self.assertRaises(PipelineError):
                reconcile_phase_execution_attempts(
                    registry, receipt, [generation], [judge], forged_dispositions,
                    phase="confirmation", lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )

            cross_phase = copy.deepcopy(confirmation_dispositions)
            cross_phase[0] = copy.deepcopy(support_dispositions[0])
            with self.assertRaises(IdentityError):
                reconcile_phase_execution_attempts(
                    registry, receipt, [generation], [judge], cross_phase,
                    phase="confirmation", lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )
            duplicate = copy.deepcopy(confirmation_dispositions)
            duplicate[-1] = copy.deepcopy(duplicate[0])
            with self.assertRaises(IdentityError):
                reconcile_phase_execution_attempts(
                    registry, receipt, [generation], [judge], duplicate,
                    phase="confirmation", lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )

            wrong_receipt = AppendOnlyReceipt(root / "wrong-phase-attempts.jsonl", synthetic=True)
            wrong_receipt.bind_execution_registry(
                registry_sha256=manifest["registry_sha256"],
                parent_self_sha256=support_parent,
                lifecycle_event="FORMAL_SUPPORT_GENERATION_STARTED",
                lifecycle_tip_sha256=confirmation_authorization["entry_sha256"],
            )
            wrong_phase_producer = GenerationProducer(
                registry,
                lambda _identity, _request: {"output_text": "must-not-run", "diagnostics": {}},
                synthetic=True,
                execution_receipt=wrong_receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=root,
            )
            with self.assertRaises(PipelineError):
                wrong_phase_producer.produce(
                    logical_id, {"logical_id": logical_id, "decode_config": DECODE_CONFIG}
                )
            with self.assertRaises(PipelineError):
                reconcile_phase_execution_attempts(
                    registry, wrong_receipt, [], [], support_dispositions,
                    phase="support", lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )

    def test_executed_support_success_and_terminal_failures_freeze_event8(self) -> None:
        captured: dict[str, object] = {}

        def execute_support(
            registry: LogicalIdentityRegistry,
            lifecycle: FreezeLifecycle,
            receipt: AppendOnlyReceipt,
            measurement_result: object,
        ) -> dict[str, object]:
            assert isinstance(measurement_result, dict)
            dose_binding = measurement_result["dose_binding"]
            selected = [
                item for item in registry.records()
                if item["identity"]["block"] == "support"
            ][:4]
            completed_id, technical_id, deterministic_id, indeterminate_id = [
                item["logical_id"] for item in selected
            ]
            evidence_by_id: dict[str, dict[str, object]] = {}

            def evidence_for(identity: dict[str, object], status: str) -> dict[str, object]:
                return build_call_dose_evidence(
                    identity=identity,
                    dose_binding=dose_binding,
                    generation_status=status,
                    pre_hook_l2=10.0,
                    post_hook_l2=10.5,
                    vector_alignment=0.95,
                    cosine_drift=0.05,
                )

            def backend(identity: dict[str, object], request: dict[str, object]) -> dict[str, object]:
                logical_id = request["logical_id"]
                if logical_id == technical_id:
                    evidence = evidence_for(identity, "TERMINAL_TECHNICAL_FAILURE")
                    evidence_by_id[logical_id] = evidence
                    raise TechnicalGenerationError(
                        "synthetic support technical failure",
                        diagnostics={"dose_evidence_sha256": canonical_sha256(evidence)},
                    )
                if logical_id == deterministic_id:
                    evidence = evidence_for(identity, "TERMINAL_FAILURE")
                    evidence_by_id[logical_id] = evidence
                    raise TerminalGenerationError(
                        "synthetic support deterministic failure",
                        diagnostics={"dose_evidence_sha256": canonical_sha256(evidence)},
                    )
                if logical_id == indeterminate_id:
                    evidence = evidence_for(identity, "TERMINAL_INDETERMINATE_FAILURE")
                    evidence_by_id[logical_id] = evidence
                    failure = RuntimeError("synthetic support indeterminate failure")
                    failure.diagnostics = {  # type: ignore[attr-defined]
                        "dose_evidence_sha256": canonical_sha256(evidence)
                    }
                    raise failure
                evidence = evidence_for(identity, "COMPLETED")
                evidence_by_id[logical_id] = evidence
                return {
                    "output_text": "synthetic support output",
                    "diagnostics": {"dose_evidence_sha256": canonical_sha256(evidence)},
                }

            producer = GenerationProducer(
                registry,
                backend,
                synthetic=True,
                execution_receipt=receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=lifecycle.artifact_root,
            )
            generation_records = [
                validate_generation_record(producer.produce(
                    item["logical_id"],
                    {"logical_id": item["logical_id"], "decode_config": DECODE_CONFIG},
                ))
                for item in selected
            ]
            generation_by_id = {
                record["logical_id"]: record for record in generation_records
            }
            judge = validate_judge_record(parse_judge_with_retry(
                completed_id,
                lambda _attempt, _request: '{"label":"safe","rationale":"synthetic"}',
                {"logical_id": completed_id, "judge_config": JUDGE_CONFIG},
                registry=registry,
                generation_record=generation_by_id[completed_id],
                synthetic=True,
                execution_receipt=receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=lifecycle.artifact_root,
            ))
            judge_records = [judge]
            response_records = []
            for item in registry.records():
                identity = item["identity"]
                if identity["block"] != "support":
                    continue
                logical_id = item["logical_id"]
                generation = generation_by_id.get(logical_id)
                response = {
                    "logical_id": logical_id,
                    "identity_sha256": canonical_sha256(identity),
                    "synthetic": True,
                    "anchor": identity["anchor"],
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
                }
                if generation is not None:
                    dose_valid = True
                    evidence = evidence_by_id.get(logical_id)
                    if evidence is None:
                        raise AssertionError("executed support path lost its call-dose evidence")
                    response.update({
                        "generation_completed": generation["generation_completed"],
                        "judge_eligible": logical_id == completed_id,
                        "judge_label_parsed": logical_id == completed_id,
                        "dose_denominator_valid": dose_valid,
                        "dose_geometry_finite": dose_valid,
                        "post_dtype_alpha_finite": dose_valid,
                        "dose_evidence": evidence,
                        "generation_record_sha256": generation["record_sha256"],
                        "judge_record_sha256": (
                            canonical_sha256(judge) if logical_id == completed_id else None
                        ),
                        "label": "safe" if logical_id == completed_id else None,
                        "terminal_status": (
                            "COMPLETED_PARSED" if logical_id == completed_id
                            else "TERMINAL_GENERATION_FAILURE"
                        ),
                        "retained": logical_id == completed_id,
                    })
                response_records.append(response)
            captured.update({
                "generation_records": generation_records,
                "response_records": response_records,
                "deterministic_id": deterministic_id,
            })
            return {
                "generation_records": generation_records,
                "judge_records": judge_records,
                "response_records": response_records,
            }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry, dose_binding = build_plan()
            lifecycle, summary, _ = build_synthetic_lifecycle(
                ArtifactStore(root, synthetic=True),
                registry.manifest(),
                dose_binding,
                support_execution_callback=execute_support,
            )
            self.assertEqual(summary["entry_count"], 10)
            support_manifest = lifecycle.read_validated_document(
                "protocol/support_execution_manifest.json"
            )
            self.assertEqual(support_manifest["actual_calls"], {
                "generation_first_pass_calls": 4,
                "generation_technical_retries": 1,
                "generation_calls": 5,
                "judge_first_pass_calls": 1,
                "judge_parse_retries": 0,
                "judge_calls": 1,
            })
            generation_records = captured["generation_records"]
            assert isinstance(generation_records, list)
            for generation in generation_records:
                for attempt in generation["attempts"]:
                    self.assertEqual(
                        attempt["diagnostics"][
                            "measurement_result_dose_manifest_self_sha256"
                        ],
                        lifecycle.read_validated_document(
                            "protocol/measurement_result_dose_manifest.json"
                        )["self_sha256"],
                    )
            deterministic_id = captured["deterministic_id"]
            deterministic_generation = next(
                record for record in generation_records
                if record["logical_id"] == deterministic_id
            )
            deterministic_response = next(
                record for record in captured["response_records"]
                if record["logical_id"] == deterministic_id
            )
            measurement_result = lifecycle.read_validated_document(
                "protocol/measurement_result_dose_manifest.json"
            )
            dose_context = lifecycle.authenticated_dose_context()
            validate_support_response_materialization(
                deterministic_response,
                registry=registry,
                generation_record=deterministic_generation,
                judge_record=None,
                measurement_result_dose_manifest=measurement_result,
                dose_context=dose_context,
            )
            for replacement in (None, "0" * 64):
                tampered_generation = copy.deepcopy(deterministic_generation)
                diagnostics = tampered_generation["attempts"][-1]["diagnostics"]
                if replacement is None:
                    diagnostics.pop("measurement_result_dose_manifest_self_sha256")
                else:
                    diagnostics["measurement_result_dose_manifest_self_sha256"] = replacement
                tampered_generation["record_sha256"] = canonical_sha256({
                    key: value for key, value in tampered_generation.items()
                    if key != "record_sha256"
                })
                tampered_response = dict(
                    deterministic_response,
                    generation_record_sha256=tampered_generation["record_sha256"],
                )
                with self.assertRaises(RecordSchemaError):
                    validate_support_response_materialization(
                        tampered_response,
                        registry=registry,
                        generation_record=tampered_generation,
                        judge_record=None,
                        measurement_result_dose_manifest=measurement_result,
                        dose_context=dose_context,
                    )

    def test_retained_and_support_status_precedence(self) -> None:
        row = {field: True for field in (
            "scheduled_identity_match", "generation_completed", "judge_eligible",
            "judge_label_parsed", "identity_complete", "dose_denominator_valid",
            "dose_geometry_finite", "post_dtype_alpha_finite"
        )}
        row["identity_collision"] = False
        self.assertTrue(retained_identity(row))
        base = {
            "anchor": "A", "scheduled_identities": 300, "unique_scheduled_identities": 300,
            "retained_identities": 284, "identity_collisions": 0, "unexpected_identities": 0,
            "missing_scheduled_identities": 0, "denominator_failures": 0,
            "dose_geometry_failures": 0, "post_dtype_alpha_failures": 0,
        }
        self.assertEqual(classify_support(base)["support_status"], "SUPPORT_LIMITED")
        collision = dict(base, retained_identities=299, unique_scheduled_identities=299, identity_collisions=1)
        self.assertEqual(classify_support(collision)["support_status"], "NON_ESTIMABLE_IDENTITY")
        self.assertEqual(status_with_analysis_precedence("SUPPORTED", False), "NON_ESTIMABLE_ANALYSIS")
        self.assertEqual(
            status_with_analysis_precedence("NON_ESTIMABLE_IDENTITY", False),
            "NON_ESTIMABLE_IDENTITY",
        )
        expected_blocked = {
            "A": ({"P2_A_all", "P2_A_content"}, 2_000),
            "T": ({"P2_T_all", "P2_T_content", "benign_T"}, 2_600),
            "H": (set(), 0),
        }
        for anchor, (blocks, expected_count) in expected_blocked.items():
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                store = ArtifactStore(root, synthetic=True)
                registry, dose_binding = build_plan()
                lifecycle, _, lifecycle_documents = build_synthetic_lifecycle(
                    store,
                    registry.manifest(),
                    dose_binding,
                    support_identity_failure_anchor=anchor,
                )
                confirmation = json.loads(
                    (root / "protocol/behavior_confirmation_freeze.json").read_text(
                        encoding="utf-8"
                    )
                )
                blocked = [
                    row for row in confirmation["confirmation_rows"]
                    if row["execution_disposition"] == "UNATTEMPTED_DUE_INTEGRITY_BLOCK"
                ]
                self.assertEqual(len(blocked), expected_count)
                self.assertEqual({row["block"] for row in blocked}, blocks)
                self.assertTrue(all(
                    row["block"] not in {"harmful_clean", "benign_clean"}
                    for row in blocked
                ))
                authorization = lifecycle.receipt._load()[-1]
                receipt = AppendOnlyReceipt(root / f"confirmation-gate-{anchor}.jsonl", synthetic=True)
                receipt.bind_execution_registry(
                    registry_sha256=registry.manifest()["registry_sha256"],
                    parent_self_sha256=lifecycle_documents[
                        "FORMAL_CONFIRMATION_GENERATION_STARTED"
                    ]["self_sha256"],
                    lifecycle_event="FORMAL_CONFIRMATION_GENERATION_STARTED",
                    lifecycle_tip_sha256=authorization["entry_sha256"],
                )
                backend_calls = 0

                def backend(_identity: object, _request: object) -> dict[str, object]:
                    nonlocal backend_calls
                    backend_calls += 1
                    return {"output_text": "authorized", "diagnostics": {}}

                producer = GenerationProducer(
                    registry,
                    backend,
                    synthetic=True,
                    execution_receipt=receipt,
                    lifecycle_receipt=lifecycle.receipt,
                    lifecycle_artifact_root=root,
                )
                if blocked:
                    blocked_id = blocked[0]["logical_id"]
                    with self.assertRaises(PipelineError):
                        producer.produce(
                            blocked_id,
                            {"logical_id": blocked_id, "decode_config": DECODE_CONFIG},
                        )
                    self.assertEqual(backend_calls, 0)
                    self.assertEqual(receipt.verify()["entry_count"], 1)
                authorized_row = next(
                    row for row in confirmation["confirmation_rows"]
                    if row["execution_disposition"] == "AUTHORIZED"
                    and (
                        row["block"] == "P2_A_all" if anchor == "H"
                        else row["block"] == "harmful_clean"
                    )
                )
                authorized_id = authorized_row["logical_id"]
                producer.produce(
                    authorized_id,
                    {"logical_id": authorized_id, "decode_config": DECODE_CONFIG},
                )
                self.assertEqual(backend_calls, 1)

                if anchor == "A":
                    forged_receipt = AppendOnlyReceipt(
                        root / "blocked-reconciliation.jsonl", synthetic=True
                    )
                    forged_receipt.bind_execution_registry(
                        registry_sha256=registry.manifest()["registry_sha256"],
                        parent_self_sha256=lifecycle_documents[
                            "FORMAL_CONFIRMATION_GENERATION_STARTED"
                        ]["self_sha256"],
                        lifecycle_event="FORMAL_CONFIRMATION_GENERATION_STARTED",
                        lifecycle_tip_sha256=authorization["entry_sha256"],
                    )

                    def fail_backend(_identity: object, _request: object) -> dict[str, object]:
                        raise TechnicalGenerationError("synthetic blocked-record forgery")

                    forged_generation = GenerationProducer(
                        registry,
                        fail_backend,
                        synthetic=True,
                        execution_receipt=forged_receipt,
                    ).produce(
                        blocked[0]["logical_id"],
                        {
                            "logical_id": blocked[0]["logical_id"],
                            "decode_config": DECODE_CONFIG,
                        },
                    )
                    forged_dispositions = execution_dispositions(
                        registry,
                        [forged_generation],
                        [],
                        lifecycle_documents[
                            "FORMAL_CONFIRMATION_GENERATION_STARTED"
                        ]["self_sha256"],
                        phase="confirmation",
                    )
                    with self.assertRaises(PipelineError):
                        reconcile_phase_execution_attempts(
                            registry,
                            forged_receipt,
                            [forged_generation],
                            [],
                            forged_dispositions,
                            phase="confirmation",
                            lifecycle_receipt=lifecycle.receipt,
                            lifecycle_artifact_root=root,
                        )

    def test_record_schemas_and_missingness(self) -> None:
        p1 = {
            "schema_version": "paper1-stage3-p1-measurement-record-v1", "protocol_version": "v3.5-rc2",
            "synthetic": True, "logical_id": "p1", "prompt_id": "p", "stratum": "harmful",
            "identity_complete": True, "render_complete": True, "valid_mask_complete": True,
            "forward_complete": True, "identity_collision": False, "valid_token_count": 2,
            "content_token_count": 1, "unresolved_valid_token_count": 1,
            "required_norms_finite": True, "v_sum": 2.0, "c_sum": 1.0,
            "terminal_status": "EXCLUDED_UNRESOLVED", "exclusion_reason": "EXCLUDED_UNRESOLVED",
        }
        self.assertFalse(validate_p1_record(p1)["complete_case"])
        nonfinite = dict(p1, unresolved_valid_token_count=0, required_norms_finite=False,
                         v_sum=None, c_sum=None, terminal_status="EXCLUDED_NONFINITE",
                         exclusion_reason="EXCLUDED_NONFINITE")
        self.assertFalse(validate_p1_record(nonfinite)["complete_case"])
        with self.assertRaises(RecordSchemaError):
            validate_p1_record(dict(nonfinite, terminal_status="COMPLETE_CASE"))
        complete = dict(
            p1,
            unresolved_valid_token_count=0,
            terminal_status="COMPLETE_CASE",
            exclusion_reason=None,
        )
        self.assertTrue(validate_p1_record(complete)["complete_case"])
        for field in ("v_sum", "c_sum"):
            negative = dict(complete, **{field: -1.0})
            with self.assertRaises(RecordSchemaError):
                validate_p1_record(negative)
        with self.assertRaises(RecordSchemaError):
            validate_p1_record(
                dict(complete, terminal_status="COMPLETE_CASE", exclusion_reason="COMPLETE_CASE")
            )

    def test_p2_k1_benign_schema_and_zero_cost_reuse(self) -> None:
        p2 = {
            "schema_version": "paper1-stage3-p2-response-record-v1", "protocol_version": "v3.5-rc2",
            "synthetic": True, "logical_id": "id", "identity_sha256": HASH,
            "generation_record_sha256": HASH, "judge_record_sha256": HASH,
            "cell": "P2_A_all", "prompt_id": "p",
            "vector_id": "v", "pair_id": "pair", "arm": "all-token", "anchor": "A",
            "estimator": "mu_all_tw", "scheduled_identity_match": True,
            "generation_completed": True, "judge_eligible": True,
            "judge_label_parsed": True, "identity_complete": True, "identity_collision": False,
            "dose_denominator_valid": True, "dose_geometry_finite": True,
            "post_dtype_alpha_finite": True, "dose_evidence": synthetic_dose_evidence(),
            "label": "safe", "terminal_status": "COMPLETED_PARSED",
        }
        validated = validate_p2_record(p2)
        self.assertTrue(validated["retained"])
        invalid_evidence = synthetic_dose_evidence()
        invalid_evidence.update({"status": "INVALID", "failure_code": "NONFINITE_GEOMETRY"})
        for field in (
            "nominal_c", "mu_value", "alpha_pre_dtype", "alpha_post_dtype",
            "pre_hook_l2", "post_hook_l2", "relative_dose", "norm_ratio",
            "vector_alignment", "cosine_drift",
        ):
            invalid_evidence[field] = None
        invalid_p2 = dict(
            p2,
            dose_denominator_valid=False,
            dose_geometry_finite=False,
            post_dtype_alpha_finite=False,
            dose_evidence=invalid_evidence,
            terminal_status="NON_ESTIMABLE_DOSE",
        )
        self.assertFalse(validate_p2_record(invalid_p2)["retained"])
        mixed_invalid = copy.deepcopy(invalid_p2)
        mixed_invalid["dose_evidence"]["nominal_c"] = binary64(0.25)
        with self.assertRaises(RecordSchemaError):
            validate_p2_record(mixed_invalid)
        unexpected = dict(p2, scheduled_identity_match=False, terminal_status="NON_ESTIMABLE_IDENTITY")
        self.assertFalse(validate_p2_record(unexpected)["retained"])
        impossible = dict(
            p2,
            generation_completed=False,
            judge_eligible=False,
            terminal_status="TERMINAL_GENERATION_FAILURE",
        )
        with self.assertRaises(RecordSchemaError):
            validate_p2_record(impossible)
        with self.assertRaises(RecordSchemaError):
            validate_p2_record(dict(
                p2,
                judge_label_parsed=False,
                label="arbitrary",
                terminal_status="TERMINAL_JUDGE_FAILURE",
            ))
        k1 = {
            "schema_version": "paper1-stage3-k1-reuse-record-v1", "protocol_version": "v3.5-rc2",
            "synthetic": True, "logical_id": "id", "source_p2_logical_id": "id",
            "source_p2_record_sha256": "a" * 64, "cell": "P2_A_all", "prompt_id": "p",
            "vector_id": "v", "label": "safe", "generation_calls_added": 0, "judge_calls_added": 0,
        }
        validate_k1_record(k1)
        benign = {
            "schema_version": "paper1-stage3-benign-response-record-v1", "protocol_version": "v3.5-rc2",
            "synthetic": True, "logical_id": "b", "identity_sha256": HASH,
            "generation_record_sha256": HASH, "judge_record_sha256": HASH,
            "cell": "benign_clean", "prompt_id": "bp",
            "vector_id": None, "anchor": "clean", "estimator": "clean",
            "scheduled_identity_match": True, "generation_completed": True,
            "judge_eligible": True, "judge_label_parsed": True,
            "identity_complete": True, "identity_collision": False, "dose_denominator_valid": True,
            "dose_geometry_finite": True, "post_dtype_alpha_finite": True,
            "dose_evidence": None, "label": "helpful", "terminal_status": "COMPLETED_PARSED",
        }
        self.assertTrue(validate_benign_record(benign)["retained"])
        invalid_benign = dict(
            benign,
            cell="benign_T",
            vector_id="v",
            anchor="T",
            estimator="mu_all_tw",
            dose_denominator_valid=False,
            dose_geometry_finite=False,
            post_dtype_alpha_finite=False,
            dose_evidence=copy.deepcopy(invalid_evidence),
            terminal_status="NON_ESTIMABLE_DOSE",
        )
        self.assertFalse(validate_benign_record(invalid_benign)["retained"])
        for schema_name in (
            "p2_response_record.schema.json", "benign_response_record.schema.json"
        ):
            schema = json.loads(
                (ROOT / "stage3_pipeline/schemas" / schema_name).read_text(encoding="utf-8")
            )
            conditional = schema["$defs"]["dose_evidence"]["allOf"][0]
            for field in (
                "nominal_c", "mu_value", "alpha_pre_dtype", "alpha_post_dtype",
                "pre_hook_l2", "post_hook_l2", "relative_dose", "norm_ratio",
                "vector_alignment", "cosine_drift",
            ):
                self.assertEqual(
                    conditional["else"]["properties"][field], {"type": "null"}
                )
                self.assertEqual(
                    conditional["then"]["properties"][field],
                    {"$ref": "#/$defs/binary64"},
                )
        unexpected_benign = dict(
            benign,
            scheduled_identity_match=False,
            terminal_status="NON_ESTIMABLE_IDENTITY",
        )
        self.assertFalse(validate_benign_record(unexpected_benign)["retained"])
        with self.assertRaises(RecordSchemaError):
            validate_benign_record(dict(
                benign,
                judge_label_parsed=False,
                label="arbitrary",
                terminal_status="TERMINAL_JUDGE_FAILURE",
            ))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            benign_registry, benign_dose_binding = build_plan()
            lifecycle, _, lifecycle_documents = build_synthetic_lifecycle(
                ArtifactStore(root, synthetic=True),
                benign_registry.manifest(),
                benign_dose_binding,
            )
            selected = next(
                item for item in benign_registry.records()
                if item["identity"]["block"] == "benign_clean"
            )
            benign_id = selected["logical_id"]
            benign_identity = selected["identity"]
            authorization = lifecycle.receipt._load()[-1]
            receipt = AppendOnlyReceipt(root / "benign-attempts.jsonl", synthetic=True)
            receipt.bind_execution_registry(
                registry_sha256=benign_registry.manifest()["registry_sha256"],
                parent_self_sha256=lifecycle_documents[
                    "FORMAL_CONFIRMATION_GENERATION_STARTED"
                ]["self_sha256"],
                lifecycle_event="FORMAL_CONFIRMATION_GENERATION_STARTED",
                lifecycle_tip_sha256=authorization["entry_sha256"],
            )
            benign_measurement_result = lifecycle.read_validated_document(
                "protocol/measurement_result_dose_manifest.json"
            )
            benign_dose_context = lifecycle.authenticated_dose_context()
            benign_generation = GenerationProducer(
                benign_registry,
                lambda _identity, _request: {"output_text": "benign", "diagnostics": {}},
                synthetic=True,
                execution_receipt=receipt,
                lifecycle_receipt=lifecycle.receipt,
                lifecycle_artifact_root=root,
            ).produce(
                benign_id, {"logical_id": benign_id, "decode_config": DECODE_CONFIG}
            )
            benign_judge = {
                "schema_version": "paper1-stage3-judge-record-v1",
                "protocol_version": "v3.5-rc2",
                "logical_id": benign_id,
                "identity_sha256": benign_generation["identity_sha256"],
                "generation_record_sha256": benign_generation["record_sha256"],
                "domain": "benign",
                "judge_freeze_self_sha256": HASH,
                "rubric_sha256": HASH,
                "request_sha256": HASH,
                "synthetic": True,
                "formal_experiment": False,
                "attempts": [{
                    "attempt_index": 1,
                    "status": "PARSED",
                    "failure_code": None,
                    "payload_sha256": HASH,
                    "request_sha256": HASH,
                }],
                "judge_label_parsed": True,
                "terminal_status": "PARSED",
                "label": "helpful",
                "rationale": "synthetic",
            }
            materialized_benign = dict(
                benign,
                logical_id=benign_id,
                identity_sha256=benign_generation["identity_sha256"],
                generation_record_sha256=benign_generation["record_sha256"],
                judge_record_sha256=canonical_sha256(benign_judge),
                prompt_id=benign_identity["prompt_id"],
            )
            validate_benign_materialization(
                materialized_benign,
                registry=benign_registry,
                generation_record=benign_generation,
                judge_record=benign_judge,
                measurement_result_dose_manifest=benign_measurement_result,
                dose_context=benign_dose_context,
            )
            for tampered in (
                dict(materialized_benign, prompt_id="wrong"),
                dict(materialized_benign, label="unsafe"),
            ):
                with self.assertRaises(RecordSchemaError):
                    validate_benign_materialization(
                        tampered,
                        registry=benign_registry,
                        generation_record=benign_generation,
                        judge_record=benign_judge,
                        measurement_result_dose_manifest=benign_measurement_result,
                        dose_context=benign_dose_context,
                    )

    def test_budget_artifact_and_reference_bindings(self) -> None:
        self.assertEqual(assert_budget(BLOCK_BUDGET)["logical_generation"], 5580)
        with self.assertRaises(PipelineError):
            assert_budget(dict(BLOCK_BUDGET, support=901))
        actual = assert_actual_call_budget(
            generation_unattempted=80,
            generation_technical_retries=50,
            prejudge_terminal=30,
            judge_parse_retries=20,
        )
        self.assertEqual(actual["generation_calls"], 5_550)
        self.assertEqual(actual["judge_calls"], 5_490)
        with self.assertRaises(PipelineError):
            assert_actual_call_budget(
                generation_unattempted=0,
                generation_technical_retries=5_581,
                prejudge_terminal=0,
                judge_parse_retries=0,
            )
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory), synthetic=True)
            stored = store.write_json_once("manifest.json", {"kind": "fixture"})
            self.assertFalse(stored["formal_experiment"])
            with self.assertRaises(PipelineError):
                store.write_json_once("manifest.json", {"kind": "fixture"})
            with self.assertRaises(PipelineError):
                store.write_json_once(
                    "wrong-mode.json",
                    {"kind": "fixture", "synthetic": False, "formal_experiment": True},
                )
        report = ReferenceAdapter(ROOT).binding_report()
        self.assertFalse(report["alternate_algorithm"])
        self.assertEqual(len(report["loaded"]), 4)

    def test_bound_statistical_quota_two_phase_and_retained_goldens(self) -> None:
        commands = (
            ([sys.executable, "-B", "writing/stage3 design/v3_5_rc2_statistics/verify_golden.py"],
             "STATISTICAL_GOLDEN_PASS"),
            ([sys.executable, "-B", "scripts/stage3_design/v3_5_rc2/human_quota.py",
              "--verify-golden", "writing/stage3 design/v3_5_rc2_closure/C/human_quota_golden.json"],
             "PASS"),
            ([sys.executable, "-B", "scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py"],
             "AMENDMENT_STATIC_VERIFICATION_PASS"),
        )
        for command, marker in commands:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            combined = completed.stdout + completed.stderr
            self.assertEqual(completed.returncode, 0, combined)
            self.assertIn(marker, combined)
        quota_records = [
            {
                "response_id": f"e0-{index:04d}",
                "block": "harmful_clean",
                "predicted_class": ("broken", "unsafe", "refusal", "safe")[index % 4],
                "matched": False,
            }
            for index in range(720)
        ]
        trace = ReferenceAdapter(ROOT).fixed720(quota_records)
        self.assertEqual(trace["selected_n"], 720)
        self.assertEqual(trace["fixed720_status"], "complete")


def main() -> int:
    require_project_local_temp(ROOT)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(E0Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    print(json.dumps({
        "marker": "STAGE3_E0_SYNTHETIC_PASS",
        "tests_run": result.testsRun,
        "synthetic_only": True,
        "formal_experiment_run": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
