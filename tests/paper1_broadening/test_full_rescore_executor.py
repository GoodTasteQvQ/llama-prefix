from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.core_judge_full_rescore_executor as executor_module
from scripts.core_judge_full_rescore_executor import (
    FullRescoreContractError,
    FullRescoreExecutor,
    parse_direct_json,
)


ROOT = Path("/data/goodtaste_workspace/llama-prefix")
MANIFEST = ROOT / ".codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness/full_rescore_request_manifest.jsonl"


def _identity(row):
    return {"ordinal": row["ordinal"], "response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "parser": "strict_direct_json_v1", "enable_thinking": False, "max_new_tokens": 1296}


def test_parser_is_exact_and_domain_bound():
    assert parse_direct_json('{"label":"refusal","rationale":"declines"}', "harmful") == ("refusal", "declines")
    for raw in ['{"label":"refusal","rationale":"x","extra":1}', '{"label":"refusal","rationale":"x","label":"safe"}', '{"label":"helpful","rationale":"x"}', '{"label":"safe","rationale":""}', '```json\n{"label":"safe","rationale":"x"}\n```']:
        with pytest.raises(FullRescoreContractError):
            parse_direct_json(raw, "harmful")


def test_executor_fixture_separates_logical_budget_and_calls(tmp_path: Path):
    rows = [json.loads(x) for x in MANIFEST.read_text().splitlines()]
    calls = []

    def backend(row, retry_no):
        calls.append((row["ordinal"], retry_no))
        if row["ordinal"] == 1 and retry_no == 0:
            return {"request_identity": _identity(row), "raw": "not-json", "diagnostics": {}}
        return {"request_identity": _identity(row), "raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {"fixture": True}}

    result = FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend).run()
    assert result["logical_identity_count"] == 1200
    assert result["actual_judge_calls"] == 1201
    assert result["retry_calls"] == 1
    assert calls[:2] == [(1, 0), (1, 1)]
    records = [json.loads(x) for x in (tmp_path / "run/request_records.jsonl").read_text().splitlines()]
    assert len(records) == 1200 and all(r["status"] == "PARSED" for r in records)


def test_executor_missing_cell_is_blocked(tmp_path: Path):
    rows = [json.loads(x) for x in MANIFEST.read_text().splitlines()]
    manifest = tmp_path / "manifest.jsonl"
    for row in rows[:60]:
        row["logical_identity"]["rho"] = 0.75
        row["logical_identity"]["direction_id"] += ":merged"
        row["cell"]["rho"] = 0.75
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def backend(row, retry_no):
        return {"request_identity": _identity(row), "raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {}}

    with pytest.raises(FullRescoreContractError, match="20 cells"):
        FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend, manifest_path=manifest).run()


def test_old_label_contamination_fails_closed(tmp_path: Path):
    rows = [json.loads(x) for x in MANIFEST.read_text().splitlines()]
    rows[0]["old_judge_label"] = "refusal"
    bad = tmp_path / "bad.jsonl"
    bad.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(FullRescoreContractError, match="contamination"):
        FullRescoreExecutor(run_dir=tmp_path / "run", backend=lambda *_: {}, manifest_path=bad).preflight()


def test_manifest_cell_and_domain_binding_fails_closed(tmp_path: Path):
    rows = [json.loads(x) for x in MANIFEST.read_text().splitlines()]
    rows[0]["logical_identity"]["model_id"] = "unbound-model"
    bad = tmp_path / "bad.jsonl"
    bad.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(FullRescoreContractError, match="cell binding"):
        FullRescoreExecutor(run_dir=tmp_path / "run", backend=lambda *_: {}, manifest_path=bad).preflight()


def test_generation_identity_binding_fails_closed(tmp_path: Path):
    rows = [json.loads(x) for x in MANIFEST.read_text().splitlines()]
    rows[0]["source_line"]["schedule"] = 2
    bad = tmp_path / "bad.jsonl"
    bad.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def backend(row, retry_no):
        return {"request_identity": _identity(row), "raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {}}

    result = FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend, manifest_path=bad).run()
    assert result["status"] == "CORE_SCREEN_V3_BLOCKED"
    assert result["stopped_on_contract_failure"] is True
    records = [json.loads(x) for x in (tmp_path / "run/request_records.jsonl").read_text().splitlines()]
    assert records[0]["status"] == "CONTRACT_FAILURE"


def test_missing_gate_allows_one_but_blocks_two(tmp_path: Path):
    def backend(row, retry_no):
        if row["ordinal"] in {1, 2}:
            return {"request_identity": _identity(row), "status": "MISSING", "reason": "fixture_missing"}
        return {"request_identity": _identity(row), "raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {}}

    result = FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend).run()
    assert result["status"] == "CORE_SCREEN_V3_BLOCKED"
    assert result["technical_failures"] == 0
    assert result["missing"] == 2
    assert result["cell_gate"]["qwen25|rogue|0.5"]["missing"] == 2


def test_identity_failure_stops_and_preserves_completed_records(tmp_path: Path):
    def backend(row, retry_no):
        if row["ordinal"] == 2:
            return {"request_identity": {"bad": True}, "raw": '{"label":"safe","rationale":"x"}', "diagnostics": {}}
        return {"request_identity": _identity(row), "raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {}}

    result = FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend).run()
    assert result["status"] == "CORE_SCREEN_V3_BLOCKED"
    assert result["stopped_on_contract_failure"] is True
    records = [json.loads(x) for x in (tmp_path / "run/request_records.jsonl").read_text().splitlines()]
    assert len(records) == 2 and records[-1]["status"] == "CONTRACT_FAILURE"


def test_technical_failure_retries_once_and_is_accounted_separately(tmp_path: Path):
    def backend(row, retry_no):
        if row["ordinal"] == 1 and retry_no == 0:
            return {"request_identity": _identity(row), "status": "TECHNICAL_FAILURE", "error": "fixture transport"}
        if row["ordinal"] == 1:
            return {"request_identity": _identity(row), "raw": '{"label":"safe","rationale":"recovered"}', "diagnostics": {"token_count": 3}}
        return {"request_identity": _identity(row), "raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {}}

    result = FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend).run()
    assert result["status"] == "CORE_SCREEN_V3_PASS"
    assert result["actual_judge_calls"] == 1201
    assert result["retry_calls"] == 1


def test_retry_exhaustion_technical_failure_stops_before_next_identity(tmp_path: Path):
    calls = []

    def backend(row, retry_no):
        calls.append((row["ordinal"], retry_no))
        return {"request_identity": _identity(row), "status": "TECHNICAL_FAILURE", "error": "fixture transport"}

    result = FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend).run()
    assert calls == [(1, 0), (1, 1)]
    assert result["stopped_on_contract_failure"] is True
    assert result["technical_failures"] == 1
    assert result["logical_identity_count"] == 1
    record = json.loads((tmp_path / "run/request_records.jsonl").read_text().splitlines()[0])
    assert record["status"] == "TECHNICAL_FAILURE"
    assert len(record["attempt_records"]) == 2


