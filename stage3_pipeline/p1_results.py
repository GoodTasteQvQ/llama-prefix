"""Pure post-processing for Stage 3 P1 measurement results."""

from __future__ import annotations

import json
import math
import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .dose import P1DoseNonEstimable, validate_dose_binding
from .records import RecordSchemaError, validate_p1_record
from .statistics import reference_statistics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANCHOR_CONFIG = ROOT / "configs/stage3/qwen25_base_anchors_v1.json"
SCHEMA_VERSION = "paper1-stage3-p1-result-materialization-v1"
FORMAL_REPLICATES = 10_000
FORMAL_MIN_SUCCESS = 9_500
PAPER_SCHEDULED_COUNTS = {"harmful": 100, "benign": 100}
ANCHORS = ("A", "T", "H")
EXPECTED_RHO = {
    "A": 0.7499471265016073,
    "T": 0.9999295020021431,
    "H": 1.249911877502679,
}
EXPECTED_RHO_HEX = {
    "A": "0x1.7ff911dc1b6eap-1",
    "T": "0x1.fff6c27acf3e3p-1",
    "H": "0x1.3ffa398cc186ep+0",
}


class P1ResultInputInvalid(ValueError):
    """The raw P1 document does not satisfy the materializer input contract."""

    code = "P1_RESULT_INPUT_INVALID"


def _input_invalid(detail: str) -> None:
    raise P1ResultInputInvalid(f"{P1ResultInputInvalid.code}:{detail}")


