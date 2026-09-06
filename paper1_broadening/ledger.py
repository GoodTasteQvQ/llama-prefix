"""Stable logical identities, alias-aware schedules, and append-only attempts."""

from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .common import BroadeningError, append_jsonl, atomic_write_bytes, canonical_json, canonical_sha256, read_jsonl


IDENTITY_FIELDS = (
    "run_id",
    "block",
    "model_id",
    "layer",
    "family",
    "condition",
    "rho",
    "direction_id",
    "prompt_id",
)


def _scalar(value: Any, field: str) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise BroadeningError(f"identity field {field} is not a scalar/null")


def identity_array(identity: Mapping[str, Any]) -> list[Any]:
    if set(identity) != set(IDENTITY_FIELDS):
        raise BroadeningError("identity fields differ from the MBD scientific key")
    for field in ("run_id", "block", "model_id", "prompt_id"):
        if not isinstance(identity[field], str) or not identity[field]:
            raise BroadeningError(f"identity field {field} is invalid")
    condition = identity["condition"]
    if condition not in {"clean", "public_v1", "decode_only"}:
        raise BroadeningError("identity condition is invalid")
    layer = identity["layer"]
    if layer is not None and (isinstance(layer, bool) or not isinstance(layer, int) or layer < 0):
        raise BroadeningError("identity layer is invalid")
    family = identity["family"]
    if family is not None and family not in {"rogue", "contrastive"}:
        raise BroadeningError("identity family is invalid")
    direction_id = identity["direction_id"]
    if direction_id is not None and (not isinstance(direction_id, str) or not direction_id):
        raise BroadeningError("identity direction is invalid")
    rho = identity["rho"]
    if rho is not None and (
        isinstance(rho, bool) or not isinstance(rho, (int, float))
        or not math.isfinite(float(rho)) or float(rho) < 0.0
    ):
        raise BroadeningError("identity rho is invalid")
    if condition == "clean":
        if any(identity[field] is not None for field in ("layer", "family", "rho", "direction_id")):
            raise BroadeningError("clean identity must have null steering fields")
    elif any(identity[field] is None for field in ("layer", "family", "rho", "direction_id")):
        raise BroadeningError("steered identity lacks a steering field")
    return [_scalar(identity[field], field) for field in IDENTITY_FIELDS]


def stable_id(prefix: str, identity: Mapping[str, Any]) -> str:
    return f"{prefix}-{canonical_sha256(identity_array(identity))}"


def clean_identity(*, run_id: str, block: str, model_id: str, prompt_id: str) -> dict[str, Any]:
    identity = {
        "run_id": run_id,
        "block": block,
        "model_id": model_id,
        "layer": None,
        "family": None,
        "condition": "clean",
        "rho": None,
        "direction_id": None,
        "prompt_id": prompt_id,
    }
    identity_array(identity)
    return identity


def steered_identity(
    *, run_id: str, block: str, model_id: str, layer: int, family: str,
    condition: str, rho: float, direction_id: str, prompt_id: str,
) -> dict[str, Any]:
    if family not in {"rogue", "contrastive"}:
        raise BroadeningError("steered identity family is invalid")
    if condition not in {"public_v1", "decode_only"}:
        raise BroadeningError("steered identity condition is invalid")
    if not isinstance(layer, int) or layer < 0:
        raise BroadeningError("steered identity layer is invalid")
    identity = {
        "run_id": run_id,
        "block": block,
        "model_id": model_id,
        "layer": layer,
        "family": family,
        "condition": condition,
        "rho": float(rho),
        "direction_id": direction_id,
        "prompt_id": prompt_id,
    }
    identity_array(identity)
    return identity


