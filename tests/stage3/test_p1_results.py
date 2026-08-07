from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stage3_pipeline.core import PROTOCOL_VERSION, canonical_sha256
from stage3_pipeline.dose import P1DoseNonEstimable, validate_dose_binding
from stage3_pipeline import p1_results


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts/stage3_production/materialize_p1_results.py"
SMOKE_RAW = ROOT / ".codex-temp/stage3_p1_smoke_runs/p1_smoke_core.json"


def _identity(domain: str, prompt_id: str) -> str:
    return hashlib.sha256(f"{domain}:{prompt_id}".encode("ascii")).hexdigest()


def _terminal_record(
    *,
    domain: str,
    prompt_id: str,
    identity_sha256: str,
    valid_positions: list[int],
    content_positions: list[int],
    unresolved: int,
    norms: list[float],
    run_mode: str,
) -> dict[str, object]:
    valid_count = len(valid_positions)
    content_count = len(content_positions)
    complete = unresolved == 0 and valid_count > 0 and content_count > 0
    terminal_status = "COMPLETE_CASE" if complete else (
        "EXCLUDED_UNRESOLVED" if unresolved else "EXCLUDED_ZERO_DENOMINATOR"
    )
    record: dict[str, object] = {
        "schema_version": "paper1-stage3-p1-measurement-record-v3",
        "protocol_version": PROTOCOL_VERSION,
        "run_mode": run_mode,
        "paper_result_eligible": False,
        "logical_id": f"p1-{run_mode}:{domain}:{prompt_id}",
        "identity_sha256": identity_sha256,
        "prompt_id": prompt_id,
        "domain": domain,
        "identity_complete": True,
        "render_complete": True,
        "valid_mask_complete": True,
        "forward_complete": True,
        "identity_collision": False,
        "valid_token_count": valid_count,
        "content_token_count": content_count,
        "unresolved_valid_token_count": unresolved,
        "required_norms_finite": True,
        "all_norm_sum": math.fsum(norms[position] for position in valid_positions),
        "content_norm_sum": math.fsum(norms[position] for position in content_positions),
        "complete_case": complete,
        "terminal_status": terminal_status,
        "exclusion_reason": None if complete else terminal_status,
    }
    record["record_sha256"] = canonical_sha256(record)
    return record


def _measurement(
    domain: str,
    prompt_id: str,
    norms: list[float],
    *,
    valid_positions: list[int] | None = None,
    content_positions: list[int] | None = None,
    unresolved: int = 0,
    run_mode: str = "paper",
) -> tuple[dict[str, object], dict[str, object]]:
    valid = list(range(len(norms))) if valid_positions is None else valid_positions
    content = valid if content_positions is None else content_positions
    identity_sha256 = _identity(domain, prompt_id)
    extraction = {
        "domain": domain,
        "prompt_identity_sha256": identity_sha256,
        "prompt_id": prompt_id,
        "valid_token_positions": valid,
        "content_token_positions": content,
        "unresolved_valid_token_positions": valid[:unresolved],
        "valid_token_count": len(valid),
        "content_token_count": len(content),
        "unresolved_valid_token_count": unresolved,
        "render_complete": True,
        "valid_mask_complete": True,
    }
    detail: dict[str, object] = {
        "prompt": {
            "domain": domain,
            "prompt_id": prompt_id,
            "identity_sha256": identity_sha256,
        },
        "extraction": extraction,
        "measurement": {
            "activation_token_count": len(norms),
            "token_norms_float32": norms,
            "forward_complete": True,
            "required_norms_finite": True,
            "all_norm_sum": math.fsum(norms[position] for position in valid),
            "content_norm_sum": math.fsum(norms[position] for position in content),
        },
    }
    terminal = _terminal_record(
        domain=domain,
        prompt_id=prompt_id,
        identity_sha256=identity_sha256,
        valid_positions=valid,
        content_positions=content,
        unresolved=unresolved,
        norms=norms,
        run_mode=run_mode,
    )
    return detail, terminal


def _raw(
    rows: list[tuple[str, str, list[float], list[int], list[int]]],
    *,
    run_mode: str = "paper",
) -> dict[str, object]:
    details: list[dict[str, object]] = []
    terminals: list[dict[str, object]] = []
    for domain, prompt_id, norms, valid, content in rows:
        detail, terminal = _measurement(
            domain,
            prompt_id,
            norms,
            valid_positions=valid,
            content_positions=content,
            run_mode=run_mode,
        )
        details.append(detail)
        terminals.append(terminal)
    return {
        "run_mode": run_mode,
        "prompt_measurements": details,
        "p1_terminal_records": terminals,
    }


def _four_prompt_raw() -> dict[str, object]:
    return _raw(
        [
            ("harmful", "h1", [1.0, 2.0], [0, 1], [1]),
            ("harmful", "h2", [3.0, 5.0], [0, 1], [0]),
            ("benign", "b1", [4.0, 8.0], [0, 1], [1]),
            ("benign", "b2", [6.0, 10.0], [0, 1], [0]),
        ]
    )


class P1ResultMaterializationTests(unittest.TestCase):
    def test_recomputes_pooled_statistics_and_pooled_content_token_median(self) -> None:
        raw = _four_prompt_raw()
        for detail, record in zip(
            raw["prompt_measurements"], raw["p1_terminal_records"], strict=True
        ):
            detail["measurement"]["all_norm_sum"] = 999999.0
            detail["measurement"]["content_norm_sum"] = 888888.0
            record["all_norm_sum"] = 777777.0
            record["content_norm_sum"] = 666666.0
            record["record_sha256"] = canonical_sha256(
                {key: value for key, value in record.items() if key != "record_sha256"}
            )

        frame = p1_results.build_complete_case_frame(raw)
        original = p1_results.reference_statistics.p1_interval
        with mock.patch.object(
            p1_results.reference_statistics, "p1_interval", wraps=original
        ) as interval:
            result = p1_results.compute_p1_statistics(
                frame, replicates=100, min_success=95
            )
        interval.assert_called_once_with(frame["strata"], replicates=100, min_success=95)

        pooled = result["pooled_statistics"]
        self.assertEqual(
            pooled["pooled_sums_and_counts"],
            {
                "all_norm_sum": 39.0,
                "content_norm_sum": 19.0,
                "valid_token_count": 8,
                "content_token_count": 4,
            },
        )
        self.assertEqual(pooled["mu_all_tw_Qwen"], 39.0 / 8.0)
        self.assertEqual(pooled["mu_content_tw_Qwen"], 19.0 / 4.0)
        self.assertEqual(pooled["delta_select_tw"], (39.0 / 8.0 - 19.0 / 4.0) / (19.0 / 4.0))
        self.assertEqual(pooled["ratio_select_tw"], (39.0 / 8.0) / (19.0 / 4.0))
        self.assertEqual(result["median_content_norm_Qwen"], 4.5)
        self.assertEqual(frame["complete_case_prompt_ids"], {
            "harmful": ["h1", "h2"], "benign": ["b1", "b2"]
        })

    def test_current_one_plus_one_smoke_is_nonestimable_without_dose(self) -> None:
        self.assertTrue(SMOKE_RAW.is_file())
        result = p1_results.materialize_p1_results(
            p1_results.load_raw_measurement(SMOKE_RAW)
        )
        self.assertEqual(result["status"], "P1_RESULT_NON_ESTIMABLE")
        self.assertEqual(result["reason"], "P1_DEVELOPMENT_DIAGNOSTIC_INPUT")
        self.assertEqual(result["scheduled_counts"], {
            "harmful": 1, "benign": 1, "total": 2
        })
        self.assertIsNone(result["dose_binding"])
        self.assertFalse(result["formal_experiment_run"])
        self.assertFalse(result["paper_result_eligible"])

    def test_unresolved_is_preserved_as_terminal_exclusion(self) -> None:
        harmful, harmful_terminal = _measurement(
            "harmful",
            "h1",
            [1.0, 2.0],
            content_positions=[1],
            unresolved=1,
            run_mode="smoke",
        )
        benign, benign_terminal = _measurement(
            "benign", "b1", [3.0, 4.0], run_mode="smoke"
        )
        result = p1_results.materialize_p1_results(
            {
                "run_mode": "smoke",
                "prompt_measurements": [harmful, benign],
                "p1_terminal_records": [harmful_terminal, benign_terminal],
            }
        )
        self.assertEqual(result["status"], "P1_RESULT_NON_ESTIMABLE")
        self.assertEqual(result["complete_counts"]["harmful"], 0)
        self.assertEqual(result["exclusion_reasons"][0]["reason"], "EXCLUDED_UNRESOLVED")
        self.assertIsNone(result["dose_binding"])

    def test_nonfinite_norm_wrong_token_count_and_illegal_record_are_input_invalid(self) -> None:
        nonfinite = _four_prompt_raw()
        nonfinite["prompt_measurements"][0]["measurement"]["token_norms_float32"][0] = math.inf
        with self.assertRaisesRegex(
            p1_results.P1ResultInputInvalid, "NONFINITE_OR_NEGATIVE"
        ):
            p1_results.build_complete_case_frame(nonfinite)

        wrong_count = _four_prompt_raw()
        wrong_count["prompt_measurements"][0]["measurement"]["activation_token_count"] = 3
        with self.assertRaisesRegex(p1_results.P1ResultInputInvalid, "TOKEN_COUNT_MISMATCH"):
            p1_results.build_complete_case_frame(wrong_count)

        illegal = _four_prompt_raw()
        illegal["p1_terminal_records"][0]["terminal_status"] = "EXCLUDED_FORWARD"
        with self.assertRaisesRegex(p1_results.P1ResultInputInvalid, "p1_terminal_records"):
            p1_results.build_complete_case_frame(illegal)

    def test_duplicate_prompt_identity_is_nonestimable(self) -> None:
        raw = _raw(
            [
                ("harmful", "h1", [1.0, 2.0], [0, 1], [1]),
                ("benign", "b1", [3.0, 4.0], [0, 1], [1]),
            ],
            run_mode="smoke",
        )
        duplicate = raw["prompt_measurements"][0]["prompt"]["identity_sha256"]
        raw["prompt_measurements"][1]["prompt"]["identity_sha256"] = duplicate
        raw["prompt_measurements"][1]["extraction"]["prompt_identity_sha256"] = duplicate
        raw["p1_terminal_records"][1]["identity_sha256"] = duplicate
        raw["p1_terminal_records"][1]["record_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in raw["p1_terminal_records"][1].items()
                if key != "record_sha256"
            }
        )
        result = p1_results.materialize_p1_results(raw)
        self.assertEqual(result["status"], "P1_RESULT_NON_ESTIMABLE")
        self.assertEqual(result["reason"], "P1_PROMPT_IDENTITY_NOT_UNIQUE")
        self.assertIsNone(result["dose_binding"])

    def test_exact_rho_formula_post_dtype_binding_and_validator(self) -> None:
        frame = p1_results.build_complete_case_frame(_four_prompt_raw())
        statistics_result = p1_results.compute_p1_statistics(
            frame, replicates=100, min_success=95
        )
        pooled = statistics_result["pooled_statistics"]
        median = statistics_result["median_content_norm_Qwen"]
        binding = p1_results.build_measurement_dose_binding(pooled, median)
        validated = validate_dose_binding(binding)

        self.assertEqual([entry["anchor"] for entry in binding["anchors"]], ["A", "T", "H"])
        for entry in binding["anchors"]:
            anchor = entry["anchor"]
            rho = p1_results.EXPECTED_RHO[anchor]
            expected_c = rho * median / pooled["mu_all_tw_Qwen"]
            self.assertEqual(entry["rho"]["value"], rho)
            self.assertEqual(entry["rho"]["binary64_hex"], rho.hex())
            self.assertEqual(entry["c"]["value"].hex(), expected_c.hex())
            for estimator in ("mu_all_tw", "mu_content_tw"):
                alpha = entry["alpha_by_estimator"][estimator]
                self.assertEqual(
                    alpha["pre_dtype"]["value"].hex(),
                    (expected_c * binding[estimator]["value"]).hex(),
                )
                self.assertEqual(
                    validated[anchor][estimator]["alpha_post_dtype_hex"],
                    alpha["post_dtype"]["value"].hex(),
                )

    def test_nonfinite_or_missing_statistics_never_build_dose(self) -> None:
        for statistics_value in (
            {"mu_all_tw_Qwen": math.inf, "mu_content_tw_Qwen": 1.0},
            {"mu_all_tw_Qwen": 1.0},
        ):
            with self.subTest(statistics_value=statistics_value):
                with self.assertRaises(P1DoseNonEstimable):
                    p1_results.build_measurement_dose_binding(statistics_value, 2.0)

    def test_existing_output_is_rejected_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            directory = Path(temporary)
            raw_path = directory / "raw.json"
            output_path = directory / "result.json"
            raw_path.write_text(json.dumps(_four_prompt_raw()), encoding="utf-8")
            output_path.write_text("owner-data\n", encoding="utf-8")
            environment = dict(os.environ)
            environment.update(
                {
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                    "HF_DATASETS_OFFLINE": "1",
                }
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--input",
                    str(raw_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("P1_RESULT_INPUT_INVALID", completed.stderr)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "owner-data\n")

    def test_module_has_no_model_forward_generation_judge_or_network_calls(self) -> None:
        tree = ast.parse(
            (ROOT / "stage3_pipeline/p1_results.py").read_text(encoding="utf-8")
        )
        called_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called_names.add(node.func.attr)
        forbidden = {
            "from_pretrained",
            "load_behavior_model",
            "measure_resid_pre",
            "forward",
            "generate",
            "judge",
            "urlopen",
        }
        self.assertTrue(forbidden.isdisjoint(called_names), forbidden & called_names)
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue({"requests", "urllib", "socket", "httpx"}.isdisjoint(imported_roots))


if __name__ == "__main__":
    unittest.main()
