"""Validation and materialization of Stage 3 P1 dose values."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .core import PipelineError, canonical_sha256


class P1DoseNonEstimable(PipelineError):
    code = "P1_DOSE_NON_ESTIMABLE"


def _fail(detail: str) -> None:
    raise P1DoseNonEstimable(f"{P1DoseNonEstimable.code}:{detail}")


def _binary64(item: Any, field: str, *, positive: bool = False) -> float:
    if not isinstance(item, Mapping) or set(item) != {"value", "binary64_hex"}:
        _fail(f"INVALID_BINARY64_OBJECT:{field}")
    value = item["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"INVALID_NUMBER:{field}")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0.0):
        _fail(f"NONFINITE_OR_NONPOSITIVE:{field}")
    if item["binary64_hex"] != number.hex():
        _fail(f"BINARY64_HEX_MISMATCH:{field}")
    return number


def validate_dose_binding(document: Mapping[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    """Validate formula, binary64 identity, and anchor ordering."""
    required = {
        "schema_version",
        "protocol_version",
        "status",
        "mu_all_tw",
        "mu_content_tw",
        "median_content_norm",
        "anchors",
    }
    if set(document) != required:
        _fail("DOCUMENT_KEYS")
    if document["schema_version"] != "paper1-stage3-measurement-dose-v1":
        _fail("SCHEMA_VERSION")
    if document["protocol_version"] != "paper1-stage3-current-v1":
        _fail("PROTOCOL_VERSION")
    if document["status"] != "ESTIMABLE":
        _fail("STATUS_NOT_ESTIMABLE")

    mu_all = _binary64(document["mu_all_tw"], "mu_all_tw", positive=True)
    mu_content = _binary64(document["mu_content_tw"], "mu_content_tw", positive=True)
    median = _binary64(document["median_content_norm"], "median_content_norm", positive=True)
    anchors = document["anchors"]
    if (
        not isinstance(anchors, list)
        or [entry.get("anchor") for entry in anchors if isinstance(entry, Mapping)] != ["A", "T", "H"]
    ):
        _fail("ANCHOR_ORDER")

    rho_values: list[float] = []
    result: dict[str, dict[str, dict[str, str]]] = {}
    for entry in anchors:
        if not isinstance(entry, Mapping) or set(entry) != {"anchor", "rho", "c", "alpha_by_estimator"}:
            _fail("ANCHOR_KEYS")
        anchor = entry["anchor"]
        rho = _binary64(entry["rho"], f"rho_{anchor}", positive=True)
        c_value = _binary64(entry["c"], f"c_{anchor}", positive=True)
        if c_value.hex() != (rho * median / mu_all).hex():
            _fail(f"C_FORMULA_MISMATCH:{anchor}")
        alpha_map = entry["alpha_by_estimator"]
        if not isinstance(alpha_map, Mapping) or set(alpha_map) != {"mu_all_tw", "mu_content_tw"}:
            _fail(f"ALPHA_ESTIMATOR_SET:{anchor}")
        result[anchor] = {}
        for estimator, mu in (("mu_all_tw", mu_all), ("mu_content_tw", mu_content)):
            alpha = alpha_map[estimator]
            if not isinstance(alpha, Mapping) or set(alpha) != {"pre_dtype", "post_dtype"}:
                _fail(f"ALPHA_KEYS:{anchor}:{estimator}")
            pre = _binary64(alpha["pre_dtype"], f"alpha_pre:{anchor}:{estimator}")
            post = _binary64(alpha["post_dtype"], f"alpha_post:{anchor}:{estimator}")
            if pre.hex() != (c_value * mu).hex():
                _fail(f"ALPHA_FORMULA_MISMATCH:{anchor}:{estimator}")
            actual_rho = post / median
            if not math.isfinite(actual_rho):
                _fail(f"ACTUAL_RHO_NONFINITE:{anchor}:{estimator}")
            result[anchor][estimator] = {
                "c_hex": c_value.hex(),
                "alpha_pre_dtype_hex": pre.hex(),
                "alpha_post_dtype_hex": post.hex(),
                "rho_hex": actual_rho.hex(),
            }
        rho_values.append(rho)
    if not (0.0 < rho_values[0] < rho_values[1] < rho_values[2]):
        _fail("RHO_STRICT_ORDER")
    return result


def build_test_dose_binding(
    *,
    mu_all_tw: float,
    mu_content_tw: float,
    median_content_norm: float,
    rho_by_anchor: Mapping[str, float],
) -> dict[str, Any]:
    """Build a small deterministic dose document for fake-backend tests."""
    anchors = []
    for anchor in ("A", "T", "H"):
        rho = float(rho_by_anchor[anchor])
        c_value = rho * median_content_norm / mu_all_tw
        alpha = {}
        for estimator, mu in (("mu_all_tw", mu_all_tw), ("mu_content_tw", mu_content_tw)):
            pre = c_value * mu
            alpha[estimator] = {
                "pre_dtype": {"value": pre, "binary64_hex": pre.hex()},
                "post_dtype": {"value": pre, "binary64_hex": pre.hex()},
            }
        anchors.append({
            "anchor": anchor,
            "rho": {"value": rho, "binary64_hex": rho.hex()},
            "c": {"value": c_value, "binary64_hex": c_value.hex()},
            "alpha_by_estimator": alpha,
        })
    return {
        "schema_version": "paper1-stage3-measurement-dose-v1",
        "protocol_version": "paper1-stage3-current-v1",
        "status": "ESTIMABLE",
        "mu_all_tw": {"value": mu_all_tw, "binary64_hex": mu_all_tw.hex()},
        "mu_content_tw": {"value": mu_content_tw, "binary64_hex": mu_content_tw.hex()},
        "median_content_norm": {
            "value": median_content_norm,
            "binary64_hex": median_content_norm.hex(),
        },
        "anchors": anchors,
    }


def build_call_dose_evidence(
    *,
    identity: Mapping[str, Any],
    dose_binding: Mapping[str, Any],
    generation_status: str,
    pre_hook_l2: float,
    post_hook_l2: float,
    vector_alignment: float,
    cosine_drift: float,
) -> dict[str, Any]:
    doses = validate_dose_binding(dose_binding)
    anchor = identity.get("anchor")
    estimator = identity.get("estimator")
    if anchor not in {"A", "T", "H"} or estimator not in {"mu_all_tw", "mu_content_tw"}:
        raise PipelineError("dose evidence requires one registered steered identity")
    bound = doses[anchor][estimator]
    for field in ("c_hex", "alpha_pre_dtype_hex", "alpha_post_dtype_hex", "rho_hex"):
        if identity.get(field) != bound[field]:
            raise PipelineError(f"logical identity differs from dose input: {field}")
    values = {
        "nominal_c": float.fromhex(bound["c_hex"]),
        "mu_value": float(dose_binding[estimator]["value"]),
        "alpha_pre_dtype": float.fromhex(bound["alpha_pre_dtype_hex"]),
        "alpha_post_dtype": float.fromhex(bound["alpha_post_dtype_hex"]),
        "pre_hook_l2": float(pre_hook_l2),
        "post_hook_l2": float(post_hook_l2),
        "vector_alignment": float(vector_alignment),
        "cosine_drift": float(cosine_drift),
    }
    if any(not math.isfinite(value) for value in values.values()):
        raise PipelineError("dose evidence contains a nonfinite value")
    if values["pre_hook_l2"] <= 0.0 or values["post_hook_l2"] <= 0.0:
        raise PipelineError("dose evidence hook norms must be positive")
    values["relative_dose"] = values["alpha_post_dtype"] / values["pre_hook_l2"]
    values["norm_ratio"] = values["post_hook_l2"] / values["pre_hook_l2"]
    if not -1.0 <= values["vector_alignment"] <= 1.0:
        raise PipelineError("vector_alignment is outside cosine bounds")
    if not 0.0 <= values["cosine_drift"] <= 2.0:
        raise PipelineError("cosine_drift is outside cosine bounds")
    return {
        "status": "VALIDATED",
        "failure_code": None,
        **{
            name: {"value": value, "binary64_hex": value.hex()}
            for name, value in values.items()
        },
        "mu_estimator": estimator,
        "mu_source_sha256": canonical_sha256(dose_binding[estimator]),
        "measurement_dose_sha256": canonical_sha256(dose_binding),
        "generation_status": generation_status,
        "phase": "decode-only",
        "use_cache": True,
    }
