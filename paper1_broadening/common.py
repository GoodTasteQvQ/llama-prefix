"""Small, dependency-light helpers shared by the broadening workflow."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


class BroadeningError(ValueError):
    """A fail-closed protocol or artifact error."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BroadeningError(f"invalid JSON file: {path}") from exc


def atomic_write_bytes(path: Path, payload: bytes, *, overwrite: bool = False) -> None:
    """Write in the destination directory and never replace by accident."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise BroadeningError(f"refusing to overwrite existing file: {path}") from exc
            finally:
                if temporary.exists():
                    temporary.unlink()
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def atomic_write_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    atomic_write_bytes(
        path,
        (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        overwrite=overwrite,
    )


def append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(dict(record)) + "\n").encode("utf-8")
    needs_separator = False
    if path.exists() and path.stat().st_size:
        with path.open("rb") as reader:
            reader.seek(-1, os.SEEK_END)
            needs_separator = reader.read(1) not in {b"\n", b"\r"}
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    with os.fdopen(descriptor, "ab") as handle:
        if needs_separator:
            handle.write(b"\n")
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise BroadeningError(f"JSONL file is missing: {path}")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BroadeningError(f"invalid JSONL line {number}: {path}") from exc
        if not isinstance(value, dict):
            raise BroadeningError(f"JSONL line {number} is not an object: {path}")
        rows.append(value)
    return rows


def recover_jsonl_tail(path: Path) -> dict[str, Any]:
    """Preserve a damaged final JSONL fragment before resuming an interrupted run."""
    raw = path.read_bytes()
    if not raw:
        return {"recovered": False, "complete_rows": 0, "tail_path": None}
    lines = raw.splitlines(keepends=True)
    complete: list[bytes] = []
    tail: bytes | None = None
    for index, line in enumerate(lines):
        candidate = line.strip()
        if not candidate:
            complete.append(line)
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            if index != len(lines) - 1:
                raise BroadeningError(
                    f"corrupt non-terminal JSONL line {index + 1}: {path}"
                ) from exc
            tail = b"".join(lines[index:])
            break
        if not isinstance(parsed, dict):
            raise BroadeningError(f"JSONL line {index + 1} is not an object: {path}")
        complete.append(line)
    if tail is None:
        return {"recovered": False, "complete_rows": len(complete), "tail_path": None}
    tail_path = path.with_name(f"{path.name}.tail-{utc_now().replace(':', '')}.jsonl")
    atomic_write_bytes(tail_path, tail, overwrite=False)
    atomic_write_bytes(path, b"".join(complete), overwrite=True)
    return {"recovered": True, "complete_rows": len(complete), "tail_path": str(tail_path)}


def git_state(repo_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                encoding="utf-8",
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BroadeningError("unable to inspect repository state") from exc
    return {"code_commit": commit, "dirty": dirty}


def copy_source_snapshot(
    *, repo_root: Path, destination: Path, relative_paths: Iterable[str]
) -> list[str]:
    """Copy only the modules and scripts that define this protocol's execution."""
    copied: list[str] = []
    for relative in sorted(set(relative_paths)):
        source = (repo_root / relative).resolve()
        try:
            source.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise BroadeningError(f"source path escapes repository: {relative}") from exc
        if not source.is_file():
            raise BroadeningError(f"required source snapshot file is missing: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative)
    return copied


def project_tempdir(project_root: Path) -> Path:
    path = project_root / ".codex-temp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def temporary_directory(project_root: Path, prefix: str) -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix=prefix, dir=project_tempdir(project_root))
