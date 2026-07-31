"""Schema-backed semantic validators for Stage 3 runtime records."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from .core import (
    BLOCK_IDENTITY_RULES,
    JUDGE_LABELS,
    PROTOCOL_VERSION,
    LogicalIdentityRegistry,
    PipelineError,
    canonical_sha256,
    normalize_identity,
    validate_generation_config,
    validate_judge_config,
    validate_run_mode,
)
from .dose import validate_dose_binding
from .json_schema import SchemaDefinitionError, SchemaValidationError, validate_schema


SCHEMA_DIRECTORY = Path(__file__).with_name("schemas")


class RecordSchemaError(PipelineError):
    """A runtime record failed structural or semantic validation."""


def _schema(record: Mapping[str, Any], name: str) -> None:
    try:
        validate_schema(record, SCHEMA_DIRECTORY / f"{name}.schema.json")
    except (SchemaDefinitionError, SchemaValidationError) as exc:
        raise RecordSchemaError(f"{name} schema rejected record: {exc}") from exc


def _exact_keys(record: Mapping[str, Any], required: set[str], name: str) -> None:
    if not isinstance(record, Mapping):
        raise RecordSchemaError(f"{name} must be an object")
    actual = set(record)
    if actual != required:
        raise RecordSchemaError(
            f"{name} keys differ: missing={sorted(required-actual)}, extra={sorted(actual-required)}"
        )


def _text(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RecordSchemaError(f"{field} must be a nonempty string")
    return value


def _sha(value: Any, field: str, *, nullable: bool = False) -> str | None:
    text = _text(value, field, nullable=nullable)
    if text is None:
        return None
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise RecordSchemaError(f"{field} must be lowercase SHA256")
    return text


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RecordSchemaError(f"{field} must be a nonnegative integer")
    return value


def _finite(value: Any, field: str, *, nullable: bool = False, nonnegative: bool = False) -> float | None:
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecordSchemaError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number) or (nonnegative and number < 0.0):
        raise RecordSchemaError(f"{field} must be finite and nonnegative")
    return number


def _record_hash(record: Mapping[str, Any]) -> None:
    expected = canonical_sha256({key: value for key, value in record.items() if key != "record_sha256"})
    if record.get("record_sha256") != expected:
        raise RecordSchemaError("record_sha256 mismatch")


GENERATION_RECORD_KEYS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible", "fake_backend",
    "logical_id", "identity_sha256", "request_sha256", "generation_config", "attempts",
    "attempt_count", "retry_count", "terminal_status", "generation_completed", "output_text",
    "record_sha256",
}


def validate_generation_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _schema(record, "generation_record")
    _exact_keys(record, GENERATION_RECORD_KEYS, "generation record")
    if record["schema_version"] != "paper1-stage3-generation-record-v2":
        raise RecordSchemaError("invalid generation schema_version")
    if record["protocol_version"] != PROTOCOL_VERSION:
        raise RecordSchemaError("invalid generation protocol_version")
    mode = validate_run_mode(record["run_mode"])
    if record["paper_result_eligible"] is not False or not isinstance(record["fake_backend"], bool):
        raise RecordSchemaError("invalid generation eligibility/backend flags")
    _text(record["logical_id"], "logical_id")
    _sha(record["identity_sha256"], "identity_sha256")
    _sha(record["request_sha256"], "request_sha256")
    validate_generation_config(record["generation_config"], run_mode=mode)
    attempts = record["attempts"]
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 2:
        raise RecordSchemaError("generation attempts must contain one or two entries")
    statuses: list[str] = []
    for index, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, Mapping) or set(attempt) != {
            "attempt_index", "status", "output_text", "failure_code", "diagnostics"
        }:
            raise RecordSchemaError("generation attempt fields differ")
        if attempt["attempt_index"] != index or not isinstance(attempt["diagnostics"], Mapping):
            raise RecordSchemaError("generation attempt order or diagnostics are invalid")
        status = attempt["status"]
        if status not in {
            "COMPLETED", "TECHNICAL_FAILURE_RETRYABLE", "TERMINAL_TECHNICAL_FAILURE",
            "TERMINAL_FAILURE", "TERMINAL_INDETERMINATE_FAILURE",
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
    if len(attempts) == 2:
        if statuses[0] != "TECHNICAL_FAILURE_RETRYABLE" or statuses[1] not in {
            "COMPLETED", "TERMINAL_TECHNICAL_FAILURE", "TERMINAL_FAILURE",
            "TERMINAL_INDETERMINATE_FAILURE",
        }:
            raise RecordSchemaError("generation retry violates the one-identical-retry rule")
    elif statuses[0] not in {"COMPLETED", "TERMINAL_FAILURE", "TERMINAL_INDETERMINATE_FAILURE"}:
        raise RecordSchemaError("a single generation attempt must already be terminal")
    if record["attempt_count"] != len(attempts) or record["retry_count"] != len(attempts) - 1:
        raise RecordSchemaError("generation attempt counters differ")
    terminal = attempts[-1]
    if record["terminal_status"] != terminal["status"]:
        raise RecordSchemaError("generation terminal status differs")
    completed = terminal["status"] == "COMPLETED"
    if record["generation_completed"] is not completed or record["output_text"] != terminal["output_text"]:
        raise RecordSchemaError("generation terminal fields differ from the final attempt")
    _record_hash(record)
    return dict(record)


JUDGE_RECORD_KEYS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible", "fake_backend",
    "logical_id", "identity_sha256", "generation_record_sha256", "domain", "judge_config",
    "judge_identity", "request_sha256", "attempts", "judge_label_parsed", "terminal_status",
    "label", "rationale", "record_sha256",
}


def validate_judge_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _schema(record, "judge_record")
    _exact_keys(record, JUDGE_RECORD_KEYS, "judge record")
    if record["schema_version"] != "paper1-stage3-judge-record-v2" or record["protocol_version"] != PROTOCOL_VERSION:
        raise RecordSchemaError("invalid judge schema/protocol version")
    mode = validate_run_mode(record["run_mode"])
    if record["paper_result_eligible"] is not False or not isinstance(record["fake_backend"], bool):
        raise RecordSchemaError("invalid judge eligibility/backend flags")
    _text(record["logical_id"], "logical_id")
    for field in ("identity_sha256", "generation_record_sha256", "request_sha256"):
        _sha(record[field], field)
    domain = record["domain"]
    if domain not in JUDGE_LABELS:
        raise RecordSchemaError("invalid judge domain")
    validate_judge_config(record["judge_config"], run_mode=mode)
    identity = record["judge_identity"]
    if not isinstance(identity, Mapping) or set(identity) != {
        "model_path_or_id", "tokenizer_path_or_id", "rubric_sha256"
    }:
        raise RecordSchemaError("judge_identity fields differ")
    _text(identity["model_path_or_id"], "judge.model_path_or_id")
    _text(identity["tokenizer_path_or_id"], "judge.tokenizer_path_or_id")
    _sha(identity["rubric_sha256"], "judge.rubric_sha256")
    attempts = record["attempts"]
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 2:
        raise RecordSchemaError("judge attempts must contain one or two entries")
    statuses: list[str] = []
    for index, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, Mapping) or set(attempt) != {
            "attempt_index", "status", "failure_code", "payload_sha256", "request_sha256"
        }:
            raise RecordSchemaError("judge attempt fields differ")
        if attempt["attempt_index"] != index or attempt["request_sha256"] != record["request_sha256"]:
            raise RecordSchemaError("judge attempt order or request hash differs")
        status = attempt["status"]
        if status not in {"PARSED", "RETRYABLE_FAILURE", "TERMINAL_FAILURE", "TERMINAL_INDETERMINATE_FAILURE"}:
            raise RecordSchemaError("invalid judge attempt status")
        statuses.append(status)
        if attempt["payload_sha256"] is not None:
            _sha(attempt["payload_sha256"], "judge.payload_sha256")
        if status == "PARSED":
            if attempt["failure_code"] is not None or attempt["payload_sha256"] is None:
                raise RecordSchemaError("parsed judge attempt has invalid payload")
        elif not isinstance(attempt["failure_code"], str) or not attempt["failure_code"]:
            raise RecordSchemaError("failed judge attempt requires a failure_code")
    if len(attempts) == 2:
        if statuses[0] != "RETRYABLE_FAILURE" or statuses[1] not in {"PARSED", "TERMINAL_FAILURE"}:
            raise RecordSchemaError("judge retry violates the one-identical-retry rule")
    elif statuses[0] not in {"PARSED", "TERMINAL_INDETERMINATE_FAILURE"}:
        raise RecordSchemaError("a single judge attempt must already be terminal")
    expected_terminal = {
        "PARSED": "PARSED",
        "TERMINAL_FAILURE": "TERMINAL_PARSE_OR_INFRASTRUCTURE_FAILURE",
        "TERMINAL_INDETERMINATE_FAILURE": "TERMINAL_INDETERMINATE_FAILURE",
    }[statuses[-1]]
    if record["terminal_status"] != expected_terminal:
        raise RecordSchemaError("judge terminal status differs from terminal attempt")
    parsed = expected_terminal == "PARSED"
    if record["judge_label_parsed"] is not parsed:
        raise RecordSchemaError("judge_label_parsed differs from terminal status")
    if parsed:
        if record["label"] not in JUDGE_LABELS[domain] or not isinstance(record["rationale"], str) or not record["rationale"]:
            raise RecordSchemaError("parsed judge output is invalid")
    elif record["label"] is not None or record["rationale"] is not None:
        raise RecordSchemaError("failed judge output must not contain a label")
    _record_hash(record)
    return dict(record)


RESPONSE_RECORD_KEYS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible", "fake_backend",
    "generation_fake_backend", "judge_fake_backend", "logical_id", "block", "domain",
    "prompt_id", "vector_id", "identity_sha256", "generation_record_sha256",
    "judge_record_sha256", "generation_completed", "judge_eligible", "judge_label_parsed",
    "label", "missingness_code", "dose_evidence", "record_sha256",
}


def validate_response_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the common response envelope used by vector-free harmful clean rows."""
    _schema(record, "response_record")
    _exact_keys(record, RESPONSE_RECORD_KEYS, "response record")
    if record["schema_version"] != "paper1-stage3-response-record-v2" or record["protocol_version"] != PROTOCOL_VERSION:
        raise RecordSchemaError("invalid response schema/protocol version")
    validate_run_mode(record["run_mode"])
    if record["paper_result_eligible"] is not False:
        raise RecordSchemaError("raw response records are not paper-result eligible")
    if not isinstance(record["generation_fake_backend"], bool):
        raise RecordSchemaError("generation_fake_backend must be boolean")
    judge_fake = record["judge_fake_backend"]
    if judge_fake is not None and not isinstance(judge_fake, bool):
        raise RecordSchemaError("judge_fake_backend must be boolean or null")
    if (record["judge_record_sha256"] is None) is not (judge_fake is None):
        raise RecordSchemaError("judge fake provenance disagrees with judge record presence")
    if record["fake_backend"] is not (record["generation_fake_backend"] or judge_fake is True):
        raise RecordSchemaError("response fake_backend disagrees with upstream provenance")
    for field in ("logical_id", "block", "domain", "prompt_id"):
        _text(record[field], field)
    if record["block"] != "harmful_clean" or record["domain"] != "harmful" or record["vector_id"] is not None:
        raise RecordSchemaError("the common response envelope is restricted to harmful_clean")
    _sha(record["identity_sha256"], "identity_sha256")
    _sha(record["generation_record_sha256"], "generation_record_sha256")
    _sha(record["judge_record_sha256"], "judge_record_sha256", nullable=True)
    for field in ("generation_completed", "judge_eligible", "judge_label_parsed"):
        if not isinstance(record[field], bool):
            raise RecordSchemaError(f"{field} must be boolean")
    if record["judge_eligible"] and not record["generation_completed"]:
        raise RecordSchemaError("harmful clean judge eligibility requires generation completion")
    if record["judge_eligible"] is not (record["judge_record_sha256"] is not None):
        raise RecordSchemaError("harmful clean judge provenance differs from eligibility")
    if record["judge_label_parsed"]:
        if record["label"] not in JUDGE_LABELS["harmful"] or record["missingness_code"] is not None:
            raise RecordSchemaError("parsed harmful clean response is inconsistent")
    else:
        if record["label"] is not None:
            raise RecordSchemaError("unparsed harmful clean response must have null label")
        if not record["generation_completed"]:
            expected_missingness = {
                "TERMINAL_TECHNICAL_FAILURE": "TERMINAL_GENERATION_TECHNICAL_FAILURE",
                "TERMINAL_FAILURE": "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
                "TERMINAL_INDETERMINATE_FAILURE": "TERMINAL_GENERATION_INDETERMINATE_FAILURE",
            }
            if record["missingness_code"] not in set(expected_missingness.values()):
                raise RecordSchemaError("harmful clean generation missingness is invalid")
        elif not record["judge_eligible"]:
            if record["missingness_code"] != "TERMINAL_PREJUDGE_FAILURE":
                raise RecordSchemaError("harmful clean prejudge missingness is invalid")
        elif record["missingness_code"] not in {
            "TERMINAL_JUDGE_FAILURE", "TERMINAL_JUDGE_INDETERMINATE_FAILURE"
        }:
            raise RecordSchemaError("harmful clean judge missingness is invalid")
    if record["dose_evidence"] is not None:
        raise RecordSchemaError("harmful clean response must not contain dose evidence")
    _record_hash(record)
    return dict(record)


