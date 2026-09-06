from __future__ import annotations

from pathlib import Path

import pytest

from paper1_broadening.allocator import choose_doses
from paper1_broadening.common import BroadeningError, read_jsonl
from paper1_broadening.judge import (
    JudgeParseError,
    build_judge_record,
    labels_for_domain,
    strict_binary_parse,
    strict_four_class_parse,
)
from paper1_broadening.ledger import (
    append_generation_attempt,
    canonical_generation_records,
    clean_identity,
    generation_attempt,
    ledger_accounting,
    response_aliases,
    steered_identity,
    validate_attempt_sequence,
)


def _identity(run_id: str = "run") -> dict[str, object]:
    return steered_identity(
        run_id=run_id,
        block="core_harmful_steered",
        model_id="qwen25",
        layer=9,
        family="rogue",
        condition="decode_only",
        rho=0.5,
        direction_id="rogue:0",
        prompt_id="jbb:v1:0",
    )


def _attempt(identity: dict[str, object], *, number: int, status: str, text: str | None = None, response_id: str = "response-1") -> dict[str, object]:
    return generation_attempt(
        response_id=response_id,
        attempt_no=number,
        status=status,
        text=text,
        token_ids=[1, 2] if text is not None else None,
        runtime={"condition": identity["condition"]},
        diagnostics={},
        error=None if text is not None else "transient",
        identity=identity,
        dose_label="A",
    )


def test_alias_schedule_and_canonical_retry_accounting(tmp_path: Path) -> None:
    identity = _identity()
    from paper1_broadening.ledger import build_alias_aware_schedule

    schedule = build_alias_aware_schedule([(identity, "A"), (identity, "S")])
    assert len(schedule) == 2
    assert len(response_aliases(schedule)) == 1
    response_id = schedule[0]["response_id"]
    first = _attempt(identity, number=1, status="TECHNICAL_FAILURE_RETRYABLE", response_id=response_id)
    second = _attempt(identity, number=2, status="COMPLETED", text="", response_id=response_id)
    path = tmp_path / "attempts.jsonl"
    append_generation_attempt(path, first)
    append_generation_attempt(path, second)
    state = canonical_generation_records(read_jsonl(path))
    assert state[response_id]["canonical_attempt"]["attempt_no"] == 2
    accounting = ledger_accounting(schedule, read_jsonl(path))
    assert accounting["logical_scheduled"] == 2
    assert accounting["physical_scheduled"] == 1
    assert accounting["A_S_alias_deduplicated"] == 1
    assert accounting["completed_physical"] == 1

    retry_again = _attempt(identity, number=2, status="TECHNICAL_FAILURE_RETRYABLE", response_id=response_id)
    with pytest.raises(BroadeningError):
        validate_attempt_sequence([first, retry_again], allow_pending_retry=True)


def test_clean_identity_and_attempt_identity_are_fail_closed() -> None:
    clean = clean_identity(run_id="run", block="core_harmful_clean", model_id="qwen25", prompt_id="p")
    assert clean["family"] is None and clean["rho"] is None and clean["direction_id"] is None
    with pytest.raises(BroadeningError):
        steered_identity(
            run_id="run", block="x", model_id="qwen25", layer=-1, family="rogue",
            condition="decode_only", rho=1.0, direction_id="rogue:0", prompt_id="p",
        )
    identity = _identity()
    attempt = _attempt(identity, number=1, status="TECHNICAL_FAILURE_RETRYABLE")
    forged = _attempt({**identity, "prompt_id": "other"}, number=2, status="COMPLETED", text="response")
    with pytest.raises(BroadeningError):
        validate_attempt_sequence([attempt, forged], allow_pending_retry=True)


def test_identity_and_completed_attempt_payloads_are_strict() -> None:
    with pytest.raises(BroadeningError):
        clean_identity(run_id="run", block="core_harmful_clean", model_id="qwen25", prompt_id="")
    identity = _identity()
    with pytest.raises(BroadeningError):
        generation_attempt(
            response_id="r", attempt_no=1, status="COMPLETED", text="output", token_ids=None,
            runtime={}, diagnostics={}, error=None, identity=identity, dose_label="A",
        )


def _dose_rows(labels_by_rho: dict[float, list[str | None]]) -> list[dict[str, object]]:
    return [
        {"rho": rho, "label": label}
        for rho, labels in labels_by_rho.items()
        for label in labels
    ]


def test_dose_allocator_ties_missing_and_ordering_states() -> None:
    labels = {
        0.50: ["unsafe", "unsafe", "safe"],
        0.75: ["unsafe", "unsafe", "safe"],
        1.00: ["safe", "safe", "safe"],
        1.25: ["broken", "broken", "safe"],
        1.50: ["broken", "broken", "safe"],
    }
    decision = choose_doses(_dose_rows(labels), mu_content=2.0, expected_per_rho=3)
    assert decision["A"]["rho"] == 0.5
    assert decision["S"]["rho"] == 1.25
    assert decision["ordering_not_established"] is False

    zero_unsafe = {rho: ["safe", "safe", "safe"] for rho in labels}
    zero = choose_doses(_dose_rows(zero_unsafe), mu_content=2.0, expected_per_rho=3)
    assert zero["A"]["status"] == "A_NOT_ESTABLISHED"
    assert zero["S"]["status"] == "S_NOT_ATTAINED"

    s_le_a = {
        0.50: ["broken", "broken", "safe"],
        0.75: ["safe", "safe", "safe"],
        1.00: ["safe", "safe", "safe"],
        1.25: ["unsafe", "unsafe", "safe"],
        1.50: ["safe", "safe", "safe"],
    }
    ordering = choose_doses(_dose_rows(s_le_a), mu_content=1.0, expected_per_rho=3)
    assert ordering["S"]["rho"] == 0.5
    assert ordering["ordering_not_established"] is True

    missing = _dose_rows(labels)
    missing[0]["label"] = None
    blocked = choose_doses(missing, mu_content=1.0, expected_per_rho=3)
    assert blocked["status"] == "SCREEN_GATE_BLOCKED"
    assert blocked["A"] is None and blocked["S"] is None


def test_judge_parsing_is_strict_and_domains_stay_separate() -> None:
    assert labels_for_domain("harmful") == ("unsafe", "refusal", "safe", "broken")
    assert strict_four_class_parse('{"label":"broken","rationale":"valid"}', "harmful") == ("broken", "valid")
    assert strict_binary_parse("UNSAFE") == "unsafe"
    with pytest.raises(JudgeParseError):
        strict_four_class_parse('{"label":"helpful","rationale":"wrong domain"}', "harmful")
    with pytest.raises(JudgeParseError):
        strict_four_class_parse('{"label":"safe","rationale":""}', "harmful")
    with pytest.raises(JudgeParseError):
        strict_binary_parse("maybe")
    record = build_judge_record(
        response_id="r", prompt="p", response="", domain="benign",
        four_class={"status": "UNEXECUTED", "error": "generation_missing", "actual_call_count": 0},
    )
    assert record["domain"] == "benign"
    assert record["four_class_label"] is None
    assert record["binary_status"] == "NOT_REQUESTED"
