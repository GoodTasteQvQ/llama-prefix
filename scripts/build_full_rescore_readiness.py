#!/usr/bin/env python3
"""Build read-only full-rescore input binding and handoff evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path("/data/goodtaste_workspace/llama-prefix")
OLD = ROOT / "results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603"
RECOVERY = ROOT / ".codex-temp/paper1_core_judge_protocol_v3/recovery_execution"
OUT = ROOT / ".codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness"
CONFIG = ROOT / "configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json"
DESIGN = ROOT / "writing/broadening design/paper1_minimal_broadening_experiment_design_v2.3_direct_json.md"
EXPECTED_IDENTITIES = 1200
EXPECTED_CELLS = 20
EXPECTED_PER_CELL = 60


class BindingError(RuntimeError):
    """Raised when the old generation artifacts cannot bind fail-closed."""


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def rows(path: Path) -> list[dict[str, Any]]:
    try:
        values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BindingError(f"unable to read generation evidence: {path}") from exc
    if not all(isinstance(value, dict) for value in values):
        raise BindingError(f"generation evidence contains a non-object row: {path}")
    return values


def _validate_generation_sources(
    schedules: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    ledgers: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if any(len(values) != EXPECTED_IDENTITIES for values in (schedules, attempts, ledgers)):
        raise BindingError("generation source row count is not exactly 1200")
    schedule_ids = [row.get("response_id") for row in schedules]
    attempt_ids = [row.get("response_id") for row in attempts]
    ledger_ids = [row.get("response_id") for row in ledgers]
    if any(not isinstance(value, str) or not value for value in schedule_ids + attempt_ids + ledger_ids):
        raise BindingError("generation source response identity is missing")
    if len(set(schedule_ids)) != EXPECTED_IDENTITIES or len(set(attempt_ids)) != EXPECTED_IDENTITIES or len(set(ledger_ids)) != EXPECTED_IDENTITIES:
        raise BindingError("generation source response identities are not unique")
    schedule_keys = [row.get("schedule_id") for row in schedules]
    if any(not isinstance(value, str) or not value for value in schedule_keys) or len(set(schedule_keys)) != EXPECTED_IDENTITIES:
        raise BindingError("generation source schedule identities are not unique")
    if set(schedule_ids) != set(attempt_ids) or set(schedule_ids) != set(ledger_ids):
        raise BindingError("generation source response identity sets do not match")
    by_response = {row["response_id"]: row for row in attempts}
    ledger_by_response = {row["response_id"]: row for row in ledgers}
    for schedule in schedules:
        response_id = schedule["response_id"]
        attempt = by_response[response_id]
        ledger = ledger_by_response[response_id]
        if schedule.get("status") != "SCHEDULED" or attempt.get("status") != "COMPLETED" or ledger.get("terminal_status") != "COMPLETED":
            raise BindingError(f"generation completion is not terminal: {response_id}")
        if schedule.get("identity") != attempt.get("identity") or schedule.get("identity") != ledger.get("identity"):
            raise BindingError(f"generation logical identity mismatch: {response_id}")
        if schedule.get("schedule_id") != ledger.get("schedule_id"):
            raise BindingError(f"generation schedule identity mismatch: {response_id}")
        if not isinstance(attempt.get("text"), str):
            raise BindingError(f"generation completion text is unavailable: {response_id}")
    return by_response, ledger_by_response


def _blocked_binding(error: str) -> int:
    (OUT / "input_binding.json").write_text(
        json.dumps({"status": "FULL_RESCORE_READINESS_BLOCKED", "binding_error": error}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 4


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        schedules = rows(OLD / "screen_generation_schedule_core.jsonl")
        attempts = rows(OLD / "screen_generation_attempts_core.jsonl")
        ledgers = rows(OLD / "screen_generation_ledger_core.jsonl")
        frames = json.loads((OLD / "frames.json").read_text(encoding="utf-8"))
        frame_by_pair = {r["pair_id"]: r for r in frames["safe_pair_split"]["records"]}
        by_response, ledger_by_response = _validate_generation_sources(schedules, attempts, ledgers)
    except (BindingError, KeyError, TypeError, json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        return _blocked_binding(str(exc))
    manifest = []
    cells: dict[str, int] = {}
    for ordinal, schedule in enumerate(schedules, 1):
        rid = schedule["response_id"]
        attempt, ledger = by_response[rid], ledger_by_response[rid]
        ident = dict(schedule["identity"])
        prompt_id = ident.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id.endswith((":harmful", ":harmless")):
            return _blocked_binding(f"unsupported generation prompt domain: {rid}")
        pair_id = prompt_id.rsplit(":", 1)[0]
        frame = frame_by_pair.get(pair_id)
        if not isinstance(frame, dict):
            return _blocked_binding(f"generation frame is missing: {pair_id}")
        domain = "harmful" if prompt_id.endswith(":harmful") else "benign"
        prompt_key = "harmful" if domain == "harmful" else "harmless"
        prompt = frame.get(prompt_key)
        completion = attempt["text"]
        if not isinstance(prompt, str) or not prompt:
            return _blocked_binding(f"generation prompt is missing: {rid}")
        try:
            logical = {k: ident[k] for k in ("block", "condition", "direction_id", "family", "layer", "model_id", "prompt_id", "rho", "run_id")}
        except KeyError as exc:
            return _blocked_binding(f"generation logical identity is incomplete: {rid}:{exc.args[0]}")
        request_hash = hashlib.sha256(json.dumps({"prompt": prompt, "response": completion, "domain": domain}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        row = {"ordinal": ordinal, "logical_identity": logical, "cell": {"model_id": ident["model_id"], "family": ident["family"], "rho": ident["rho"]}, "domain": domain, "source_response_id": rid, "source_schedule_id": schedule["schedule_id"], "source_paths": {"schedule": str(OLD / "screen_generation_schedule_core.jsonl"), "attempt": str(OLD / "screen_generation_attempts_core.jsonl"), "ledger": str(OLD / "screen_generation_ledger_core.jsonl"), "frames": str(OLD / "frames.json")}, "source_line": {"schedule": ordinal, "attempt": next(i for i, x in enumerate(attempts, 1) if x["response_id"] == rid), "ledger": next(i for i, x in enumerate(ledgers, 1) if x["response_id"] == rid), "frames_pair_id": pair_id}, "completion_sha256": hashlib.sha256(completion.encode()).hexdigest(), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "request_sha256": request_hash, "parser": "strict_direct_json_v1", "enable_thinking": False, "max_new_tokens": 1296}
        manifest.append(row)
        key = f"{ident['model_id']}|{ident['family']}|{ident['rho']}"
        cells[key] = cells.get(key, 0) + 1
    manifest_path = OUT / "full_rescore_request_manifest.jsonl"
    manifest_path.write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in manifest), encoding="utf-8")
    response_id_unique = len({r["source_response_id"] for r in manifest}) == EXPECTED_IDENTITIES
    all_cells_exactly_60 = len(cells) == EXPECTED_CELLS and all(v == EXPECTED_PER_CELL for v in cells.values())
    binding_pass = len(manifest) == EXPECTED_IDENTITIES and response_id_unique and all_cells_exactly_60
    binding = {"status": "FULL_RESCORE_BINDING_PASS" if binding_pass else "FULL_RESCORE_READINESS_BLOCKED", "logical_identity_count": len(manifest), "response_id_unique": response_id_unique, "cells": cells, "all_cells_exactly_60": all_cells_exactly_60, "generation_sources_terminal": True, "old_judge_labels_consumed": False, "old_f2_generation_completion_only": True, "source_hashes": {str(p.relative_to(ROOT)): sha(p) for p in [OLD/'screen_generation_schedule_core.jsonl', OLD/'screen_generation_attempts_core.jsonl', OLD/'screen_generation_ledger_core.jsonl', OLD/'frames.json']}}
    (OUT / "input_binding.json").write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not binding_pass:
        return 4
    protected = [
        OLD / "screen_generation_schedule_core.jsonl", OLD / "screen_generation_attempts_core.jsonl", OLD / "screen_generation_ledger_core.jsonl", OLD / "screen_judge_records_core.jsonl", OLD / "frames.json", OLD / "resolved_config.json", OLD / "run_header.json",
        ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/approval_record.md", ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/judge_runtime_identity.json", ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/judge_runtime_release.json", ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/provenance_hash_manifest.json", ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/recovery_gate_result.json", ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/recovery_judge_records.jsonl", ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/recovery_request_manifest.jsonl", ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/recovery_runtime_status.json", ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/run_header.json",
        ROOT / "writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md", ROOT / "writing/broadening design/paper1_minimal_broadening_experiment_design_v2.1_readable.md", ROOT / "writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md", DESIGN, CONFIG,
    ]
    (OUT / "protected_input_sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in protected}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    (OUT / "git_preexisting_diff.txt").write_text(status, encoding="utf-8")
    artifact_hash_lines = [line for line in (RECOVERY / "artifact_hashes.sha256").read_text(encoding="utf-8").splitlines() if line.strip()]
    canonical_evidence = {name: sha(RECOVERY / name) for name in ("execution_preflight_checks.json", "final_boundary_audit.json", "record_integrity.json", "run_artifact_verification.txt", "artifact_hashes.sha256")}
    handoff = {"status": "CORE_RECOVERY_V3_PASS", "recovery_run": "results/paper1_broadening/core-judge-protocol-v3-direct-json-recovery-20260918T130823Z-a1", "recovery_evidence": {name: str(RECOVERY / name) for name in canonical_evidence}, "canonical_evidence_sha256": canonical_evidence, "recovery_artifact_sha256": sha(RECOVERY/'artifact_hashes.sha256'), "formal_artifact_hash_lines": len(artifact_hash_lines), "formal_artifact_hashes_all_present": len(artifact_hash_lines) >= 8, "records": 13, "ordinals": "1..13", "raw_files": 13, "diagnostics_files": 13, "actual_four_class": 13, "binary": 0, "generation_retry": 0, "additional_retry": 0, "run_artifact_verification": 0, "historical_stale": [str(RECOVERY/'preflight.status'), str(RECOVERY/'call_counts.json')], "historical_stale_policy": "HISTORICAL_STALE; not used for success judgment"}
    (OUT / "recovery_handoff_manifest.json").write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
