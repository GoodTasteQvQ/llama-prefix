"""Hash-bound adapters to the frozen Stage 3 reference implementations."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

from .core import PipelineError, file_sha256


ROOT_MANIFEST_SHA256 = {
    "writing/stage3 design/v3_5_rc2_statistics/statistical_reference_manifest.json":
        "b0e3456a303ac4831daa35cc5aa162073a2cde1a91d5bb7d184a5df0b7e23ece",
    "writing/stage3 design/v3_5_rc2_closure/C/binding_manifest.json":
        "f29943a08a87177a0fce99d536d3cebbb0c99d0ca10c55cd53c8bec27de020fd",
    "writing/stage3 design/v3_5_rc2_binding_amendment_01/amendment_binding_manifest.json":
        "98d63c66302e8bc05ab5af32ccb7ee64993c598698f6d1e0acfb384cae95d9b8",
}


class ReferenceBindingError(PipelineError):
    """A bound reference or manifest failed identity verification."""


class ReferenceAdapter:
    """Load only hash-verified reference modules from the current release."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self._modules: dict[str, ModuleType] = {}

    def _load_module(self, key: str, relative_path: str, expected_sha256: str) -> ModuleType:
        path = self.repo_root / relative_path
        if not path.is_file():
            raise ReferenceBindingError(f"missing reference: {relative_path}")
        actual = file_sha256(path)
        if actual != expected_sha256:
            raise ReferenceBindingError(
                f"reference hash mismatch for {relative_path}: expected {expected_sha256}, got {actual}"
            )
        if key not in self._modules:
            spec = importlib.util.spec_from_file_location(f"stage3_bound_{key}", path)
            if spec is None or spec.loader is None:
                raise ReferenceBindingError(f"cannot import reference: {relative_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._modules[key] = module
        return self._modules[key]

    def _json(self, relative_path: str, *, root_manifest: bool = False) -> Any:
        path = self.repo_root / relative_path
        if root_manifest:
            expected = ROOT_MANIFEST_SHA256.get(relative_path)
            if expected is None:
                raise ReferenceBindingError(f"unregistered root manifest: {relative_path}")
            actual = file_sha256(path)
            if actual != expected:
                raise ReferenceBindingError(
                    f"root manifest hash mismatch for {relative_path}: expected {expected}, got {actual}"
                )
        return json.loads(path.read_text(encoding="utf-8"))

    def _base_statistics(self) -> ModuleType:
        directory = "writing/stage3 design/v3_5_rc2_statistics"
        manifest = self._json(
            f"{directory}/statistical_reference_manifest.json", root_manifest=True
        )
        expected = manifest["sha256"]["reference_statistics.py"]
        return self._load_module(
            "base_statistics", f"{directory}/reference_statistics.py", expected
        )

    def _amendment_artifact(self, role: str, key: str) -> ModuleType:
        manifest = self._json(
            "writing/stage3 design/v3_5_rc2_binding_amendment_01/amendment_binding_manifest.json",
            root_manifest=True,
        )
        matches = [entry for entry in manifest["artifacts"] if entry["role"] == role]
        if len(matches) != 1:
            raise ReferenceBindingError(f"amendment manifest has no unique role {role}")
        entry = matches[0]
        return self._load_module(key, entry["path"], entry["sha256"])

    def _base_closure_artifact(self, role: str, key: str) -> ModuleType:
        manifest = self._json(
            "writing/stage3 design/v3_5_rc2_closure/C/binding_manifest.json",
            root_manifest=True,
        )
        matches = [entry for entry in manifest["artifacts"] if entry["role"] == role]
        if len(matches) != 1:
            raise ReferenceBindingError(f"closure manifest has no unique role {role}")
        entry = matches[0]
        return self._load_module(key, entry["path"], entry["sha256"])

    def p1(self, strata: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
        module = self._base_statistics()
        return module.p1_interval(dict(strata), replicates=10_000, min_success=9_500)

    def p2_raw(self, members: Sequence[dict[str, Any]]) -> dict[str, Any]:
        module = self._base_statistics()
        return module.p2_raw_simultaneous(list(members), replicates=9_999, min_success=9_500)

    def retained_k1(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        module = self._amendment_artifact("retained_reference", "retained")
        return module.analyze_k1(payload, fixture_mode=False)

    def retained_harmful_clean(
        self, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        module = self._amendment_artifact("retained_reference", "retained")
        return module.analyze_harmful_clean(payload, fixture_mode=False)

    def retained_benign_broken(
        self, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        module = self._amendment_artifact("retained_reference", "retained")
        return module.analyze_benign_broken(payload, fixture_mode=False)

    def two_phase_point(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        module = self._amendment_artifact("two_phase_reference", "two_phase")
        return module.point_estimates(payload)

    def two_phase_interval(self, payload: Mapping[str, Any], *, vector_aware: bool) -> dict[str, Any]:
        module = self._amendment_artifact("two_phase_reference", "two_phase")
        block = module.BLOCKS["vector" if vector_aware else "prompt"]
        return module.simultaneous_interval(payload, block)

    def fixed720(self, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        module = self._base_closure_artifact("fixed720_reference_implementation", "fixed720")
        return module.allocate_human_sample(records, n_total=720, master_seed=42)

    def binding_report(self) -> dict[str, Any]:
        """Load every production reference and report the verified hashes."""
        self._base_statistics()
        self._amendment_artifact("retained_reference", "retained")
        self._amendment_artifact("two_phase_reference", "two_phase")
        self._base_closure_artifact("fixed720_reference_implementation", "fixed720")
        return {
            "status": "REFERENCE_BINDINGS_VERIFIED",
            "loaded": sorted(self._modules),
            "alternate_algorithm": False,
        }
