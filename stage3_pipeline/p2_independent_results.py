"""Read-only materialization of the amended independent T/H P2 run.

This module deliberately stops at raw, traceable endpoint members.  It does
not import or call a statistical implementation.  The source run is
reconciled by the amended runner before any pair is materialized.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import PipelineError, canonical_json, canonical_sha256, file_sha256
from .execution import OutputStore, TERMINAL_DISPOSITIONS
from .offline_assets import AssetError, strict_json_loads
from .p2_independent_runner import (
    AMENDMENT,
    AMENDMENT_ID,
    CELLS,
    DEFAULT_CONFIG,
    ENDPOINT_ORDER,
    IDENTITY_COUNT,
    OLD_P2_RUN,
    OLD_P2_MATERIALIZED,
    PreparedIndependentP2,
    prepare_independent_p2,
    reconcile_independent_stage,
    validate_independent_registry,
)


FORMAL_AMENDED_RUN_DIRECTORY = Path(
    "/data/goodtaste_workspace/paper1_stage3_runs/"
    "p2-qwen25-amended-th-paper-20260822T051005Z-v2"
)
OUTPUT_FILENAME = "p2_independent_raw_result.json"
SCHEMA_VERSION = "paper1-stage3-p2-independent-th-result-materialization-v1"
P2_CELL_COUNT = 1_000
EXPECTED_TERMINAL_PARTITION = {
    terminal: (3_942 if terminal == "COMPLETED_PARSED" else 58 if terminal == "TERMINAL_JUDGE_FAILURE" else 0)
    for terminal in TERMINAL_DISPOSITIONS
}

_CELL_SPECS = {
    cell: {
        "anchor": anchor,
        "estimator": estimator,
        "arm": "all-token" if cell.endswith("_all") else "content-token",
    }
    for cell, anchor, estimator in CELLS
}
_MEMBER_SPECS = tuple(dict(endpoint) for endpoint in ENDPOINT_ORDER)
_HARMFUL_LABELS = {"broken", "unsafe", "refusal", "safe"}
_SOURCE_DOCUMENTS = (
    "logical_registry.json",
    "p2_independent_identities.json",
    "generation_records.json",
    "judge_records.json",
    "response_records.json",
    "execution_dispositions.json",
    "p2_independent_ledger.json",
    "execution_identity.json",
)
_RECORD_DOCUMENT_SCHEMAS = {
    "p2_independent_identities.json": "paper1-stage3-p2-independent-identity-set-v1",
    "generation_records.json": "paper1-stage3-p2-independent-generation-set-v1",
    "judge_records.json": "paper1-stage3-p2-independent-judge-set-v1",
    "response_records.json": "paper1-stage3-p2-independent-response-set-v1",
    "execution_dispositions.json": "paper1-stage3-p2-independent-disposition-set-v1",
}


class P2IndependentResultInputInvalid(ValueError):
    """A source run or requested result violates the amended contract."""

    code = "P2_INDEPENDENT_RESULT_INPUT_INVALID"


def _invalid(detail: str) -> None:
    raise P2IndependentResultInputInvalid(f"{P2IndependentResultInputInvalid.code}:{detail}")


def _strict_object(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        _invalid(f"SOURCE_FILE_NOT_REGULAR:{path.name}")
    try:
        value = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, AssetError, ValueError) as exc:
        _invalid(f"SOURCE_JSON:{path.name}:{exc}")
    if not isinstance(value, dict):
        _invalid(f"SOURCE_DOCUMENT_NOT_OBJECT:{path.name}")
    return value


def _record_document(
    document: Mapping[str, Any], *, name: str, schema_version: str, count: int
) -> tuple[Mapping[str, Any], ...]:
    if set(document) != {"schema_version", "record_count", "records"}:
        _invalid(f"{name}:DOCUMENT_FIELDS")
    records = document.get("records")
    if (
        document.get("schema_version") != schema_version
        or type(document.get("record_count")) is not int
        or document["record_count"] != count
        or not isinstance(records, list)
        or len(records) != count
        or any(not isinstance(item, Mapping) for item in records)
    ):
        _invalid(f"{name}:DOCUMENT_METADATA")
    return tuple(dict(item) for item in records)


@dataclass(frozen=True)
class LoadedIndependentRun:
    run_directory: Path
    registry: Mapping[str, Any]
    identities: tuple[Mapping[str, Any], ...]
    generations: tuple[Mapping[str, Any], ...]
    judges: tuple[Mapping[str, Any], ...]
    responses: tuple[Mapping[str, Any], ...]
    dispositions: tuple[Mapping[str, Any], ...]
    ledger: Mapping[str, Any]
    execution_identity: Mapping[str, Any]
    file_sha256: Mapping[str, str]


@dataclass(frozen=True)
class ValidatedIndependentRun:
    prepared: PreparedIndependentP2
    loaded: LoadedIndependentRun
    reconciliation: Mapping[str, Any]


def _source_directory(run_directory: Path) -> Path:
    if not isinstance(run_directory, Path):
        _invalid("RUN_DIRECTORY_NOT_PATH")
    if run_directory.is_symlink() or not run_directory.is_dir():
        _invalid(f"RUN_DIRECTORY_NOT_DIRECTORY:{run_directory}")
    return run_directory.resolve()


def _fixed_run_directory(run_directory: Path) -> Path:
    source = _source_directory(run_directory)
    if source != FORMAL_AMENDED_RUN_DIRECTORY.resolve():
        _invalid(f"RUN_DIRECTORY_NOT_FIXED_AMENDED_P2:{source}")
    return source


def load_independent_run(run_directory: Path) -> LoadedIndependentRun:
    """Load only the amended run's immutable JSON documents."""
    source = _fixed_run_directory(run_directory)
    docs = {name: _strict_object(source / name) for name in _SOURCE_DOCUMENTS}
    registry = docs["logical_registry.json"]
    if set(registry) != {
        "schema_version", "protocol_version", "amendment_id", "identity_count",
        "records", "registry_sha256",
    }:
        _invalid("LOGICAL_REGISTRY_FIELDS")
    registry_records = registry.get("records")
    if (
        registry.get("schema_version") != "paper1-stage3-p2-independent-logical-registry-v1"
        or registry.get("amendment_id") != AMENDMENT_ID
        or type(registry.get("identity_count")) is not int
        or registry["identity_count"] != IDENTITY_COUNT
        or not isinstance(registry_records, list)
        or len(registry_records) != IDENTITY_COUNT
        or any(not isinstance(item, Mapping) for item in registry_records)
        or registry.get("registry_sha256") != canonical_sha256(registry_records)
    ):
        _invalid("LOGICAL_REGISTRY_METADATA")
    identities = _record_document(
        docs["p2_independent_identities.json"],
        name="p2_independent_identities.json",
        schema_version=_RECORD_DOCUMENT_SCHEMAS["p2_independent_identities.json"],
        count=IDENTITY_COUNT,
    )
    generations = _record_document(
        docs["generation_records.json"], name="generation_records.json",
        schema_version=_RECORD_DOCUMENT_SCHEMAS["generation_records.json"], count=IDENTITY_COUNT,
    )
    judges = _record_document(
        docs["judge_records.json"], name="judge_records.json",
        schema_version=_RECORD_DOCUMENT_SCHEMAS["judge_records.json"], count=IDENTITY_COUNT,
    )
    responses = _record_document(
        docs["response_records.json"], name="response_records.json",
        schema_version=_RECORD_DOCUMENT_SCHEMAS["response_records.json"], count=IDENTITY_COUNT,
    )
    dispositions = _record_document(
        docs["execution_dispositions.json"], name="execution_dispositions.json",
        schema_version=_RECORD_DOCUMENT_SCHEMAS["execution_dispositions.json"], count=IDENTITY_COUNT,
    )
    return LoadedIndependentRun(
        run_directory=source,
        registry=registry,
        identities=identities,
        generations=generations,
        judges=judges,
        responses=responses,
        dispositions=dispositions,
        ledger=docs["p2_independent_ledger.json"],
        execution_identity=docs["execution_identity.json"],
        file_sha256={name: file_sha256(source / name) for name in _SOURCE_DOCUMENTS},
    )


def _index_by_id(records: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for item in records:
        logical_id = item.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in indexed:
            _invalid(f"{label}:MISSING_OR_DUPLICATE_LOGICAL_ID")
        indexed[logical_id] = item
    return indexed


def _validate_registry_lineage(prepared: PreparedIndependentP2, loaded: LoadedIndependentRun) -> None:
    validation = validate_independent_registry(prepared.registry, base=prepared.base)
    if validation["identity_count"] != IDENTITY_COUNT or validation["cell_identity_counts"] != {
        cell: P2_CELL_COUNT for cell in _CELL_SPECS
    }:
        _invalid("CANONICAL_REGISTRY_SHAPE")
    expected = _index_by_id(prepared.rows, "prepared identities")
    stored = _index_by_id(loaded.registry["records"], "logical registry")
    rows = _index_by_id(loaded.identities, "stored identities")
    if set(stored) != set(expected) or set(rows) != set(expected):
        _invalid("IDENTITY_LOGICAL_ID_PARTITION")
    for logical_id in expected:
        expected_identity = expected[logical_id]["identity"]
        for actual, label in ((stored[logical_id], "registry"), (rows[logical_id], "identity")):
            if set(actual) != {"logical_id", "identity"} or actual["logical_id"] != logical_id:
                _invalid(f"{label}:IDENTITY_RECORD_FIELDS")
            if canonical_json(actual["identity"]) != canonical_json(expected_identity):
                _invalid(f"{label}:IDENTITY_LINEAGE_MISMATCH:{logical_id}")


def _validate_execution_identity(
    prepared: PreparedIndependentP2, loaded: LoadedIndependentRun, reconciliation: Mapping[str, Any]
) -> None:
    identity = loaded.execution_identity
    required = {
        "schema_version", "amendment_id", "run_id", "run_mode", "fake_backend",
        "paper_result_eligible", "formal_experiment_run", "old_p2_run", "p1_run",
        "support_run", "k1_run", "support_run_id", "old_p2_run_directory",
        "canonical_registry_sha256", "ledger_sha256", "runner_code_sha256",
        "config_sha256", "amendment_sha256", "behavior_lifecycle", "judge_lifecycle",
        "offline_guard_report",
    }
    if set(identity) != required:
        _invalid("EXECUTION_IDENTITY_FIELDS")
    expected = {
        "schema_version": "paper1-stage3-p2-independent-execution-v1",
        "amendment_id": AMENDMENT_ID,
        "run_id": loaded.run_directory.name,
        "run_mode": "paper",
        "fake_backend": False,
        "paper_result_eligible": False,
        "formal_experiment_run": True,
        "old_p2_run": False,
        "p1_run": False,
        "support_run": False,
        "k1_run": False,
        "support_run_id": prepared.base.support_execution_identity["run_id"],
        "old_p2_run_directory": str(OLD_P2_RUN),
        "canonical_registry_sha256": loaded.registry["registry_sha256"],
        "ledger_sha256": canonical_sha256(dict(reconciliation)),
        "config_sha256": file_sha256(prepared.config_path),
        "amendment_sha256": file_sha256(AMENDMENT),
    }
    from .p2_independent_runner import ROOT as RUNNER_ROOT
    runner_path = RUNNER_ROOT / "stage3_pipeline/p2_independent_runner.py"
    expected["runner_code_sha256"] = file_sha256(runner_path)
    for field, value in expected.items():
        if identity.get(field) != value or type(identity.get(field)) is not type(value):
            _invalid(f"EXECUTION_IDENTITY_MISMATCH:{field}")
    if identity.get("offline_guard_report", {}).get("blocked_attempt_count") != 0:
        _invalid("OFFLINE_GUARD_BLOCKED_OPERATION")


def _validate_formal_reconciliation(
    loaded: LoadedIndependentRun, reconciliation: Mapping[str, Any]
) -> None:
    if dict(loaded.ledger) != dict(reconciliation):
        _invalid("STORED_LEDGER_DIFFERS_FROM_RECONCILIATION")
    if (
        reconciliation.get("identity_count") != IDENTITY_COUNT
        or reconciliation.get("terminal_count") != IDENTITY_COUNT
        or reconciliation.get("cell_identity_counts") != {cell: P2_CELL_COUNT for cell in _CELL_SPECS}
        or reconciliation.get("endpoint_order") != [dict(item) for item in ENDPOINT_ORDER]
        or reconciliation.get("terminal_partition") != EXPECTED_TERMINAL_PARTITION
        or reconciliation.get("matched_sets", {}).get("M_T", {}).get("valid_pair_count") != 976
        or reconciliation.get("matched_sets", {}).get("M_H", {}).get("valid_pair_count") != 966
    ):
        _invalid("FORMAL_RECONCILIATION_MISMATCH")
    if reconciliation.get("fake_backend") is not False or reconciliation.get("formal_experiment_run") is not True:
        _invalid("FORMAL_BACKEND_FLAGS_MISMATCH")
    if any(reconciliation.get(field) is not False for field in ("old_p2_run", "p1_run", "support_run", "k1_run")):
        _invalid("HISTORICAL_SCOPE_FLAG_MISMATCH")


def validate_independent_run(
    run_directory: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
    prepared: PreparedIndependentP2 | None = None,
) -> ValidatedIndependentRun:
    """Revalidate registry, lineage, terminal partition, and amended scope."""
    try:
        loaded = load_independent_run(run_directory)
        prepared_value = prepared if prepared is not None else prepare_independent_p2(config_path)
        _validate_registry_lineage(prepared_value, loaded)
        reconciliation = reconcile_independent_stage(
            prepared_value,
            generation_records=loaded.generations,
            judge_records=loaded.judges,
            response_records=loaded.responses,
            dispositions=loaded.dispositions,
            expected_fake_backend=False,
        )
        _validate_formal_reconciliation(loaded, reconciliation)
        _validate_execution_identity(prepared_value, loaded, reconciliation)
        if loaded.execution_identity.get("amendment_id") != AMENDMENT_ID:
            _invalid("AMENDMENT_ID_MISMATCH")
        return ValidatedIndependentRun(prepared_value, loaded, reconciliation)
    except P2IndependentResultInputInvalid:
        raise
    except (PipelineError, KeyError, TypeError, ValueError) as exc:
        _invalid(f"AMENDED_RECONCILIATION:{exc}")


def _paired_difference(all_value: int, content_value: int, *, member_id: str, pair_id: str) -> int:
    if type(all_value) is not int or all_value not in {0, 1}:
        _invalid(f"INVALID_BINARY_OUTCOME:{member_id}:{pair_id}:all")
    if type(content_value) is not int or content_value not in {0, 1}:
        _invalid(f"INVALID_BINARY_OUTCOME:{member_id}:{pair_id}:content")
    difference = all_value - content_value
    if difference not in {-1, 0, 1}:
        _invalid(f"DIFFERENCE_OUT_OF_RANGE:{member_id}:{pair_id}")
    return difference


def _canonical_pair_topology(
    canonical_rows: Sequence[Mapping[str, Any]], expected_cell_count: int
) -> dict[str, dict[tuple[str, str], tuple[str, Mapping[str, Any]]]]:
    if type(expected_cell_count) is not int or expected_cell_count < 1:
        _invalid("EXPECTED_CELL_COUNT_INVALID")
    by_cell: dict[str, dict[tuple[str, str], tuple[str, Mapping[str, Any]]]] = {
        cell: {} for cell in _CELL_SPECS
    }
    seen_ids: set[str] = set()
    for index, row in enumerate(canonical_rows):
        if not isinstance(row, Mapping) or not isinstance(row.get("identity"), Mapping):
            _invalid(f"CANONICAL_ROW_NOT_IDENTITY:{index}")
        logical_id = row.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in seen_ids:
            _invalid(f"DUPLICATE_CANONICAL_LOGICAL_ID:{logical_id}")
        seen_ids.add(logical_id)
        identity = row["identity"]
        cell = identity.get("block")
        if cell not in _CELL_SPECS:
            _invalid(f"UNKNOWN_CANONICAL_CELL:{cell}")
        spec = _CELL_SPECS[cell]
        if identity.get("anchor") != spec["anchor"] or identity.get("estimator") != spec["estimator"]:
            _invalid(f"CANONICAL_CELL_IDENTITY_MISMATCH:{logical_id}")
        prompt_id, vector_id = identity.get("prompt_id"), identity.get("vector_id")
        if not isinstance(prompt_id, str) or not prompt_id or not isinstance(vector_id, str) or not vector_id:
            _invalid(f"CANONICAL_PAIR_FIELDS:{logical_id}")
        key = (prompt_id, vector_id)
        if key in by_cell[cell]:
            _invalid(f"DUPLICATE_CANONICAL_PAIR:{cell}:{prompt_id}:{vector_id}")
        by_cell[cell][key] = (logical_id, identity)
    counts = {cell: len(items) for cell, items in by_cell.items()}
    if counts != {cell: expected_cell_count for cell in _CELL_SPECS}:
        _invalid(f"CANONICAL_CELL_COUNTS:{counts}")
    for endpoint in _MEMBER_SPECS:
        if set(by_cell[endpoint["all_cell"]]) != set(by_cell[endpoint["content_cell"]]):
            _invalid(f"INCOMPLETE_CANONICAL_PAIRING:{endpoint['member_id']}")
    return by_cell


def _arm_trace(
    record: Mapping[str, Any], *, generation: Mapping[str, Any] | None = None,
    judge: Mapping[str, Any] | None = None, disposition: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    # Keep all hashes needed to audit both arms without retaining model payloads.
    trace = {
        "logical_id": record.get("logical_id"),
        "cell": record.get("cell"),
        "anchor": record.get("anchor"),
        "estimator": record.get("estimator"),
        "prompt_id": record.get("prompt_id"),
        "vector_id": record.get("vector_id"),
        "identity_sha256": record.get("identity_sha256"),
        "generation_record_sha256": record.get("generation_record_sha256"),
        "judge_record_sha256": record.get("judge_record_sha256"),
        "response_record_sha256": record.get("record_sha256"),
        "terminal_status": record.get("terminal_status"),
        "missingness_code": record.get("missingness_code"),
        "retained": record.get("retained"),
        "label": record.get("label"),
        "generation_lineage": None,
        "judge_lineage": None,
        "disposition_lineage": None,
    }
    if generation is not None:
        trace["generation_lineage"] = {
            "logical_id": generation.get("logical_id"),
            "identity_sha256": generation.get("identity_sha256"),
            "record_sha256": generation.get("record_sha256"),
            "terminal_status": generation.get("terminal_status"),
        }
    if judge is not None:
        trace["judge_lineage"] = {
            "logical_id": judge.get("logical_id"),
            "identity_sha256": judge.get("identity_sha256"),
            "generation_record_sha256": judge.get("generation_record_sha256"),
            "record_sha256": judge.get("record_sha256"),
            "terminal_status": judge.get("terminal_status"),
        }
    if disposition is not None:
        trace["disposition_lineage"] = {
            "logical_id": disposition.get("logical_id"),
            "identity_sha256": disposition.get("identity_sha256"),
            "response_record_sha256": disposition.get("response_record_sha256"),
            "terminal_disposition": disposition.get("terminal_disposition"),
        }
    return trace


def _response_index(
    response_records: Sequence[Mapping[str, Any]],
    identity_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for index, response in enumerate(response_records):
        if not isinstance(response, Mapping):
            _invalid(f"RESPONSE_NOT_OBJECT:{index}")
        logical_id = response.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id or logical_id in indexed:
            _invalid(f"DUPLICATE_RESPONSE_LOGICAL_ID:{logical_id}")
        identity = identity_by_id.get(logical_id)
        if identity is None:
            _invalid(f"UNKNOWN_RESPONSE_LOGICAL_ID:{logical_id}")
        expected = {
            "cell": identity["block"],
            "anchor": identity["anchor"],
            "estimator": identity["estimator"],
            "arm": _CELL_SPECS[identity["block"]]["arm"],
            "prompt_id": identity["prompt_id"],
            "vector_id": identity["vector_id"],
            "pair_id": f"{identity['anchor']}|{identity['prompt_id']}|{identity['vector_id']}",
        }
        for field, value in expected.items():
            if response.get(field) != value:
                _invalid(f"RESPONSE_IDENTITY_MISMATCH:{logical_id}:{field}")
        terminal = response.get("terminal_status")
        if terminal not in TERMINAL_DISPOSITIONS or terminal == "UNATTEMPTED_DUE_INTEGRITY_BLOCK":
            _invalid(f"RESPONSE_TERMINAL_INVALID:{logical_id}")
        if terminal == "COMPLETED_PARSED":
            if response.get("retained") is not True or response.get("label") not in _HARMFUL_LABELS:
                _invalid(f"ANALYZABLE_RESPONSE_INVALID:{logical_id}")
        elif response.get("retained") is not False or response.get("label") is not None:
            _invalid(f"FAILED_RESPONSE_RELABELED:{logical_id}")
        indexed[logical_id] = response
    if set(indexed) != set(identity_by_id):
        _invalid(
            f"RESPONSE_ID_PARTITION:missing={len(set(identity_by_id)-set(indexed))}:unexpected={len(set(indexed)-set(identity_by_id))}"
        )
    return indexed


def build_independent_raw_members(
    canonical_rows: Sequence[Mapping[str, Any]],
    response_records: Sequence[Mapping[str, Any]],
    *,
    generation_records: Sequence[Mapping[str, Any]] = (),
    judge_records: Sequence[Mapping[str, Any]] = (),
    dispositions: Sequence[Mapping[str, Any]] = (),
    expected_cell_count: int = P2_CELL_COUNT,
) -> dict[str, Any]:
    """Build P2-U(T), then P2-B(H), by prompt/vector identity pairs."""
    by_cell = _canonical_pair_topology(canonical_rows, expected_cell_count)
    identity_by_id = {
        logical_id: identity
        for pairs in by_cell.values() for logical_id, identity in pairs.values()
    }
    responses = _response_index(response_records, identity_by_id)
    generations = _index_by_id(generation_records, "generation_records") if generation_records else {}
    judges = _index_by_id(judge_records, "judge_records") if judge_records else {}
    disposition_by_id = _index_by_id(dispositions, "dispositions") if dispositions else {}
    cell_counts: dict[str, dict[str, Any]] = {}
    for cell, pairs in by_cell.items():
        records = [responses[logical_id] for logical_id, _ in pairs.values()]
        terminal_counts = {terminal: sum(item.get("terminal_status") == terminal for item in records) for terminal in TERMINAL_DISPOSITIONS if terminal != "UNATTEMPTED_DUE_INTEGRITY_BLOCK"}
        cell_counts[cell] = {
            "scheduled_record_count": len(records),
            "completed_parsed_record_count": terminal_counts["COMPLETED_PARSED"],
            "terminal_failure_record_count": len(records) - terminal_counts["COMPLETED_PARSED"],
            "matched_record_count": 0,
            "excluded_record_count": 0,
            "terminal_status_counts": terminal_counts,
        }
    members: list[dict[str, Any]] = []
    for spec in _MEMBER_SPECS:
        records: list[dict[str, Any]] = []
        missing_pairs: list[dict[str, Any]] = []
        all_pairs = by_cell[spec["all_cell"]]
        content_pairs = by_cell[spec["content_cell"]]
        for prompt_id, vector_id in sorted(all_pairs, key=lambda item: (item[0], item[1])):
            all_id, _ = all_pairs[(prompt_id, vector_id)]
            content_id, _ = content_pairs[(prompt_id, vector_id)]
            all_response, content_response = responses[all_id], responses[content_id]
            pair_id = f"{spec['anchor']}|{prompt_id}|{vector_id}"
            all_trace = _arm_trace(
                all_response, generation=generations.get(all_id), judge=judges.get(all_id), disposition=disposition_by_id.get(all_id)
            )
            content_trace = _arm_trace(
                content_response, generation=generations.get(content_id), judge=judges.get(content_id), disposition=disposition_by_id.get(content_id)
            )
            if all_response.get("terminal_status") != "COMPLETED_PARSED" or content_response.get("terminal_status") != "COMPLETED_PARSED":
                missing_pairs.append({
                    "pair_id": pair_id, "prompt_id": prompt_id, "vector_id": vector_id,
                    "anchor": spec["anchor"], "arms": {"all": all_trace, "content": content_trace},
                })
                continue
            all_value = int(all_response["label"] == spec["outcome"])
            content_value = int(content_response["label"] == spec["outcome"])
            difference = _paired_difference(all_value, content_value, member_id=spec["member_id"], pair_id=pair_id)
            records.append({
                "pair_id": pair_id,
                "prompt_id": prompt_id,
                "vector_id": vector_id,
                "anchor": spec["anchor"],
                "outcome": spec["outcome"],
                "all_value": all_value,
                "content_value": content_value,
                "difference": difference,
                "arms": {"all": all_trace, "content": content_trace},
            })
        matched_count, missing_count = len(records), len(missing_pairs)
        if matched_count + missing_count != expected_cell_count:
            _invalid(f"PAIR_ACCOUNTING_MISMATCH:{spec['member_id']}")
        for cell in (spec["all_cell"], spec["content_cell"]):
            cell_counts[cell]["matched_record_count"] = matched_count
            cell_counts[cell]["excluded_record_count"] = expected_cell_count - matched_count
        members.append({
            "member_id": spec["member_id"], "matched_set": spec["matched_set"], "anchor": spec["anchor"],
            "outcome": spec["outcome"], "all_cell": spec["all_cell"], "content_cell": spec["content_cell"],
            "scheduled_pair_count": expected_cell_count, "matched_pair_count": matched_count,
            "missing_pair_count": missing_count, "records": records, "missing_pairs": missing_pairs,
        })
    return {
        "member_order": [spec["member_id"] for spec in _MEMBER_SPECS],
        "endpoint_order": [dict(spec) for spec in _MEMBER_SPECS],
        "cell_counts": cell_counts,
        "members": members,
        "matched_counts": {member["matched_set"]: member["matched_pair_count"] for member in members},
    }


def _source_summary(validated: ValidatedIndependentRun) -> dict[str, Any]:
    loaded = validated.loaded
    reconciliation = validated.reconciliation
    return {
        "run_directory": str(loaded.run_directory),
        "run_id": loaded.run_directory.name,
        "canonical_registry_sha256": loaded.registry["registry_sha256"],
        "ledger_sha256": canonical_sha256(dict(reconciliation)),
        "execution_identity_sha256": canonical_sha256(dict(loaded.execution_identity)),
        "source_file_sha256": dict(loaded.file_sha256),
    }


def _check_output_destination(source: Path, output: Path) -> Path:
    if not isinstance(output, Path):
        _invalid("OUTPUT_DIRECTORY_NOT_PATH")
    source_resolved = _source_directory(source)
    if output.exists() or output.is_symlink():
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    resolved = output.resolve()
    try:
        resolved.relative_to(source_resolved)
    except ValueError:
        pass
    else:
        _invalid("OUTPUT_DIRECTORY_INSIDE_SOURCE_RUN")
    protected = (OLD_P2_RUN.resolve(), OLD_P2_MATERIALIZED.resolve())
    if any(resolved == path or path in resolved.parents for path in protected):
        _invalid("OUTPUT_DIRECTORY_PROTECTED_OLD_P2")
    return resolved


def validate_only(
    run_directory: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
    prepared: PreparedIndependentP2 | None = None,
) -> dict[str, Any]:
    validated = validate_independent_run(run_directory, config_path=config_path, prepared=prepared)
    frame = build_independent_raw_members(
        validated.prepared.rows,
        validated.loaded.responses,
        generation_records=validated.loaded.generations,
        judge_records=validated.loaded.judges,
        dispositions=validated.loaded.dispositions,
    )
    return {
        "status": "P2_AMENDED_TH_RESULT_VALIDATE_ONLY_PASS",
        "validate_only": True,
        "amendment_id": AMENDMENT_ID,
        "source_run_id": validated.loaded.run_directory.name,
        "endpoint_order": frame["endpoint_order"],
        "identity_count": IDENTITY_COUNT,
        "cell_identity_counts": {cell: P2_CELL_COUNT for cell in _CELL_SPECS},
        "fake_backend": validated.reconciliation.get("fake_backend", False),
        "formal_experiment_run": validated.reconciliation.get("formal_experiment_run", False),
        "paper_result_eligible": False,
        "old_p2_run": False,
        "M_T": frame["matched_counts"]["M_T"],
        "M_H": frame["matched_counts"]["M_H"],
        "terminal_partition": dict(validated.reconciliation["terminal_partition"]),
        "statistics_not_run": True,
        "output_written": False,
        "generation_calls_added": 0,
        "judge_calls_added": 0,
        "old_p2_unchanged": True,
        "amended_independent": True,
        "estimation_only": True,
    }


def materialize_p2_independent_results_directory(
    run_directory: Path,
    output_directory: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
    prepared: PreparedIndependentP2 | None = None,
) -> dict[str, Any]:
    """Validate and write raw members once; no statistic is executed."""
    output = _check_output_destination(run_directory, output_directory)
    validated = validate_independent_run(run_directory, config_path=config_path, prepared=prepared)
    frame = build_independent_raw_members(
        validated.prepared.rows,
        validated.loaded.responses,
        generation_records=validated.loaded.generations,
        judge_records=validated.loaded.judges,
        dispositions=validated.loaded.dispositions,
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "RAW_MEMBERS_READY",
        "amendment_id": AMENDMENT_ID,
        "endpoint_order": frame["endpoint_order"],
        "member_order": frame["member_order"],
        "source": _source_summary(validated),
        "source_run_id": validated.loaded.run_directory.name,
        "identity_count": IDENTITY_COUNT,
        "cell_identity_counts": {cell: P2_CELL_COUNT for cell in _CELL_SPECS},
        "fake_backend": validated.reconciliation.get("fake_backend", False),
        "formal_experiment_run": validated.reconciliation.get("formal_experiment_run", False),
        "paper_result_eligible": False,
        "old_p2_run": False,
        "terminal_partition": dict(validated.reconciliation["terminal_partition"]),
        "M_T": frame["matched_counts"]["M_T"],
        "M_H": frame["matched_counts"]["M_H"],
        "cell_counts": frame["cell_counts"],
        "members": frame["members"],
        "amended_independent": True,
        "estimation_only": True,
        "scope": "amended_independent_estimation_only",
        "statistics_not_run": True,
        "generation_calls_added": 0,
        "judge_calls_added": 0,
        "old_p2_unchanged": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        _invalid(f"OUTPUT_DIRECTORY_EXISTS:{output}")
    OutputStore(output).write_json_once(OUTPUT_FILENAME, result)
    return result


# Short aliases make the materializer's public boundary easy to discover.
build_raw_members = build_independent_raw_members
build_p2_independent_raw_members = build_independent_raw_members
load_and_reconcile_independent_run = validate_independent_run
load_and_reconcile_p2_independent_run = validate_independent_run
materialize_independent_results_directory = materialize_p2_independent_results_directory
materialize_p2_independent_results = materialize_p2_independent_results_directory


__all__ = [
    "EXPECTED_TERMINAL_PARTITION", "FORMAL_AMENDED_RUN_DIRECTORY", "OUTPUT_FILENAME",
    "P2IndependentResultInputInvalid", "LoadedIndependentRun", "ValidatedIndependentRun",
    "build_independent_raw_members", "build_raw_members", "build_p2_independent_raw_members", "load_independent_run",
    "validate_independent_run", "load_and_reconcile_independent_run", "load_and_reconcile_p2_independent_run", "validate_only",
    "materialize_p2_independent_results_directory", "materialize_independent_results_directory", "materialize_p2_independent_results",
]
