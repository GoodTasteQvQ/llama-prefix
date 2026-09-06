"""Deterministic prompt frames, overlap queues, and role isolation."""

from __future__ import annotations

import json
import random
import re
import unicodedata
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import BroadeningError, canonical_sha256, read_json
from .config import resolve_path


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        raise BroadeningError("prompt text must be a string")
    return " ".join(unicodedata.normalize("NFKC", text).lower().split())


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize_text(text)))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def load_jbb(path: Path, source_revision: str) -> list[dict[str, Any]]:
    rows = read_json(path)
    if not isinstance(rows, list) or len(rows) != 100:
        raise BroadeningError("JBB100 must be a JSON list of exactly 100 rows")
    frames: list[dict[str, Any]] = []
    seen_indices: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise BroadeningError("JBB row is not an object")
        index = row.get("Index")
        category = row.get("Category")
        text = row.get("Goal")
        source = row.get("Source")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index in seen_indices:
            raise BroadeningError("JBB source indices must be unique integers")
        if not isinstance(category, str) or not category or not isinstance(text, str) or not text:
            raise BroadeningError("JBB category or Goal is invalid")
        seen_indices.add(index)
        frames.append(
            {
                "prompt_id": f"jbb:{source_revision}:{index}",
                "source_id": str(source or "UNKNOWN"),
                "source_revision": source_revision,
                "source_index": index,
                "category": category,
                "text": text,
                "role": "evaluation",
                "frame": "JBB100",
            }
        )
    if len({row["category"] for row in frames}) != 10:
        raise BroadeningError("JBB100 must retain 10 source categories")
    return sorted(frames, key=lambda row: row["source_index"])


def build_jbb40(jbb100: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for source in jbb100:
        row = dict(source)
        grouped.setdefault(row["category"], []).append(row)
    result: list[dict[str, Any]] = []
    for category, rows in grouped.items():
        selected = sorted(rows, key=lambda row: row["source_index"])[:4]
        if len(selected) != 4:
            raise BroadeningError(f"JBB category lacks four rows: {category}")
        for row in selected:
            row["frame"] = "JBB40"
            result.append(row)
    if len(result) != 40:
        raise BroadeningError("JBB40 must contain exactly four rows from each source category")
    return result


def load_benign(path: Path) -> list[dict[str, Any]]:
    document = read_json(path)
    rows = document.get("records") if isinstance(document, dict) else None
    if not isinstance(rows, list) or len(rows) != 30:
        raise BroadeningError("benign confirm frame must contain exactly 30 records")
    frames: list[dict[str, Any]] = []
    seen_prompt_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("prompt"), str):
            raise BroadeningError("benign frame has an invalid prompt")
        source_id = row.get("source_id")
        source_index = row.get("source_index")
        if not isinstance(source_id, str) or not source_id or isinstance(source_index, bool) or not isinstance(source_index, int):
            raise BroadeningError("benign frame requires source identity")
        prompt_id = f"benign:{source_id}"
        if prompt_id in seen_prompt_ids:
            raise BroadeningError("benign frame source identity is duplicated")
        seen_prompt_ids.add(prompt_id)
        frames.append(
            {
                "prompt_id": prompt_id,
                "source_id": source_id,
                "source_revision": "selected_benign_confirm_30",
                "source_index": source_index,
                "category": str(row.get("native_category", "UNKNOWN")),
                "text": row["prompt"],
                "role": "evaluation",
                "frame": "benign30",
            }
        )
    return frames


def _review_decisions(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    document = read_json(path)
    rows = document.get("records", document) if isinstance(document, dict) else document
    if not isinstance(rows, list):
        raise BroadeningError("overlap decisions must be a list or records object")
    decisions: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("pair_id"), str):
            raise BroadeningError("overlap decision requires pair_id")
        pair_id = row["pair_id"]
        if pair_id in decisions:
            raise BroadeningError(f"duplicate overlap decision: {pair_id}")
        decisions[pair_id] = row
    return decisions


def _e1_review_decisions(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    document = read_json(path)
    rows = document.get("records", document) if isinstance(document, dict) else document
    if not isinstance(rows, list):
        raise BroadeningError("E1 overlap decisions must be a list or records object")
    decisions: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("prompt_id"), str):
            raise BroadeningError("E1 overlap decision requires prompt_id")
        if row["prompt_id"] in decisions:
            raise BroadeningError(f"duplicate E1 overlap decision: {row['prompt_id']}")
        decisions[row["prompt_id"]] = row
    return decisions