P1_KEYS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible", "logical_id",
    "identity_sha256", "prompt_id", "domain", "identity_complete", "render_complete",
    "valid_mask_complete", "forward_complete", "identity_collision", "valid_token_count",
    "content_token_count", "unresolved_valid_token_count", "required_norms_finite",
    "all_norm_sum", "content_norm_sum", "complete_case", "terminal_status",
    "exclusion_reason", "record_sha256",
}


def validate_p1_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _schema(record, "p1_measurement_record")
    _exact_keys(record, P1_KEYS, "P1 record")
    if record["schema_version"] != "paper1-stage3-p1-measurement-record-v3" or record["protocol_version"] != PROTOCOL_VERSION:
        raise RecordSchemaError("invalid P1 schema/protocol version")
    validate_run_mode(record["run_mode"])
    if record["paper_result_eligible"] is not False:
        raise RecordSchemaError("raw P1 records are not paper-result eligible")
    _text(record["logical_id"], "logical_id")
    _sha(record["identity_sha256"], "identity_sha256")
    _text(record["prompt_id"], "prompt_id")
    if record["domain"] not in {"harmful", "benign"}:
        raise RecordSchemaError("P1 domain must be harmful or benign")
    flags = {}
    for field in (
        "identity_complete", "render_complete", "valid_mask_complete", "forward_complete",
        "identity_collision", "required_norms_finite",
    ):
        if not isinstance(record[field], bool):
            raise RecordSchemaError(f"{field} must be boolean")
        flags[field] = record[field]
    valid_count = _count(record["valid_token_count"], "valid_token_count")
    content_count = _count(record["content_token_count"], "content_token_count")
    unresolved = _count(record["unresolved_valid_token_count"], "unresolved_valid_token_count")
    all_sum = _finite(record["all_norm_sum"], "all_norm_sum", nullable=True, nonnegative=True)
    content_sum = _finite(record["content_norm_sum"], "content_norm_sum", nullable=True, nonnegative=True)
    if (
        content_count > valid_count
        or unresolved > valid_count
        or content_count + unresolved > valid_count
    ):
        raise RecordSchemaError("P1 token counts are internally inconsistent")
    if all_sum is not None and valid_count == 0 and all_sum != 0.0:
        raise RecordSchemaError("P1 zero valid-token denominator requires a zero all-token norm sum")
    if content_sum is not None and content_count == 0 and content_sum != 0.0:
        raise RecordSchemaError("P1 zero content-token denominator requires a zero content norm sum")
    if all_sum is not None and content_sum is not None and content_sum > all_sum:
        raise RecordSchemaError("P1 content-token norm sum exceeds its all-token superset")
    if flags["required_norms_finite"] is not (all_sum is not None and content_sum is not None):
        raise RecordSchemaError("P1 finite-norm flag differs from norm presence")
    complete = (
        flags["identity_complete"] and flags["render_complete"] and flags["valid_mask_complete"]
        and flags["forward_complete"] and not flags["identity_collision"]
        and flags["required_norms_finite"] and unresolved == 0 and valid_count > 0
        and content_count > 0 and content_count <= valid_count
        and all_sum is not None and content_sum is not None
    )
    if not flags["identity_complete"] or flags["identity_collision"]:
        expected_terminal = "EXCLUDED_IDENTITY"
    elif not flags["render_complete"]:
        expected_terminal = "EXCLUDED_RENDER"
    elif not flags["valid_mask_complete"]:
        expected_terminal = "EXCLUDED_VALID_MASK"
    elif not flags["forward_complete"]:
        expected_terminal = "EXCLUDED_FORWARD"
    elif unresolved != 0:
        expected_terminal = "EXCLUDED_UNRESOLVED"
    elif not flags["required_norms_finite"] or all_sum is None or content_sum is None:
        expected_terminal = "EXCLUDED_NONFINITE"
    elif valid_count == 0 or content_count == 0 or content_count > valid_count:
        expected_terminal = "EXCLUDED_ZERO_DENOMINATOR"
    else:
        expected_terminal = "COMPLETE_CASE"
    if record["complete_case"] is not complete or record["terminal_status"] != expected_terminal:
        raise RecordSchemaError("P1 complete-case or first-failure terminal status differs")
    expected_reason = None if complete else expected_terminal
    if record["exclusion_reason"] != expected_reason:
        raise RecordSchemaError("P1 exclusion_reason differs from first-failure status")
    _record_hash(record)
    return dict(record)


