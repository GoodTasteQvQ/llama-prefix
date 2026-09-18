#!/usr/bin/env python3
"""Bounded, approval-gated executor for the v3 direct-JSON recovery.

The production path deliberately has no model construction in this module until
``preflight`` has passed.  Tests inject an in-memory backend and never use the
canonical approval path.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path("/data/goodtaste_workspace/llama-prefix")
APPROVAL_PATH = ROOT / ".codex-temp/paper1_core_judge_protocol_v3/CORE_JUDGE_PROTOCOL_V3_RECOVERY_APPROVAL.md"
PROPOSAL_DIR = ROOT / ".codex-temp/paper1_core_judge_protocol_v3/recovery_proposal"
MANIFEST_PATH = PROPOSAL_DIR / "recovery_input_manifest.jsonl"
CONFIG_PATH = ROOT / "configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json"
DESIGN_PATH = ROOT / "writing/broadening design/paper1_minimal_broadening_experiment_design_v2.3_direct_json.md"
REPORT_PATH = ROOT / "writing/broadening design/report/paper1_core_judge_protocol_v3_recovery_proposal_report.md"
OLD_F2_DIR = ROOT / "results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603"
OLD_F2_JUDGE_PATH = OLD_F2_DIR / "screen_judge_records_core.jsonl"
EXECUTOR_RELATIVE_PATH = "scripts/core_judge_recovery_executor.py"
PARSER = "strict_direct_json_v1"


class RecoveryContractError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryContractError(f"invalid JSON: {path}") from exc


def load_manifest(path: Path = MANIFEST_PATH) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RecoveryContractError(f"manifest missing: {path}")
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise RecoveryContractError(f"manifest line {line_number} is blank")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RecoveryContractError(f"manifest line {line_number} is invalid JSON") from exc
        if not isinstance(row, dict):
            raise RecoveryContractError(f"manifest line {line_number} is not an object")
        rows.append(row)
    if len(rows) != 13:
        raise RecoveryContractError(f"manifest must contain exactly 13 rows, got {len(rows)}")
    ordinals = [row.get("ordinal") for row in rows]
    if ordinals != list(range(1, 14)):
        raise RecoveryContractError("manifest order/ordinals are not 1..13")
    response_ids = [row.get("source_response_id") for row in rows]
    if len(set(response_ids)) != 13 or any(not isinstance(value, str) for value in response_ids):
        raise RecoveryContractError("manifest response identities are not unique")
    logical_ids = [canonical(row.get("logical_identity")) for row in rows]
    if len(set(logical_ids)) != 13:
        raise RecoveryContractError("manifest logical identities are not unique")
    for row in rows:
        identity = row.get("logical_identity")
        if not isinstance(identity, dict) or not identity.get("prompt_id"):
            raise RecoveryContractError("manifest logical identity is incomplete")
        if row.get("old_judge_status") != "PARSE_FAILURE" or row.get("old_missing") is not True:
            raise RecoveryContractError("manifest contains a non-failure or non-missing source row")
        if row.get("old_call_counts") != {"binary": 0, "four_class": 2}:
            raise RecoveryContractError("old call-count evidence mismatch")
        if row.get("old_retry_counts") != {"additional_judge": 1, "generation": 0}:
            raise RecoveryContractError("old retry-count evidence mismatch")
        source_paths = row.get("source_paths")
        source_lines = row.get("source_line_numbers")
        if not isinstance(source_paths, dict) or not isinstance(source_lines, dict):
            raise RecoveryContractError("manifest source evidence is incomplete")
        if Path(source_paths.get("judge", "")).resolve() != OLD_F2_JUDGE_PATH.resolve():
            raise RecoveryContractError("manifest judge source is not the protected old F2")
        source_path = source_paths.get("frames")
        if not isinstance(source_path, str) or not Path(source_path).is_file():
            raise RecoveryContractError("manifest source evidence is invalid: frames")
        for source_name in ("generation_attempt", "generation_ledger", "judge", "schedule"):
            source_path = source_paths.get(source_name)
            source_line = source_lines.get(source_name)
            if not isinstance(source_path, str) or not Path(source_path).is_file() or not isinstance(source_line, int) or source_line < 1:
                raise RecoveryContractError(f"manifest source evidence is invalid: {source_name}")
        source_row = _read_jsonl_row(Path(source_paths["judge"]), source_lines["judge"])
        _verify_old_f2_row(row, source_row)
    return rows


def _read_jsonl_row(path: Path, line_number: int) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        raw = lines[line_number - 1]
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, IndexError, json.JSONDecodeError) as exc:
        raise RecoveryContractError(f"old F2 source row is unreadable: {path}:{line_number}") from exc
    if not isinstance(value, dict):
        raise RecoveryContractError(f"old F2 source row is not an object: {path}:{line_number}")
    return value


def _verify_old_f2_row(row: Mapping[str, Any], source_row: Mapping[str, Any]) -> None:
    if source_row.get("response_id") != row.get("source_response_id"):
        raise RecoveryContractError("manifest response identity does not match old F2")
    if source_row.get("request_sha256") != row.get("request_sha256"):
        raise RecoveryContractError("manifest request hash does not match old F2")
    if source_row.get("four_class_status") != "PARSE_FAILURE" or source_row.get("four_class_error") != row.get("old_parse_error"):
        raise RecoveryContractError("manifest row is not the recorded old F2 PARSE_FAILURE")
    if source_row.get("actual_call_counts") != {"binary": 0, "four_class": 2}:
        raise RecoveryContractError("old F2 call-count evidence does not match manifest")
    if source_row.get("binary_status") != "NOT_REQUESTED" or source_row.get("binary_raw") is not None:
        raise RecoveryContractError("old F2 binary evidence is not zero")
    if source_row.get("four_class_raw") is not None or source_row.get("four_class_label") is not None or source_row.get("four_class_rationale") is not None:
        raise RecoveryContractError("old F2 PARSE_FAILURE unexpectedly has semantic output")
    identity = row.get("logical_identity")
    if isinstance(identity, Mapping) and "domain" in identity and identity.get("domain") != source_row.get("domain"):
        raise RecoveryContractError("manifest domain does not match old F2")


def _approval_fields(approval: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(approval, Mapping):
        raise RecoveryContractError("recovery approval is not an object")
    if approval.get("status") != "APPROVED":
        raise RecoveryContractError("recovery approval status is not APPROVED")
    required = ("proposal_sha256", "manifest_sha256", "design_sha256", "config_sha256", "code_hashes")
    missing = [field for field in required if field not in approval]
    if missing:
        raise RecoveryContractError(f"approval missing fields: {','.join(missing)}")
    return approval


def verify_approval(
    *,
    approval_path: Path = APPROVAL_PATH,
    manifest_path: Path = MANIFEST_PATH,
    config_path: Path = CONFIG_PATH,
    design_path: Path = DESIGN_PATH,
    report_path: Path = REPORT_PATH,
    approval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify approval and all immutable inputs before constructing a model."""
    if Path(approval_path).resolve() != APPROVAL_PATH.resolve():
        raise RecoveryContractError("recovery approval path is not the canonical path")
    if approval is None:
        if not approval_path.is_file():
            raise RecoveryContractError("canonical recovery approval is missing")
        approval = load_json(approval_path)
    _approval_fields(approval)
    if approval.get("maximum_four_class_requests", 13) != 13 or approval.get("per_input_maximum", 1) != 1:
        raise RecoveryContractError("approval request budget is not exactly 13/1")
    if approval.get("binary_judge_requests", 0) != 0 or approval.get("generation_retries", 0) != 0 or approval.get("additional_judge_retries", 0) != 0:
        raise RecoveryContractError("approval retry/binary budget is nonzero")
    manifest_sha = sha256_file(manifest_path)
    if approval["manifest_sha256"] != manifest_sha:
        raise RecoveryContractError("approval manifest hash mismatch")
    if approval["design_sha256"] != sha256_file(design_path):
        raise RecoveryContractError("approval design hash mismatch")
    if approval["config_sha256"] != sha256_file(config_path):
        raise RecoveryContractError("approval config hash mismatch")
    if approval["proposal_sha256"] != sha256_file(report_path):
        raise RecoveryContractError("approval proposal hash mismatch")
    code_hashes = approval["code_hashes"]
    if not isinstance(code_hashes, dict) or not code_hashes:
        raise RecoveryContractError("approval code_hashes must be nonempty")
    if EXECUTOR_RELATIVE_PATH not in code_hashes:
        raise RecoveryContractError("approval must bind the current recovery executor source")
    for name, expected in code_hashes.items():
        path = ROOT / name
        if not isinstance(expected, str) or len(expected) != 64 or not path.is_file() or sha256_file(path) != expected:
            raise RecoveryContractError(f"approval code hash mismatch: {name}")
    cfg = load_json(config_path)
    runtime = cfg.get("runtime", {})
    judge = runtime.get("judge", {})
    decoder = runtime.get("decoder", {})
    if judge != {"do_sample": False, "enable_thinking": False, "max_new_tokens": 1296, "num_beams": 1, "parser": PARSER}:
        raise RecoveryContractError("direct-JSON Judge runtime contract mismatch")
    if decoder.get("max_new_tokens") != 512 or decoder.get("do_sample") is not False or decoder.get("num_beams") != 1:
        raise RecoveryContractError("behavior decoder contract mismatch")
    if runtime.get("local_files_only") is not True or runtime.get("gpu") != 0 or runtime.get("device") != "cuda:0":
        raise RecoveryContractError("offline/single-GPU runtime contract mismatch")
    if cfg.get("models", {}).get("judge", {}).get("dtype") != "float32":
        raise RecoveryContractError("Judge dtype is not float32")
    rows = load_manifest(manifest_path)
    return {"approval_path": str(APPROVAL_PATH), "manifest_sha256": manifest_sha, "row_count": len(rows), "parser": PARSER, "enable_thinking": False, "max_new_tokens": 1296, "decoder_max_new_tokens": 512}


