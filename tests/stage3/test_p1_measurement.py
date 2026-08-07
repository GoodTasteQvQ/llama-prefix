from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

try:
    import torch
except ModuleNotFoundError as exc:
    if exc.name != "torch":
        raise
    torch = None

if torch is not None:
    from scripts.stage3_production import run_p1_measurement
    from stage3_pipeline import p1_measurement, real_backend, real_judge
    from stage3_pipeline.records import validate_p1_record


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs/stage3/qwen25_p1_measurement_development_v1.json"
DEVELOPMENT_PATH = ROOT / "configs/stage3/qwen25_stage3_development_inputs_v1.json"


def setUpModule() -> None:
    if torch is None:
        raise unittest.SkipTest("Torch is not installed in the current Python environment")


if torch is not None:
    PINNED_TEMPLATE = json.loads(
        (
            Path("/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct")
            / "tokenizer_config.json"
        ).read_text(encoding="utf-8")
    )["chat_template"]


    class FakeTokenizer:
        chat_template = PINNED_TEMPLATE
        all_special_ids = [1, 2]

        def apply_chat_template(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[Any],
            tokenize: bool,
            add_generation_prompt: bool,
        ) -> str:
            if tools != [] or tokenize is not False:
                raise AssertionError("T0 must use empty tools and text rendering")
            if messages != [{"role": "user", "content": messages[0]["content"]}]:
                raise AssertionError("T0 must contain exactly one user message")
            rendered = (
                "<|im_start|>system\n"
                + p1_measurement.DEFAULT_SYSTEM_CONTENT
                + "<|im_end|>\n<|im_start|>user\n"
                + messages[0]["content"]
                + "<|im_end|>\n"
            )
            if add_generation_prompt:
                rendered += "<|im_start|>assistant\n"
            return rendered

        def __call__(self, rendered: str, **kwargs: Any) -> dict[str, Any]:
            required = {
                "add_special_tokens": False,
                "return_attention_mask": True,
                "return_offsets_mapping": True,
                "return_special_tokens_mask": True,
            }
            if any(kwargs.get(key) != value for key, value in required.items()):
                raise AssertionError("required tokenizer metadata was not requested")
            input_ids: list[int] = []
            offsets: list[tuple[int, int]] = []
            special_mask: list[int] = []
            index = 0
            special = {"<|im_start|>": 1, "<|im_end|>": 2}
            while index < len(rendered):
                marker = next(
                    (value for value in special if rendered.startswith(value, index)), None
                )
                if marker is not None:
                    input_ids.append(special[marker])
                    offsets.append((index, index + len(marker)))
                    special_mask.append(1)
                    index += len(marker)
                else:
                    input_ids.append(1000 + ord(rendered[index]))
                    offsets.append((index, index + 1))
                    special_mask.append(0)
                    index += 1
            return {
                "input_ids": input_ids,
                "attention_mask": [1] * len(input_ids),
                "special_tokens_mask": special_mask,
                "offset_mapping": offsets,
            }


    class BoundaryOffsetTokenizer(FakeTokenizer):
        def __call__(self, rendered: str, **kwargs: Any) -> dict[str, Any]:
            encoded = super().__call__(rendered, **kwargs)
            system_start = rendered.index(p1_measurement.DEFAULT_SYSTEM_CONTENT)
            boundary_index = encoded["offset_mapping"].index((system_start - 1, system_start))
            encoded["offset_mapping"][boundary_index] = (system_start - 1, system_start + 1)
            return encoded


    class AddLayer(torch.nn.Module):
        def __init__(self, amount: float = 0.0) -> None:
            super().__init__()
            self.amount = amount

        def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
            return hidden_states + self.amount


    class FakeTransformer(torch.nn.Module):
        def __init__(self, activation: torch.Tensor, *, fail_after_layer_9: bool = False) -> None:
            super().__init__()
            layers = [AddLayer() for _ in range(10)]
            layers[9] = AddLayer(100.0)
            self.model = torch.nn.Module()
            self.model.layers = torch.nn.ModuleList(layers)
            self.activation = activation
            self.fail_after_layer_9 = fail_after_layer_9
            self.device = torch.device("cpu")

        def forward(
            self, input_ids: torch.Tensor, attention_mask: torch.Tensor
        ) -> torch.Tensor:
            del attention_mask
            hidden = self.activation[:, : input_ids.shape[1], :]
            for index, layer in enumerate(self.model.layers):
                hidden = layer(hidden)
                if index == 9 and self.fail_after_layer_9:
                    raise RuntimeError("fake forward failure")
            return hidden


def extraction_for(
    token_count: int,
    *,
    valid_positions: list[int] | None = None,
    content_positions: list[int] | None = None,
    unresolved_positions: list[int] | None = None,
) -> dict[str, Any]:
    valid = list(range(token_count)) if valid_positions is None else valid_positions
    content = valid if content_positions is None else content_positions
    unresolved = [] if unresolved_positions is None else unresolved_positions
    return {
        "input_ids": list(range(10, 10 + token_count)),
        "attention_mask": [1] * token_count,
        "valid_token_positions": valid,
        "content_token_positions": content,
        "unresolved_valid_token_positions": unresolved,
        "valid_token_count": len(valid),
        "content_token_count": len(content),
        "unresolved_valid_token_count": len(unresolved),
        "render_complete": True,
        "valid_mask_complete": True,
        "complete_case": not unresolved and bool(valid) and bool(content),
    }