DOSE_FIELDS = {
    "status", "failure_code", "nominal_c", "mu_estimator", "mu_value", "mu_source_sha256",
    "alpha_pre_dtype", "alpha_post_dtype", "pre_hook_l2", "post_hook_l2", "relative_dose",
    "norm_ratio", "vector_alignment", "cosine_drift", "measurement_dose_sha256",
    "generation_status", "phase", "use_cache",
}
_BINARY_FIELDS = (
    "nominal_c", "mu_value", "alpha_pre_dtype", "alpha_post_dtype", "pre_hook_l2",
    "post_hook_l2", "relative_dose", "norm_ratio", "vector_alignment", "cosine_drift",
)


def _binary64(value: Any, field: str, *, nullable: bool) -> float | None:
    if nullable and value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"value", "binary64_hex"}:
        raise RecordSchemaError(f"dose_evidence.{field} must be a binary64 object")
    number = _finite(value["value"], f"dose_evidence.{field}")
    assert number is not None
    if value["binary64_hex"] != number.hex():
        raise RecordSchemaError(f"dose_evidence.{field} binary64 hex mismatch")
    return number


def validate_dose_evidence(
    evidence: Mapping[str, Any] | None,
    *,
    estimator: str,
    generation_status: str,
    dose_valid: bool,
    expected_failure_code: str | None,
) -> dict[str, Any] | None:
    if evidence is None:
        raise RecordSchemaError("steered record lacks required dose provenance evidence")
    _exact_keys(evidence, DOSE_FIELDS, "dose evidence")
    if evidence["mu_estimator"] != estimator or evidence["generation_status"] != generation_status:
        raise RecordSchemaError("dose evidence estimator/generation status differs")
    _sha(evidence["mu_source_sha256"], "dose_evidence.mu_source_sha256")
    _sha(evidence["measurement_dose_sha256"], "dose_evidence.measurement_dose_sha256")
    if evidence["phase"] != "decode-only" or evidence["use_cache"] is not True:
        raise RecordSchemaError("dose evidence phase/cache differs")
    if dose_valid:
        if (
            expected_failure_code is not None
            or evidence["status"] != "VALIDATED"
            or evidence["failure_code"] is not None
        ):
            raise RecordSchemaError("valid dose flags require VALIDATED evidence")
        values = {field: _binary64(evidence[field], field, nullable=False) for field in _BINARY_FIELDS}
        if values["pre_hook_l2"] <= 0.0 or values["post_hook_l2"] <= 0.0:
            raise RecordSchemaError("dose hook norms must be positive")
        if values["relative_dose"].hex() != (values["alpha_post_dtype"] / values["pre_hook_l2"]).hex():
            raise RecordSchemaError("relative dose formula mismatch")
        if values["norm_ratio"].hex() != (values["post_hook_l2"] / values["pre_hook_l2"]).hex():
            raise RecordSchemaError("norm ratio formula mismatch")
        if not -1.0 <= values["vector_alignment"] <= 1.0 or not 0.0 <= values["cosine_drift"] <= 2.0:
            raise RecordSchemaError("dose geometry exceeds cosine bounds")
    else:
        if (
            expected_failure_code is None
            or evidence["status"] != "INVALID"
            or evidence["failure_code"] != expected_failure_code
        ):
            raise RecordSchemaError("invalid dose evidence failure_code differs from first dose failure")
        for field in _BINARY_FIELDS:
            if evidence[field] is not None:
                raise RecordSchemaError("invalid dose evidence must not retain numeric summaries")
    return dict(evidence)


RESPONSE_FLAGS = (
    "scheduled_identity_match", "generation_completed", "judge_eligible", "judge_label_parsed",
    "identity_complete", "identity_collision", "dose_denominator_valid", "dose_geometry_finite",
    "post_dtype_alpha_finite",
)
RESPONSE_TERMINALS = {
    "COMPLETED_PARSED",
    "NON_ESTIMABLE_IDENTITY",
    "NON_ESTIMABLE_DOSE",
    "TERMINAL_GENERATION_TECHNICAL_FAILURE",
    "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
    "TERMINAL_GENERATION_INDETERMINATE_FAILURE",
    "TERMINAL_PREJUDGE_FAILURE",
    "TERMINAL_JUDGE_FAILURE",
    "TERMINAL_JUDGE_INDETERMINATE_FAILURE",
}


def _generation_terminal(status: str) -> str:
    try:
        return {
            "TERMINAL_TECHNICAL_FAILURE": "TERMINAL_GENERATION_TECHNICAL_FAILURE",
            "TERMINAL_FAILURE": "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
            "TERMINAL_INDETERMINATE_FAILURE": "TERMINAL_GENERATION_INDETERMINATE_FAILURE",
        }[status]
    except KeyError as exc:
        raise RecordSchemaError(f"invalid failed generation terminal status: {status}") from exc


def _response_semantics(record: Mapping[str, Any], *, domain: str, steered: bool) -> dict[str, Any]:
    flags: dict[str, bool] = {}
    for field in RESPONSE_FLAGS:
        if not isinstance(record[field], bool):
            raise RecordSchemaError(f"{field} must be boolean")
        flags[field] = record[field]
    if flags["judge_eligible"] and not flags["generation_completed"]:
        raise RecordSchemaError("judge eligibility requires completed generation")
    if flags["judge_label_parsed"] and not flags["judge_eligible"]:
        raise RecordSchemaError("parsed label requires judge eligibility")
    if flags["judge_eligible"] is not (record["judge_record_sha256"] is not None):
        raise RecordSchemaError("judge record presence differs from judge eligibility")
    if flags["judge_label_parsed"]:
        if record["label"] not in JUDGE_LABELS[domain]:
            raise RecordSchemaError("parsed label is outside the domain")
    elif record["label"] is not None:
        raise RecordSchemaError("unparsed response must have a null label")
    dose_valid = all(
        flags[field]
        for field in ("dose_denominator_valid", "dose_geometry_finite", "post_dtype_alpha_finite")
    )
    expected_dose_failure = None
    if not flags["dose_denominator_valid"]:
        expected_dose_failure = "INVALID_DOSE_DENOMINATOR"
    elif not flags["dose_geometry_finite"]:
        expected_dose_failure = "INVALID_DOSE_GEOMETRY"
    elif not flags["post_dtype_alpha_finite"]:
        expected_dose_failure = "INVALID_POST_DTYPE_ALPHA"
    if steered:
        validate_dose_evidence(
            record["dose_evidence"],
            estimator=record["estimator"],
            generation_status=record["generation_terminal_status"],
            dose_valid=dose_valid,
            expected_failure_code=expected_dose_failure,
        )
    elif record["dose_evidence"] is not None or not dose_valid:
        raise RecordSchemaError("clean response dose fields are inconsistent")
    identity_failed = (
        not flags["scheduled_identity_match"]
        or not flags["identity_complete"]
        or flags["identity_collision"]
    )
    if identity_failed:
        terminal = "NON_ESTIMABLE_IDENTITY"
    elif not dose_valid:
        terminal = "NON_ESTIMABLE_DOSE"
    elif not flags["generation_completed"]:
        terminal = _generation_terminal(record["generation_terminal_status"])
    elif not flags["judge_eligible"]:
        terminal = "TERMINAL_PREJUDGE_FAILURE"
    elif not flags["judge_label_parsed"]:
        terminal = (
            "TERMINAL_JUDGE_INDETERMINATE_FAILURE"
            if record["judge_terminal_status"] == "TERMINAL_INDETERMINATE_FAILURE"
            else "TERMINAL_JUDGE_FAILURE"
        )
    else:
        terminal = "COMPLETED_PARSED"
    if terminal not in RESPONSE_TERMINALS or record["terminal_status"] != terminal:
        raise RecordSchemaError("response terminal status violates first-failure precedence")
    if record["retained"] is not (terminal == "COMPLETED_PARSED"):
        raise RecordSchemaError("retained status differs from terminal status")
    expected_missingness = None if terminal == "COMPLETED_PARSED" else terminal
    if record["missingness_code"] != expected_missingness:
        raise RecordSchemaError("missingness code differs from terminal status")
    if flags["generation_completed"] is not (record["generation_terminal_status"] == "COMPLETED"):
        raise RecordSchemaError("generation terminal status differs from completion flag")
    if flags["judge_label_parsed"] is not (record["judge_terminal_status"] == "PARSED"):
        raise RecordSchemaError("judge parsed flag differs from judge terminal status")
    if flags["judge_eligible"]:
        if record["judge_terminal_status"] not in {
            "PARSED", "TERMINAL_PARSE_OR_INFRASTRUCTURE_FAILURE", "TERMINAL_INDETERMINATE_FAILURE"
        }:
            raise RecordSchemaError("judge terminal status is invalid")
    elif record["judge_terminal_status"] is not None:
        raise RecordSchemaError("ineligible response must not claim judge terminal provenance")
    return dict(record)


P2_KEYS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible", "fake_backend",
    "logical_id", "identity_sha256", "generation_record_sha256", "judge_record_sha256",
    "cell", "prompt_id", "vector_id", "pair_id", "arm", "anchor", "estimator",
    *RESPONSE_FLAGS, "generation_terminal_status", "judge_terminal_status", "dose_evidence",
    "label", "terminal_status", "missingness_code", "retained", "record_sha256",
}