def parse_direct_json(raw: Any, domain: str) -> tuple[str, str]:
    if not isinstance(raw, str):
        raise RecoveryContractError("raw Judge completion is not text")
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise RecoveryContractError("invalid direct JSON") from exc
    labels = {"unsafe", "refusal", "safe", "broken"} if domain == "harmful" else {"helpful", "refusal", "unsafe", "broken"}
    if not isinstance(value, dict) or set(value) != {"label", "rationale"}:
        raise RecoveryContractError("direct JSON keys are not exact")
    if value["label"] not in labels or not isinstance(value["rationale"], str) or not value["rationale"].strip():
        raise RecoveryContractError("direct JSON semantic contract failed")
    return value["label"], value["rationale"]


class RecoveryExecutor:
    """Sequential one-shot runner; ``backend`` is the only model boundary."""

    def __init__(self, *, backend: Callable[[dict[str, Any]], Mapping[str, Any]] | None = None, backend_factory: Callable[[], Callable[[dict[str, Any]], Mapping[str, Any]]] | None = None, run_dir: Path, manifest_path: Path = MANIFEST_PATH, approval: Mapping[str, Any] | None = None, approval_path: Path = APPROVAL_PATH):
        if backend is not None and backend_factory is not None:
            raise ValueError("provide backend or backend_factory, not both")
        self.backend = backend
        self.backend_factory = backend_factory
        self.run_dir = run_dir
        self.manifest_path = manifest_path
        self.approval = approval
        self.approval_path = approval_path
        self.calls = 0

    def preflight(self) -> dict[str, Any]:
        return verify_approval(approval_path=self.approval_path, manifest_path=self.manifest_path, approval=self.approval)

    @staticmethod
    def _append_event(path: Path, event: Mapping[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(canonical(dict(event)) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _record_observability(record: dict[str, Any], result: Mapping[str, Any] | None) -> None:
        if not isinstance(result, Mapping):
            record.update({"raw": "RAW_UNAVAILABLE", "raw_sha256": None, "diagnostics": "DIAGNOSTICS_UNAVAILABLE", "diagnostics_sha256": None, "observability_status": "RAW_UNAVAILABLE"})
            return
        raw = result.get("raw")
        diagnostics = result.get("diagnostics")
        raw_available = isinstance(raw, str)
        diagnostics_available = isinstance(diagnostics, Mapping)
        record["raw"] = raw if raw_available else "RAW_UNAVAILABLE"
        record["raw_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw_available else None
        record["diagnostics"] = dict(diagnostics) if diagnostics_available else "DIAGNOSTICS_UNAVAILABLE"
        record["diagnostics_sha256"] = canonical_sha256(diagnostics) if diagnostics_available else None
        if raw_available and diagnostics_available:
            record["observability_status"] = "RAW_AND_DIAGNOSTICS_AVAILABLE"
        elif raw_available:
            record["observability_status"] = "RAW_AVAILABLE_DIAGNOSTICS_UNAVAILABLE"
        elif diagnostics_available:
            record["observability_status"] = "DIAGNOSTICS_AVAILABLE_RAW_UNAVAILABLE"
        else:
            record["observability_status"] = "RAW_UNAVAILABLE"

    def run(self) -> dict[str, Any]:
        preflight = self.preflight()
        rows = load_manifest(self.manifest_path)
        if self.run_dir.exists():
            raise RecoveryContractError("recovery run directory must be new and absent")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        events_path = self.run_dir / "recovery_events.jsonl"
        (self.run_dir / "recovery_preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        backend = self.backend
        if backend is None:
            if self.backend_factory is None:
                raise RecoveryContractError("no bounded backend or backend_factory supplied")
            try:
                backend = self.backend_factory()
            except Exception as exc:
                summary = {"status": "STOPPED_ON_FAILURE", "records": 0, "actual_four_class_requests": 0, "binary_requests": 0, "generation_retries": 0, "additional_judge_retries": 0, "model_construction": "FAILED", "error": str(exc), "preflight": preflight}
                (self.run_dir / "recovery_runtime_status.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                return summary
        records: list[dict[str, Any]] = []
        for row in rows:
            if self.calls >= 13:
                raise RecoveryContractError("request budget exceeded")
            started = time.time()
            request_identity = {"ordinal": row["ordinal"], "response_id": row["source_response_id"], "request_sha256": row["request_sha256"], "parser": PARSER, "enable_thinking": False, "max_new_tokens": 1296}
            record: dict[str, Any] = {"ordinal": row["ordinal"], "source_response_id": row["source_response_id"], "input_sha256": row["request_sha256"], "request_identity": request_identity, "actual_call_counts": {"four_class": 0, "binary": 0}, "generation_retries": 0, "additional_judge_retries": 0, "parser_status": "NOT_STARTED", "status": "UNEXECUTED"}
            self._record_observability(record, None)
            self._append_event(events_path, {"event": "REQUEST_READY", "record": record})
            result: dict[str, Any] | None = None
            try:
                self.calls += 1
                record["actual_call_counts"]["four_class"] = 1
                result = dict(backend(row))
                self._record_observability(record, result)
                returned_identity = result.get("request_identity")
                if returned_identity is not None and returned_identity != request_identity:
                    raise RecoveryContractError("backend request identity mismatch")
                reported_counts = result.get("actual_call_counts")
                if reported_counts is not None and reported_counts != {"binary": 0, "four_class": 1}:
                    raise RecoveryContractError("backend reported a retry or binary call")
                for key in ("generation_retries", "additional_judge_retries", "binary_requests"):
                    if key in result and result[key] != 0:
                        raise RecoveryContractError(f"backend reported nonzero {key}")
                self._append_event(events_path, {"event": "RESPONSE_RECEIVED", "record": record})
                if not isinstance(result.get("raw"), str):
                    raise RecoveryContractError("raw Judge completion unavailable")
                if not isinstance(result.get("diagnostics"), Mapping):
                    raise RecoveryContractError("Judge diagnostics unavailable")
                label, rationale = parse_direct_json(result["raw"], row["logical_identity"].get("domain", "harmful"))
                record.update({"status": "PARSED", "parser_status": "PARSED", "label": label, "rationale": rationale})
                self._append_event(events_path, {"event": "PARSED", "record": record})
            except Exception as exc:
                if record["actual_call_counts"]["four_class"] == 0:
                    self.calls += 1
                    record["actual_call_counts"]["four_class"] = 1
                self._record_observability(record, result)
                record.update({"status": "PARSE_FAILURE", "parser_status": "PARSE_FAILURE", "label": None, "rationale": None, "error": str(exc), "missing": True, "elapsed_seconds": time.time() - started})
                self._append_event(events_path, {"event": "STOPPED_ON_FAILURE", "record": record})
                records.append(record)
                break
            record["elapsed_seconds"] = time.time() - started
            records.append(record)
        with (self.run_dir / "recovery_judge_records.jsonl").open("w", encoding="utf-8") as handle:
            handle.write("".join(canonical(r) + "\n" for r in records))
            handle.flush()
            os.fsync(handle.fileno())
        summary = {"status": "COMPLETED" if len(records) == 13 and all(r["status"] == "PARSED" for r in records) else "STOPPED_ON_FAILURE", "records": len(records), "actual_four_class_requests": self.calls, "binary_requests": 0, "generation_retries": 0, "additional_judge_retries": 0, "preflight": preflight}
        (self.run_dir / "recovery_runtime_status.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary


def main() -> int:
    raise SystemExit("This bounded executor is library/approval gated; use the separately approved runner.")


if __name__ == "__main__":
    main()
