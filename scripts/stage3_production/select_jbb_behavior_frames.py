#!/usr/bin/env python
"""Build the deterministic Paper 1 Stage 3 JBB behavior prompt frames."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "paper1-stage3-jbb-behavior-frames-v1"
SELECTION_NAMESPACE = "paper1-stage3-jbb-split-v1"
MASTER_SEED = 42
EXPECTED_FIELDS = ["Index", "Goal", "Target", "Behavior", "Category", "Source"]
EXPECTED_CATEGORIES = [
    "Disinformation",
    "Economic harm",
    "Expert advice",
    "Fraud/Deception",
    "Government decision-making",
    "Harassment/Discrimination",
    "Malware/Hacking",
    "Physical harm",
    "Privacy",
    "Sexual/Adult content",
]
LOCAL_SOURCE_SHA256 = "9ee1cb2aab52550f0817f036e4423e9f3cc05a6bb5a0084da404f1817d535e77"
SOURCE_RECORD_FRAME_SHA256 = "ffd1760322b378c27496ea8f188b5b1e0fa463b2e3f0b6c6b90db24ec9358a0e"
P1_SELECTED_SHA256 = "700c2c391c86273fca01ec9823feb66a3b1927ac39cc81d1de7567c71bebfd36"
OFFICIAL_DATASET_REVISION = "886acc352a31533ffbcf4ef22c744658688086fc"
OFFICIAL_CSV_SHA256 = "4a8ec6832056b631eb092dccc60d37a61c3d441268268888b3d006288afeffa1"
OFFICIAL_CSV_GIT_OID = "5a7549cd9de9bb327914de0800606a1af1ec8849"
OFFICIAL_LICENSE_SHA256 = "7e1ae8f3676f39ff6e62af1743385c176a9476b1157f35bb9d05b4e6c65b7d94"

SOURCE_RELATIVE_PATH = Path("data/jbb_behaviors_harmful.json")
P1_SELECTED_RELATIVE_PATH = Path(
    "data/stage3/p1_harmful_do_not_answer_v1/selected_p1_harmful_100.json"
)
P1_REVIEW_RELATIVE_PATH = Path(
    "data/stage3/p1_harmful_do_not_answer_v1/duplicate_leakage_review.json"
)
DEFAULT_ARTIFACT_DIRECTORY = Path("data/stage3/jbb_behavior_frames_v1")
DEFAULT_CONFIG_DIRECTORY = Path("configs/stage3")

EXPECTED_MEMBERSHIP_IDS = {
    "confirm": [
        0, 2, 3, 7, 8, 10, 11, 12, 15, 19, 20, 21, 23, 26, 29, 30, 31,
        35, 38, 39, 42, 43, 44, 45, 46, 50, 51, 54, 55, 56, 60, 61, 62,
        65, 66, 72, 73, 74, 75, 79, 80, 83, 84, 86, 89, 91, 92, 96, 98,
        99,
    ],
    "screen": [
        1, 5, 9, 13, 14, 17, 22, 24, 27, 34, 36, 37, 41, 47, 49, 53,
        57, 59, 64, 68, 69, 76, 77, 78, 81, 82, 87, 93, 94, 95,
    ],
    "unused": [
        4, 6, 16, 18, 25, 28, 32, 33, 40, 48, 52, 58, 63, 67, 70, 71,
        85, 88, 90, 97,
    ],
}

NEAR_DUPLICATE_REVIEW = {
    (10, 13): ("KEEP_DISTINCT", "disable_antivirus_vs_password_cracking"),
    (25, 29): ("KEEP_DISTINCT", "eating_disorder_promotion_vs_predatory_stalking"),
    (51, 53): ("KEEP_DISTINCT", "september_11_conspiracy_vs_holocaust_denial"),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")


def normalize_exact(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).lower()


def _word_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[^\W_]+", normalize_exact(value), flags=re.UNICODE)
        if len(token) >= 3
    }


def _character_ngrams(value: str, n: int = 5) -> set[str]:
    normalized = re.sub(r"\W+", " ", normalize_exact(value), flags=re.UNICODE).strip()
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[index : index + n] for index in range(len(normalized) - n + 1)}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def lexical_scores(left: str, right: str) -> tuple[float, float]:
    return (
        _jaccard(_word_tokens(left), _word_tokens(right)),
        _jaccard(_character_ngrams(left), _character_ngrams(right)),
    )


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot strictly load JSON from {path}: {exc}") from exc


def load_and_validate_source(repo_root: Path) -> list[dict[str, Any]]:
    source_path = repo_root / SOURCE_RELATIVE_PATH
    observed_sha256 = file_sha256(source_path)
    if observed_sha256 != LOCAL_SOURCE_SHA256:
        raise SystemExit(
            "Local JBB source SHA256 mismatch: "
            f"observed={observed_sha256} expected={LOCAL_SOURCE_SHA256}."
        )
    rows = _load_json(source_path)
    if not isinstance(rows, list) or len(rows) != 100:
        raise SystemExit("JBB source must be a top-level 100-record JSON array.")

    indices: list[int] = []
    goals: list[str] = []
    for position, row in enumerate(rows):
        if not isinstance(row, dict) or list(row) != EXPECTED_FIELDS:
            raise SystemExit(
                f"JBB row {position} does not have the exact ordered source schema."
            )
        index = row["Index"]
        if not isinstance(index, int) or isinstance(index, bool):
            raise SystemExit(f"JBB row {position} has a non-integer Index.")
        if any(not isinstance(row[field], str) or not row[field] for field in EXPECTED_FIELDS[1:]):
            raise SystemExit(f"JBB row {position} has an empty or non-string source field.")
        indices.append(index)
        goals.append(row["Goal"])

    if indices != list(range(100)) or len(set(indices)) != 100:
        raise SystemExit("JBB source Index values must be unique and ordered 0..99.")
    if len(set(goals)) != 100:
        raise SystemExit("JBB source Goal values must be unique.")
    if canonical_sha256(rows) != SOURCE_RECORD_FRAME_SHA256:
        raise SystemExit("JBB canonical six-field record frame identity mismatch.")
    if len({canonical_sha256(row) for row in rows}) != 100:
        raise SystemExit("JBB canonical source record identities must be unique.")

    category_counts = Counter(row["Category"] for row in rows)
    if sorted(category_counts) != EXPECTED_CATEGORIES or set(category_counts.values()) != {10}:
        raise SystemExit("JBB source must contain the exact ten categories with ten rows each.")
    return rows


def selection_rank(row: dict[str, Any]) -> str:
    payload = {
        "category": row["Category"],
        "index": row["Index"],
        "master_seed": MASTER_SEED,
        "namespace": SELECTION_NAMESPACE,
    }
    return canonical_sha256(payload)


def assign_memberships(
    rows: list[dict[str, Any]],
) -> tuple[dict[int, str], dict[int, str], dict[str, dict[str, list[int]]]]:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_category[row["Category"]].append(row)

    memberships: dict[int, str] = {}
    ranks: dict[int, str] = {}
    category_ids: dict[str, dict[str, list[int]]] = {}
    for category in EXPECTED_CATEGORIES:
        ranked = sorted(
            by_category[category],
            key=lambda row: (selection_rank(row), row["Index"]),
        )
        assignments = {
            "confirm": ranked[:5],
            "screen": ranked[5:8],
            "unused": ranked[8:],
        }
        category_ids[category] = {
            membership: [row["Index"] for row in members]
            for membership, members in assignments.items()
        }
        for membership, members in assignments.items():
            for row in members:
                index = row["Index"]
                memberships[index] = membership
                ranks[index] = selection_rank(row)

    actual_ids = {
        membership: sorted(index for index, value in memberships.items() if value == membership)
        for membership in ("confirm", "screen", "unused")
    }
    if actual_ids != EXPECTED_MEMBERSHIP_IDS:
        raise SystemExit("Deterministic JBB membership does not match the reviewed v1 split.")
    if len(memberships) != 100 or len(ranks) != 100 or len(set(ranks.values())) != 100:
        raise SystemExit("JBB split coverage or rank uniqueness failure.")
    return memberships, ranks, category_ids


def _normalized_duplicate_groups(values: Iterable[tuple[int, str]]) -> list[list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for identity, value in values:
        groups[normalize_exact(value)].append(identity)
    return sorted(sorted(group) for group in groups.values() if len(group) > 1)


def build_duplicate_leakage_summary(
    repo_root: Path,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    p1_path = repo_root / P1_SELECTED_RELATIVE_PATH
    if file_sha256(p1_path) != P1_SELECTED_SHA256:
        raise SystemExit("P1 selected harmful artifact identity mismatch.")
    p1 = _load_json(p1_path)
    p1_records = p1.get("records") if isinstance(p1, dict) else None
    if not isinstance(p1_records, list) or len(p1_records) != 100:
        raise SystemExit("P1 selected harmful artifact does not contain 100 records.")

    jbb_normalized = {normalize_exact(row["Goal"]): row["Index"] for row in rows}
    p1_normalized = {
        normalize_exact(record["question"]): record["source_id"] for record in p1_records
    }
    internal_exact = _normalized_duplicate_groups(
        (row["Index"], row["Goal"]) for row in rows
    )
    exact_overlap = sorted(set(jbb_normalized) & set(p1_normalized))
    if internal_exact or exact_overlap:
        raise SystemExit(
            "A normalized exact duplicate affects the fixed JBB source; owner decision required."
        )

    internal_candidates: list[dict[str, Any]] = []
    for left_position, left in enumerate(rows):
        for right in rows[left_position + 1 :]:
            word_score, character_score = lexical_scores(left["Goal"], right["Goal"])
            if word_score >= 0.35 or character_score >= 0.35:
                key = (left["Index"], right["Index"])
                if key not in NEAR_DUPLICATE_REVIEW:
                    raise SystemExit(f"Unreviewed JBB lexical candidate: {key}.")
                disposition, rationale = NEAR_DUPLICATE_REVIEW[key]
                internal_candidates.append(
                    {
                        "source_indices": list(key),
                        "word_token_jaccard": round(word_score, 12),
                        "character_5gram_jaccard": round(character_score, 12),
                        "manual_review_disposition": disposition,
                        "manual_review_rationale": rationale,
                    }
                )
    if {tuple(item["source_indices"]) for item in internal_candidates} != set(
        NEAR_DUPLICATE_REVIEW
    ):
        raise SystemExit("Reviewed JBB lexical candidate set is incomplete.")

    cross_candidates: list[dict[str, Any]] = []
    for row in rows:
        for record in p1_records:
            word_score, character_score = lexical_scores(row["Goal"], record["question"])
            if word_score >= 0.30 or character_score >= 0.30:
                cross_candidates.append(
                    {
                        "jbb_index": row["Index"],
                        "p1_source_id": record["source_id"],
                        "word_token_jaccard": round(word_score, 12),
                        "character_5gram_jaccard": round(character_score, 12),
                    }
                )
    if cross_candidates:
        raise SystemExit("Unexpected P1-to-JBB lexical candidates require owner review.")

    review = _load_json(repo_root / P1_REVIEW_RELATIVE_PATH)
    final_review = review.get("final_frame") if isinstance(review, dict) else None
    if (
        review.get("jbb_scope", {}).get("sha256") != LOCAL_SOURCE_SHA256
        or not isinstance(final_review, dict)
        or final_review.get("normalized_exact_overlap_with_jbb_count") != 0
        or final_review.get("jbb_threshold_candidates") != []
    ):
        raise SystemExit("Existing P1 duplicate/leakage review does not confirm this JBB source.")

    return {
        "exact_normalization": [
            "Unicode_NFKC",
            "trim",
            "collapse_consecutive_whitespace_to_ASCII_space",
            "lowercase",
        ],
        "jbb_internal_normalized_exact_duplicate_count": 0,
        "p1_harmful_to_jbb_normalized_exact_overlap_count": 0,
        "jbb_internal_lexical_candidate_threshold": "word>=0.35 OR char5>=0.35",
        "jbb_internal_lexical_candidates": internal_candidates,
        "p1_to_jbb_lexical_candidate_threshold": "word>=0.30 OR char5>=0.30",
        "p1_to_jbb_lexical_candidates": [],
        "lexical_candidates_change_membership": False,
        "existing_p1_review_relative_path": P1_REVIEW_RELATIVE_PATH.as_posix(),
        "existing_p1_review_conclusion": {
            "normalized_exact_overlap_with_jbb_count": 0,
            "jbb_threshold_candidates": 0,
        },
    }


def _source_provenance() -> dict[str, Any]:
    return {
        "official_dataset_id": "JailbreakBench/JBB-Behaviors",
        "official_code_repository": "JailbreakBench/jailbreakbench",
        "dataset_revision": OFFICIAL_DATASET_REVISION,
        "config": "behaviors",
        "split": "harmful",
        "source_path": "data/harmful-behaviors.csv",
        "source_file_git_oid": OFFICIAL_CSV_GIT_OID,
        "source_csv_raw_byte_length": 23116,
        "source_csv_raw_sha256": OFFICIAL_CSV_SHA256,
        "local_json_relative_path": SOURCE_RELATIVE_PATH.as_posix(),
        "local_json_raw_byte_length": 34556,
        "local_json_raw_sha256": LOCAL_SOURCE_SHA256,
        "format_independent_record_frame_sha256": SOURCE_RECORD_FRAME_SHA256,
        "local_to_official_relation": (
            "100 records in source order, all six source fields equal; zero field mismatches"
        ),
        "license": "MIT",
        "license_file_raw_sha256": OFFICIAL_LICENSE_SHA256,
    }


def _selected_artifact(
    rows: list[dict[str, Any]],
    memberships: dict[int, str],
    ranks: dict[int, str],
    membership: str,
) -> dict[str, Any]:
    selected_rows = [row for row in rows if memberships[row["Index"]] == membership]
    records = [
        {
            "source_index": row["Index"],
            "prompt": row["Goal"],
            "behavior": row["Behavior"],
            "category": row["Category"],
            "source": row["Source"],
            "source_record_identity_sha256": canonical_sha256(row),
            "selection_rank_sha256": ranks[row["Index"]],
            "split_membership": membership,
        }
        for row in selected_rows
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "jbb_behavior_prompt_frame",
        "role": f"D_behavior_{membership}",
        "status": "design_selected",
        "formal_experiment_run": False,
        "selection_namespace": SELECTION_NAMESPACE,
        "master_seed": MASTER_SEED,
        "frame_order_rule": "source_index_ascending",
        "record_count": len(records),
        "frame_source_indices_sha256": canonical_sha256(
            [record["source_index"] for record in records]
        ),
        "frame_record_identities_sha256": canonical_sha256(
            [record["source_record_identity_sha256"] for record in records]
        ),
        "records": records,
    }


def _license_notice() -> bytes:
    text = f"""# JBB Behavior Frames v1: Provenance and License Notice

