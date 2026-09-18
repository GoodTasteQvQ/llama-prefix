#!/usr/bin/env python3
"""Validate batch 1 evidence and materialize the append-only expanded public input."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / ".codex-temp" / "paper1_source_recovery_v2"
BATCH_RUN = RECOVERY / "batch1_review_run"
CANDIDATE = RECOVERY / "candidate_research" / "turkish-over-refusal-set"
CANDIDATE_DATA = CANDIDATE / "data" / "turkish_over_refusal.jsonl"
SOURCE_COPY = RECOVERY / "sources" / "turkish-over-refusal-set-13682bf03c9e" / "data" / "turkish_over_refusal.jsonl"
OLD_SOURCE = ROOT / "data" / "safe_pairs_public_semantic_v1.json"
OLD_LEDGER = ROOT / ".codex-temp" / "paper1_broadening_machine_reviews" / "public-semantic-pairs-v2-20260908T111917Z" / "public_pair_quality_decisions.v2.rebuilt.json"
OLD_CONFIG = ROOT / "configs" / "paper1_broadening" / "mbd_nm_v211_public_assets.json"
FREEZE = RECOVERY / "batch1_freeze.json"
FREEZE_STARTED = RECOVERY / "batch1_freeze_review_started.json"
BATCH_PAIRS = RECOVERY / "batch1_pairs.json"
BATCH_LEDGER = BATCH_RUN / "public_pair_quality_decisions.batch1.json"
BATCH_SUMMARY = BATCH_RUN / "rebuilt_summary.batch1.json"
EXPANDED_SOURCE = ROOT / "data" / "safe_pairs_public_semantic_v2_expanded.json"
EXPANDED_LEDGER = ROOT / "data" / "safe_pairs_public_semantic_v2_expanded_ledger.json"
EXPANDED_CONFIG = ROOT / "configs" / "paper1_broadening" / "mbd_nm_v212_public_expanded.json"
MANIFEST = ROOT / "data" / "safe_pairs_public_semantic_v2_expanded.manifest.json"
AUDIT = RECOVERY / "batch1_review_run" / "batch1_raw_audit.json"
SUMMARY = RECOVERY / "expanded_summary.json"

EXPECTED_SOURCE_SHA = "009a58760b4b22b445a53b6ca52213af3ae98cb5f9dc04d0c2f70192231b3cce"
EXPECTED_CANDIDATE_SHA = "5e1910a1dfb129de7c68ee875143e2e810056efec895dec9b1b5cf663709f396"
EXPECTED_OLD_LEDGER_SHA = "f5d9ce975a5214b2c8ffdd343497cf35ceb565d1904ee809d872ad284a4f34fe"
EXPECTED_DIGEST = "db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7"
REVISION = "public-semantic-pair-quality-v2"
DESIGN_REVISION = "MBD-NM v2.1.2-public-pairs-expanded"


def sha_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def fail(message: str) -> None:
    raise SystemExit("RECOVERY_INTEGRATION_CHECK_FAILED: " + message)


def check(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load_candidate_pairs() -> dict[str, dict[str, Any]]:
    check(sha_bytes(CANDIDATE_DATA) == EXPECTED_CANDIDATE_SHA, "candidate data hash differs")
    copied_hash = sha_bytes(SOURCE_COPY) if SOURCE_COPY.is_file() else None
    check(copied_hash == EXPECTED_CANDIDATE_SHA, "frozen source copy hash differs")
    try:
        commit = subprocess.check_output(["git", "-C", str(CANDIDATE), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        fail(f"cannot read candidate commit: {exc}")
    check(commit == "13682bf03c9e7805b81df2eab7e23fb2512e560b", "candidate commit differs")
    groups: dict[str, list[dict[str, Any]]] = {}
    for line_index, line in enumerate(CANDIDATE_DATA.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        row["source_line_index"] = line_index
        groups.setdefault(str(row.get("pair_id")), []).append(row)
    result: dict[str, dict[str, Any]] = {}
    for pair_id, rows in groups.items():
        english = [row for row in rows if row.get("lang") == "en"]
        safe = [row for row in english if row.get("type") == "safe"]
        harmful = [row for row in english if row.get("type") == "harmful"]
        check(len(english) == 2 and len(safe) == 1 and len(harmful) == 1, f"candidate structure invalid for {pair_id}")
        check(all(isinstance(row.get("prompt"), str) and row["prompt"].strip() for row in english), f"candidate text invalid for {pair_id}")
        result[f"turkish-over-refusal-set:{pair_id}"] = {
            "pair_id": f"turkish-over-refusal-set:{pair_id}",
            "harmful": harmful[0]["prompt"],
            "harmless": safe[0]["prompt"],
            "harmful_source_index": harmful[0]["source_line_index"],
            "harmless_source_index": safe[0]["source_line_index"],
            "source_dataset": "fevziegeyurtsevenler/turkish-over-refusal-set",
            "source_file": "data/turkish_over_refusal.jsonl",
            "source_revision": "13682bf03c9e7805b81df2eab7e23fb2512e560b",
            "upstream_pair_id": int(pair_id) if pair_id.isdigit() else pair_id,
        }
    check(len(result) == 120, "candidate pair count differs")
    return result


def validate_freeze(batch_pairs: list[dict[str, Any]], candidate: dict[str, dict[str, Any]]) -> None:
    freeze = read(FREEZE_STARTED)
    check(freeze.get("review_started") is True, "freeze does not record started review")
    selected = freeze.get("selected_pair_ids")
    check(selected == [f"turkish-over-refusal-set:{i}" for i in range(1, 101)], "selected order differs")
    check(freeze.get("precheck_excluded_pair_ids") == [], "precheck exclusions are not empty")
    check(freeze.get("not_selected_pair_ids") == [f"turkish-over-refusal-set:{i}" for i in range(101, 121)], "not-selected IDs differ")
    check(len(batch_pairs) == 100, "batch pair count differs")
    check([row.get("pair_id") for row in batch_pairs] == selected, "batch order differs from freeze")
    for row in batch_pairs:
        source = candidate.get(row.get("pair_id"))
        check(source is not None, f"batch pair missing from candidate: {row.get('pair_id')}")
        check(row.get("harmful") == source["harmful"] and row.get("harmless") == source["harmless"], f"batch text mismatch: {row.get('pair_id')}")
        check(row.get("preliminary_eligible") is True and row.get("precheck_exclusion_reasons") == [], f"batch precheck invalid: {row.get('pair_id')}")


def validate_raw(batch_pairs: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_id = {row["pair_id"]: row for row in batch_pairs}
    envelopes: dict[str, dict[str, Any]] = {}
    thread_ids: set[str] = set()
    attempt_counts: Counter[int] = Counter()
    retry_ids: list[str] = []
    for pair_id, pair in by_id.items():
        for side in ("a", "b"):
            request_id = pair_id.replace(":", "_") + f".{side}"
            path = BATCH_RUN / "raw" / side / f"{request_id}.json"
            check(path.is_file(), f"missing raw envelope: {path}")
            value = read(path)
            check(value.get("schema_version") == "public-safe-pair-review-request-v2", f"raw schema invalid: {request_id}")
            check(value.get("status") == "ok" and value.get("side") == side and value.get("pair_id") == pair_id, f"raw binding invalid: {request_id}")
            check(value.get("request_id") == request_id, f"request ID invalid: {request_id}")
            identity = value.get("agent_identity", {})
            thread_id = identity.get("thread_id")
            check(isinstance(thread_id, str) and thread_id and thread_id not in thread_ids, f"thread identity invalid or duplicated: {request_id}")
            thread_ids.add(thread_id)
            pair_input = value.get("pair_input")
            expected_input = {"pair_id": pair_id, "harmful": pair["harmful"], "harmless": pair["harmless"], "evaluation_frame_digest": EXPECTED_DIGEST}
            check(pair_input == expected_input, f"pair input mismatch: {request_id}")
            check(value.get("pair_input_json_sha256") == sha_text(canonical(expected_input)), f"pair input hash mismatch: {request_id}")
            parsed = value.get("parsed_output")
            check(isinstance(parsed, dict), f"parsed output missing: {request_id}")
            check(parsed.get("pair_id") == pair_id and parsed.get("prompt_revision") == REVISION, f"parsed binding invalid: {request_id}")
            check(parsed.get("verdict") in {"include", "exclude", "uncertain"}, f"parsed verdict invalid: {request_id}")
            for field in ("harmful_is_materially_unsafe", "harmless_is_materially_benign", "semantic_pair_is_comparable", "evaluation_overlap_checked"):
                check(isinstance(parsed.get(field), bool), f"parsed boolean invalid: {request_id}:{field}")
            check(isinstance(parsed.get("rationale"), str) and parsed["rationale"].strip(), f"parsed rationale missing: {request_id}")
            raw_output = value.get("raw_output")
            check(isinstance(raw_output, str) and json.loads(raw_output) == parsed, f"raw output mismatch: {request_id}")
            check(value.get("raw_output_sha256") == sha_text(raw_output), f"raw output hash mismatch: {request_id}")
            attempts = value.get("attempts")
            check(isinstance(attempts, list) and value.get("attempt_count") == len(attempts) and len(attempts) >= 1, f"attempt record invalid: {request_id}")
            attempt_counts[len(attempts)] += 1
            if len(attempts) > 1:
                retry_ids.append(request_id)
            for attempt in attempts:
                event_path = Path(str(attempt.get("event_path", "")))
                check(event_path.is_file(), f"attempt event missing: {request_id}")
                check(attempt.get("returncode") == 0, f"attempt returncode invalid: {request_id}")
            envelopes[f"{pair_id}|{side}"] = value
    check(len(envelopes) == 200 and len(thread_ids) == 200, "raw envelope or thread count differs")
    return envelopes, {"request_envelopes": 200, "unique_thread_ids": 200, "attempt_counts": dict(sorted(attempt_counts.items())), "retry_request_ids": retry_ids}


def validate_batch_ledger(batch_pairs: list[dict[str, Any]], envelopes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    document = read(BATCH_LEDGER)
    records = document.get("records") if isinstance(document, dict) else None
    check(document.get("schema_version") == "public-safe-pair-quality-ledger-v2", "batch ledger schema differs")
    check(document.get("status") == "COMPLETE" and isinstance(records, list) and len(records) == 100, "batch ledger is not complete")
    by_id = {row["pair_id"]: row for row in batch_pairs}
    result: list[dict[str, Any]] = []
    for record in records:
        pair_id = record.get("pair_id")
        check(pair_id in by_id, f"ledger pair not frozen: {pair_id}")
        check(record.get("review_prompt_revision") == REVISION and record.get("evaluation_frame_digest") == EXPECTED_DIGEST, f"ledger protocol mismatch: {pair_id}")
        a = envelopes[f"{pair_id}|a"]
        b = envelopes[f"{pair_id}|b"]
        pa, pb = a["parsed_output"], b["parsed_output"]
        check(record.get("reviewer_a") == pa["verdict"] and record.get("reviewer_b") == pb["verdict"], f"ledger verdict mismatch: {pair_id}")
        expected = "include" if pa["verdict"] == pb["verdict"] == "include" else "exclude"
        check(record.get("decision") == expected, f"ledger adjudication mismatch: {pair_id}")
        check(record.get("reviewer_a_agent_id") == a["agent_identity"]["thread_id"] and record.get("reviewer_b_agent_id") == b["agent_identity"]["thread_id"], f"ledger identity mismatch: {pair_id}")
        result.append({**record, "review_pair_id": pair_id})
    check({row["pair_id"] for row in result} == set(by_id), "batch ledger pair set differs")
    return result


def build_expanded_source(old_bytes: bytes, old_rows: list[dict[str, Any]], batch_pairs: list[dict[str, Any]]) -> tuple[bytes, list[dict[str, Any]]]:
    appended: list[dict[str, Any]] = []
    for index, row in enumerate(batch_pairs, start=len(old_rows)):
        appended.append({
            "harmful": row["harmful"],
            "harmless": row["harmless"],
            "harmful_source_index": row["harmful_source_index"],
            "harmless_source_index": row["harmless_source_index"],
            "pair_id": row["pair_id"],
            "review_pair_id": row["pair_id"],
            "source_dataset": row["source_dataset"],
            "source_file": row["source_file"],
            "source_index": index,
            "source_revision": row["source_revision"],
            "upstream_pair_id": row["upstream_pair_id"],
        })
    old_prefix = old_bytes.rstrip()
    check(old_prefix.endswith(b"]"), "old source is not a JSON array")
    rows_bytes = b",".join(canonical(row).encode("utf-8") for row in appended)
    merged = old_prefix[:-1] + b"," + rows_bytes + b"]\n"
    parsed = json.loads(merged.decode("utf-8"))
    check(parsed[: len(old_rows)] == old_rows and parsed[len(old_rows) :] == appended, "append-only source verification failed")
    return merged, appended


def main() -> int:
    old_bytes = OLD_SOURCE.read_bytes()
    check(sha_bytes(OLD_SOURCE) == EXPECTED_SOURCE_SHA, "old source was modified")
    check(sha_bytes(OLD_LEDGER) == EXPECTED_OLD_LEDGER_SHA, "old ledger was modified")
    old_rows = read(OLD_SOURCE)
    old_ledger = read(OLD_LEDGER)
    check(isinstance(old_rows, list) and len(old_rows) == 416, "old source count differs")
    check(isinstance(old_ledger, dict) and len(old_ledger.get("records", [])) == 409, "old ledger count differs")
    candidate = load_candidate_pairs()
    freeze = read(FREEZE)
    batch_doc = read(BATCH_PAIRS)
    batch_pairs = batch_doc.get("pairs") if isinstance(batch_doc, dict) else None
    check(isinstance(batch_pairs, list), "batch pairs schema differs")
    validate_freeze(batch_pairs, candidate)
    envelopes, raw_stats = validate_raw(batch_pairs)
    new_records = validate_batch_ledger(batch_pairs, envelopes)

    merged_source_bytes, appended = build_expanded_source(old_bytes, old_rows, batch_pairs)
    EXPANDED_SOURCE.write_bytes(merged_source_bytes)
    merged_records = old_ledger["records"] + new_records
    merged_ledger = {
        "schema_version": "public-safe-pair-quality-ledger-v2",
        "status": "COMPLETE",
        "design_revision": DESIGN_REVISION,
        "records": merged_records,
        "old_ledger_sha256": EXPECTED_OLD_LEDGER_SHA,
        "batch1_ledger_sha256": sha_bytes(BATCH_LEDGER),
    }
    write(EXPANDED_LEDGER, merged_ledger)

    config = read(OLD_CONFIG)
    config["design_revision"] = "v2.1.2-public-pairs-expanded"
    config["data"]["safe_pairs_path"] = "data/safe_pairs_public_semantic_v2_expanded.json"
    config["data"]["overlap_decisions_path"] = "data/safe_pairs_public_semantic_v2_expanded_ledger.json"
    config["data"]["safe_pairs_source_manifest_path"] = "data/safe_pairs_public_semantic_v2_expanded.manifest.json"
    write(EXPANDED_CONFIG, config)

    manifest = {
        "schema_version": "paper1-public-safe-pair-expanded-source-manifest-v1",
        "design_revision": DESIGN_REVISION,
        "formal_experiments_not_run": True,
        "old_source": {"path": str(OLD_SOURCE), "count": len(old_rows), "sha256": EXPECTED_SOURCE_SHA},
        "appended_source": {"count": len(appended), "pair_ids": [row["pair_id"] for row in appended], "source_revision": "13682bf03c9e7805b81df2eab7e23fb2512e560b", "dataset": "fevziegeyurtsevenler/turkish-over-refusal-set", "data_sha256": EXPECTED_CANDIDATE_SHA, "license": "Apache-2.0"},
        "batch_freeze_sha256": sha_bytes(FREEZE),
        "batch_pairs_sha256": sha_bytes(BATCH_PAIRS),
        "batch_ledger_sha256": sha_bytes(BATCH_LEDGER),
        "source_path": str(EXPANDED_SOURCE),
        "source_count": len(old_rows) + len(appended),
        "source_sha256": sha_bytes(EXPANDED_SOURCE),
        "ledger_path": str(EXPANDED_LEDGER),
        "ledger_count": len(merged_records),
        "ledger_sha256": sha_bytes(EXPANDED_LEDGER),
        "config_path": str(EXPANDED_CONFIG),
    }
    write(MANIFEST, manifest)

    import sys
    sys.path.insert(0, str(ROOT))
    from paper1_broadening.config import load_config
    from paper1_broadening.frames import build_frames

    loaded = load_config(EXPANDED_CONFIG)
    frames = build_frames(loaded)
    split = frames["safe_pair_split"]
    check(split["source_count"] == 516, f"expanded source count differs: {split['source_count']}")
    check(split["preliminary_eligible_count"] == 509, f"expanded preliminary count differs: {split['preliminary_eligible_count']}")
    check(split["executable_eligible_count"] == 300, f"expanded executable count differs: {split['executable_eligible_count']}")
    check(split["actual_k"] == 40 and split["gate"] == "READY_FOR_CONSTRUCTION", "expanded safe-pair gate did not pass")
    check(len(split["construction_folds"]) == 5 and all(len(fold) == 40 for fold in split["construction_folds"]), "fold sizes differ")
    check(len(split["development"]) == 100 and not split["unused"], "development or unused allocation differs")
    check(split["role_isolation"]["construction_and_development_disjoint"] is True, "construction/development overlap")
    check(not split["mixed_evaluation_frame_digest"], "mixed evaluation digest")

    audit = {
        "schema_version": "paper1-public-safe-pair-batch1-raw-audit-v1",
        "batch_ledger_sha256": sha_bytes(BATCH_LEDGER),
        "batch_summary_sha256": sha_bytes(BATCH_SUMMARY),
        "evaluation_frame_digest": EXPECTED_DIGEST,
        "prompt_revision": REVISION,
        "selected_pair_count": len(batch_pairs),
        "raw": raw_stats,
        "unanimous_include": sum(row["decision"] == "include" for row in new_records),
        "exclude": sum(row["decision"] == "exclude" for row in new_records),
        "invalid_requests": 0,
        "formal_experiments_not_run": True,
    }
    write(AUDIT, audit)
    write(SUMMARY, {
        "schema_version": "paper1-public-safe-pair-expanded-summary-v1",
        "source_count": split["source_count"],
        "preliminary_eligible_count": split["preliminary_eligible_count"],
        "executable_eligible_count": split["executable_eligible_count"],
        "actual_k": split["actual_k"],
        "gate": split["gate"],
        "construction_fold_sizes": [len(fold) for fold in split["construction_folds"]],
        "development_count": len(split["development"]),
        "unused_count": len(split["unused"]),
        "evaluation_frame_digest": split["evaluation_frame_digest"],
        "frame_digest": frames["frame_digest"],
        "ledger_count": len(merged_records),
        "ledger_sha256": sha_bytes(EXPANDED_LEDGER),
        "source_sha256": sha_bytes(EXPANDED_SOURCE),
        "formal_experiments_not_run": True,
    })
    print(json.dumps({"source": str(EXPANDED_SOURCE), "ledger": str(EXPANDED_LEDGER), "config": str(EXPANDED_CONFIG), "source_count": split["source_count"], "preliminary": split["preliminary_eligible_count"], "executable": split["executable_eligible_count"], "actual_k": split["actual_k"], "gate": split["gate"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
