from __future__ import annotations

import hashlib
import json
import math
import sys
import unittest
import warnings
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POOL_DIRECTORY = ROOT / "data/stage3/qwen25_vector_pool_v1"
TENSOR_PATH = POOL_DIRECTORY / "qwen25_stage3_vectors.pt"
MANIFEST_PATH = POOL_DIRECTORY / "qwen25_stage3_vectors.manifest.json"
TENSOR_RELATIVE_PATH = "data/stage3/qwen25_vector_pool_v1/qwen25_stage3_vectors.pt"
EXPECTED_SHAPE = (30, 3584)
MAX_UNIT_NORM_ERROR = 1e-6
HASH_DEFINITION = "SHA-256 of CPU contiguous float32 raw bytes in row-major order"


def load_torch() -> tuple[Any, bool]:
    try:
        import torch

        return torch, False
    except ModuleNotFoundError as original_error:
        fallback = (
            ROOT.parent
            / "envs/stage3-vector-torch271-py31210/lib/python3.12/site-packages"
        )
        if not fallback.is_dir():
            raise original_error
        sys.path.insert(0, str(fallback))
        warnings.filterwarnings("ignore", message="Failed to initialize NumPy")
        import torch

        return torch, True


torch, TORCH_IMPORTED_FROM_FALLBACK = load_torch()


def reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def assert_finite_numbers(test: unittest.TestCase, value: Any) -> None:
    if isinstance(value, dict):
        for child in value.values():
            assert_finite_numbers(test, child)
    elif isinstance(value, list):
        for child in value:
            assert_finite_numbers(test, child)
    elif isinstance(value, float):
        test.assertTrue(math.isfinite(value))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(tensor: Any) -> str:
    if tensor.device.type != "cpu" or tensor.dtype != torch.float32:
        raise AssertionError("hash input must be a CPU float32 tensor")
    payload = bytes(tensor.contiguous().view(torch.uint8).reshape(-1).tolist())
    return hashlib.sha256(payload).hexdigest()


class Qwen25Stage3VectorPoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8"),
            parse_constant=reject_nonstandard_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
        cls.tensor = torch.load(
            TENSOR_PATH,
            map_location="cpu",
            weights_only=True,
        )

    def test_manifest_strict_json_status_and_contract(self) -> None:
        self.assertIsInstance(self.manifest, dict)
        assert_finite_numbers(self, self.manifest)
        self.assertEqual(
            self.manifest["schema_version"],
            "paper1-stage3-qwen25-vector-pool-v1",
        )
        self.assertEqual(self.manifest["status"], "design_generated")
        self.assertFalse(self.manifest["formal_experiment_run"])
        self.assertEqual(self.manifest["generator"], "torch.Generator(device=cpu)")
        self.assertEqual(self.manifest["seed"], 42)
        self.assertEqual(self.manifest["device"], "cpu")
        self.assertEqual(self.manifest["dtype"], "float32")
        self.assertEqual(self.manifest["shape"], [30, 3584])
        self.assertEqual(self.manifest["hidden_dim"], 3584)
        self.assertEqual(self.manifest["num_vectors"], 30)
        self.assertEqual(self.manifest["generation_call"], "torch.randn")
        self.assertEqual(
            self.manifest["normalization"],
            "torch.linalg.vector_norm(ord=2, dim=1, keepdim=True)",
        )
        self.assertEqual(
            self.manifest["zero_or_nonfinite_policy"], "fail_without_redraw"
        )
        self.assertEqual(self.manifest["hash_definition"], HASH_DEFINITION)
        self.assertIn(self.manifest["sys_byteorder"], ("little", "big"))

    def test_manifest_contains_no_freeze_readiness_or_promotion_fields(self) -> None:
        forbidden_fragments = ("freeze", "readiness", "promotion")

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    normalized = key.lower()
                    self.assertFalse(
                        any(fragment in normalized for fragment in forbidden_fragments),
                        key,
                    )
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.manifest)

    def test_tensor_load_shape_dtype_device_finiteness_and_unit_norms(self) -> None:
        self.assertTrue(TENSOR_PATH.is_file())
        self.assertIs(type(self.tensor), torch.Tensor)
        self.assertEqual(tuple(self.tensor.shape), EXPECTED_SHAPE)
        self.assertEqual(self.tensor.dtype, torch.float32)
        self.assertEqual(self.tensor.device.type, "cpu")
        self.assertTrue(self.tensor.is_contiguous())
        self.assertTrue(bool(torch.isfinite(self.tensor).all().item()))

        norms = torch.linalg.vector_norm(self.tensor, ord=2, dim=1)
        errors = torch.abs(norms - 1.0)
        self.assertEqual(tuple(norms.shape), (30,))
        self.assertLessEqual(torch.max(errors).item(), MAX_UNIT_NORM_ERROR)

    def test_manifest_partition_is_exact_and_complete(self) -> None:
        self.assertEqual(self.manifest["V_screen"], [0, 9])
        self.assertEqual(self.manifest["V_confirm"], [10, 29])
        screen = list(range(self.manifest["V_screen"][0], self.manifest["V_screen"][1] + 1))
        confirm = list(
            range(self.manifest["V_confirm"][0], self.manifest["V_confirm"][1] + 1)
        )
        self.assertEqual(screen, list(range(10)))
        self.assertEqual(confirm, list(range(10, 30)))
        self.assertEqual(screen + confirm, list(range(30)))

    def test_file_payload_and_ordered_row_hashes_match(self) -> None:
        self.assertEqual(self.manifest["pt_relative_path"], TENSOR_RELATIVE_PATH)
        self.assertEqual(self.manifest["pt_file_sha256"], file_sha256(TENSOR_PATH))
        self.assertEqual(
            self.manifest["tensor_payload_sha256"], tensor_sha256(self.tensor)
        )
        expected_rows = [tensor_sha256(self.tensor[index]) for index in range(30)]
        self.assertEqual(len(self.manifest["row_tensor_sha256"]), 30)
        self.assertEqual(self.manifest["row_tensor_sha256"], expected_rows)
        self.assertEqual(len(set(expected_rows)), 30)

    def test_torch_271_regeneration_is_bitwise_equal(self) -> None:
        if TORCH_IMPORTED_FROM_FALLBACK or torch.__version__.split("+", 1)[0] != "2.7.1":
            self.skipTest("current interpreter does not provide Torch 2.7.1")

        generator = torch.Generator(device="cpu")
        generator.manual_seed(42)

        vectors = torch.randn(
            (30, 3584),
            generator=generator,
            dtype=torch.float32,
            device="cpu",
        )

        norms = torch.linalg.vector_norm(
            vectors,
            ord=2,
            dim=1,
            keepdim=True,
        )
        self.assertTrue(bool(torch.isfinite(norms).all().item()))
        self.assertFalse(bool((norms == 0).any().item()))

        vectors = (vectors / norms).contiguous()
        self.assertTrue(torch.equal(vectors, self.tensor))


if __name__ == "__main__":
    unittest.main()
