from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import pytest

from paper1_broadening.common import BroadeningError, canonical_sha256
from paper1_broadening.config import (
    DESIGN_REVISION,
    PUBLIC_DESIGN_REVISION,
    PUBLIC_EXPANDED_DESIGN_REVISION,
    load_config,
)
from paper1_broadening.frames import (
    DEFAULT_E1_REVIEW_PROMPT_REVISION,
    _e1_semantic_status,
    _e1_reference_snapshot,
    _load_e1,
    _semantic_status,
    build_frames,
    build_safe_pair_split,
    close_e1_overlap_gate,
)
from scripts.adapt_harmbench_e1 import materialize


def _decision(pair_id: str, revision: str = "public-semantic-pair-quality-v2") -> dict[str, object]:
    decision: dict[str, object] = {
        "review_mode": "dual_codex_subagents_v1",
        "review_prompt_revision": revision,
        "adjudication_rule": "unanimous_include_else_exclude",
        "evaluation_frame_digest": "digest-a",
        "reviewer_a": "include",
        "reviewer_b": "include",
        "decision": "include",
        "reviewer_a_agent_id": "agent-a",
        "reviewer_b_agent_id": "agent-b",
        "reviewer_a_model": "model-a",
        "reviewer_b_model": "model-b",
        "reviewer_a_rationale": "rationale",
        "reviewer_b_rationale": "rationale",
        "reviewed_at": "2026-09-08T00:00:00Z",
    }
    for side in ("a", "b"):
        decision[f"reviewer_{side}_raw_output"] = json.dumps(
            {"pair_id": pair_id, "prompt_revision": revision, "verdict": "include"}
        )
    return decision


def test_raw_provenance_and_v2_are_strict() -> None:
    valid = _decision("safe-pair:0")
    assert _semantic_status(valid, pair_id="safe-pair:0") == "SEMANTIC_INCLUDE"
    for field, value in (("pair_id", "safe-pair:9"), ("prompt_revision", "safe-pair-semantic-overlap-v1"), ("verdict", "exclude")):
        tampered = copy.deepcopy(valid)
        raw = json.loads(tampered["reviewer_b_raw_output"])
        raw[field] = value
        tampered["reviewer_b_raw_output"] = json.dumps(raw)
        assert _semantic_status(tampered, pair_id="safe-pair:0") == "PENDING_SEMANTIC_REVIEW"


def test_mixed_evaluation_digest_cannot_be_executable() -> None:
    decisions = {f"safe-pair:{index}": _decision(f"safe-pair:{index}") for index in range(416)}
    decisions["safe-pair:1"]["evaluation_frame_digest"] = "digest-b"
    split = build_safe_pair_split(
        [{"harmful": f"h{index}", "harmless": f"s{index}"} for index in range(416)],
        decisions=decisions,
    )
    assert split["mixed_evaluation_frame_digest"] is True
    assert split["gate"] != "READY_FOR_CONSTRUCTION"


def test_legacy_and_public_configs_validate_without_prepare() -> None:
    root = Path(__file__).resolve().parents[2]
    legacy = load_config(root / "configs/paper1_broadening/mbd_nm_v21.json")
    public = load_config(root / "configs/paper1_broadening/mbd_nm_v211_public.json")
    assert legacy["design_revision"] == DESIGN_REVISION
    assert public["design_revision"] == PUBLIC_DESIGN_REVISION
    assert public["data"]["safe_pairs_path"] == "data/safe_pairs_public_semantic_v1.json"


def test_expanded_review_pair_id_cannot_fallback_to_internal_alias(tmp_path: Path) -> None:
    source = [{
        "pair_id": "upstream:1",
        "review_pair_id": "upstream:1",
        "source_index": 0,
        "harmful": "harmful",
        "harmless": "harmless",
    }]
    decision = _decision("safe-pair:0")
    with pytest.raises(BroadeningError, match="forbidden internal alias"):
        build_safe_pair_split(source, decisions={"safe-pair:0": decision})
    valid_decision = _decision("upstream:1")
    pair_input = {
        "pair_id": "upstream:1", "harmful": "harmful", "harmless": "harmless",
        "evaluation_frame_digest": "digest-a",
    }
    for side in ("a", "b"):
        raw_path = tmp_path / f"{side}.json"
        raw_path.write_text(json.dumps({
            "pair_input": pair_input,
            "pair_input_json_sha256": canonical_sha256(pair_input),
        }), encoding="utf-8")
        valid_decision[f"reviewer_{side}_raw_path"] = str(raw_path)
    split = build_safe_pair_split(source, decisions={"upstream:1": valid_decision})
    assert split["records"][0]["review_pair_id"] == "upstream:1"
    tampered = [dict(source[0], harmful="changed text")]
    with pytest.raises(BroadeningError, match="raw text differs"):
        build_safe_pair_split(tampered, decisions={"upstream:1": valid_decision})


def test_e1_consumer_requires_independent_reference_bound_schema() -> None:
    digest = canonical_sha256([])
    valid = {
        "schema_version": "paper1-e1-overlap-decision-v1",
        "prompt_id": "harmbench:r1:p0",
        "review_mode": "e1_dual_codex_v1",
        "review_prompt_revision": DEFAULT_E1_REVIEW_PROMPT_REVISION,
        "reference_digest": digest,
        "reviewer_a": "include",
        "reviewer_b": "include",
        "decision": "include",
        "reviewer_a_agent_id": "agent-a",
        "reviewer_b_agent_id": "agent-b",
        "reviewer_a_raw_output": json.dumps({
            "prompt_id": "harmbench:r1:p0", "prompt_revision": DEFAULT_E1_REVIEW_PROMPT_REVISION,
            "reference_digest": digest, "verdict": "include",
        }),
        "reviewer_b_raw_output": json.dumps({
            "prompt_id": "harmbench:r1:p0", "prompt_revision": DEFAULT_E1_REVIEW_PROMPT_REVISION,
            "reference_digest": digest, "verdict": "include",
        }),
    }
    assert _e1_semantic_status(valid, prompt_id="harmbench:r1:p0", reference_digest=digest) == "SEMANTIC_INCLUDE"
    legacy = dict(valid)
    legacy["review_prompt_revision"] = "paper1-e1-overlap-v1"
    legacy["reviewer_a_raw_output"] = json.dumps({
        "prompt_id": "harmbench:r1:p0", "prompt_revision": "paper1-e1-overlap-v1",
        "reference_digest": digest, "verdict": "include",
    })
    legacy["reviewer_b_raw_output"] = json.dumps({
        "prompt_id": "harmbench:r1:p0", "prompt_revision": "paper1-e1-overlap-v1",
        "reference_digest": digest, "verdict": "include",
    })
    assert _e1_semantic_status(
        legacy,
        prompt_id="harmbench:r1:p0",
        reference_digest=digest,
        review_prompt_revision="paper1-e1-overlap-v1",
    ) == "SEMANTIC_INCLUDE"
    safe_pair_shaped = _decision("harmbench:r1:p0")
    assert _e1_semantic_status(safe_pair_shaped, prompt_id="harmbench:r1:p0", reference_digest=digest) == "PENDING_SEMANTIC_REVIEW"


def test_e1_consumer_accepts_c2_reference_id_field() -> None:
    result = close_e1_overlap_gate(
        [{"prompt_id": "hb:r1:p0", "category": "illegal", "text": "harmful request extra"}],
        forbidden_frames=[{"reference_id": "safe-pair:0:harmful", "text": "harmful request"}],
    )
    assert result["status"] == "NOT_RUN"
    assert result["reason"] == "E1_SEMANTIC_OVERLAP_REVIEW_PENDING"
    assert result["review_prompt_revision"] == DEFAULT_E1_REVIEW_PROMPT_REVISION
    assert result["review_queue"][0]["candidates"][0]["prompt_id"] == "safe-pair:0:harmful"


def test_e1_reference_snapshot_matches_c2_scope_and_digest() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "configs/paper1_broadening/mbd_nm_v212_public_expanded.json")
    frames = build_frames(config)
    safe_pairs_path = Path(config["project_root"]) / config["data"]["safe_pairs_path"]
    safe_pairs = json.loads(safe_pairs_path.read_text(encoding="utf-8"))
    references = _e1_reference_snapshot(
        jbb100=frames["jbb100"],
        jbb40=frames["jbb40"],
        benign30=frames["benign30"],
        safe_pairs=safe_pairs,
        safe_split=frames["safe_pair_split"],
    )
    assert len(references) == 700
    assert not any(row["reference_kind"] == "benign30" for row in references)
    assert canonical_sha256(references) == "d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a"


def test_expanded_config_manifest_and_revision_are_bound() -> None:
    root = Path(__file__).resolve().parents[2]
    expanded = load_config(root / "configs/paper1_broadening/mbd_nm_v212_public_expanded.json")
    assert expanded["design_revision"] == PUBLIC_EXPANDED_DESIGN_REVISION
    assert expanded["data"]["safe_pairs_source_manifest_path"].endswith(
        "safe_pairs_public_semantic_v2_expanded.manifest.json"
    )


def test_harmbench_adapter_preserves_all_csv_indices_and_native_fields(tmp_path: Path) -> None:
    source_csv = tmp_path / "all.csv"
    source_metadata = tmp_path / "all.metadata.json"
    output_json = tmp_path / "standard.json"
    output_metadata = tmp_path / "standard.metadata.json"
    fields = ["Behavior", "FunctionalCategory", "SemanticCategory", "Tags", "ContextString", "BehaviorID"]
    rows = [
        ["first", "copyright", "copyright", "", "", "id-first"],
        ["second", "standard", "illegal", "tag", "", "id-second"],
        ["third", "contextual", "harmful", "", "context", "id-third"],
        ["fourth", "standard", "cybercrime_intrusion", "", "", "id-fourth"],
    ]
    with source_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)
    source_metadata.write_text(json.dumps({"benchmark": "HarmBench_standard_text", "revision": "fixture-r1"}), encoding="utf-8")
    result = materialize(
        source_csv=source_csv,
        source_metadata=source_metadata,
        output_json=output_json,
        output_metadata=output_metadata,
    )
    assert result["record_count"] == 2
    loaded = _load_e1(output_json, output_metadata)
    assert [row["source_index"] for row in loaded["candidate_records"][:2]] == [1, 3]
    assert [row["source_id"] for row in loaded["candidate_records"][:2]] == ["id-second", "id-fourth"]
    assert [row["category"] for row in loaded["candidate_records"][:2]] == ["illegal", "cybercrime_intrusion"]
    assert [row["text"] for row in loaded["candidate_records"][:2]] == ["second", "fourth"]


def test_public_assets_config_is_explicit_and_preserves_budget() -> None:
    root = Path(__file__).resolve().parents[2]
    assets = load_config(root / "configs/paper1_broadening/mbd_nm_v211_public_assets.json")
    assert assets["models"]["gemma2_9b_it"]["model_path"] == "/data/goodtaste_workspace/models/gemma-2-9b-it"
    assert assets["models"]["gemma2_9b_it"]["layer"] == 14
    assert assets["data"]["e1_harmbench_path"].endswith("harmbench_behaviors_text_standard.json")
    assert assets["budget"]["logical_generation_total"] == 20_480
