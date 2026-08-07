"""Minimal P1 development smoke rendering and resid-pre measurement core."""

from __future__ import annotations

import gc
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

import torch

from scripts.stage3_production.validate_stage3_development_inputs import (
    _resolve_repo_file,
    _strict_json_object,
    validate_dataset_entries,
    validate_development_inputs,
    validate_static_config,
)

from .core import PROTOCOL_VERSION, PipelineError, canonical_sha256
from .real_backend import AutoModelForCausalLM, inspect_local_model_assets
from .records import validate_p1_record


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/stage3/qwen25_p1_measurement_development_v1.json"
DEFAULT_SYSTEM_CONTENT = (
    "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
)
EXPECTED_DEVELOPMENT_INPUT = (
    "configs/stage3/qwen25_stage3_development_inputs_v1.json"
)
EXPECTED_OUTPUT_ROOT = ".codex-temp/stage3_p1_smoke_runs"
EXPECTED_PROMPTS = (
    {
        "domain": "harmful",
        "active_entry_relative_path": "configs/stage3/p1_harmful_do_not_answer_v1.json",
        "source_id": 774,
        "identity_sha256": "88c647285a6bea65113805c27efe841706864075bdb86071005049aa1d8b0687",
    },
    {
        "domain": "benign",
        "active_entry_relative_path": "configs/stage3/p1_benign_v1.json",
        "source_id": (
            "databricks/databricks-dolly-15k@"
            "bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a:"
            "databricks-dolly-15k.jsonl:default/train:row=00038"
        ),
        "identity_sha256": "18deb928ba9abf39dfcfe7b8bc1728eb08c82a4039bc75cee7e019ce2d98c16b",
    },
)

PADDING = "padding"
SPECIAL_CONTROL = "special control"
SYSTEM_CONTENT = "system content"
USER_CONTENT = "user content"
ASSISTANT_PREAMBLE = "assistant preamble"
TEMPLATE_WHITESPACE = "template whitespace/newline"
ROLE_TEMPLATE_DELIMITER = "role/template delimiter"
UNRESOLVED = "unresolved"

_CONFIG_FIELDS = (
    "schema_version",
    "status",
    "run_mode",
    "development_input_config_relative_path",
    "paper_result_eligible",
    "formal_experiment_run",
    "behavior",
    "prompts",
    "output_root",
)
_BEHAVIOR_FIELDS = (
    "checkpoint_path",
    "tokenizer_path",
    "dtype",
    "device",
    "trust_remote_code",
    "trust_remote_code_reason",
    "layer",
    "hook_site",
    "batch_size",
)
_PROMPT_FIELDS = (
    "domain",
    "active_entry_relative_path",
    "source_id",
    "identity_sha256",
)


class P1SmokeCoreError(PipelineError):
    """A smoke-core input or execution contract failed closed."""


