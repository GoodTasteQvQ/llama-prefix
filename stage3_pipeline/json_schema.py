"""Fail-closed JSON Schema subset for active Stage 3 runtime records."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any


class SchemaDefinitionError(ValueError):
    """An active schema uses an unsupported or malformed construct."""


class SchemaValidationError(ValueError):
    """An instance does not satisfy an active schema."""


_ANNOTATIONS = {"$schema", "$id", "title", "description"}
_KEYWORDS = _ANNOTATIONS | {
    "$defs",
    "$ref",
    "type",
    "const",
    "enum",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "pattern",
    "minimum",
    "maximum",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "if",
    "then",
    "else",
}
_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def _reject_constant(value: str) -> None:
    raise SchemaDefinitionError(f"non-standard JSON constant in schema: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SchemaDefinitionError(f"duplicate schema key: {key}")
        result[key] = value
    return result


@lru_cache(maxsize=32)
def load_schema(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        schema = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaDefinitionError(f"schema is unavailable or invalid: {path}") from exc
    if not isinstance(schema, Mapping):
        raise SchemaDefinitionError(f"schema must be an object: {path}")
    _check_schema(schema, schema, set())
    return schema


def _resolve(root: Mapping[str, Any], reference: Any) -> Any:
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise SchemaDefinitionError(f"only internal JSON Pointer references are supported: {reference!r}")
    node: Any = root
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, Mapping) or part not in node:
            raise SchemaDefinitionError(f"unresolvable schema reference: {reference}")
        node = node[part]
    return node


def _nonnegative_integer(value: Any, keyword: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SchemaDefinitionError(f"{keyword} must be a nonnegative integer")
    return value


def _check_schema(node: Any, root: Mapping[str, Any], active_refs: set[str]) -> None:
    if isinstance(node, bool):
        return
    if not isinstance(node, Mapping):
        raise SchemaDefinitionError("schema node must be an object or boolean")
    unknown = set(node) - _KEYWORDS
    if unknown:
        raise SchemaDefinitionError(f"unsupported schema keywords: {sorted(unknown)}")
    if "$ref" in node:
        reference = node["$ref"]
        if reference in active_refs:
            raise SchemaDefinitionError(f"cyclic schema reference: {reference}")
        active_refs.add(reference)
        _check_schema(_resolve(root, reference), root, active_refs)
        active_refs.remove(reference)
    if "$defs" in node:
        definitions = node["$defs"]
        if not isinstance(definitions, Mapping):
            raise SchemaDefinitionError("$defs must be an object")
        for child in definitions.values():
            _check_schema(child, root, active_refs)
    if "type" in node:
        values = [node["type"]] if isinstance(node["type"], str) else node["type"]
        if not isinstance(values, list) or not values or any(value not in _TYPES for value in values):
            raise SchemaDefinitionError(f"unsupported or malformed type: {node['type']!r}")
    if "enum" in node and (not isinstance(node["enum"], list) or not node["enum"]):
        raise SchemaDefinitionError("enum must be a nonempty array")
    if "required" in node:
        required = node["required"]
        if (
            not isinstance(required, list)
            or any(not isinstance(item, str) for item in required)
            or len(required) != len(set(required))
        ):
            raise SchemaDefinitionError("required must contain unique strings")
    if "properties" in node:
        properties = node["properties"]
        if not isinstance(properties, Mapping):
            raise SchemaDefinitionError("properties must be an object")
        for child in properties.values():
            _check_schema(child, root, active_refs)
    if "additionalProperties" in node and not isinstance(node["additionalProperties"], bool):
        raise SchemaDefinitionError("only boolean additionalProperties is supported")
    for keyword in ("items", "not", "if", "then", "else"):
        if keyword in node:
            _check_schema(node[keyword], root, active_refs)
    for keyword in ("prefixItems", "allOf", "anyOf", "oneOf"):
        if keyword in node:
            children = node[keyword]
            if not isinstance(children, list) or (keyword != "prefixItems" and not children):
                raise SchemaDefinitionError(f"{keyword} must be an array")
            for child in children:
                _check_schema(child, root, active_refs)
    for keyword in ("minItems", "maxItems", "minLength"):
        if keyword in node:
            _nonnegative_integer(node[keyword], keyword)
    if node.get("minItems", 0) > node.get("maxItems", math.inf):
        raise SchemaDefinitionError("minItems must not exceed maxItems")
    if "uniqueItems" in node and not isinstance(node["uniqueItems"], bool):
        raise SchemaDefinitionError("uniqueItems must be boolean")
    if "pattern" in node:
        if not isinstance(node["pattern"], str):
            raise SchemaDefinitionError("pattern must be a string")
        try:
            re.compile(node["pattern"])
        except re.error as exc:
            raise SchemaDefinitionError("pattern is not a valid regular expression") from exc
    for keyword in ("minimum", "maximum"):
        if keyword in node:
            value = node[keyword]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
            ):
                raise SchemaDefinitionError(f"{keyword} must be finite")


def _matches_type(value: Any, type_name: str) -> bool:
    return {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value)),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }[type_name]


def _json_key(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise SchemaValidationError("instance contains a non-JSON value") from exc


def _try_validate(node: Any, root: Mapping[str, Any], value: Any, path: str) -> str | None:
    try:
        _validate(node, root, value, path)
    except SchemaValidationError as exc:
        return str(exc)
    return None


def _validate(node: Any, root: Mapping[str, Any], value: Any, path: str) -> None:
    if node is True:
        return
    if node is False:
        raise SchemaValidationError(f"{path}: forbidden by false schema")
    if "$ref" in node:
        _validate(_resolve(root, node["$ref"]), root, value, path)
    for child in node.get("allOf", []):
        _validate(child, root, value, path)
    if "anyOf" in node:
        errors = [_try_validate(child, root, value, path) for child in node["anyOf"]]
        if all(error is not None for error in errors):
            raise SchemaValidationError(f"{path}: no anyOf branch matched")
    if "oneOf" in node:
        matches = sum(_try_validate(child, root, value, path) is None for child in node["oneOf"])
        if matches != 1:
            raise SchemaValidationError(f"{path}: expected exactly one oneOf match, got {matches}")
    if "not" in node and _try_validate(node["not"], root, value, path) is None:
        raise SchemaValidationError(f"{path}: forbidden not-schema matched")
    if "if" in node:
        branch = "then" if _try_validate(node["if"], root, value, path) is None else "else"
        if branch in node:
            _validate(node[branch], root, value, path)
    if "type" in node:
        candidates = [node["type"]] if isinstance(node["type"], str) else node["type"]
        if not any(_matches_type(value, candidate) for candidate in candidates):
            raise SchemaValidationError(f"{path}: type mismatch; expected {candidates}")
    if "const" in node and _json_key(value) != _json_key(node["const"]):
        raise SchemaValidationError(f"{path}: const mismatch")
    if "enum" in node and all(_json_key(value) != _json_key(item) for item in node["enum"]):
        raise SchemaValidationError(f"{path}: enum mismatch")
    if isinstance(value, Mapping):
        missing = [key for key in node.get("required", []) if key not in value]
        if missing:
            raise SchemaValidationError(f"{path}: missing required fields {missing}")
        properties = node.get("properties", {})
        if node.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise SchemaValidationError(f"{path}: unexpected fields {extra}")
        for key, child in properties.items():
            if key in value:
                _validate(child, root, value[key], f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < node.get("minItems", 0):
            raise SchemaValidationError(f"{path}: too few items")
        if "maxItems" in node and len(value) > node["maxItems"]:
            raise SchemaValidationError(f"{path}: too many items")
        if node.get("uniqueItems"):
            keys = [_json_key(item) for item in value]
            if len(keys) != len(set(keys)):
                raise SchemaValidationError(f"{path}: duplicate items")
        prefix = node.get("prefixItems", [])
        for index, child in enumerate(prefix[: len(value)]):
            _validate(child, root, value[index], f"{path}[{index}]")
        if "items" in node:
            for index in range(len(prefix), len(value)):
                _validate(node["items"], root, value[index], f"{path}[{index}]")
    if isinstance(value, str):
        if len(value) < node.get("minLength", 0):
            raise SchemaValidationError(f"{path}: string is too short")
        if "pattern" in node and re.fullmatch(node["pattern"], value) is None:
            raise SchemaValidationError(f"{path}: pattern mismatch")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            raise SchemaValidationError(f"{path}: number is nonfinite")
        if "minimum" in node and value < node["minimum"]:
            raise SchemaValidationError(f"{path}: below minimum")
        if "maximum" in node and value > node["maximum"]:
            raise SchemaValidationError(f"{path}: above maximum")


def validate_schema(instance: Any, schema_path: Path) -> None:
    schema = load_schema(schema_path.resolve())
    _validate(schema, schema, instance, "$")
