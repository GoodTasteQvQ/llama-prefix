#!/usr/bin/env python3
"""Static verifier for the v3.5-rc2 binding amendment 01.

This verifier reads design artifacts and explicitly synthetic fixtures only. It
cannot execute P1, generation, support, judging, or human annotation.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]
AMENDMENT_ID = "v3.5-rc2-binding-amendment-01"
WRITE_DIR = ROOT / "writing/stage3 design/v3_5_rc2_binding_amendment_01"
SCRIPT_DIR = ROOT / "scripts/stage3_design/v3_5_rc2_binding_amendment_01"
AMENDMENT_DOC = (
    ROOT
    / "writing/stage3 design/revision/"
    "paper1_attention_sink_mu_experiment_design_v3_5_rc2_binding_amendment_01.md"
)
COMPLETION_REPORT = (
    ROOT
    / "writing/stage3 design/revision/"
    "paper1_attention_sink_mu_v3_5_rc2_binding_amendment_01_repair_completion.md"
)
PARTIAL_WITNESS_COMPLETION_REPORT = (
    ROOT
    / "writing/stage3 design/revision/"
    "paper1_attention_sink_mu_v3_5_rc2_binding_amendment_01_partial_witness_repair_completion.md"
)
COMPLETION_REPORTS = (COMPLETION_REPORT, PARTIAL_WITNESS_COMPLETION_REPORT)
FINAL_CLOSURE_AUDIT = (
    ROOT
    / "writing/stage3 design/revision/"
    "paper1_attention_sink_mu_design_freeze_binding_amendment_01_final_closure_audit.md"
)
BASELINE = WRITE_DIR / "base_rc2_hashes_initial.sha256"
BINDING_MANIFEST = WRITE_DIR / "amendment_binding_manifest.json"
RELEASE_MANIFEST = WRITE_DIR / "amendment_release_manifest.json"
VERIFIER_CONFIG = WRITE_DIR / "verifier_contract.json"
BASELINE_FILE_SHA256 = "62cdc07760c709799a2a1cce17177df1fabe838a3f0d5054d853bd6d839a722d"

TWO_PHASE_MODULE = SCRIPT_DIR / "two_phase/two_phase_reference.py"
TWO_PHASE_VERIFIER = SCRIPT_DIR / "two_phase/verify_two_phase_golden.py"
RETAINED_MODULE = SCRIPT_DIR / "retained_bootstrap/retained_bootstrap.py"
RETAINED_SCHEMA_HELPER = SCRIPT_DIR / "retained_bootstrap/draft202012_subset.py"
RETAINED_VERIFIER = SCRIPT_DIR / "retained_bootstrap/verify_golden.py"
RETAINED_SCHEMA = WRITE_DIR / "retained_bootstrap/retained_bootstrap_schema.json"
PARTIAL_WITNESS_INPUT = (
    WRITE_DIR / "retained_bootstrap/fixtures/partial_harmful_production_shape_input.json"
)
PARTIAL_WITNESS_EXPECTED = (
    WRITE_DIR / "retained_bootstrap/fixtures/partial_harmful_production_shape_expected.json"
)
HARMFUL_CLEAN_SUBSCHEMA = "#/$defs/harmfulClean"
RECEIPT_SHA256_RULE = "sha256_utf8_excluding_parent_release_identity_block_v1"
RECEIPT_PARENT_BEGIN = "PARENT_RELEASE_IDENTITY_BEGIN"
RECEIPT_PARENT_END = "PARENT_RELEASE_IDENTITY_END"

EXPECTED_BASE_DEPENDENCIES = {
    "writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc2.md":
        "0aadb33cf14697f4e7751086b3663a176498d816435930bdafa2a2488a297e9d",
    "writing/stage3 design/revision/paper1_attention_sink_mu_design_freeze_closure_audit_v3_5_rc2.md":
        "eb5aa86d03efb0e8534c2c12c23940ef92016fddfbea0698f935ac073844f0a6",
    "writing/stage3 design/revision/paper1_attention_sink_mu_experiment_design_v3_5_rc1_to_v3_5_rc2_semantic_diff.md":
        "83d7d096660349e82af05cfbe3fba894f29a73c2592da149542265d47918048d",
    "writing/stage3 design/v3_5_rc2_statistics/statistical_reference_manifest.json":
        "b0e3456a303ac4831daa35cc5aa162073a2cde1a91d5bb7d184a5df0b7e23ece",
    "writing/stage3 design/v3_5_rc2_closure/C/binding_manifest.json":
        "f29943a08a87177a0fce99d536d3cebbb0c99d0ca10c55cd53c8bec27de020fd",
    "writing/stage3 design/v3_5_rc2_contracts/v3_5_rc2_hash_manifest.json":
        "6f80ba31a5fe79ec26693c69e0be410ce3fac3b2d4ff52f19105bb98f22a1a27",
    "writing/stage3 design/v3_5_rc2_contracts/v3_5_rc2_release_manifest.json":
        "79af2f0d2e62c4e2d95f3359bab74cbc873aed737baf25fee9e0a5b12e83d11a",
}

EXPECTED_REPAIR_INPUT_DEPENDENCIES = {
    "writing/stage3 design/revision/paper1_attention_sink_mu_design_freeze_binding_amendment_01_final_closure_audit.md":
        "1d4c45fcc015586a6cd50bdf86d1d8e798351dcedc225765a2a0fd765ba63eb2",
}

EXPECTED_BUDGET = {
    "support": 900,
    "p2_four_cells": 4000,
    "k1_reuse": 0,
    "harmful_clean": 50,
    "benign_t_steered": 600,
    "benign_clean": 30,
    "logical_generation": 5580,
    "first_pass_scheduled_judge": 5580,
    "human_items": 720,
}
EXPECTED_SCOPE = {"P": 50, "V": 20, "human_items": 720, "new_experiment_blocks": 0}
EXPECTED_NON_OUTPUTS = {
    "formal_P1": False,
    "formal_generation": False,
    "formal_human_experiment": False,
    "formal_judge": False,
    "formal_results": False,
    "formal_support": False,
}
EXPECTED_PARAMETERS = {
    "two_phase_prompt": {"replicates": 9999, "common_success_required": 9500},
    "two_phase_vector": {"replicates": 9999, "common_success_required": 9500},
    "k1_profile": {"replicates": 10000, "common_success_fraction_percent": 95},
    "harmful_clean": {"replicates": 10000, "common_success_fraction_percent": 95},
    "benign_broken": {"replicates": 10000, "common_success_fraction_percent": 95},
}


class VerificationError(RuntimeError):
    """Raised when an immutable or executable amendment condition fails."""


def fail(condition: bool, message: str) -> None:
    if condition:
        raise VerificationError(message)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any, *, exclude_self: bool = False) -> bytes:
    if exclude_self:
        fail(not isinstance(value, dict), "self-hashed document must be an object")
        value = {key: item for key, item in value.items() if key != "self_sha256"}
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def load_json(path: Path) -> Any:
    fail(not path.is_file(), f"required JSON is missing: {repo_path(path)}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise VerificationError(f"path escapes repository: {path}") from exc


def validate_self_hash(document: dict[str, Any], label: str) -> None:
    expected = document.get("self_sha256")
    actual = hashlib.sha256(canonical_bytes(document, exclude_self=True)).hexdigest()
    fail(expected != actual, f"{label} self_sha256 mismatch: {expected!r} != {actual}")


def parse_baseline() -> dict[str, str]:
    fail(file_sha256(BASELINE) != BASELINE_FILE_SHA256, "initial base hash evidence changed")
    result: dict[str, str] = {}
    pattern = re.compile(r"^([0-9a-f]{64})  (.+)$")
    for line_number, line in enumerate(BASELINE.read_text(encoding="utf-8").splitlines(), 1):
        match = pattern.fullmatch(line)
        fail(match is None, f"invalid baseline line {line_number}")
        assert match is not None
        digest, relative = match.groups()
        fail(relative in result, f"duplicate baseline path: {relative}")
        result[relative] = digest
    fail(len(result) != 25, f"initial baseline must contain exactly 25 files, got {len(result)}")
    return result


def verify_base_immutability() -> int:
    baseline = parse_baseline()
    for relative, expected in baseline.items():
        path = ROOT / relative
        fail(not path.is_file(), f"base rc2 file missing: {relative}")
        fail(file_sha256(path) != expected, f"base rc2 hash mismatch: {relative}")
    for relative, expected in EXPECTED_BASE_DEPENDENCIES.items():
        fail(baseline.get(relative) != expected, f"base dependency absent from initial hashes: {relative}")
    return len(baseline)


def verify_config() -> dict[str, Any]:
    config = load_json(VERIFIER_CONFIG)
    fail(config.get("schema_version") != "1.0.0", "verifier contract schema changed")
    fail(config.get("amendment_id") != AMENDMENT_ID, "verifier contract amendment_id changed")
    fail(config.get("formal_data_used") is not False, "formal_data_used must be false")
    fail(config.get("no_scope_expansion") is not True, "no_scope_expansion must be true")
    fail(config.get("status") != "DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED", "invalid amendment status")
    fail(config.get("fixed_budget") != EXPECTED_BUDGET, "fixed budget contract changed")
    fail(config.get("production_parameters") != EXPECTED_PARAMETERS, "production resampling parameters changed")
    restorations = config.get("prohibited_restorations")
    fail(not isinstance(restorations, dict) or not restorations, "prohibited restoration registry missing")
    fail(any(value is not False for value in restorations.values()), "a prohibited scope item is enabled")
    return config


def verify_manifest_entry(entry: dict[str, Any]) -> None:
    relative = entry.get("path")
    fail(not isinstance(relative, str) or not relative, "manifest artifact path is invalid")
    path = ROOT / relative
    fail(repo_path(path) != relative, f"manifest path is not canonical: {relative}")
    fail(not path.is_file(), f"manifest artifact missing: {relative}")
    fail(entry.get("sha256") != file_sha256(path), f"manifest artifact hash mismatch: {relative}")
    fail(entry.get("length") != path.stat().st_size, f"manifest artifact length mismatch: {relative}")


def receipt_projection(path: Path) -> tuple[bytes, str, str]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError("partial-witness receipt is not UTF-8") from exc
    fail(text.count(RECEIPT_PARENT_BEGIN) != 1, "receipt parent begin marker must occur exactly once")
    fail(text.count(RECEIPT_PARENT_END) != 1, "receipt parent end marker must occur exactly once")
    pattern = re.compile(
        re.escape(RECEIPT_PARENT_BEGIN)
        + r"\nrelease_manifest_physical_sha256=([0-9a-f]{64})"
        + r"\nrelease_manifest_self_sha256=([0-9a-f]{64})\n"
        + re.escape(RECEIPT_PARENT_END)
    )
    match = pattern.search(text)
    fail(match is None, "receipt parent identity block is malformed")
    assert match is not None
    replacement = (
        RECEIPT_PARENT_BEGIN
        + "\nrelease_manifest_physical_sha256=" + "0" * 64
        + "\nrelease_manifest_self_sha256=" + "0" * 64 + "\n"
        + RECEIPT_PARENT_END
    )
    projected = text[:match.start()] + replacement + text[match.end():]
    return projected.encode("utf-8"), match.group(1), match.group(2)


def verify_release_entry(entry: dict[str, Any], release: dict[str, Any]) -> None:
    relative = entry.get("path")
    fail(not isinstance(relative, str) or not relative, "release artifact path is invalid")
    path = ROOT / relative
    fail(repo_path(path) != relative, f"release path is not canonical: {relative}")
    fail(not path.is_file(), f"release artifact missing: {relative}")
    fail(entry.get("length") != path.stat().st_size, f"release artifact length mismatch: {relative}")
    rule = entry.get("sha256_rule")
    if rule is None:
        fail(set(entry) != {"path", "sha256", "length"}, f"invalid physical release entry fields: {relative}")
        fail(entry.get("sha256") != file_sha256(path), f"release artifact hash mismatch: {relative}")
        return
    fail(
        relative != repo_path(PARTIAL_WITNESS_COMPLETION_REPORT)
        or rule != RECEIPT_SHA256_RULE
        or set(entry) != {"path", "sha256", "length", "sha256_rule"},
        f"unregistered release artifact hash rule: {relative}",
    )
    projected, embedded_physical, embedded_self = receipt_projection(path)
    actual = hashlib.sha256(projected).hexdigest()
    fail(entry.get("sha256") != actual, f"receipt projection hash mismatch: {actual}")
    fail(embedded_self != release.get("self_sha256"), "receipt embeds wrong release self_sha256")
    fail(embedded_physical != file_sha256(RELEASE_MANIFEST), "receipt embeds wrong release physical SHA256")


def verify_component_manifest(path: Path, expected_schema: str) -> int:
    document = load_json(path)
    fail(document.get("schema_version") != expected_schema, f"component manifest schema changed: {repo_path(path)}")
    validate_self_hash(document, repo_path(path))
    fail(document.get("amendment_id") != AMENDMENT_ID, f"component amendment_id changed: {repo_path(path)}")
    fail(
        document.get("status") != "DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED",
        f"component status changed: {repo_path(path)}",
    )
    fail(document.get("formal_data_used") is not False, f"component formal_data_used changed: {repo_path(path)}")
    fail(document.get("no_scope_expansion") is not True, f"component no_scope_expansion changed: {repo_path(path)}")
    dependencies = document.get("transitive_dependencies")
    fail(not isinstance(dependencies, list) or not dependencies, f"component dependencies missing: {repo_path(path)}")
    baseline = parse_baseline()
    for entry in dependencies:
        relative = entry.get("path")
        fail(not isinstance(relative, str) or relative not in baseline, f"unexpected component dependency: {relative!r}")
        fail(entry.get("sha256") != baseline[relative], f"component dependency hash changed: {relative}")
        fail(file_sha256(ROOT / relative) != entry["sha256"], f"component dependency mismatch: {relative}")
    artifacts = document.get("artifacts")
    fail(not isinstance(artifacts, list) or not artifacts, f"component artifacts missing: {repo_path(path)}")
    seen: set[str] = set()
    for entry in artifacts:
        relative = entry.get("path")
        fail(not isinstance(relative, str) or relative in seen, f"duplicate/invalid component artifact: {relative!r}")
        seen.add(relative)
        artifact = ROOT / relative
        fail(not artifact.is_file(), f"component artifact missing: {relative}")
        fail(file_sha256(artifact) != entry.get("sha256"), f"component artifact hash mismatch: {relative}")
        recorded_length = entry.get("bytes", entry.get("length"))
        fail(artifact.stat().st_size != recorded_length, f"component artifact length mismatch: {relative}")
    return len(artifacts)


def inventory(*, include_binding: bool) -> set[str]:
    excluded = {repo_path(RELEASE_MANIFEST)}
    if not include_binding:
        excluded.add(repo_path(BINDING_MANIFEST))
        excluded.add(repo_path(BASELINE))
    paths = {repo_path(AMENDMENT_DOC)} if AMENDMENT_DOC.is_file() else set()
    # Completion receipts are children of the aggregate binding and are bound
    # only by the downstream release manifest.
    if include_binding:
        paths.update(repo_path(path) for path in COMPLETION_REPORTS if path.is_file())
    for root in (WRITE_DIR, SCRIPT_DIR):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix == ".pyc" or "__pycache__" in path.parts:
                continue
            relative = repo_path(path)
            if relative not in excluded:
                paths.add(relative)
    return paths


def verify_manifests() -> dict[str, int]:
    binding = load_json(BINDING_MANIFEST)
    release = load_json(RELEASE_MANIFEST)
    fail(binding.get("schema_version") != "v3.5-rc2-binding-amendment-manifest-v1", "binding schema changed")
    fail(release.get("schema_version") != "v3.5-rc2-binding-amendment-release-v1", "release schema changed")
    validate_self_hash(binding, "amendment binding manifest")
    validate_self_hash(release, "amendment release manifest")
    for document, label in ((binding, "binding"), (release, "release")):
        fail(document.get("amendment_id") != AMENDMENT_ID, f"{label} amendment_id changed")
        fail(document.get("formal_data_used") is not False, f"{label} formal_data_used must be false")
        fail(document.get("no_scope_expansion") is not True, f"{label} no_scope_expansion must be true")
        fail(document.get("status") != "DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED", f"{label} status changed")
        fail(document.get("fixed_scope") != EXPECTED_SCOPE, f"{label} fixed_scope changed")
        fail(document.get("fixed_budget") != EXPECTED_BUDGET, f"{label} fixed_budget changed")
        fail(document.get("non_outputs") != EXPECTED_NON_OUTPUTS, f"{label} non_outputs changed")
        fail(document.get("production_parameters") != EXPECTED_PARAMETERS, f"{label} production_parameters changed")

    dependencies = {entry["path"]: entry["sha256"] for entry in binding.get("transitive_dependencies", [])}
    expected_dependencies = {
        **EXPECTED_BASE_DEPENDENCIES,
        **EXPECTED_REPAIR_INPUT_DEPENDENCIES,
    }
    fail(dependencies != expected_dependencies, "binding transitive dependency set/hash changed")
    for relative, expected in EXPECTED_REPAIR_INPUT_DEPENDENCIES.items():
        fail(file_sha256(ROOT / relative) != expected, f"repair input dependency mismatch: {relative}")
    base = binding.get("base_protocol", {})
    fail(base.get("path") not in EXPECTED_BASE_DEPENDENCIES, "base protocol path changed")
    fail(base.get("sha256") != EXPECTED_BASE_DEPENDENCIES.get(base.get("path")), "base protocol hash changed")
    base_release = binding.get("base_rc2_release_manifest", {})
    fail(base_release.get("path") not in EXPECTED_BASE_DEPENDENCIES, "base release path changed")
    fail(base_release.get("sha256") != EXPECTED_BASE_DEPENDENCIES.get(base_release.get("path")), "base release hash changed")
    initial = binding.get("initial_base_hash_evidence", {})
    fail(initial.get("path") != repo_path(BASELINE), "initial hash evidence path changed")
    fail(initial.get("sha256") != BASELINE_FILE_SHA256, "initial hash evidence digest changed")

    binding_entries = binding.get("artifacts", [])
    fail(not isinstance(binding_entries, list), "binding artifacts must be a list")
    binding_paths = [entry.get("path") for entry in binding_entries]
    fail(len(binding_paths) != len(set(binding_paths)), "binding artifact paths are duplicated")
    for entry in binding_entries:
        verify_manifest_entry(entry)
    fail(set(binding_paths) != inventory(include_binding=False), "binding artifact inventory is incomplete or excessive")

    producer = binding.get("producer", {})
    for kind, expected_path in (("code", repo_path(Path(__file__))), ("config", repo_path(VERIFIER_CONFIG))):
        entry = producer.get(kind, {})
        fail(entry.get("path") != expected_path, f"producer {kind} path changed")
        fail(entry.get("sha256") != file_sha256(ROOT / expected_path), f"producer {kind} hash mismatch")

    release_entries = release.get("artifacts", [])
    fail(not isinstance(release_entries, list), "release artifacts must be a list")
    release_paths = [entry.get("path") for entry in release_entries]
    fail(len(release_paths) != len(set(release_paths)), "release artifact paths are duplicated")
    for entry in release_entries:
        verify_release_entry(entry, release)
    special_entries = [entry for entry in release_entries if entry.get("sha256_rule") is not None]
    expected_special_count = 1 if PARTIAL_WITNESS_COMPLETION_REPORT.is_file() else 0
    fail(len(special_entries) != expected_special_count, "release receipt projection entry count changed")
    fail(set(release_paths) != inventory(include_binding=True), "release artifact inventory is incomplete or excessive")
    binding_entry = next((entry for entry in release_entries if entry.get("path") == repo_path(BINDING_MANIFEST)), None)
    fail(binding_entry is None, "release does not bind amendment binding manifest")
    assert binding_entry is not None
    fail(binding_entry["sha256"] != file_sha256(BINDING_MANIFEST), "release binding-manifest hash mismatch")
    two_phase_count = verify_component_manifest(
        WRITE_DIR / "two_phase/two_phase_binding_manifest.json",
        "v3.5-rc2-binding-amendment-01-two-phase-manifest-v1",
    )
    retained_count = verify_component_manifest(
        WRITE_DIR / "retained_bootstrap/retained_bootstrap_manifest.json",
        "v3.5-rc2-amendment-01-retained-bootstrap-manifest-v1",
    )
    return {
        "binding_artifacts": len(binding_entries),
        "release_artifacts": len(release_entries),
        "component_artifacts": two_phase_count + retained_count,
    }


def import_reference(path: Path, name: str) -> ModuleType:
    fail(not path.is_file(), f"reference implementation missing: {repo_path(path)}")
    spec = importlib.util.spec_from_file_location(name, path)
    fail(spec is None or spec.loader is None, f"cannot load reference: {repo_path(path)}")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_reference_parameters(two_phase: ModuleType, retained: ModuleType) -> None:
    fail(getattr(two_phase, "REPLICATES", None) != 9999, "two-phase REPLICATES changed")
    fail(
        getattr(two_phase, "COMMON_SUCCESS_REQUIRED", None) != 9500,
        "two-phase COMMON_SUCCESS_REQUIRED changed",
    )
    fail(
        tuple(getattr(two_phase, "MEMBER_ORDER", ())) != ("P2-U(A)", "P2-B(T)"),
        "two-phase member order changed",
    )
    fail(
        getattr(two_phase, "BLOCKS", None)
        != {"prompt": "p2-two-phase-prompt", "vector": "p2-two-phase-vector"},
        "two-phase block registry changed",
    )
    fail(
        getattr(retained, "PRODUCTION_REPLICATES", None) != 10000,
        "retained PRODUCTION_REPLICATES changed",
    )
    fail(
        getattr(retained, "PRODUCTION_MIN_SUCCESS", None) != 9500,
        "retained PRODUCTION_MIN_SUCCESS changed",
    )
    fail(
        getattr(retained, "PRODUCTION_SUCCESS_FRACTION", None) != 0.95,
        "retained PRODUCTION_SUCCESS_FRACTION changed",
    )
    fail(getattr(retained, "K1_BLOCK_ID", None) != "k1-profile", "K1 block_id changed")
    fail(
        getattr(retained, "HARMFUL_CLEAN_BLOCK_ID", None) != "harmful-clean-prompt",
        "harmful-clean block_id changed",
    )
    fail(
        getattr(retained, "BENIGN_BROKEN_BLOCK_ID", None) != "benign-broken-prompt",
        "benign-broken block_id changed",
    )


def run_reference_verifier(path: Path, marker: str) -> None:
    env = os.environ.copy()
    local_temp = ROOT / ".codex-temp"
    local_temp.mkdir(exist_ok=True)
    env.update({
        "TEMP": str(local_temp),
        "TMP": str(local_temp),
        "NX_DAEMON": "false",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    completed = subprocess.run(
        [sys.executable, "-B", str(path)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    fail(
        completed.returncode != 0 or marker not in completed.stdout,
        f"reference verifier failed: {repo_path(path)}; stdout={completed.stdout!r}; stderr={completed.stderr!r}",
    )


def verify_references() -> dict[str, int]:
    two_phase = import_reference(TWO_PHASE_MODULE, "amendment_two_phase_reference")
    retained = import_reference(RETAINED_MODULE, "amendment_retained_bootstrap_reference")
    schema_helper = import_reference(RETAINED_SCHEMA_HELPER, "amendment_retained_schema_helper")
    verify_reference_parameters(two_phase, retained)
    verify_reference_behavior(two_phase, retained, schema_helper)
    run_reference_verifier(TWO_PHASE_VERIFIER, "TWO_PHASE_AMENDMENT_GOLDEN_PASS")
    run_reference_verifier(
        RETAINED_VERIFIER,
        "RETAINED_BOOTSTRAP_GOLDEN_PASS partial_schema_valid=1 partial_prompt_count=50",
    )
    return {"bound_schema_helpers": 1, "direct_reference_modules": 2, "golden_verifiers": 2}


def verify_reference_behavior(
    two_phase: ModuleType, retained: ModuleType, schema_helper: ModuleType
) -> None:
    """Directly execute both references and independently check fixed identities."""
    required_two_phase = (
        "evaluate_success_fixture", "evaluate_failure_fixture", "prompt_sync_unit",
        "phase_two_sync_unit", "vector_sync_unit", "seed_material", "Sha256CounterRng",
    )
    required_retained = (
        "evaluate_success_fixture", "evaluate_failure_fixture", "sync_unit_id",
        "seed_bytes", "Sha256CounterRng", "analyze_harmful_clean",
    )
    for name in required_two_phase:
        fail(not callable(getattr(two_phase, name, None)), f"two-phase direct callable missing: {name}")
    for name in required_retained:
        fail(not callable(getattr(retained, name, None)), f"retained direct callable missing: {name}")
    fail(
        not callable(getattr(schema_helper, "validate_subschema", None)),
        "bound schema validation helper is missing",
    )

    tp_input = load_json(WRITE_DIR / "two_phase/fixtures/success_input.json")
    tp_expected = load_json(WRITE_DIR / "two_phase/fixtures/success_expected.json")
    tp_failure_input = load_json(WRITE_DIR / "two_phase/fixtures/failure_input.json")
    tp_failure_expected = load_json(WRITE_DIR / "two_phase/fixtures/failure_expected.json")
    tp_actual = two_phase.evaluate_success_fixture(tp_input)
    fail(canonical_bytes(tp_actual) != canonical_bytes(tp_expected), "direct two-phase success golden mismatch")
    tp_failure_actual = two_phase.evaluate_failure_fixture(tp_input, tp_failure_input)
    fail(
        canonical_bytes(tp_failure_actual) != canonical_bytes(tp_failure_expected),
        "direct two-phase failure golden mismatch",
    )
    required_tp_failures = {
        "incomplete_pair", "empty_arm", "invalid_pi", "phase2_n_h_zero",
        "phase2_n_h_one_noncensus", "nonfinite_value", "invalid_residual_denominator",
        "frame_hash_mismatch", "compound_hash_precedes_invalid_pi", "wrong_member_order",
        "insufficient_prompt_clusters", "kish_ess_below_20", "max_normalized_weight_above_0_20",
        "common_success_9499",
        "member_id_forbidden_in_sync",
    }
    fail(
        {item.get("case_id") for item in tp_failure_actual.get("results", [])} != required_tp_failures,
        "two-phase failure coverage set changed",
    )

    retained_input = load_json(WRITE_DIR / "retained_bootstrap/fixtures/success_golden_input.json")
    retained_expected = load_json(WRITE_DIR / "retained_bootstrap/fixtures/success_golden_expected.json")
    retained_failure_input = load_json(WRITE_DIR / "retained_bootstrap/fixtures/failure_golden_input.json")
    retained_failure_expected = load_json(WRITE_DIR / "retained_bootstrap/fixtures/failure_golden_expected.json")
    retained_actual = retained.evaluate_success_fixture(retained_input)
    fail(
        canonical_bytes(retained_actual) != canonical_bytes(retained_expected),
        "direct retained-bootstrap success golden mismatch",
    )
    retained_failure_actual = retained.evaluate_failure_fixture(retained_input, retained_failure_input)
    fail(
        canonical_bytes(retained_failure_actual) != canonical_bytes(retained_failure_expected),
        "direct retained-bootstrap failure golden mismatch",
    )

    partial_fixture = load_json(PARTIAL_WITNESS_INPUT)
    partial_expected = load_json(PARTIAL_WITNESS_EXPECTED)
    fail(
        partial_fixture.get("synthetic_data") is not True
        or partial_fixture.get("formal_data_used") is not False
        or partial_fixture.get("data_origin") != "SYNTHETIC_GOLDEN_ONLY",
        "partial production-shape fixture provenance changed",
    )
    partial_payload = partial_fixture.get("production_schema_payload")
    fail(not isinstance(partial_payload, dict), "partial production payload is missing")
    bound_schema = load_json(RETAINED_SCHEMA)
    schema_helper.validate_subschema(bound_schema, HARMFUL_CLEAN_SUBSCHEMA, partial_payload)

    negative_controls: list[tuple[str, dict[str, Any], str]] = []
    prompt_49 = copy.deepcopy(partial_payload)
    prompt_49["prompt_frame"] = prompt_49["prompt_frame"][:49]
    negative_controls.append(("49_prompts", prompt_49, "minItems"))
    records_51 = copy.deepcopy(partial_payload)
    records_51["records"].extend(
        {
            "row_id": f"synthetic-aggregate-negative-row-{index:02d}",
            "prompt_id": partial_payload["prompt_frame"][3]["prompt_id"],
            "label": "safe",
        }
        for index in range(4, 52)
    )
    negative_controls.append(("51_records", records_51, "maxItems"))
    empty_records = copy.deepcopy(partial_payload)
    empty_records["records"] = []
    negative_controls.append(("empty_records", empty_records, "minItems"))
    inner_synthetic = copy.deepcopy(partial_payload)
    inner_synthetic["synthetic_data"] = True
    negative_controls.append(("inner_synthetic_true", inner_synthetic, "const"))
    for case_id, control, expected_keyword in negative_controls:
        try:
            schema_helper.validate_subschema(bound_schema, HARMFUL_CLEAN_SUBSCHEMA, control)
        except schema_helper.InstanceValidationError as error:
            fail(error.keyword != expected_keyword, f"partial schema negative mismatch: {case_id}")
        else:
            raise VerificationError(f"partial schema negative unexpectedly passed: {case_id}")

    partial_output = retained.analyze_harmful_clean(partial_payload)
    partial_points = {
        label: partial_output["statistics"][label]["point"]
        for label in retained.HARMFUL_LABELS
    }
    partial_actual = {
        "fixture_schema": "v3.5-rc2-amendment-01-partial-harmful-production-shape-receipt-v1",
        "synthetic_data": True,
        "formal_data_used": False,
        "data_origin": "SYNTHETIC_GOLDEN_ONLY",
        "purpose": "production-schema partial-record execution witness",
        "schema_validation": {
            "bound_schema_path": HARMFUL_CLEAN_SUBSCHEMA,
            "bound_schema_sha256": file_sha256(RETAINED_SCHEMA),
            "negative_controls_rejected": 10,
            "status": "PASS",
        },
        "production_entry": {
            "call": "analyze_harmful_clean(payload)",
            "fixture_mode": False,
        },
        "witness": {
            "inner_synthetic_data": partial_payload["synthetic_data"],
            "prompt_count": len(partial_payload["prompt_frame"]),
            "retained_count": len(partial_payload["records"]),
            "point_denominator": len(partial_payload["records"]),
            "point_profile": partial_points,
            "draw_size": partial_output["frame"]["prompt_sample_size_per_replicate"],
            "replicates_requested": partial_output["replicates_requested"],
            "common_successes": partial_output["replicates_successful"],
            "failed_replicates": partial_output["replicates_failed"],
            "failure_reason_family": "INVALID_DENOMINATOR:zero_retained_denominator",
            "no_reroll": True,
            "output_canonical_sha256": hashlib.sha256(canonical_bytes(partial_output)).hexdigest(),
        },
    }
    fail(canonical_bytes(partial_actual) != canonical_bytes(partial_expected), "partial fixed receipt mismatch")
    fail(
        len(partial_payload["prompt_frame"]) != 50
        or len(partial_payload["records"]) != 3
        or partial_output["frame"]["prompt_sample_size_per_replicate"] != 50
        or partial_output["replicates_successful"] != 9537
        or partial_output["replicates_failed"] != 463
        or partial_points != {"broken": 1 / 3, "unsafe": 1 / 3, "refusal": 1 / 3, "safe": 0.0},
        "partial production-entry witness changed",
    )

    fail(tp_actual.get("prompt_phase_two", {}).get("block_id") != "p2-two-phase-prompt", "prompt two-phase coverage missing")
    fail(tp_actual.get("vector_aware", {}).get("block_id") != "p2-two-phase-vector", "vector-aware coverage missing")
    fail(tp_actual.get("completion_boundary") != {"9499": "FAIL", "9500": "PASS"}, "two-phase completion boundary changed")
    fail(
        tp_actual["prompt_phase_two"].get("member_order") != ["P2-U(A)", "P2-B(T)"]
        or tp_actual["vector_aware"].get("member_order") != ["P2-U(A)", "P2-B(T)"],
        "two-phase members do not share fixed family order",
    )
    fail(len(tp_actual.get("rng_byte_golden", {}).get("cases", [])) < 3, "two-phase RNG golden coverage missing")
    fail(
        tp_actual.get("rng_byte_golden", {}).get("scripted_rejection", {}).get("words_consumed") != 3,
        "two-phase rejection consumption golden changed",
    )

    expected_retained_blocks = {
        "k1": "k1-profile",
        "harmful_clean": "harmful-clean-prompt",
        "benign_broken": "benign-broken-prompt",
    }
    for key, block_id in expected_retained_blocks.items():
        fail(retained_actual.get(key, {}).get("block_id") != block_id, f"retained block coverage changed: {key}")
        fail(retained_actual.get(key, {}).get("replicates") != [10000, 9500], f"retained coverage/count changed: {key}")
    fail(len(retained_actual["k1"].get("statistics", {})) != 16, "K1 four-cell/four-class coverage changed")
    fail(len(retained_actual["harmful_clean"].get("statistics", {})) != 4, "harmful-clean four-class coverage changed")
    fail(set(retained_actual["benign_broken"].get("statistics", {})) != {"RD_benign_broken"}, "benign RD coverage changed")
    fail(
        retained_actual["k1"].get("row_weight") != "prompt_multiplicity*vector_multiplicity",
        "K1 product multiplicity changed",
    )
    fail(
        retained_actual["benign_broken"].get("operation_order")
        != "20-vector average within complete prompt, then prompt bootstrap",
        "benign vector-average-before-bootstrap changed",
    )
    zero_statistics = retained_actual.get("zero_sd", {}).get("statistics", {})
    fail(
        not zero_statistics
        or any(item.get("degenerate_bootstrap") is not True for item in zero_statistics.values()),
        "zero-SD degenerate interval coverage missing",
    )
    failure_by_id = {item["case_id"]: item for item in retained_failure_actual["results"]}
    required_retained_failures = {
        "identity_collision_precedes_order_and_membership", "record_collision_precedes_frame_order",
        "insufficient_prompt_units",
        "invalid_profile_denominator", "common_success_9499_fails",
        "common_success_9500_passes", "nonfinite_point", "member_id_forbidden_in_sync",
        "replicate_zero_forbidden", "wrong_block_family_forbidden",
    }
    fail(set(failure_by_id) != required_retained_failures, "retained failure coverage set changed")
    fail(
        failure_by_id.get("common_success_9499_fails", {}).get("status") != "NON_ESTIMABLE",
        "retained 9499 boundary changed",
    )
    fail(
        failure_by_id.get("common_success_9500_passes", {}).get("status") != "EXPECTED_PASS",
        "retained 9500 boundary changed",
    )
    fail(len(retained_actual.get("rng_success", {}).get("cases", [])) != 4, "retained RNG golden coverage changed")
    fail(
        retained_actual.get("rng_success", {}).get("scripted_rejection", {}).get("words_consumed") != 2,
        "retained rejection consumption golden changed",
    )

    zero_hash = "0" * 64
    tp_units = [
        two_phase.prompt_sync_unit("p2-two-phase-prompt", zero_hash, "synthetic-cat-A"),
        two_phase.phase_two_sync_unit("p2-two-phase-prompt", zero_hash, "synthetic-h-A"),
        two_phase.vector_sync_unit("p2-two-phase-vector", zero_hash, "V_confirm"),
    ]
    expected_tp_units = [
        '{"axis":"prompt-stratum","family":"p2-two-phase-prompt","frame_sha256":"' + zero_hash + '","stratum_id":"synthetic-cat-A"}',
        '{"axis":"phase2-stratum","family":"p2-two-phase-prompt","frame_sha256":"' + zero_hash + '","stratum_id":"synthetic-h-A"}',
        '{"axis":"vector","entity_id":"V_confirm","family":"p2-two-phase-vector","frame_sha256":"' + zero_hash + '"}',
    ]
    fail(tp_units != expected_tp_units, "two-phase exact sync JSON changed")
    expected_tp_rng = [
        ("p2-two-phase-prompt", "9461d2b63f3ac7f1bf3b8c017a373ac5", ["fa12c0e694322a79", "8239468351dd1c4e", "970c23339197f925"]),
        ("p2-two-phase-prompt", "0a691001a35d43f243901fc0a54c2445", ["3dd10872d2807f20", "ca4047750b573642", "6a9fd41274762578"]),
        ("p2-two-phase-vector", "de7f948d7d8fe115060d487d8c552de9", ["10be11f04aef52da", "0bde819027c940e2", "97c2917aca59f76d"]),
    ]
    for unit, (block, seed_hex, word_hex) in zip(tp_units, expected_tp_rng):
        payload, seed = two_phase.seed_material(block, unit, 1)
        expected_payload = f"v3.5-rc2|master=42|block={block}|sync_unit={unit}|rep=000001"
        fail(payload != expected_payload or seed.hex() != seed_hex, "two-phase seed golden changed")
        rng = two_phase.Sha256CounterRng(seed)
        actual_words = [f"{rng.uint64():016x}" for _ in range(3)]
        fail(actual_words != word_hex or rng.counter != 3, "two-phase counter-word order changed")

    retained_cases = [
        ("k1-profile", "prompt", "k1-profile", "4c3a8b05298e5cd9faf234d479d22bc5", ["b236135826055f60", "6085ccb282b784a4", "a29589b7f34d3ffc"]),
        ("k1-profile", "vector", "k1-profile", "bf4f2ca19625e29417bf08ef57f6af58", ["6a940f30cf03a783", "443424dc118d0f11", "91a0ece56426ef7f"]),
        ("harmful-clean", "prompt", "harmful-clean-prompt", "a239961ced58e286f0a12e0a1f6885a2", ["da46a2745c1a3d3a", "e657f6f59646b8db", "4dc383cb21d6cef4"]),
        ("benign-broken", "prompt", "benign-broken-prompt", "62cdaf565e30140596c84117fe7d5873", ["f9cf847d8481c599", "6f51365a339c511a", "e19db3db5de27c10"]),
    ]
    for family, axis, block, seed_hex, word_hex in retained_cases:
        unit = retained.sync_unit_id(family=family, axis=axis, frame_hash=zero_hash)
        expected_unit = '{"axis":"' + axis + '","entity_id":"sha256:' + zero_hash + '","family":"' + family + '"}'
        fail(unit != expected_unit, f"retained exact sync JSON changed: {family}/{axis}")
        seed = retained.seed_bytes(block, unit, 1)
        fail(seed.hex() != seed_hex, f"retained seed golden changed: {family}/{axis}")
        rng = retained.Sha256CounterRng(seed)
        actual_words = [f"{rng.uint64():016x}" for _ in range(3)]
        fail(actual_words != word_hex or rng.counter != 3, f"retained counter-word order changed: {family}/{axis}")

    try:
        two_phase.sync_unit_id({"axis": "prompt-stratum", "family": "p2-two-phase-prompt", "member_id": "P2-U(A)"})
    except two_phase.NonEstimable as error:
        fail(
            error.status != "INPUT_INVALID_NON_ESTIMABLE" or error.reason_code != "MEMBER_ID_IN_SYNC_UNIT",
            "two-phase member_id rejection code changed",
        )
    else:
        raise VerificationError("two-phase permits member_id in sync_unit_id")
    try:
        retained.sync_unit_id(
            family="k1-profile", axis="prompt", frame_hash=zero_hash, member_id="P2_A_all"
        )
    except retained.RetainedBootstrapError as error:
        fail(
            error.code != "RNG_IDENTITY_INVALID"
            or error.detail != "member identity must not enter sync_unit_id",
            "retained member_id rejection code changed",
        )
    else:
        raise VerificationError("retained reference permits member_id in sync_unit_id")

    try:
        two_phase.require_common_success(9499)
    except two_phase.NonEstimable as error:
        fail(
            error.status != "RESAMPLING_COMPLETION_NON_ESTIMABLE"
            or error.reason_code != "COMMON_SUCCESSES_BELOW_9500",
            "two-phase 9499 failure code changed",
        )
    else:
        raise VerificationError("two-phase accepts 9499 common successes")
    fail(two_phase.require_common_success(9500) != 9500, "two-phase rejects 9500 common successes")


def verify_synthetic_fixtures() -> int:
    fixtures = [path for path in WRITE_DIR.rglob("*.json") if "fixtures" in path.parts]
    fail(not fixtures, "no amendment fixtures found")
    for path in fixtures:
        document = load_json(path)
        fail(not isinstance(document, dict), f"fixture is not an object: {repo_path(path)}")
        fail(document.get("synthetic_data") is not True, f"fixture lacks synthetic_data=true: {repo_path(path)}")
    return len(fixtures)


def verify_scope(config: dict[str, Any]) -> int:
    amendment_text = AMENDMENT_DOC.read_text(encoding="utf-8")
    fail("DESIGN-FREEZE-PASS" in amendment_text, "amendment may not announce DESIGN-FREEZE-PASS")
    fail("DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED" not in amendment_text, "required amendment status missing")

    active_patterns = {
        "model-based inference registration": r'(?i)(?:block_id|algorithm|family)\s*[:=]\s*["\'](?:p2-model|model-based|population-integration)',
        "K2 registration": r'(?im)^\s*(?:#{1,6}\s+|["\']block_id["\']\s*:\s*["\'])K2\b',
        "V2 registration": r'(?im)^\s*(?:#{1,6}\s+|["\']block_id["\']\s*:\s*["\'])V2\b',
        "stochastic generation enabled": r'(?i)(?:do_sample|stochastic(?:_decoding)?)\s*["\']?\s*[:=]\s*(?:true|True)',
        "scope flag enabled": r'(?i)(?:power|coverage|selector|phase_confirmation|rendering_2x2|attention)\w*\s*["\']?\s*[:=]\s*(?:true|True)',
    }
    scan_paths = [AMENDMENT_DOC, VERIFIER_CONFIG]
    scan_paths.extend(path for path in COMPLETION_REPORTS if path.is_file())
    scan_paths.extend(path for path in WRITE_DIR.rglob("*.md"))
    scan_paths.extend(path for path in WRITE_DIR.rglob("*.json") if "fixtures" not in path.parts)
    scan_paths.extend(path for path in SCRIPT_DIR.rglob("*.py"))
    scanned = 0
    for path in sorted(set(scan_paths)):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".md":
            fail("DESIGN-FREEZE-PASS" in text, f"final freeze verdict appears in amendment prose: {repo_path(path)}")
        for label, pattern in active_patterns.items():
            fail(re.search(pattern, text) is not None, f"prohibited active scope found ({label}) in {repo_path(path)}")
        scanned += 1
    fail(config["fixed_scope"] != EXPECTED_SCOPE, "fixed scope changed")
    return scanned


def verify_budget() -> dict[str, int]:
    protocol = (ROOT / "writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc2.md").read_text(encoding="utf-8")
    try:
        budget_section = protocol.split("### 11.1 Logical generation and judge budget", 1)[1].split(
            "### 11.2 Actual call accounting", 1
        )[0]
    except IndexError as exc:
        raise VerificationError("base protocol budget section boundary changed") from exc
    expected_rows = {
        "Qwen A/T/H support": (900, 900),
        "P2 four cells": (4000, 4000),
        "K1 reuse": (0, 0),
        "harmful clean": (50, 50),
        "benign T-steered": (600, 600),
        "benign clean": (30, 30),
        "**total**": (5580, 5580),
    }
    parsed: dict[str, tuple[int, int]] = {}
    for line in budget_section.splitlines():
        if not line.startswith("|"):
            continue
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        if len(columns) != 4 or columns[0] not in expected_rows:
            continue
        try:
            parsed[columns[0]] = tuple(int(item.replace("*", "").replace(",", "")) for item in columns[2:4])
        except ValueError as exc:
            raise VerificationError(f"budget row is not numeric: {columns[0]}") from exc
    fail(parsed != expected_rows, f"base protocol budget table changed: {parsed!r}")
    fail(sum(value[0] for key, value in parsed.items() if key != "**total**") != 5580, "generation budget arithmetic failed")
    fail(sum(value[1] for key, value in parsed.items() if key != "**total**") != 5580, "judge budget arithmetic failed")
    human = re.search(r"^human response items = ([0-9,]+)$", protocol, flags=re.MULTILINE)
    fail(human is None or int(human.group(1).replace(",", "")) != 720, "human budget changed")
    return {"logical_generation": 5580, "first_pass_scheduled_judge": 5580, "human_items": 720}


def verify_all() -> dict[str, Any]:
    config = verify_config()
    report = {
        "schema_version": "v3.5-rc2-binding-amendment-static-verification-v1",
        "amendment_id": AMENDMENT_ID,
        "status": "DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED",
        "formal_data_used": False,
        "no_scope_expansion": True,
        "base_files_unchanged": verify_base_immutability(),
        "manifests": verify_manifests(),
        "references": verify_references(),
        "synthetic_fixture_files": verify_synthetic_fixtures(),
        "scope_files_scanned": verify_scope(config),
        "budget": verify_budget(),
    }
    return report


def main() -> int:
    try:
        report = verify_all()
        print(json.dumps(report, ensure_ascii=True, allow_nan=False, sort_keys=True))
        print("AMENDMENT_STATIC_VERIFICATION_PASS")
        return 0
    except (OSError, KeyError, TypeError, ValueError, VerificationError) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}, ensure_ascii=True, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
