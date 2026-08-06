"""Strict loader for the fixed Qwen2.5 Stage 3 vector pool."""

from __future__ import annotations

import hashlib
import math
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import torch

from .core import PipelineError
from .offline_assets import strict_json_loads


MANIFEST_RELATIVE_PATH = (
    "data/stage3/qwen25_vector_pool_v1/qwen25_stage3_vectors.manifest.json"
)
TENSOR_RELATIVE_PATH = (
    "data/stage3/qwen25_vector_pool_v1/qwen25_stage3_vectors.pt"
)
EXPECTED_SHAPE = (30, 3584)
EXPECTED_SCREEN = tuple(range(10))
EXPECTED_CONFIRM = tuple(range(10, 30))
MAX_UNIT_NORM_ERROR = 1e-6
HASH_DEFINITION = "SHA-256 of CPU contiguous float32 raw bytes in row-major order"
MANIFEST_FIELDS = (
    "schema_version",
    "status",
    "formal_experiment_run",
    "generator",
    "seed",
    "torch_version",
    "python_version",
    "device",
    "dtype",
    "shape",
    "hidden_dim",
    "num_vectors",
    "generation_call",
    "normalization",
    "zero_or_nonfinite_policy",
    "V_screen",
    "V_confirm",
    "pt_relative_path",
    "pt_file_sha256",
    "tensor_payload_sha256",
    "row_tensor_sha256",
    "hash_definition",
    "sys_byteorder",
)


class VectorPoolError(PipelineError):
    """The fixed vector-pool manifest or tensor violates its contract."""


@dataclass(frozen=True)
class LoadedVectorPool:
    tensor: torch.Tensor
    manifest: Mapping[str, Any]
    manifest_path: Path
    tensor_path: Path


