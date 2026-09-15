from __future__ import annotations

import json
from pathlib import Path


report = json.loads(Path(".codex-temp/paper1_broadening_smoke-final/smoke_report.json").read_text())
assert report["status"] == "PASS"
assert report["evidence_status"] == "NON_EVIDENCE"
assert report["generation_calls"] == 24
assert report["judge_calls"] == 4
assert report["zero_alpha_clean_token_ids_equal"] is True
assert report["family_vector_checks"] == {
    "actual_generation_vector_families": ["contrastive", "rogue"],
    "contrastive": True,
    "rogue": True,
}
for model, lifecycle in report["lifecycle"].items():
    assert lifecycle["behavior_hook_removed"] is True
    assert lifecycle["behavior_released"] is True
    assert lifecycle["models_concurrently_resident"] is False
for case in report["cases"]:
    assert case["evidence_status"] == "NON_EVIDENCE"
    if case.get("condition") in {"public_v1", "decode_only"}:
        counters = case["runtime_counters"]
        assert counters["prefill_calls"] == 1
        assert counters["decode_cached_calls"] == 15
        assert counters["trace_count"] == 16
print(json.dumps({
    "status": "CORE_REAL_SMOKE_PASS",
    "evidence_status": "NON_EVIDENCE",
    "generation_calls": report["generation_calls"],
    "judge_calls": report["judge_calls"],
    "models": sorted(report["lifecycle"]),
}, sort_keys=True))
