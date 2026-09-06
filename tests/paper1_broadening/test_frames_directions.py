from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from paper1_broadening.common import BroadeningError
from paper1_broadening.directions import (
    ContentSpan,
    DirectionError,
    alpha_from_rho,
    content_mask,
    content_mu,
    contrastive_direction,
    e3_layers,
    masked_token_mean,
    render_native_user_prompt,
    rogue_directions,
    sign_diagnostic,
    third_model_layer,
    user_content_span,
    validate_unit_vector,
)
from paper1_broadening.frames import (
    _load_e1,
    build_jbb40,
    build_overlap_queue,
    build_safe_pair_split,
    close_e1_overlap_gate,
    load_jbb,
)


class CharTokenizer:
    def apply_chat_template(self, messages, *, tokenize=False, add_generation_prompt=False, **_kwargs):
        assert tokenize is False
        content = messages[0]["content"]
        return f"<system>empty</system><user>{content}</user><assistant>"

    def __call__(self, rendered, *, add_special_tokens=False, return_offsets_mapping=False, **_kwargs):
        assert add_special_tokens is False
        if return_offsets_mapping:
            return {"offset_mapping": [(index, index + 1) for index in range(len(rendered))]}
        raise AssertionError("the fixture tokenizer only supports offset mapping")


def _jbb_rows() -> list[dict[str, object]]:
    rows = []
    for category_index in range(10):
        for item_index in range(10):
            source_index = category_index * 10 + item_index
            rows.append({
                "Index": source_index,
                "Category": f"category-{category_index}",
                "Goal": f"goal {source_index}",
                "Source": "fixture-jbb",
            })
    return rows


def test_jbb100_and_jbb40_preserve_source_index_and_category_quota(tmp_path: Path) -> None:
    path = tmp_path / "jbb.json"
    path.write_text(json.dumps(list(reversed(_jbb_rows()))), encoding="utf-8")
    jbb100 = load_jbb(path, "fixture-v1")
    assert len(jbb100) == 100
    assert [row["source_index"] for row in jbb100] == list(range(100))
    jbb40 = build_jbb40(jbb100)
    assert len(jbb40) == 40
    assert all(sum(row["category"] == category for row in jbb40) == 4 for category in {row["category"] for row in jbb100})
    assert {row["source_index"] for row in jbb40} == {
        category_index * 10 + item_index
        for category_index in range(10)
        for item_index in range(4)
    }


def test_safe_pair_split_deduplicates_roles_and_keeps_semantic_gate_pending() -> None:
    pairs = [
        {"harmful": f"harmful request {index}", "harmless": f"harmless request {index}"}
        for index in range(500)
    ]
    pairs[499]["harmful"] = pairs[0]["harmful"]
    pairs[2]["harmless"] = "evaluation exact text"
    evaluation = [
        {"prompt_id": "jbb:0", "text": "evaluation exact text"},
        {"prompt_id": "jbb:near", "text": "harmful request 3 extra wording"},
    ]
    split = build_safe_pair_split(pairs, evaluation_frames=evaluation)
    assert split["source_count"] == 500
    assert split["preliminary_eligible_count"] == 498
    assert split["actual_k"] == 79
    assert len(split["construction_folds"]) == 5
    assert all(len(fold) == 79 for fold in split["construction_folds"])
    assert len(split["development"]) == 100
    assert split["gate"] == "PENDING_SEMANTIC_REVIEW"
    construction = set().union(*map(set, split["construction_folds"]))
    assert construction.isdisjoint(split["development"])
    assert split["role_isolation"]["construction_and_development_disjoint"] is True
    assert split["exact_evaluation_overlap_count"] == 1
    queue = build_overlap_queue(safe_split=split, evaluation_frames=evaluation)
    assert any(row["pair_id"] == "safe-pair:3" for row in queue)

    decisions = {
        row["pair_id"]: {"reviewer_a": "include", "reviewer_b": "include", "decision": "include"}
        for row in split["records"]
    }
    ready = build_safe_pair_split(pairs, decisions=decisions)
    assert ready["gate"] == "READY_FOR_CONSTRUCTION"
    assert ready["executable_eligible_count"] == ready["preliminary_eligible_count"]


def test_dual_codex_semantic_review_is_provenanced_and_conservatively_resolved() -> None:
    pairs = [
        {"harmful": f"harmful request {index}", "harmless": f"harmless request {index}"}
        for index in range(500)
    ]
    base = {
        "review_mode": "dual_codex_subagents_v1",
        "review_prompt_revision": "safe-pair-semantic-overlap-v1",
        "adjudication_rule": "unanimous_include_else_exclude",
        "evaluation_frame_digest": "fixture-evaluation-digest",
        "reviewer_a_agent_id": "agent-a",
        "reviewer_b_agent_id": "agent-b",
        "reviewer_a_model": "fixture-model-a",
        "reviewer_b_model": "fixture-model-b",
        "reviewer_a_raw_output": "{\"verdict\":\"include\"}",
        "reviewer_b_raw_output": "{\"verdict\":\"include\"}",
        "reviewer_a_rationale": "distinct requested task",
        "reviewer_b_rationale": "distinct requested task",
        "reviewed_at": "2026-09-06T00:00:00Z",
    }
    decisions = {
        f"safe-pair:{index}": {**base, "reviewer_a": "include", "reviewer_b": "include", "decision": "include"}
        for index in range(500)
    }
    decisions["safe-pair:3"] = {
        **base,
        "reviewer_a": "include",
        "reviewer_b": "uncertain",
        "decision": "exclude",
        "reviewer_b_rationale": "possible shared operational goal",
    }
    split = build_safe_pair_split(pairs, decisions=decisions)
    assert split["gate"] == "READY_FOR_CONSTRUCTION"
    assert split["executable_eligible_count"] == 499
    assert next(row for row in split["records"] if row["pair_id"] == "safe-pair:3")["semantic_review_status"] == "SEMANTIC_EXCLUDE"

    decisions["safe-pair:4"] = {
        **decisions["safe-pair:4"],
        "reviewer_b_agent_id": "agent-a",
    }
    assert build_safe_pair_split(pairs, decisions=decisions)["gate"] == "PENDING_SEMANTIC_REVIEW"


def test_e1_selection_uses_native_category_order_and_source_index(tmp_path: Path) -> None:
    source = []
    for category in ("zeta", "alpha", "beta", "delta"):
        for source_index in (9, 1, 5, 3, 7, 0, 2, 4, 6, 8):
            source.append({
                "source_id": f"{category}-{source_index}",
                "source_index": source_index,
                "category": category,
                "text": f"{category} request {source_index}",
            })
    source_path = tmp_path / "harmbench.json"
    metadata_path = tmp_path / "metadata.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    metadata_path.write_text(json.dumps({"benchmark": "HarmBench_standard_text", "revision": "fixture-r1"}), encoding="utf-8")
    loaded = _load_e1(source_path, metadata_path)
    candidates = loaded["candidate_records"]
    assert [row["prompt_id"] for row in candidates[:4]] == [
        "harmbench:fixture-r1:zeta-0",
        "harmbench:fixture-r1:zeta-1",
        "harmbench:fixture-r1:zeta-2",
        "harmbench:fixture-r1:zeta-3",
    ]
    closed = close_e1_overlap_gate(candidates, forbidden_frames=[])
    assert closed["status"] == "READY_FOR_RUN"
    assert len(closed["records"]) == 40
    assert [row["category"] for row in closed["records"][:4]] == ["zeta", "alpha", "beta", "delta"]


def test_content_span_excludes_template_and_validates_direction_geometry() -> None:
    tokenizer = CharTokenizer()
    prompt = "repeat <user> text"
    rendered = render_native_user_prompt(tokenizer, prompt)
    span = user_content_span(tokenizer, prompt)
    assert rendered[span.char_start : span.char_end] == prompt
    assert span.token_count == len(prompt)
    mask = content_mask(len(rendered), span)
    assert int(mask.sum()) == len(prompt)
    assert not bool(mask[0])

    harmful = torch.tensor([[2.0, 0.0], [2.0, 0.0]])
    harmless = torch.zeros_like(harmful)
    assert torch.allclose(masked_token_mean(harmful, torch.ones(2, dtype=torch.bool)), torch.tensor([2.0, 0.0]))
    direction = contrastive_direction([(masked_token_mean(harmful, torch.ones(2, dtype=torch.bool)), torch.zeros(2))])
    assert torch.allclose(direction, torch.tensor([1.0, 0.0]))
    assert sign_diagnostic([torch.tensor([2.0, 0.0])], [torch.zeros(2)], direction)["sign_check"] == "SIGN_VALIDATED"
    assert sign_diagnostic([torch.zeros(2)], [torch.tensor([2.0, 0.0])], direction)["sign_check"] == "SIGN_NOT_VALIDATED"
    assert validate_unit_vector(direction, hidden_size=2) == pytest.approx(1.0)
    assert content_mu([torch.tensor([[3.0, 4.0], [0.0, 4.0]])]) == (4.5, 2)
    assert alpha_from_rho(0.5, 4.0) == 2.0
    with pytest.raises(DirectionError):
        masked_token_mean(torch.tensor([[float("nan")]]), torch.ones(1, dtype=torch.bool))
    with pytest.raises(DirectionError):
        contrastive_direction([(torch.ones(2), torch.ones(2))])
    with pytest.raises(DirectionError):
        alpha_from_rho(-1.0, 1.0)


def test_random_directions_and_layer_formulas_are_fixed() -> None:
    first = rogue_directions(hidden_size=5, model_index=1, count=3)
    second = rogue_directions(hidden_size=5, model_index=1, count=3)
    assert all(torch.equal(left, right) for left, right in zip(first, second))
    assert all(torch.linalg.vector_norm(vector).item() == pytest.approx(1.0) for vector in first)
    assert third_model_layer(28) == 9
    assert e3_layers(28) == (7, 20)
    with pytest.raises(DirectionError):
        validate_unit_vector(torch.zeros(5), hidden_size=5)
