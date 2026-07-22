"""Fail-closed Draft 2020-12 subset used by the retained golden verifier.

This is intentionally not a general JSON Schema implementation. It validates
the keywords reachable from ``#/$defs/harmfulClean`` in the bound retained
bootstrap schema and rejects every unsupported or malformed schema construct.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any


SUPPORTED_KEYWORDS = frozenset(
    {
        "$ref",
        "type",
        "const",
        "enum",
        "required",
        "properties",
        "additionalProperties",
        "minItems",
        "maxItems",
        "items",
        "minLength",
        "minimum",
        "description",
    }
)
SUPPORTED_TYPES = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})


class SchemaDefinitionError(ValueError):
    """The bound schema uses a construct outside this fail-closed subset."""


class InstanceValidationError(ValueError):
    """The instance does not satisfy the selected bound subschema."""

    def __init__(self, path: str, keyword: str, detail: str):
        self.path = path
        self.keyword = keyword
        self.detail = detail
        super().__init__(f"{path}:{keyword}:{detail}")


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _json_equal(left: Any, right: Any) -> bool:
    try:
        return json.dumps(left, allow_nan=False, sort_keys=True, separators=(",", ":")) == json.dumps(
            right, allow_nan=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as error:
        raise SchemaDefinitionError("const/enum contains a non-JSON value") from error


def _resolve_pointer(document: Mapping[str, Any], reference: str) -> Any:
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise SchemaDefinitionError(f"only nonempty internal JSON Pointer $ref is supported: {reference!r}")
    current: Any = document
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or part not in current:
            raise SchemaDefinitionError(f"unresolvable internal $ref: {reference}")
        current = current[part]
    return current


def _nonnegative_integer(value: Any, keyword: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SchemaDefinitionError(f"{keyword} must be a nonnegative integer")
    return value


def _check_schema(
    schema: Any,
    document: Mapping[str, Any],
    checked: set[int],
    active_refs: set[str],
) -> None:
    if isinstance(schema, bool):
        return
    if not isinstance(schema, Mapping):
        raise SchemaDefinitionError("schema node must be an object or boolean")
    identity = id(schema)
    if identity in checked:
        return
    checked.add(identity)
    unknown = set(schema) - SUPPORTED_KEYWORDS
    if unknown:
        raise SchemaDefinitionError(f"unsupported schema keywords: {sorted(unknown)}")

    if "$ref" in schema:
        reference = schema["$ref"]
        if reference in active_refs:
            raise SchemaDefinitionError(f"cyclic internal $ref is unsupported: {reference}")
        active_refs.add(reference)
        _check_schema(_resolve_pointer(document, reference), document, checked, active_refs)
        active_refs.remove(reference)
    if "type" in schema and (
        not isinstance(schema["type"], str) or schema["type"] not in SUPPORTED_TYPES
    ):
        raise SchemaDefinitionError(f"unsupported or malformed type: {schema['type']!r}")
    if "enum" in schema and (
        not isinstance(schema["enum"], list) or not schema["enum"]
    ):
        raise SchemaDefinitionError("enum must be a nonempty array")
    if "required" in schema:
        required = schema["required"]
        if (
            not isinstance(required, list)
            or any(not isinstance(item, str) for item in required)
            or len(required) != len(set(required))
        ):
            raise SchemaDefinitionError("required must be an array of unique strings")
    if "properties" in schema:
        properties = schema["properties"]
        if not isinstance(properties, Mapping) or any(not isinstance(key, str) for key in properties):
            raise SchemaDefinitionError("properties must be an object with string keys")
        for child in properties.values():
            _check_schema(child, document, checked, active_refs)
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        raise SchemaDefinitionError("this subset supports only boolean additionalProperties")
    for keyword in ("minItems", "maxItems", "minLength"):
        if keyword in schema:
            _nonnegative_integer(schema[keyword], keyword)
    if "minItems" in schema and "maxItems" in schema and schema["minItems"] > schema["maxItems"]:
        raise SchemaDefinitionError("minItems must not exceed maxItems")
    if "items" in schema:
        _check_schema(schema["items"], document, checked, active_refs)
    if "minimum" in schema:
        minimum = schema["minimum"]
        if (
            not isinstance(minimum, (int, float))
            or isinstance(minimum, bool)
            or not math.isfinite(float(minimum))
        ):
            raise SchemaDefinitionError("minimum must be a finite number")
    if "description" in schema and not isinstance(schema["description"], str):
        raise SchemaDefinitionError("description must be a string")


def _matches_type(instance: Any, type_name: str) -> bool:
    return {
        "object": isinstance(instance, Mapping),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "number": isinstance(instance, (int, float))
        and not isinstance(instance, bool)
        and math.isfinite(float(instance)),
        "boolean": isinstance(instance, bool),
        "null": instance is None,
    }[type_name]


def _validate(schema: Any, document: Mapping[str, Any], instance: Any, path: str) -> None:
    if schema is True:
        return
    if schema is False:
        raise InstanceValidationError(path, "false-schema", "instance is forbidden")
    if "$ref" in schema:
        _validate(_resolve_pointer(document, schema["$ref"]), document, instance, path)
    if "type" in schema and not _matches_type(instance, schema["type"]):
        raise InstanceValidationError(path, "type", f"expected {schema['type']}")
    if "const" in schema and not _json_equal(instance, schema["const"]):
        raise InstanceValidationError(path, "const", "value does not equal const")
    if "enum" in schema and not any(_json_equal(instance, item) for item in schema["enum"]):
        raise InstanceValidationError(path, "enum", "value is not in enum")

    if isinstance(instance, Mapping):
        if "required" in schema:
            missing = [key for key in schema["required"] if key not in instance]
            if missing:
                raise InstanceValidationError(path, "required", f"missing properties {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                raise InstanceValidationError(path, "additionalProperties", f"unexpected properties {extra}")
        for key, child_schema in properties.items():
            if key in instance:
                _validate(child_schema, document, instance[key], f"{path}.{key}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise InstanceValidationError(path, "minItems", f"{len(instance)}<{schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise InstanceValidationError(path, "maxItems", f"{len(instance)}>{schema['maxItems']}")
        if "items" in schema:
            for index, item in enumerate(instance):
                _validate(schema["items"], document, item, f"{path}[{index}]")

    if isinstance(instance, str) and "minLength" in schema and len(instance) < schema["minLength"]:
        raise InstanceValidationError(path, "minLength", f"{len(instance)}<{schema['minLength']}")
    if (
        "minimum" in schema
        and isinstance(instance, (int, float))
        and not isinstance(instance, bool)
        and instance < schema["minimum"]
    ):
        raise InstanceValidationError(path, "minimum", f"{instance}<{schema['minimum']}")


def validate_subschema(document: Mapping[str, Any], pointer: str, instance: Any) -> None:
    """Validate ``instance`` against one internal subschema in ``document``."""

    if not isinstance(document, Mapping):
        raise SchemaDefinitionError("schema document must be an object")
    schema = _resolve_pointer(document, pointer)
    _check_schema(schema, document, set(), set())
    _validate(schema, document, instance, "$")
