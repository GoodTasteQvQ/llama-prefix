from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

try:
    import torch
except ModuleNotFoundError as exc:
    if exc.name != "torch":
        raise
    torch = None
else:
    from stage3_pipeline.vector_pool import VectorPoolError, load_stage3_vector_pool

from stage3_pipeline.core import PipelineError


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs/stage3/qwen25_stage3_development_inputs_v1.json"
MANIFEST_RELATIVE_PATH = Path(
    "data/stage3/qwen25_vector_pool_v1/qwen25_stage3_vectors.manifest.json"
)
TENSOR_RELATIVE_PATH = Path(
    "data/stage3/qwen25_vector_pool_v1/qwen25_stage3_vectors.pt"
)


def setUpModule() -> None:
    if torch is None:
        raise unittest.SkipTest("Torch is not installed in the current Python environment")


def validator_module() -> Any:
    return importlib.import_module(
        "scripts.stage3_production.validate_stage3_development_inputs"
    )


class FakeTokenizer:
    chat_template = "{{ messages[0]['content'] }}"

    def apply_chat_template(self, messages: Any, **_kwargs: Any) -> str:
        return f"validated:{messages[0]['content']}"


def fake_model_inspector(**kwargs: Any) -> tuple[dict[str, Any], FakeTokenizer]:
    resolved_model = str(Path(kwargs["model_path"]).resolve())
    resolved_tokenizer = str(Path(kwargs["tokenizer_path"]).resolve())
    role = kwargs["model_role"]
    return (
        {
            "model_role": role,
            "resolved_model_path": resolved_model,
            "resolved_tokenizer_path": resolved_tokenizer,
            "local_files_only": True,
            "hidden_size": 3584 if role == "behavior" else 4096,
            "layer_count": 28 if role == "behavior" else 36,
            "model_revision": f"fake-{role}-revision",
        },
        FakeTokenizer(),
    )


