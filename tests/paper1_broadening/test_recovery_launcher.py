from __future__ import annotations

import json
from pathlib import Path

from scripts import core_judge_recovery_run as launcher


def test_launcher_import_has_no_torch_or_transformers_side_effect():
    assert "torch" not in launcher.__dict__
    assert "transformers" not in launcher.__dict__
    assert launcher.APPROVAL_PATH.name == "CORE_JUDGE_PROTOCOL_V3_RECOVERY_APPROVAL.md"


def test_launcher_without_canonical_approval_is_blocked_before_backend(tmp_path: Path):
    run_dir = tmp_path / "new-recovery-run"
    result = launcher.run(run_dir=run_dir)
    assert result == 3
    status = json.loads((run_dir / "launcher_status.json").read_text())
    assert status["status"] == "RECOVERY_APPROVAL_BLOCKED"
    assert status["actual_judge_requests"] == 0
    assert status["models_loaded"] == 0


def test_launcher_rejects_existing_run_directory(tmp_path: Path):
    run_dir = tmp_path / "existing"
    run_dir.mkdir()
    (run_dir / "sentinel").write_text("fixture")
    result = launcher.main(["--run-dir", str(run_dir)])
    assert result == 3
    assert (run_dir / "sentinel").read_text() == "fixture"
