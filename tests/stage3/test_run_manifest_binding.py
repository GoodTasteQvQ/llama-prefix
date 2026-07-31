from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path

from stage3_pipeline.core import DECODE_CONFIG, offline_execution_guard
from stage3_pipeline.execution import reconcile_execution
from stage3_pipeline.run_manifest import (
    RunManifestError,
    build_run_manifest,
    validate_run_manifest,
    write_run_manifest,
)
from tests.stage3.helpers import P1_INPUT, ROOT, test_dose_binding
from tests.stage3.test_execution_reconciliation import paper_registry, unattempted_dispositions


class RunManifestBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.update({
            "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "TEMP": str(ROOT / ".codex-temp"), "TMP": str(ROOT / ".codex-temp"),
        })

    def _paper_facts(self):
        registry = paper_registry()
        return reconcile_execution(
            registry, run_mode="paper", generation_records=[], judge_records=[],
            response_records=[], dispositions=unattempted_dispositions(
                registry,
                support_status={"A": "NON_ESTIMABLE_IDENTITY", "T": "NON_ESTIMABLE_IDENTITY"},
            ),
            dose_binding=test_dose_binding(),
        )

    def test_successful_paper_manifest_binds_complete_5580_partition(self) -> None:
        reconciliation = self._paper_facts()
        guard = offline_execution_guard()
        with guard:
            pass
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            manifest = build_run_manifest(
                repo_root=ROOT, run_mode="paper", command=["python", "paper.py"],
                started_at_utc="2026-07-30T00:00:00Z",
                completed_at_utc="2026-07-30T00:00:01Z",
                model_path_or_id="local-model", tokenizer_path_or_id="local-tokenizer",
                input_paths=[P1_INPUT], generation_config=DECODE_CONFIG, seed=42,
                gpu_identity="fake-gpu", output_directory=Path(temporary) / "paper",
                exit_status="success", exit_code=0, fake_backend=False,
                reconciliation=reconciliation, offline_guard=guard,
                runtime_versions={"python": "test", "torch": None, "transformers": None, "cuda": None},
            )
        validated = validate_run_manifest(manifest)
        self.assertEqual(validated["reconciliation"]["scheduled_logical_ids"], 5_580)
        self.assertEqual(validated["reconciliation"]["terminal_partition"]["UNATTEMPTED_DUE_INTEGRITY_BLOCK"], 5_580)
        self.assertFalse(validated["paper_result_eligible"])

    def test_caller_counts_and_unverified_reconciliation_cannot_bypass(self) -> None:
        reconciliation = self._paper_facts()
        guard = offline_execution_guard()
        with guard:
            pass
        kwargs = {
            "repo_root": ROOT, "run_mode": "paper", "command": ["python", "paper.py"],
            "started_at_utc": "2026-07-30T00:00:00Z",
            "completed_at_utc": "2026-07-30T00:00:01Z",
            "model_path_or_id": "local-model", "tokenizer_path_or_id": "local-tokenizer",
            "input_paths": [P1_INPUT], "generation_config": DECODE_CONFIG, "seed": 42,
            "gpu_identity": None, "output_directory": ROOT / ".codex-temp/manifest-negative",
            "exit_status": "success", "exit_code": 0, "fake_backend": False,
            "reconciliation": reconciliation, "offline_guard": guard,
            "runtime_versions": {"python": "test", "torch": None, "transformers": None, "cuda": None},
        }
        bad_claim = {field: reconciliation[field] for field in (
            "scheduled_logical_ids", "generation_first_pass_scheduled",
            "generation_first_pass_calls", "generation_completed", "generation_retry_calls",
            "generation_total_calls", "judge_first_pass_scheduled", "judge_eligible",
            "judge_first_pass_calls", "judge_parsed", "judge_retry_calls", "judge_total_calls",
            "completed_item_count", "failure_count", "unattempted_count",
            "k1_additional_generation_calls", "k1_additional_judge_calls",
        )}
        bad_claim["completed_item_count"] = 5_580
        with self.assertRaises(RunManifestError):
            build_run_manifest(**kwargs, claimed_counts=bad_claim)
        forged = reconciliation.as_dict()
        with self.assertRaises(RunManifestError):
            build_run_manifest(**{**kwargs, "reconciliation": forged})
        exposed_partition = reconciliation["terminal_partition"]
        exposed_partition["UNATTEMPTED_DUE_INTEGRITY_BLOCK"] = 0
        self.assertEqual(
            reconciliation["terminal_partition"]["UNATTEMPTED_DUE_INTEGRITY_BLOCK"],
            5_580,
        )

        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            manifest = build_run_manifest(**{
                **kwargs,
                "output_directory": Path(temporary) / "paper",
            })
            alternate = Path(temporary) / "forged-builder-target"
            with self.assertRaises(RunManifestError):
                write_run_manifest(alternate, manifest)
            self.assertFalse(alternate.exists())
            raw = manifest.as_dict()
            with self.assertRaises(RunManifestError):
                write_run_manifest(Path(temporary) / "forged", raw)
            self.assertFalse((Path(temporary) / "forged" / "run_manifest.json").exists())

    def test_manifest_offline_counts_are_closed_guard_facts(self) -> None:
        reconciliation = self._paper_facts()
        active_guard = offline_execution_guard()
        active_guard.__enter__()
        try:
            with self.assertRaises(Exception):
                _ = active_guard.report
        finally:
            active_guard.__exit__(None, None, None)
        guard = offline_execution_guard()
        with guard:
            pass
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            manifest = build_run_manifest(
                repo_root=ROOT, run_mode="paper", command=["python", "paper.py"],
                started_at_utc="2026-07-30T00:00:00Z", completed_at_utc="2026-07-30T00:00:01Z",
                model_path_or_id="local-model", tokenizer_path_or_id="local-tokenizer",
                input_paths=[P1_INPUT], generation_config=DECODE_CONFIG, seed=42,
                gpu_identity=None, output_directory=Path(temporary), exit_status="success",
                exit_code=0, fake_backend=False, reconciliation=reconciliation,
                offline_guard=guard,
                runtime_versions={"python": "test", "torch": None, "transformers": None, "cuda": None},
            )
        forged = copy.deepcopy(manifest.as_dict())
        forged["offline_guard_report"]["category_counts"]["network"] = 1
        with self.assertRaises(RunManifestError):
            validate_run_manifest(forged)


if __name__ == "__main__":
    unittest.main()
