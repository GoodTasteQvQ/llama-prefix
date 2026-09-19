from __future__ import annotations

import json
from pathlib import Path

from scripts.core_full_rescore_dose_adapter import adapt


def _fixture_run(tmp_path: Path) -> Path:
    source = Path(".codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness/full_rescore_request_manifest.jsonl")
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    run = tmp_path / "run"
    run.mkdir()
    (run / "request_manifest.jsonl").write_text(source.read_text())
    records = []
    for row in rows:
        domain = row["domain"]
        label = "safe" if domain == "harmful" else "helpful"
        records.append({
            "ordinal": row["ordinal"],
            "logical_identity": row["logical_identity"],
            "source_response_id": row["source_response_id"],
            "request_sha256": row["request_sha256"],
            "status": "PARSED",
            "label": label,
            "rationale": "fixture",
            "raw": json.dumps({"label": label, "rationale": "fixture"}),
            "diagnostics": {"fixture": True},
            "retry_count": 0,
            "actual_call_counts": {"four_class": 1, "binary": 0},
        })
    (run / "request_records.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
    return run


def test_adapter_maps_full_rescore_records_and_writes_as_outputs(tmp_path: Path):
    result = adapt(_fixture_run(tmp_path))
    assert result["status"] == "CORE_DOSE_SCREEN_READY"
    assert result["logical_identity_count"] == 1200
    assert result["actual_judge_calls"] == 1200
    assert set(result["groups"]) == {"qwen25|rogue", "qwen25|contrastive", "llama31|rogue", "llama31|contrastive"}
    assert (tmp_path / "run/dose_decisions.json").is_file()
    assert len((tmp_path / "run/judge_records_view.jsonl").read_text().splitlines()) == 1200
    assert len(json.loads((tmp_path / "run/judge_records_index.json").read_text())) == 1200
    assert (tmp_path / "run/artifact_hashes.sha256").is_file()