class Stage3VectorPoolLoaderTests(unittest.TestCase):
    def _mutated_pool(self, mutation: Any) -> Path:
        temporary = tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        manifest_path = root / MANIFEST_RELATIVE_PATH
        tensor_path = root / TENSOR_RELATIVE_PATH
        manifest_path.parent.mkdir(parents=True)
        tensor_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = json.loads((ROOT / MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8"))
        mutation(manifest)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        shutil.copyfile(ROOT / TENSOR_RELATIVE_PATH, tensor_path)
        return root

    def test_fixed_pool_loads_all_vectors_without_transformation(self) -> None:
        loaded = load_stage3_vector_pool(ROOT)
        self.assertEqual(tuple(loaded.tensor.shape), (30, 3584))
        self.assertEqual(loaded.manifest["V_screen"], [0, 9])
        self.assertEqual(loaded.manifest["V_confirm"], [10, 29])

    def test_manifest_shape_partition_or_row_identity_tampering_is_rejected(self) -> None:
        mutations = {
            "shape": lambda value: value.__setitem__("shape", [29, 3584]),
            "partition": lambda value: value.__setitem__("V_screen", [0, 10]),
            "row_identity": lambda value: value["row_tensor_sha256"].__setitem__(0, "0" * 64),
        }
        for label, mutation in mutations.items():
            with self.subTest(label=label):
                root = self._mutated_pool(mutation)
                with self.assertRaises(VectorPoolError):
                    load_stage3_vector_pool(root)

    def test_manifest_duplicate_keys_and_nonfinite_numbers_are_rejected(self) -> None:
        for label, replacement in (
            (
                "duplicate",
                '  "schema_version": "paper1-stage3-qwen25-vector-pool-v1",\n'
                '  "schema_version": "paper1-stage3-qwen25-vector-pool-v1",',
            ),
            ("nonfinite", '  "seed": 1e400,'),
        ):
            with self.subTest(label=label):
                temporary = tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp")
                self.addCleanup(temporary.cleanup)
                root = Path(temporary.name)
                manifest_path = root / MANIFEST_RELATIVE_PATH
                tensor_path = root / TENSOR_RELATIVE_PATH
                manifest_path.parent.mkdir(parents=True)
                tensor_path.parent.mkdir(parents=True, exist_ok=True)
                text = (ROOT / MANIFEST_RELATIVE_PATH).read_text(encoding="utf-8")
                if label == "duplicate":
                    text = text.replace(
                        '  "schema_version": "paper1-stage3-qwen25-vector-pool-v1",',
                        replacement,
                        1,
                    )
                else:
                    text = text.replace('  "seed": 42,', replacement, 1)
                manifest_path.write_text(text, encoding="utf-8")
                shutil.copyfile(ROOT / TENSOR_RELATIVE_PATH, tensor_path)
                with self.assertRaises(VectorPoolError):
                    load_stage3_vector_pool(root)


class Stage3DevelopmentInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = validator_module()
        self.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def _temporary_json(self, value: Any) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp")
        path = Path(temporary.name) / "config.json"
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return temporary, path

    def test_normal_config_validates_without_weight_generation_or_judge_calls(self) -> None:
        from stage3_pipeline import real_backend, real_judge

        forbidden = [
            mock.patch.object(real_backend.AutoModelForCausalLM, "from_pretrained"),
            mock.patch.object(real_backend.RealBehaviorBackend, "from_pretrained"),
            mock.patch.object(real_backend.RealBehaviorBackend, "__call__"),
            mock.patch.object(real_judge.RealJudgeBackend, "from_pretrained"),
            mock.patch.object(real_judge.RealJudgeBackend, "__call__"),
        ]
        active = [patcher.start() for patcher in forbidden]
        for patcher in forbidden:
            self.addCleanup(patcher.stop)
        result = self.validator.validate_development_inputs(
            CONFIG_PATH, model_asset_inspector=fake_model_inspector
        )
        self.assertEqual(
            result["status"], "STAGE3_DEVELOPMENT_INPUTS_VALIDATE_ONLY_PASS"
        )
        for field in (
            "model_weights_loaded",
            "generation_run",
            "judge_run",
            "p1_run",
            "formal_experiment_run",
            "paper_result_eligible",
        ):
            self.assertFalse(result[field])
        for forbidden_call in active:
            forbidden_call.assert_not_called()

    def test_dataset_selected_sha_or_active_row_count_mismatch_is_rejected(self) -> None:
        dataset = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["datasets"][0]
        source_entry_path = ROOT / dataset["active_entry_relative_path"]
        for label, mutate in (
            ("selected_sha", lambda value: value.__setitem__("selected_raw_sha256", "0" * 64)),
            ("row_count", lambda value: value.__setitem__("row_count", 99)),
        ):
            with self.subTest(label=label):
                temporary_root = tempfile.TemporaryDirectory(dir=ROOT / ".codex-temp")
                self.addCleanup(temporary_root.cleanup)
                root = Path(temporary_root.name)
                entry = json.loads(source_entry_path.read_text(encoding="utf-8"))
                mutate(entry)
                target_entry_path = root / dataset["active_entry_relative_path"]
                target_selected_path = root / entry["relative_path"]
                target_entry_path.parent.mkdir(parents=True)
                target_selected_path.parent.mkdir(parents=True)
                target_entry_path.write_text(
                    json.dumps(entry, indent=2) + "\n", encoding="utf-8"
                )
                shutil.copyfile(ROOT / entry["relative_path"], target_selected_path)
                with self.assertRaises(PipelineError):
                    self.validator.validate_dataset_entries(root, [dataset])

    def test_anchor_order_or_exact_value_mismatch_is_rejected(self) -> None:
        anchor = json.loads(
            (ROOT / self.validator.ANCHOR_RELATIVE_PATH).read_text(encoding="utf-8")
        )
        mutations = {
            "order": lambda value: value.__setitem__(
                "rho_by_anchor",
                {
                    "H": value["rho_by_anchor"]["H"],
                    "T": value["rho_by_anchor"]["T"],
                    "A": value["rho_by_anchor"]["A"],
                },
            ),
            "value": lambda value: value["rho_by_anchor"].__setitem__("T", 1.0),
        }
        for label, mutation in mutations.items():
            with self.subTest(label=label):
                candidate = json.loads(json.dumps(anchor))
                mutation(candidate)
                temporary, path = self._temporary_json(candidate)
                self.addCleanup(temporary.cleanup)
                with self.assertRaises(PipelineError):
                    self.validator.validate_anchor_config(path)

    def test_non_null_p1_measurement_or_dose_binding_is_rejected(self) -> None:
        for field, value in (
            ("mu_all_tw_Qwen", 1.0),
            ("dose_binding", {"status": "forged"}),
        ):
            with self.subTest(field=field):
                candidate = json.loads(json.dumps(self.config))
                candidate["p1_measurement_and_dose"][field] = value
                with self.assertRaises(PipelineError):
                    self.validator.validate_static_config(candidate)


if __name__ == "__main__":
    unittest.main()