def _exact_ordered_fields(
    value: Any, expected: tuple[str, ...], label: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or tuple(value) != expected:
        raise P1SmokeCoreError(f"{label} exact ordered fields mismatch")
    return value


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_smoke_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the sole supported 1 harmful + 1 benign development smoke."""
    actual = dict(_exact_ordered_fields(config, _CONFIG_FIELDS, "P1 smoke config"))
    expected_scalars = {
        "schema_version": "paper1-stage3-p1-measurement-development-v1",
        "status": "development_smoke_only",
        "run_mode": "smoke",
        "development_input_config_relative_path": EXPECTED_DEVELOPMENT_INPUT,
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "output_root": EXPECTED_OUTPUT_ROOT,
    }
    for field, expected in expected_scalars.items():
        value = actual[field]
        if (value is not expected) if isinstance(expected, bool) else (value != expected):
            raise P1SmokeCoreError(f"P1 smoke config {field} mismatch")

    behavior = dict(
        _exact_ordered_fields(actual["behavior"], _BEHAVIOR_FIELDS, "behavior")
    )
    expected_behavior = {
        "checkpoint_path": "/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct",
        "tokenizer_path": "/data/goodtaste_workspace/models/Qwen2.5-7B-Instruct",
        "dtype": "bfloat16",
        "device": "cuda:0",
        "trust_remote_code": False,
        "trust_remote_code_reason": None,
        "layer": 9,
        "hook_site": "resid_pre",
        "batch_size": 1,
    }
    if behavior != expected_behavior:
        raise P1SmokeCoreError("P1 smoke behavior metadata mismatch")

    prompts = actual["prompts"]
    if not isinstance(prompts, list) or len(prompts) != 2:
        raise P1SmokeCoreError("smoke requires exactly 1 harmful + 1 benign prompt")
    normalized_prompts: list[dict[str, Any]] = []
    for index, expected in enumerate(EXPECTED_PROMPTS):
        prompt = dict(
            _exact_ordered_fields(prompts[index], _PROMPT_FIELDS, f"prompts[{index}]")
        )
        if prompt != expected or not _valid_sha256(prompt["identity_sha256"]):
            raise P1SmokeCoreError(f"prompts[{index}] fixed identity mismatch")
        normalized_prompts.append(prompt)
    if [prompt["domain"] for prompt in normalized_prompts] != ["harmful", "benign"]:
        raise P1SmokeCoreError("smoke requires exactly 1 harmful + 1 benign prompt")

    actual["behavior"] = behavior
    actual["prompts"] = normalized_prompts
    return actual


def load_smoke_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return validate_smoke_config(_strict_json_object(path.resolve(), "P1 smoke config"))


def _development_config(config: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    path = _resolve_repo_file(
        repo_root,
        config["development_input_config_relative_path"],
        "development_input_config_relative_path",
    )
    return validate_static_config(_strict_json_object(path, "development input config"))


def _selected_prompt_records(
    config: Mapping[str, Any], development: Mapping[str, Any], repo_root: Path
) -> tuple[list[dict[str, Any]], str]:
    datasets = {
        item["active_entry_relative_path"]: item for item in development["datasets"]
    }
    requested = []
    for prompt in config["prompts"]:
        try:
            requested.append(datasets[prompt["active_entry_relative_path"]])
        except KeyError as exc:
            raise P1SmokeCoreError(
                "smoke active entry is absent from the development input config"
            ) from exc
    validated = validate_dataset_entries(repo_root, requested)

    selected_records: list[dict[str, Any]] = []
    pinned_template_sha256 = ""
    for prompt, dataset, validated_entry in zip(
        config["prompts"], requested, validated, strict=True
    ):
        active_path = _resolve_repo_file(
            repo_root,
            dataset["active_entry_relative_path"],
            f"{prompt['domain']} active entry",
        )
        active = _strict_json_object(active_path, f"{prompt['domain']} active entry")
        selected_path = _resolve_repo_file(
            repo_root,
            validated_entry["selected_relative_path"],
            f"{prompt['domain']} selected dataset",
        )
        selected = _strict_json_object(selected_path, f"{prompt['domain']} selected dataset")
        matches = [
            record
            for record in selected["records"]
            if isinstance(record, Mapping) and record.get("source_id") == prompt["source_id"]
        ]
        if len(matches) != 1:
            raise P1SmokeCoreError(
                f"{prompt['domain']} fixed smoke prompt is missing or duplicated"
            )
        record = dict(matches[0])
        if prompt["domain"] == "harmful":
            content = record.get("question")
            observed_identity = record.get("record_identity_sha256")
            if (
                not isinstance(content, str)
                or not content
                or hashlib.sha256(content.encode("utf-8")).hexdigest()
                != record.get("question_sha256")
            ):
                raise P1SmokeCoreError("harmful smoke prompt content identity mismatch")
            messages = [{"role": "user", "content": content}]
        else:
            content = record.get("prompt")
            messages = record.get("messages")
            observed_identity = record.get("prompt_identity_sha256")
            if (
                not isinstance(content, str)
                or not content
                or messages != [{"role": "user", "content": content}]
                or hashlib.sha256(content.encode("utf-8")).hexdigest()
                != record.get("prompt_sha256")
            ):
                raise P1SmokeCoreError("benign smoke prompt content identity mismatch")
            pinned_template_sha256 = active.get("chat_template_sha256", "")
            if not _valid_sha256(pinned_template_sha256):
                raise P1SmokeCoreError("benign active entry lacks pinned chat template identity")
        if observed_identity != prompt["identity_sha256"]:
            raise P1SmokeCoreError(f"{prompt['domain']} smoke prompt identity mismatch")
        selected_records.append(
            {
                "domain": prompt["domain"],
                "source_id": prompt["source_id"],
                "identity_sha256": prompt["identity_sha256"],
                "content": content,
                "messages": messages,
                "active_entry_relative_path": prompt["active_entry_relative_path"],
                "selected_relative_path": validated_entry["selected_relative_path"],
            }
        )
    return selected_records, pinned_template_sha256


def _unique_span(text: str, content: str, label: str) -> tuple[int, int]:
    start = text.find(content)
    if start < 0 or text.find(content, start + 1) >= 0:
        raise P1SmokeCoreError(f"rendered {label} span is not uniquely identifiable")
    return start, start + len(content)


def _flat_values(value: Any, label: str) -> list[Any]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, tuple):
        value = list(value)
    if not isinstance(value, list):
        raise P1SmokeCoreError(f"tokenizer {label} must be a sequence")
    if len(value) == 1 and isinstance(value[0], (list, tuple)):
        value = list(value[0])
    return value


def _tokenize_with_offsets(tokenizer: Any, rendered: str) -> dict[str, list[Any]]:
    try:
        encoded = tokenizer(
            rendered,
            add_special_tokens=False,
            return_attention_mask=True,
            return_offsets_mapping=True,
            return_special_tokens_mask=True,
        )
    except Exception as exc:
        raise P1SmokeCoreError("tokenizer cannot produce required offset metadata") from exc
    if not isinstance(encoded, Mapping):
        try:
            encoded = dict(encoded)
        except Exception as exc:
            raise P1SmokeCoreError("tokenizer result is not a mapping") from exc
    required = ("input_ids", "attention_mask", "special_tokens_mask", "offset_mapping")
    if any(field not in encoded for field in required):
        raise P1SmokeCoreError("tokenizer omitted required token metadata")
    flattened = {field: _flat_values(encoded[field], field) for field in required}
    lengths = {len(values) for values in flattened.values()}
    if len(lengths) != 1:
        raise P1SmokeCoreError("tokenizer metadata lengths differ")
    return flattened


def _overlaps(offset: tuple[int, int], span: tuple[int, int]) -> bool:
    return offset[0] < span[1] and span[0] < offset[1]


def _inside(offset: tuple[int, int], span: tuple[int, int]) -> bool:
    return span[0] <= offset[0] and offset[1] <= span[1]


def render_and_extract_t0(tokenizer: Any, user_content: str) -> dict[str, Any]:
    """Render the pinned user-only T0 branch and classify actual tokenizer offsets."""
    if not isinstance(user_content, str) or not user_content:
        raise P1SmokeCoreError("T0 user content must be nonempty text")
    template = getattr(tokenizer, "chat_template", None)
    if not isinstance(template, str) or DEFAULT_SYSTEM_CONTENT not in template:
        raise P1SmokeCoreError("tokenizer lacks the pinned Qwen default system branch")
    messages = [{"role": "user", "content": user_content}]
    try:
        rendered = tokenizer.apply_chat_template(
            messages,
            tools=[],
            tokenize=False,
            add_generation_prompt=True,
        )
        without_generation = tokenizer.apply_chat_template(
            messages,
            tools=[],
            tokenize=False,
            add_generation_prompt=False,
        )
    except Exception as exc:
        raise P1SmokeCoreError("T0 chat template rendering failed") from exc
    if (
        not isinstance(rendered, str)
        or not isinstance(without_generation, str)
        or not rendered
        or not without_generation
        or not rendered.startswith(without_generation)
        or len(rendered) == len(without_generation)
    ):
        raise P1SmokeCoreError("assistant generation preamble is not uniquely identifiable")

    spans = {
        SYSTEM_CONTENT: _unique_span(rendered, DEFAULT_SYSTEM_CONTENT, "system content"),
        USER_CONTENT: _unique_span(rendered, user_content, "user content"),
        ASSISTANT_PREAMBLE: (len(without_generation), len(rendered)),
    }
    ordered_spans = sorted(spans.values())
    if any(left[1] > right[0] for left, right in zip(ordered_spans, ordered_spans[1:])):
        raise P1SmokeCoreError("T0 semantic spans overlap")

    encoded = _tokenize_with_offsets(tokenizer, rendered)
    try:
        input_ids = [int(value) for value in encoded["input_ids"]]
        attention_mask = [int(value) for value in encoded["attention_mask"]]
        special_tokens_mask = [int(value) for value in encoded["special_tokens_mask"]]
    except (TypeError, ValueError) as exc:
        raise P1SmokeCoreError("token IDs and masks must be integer-valued") from exc
    if any(value not in (0, 1) for value in attention_mask + special_tokens_mask):
        raise P1SmokeCoreError("token masks must be binary")
    special_ids = {int(value) for value in getattr(tokenizer, "all_special_ids", ())}

    offsets: list[list[int]] = []
    classifications: list[str] = []
    valid_membership: list[bool] = []
    content_membership: list[bool] = []
    for token_id, attended, special_mask, raw_offset in zip(
        input_ids,
        attention_mask,
        special_tokens_mask,
        encoded["offset_mapping"],
        strict=True,
    ):
        if hasattr(raw_offset, "tolist"):
            raw_offset = raw_offset.tolist()
        valid_offset = (
            isinstance(raw_offset, (list, tuple))
            and len(raw_offset) == 2
            and all(type(value) is int for value in raw_offset)
            and 0 <= raw_offset[0] <= raw_offset[1] <= len(rendered)
        )
        offset = (raw_offset[0], raw_offset[1]) if valid_offset else (0, 0)
        offsets.append([offset[0], offset[1]])

        if attended == 0:
            classification = PADDING
        elif special_mask == 1 or token_id in special_ids:
            classification = SPECIAL_CONTROL
        elif not valid_offset or offset[0] == offset[1]:
            classification = UNRESOLVED
        else:
            overlapping = [name for name, span in spans.items() if _overlaps(offset, span)]
            if len(overlapping) == 1 and _inside(offset, spans[overlapping[0]]):
                classification = overlapping[0]
            elif overlapping:
                classification = UNRESOLVED
            else:
                token_text = rendered[offset[0] : offset[1]]
                classification = (
                    TEMPLATE_WHITESPACE if token_text.isspace() else ROLE_TEMPLATE_DELIMITER
                )
        is_valid = attended == 1 and classification != SPECIAL_CONTROL
        is_content = is_valid and classification in {SYSTEM_CONTENT, USER_CONTENT}
        classifications.append(classification)
        valid_membership.append(is_valid)
        content_membership.append(is_content)

    valid_positions = [index for index, value in enumerate(valid_membership) if value]
    content_positions = [index for index, value in enumerate(content_membership) if value]
    unresolved_positions = [
        index
        for index, classification in enumerate(classifications)
        if attention_mask[index] == 1 and classification == UNRESOLVED
    ]
    identity_payload = {
        "messages": messages,
        "tools": [],
        "add_generation_prompt": True,
        "default_system_content": DEFAULT_SYSTEM_CONTENT,
        "rendered_text_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "special_token_ids": sorted(special_ids),
        "special_tokens_mask": special_tokens_mask,
        "offset_mapping": offsets,
        "token_classification": classifications,
        "valid_token_membership": valid_membership,
        "content_token_membership": content_membership,
    }
    return {
        **identity_payload,
        "rendered_text": rendered,
        "system_content_span": list(spans[SYSTEM_CONTENT]),
        "user_content_span": list(spans[USER_CONTENT]),
        "assistant_preamble_span": list(spans[ASSISTANT_PREAMBLE]),
        "valid_token_positions": valid_positions,
        "content_token_positions": content_positions,
        "unresolved_valid_token_positions": unresolved_positions,
        "valid_token_count": len(valid_positions),
        "content_token_count": len(content_positions),
        "unresolved_valid_token_count": len(unresolved_positions),
        "render_complete": True,
        "valid_mask_complete": True,
        "complete_case": (
            not unresolved_positions and bool(valid_positions) and bool(content_positions)
        ),
        "extraction_identity_sha256": canonical_sha256(identity_payload),
    }


def _model_layers(model: Any) -> Any:
    layers = getattr(getattr(model, "model", None), "layers", None)
    if layers is None or not hasattr(layers, "__len__") or not hasattr(layers, "__getitem__"):
        raise P1SmokeCoreError("model does not expose transformer layers at model.layers")
    return layers


def measure_resid_pre(
    model: Any,
    model_inputs: Mapping[str, Any],
    extraction: Mapping[str, Any],
    *,
    layer: int = 9,
    hook_site: str = "resid_pre",
    batch_size: int = 1,
    torch_module: Any = torch,
) -> dict[str, Any]:
    """Capture a transformer layer input with a removable forward-pre-hook."""
    if layer != 9 or hook_site != "resid_pre" or batch_size != 1:
        raise P1SmokeCoreError("P1 smoke requires batch_size=1 layer=9 resid_pre")
    input_ids = model_inputs.get("input_ids")
    attention_mask = model_inputs.get("attention_mask")
    if (
        not isinstance(input_ids, torch_module.Tensor)
        or input_ids.ndim != 2
        or int(input_ids.shape[0]) != 1
        or not isinstance(attention_mask, torch_module.Tensor)
        or tuple(attention_mask.shape) != tuple(input_ids.shape)
    ):
        raise P1SmokeCoreError("forward inputs must contain matching rank-two batch-one tensors")
    token_count = len(extraction["input_ids"])
    if int(input_ids.shape[1]) != token_count:
        raise P1SmokeCoreError("forward input token sequence differs from extraction")
    if input_ids.detach().cpu().tolist()[0] != list(extraction["input_ids"]):
        raise P1SmokeCoreError("forward input token IDs differ from extraction")
    if attention_mask.detach().cpu().tolist()[0] != list(extraction["attention_mask"]):
        raise P1SmokeCoreError("forward attention mask differs from extraction")

    layers = _model_layers(model)
    if layer >= len(layers):
        raise P1SmokeCoreError("configured transformer layer is unavailable")
    captured: list[Any] = []

    def capture_layer_input(_module: Any, args: tuple[Any, ...]) -> None:
        if not args or not isinstance(args[0], torch_module.Tensor):
            raise P1SmokeCoreError("resid_pre hook received no tensor layer input")
        captured.append(args[0].detach().clone())

    handle = layers[layer].register_forward_pre_hook(capture_layer_input)
    try:
        with torch_module.no_grad():
            model(**dict(model_inputs))
    finally:
        handle.remove()

    base = {
        "layer": layer,
        "hook_site": hook_site,
        "batch_size": batch_size,
        "hook_removed": True,
        "activation_token_count": None,
        "token_norms_float32": None,
        "all_norm_sum": None,
        "content_norm_sum": None,
        "forward_complete": False,
        "required_norms_finite": False,
        "failure_code": None,
    }
    if len(captured) != 1:
        return {**base, "failure_code": "RESID_PRE_CAPTURE_COUNT"}
    activation = captured[0]
    if activation.ndim != 3 or int(activation.shape[0]) != 1:
        return {**base, "failure_code": "RESID_PRE_ACTIVATION_SHAPE"}
    activation_token_count = int(activation.shape[1])
    if activation_token_count != token_count:
        return {
            **base,
            "activation_token_count": activation_token_count,
            "failure_code": "ACTIVATION_TOKEN_LENGTH_MISMATCH",
        }

    norms = torch_module.linalg.vector_norm(activation[0].to(torch_module.float32), dim=-1)
    norm_values = [float(value) for value in norms.detach().cpu().tolist()]
    finite = all(math.isfinite(value) for value in norm_values)
    if not finite:
        return {
            **base,
            "activation_token_count": activation_token_count,
            "token_norms_float32": norm_values,
            "forward_complete": True,
            "failure_code": "NONFINITE_TOKEN_NORM",
        }
    valid_positions = list(extraction["valid_token_positions"])
    content_positions = list(extraction["content_token_positions"])
    all_sum = float(sum(norm_values[position] for position in valid_positions))
    content_sum = float(sum(norm_values[position] for position in content_positions))
    if not math.isfinite(all_sum) or not math.isfinite(content_sum):
        return {
            **base,
            "activation_token_count": activation_token_count,
            "token_norms_float32": norm_values,
            "forward_complete": True,
            "failure_code": "NONFINITE_NORM_SUM",
        }
    return {
        **base,
        "activation_token_count": activation_token_count,
        "token_norms_float32": norm_values,
        "all_norm_sum": all_sum,
        "content_norm_sum": content_sum,
        "forward_complete": True,
        "required_norms_finite": True,
    }


def build_p1_terminal_record(
    prompt: Mapping[str, Any],
    extraction: Mapping[str, Any],
    measurement: Mapping[str, Any],
    *,
    identity_complete: bool = True,
    identity_collision: bool = False,
) -> dict[str, Any]:
    """Build and validate the existing v3 P1 record with its failure precedence."""
    valid_count = int(extraction["valid_token_count"])
    content_count = int(extraction["content_token_count"])
    unresolved = int(extraction["unresolved_valid_token_count"])
    flags = {
        "identity_complete": bool(identity_complete),
        "render_complete": bool(extraction.get("render_complete", False)),
        "valid_mask_complete": bool(extraction.get("valid_mask_complete", False)),
        "forward_complete": bool(measurement.get("forward_complete", False)),
        "identity_collision": bool(identity_collision),
        "required_norms_finite": bool(measurement.get("required_norms_finite", False)),
    }
    all_sum = measurement.get("all_norm_sum")
    content_sum = measurement.get("content_norm_sum")
    complete = (
        flags["identity_complete"]
        and flags["render_complete"]
        and flags["valid_mask_complete"]
        and flags["forward_complete"]
        and not flags["identity_collision"]
        and flags["required_norms_finite"]
        and unresolved == 0
        and valid_count > 0
        and content_count > 0
        and content_count <= valid_count
        and all_sum is not None
        and content_sum is not None
    )
    if not flags["identity_complete"] or flags["identity_collision"]:
        terminal = "EXCLUDED_IDENTITY"
    elif not flags["render_complete"]:
        terminal = "EXCLUDED_RENDER"
    elif not flags["valid_mask_complete"]:
        terminal = "EXCLUDED_VALID_MASK"
    elif not flags["forward_complete"]:
        terminal = "EXCLUDED_FORWARD"
    elif unresolved:
        terminal = "EXCLUDED_UNRESOLVED"
    elif not flags["required_norms_finite"] or all_sum is None or content_sum is None:
        terminal = "EXCLUDED_NONFINITE"
    elif valid_count == 0 or content_count == 0 or content_count > valid_count:
        terminal = "EXCLUDED_ZERO_DENOMINATOR"
    else:
        terminal = "COMPLETE_CASE"
    record = {
        "schema_version": "paper1-stage3-p1-measurement-record-v3",
        "protocol_version": PROTOCOL_VERSION,
        "run_mode": "smoke",
        "paper_result_eligible": False,
        "logical_id": f"p1-smoke:{prompt['domain']}:{prompt['source_id']}",
        "identity_sha256": prompt["identity_sha256"],
        "prompt_id": str(prompt["source_id"]),
        "domain": prompt["domain"],
        **flags,
        "valid_token_count": valid_count,
        "content_token_count": content_count,
        "unresolved_valid_token_count": unresolved,
        "all_norm_sum": all_sum,
        "content_norm_sum": content_sum,
        "complete_case": complete,
        "terminal_status": terminal,
        "exclusion_reason": None if complete else terminal,
    }
    record["record_sha256"] = canonical_sha256(record)
    return validate_p1_record(record)


def _prepare_smoke(
    config_path: Path,
    *,
    repo_root: Path,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]],
    development_validator: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    config = load_smoke_config(config_path)
    development = _development_config(config, repo_root)
    selected_prompts, pinned_template_sha256 = _selected_prompt_records(
        config, development, repo_root
    )
    captured: dict[str, tuple[dict[str, Any], Any]] = {}

    def capture_inspection(**kwargs: Any) -> tuple[dict[str, Any], Any]:
        identity, tokenizer = model_asset_inspector(**kwargs)
        captured[kwargs["model_role"]] = (identity, tokenizer)
        return identity, tokenizer

    development_path = _resolve_repo_file(
        repo_root,
        config["development_input_config_relative_path"],
        "development_input_config_relative_path",
    )
    development_result = development_validator(
        development_path,
        repo_root=repo_root,
        model_asset_inspector=capture_inspection,
    )
    if development_result.get("status") != "STAGE3_DEVELOPMENT_INPUTS_VALIDATE_ONLY_PASS":
        raise P1SmokeCoreError("strict development input validation did not pass")
    if "behavior" not in captured:
        raise P1SmokeCoreError("development validator did not inspect behavior metadata")
    behavior_identity, tokenizer = captured["behavior"]
    behavior = config["behavior"]
    if any(
        behavior[field] != development["behavior"][field]
        for field in (
            "checkpoint_path",
            "tokenizer_path",
            "dtype",
            "device",
            "trust_remote_code",
            "trust_remote_code_reason",
            "layer",
            "hook_site",
        )
    ):
        raise P1SmokeCoreError("P1 smoke behavior differs from development input config")
    actual_template_sha256 = hashlib.sha256(tokenizer.chat_template.encode("utf-8")).hexdigest()
    if (
        actual_template_sha256 != pinned_template_sha256
        or behavior_identity.get("chat_template_sha256") != pinned_template_sha256
    ):
        raise P1SmokeCoreError("behavior tokenizer differs from the pinned P1 template")
    layer_count = behavior_identity.get("layer_count")
    if type(layer_count) is not int or behavior["layer"] >= layer_count:
        raise P1SmokeCoreError("P1 smoke layer is outside the behavior model metadata")

    extractions = [
        render_and_extract_t0(tokenizer, prompt["content"])
        for prompt in selected_prompts
    ]
    return {
        "config": config,
        "development_result": development_result,
        "behavior_identity": behavior_identity,
        "tokenizer": tokenizer,
        "prompts": selected_prompts,
        "extractions": extractions,
    }


def validate_only(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
) -> dict[str, Any]:
    """Validate metadata and both T0 extractions without loading weights or forwarding."""
    prepared = _prepare_smoke(
        config_path,
        repo_root=repo_root.resolve(),
        model_asset_inspector=model_asset_inspector,
        development_validator=development_validator,
    )
    return {
        "status": "P1_SMOKE_CORE_VALIDATE_ONLY_PASS",
        "prompt_count": len(prepared["prompts"]),
        "domains": [prompt["domain"] for prompt in prepared["prompts"]],
        "extraction_complete": [
            extraction["complete_case"] for extraction in prepared["extractions"]
        ],
        "model_weights_loaded": False,
        "forward_executed": False,
        "generation_run": False,
        "judge_run": False,
        "p1_run": False,
        "formal_experiment_run": False,
        "paper_result_eligible": False,
    }


def _output_directory(config: Mapping[str, Any], repo_root: Path) -> Path:
    raw = config["output_root"]
    relative = PurePosixPath(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise P1SmokeCoreError("output_root must remain below the repository")
    output = (repo_root / Path(*relative.parts)).resolve()
    try:
        output.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise P1SmokeCoreError("output_root escapes the repository") from exc
    return output


def load_behavior_model(
    behavior: Mapping[str, Any], *, model_loader: Any = AutoModelForCausalLM
) -> Any:
    """Future smoke-only local weight-loading entry; validation never calls this."""
    dtype = {"bfloat16": torch.bfloat16}[behavior["dtype"]]
    model = model_loader.from_pretrained(
        behavior["checkpoint_path"],
        local_files_only=True,
        trust_remote_code=behavior["trust_remote_code"],
        dtype=dtype,
    )
    model.to(behavior["device"])
    model.eval()
    return model


def release_model_resources(
    *, device: str, torch_module: Any = torch, collect: Callable[[], int] = gc.collect
) -> dict[str, Any]:
    collected = collect()
    emptied = False
    if device.startswith("cuda:") and bool(torch_module.cuda.is_available()):
        torch_module.cuda.synchronize(device)
        torch_module.cuda.empty_cache()
        emptied = True
    return {
        "model_reference_cleared": True,
        "gc_collect_called": True,
        "gc_collected_count": collected,
        "cuda_empty_cache_called": emptied,
    }


def run_smoke(
    config_path: Path = DEFAULT_CONFIG,
    *,
    repo_root: Path = ROOT,
    model_asset_inspector: Callable[..., tuple[dict[str, Any], Any]] = inspect_local_model_assets,
    development_validator: Callable[..., dict[str, Any]] = validate_development_inputs,
    weight_loader: Callable[[Mapping[str, Any]], Any] = load_behavior_model,
    torch_module: Any = torch,
) -> dict[str, Any]:
    """Run only the bounded two-prompt forward smoke; never generate or judge."""
    root = repo_root.resolve()
    config = load_smoke_config(config_path)
    output_directory = _output_directory(config, root)
    if output_directory.exists() or output_directory.is_symlink():
        raise P1SmokeCoreError(f"refusing to overwrite output directory: {output_directory}")
    prepared = _prepare_smoke(
        config_path,
        repo_root=root,
        model_asset_inspector=model_asset_inspector,
        development_validator=development_validator,
    )
    if len(prepared["prompts"]) != 2 or [
        prompt["domain"] for prompt in prepared["prompts"]
    ] != ["harmful", "benign"]:
        raise P1SmokeCoreError("smoke requires exactly 1 harmful + 1 benign prompt")

    output_directory.mkdir(parents=True, exist_ok=False)
    model: Any = None
    details: list[dict[str, Any]] = []
    terminal_records: list[dict[str, Any]] = []
    lifecycle: dict[str, Any] | None = None
    try:
        model = weight_loader(prepared["config"]["behavior"])
        device = getattr(model, "device", prepared["config"]["behavior"]["device"])
        for prompt, extraction in zip(
            prepared["prompts"], prepared["extractions"], strict=True
        ):
            inputs = {
                "input_ids": torch_module.tensor(
                    [extraction["input_ids"]], dtype=torch_module.long, device=device
                ),
                "attention_mask": torch_module.tensor(
                    [extraction["attention_mask"]], dtype=torch_module.long, device=device
                ),
            }
            measurement = measure_resid_pre(
                model,
                inputs,
                extraction,
                layer=9,
                hook_site="resid_pre",
                batch_size=1,
                torch_module=torch_module,
            )
            terminal = build_p1_terminal_record(prompt, extraction, measurement)
            details.append(
                {"prompt": prompt, "extraction": extraction, "measurement": measurement}
            )
            terminal_records.append(terminal)
    finally:
        model = None
        lifecycle = release_model_resources(
            device=prepared["config"]["behavior"]["device"], torch_module=torch_module
        )

    payload = {
        "schema_version": "paper1-stage3-p1-smoke-core-output-v1",
        "status": "P1_SMOKE_CORE_RUN_PASS",
        "run_mode": "smoke",
        "paper_result_eligible": False,
        "formal_experiment_run": False,
        "generation_run": False,
        "judge_run": False,
        "p1_run": True,
        "prompt_measurements": details,
        "p1_terminal_records": terminal_records,
        "smoke_summary": {
            "prompt_count": len(terminal_records),
            "complete_case_count": sum(
                bool(record["complete_case"]) for record in terminal_records
            ),
            "model_released": lifecycle,
        },
    }
    (output_directory / "p1_smoke_core.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload
