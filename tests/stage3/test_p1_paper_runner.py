from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping
from unittest import mock

from stage3_pipeline import p1_measurement, real_backend, real_judge
from stage3_pipeline.records import validate_p1_record
from tests.stage3.test_p1_measurement import FakeTokenizer, PINNED_TEMPLATE


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs/stage3/qwen25_p1_measurement_paper_v1.json"
DEVELOPMENT_PATH = ROOT / "configs/stage3/qwen25_stage3_development_inputs_v1.json"


def fake_inspector(**kwargs: Any) -> tuple[dict[str, Any], FakeTokenizer]:
    template_sha256 = hashlib.sha256(PINNED_TEMPLATE.encode("utf-8")).hexdigest()
    return (
        {
            "model_role": kwargs["model_role"],
            "resolved_model_path": str(Path(kwargs["model_path"]).resolve()),
            "resolved_tokenizer_path": str(Path(kwargs["tokenizer_path"]).resolve()),
            "local_files_only": True,
            "hidden_size": 3584,
            "layer_count": 28,
            "dtype": kwargs["dtype"],
            "device": kwargs["device"],
            "trust_remote_code": kwargs["trust_remote_code"],
            "trust_remote_code_reason": kwargs["trust_remote_code_reason"],
            "chat_template_sha256": template_sha256,
        },
        FakeTokenizer(),
    )


class P1PaperRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = p1_measurement._prepare_paper(
            CONFIG_PATH,
            repo_root=ROOT,
            model_asset_inspector=fake_inspector,
        )

    def test_loads_approved_100_plus_100_in_exact_order(self) -> None:
        prompts = self.prepared["prompts"]
        harmful = json.loads(
            (
                ROOT
                / "data/stage3/p1_harmful_do_not_answer_v1/selected_p1_harmful_100.json"
            ).read_text(encoding="utf-8")
        )["records"]
        benign = json.loads(
            (
                ROOT
                / "data/stage3/benign_prompt_frames_v1/selected_p1_benign_100.json"
            ).read_text(encoding="utf-8")
        )["records"]

        self.assertEqual(len(prompts), 200)
        self.assertEqual([item["domain"] for item in prompts], ["harmful"] * 100 + ["benign"] * 100)
        self.assertEqual(
            [item["source_id"] for item in prompts[:100]],
            [item["source_id"] for item in harmful],
        )
        self.assertEqual(
            [item["identity_sha256"] for item in prompts[:100]],
            [item["record_identity_sha256"] for item in harmful],
        )
        self.assertEqual(
            [item["source_id"] for item in prompts[100:]],
            [item["source_id"] for item in benign],
        )
        self.assertEqual(
            [item["identity_sha256"] for item in prompts[100:]],
            [item["prompt_identity_sha256"] for item in benign],
        )
        self.assertEqual(len({item["identity_sha256"] for item in prompts}), 200)
        self.assertEqual(len({item["logical_id"] for item in prompts}), 200)

    def test_bad_count_duplicate_identity_and_wrong_domain_fail_before_weights(self) -> None:
        bad_frames = []
        missing = copy.deepcopy(self.prepared["prompts"][:-1])
        bad_frames.append((missing, "exactly 200"))
        duplicate = copy.deepcopy(self.prepared["prompts"])
        duplicate[1]["identity_sha256"] = duplicate[0]["identity_sha256"]
        bad_frames.append((duplicate, "identities must be unique"))
        wrong_domain = copy.deepcopy(self.prepared["prompts"])
        wrong_domain[0]["domain"] = "benign"
        bad_frames.append((wrong_domain, "preserve harmful"))

        for prompts, message in bad_frames:
            with self.subTest(message=message), tempfile.TemporaryDirectory(
                dir=ROOT / ".codex-temp"
            ) as temporary:
                weight_loader = mock.Mock()
                with self.assertRaisesRegex(p1_measurement.P1SmokeCoreError, message):
                    p1_measurement.run_paper(
                        CONFIG_PATH,
                        run_id="fake-invalid-frame",
                        repo_root=ROOT,
                        model_asset_inspector=fake_inspector,
                        frame_loader=lambda _config, _development, _root, p=prompts: (
                            p,
                            hashlib.sha256(PINNED_TEMPLATE.encode("utf-8")).hexdigest(),
                        ),
                        weight_loader=weight_loader,
                        output_directory_resolver=lambda _config, _run_id, t=temporary: Path(t)
                        / "run",
                    )
                weight_loader.assert_not_called()

    def test_fake_200_prompt_runner_lifecycle_outputs_and_no_generation_or_judge(self) -> None:
        events: list[str] = []
        forward_count = 0

        def weight_loader(_behavior: Mapping[str, Any]) -> Any:
            events.append("load")
            return SimpleNamespace(device="cpu")

        def input_builder(
            _extraction: Mapping[str, Any], *, device: Any, torch_module: Any
        ) -> dict[str, Any]:
            self.assertEqual(device, "cpu")
            self.assertIsNotNone(torch_module)
            return {}

        def measurement_runner(
            _model: Any,
            _inputs: Mapping[str, Any],
            extraction: Mapping[str, Any],
            **kwargs: Any,
        ) -> dict[str, Any]:
            nonlocal forward_count
            forward_count += 1
            self.assertEqual(
                (kwargs["layer"], kwargs["hook_site"], kwargs["batch_size"]),
                (9, "resid_pre", 1),
            )
            token_count = len(extraction["input_ids"])
            norms = [1.0] * token_count
            return {
                "layer": 9,
                "hook_site": "resid_pre",
                "batch_size": 1,
                "activation_token_count": token_count,
                "token_norms_float32": norms,
                "all_norm_sum": float(len(extraction["valid_token_positions"])),
                "content_norm_sum": float(len(extraction["content_token_positions"])),
                "forward_complete": True,
                "required_norms_finite": True,
            }

        def resource_releaser(**kwargs: Any) -> dict[str, Any]:
            self.assertEqual(kwargs["device"], "cuda:0")
            events.append("release")
            return {"model_reference_cleared": True}

        def materialize(raw: Mapping[str, Any]) -> dict[str, Any]:
            self.assertEqual(forward_count, 200)
            self.assertEqual(len(raw["prompt_measurements"]), 200)
            self.assertEqual(len(raw["p1_terminal_records"]), 200)
            self.assertEqual(events[-1], "release")
            events.append("materialize")
            return {"status": "FAKE_P1_RESULT", "run_mode": "paper"}

        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            output = Path(temporary) / "paper-run"
            with (
                mock.patch.object(
                    p1_measurement.p1_results,
                    "materialize_p1_results",
                    side_effect=materialize,
                ) as materializer,
                mock.patch.object(real_backend.RealBehaviorBackend, "__call__") as generation,
                mock.patch.object(real_judge.RealJudgeBackend, "from_pretrained") as judge_loader,
                mock.patch.object(real_judge.RealJudgeBackend, "__call__") as judge,
            ):
                result = p1_measurement.run_paper(
                    CONFIG_PATH,
                    run_id="fake-200",
                    repo_root=ROOT,
                    model_asset_inspector=fake_inspector,
                    weight_loader=weight_loader,
                    measurement_runner=measurement_runner,
                    input_builder=input_builder,
                    resource_releaser=resource_releaser,
                    output_directory_resolver=lambda _config, _run_id: output,
                )

            self.assertEqual(forward_count, 200)
            self.assertEqual(events.count("load"), 1)
            self.assertEqual(events, ["load", "release", "materialize"])
            materializer.assert_called_once()
            generation.assert_not_called()
            judge_loader.assert_not_called()
            judge.assert_not_called()
            self.assertEqual(result["prompt_measurement_count"], 200)
            self.assertEqual(result["terminal_record_count"], 200)
            self.assertEqual(result["harmful"], 100)
            self.assertEqual(result["benign"], 100)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"p1_measurement_raw.json", "p1_measurement_result.json"},
            )

            raw = p1_measurement.p1_results.load_raw_measurement(
                output / "p1_measurement_raw.json"
            )
            self.assertEqual(len(raw["prompt_measurements"]), 200)
            records = [validate_p1_record(item) for item in raw["p1_terminal_records"]]
            self.assertEqual([item["domain"] for item in records], ["harmful"] * 100 + ["benign"] * 100)
            self.assertTrue(all(item["run_mode"] == "paper" for item in records))
            self.assertEqual(len({item["logical_id"] for item in records}), 200)
            self.assertTrue(all(item["logical_id"].startswith("p1-paper:") for item in records))

    def test_existing_output_directory_is_rejected_before_weight_loading(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            inspector = mock.Mock(side_effect=fake_inspector)
            weight_loader = mock.Mock()
            with self.assertRaisesRegex(p1_measurement.P1SmokeCoreError, "refusing to overwrite"):
                p1_measurement.run_paper(
                    CONFIG_PATH,
                    run_id="existing",
                    repo_root=ROOT,
                    model_asset_inspector=inspector,
                    weight_loader=weight_loader,
                    output_directory_resolver=lambda _config, _run_id: output,
                )
            inspector.assert_not_called()
            weight_loader.assert_not_called()

    def test_paper_validate_only_never_loads_weights_or_forwards(self) -> None:
        with (
            mock.patch.object(p1_measurement, "load_behavior_model") as weight_loader,
            mock.patch.object(p1_measurement, "measure_resid_pre") as forward,
            mock.patch.object(
                p1_measurement.AutoModelForCausalLM, "from_pretrained"
            ) as transformers_weight_loader,
            mock.patch.object(real_backend.RealBehaviorBackend, "__call__") as generation,
            mock.patch.object(real_judge.RealJudgeBackend, "from_pretrained") as judge_loader,
            mock.patch.object(real_judge.RealJudgeBackend, "__call__") as judge,
        ):
            result = p1_measurement.validate_only(
                CONFIG_PATH,
                repo_root=ROOT,
                model_asset_inspector=fake_inspector,
            )

        self.assertEqual(result["status"], "P1_PAPER_RUNNER_VALIDATE_ONLY_PASS")
        self.assertEqual(result["paper_frame_count"], 200)
        self.assertEqual((result["harmful"], result["benign"]), (100, 100))
        self.assertTrue(result["identities_unique"])
        for field in (
            "model_weights_loaded",
            "forward_executed",
            "generation_run",
            "judge_run",
            "full_p1_run",
        ):
            self.assertFalse(result[field])
        weight_loader.assert_not_called()
        transformers_weight_loader.assert_not_called()
        forward.assert_not_called()
        generation.assert_not_called()
        judge_loader.assert_not_called()
        judge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