Status: `design_selected`. `formal_experiment_run=false`. This package is not a freeze, binding,
promotion, execution authorization, `RUN-READY`, or `PAPER-RUN-READY` declaration.

## Source provenance

- Official dataset: `JailbreakBench/JBB-Behaviors`
- Official benchmark code: `JailbreakBench/jailbreakbench`
- Immutable dataset revision: `{OFFICIAL_DATASET_REVISION}`
- Dataset selector: config `behaviors`, split `harmful`
- Source path: `data/harmful-behaviors.csv`
- Source file Git OID: `{OFFICIAL_CSV_GIT_OID}`
- Official CSV: 23,116 bytes, SHA-256 `{OFFICIAL_CSV_SHA256}`
- Local JSON transform: 34,556 bytes, SHA-256 `{LOCAL_SOURCE_SHA256}`
- Format-independent 100-record frame SHA-256: `{SOURCE_RECORD_FRAME_SHA256}`
- Identity relation: all 100 records and all six source fields match the pinned official CSV in
  source order with zero mismatches. The raw bytes differ because the local copy is JSON with CRLF
  while the official source is CSV with LF.

The selected runtime artifacts retain the source `Goal` as `prompt`. The source `Target` is excluded
from selection, ranking, matching, selected runtime JSON, and runtime input. Source record-identity
digests bind the complete original record only for provenance and misread detection.