def _strict_relative_path(value: str, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "://" in value:
        raise VectorPoolError(f"{field} must be a nonempty local POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise VectorPoolError(f"{field} must remain below the repository root")
    return path


def _resolve_file(root: Path, relative_path: str, field: str) -> Path:
    relative = _strict_relative_path(relative_path, field)
    candidate = (root / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise VectorPoolError(f"{field} escapes the repository root") from exc
    if not candidate.is_file() or candidate.is_symlink():
        raise VectorPoolError(f"{field} is not a regular local file: {relative_path}")
    return candidate


def _strict_json_object(path: Path) -> dict[str, Any]:
    try:
        text = path.read_bytes().decode("utf-8")
        value = strict_json_loads(text)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise VectorPoolError(f"unable to read strict vector manifest: {path}") from exc
    if not isinstance(value, dict):
        raise VectorPoolError("vector manifest must be a JSON object")
    _require_finite_numbers(value, "manifest")
    return value


def _require_finite_numbers(value: Any, field: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require_finite_numbers(child, f"{field}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _require_finite_numbers(child, f"{field}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise VectorPoolError(f"{field} contains a non-finite number")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise VectorPoolError(f"{field} must be a lowercase SHA-256")
    return value


def _tensor_sha256(tensor: torch.Tensor) -> str:
    if tensor.device.type != "cpu" or tensor.dtype != torch.float32:
        raise VectorPoolError("tensor hash input must be a CPU float32 tensor")
    if not tensor.is_contiguous():
        raise VectorPoolError("tensor hash input must be contiguous")
    raw = bytes(tensor.view(torch.uint8).reshape(-1).tolist())
    return hashlib.sha256(raw).hexdigest()


def _partition(interval: Any, field: str) -> tuple[int, ...]:
    if (
        not isinstance(interval, list)
        or len(interval) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in interval)
        or interval[0] > interval[1]
    ):
        raise VectorPoolError(f"{field} must be an inclusive integer interval")
    return tuple(range(interval[0], interval[1] + 1))


def _validate_manifest(
    manifest: Mapping[str, Any], *, tensor_relative_path: str
) -> None:
    if tuple(manifest) != MANIFEST_FIELDS:
        raise VectorPoolError("vector manifest exact ordered fields mismatch")
    expected_scalars = {
        "schema_version": "paper1-stage3-qwen25-vector-pool-v1",
        "status": "design_generated",
        "formal_experiment_run": False,
        "generator": "torch.Generator(device=cpu)",
        "seed": 42,
        "device": "cpu",
        "dtype": "float32",
        "shape": list(EXPECTED_SHAPE),
        "hidden_dim": EXPECTED_SHAPE[1],
        "num_vectors": EXPECTED_SHAPE[0],
        "generation_call": "torch.randn",
        "normalization": "torch.linalg.vector_norm(ord=2, dim=1, keepdim=True)",
        "zero_or_nonfinite_policy": "fail_without_redraw",
        "pt_relative_path": tensor_relative_path,
        "hash_definition": HASH_DEFINITION,
        "sys_byteorder": sys.byteorder,
    }
    for field, expected in expected_scalars.items():
        if manifest[field] != expected or type(manifest[field]) is not type(expected):
            raise VectorPoolError(f"vector manifest {field} mismatch")
    for field in ("torch_version", "python_version"):
        if not isinstance(manifest[field], str) or not manifest[field]:
            raise VectorPoolError(f"vector manifest {field} must be nonempty")

    screen = _partition(manifest["V_screen"], "V_screen")
    confirm = _partition(manifest["V_confirm"], "V_confirm")
    if screen != EXPECTED_SCREEN or confirm != EXPECTED_CONFIRM:
        raise VectorPoolError("vector manifest partitions differ from V_screen=0..9/V_confirm=10..29")
    if set(screen) & set(confirm) or set(screen) | set(confirm) != set(range(30)):
        raise VectorPoolError("vector manifest partitions must be disjoint and cover 0..29")

    _validate_sha256(manifest["pt_file_sha256"], "pt_file_sha256")
    _validate_sha256(manifest["tensor_payload_sha256"], "tensor_payload_sha256")
    rows = manifest["row_tensor_sha256"]
    if not isinstance(rows, list) or len(rows) != EXPECTED_SHAPE[0]:
        raise VectorPoolError("row_tensor_sha256 must contain 30 ordered identities")
    for index, identity in enumerate(rows):
        _validate_sha256(identity, f"row_tensor_sha256[{index}]")
    if len(set(rows)) != EXPECTED_SHAPE[0]:
        raise VectorPoolError("row_tensor_sha256 identities must be unique")


def load_stage3_vector_pool(
    repo_root: str | Path,
    *,
    manifest_relative_path: str = MANIFEST_RELATIVE_PATH,
    tensor_relative_path: str = TENSOR_RELATIVE_PATH,
) -> LoadedVectorPool:
    """Load and validate all 30 fixed vectors without transforming the tensor."""
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise VectorPoolError("repo_root must be an existing directory")
    if manifest_relative_path != MANIFEST_RELATIVE_PATH:
        raise VectorPoolError("unexpected Stage 3 vector manifest relative path")
    if tensor_relative_path != TENSOR_RELATIVE_PATH:
        raise VectorPoolError("unexpected Stage 3 vector tensor relative path")
    manifest_path = _resolve_file(root, manifest_relative_path, "manifest_relative_path")
    tensor_path = _resolve_file(root, tensor_relative_path, "tensor_relative_path")
    manifest = _strict_json_object(manifest_path)
    _validate_manifest(manifest, tensor_relative_path=tensor_relative_path)

    if _sha256_file(tensor_path) != manifest["pt_file_sha256"]:
        raise VectorPoolError("vector .pt file SHA-256 mismatch")
    try:
        tensor = torch.load(tensor_path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise VectorPoolError("unable to safely load the vector tensor") from exc
    if type(tensor) is not torch.Tensor:
        raise VectorPoolError("vector .pt payload must be exactly one torch.Tensor")
    if tuple(tensor.shape) != EXPECTED_SHAPE:
        raise VectorPoolError("vector tensor shape mismatch")
    if tensor.dtype != torch.float32:
        raise VectorPoolError("vector tensor dtype must be float32")
    if tensor.device.type != "cpu":
        raise VectorPoolError("vector tensor must be on CPU")
    if not tensor.is_contiguous():
        raise VectorPoolError("vector tensor must be contiguous")
    if not bool(torch.isfinite(tensor).all().item()):
        raise VectorPoolError("vector tensor must contain only finite values")
    norms = torch.linalg.vector_norm(tensor, ord=2, dim=1)
    if tuple(norms.shape) != (EXPECTED_SHAPE[0],):
        raise VectorPoolError("vector norm result shape mismatch")
    if float(torch.max(torch.abs(norms - 1.0)).item()) > MAX_UNIT_NORM_ERROR:
        raise VectorPoolError("every vector must have unit norm")

    if _tensor_sha256(tensor) != manifest["tensor_payload_sha256"]:
        raise VectorPoolError("vector tensor payload SHA-256 mismatch")
    actual_rows = [_tensor_sha256(tensor[index]) for index in range(EXPECTED_SHAPE[0])]
    if actual_rows != manifest["row_tensor_sha256"]:
        raise VectorPoolError("ordered vector row identities mismatch")
    return LoadedVectorPool(
        tensor=tensor,
        manifest=manifest,
        manifest_path=manifest_path,
        tensor_path=tensor_path,
    )


__all__ = [
    "EXPECTED_CONFIRM",
    "EXPECTED_SCREEN",
    "EXPECTED_SHAPE",
    "LoadedVectorPool",
    "MANIFEST_RELATIVE_PATH",
    "TENSOR_RELATIVE_PATH",
    "VectorPoolError",
    "load_stage3_vector_pool",
]
