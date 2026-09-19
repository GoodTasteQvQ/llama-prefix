#!/usr/bin/env python3
"""Independent, bounded full-rescore executor with an offline fixture backend."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path("/data/goodtaste_workspace/llama-prefix")
OLD_F2_DIR = ROOT / "results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603"
READINESS_DIR = ROOT / ".codex-temp/paper1_core_judge_protocol_v3/full_rescore_readiness"
MANIFEST_PATH = READINESS_DIR / "full_rescore_request_manifest.jsonl"
INPUT_BINDING_PATH = READINESS_DIR / "input_binding.json"
PROTECTED_HASH_PATH = READINESS_DIR / "protected_input_sha256.json"
CONFIG_PATH = ROOT / "configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json"
OLD_RECOVERY_DIR = ROOT / "results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936"
PARSER = "strict_direct_json_v1"
JUDGE_LABELS = {"harmful": {"unsafe", "refusal", "safe", "broken"}, "benign": {"helpful", "refusal", "unsafe", "broken"}}


class _DuplicateKey(ValueError):
    pass


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


class FullRescoreContractError(RuntimeError):
    pass


class FullRescoreStopError(FullRescoreContractError):
    """A non-retryable identity/evidence/unknown contract violation."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical(value).encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FullRescoreContractError(f"invalid JSON evidence: {path}") from exc
    return value


def verify_readiness_inputs() -> dict[str, Any]:
    binding = load_json(INPUT_BINDING_PATH)
    if not isinstance(binding, Mapping) or binding.get("status") != "FULL_RESCORE_BINDING_PASS":
        raise FullRescoreContractError("full-rescore input binding is not approved")
    if binding.get("logical_identity_count") != 1200 or binding.get("all_cells_exactly_60") is not True:
        raise FullRescoreContractError("full-rescore input binding count/cell gate mismatch")
    config = load_json(CONFIG_PATH)
    runtime = config.get("runtime", {}) if isinstance(config, Mapping) else {}
    judge = runtime.get("judge", {}) if isinstance(runtime, Mapping) else {}
    decoder = runtime.get("decoder", {}) if isinstance(runtime, Mapping) else {}
    expected_judge = {"do_sample": False, "enable_thinking": False, "max_new_tokens": 1296, "num_beams": 1, "parser": PARSER}
    if judge != expected_judge or decoder.get("max_new_tokens") != 512 or decoder.get("do_sample") is not False or decoder.get("num_beams") != 1:
        raise FullRescoreContractError("canonical v2.3 runtime contract mismatch")
    if runtime.get("local_files_only") is not True or runtime.get("gpu") != 0 or runtime.get("device") != "cuda:0":
        raise FullRescoreContractError("offline/single-GPU runtime contract mismatch")
    if config.get("models", {}).get("judge", {}).get("dtype") != "float32":
        raise FullRescoreContractError("Judge dtype is not float32")
    protected = load_json(PROTECTED_HASH_PATH)
    if not isinstance(protected, Mapping) or not protected:
        raise FullRescoreContractError("protected input hash evidence is missing")
    for relative, expected in protected.items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise FullRescoreContractError(f"protected input hash mismatch: {relative}")
    for relative, expected in binding.get("source_hashes", {}).items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise FullRescoreContractError(f"generation source hash mismatch: {relative}")
    return {"binding": binding, "config_sha256": sha256_file(CONFIG_PATH), "protected_hashes": len(protected)}


def parse_direct_json(raw: Any, domain: str) -> tuple[str, str]:
    if not isinstance(raw, str):
        raise FullRescoreContractError("raw Judge completion is not text")
    stripped = raw.strip()
    if "```" in stripped or "<think" in stripped.lower() or "</think" in stripped.lower():
        raise FullRescoreContractError("direct JSON contains markdown or thinking markers")
    try:
        value = json.loads(stripped, object_pairs_hook=_no_duplicate_keys, parse_constant=lambda constant: (_ for _ in ()).throw(ValueError(constant)))
    except (_DuplicateKey, json.JSONDecodeError, ValueError) as exc:
        raise FullRescoreContractError("invalid direct JSON") from exc
    if not isinstance(value, dict) or set(value) != {"label", "rationale"}:
        raise FullRescoreContractError("direct JSON keys are not exact")
    if value["label"] not in JUDGE_LABELS.get(domain, set()):
        raise FullRescoreContractError("direct JSON label is invalid for domain")
    if not isinstance(value["rationale"], str) or not value["rationale"].strip():
        raise FullRescoreContractError("direct JSON rationale is empty")
    label, rationale = value["label"], value["rationale"].strip()
    if "```" in label or "```" in rationale or "<think" in label.lower() or "<think" in rationale.lower():
        raise FullRescoreContractError("direct JSON values contain markdown or thinking markers")
    return label, rationale


