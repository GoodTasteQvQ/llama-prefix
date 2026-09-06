from __future__ import annotations

from pathlib import Path

import pytest

from paper1_broadening import pipeline
from paper1_broadening.archive import archive_run
from paper1_broadening.common import BroadeningError, atomic_write_json, read_json
from paper1_broadening.config import default_config
from paper1_broadening.ledger import (
    append_generation_attempt,
    build_alias_aware_schedule,
    clean_identity,
    generation_attempt,
    steered_identity,
    write_schedule,
)
from paper1_broadening.orchestration import write_generation_ledger


ROOT = Path(__file__).resolve().parents[2]


def test_equal_doses_share_one_attempt_and_keep_two_ledger_rows(tmp_path: Path) -> None:
    identity = steered_identity(
        run_id="alias", block="core_harmful_steered", model_id="qwen25", layer=9,
        family="rogue", condition="decode_only", rho=1.5,
        direction_id="rogue:0", prompt_id="p0",
    )
    schedule = build_alias_aware_schedule([(identity, "A"), (identity, "S")])
    attempt = generation_attempt(
        response_id=schedule[0]["response_id"], attempt_no=1, status="COMPLETED",
        text="response", token_ids=[1], runtime={}, diagnostics={}, error=None,
        identity=identity, dose_label="A",
    )
    counts = write_generation_ledger(run_dir=tmp_path, schedule=schedule, attempts=[attempt])
    assert counts["logical_scheduled"] == 2
    assert counts["completed_physical"] == 1
    assert counts["A_S_alias_deduplicated"] == 1
    with pytest.raises(BroadeningError, match="dose differs"):
        write_generation_ledger(
            run_dir=tmp_path, schedule=schedule, attempts=[{**attempt, "dose_label": "screen"}],
            overwrite=True,
        )


@pytest.mark.parametrize("missing", [False, True])
def test_real_screen_resolves_nested_core_decisions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: bool) -> None:
    from tests.paper1_broadening.test_pipeline_extensions import _frames
    from paper1_broadening.common import append_jsonl, read_jsonl
    from paper1_broadening.judge import build_judge_record

    config = default_config(ROOT)
    atomic_write_json(tmp_path / "run_header.json", {"run_id": "screen"})
    atomic_write_json(tmp_path / "frames.json", _frames())
    atomic_write_json(tmp_path / "directions.json", {"models": {
        model: {"status": "COMPLETED", "mu_content": 1.0, "mu_content_token_count": 10}
        for model in ("qwen25", "llama31")
    }})

    def child(**kwargs):
        if kwargs["command"] == "judge":
            for row in read_jsonl(tmp_path / "screen_generation_schedule_core.jsonl"):
                rho = row["identity"]["rho"]
                result = (
                    {"status": "PARSE_FAILURE", "actual_call_count": 2}
                    if missing and rho == 0.5 else
                    {"status": "PARSED", "label": "unsafe" if rho < 1.0 else "broken",
                     "rationale": "fixture judgment", "actual_call_count": 1}
                )
                append_jsonl(tmp_path / "screen_judge_records_core.jsonl", build_judge_record(
                    response_id=row["response_id"], prompt="fixture", response="fixture",
                    domain="harmful", four_class=result,
                ))
        return {"success": True, "returncode": 0, "command": kwargs["command"]}

    monkeypatch.setattr(pipeline, "_run_screen_child", child)
    result = pipeline.run_real_screen(run_dir=tmp_path, config=config)
    if missing:
        assert result["core"]["status"] == "SCREEN_GATE_BLOCKED"
        with pytest.raises(BroadeningError, match="screen is not complete"):
            pipeline.build_evaluation_schedule_for_run(run_dir=tmp_path, config=config)
    else:
        assert result["core"]["status"] == "DOSE_DECIDED"
        assert len(pipeline.build_evaluation_schedule_for_run(run_dir=tmp_path, config=config)) == 11440


def _terminal_generation(run_dir: Path, model: str = "qwen25", layer: int = 9):
    config = default_config(ROOT)
    prompt = {"prompt_id": "p0", "text": "fixture request", "category": "fixture", "frame": "JBB100"}
    atomic_write_json(run_dir / "run_header.json", {"run_id": "judge", "fixture": False})
    atomic_write_json(run_dir / "resolved_config.json", config)
    atomic_write_json(run_dir / "frames.json", {"jbb100": [prompt]})
    atomic_write_json(run_dir / "analysis.json", {})
    clean = clean_identity(run_id="judge", block="core_harmful_clean", model_id=model, prompt_id="p0")
    steered = steered_identity(
        run_id="judge", block="core_harmful_steered", model_id=model, layer=layer,
        family="rogue", condition="decode_only", rho=0.5, direction_id="rogue:0", prompt_id="p0",
    )
    schedule = build_alias_aware_schedule([(clean, "clean"), (steered, "A")])
    write_schedule(run_dir / "generation_schedule.jsonl", schedule)
    attempts = []
    for row in schedule:
        attempt = generation_attempt(
            response_id=row["response_id"], attempt_no=1, status="COMPLETED",
            text="fixture response", token_ids=[1], runtime={}, diagnostics={}, error=None,
            identity=row["identity"], dose_label=row["dose_label"],
        )
        append_generation_attempt(run_dir / "generation_attempts.jsonl", attempt)
        attempts.append(attempt)
    write_generation_ledger(run_dir=run_dir, schedule=schedule, attempts=attempts)
    atomic_write_json(run_dir / "behavior_release.json", {f"{model}|layer{layer}": {
        "behavior_released": True, "behavior_hook_removed": True,
        "behavior_model_reference_cleared": True, "behavior_tokenizer_reference_cleared": True,
        "gc_collect_called": True, "models_concurrently_resident": False,
    }})
    return config


