from __future__ import annotations

from pathlib import Path

import pytest

from paper1_broadening.common import BroadeningError, atomic_write_json, recover_jsonl_tail, read_json, read_jsonl
from paper1_broadening.config import CORE_BUDGET, EXTENSION_BUDGET, default_config, validate_config
from paper1_broadening.extensions import (
    build_e1_schedule,
    build_e2_schedule,
    build_e2_screen_schedule,
    build_e3_schedule,
    build_e3_screen_schedule,
)
from paper1_broadening.orchestration import build_core_schedule, create_run, fixture_e2e, verify_run_source_snapshot
from paper1_broadening.pipeline import (
    _development_screen_prompts,
    _prompt_map,
    _screen_rows_from_artifacts,
    run_real_screen,
)
from paper1_broadening.extensions import extension_prerequisites


def _frames() -> dict[str, object]:
    jbb = [
        {
            "prompt_id": f"jbb:p{index}", "category": f"cat-{index // 10}",
            "text": f"harmful {index}", "frame": "JBB100",
        }
        for index in range(100)
    ]
    jbb40 = [row for row in jbb if int(row["prompt_id"].split("p")[1]) % 10 < 4]
    benign = [
        {"prompt_id": f"benign:p{index}", "category": "benign", "text": f"benign {index}", "frame": "benign30"}
        for index in range(30)
    ]
    safe_pair_records = [
        {
            "pair_id": f"pair-{index}",
            "harmful": f"development harmful {index}",
            "harmless": f"development harmless {index}",
        }
        for index in range(100)
    ]
    return {
        "jbb100": jbb, "jbb40": jbb40, "benign30": benign,
        "safe_pair_split": {
            "development": [f"pair-{index}" for index in range(100)],
            "records": safe_pair_records,
        },
    }


def _doses() -> dict[str, dict[str, dict[str, float]]]:
    return {
        model: {family: {"A": 0.5, "S": 1.5} for family in ("rogue", "contrastive")}
        for model in ("qwen25", "llama31")
    }


def test_config_and_core_schedule_match_fixed_budget() -> None:
    root = Path(__file__).resolve().parents[2]
    config = validate_config(default_config(root))
    assert config["budget"]["core_total"] == 12_640
    assert config["budget"]["extension_total"] == 7_840
    assert config["budget"]["logical_generation_total"] == 20_480
    frames = _frames()
    evaluation = build_core_schedule(
        run_id="fixture", frames=frames, config=config, dose_rhos=_doses(), include_development=False
    )
    full = build_core_schedule(
        run_id="fixture", frames=frames, config=config, dose_rhos=_doses(), include_development=True
    )
    assert len(evaluation) == sum(CORE_BUDGET.values()) - CORE_BUDGET["development"]
    assert len(full) == sum(CORE_BUDGET.values())
    clean = next(row for row in evaluation if row["dose_label"] == "clean")
    assert clean["metadata"]["category"].startswith("cat-")


def test_extension_schedule_counts_and_fixed_layer_vector_references() -> None:
    frames = _frames()
    e1_frames = {
        "e1": {
            "status": "READY_FOR_RUN",
            "records": [
                {"prompt_id": f"hb:{index}", "category": f"hb-cat-{index % 4}", "text": f"hb {index}"}
                for index in range(40)
            ],
        }
    }
    e1 = build_e1_schedule(run_id="fixture", frames=e1_frames, core_dose_rhos=_doses(), core_direction_source_run="core")
    assert len(e1) == EXTENSION_BUDGET["e1_steered"] + EXTENSION_BUDGET["e1_clean"]
    assert all(row["metadata"]["core_direction_source_run"] == "core" for row in e1 if row["dose_label"] != "clean")

    e2 = build_e2_schedule(
        run_id="fixture", jbb40=frames["jbb40"], layer_count=28,
        dose_rhos={family: {"A": 0.5, "S": 1.5} for family in ("rogue", "contrastive")},
    )
    assert len(e2) == EXTENSION_BUDGET["e2_steered"] + EXTENSION_BUDGET["e2_clean"]
    assert {row["identity"]["layer"] for row in e2 if row["dose_label"] != "clean"} == {9}

    e3 = build_e3_schedule(
        run_id="fixture", jbb40=frames["jbb40"], model_layer_counts={"qwen25": 28, "llama31": 28},
        core_layers={"qwen25": 9, "llama31": 11},
        dose_rhos={
            "qwen25": {7: {"A": 0.5, "S": 1.5}, 20: {"A": 0.5, "S": 1.5}},
            "llama31": {7: {"A": 0.5, "S": 1.5}, 20: {"A": 0.5, "S": 1.5}},
        },
        core_direction_source_run="core",
    )
    assert len(e3) == EXTENSION_BUDGET["e3_steered"]
    assert {row["identity"]["direction_id"] for row in e3} == {"rogue:0", "rogue:1", "rogue:2", "rogue:3"}
    assert all(row["metadata"]["vector_source"].startswith("core:rogue:") for row in e3)