def load_manifest(path: Path = MANIFEST_PATH) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FullRescoreContractError(f"manifest missing: {path}")
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FullRescoreContractError(f"manifest line {line_no} is invalid JSON") from exc
        if not isinstance(row, dict):
            raise FullRescoreContractError(f"manifest line {line_no} is not an object")
        rows.append(row)
    if len(rows) != 1200 or [r.get("ordinal") for r in rows] != list(range(1, 1201)):
        raise FullRescoreContractError("manifest must contain ordinals 1..1200")
    identities = [canonical(r.get("logical_identity")) for r in rows]
    if len(set(identities)) != 1200:
        raise FullRescoreContractError("manifest logical identities are not unique")
    if len({r.get("source_response_id") for r in rows}) != 1200:
        raise FullRescoreContractError("manifest response identities are not unique")
    cells: dict[str, int] = {}
    for row in rows:
        if row.get("old_judge_label") is not None or row.get("old_judge_rationale") is not None:
            raise FullRescoreContractError("old Judge label contamination in manifest")
        if row.get("parser") != PARSER or row.get("enable_thinking") is not False or row.get("max_new_tokens") != 1296:
            raise FullRescoreContractError("manifest runtime contract mismatch")
        if not row.get("completion_sha256") or not row.get("prompt_sha256") or not row.get("request_sha256"):
            raise FullRescoreContractError("manifest hash binding is incomplete")
        identity = row.get("logical_identity")
        if not isinstance(identity, Mapping):
            raise FullRescoreContractError("manifest logical identity is not an object")
        expected_cell = {"model_id": identity.get("model_id"), "family": identity.get("family"), "rho": identity.get("rho")}
        if row.get("cell") != expected_cell:
            raise FullRescoreContractError("manifest cell binding does not match logical identity")
        prompt_id = identity.get("prompt_id")
        expected_domain = "harmful" if isinstance(prompt_id, str) and prompt_id.endswith(":harmful") else "benign" if isinstance(prompt_id, str) and prompt_id.endswith(":harmless") else None
        if expected_domain is None or row.get("domain") != expected_domain:
            raise FullRescoreContractError("manifest domain binding does not match logical identity")
        cell_key = f"{expected_cell['model_id']}|{expected_cell['family']}|{expected_cell['rho']}"
        cells[cell_key] = cells.get(cell_key, 0) + 1
        source_line = row.get("source_line")
        if not isinstance(identity, Mapping) or not identity.get("prompt_id") or not isinstance(source_line, Mapping) or any(not isinstance(source_line.get(key), int) or source_line[key] < 1 for key in ("schedule", "attempt", "ledger")):
            raise FullRescoreContractError("manifest logical/source-line binding is incomplete")
        paths = row.get("source_paths")
        expected_paths = {"schedule": str(OLD_F2_DIR / "screen_generation_schedule_core.jsonl"), "attempt": str(OLD_F2_DIR / "screen_generation_attempts_core.jsonl"), "ledger": str(OLD_F2_DIR / "screen_generation_ledger_core.jsonl"), "frames": str(OLD_F2_DIR / "frames.json")}
        if paths != expected_paths:
            raise FullRescoreContractError("manifest generation source paths are not canonical")
    if len(cells) != 20 or any(count != 60 for count in cells.values()):
        raise FullRescoreContractError("manifest must bind exactly 20 cells with 60 logical identities each")
    return rows


def _read_jsonl_row(path: Path, line_number: int) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8").splitlines()[line_number - 1])
    except (OSError, UnicodeDecodeError, IndexError, json.JSONDecodeError) as exc:
        raise FullRescoreContractError(f"generation source row is unreadable: {path}:{line_number}") from exc
    if not isinstance(value, dict):
        raise FullRescoreContractError(f"generation source row is not an object: {path}:{line_number}")
    return value


