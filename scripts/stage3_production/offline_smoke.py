#!/usr/bin/env python3
"""Run one strict local-asset fake-backend smoke item."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage3_pipeline.core import (  # noqa: E402
    ACTIVE_PROFILE,
    DECODE_CONFIG,
    JUDGE_CONFIG,
    GenerationProducer,
    LogicalIdentityRegistry,
    canonical_sha256,
    offline_execution_guard,
    parse_judge_with_retry,
    utc_now,
)
from stage3_pipeline.dose import (  # noqa: E402
    build_call_dose_evidence,
    build_test_dose_binding,
    validate_dose_binding,
)
from stage3_pipeline.execution import reconcile_execution  # noqa: E402
from stage3_pipeline.local_temp import require_project_local_temp  # noqa: E402
from stage3_pipeline.offline_assets import load_p1_harmful_active_entry  # noqa: E402
from stage3_pipeline.records import (  # noqa: E402
    build_block_response_record,
    validate_generation_record,
    validate_judge_record,
)
from stage3_pipeline.run_manifest import (  # noqa: E402
    build_run_manifest,
    validate_run_manifest,
    write_run_manifest,
)


ACTIVE_ENTRY = "configs/stage3/p1_harmful_do_not_answer_v1.json"


def smoke_identity(prompt_id: str, rendered_prompt_sha256: str, dose: dict[str, str]) -> dict[str, object]:
    digest = "0" * 64
    return {
        "profile": ACTIVE_PROFILE,
        "block": "support",
        "domain": "harmful",
        "split": "D_behavior_screen",
        "model_revision": "fake-local-model",
        "template_sha256": digest,
        "rendered_prompt_sha256": rendered_prompt_sha256,
        "prompt_id": prompt_id,
        "vector_id": "smoke-vector-1",
        "estimator": "mu_all_tw",
        "anchor": "A",
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


def run_smoke() -> dict[str, object]:
    local_temp = require_project_local_temp(ROOT)
    started = utc_now()
    dose_binding = build_test_dose_binding(
        mu_all_tw=0.2,
        mu_content_tw=0.1,
        median_content_norm=2.0,
        rho_by_anchor={"A": 0.01, "T": 0.02, "H": 0.03},
    )
    dose = validate_dose_binding(dose_binding)["A"]["mu_all_tw"]
    guard = offline_execution_guard()
    with guard:
        loaded = load_p1_harmful_active_entry(ROOT, ACTIVE_ENTRY)
        source = loaded["records"][0]
        identity = smoke_identity(
            f"p1-harmful-{source['source_id']}", source["question_sha256"], dose
        )
        registry = LogicalIdentityRegistry()
        logical_id = registry.register(identity)
        dose_evidence = build_call_dose_evidence(
            identity=identity,
            dose_binding=dose_binding,
            generation_status="COMPLETED",
            pre_hook_l2=2.0,
            post_hook_l2=2.1,
            vector_alignment=0.5,
            cosine_drift=0.1,
        )

        producer = GenerationProducer(
            registry,
            lambda _identity, _request: {
                "output_text": "fake smoke output",
                "diagnostics": {"backend": "fake", "steering_hook_called": True},
                "dose_evidence": dose_evidence,
            },
            run_mode="smoke",
            fake_backend=True,
        )
        generation = validate_generation_record(producer.produce(
            logical_id, {"logical_id": logical_id, "generation_config": DECODE_CONFIG}
        ))
        judge = validate_judge_record(parse_judge_with_retry(
            logical_id,
            lambda _attempt, _request: '{"label":"safe","rationale":"fake smoke"}',
            {"logical_id": logical_id, "judge_config": JUDGE_CONFIG},
            registry=registry,
            generation_record=generation,
            run_mode="smoke",
            judge_identity={
                "model_path_or_id": "fake-local-judge",
                "tokenizer_path_or_id": "fake-local-tokenizer",
                "rubric_sha256": "1" * 64,
            },
            fake_backend=True,
        ))
    response = build_block_response_record(
        identity=identity,
        generation_record=generation,
        judge_record=judge,
        dose_evidence=dose_evidence,
    )
    disposition = {
        "schema_version": "paper1-stage3-execution-disposition-v2",
        "logical_id": logical_id,
        "identity_sha256": canonical_sha256(identity),
        "terminal_disposition": "COMPLETED_PARSED",
        "generation_record_sha256": generation["record_sha256"],
        "judge_record_sha256": judge["record_sha256"],
        "response_record_sha256": response["record_sha256"],
        "integrity_block_reason": None,
    }
    reconciliation = reconcile_execution(
        registry,
        run_mode="smoke",
        generation_records=[generation],
        judge_records=[judge],
        response_records=[response],
        dispositions=[disposition],
        dose_binding=dose_binding,
    )
    completed = utc_now()

    with tempfile.TemporaryDirectory(prefix="offline-smoke-", dir=local_temp) as temporary:
        output_directory = Path(temporary) / "output"
        manifest = build_run_manifest(
            repo_root=ROOT,
            run_mode="smoke",
            command=[sys.executable, "-B", str(Path(__file__).relative_to(ROOT))],
            started_at_utc=started,
            completed_at_utc=completed,
            model_path_or_id="fake-local-model",
            tokenizer_path_or_id="fake-local-tokenizer",
            input_paths=[ROOT / ACTIVE_ENTRY, ROOT / loaded["selected_relative_path"]],
            generation_config=DECODE_CONFIG,
            seed=42,
            gpu_identity=None,
            output_directory=output_directory,
            exit_status="success",
            exit_code=0,
            fake_backend=True,
            reconciliation=reconciliation,
            offline_guard=guard,
            runtime_versions={"python": "test", "torch": None, "transformers": None, "cuda": None},
        )
        path = write_run_manifest(output_directory, manifest)
        validated = validate_run_manifest(json.loads(path.read_text(encoding="utf-8")))
    return {
        "status": "OFFLINE_SMOKE_PASS",
        "run_mode": validated["run_mode"],
        "asset_rows_loaded": loaded["row_count"],
        "generation_completed": generation["generation_completed"],
        "paper_result_eligible": validated["paper_result_eligible"],
        "blocked_attempts": validated["offline_guard_report"]["blocked_attempt_count"],
        "reconciled_logical_ids": validated["reconciliation"]["scheduled_logical_ids"],
    }


def main() -> int:
    print(json.dumps(run_smoke(), ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