def _semantic_status(decision: Mapping[str, Any] | None) -> str:
    if decision is None:
        return "PENDING_SEMANTIC_REVIEW"
    required = {"reviewer_a", "reviewer_b", "decision"}
    if not required.issubset(decision):
        return "PENDING_SEMANTIC_REVIEW"
    reviewers = {decision["reviewer_a"], decision["reviewer_b"]}
    if reviewers == {"include"} and decision["decision"] == "include":
        return "SEMANTIC_INCLUDE"
    if reviewers == {"exclude"} and decision["decision"] == "exclude":
        return "SEMANTIC_EXCLUDE"
    return "PENDING_SEMANTIC_REVIEW"


def build_safe_pair_split(
    safe_pairs: list[Mapping[str, Any]], *, decisions: Mapping[str, Mapping[str, Any]] | None = None,
    master_seed: int = 42, max_fold_size: int = 80, min_fold_size: int = 30,
    evaluation_frames: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a preliminary deterministic split without fabricating semantic review PASS."""
    decisions = decisions or {}
    evaluation_normalized: set[str] = set()
    for frame in evaluation_frames or ():
        text = frame.get("text") if isinstance(frame, Mapping) else None
        if isinstance(text, str):
            evaluation_normalized.add(normalize_text(text))
    records: list[dict[str, Any]] = []
    seen_harmful: set[str] = set()
    seen_harmless: set[str] = set()
    for index, source in enumerate(safe_pairs):
        harmful = source.get("harmful") if isinstance(source, Mapping) else None
        harmless = source.get("harmless") if isinstance(source, Mapping) else None
        if not isinstance(harmful, str) or not isinstance(harmless, str):
            raise BroadeningError(f"safe pair {index} has non-string text")
        pair_id = f"safe-pair:{index}"
        harmful_normalized = normalize_text(harmful)
        harmless_normalized = normalize_text(harmless)
        duplicate_reasons: list[str] = []
        if not harmful_normalized or not harmless_normalized:
            duplicate_reasons.append("empty_after_normalization")
        if harmful_normalized in seen_harmful:
            duplicate_reasons.append("duplicate_harmful")
        if harmless_normalized in seen_harmless:
            duplicate_reasons.append("duplicate_harmless")
        if harmful_normalized in evaluation_normalized:
            duplicate_reasons.append("exact_evaluation_overlap_harmful")
        if harmless_normalized in evaluation_normalized:
            duplicate_reasons.append("exact_evaluation_overlap_harmless")
        seen_harmful.add(harmful_normalized)
        seen_harmless.add(harmless_normalized)
        semantic = _semantic_status(decisions.get(pair_id))
        records.append(
            {
                "pair_id": pair_id,
                "source_index": index,
                "harmful": harmful,
                "harmless": harmless,
                "normalized_harmful": harmful_normalized,
                "normalized_harmless": harmless_normalized,
                "exact_duplicate_reasons": duplicate_reasons,
                "semantic_review_status": semantic,
                "preliminary_include": not duplicate_reasons,
                "executable_include": not duplicate_reasons and semantic == "SEMANTIC_INCLUDE",
            }
        )
    preliminary = [row for row in records if row["preliminary_include"]]
    pending_review = any(
        row["semantic_review_status"] not in {"SEMANTIC_INCLUDE", "SEMANTIC_EXCLUDE"}
        for row in preliminary
    )
    split_basis = (
        preliminary
        if pending_review
        else [row for row in preliminary if row["executable_include"]]
    )
    shuffled = list(split_basis)
    random.Random(master_seed).shuffle(shuffled)
    count = len(shuffled)
    k = min(max_fold_size, (count - 100) // 5) if count >= 100 else -1
    if k < min_fold_size:
        gate = "BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS"
        folds: list[list[dict[str, Any]]] = []
        development: list[dict[str, Any]] = []
        unused = shuffled
    else:
        folds = [shuffled[index * k : (index + 1) * k] for index in range(5)]
        development = shuffled[-100:]
        unused = shuffled[5 * k : -100]
        gate = "PENDING_SEMANTIC_REVIEW" if pending_review else "READY_FOR_CONSTRUCTION"
    return {
        "source_count": len(safe_pairs),
        "preliminary_eligible_count": count,
        "executable_eligible_count": sum(row["executable_include"] for row in records),
        "exact_evaluation_overlap_count": sum(
            any(reason.startswith("exact_evaluation_overlap") for reason in row["exact_duplicate_reasons"])
            for row in records
        ),
        "master_seed": master_seed,
        "actual_k": k if k >= 0 else None,
        "gate": gate,
        "records": records,
        "construction_folds": [[row["pair_id"] for row in fold] for fold in folds],
        "development": [row["pair_id"] for row in development],
        "screen_prompt_pair_ids": [row["pair_id"] for row in development[:20]],
        "unused": [row["pair_id"] for row in unused],
        "role_isolation": {
            "construction_and_development_disjoint": not set().union(
                *(set(fold) for fold in [[row["pair_id"] for row in fold] for fold in folds])
            ).intersection({row["pair_id"] for row in development}),
            "evaluation_role": "JBB_and_benign_only",
        },
    }


def build_overlap_queue(
    *, safe_split: Mapping[str, Any], evaluation_frames: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    evaluation = list(evaluation_frames)
    for pair in safe_split["records"]:
        if pair["exact_duplicate_reasons"]:
            continue
        for side in ("harmful", "harmless"):
            left = _token_set(pair[side])
            for frame in evaluation:
                right = _token_set(str(frame["text"]))
                containment = bool(left and right and (left <= right or right <= left))
                score = _jaccard(left, right)
                if containment or score >= 0.5:
                    queue.append(
                        {
                            "pair_id": pair["pair_id"],
                            "pair_side": side,
                            "evaluation_prompt_id": frame["prompt_id"],
                            "jaccard": score,
                            "containment_candidate": containment,
                            "review_status": pair["semantic_review_status"],
                        }
                    )
    return queue


def _load_e1(path: Path | None, metadata_path: Path | None) -> dict[str, Any]:
    if path is None or metadata_path is None or not path.is_file() or not metadata_path.is_file():
        return {"status": "NOT_RUN", "reason": "HARM_BENCH_ASSET_OR_METADATA_MISSING", "records": []}
    metadata = read_json(metadata_path)
    if not isinstance(metadata, dict) or metadata.get("benchmark") != "HarmBench_standard_text":
        return {"status": "NOT_RUN", "reason": "HARM_BENCH_METADATA_NOT_REGISTERED", "records": []}
    source = read_json(path)
    rows = source.get("records", source) if isinstance(source, dict) else source
    if not isinstance(rows, list):
        raise BroadeningError("HarmBench source must be a list")
    categories: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    seen_prompt_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise BroadeningError("HarmBench row is invalid")
        text, category = row.get("text"), row.get("category")
        source_id = row.get("source_id", index)
        source_index = row.get("source_index", index)
        if not isinstance(text, str) or not text or not isinstance(category, str) or not category:
            raise BroadeningError("HarmBench row lacks text/category")
        if isinstance(source_index, bool) or not isinstance(source_index, int):
            raise BroadeningError("HarmBench source_index must be an integer")
        prompt_id = f"harmbench:{metadata.get('revision', 'UNKNOWN')}:{source_id}"
        if prompt_id in seen_prompt_ids:
            raise BroadeningError("HarmBench source identity is duplicated")
        seen_prompt_ids.add(prompt_id)
        categories.setdefault(category, []).append(
            {
                "prompt_id": prompt_id,
                "source_id": str(source_id),
                "source_revision": metadata.get("revision", "UNKNOWN"),
                "source_index": source_index,
                "category": category,
                "text": text,
                "role": "evaluation",
                "frame": "E1-HarmBench40",
            }
        )
    candidates = [
        row
        for rows_for_category in categories.values()
        for row in sorted(rows_for_category, key=lambda item: item["source_index"])
    ]
    if len(categories) < 4:
        return {
            "status": "NOT_RUN", "reason": "HARM_BENCH_FEWER_THAN_FOUR_NATIVE_CATEGORIES",
            "records": [], "candidate_records": candidates, "metadata": metadata,
        }
    return {
        "status": "READY_FOR_OVERLAP_GATE", "reason": None, "records": [],
        "candidate_records": candidates, "metadata": metadata,
    }


def close_e1_overlap_gate(
    candidates: Iterable[Mapping[str, Any]], *, forbidden_frames: Iterable[Mapping[str, Any]],
    decisions: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Filter external candidates before deterministic native-category rotation."""
    decisions = decisions or {}
    forbidden = [row for row in forbidden_frames if isinstance(row.get("text"), str)]
    accepted: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    queue: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for raw in candidates:
        row = dict(raw)
        prompt_id = row.get("prompt_id")
        text = row.get("text")
        category = row.get("category")
        if not all(isinstance(value, str) and value for value in (prompt_id, text, category)):
            raise BroadeningError("E1 candidate lacks prompt_id/text/native category")
        normalized = normalize_text(text)
        exact = [frame["prompt_id"] for frame in forbidden if normalize_text(frame["text"]) == normalized]
        if exact:
            excluded.append({"prompt_id": prompt_id, "reason": "exact_overlap", "matches": exact})
            continue
        tokens = _token_set(text)
        candidates_for_review: list[dict[str, Any]] = []
        for frame in forbidden:
            other = _token_set(frame["text"])
            score = _jaccard(tokens, other)
            containment = bool(tokens and other and (tokens <= other or other <= tokens))
            if containment or score >= 0.5:
                candidates_for_review.append({
                    "prompt_id": frame["prompt_id"], "jaccard": score, "containment_candidate": containment,
                })
        decision = decisions.get(prompt_id)
        status = _semantic_status(decision)
        if status == "SEMANTIC_EXCLUDE":
            excluded.append({"prompt_id": prompt_id, "reason": "semantic_exclude", "matches": candidates_for_review})
            continue
        if candidates_for_review and status != "SEMANTIC_INCLUDE":
            queue.append({"prompt_id": prompt_id, "candidates": candidates_for_review, "review_status": status})
            continue
        accepted.setdefault(category, []).append(row)
    selected: list[dict[str, Any]] = []
    positions = {category: 0 for category in accepted}
    while len(selected) < 40:
        progressed = False
        for category, rows in accepted.items():
            if positions[category] < len(rows):
                selected.append(rows[positions[category]])
                positions[category] += 1
                progressed = True
                if len(selected) == 40:
                    break
        if not progressed:
            break
    if queue:
        status, reason = "NOT_RUN", "E1_SEMANTIC_OVERLAP_REVIEW_PENDING"
    elif len(accepted) < 4:
        status, reason = "NOT_RUN", "E1_FEWER_THAN_FOUR_NATIVE_CATEGORIES_AFTER_OVERLAP"
    elif len(selected) != 40:
        status, reason = "NOT_RUN", "E1_FEWER_THAN_40_PROMPTS_AFTER_OVERLAP"
    else:
        status, reason = "READY_FOR_RUN", None
    return {
        "status": status,
        "reason": reason,
        "records": selected if status == "READY_FOR_RUN" else [],
        "review_queue": queue,
        "excluded": excluded,
        "native_category_count": len(accepted),
    }


def build_frames(config: Mapping[str, Any]) -> dict[str, Any]:
    data = config["data"]
    jbb = load_jbb(resolve_path(config, data["jbb_path"]), data["jbb_source_revision"])
    jbb40 = build_jbb40(jbb)
    benign = load_benign(resolve_path(config, data["benign_path"]))
    safe_pairs = read_json(resolve_path(config, data["safe_pairs_path"]))
    if not isinstance(safe_pairs, list):
        raise BroadeningError("safe pairs source must be a list")
    decisions = _review_decisions(resolve_path(config, data.get("overlap_decisions_path")))
    protocol = config["protocol"]
    safe_split = build_safe_pair_split(
        safe_pairs,
        decisions=decisions,
        master_seed=protocol["master_seed"],
        max_fold_size=protocol["max_fold_size"],
        min_fold_size=protocol["min_fold_size"],
        evaluation_frames=[*jbb, *benign],
    )
    overlap_queue = build_overlap_queue(safe_split=safe_split, evaluation_frames=[*jbb, *benign])
    e1 = _load_e1(
        resolve_path(config, data.get("e1_harmbench_path")),
        resolve_path(config, data.get("e1_metadata_path")),
    )
    if e1.get("status") == "READY_FOR_OVERLAP_GATE":
        e1_decisions = _e1_review_decisions(resolve_path(config, data.get("e1_overlap_decisions_path")))
        safe_by_id = {row["pair_id"]: row for row in safe_split["records"]}
        role_pair_ids = set(safe_split["development"])
        role_pair_ids.update(pair_id for fold in safe_split["construction_folds"] for pair_id in fold)
        safe_role_frames = [
            {"prompt_id": f"{pair_id}:{side}", "text": safe_by_id[pair_id][side]}
            for pair_id in sorted(role_pair_ids)
            for side in ("harmful", "harmless")
            if pair_id in safe_by_id
        ]
        e1_gate = close_e1_overlap_gate(
            e1["candidate_records"],
            forbidden_frames=[*jbb, *safe_role_frames],
            decisions=e1_decisions,
        )
        e1 = {**e1, **e1_gate}
    document = {
        "schema_version": "paper1-broadening-frames-v1",
        "jbb100": jbb,
        "jbb40": jbb40,
        "benign30": benign,
        "safe_pair_split": safe_split,
        "overlap_review_queue": overlap_queue,
        "e1": e1,
    }
    document["frame_digest"] = canonical_sha256(document)
    return document