def test_extension_screen_schedules_keep_fixed_grid_and_layer_strata() -> None:
    frames = _frames()
    screen_prompts = _development_screen_prompts(frames)
    e2 = build_e2_screen_schedule(
        run_id="fixture", screen_prompts=screen_prompts, layer=9, source_run_id="core",
    )
    e3 = build_e3_screen_schedule(
        run_id="fixture", screen_prompts=screen_prompts,
        model_layer_counts={"qwen25": 28, "llama31": 28},
        core_layers={"qwen25": 9, "llama31": 11}, source_run_id="core",
    )
    assert len(e2) == 600
    assert len(e3) == 1_200
    assert {row["dose_label"] for row in e2 + e3} == {"screen"}
    assert {row["identity"]["rho"] for row in e2} == {0.5, 0.75, 1.0, 1.25, 1.5}
    assert {row["identity"]["layer"] for row in e3} == {7, 20}
    assert {row["identity"]["prompt_id"] for row in e2 + e3} <= {
        f"pair-{index}:harmful" for index in range(20)
    }
    assert {row["metadata"]["frame"] for row in e2 + e3} == {"development20"}


def test_screen_rows_group_by_model_family_and_optional_layer() -> None:
    schedule = [
        {"response_id": "r0", "identity": {"block": "E3_development", "model_id": "qwen25", "family": "rogue", "layer": 7, "rho": 0.5}},
        {"response_id": "r1", "identity": {"block": "E3_development", "model_id": "qwen25", "family": "rogue", "layer": 20, "rho": 1.5}},
    ]
    judges = [{"response_id": "r0", "four_class_label": "unsafe"}, {"response_id": "r1", "four_class_label": "safe"}]
    grouped = _screen_rows_from_artifacts(schedule, judges, include_layer=True)
    assert set(grouped) == {("qwen25", "rogue", 7), ("qwen25", "rogue", 20)}
    assert grouped[("qwen25", "rogue", 7)][0]["label"] == "unsafe"


def test_e1_prompt_mapping_and_missing_gemma_prerequisite_fail_closed() -> None:
    assert _prompt_map({"e1": {"records": [{"prompt_id": "hb:0", "text": "external request"}]}})["hb:0"] == "external request"
    config = __import__("paper1_broadening.config", fromlist=["default_config"]).default_config(Path(__file__).resolve().parents[2])
    result = extension_prerequisites({"e1": {"status": "NOT_RUN", "records": []}}, config)
    assert result["E2"]["status"] == "NOT_RUN"
    assert result["E2"]["reason"] == "MODEL_PATH_NOT_CONFIGURED"


def test_failed_screen_generation_does_not_start_judge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[2]
    config = validate_config(default_config(root))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    atomic_write_json(run_dir / "run_header.json", {"run_id": "run-failed-screen"}, overwrite=False)
    frames = _frames()
    atomic_write_json(run_dir / "frames.json", frames, overwrite=False)
    atomic_write_json(
        run_dir / "directions.json",
        {
            "models": {
                "qwen25": {"status": "COMPLETED", "mu_content": 1.0, "mu_content_token_count": 1},
                "llama31": {"status": "COMPLETED", "mu_content": 1.0, "mu_content_token_count": 1},
            }
        },
        overwrite=False,
    )
    calls: list[str] = []

    def fake_screen_child(*, run_dir: Path, config: dict[str, object], block: str, command: str) -> dict[str, object]:
        calls.append(command)
        return {"command": command, "returncode": 1, "success": False, "log": str(run_dir / "failed.log")}

    monkeypatch.setattr("paper1_broadening.pipeline._run_screen_child", fake_screen_child)
    result = run_real_screen(run_dir=run_dir, config=config, block="core")

    assert result["status"] == "SCREEN_GATE_BLOCKED"
    assert result["E1"]["status"] == "NOT_RUN"
    assert calls == ["generate"]
    process = read_json(run_dir / "screen_processes_core.json")
    assert process["judge"]["status"] == "NOT_RUN"
    assert read_json(run_dir / "screen_judge_runtime_status_core.json")["status"] == "RUNTIME_NOT_RUN"


def test_jsonl_tail_is_preserved_before_resume(tmp_path: Path) -> None:
    path = tmp_path / "attempts.jsonl"
    path.write_bytes(b'{"complete": true}\n{"broken":')
    recovery = recover_jsonl_tail(path)
    assert recovery["recovered"] is True
    assert read_jsonl(path) == [{"complete": True}]
    assert Path(recovery["tail_path"]).read_bytes() == b'{"broken":'


def test_fixture_e2e_runs_real_artifact_flow_and_stays_non_evidence(tmp_path: Path) -> None:
    result = fixture_e2e(repo_root=Path(__file__).resolve().parents[2], output_dir=tmp_path / "fixture-run")
    assert result["status"] == "NON_EVIDENCE"
    assert result["fixture"] is True
    assert result["schedule_count"] == 16
    run_dir = Path(result["run_dir"])
    assert (run_dir / "generation_ledger.jsonl").is_file()
    assert (run_dir / "judge_records.jsonl").is_file()
    assert Path(result["archive"]).is_file()
    assert result["archive_revision"] == 1


def test_run_source_snapshot_verification_fails_closed_on_worktree_change(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    config = validate_config(default_config(root))
    run_dir, _ = create_run(config=config, repo_root=root, output_dir=tmp_path / "run")
    assert verify_run_source_snapshot(run_dir=run_dir, repo_root=root)["verified"] is True
    source_file = root / "paper1_broadening" / "pipeline.py"
    snapshot_file = run_dir / "source_snapshot" / "paper1_broadening" / "pipeline.py"
    original = source_file.read_bytes()
    snapshot_file.write_bytes(original + b"\n")
    with pytest.raises(BroadeningError, match="source snapshot differs"):
        verify_run_source_snapshot(run_dir=run_dir, repo_root=root)