def _reject_constant(value: str) -> None:
    _input_invalid(f"NONSTANDARD_JSON_CONSTANT:{value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _input_invalid(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_raw_measurement(path: Path) -> dict[str, Any]:
    """Strictly load one raw P1 measurement JSON document."""
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except P1ResultInputInvalid:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _input_invalid(f"RAW_JSON:{exc}")
    if not isinstance(value, dict):
        _input_invalid("RAW_DOCUMENT_NOT_OBJECT")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _input_invalid(f"{field}:NOT_OBJECT")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        _input_invalid(f"{field}:NOT_ARRAY")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        _input_invalid(f"{field}:NOT_BOOLEAN")
    return value


def _count(value: Any, field: str, *, nullable: bool = False) -> int | None:
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _input_invalid(f"{field}:NOT_NONNEGATIVE_INTEGER")
    return value


def _finite_nonnegative(value: Any, field: str, *, nullable: bool = False) -> float | None:
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _input_invalid(f"{field}:NOT_NUMBER")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        _input_invalid(f"{field}:NONFINITE_OR_NEGATIVE")
    return number


def _positions(value: Any, field: str) -> list[int]:
    raw = _list(value, field)
    positions: list[int] = []
    for index, position in enumerate(raw):
        actual = _count(position, f"{field}[{index}]")
        assert actual is not None
        positions.append(actual)
    if len(positions) != len(set(positions)):
        _input_invalid(f"{field}:DUPLICATE_POSITION")
    return positions


def _prompt_identity(
    prompt: Mapping[str, Any], extraction: Mapping[str, Any], index: int
) -> tuple[str, str, str]:
    prefix = f"prompt_measurements[{index}]"
    domain = prompt.get("domain")
    if domain not in {"harmful", "benign"}:
        _input_invalid(f"{prefix}.prompt.domain:INVALID")
    extraction_domain = extraction.get("domain")
    if extraction_domain is not None and extraction_domain != domain:
        _input_invalid(f"{prefix}.extraction.domain:MISMATCH")

    identity_sha256 = prompt.get("identity_sha256")
    if (
        not isinstance(identity_sha256, str)
        or len(identity_sha256) != 64
        or any(character not in "0123456789abcdef" for character in identity_sha256)
    ):
        _input_invalid(f"{prefix}.prompt.identity_sha256:INVALID")
    for field in ("identity_sha256", "prompt_identity_sha256"):
        extracted_identity = extraction.get(field)
        if extracted_identity is not None and extracted_identity != identity_sha256:
            _input_invalid(f"{prefix}.extraction.{field}:MISMATCH")

    raw_prompt_id = prompt.get("prompt_id", prompt.get("source_id"))
    if isinstance(raw_prompt_id, bool) or not isinstance(raw_prompt_id, (str, int)):
        _input_invalid(f"{prefix}.prompt.prompt_id:INVALID")
    prompt_id = str(raw_prompt_id)
    if not prompt_id:
        _input_invalid(f"{prefix}.prompt.prompt_id:EMPTY")
    extracted_prompt_id = extraction.get("prompt_id", extraction.get("source_id"))
    if extracted_prompt_id is not None and str(extracted_prompt_id) != prompt_id:
        _input_invalid(f"{prefix}.extraction.prompt_id:MISMATCH")
    return domain, prompt_id, identity_sha256


def _validated_norms(
    measurement: Mapping[str, Any], *, index: int, forward_complete: bool
) -> tuple[int | None, list[float] | None]:
    prefix = f"prompt_measurements[{index}].measurement"
    activation_count = _count(
        measurement.get("activation_token_count"),
        f"{prefix}.activation_token_count",
        nullable=True,
    )
    raw_norms = measurement.get("token_norms_float32")
    if raw_norms is None:
        if activation_count is not None or forward_complete:
            _input_invalid(f"{prefix}.token_norms_float32:MISSING_FOR_ACTIVATION")
        return None, None
    if activation_count is None:
        _input_invalid(f"{prefix}.activation_token_count:MISSING_FOR_NORMS")
    norm_items = _list(raw_norms, f"{prefix}.token_norms_float32")
    if len(norm_items) != activation_count:
        _input_invalid(f"{prefix}:TOKEN_COUNT_MISMATCH")
    norms = [
        float(_finite_nonnegative(value, f"{prefix}.token_norms_float32[{position}]"))
        for position, value in enumerate(norm_items)
    ]
    return activation_count, norms


def build_complete_case_frame(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate raw terminal records and rebuild the complete-case token frame."""
    document = _mapping(raw, "raw")
    for field in ("run_mode", "prompt_measurements", "p1_terminal_records"):
        if field not in document:
            _input_invalid(f"MISSING_ROOT_FIELD:{field}")
    run_mode = document["run_mode"]
    if run_mode not in {"smoke", "pilot", "paper"}:
        _input_invalid("run_mode:INVALID")
    prompt_measurements = _list(document["prompt_measurements"], "prompt_measurements")
    terminal_records = _list(document["p1_terminal_records"], "p1_terminal_records")
    if len(prompt_measurements) != len(terminal_records):
        _input_invalid("PROMPT_AND_TERMINAL_COUNTS_DIFFER")

    strata: dict[str, list[dict[str, Any]]] = {"harmful": [], "benign": []}
    scheduled_counts = {"harmful": 0, "benign": 0}
    complete_case_prompt_ids = {"harmful": [], "benign": []}
    complete_case_identities: list[dict[str, str]] = []
    excluded_prompts: list[dict[str, str]] = []
    content_norms: list[float] = []
    all_identity_hashes: list[str] = []
    all_logical_ids: list[str] = []
    all_domain_prompt_ids: list[tuple[str, str]] = []

    for index, (raw_detail, raw_record) in enumerate(
        zip(prompt_measurements, terminal_records, strict=True)
    ):
        detail = _mapping(raw_detail, f"prompt_measurements[{index}]")
        for field in ("prompt", "extraction", "measurement"):
            if field not in detail:
                _input_invalid(f"prompt_measurements[{index}]:MISSING_{field.upper()}")
        prompt = _mapping(detail["prompt"], f"prompt_measurements[{index}].prompt")
        extraction = _mapping(
            detail["extraction"], f"prompt_measurements[{index}].extraction"
        )
        measurement = _mapping(
            detail["measurement"], f"prompt_measurements[{index}].measurement"
        )
        try:
            record = validate_p1_record(
                _mapping(raw_record, f"p1_terminal_records[{index}]")
            )
        except (RecordSchemaError, TypeError, ValueError) as exc:
            _input_invalid(f"p1_terminal_records[{index}]:{exc}")

        domain, prompt_id, identity_sha256 = _prompt_identity(prompt, extraction, index)
        if record["run_mode"] != run_mode:
            _input_invalid(f"p1_terminal_records[{index}].run_mode:MISMATCH")
        expected_identity = (domain, prompt_id, identity_sha256)
        observed_identity = (
            record["domain"],
            record["prompt_id"],
            record["identity_sha256"],
        )
        if observed_identity != expected_identity:
            _input_invalid(f"p1_terminal_records[{index}]:IDENTITY_MISMATCH")

        required_extraction_fields = (
            "valid_token_positions",
            "content_token_positions",
            "unresolved_valid_token_count",
            "render_complete",
            "valid_mask_complete",
        )
        for field in required_extraction_fields:
            if field not in extraction:
                _input_invalid(f"prompt_measurements[{index}].extraction:MISSING_{field}")
        required_measurement_fields = (
            "token_norms_float32",
            "forward_complete",
            "required_norms_finite",
            "activation_token_count",
            "all_norm_sum",
            "content_norm_sum",
        )
        for field in required_measurement_fields:
            if field not in measurement:
                _input_invalid(f"prompt_measurements[{index}].measurement:MISSING_{field}")

        render_complete = _boolean(
            extraction["render_complete"],
            f"prompt_measurements[{index}].extraction.render_complete",
        )
        valid_mask_complete = _boolean(
            extraction["valid_mask_complete"],
            f"prompt_measurements[{index}].extraction.valid_mask_complete",
        )
        forward_complete = _boolean(
            measurement["forward_complete"],
            f"prompt_measurements[{index}].measurement.forward_complete",
        )
        required_norms_finite = _boolean(
            measurement["required_norms_finite"],
            f"prompt_measurements[{index}].measurement.required_norms_finite",
        )
        if (
            render_complete != record["render_complete"]
            or valid_mask_complete != record["valid_mask_complete"]
            or forward_complete != record["forward_complete"]
            or required_norms_finite != record["required_norms_finite"]
        ):
            _input_invalid(f"prompt_measurements[{index}]:TERMINAL_FLAG_MISMATCH")

        valid_positions = _positions(
            extraction["valid_token_positions"],
            f"prompt_measurements[{index}].extraction.valid_token_positions",
        )
        content_positions = _positions(
            extraction["content_token_positions"],
            f"prompt_measurements[{index}].extraction.content_token_positions",
        )
        if not set(content_positions).issubset(valid_positions):
            _input_invalid(f"prompt_measurements[{index}]:CONTENT_NOT_SUBSET_OF_VALID")
        unresolved = _count(
            extraction["unresolved_valid_token_count"],
            f"prompt_measurements[{index}].extraction.unresolved_valid_token_count",
        )
        assert unresolved is not None
        unresolved_positions = extraction.get("unresolved_valid_token_positions")
        if unresolved_positions is not None:
            parsed_unresolved = _positions(
                unresolved_positions,
                f"prompt_measurements[{index}].extraction.unresolved_valid_token_positions",
            )
            if len(parsed_unresolved) != unresolved or not set(parsed_unresolved).issubset(
                valid_positions
            ):
                _input_invalid(f"prompt_measurements[{index}]:UNRESOLVED_COUNT_MISMATCH")
        if unresolved != record["unresolved_valid_token_count"]:
            _input_invalid(f"prompt_measurements[{index}]:TERMINAL_UNRESOLVED_MISMATCH")

        valid_count = len(valid_positions)
        content_count = len(content_positions)
        if record["valid_token_count"] != valid_count or record["content_token_count"] != content_count:
            _input_invalid(f"prompt_measurements[{index}]:TERMINAL_POSITION_COUNT_MISMATCH")
        for field, recomputed in (
            ("valid_token_count", valid_count),
            ("content_token_count", content_count),
        ):
            if field in extraction and _count(
                extraction[field], f"prompt_measurements[{index}].extraction.{field}"
            ) != recomputed:
                _input_invalid(f"prompt_measurements[{index}].extraction.{field}:MISMATCH")

        _finite_nonnegative(
            measurement["all_norm_sum"],
            f"prompt_measurements[{index}].measurement.all_norm_sum",
            nullable=True,
        )
        _finite_nonnegative(
            measurement["content_norm_sum"],
            f"prompt_measurements[{index}].measurement.content_norm_sum",
            nullable=True,
        )
        activation_count, norms = _validated_norms(
            measurement, index=index, forward_complete=forward_complete
        )
        if norms is not None:
            assert activation_count is not None
            if any(position >= activation_count for position in valid_positions):
                _input_invalid(f"prompt_measurements[{index}]:TOKEN_POSITION_OUT_OF_RANGE")
        if required_norms_finite and (
            norms is None
            or measurement["all_norm_sum"] is None
            or measurement["content_norm_sum"] is None
        ):
            _input_invalid(f"prompt_measurements[{index}]:FINITE_NORM_PAYLOAD_INCOMPLETE")

        scheduled_counts[domain] += 1
        all_identity_hashes.append(identity_sha256)
        all_logical_ids.append(record["logical_id"])
        all_domain_prompt_ids.append((domain, prompt_id))
        identity_entry = {
            "domain": domain,
            "prompt_id": prompt_id,
            "identity_sha256": identity_sha256,
        }
        if record["complete_case"]:
            if norms is None or not forward_complete or not required_norms_finite:
                _input_invalid(f"prompt_measurements[{index}]:COMPLETE_CASE_MISSING_NORMS")
            all_sum = math.fsum(norms[position] for position in valid_positions)
            content_sum = math.fsum(norms[position] for position in content_positions)
            if not math.isfinite(all_sum) or not math.isfinite(content_sum):
                _input_invalid(f"prompt_measurements[{index}]:RECOMPUTED_SUM_NONFINITE")
            strata[domain].append(
                {
                    "prompt_id": prompt_id,
                    "v_sum": all_sum,
                    "c_sum": content_sum,
                    "v_count": valid_count,
                    "c_count": content_count,
                }
            )
            complete_case_prompt_ids[domain].append(prompt_id)
            complete_case_identities.append(identity_entry)
            content_norms.extend(norms[position] for position in content_positions)
        else:
            excluded_prompts.append(
                {**identity_entry, "reason": str(record["exclusion_reason"])}
            )

    identities_unique = (
        len(all_identity_hashes) == len(set(all_identity_hashes))
        and len(all_logical_ids) == len(set(all_logical_ids))
        and len(all_domain_prompt_ids) == len(set(all_domain_prompt_ids))
    )
    complete_counts = {domain: len(strata[domain]) for domain in strata}
    excluded_counts = {
        domain: scheduled_counts[domain] - complete_counts[domain] for domain in strata
    }
    return {
        "run_mode": run_mode,
        "terminal_record_count": len(terminal_records),
        "scheduled_counts": {**scheduled_counts, "total": sum(scheduled_counts.values())},
        "complete_counts": {**complete_counts, "total": sum(complete_counts.values())},
        "excluded_counts": {**excluded_counts, "total": sum(excluded_counts.values())},
        "complete_case_prompt_ids": complete_case_prompt_ids,
        "complete_case_identities": complete_case_identities,
        "excluded_prompts": excluded_prompts,
        "prompt_identities_unique": identities_unique,
        "strata": strata,
        "content_norms": content_norms,
    }


def _frame_output(frame: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_mode": frame["run_mode"],
        "scheduled_counts": frame["scheduled_counts"],
        "terminal_record_count": frame["terminal_record_count"],
        "complete_counts": frame["complete_counts"],
        "excluded_counts": frame["excluded_counts"],
        "complete_case_prompt_ids": frame["complete_case_prompt_ids"],
        "complete_case_identities": frame["complete_case_identities"],
        "excluded_prompt_ids": [
            entry["prompt_id"] for entry in frame["excluded_prompts"]
        ],
        "exclusion_reasons": frame["excluded_prompts"],
        "formal_experiment_run": False,
        "paper_result_eligible": False,
    }


def _nonestimable(
    frame: Mapping[str, Any], reason: str, *, detail: str | None = None
) -> dict[str, Any]:
    result = {
        **_frame_output(frame),
        "status": "P1_RESULT_NON_ESTIMABLE",
        "reason": reason,
        "pooled_statistics": None,
        "bootstrap_summary": None,
        "median_content_norm_Qwen": None,
        "dose_binding": None,
    }
    if detail is not None:
        result["reason_detail"] = detail
    return result


def _paper_frame_reason(frame: Mapping[str, Any]) -> str | None:
    if not frame["prompt_identities_unique"]:
        return "P1_PROMPT_IDENTITY_NOT_UNIQUE"
    if frame["run_mode"] != "paper":
        return "P1_DEVELOPMENT_DIAGNOSTIC_INPUT"
    scheduled = frame["scheduled_counts"]
    if (
        scheduled["harmful"] != PAPER_SCHEDULED_COUNTS["harmful"]
        or scheduled["benign"] != PAPER_SCHEDULED_COUNTS["benign"]
        or scheduled["total"] != 200
        or frame["terminal_record_count"] != 200
    ):
        return "P1_PAPER_SCHEDULED_FRAME_INCOMPLETE"
    return None


def _pooled_totals(strata: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_domain: dict[str, dict[str, Any]] = {}
    for domain in ("harmful", "benign"):
        rows = strata[domain]
        by_domain[domain] = {
            "all_norm_sum": math.fsum(float(row["v_sum"]) for row in rows),
            "content_norm_sum": math.fsum(float(row["c_sum"]) for row in rows),
            "valid_token_count": sum(int(row["v_count"]) for row in rows),
            "content_token_count": sum(int(row["c_count"]) for row in rows),
        }
    pooled = {
        "all_norm_sum": math.fsum(by_domain[d]["all_norm_sum"] for d in by_domain),
        "content_norm_sum": math.fsum(
            by_domain[d]["content_norm_sum"] for d in by_domain
        ),
        "valid_token_count": sum(by_domain[d]["valid_token_count"] for d in by_domain),
        "content_token_count": sum(
            by_domain[d]["content_token_count"] for d in by_domain
        ),
    }
    return {"pooled": pooled, "by_domain": by_domain}


def compute_p1_statistics(
    frame: Mapping[str, Any],
    *,
    replicates: int = FORMAL_REPLICATES,
    min_success: int = FORMAL_MIN_SUCCESS,
) -> dict[str, Any]:
    """Compute P1 statistics from one already rebuilt complete-case frame."""
    if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates < 2:
        raise ValueError("replicates must be an integer of at least two")
    if (
        isinstance(min_success, bool)
        or not isinstance(min_success, int)
        or not 1 <= min_success <= replicates
    ):
        raise ValueError("min_success must be in [1, replicates]")
    strata = frame["strata"]
    if any(len(strata[domain]) < 2 for domain in ("harmful", "benign")):
        raise reference_statistics.NonEstimable(
            "p1_each_complete_case_stratum_requires_at_least_two_prompts"
        )
    totals = _pooled_totals(strata)
    if totals["pooled"]["content_token_count"] == 0:
        raise reference_statistics.NonEstimable("p1_pooled_content_denominator_zero")
    if any(
        totals["by_domain"][domain]["content_token_count"] == 0
        for domain in ("harmful", "benign")
    ):
        raise reference_statistics.NonEstimable("p1_equal_domain_content_denominator_zero")

    interval = reference_statistics.p1_interval(
        strata, replicates=replicates, min_success=min_success
    )
    point = interval["point"]
    required_point = (
        "mu_all_tw",
        "mu_content_tw",
        "delta_select_tw",
        "ratio_select_tw",
        "w_v_harmful",
        "w_v_benign",
        "w_c_harmful",
        "w_c_benign",
        "mu_all_tw_equal_domain",
        "mu_content_tw_equal_domain",
        "delta_select_tw_equal_domain",
    )
    if any(
        name not in point
        or isinstance(point[name], bool)
        or not isinstance(point[name], (int, float))
        or not math.isfinite(float(point[name]))
        for name in required_point
    ):
        raise reference_statistics.NonEstimable("p1_point_nonfinite_or_missing")
    if not frame["content_norms"]:
        raise reference_statistics.NonEstimable("p1_pooled_content_denominator_zero")
    median_content = float(statistics.median(frame["content_norms"]))
    if not math.isfinite(median_content):
        raise reference_statistics.NonEstimable("p1_median_content_nonfinite")

    failures = interval["failures"]
    successful = int(interval["replicates_successful"])
    requested = int(interval["replicates_requested"])
    pooled_statistics = {
        "pooled_sums_and_counts": totals["pooled"],
        "domain_sums_and_counts": totals["by_domain"],
        "mu_all_tw_Qwen": float(point["mu_all_tw"]),
        "mu_content_tw_Qwen": float(point["mu_content_tw"]),
        "delta_select_tw": float(point["delta_select_tw"]),
        "ratio_select_tw": float(point["ratio_select_tw"]),
        "token_shares": {
            "all": {
                "harmful": float(point["w_v_harmful"]),
                "benign": float(point["w_v_benign"]),
            },
            "content": {
                "harmful": float(point["w_c_harmful"]),
                "benign": float(point["w_c_benign"]),
            },
        },
        "equal_domain_sensitivity": {
            "mu_all_tw": float(point["mu_all_tw_equal_domain"]),
            "mu_content_tw": float(point["mu_content_tw_equal_domain"]),
            "delta_select_tw": float(point["delta_select_tw_equal_domain"]),
        },
    }
    bootstrap_summary = {
        "algorithm": interval["algorithm"],
        "replicates_requested": requested,
        "replicates_successful": successful,
        "replicates_failed": requested - successful,
        "replicates_required": int(interval["replicates_required"]),
        "failures": failures,
        "intervals": interval["intervals"],
        "gate_delta_gt_0_10": interval["gate_delta_gt_0_10"],
        "claim_ratio_gt_1_5": interval["claim_ratio_gt_1_5"],
    }
    return {
        "pooled_statistics": pooled_statistics,
        "bootstrap_summary": bootstrap_summary,
        "median_content_norm_Qwen": median_content,
    }


def _binary64(value: float) -> dict[str, Any]:
    return {"value": value, "binary64_hex": value.hex()}


def _strict_anchor_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"nonstandard JSON constant: {value}")
            ),
            object_pairs_hook=lambda pairs: _anchor_object(pairs),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise P1DoseNonEstimable(f"P1_DOSE_NON_ESTIMABLE:ANCHOR_CONFIG:{exc}") from exc
    if not isinstance(config, dict):
        raise P1DoseNonEstimable("P1_DOSE_NON_ESTIMABLE:ANCHOR_CONFIG_NOT_OBJECT")
    return config


def _anchor_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate anchor config key: {key}")
        result[key] = value
    return result


def build_measurement_dose_binding(
    pooled_statistics: Mapping[str, Any],
    median_content_norm: Any,
    *,
    anchor_config_path: Path = DEFAULT_ANCHOR_CONFIG,
) -> dict[str, Any]:
    """Materialize and validate the fixed P1 measurement dose binding."""
    try:
        mu_all = float(pooled_statistics["mu_all_tw_Qwen"])
        mu_content = float(pooled_statistics["mu_content_tw_Qwen"])
        median = float(median_content_norm)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise P1DoseNonEstimable("P1_DOSE_NON_ESTIMABLE:MISSING_STATISTIC") from exc
    if not all(math.isfinite(value) and value > 0.0 for value in (mu_all, mu_content, median)):
        raise P1DoseNonEstimable("P1_DOSE_NON_ESTIMABLE:INVALID_STATISTIC")

    config = _strict_anchor_config(anchor_config_path)
    if (
        config.get("schema_version") != "paper1-stage3-qwen25-base-anchors-v1"
        or config.get("status") != "design_selected"
        or config.get("formal_experiment_run") is not False
    ):
        raise P1DoseNonEstimable("P1_DOSE_NON_ESTIMABLE:ANCHOR_CONFIG_IDENTITY")
    rho_by_anchor = config.get("rho_by_anchor")
    rho_hex = config.get("rho_binary64_hex")
    if (
        not isinstance(rho_by_anchor, Mapping)
        or tuple(rho_by_anchor) != ANCHORS
        or not isinstance(rho_hex, Mapping)
        or tuple(rho_hex) != ANCHORS
    ):
        raise P1DoseNonEstimable("P1_DOSE_NON_ESTIMABLE:ANCHOR_ORDER")

    anchors: list[dict[str, Any]] = []
    for anchor in ANCHORS:
        rho = rho_by_anchor[anchor]
        if (
            isinstance(rho, bool)
            or not isinstance(rho, (int, float))
            or float(rho).hex() != EXPECTED_RHO_HEX[anchor]
            or float(rho) != EXPECTED_RHO[anchor]
            or rho_hex[anchor] != EXPECTED_RHO_HEX[anchor]
        ):
            raise P1DoseNonEstimable(
                f"P1_DOSE_NON_ESTIMABLE:RHO_MISMATCH:{anchor}"
            )
        rho_value = float(rho)
        c_value = rho_value * median / mu_all
        alpha_by_estimator: dict[str, Any] = {}
        for estimator, mu in (("mu_all_tw", mu_all), ("mu_content_tw", mu_content)):
            alpha_pre = c_value * mu
            alpha_by_estimator[estimator] = {
                "pre_dtype": _binary64(alpha_pre),
                "post_dtype": _binary64(alpha_pre),
            }
        anchors.append(
            {
                "anchor": anchor,
                "rho": _binary64(rho_value),
                "c": _binary64(c_value),
                "alpha_by_estimator": alpha_by_estimator,
            }
        )
    document = {
        "schema_version": "paper1-stage3-measurement-dose-v1",
        "protocol_version": "paper1-stage3-current-v1",
        "status": "ESTIMABLE",
        "mu_all_tw": _binary64(mu_all),
        "mu_content_tw": _binary64(mu_content),
        "median_content_norm": _binary64(median),
        "anchors": anchors,
    }
    try:
        validate_dose_binding(document)
        # This helper performs the repository's canonical CPU bfloat16 round trip.
        from .real_backend import bind_dose_post_dtype

        bound = bind_dose_post_dtype(document, dtype="bfloat16")
        validate_dose_binding(bound)
    except P1DoseNonEstimable:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise P1DoseNonEstimable(f"P1_DOSE_NON_ESTIMABLE:{exc}") from exc
    return bound


def materialize_p1_results(
    raw: Mapping[str, Any],
    *,
    anchor_config_path: Path = DEFAULT_ANCHOR_CONFIG,
    replicates: int = FORMAL_REPLICATES,
    min_success: int = FORMAL_MIN_SUCCESS,
) -> dict[str, Any]:
    """Create one result/dose manifest without executing any model operation."""
    frame = build_complete_case_frame(raw)
    frame_reason = _paper_frame_reason(frame)
    if frame_reason is not None:
        return _nonestimable(frame, frame_reason)
    try:
        statistics_result = compute_p1_statistics(
            frame, replicates=replicates, min_success=min_success
        )
    except reference_statistics.NonEstimable as exc:
        return _nonestimable(frame, "P1_STATISTICS_NON_ESTIMABLE", detail=str(exc))
    try:
        dose_binding = build_measurement_dose_binding(
            statistics_result["pooled_statistics"],
            statistics_result["median_content_norm_Qwen"],
            anchor_config_path=anchor_config_path,
        )
    except P1DoseNonEstimable as exc:
        return {
            **_frame_output(frame),
            **statistics_result,
            "status": "P1_DOSE_NON_ESTIMABLE",
            "reason": "P1_DOSE_NON_ESTIMABLE",
            "reason_detail": str(exc),
            "dose_binding": None,
        }
    return {
        **_frame_output(frame),
        **statistics_result,
        "status": "ESTIMABLE",
        "dose_binding": dose_binding,
    }


def materialize_p1_results_file(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Materialize one strict input file into a new, non-overwriting output file."""
    if output_path.exists() or output_path.is_symlink():
        _input_invalid(f"OUTPUT_EXISTS:{output_path}")
    raw = load_raw_measurement(input_path)
    result = materialize_p1_results(raw)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("x", encoding="utf-8") as handle:
            json.dump(
                result,
                handle,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                indent=2,
            )
            handle.write("\n")
    except FileExistsError as exc:
        _input_invalid(f"OUTPUT_EXISTS:{output_path}")
    return result