def inputs_for(extraction: Mapping[str, Any]) -> dict[str, Any]:
    assert torch is not None
    return {
        "input_ids": torch.tensor([extraction["input_ids"]], dtype=torch.long),
        "attention_mask": torch.tensor(
            [extraction["attention_mask"]], dtype=torch.long
        ),
    }


def smoke_prompt(domain: str = "harmful") -> dict[str, Any]:
    expected = p1_measurement.EXPECTED_PROMPTS[0 if domain == "harmful" else 1]
    return dict(expected)


class P1MeasurementSmokeCoreTests(unittest.TestCase):
    def test_t0_renders_default_system_user_and_assistant_preamble(self) -> None:
        extraction = p1_measurement.render_and_extract_t0(FakeTokenizer(), "User text")
        self.assertEqual(extraction["messages"], [{"role": "user", "content": "User text"}])
        self.assertEqual(extraction["tools"], [])
        self.assertTrue(extraction["add_generation_prompt"])
        rendered = extraction["rendered_text"]
        self.assertIn(
            "system\n" + p1_measurement.DEFAULT_SYSTEM_CONTENT + "<|im_end|>", rendered
        )
        self.assertIn("user\nUser text<|im_end|>", rendered)
        self.assertTrue(rendered.endswith("<|im_start|>assistant\n"))
        assistant_span = extraction["assistant_preamble_span"]
        self.assertEqual(rendered[slice(*assistant_span)], "<|im_start|>assistant\n")

    def test_offset_classification_is_mutually_exclusive_and_fail_closed(self) -> None:
        extraction = p1_measurement.render_and_extract_t0(
            BoundaryOffsetTokenizer(), "Classify me"
        )
        classes = extraction["token_classification"]
        for expected in (
            p1_measurement.SPECIAL_CONTROL,
            p1_measurement.SYSTEM_CONTENT,
            p1_measurement.USER_CONTENT,
            p1_measurement.ASSISTANT_PREAMBLE,
            p1_measurement.TEMPLATE_WHITESPACE,
            p1_measurement.ROLE_TEMPLATE_DELIMITER,
            p1_measurement.UNRESOLVED,
        ):
            self.assertIn(expected, classes)
        for index, classification in enumerate(classes):
            in_valid = extraction["valid_token_membership"][index]
            in_content = extraction["content_token_membership"][index]
            if classification == p1_measurement.SPECIAL_CONTROL:
                self.assertFalse(in_valid)
            if classification in {
                p1_measurement.SYSTEM_CONTENT,
                p1_measurement.USER_CONTENT,
            }:
                self.assertTrue(in_valid)
                self.assertTrue(in_content)
            elif classification == p1_measurement.UNRESOLVED:
                self.assertTrue(in_valid)
                self.assertFalse(in_content)
        self.assertEqual(extraction["unresolved_valid_token_count"], 1)
        self.assertFalse(extraction["complete_case"])

    def test_layer_9_forward_pre_hook_captures_input_and_is_always_removed(self) -> None:
        extraction = extraction_for(3)
        activation = torch.tensor([[[3.0, 4.0], [0.0, 2.0], [8.0, 15.0]]])
        model = FakeTransformer(activation)
        measurement = p1_measurement.measure_resid_pre(
            model, inputs_for(extraction), extraction
        )
        self.assertEqual(measurement["token_norms_float32"], [5.0, 2.0, 17.0])
        self.assertEqual(len(model.model.layers[9]._forward_pre_hooks), 0)

        failing = FakeTransformer(activation, fail_after_layer_9=True)
        with self.assertRaisesRegex(RuntimeError, "fake forward failure"):
            p1_measurement.measure_resid_pre(
                failing, inputs_for(extraction), extraction
            )
        self.assertEqual(len(failing.model.layers[9]._forward_pre_hooks), 0)

    def test_length_nonfinite_and_unresolved_cases_fail_closed(self) -> None:
        extraction = extraction_for(3)
        short_model = FakeTransformer(torch.ones((1, 2, 2)))
        short = p1_measurement.measure_resid_pre(
            short_model, inputs_for(extraction), extraction
        )
        self.assertFalse(short["forward_complete"])
        self.assertEqual(short["failure_code"], "ACTIVATION_TOKEN_LENGTH_MISMATCH")
        short_record = p1_measurement.build_p1_terminal_record(
            smoke_prompt(), extraction, short
        )
        self.assertEqual(short_record["terminal_status"], "EXCLUDED_FORWARD")

        nonfinite_model = FakeTransformer(
            torch.tensor([[[3.0, 4.0], [float("nan"), 0.0], [8.0, 15.0]]])
        )
        nonfinite = p1_measurement.measure_resid_pre(
            nonfinite_model, inputs_for(extraction), extraction
        )
        self.assertTrue(nonfinite["forward_complete"])
        self.assertFalse(nonfinite["required_norms_finite"])
        nonfinite_record = p1_measurement.build_p1_terminal_record(
            smoke_prompt(), extraction, nonfinite
        )
        self.assertEqual(nonfinite_record["terminal_status"], "EXCLUDED_NONFINITE")

        unresolved = extraction_for(3, content_positions=[1], unresolved_positions=[0])
        finite = p1_measurement.measure_resid_pre(
            FakeTransformer(torch.ones((1, 3, 2))),
            inputs_for(unresolved),
            unresolved,
        )
        unresolved_record = p1_measurement.build_p1_terminal_record(
            smoke_prompt(), unresolved, finite
        )
        self.assertFalse(unresolved_record["complete_case"])
        self.assertEqual(unresolved_record["terminal_status"], "EXCLUDED_UNRESOLVED")

    def test_manual_norm_sums_and_existing_p1_validator(self) -> None:
        extraction = extraction_for(
            3, valid_positions=[0, 1, 2], content_positions=[0, 2]
        )
        activation = torch.tensor([[[3.0, 4.0], [0.0, 2.0], [8.0, 15.0]]])
        measurement = p1_measurement.measure_resid_pre(
            FakeTransformer(activation), inputs_for(extraction), extraction
        )
        self.assertEqual(measurement["all_norm_sum"], 24.0)
        self.assertEqual(measurement["content_norm_sum"], 22.0)
        self.assertEqual(extraction["valid_token_count"], 3)
        self.assertEqual(extraction["content_token_count"], 2)
        record = p1_measurement.build_p1_terminal_record(
            smoke_prompt(), extraction, measurement
        )
        self.assertTrue(record["complete_case"])
        self.assertEqual(validate_p1_record(record), record)

    def test_validate_only_forbids_execution_and_smoke_bounds_and_overwrite(self) -> None:
        development = json.loads(DEVELOPMENT_PATH.read_text(encoding="utf-8"))
        template_sha256 = hashlib.sha256(PINNED_TEMPLATE.encode("utf-8")).hexdigest()

        def fake_inspector(**kwargs: Any) -> tuple[dict[str, Any], FakeTokenizer]:
            role = kwargs["model_role"]
            return (
                {
                    "model_role": role,
                    "resolved_model_path": str(Path(kwargs["model_path"]).resolve()),
                    "resolved_tokenizer_path": str(
                        Path(kwargs["tokenizer_path"]).resolve()
                    ),
                    "local_files_only": True,
                    "hidden_size": 3584 if role == "behavior" else 4096,
                    "layer_count": 28 if role == "behavior" else 36,
                    "model_revision": f"fake-{role}",
                    "chat_template_sha256": template_sha256,
                },
                FakeTokenizer(),
            )

        def fake_development_validator(
            path: Path, *, repo_root: Path, model_asset_inspector: Any
        ) -> dict[str, Any]:
            self.assertEqual(path.resolve(), DEVELOPMENT_PATH.resolve())
            self.assertEqual(repo_root, ROOT)
            for role in ("behavior", "judge"):
                value = development[role]
                model_asset_inspector(
                    model_path=value["checkpoint_path"],
                    tokenizer_path=value["tokenizer_path"],
                    model_role=role,
                    dtype=value["dtype"],
                    device=value["device"],
                    trust_remote_code=value["trust_remote_code"],
                    trust_remote_code_reason=value["trust_remote_code_reason"],
                )
            return {"status": "STAGE3_DEVELOPMENT_INPUTS_VALIDATE_ONLY_PASS"}

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
                model_asset_inspector=fake_inspector,
                development_validator=fake_development_validator,
            )
        self.assertEqual(result["status"], "P1_SMOKE_CORE_VALIDATE_ONLY_PASS")
        for field in (
            "model_weights_loaded",
            "forward_executed",
            "generation_run",
            "judge_run",
            "p1_run",
            "formal_experiment_run",
        ):
            self.assertFalse(result[field])
        weight_loader.assert_not_called()
        transformers_weight_loader.assert_not_called()
        forward.assert_not_called()
        generation.assert_not_called()
        judge_loader.assert_not_called()
        judge.assert_not_called()

        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        config["prompts"] = config["prompts"][:1]
        with self.assertRaisesRegex(
            p1_measurement.P1SmokeCoreError, "exactly 1 harmful"
        ):
            p1_measurement.validate_smoke_config(config)

        with tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp") as temporary:
            temporary_root = Path(temporary)
            existing = temporary_root / p1_measurement.EXPECTED_OUTPUT_ROOT
            existing.mkdir(parents=True)
            forbidden_loader = mock.Mock()
            with self.assertRaisesRegex(
                p1_measurement.P1SmokeCoreError, "refusing to overwrite"
            ):
                p1_measurement.run_smoke(
                    CONFIG_PATH,
                    repo_root=temporary_root,
                    weight_loader=forbidden_loader,
                )
            forbidden_loader.assert_not_called()

        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            status = run_p1_measurement.main(["--run-mode", "paper"])
        self.assertEqual(status, 1)
        self.assertIn("only --validate-only or --run-mode smoke", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