def validate_p2_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _schema(record, "p2_response_record")
    _exact_keys(record, P2_KEYS, "P2 record")
    if record["schema_version"] != "paper1-stage3-p2-response-record-v2" or record["protocol_version"] != PROTOCOL_VERSION:
        raise RecordSchemaError("invalid P2 schema/protocol version")
    validate_run_mode(record["run_mode"])
    if record["paper_result_eligible"] is not False or not isinstance(record["fake_backend"], bool):
        raise RecordSchemaError("invalid P2 eligibility/backend flags")
    for field in ("logical_id", "prompt_id", "vector_id", "pair_id"):
        _text(record[field], field)
    for field in ("identity_sha256", "generation_record_sha256"):
        _sha(record[field], field)
    _sha(record["judge_record_sha256"], "judge_record_sha256", nullable=True)
    expected = {
        "P2_A_all": ("all-token", "A", "mu_all_tw"),
        "P2_A_content": ("content-token", "A", "mu_content_tw"),
        "P2_T_all": ("all-token", "T", "mu_all_tw"),
        "P2_T_content": ("content-token", "T", "mu_content_tw"),
    }.get(record["cell"])
    if expected is None or (record["arm"], record["anchor"], record["estimator"]) != expected:
        raise RecordSchemaError("P2 cell/arm/anchor/estimator mapping changed")
    if record["pair_id"] != f"{record['anchor']}|{record['prompt_id']}|{record['vector_id']}":
        raise RecordSchemaError("P2 pair identity changed")
    result = _response_semantics(record, domain="harmful", steered=True)
    _record_hash(record)
    return result


BENIGN_KEYS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible", "fake_backend",
    "logical_id", "identity_sha256", "generation_record_sha256", "judge_record_sha256",
    "cell", "prompt_id", "vector_id", "anchor", "estimator", *RESPONSE_FLAGS,
    "generation_terminal_status", "judge_terminal_status", "dose_evidence", "label",
    "terminal_status", "missingness_code", "retained", "record_sha256",
}


def validate_benign_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _schema(record, "benign_response_record")
    _exact_keys(record, BENIGN_KEYS, "benign record")
    if record["schema_version"] != "paper1-stage3-benign-response-record-v2" or record["protocol_version"] != PROTOCOL_VERSION:
        raise RecordSchemaError("invalid benign schema/protocol version")
    validate_run_mode(record["run_mode"])
    if record["paper_result_eligible"] is not False or not isinstance(record["fake_backend"], bool):
        raise RecordSchemaError("invalid benign eligibility/backend flags")
    for field in ("logical_id", "prompt_id"):
        _text(record[field], field)
    for field in ("identity_sha256", "generation_record_sha256"):
        _sha(record[field], field)
    _sha(record["judge_record_sha256"], "judge_record_sha256", nullable=True)
    if record["cell"] == "benign_clean":
        if record["vector_id"] is not None or record["anchor"] != "clean" or record["estimator"] != "clean":
            raise RecordSchemaError("benign clean identity changed")
        steered = False
    elif record["cell"] == "benign_T":
        _text(record["vector_id"], "vector_id")
        if record["anchor"] != "T" or record["estimator"] != "mu_all_tw":
            raise RecordSchemaError("benign T identity changed")
        steered = True
    else:
        raise RecordSchemaError("invalid benign cell")
    result = _response_semantics(record, domain="benign", steered=steered)
    _record_hash(record)
    return result


SUPPORT_KEYS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible", "fake_backend",
    "logical_id", "identity_sha256", "generation_record_sha256", "judge_record_sha256",
    "prompt_id", "vector_id", "anchor", "estimator", *RESPONSE_FLAGS,
    "generation_terminal_status", "judge_terminal_status", "dose_evidence", "label",
    "terminal_status", "missingness_code", "retained", "record_sha256",
}


def validate_support_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _schema(record, "support_response_record")
    _exact_keys(record, SUPPORT_KEYS, "support record")
    if record["schema_version"] != "paper1-stage3-support-response-record-v1" or record["protocol_version"] != PROTOCOL_VERSION:
        raise RecordSchemaError("invalid support schema/protocol version")
    validate_run_mode(record["run_mode"])
    if record["paper_result_eligible"] is not False or not isinstance(record["fake_backend"], bool):
        raise RecordSchemaError("invalid support eligibility/backend flags")
    for field in ("logical_id", "prompt_id", "vector_id"):
        _text(record[field], field)
    for field in ("identity_sha256", "generation_record_sha256"):
        _sha(record[field], field)
    _sha(record["judge_record_sha256"], "judge_record_sha256", nullable=True)
    if record["anchor"] not in {"A", "T", "H"} or record["estimator"] != "mu_all_tw":
        raise RecordSchemaError("support anchor/estimator mapping changed")
    result = _response_semantics(record, domain="harmful", steered=True)
    _record_hash(record)
    return result


K1_KEYS = {
    "schema_version", "protocol_version", "run_mode", "paper_result_eligible", "fake_backend",
    "logical_id", "identity_sha256", "source_p2_logical_id", "source_p2_record_sha256",
    "cell", "prompt_id", "vector_id", "pair_id", "arm", "anchor", "estimator", "label",
    "retained", "generation_calls_added", "judge_calls_added", "record_sha256",
}


def validate_k1_record(record: Mapping[str, Any]) -> dict[str, Any]:
    _schema(record, "k1_reuse_record")
    _exact_keys(record, K1_KEYS, "K1 record")
    if record["schema_version"] != "paper1-stage3-k1-reuse-record-v2" or record["protocol_version"] != PROTOCOL_VERSION:
        raise RecordSchemaError("invalid K1 schema/protocol version")
    validate_run_mode(record["run_mode"])
    if record["paper_result_eligible"] is not False or not isinstance(record["fake_backend"], bool):
        raise RecordSchemaError("invalid K1 eligibility/backend flags")
    for field in ("logical_id", "source_p2_logical_id", "prompt_id", "vector_id", "pair_id"):
        _text(record[field], field)
    for field in ("identity_sha256", "source_p2_record_sha256"):
        _sha(record[field], field)
    if record["logical_id"] != record["source_p2_logical_id"]:
        raise RecordSchemaError("K1 must reuse the exact P2 logical identity")
    expected = {
        "P2_A_all": ("all-token", "A", "mu_all_tw"),
        "P2_A_content": ("content-token", "A", "mu_content_tw"),
        "P2_T_all": ("all-token", "T", "mu_all_tw"),
        "P2_T_content": ("content-token", "T", "mu_content_tw"),
    }.get(record["cell"])
    if expected is None or (record["arm"], record["anchor"], record["estimator"]) != expected:
        raise RecordSchemaError("K1 cell mapping differs from P2")
    if record["pair_id"] != f"{record['anchor']}|{record['prompt_id']}|{record['vector_id']}":
        raise RecordSchemaError("K1 pair identity changed")
    if record["label"] not in JUDGE_LABELS["harmful"] or record["retained"] is not True:
        raise RecordSchemaError("K1 requires one retained harmful P2 label")
    if _count(record["generation_calls_added"], "generation_calls_added") != 0 or _count(record["judge_calls_added"], "judge_calls_added") != 0:
        raise RecordSchemaError("K1 adds zero generation and judge calls")
    _record_hash(record)
    return dict(record)


