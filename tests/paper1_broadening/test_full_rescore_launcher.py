from __future__ import annotations

import json
from pathlib import Path

from scripts import core_judge_full_rescore_run as launcher


def test_launcher_import_has_no_model_stack_side_effect():
    assert "torch" not in launcher.__dict__
    assert "transformers" not in launcher.__dict__


def test_default_real_mode_is_blocked(tmp_path: Path):
    assert launcher.main(["--run-dir", str(tmp_path / "run")]) == 3


def test_preflight_does_not_load_or_call_judge(tmp_path: Path):
    run = tmp_path / "preflight"
    assert launcher.main(["--run-dir", str(run), "--preflight"]) == 0
    value = json.loads((run / "launcher_status.json").read_text())
    assert value["models_loaded"] == value["actual_judge_requests"] == 0
    assert value["input_protection"]["binding"]["status"] == "FULL_RESCORE_BINDING_PASS"
    assert value["input_protection"]["protected_hashes"] == 21