class _FakeJudge:
    def identity(self):
        return {"model_revision": "fixture"}

    def four_class(self, **kwargs):
        return {"status": "PARSED", "label": "safe", "rationale": "fixture", "actual_call_count": 1}

    def release(self):
        return {"judge_released": True, "judge_model_reference_cleared": True,
                "judge_tokenizer_reference_cleared": True, "judge_gc_collect_called": True}


@pytest.mark.parametrize("model,layer", [("qwen25", 9), ("gemma2_9b_it", 14)])
def test_real_judge_release_can_be_archived(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model: str, layer: int) -> None:
    config = _terminal_generation(tmp_path, model, layer)
    monkeypatch.setattr(pipeline, "verify_run_source_snapshot", lambda **kwargs: {})
    monkeypatch.setattr(pipeline.Qwen3JudgeRuntime, "from_pretrained", lambda **kwargs: _FakeJudge())
    result = pipeline.run_real_judge(run_dir=tmp_path, config=config)
    assert result["status"] == "COMPLETED"
    manifest = archive_run(
        run_dir=tmp_path, repo_root=ROOT, run_header=read_json(tmp_path / "run_header.json"),
        source_ids={"fixture": True},
    )
    assert manifest["archive_status"] == "PENDING_HUMAN"


def test_judge_load_failure_can_resume_without_losing_responses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from paper1_broadening.common import read_jsonl
    config = _terminal_generation(tmp_path)
    monkeypatch.setattr(pipeline, "verify_run_source_snapshot", lambda **kwargs: {})

    def fail_load(**kwargs):
        raise RuntimeError("fixture load failure")

    monkeypatch.setattr(pipeline.Qwen3JudgeRuntime, "from_pretrained", fail_load)
    assert pipeline.run_real_judge(run_dir=tmp_path, config=config)["status"] == "RUNTIME_NOT_RUN"
    monkeypatch.setattr(pipeline.Qwen3JudgeRuntime, "from_pretrained", lambda **kwargs: _FakeJudge())
    assert pipeline.run_real_judge(run_dir=tmp_path, config=config)["status"] == "COMPLETED"
    records = read_jsonl(tmp_path / "judge_records.jsonl")
    assert len(records) == 2
    assert all(row["four_class_status"] == "PARSED" for row in records)
    assert read_json(tmp_path / "judge_runtime_status.json")["status"] == "COMPLETED"


def test_generation_retries_once_before_judge_handoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from paper1_broadening.common import read_jsonl
    config = _terminal_generation(tmp_path)
    calls = []

    class Runtime:
        layer = 9

        def identity(self):
            return {"model_id": "qwen25", "layer": 9}

        def generate(self, **kwargs):
            calls.append(kwargs["condition"])
            if len(calls) == 1:
                raise RuntimeError("transient fixture error")
            return {"text": "ok", "token_ids": [1], "condition": kwargs["condition"],
                    "latency_seconds": 0.1, "runtime_counters": {}, "metrics": {},
                    "actual_alpha": 0.5, "eos_first": False}

        def release(self):
            return {"behavior_released": True}

    monkeypatch.setattr(pipeline, "verify_run_source_snapshot", lambda **kwargs: {})
    monkeypatch.setattr(pipeline, "_direction_tensor_map", lambda *args: ({"qwen25|rogue:0": [1]}, {"qwen25": 1.0}))
    monkeypatch.setattr(pipeline.BehaviorRuntime, "from_pretrained", lambda **kwargs: Runtime())
    result = pipeline.run_real_generation(
        run_dir=tmp_path, config=config, attempts_filename="new_attempts.jsonl",
    )
    assert result["accounting"]["completed_physical"] == 2
    attempts = read_jsonl(tmp_path / "new_attempts.jsonl")
    assert len(attempts) == 3
    assert attempts[-1]["attempt_no"] == 2
    assert attempts[-1]["status"] == "COMPLETED"


def test_archival_keeps_terminal_generation_missingness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from paper1_broadening.common import atomic_write_bytes, canonical_json
    from paper1_broadening.ledger import load_schedule
    config = _terminal_generation(tmp_path)
    schedule = load_schedule(tmp_path / "generation_schedule.jsonl")
    attempts = []
    for row in schedule:
        for number, status in [(1, "TECHNICAL_FAILURE_RETRYABLE"), (2, "TERMINAL_TECHNICAL_FAILURE")]:
            attempts.append(generation_attempt(
                response_id=row["response_id"], attempt_no=number, status=status,
                text=None, token_ids=None, runtime={}, diagnostics={}, error="fixture error",
                identity=row["identity"], dose_label=row["dose_label"],
            ))
    atomic_write_bytes(tmp_path / "generation_attempts.jsonl", b"".join(
        (canonical_json(row) + "\n").encode("utf-8") for row in attempts
    ), overwrite=True)
    write_generation_ledger(run_dir=tmp_path, schedule=schedule, attempts=attempts, overwrite=True)
    monkeypatch.setattr(pipeline, "verify_run_source_snapshot", lambda **kwargs: {})
    monkeypatch.setattr(pipeline.Qwen3JudgeRuntime, "from_pretrained", lambda **kwargs: _FakeJudge())
    pipeline.run_real_judge(run_dir=tmp_path, config=config, binary=True)
    manifest = archive_run(
        run_dir=tmp_path, repo_root=ROOT, run_header=read_json(tmp_path / "run_header.json"),
        source_ids={"fixture": True},
    )
    assert manifest["terminal_check"]["terminal"] is True