def _source_lineage(
    record: Mapping[str, Any],
    *,
    registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    identity = registry.require(record["logical_id"])
    generation = validate_generation_record(generation_record)
    judge = validate_judge_record(judge_record) if judge_record is not None else None
    identity_hash = canonical_sha256(identity)
    if (
        generation["logical_id"] != record["logical_id"]
        or generation["identity_sha256"] != identity_hash
        or record["identity_sha256"] != identity_hash
        or record["generation_record_sha256"] != generation["record_sha256"]
        or record["generation_completed"] is not generation["generation_completed"]
        or record["run_mode"] != generation["run_mode"]
    ):
        raise RecordSchemaError("response generation lineage differs from registry/source records")
    if (
        "generation_terminal_status" in record
        and record["generation_terminal_status"] != generation["terminal_status"]
    ):
        raise RecordSchemaError("response generation terminal status differs from source record")
    if record["judge_eligible"]:
        if judge is None:
            raise RecordSchemaError("judge-eligible response lacks its judge record")
        if (
            judge["logical_id"] != record["logical_id"]
            or judge["identity_sha256"] != identity_hash
            or judge["generation_record_sha256"] != generation["record_sha256"]
            or judge["domain"] != identity["domain"]
            or judge["run_mode"] != record["run_mode"]
            or record["judge_record_sha256"] != judge["record_sha256"]
            or record["judge_label_parsed"] is not judge["judge_label_parsed"]
            or record["label"] != judge["label"]
        ):
            raise RecordSchemaError("response judge lineage differs from source records")
        if (
            "judge_terminal_status" in record
            and record["judge_terminal_status"] != judge["terminal_status"]
        ):
            raise RecordSchemaError("response judge terminal status differs from source record")
    elif judge is not None or record["judge_record_sha256"] is not None:
        raise RecordSchemaError("judge-ineligible response claims judge provenance")
    expected_fake = generation["fake_backend"] or (judge is not None and judge["fake_backend"])
    if record["fake_backend"] is not expected_fake:
        raise RecordSchemaError("response fake backend differs from source lineage")
    if "generation_fake_backend" in record and (
        record["generation_fake_backend"] is not generation["fake_backend"]
        or record["judge_fake_backend"] is not (
            None if judge is None else judge["fake_backend"]
        )
    ):
        raise RecordSchemaError("response backend provenance differs from source lineage")
    if "scheduled_identity_match" in record:
        if (
            record["scheduled_identity_match"] is not True
            or record["identity_complete"] is not True
            or record["identity_collision"] is not False
        ):
            raise RecordSchemaError("registered response may not self-report a forged identity state")
    return identity, generation, judge


def _terminal_producer_dose(
    generation: Mapping[str, Any], *, steered: bool
) -> dict[str, Any] | None:
    diagnostics = generation["attempts"][-1]["diagnostics"]
    evidence = diagnostics.get("dose_evidence")
    if steered:
        if not isinstance(evidence, Mapping):
            raise RecordSchemaError("steered terminal generation lacks producer dose evidence")
        return dict(evidence)
    if "dose_evidence" in diagnostics:
        raise RecordSchemaError("clean terminal generation claims dose evidence")
    return None


def _dose_source(
    record: Mapping[str, Any],
    *,
    identity: Mapping[str, Any],
    generation: Mapping[str, Any],
    dose_binding: Mapping[str, Any],
) -> None:
    if identity["estimator"] == "clean":
        if record["dose_evidence"] is not None:
            raise RecordSchemaError("clean response claims dose evidence")
        _terminal_producer_dose(generation, steered=False)
        return
    producer_evidence = _terminal_producer_dose(generation, steered=True)
    doses = validate_dose_binding(dose_binding)
    expected = doses[identity["anchor"]][identity["estimator"]]
    for field in ("c_hex", "alpha_pre_dtype_hex", "alpha_post_dtype_hex", "rho_hex"):
        if identity[field] != expected[field]:
            raise RecordSchemaError(f"logical identity differs from dose source: {field}")
    evidence = record["dose_evidence"]
    if not isinstance(evidence, Mapping):
        raise RecordSchemaError("steered response lacks dose source evidence")
    if canonical_sha256(evidence) != canonical_sha256(producer_evidence):
        raise RecordSchemaError("response dose evidence differs from terminal generation producer")
    if (
        evidence["measurement_dose_sha256"] != canonical_sha256(dose_binding)
        or evidence["mu_estimator"] != identity["estimator"]
        or evidence["mu_source_sha256"] != canonical_sha256(dose_binding[identity["estimator"]])
    ):
        raise RecordSchemaError("dose evidence provenance differs from actual dose source")
    if evidence["status"] == "VALIDATED":
        expected_hex = {
            "nominal_c": identity["c_hex"],
            "mu_value": float(dose_binding[identity["estimator"]]["value"]).hex(),
            "alpha_pre_dtype": identity["alpha_pre_dtype_hex"],
            "alpha_post_dtype": identity["alpha_post_dtype_hex"],
        }
        for field, value in expected_hex.items():
            if evidence[field]["binary64_hex"] != value:
                raise RecordSchemaError(f"dose evidence differs from identity: {field}")


def validate_p2_materialization(
    record: Mapping[str, Any], *, registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any], judge_record: Mapping[str, Any] | None,
    dose_binding: Mapping[str, Any],
) -> dict[str, Any]:
    validated = validate_p2_record(record)
    identity, generation, _ = _source_lineage(
        record, registry=registry, generation_record=generation_record, judge_record=judge_record
    )
    if (
        identity["block"] != record["cell"] or identity["domain"] != "harmful"
        or identity["prompt_id"] != record["prompt_id"] or identity["vector_id"] != record["vector_id"]
        or identity["anchor"] != record["anchor"] or identity["estimator"] != record["estimator"]
    ):
        raise RecordSchemaError("P2 response fields differ from registry identity")
    _dose_source(record, identity=identity, generation=generation, dose_binding=dose_binding)
    return validated


def validate_benign_materialization(
    record: Mapping[str, Any], *, registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any], judge_record: Mapping[str, Any] | None,
    dose_binding: Mapping[str, Any],
) -> dict[str, Any]:
    validated = validate_benign_record(record)
    identity, generation, _ = _source_lineage(
        record, registry=registry, generation_record=generation_record, judge_record=judge_record
    )
    if (
        identity["block"] != record["cell"] or identity["domain"] != "benign"
        or identity["prompt_id"] != record["prompt_id"] or identity["vector_id"] != record["vector_id"]
        or identity["anchor"] != record["anchor"] or identity["estimator"] != record["estimator"]
    ):
        raise RecordSchemaError("benign response fields differ from registry identity")
    _dose_source(record, identity=identity, generation=generation, dose_binding=dose_binding)
    return validated


def validate_support_materialization(
    record: Mapping[str, Any], *, registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any], judge_record: Mapping[str, Any] | None,
    dose_binding: Mapping[str, Any],
) -> dict[str, Any]:
    validated = validate_support_record(record)
    identity, generation, _ = _source_lineage(
        record, registry=registry, generation_record=generation_record, judge_record=judge_record
    )
    if (
        identity["block"] != "support" or identity["domain"] != "harmful"
        or identity["prompt_id"] != record["prompt_id"] or identity["vector_id"] != record["vector_id"]
        or identity["anchor"] != record["anchor"] or identity["estimator"] != record["estimator"]
    ):
        raise RecordSchemaError("support response fields differ from registry identity")
    _dose_source(record, identity=identity, generation=generation, dose_binding=dose_binding)
    return validated


