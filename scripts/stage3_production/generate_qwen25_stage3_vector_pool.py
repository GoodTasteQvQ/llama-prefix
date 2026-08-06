#!/usr/bin/env python
"""Generate the deterministic Qwen2.5 Paper 1 Stage 3 vector pool."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import sys
from pathlib import Path
from typing import Any

import torch


REQUIRED_TORCH_RELEASE = "2.7.1"
SCHEMA_VERSION = "paper1-stage3-qwen25-vector-pool-v1"
SEED = 42
NUM_VECTORS = 30
HIDDEN_DIM = 3584
SHAPE = (NUM_VECTORS, HIDDEN_DIM)
MAX_UNIT_NORM_ERROR = 1e-6

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_RELATIVE_DIRECTORY = Path("data/stage3/qwen25_vector_pool_v1")
TENSOR_RELATIVE_PATH = OUTPUT_RELATIVE_DIRECTORY / "qwen25_stage3_vectors.pt"
MANIFEST_RELATIVE_PATH = (
    OUTPUT_RELATIVE_DIRECTORY / "qwen25_stage3_vectors.manifest.json"
)
OUTPUT_DIRECTORY = REPO_ROOT / OUTPUT_RELATIVE_DIRECTORY
TENSOR_PATH = REPO_ROOT / TENSOR_RELATIVE_PATH
MANIFEST_PATH = REPO_ROOT / MANIFEST_RELATIVE_PATH
HASH_DEFINITION = "SHA-256 of CPU contiguous float32 raw bytes in row-major order"


class VectorPoolError(RuntimeError):
    """Raised when generation or validation violates the fixed contract."""


def require_torch_271() -> None:
    release = torch.__version__.split("+", 1)[0]
    if release != REQUIRED_TORCH_RELEASE:
        raise VectorPoolError(
            f"Torch {REQUIRED_TORCH_RELEASE} is required; found {torch.__version__}"
        )


def generate_vectors() -> torch.Tensor:
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

    if not bool(torch.isfinite(norms).all().item()) or bool((norms == 0).any().item()):
        raise VectorPoolError("A generated row norm is zero or non-finite; no redraw allowed")

    vectors = (vectors / norms).contiguous()
    validate_tensor(vectors)
    return vectors


def validate_tensor(vectors: torch.Tensor) -> None:
    if type(vectors) is not torch.Tensor:
        raise VectorPoolError("Vector payload must be a direct torch.Tensor")
    if tuple(vectors.shape) != SHAPE:
        raise VectorPoolError(f"Unexpected vector shape: {tuple(vectors.shape)}")
    if vectors.dtype != torch.float32:
        raise VectorPoolError(f"Unexpected vector dtype: {vectors.dtype}")
    if vectors.device.type != "cpu":
        raise VectorPoolError(f"Unexpected vector device: {vectors.device}")
    if not vectors.is_contiguous():
        raise VectorPoolError("Vector tensor must be contiguous")
    if not bool(torch.isfinite(vectors).all().item()):
        raise VectorPoolError("Vector tensor contains a non-finite element")

    row_norms = torch.linalg.vector_norm(vectors, ord=2, dim=1)
    max_error = torch.max(torch.abs(row_norms - 1.0)).item()
    if max_error > MAX_UNIT_NORM_ERROR:
        raise VectorPoolError(f"Maximum row unit-norm error is {max_error!r}")


def tensor_raw_bytes(tensor: torch.Tensor) -> bytes:
    if tensor.device.type != "cpu" or tensor.dtype != torch.float32:
        raise VectorPoolError("Hash input must be a CPU float32 tensor")
    contiguous = tensor.contiguous()
    return bytes(contiguous.view(torch.uint8).reshape(-1).tolist())


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def serialize_tensor(vectors: torch.Tensor) -> bytes:
    buffer = io.BytesIO()
    torch.save(vectors, buffer, _use_new_zipfile_serialization=True)
    payload = buffer.getvalue()
    if not payload.startswith(b"PK\x03\x04"):
        raise VectorPoolError("torch.save did not produce zip serialization")
    return payload


def build_manifest(vectors: torch.Tensor, pt_file_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "design_generated",
        "formal_experiment_run": False,
        "generator": "torch.Generator(device=cpu)",
        "seed": SEED,
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
        "device": "cpu",
        "dtype": "float32",
        "shape": [NUM_VECTORS, HIDDEN_DIM],
        "hidden_dim": HIDDEN_DIM,
        "num_vectors": NUM_VECTORS,
        "generation_call": "torch.randn",
        "normalization": "torch.linalg.vector_norm(ord=2, dim=1, keepdim=True)",
        "zero_or_nonfinite_policy": "fail_without_redraw",
        "V_screen": [0, 9],
        "V_confirm": [10, 29],
        "pt_relative_path": TENSOR_RELATIVE_PATH.as_posix(),
        "pt_file_sha256": pt_file_sha256,
        "tensor_payload_sha256": sha256_bytes(tensor_raw_bytes(vectors)),
        "row_tensor_sha256": [
            sha256_bytes(tensor_raw_bytes(vectors[index]))
            for index in range(NUM_VECTORS)
        ],
        "hash_definition": HASH_DEFINITION,
        "sys_byteorder": sys.byteorder,
    }


def reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_manifest_strictly() -> dict[str, Any]:
    try:
        value = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8"),
            parse_constant=reject_nonstandard_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise VectorPoolError(f"Cannot strictly load manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise VectorPoolError("Manifest must be a JSON object")
    return value


def check_saved_assets() -> None:
    if not TENSOR_PATH.is_file() or not MANIFEST_PATH.is_file():
        raise VectorPoolError("Both fixed vector-pool assets must exist for --check")

    regenerated = generate_vectors()
    try:
        saved = torch.load(TENSOR_PATH, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise VectorPoolError(f"Cannot load saved tensor: {exc}") from exc
    validate_tensor(saved)
    if not torch.equal(regenerated, saved):
        raise VectorPoolError("Saved tensor differs from deterministic regeneration")

    expected_manifest = build_manifest(saved, file_sha256(TENSOR_PATH))
    observed_manifest = load_manifest_strictly()
    if observed_manifest != expected_manifest:
        raise VectorPoolError("Manifest does not exactly match the saved tensor and contract")


def write_assets() -> None:
    expected_output = (REPO_ROOT / OUTPUT_RELATIVE_DIRECTORY).resolve()
    if OUTPUT_DIRECTORY.resolve() != expected_output:
        raise VectorPoolError("Output directory is not the fixed repository path")
    existing = [path for path in (TENSOR_PATH, MANIFEST_PATH) if path.exists()]
    if existing:
        paths = ", ".join(path.relative_to(REPO_ROOT).as_posix() for path in existing)
        raise VectorPoolError(f"Refusing to overwrite existing target(s): {paths}")

    vectors = generate_vectors()
    tensor_file_bytes = serialize_tensor(vectors)
    manifest = build_manifest(vectors, sha256_bytes(tensor_file_bytes))
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with TENSOR_PATH.open("xb") as handle:
        handle.write(tensor_file_bytes)
    with MANIFEST_PATH.open("xb") as handle:
        handle.write(manifest_bytes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate in memory and validate the fixed saved assets without writing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        require_torch_271()
        if args.check:
            check_saved_assets()
            print("qwen25-stage3-vector-pool check: PASS")
        else:
            write_assets()
            print(f"wrote {TENSOR_RELATIVE_PATH.as_posix()}")
            print(f"wrote {MANIFEST_RELATIVE_PATH.as_posix()}")
    except VectorPoolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
