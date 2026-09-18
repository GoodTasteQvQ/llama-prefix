"""Deterministic prompt frames, overlap queues, and role isolation."""

from __future__ import annotations

import json
import hashlib
import random
import re
import unicodedata
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import BroadeningError, canonical_sha256, read_json
from .config import resolve_path


DEFAULT_E1_REVIEW_PROMPT_REVISION = "harmbench-e1-dual-codex-overlap-v1"


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


def _validate_expanded_source_identity(
    safe_pairs: list[Mapping[str, Any]], decisions: Mapping[str, Mapping[str, Any]]
) -> None:
    """Bind expanded source rows to their own upstream review records."""
    review_ids: set[str] = set()
    for index, source in enumerate(safe_pairs):
        review_pair_id = source.get("review_pair_id")
        if review_pair_id is None:
            continue
        if source.get("source_index") != index:
            raise BroadeningError("expanded safe-pair source indices are not contiguous")
        if not isinstance(review_pair_id, str) or not review_pair_id:
            raise BroadeningError("expanded safe-pair review_pair_id is invalid")
        if review_pair_id in review_ids:
            raise BroadeningError(f"duplicate expanded review_pair_id: {review_pair_id}")
        review_ids.add(review_pair_id)
        if source.get("pair_id") != review_pair_id:
            raise BroadeningError(f"expanded pair_id/review_pair_id mismatch: {review_pair_id}")
        internal_alias = f"safe-pair:{index}"
        if internal_alias in decisions:
            raise BroadeningError(f"expanded review decision uses forbidden internal alias: {review_pair_id}")
        decision = decisions.get(review_pair_id)
        if not isinstance(decision, Mapping):
            raise BroadeningError(f"expanded safe pair lacks review decision: {review_pair_id}")
        if decision.get("pair_id") not in {None, review_pair_id}:
            raise BroadeningError(f"expanded review decision pair identity differs: {review_pair_id}")
        if decision.get("review_pair_id") not in {None, review_pair_id}:
            raise BroadeningError(f"expanded review alias differs: {review_pair_id}")
        for source_key, decision_key in (
            ("source_revision", "source_revision"),
            ("source_dataset", "source_dataset"),
            ("harmful_source_index", "source_index_harmful"),
            ("harmless_source_index", "source_index_harmless"),
        ):
            source_value = source.get(source_key)
            decision_value = decision.get(decision_key)
            if source_value is not None and decision_value is not None and source_value != decision_value:
                raise BroadeningError(f"expanded source/review provenance differs: {review_pair_id}:{source_key}")
        for side in ("a", "b"):
            raw_path = decision.get(f"reviewer_{side}_raw_path")
            if not isinstance(raw_path, str) or not raw_path:
                raise BroadeningError(f"expanded safe pair raw provenance path is missing: {review_pair_id}:{side}")
            try:
                envelope = read_json(Path(raw_path))
            except BroadeningError as exc:
                raise BroadeningError(f"expanded safe pair raw provenance is unreadable: {review_pair_id}:{side}") from exc
            pair_input = envelope.get("pair_input") if isinstance(envelope, Mapping) else None
            if not isinstance(pair_input, Mapping) or pair_input.get("pair_id") != review_pair_id:
                raise BroadeningError(f"expanded raw pair identity differs: {review_pair_id}:{side}")
            if pair_input.get("harmful") != source.get("harmful") or pair_input.get("harmless") != source.get("harmless"):
                raise BroadeningError(f"expanded raw text differs from source: {review_pair_id}:{side}")
            raw_input_hash = hashlib.sha256(
                json.dumps(dict(pair_input), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if envelope.get("pair_input_json_sha256") != raw_input_hash:
                raise BroadeningError(f"expanded raw input hash differs: {review_pair_id}:{side}")


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


def _e1_semantic_status(
    decision: Mapping[str, Any] | None,
    *,
    prompt_id: str,
    reference_digest: str,
    review_prompt_revision: str = DEFAULT_E1_REVIEW_PROMPT_REVISION,
) -> str:
    """Validate the independent E1 overlap decision schema fail-closed.

    E1 decisions are intentionally not accepted by the safe-pair quality
    validator: they answer a different question and bind to a different
    reference set.
    """
    if decision is None:
        return "PENDING_SEMANTIC_REVIEW"
    required = {
        "schema_version", "prompt_id", "review_mode", "review_prompt_revision",
        "reference_digest", "reviewer_a", "reviewer_b", "decision",
        "reviewer_a_agent_id", "reviewer_b_agent_id",
        "reviewer_a_raw_output", "reviewer_b_raw_output",
    }
    if not required.issubset(decision):
        return "PENDING_SEMANTIC_REVIEW"
    if decision.get("schema_version") != "paper1-e1-overlap-decision-v1":
        return "PENDING_SEMANTIC_REVIEW"
    if decision.get("prompt_id") != prompt_id or decision.get("reference_digest") != reference_digest:
        return "PENDING_SEMANTIC_REVIEW"
    if decision.get("review_mode") != "e1_dual_codex_v1":
        return "PENDING_SEMANTIC_REVIEW"
    if decision.get("review_prompt_revision") != review_prompt_revision:
        return "PENDING_SEMANTIC_REVIEW"
    if decision.get("reviewer_a_agent_id") == decision.get("reviewer_b_agent_id"):
        return "PENDING_SEMANTIC_REVIEW"
    verdicts = {decision.get("reviewer_a"), decision.get("reviewer_b")}
    if not verdicts.issubset({"include", "exclude", "uncertain"}):
        return "PENDING_SEMANTIC_REVIEW"
    for side in ("a", "b"):
        try:
            raw = json.loads(str(decision[f"reviewer_{side}_raw_output"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return "PENDING_SEMANTIC_REVIEW"
        if not isinstance(raw, dict) or any(
            raw.get(field) != expected
            for field, expected in (
                ("prompt_id", prompt_id),
                ("prompt_revision", review_prompt_revision),
                ("reference_digest", reference_digest),
                ("verdict", decision.get(f"reviewer_{side}")),
            )
        ):
            return "PENDING_SEMANTIC_REVIEW"
    if verdicts == {"include"} and decision.get("decision") == "include":
        return "SEMANTIC_INCLUDE"
    if decision.get("decision") == "exclude" and verdicts != {"include"}:
        return "SEMANTIC_EXCLUDE"
    return "PENDING_SEMANTIC_REVIEW"


def _semantic_status(
    decision: Mapping[str, Any] | None, *, pair_id: str | None = None,
    review_pair_id: str | None = None,
    expected_evaluation_frame_digest: str | None = None,
) -> str:
    if decision is None:
        return "PENDING_SEMANTIC_REVIEW"
    required = {"reviewer_a", "reviewer_b", "decision"}
    if not required.issubset(decision):
        return "PENDING_SEMANTIC_REVIEW"
    reviewers = {decision["reviewer_a"], decision["reviewer_b"]}
    if decision.get("review_mode") == "dual_codex_subagents_v1":
        provenance = {
            "review_prompt_revision",
            "adjudication_rule",
            "evaluation_frame_digest",
            "reviewer_a_agent_id",
            "reviewer_b_agent_id",
            "reviewer_a_model",
            "reviewer_b_model",
            "reviewer_a_raw_output",
            "reviewer_b_raw_output",
            "reviewer_a_rationale",
            "reviewer_b_rationale",
            "reviewed_at",
        }
        if not provenance.issubset(decision):
            return "PENDING_SEMANTIC_REVIEW"
        if decision.get("review_prompt_revision") not in {
            "safe-pair-semantic-overlap-v1",
            "public-semantic-pair-quality-v1",
            "public-semantic-pair-quality-v2",
        }:
            return "PENDING_SEMANTIC_REVIEW"
        if decision.get("adjudication_rule") != "unanimous_include_else_exclude":
            return "PENDING_SEMANTIC_REVIEW"
        if expected_evaluation_frame_digest is not None and decision.get("evaluation_frame_digest") != expected_evaluation_frame_digest:
            return "PENDING_SEMANTIC_REVIEW"
        if any(
            not isinstance(decision.get(field), str) or not decision[field]
            for field in provenance - {"review_prompt_revision", "adjudication_rule"}
        ):
            return "PENDING_SEMANTIC_REVIEW"
        for side in ("a", "b"):
            try:
                raw = json.loads(decision[f"reviewer_{side}_raw_output"])
            except (TypeError, ValueError, json.JSONDecodeError):
                return "PENDING_SEMANTIC_REVIEW"
            if not isinstance(raw, dict) or any(
                raw.get(field) != expected
                for field, expected in (
                    ("pair_id", review_pair_id or pair_id),
                    ("prompt_revision", decision.get("review_prompt_revision")),
                    ("verdict", decision.get(f"reviewer_{side}")),
                )
            ):
                return "PENDING_SEMANTIC_REVIEW"
        if decision["reviewer_a_agent_id"] == decision["reviewer_b_agent_id"]:
            return "PENDING_SEMANTIC_REVIEW"
        if not reviewers.issubset({"include", "exclude", "uncertain"}):
            return "PENDING_SEMANTIC_REVIEW"
        if reviewers == {"include"} and decision["decision"] == "include":
            return "SEMANTIC_INCLUDE"
        if decision["decision"] == "exclude" and reviewers != {"include"}:
            return "SEMANTIC_EXCLUDE"
        return "PENDING_SEMANTIC_REVIEW"
    if reviewers == {"include"} and decision["decision"] == "include":
        return "SEMANTIC_INCLUDE"
    if reviewers == {"exclude"} and decision["decision"] == "exclude":
        return "SEMANTIC_EXCLUDE"
    return "PENDING_SEMANTIC_REVIEW"


def build_safe_pair_split(
    safe_pairs: list[Mapping[str, Any]], *, decisions: Mapping[str, Mapping[str, Any]] | None = None,
    master_seed: int = 42, max_fold_size: int = 80, min_fold_size: int = 30,
    evaluation_frames: Iterable[Mapping[str, Any]] | None = None,
    evaluation_frame_digest: str | None = None,
) -> dict[str, Any]:
    """Build a preliminary deterministic split without fabricating semantic review PASS."""
    decisions = decisions or {}
    _validate_expanded_source_identity(safe_pairs, decisions)
    evaluation_frames = list(evaluation_frames or ())
    evaluation_normalized: set[str] = set()
    for frame in evaluation_frames:
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
        review_pair_id = source.get("review_pair_id") if isinstance(source.get("review_pair_id"), str) else None
        # Expanded rows are bound only through their immutable upstream review ID.
        # Falling back to the internal index would allow a raw decision to be
        # silently reused for a different source row.
        decision = decisions.get(review_pair_id) if review_pair_id else decisions.get(pair_id)
        semantic = _semantic_status(
            decision,
            pair_id=pair_id,
            review_pair_id=review_pair_id,
            expected_evaluation_frame_digest=(
                evaluation_frame_digest or (canonical_sha256(evaluation_frames) if evaluation_frames and decisions else None)
            ),
        )
        records.append(
            {
                "pair_id": pair_id,
                **({"review_pair_id": review_pair_id} if review_pair_id else {}),
                "source_index": index,
                **({"source_revision": source.get("source_revision")} if isinstance(source.get("source_revision"), str) else {}),
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
    evaluation_frame_digest = evaluation_frame_digest or (canonical_sha256(evaluation_frames) if evaluation_frames else None)
    decision_digests = {
        decision.get("evaluation_frame_digest")
        for decision in decisions.values()
        if isinstance(decision, Mapping) and decision.get("evaluation_frame_digest")
    }
    mixed_digest = len(decision_digests) > 1
    if mixed_digest:
        pending_review = True
        gate = "PENDING_SEMANTIC_REVIEW"
    return {
        "source_count": len(safe_pairs),
        "preliminary_eligible_count": len(preliminary),
        "executable_eligible_count": sum(row["executable_include"] for row in records),
        "exact_evaluation_overlap_count": sum(
            any(reason.startswith("exact_evaluation_overlap") for reason in row["exact_duplicate_reasons"])
            for row in records
        ),
        "master_seed": master_seed,
        "evaluation_frame_digest": evaluation_frame_digest,
        "decision_evaluation_frame_digests": sorted(decision_digests),
        "mixed_evaluation_frame_digest": mixed_digest,
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
    if path.suffix.lower() == ".csv":
        raise BroadeningError(
            "HarmBench CSV requires the deterministic CSV-to-JSON adapter; configure the materialized JSON path"
        )
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
    reference_digest: str | None = None,
    review_prompt_revision: str = DEFAULT_E1_REVIEW_PROMPT_REVISION,
) -> dict[str, Any]:
    """Filter external candidates before deterministic native-category rotation."""
    decisions = decisions or {}
    forbidden = [row for row in forbidden_frames if isinstance(row.get("text"), str)]
    reference_digest = reference_digest or canonical_sha256([
        {key: row.get(key) for key in ("prompt_id", "source_id", "source_revision", "source_index", "text")}
        for row in forbidden
    ])
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
        exact = [frame.get("prompt_id", frame.get("reference_id")) for frame in forbidden if normalize_text(frame["text"]) == normalized]
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
                    "prompt_id": frame.get("prompt_id", frame.get("reference_id")),
                    "jaccard": score, "containment_candidate": containment,
                })
        decision = decisions.get(prompt_id)
        status = _e1_semantic_status(
            decision,
            prompt_id=prompt_id,
            reference_digest=reference_digest,
            review_prompt_revision=review_prompt_revision,
        )
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
        "reference_digest": reference_digest,
        "review_prompt_revision": review_prompt_revision,
    }


def _e1_reference_snapshot(
    *,
    jbb100: Iterable[Mapping[str, Any]],
    jbb40: Iterable[Mapping[str, Any]],
    benign30: Iterable[Mapping[str, Any]],
    safe_pairs: list[Mapping[str, Any]],
    safe_split: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build the same reference records used by the independent E1 C2 input freeze."""
    references: list[dict[str, Any]] = []
    jbb40_ids = {row["prompt_id"] for row in jbb40}
    for row in jbb100:
        references.append({
            "reference_id": row["prompt_id"],
            "reference_kind": "JBB",
            "frame_memberships": ["JBB100"] + (["JBB40"] if row["prompt_id"] in jbb40_ids else []),
            "source_id": row["source_id"],
            "source_revision": row["source_revision"],
            "source_index": row["source_index"],
            "text": row["text"],
        })
    # benign30 is a Core evaluation frame, not an E1 forbidden reference.
    # Keep the parameter for the shared frame-building call signature, but do
    # not let it alter the independent C2 reference digest.
    del benign30
    safe_by_id = {row["pair_id"]: row for row in safe_split.get("records", [])}
    source_by_index = {index: row for index, row in enumerate(safe_pairs)}
    selected_ids = [pair_id for fold in safe_split.get("construction_folds", []) for pair_id in fold]
    selected_ids.extend(safe_split.get("development", []))
    for pair_id in selected_ids:
        frame_row = safe_by_id[pair_id]
        source_row = source_by_index[frame_row["source_index"]]
        for side in ("harmful", "harmless"):
            references.append({
                "reference_id": f"{pair_id}:{side}",
                "reference_kind": "safe_pair_role",
                "frame_memberships": ["construction_or_development"],
                "pair_id": pair_id,
                "side": side,
                "source_index": frame_row["source_index"],
                "source_revision": source_row.get("source_revision", "UNKNOWN"),
                "source_dataset": source_row.get("source_dataset", "UNKNOWN"),
                "source_pair_id": source_row.get("pair_id", "UNKNOWN"),
                "review_pair_id": source_row.get("review_pair_id"),
                "upstream_pair_id": source_row.get("upstream_pair_id"),
                "text": frame_row[side],
            })
    return references


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
    evaluation_frame_digest = canonical_sha256({"jbb100": jbb, "jbb40": jbb40, "benign30": benign})
    safe_split = build_safe_pair_split(
        safe_pairs,
        decisions=decisions,
        master_seed=protocol["master_seed"],
        max_fold_size=protocol["max_fold_size"],
        min_fold_size=protocol["min_fold_size"],
        evaluation_frames=[*jbb, *benign],
        evaluation_frame_digest=evaluation_frame_digest,
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
            {
                "prompt_id": f"{pair_id}:{side}",
                "text": safe_by_id[pair_id][side],
                "source_id": safe_pairs[safe_by_id[pair_id]["source_index"]].get("pair_id", pair_id),
                "source_revision": safe_pairs[safe_by_id[pair_id]["source_index"]].get("source_revision", "UNKNOWN"),
                "source_index": safe_by_id[pair_id]["source_index"],
            }
            for pair_id in sorted(role_pair_ids)
            for side in ("harmful", "harmless")
            if pair_id in safe_by_id
        ]
        e1_gate = close_e1_overlap_gate(
            e1["candidate_records"],
            forbidden_frames=[*jbb, *safe_role_frames],
            decisions=e1_decisions,
            reference_digest=canonical_sha256(_e1_reference_snapshot(
                jbb100=jbb,
                jbb40=jbb40,
                benign30=benign,
                safe_pairs=safe_pairs,
                safe_split=safe_split,
            )),
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