def validate_response_materialization(
    record: Mapping[str, Any], *, registry: LogicalIdentityRegistry,
    generation_record: Mapping[str, Any], judge_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    validated = validate_response_record(record)
    identity, generation, judge = _source_lineage(
        record, registry=registry, generation_record=generation_record, judge_record=judge_record
    )
    if (
        identity["block"] != "harmful_clean"
        or identity["domain"] != "harmful"
        or identity["prompt_id"] != record["prompt_id"]
        or identity["vector_id"] is not None
        or identity["estimator"] != "clean"
        or identity["anchor"] != "clean"
        or record["block"] != identity["block"]
        or record["domain"] != identity["domain"]
        or record["vector_id"] is not None
    ):
        raise RecordSchemaError("harmful clean response differs from registry identity")
    _terminal_producer_dose(generation, steered=False)
    if not generation["generation_completed"]:
        expected_missingness = {
            "TERMINAL_TECHNICAL_FAILURE": "TERMINAL_GENERATION_TECHNICAL_FAILURE",
            "TERMINAL_FAILURE": "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
            "TERMINAL_INDETERMINATE_FAILURE": "TERMINAL_GENERATION_INDETERMINATE_FAILURE",
        }[generation["terminal_status"]]
    elif judge is None:
        expected_missingness = "TERMINAL_PREJUDGE_FAILURE"
    elif judge["terminal_status"] == "PARSED":
        expected_missingness = None
    elif judge["terminal_status"] == "TERMINAL_INDETERMINATE_FAILURE":
        expected_missingness = "TERMINAL_JUDGE_INDETERMINATE_FAILURE"
    else:
        expected_missingness = "TERMINAL_JUDGE_FAILURE"
    if record["missingness_code"] != expected_missingness:
        raise RecordSchemaError("harmful clean missingness differs from source terminal lineage")
    return validated


def validate_k1_materialization(
    record: Mapping[str, Any], *, registry: LogicalIdentityRegistry,
    source_p2_record: Mapping[str, Any], generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None, dose_binding: Mapping[str, Any],
) -> dict[str, Any]:
    validated = validate_k1_record(record)
    source = validate_p2_materialization(
        source_p2_record,
        registry=registry,
        generation_record=generation_record,
        judge_record=judge_record,
        dose_binding=dose_binding,
    )
    if not source["retained"]:
        raise RecordSchemaError("K1 source P2 record is not retained")
    checks = {
        "logical_id": source["logical_id"],
        "source_p2_logical_id": source["logical_id"],
        "source_p2_record_sha256": source["record_sha256"],
        "identity_sha256": source["identity_sha256"],
        "cell": source["cell"],
        "prompt_id": source["prompt_id"],
        "vector_id": source["vector_id"],
        "pair_id": source["pair_id"],
        "arm": source["arm"],
        "anchor": source["anchor"],
        "estimator": source["estimator"],
        "label": source["label"],
        "fake_backend": source["fake_backend"],
        "run_mode": source["run_mode"],
    }
    for field, expected in checks.items():
        if record[field] != expected:
            raise RecordSchemaError(f"K1 field differs from exact retained P2 source: {field}")
    return validated


def build_response_record(
    *, identity: Mapping[str, Any], generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None, missingness_code: str | None,
    dose_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a parsed or terminal response using only validated upstream records."""
    normalized = normalize_identity(identity)
    generation = validate_generation_record(generation_record)
    identity_sha = canonical_sha256(normalized)
    if generation["identity_sha256"] != identity_sha:
        raise RecordSchemaError("generation record does not match response identity")
    judge = validate_judge_record(judge_record) if judge_record is not None else None
    if judge is not None and (
        not generation["generation_completed"]
        or judge["logical_id"] != generation["logical_id"]
        or judge["identity_sha256"] != identity_sha
        or judge["generation_record_sha256"] != generation["record_sha256"]
        or judge["domain"] != normalized["domain"]
        or judge["run_mode"] != generation["run_mode"]
    ):
        raise RecordSchemaError("judge record does not match generation provenance")
    judge_eligible = judge is not None
    parsed = judge is not None and judge["judge_label_parsed"]
    fake = generation["fake_backend"] or (judge is not None and judge["fake_backend"])
    if normalized["block"] == "harmful_clean":
        if dose_evidence is not None:
            raise RecordSchemaError("clean response builder rejects dose evidence")
        _terminal_producer_dose(generation, steered=False)
        if parsed:
            code = None
        elif not generation["generation_completed"]:
            code = {
                "TERMINAL_TECHNICAL_FAILURE": "TERMINAL_GENERATION_TECHNICAL_FAILURE",
                "TERMINAL_FAILURE": "TERMINAL_GENERATION_DETERMINISTIC_FAILURE",
                "TERMINAL_INDETERMINATE_FAILURE": "TERMINAL_GENERATION_INDETERMINATE_FAILURE",
            }[generation["terminal_status"]]
        elif judge is None:
            code = "TERMINAL_PREJUDGE_FAILURE"
        elif judge["terminal_status"] == "TERMINAL_INDETERMINATE_FAILURE":
            code = "TERMINAL_JUDGE_INDETERMINATE_FAILURE"
        else:
            code = "TERMINAL_JUDGE_FAILURE"
        if missingness_code is not None and missingness_code != code:
            raise RecordSchemaError("caller missingness differs from derived harmful-clean terminal")
        record = {
            "schema_version": "paper1-stage3-response-record-v2",
            "protocol_version": PROTOCOL_VERSION,
            "run_mode": generation["run_mode"],
            "paper_result_eligible": False,
            "fake_backend": fake,
            "generation_fake_backend": generation["fake_backend"],
            "judge_fake_backend": None if judge is None else judge["fake_backend"],
            "logical_id": generation["logical_id"],
            "block": "harmful_clean",
            "domain": "harmful",
            "prompt_id": normalized["prompt_id"],
            "vector_id": None,
            "identity_sha256": identity_sha,
            "generation_record_sha256": generation["record_sha256"],
            "judge_record_sha256": None if judge is None else judge["record_sha256"],
            "generation_completed": generation["generation_completed"],
            "judge_eligible": judge_eligible,
            "judge_label_parsed": parsed,
            "label": None if judge is None else judge["label"],
            "missingness_code": code,
            "dose_evidence": None,
        }
        record["record_sha256"] = canonical_sha256(record)
        return validate_response_record(record)
    raise RecordSchemaError("use the block-specific response builder for steered or benign records")


def _dose_flags_from_producer_evidence(evidence: Mapping[str, Any]) -> dict[str, bool]:
    status = evidence.get("status")
    failure_code = evidence.get("failure_code")
    if status == "VALIDATED" and failure_code is None:
        return {
            "dose_denominator_valid": True,
            "dose_geometry_finite": True,
            "post_dtype_alpha_finite": True,
        }
    failure_flags = {
        "INVALID_DOSE_DENOMINATOR": {
            "dose_denominator_valid": False,
            "dose_geometry_finite": True,
            "post_dtype_alpha_finite": True,
        },
        "INVALID_DOSE_GEOMETRY": {
            "dose_denominator_valid": True,
            "dose_geometry_finite": False,
            "post_dtype_alpha_finite": True,
        },
        "INVALID_POST_DTYPE_ALPHA": {
            "dose_denominator_valid": True,
            "dose_geometry_finite": True,
            "post_dtype_alpha_finite": False,
        },
    }
    if status != "INVALID" or failure_code not in failure_flags:
        raise RecordSchemaError("producer dose evidence status/failure_code is not canonical")
    return failure_flags[failure_code]


def build_block_response_record(
    *,
    identity: Mapping[str, Any],
    generation_record: Mapping[str, Any],
    judge_record: Mapping[str, Any] | None,
    dose_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build one support, P2, or benign terminal record from validated sources."""
    normalized = normalize_identity(identity)
    if normalized["block"] == "harmful_clean":
        return build_response_record(
            identity=normalized,
            generation_record=generation_record,
            judge_record=judge_record,
            missingness_code=None,
            dose_evidence=dose_evidence,
        )
    generation = validate_generation_record(generation_record)
    identity_sha256 = canonical_sha256(normalized)
    if generation["identity_sha256"] != identity_sha256:
        raise RecordSchemaError("generation record does not match response identity")
    judge = validate_judge_record(judge_record) if judge_record is not None else None
    if judge is not None and (
        not generation["generation_completed"]
        or judge["logical_id"] != generation["logical_id"]
        or judge["identity_sha256"] != identity_sha256
        or judge["generation_record_sha256"] != generation["record_sha256"]
        or judge["domain"] != normalized["domain"]
        or judge["run_mode"] != generation["run_mode"]
    ):
        raise RecordSchemaError("judge record does not match generation provenance")
    steered = normalized["estimator"] != "clean"
    if steered:
        if not isinstance(dose_evidence, Mapping):
            raise RecordSchemaError("steered response builder requires caller dose evidence")
        producer_evidence = _terminal_producer_dose(generation, steered=True)
        if canonical_sha256(dose_evidence) != canonical_sha256(producer_evidence):
            raise RecordSchemaError(
                "caller dose evidence differs from terminal generation producer evidence"
            )
        dose_flags = _dose_flags_from_producer_evidence(producer_evidence)
        dose_valid = all(dose_flags.values())
    else:
        if dose_evidence is not None:
            raise RecordSchemaError("clean response may not contain dose evidence")
        _terminal_producer_dose(generation, steered=False)
        producer_evidence = None
        dose_flags = {
            "dose_denominator_valid": True,
            "dose_geometry_finite": True,
            "post_dtype_alpha_finite": True,
        }
        dose_valid = True
    parsed = judge is not None and judge["judge_label_parsed"]
    flags = {
        "scheduled_identity_match": True,
        "generation_completed": generation["generation_completed"],
        "judge_eligible": judge is not None,
        "judge_label_parsed": parsed,
        "identity_complete": True,
        "identity_collision": False,
        **dose_flags,
    }
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
    common = {
        "protocol_version": PROTOCOL_VERSION,
        "run_mode": generation["run_mode"],
        "paper_result_eligible": False,
        "fake_backend": generation["fake_backend"] or (judge is not None and judge["fake_backend"]),
        "logical_id": generation["logical_id"],
        "identity_sha256": identity_sha256,
        "generation_record_sha256": generation["record_sha256"],
        "judge_record_sha256": None if judge is None else judge["record_sha256"],
        "prompt_id": normalized["prompt_id"],
        "vector_id": normalized["vector_id"],
        **flags,
        "generation_terminal_status": generation["terminal_status"],
        "judge_terminal_status": None if judge is None else judge["terminal_status"],
        "dose_evidence": producer_evidence,
        "label": None if judge is None else judge["label"],
        "terminal_status": terminal,
        "missingness_code": None if terminal == "COMPLETED_PARSED" else terminal,
        "retained": terminal == "COMPLETED_PARSED",
    }
    block = normalized["block"]
    if block == "support":
        record = {
            "schema_version": "paper1-stage3-support-response-record-v1",
            **common,
            "anchor": normalized["anchor"],
            "estimator": normalized["estimator"],
        }
        validator = validate_support_record
    elif block.startswith("P2_"):
        arm = "all-token" if block.endswith("_all") else "content-token"
        record = {
            "schema_version": "paper1-stage3-p2-response-record-v2",
            **common,
            "cell": block,
            "pair_id": f"{normalized['anchor']}|{normalized['prompt_id']}|{normalized['vector_id']}",
            "arm": arm,
            "anchor": normalized["anchor"],
            "estimator": normalized["estimator"],
        }
        validator = validate_p2_record
    elif block in {"benign_T", "benign_clean"}:
        record = {
            "schema_version": "paper1-stage3-benign-response-record-v2",
            **common,
            "cell": block,
            "anchor": normalized["anchor"],
            "estimator": normalized["estimator"],
        }
        validator = validate_benign_record
    else:
        raise RecordSchemaError(f"unsupported block-specific response builder: {block}")
    record["record_sha256"] = canonical_sha256(record)
    return validator(record)


def build_k1_reuse_record(source_p2_record: Mapping[str, Any]) -> dict[str, Any]:
    """Materialize K1 metadata without adding a generation or judge identity."""
    source = validate_p2_record(source_p2_record)
    if not source["retained"]:
        raise RecordSchemaError("K1 can reuse only a retained P2 response")
    record = {
        "schema_version": "paper1-stage3-k1-reuse-record-v2",
        "protocol_version": PROTOCOL_VERSION,
        "run_mode": source["run_mode"],
        "paper_result_eligible": False,
        "fake_backend": source["fake_backend"],
        "logical_id": source["logical_id"],
        "identity_sha256": source["identity_sha256"],
        "source_p2_logical_id": source["logical_id"],
        "source_p2_record_sha256": source["record_sha256"],
        "cell": source["cell"],
        "prompt_id": source["prompt_id"],
        "vector_id": source["vector_id"],
        "pair_id": source["pair_id"],
        "arm": source["arm"],
        "anchor": source["anchor"],
        "estimator": source["estimator"],
        "label": source["label"],
        "retained": True,
        "generation_calls_added": 0,
        "judge_calls_added": 0,
    }
    record["record_sha256"] = canonical_sha256(record)
    return validate_k1_record(record)


VALIDATORS: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "generation": validate_generation_record,
    "judge": validate_judge_record,
    "response": validate_response_record,
    "p1": validate_p1_record,
    "p2": validate_p2_record,
    "k1": validate_k1_record,
    "benign": validate_benign_record,
    "support": validate_support_record,
}


def validate_record(record_type: str, record: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validator = VALIDATORS[record_type]
    except KeyError as exc:
        raise RecordSchemaError(f"unknown record type: {record_type}") from exc
    return validator(record)