def test_retry_exhaustion_parse_failure_stops_before_next_identity(tmp_path: Path):
    calls = []

    def backend(row, retry_no):
        calls.append((row["ordinal"], retry_no))
        return {"request_identity": _identity(row), "raw": "not-json", "diagnostics": {"fixture": True}}

    result = FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend).run()
    assert calls == [(1, 0), (1, 1)]
    assert result["stopped_on_contract_failure"] is True
    assert result["parse_failures"] == 1
    assert result["logical_identity_count"] == 1
    record = json.loads((tmp_path / "run/request_records.jsonl").read_text().splitlines()[0])
    assert record["status"] == "PARSE_FAILURE"
    assert len(record["attempt_records"]) == 2


def test_attempt_evidence_is_durable_before_later_backend_exception(tmp_path: Path):
    def backend(row, retry_no):
        if row["ordinal"] == 2:
            raise RuntimeError("fixture interruption")
        return {"request_identity": _identity(row), "raw": '{"label":"safe","rationale":"fixture"}', "diagnostics": {"token_count": 2}}

    result = FullRescoreExecutor(run_dir=tmp_path / "run", backend=backend).run()
    assert result["stopped_on_contract_failure"] is True
    attempts = [json.loads(line) for line in (tmp_path / "run/attempt_records.jsonl").read_text().splitlines()]
    events = [json.loads(line) for line in (tmp_path / "run/events.jsonl").read_text().splitlines()]
    records = [json.loads(line) for line in (tmp_path / "run/request_records.jsonl").read_text().splitlines()]
    assert attempts[0]["ordinal"] == 1 and attempts[0]["status"] == "PARSED"
    assert any(event["event"] == "PARSED" and event["ordinal"] == 1 for event in events)
    assert records[0]["ordinal"] == 1 and records[0]["status"] == "PARSED"


def _handoff_fixture(tmp_path: Path, *, status="CORE_RECOVERY_V3_PASS", mutate_hash=False):
    evidence_dir = tmp_path / "recovery"
    evidence_dir.mkdir()
    names = ("execution_preflight_checks.json", "final_boundary_audit.json", "record_integrity.json", "run_artifact_verification.txt", "artifact_hashes.sha256")
    evidence, hashes = {}, {}
    for name in names:
        path = evidence_dir / name
        path.write_text("fixture\n")
        evidence[name], hashes[name] = str(path), executor_module.sha256_file(path)
    stale = []
    for name in ("preflight.status", "call_counts.json"):
        path = evidence_dir / name
        path.write_text("HISTORICAL_STALE\n")
        stale.append(str(path))
    if mutate_hash:
        hashes[names[0]] = "0" * 64
    handoff = {"status": status, "records": 13, "ordinals": "1..13", "raw_files": 13, "diagnostics_files": 13, "actual_four_class": 13, "binary": 0, "generation_retry": 0, "additional_retry": 0, "run_artifact_verification": 0, "recovery_evidence": evidence, "canonical_evidence_sha256": hashes, "historical_stale": stale}
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(handoff))
    return path


@pytest.mark.parametrize("case", ["missing", "status", "hash"])
def test_recovery_handoff_fail_closed_before_backend_construction(tmp_path: Path, monkeypatch, case):
    handoff = tmp_path / "handoff.json"
    if case == "missing":
        pass
    elif case == "status":
        handoff = _handoff_fixture(tmp_path, status="RECOVERY_APPROVAL_BLOCKED")
    else:
        handoff = _handoff_fixture(tmp_path, mutate_hash=True)
    monkeypatch.setattr(executor_module, "RECOVERY_HANDOFF_PATH", handoff)
    backend_constructed = []

    def verify():
        return executor_module._verify_recovery_handoff()

    monkeypatch.setattr(executor_module, "verify_readiness_inputs", verify)
    with pytest.raises(FullRescoreContractError):
        FullRescoreExecutor(run_dir=tmp_path / "run", backend_factory=lambda: backend_constructed.append(True)).preflight()
    assert backend_constructed == []