def schedule_row(
    *, identity: Mapping[str, Any], dose_label: str, status: str = "SCHEDULED",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    array = identity_array(identity)
    if dose_label not in {"clean", "A", "S", "screen"}:
        raise BroadeningError("schedule dose label is invalid")
    if identity["condition"] == "clean":
        if dose_label != "clean" or any(identity[field] is not None for field in ("family", "layer", "rho", "direction_id")):
            raise BroadeningError("clean identity must have null steering fields")
    elif dose_label == "clean":
        raise BroadeningError("steered identity cannot use clean dose label")
    schedule_key = {"identity": array, "dose_label": dose_label}
    row = {
        "schema_version": "paper1-broadening-scheduled-identity-v1",
        "schedule_id": "schedule-" + canonical_sha256(schedule_key),
        "response_id": stable_id("response", identity),
        "identity": dict(identity),
        "dose_label": dose_label,
        "status": status,
    }
    if metadata is not None:
        row["metadata"] = dict(metadata)
    return row


def build_alias_aware_schedule(
    requests: Iterable[tuple[Mapping[str, Any], str] | tuple[Mapping[str, Any], str, Mapping[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_schedule_ids: set[str] = set()
    for request in requests:
        if len(request) == 2:
            identity, dose_label = request
            metadata = None
        elif len(request) == 3:
            identity, dose_label, metadata = request
        else:
            raise BroadeningError("schedule request must contain identity, dose, and optional metadata")
        row = schedule_row(identity=identity, dose_label=dose_label, metadata=metadata)
        if row["schedule_id"] in seen_schedule_ids:
            raise BroadeningError("duplicate logical schedule identity")
        seen_schedule_ids.add(row["schedule_id"])
        rows.append(row)
    return rows


def response_aliases(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        aliases[str(row["response_id"])].append(str(row["schedule_id"]))
    return {response_id: sorted(schedule_ids) for response_id, schedule_ids in sorted(aliases.items())}


def write_schedule(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    payload = b"".join((canonical_json(dict(row)) + "\n").encode("utf-8") for row in rows)
    atomic_write_bytes(path, payload, overwrite=False)


def load_schedule(path: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    seen: set[str] = set()
    for row in rows:
        if row.get("schema_version") != "paper1-broadening-scheduled-identity-v1":
            raise BroadeningError("scheduled identity schema differs")
        schedule_id = row.get("schedule_id")
        if not isinstance(schedule_id, str) or schedule_id in seen:
            raise BroadeningError("scheduled identity is missing or duplicated")
        seen.add(schedule_id)
        metadata = row.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise BroadeningError("schedule metadata must be an object")
        expected = schedule_row(
            identity=row.get("identity", {}), dose_label=row.get("dose_label", ""), metadata=metadata
        )
        if any(row.get(field) != expected[field] for field in ("schedule_id", "response_id", "identity", "dose_label")):
            raise BroadeningError("scheduled identity is not canonical")
    return rows


GENERATION_ATTEMPT_STATUSES = {
    "COMPLETED",
    "TECHNICAL_FAILURE_RETRYABLE",
    "TERMINAL_TECHNICAL_FAILURE",
    "TERMINAL_FAILURE",
    "UNEXECUTED",
}


def generation_attempt(
    *, response_id: str, attempt_no: int, status: str, text: str | None,
    token_ids: Sequence[int] | None, runtime: Mapping[str, Any] | None,
    diagnostics: Mapping[str, Any] | None, error: str | None,
    identity: Mapping[str, Any] | None = None, dose_label: str | None = None,
) -> dict[str, Any]:
    if not isinstance(response_id, str) or not response_id:
        raise BroadeningError("generation attempt response_id is invalid")
    if isinstance(attempt_no, bool) or not isinstance(attempt_no, int) or attempt_no < 1 or attempt_no > 2:
        raise BroadeningError("generation attempt status or number is invalid")
    if status not in GENERATION_ATTEMPT_STATUSES:
        raise BroadeningError("generation attempt status or number is invalid")
    if identity is not None:
        identity_array(identity)
        if dose_label not in {"clean", "A", "S", "screen"}:
            raise BroadeningError("generation attempt identity requires a valid dose label")
    elif dose_label is not None:
        raise BroadeningError("generation attempt dose label requires identity")
    completed = status == "COMPLETED"
    if completed:
        if not isinstance(text, str) or error is not None:
            raise BroadeningError("completed generation requires text and no error")
        if token_ids is None or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in token_ids):
            raise BroadeningError("completed generation requires nonnegative integer token ids")
    elif text is not None or token_ids is not None or not isinstance(error, str) or not error:
        raise BroadeningError("failed generation requires an error and no response payload")
    return {
        "schema_version": "paper1-broadening-generation-attempt-v1",
        "response_id": response_id,
        "attempt_no": attempt_no,
        "status": status,
        "text": text,
        "token_ids": list(token_ids) if token_ids is not None else None,
        "runtime": dict(runtime or {}),
        "diagnostics": dict(diagnostics or {}),
        "error": error,
        "identity": dict(identity) if identity is not None else None,
        "dose_label": dose_label,
    }


def validate_attempt_sequence(
    attempts: Sequence[Mapping[str, Any]], *, allow_pending_retry: bool = False,
) -> dict[str, Any]:
    if not attempts or len(attempts) > 2:
        raise BroadeningError("a response has an invalid number of attempts")
    response_ids = {attempt.get("response_id") for attempt in attempts}
    if len(response_ids) != 1 or None in response_ids:
        raise BroadeningError("attempts do not share one response_id")
    normalized: list[dict[str, Any]] = []
    for number, attempt in enumerate(attempts, 1):
        expected = generation_attempt(
            response_id=attempt.get("response_id"),
            attempt_no=attempt.get("attempt_no"),
            status=attempt.get("status"),
            text=attempt.get("text"),
            token_ids=attempt.get("token_ids"),
            runtime=attempt.get("runtime"),
            diagnostics=attempt.get("diagnostics"),
            error=attempt.get("error"),
            identity=attempt.get("identity"),
            dose_label=attempt.get("dose_label"),
        )
        if expected != dict(attempt) or expected["attempt_no"] != number:
            raise BroadeningError("generation attempt is noncanonical or out of order")
        normalized.append(expected)
    if len(normalized) == 2 and normalized[0]["status"] != "TECHNICAL_FAILURE_RETRYABLE":
        raise BroadeningError("only a technical first failure may be retried")
    if len(normalized) == 2 and normalized[1]["status"] == "TECHNICAL_FAILURE_RETRYABLE":
        raise BroadeningError("the one allowed retry cannot remain retryable")
    if len(normalized) == 2 and (
        normalized[0].get("identity") != normalized[1].get("identity")
        or normalized[0].get("dose_label") != normalized[1].get("dose_label")
    ):
        raise BroadeningError("retry attempts must retain the same scientific identity")
    if (
        len(normalized) == 1
        and normalized[0]["status"] == "TECHNICAL_FAILURE_RETRYABLE"
        and not allow_pending_retry
    ):
        raise BroadeningError("retryable failure requires its one allowed retry")
    return {
        "response_id": normalized[0]["response_id"],
        "attempt_count": len(normalized),
        "canonical_attempt_no": next(
            (attempt["attempt_no"] for attempt in normalized if attempt["status"] == "COMPLETED"),
            None,
        ),
        "terminal_status": normalized[-1]["status"],
    }


def append_generation_attempt(path: Path, attempt: Mapping[str, Any]) -> None:
    expected = generation_attempt(
        response_id=attempt.get("response_id"),
        attempt_no=attempt.get("attempt_no"),
        status=attempt.get("status"),
        text=attempt.get("text"),
        token_ids=attempt.get("token_ids"),
        runtime=attempt.get("runtime"),
        diagnostics=attempt.get("diagnostics"),
        error=attempt.get("error"),
        identity=attempt.get("identity"),
        dose_label=attempt.get("dose_label"),
    )
    existing = [row for row in read_jsonl(path)] if path.exists() else []
    same_response = [row for row in existing if row.get("response_id") == expected["response_id"]]
    validate_attempt_sequence([*same_response, expected], allow_pending_retry=True)
    append_jsonl(path, expected)


def canonical_generation_records(attempts: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        grouped[str(attempt.get("response_id"))].append(attempt)
    records: dict[str, dict[str, Any]] = {}
    for response_id, items in grouped.items():
        items = sorted(items, key=lambda item: item.get("attempt_no", -1))
        state = validate_attempt_sequence(items, allow_pending_retry=True)
        canonical = next((item for item in items if item["status"] == "COMPLETED"), None)
        records[response_id] = {
            **state,
            "canonical_attempt": dict(canonical) if canonical is not None else None,
            "attempts": [dict(item) for item in items],
        }
    return records


def ledger_accounting(schedule: Sequence[Mapping[str, Any]], attempts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    canonical = canonical_generation_records(attempts)
    aliases = response_aliases(schedule)
    scheduled_response_ids = set(aliases)
    unknown = set(canonical) - scheduled_response_ids
    if unknown:
        raise BroadeningError("generation attempts reference unscheduled responses")
    completed = sum(record["canonical_attempt"] is not None for record in canonical.values())
    terminal = sum(
        record["terminal_status"] != "COMPLETED" for record in canonical.values()
    )
    unexecuted = len(scheduled_response_ids - set(canonical))
    return {
        "logical_scheduled": len(schedule),
        "physical_scheduled": len(scheduled_response_ids),
        "A_S_alias_deduplicated": len(schedule) - len(scheduled_response_ids),
        "attempted_physical": len(canonical),
        "completed_physical": completed,
        "terminal_failed_physical": terminal,
        "unexecuted_physical": unexecuted,
    }
