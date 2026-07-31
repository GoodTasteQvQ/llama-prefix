#!/usr/bin/env python3
"""Current matched two-phase inference implementation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


IMPLEMENTATION_VERSION = "paper1-stage3-two-phase-v1"
RNG_NAMESPACE = "v3.5-rc2"
INPUT_SCHEMA = "paper1-stage3-two-phase-input-v1"
MASTER_SEED = 42
REPLICATES = 9_999
COMMON_SUCCESS_REQUIRED = 9_500
SE_FLOOR = 1e-8
MEMBER_ORDER = ("P2-U(A)", "P2-B(T)")
ARMS = ("all-token", "content-token")
MEMBER_CONTRACT = {
    "P2-U(A)": {"anchor": "A", "endpoint": "unsafe", "frame_id": "M_A"},
    "P2-B(T)": {"anchor": "T", "endpoint": "broken", "frame_id": "M_T"},
}
BLOCKS = {
    "prompt": "p2-two-phase-prompt",
    "vector": "p2-two-phase-vector",
}
INPUT_SCHEMA_PATH = Path(__file__).with_name("schemas") / "two_phase_input.schema.json"


class NonEstimable(ValueError):
    """First canonical failure; no fallback is evaluated after this exception."""

    def __init__(self, status: str, reason_code: str, detail: str = "") -> None:
        self.status = status
        self.reason_code = reason_code
        self.detail = detail
        message = f"{status}:{reason_code}"
        if detail:
            message += f":{detail}"
        super().__init__(message)

    def as_dict(self) -> dict[str, str]:
        result = {"status": self.status, "reason_code": self.reason_code}
        if self.detail:
            result["detail"] = self.detail
        return result


def _fail_input(reason: str, detail: str = "") -> None:
    raise NonEstimable("INPUT_INVALID_NON_ESTIMABLE", reason, detail)


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        _fail_input("NONCANONICAL_JSON_VALUE", str(exc))
    raise AssertionError("unreachable")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _valid_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail_input("INVALID_ID", field)
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        _fail_input("INVALID_UNICODE_SCALAR", field)
    return value


def _unicode_key(value: str) -> tuple[int, ...]:
    return tuple(ord(character) for character in value)


def _exact_keys(value: Any, required: set[str], optional: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail_input("SCHEMA_TYPE", label)
    keys = set(value)
    missing = sorted(required - keys)
    extra = sorted(keys - required - optional)
    if missing or extra:
        _fail_input("SCHEMA_KEYS", f"{label}:missing={missing},extra={extra}")
    return value


def _strict_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        _fail_input("INVALID_INTEGER", field)
    return value


def _schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    _fail_input("SCHEMA_UNSUPPORTED_KEYWORD", f"type={expected}")
    raise AssertionError("unreachable")


def _resolve_schema_ref(root_schema: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        _fail_input("SCHEMA_EXTERNAL_REF_FORBIDDEN", reference)
    node: Any = root_schema
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, Mapping) or token not in node:
            _fail_input("SCHEMA_REF_NOT_FOUND", reference)
        node = node[token]
    if not isinstance(node, Mapping):
        _fail_input("SCHEMA_REF_NOT_OBJECT", reference)
    return node


def _validate_schema_node(
    value: Any,
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path: str,
) -> None:
    if "$ref" in schema:
        _validate_schema_node(value, _resolve_schema_ref(root_schema, schema["$ref"]), root_schema, path)
        return
    if "allOf" in schema:
        all_of = schema["allOf"]
        if not isinstance(all_of, list) or not all_of or not all(
            isinstance(item_schema, Mapping) for item_schema in all_of
        ):
            _fail_input("SCHEMA_INVALID", f"{path}:allOf")
        for item_schema in all_of:
            _validate_schema_node(value, item_schema, root_schema, path)
    if "const" in schema and value != schema["const"]:
        _fail_input("SCHEMA_VALIDATION", f"{path}:const")
    if "enum" in schema and value not in schema["enum"]:
        _fail_input("SCHEMA_VALIDATION", f"{path}:enum")
    expected_type = schema.get("type")
    if expected_type is not None:
        candidates = [expected_type] if isinstance(expected_type, str) else expected_type
        if not isinstance(candidates, list) or not all(isinstance(item, str) for item in candidates):
            _fail_input("SCHEMA_INVALID", f"{path}:type")
        if not any(_schema_type_matches(value, item) for item in candidates):
            _fail_input("SCHEMA_VALIDATION", f"{path}:type")
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            _fail_input("SCHEMA_VALIDATION", f"{path}:minLength")
        pattern = schema.get("pattern")
        if pattern is not None and re.fullmatch(pattern, value) is None:
            _fail_input("SCHEMA_VALIDATION", f"{path}:pattern")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            _fail_input("SCHEMA_VALIDATION", f"{path}:minimum")
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            _fail_input("SCHEMA_VALIDATION", f"{path}:minItems")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            _fail_input("SCHEMA_VALIDATION", f"{path}:maxItems")
        if schema.get("uniqueItems"):
            rendered = [canonical_json(item) for item in value]
            if len(rendered) != len(set(rendered)):
                _fail_input("SCHEMA_VALIDATION", f"{path}:uniqueItems")
        prefix_items = schema.get("prefixItems", [])
        if not isinstance(prefix_items, list) or not all(
            isinstance(item_schema, Mapping) for item_schema in prefix_items
        ):
            _fail_input("SCHEMA_INVALID", f"{path}:prefixItems")
        prefix_count = min(len(value), len(prefix_items))
        for index in range(prefix_count):
            _validate_schema_node(value[index], prefix_items[index], root_schema, f"{path}[{index}]")

        if "items" in schema:
            item_schema = schema["items"]
            if item_schema is False:
                if len(value) > len(prefix_items):
                    _fail_input("SCHEMA_VALIDATION", f"{path}:items[{len(prefix_items)}]")
            elif item_schema is not True:
                if not isinstance(item_schema, Mapping):
                    _fail_input("SCHEMA_INVALID", f"{path}:items")
                for index in range(len(prefix_items), len(value)):
                    _validate_schema_node(value[index], item_schema, root_schema, f"{path}[{index}]")
    if isinstance(value, Mapping):
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            _fail_input("SCHEMA_INVALID", f"{path}:required")
        missing = [item for item in required if item not in value]
        if missing:
            _fail_input("SCHEMA_VALIDATION", f"{path}:required={missing}")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            _fail_input("SCHEMA_INVALID", f"{path}:properties")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                _fail_input("SCHEMA_VALIDATION", f"{path}:additionalProperties={extra}")
        for key, item_schema in properties.items():
            if key in value:
                if not isinstance(item_schema, Mapping):
                    _fail_input("SCHEMA_INVALID", f"{path}.{key}")
                _validate_schema_node(value[key], item_schema, root_schema, f"{path}.{key}")


def validate_against_input_schema(payload: Any) -> None:
    """Apply the bound JSON Schema before semantic/cross-frame validation."""
    try:
        schema = json.loads(INPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NonEstimable(
            "IMPLEMENTATION_FIX_REQUIRED", "INPUT_SCHEMA_UNAVAILABLE_OR_INVALID", str(exc)
        ) from exc
    if not isinstance(schema, Mapping):
        raise NonEstimable("IMPLEMENTATION_FIX_REQUIRED", "INPUT_SCHEMA_NOT_OBJECT")
    _validate_schema_node(payload, schema, schema, "$")


def _binary(value: Any, field: str) -> int:
    if isinstance(value, float) and not math.isfinite(value):
        _fail_input("NONFINITE_VALUE", field)
    if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
        _fail_input("INVALID_BINARY_VALUE", field)
    return value


def _fraction(value: Any, field: str) -> tuple[int, int, float]:
    if not isinstance(value, str) or value.count("/") != 1:
        _fail_input("INVALID_PI", field)
    numerator_text, denominator_text = value.split("/", 1)
    if not numerator_text.isdigit() or not denominator_text.isdigit():
        _fail_input("INVALID_PI", field)
    numerator = int(numerator_text)
    denominator = int(denominator_text)
    if (
        numerator <= 0
        or denominator <= 0
        or numerator > denominator
        or str(numerator) != numerator_text
        or str(denominator) != denominator_text
        or math.gcd(numerator, denominator) != 1
    ):
        _fail_input("INVALID_PI", field)
    return numerator, denominator, numerator / denominator


def sync_unit_id(fields: Mapping[str, Any]) -> str:
    """Serialize one exact shared-stream identity; member identity is forbidden."""
    forbidden = {"member", "member_id"}.intersection(fields)
    if forbidden:
        _fail_input("MEMBER_ID_IN_SYNC_UNIT", ",".join(sorted(forbidden)))
    return canonical_json(dict(fields))


def prompt_sync_unit(block_id: str, frame_sha256: str, stratum_id: str) -> str:
    return sync_unit_id({
        "axis": "prompt-stratum",
        "family": block_id,
        "frame_sha256": frame_sha256,
        "stratum_id": stratum_id,
    })


def phase_two_sync_unit(block_id: str, frame_sha256: str, stratum_id: str) -> str:
    return sync_unit_id({
        "axis": "phase2-stratum",
        "family": block_id,
        "frame_sha256": frame_sha256,
        "stratum_id": stratum_id,
    })


def vector_sync_unit(block_id: str, frame_sha256: str, frame_id: str) -> str:
    return sync_unit_id({
        "axis": "vector",
        "entity_id": frame_id,
        "family": block_id,
        "frame_sha256": frame_sha256,
    })


def seed_material(block_id: str, unit_id: str, replicate_index: int) -> tuple[str, bytes]:
    if block_id not in BLOCKS.values():
        _fail_input("INVALID_BLOCK_ID", block_id)
    if not isinstance(replicate_index, int) or isinstance(replicate_index, bool) or replicate_index < 1:
        _fail_input("INVALID_REPLICATE_INDEX", str(replicate_index))
    payload = (
        f"{RNG_NAMESPACE}|master={MASTER_SEED}|block={block_id}"
        f"|sync_unit={unit_id}|rep={replicate_index:06d}"
    )
    return payload, hashlib.sha256(payload.encode("utf-8")).digest()[:16]


class Sha256CounterRng:
    """SHA256(seed || uint64_be(counter)); first uint64_be word per digest."""

    def __init__(self, seed: bytes) -> None:
        if not isinstance(seed, bytes) or len(seed) != 16:
            _fail_input("INVALID_RNG_SEED_LENGTH")
        self.seed = seed
        self.counter = 0

    def block(self) -> bytes:
        if self.counter >= (1 << 64):
            _fail_input("RNG_COUNTER_EXHAUSTED")
        result = hashlib.sha256(self.seed + self.counter.to_bytes(8, "big")).digest()
        self.counter += 1
        return result

    def uint64(self) -> int:
        return int.from_bytes(self.block()[:8], "big", signed=False)

    def randbelow(self, upper: int) -> int:
        return rejection_sample(upper, self.uint64)[0]


def rejection_sample(upper: int, next_word: Any) -> tuple[int, int]:
    """Return (draw, consumed words) using the normative 64-bit rejection rule."""
    if not isinstance(upper, int) or isinstance(upper, bool) or upper <= 0:
        _fail_input("INVALID_RNG_UPPER", str(upper))
    limit = (1 << 64) - ((1 << 64) % upper)
    consumed = 0
    while True:
        word = next_word()
        consumed += 1
        if not isinstance(word, int) or isinstance(word, bool) or not 0 <= word < (1 << 64):
            _fail_input("INVALID_RNG_WORD", str(word))
        if word < limit:
            return word % upper, consumed


def nearest_rank(values: Iterable[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise NonEstimable("NONFINITE_INTERVAL_NON_ESTIMABLE", "EMPTY_QUANTILE")
    if not all(math.isfinite(value) for value in ordered):
        raise NonEstimable("NONFINITE_INTERVAL_NON_ESTIMABLE", "NONFINITE_QUANTILE_INPUT")
    if not 0.0 < probability <= 1.0:
        _fail_input("INVALID_QUANTILE_PROBABILITY", str(probability))
    return ordered[max(1, math.ceil(probability * len(ordered))) - 1]


def sample_sd(values: Sequence[float]) -> float:
    if len(values) < 2 or not all(math.isfinite(value) for value in values):
        raise NonEstimable("INVALID_SE_NON_ESTIMABLE", "INVALID_FIXED_SCALE_SAMPLE")
    center = math.fsum(values) / len(values)
    variance = math.fsum((value - center) ** 2 for value in values) / (len(values) - 1)
    if not math.isfinite(variance) or variance < 0.0:
        raise NonEstimable("INVALID_SE_NON_ESTIMABLE", "NONFINITE_OR_NEGATIVE_VARIANCE")
    return math.sqrt(variance)


def require_common_success(successes: int, requested: int = REPLICATES) -> int:
    if requested != REPLICATES:
        _fail_input("REPLICATE_COUNT_NOT_9999", str(requested))
    if successes < COMMON_SUCCESS_REQUIRED:
        raise NonEstimable(
            "RESAMPLING_COMPLETION_NON_ESTIMABLE",
            "COMMON_SUCCESSES_BELOW_9500",
            f"{successes}<{COMMON_SUCCESS_REQUIRED}",
        )
    return successes


def _prompt_core(frame: Mapping[str, Any]) -> dict[str, Any]:
    return {"frame_id": frame["frame_id"], "strata": frame["strata"]}


def _vector_core(frame: Mapping[str, Any]) -> dict[str, Any]:
    return {"frame_id": frame["frame_id"], "vector_ids": frame["vector_ids"]}


def _phase_core(frame: Mapping[str, Any]) -> dict[str, Any]:
    return {"frame_id": frame["frame_id"], "strata": frame["strata"]}


IDENTITY_ROW_FIELDS = (
    "response_id", "pair_id", "prompt_id", "prompt_category", "vector_id", "anchor", "arm"
)


def _member_core(member: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "frame_id": member["frame_id"],
        "member_id": member["member_id"],
        "rows": [{field: row[field] for field in IDENTITY_ROW_FIELDS} for row in member["rows"]],
    }


def computed_frame_hashes(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "prompt_frame_sha256": canonical_sha256(_prompt_core(payload["prompt_frame"])),
        "vector_frame_sha256": canonical_sha256(_vector_core(payload["vector_frame"])),
        "phase_two_frame_sha256": canonical_sha256(_phase_core(payload["phase_two_frame"])),
        "member_frame_sha256": {
            member["member_id"]: canonical_sha256(_member_core(member))
            for member in payload["members"]
        },
    }


def refresh_frame_hashes(payload: dict[str, Any]) -> dict[str, Any]:
    """Fixture-author helper; paper callers must supply recorded frame hashes."""
    result = copy.deepcopy(payload)
    hashes = computed_frame_hashes(result)
    result["prompt_frame"]["frame_sha256"] = hashes["prompt_frame_sha256"]
    result["vector_frame"]["frame_sha256"] = hashes["vector_frame_sha256"]
    result["phase_two_frame"]["frame_sha256"] = hashes["phase_two_frame_sha256"]
    for member in result["members"]:
        member["frame_sha256"] = hashes["member_frame_sha256"][member["member_id"]]
    return result


def _validate_prompt_frame(frame: Mapping[str, Any]) -> tuple[dict[str, str], list[str]]:
    _exact_keys(frame, {"frame_id", "frame_sha256", "strata"}, set(), "prompt_frame")
    _valid_text(frame["frame_id"], "prompt_frame.frame_id")
    if frame["frame_id"] != "D_behavior_confirm":
        _fail_input("INVALID_PROMPT_FRAME_ID", str(frame["frame_id"]))
    if not isinstance(frame["strata"], list) or not frame["strata"]:
        _fail_input("EMPTY_PROMPT_FRAME")
    prompt_category: dict[str, str] = {}
    stratum_ids: list[str] = []
    for index, stratum in enumerate(frame["strata"]):
        _exact_keys(stratum, {"stratum_id", "prompt_ids"}, set(), f"prompt_strata[{index}]")
        stratum_id = _valid_text(stratum["stratum_id"], f"prompt_strata[{index}].stratum_id")
        stratum_ids.append(stratum_id)
        ids = stratum["prompt_ids"]
        if not isinstance(ids, list) or not ids:
            _fail_input("EMPTY_PROMPT_STRATUM", stratum_id)
        checked = [_valid_text(item, f"prompt_id:{stratum_id}") for item in ids]
        if checked != sorted(checked, key=_unicode_key):
            _fail_input("NONCANONICAL_PROMPT_ORDER", stratum_id)
        if len(checked) != len(set(checked)):
            _fail_input("IDENTITY_COLLISION", f"prompt:{stratum_id}")
        for prompt_id in checked:
            if prompt_id in prompt_category:
                _fail_input("IDENTITY_COLLISION", f"prompt:{prompt_id}")
            prompt_category[prompt_id] = stratum_id
    if stratum_ids != sorted(stratum_ids, key=_unicode_key) or len(stratum_ids) != len(set(stratum_ids)):
        _fail_input("NONCANONICAL_PROMPT_STRATA_ORDER")
    expected = canonical_sha256(_prompt_core(frame))
    if frame["frame_sha256"] != expected:
        _fail_input("FRAME_HASH_MISMATCH", "prompt_frame")
    return prompt_category, stratum_ids


def _validate_vector_frame(frame: Mapping[str, Any]) -> list[str]:
    _exact_keys(frame, {"frame_id", "frame_sha256", "vector_ids"}, set(), "vector_frame")
    if frame["frame_id"] != "V_confirm":
        _fail_input("INVALID_VECTOR_FRAME_ID", str(frame["frame_id"]))
    ids = frame["vector_ids"]
    if not isinstance(ids, list) or len(ids) != 20:
        _fail_input("VECTOR_FRAME_MUST_HAVE_20_IDS")
    checked = [_valid_text(item, "vector_id") for item in ids]
    if checked != sorted(checked, key=_unicode_key):
        _fail_input("NONCANONICAL_VECTOR_ORDER")
    if len(checked) != len(set(checked)):
        _fail_input("IDENTITY_COLLISION", "vector")
    if frame["frame_sha256"] != canonical_sha256(_vector_core(frame)):
        _fail_input("FRAME_HASH_MISMATCH", "vector_frame")
    return checked


def _row_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    arm_rank = ARMS.index(row["arm"]) if row.get("arm") in ARMS else 99
    return (
        _unicode_key(str(row.get("prompt_category", ""))),
        _unicode_key(str(row.get("prompt_id", ""))),
        _unicode_key(str(row.get("vector_id", ""))),
        _unicode_key(str(row.get("pair_id", ""))),
        arm_rank,
        _unicode_key(str(row.get("response_id", ""))),
    )


def _validate_member_structure(member: Mapping[str, Any], expected_id: str) -> None:
    _exact_keys(
        member,
        {"member_id", "anchor", "endpoint", "frame_id", "frame_sha256", "rows"},
        set(),
        f"member:{expected_id}",
    )
    if member["member_id"] != expected_id:
        _fail_input("MEMBER_ORDER", f"expected={expected_id}")
    contract = MEMBER_CONTRACT[expected_id]
    for field in ("anchor", "endpoint", "frame_id"):
        if member[field] != contract[field]:
            _fail_input("MEMBER_CONTRACT_MISMATCH", f"{expected_id}:{field}")
    rows = member["rows"]
    if not isinstance(rows, list) or not rows:
        _fail_input("EMPTY_MEMBER", expected_id)
    if rows != sorted(rows, key=_row_key):
        _fail_input("NONCANONICAL_MEMBER_FRAME_ORDER", expected_id)
    arms_present = {row.get("arm") for row in rows}
    if arms_present != set(ARMS):
        _fail_input("EMPTY_ARM", expected_id)
    pairs: dict[str, list[Mapping[str, Any]]] = {}
    seen_prompt_vector: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        required = set(IDENTITY_ROW_FIELDS) | {"judge", "selected", "phase2_stratum_id"}
        optional = {"gold", "pi"}
        _exact_keys(row, required, optional, f"{expected_id}.rows[{index}]")
        for field in IDENTITY_ROW_FIELDS + ("phase2_stratum_id",):
            _valid_text(row[field], f"{expected_id}.rows[{index}].{field}")
        if row["anchor"] != contract["anchor"] or row["arm"] not in ARMS:
            _fail_input("ROW_MEMBER_CONTRACT_MISMATCH", f"{expected_id}:{index}")
        if not isinstance(row["selected"], bool):
            _fail_input("INVALID_SELECTED_FLAG", f"{expected_id}:{index}")
        pair_id = row["pair_id"]
        pairs.setdefault(pair_id, []).append(row)
    for pair_id, pair_rows in pairs.items():
        if len(pair_rows) != 2 or {row["arm"] for row in pair_rows} != set(ARMS):
            _fail_input("INCOMPLETE_PAIR", f"{expected_id}:{pair_id}")
        identity = {(row["prompt_id"], row["prompt_category"], row["vector_id"]) for row in pair_rows}
        if len(identity) != 1:
            _fail_input("PAIR_IDENTITY_MISMATCH", f"{expected_id}:{pair_id}")
        prompt_vector = next(iter(identity))[::2]
        if prompt_vector in seen_prompt_vector:
            _fail_input("IDENTITY_COLLISION", f"{expected_id}:{prompt_vector}")
        seen_prompt_vector.add(prompt_vector)
    if member["frame_sha256"] != canonical_sha256(_member_core(member)):
        _fail_input("FRAME_HASH_MISMATCH", expected_id)


def _validate_phase_frame(
    frame: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, str], dict[str, str]]:
    _exact_keys(frame, {"frame_id", "frame_sha256", "strata"}, set(), "phase_two_frame")
    if frame["frame_id"] != "human_validation_sample":
        _fail_input("INVALID_PHASE2_FRAME_ID", str(frame["frame_id"]))
    strata = frame["strata"]
    if not isinstance(strata, list) or not strata:
        _fail_input("EMPTY_PHASE2_FRAME")
    ids = [str(item.get("stratum_id", "")) for item in strata]
    if ids != sorted(ids, key=_unicode_key) or len(ids) != len(set(ids)):
        _fail_input("NONCANONICAL_PHASE2_STRATA_ORDER")
    by_id: dict[str, Mapping[str, Any]] = {}
    population_to_stratum: dict[str, str] = {}
    sampled_to_stratum: dict[str, str] = {}
    coverage = {(member_id, arm): 0 for member_id in MEMBER_ORDER for arm in ARMS}
    for index, stratum in enumerate(strata):
        _exact_keys(
            stratum,
            {"stratum_id", "member_id", "arm", "N_h", "n_h", "population_response_ids",
             "sampled_response_ids"},
            set(),
            f"phase2_strata[{index}]",
        )
        stratum_id = _valid_text(stratum["stratum_id"], f"phase2_strata[{index}].stratum_id")
        if stratum["member_id"] not in MEMBER_ORDER or stratum["arm"] not in ARMS:
            _fail_input("INVALID_PHASE2_MEMBER_ARM", stratum_id)
        reported_population_n = _strict_int(stratum["N_h"], f"{stratum_id}.N_h", minimum=1)
        reported_sample_n = _strict_int(stratum["n_h"], f"{stratum_id}.n_h", minimum=0)
        population = stratum["population_response_ids"]
        sampled = stratum["sampled_response_ids"]
        if not isinstance(population, list):
            _fail_input("SCHEMA_TYPE", f"{stratum_id}.population_response_ids")
        if not isinstance(sampled, list):
            _fail_input("SCHEMA_TYPE", f"{stratum_id}.sampled_response_ids")
        population_checked = [
            _valid_text(item, f"{stratum_id}.population_response_id") for item in population
        ]
        checked = [_valid_text(item, f"{stratum_id}.sampled_response_id") for item in sampled]
        if population_checked != sorted(population_checked, key=_unicode_key):
            _fail_input("NONCANONICAL_PHASE2_POPULATION_ORDER", stratum_id)
        if checked != sorted(checked, key=_unicode_key):
            _fail_input("NONCANONICAL_PHASE2_SAMPLE_ORDER", stratum_id)
        if (
            len(population_checked) != len(set(population_checked))
            or any(item in population_to_stratum for item in population_checked)
            or len(checked) != len(set(checked))
            or any(item in sampled_to_stratum for item in checked)
        ):
            _fail_input("IDENTITY_COLLISION", f"phase2:{stratum_id}")
        population_n = len(population_checked)
        sample_n = len(checked)
        if (
            reported_population_n != population_n
            or reported_sample_n != sample_n
            or sample_n > population_n
        ):
            _fail_input("INVALID_PHASE2_SAMPLE_SIZE", stratum_id)
        if not set(checked).issubset(population_checked):
            _fail_input("PHASE2_SAMPLE_NOT_SUBSET", stratum_id)
        if sample_n == 0:
            _fail_input("PHASE2_ZERO_SAMPLE", stratum_id)
        if sample_n == 1 and sample_n < population_n:
            _fail_input("PHASE2_NONCENSUS_SINGLETON", stratum_id)
        for response_id in population_checked:
            population_to_stratum[response_id] = stratum_id
        for response_id in checked:
            sampled_to_stratum[response_id] = stratum_id
        coverage[(stratum["member_id"], stratum["arm"])] += 1
        by_id[stratum_id] = stratum
    missing_coverage = [f"{member}:{arm}" for (member, arm), count in coverage.items() if count == 0]
    if missing_coverage:
        _fail_input("PHASE2_ARM_STRATUM_MISSING", ",".join(missing_coverage))
    if frame["frame_sha256"] != canonical_sha256(_phase_core(frame)):
        _fail_input("FRAME_HASH_MISMATCH", "phase_two_frame")
    return by_id, population_to_stratum, sampled_to_stratum


def _validate_values_and_cross_references(
    payload: Mapping[str, Any],
    prompt_category: Mapping[str, str],
    vector_ids: Sequence[str],
    phase_by_id: Mapping[str, Mapping[str, Any]],
    population_to_stratum: Mapping[str, str],
    sampled_to_stratum: Mapping[str, str],
) -> None:
    seen_response_ids: set[str] = set()
    for member in payload["members"]:
        for row in member["rows"]:
            response_id = row["response_id"]
            if response_id in seen_response_ids:
                _fail_input("IDENTITY_COLLISION", f"response:{response_id}")
            seen_response_ids.add(response_id)
            if prompt_category.get(row["prompt_id"]) != row["prompt_category"]:
                _fail_input("PROMPT_FRAME_MISMATCH", response_id)
            if row["vector_id"] not in vector_ids:
                _fail_input("VECTOR_FRAME_MISMATCH", response_id)
            _binary(row["judge"], f"judge:{response_id}")
            stratum_id = row["phase2_stratum_id"]
            if stratum_id not in phase_by_id or population_to_stratum.get(response_id) != stratum_id:
                _fail_input("PHASE2_POPULATION_CROSS_REFERENCE", response_id)
            stratum = phase_by_id[stratum_id]
            if stratum["member_id"] != member["member_id"] or stratum["arm"] != row["arm"]:
                _fail_input("PHASE2_MEMBER_ARM_MISMATCH", response_id)
            if row["selected"]:
                if set(("gold", "pi")) - set(row):
                    _fail_input("SELECTED_FIELDS_MISSING", response_id)
                _binary(row["gold"], f"gold:{response_id}")
                numerator, denominator, _ = _fraction(row["pi"], f"pi:{response_id}")
                if sampled_to_stratum.get(response_id) != stratum_id:
                    _fail_input("PHASE2_SELECTION_CROSS_REFERENCE", response_id)
                population_n = len(stratum["population_response_ids"])
                sample_n = len(stratum["sampled_response_ids"])
                if numerator * population_n != denominator * sample_n:
                    _fail_input("INVALID_PI", response_id)
            elif response_id in sampled_to_stratum:
                _fail_input("PHASE2_SAMPLE_NOT_SELECTED", response_id)
            elif any(field in row for field in ("gold", "pi")):
                _fail_input("UNSELECTED_EXPOSES_PHASE2_FIELDS", response_id)
    if seen_response_ids != set(population_to_stratum):
        missing = sorted(seen_response_ids - set(population_to_stratum), key=_unicode_key)
        extra = sorted(set(population_to_stratum) - seen_response_ids, key=_unicode_key)
        _fail_input("PHASE2_POPULATION_NOT_EXHAUSTIVE", f"missing={missing},extra={extra}")


def validate_input(payload: Mapping[str, Any]) -> dict[str, Any]:
    validate_against_input_schema(payload)
    _exact_keys(
        payload,
        {"schema_version", "synthetic_data", "data_origin", "master_seed", "prompt_frame",
         "vector_frame", "phase_two_frame", "members"},
        set(),
        "root",
    )
    if payload["schema_version"] != INPUT_SCHEMA:
        _fail_input("SCHEMA_VERSION_MISMATCH")
    if not isinstance(payload["synthetic_data"], bool):
        _fail_input("SCHEMA_TYPE", "synthetic_data")
    if payload["data_origin"] not in ("TEST_FIXTURE", "PAPER_INPUT"):
        _fail_input("INVALID_DATA_ORIGIN")
    if payload["synthetic_data"] != (payload["data_origin"] == "TEST_FIXTURE"):
        _fail_input("DATA_ORIGIN_FLAG_MISMATCH")
    if payload["master_seed"] != MASTER_SEED:
        _fail_input("MASTER_SEED_NOT_42")
    members = payload["members"]
    if not isinstance(members, list):
        _fail_input("SCHEMA_TYPE", "members")
    for index, member in enumerate(members):
        if not isinstance(member, Mapping):
            _fail_input("SCHEMA_TYPE", f"members[{index}]")
    if [item.get("member_id") for item in members] != list(MEMBER_ORDER):
        _fail_input("MEMBER_ORDER")

    prompt_category, prompt_strata = _validate_prompt_frame(payload["prompt_frame"])
    if payload["data_origin"] == "PAPER_INPUT" and len(prompt_category) != 50:
        _fail_input("PAPER_PROMPT_FRAME_NOT_50", str(len(prompt_category)))
    vector_ids = _validate_vector_frame(payload["vector_frame"])
    for member, member_id in zip(members, MEMBER_ORDER):
        _validate_member_structure(member, member_id)
    phase_by_id, population_to_stratum, sampled_to_stratum = _validate_phase_frame(
        payload["phase_two_frame"]
    )
    _validate_values_and_cross_references(
        payload, prompt_category, vector_ids, phase_by_id, population_to_stratum, sampled_to_stratum
    )
    return {
        "prompt_category": prompt_category,
        "prompt_strata": prompt_strata,
        "vector_ids": vector_ids,
        "phase_by_id": phase_by_id,
    }


def _point_member(member: Mapping[str, Any]) -> dict[str, Any]:
    arms: dict[str, dict[str, float | int]] = {}
    for arm in ARMS:
        rows = [row for row in member["rows"] if row["arm"] == arm]
        if not rows:
            _fail_input("EMPTY_ARM", f"{member['member_id']}:{arm}")
        judge_denominator = len(rows)
        judge_rate = math.fsum(float(row["judge"]) for row in rows) / judge_denominator
        selected = [row for row in rows if row["selected"]]
        if not selected:
            _fail_input("INVALID_RESIDUAL_DENOMINATOR", f"{member['member_id']}:{arm}")
        residual_weights: list[float] = []
        residual_terms: list[float] = []
        for row in selected:
            _, _, pi = _fraction(row["pi"], f"pi:{row['response_id']}")
            weight = 1.0 / pi
            residual_weights.append(weight)
            residual_terms.append(weight * (row["gold"] - row["judge"]))
        residual_denominator = math.fsum(residual_weights)
        if not math.isfinite(residual_denominator) or residual_denominator <= 0.0:
            _fail_input("INVALID_RESIDUAL_DENOMINATOR", f"{member['member_id']}:{arm}")
        residual = math.fsum(residual_terms) / residual_denominator
        unbounded = judge_rate + residual
        corrected = min(1.0, max(0.0, unbounded))
        if not all(math.isfinite(value) for value in (judge_rate, residual, unbounded, corrected)):
            _fail_input("NONFINITE_VALUE", f"{member['member_id']}:{arm}")
        arms[arm] = {
            "judge_denominator": judge_denominator,
            "selected_residual_n": len(selected),
            "judge_rate": judge_rate,
            "hajek_residual": residual,
            "unbounded": unbounded,
            "corrected": corrected,
            "clipped": corrected != unbounded,
        }
    theta = float(arms["all-token"]["corrected"]) - float(arms["content-token"]["corrected"])
    if not math.isfinite(theta):
        _fail_input("NONFINITE_VALUE", f"theta:{member['member_id']}")
    return {"theta_hat": theta, "arms": arms}


def point_estimates(payload: Mapping[str, Any]) -> dict[str, Any]:
    validate_input(payload)
    return {member["member_id"]: _point_member(member) for member in payload["members"]}


def _draw_multiplicity(ids: Sequence[str], rng: Sha256CounterRng) -> dict[str, int]:
    counts = Counter(ids[rng.randbelow(len(ids))] for _ in range(len(ids)))
    return {item: counts.get(item, 0) for item in ids}


def _draw_plan(payload: Mapping[str, Any], prepared: Mapping[str, Any], block_id: str, replicate: int) -> dict[str, Any]:
    prompt_multiplicity: dict[str, int] = {}
    for stratum in payload["prompt_frame"]["strata"]:
        unit = prompt_sync_unit(block_id, payload["prompt_frame"]["frame_sha256"], stratum["stratum_id"])
        _, seed = seed_material(block_id, unit, replicate)
        prompt_multiplicity.update(_draw_multiplicity(stratum["prompt_ids"], Sha256CounterRng(seed)))

    phase_g: dict[str, float] = {}
    for stratum in payload["phase_two_frame"]["strata"]:
        sampled = stratum["sampled_response_ids"]
        sample_n = len(sampled)
        population_n = len(stratum["population_response_ids"])
        if sample_n == population_n:
            for response_id in sampled:
                phase_g[response_id] = 1.0
            continue
        unit = phase_two_sync_unit(
            block_id, payload["phase_two_frame"]["frame_sha256"], stratum["stratum_id"]
        )
        _, seed = seed_material(block_id, unit, replicate)
        rng = Sha256CounterRng(seed)
        counts = Counter(sampled[rng.randbelow(sample_n)] for _ in range(sample_n - 1))
        factor = math.sqrt(1.0 - (sample_n / population_n))
        for response_id in sampled:
            phase_g[response_id] = 1.0 + factor * (
                sample_n * counts.get(response_id, 0) / (sample_n - 1) - 1.0
            )

    vector_multiplicity = {vector_id: 1 for vector_id in prepared["vector_ids"]}
    if block_id == BLOCKS["vector"]:
        unit = vector_sync_unit(
            block_id, payload["vector_frame"]["frame_sha256"], payload["vector_frame"]["frame_id"]
        )
        _, seed = seed_material(block_id, unit, replicate)
        vector_multiplicity = _draw_multiplicity(prepared["vector_ids"], Sha256CounterRng(seed))
    return {
        "prompt_multiplicity": prompt_multiplicity,
        "phase_g": phase_g,
        "vector_multiplicity": vector_multiplicity,
    }


def draw_consumption_order(payload: Mapping[str, Any], block_id: str) -> list[dict[str, Any]]:
    """Return the exact independent-stream initialization and draw order per replicate."""
    validate_input(payload)
    if block_id not in BLOCKS.values():
        _fail_input("INVALID_BLOCK_ID", block_id)
    result: list[dict[str, Any]] = []
    for stratum in payload["prompt_frame"]["strata"]:
        result.append({
            "axis": "prompt-stratum",
            "entity_or_stratum_id": stratum["stratum_id"],
            "draws_per_replicate": len(stratum["prompt_ids"]),
            "sync_unit_id": prompt_sync_unit(
                block_id, payload["prompt_frame"]["frame_sha256"], stratum["stratum_id"]
            ),
        })
    for stratum in payload["phase_two_frame"]["strata"]:
        sample_n = len(stratum["sampled_response_ids"])
        population_n = len(stratum["population_response_ids"])
        census = sample_n == population_n
        result.append({
            "axis": "phase2-stratum",
            "entity_or_stratum_id": stratum["stratum_id"],
            "draws_per_replicate": 0 if census else sample_n - 1,
            "census": census,
            "sync_unit_id": phase_two_sync_unit(
                block_id, payload["phase_two_frame"]["frame_sha256"], stratum["stratum_id"]
            ),
        })
    if block_id == BLOCKS["vector"]:
        result.append({
            "axis": "vector",
            "entity_or_stratum_id": payload["vector_frame"]["frame_id"],
            "draws_per_replicate": 20,
            "sync_unit_id": vector_sync_unit(
                block_id, payload["vector_frame"]["frame_sha256"], payload["vector_frame"]["frame_id"]
            ),
        })
    for index, item in enumerate(result, start=1):
        item["order"] = index
    return result


def _replicate_member(member: Mapping[str, Any], plan: Mapping[str, Any]) -> float:
    corrected: dict[str, float] = {}
    for arm in ARMS:
        rows = [row for row in member["rows"] if row["arm"] == arm]
        judge_weights: list[float] = []
        judge_terms: list[float] = []
        residual_weights: list[float] = []
        residual_terms: list[float] = []
        for row in rows:
            multiplicity = (
                plan["prompt_multiplicity"][row["prompt_id"]]
                * plan["vector_multiplicity"][row["vector_id"]]
            )
            judge_weights.append(float(multiplicity))
            judge_terms.append(float(multiplicity * row["judge"]))
            if row["selected"]:
                _, _, pi = _fraction(row["pi"], f"pi:{row['response_id']}")
                weight = multiplicity * (1.0 / pi) * plan["phase_g"][row["response_id"]]
                residual_weights.append(weight)
                residual_terms.append(weight * (row["gold"] - row["judge"]))
        judge_denominator = math.fsum(judge_weights)
        residual_denominator = math.fsum(residual_weights)
        if (
            not math.isfinite(judge_denominator)
            or judge_denominator <= 0.0
            or not math.isfinite(residual_denominator)
            or residual_denominator <= 0.0
        ):
            raise ArithmeticError("replicate denominator invalid")
        judge_rate = math.fsum(judge_terms) / judge_denominator
        residual = math.fsum(residual_terms) / residual_denominator
        unbounded = judge_rate + residual
        value = min(1.0, max(0.0, unbounded))
        if not all(math.isfinite(item) for item in (judge_rate, residual, unbounded, value)):
            raise ArithmeticError("replicate statistic nonfinite")
        corrected[arm] = value
    theta = corrected["all-token"] - corrected["content-token"]
    if not math.isfinite(theta):
        raise ArithmeticError("replicate theta nonfinite")
    return theta


def validate_weight_diagnostics(
    base_weights: Sequence[float], member_id: str
) -> dict[str, float | int]:
    weight_sum = math.fsum(base_weights)
    weight_square_sum = math.fsum(weight * weight for weight in base_weights)
    if (
        not math.isfinite(weight_sum)
        or not math.isfinite(weight_square_sum)
        or weight_sum <= 0.0
        or weight_square_sum <= 0.0
    ):
        _fail_input("INVALID_WEIGHT_DIAGNOSTIC", member_id)
    kish_ess = weight_sum * weight_sum / weight_square_sum
    max_normalized_weight = max(base_weights) / weight_sum
    if not math.isfinite(kish_ess) or kish_ess < 20.0:
        _fail_input("KISH_ESS_BELOW_20", member_id)
    if not math.isfinite(max_normalized_weight) or max_normalized_weight > 0.20:
        _fail_input("MAX_NORMALIZED_WEIGHT_ABOVE_0_20", member_id)
    return {
        "selected_response_n": len(base_weights),
        "base_weight_sum": weight_sum,
        "kish_ess": kish_ess,
        "max_normalized_weight": max_normalized_weight,
    }


def _support_gate(payload: Mapping[str, Any]) -> dict[str, dict[str, float | int]]:
    diagnostics: dict[str, dict[str, float | int]] = {}
    for member in payload["members"]:
        prompts = {row["prompt_id"] for row in member["rows"]}
        vectors = {row["vector_id"] for row in member["rows"]}
        if len(prompts) < 15:
            raise NonEstimable(
                "INSUFFICIENT_CLUSTERS_NON_ESTIMABLE", "FEWER_THAN_15_UNIQUE_PROMPTS", member["member_id"]
            )
        if len(vectors) < 10:
            raise NonEstimable(
                "INSUFFICIENT_CLUSTERS_NON_ESTIMABLE", "FEWER_THAN_10_UNIQUE_VECTORS", member["member_id"]
            )
        base_weights = []
        for row in member["rows"]:
            if row["selected"]:
                _, _, pi = _fraction(row["pi"], f"pi:{row['response_id']}")
                base_weights.append(1.0 / pi)
        diagnostics[member["member_id"]] = validate_weight_diagnostics(
            base_weights, member["member_id"]
        )
    return diagnostics


def simultaneous_interval(payload: Mapping[str, Any], block_id: str) -> dict[str, Any]:
    if block_id not in BLOCKS.values():
        _fail_input("INVALID_BLOCK_ID", block_id)
    prepared = validate_input(payload)
    points = {member["member_id"]: _point_member(member) for member in payload["members"]}
    positivity_diagnostics = _support_gate(payload)
    successful: dict[str, list[float]] = {member_id: [] for member_id in MEMBER_ORDER}
    failed_replicates: list[int] = []
    first_plan: dict[str, Any] | None = None
    for replicate in range(1, REPLICATES + 1):
        plan = _draw_plan(payload, prepared, block_id, replicate)
        if first_plan is None:
            first_plan = plan
        try:
            values = {
                member["member_id"]: _replicate_member(member, plan)
                for member in payload["members"]
            }
        except (ArithmeticError, KeyError, ZeroDivisionError, OverflowError):
            failed_replicates.append(replicate)
            continue
        if not all(math.isfinite(value) for value in values.values()):
            failed_replicates.append(replicate)
            continue
        for member_id in MEMBER_ORDER:
            successful[member_id].append(values[member_id])

    count = len(successful[MEMBER_ORDER[0]])
    require_common_success(count)
    standard_errors = {member_id: sample_sd(successful[member_id]) for member_id in MEMBER_ORDER}
    for member_id, standard_error in standard_errors.items():
        if not math.isfinite(standard_error) or standard_error < SE_FLOOR:
            raise NonEstimable(
                "INVALID_SE_NON_ESTIMABLE", "SE_BELOW_1E_8_OR_NONFINITE", member_id
            )
    maxima = []
    for draw_index in range(count):
        statistics = [
            (successful[member_id][draw_index] - points[member_id]["theta_hat"])
            / standard_errors[member_id]
            for member_id in MEMBER_ORDER
        ]
        if not all(math.isfinite(value) for value in statistics):
            raise NonEstimable("INVALID_SE_NON_ESTIMABLE", "NONFINITE_STUDENTIZED_STATISTIC")
        maxima.append(max(abs(value) for value in statistics))
    critical = nearest_rank(maxima, 0.95)
    intervals: dict[str, Any] = {}
    for member_id in MEMBER_ORDER:
        point = points[member_id]["theta_hat"]
        se = standard_errors[member_id]
        endpoints = [point - critical * se, point + critical * se]
        if not all(math.isfinite(value) for value in endpoints):
            raise NonEstimable("NONFINITE_INTERVAL_NON_ESTIMABLE", "NONFINITE_ENDPOINT", member_id)
        intervals[member_id] = {
            "theta_hat": point,
            "se_fixed_scale": se,
            "simultaneous_95": endpoints,
        }
    assert first_plan is not None
    phase_preview = {}
    for stratum in payload["phase_two_frame"]["strata"]:
        response_id = stratum["sampled_response_ids"][0]
        phase_preview[stratum["stratum_id"]] = {
            "response_id": response_id,
            "g": first_plan["phase_g"][response_id],
            "census": len(stratum["sampled_response_ids"]) == len(stratum["population_response_ids"]),
            "draws_consumed": 0 if len(stratum["sampled_response_ids"]) == len(stratum["population_response_ids"]) else len(stratum["sampled_response_ids"]) - 1,
        }
    return {
        "algorithm": "matched_hajek_rao_wu_fixed_scale_max_abs_v1",
        "block_id": block_id,
        "family": block_id,
        "vector_aware": block_id == BLOCKS["vector"],
        "member_order": list(MEMBER_ORDER),
        "replicates_requested": REPLICATES,
        "common_success_required": COMMON_SUCCESS_REQUIRED,
        "common_successful": count,
        "failed_replicate_count": len(failed_replicates),
        "first_failed_replicates": failed_replicates[:10],
        "critical_value_nearest_rank_0_95": critical,
        "intervals": intervals,
        "positivity_diagnostics": positivity_diagnostics,
        "first_replicate_multiplicity": {
            "prompt": first_plan["prompt_multiplicity"],
            "vector": first_plan["vector_multiplicity"],
        },
        "first_replicate_phase_g_sha256": canonical_sha256(first_plan["phase_g"]),
        "first_replicate_phase_g_by_stratum": phase_preview,
    }


def rng_golden(payload: Mapping[str, Any]) -> dict[str, Any]:
    validate_input(payload)
    prompt_stratum = payload["prompt_frame"]["strata"][0]["stratum_id"]
    phase_stratum = next(
        item for item in payload["phase_two_frame"]["strata"]
        if len(item["sampled_response_ids"]) < len(item["population_response_ids"])
    )
    cases = [
        (
            BLOCKS["prompt"],
            prompt_sync_unit(BLOCKS["prompt"], payload["prompt_frame"]["frame_sha256"], prompt_stratum),
            1,
            7,
        ),
        (
            BLOCKS["prompt"],
            phase_two_sync_unit(
                BLOCKS["prompt"], payload["phase_two_frame"]["frame_sha256"], phase_stratum["stratum_id"]
            ),
            2,
            len(phase_stratum["sampled_response_ids"]),
        ),
        (
            BLOCKS["vector"],
            vector_sync_unit(
                BLOCKS["vector"], payload["vector_frame"]["frame_sha256"], payload["vector_frame"]["frame_id"]
            ),
            1,
            20,
        ),
    ]
    results = []
    for block_id, unit_id, replicate, upper in cases:
        seed_text, seed = seed_material(block_id, unit_id, replicate)
        rng = Sha256CounterRng(seed)
        blocks = [rng.block() for _ in range(4)]
        results.append({
            "block_id": block_id,
            "sync_unit_id": unit_id,
            "seed_payload": seed_text,
            "seed_hex": seed.hex(),
            "counter_block_hex": [block.hex() for block in blocks],
            "first_uint64_be": [int.from_bytes(block[:8], "big") for block in blocks],
            "first_mod_upper_without_rejection": [int.from_bytes(block[:8], "big") % upper for block in blocks],
            "upper": upper,
        })
    upper = 10
    limit = (1 << 64) - ((1 << 64) % upper)
    scripted_words = [limit, limit + 5, 123]
    scripted_iterator = iter(scripted_words)
    scripted_draw, scripted_consumed = rejection_sample(upper, lambda: next(scripted_iterator))
    return {
        "cases": results,
        "scripted_rejection": {
            "upper": upper,
            "limit": limit,
            "word_hex": [f"{word:016x}" for word in scripted_words],
            "accepted_draw": scripted_draw,
            "words_consumed": scripted_consumed,
            "rejected_word_count": scripted_consumed - 1,
        },
    }


def _armwise_clipping_point(payload: Mapping[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(payload)
    member = mutated["members"][0]
    for row in member["rows"]:
        if row["arm"] == "all-token":
            if row["selected"]:
                row["judge"] = 1
                row["gold"] = 0
            else:
                row["judge"] = 0
    return point_estimates(mutated)["P2-U(A)"]


def evaluate_success_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if fixture.get("synthetic_data") is not True:
        _fail_input("FIXTURE_NOT_MARKED_SYNTHETIC")
    payload = fixture["input"]
    points = point_estimates(payload)
    prompt = simultaneous_interval(payload, BLOCKS["prompt"])
    vector = simultaneous_interval(payload, BLOCKS["vector"])
    rng = rng_golden(payload)
    member_sync_rejected = False
    try:
        sync_unit_id({"axis": "prompt-stratum", "family": BLOCKS["prompt"], "member_id": "P2-U(A)"})
    except NonEstimable as error:
        member_sync_rejected = error.reason_code == "MEMBER_ID_IN_SYNC_UNIT"
    if not member_sync_rejected:
        raise AssertionError("member_id entered a shared sync unit")
    shared_unit = prompt_sync_unit(
        BLOCKS["prompt"], payload["prompt_frame"]["frame_sha256"],
        payload["prompt_frame"]["strata"][0]["stratum_id"],
    )
    return {
        "fixture_schema": "paper1-stage3-two-phase-success-v1",
        "synthetic_data": True,
        "normal_matched_point": points,
        "armwise_clipping_point": _armwise_clipping_point(payload),
        "prompt_phase_two": prompt,
        "vector_aware": vector,
        "draw_consumption_order": {
            block_id: {
                "full_trace_sha256": canonical_sha256(draw_consumption_order(payload, block_id)),
                "steps": [
                    f"{item['order']}:{item['axis']}:{item['entity_or_stratum_id']}:{item['draws_per_replicate']}"
                    for item in draw_consumption_order(payload, block_id)
                ],
            }
            for block_id in BLOCKS.values()
        },
        "rng_byte_golden": rng,
        "shared_rng": {
            "member_ids": list(MEMBER_ORDER),
            "member_id_in_sync_unit": False,
            "same_sync_unit_id": shared_unit,
            "same_seed_hex": seed_material(BLOCKS["prompt"], shared_unit, 1)[1].hex(),
        },
        "completion_boundary": {
            "9499": "FAIL",
            "9500": "PASS" if require_common_success(9500) == 9500 else "UNEXPECTED",
        },
        "census_strata": [
            item["stratum_id"] for item in payload["phase_two_frame"]["strata"]
        if len(item["sampled_response_ids"]) == len(item["population_response_ids"])
        ],
    }


def _strip_selection(row: dict[str, Any]) -> None:
    row["selected"] = False
    for field in ("gold", "pi"):
        row.pop(field, None)


def evaluate_failure_fixture(base_fixture: Mapping[str, Any], failure_fixture: Mapping[str, Any]) -> dict[str, Any]:
    if base_fixture.get("synthetic_data") is not True or failure_fixture.get("synthetic_data") is not True:
        _fail_input("FIXTURE_NOT_MARKED_SYNTHETIC")
    results = []
    for case in failure_fixture["cases"]:
        mutation = case["mutation"]
        payload = copy.deepcopy(base_fixture["input"])
        try:
            if mutation == "incomplete_pair":
                member = payload["members"][0]
                pair_id = member["rows"][0]["pair_id"]
                member["rows"] = [
                    row for row in member["rows"]
                    if not (row["pair_id"] == pair_id and row["arm"] == "content-token")
                ]
                payload = refresh_frame_hashes(payload)
                point_estimates(payload)
            elif mutation == "empty_arm":
                payload["members"][0]["rows"] = [
                    row for row in payload["members"][0]["rows"] if row["arm"] == "all-token"
                ]
                payload = refresh_frame_hashes(payload)
                point_estimates(payload)
            elif mutation == "invalid_pi":
                row = next(row for row in payload["members"][0]["rows"] if row["selected"])
                row["pi"] = "3/2"
                point_estimates(payload)
            elif mutation == "phase2_zero_sample":
                stratum = payload["phase_two_frame"]["strata"][0]
                stratum["n_h"] = 0
                stratum["sampled_response_ids"] = []
                payload = refresh_frame_hashes(payload)
                point_estimates(payload)
            elif mutation == "phase2_singleton_noncensus":
                stratum = next(item for item in payload["phase_two_frame"]["strata"] if item["n_h"] < item["N_h"])
                retained = stratum["sampled_response_ids"][:1]
                stratum["n_h"] = 1
                stratum["sampled_response_ids"] = retained
                for member in payload["members"]:
                    for row in member["rows"]:
                        if row["phase2_stratum_id"] == stratum["stratum_id"] and row["response_id"] not in retained:
                            _strip_selection(row)
                        elif row["phase2_stratum_id"] == stratum["stratum_id"]:
                            row["pi"] = f"1/{stratum['N_h']}"
                payload = refresh_frame_hashes(payload)
                point_estimates(payload)
            elif mutation == "nonfinite_value":
                _binary(math.inf, "judge:syn-A-00-all")
            elif mutation == "invalid_residual_denominator":
                for row in payload["members"][0]["rows"]:
                    if row["arm"] == "content-token" and row["selected"]:
                        _strip_selection(row)
                _point_member(payload["members"][0])
            elif mutation == "frame_hash_mismatch":
                payload["prompt_frame"]["frame_sha256"] = "0" * 64
                point_estimates(payload)
            elif mutation == "compound_hash_before_pi":
                payload["prompt_frame"]["frame_sha256"] = "0" * 64
                row = next(row for row in payload["members"][0]["rows"] if row["selected"])
                row["pi"] = "3/2"
                point_estimates(payload)
            elif mutation == "member_order":
                payload["members"] = list(reversed(payload["members"]))
                if [item.get("member_id") for item in payload["members"]] != list(MEMBER_ORDER):
                    _fail_input("MEMBER_ORDER")
            elif mutation == "insufficient_prompt_clusters":
                member = payload["members"][0]
                keep = {member["rows"][0]["prompt_id"]}
                member["rows"] = [row for row in member["rows"] if row["prompt_id"] in keep]
                member["rows"] = sorted(member["rows"], key=_row_key)
                retained_ids = {row["response_id"] for row in member["rows"]}
                for stratum in payload["phase_two_frame"]["strata"]:
                    if stratum["member_id"] != member["member_id"]:
                        continue
                    stratum["population_response_ids"] = [
                        item for item in stratum["population_response_ids"] if item in retained_ids
                    ]
                    stratum["sampled_response_ids"] = [
                        item for item in stratum["sampled_response_ids"] if item in retained_ids
                    ]
                    stratum["N_h"] = len(stratum["population_response_ids"])
                    stratum["n_h"] = len(stratum["sampled_response_ids"])
                for row in member["rows"]:
                    row["pi"] = "1/1"
                payload = refresh_frame_hashes(payload)
                simultaneous_interval(payload, BLOCKS["prompt"])
            elif mutation == "kish_ess_below_20":
                stratum = next(
                    item for item in payload["phase_two_frame"]["strata"]
                    if item["stratum_id"] == "h-T-all"
                )
                retained = stratum["sampled_response_ids"][:2]
                stratum["sampled_response_ids"] = retained
                stratum["n_h"] = len(retained)
                population_n = len(stratum["population_response_ids"])
                for member in payload["members"]:
                    for row in member["rows"]:
                        if row["phase2_stratum_id"] == "h-T-all" and row["response_id"] not in retained:
                            _strip_selection(row)
                        elif row["phase2_stratum_id"] == "h-T-all" and row["selected"]:
                            divisor = math.gcd(len(retained), population_n)
                            row["pi"] = f"{len(retained) // divisor}/{population_n // divisor}"
                payload = refresh_frame_hashes(payload)
                simultaneous_interval(payload, BLOCKS["prompt"])
            elif mutation == "max_normalized_weight_above_0_20":
                validate_weight_diagnostics([50.0] + [1.0] * 199, "P2-U(A)")
            elif mutation == "completion_9499":
                require_common_success(9499)
            elif mutation == "member_id_in_sync_unit":
                sync_unit_id({"axis": "prompt-stratum", "family": BLOCKS["prompt"], "member_id": "P2-U(A)"})
            else:
                raise AssertionError(f"unknown mutation: {mutation}")
        except NonEstimable as error:
            results.append({"case_id": case["case_id"], **error.as_dict()})
        else:
            results.append({
                "case_id": case["case_id"],
                "status": "UNEXPECTED_PASS",
                "reason_code": "NONE",
            })
    return {
        "fixture_schema": "paper1-stage3-two-phase-failure-v1",
        "synthetic_data": True,
        "results": results,
    }


def evaluate_schema_negative_fixture(
    base_fixture: Mapping[str, Any], schema_negative_fixture: Mapping[str, Any]
) -> dict[str, Any]:
    """Run synthetic member-cardinality/order/type witnesses without changing fixed goldens."""
    if (
        base_fixture.get("synthetic_data") is not True
        or schema_negative_fixture.get("synthetic_data") is not True
    ):
        _fail_input("FIXTURE_NOT_MARKED_SYNTHETIC")
    results = []
    for case in schema_negative_fixture["cases"]:
        payload = copy.deepcopy(base_fixture["input"])
        mutation = case["mutation"]
        try:
            if mutation == "third_member":
                payload["members"].append(copy.deepcopy(payload["members"][1]))
            elif mutation == "wrong_member_order":
                payload["members"] = list(reversed(payload["members"]))
            elif mutation == "wrong_member_type":
                payload["members"][0] = "synthetic-not-a-member-object"
            else:
                raise AssertionError(f"unknown schema-negative mutation: {mutation}")
            validate_input(payload)
        except NonEstimable as error:
            results.append({"case_id": case["case_id"], **error.as_dict()})
        else:
            results.append({
                "case_id": case["case_id"],
                "status": "UNEXPECTED_PASS",
                "reason_code": "NONE",
            })
    return {
        "fixture_schema": "paper1-stage3-two-phase-schema-negative-v1",
        "synthetic_data": True,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--block", choices=tuple(BLOCKS.values()))
    parser.add_argument("--point-only", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    try:
        result = point_estimates(payload) if args.point_only else simultaneous_interval(
            payload, args.block or BLOCKS["prompt"]
        )
    except NonEstimable as error:
        print(canonical_json(error.as_dict()))
        return 2
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
