from __future__ import annotations

from pathlib import Path
import json
import torch


def normalize_vector(vector: torch.Tensor) -> torch.Tensor:
    norm = vector.norm()
    if norm.item() == 0:
        return vector
    return vector / norm


def load_vector(
    vector_source: str,
    hidden_dim: int,
    device: torch.device,
    vector_path: str | None = None,
    vector_index: int = 0,
    vector_layer: int | None = None,
    vector_manifest_path: str | None = None,
    normalize: bool = True,
    seed: int = 42,
) -> torch.Tensor:
    if vector_source == "random":
        generator = torch.Generator(device=device)
        generator.manual_seed(seed + vector_index)
        vector = torch.randn(hidden_dim, device=device, generator=generator)
    elif vector_source == "tensor_file":
        if vector_path is None:
            raise ValueError("vector_path is required when vector_source=tensor_file")
        resolved_index = vector_index
        if vector_layer is not None and vector_manifest_path is not None:
            resolved_index = resolve_vector_index(vector_manifest_path, vector_layer)
        tensor = torch.load(Path(vector_path), map_location=device)
        if tensor.ndim == 1:
            vector = tensor
        else:
            vector = tensor[resolved_index]
    else:
        raise ValueError(f"Unsupported vector_source: {vector_source}")

    if normalize:
        vector = normalize_vector(vector)
    return vector


def generate_random_vector_pool(
    hidden_dim: int,
    num_vectors: int,
    seed: int = 42,
    normalize: bool = True,
) -> torch.Tensor:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    vectors = torch.randn(num_vectors, hidden_dim, generator=generator)
    if normalize:
        norms = vectors.norm(dim=1, keepdim=True)
        norms = torch.where(norms == 0, torch.ones_like(norms), norms)
        vectors = vectors / norms
    return vectors


def ensure_random_vector_pool(
    vector_path: str | Path,
    hidden_dim: int,
    num_vectors: int,
    seed: int = 42,
    normalize: bool = True,
    overwrite: bool = False,
) -> dict[str, object]:
    tensor_path = Path(vector_path)
    tensor_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = tensor_path.with_suffix(f"{tensor_path.suffix}.manifest.json")

    if not overwrite and tensor_path.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "vector_path": str(tensor_path),
            "manifest_path": str(manifest_path),
            **manifest,
        }

    vectors = generate_random_vector_pool(
        hidden_dim=hidden_dim,
        num_vectors=num_vectors,
        seed=seed,
        normalize=normalize,
    )
    torch.save(vectors, tensor_path)
    manifest = {
        "hidden_dim": hidden_dim,
        "num_vectors": num_vectors,
        "seed": seed,
        "normalize": normalize,
        "dtype": str(vectors.dtype).replace("torch.", ""),
        "vector_source": "random_pool",
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "vector_path": str(tensor_path),
        "manifest_path": str(manifest_path),
        **manifest,
    }


def resolve_vector_index(vector_manifest_path: str | Path, vector_layer: int) -> int:
    manifest_path = Path(vector_manifest_path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = raw["vectors"] if isinstance(raw, dict) and "vectors" in raw else raw
    for entry in entries:
        if int(entry["layer"]) == int(vector_layer):
            return int(entry["vector_index"])
    raise ValueError(
        f"Could not find layer {vector_layer} in vector manifest: {manifest_path}"
    )
