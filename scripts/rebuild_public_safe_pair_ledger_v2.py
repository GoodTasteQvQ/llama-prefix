#!/usr/bin/env python3
"""Independently rebuild the v2 decision ledger from request-level raw evidence."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-v2-20260908T111917Z"
REVISION = "public-semantic-pair-quality-v2"

sys_path = str(ROOT)
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
from paper1_broadening.common import canonical_sha256
from paper1_broadening.config import load_config, resolve_path
from paper1_broadening.frames import build_jbb40, build_safe_pair_split, load_benign, load_jbb


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    config = load_config(ROOT / "configs/paper1_broadening/mbd_nm_v211_public.json")
    source = json.loads((ROOT / "data/safe_pairs_public_semantic_v1.json").read_text(encoding="utf-8"))
    jbb = load_jbb(resolve_path(config, config["data"]["jbb_path"]), config["data"]["jbb_source_revision"])
    jbb40 = build_jbb40(jbb)
    benign = load_benign(resolve_path(config, config["data"]["benign_path"]))
    evaluation = [*jbb, *benign]
    evaluation_digest = canonical_sha256({"jbb100": jbb, "jbb40": jbb40, "benign30": benign})
    preliminary = build_safe_pair_split(
        source, decisions={}, master_seed=config["protocol"]["master_seed"],
        max_fold_size=config["protocol"]["max_fold_size"], min_fold_size=config["protocol"]["min_fold_size"],
        evaluation_frames=evaluation, evaluation_frame_digest=evaluation_digest,
    )
    rows = [
        {"pair_id": row["pair_id"], "harmful": row["harmful"], "harmless": row["harmless"]}
        for row in preliminary["records"] if row["preliminary_include"]
    ]
    envelopes: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    for side in ("a", "b"):
        for path in (RUN / "raw" / side).glob("*.json"):
            try:
                value = read(path)
            except Exception:
                continue
            if value.get("schema_version") == "public-safe-pair-review-request-v2":
                envelopes[(value.get("pair_id"), value.get("side"))] = (path, value)
    retry = RUN / "raw/a/safe-pair_341.a.retry.json"
    if retry.is_file():
        value = read(retry)
        envelopes[(value.get("pair_id"), value.get("side"))] = (retry, value)
    decisions = []
    used_ids: set[str] = set()
    invalid_requests = []
    for row in rows:
        pair_id = row["pair_id"]
        sides = {}
        for side in ("a", "b"):
            path, value = envelopes.get((pair_id, side), (None, None))
            parsed = value.get("parsed_output") if isinstance(value, dict) else None
            valid = (
                isinstance(value, dict) and value.get("status") == "ok" and isinstance(parsed, dict)
                and parsed.get("pair_id") == pair_id and parsed.get("prompt_revision") == REVISION
                and parsed.get("verdict") in {"include", "exclude", "uncertain"}
                and all(isinstance(parsed.get(key), bool) for key in ("harmful_is_materially_unsafe", "harmless_is_materially_benign", "semantic_pair_is_comparable", "evaluation_overlap_checked"))
                and isinstance(parsed.get("rationale"), str) and bool(parsed.get("rationale", "").strip())
                and isinstance(value.get("agent_identity", {}).get("thread_id"), str)
                and value.get("agent_identity", {}).get("thread_id") not in used_ids
            )
            if valid:
                used_ids.add(value["agent_identity"]["thread_id"])
            else:
                invalid_requests.append({"pair_id": pair_id, "side": side, "path": str(path) if path else None})
            sides[side] = (path, value, parsed if valid else None)
        pa, va, oa = sides["a"]
        pb, vb, ob = sides["b"]
        verdict_a = oa.get("verdict") if oa else None
        verdict_b = ob.get("verdict") if ob else None
        decision = "pending" if oa is None or ob is None else ("include" if verdict_a == verdict_b == "include" else "exclude")
        decisions.append({
            "pair_id": pair_id,
            "review_mode": "dual_codex_subagents_v1",
            "review_prompt_revision": REVISION,
            "adjudication_rule": "unanimous_include_else_exclude",
            "evaluation_frame_digest": evaluation_digest,
            "reviewer_a": verdict_a,
            "reviewer_b": verdict_b,
            "decision": decision,
            "reviewer_a_agent_id": va.get("agent_identity", {}).get("thread_id") if va else None,
            "reviewer_b_agent_id": vb.get("agent_identity", {}).get("thread_id") if vb else None,
            "reviewer_a_model": va.get("agent_identity", {}).get("model") if va else None,
            "reviewer_b_model": vb.get("agent_identity", {}).get("model") if vb else None,
            "reviewer_a_raw_output": va.get("raw_output", "") if va else "",
            "reviewer_b_raw_output": vb.get("raw_output", "") if vb else "",
            "reviewer_a_raw_output_sha256": va.get("raw_output_sha256") if va else None,
            "reviewer_b_raw_output_sha256": vb.get("raw_output_sha256") if vb else None,
            "reviewer_a_rationale": oa.get("rationale", "") if oa else "",
            "reviewer_b_rationale": ob.get("rationale", "") if ob else "",
            "reviewer_a_request_id": va.get("request_id") if va else None,
            "reviewer_b_request_id": vb.get("request_id") if vb else None,
            "reviewer_a_raw_path": str(pa) if pa else None,
            "reviewer_b_raw_path": str(pb) if pb else None,
            "reviewed_at": max((x.get("ended_at_utc", "") for x in (va, vb) if isinstance(x, dict)), default=""),
        })
    ledger = {"schema_version": "public-safe-pair-quality-ledger-v2", "status": "COMPLETE" if not invalid_requests else "COMPLETE_WITH_PENDING", "records": decisions}
    target = RUN / "public_pair_quality_decisions.v2.rebuilt.json"
    target.write_text(json.dumps(ledger, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": "public-safe-pair-quality-ledger-summary-v2",
        "source_count": len(source),
        "preliminary_count": len(rows),
        "request_envelopes": len(envelopes),
        "unique_agent_ids": len(used_ids),
        "invalid_requests": invalid_requests,
        "verdict_a": dict(Counter(r["reviewer_a"] for r in decisions)),
        "verdict_b": dict(Counter(r["reviewer_b"] for r in decisions)),
        "decisions": dict(Counter(r["decision"] for r in decisions)),
        "ledger": str(target),
        "ledger_sha256": sha(target.read_text(encoding="utf-8")),
    }
    (RUN / "rebuilt_summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
