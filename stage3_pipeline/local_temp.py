"""Enforce the repository-local temporary-directory policy."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .core import PipelineError


def require_project_local_temp(repo_root: Path) -> Path:
    required = (repo_root.resolve() / ".codex-temp").resolve()
    for variable in ("TEMP", "TMP"):
        value = os.environ.get(variable)
        if not value or Path(value).resolve() != required:
            raise PipelineError(f"{variable} must resolve to {required}")
    stage3_temp = required / "stage3"
    stage3_temp.mkdir(parents=True, exist_ok=True)
    probe = stage3_temp / f".write-probe-{os.getpid()}"
    descriptor: int | None = None
    try:
        descriptor = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, b"stage3-local-temp-probe\n")
        os.fsync(descriptor)
    except OSError as exc:
        raise PipelineError(f"project-local temporary directory is not writable: {stage3_temp}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise PipelineError(f"project-local temporary probe cannot be removed: {probe}") from exc
    tempfile.tempdir = str(stage3_temp)
    resolved = Path(tempfile.gettempdir()).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise PipelineError(f"tempfile escaped repository: {resolved}") from exc
    return stage3_temp