## License and redistribution

The pinned dataset declares the MIT License, copyright (c) 2023 JailbreakBench Team. Redistribution is
permitted, including use, copying, modification, merging, publishing, sublicensing, and sale, provided
the copyright notice and permission notice are included in all copies or substantial portions. The work
is provided without warranty. The official dataset card separately requests citation of JailbreakBench
and consideration of the constituent AdvBench and TDC/HarmBench sources; that citation request is
distinct from the MIT redistribution condition. Source labels are retained in every selected record.

## MIT License

Copyright (c) 2023 JailbreakBench Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
    return text.encode("utf-8")


def _active_entry(
    membership: str,
    row_count: int,
    selected_relative_path: Path,
    selected_sha256: str,
) -> dict[str, Any]:
    quota = 5 if membership == "confirm" else 3
    return {
        "schema_version": "paper1-stage3-active-dataset-entry-v1",
        "role": f"D_behavior_{membership}",
        "status": "design_selected",
        "formal_experiment_run": False,
        "relative_path": selected_relative_path.as_posix(),
        "selected_raw_sha256": selected_sha256,
        "row_count": row_count,
        "prompt_field": "prompt",
        "source_index_field": "source_index",
        "source_record_identity_field": "source_record_identity_sha256",
        "selection_rank_field": "selection_rank_sha256",
        "split_membership": membership,
        "selection_namespace": SELECTION_NAMESPACE,
        "master_seed": MASTER_SEED,
        "category_quota": quota,
        "category_count": 10,
        "source_dataset": "JailbreakBench/JBB-Behaviors",
        "source_revision": OFFICIAL_DATASET_REVISION,
        "source_config": "behaviors",
        "source_split": "harmful",
        "source_path": "data/harmful-behaviors.csv",
        "source_local_raw_sha256": LOCAL_SOURCE_SHA256,
        "license": "MIT",
        "split_manifest_relative_path": (
            DEFAULT_ARTIFACT_DIRECTORY / "jbb_behavior_split_manifest.json"
        ).as_posix(),
        "provenance_notice_relative_path": (
            DEFAULT_ARTIFACT_DIRECTORY / "provenance_license_notice.md"
        ).as_posix(),
    }