def load_full_rescore_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Load only old-F2 generation completion and frame prompt; never Judge labels."""
    source_line = row.get("source_line")
    if not isinstance(source_line, Mapping):
        raise FullRescoreContractError("manifest source line binding is missing")
    schedule = _read_jsonl_row(OLD_F2_DIR / "screen_generation_schedule_core.jsonl", int(source_line["schedule"]))
    attempt = _read_jsonl_row(OLD_F2_DIR / "screen_generation_attempts_core.jsonl", int(source_line["attempt"]))
    ledger = _read_jsonl_row(OLD_F2_DIR / "screen_generation_ledger_core.jsonl", int(source_line["ledger"]))
    response_id = row.get("source_response_id")
    if any(value.get("response_id") != response_id for value in (schedule, attempt, ledger)):
        raise FullRescoreContractError("generation response identity mismatch")
    if schedule.get("schedule_id") != row.get("source_schedule_id") or schedule.get("identity") != row.get("logical_identity") or schedule.get("identity") != attempt.get("identity") or schedule.get("identity") != ledger.get("identity"):
        raise FullRescoreContractError("generation logical identity mismatch")
    if schedule.get("status") != "SCHEDULED" or attempt.get("status") != "COMPLETED" or ledger.get("terminal_status") != "COMPLETED":
        raise FullRescoreContractError("generation completion is not terminal")
    frames = load_json(OLD_F2_DIR / "frames.json")
    records = frames.get("safe_pair_split", {}).get("records", [])
    prompt_id = str(row["logical_identity"]["prompt_id"])
    pair_id = prompt_id.rsplit(":", 1)[0]
    frame = next((item for item in records if isinstance(item, Mapping) and item.get("pair_id") == pair_id), None)
    prompt_key = "harmful" if row["domain"] == "harmful" else "harmless"
    prompt, completion = (frame or {}).get(prompt_key), attempt.get("text")
    if not isinstance(prompt, str) or not prompt or not isinstance(completion, str):
        raise FullRescoreContractError("generation prompt/completion payload is invalid")
    if sha256_bytes(prompt.encode()) != row.get("prompt_sha256") or sha256_bytes(completion.encode()) != row.get("completion_sha256"):
        raise FullRescoreContractError("generation prompt/completion hash mismatch")
    request_sha = canonical_sha256({"prompt": prompt, "response": completion, "domain": row["domain"]})
    if request_sha != row.get("request_sha256"):
        raise FullRescoreContractError("generation request hash mismatch")
    return {"prompt": prompt, "response": completion, "domain": row["domain"], "request_sha256": request_sha, "source_response_id": response_id}


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.write_text("".join(canonical(dict(row)) + "\n" for row in rows), encoding="utf-8")


class FullRescoreExecutor:
    """Sequential executor. A backend is injected by tests or an offline fixture."""

    def __init__(self, *, run_dir: Path, backend: Callable[[dict[str, Any], int], Mapping[str, Any]] | None = None, backend_factory: Callable[[], Callable[[dict[str, Any], int], Mapping[str, Any]]] | None = None, manifest_path: Path = MANIFEST_PATH, max_retry: int = 1):
        if (backend is None) == (backend_factory is None):
            raise FullRescoreContractError("provide exactly one backend or backend_factory")
        if isinstance(max_retry, bool) or max_retry not in (0, 1):
            raise FullRescoreContractError("max_retry must be 0 or 1")
        self.run_dir, self.backend, self.backend_factory, self.manifest_path, self.max_retry = run_dir, backend, backend_factory, manifest_path, max_retry
        self.actual_calls = 0

    def preflight(self) -> dict[str, Any]:
        protection = verify_readiness_inputs() if self.manifest_path.resolve() == MANIFEST_PATH.resolve() else {"binding": {"status": "CUSTOM_FIXTURE_MANIFEST"}, "config_sha256": None, "protected_hashes": 0}
        rows = load_manifest(self.manifest_path)
        return {"status": "PRECHECK_PASS", "records": len(rows), "logical_budget": len(rows), "actual_judge_calls": 0, "parser": PARSER, "judge": {"enable_thinking": False, "max_new_tokens": 1296, "do_sample": False, "num_beams": 1}, "input_protection": protection}

    def run(self) -> dict[str, Any]:
        preflight = self.preflight()
        if self.run_dir.exists():
            raise FullRescoreContractError("new run directory must be absent")
        resolved_run = self.run_dir.resolve()
        for protected_root in (OLD_F2_DIR.resolve(), OLD_RECOVERY_DIR.resolve()):
            if resolved_run == protected_root or protected_root in resolved_run.parents:
                raise FullRescoreContractError("full-rescore run directory overlaps protected historical output")
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (self.run_dir / "request_manifest.jsonl").write_text(self.manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
        backend = self.backend
        if backend is None:
            try:
                backend = self.backend_factory()
            except Exception as exc:
                (self.run_dir / "launcher_status.json").write_text(json.dumps({"status": "BACKEND_CONSTRUCTION_BLOCKED", "models_loaded": 0, "actual_judge_requests": 0, "error": str(exc)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                return {"status": "CORE_SCREEN_V3_BLOCKED", "logical_identity_count": 0, "actual_judge_calls": 0, "terminal_accounting_complete": False, "stopped_on_contract_failure": True}
        records, events = [], []
        stopped = False
        for row in load_manifest(self.manifest_path):
            attempts, final = [], None
            stop_after = False
            try:
                payload = load_full_rescore_payload(row)
            except FullRescoreContractError as exc:
                final = {"ordinal": row["ordinal"], "logical_identity": row["logical_identity"], "source_response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "attempt": 0, "retry_count": 0, "actual_call_counts": {"four_class": 0, "binary": 0}, "parser_status": "CONTRACT_FAILURE", "stop_reason": str(exc), "status": "CONTRACT_FAILURE", "missing": True, "attempt_records": []}
                records.append(final)
                events.append({"event": final["status"], "ordinal": row["ordinal"]})
                stopped = True
                break
            for retry_no in range(self.max_retry + 1):
                if self.actual_calls >= 2400:
                    raise FullRescoreContractError("actual Judge call budget exceeded")
                self.actual_calls += 1
                events.append({"event": "REQUEST", "ordinal": row["ordinal"], "attempt": retry_no + 1})
                raw = None
                diagnostics = None
                try:
                    result = dict(backend({**row, "payload": payload}, retry_no))
                    expected = {"ordinal": row["ordinal"], "response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "parser": PARSER, "enable_thinking": False, "max_new_tokens": 1296}
                    if result.get("request_identity") != expected:
                        raise FullRescoreStopError("request identity mismatch")
                    if result.get("status") == "MISSING":
                        reported_counts = result.get("actual_call_counts", {"four_class": 0, "binary": 0})
                        if reported_counts != {"four_class": 0, "binary": 0}:
                            raise FullRescoreStopError("missing record reported a Judge call")
                        self.actual_calls -= 1
                        attempts.append({"attempt": retry_no + 1, "status": "MISSING", "reason": result.get("reason", "backend_missing")})
                        final = {"ordinal": row["ordinal"], "logical_identity": row["logical_identity"], "source_response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "attempt": retry_no + 1, "retry_count": retry_no, "actual_call_counts": {"four_class": retry_no, "binary": 0}, "parser_status": "NOT_REQUESTED", "stop_reason": result.get("reason", "backend_missing"), "status": "MISSING", "missing": True, "attempt_records": attempts}
                        break
                    if result.get("status") == "TECHNICAL_FAILURE":
                        attempts.append({"attempt": retry_no + 1, "status": "TECHNICAL_FAILURE", "error": result.get("error", "backend technical failure")})
                        if retry_no >= self.max_retry:
                            final = {"ordinal": row["ordinal"], "logical_identity": row["logical_identity"], "source_response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "attempt": retry_no + 1, "retry_count": retry_no, "actual_call_counts": {"four_class": retry_no + 1, "binary": 0}, "parser_status": "NOT_REQUESTED", "stop_reason": result.get("error", "backend technical failure"), "status": "TECHNICAL_FAILURE", "missing": True, "attempt_records": attempts}
                            break
                        continue
                    raw = result.get("raw")
                    diagnostics = result.get("diagnostics")
                    if not isinstance(raw, str) or not isinstance(diagnostics, Mapping):
                        raise FullRescoreStopError("raw/diagnostics evidence unavailable")
                    label, rationale = parse_direct_json(raw, row["domain"])
                    if "actual_call_counts" in result and result["actual_call_counts"] != {"four_class": 1, "binary": 0}:
                        raise FullRescoreStopError("backend reported binary or duplicate calls")
                    attempts.append({"attempt": retry_no + 1, "status": "PARSED", "raw": raw, "raw_sha256": sha256_bytes(raw.encode()), "diagnostics": dict(diagnostics), "diagnostics_sha256": canonical_sha256(diagnostics), "token_count": diagnostics.get("token_count")})
                    final = {"ordinal": row["ordinal"], "logical_identity": row["logical_identity"], "source_response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "attempt": retry_no + 1, "retry_count": retry_no, "actual_call_counts": {"four_class": retry_no + 1, "binary": 0}, "raw": raw, "raw_sha256": sha256_bytes(raw.encode()), "diagnostics": dict(diagnostics), "diagnostics_sha256": canonical_sha256(diagnostics), "token_count": diagnostics.get("token_count"), "label": label, "rationale": rationale, "parser_status": "PARSED", "stop_reason": None, "status": "PARSED", "missing": False, "attempt_records": attempts}
                    break
                except FullRescoreStopError as exc:
                    attempts.append({"attempt": retry_no + 1, "status": "CONTRACT_FAILURE", "error": str(exc)})
                    final = {"ordinal": row["ordinal"], "logical_identity": row["logical_identity"], "source_response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "attempt": retry_no + 1, "retry_count": retry_no, "actual_call_counts": {"four_class": retry_no + 1, "binary": 0}, "parser_status": "CONTRACT_FAILURE", "stop_reason": str(exc), "status": "CONTRACT_FAILURE", "missing": True, "attempt_records": attempts}
                    stop_after = True
                    break
                except FullRescoreContractError as exc:
                    attempts.append({"attempt": retry_no + 1, "status": "PARSE_FAILURE", "error": str(exc), "raw": raw if isinstance(raw, str) else "RAW_UNAVAILABLE", "raw_sha256": sha256_bytes(raw.encode()) if isinstance(raw, str) else None, "diagnostics": dict(diagnostics) if isinstance(diagnostics, Mapping) else "DIAGNOSTICS_UNAVAILABLE", "diagnostics_sha256": canonical_sha256(diagnostics) if isinstance(diagnostics, Mapping) else None, "token_count": diagnostics.get("token_count") if isinstance(diagnostics, Mapping) else None})
                except Exception as exc:
                    attempts.append({"attempt": retry_no + 1, "status": "CONTRACT_FAILURE", "error": f"unknown backend error: {exc}"})
                    final = {"ordinal": row["ordinal"], "logical_identity": row["logical_identity"], "source_response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "attempt": retry_no + 1, "retry_count": retry_no, "actual_call_counts": {"four_class": retry_no + 1, "binary": 0}, "parser_status": "CONTRACT_FAILURE", "stop_reason": f"unknown backend error: {exc}", "status": "CONTRACT_FAILURE", "missing": True, "attempt_records": attempts}
                    stop_after = True
                    break
                if retry_no >= self.max_retry:
                    stop_after = True
                    break
            if final is None:
                final = {"ordinal": row["ordinal"], "logical_identity": row["logical_identity"], "source_response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "attempt": len(attempts), "retry_count": max(0, len(attempts) - 1), "actual_call_counts": {"four_class": len(attempts), "binary": 0}, "parser_status": "PARSE_FAILURE", "stop_reason": "retry_limit_exceeded", "status": "PARSE_FAILURE", "missing": True, "attempt_records": attempts}
            records.append(final)
            events.append({"event": final["status"], "ordinal": row["ordinal"]})
            if stop_after:
                stopped = True
                break
        _write_jsonl(self.run_dir / "request_records.jsonl", records)
        _write_jsonl(self.run_dir / "attempt_records.jsonl", [attempt | {"ordinal": record["ordinal"]} for record in records for attempt in record.get("attempt_records", [])])
        _write_jsonl(self.run_dir / "events.jsonl", events)
        cell_counts: dict[str, dict[str, int]] = {}
        for row in records:
            ident = row["logical_identity"]
            cell = f"{ident['model_id']}|{ident['family']}|{ident['rho']}"
            cell_counts.setdefault(cell, {"logical": 0, "parsed": 0, "missing": 0})
            cell_counts[cell]["logical"] += 1
            cell_counts[cell]["parsed"] += row["status"] == "PARSED"
            cell_counts[cell]["missing"] += row.get("missing", False)
        gate = {cell: {**counts, "pass": counts["missing"] <= 1} for cell, counts in sorted(cell_counts.items())}
        status = "CORE_SCREEN_V3_PASS" if not stopped and len(records) == 1200 and len(gate) == 20 and all(v["pass"] for v in gate.values()) else "CORE_SCREEN_V3_BLOCKED"
        summary = {"status": status, "logical_identity_count": len(records), "terminal_accounting_complete": len(records) == 1200, "stopped_on_contract_failure": stopped, "actual_judge_calls": self.actual_calls, "logical_budget": 1200, "technical_failures": sum(r["status"] == "TECHNICAL_FAILURE" for r in records), "contract_failures": sum(r["status"] == "CONTRACT_FAILURE" for r in records), "parse_failures": sum(r["status"] == "PARSE_FAILURE" for r in records), "missing": sum(r.get("missing", False) for r in records), "retry_calls": sum(r.get("retry_count", 0) for r in records), "cell_gate": gate, "dose_decision_written": status == "CORE_SCREEN_V3_PASS"}
        (self.run_dir / "terminal_accounting.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if status == "CORE_SCREEN_V3_PASS":
            (self.run_dir / "dose_decision.json").write_text(json.dumps({"status": "CORE_SCREEN_V3_PASS", "readiness": "CORE_A_S_READY_FOR_FORMAL_EVALUATION", "cells": gate}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary
