from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import torch

from paper1_broadening.judge import (
    JudgeParseError,
    Qwen3JudgeRuntime,
    build_judge_record,
)


class _Tokenizer:
    pad_token_id = 0
    eos_token_id = 2
    pad_token = "<pad>"
    eos_token = "<eos>"

    def apply_chat_template(self, messages, *, tokenize=False, add_generation_prompt=True, enable_thinking=True):
        assert tokenize is False
        assert add_generation_prompt is True
        assert enable_thinking is True
        return f"<user>{messages[0]['content']}</user><assistant>"

    def __call__(self, _rendered, **_kwargs):
        return {
            "input_ids": torch.tensor([[5, 6]], dtype=torch.long),
            "attention_mask": torch.tensor([[1, 1]], dtype=torch.long),
        }

    def decode(self, _ids, **_kwargs):
        return "<think>fixture reasoning</think>fixture completion"


class _Model:
    def generate(self, **_kwargs):
        return torch.tensor([[5, 6, 7, 8]], dtype=torch.long)


def _runtime(tmp_path: Path) -> Qwen3JudgeRuntime:
    return Qwen3JudgeRuntime(
        model=_Model(),
        tokenizer=_Tokenizer(),
        model_path=tmp_path,
        device="cpu",
        lifecycle={},
        torch_module=torch,
    )


def test_split_failure_keeps_raw_diagnostics_and_parse_failure_status(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    with patch(
        "paper1_broadening.judge.split_qwen3_thinking_final",
        side_effect=ValueError("semantic boundary missing"),
    ):
        result = runtime.four_class(prompt="request", response="answer", domain="harmful")

    assert result["status"] == "PARSE_FAILURE"
    assert result["label"] is None
    assert result["rationale"] is None
    assert result["raw"] == "<think>fixture reasoning</think>fixture completion"
    assert result["diagnostics"]["raw_completion_sha256"]
    assert result["diagnostics"]["split_error_type"] == "ValueError"
    assert result["diagnostics"]["split_error"] == "semantic boundary missing"
    assert result["observability_status"] == "RAW_AND_DIAGNOSTICS_AVAILABLE"
    assert result["actual_call_count"] == 1

    record = build_judge_record(
        response_id="response-1",
        prompt="request",
        response="answer",
        domain="harmful",
        four_class=result,
    )
    assert record["four_class_raw"] == result["raw"]
    assert record["four_class_diagnostics"] == result["diagnostics"]
    assert record["four_class_observability_status"] == "RAW_AND_DIAGNOSTICS_AVAILABLE"
    assert record["actual_call_counts"] == {"four_class": 1, "binary": 0}


def test_strict_parse_failure_keeps_the_generated_raw_completion(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    split = {
        "final_completion": "not-json",
        "thinking": "fixture reasoning",
        "thinking_token_count": 1,
        "final_token_count": 1,
    }
    with patch("paper1_broadening.judge.split_qwen3_thinking_final", return_value=split):
        result = runtime.four_class(prompt="request", response="answer", domain="harmful")

    assert result["status"] == "PARSE_FAILURE"
    assert result["raw"] == "<think>fixture reasoning</think>fixture completion"
    assert result["diagnostics"]["final_completion_sha256"]
    assert result["observability_status"] == "RAW_AND_DIAGNOSTICS_AVAILABLE"
    assert result["actual_call_count"] == 1


def test_failure_before_raw_generation_is_explicitly_unobservable(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    with patch.object(runtime, "_final_completion", side_effect=JudgeParseError("failed before raw")):
        result = runtime.four_class(prompt="request", response="answer", domain="harmful")

    assert result == {
        "status": "PARSE_FAILURE",
        "label": None,
        "rationale": None,
        "raw": None,
        "error": "failed before raw",
        "diagnostics": {},
        "observability_status": "RAW_UNAVAILABLE",
        "actual_call_count": 1,
    }

    record = build_judge_record(
        response_id="response-2",
        prompt="request",
        response="answer",
        domain="harmful",
        four_class=result,
    )
    assert record["four_class_raw"] is None
    assert record["four_class_diagnostics"] == {}
    assert record["four_class_observability_status"] == "RAW_UNAVAILABLE"


def test_binary_success_keeps_existing_label_and_call_semantics(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    split = {
        "final_completion": "unsafe",
        "thinking": "fixture reasoning",
        "thinking_token_count": 1,
        "final_token_count": 1,
    }
    with patch("paper1_broadening.judge.split_qwen3_thinking_final", return_value=split):
        result = runtime.rogue_binary(prompt="request", response="x" * 1000)

    assert result["status"] == "PARSED"
    assert result["value"] == "unsafe"
    assert result["short_rule_applied"] is False
    assert result["actual_call_count"] == 1
    assert result["observability_status"] == "RAW_AND_DIAGNOSTICS_AVAILABLE"