def build_outputs(
    repo_root: Path,
    artifact_directory: Path = DEFAULT_ARTIFACT_DIRECTORY,
    config_directory: Path = DEFAULT_CONFIG_DIRECTORY,
) -> dict[Path, bytes]:
    rows = load_and_validate_source(repo_root)
    memberships, ranks, category_ids = assign_memberships(rows)
    duplicate_summary = build_duplicate_leakage_summary(repo_root, rows)

    screen = _selected_artifact(rows, memberships, ranks, "screen")
    confirm = _selected_artifact(rows, memberships, ranks, "confirm")
    screen_path = artifact_directory / "selected_jbb_screen_30.json"
    confirm_path = artifact_directory / "selected_jbb_confirm_50.json"
    screen_bytes = pretty_json_bytes(screen)
    confirm_bytes = pretty_json_bytes(confirm)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "jbb_behavior_split_manifest",
        "status": "design_selected",
        "formal_experiment_run": False,
        "source_provenance": _source_provenance(),
        "selection": {
            "namespace": SELECTION_NAMESPACE,
            "master_seed": MASTER_SEED,
            "canonical_rank_payload_fields": [
                "category",
                "index",
                "master_seed",
                "namespace",
            ],
            "canonical_json": "UTF-8, Unicode-code-point key order, no whitespace, ASCII escapes",
            "rank": "SHA256(canonical JSON)",
            "within_category_order": "selection rank ascending, source Index tie-break",
            "quota_per_category": {"confirm": 5, "screen": 3, "unused": 2},
            "final_output_order": "source Index ascending",
            "membership_inputs": ["Category", "Index", "master_seed", "namespace"],
            "source_goal_role": "runtime prompt only after membership is fixed",
            "source_response_prefix_role": "excluded from selection, sorting, matching, and runtime input",
        },
        "category_memberships_in_rank_order": category_ids,
        "final_membership_ids_in_source_index_order": EXPECTED_MEMBERSHIP_IDS,
        "counts": {"confirm": 50, "screen": 30, "unused": 20, "union": 100},
        "pairwise_disjoint": True,
        "complete_source_coverage": True,
        "duplicate_leakage": duplicate_summary,
        "selected_artifacts": {
            "screen": {
                "relative_path": screen_path.as_posix(),
                "raw_sha256": hashlib.sha256(screen_bytes).hexdigest(),
                "row_count": 30,
            },
            "confirm": {
                "relative_path": confirm_path.as_posix(),
                "raw_sha256": hashlib.sha256(confirm_bytes).hexdigest(),
                "row_count": 50,
            },
        },
    }

    config_outputs = {
        config_directory / "jbb_behavior_screen_v1.json": pretty_json_bytes(
            _active_entry(
                "screen", 30, DEFAULT_ARTIFACT_DIRECTORY / screen_path.name,
                hashlib.sha256(screen_bytes).hexdigest(),
            )
        ),
        config_directory / "jbb_behavior_confirm_v1.json": pretty_json_bytes(
            _active_entry(
                "confirm", 50, DEFAULT_ARTIFACT_DIRECTORY / confirm_path.name,
                hashlib.sha256(confirm_bytes).hexdigest(),
            )
        ),
    }
    return {
        artifact_directory / screen_path.name: screen_bytes,
        artifact_directory / confirm_path.name: confirm_bytes,
        artifact_directory / "jbb_behavior_split_manifest.json": pretty_json_bytes(manifest),
        artifact_directory / "provenance_license_notice.md": _license_notice(),
        **config_outputs,
    }


def write_outputs(repo_root: Path, outputs: dict[Path, bytes]) -> None:
    for relative_path, payload in outputs.items():
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_bytes()
            if existing != payload:
                raise SystemExit(
                    f"Refusing to replace differing deterministic artifact: {relative_path}."
                )
            continue
        with path.open("xb") as handle:
            handle.write(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--artifact-directory", type=Path, default=DEFAULT_ARTIFACT_DIRECTORY)
    parser.add_argument("--config-directory", type=Path, default=DEFAULT_CONFIG_DIRECTORY)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    outputs = build_outputs(
        repo_root,
        artifact_directory=args.artifact_directory,
        config_directory=args.config_directory,
    )
    write_outputs(repo_root, outputs)
    for relative_path in sorted(outputs, key=lambda path: path.as_posix()):
        print(
            f"{relative_path.as_posix()} "
            f"{hashlib.sha256(outputs[relative_path]).hexdigest()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
