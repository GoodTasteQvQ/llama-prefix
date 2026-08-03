"""Shared Stage 3 test data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from stage3_pipeline.core import (
    ACTIVE_PROFILE,
    DECODE_CONFIG,
    JUDGE_CONFIG,
    GenerationProducer,
    LogicalIdentityRegistry,
    canonical_sha256,
    parse_judge_with_retry,
)
from stage3_pipeline.dose import (
    build_call_dose_evidence,
    build_test_dose_binding,
    validate_dose_binding,
)
from stage3_pipeline.execution import reconcile_execution, response_terminal_disposition
from stage3_pipeline.records import build_block_response_record


ROOT = Path(__file__).resolve().parents[2]
P1_DIRECTORY = ROOT / "data/stage3/p1_harmful_do_not_answer_v1"
P1_INPUT = P1_DIRECTORY / "selected_p1_harmful_100.json"
ACTIVE_ENTRY = ROOT / "configs/stage3/p1_harmful_do_not_answer_v1.json"


def test_dose_binding() -> dict[str, Any]:
    return build_test_dose_binding(
        mu_all_tw=0.2,
        mu_content_tw=0.1,
        median_content_norm=2.0,
        rho_by_anchor={"A": 0.01, "T": 0.02, "H": 0.03},
    )


def identity(prompt_id: str = "test-prompt", *, rendered_seed: str = "0") -> dict[str, object]:
    return block_identity("support", prompt_id, rendered_seed=rendered_seed)


def block_identity(
    block: str,
    prompt_id: str = "test-prompt",
    *,
    vector_id: str | None = None,
    rendered_seed: str = "0",
) -> dict[str, object]:
    digest = "0" * 64
    rendered = rendered_seed * 64
    mapping = {
        "support": ("harmful", "D_behavior_screen", "mu_all_tw", "A"),
        "P2_A_all": ("harmful", "D_behavior_confirm", "mu_all_tw", "A"),
        "P2_A_content": ("harmful", "D_behavior_confirm", "mu_content_tw", "A"),
        "P2_T_all": ("harmful", "D_behavior_confirm", "mu_all_tw", "T"),
        "P2_T_content": ("harmful", "D_behavior_confirm", "mu_content_tw", "T"),
        "harmful_clean": ("harmful", "D_behavior_confirm", "clean", "clean"),
        "benign_T": ("benign", "D_benign_confirm", "mu_all_tw", "T"),
        "benign_clean": ("benign", "D_benign_confirm", "clean", "clean"),
    }
    domain, split, estimator, anchor = mapping[block]
    if estimator == "clean":
        dose = {
            "c_hex": float(0.0).hex(),
            "alpha_pre_dtype_hex": float(0.0).hex(),
            "alpha_post_dtype_hex": float(0.0).hex(),
            "rho_hex": float(0.0).hex(),
        }
        actual_vector = None
    else:
        dose = validate_dose_binding(test_dose_binding())[anchor][estimator]
        actual_vector = vector_id or f"vector-{prompt_id}"
    return {
        "profile": ACTIVE_PROFILE,
        "block": block,
        "domain": domain,
        "split": split,
        "model_revision": "fake-local-model",
        "template_sha256": digest,
        "rendered_prompt_sha256": rendered,
        "prompt_id": prompt_id,
        "vector_id": actual_vector,
        "estimator": estimator,
        "anchor": anchor,
        **dose,
        "layer": 1,
        "hook_site": "resid_post",
        "phase": "decode-only",
        "use_cache": True,
        "generation_config_sha256": canonical_sha256(DECODE_CONFIG),
        "code_sha256": digest,
        "config_sha256": digest,
        "environment_sha256": digest,
    }


def completed_chain(
    block: str = "support",
    *,
    run_mode: str = "smoke",
    prompt_id: str = "test-prompt",
    label: str | None = None,
    dose_failure_code: str | None = None,
) -> dict[str, Any]:
    item_identity = block_identity(block, prompt_id)
    registry = LogicalIdentityRegistry()
    logical_id = registry.register(item_identity)
    if item_identity["estimator"] == "clean":
        dose_evidence = None
    else:
        dose_evidence = build_call_dose_evidence(
            identity=item_identity,
            dose_binding=test_dose_binding(),
            generation_status="COMPLETED",
            pre_hook_l2=2.0,
            post_hook_l2=2.1,
            vector_alignment=0.5,
            cosine_drift=0.1,
        )
        if dose_failure_code is not None:
            dose_evidence["status"] = "INVALID"
            dose_evidence["failure_code"] = dose_failure_code
            for field in (
                "nominal_c", "mu_value", "alpha_pre_dtype", "alpha_post_dtype",
                "pre_hook_l2", "post_hook_l2", "relative_dose", "norm_ratio",
                "vector_alignment", "cosine_drift",
            ):
                dose_evidence[field] = None
    generation = GenerationProducer(
        registry,
        lambda _identity, _request: {
            "output_text": "fake output",
            "diagnostics": {},
            **({} if dose_evidence is None else {"dose_evidence": dose_evidence}),
        },
        run_mode=run_mode,
        fake_backend=True,
    ).produce(logical_id, {"logical_id": logical_id, "generation_config": DECODE_CONFIG})
    domain = item_identity["domain"]
    actual_label = label or ("safe" if domain == "harmful" else "helpful")
    judge = parse_judge_with_retry(
        logical_id,
        lambda _attempt, _request: json_label(actual_label),
        {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
        registry=registry,
        generation_record=generation,
        run_mode=run_mode,
        judge_identity={
            "model_path_or_id": "fake-judge",
            "tokenizer_path_or_id": "fake-tokenizer",
            "rubric_sha256": "1" * 64,
        },
        fake_backend=True,
    )
    response = build_block_response_record(
        identity=item_identity,
        generation_record=generation,
        judge_record=judge,
        dose_evidence=dose_evidence,
    )
    disposition = {
        "schema_version": "paper1-stage3-execution-disposition-v2",
        "logical_id": logical_id,
        "identity_sha256": canonical_sha256(item_identity),
        "terminal_disposition": response_terminal_disposition(
            item_identity, response, generation, judge
        ),
        "generation_record_sha256": generation["record_sha256"],
        "judge_record_sha256": judge["record_sha256"],
        "response_record_sha256": response["record_sha256"],
        "integrity_block_reason": None,
    }
    reconciliation = reconcile_execution(
        registry,
        run_mode=run_mode,
        generation_records=[generation],
        judge_records=[judge],
        response_records=[response],
        dispositions=[disposition],
        dose_binding=test_dose_binding(),
    )
    return {
        "identity": item_identity,
        "registry": registry,
        "logical_id": logical_id,
        "generation": generation,
        "judge": judge,
        "response": response,
        "disposition": disposition,
        "reconciliation": reconciliation,
        "dose_binding": test_dose_binding(),
    }


def json_label(label: str) -> str:
    return '{"label":"' + label + '","rationale":"fixture"}'
