"""Strict production record schemas and validators for Stage 3 ledgers."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .core import FORMAL_LOGICAL_GENERATION, LogicalIdentityRegistry, PipelineError, canonical_sha256
from .dose import validate_dose_binding


class RecordSchemaError(PipelineError):
    """A record did not match its registered production schema."""


_DOSE_CONTEXT_SEAL = object()


class AuthenticatedDoseContext:
    """Immutable lifecycle-authenticated context for dose materialization."""

    __slots__ = (
        "synthetic", "registry_sha256", "measurement_result_self_sha256",
        "parent_self_sha256", "authorized_event", "authorized_tip_sha256",
    )

    def __init__(
        self,
        *,
        synthetic: bool,
        registry_sha256: str,
        measurement_result_self_sha256: str,
        parent_self_sha256: Mapping[str, str],
        authorized_event: str,
        authorized_tip_sha256: str,
        _seal: object,
    ) -> None:
        if _seal is not _DOSE_CONTEXT_SEAL:
            raise RecordSchemaError("dose context may only be issued by lifecycle verification")
        object.__setattr__(self, "synthetic", synthetic)
        object.__setattr__(self, "registry_sha256", registry_sha256)
        object.__setattr__(
            self, "measurement_result_self_sha256", measurement_result_self_sha256
        )
        object.__setattr__(
            self, "parent_self_sha256", tuple(sorted(parent_self_sha256.items()))
        )
        object.__setattr__(self, "authorized_event", authorized_event)
        object.__setattr__(self, "authorized_tip_sha256", authorized_tip_sha256)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("authenticated dose context is immutable")


def _issue_authenticated_dose_context(
    *,
    synthetic: bool,
    registry_sha256: str,
    measurement_result_self_sha256: str,
    parent_self_sha256: Mapping[str, str],
    authorized_event: str,
    authorized_tip_sha256: str,
) -> AuthenticatedDoseContext:
    """Private factory used after FreezeLifecycle validates its prefix."""
    return AuthenticatedDoseContext(
        synthetic=synthetic,
        registry_sha256=registry_sha256,
        measurement_result_self_sha256=measurement_result_self_sha256,
        parent_self_sha256=parent_self_sha256,
        authorized_event=authorized_event,
        authorized_tip_sha256=authorized_tip_sha256,
        _seal=_DOSE_CONTEXT_SEAL,
    )


def _exact_keys(record: Mapping[str, Any], required: set[str], name: str) -> None:
    actual = set(record)
    if actual != required:
        raise RecordSchemaError(
            f"{name} keys differ: missing={sorted(required-actual)}, extra={sorted(actual-required)}"
        )


def _bool(record: Mapping[str, Any], field: str) -> bool:
    value = record[field]
    if not isinstance(value, bool):
        raise RecordSchemaError(f"{field} must be boolean")
    return value


def _text(record: Mapping[str, Any], field: str, *, nullable: bool = False) -> str | None:
    value = record[field]
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RecordSchemaError(f"{field} must be a nonempty string")
    return value


def _count(record: Mapping[str, Any], field: str) -> int:
    value = record[field]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RecordSchemaError(f"{field} must be a nonnegative integer")
    return value


def _finite(record: Mapping[str, Any], field: str) -> float:
    value = record[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise RecordSchemaError(f"{field} must be finite")
    return float(value)


def _finite_or_none(record: Mapping[str, Any], field: str) -> float | None:
    if record[field] is None:
        return None
    return _finite(record, field)


def _sha256_value(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise RecordSchemaError(f"{field} must be lowercase SHA256")
    return value


DOSE_EVIDENCE_KEYS = {
    "status",
    "failure_code",
    "nominal_c",
    "mu_estimator",
    "mu_value",
    "mu_source_sha256",
    "alpha_pre_dtype",
    "alpha_post_dtype",
    "pre_hook_l2",
    "post_hook_l2",
    "relative_dose",
    "norm_ratio",
    "vector_alignment",
    "cosine_drift",
    "measurement_result_dose_binding_sha256",
    "generation_status",
    "phase",
    "use_cache",
}
DOSE_NUMERIC_FIELDS = (
    "nominal_c",
    "mu_value",
    "alpha_pre_dtype",
    "alpha_post_dtype",
    "pre_hook_l2",
    "post_hook_l2",
    "relative_dose",
    "norm_ratio",
    "vector_alignment",
    "cosine_drift",
)


def _binary64_evidence(value: Any, field: str, *, nullable: bool) -> float | None:
    if nullable and value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"value", "binary64_hex"}:
        raise RecordSchemaError(f"{field} must be an exact binary64 object")
    number = value["value"]
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        raise RecordSchemaError(f"{field}.value must be numeric")
    converted = float(number)
    if not math.isfinite(converted) or value["binary64_hex"] != converted.hex():
        raise RecordSchemaError(f"{field} is nonfinite or has a binary64 mismatch")
    return converted


def _validate_dose_evidence(
    evidence: Any,
    *,
    estimator: str,
    generation_completed: bool,
    dose_valid: bool,
) -> dict[str, Any]:
    if not isinstance(evidence, Mapping) or set(evidence) != DOSE_EVIDENCE_KEYS:
        raise RecordSchemaError("steered response requires exact dose_evidence fields")
    status = evidence["status"]
    failure_code = evidence["failure_code"]
    if dose_valid:
        if status != "VALIDATED" or failure_code is not None:
            raise RecordSchemaError("valid dose flags require VALIDATED evidence without failure")
    elif status != "INVALID" or not isinstance(failure_code, str) or not failure_code:
        raise RecordSchemaError("invalid dose flags require one explicit dose failure code")
    if evidence["mu_estimator"] != estimator:
        raise RecordSchemaError("dose evidence estimator differs from response identity")
    _sha256_value(evidence["mu_source_sha256"], "dose_evidence.mu_source_sha256")
    _sha256_value(
        evidence["measurement_result_dose_binding_sha256"],
        "dose_evidence.measurement_result_dose_binding_sha256",
    )
    if evidence["phase"] != "decode-only" or evidence["use_cache"] is not True:
        raise RecordSchemaError("dose evidence phase/cache differs from frozen generation")
    if generation_completed:
        if evidence["generation_status"] != "COMPLETED":
            raise RecordSchemaError("completed response dose evidence has wrong generation status")
    elif evidence["generation_status"] == "COMPLETED" or not isinstance(
        evidence["generation_status"], str
    ):
        raise RecordSchemaError("failed response dose evidence has wrong generation status")
    numeric = {
        field: _binary64_evidence(evidence[field], f"dose_evidence.{field}", nullable=not dose_valid)
        for field in DOSE_NUMERIC_FIELDS
    }
    if not dose_valid and any(numeric[field] is not None for field in DOSE_NUMERIC_FIELDS):
        raise RecordSchemaError("invalid dose evidence requires the canonical all-null geometry")
    if dose_valid:
        if any(numeric[field] is None for field in DOSE_NUMERIC_FIELDS):
            raise RecordSchemaError("validated dose evidence cannot contain null numeric fields")
        c_value = numeric["nominal_c"]
        mu_value = numeric["mu_value"]
        alpha_pre = numeric["alpha_pre_dtype"]
        alpha_post = numeric["alpha_post_dtype"]
        pre_hook = numeric["pre_hook_l2"]
        post_hook = numeric["post_hook_l2"]
        if any(
            value is None or value <= 0.0
            for value in (c_value, mu_value, alpha_pre, alpha_post, pre_hook, post_hook)
        ):
            raise RecordSchemaError("validated dose evidence requires positive geometry values")
        if alpha_pre.hex() != (c_value * mu_value).hex():
            raise RecordSchemaError("dose evidence alpha_pre formula mismatch")
        if numeric["relative_dose"].hex() != (alpha_post / pre_hook).hex():
            raise RecordSchemaError("dose evidence relative_dose formula mismatch")
        if numeric["norm_ratio"].hex() != (post_hook / pre_hook).hex():
            raise RecordSchemaError("dose evidence norm_ratio formula mismatch")
        alignment = numeric["vector_alignment"]
        drift = numeric["cosine_drift"]
        if alignment < -1.0 or alignment > 1.0 or drift < 0.0 or drift > 2.0:
            raise RecordSchemaError("dose evidence alignment/drift is outside cosine bounds")
    return dict(evidence)


MEASUREMENT_RESULT_DOSE_MANIFEST_KEYS = {
    "schema_version", "protocol_version", "artifact_kind", "synthetic",
    "formal_experiment", "registry_sha256", "logical_identity_count", "parents",
    "scheduled_p1_identity_count", "terminal_status", "dose_binding",
    "code_sha256", "config_sha256", "environment_sha256", "created_at_utc",
    "self_sha256",
}


def _validate_frozen_dose_source(
    document: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    dose_context: AuthenticatedDoseContext,
) -> Mapping[str, Any]:
    if not isinstance(dose_context, AuthenticatedDoseContext):
        raise RecordSchemaError("dose materialization requires authenticated lifecycle context")
    _sha256_value(dose_context.registry_sha256, "dose_context.registry_sha256")
    _sha256_value(
        dose_context.measurement_result_self_sha256,
        "dose_context.measurement_result_self_sha256",
    )
    _sha256_value(dose_context.authorized_tip_sha256, "dose_context.authorized_tip_sha256")
    if (
        dose_context.synthetic is not registry.synthetic
        or dose_context.registry_sha256 != registry.manifest()["registry_sha256"]
        or dose_context.measurement_result_self_sha256 != document.get("self_sha256")
        or dose_context.authorized_event not in {
            "FORMAL_SUPPORT_GENERATION_STARTED",
            "SUPPORT_EXECUTION_MANIFEST_FROZEN",
            "BEHAVIOR_CONFIRMATION_FROZEN",
            "FORMAL_CONFIRMATION_GENERATION_STARTED",
        }
    ):
        raise RecordSchemaError("dose context is not bound to the supplied lifecycle source")
    _exact_keys(
        document,
        MEASUREMENT_RESULT_DOSE_MANIFEST_KEYS,
        "measurement-result dose manifest",
    )
    if (
        document["schema_version"] != "paper1-stage3-measurement-result-dose-manifest-v1"
        or document["protocol_version"] != "v3.5-rc2"
        or document["artifact_kind"] != "measurement_result_dose_manifest"
        or document["synthetic"] is not registry.synthetic
        or document["formal_experiment"] is not (not registry.synthetic)
        or document["registry_sha256"] != registry.manifest()["registry_sha256"]
        or document["logical_identity_count"] != FORMAL_LOGICAL_GENERATION
        or document["scheduled_p1_identity_count"] != 200
        or document["terminal_status"] != "ESTIMABLE"
    ):
        raise RecordSchemaError("measurement-result dose source is not the frozen estimable source")
    if document["self_sha256"] != canonical_sha256(
        {key: value for key, value in document.items() if key != "self_sha256"}
    ):
        raise RecordSchemaError("measurement-result dose source self hash mismatch")
    parents = document["parents"]
    expected_parent_keys = {
        "measurement_specification_freeze", "experiment_identity_manifest",
        "base_anchor_manifest", "p1_terminal_records",
    }
    if not isinstance(parents, Mapping) or set(parents) != expected_parent_keys:
        raise RecordSchemaError("measurement-result dose source parent set differs")
    for name, value in parents.items():
        _sha256_value(value, f"measurement_result.parents.{name}")
    if parents != dict(dose_context.parent_self_sha256):
        raise RecordSchemaError(
            "measurement-result parents differ from lifecycle-authenticated context"
        )
    for field in ("code_sha256", "config_sha256", "environment_sha256"):
        _sha256_value(document[field], f"measurement_result.{field}")
    if not isinstance(document["created_at_utc"], str) or not document["created_at_utc"]:
        raise RecordSchemaError("measurement-result dose source timestamp is invalid")
    dose_binding = document["dose_binding"]
    if not isinstance(dose_binding, Mapping):
        raise RecordSchemaError("measurement-result dose source lacks its dose binding")
    validate_dose_binding(dose_binding)
    if (
        dose_binding["synthetic"] is not registry.synthetic
        or dose_binding["parent_self_sha256"]
        != {
            "measurement_specification_freeze": parents["measurement_specification_freeze"],
            "experiment_identity_manifest": parents["experiment_identity_manifest"],
            "base_anchor_manifest": parents["base_anchor_manifest"],
        }
    ):
        raise RecordSchemaError("dose binding mode or parent hashes differ from its frozen manifest")
    return dose_binding


def _validate_materialized_dose_source(
    record: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    identity: Mapping[str, Any],
    generation: Mapping[str, Any],
    measurement_result_dose_manifest: Mapping[str, Any],
    dose_context: AuthenticatedDoseContext,
) -> None:
    dose_binding = _validate_frozen_dose_source(
        measurement_result_dose_manifest,
        registry=registry,
        dose_context=dose_context,
    )
    terminal_diagnostics = generation["attempts"][-1]["diagnostics"]
    if (
        terminal_diagnostics.get("measurement_result_dose_manifest_self_sha256")
        != measurement_result_dose_manifest["self_sha256"]
    ):
        raise RecordSchemaError(
            "generation record is not bound to the frozen measurement-result dose manifest"
        )
    evidence = record["dose_evidence"]
    clean = identity["block"] in {"harmful_clean", "benign_clean"}
    if clean:
        if evidence is not None:
            raise RecordSchemaError("clean response cannot contain steered dose evidence")
        return
    if not isinstance(evidence, Mapping):
        raise RecordSchemaError("steered response lacks materialized dose evidence")
    estimator = identity["estimator"]
    anchor = identity["anchor"]
    if (
        evidence["measurement_result_dose_binding_sha256"] != dose_binding["self_sha256"]
        or evidence["mu_estimator"] != estimator
        or evidence["mu_source_sha256"] != canonical_sha256(dose_binding[estimator])
        or evidence["generation_status"] != generation["terminal_status"]
    ):
        raise RecordSchemaError("response dose provenance differs from the frozen dose source")
    if evidence["status"] == "VALIDATED":
        bound = validate_dose_binding(dose_binding)[anchor][estimator]
        expected_hex = {
            "nominal_c": identity["c_hex"],
            "mu_value": dose_binding[estimator]["binary64_hex"],
            "alpha_pre_dtype": identity["alpha_pre_dtype_hex"],
            "alpha_post_dtype": identity["alpha_post_dtype_hex"],
        }
        if (
            identity["c_hex"] != bound["c_hex"]
            or identity["alpha_pre_dtype_hex"] != bound["alpha_pre_dtype_hex"]
            or identity["alpha_post_dtype_hex"] != bound["alpha_post_dtype_hex"]
        ):
            raise RecordSchemaError("logical identity dose differs from the frozen dose source")
        for field, expected in expected_hex.items():
            item = evidence[field]
            if not isinstance(item, Mapping) or item.get("binary64_hex") != expected:
                raise RecordSchemaError(f"dose_evidence.{field} differs from frozen dose identity")
        if terminal_diagnostics.get("dose_evidence_sha256") != canonical_sha256(evidence):
            raise RecordSchemaError(
                "validated per-call dose evidence is not bound to the generation record"
            )


P1_KEYS = {
    "schema_version",
    "protocol_version",
    "synthetic",
    "logical_id",
    "prompt_id",
    "stratum",
    "identity_complete",
    "render_complete",
    "valid_mask_complete",
    "forward_complete",
    "identity_collision",
    "valid_token_count",
    "content_token_count",
    "unresolved_valid_token_count",
    "required_norms_finite",
    "v_sum",
    "c_sum",
    "terminal_status",
    "exclusion_reason",
}


def validate_p1_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(record, P1_KEYS, "P1 record")
    if record["schema_version"] != "paper1-stage3-p1-measurement-record-v1":
        raise RecordSchemaError("invalid P1 schema_version")
    if record["protocol_version"] != "v3.5-rc2":
        raise RecordSchemaError("invalid protocol_version")
    _bool(record, "synthetic")
    _text(record, "logical_id")
    _text(record, "prompt_id")
    if record["stratum"] not in {"harmful", "benign"}:
        raise RecordSchemaError("P1 stratum must be harmful or benign")
    flags = {
        field: _bool(record, field)
        for field in (
            "identity_complete",
            "render_complete",
            "valid_mask_complete",
            "forward_complete",
            "identity_collision",
            "required_norms_finite",
        )
    }
    valid_count = _count(record, "valid_token_count")
    content_count = _count(record, "content_token_count")
    unresolved_count = _count(record, "unresolved_valid_token_count")
    v_sum = _finite_or_none(record, "v_sum")
    c_sum = _finite_or_none(record, "c_sum")
    if v_sum is not None and v_sum < 0.0:
        raise RecordSchemaError("v_sum must be nonnegative when present")
    if c_sum is not None and c_sum < 0.0:
        raise RecordSchemaError("c_sum must be nonnegative when present")
    terminal_status = _text(record, "terminal_status")
    exclusion_reason = _text(record, "exclusion_reason", nullable=True)
    complete_case = (
        flags["identity_complete"]
        and flags["render_complete"]
        and flags["valid_mask_complete"]
        and flags["forward_complete"]
        and not flags["identity_collision"]
        and flags["required_norms_finite"]
        and unresolved_count == 0
        and valid_count > 0
        and content_count > 0
        and content_count <= valid_count
        and v_sum is not None
        and c_sum is not None
        and v_sum >= 0.0
        and c_sum >= 0.0
    )
    if terminal_status == "COMPLETE_CASE" and (
        not complete_case or exclusion_reason is not None
    ):
        raise RecordSchemaError(
            "COMPLETE_CASE requires a complete record and null exclusion_reason"
        )
    if complete_case and terminal_status != "COMPLETE_CASE":
        raise RecordSchemaError("complete P1 record requires COMPLETE_CASE status")
    if not complete_case and exclusion_reason is None:
        raise RecordSchemaError("excluded P1 record requires one exclusion_reason")
    if not flags["identity_complete"] or flags["identity_collision"]:
        expected_status = "EXCLUDED_IDENTITY"
    elif not flags["render_complete"]:
        expected_status = "EXCLUDED_RENDER"
    elif not flags["valid_mask_complete"]:
        expected_status = "EXCLUDED_VALID_MASK"
    elif not flags["forward_complete"]:
        expected_status = "EXCLUDED_FORWARD"
    elif unresolved_count != 0:
        expected_status = "EXCLUDED_UNRESOLVED"
    elif not flags["required_norms_finite"] or v_sum is None or c_sum is None:
        expected_status = "EXCLUDED_NONFINITE"
    elif valid_count == 0 or content_count == 0 or content_count > valid_count:
        expected_status = "EXCLUDED_ZERO_DENOMINATOR"
    else:
        expected_status = "COMPLETE_CASE"
    if terminal_status != expected_status:
        raise RecordSchemaError(
            f"P1 terminal_status {terminal_status!r}, expected first failure {expected_status!r}"
        )
    expected_reason = None if complete_case else expected_status
    if exclusion_reason != expected_reason:
        raise RecordSchemaError("P1 exclusion_reason must equal the first terminal failure code")
    result = dict(record)
    result["complete_case"] = complete_case
    result["record_sha256"] = canonical_sha256(record)
    return result


P2_CELLS = {"P2_A_all", "P2_A_content", "P2_T_all", "P2_T_content"}
P2_KEYS = {
    "schema_version",
    "protocol_version",
    "synthetic",
    "logical_id",
    "identity_sha256",
    "generation_record_sha256",
    "judge_record_sha256",
    "cell",
    "prompt_id",
    "vector_id",
    "pair_id",
    "arm",
    "anchor",
    "estimator",
    "scheduled_identity_match",
    "generation_completed",
    "judge_eligible",
    "judge_label_parsed",
    "identity_complete",
    "identity_collision",
    "dose_denominator_valid",
    "dose_geometry_finite",
    "post_dtype_alpha_finite",
    "dose_evidence",
    "label",
    "terminal_status",
}


def validate_p2_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(record, P2_KEYS, "P2 record")
    if record["schema_version"] != "paper1-stage3-p2-response-record-v1":
        raise RecordSchemaError("invalid P2 schema_version")
    if record["protocol_version"] != "v3.5-rc2":
        raise RecordSchemaError("invalid protocol_version")
    _bool(record, "synthetic")
    _sha256_value(record["identity_sha256"], "identity_sha256")
    _sha256_value(record["generation_record_sha256"], "generation_record_sha256")
    if record["judge_record_sha256"] is not None:
        _sha256_value(record["judge_record_sha256"], "judge_record_sha256")
    for field in ("logical_id", "prompt_id", "vector_id", "pair_id", "estimator", "terminal_status"):
        _text(record, field)
    cell = record["cell"]
    if cell not in P2_CELLS:
        raise RecordSchemaError("invalid P2 cell")
    expected = {
        "P2_A_all": ("all-token", "A", "mu_all_tw"),
        "P2_A_content": ("content-token", "A", "mu_content_tw"),
        "P2_T_all": ("all-token", "T", "mu_all_tw"),
        "P2_T_content": ("content-token", "T", "mu_content_tw"),
    }[cell]
    if (record["arm"], record["anchor"], record["estimator"]) != expected:
        raise RecordSchemaError("P2 cell/arm/anchor/estimator mapping changed")
    flags = {
        field: _bool(record, field)
        for field in (
            "scheduled_identity_match",
            "generation_completed",
            "judge_eligible",
            "judge_label_parsed",
            "identity_complete",
            "identity_collision",
            "dose_denominator_valid",
            "dose_geometry_finite",
            "post_dtype_alpha_finite",
        )
    }
    label = _text(record, "label", nullable=True)
    if flags["judge_label_parsed"] and not flags["judge_eligible"]:
        raise RecordSchemaError("parsed P2 label requires judge_eligible")
    if flags["judge_eligible"] and not flags["generation_completed"]:
        raise RecordSchemaError("judge-eligible P2 row requires completed generation")
    if flags["judge_label_parsed"]:
        if label not in {"broken", "unsafe", "refusal", "safe"}:
            raise RecordSchemaError("parsed P2 status requires a registered harmful label")
    elif label is not None:
        raise RecordSchemaError("unparsed P2 status requires a null label")
    if flags["judge_label_parsed"] != (label in {"broken", "unsafe", "refusal", "safe"}):
        raise RecordSchemaError("P2 parsed status disagrees with label")
    dose_valid = all(
        flags[field]
        for field in ("dose_denominator_valid", "dose_geometry_finite", "post_dtype_alpha_finite")
    )
    _validate_dose_evidence(
        record["dose_evidence"],
        estimator=record["estimator"],
        generation_completed=flags["generation_completed"],
        dose_valid=dose_valid,
    )
    if (
        not flags["scheduled_identity_match"]
        or flags["identity_collision"]
        or not flags["identity_complete"]
    ):
        expected_terminal = "NON_ESTIMABLE_IDENTITY"
    elif not all(
        flags[field]
        for field in ("dose_denominator_valid", "dose_geometry_finite", "post_dtype_alpha_finite")
    ):
        expected_terminal = "NON_ESTIMABLE_DOSE"
    elif not flags["generation_completed"]:
        expected_terminal = "TERMINAL_GENERATION_FAILURE"
    elif not flags["judge_eligible"] or not flags["judge_label_parsed"]:
        expected_terminal = "TERMINAL_JUDGE_FAILURE"
    else:
        expected_terminal = "COMPLETED_PARSED"
    if record["terminal_status"] != expected_terminal:
        raise RecordSchemaError("P2 terminal_status violates failure precedence")
    result = dict(record)
    result["retained"] = (
        flags["scheduled_identity_match"]
        and flags["generation_completed"]
        and flags["judge_eligible"]
        and flags["judge_label_parsed"]
        and flags["identity_complete"]
        and not flags["identity_collision"]
        and flags["dose_denominator_valid"]
        and flags["dose_geometry_finite"]
        and flags["post_dtype_alpha_finite"]
    )
    result["record_sha256"] = canonical_sha256(record)
    return result


K1_KEYS = {
    "schema_version",
    "protocol_version",
    "synthetic",
    "logical_id",
    "source_p2_logical_id",
    "source_p2_record_sha256",
    "cell",
    "prompt_id",
    "vector_id",
    "label",
    "generation_calls_added",
    "judge_calls_added",
}


def validate_k1_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(record, K1_KEYS, "K1 record")
    if record["schema_version"] != "paper1-stage3-k1-reuse-record-v1":
        raise RecordSchemaError("invalid K1 schema_version")
    if record["protocol_version"] != "v3.5-rc2":
        raise RecordSchemaError("invalid protocol_version")
    _bool(record, "synthetic")
    for field in (
        "logical_id",
        "source_p2_logical_id",
        "prompt_id",
        "vector_id",
    ):
        _text(record, field)
    source_hash = _text(record, "source_p2_record_sha256")
    if len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
        raise RecordSchemaError("source_p2_record_sha256 must be lowercase SHA256")
    if record["logical_id"] != record["source_p2_logical_id"]:
        raise RecordSchemaError("K1 must reuse the exact P2 logical identity")
    if record["cell"] not in P2_CELLS:
        raise RecordSchemaError("K1 source cell is not a P2 cell")
    if record["label"] not in {"broken", "unsafe", "refusal", "safe"}:
        raise RecordSchemaError("invalid K1 label")
    if _count(record, "generation_calls_added") != 0 or _count(record, "judge_calls_added") != 0:
        raise RecordSchemaError("K1 adds zero generation and judge calls")
    result = dict(record)
    result["record_sha256"] = canonical_sha256(record)
    return result


BENIGN_KEYS = {
    "schema_version",
    "protocol_version",
    "synthetic",
    "logical_id",
    "identity_sha256",
    "generation_record_sha256",
    "judge_record_sha256",
    "cell",
    "prompt_id",
    "vector_id",
    "anchor",
    "estimator",
    "scheduled_identity_match",
    "generation_completed",
    "judge_eligible",
    "judge_label_parsed",
    "identity_complete",
    "identity_collision",
    "dose_denominator_valid",
    "dose_geometry_finite",
    "post_dtype_alpha_finite",
    "dose_evidence",
    "label",
    "terminal_status",
}


def validate_benign_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(record, BENIGN_KEYS, "benign record")
    if record["schema_version"] != "paper1-stage3-benign-response-record-v1":
        raise RecordSchemaError("invalid benign schema_version")
    if record["protocol_version"] != "v3.5-rc2":
        raise RecordSchemaError("invalid protocol_version")
    _bool(record, "synthetic")
    _sha256_value(record["identity_sha256"], "identity_sha256")
    _sha256_value(record["generation_record_sha256"], "generation_record_sha256")
    if record["judge_record_sha256"] is not None:
        _sha256_value(record["judge_record_sha256"], "judge_record_sha256")
    for field in ("logical_id", "prompt_id", "terminal_status"):
        _text(record, field)
    cell = record["cell"]
    if cell == "benign_clean":
        if record["vector_id"] is not None or record["anchor"] != "clean" or record["estimator"] != "clean":
            raise RecordSchemaError("benign clean identity changed")
    elif cell == "benign_T":
        _text(record, "vector_id")
        if record["anchor"] != "T" or record["estimator"] != "mu_all_tw":
            raise RecordSchemaError("benign T identity changed")
    else:
        raise RecordSchemaError("invalid benign cell")
    flags = {
        field: _bool(record, field)
        for field in (
            "scheduled_identity_match",
            "generation_completed",
            "judge_eligible",
            "judge_label_parsed",
            "identity_complete",
            "identity_collision",
            "dose_denominator_valid",
            "dose_geometry_finite",
            "post_dtype_alpha_finite",
        )
    }
    label = _text(record, "label", nullable=True)
    if flags["judge_label_parsed"] and not flags["judge_eligible"]:
        raise RecordSchemaError("parsed benign label requires judge_eligible")
    if flags["judge_eligible"] and not flags["generation_completed"]:
        raise RecordSchemaError("judge-eligible benign row requires completed generation")
    if flags["judge_label_parsed"]:
        if label not in {"broken", "unsafe", "refusal", "helpful"}:
            raise RecordSchemaError("parsed benign status requires a registered benign label")
    elif label is not None:
        raise RecordSchemaError("unparsed benign status requires a null label")
    if flags["judge_label_parsed"] != (label in {"broken", "unsafe", "refusal", "helpful"}):
        raise RecordSchemaError("benign parsed status disagrees with label")
    dose_valid = all(
        flags[field]
        for field in ("dose_denominator_valid", "dose_geometry_finite", "post_dtype_alpha_finite")
    )
    if cell == "benign_clean":
        if record["dose_evidence"] is not None:
            raise RecordSchemaError("benign clean response must not contain steered dose evidence")
    else:
        _validate_dose_evidence(
            record["dose_evidence"],
            estimator=record["estimator"],
            generation_completed=flags["generation_completed"],
            dose_valid=dose_valid,
        )
    if (
        not flags["scheduled_identity_match"]
        or flags["identity_collision"]
        or not flags["identity_complete"]
    ):
        expected_terminal = "NON_ESTIMABLE_IDENTITY"
    elif not all(
        flags[field]
        for field in ("dose_denominator_valid", "dose_geometry_finite", "post_dtype_alpha_finite")
    ):
        expected_terminal = "NON_ESTIMABLE_DOSE"
    elif not flags["generation_completed"]:
        expected_terminal = "TERMINAL_GENERATION_FAILURE"
    elif not flags["judge_eligible"] or not flags["judge_label_parsed"]:
        expected_terminal = "TERMINAL_JUDGE_FAILURE"
    else:
        expected_terminal = "COMPLETED_PARSED"
    if record["terminal_status"] != expected_terminal:
        raise RecordSchemaError("benign terminal_status violates failure precedence")
    result = dict(record)
    result["retained"] = (
        flags["scheduled_identity_match"]
        and flags["generation_completed"]
        and flags["judge_eligible"]
        and flags["judge_label_parsed"]
        and flags["identity_complete"]
        and not flags["identity_collision"]
        and flags["dose_denominator_valid"]
        and flags["dose_geometry_finite"]
        and flags["post_dtype_alpha_finite"]
    )
    result["record_sha256"] = canonical_sha256(record)
    return result


GENERATION_KEYS = {
    "schema_version",
    "protocol_version",
    "synthetic",
    "formal_experiment",
    "logical_id",
    "identity_sha256",
    "request_sha256",
    "attempts",
    "attempt_count",
    "retry_count",
    "terminal_status",
    "generation_completed",
    "output_text",
    "record_sha256",
}
ATTEMPT_KEYS = {"attempt_index", "status", "output_text", "failure_code", "diagnostics"}


def validate_generation_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(record, GENERATION_KEYS, "generation record")
    if record["schema_version"] != "paper1-stage3-generation-record-v1":
        raise RecordSchemaError("invalid generation schema_version")
    if record["protocol_version"] != "v3.5-rc2":
        raise RecordSchemaError("invalid protocol_version")
    synthetic = _bool(record, "synthetic")
    formal = _bool(record, "formal_experiment")
    if formal == synthetic:
        raise RecordSchemaError("synthetic and formal_experiment flags are inconsistent")
    _text(record, "logical_id")
    for field in ("identity_sha256", "request_sha256", "record_sha256"):
        value = _text(record, field)
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise RecordSchemaError(f"{field} must be lowercase SHA256")
    attempts = record["attempts"]
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 2:
        raise RecordSchemaError("generation attempts must contain one or two entries")
    statuses = []
    for index, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, Mapping):
            raise RecordSchemaError("generation attempt must be an object")
        _exact_keys(attempt, ATTEMPT_KEYS, "generation attempt")
        if attempt["attempt_index"] != index:
            raise RecordSchemaError("generation attempt indices must be contiguous one-based")
        status = attempt["status"]
        if status not in {
            "COMPLETED",
            "TECHNICAL_FAILURE_RETRYABLE",
            "TERMINAL_TECHNICAL_FAILURE",
            "TERMINAL_FAILURE",
            "TERMINAL_INDETERMINATE_FAILURE",
        }:
            raise RecordSchemaError("invalid generation attempt status")
        statuses.append(status)
        if status == "COMPLETED":
            if not isinstance(attempt["output_text"], str) or attempt["failure_code"] is not None:
                raise RecordSchemaError("completed generation attempt has invalid payload")
        elif (
            attempt["output_text"] is not None
            or not isinstance(attempt["failure_code"], str)
            or not attempt["failure_code"]
        ):
            raise RecordSchemaError("failed generation attempt has invalid payload")
        if not isinstance(attempt["diagnostics"], Mapping):
            raise RecordSchemaError("attempt diagnostics must be an object")
    if len(attempts) == 2:
        if statuses[0] != "TECHNICAL_FAILURE_RETRYABLE" or statuses[1] not in {
            "COMPLETED",
            "TERMINAL_TECHNICAL_FAILURE",
            "TERMINAL_FAILURE",
            "TERMINAL_INDETERMINATE_FAILURE",
        }:
            raise RecordSchemaError("generation retry must follow one retryable first failure")
    elif statuses[0] not in {
        "COMPLETED", "TERMINAL_FAILURE", "TERMINAL_INDETERMINATE_FAILURE"
    }:
        raise RecordSchemaError("single generation attempt must be terminal")
    if record["attempt_count"] != len(attempts) or record["retry_count"] != len(attempts) - 1:
        raise RecordSchemaError("generation attempt counters disagree with ledger")
    if record["terminal_status"] != statuses[-1]:
        raise RecordSchemaError("generation terminal_status disagrees with final attempt")
    completed = _bool(record, "generation_completed")
    if completed != (statuses[-1] == "COMPLETED"):
        raise RecordSchemaError("generation_completed disagrees with terminal attempt")
    if completed != isinstance(record["output_text"], str):
        raise RecordSchemaError("generation output_text disagrees with completion")
    if record["output_text"] != attempts[-1]["output_text"]:
        raise RecordSchemaError("generation output_text differs from the terminal attempt")
    expected_hash = canonical_sha256(
        {key: value for key, value in record.items() if key != "record_sha256"}
    )
    if record["record_sha256"] != expected_hash:
        raise RecordSchemaError("generation record_sha256 mismatch")
    return dict(record)


JUDGE_KEYS = {
    "schema_version",
    "protocol_version",
    "logical_id",
    "identity_sha256",
    "generation_record_sha256",
    "domain",
    "judge_freeze_self_sha256",
    "rubric_sha256",
    "request_sha256",
    "synthetic",
    "formal_experiment",
    "attempts",
    "judge_label_parsed",
    "terminal_status",
    "label",
    "rationale",
}


def validate_judge_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(record, JUDGE_KEYS, "judge record")
    if record["schema_version"] != "paper1-stage3-judge-record-v1":
        raise RecordSchemaError("invalid judge schema_version")
    if record["protocol_version"] != "v3.5-rc2":
        raise RecordSchemaError("invalid protocol_version")
    _text(record, "logical_id")
    for field in (
        "identity_sha256", "generation_record_sha256", "judge_freeze_self_sha256",
        "rubric_sha256",
    ):
        _sha256_value(record[field], field)
    if record["domain"] not in {"harmful", "benign"}:
        raise RecordSchemaError("judge domain must be harmful or benign")
    request_sha256 = _text(record, "request_sha256")
    if len(request_sha256) != 64 or any(char not in "0123456789abcdef" for char in request_sha256):
        raise RecordSchemaError("judge request_sha256 must be lowercase SHA256")
    synthetic = _bool(record, "synthetic")
    formal = _bool(record, "formal_experiment")
    if formal == synthetic:
        raise RecordSchemaError("synthetic and formal judge flags are inconsistent")
    attempts = record["attempts"]
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 2:
        raise RecordSchemaError("judge attempts must contain one or two entries")
    for index, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, Mapping) or set(attempt) != {
            "attempt_index", "status", "failure_code", "payload_sha256", "request_sha256"
        }:
            raise RecordSchemaError("invalid judge attempt object")
        if attempt["attempt_index"] != index:
            raise RecordSchemaError("judge attempt indices must be contiguous one-based")
        if attempt["request_sha256"] != request_sha256:
            raise RecordSchemaError("judge retry changed request identity")
        status = attempt["status"]
        if status not in {
            "PARSED", "RETRYABLE_FAILURE", "TERMINAL_FAILURE",
            "TERMINAL_INDETERMINATE_FAILURE",
        }:
            raise RecordSchemaError("invalid judge attempt status")
        payload_hash = attempt["payload_sha256"]
        if payload_hash is not None and (
            not isinstance(payload_hash, str)
            or len(payload_hash) != 64
            or any(char not in "0123456789abcdef" for char in payload_hash)
        ):
            raise RecordSchemaError("judge payload_sha256 must be null or lowercase SHA256")
        if status == "PARSED":
            if attempt["failure_code"] is not None or payload_hash is None:
                raise RecordSchemaError("parsed judge attempt has invalid failure/hash fields")
        elif not isinstance(attempt["failure_code"], str) or not attempt["failure_code"]:
            raise RecordSchemaError("failed judge attempt requires a failure_code")
    if len(attempts) == 2:
        if attempts[0]["status"] != "RETRYABLE_FAILURE" or attempts[1]["status"] not in {
            "PARSED", "TERMINAL_FAILURE"
        }:
            raise RecordSchemaError("judge retry must follow one retryable first failure")
    elif attempts[0]["status"] not in {"PARSED", "TERMINAL_INDETERMINATE_FAILURE"}:
        raise RecordSchemaError(
            "single judge attempt must parse or terminate indeterminately"
        )
    parsed = _bool(record, "judge_label_parsed")
    label = _text(record, "label", nullable=True)
    rationale = _text(record, "rationale", nullable=True)
    allowed = {
        "harmful": {"broken", "unsafe", "refusal", "safe"},
        "benign": {"broken", "unsafe", "refusal", "helpful"},
    }[record["domain"]]
    if parsed:
        if record["terminal_status"] != "PARSED" or label not in allowed or rationale is None:
            raise RecordSchemaError("parsed judge terminal fields are inconsistent")
        if attempts[-1]["status"] != "PARSED":
            raise RecordSchemaError("parsed judge record lacks parsed terminal attempt")
    else:
        parse_failure = (
            record["terminal_status"] == "TERMINAL_PARSE_OR_INFRASTRUCTURE_FAILURE"
            and len(attempts) == 2
            and attempts[-1]["status"] == "TERMINAL_FAILURE"
        )
        indeterminate_failure = (
            record["terminal_status"] == "TERMINAL_INDETERMINATE_FAILURE"
            and len(attempts) == 1
            and attempts[-1]["status"] == "TERMINAL_INDETERMINATE_FAILURE"
        )
        if label is not None or rationale is not None or not (
            parse_failure or indeterminate_failure
        ):
            raise RecordSchemaError("failed judge terminal fields are inconsistent")
    return dict(record)


def _validate_response_sources(
    record: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None,
    expected_domain: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    identity = registry.require(record["logical_id"])
    generation = validate_generation_record(generation_record)
    judge = validate_judge_record(judge_record) if judge_record is not None else None
    if record["synthetic"] is not registry.synthetic:
        raise RecordSchemaError("response mode differs from the fixed registry")
    if (
        generation["logical_id"] != record["logical_id"]
        or generation["synthetic"] is not registry.synthetic
        or generation["identity_sha256"] != canonical_sha256(identity)
        or record["identity_sha256"] != generation["identity_sha256"]
        or record["generation_record_sha256"] != generation["record_sha256"]
        or record["generation_completed"] is not generation["generation_completed"]
    ):
        raise RecordSchemaError("response generation provenance differs from fixed sources")
    if generation["generation_completed"]:
        if judge is None:
            raise RecordSchemaError("completed generation requires its materialized judge record")
        if (
            judge["logical_id"] != record["logical_id"]
            or judge["synthetic"] is not registry.synthetic
            or judge["domain"] != expected_domain
            or judge["identity_sha256"] != generation["identity_sha256"]
            or judge["generation_record_sha256"] != generation["record_sha256"]
            or record["judge_record_sha256"] != canonical_sha256(judge)
            or record["judge_eligible"] is not True
            or record["judge_label_parsed"] is not judge["judge_label_parsed"]
            or record["label"] != judge["label"]
        ):
            raise RecordSchemaError("response judge provenance differs from fixed sources")
    elif (
        judge is not None
        or record["judge_record_sha256"] is not None
        or record["judge_eligible"] is not False
        or record["judge_label_parsed"] is not False
        or record["label"] is not None
    ):
        raise RecordSchemaError("failed generation cannot claim judge provenance")
    if (
        record["scheduled_identity_match"] is not True
        or record["identity_complete"] is not True
        or record["identity_collision"] is not False
    ):
        raise RecordSchemaError("registered response cannot self-report an identity mismatch")
    return dict(record), generation, judge, identity


def validate_p2_materialization(
    record: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None,
    measurement_result_dose_manifest: Mapping[str, Any],
    dose_context: AuthenticatedDoseContext,
) -> dict[str, Any]:
    validated = validate_p2_record(record)
    _, generation, _, identity = _validate_response_sources(
        record,
        registry=registry,
        generation_record=generation_record,
        judge_record=judge_record,
        expected_domain="harmful",
    )
    if (
        identity["block"] != record["cell"]
        or identity["domain"] != "harmful"
        or identity["prompt_id"] != record["prompt_id"]
        or identity["vector_id"] != record["vector_id"]
        or identity["anchor"] != record["anchor"]
        or identity["estimator"] != record["estimator"]
        or record["pair_id"]
        != f"{identity['anchor']}|{identity['prompt_id']}|{identity['vector_id']}"
    ):
        raise RecordSchemaError("P2 response fields differ from its fixed logical identity")
    _validate_materialized_dose_source(
        record,
        registry=registry,
        identity=identity,
        generation=generation,
        measurement_result_dose_manifest=measurement_result_dose_manifest,
        dose_context=dose_context,
    )
    return validated


def validate_benign_materialization(
    record: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None,
    measurement_result_dose_manifest: Mapping[str, Any],
    dose_context: AuthenticatedDoseContext,
) -> dict[str, Any]:
    validated = validate_benign_record(record)
    _, generation, _, identity = _validate_response_sources(
        record,
        registry=registry,
        generation_record=generation_record,
        judge_record=judge_record,
        expected_domain="benign",
    )
    if (
        identity["block"] != record["cell"]
        or identity["domain"] != "benign"
        or identity["prompt_id"] != record["prompt_id"]
        or identity["vector_id"] != record["vector_id"]
        or identity["anchor"] != record["anchor"]
        or identity["estimator"] != record["estimator"]
    ):
        raise RecordSchemaError("benign response fields differ from its fixed logical identity")
    _validate_materialized_dose_source(
        record,
        registry=registry,
        identity=identity,
        generation=generation,
        measurement_result_dose_manifest=measurement_result_dose_manifest,
        dose_context=dose_context,
    )
    return validated


SUPPORT_RESPONSE_KEYS = {
    "logical_id", "identity_sha256", "synthetic", "anchor", "scheduled_identity_match",
    "generation_completed", "judge_eligible", "judge_label_parsed",
    "identity_complete", "identity_collision", "dose_denominator_valid",
    "dose_geometry_finite", "post_dtype_alpha_finite", "dose_evidence",
    "generation_record_sha256", "judge_record_sha256", "label",
    "terminal_status", "retained",
}


def validate_support_response_materialization(
    record: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any] | None,
    judge_record: Mapping[str, Any] | None,
    measurement_result_dose_manifest: Mapping[str, Any],
    dose_context: AuthenticatedDoseContext,
    unattempted_parent_status: str | None = None,
) -> dict[str, Any]:
    _exact_keys(record, SUPPORT_RESPONSE_KEYS, "support response materialization")
    identity = registry.require(record["logical_id"])
    if (
        identity["block"] != "support"
        or record["synthetic"] is not registry.synthetic
        or record["identity_sha256"] != canonical_sha256(identity)
        or record["anchor"] != identity["anchor"]
    ):
        raise RecordSchemaError("support response differs from its fixed logical identity")
    flags = {
        field: _bool(record, field)
        for field in (
            "scheduled_identity_match", "generation_completed", "judge_eligible",
            "judge_label_parsed", "identity_complete", "identity_collision",
            "dose_denominator_valid", "dose_geometry_finite",
            "post_dtype_alpha_finite", "retained",
        )
    }
    expected_retained = (
        flags["scheduled_identity_match"]
        and flags["generation_completed"]
        and flags["judge_eligible"]
        and flags["judge_label_parsed"]
        and flags["identity_complete"]
        and not flags["identity_collision"]
        and flags["dose_denominator_valid"]
        and flags["dose_geometry_finite"]
        and flags["post_dtype_alpha_finite"]
    )
    if flags["retained"] is not expected_retained:
        raise RecordSchemaError("support response retained predicate differs")
    if generation_record is None:
        if (
            judge_record is not None
            or record["generation_record_sha256"] is not None
            or record["judge_record_sha256"] is not None
            or flags["generation_completed"]
            or flags["judge_eligible"]
            or flags["judge_label_parsed"]
            or record["label"] is not None
            or record["dose_evidence"] is not None
        ):
            raise RecordSchemaError("unexecuted support response claims call materialization")
        synthetic_unexecuted = (
            registry.synthetic
            and record["terminal_status"] == "SYNTHETIC_NOT_EXECUTED"
            and flags["scheduled_identity_match"]
            and flags["identity_complete"]
            and not flags["identity_collision"]
            and all(
                flags[field]
                for field in (
                    "dose_denominator_valid", "dose_geometry_finite",
                    "post_dtype_alpha_finite",
                )
            )
        )
        identity_failure = (
            record["terminal_status"] == "NON_ESTIMABLE_IDENTITY"
            and (
                not flags["scheduled_identity_match"]
                or not flags["identity_complete"]
                or flags["identity_collision"]
            )
        )
        integrity_unattempted = (
            not registry.synthetic
            and isinstance(unattempted_parent_status, str)
            and bool(unattempted_parent_status)
            and record["terminal_status"] == unattempted_parent_status
        )
        if not (synthetic_unexecuted or identity_failure or integrity_unattempted):
            raise RecordSchemaError("unexecuted support response lacks an explicit terminal cause")
        return dict(record)

    _, generation, _, _ = _validate_response_sources(
        record,
        registry=registry,
        generation_record=generation_record,
        judge_record=judge_record,
        expected_domain="harmful",
    )
    _validate_dose_evidence(
        record["dose_evidence"],
        estimator=identity["estimator"],
        generation_completed=flags["generation_completed"],
        dose_valid=all(
            flags[field]
            for field in (
                "dose_denominator_valid", "dose_geometry_finite",
                "post_dtype_alpha_finite",
            )
        ),
    )
    _validate_materialized_dose_source(
        record,
        registry=registry,
        identity=identity,
        generation=generation,
        measurement_result_dose_manifest=measurement_result_dose_manifest,
        dose_context=dose_context,
    )
    if record["label"] not in {None, "broken", "unsafe", "refusal", "safe"}:
        raise RecordSchemaError("support response label is outside the harmful rubric")
    if not flags["judge_label_parsed"] and record["label"] is not None:
        raise RecordSchemaError("unparsed support response must have a null label")
    identity_failed = (
        not flags["scheduled_identity_match"]
        or not flags["identity_complete"]
        or flags["identity_collision"]
    )
    dose_failed = not all(
        flags[field]
        for field in (
            "dose_denominator_valid", "dose_geometry_finite", "post_dtype_alpha_finite",
        )
    )
    expected_terminal = (
        "NON_ESTIMABLE_IDENTITY" if identity_failed
        else "NON_ESTIMABLE_DOSE" if dose_failed
        else "TERMINAL_GENERATION_FAILURE" if not flags["generation_completed"]
        else "TERMINAL_JUDGE_FAILURE" if not flags["judge_label_parsed"]
        else "COMPLETED_PARSED"
    )
    if record["terminal_status"] != expected_terminal:
        raise RecordSchemaError("support response terminal status violates failure precedence")
    return dict(record)


def validate_k1_materialization(
    record: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    source_p2_record: Mapping[str, Any],
    generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any],
    measurement_result_dose_manifest: Mapping[str, Any],
    dose_context: AuthenticatedDoseContext,
) -> dict[str, Any]:
    validated = validate_k1_record(record)
    raw_source = {key: source_p2_record[key] for key in P2_KEYS}
    source = validate_p2_materialization(
        raw_source,
        registry=registry,
        generation_record=generation_record,
        judge_record=judge_record,
        measurement_result_dose_manifest=measurement_result_dose_manifest,
        dose_context=dose_context,
    )
    if not source["retained"]:
        raise RecordSchemaError("K1 source P2 record is not retained")
    if (
        record["synthetic"] is not registry.synthetic
        or record["source_p2_record_sha256"] != source["record_sha256"]
        or record["source_p2_logical_id"] != source["logical_id"]
        or record["logical_id"] != source["logical_id"]
        or record["cell"] != source["cell"]
        or record["prompt_id"] != source["prompt_id"]
        or record["vector_id"] != source["vector_id"]
        or record["label"] != source["label"]
    ):
        raise RecordSchemaError("K1 fields differ from the exact retained P2 source")
    return validated


VALIDATORS = {
    "generation": validate_generation_record,
    "judge": validate_judge_record,
    "p1": validate_p1_record,
}


def validate_record(record_type: str, record: Mapping[str, Any]) -> dict[str, Any]:
    if record_type in {"p2", "k1", "benign"}:
        raise RecordSchemaError(
            f"{record_type} requires its source-aware materialization validator"
        )
    try:
        validator = VALIDATORS[record_type]
    except KeyError as exc:
        raise RecordSchemaError(f"unknown record type: {record_type}") from exc
    return validator(record)
