from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.core_judge_recovery_executor import (
    CONFIG_PATH,
    DESIGN_PATH,
    MANIFEST_PATH,
    PROPOSAL_DIR,
    REPORT_PATH,
    RecoveryContractError,
    RecoveryExecutor,
    parse_direct_json,
    sha256_file,
    verify_approval,
)


def _approval(manifest: Path = MANIFEST_PATH) -> dict:
    return {
        "status": "APPROVED",
        "proposal_sha256": sha256_file(REPORT_PATH),
        "manifest_sha256": sha256_file(manifest),
        "design_sha256": sha256_file(DESIGN_PATH),
        "config_sha256": sha256_file(CONFIG_PATH),
        "code_hashes": {
            "scripts/core_judge_recovery_executor.py": sha256_file(Path("scripts/core_judge_recovery_executor.py")),
            "scripts/core_judge_recovery_run.py": sha256_file(Path("scripts/core_judge_recovery_run.py")),
        },
    }


def _backend_evidence(row: dict) -> dict:
    return {
        "request_identity": {
            "ordinal": row["ordinal"],
            "response_id": row["source_response_id"],
            "request_sha256": row["request_sha256"],
            "parser": "strict_direct_json_v1",
            "enable_thinking": False,
            "max_new_tokens": 1296,
        },
        "actual_call_counts": {"binary": 0, "four_class": 1},
        "generation_retries": 0,
        "additional_judge_retries": 0,
        "binary_requests": 0,
    }


def test_direct_json_contract_and_runtime_values():
    assert parse_direct_json('{"label":"safe","rationale":"benign"}', "harmful") == ("safe", "benign")
    with pytest.raises(RecoveryContractError):
        parse_direct_json('{"label":"safe","rationale":"x","extra":1}', "harmful")
    cfg = json.loads(CONFIG_PATH.read_text())
    assert cfg["runtime"]["judge"] == {"do_sample": False, "enable_thinking": False, "max_new_tokens": 1296, "num_beams": 1, "parser": "strict_direct_json_v1"}
    assert cfg["runtime"]["decoder"]["max_new_tokens"] == 512


def test_missing_approval_fails_before_backend(tmp_path: Path):
    called = []
    with pytest.raises(RecoveryContractError, match="approval"):
        RecoveryExecutor(backend=lambda row: called.append(row), run_dir=tmp_path / "run", approval_path=tmp_path / "missing.md").preflight()
    assert called == []
    assert not (tmp_path / "run").exists()


def test_noncanonical_approval_path_fails_closed_before_backend_factory(tmp_path: Path):
    constructed = []
    with pytest.raises(RecoveryContractError, match="canonical"):
        RecoveryExecutor(
            backend_factory=lambda: constructed.append(True),
            run_dir=tmp_path / "run",
            approval=_approval(),
            approval_path=tmp_path / "approval.md",
        ).preflight()
    assert constructed == []


def test_manifest_duplicate_identity_and_bad_order_fail_closed(tmp_path: Path):
    rows = [json.loads(line) for line in MANIFEST_PATH.read_text().splitlines()]
    rows[1]["source_response_id"] = rows[0]["source_response_id"]
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(RecoveryContractError, match="unique"):
        verify_approval(approval=_approval(duplicate), manifest_path=duplicate)

    rows = [json.loads(line) for line in MANIFEST_PATH.read_text().splitlines()]
    rows[0]["ordinal"], rows[1]["ordinal"] = rows[1]["ordinal"], rows[0]["ordinal"]
    reordered = tmp_path / "reordered.jsonl"
    reordered.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(RecoveryContractError, match="order"):
        verify_approval(approval=_approval(reordered), manifest_path=reordered)


def test_manifest_is_exactly_thirteen_and_ordered():
    details = verify_approval(approval=_approval())
    assert details["row_count"] == 13
    assert details["enable_thinking"] is False
    assert details["max_new_tokens"] == 1296
    assert details["decoder_max_new_tokens"] == 512


def test_failure_stops_without_retry_or_next_row(tmp_path: Path):
    calls = []

    def backend(row):
        calls.append(row["ordinal"])
        if row["ordinal"] == 1:
            return {"raw": '{"label":"safe","rationale":"ok"}', "diagnostics": {"tokens": 2}, **_backend_evidence(row)}
        raise RuntimeError("fixture technical failure")

    result = RecoveryExecutor(backend=backend, run_dir=tmp_path / "run", approval=_approval()).run()
    assert result["status"] == "STOPPED_ON_FAILURE"
    assert result["records"] == 2
    assert result["actual_four_class_requests"] == 2
    assert calls == [1, 2]
    rows = [json.loads(line) for line in (tmp_path / "run/recovery_judge_records.jsonl").read_text().splitlines()]
    assert rows[-1]["status"] == "PARSE_FAILURE"
    assert rows[-1]["observability_status"] == "RAW_UNAVAILABLE"
    assert rows[-1]["actual_call_counts"] == {"four_class": 1, "binary": 0}


def test_backend_factory_runs_after_preflight(tmp_path: Path):
    events = []

    class TracedExecutor(RecoveryExecutor):
        def preflight(self):
            events.append("preflight")
            return super().preflight()

    def factory():
        events.append("backend_factory")
        return lambda row: {"raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {"ordinal": row["ordinal"]}, **_backend_evidence(row)}

    result = TracedExecutor(backend_factory=factory, run_dir=tmp_path / "run", approval=_approval()).run()
    assert result["status"] == "COMPLETED"
    assert events[:2] == ["preflight", "backend_factory"]


def test_identity_mismatch_or_missing_diagnostics_stops_immediately(tmp_path: Path):
    calls = []

    def backend(row):
        calls.append(row["ordinal"])
        if row["ordinal"] == 1:
            return {"raw": '{"label":"safe","rationale":"fixture"}', "request_identity": {"wrong": True}, "diagnostics": {}}
        raise AssertionError("next row must not be reached")

    result = RecoveryExecutor(backend=backend, run_dir=tmp_path / "run", approval=_approval()).run()
    assert result["status"] == "STOPPED_ON_FAILURE"
    assert calls == [1]
    record = json.loads((tmp_path / "run/recovery_judge_records.jsonl").read_text().splitlines()[0])
    assert record["observability_status"] == "RAW_AND_DIAGNOSTICS_AVAILABLE"
    assert record["parser_status"] == "PARSE_FAILURE"

    def missing_diagnostics(row):
        return {"raw": '{"label":"safe","rationale":"fixture"}', **_backend_evidence(row), "diagnostics": None}

    result = RecoveryExecutor(backend=missing_diagnostics, run_dir=tmp_path / "missing", approval=_approval()).run()
    record = json.loads((tmp_path / "missing/recovery_judge_records.jsonl").read_text().splitlines()[0])
    assert result["status"] == "STOPPED_ON_FAILURE"
    assert record["observability_status"] == "RAW_AVAILABLE_DIAGNOSTICS_UNAVAILABLE"
    assert record["raw_sha256"]
    assert record["diagnostics"] == "DIAGNOSTICS_UNAVAILABLE"


def test_all_fixture_rows_are_sequential_and_no_binary_or_retry(tmp_path: Path):
    def backend(row):
        return {"raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {"ordinal": row["ordinal"]}, **_backend_evidence(row)}

    result = RecoveryExecutor(backend=backend, run_dir=tmp_path / "run", approval=_approval()).run()
    assert result["status"] == "COMPLETED"
    assert result["records"] == 13
    assert result["actual_four_class_requests"] == 13
    assert result["binary_requests"] == result["generation_retries"] == result["additional_judge_retries"] == 0
    events = (tmp_path / "run/recovery_events.jsonl").read_text().splitlines()
    assert len(events) == 39
    assert json.loads(events[0])["event"] == "REQUEST_READY"
    assert json.loads(events[-1])["event"] == "PARSED"
