#!/usr/bin/env python
"""Build the deterministic Paper 1 Stage 3 benign prompt frames."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from bisect import bisect_right
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = "paper1-stage3-benign-prompt-frames-v1"
REGISTRY_SCHEMA_VERSION = "paper1-stage3-instruction-type-registry-v1"
SELECTION_NAMESPACE = "paper1-stage3-benign-joint-v1"
LENGTH_NAMESPACE = "paper1-stage3-benign-length-v1"
MASTER_SEED = 42

SOURCE_DATASET = "databricks/databricks-dolly-15k"
SOURCE_REVISION = "bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a"
SOURCE_CONFIG = "default"
SOURCE_SPLIT = "train"
SOURCE_PATH = "databricks-dolly-15k.jsonl"
SOURCE_RAW_SHA256 = "2df9083338b4abd6bceb5635764dab5d833b393b55759dffb0959b6fcbf794ec"
SOURCE_CARD_SHA256 = "db06c60090a11b20e79d1933b2f316f781605f07761ff2ae2795d6523e3e960b"
SOURCE_ROW_COUNT = 15_011
SOURCE_LICENSE = "CC-BY-SA-3.0"

TOKENIZER_SOURCE = "Qwen/Qwen2.5-7B-Instruct"
TOKENIZER_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
TOKENIZER_FILE_SHA256 = {
    "merges.txt": "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3",
    "tokenizer.json": "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539",
    "tokenizer_config.json": "5b5d4f65d0acd3b2d56a35b56d374a36cbc1c8fa5cf3b3febbbfabf22f359583",
    "vocab.json": "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
}
CHAT_TEMPLATE_SHA256 = "cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f"
DEFAULT_SYSTEM_CONTENT = (
    "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
)

P1_SELECTED_RELATIVE_PATH = Path(
    "data/stage3/p1_harmful_do_not_answer_v1/selected_p1_harmful_100.json"
)
P1_SELECTED_SHA256 = "700c2c391c86273fca01ec9823feb66a3b1927ac39cc81d1de7567c71bebfd36"
JBB_CONFIRM_RELATIVE_PATH = Path(
    "data/stage3/jbb_behavior_frames_v1/selected_jbb_confirm_50.json"
)
JBB_CONFIRM_SHA256 = "e435b314c3d50341219f940a137f09d3926777d9689e4bad5ab45d3eec7958ec"
JBB_SCREEN_RELATIVE_PATH = Path(
    "data/stage3/jbb_behavior_frames_v1/selected_jbb_screen_30.json"
)
JBB_SCREEN_SHA256 = "2d9273fd38623c8ddc79ef04d05a56bb37ef9adca37653b0161244862d424635"
JBB_MANIFEST_RELATIVE_PATH = Path(
    "data/stage3/jbb_behavior_frames_v1/jbb_behavior_split_manifest.json"
)
JBB_MANIFEST_SHA256 = "7a7174d608a42dc70f1b8360f63bb4a35bdeb9fd87b29cbb569710b942d0bcea"
JBB_CONFIRM_CONFIG_RELATIVE_PATH = Path("configs/stage3/jbb_behavior_confirm_v1.json")
JBB_CONFIRM_CONFIG_SHA256 = "e1af5c5ca272c09dbd96e27064fbf0bc2affba85d54bd127b0c6872b8bb9e483"
JBB_EVIDENCE_RELATIVE_PATH = Path(".codex-temp/stage3_jbb_frames_v1/selection_evidence.json")
JBB_SOURCE_REVISION = "886acc352a31533ffbcf4ef22c744658688086fc"

DEFAULT_SOURCE_RELATIVE_PATH = Path(
    ".codex-temp/stage3_benign_frames_v1/sources/dolly/databricks-dolly-15k.jsonl"
)
DEFAULT_TOKENIZER_RELATIVE_DIRECTORY = Path(
    ".codex-temp/stage3_benign_frames_v1/tokenizer"
)
DEFAULT_ARTIFACT_DIRECTORY = Path("data/stage3/benign_prompt_frames_v1")
DEFAULT_CONFIG_DIRECTORY = Path("configs/stage3")

TYPE_ORDER = (
    "ACTION_GUIDANCE",
    "ARTIFACT_CREATION",
    "ADVICE_OR_IDEATION",
    "INFORMATION_LOOKUP",
    "EXPLANATION_OR_DESCRIPTION",
    "TRANSFORMATION_OR_CLASSIFICATION",
)
ROLE_LENGTH_SUPPORT = {
    "p1_benign": (35, 50),
    "benign_confirm": (34, 57),
}

EXPECTED_P1_TARGET_MATRIX = {
    "ACTION_GUIDANCE": (9, 8, 9, 7, 7, 9, 7, 7, 8, 6),
    "ARTIFACT_CREATION": (0, 0, 0, 1, 0, 0, 1, 2, 1, 2),
    "ADVICE_OR_IDEATION": (0, 1, 1, 2, 0, 0, 2, 1, 1, 2),
    "INFORMATION_LOOKUP": (1, 1, 0, 0, 3, 1, 0, 0, 0, 0),
    "EXPLANATION_OR_DESCRIPTION": (0,) * 10,
    "TRANSFORMATION_OR_CLASSIFICATION": (0,) * 10,
}
EXPECTED_JBB_TARGET_MATRIX = {
    "ACTION_GUIDANCE": (1, 4, 2, 2, 2, 3, 2, 1, 2, 3),
    "ARTIFACT_CREATION": (4, 1, 1, 2, 3, 2, 3, 3, 2, 2),
    "ADVICE_OR_IDEATION": (0, 0, 2, 1, 0, 0, 0, 1, 0, 0),
    "INFORMATION_LOOKUP": (0,) * 10,
    "EXPLANATION_OR_DESCRIPTION": (0, 0, 0, 0, 0, 0, 0, 0, 1, 0),
    "TRANSFORMATION_OR_CLASSIFICATION": (0,) * 10,
}
EXPECTED_CONFIRM_QUOTA_MATRIX = {
    "ACTION_GUIDANCE": (1, 2, 1, 1, 1, 2, 1, 1, 1, 2),
    "ARTIFACT_CREATION": (2, 1, 1, 1, 2, 1, 2, 2, 1, 1),
    "ADVICE_OR_IDEATION": (0, 0, 1, 1, 0, 0, 0, 1, 0, 0),
    "INFORMATION_LOOKUP": (0,) * 10,
    "EXPLANATION_OR_DESCRIPTION": (0,) * 10,
    "TRANSFORMATION_OR_CLASSIFICATION": (0,) * 10,
}

P1_ARTIFACT_SOURCE_IDS = {638, 647, 736, 758, 761, 763, 764}
P1_ADVICE_SOURCE_IDS = {554, 633, 656, 660, 663, 675, 689, 696, 724, 726}
P1_INFORMATION_SOURCE_IDS = {574, 580, 585, 590, 621, 636}
JBB_ARTIFACT_SOURCE_IDS = {
    0, 2, 3, 8, 10, 12, 15, 23, 29, 30, 44, 50, 51, 54, 56, 60, 61,
    62, 65, 66, 72, 73, 75,
}
JBB_ADVICE_SOURCE_IDS = {43, 80, 89, 96}
JBB_EXPLANATION_SOURCE_IDS = {55}

TRANSFORM_RE = re.compile(
    r"\b(classif(?:y|ication)|categorize|extract|summari[sz]e|translate|rewrite|rephrase|convert)\b",
    re.I,
)
PROCEDURE_RE = re.compile(
    r"(?:\bhow\s+(?:can|could|do|does|should|would|to)\b|"
    r"\b(?:step[- ]by[- ]step|instructions?|tutorial|guide|procedure|techniques?)\b|"
    r"\bsteps\s+(?:necessary|required|needed)\b)",
    re.I,
)
ARTIFACT_RE = re.compile(
    r"^(?:please\s+)?(?:can you\s+(?:help me\s+)?|could you\s+(?:help me\s+)?|"
    r"help me\s+|(?:can you\s+)?assist(?: me)?\s+in\s+)?"
    r"(?:write|draft|create|generate|develop|design|compose|craft|produce|make|plan)\b",
    re.I,
)
ARTIFACT_DELIVERABLE_RE = re.compile(
    r"^(?:please\s+)?(?:can you\s+)?(?:give|provide|show|offer)(?: me)?\s+"
    r"(?:an?\s+)?(?:template|draft|script|story|poem|article|letter|message|email|post|plan)\b",
    re.I,
)
DIRECT_ACTION_RE = re.compile(
    r"^(?:please\s+)?(?:can you\s+(?:help me\s+)?|could you\s+(?:help me\s+)?|"
    r"help me\s+|assist me\s+|can you assist me\s+|can you help me\s+)?"
    r"(?:send|spread|reveal|release|open|post|hide|access|share|publish|distribute)\b",
    re.I,
)
ADVICE_RE = re.compile(
    r"\b(?:advice|recommend|suggest|brainstorm|ideas?|options?|strateg(?:y|ies)|tactics|"
    r"best ways?|quickest way|ways to|convince|encourage|pressure|provoke)\b",
    re.I,
)
INFO_RE = re.compile(
    r"^(?:please\s+)?(?:can you\s+(?:help me\s+)?|could you\s+)?"
    r"(?:what|where|who|when|which|list|name|identify|find|give me a list|tell me)\b",
    re.I,
)
EXPLAIN_RE = re.compile(r"\b(?:explain|describe|why|analy[sz]e|compare|discuss)\b", re.I)
UNSAFE_RE = re.compile(
    r"\b(?:abduct|abuse|arson|assault|attack|blackmail|bomb|bully|bypass|cheat|cocaine|"
    r"counterfeit|dangerous|deepfake|disinformation|dox|drugs?|embezz|evade|exploit|"
    r"explosive|extort|fentanyl|firearm|fraud|gambl|guns?|hack|harass|hate speech|heroin|"
    r"illegal|illicit|kidnap|kill|knives?|launder|lockpick|lsd|malware|methamphetamine|"
    r"misinformation|murder|nudity|phish|pirat|poach|poison|porn|propaganda|racis|rape|"
    r"ransom|ransomware|robbery|sabotage|scam|self[- ]harm|sexual|silencer|smuggl|stalk|"
    r"starv|steal|suicide|terroris|theft|threaten|torture|violence|violent|virus|weapons?|"
    r"xenophob)\w*\b",
    re.I,
)
SPECIAL_TOKEN_RE = re.compile(r"<\|[^|<>]+\|>")

WORD_NEAR_DUPLICATE_THRESHOLD = 0.70
CHAR5_NEAR_DUPLICATE_THRESHOLD = 0.75
NEAR_DUPLICATE_REVIEW: dict[tuple[str, str], tuple[str, str]] = {}


class SelectionError(RuntimeError):
    """A fail-closed benign-frame selection error."""


class CapacityError(SelectionError):
    """A required type-by-decile cell does not have enough candidates."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")


def normalize_prompt(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip())


def normalized_exact_key(value: str) -> str:
    return normalize_prompt(value).casefold()


def is_english_instruction(prompt: str) -> bool:
    letters = [char for char in prompt if char.isalpha()]
    if len(letters) < 3:
        return False
    latin = sum("LATIN" in unicodedata.name(char, "") for char in letters)
    return latin / len(letters) >= 0.90


def dolly_source_id(source_index: int) -> str:
    return (
        f"{SOURCE_DATASET}@{SOURCE_REVISION}:{SOURCE_PATH}:"
        f"{SOURCE_CONFIG}/{SOURCE_SPLIT}:row={source_index:05d}"
    )


def instruction_type(prompt: str, native_category: str | None = None) -> str:
    normalized = normalize_prompt(prompt)
    native = (native_category or "").strip().lower()
    if TRANSFORM_RE.search(normalized):
        return "TRANSFORMATION_OR_CLASSIFICATION"
    if PROCEDURE_RE.search(normalized):
        return "ACTION_GUIDANCE"
    if ARTIFACT_RE.search(normalized) or ARTIFACT_DELIVERABLE_RE.search(normalized):
        return "ARTIFACT_CREATION"
    if DIRECT_ACTION_RE.search(normalized):
        return "ACTION_GUIDANCE"
    if ADVICE_RE.search(normalized):
        return "ADVICE_OR_IDEATION"
    if INFO_RE.search(normalized):
        return "INFORMATION_LOOKUP"
    if EXPLAIN_RE.search(normalized):
        return "EXPLANATION_OR_DESCRIPTION"
    if native == "creative_writing":
        return "ARTIFACT_CREATION"
    if native == "brainstorming":
        return "ADVICE_OR_IDEATION"
    if native == "classification":
        return "TRANSFORMATION_OR_CLASSIFICATION"
    if native in {"open_qa", "general_qa", "closed_qa"}:
        return "EXPLANATION_OR_DESCRIPTION"
    return "EXPLANATION_OR_DESCRIPTION"


def target_instruction_type(role: str, source_id: int) -> str:
    if role == "p1_harmful":
        if source_id in P1_ARTIFACT_SOURCE_IDS:
            return "ARTIFACT_CREATION"
        if source_id in P1_ADVICE_SOURCE_IDS:
            return "ADVICE_OR_IDEATION"
        if source_id in P1_INFORMATION_SOURCE_IDS:
            return "INFORMATION_LOOKUP"
        return "ACTION_GUIDANCE"
    if role == "jbb_confirm":
        if source_id in JBB_ARTIFACT_SOURCE_IDS:
            return "ARTIFACT_CREATION"
        if source_id in JBB_ADVICE_SOURCE_IDS:
            return "ADVICE_OR_IDEATION"
        if source_id in JBB_EXPLANATION_SOURCE_IDS:
            return "EXPLANATION_OR_DESCRIPTION"
        return "ACTION_GUIDANCE"
    raise SelectionError(f"UNKNOWN_TARGET_ROLE: {role}")


def _bytes_to_unicode() -> dict[int, str]:
    byte_values = list(range(ord("!"), ord("~") + 1))
    byte_values += list(range(ord("¡"), ord("¬") + 1))
    byte_values += list(range(ord("®"), ord("ÿ") + 1))
    code_points = list(byte_values)
    extra = 0
    for byte_value in range(256):
        if byte_value not in byte_values:
            byte_values.append(byte_value)
            code_points.append(256 + extra)
            extra += 1
    return dict(zip(byte_values, map(chr, code_points), strict=True))


def _is_letter(char: str) -> bool:
    return unicodedata.category(char).startswith("L")


def _is_number(char: str) -> bool:
    return unicodedata.category(char).startswith("N")


def _qwen_pretokenize(text: str) -> list[str]:
    pieces: list[str] = []
    index = 0
    contractions = ("'ll", "'re", "'ve", "'s", "'t", "'m", "'d")
    while index < len(text):
        remaining = text[index:]
        lowered = remaining.lower()
        contraction = next(
            (item for item in contractions if lowered.startswith(item)), None
        )
        if contraction is not None:
            pieces.append(remaining[: len(contraction)])
            index += len(contraction)
            continue

        char = text[index]
        letter_start = index
        if _is_letter(char):
            pass
        elif (
            char not in "\r\n"
            and not _is_letter(char)
            and not _is_number(char)
            and index + 1 < len(text)
            and _is_letter(text[index + 1])
        ):
            letter_start = index + 1
        else:
            letter_start = -1
        if letter_start >= 0:
            end = letter_start
            while end < len(text) and _is_letter(text[end]):
                end += 1
            pieces.append(text[index:end])
            index = end
            continue

        if _is_number(char):
            pieces.append(char)
            index += 1
            continue

        punctuation_start = index
        if char == " " and index + 1 < len(text):
            next_char = text[index + 1]
            if (
                not next_char.isspace()
                and not _is_letter(next_char)
                and not _is_number(next_char)
            ):
                punctuation_start = index + 1
            else:
                punctuation_start = -1
        elif char.isspace() or _is_letter(char) or _is_number(char):
            punctuation_start = -1
        if punctuation_start >= 0:
            end = punctuation_start
            while (
                end < len(text)
                and not text[end].isspace()
                and not _is_letter(text[end])
                and not _is_number(text[end])
            ):
                end += 1
            while end < len(text) and text[end] in "\r\n":
                end += 1
            pieces.append(text[index:end])
            index = end
            continue

        if char.isspace():
            run_end = index
            while run_end < len(text) and text[run_end].isspace():
                run_end += 1
            whitespace_run = text[index:run_end]
            last_newline = max(whitespace_run.rfind("\r"), whitespace_run.rfind("\n"))
            if last_newline >= 0:
                end = index + last_newline + 1
                pieces.append(text[index:end])
                index = end
                continue
            if run_end == len(text):
                pieces.append(whitespace_run)
                index = run_end
                continue
            if len(whitespace_run) >= 2:
                pieces.append(whitespace_run[:-1])
                index = run_end - 1
                continue
            pieces.append(whitespace_run)
            index = run_end
            continue

        raise AssertionError(
            f"Qwen pre-tokenizer made no progress at {index}: {text[index:index + 20]!r}"
        )
    if "".join(pieces) != text:
        raise AssertionError("Qwen pre-tokenizer did not preserve the input text.")
    return pieces


class QwenTokenizer:
    """Pinned Qwen ByteLevel-BPE for the approved user-only template branch."""

    def __init__(self, directory: Path) -> None:
        for name, expected_sha256 in TOKENIZER_FILE_SHA256.items():
            path = directory / name
            if not path.is_file():
                raise SelectionError(f"TOKENIZER_IDENTITY_MISMATCH: missing {name}")
            observed = file_sha256(path)
            if observed != expected_sha256:
                raise SelectionError(
                    "TOKENIZER_IDENTITY_MISMATCH: "
                    f"{name} observed={observed} expected={expected_sha256}"
                )

        payload = _load_json(directory / "tokenizer.json")
        config = _load_json(directory / "tokenizer_config.json")
        chat_template = config.get("chat_template") if isinstance(config, dict) else None
        if not isinstance(chat_template, str):
            raise SelectionError("TOKENIZER_IDENTITY_MISMATCH: chat_template is absent")
        if hashlib.sha256(chat_template.encode("utf-8")).hexdigest() != CHAT_TEMPLATE_SHA256:
            raise SelectionError("TOKENIZER_IDENTITY_MISMATCH: chat_template hash")
        if DEFAULT_SYSTEM_CONTENT not in chat_template:
            raise SelectionError("TOKENIZER_IDENTITY_MISMATCH: default system branch")
        default_branch_matches = re.findall(
            r"\{\{- '(?P<render><\|im_start\|>system\\n[^{}']*?<\|im_end\|>\\n)' \}\}",
            chat_template,
        )
        if len(default_branch_matches) != 1:
            raise SelectionError("TOKENIZER_IDENTITY_MISMATCH: default system projection")
        if DEFAULT_SYSTEM_CONTENT not in default_branch_matches[0]:
            raise SelectionError("TOKENIZER_IDENTITY_MISMATCH: default system content")

        try:
            self.vocab: dict[str, int] = payload["model"]["vocab"]
            raw_merges = payload["model"]["merges"]
            added_tokens = payload["added_tokens"]
        except (KeyError, TypeError) as exc:
            raise SelectionError("TOKENIZER_IDENTITY_MISMATCH: tokenizer schema") from exc
        merge_pairs: list[tuple[str, str]] = []
        for raw_merge in raw_merges:
            if isinstance(raw_merge, str):
                left, right = raw_merge.split(" ", 1)
            else:
                left, right = raw_merge
            merge_pairs.append((left, right))
        self.merge_ranks = {pair: rank for rank, pair in enumerate(merge_pairs)}
        self.byte_encoder = _bytes_to_unicode()
        self.added_tokens = {item["content"]: item["id"] for item in added_tokens}
        alternatives = "|".join(
            re.escape(item) for item in sorted(self.added_tokens, key=len, reverse=True)
        )
        self.added_pattern = re.compile(f"({alternatives})")
        self.chat_template = chat_template
        if re.search(r"\\(?!n)", default_branch_matches[0]):
            raise SelectionError("TOKENIZER_IDENTITY_MISMATCH: unsupported template escape")
        self.default_system_render = default_branch_matches[0].replace(r"\n", "\n")

    @lru_cache(maxsize=100_000)
    def _bpe(self, token: str) -> tuple[str, ...]:
        word = tuple(token)
        if len(word) <= 1:
            return word
        while True:
            pairs = {(word[index], word[index + 1]) for index in range(len(word) - 1)}
            best = min(pairs, key=lambda pair: self.merge_ranks.get(pair, math.inf))
            if best not in self.merge_ranks:
                break
            first, second = best
            merged: list[str] = []
            index = 0
            while index < len(word):
                try:
                    next_match = word.index(first, index)
                except ValueError:
                    merged.extend(word[index:])
                    break
                merged.extend(word[index:next_match])
                if next_match < len(word) - 1 and word[next_match + 1] == second:
                    merged.append(first + second)
                    index = next_match + 2
                else:
                    merged.append(first)
                    index = next_match + 1
            word = tuple(merged)
            if len(word) <= 1:
                break
        return word

    def encode(self, text: str) -> list[int]:
        text = unicodedata.normalize("NFC", text)
        token_ids: list[int] = []
        for part in self.added_pattern.split(text):
            if not part:
                continue
            if part in self.added_tokens:
                token_ids.append(self.added_tokens[part])
                continue
            for pretoken in _qwen_pretokenize(part):
                byte_token = "".join(
                    self.byte_encoder[value] for value in pretoken.encode("utf-8")
                )
                for bpe_token in self._bpe(byte_token):
                    token_ids.append(self.vocab[bpe_token])
        return token_ids

    def apply_t0_user_only(self, messages: Sequence[dict[str, str]]) -> str:
        if len(messages) != 1 or set(messages[0]) != {"role", "content"}:
            raise SelectionError("T0_MESSAGES_INVALID: exactly one role/content message required")
        message = messages[0]
        if message["role"] != "user" or not isinstance(message["content"], str):
            raise SelectionError("T0_MESSAGES_INVALID: input must contain one user message")
        # This is the exact no-tools, non-system-input, add_generation_prompt=true
        # projection of the pinned template whose complete hash is validated above.
        return (
            self.default_system_render
            + "<|im_start|>user\n"
            + message["content"]
            + "<|im_end|>\n<|im_start|>assistant\n"
        )

    def rendered_length(self, prompt: str) -> int:
        messages = [{"role": "user", "content": prompt}]
        return len(self.encode(self.apply_t0_user_only(messages)))


def _load_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise SelectionError(f"STRICT_JSON_ERROR: BOM in {path}")
        return json.loads(raw.decode("utf-8"))
    except SelectionError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SelectionError(f"STRICT_JSON_ERROR: {path}: {exc}") from exc


def _require_jbb(condition: bool, detail: str) -> None:
    if not condition:
        raise SelectionError(f"JBB_DEPENDENCY_MISMATCH: {detail}")


def validate_and_load_targets(
    repo_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    p1_path = repo_root / P1_SELECTED_RELATIVE_PATH
    if not p1_path.is_file() or file_sha256(p1_path) != P1_SELECTED_SHA256:
        raise SelectionError("P1_TARGET_DEPENDENCY_MISMATCH: selected P1 bytes")
    p1_payload = _load_json(p1_path)
    p1_records = p1_payload.get("records") if isinstance(p1_payload, dict) else None
    if not isinstance(p1_records, list) or len(p1_records) != 100:
        raise SelectionError("P1_TARGET_DEPENDENCY_MISMATCH: expected 100 records")

    confirm_path = repo_root / JBB_CONFIRM_RELATIVE_PATH
    screen_path = repo_root / JBB_SCREEN_RELATIVE_PATH
    manifest_path = repo_root / JBB_MANIFEST_RELATIVE_PATH
    config_path = repo_root / JBB_CONFIRM_CONFIG_RELATIVE_PATH
    evidence_path = repo_root / JBB_EVIDENCE_RELATIVE_PATH
    for path, label in (
        (confirm_path, "confirm artifact"),
        (screen_path, "screen artifact"),
        (manifest_path, "manifest"),
        (config_path, "config"),
        (evidence_path, "selection evidence"),
    ):
        _require_jbb(path.is_file(), f"missing {label}")
    _require_jbb(file_sha256(confirm_path) == JBB_CONFIRM_SHA256, "confirm bytes")
    _require_jbb(file_sha256(screen_path) == JBB_SCREEN_SHA256, "screen bytes")
    _require_jbb(file_sha256(manifest_path) == JBB_MANIFEST_SHA256, "manifest bytes")
    _require_jbb(file_sha256(config_path) == JBB_CONFIRM_CONFIG_SHA256, "config bytes")

    try:
        confirm_payload = _load_json(confirm_path)
        screen_payload = _load_json(screen_path)
        manifest = _load_json(manifest_path)
        config = _load_json(config_path)
        evidence = _load_json(evidence_path)
    except SelectionError as exc:
        raise SelectionError(f"JBB_DEPENDENCY_MISMATCH: invalid JSON: {exc}") from exc
    confirm_records = (
        confirm_payload.get("records") if isinstance(confirm_payload, dict) else None
    )
    screen_records = screen_payload.get("records") if isinstance(screen_payload, dict) else None
    _require_jbb(isinstance(confirm_records, list) and len(confirm_records) == 50, "50 rows")
    _require_jbb(isinstance(screen_records, list) and len(screen_records) == 30, "30 screen rows")
    _require_jbb(config.get("row_count") == 50, "config row_count")
    _require_jbb(config.get("selected_raw_sha256") == JBB_CONFIRM_SHA256, "selected hash")
    _require_jbb(config.get("source_revision") == JBB_SOURCE_REVISION, "source revision")
    _require_jbb(config.get("prompt_field") == "prompt", "prompt field")
    _require_jbb(manifest.get("counts", {}).get("confirm") == 50, "manifest count")
    _require_jbb(
        manifest.get("source_provenance", {}).get("dataset_revision") == JBB_SOURCE_REVISION,
        "manifest revision",
    )
    _require_jbb(evidence.get("status") == "JBB-FRAMES-SELECTION-PASS", "verdict")
    _require_jbb(
        "READY-FOR-BENIGN-FRAME-SELECTION" in evidence.get("readiness", []),
        "readiness",
    )
    _require_jbb(
        all("Target" not in record for record in confirm_records),
        "Target present in confirm runtime records",
    )

    p1_targets: list[dict[str, Any]] = []
    for record in p1_records:
        source_id = record.get("source_id")
        prompt = record.get("question")
        if isinstance(source_id, bool) or not isinstance(source_id, int):
            raise SelectionError("P1_TARGET_DEPENDENCY_MISMATCH: source_id type")
        if not isinstance(prompt, str) or not normalize_prompt(prompt):
            raise SelectionError("P1_TARGET_DEPENDENCY_MISMATCH: prompt type")
        p1_targets.append(
            {
                "target_role": "p1_harmful",
                "source_id": source_id,
                "prompt": normalize_prompt(prompt),
                "instruction_type": target_instruction_type("p1_harmful", source_id),
            }
        )
    if len({record["source_id"] for record in p1_targets}) != 100:
        raise SelectionError("P1_TARGET_DEPENDENCY_MISMATCH: duplicate source IDs")

    jbb_targets: list[dict[str, Any]] = []
    for record in confirm_records:
        source_id = record.get("source_index")
        prompt = record.get("prompt")
        if isinstance(source_id, bool) or not isinstance(source_id, int):
            _require_jbb(False, "source_index type")
        if not isinstance(prompt, str) or not normalize_prompt(prompt):
            _require_jbb(False, "prompt type")
        jbb_targets.append(
            {
                "target_role": "jbb_confirm",
                "source_id": source_id,
                "prompt": normalize_prompt(prompt),
                "instruction_type": target_instruction_type("jbb_confirm", source_id),
            }
        )
    if len({record["source_id"] for record in jbb_targets}) != 50:
        _require_jbb(False, "duplicate source indices")
    return p1_targets, jbb_targets, screen_records


def _eligibility_reason(row: Any) -> tuple[str | None, str | None, str | None]:
    if not isinstance(row, dict) or set(row) != {
        "instruction", "context", "response", "category"
    }:
        return "invalid_fields", None, None
    instruction = row.get("instruction")
    context = row.get("context")
    category = row.get("category")
    if not isinstance(instruction, str) or not isinstance(context, str) or not isinstance(category, str):
        return "invalid_fields", None, None
    prompt = normalize_prompt(instruction)
    if not prompt:
        return "blank_prompt", None, None
    if normalize_prompt(context):
        return "context_dependent", None, None
    if not is_english_instruction(prompt):
        return "not_english", None, None
    if SPECIAL_TOKEN_RE.search(prompt):
        return "reserved_special_token", None, None
    if UNSAFE_RE.search(prompt):
        return "obvious_unsafe_lexical", None, None
    return None, prompt, category


def load_and_filter_dolly(
    source_path: Path,
    *,
    expected_sha256: str | None = SOURCE_RAW_SHA256,
    expected_row_count: int | None = SOURCE_ROW_COUNT,
) -> tuple[list[dict[str, Any]], Counter[str], dict[str, Any]]:
    if expected_sha256 is not None:
        observed = file_sha256(source_path)
        if observed != expected_sha256:
            raise SelectionError(
                f"SOURCE_IDENTITY_MISMATCH: observed={observed} expected={expected_sha256}"
            )

    reasons: Counter[str] = Counter()
    provisional: list[dict[str, Any]] = []
    total_rows = 0
    try:
        handle = source_path.open("rb")
    except OSError as exc:
        raise SelectionError(f"SOURCE_READ_ERROR: {source_path}: {exc}") from exc
    with handle:
        for source_index, raw_line in enumerate(handle):
            total_rows += 1
            try:
                row = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SelectionError(
                    f"SOURCE_STRICT_JSONL_ERROR: row={source_index}: {exc}"
                ) from exc
            reason, prompt, native_category = _eligibility_reason(row)
            if reason is not None:
                reasons[reason] += 1
                continue
            assert prompt is not None and native_category is not None
            source_id = dolly_source_id(source_index)
            raw_row_sha256 = hashlib.sha256(raw_line).hexdigest()
            exact_key = normalized_exact_key(prompt)
            provisional.append(
                {
                    "source_id": source_id,
                    "source_index": source_index,
                    "prompt": prompt,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "prompt_identity_sha256": hashlib.sha256(
                        exact_key.encode("utf-8")
                    ).hexdigest(),
                    "source_row_raw_sha256": raw_row_sha256,
                    "source_record_identity_sha256": canonical_sha256(
                        {
                            "category": native_category,
                            "context": row["context"],
                            "instruction": row["instruction"],
                            "source_id": source_id,
                        }
                    ),
                    "native_category": native_category,
                    "instruction_type": instruction_type(prompt, native_category),
                    "normalization_modified": row["instruction"] != prompt,
                }
            )
    if expected_row_count is not None and total_rows != expected_row_count:
        raise SelectionError(
            f"SOURCE_IDENTITY_MISMATCH: rows={total_rows} expected={expected_row_count}"
        )

    by_identity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in provisional:
        by_identity[record["prompt_identity_sha256"]].append(record)
    eligible: list[dict[str, Any]] = []
    duplicate_groups: list[dict[str, Any]] = []
    for prompt_identity in sorted(by_identity):
        group = sorted(
            by_identity[prompt_identity],
            key=lambda record: (record["source_index"], record["source_id"]),
        )
        representative = group[0]
        eligible.append(representative)
        if len(group) > 1:
            excluded = [record["source_id"] for record in group[1:]]
            reasons["normalized_exact_duplicate"] += len(excluded)
            duplicate_groups.append(
                {
                    "prompt_identity_sha256": prompt_identity,
                    "representative_source_id": representative["source_id"],
                    "excluded_source_ids": excluded,
                }
            )
    eligible.sort(key=lambda record: record["source_id"])
    reasons["eligible"] = len(eligible)
    if len({record["source_id"] for record in eligible}) != len(eligible):
        raise SelectionError("SOURCE_IDENTITY_MISMATCH: duplicate stable source IDs")
    if len({record["source_record_identity_sha256"] for record in eligible}) != len(eligible):
        raise SelectionError("SOURCE_IDENTITY_MISMATCH: duplicate record identities")
    if len({record["prompt_identity_sha256"] for record in eligible}) != len(eligible):
        raise SelectionError("DUPLICATE_REPRESENTATIVE_FAILURE")
    duplicate_summary = {
        "representative_rule": "lowest zero-based source row index, then stable source ID",
        "group_count": len(duplicate_groups),
        "extra_record_count": reasons["normalized_exact_duplicate"],
        "groups_canonical_sha256": canonical_sha256(duplicate_groups),
    }
    return eligible, reasons, duplicate_summary


def validate_dolly_source_card(source_path: Path) -> None:
    card_path = source_path.parent / "README.md"
    if not card_path.is_file() or file_sha256(card_path) != SOURCE_CARD_SHA256:
        raise SelectionError("SOURCE_IDENTITY_MISMATCH: pinned dataset card")
    card = card_path.read_text(encoding="utf-8")
    required_markers = (
        "license: cc-by-sa-3.0",
        "Copyright (2023) Databricks, Inc.",
        "CC BY-SA 3.0 license",
    )
    if any(marker not in card for marker in required_markers):
        raise SelectionError("SOURCE_LICENSE_MISMATCH: pinned dataset card")


def target_tie_hash(role: str, source_id: int | str) -> str:
    return canonical_sha256(
        {"namespace": LENGTH_NAMESPACE, "role": role, "source_id": str(source_id)}
    )


def decile_for_rank(rank: int, population_size: int) -> int:
    if population_size <= 0 or rank < 0:
        raise SelectionError("DECILE_BOUNDARY_ERROR")
    clamped_rank = min(population_size - 1, rank)
    return min(10, 1 + (10 * clamped_rank) // population_size)


def assign_target_deciles(
    rows: list[dict[str, Any]], role: str
) -> list[tuple[int, str]]:
    keyed = sorted(
        (
            int(row["rendered_token_count"]),
            target_tie_hash(role, row["source_id"]),
            row,
        )
        for row in rows
    )
    keys: list[tuple[int, str]] = []
    for rank, (length, tie_hash, row) in enumerate(keyed):
        keys.append((length, tie_hash))
        row["length_decile"] = decile_for_rank(rank, len(rows))
    return keys


def candidate_decile(
    length: int,
    source_id: str,
    role: str,
    target_keys: list[tuple[int, str]],
) -> int:
    insertion_rank = bisect_right(
        target_keys, (length, target_tie_hash(role, source_id))
    )
    return decile_for_rank(insertion_rank, len(target_keys))


def counter_to_matrix(counts: Counter[tuple[str, int]]) -> dict[str, tuple[int, ...]]:
    return {
        type_name: tuple(counts[(type_name, decile)] for decile in range(1, 11))
        for type_name in TYPE_ORDER
    }


def matrix_to_json(matrix: dict[str, tuple[int, ...]]) -> dict[str, list[int]]:
    return {type_name: list(matrix[type_name]) for type_name in TYPE_ORDER}


def matrix_to_counter(matrix: dict[str, tuple[int, ...]]) -> Counter[tuple[str, int]]:
    return Counter(
        {
            (type_name, decile): values[decile - 1]
            for type_name, values in matrix.items()
            for decile in range(1, 11)
            if values[decile - 1]
        }
    )


def scaled_largest_remainder_quotas(
    counts: Counter[tuple[str, int]], target_total: int, source_total: int
) -> Counter[tuple[str, int]]:
    cells = [(type_name, decile) for type_name in TYPE_ORDER for decile in range(1, 11)]
    quotas: Counter[tuple[str, int]] = Counter(
        {cell: (counts[cell] * target_total) // source_total for cell in cells}
    )
    remaining = target_total - sum(quotas.values())
    order_index = {type_name: index for index, type_name in enumerate(TYPE_ORDER)}
    ranked = sorted(
        cells,
        key=lambda cell: (
            -((counts[cell] * target_total) % source_total),
            order_index[cell[0]],
            cell[1],
        ),
    )
    for cell in ranked[:remaining]:
        quotas[cell] += 1
    if sum(quotas.values()) != target_total:
        raise SelectionError("LARGEST_REMAINDER_TOTAL_FAILURE")
    return quotas


def selection_rank(source_id: str, split: str, type_name: str, decile: int) -> str:
    return canonical_sha256(
        {
            "master_seed": MASTER_SEED,
            "namespace": SELECTION_NAMESPACE,
            "source_id": source_id,
            "split": split,
            "stratum": f"{type_name}|D{decile}",
        }
    )


def prepare_candidates(
    candidates: list[dict[str, Any]],
    tokenizer: QwenTokenizer,
    p1_target_keys: list[tuple[int, str]],
    jbb_target_keys: list[tuple[int, str]],
) -> None:
    for record in candidates:
        length = tokenizer.rendered_length(record["prompt"])
        record["rendered_token_count"] = length
        record["p1_decile"] = candidate_decile(
            length, record["source_id"], "p1_harmful", p1_target_keys
        )
        record["jbb_decile"] = candidate_decile(
            length, record["source_id"], "jbb_confirm", jbb_target_keys
        )


def _cell_order(cell: tuple[str, int]) -> tuple[int, int]:
    return TYPE_ORDER.index(cell[0]), cell[1]


def allocate_role(
    candidates: Iterable[dict[str, Any]],
    quotas: Counter[tuple[str, int]],
    *,
    split: str,
    decile_field: str,
    length_support: tuple[int, int],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    lower, upper = length_support
    for record in candidates:
        length = int(record["rendered_token_count"])
        if lower <= length <= upper:
            groups[(record["instruction_type"], int(record[decile_field]))].append(record)

    selected: list[dict[str, Any]] = []
    capacity: dict[str, dict[str, int]] = {}
    for cell in sorted((cell for cell, quota in quotas.items() if quota), key=_cell_order):
        required = quotas[cell]
        ranked = sorted(
            groups[cell],
            key=lambda record: (
                selection_rank(record["source_id"], split, cell[0], cell[1]),
                record["source_id"],
            ),
        )
        capacity[f"{cell[0]}|D{cell[1]}"] = {
            "available": len(ranked),
            "required": required,
            "margin": len(ranked) - required,
        }
        if len(ranked) < required:
            raise CapacityError(
                f"{split.upper()}_CAPACITY_FAILURE: {cell[0]}|D{cell[1]} "
                f"available={len(ranked)} required={required}"
            )
        for record in ranked[:required]:
            chosen = dict(record)
            chosen["length_decile"] = cell[1]
            chosen["stratum"] = f"{cell[0]}|D{cell[1]}"
            chosen["selection_rank_sha256"] = selection_rank(
                record["source_id"], split, cell[0], cell[1]
            )
            chosen["split_membership"] = split
            selected.append(chosen)
    selected.sort(key=lambda record: record["source_id"])
    return selected, capacity


def joint_select(
    candidates: list[dict[str, Any]],
    p1_quotas: Counter[tuple[str, int]],
    confirm_quotas: Counter[tuple[str, int]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    selected_p1, p1_capacity = allocate_role(
        candidates,
        p1_quotas,
        split="p1_benign",
        decile_field="p1_decile",
        length_support=ROLE_LENGTH_SUPPORT["p1_benign"],
    )
    selected_source_ids = {record["source_id"] for record in selected_p1}
    selected_record_ids = {
        record["source_record_identity_sha256"] for record in selected_p1
    }
    selected_prompt_ids = {record["prompt_identity_sha256"] for record in selected_p1}
    confirm_pool = [
        record
        for record in candidates
        if record["source_id"] not in selected_source_ids
        and record["source_record_identity_sha256"] not in selected_record_ids
        and record["prompt_identity_sha256"] not in selected_prompt_ids
    ]
    selected_confirm, confirm_capacity = allocate_role(
        confirm_pool,
        confirm_quotas,
        split="benign_confirm",
        decile_field="jbb_decile",
        length_support=ROLE_LENGTH_SUPPORT["benign_confirm"],
    )
    if len(selected_p1) != 100 or len(selected_confirm) != 30:
        raise SelectionError("JOINT_COUNT_FAILURE")
    for identity_field in (
        "source_id", "source_record_identity_sha256", "prompt_identity_sha256"
    ):
        left = {record[identity_field] for record in selected_p1}
        right = {record[identity_field] for record in selected_confirm}
        if left & right:
            raise SelectionError(f"JOINT_DISJOINTNESS_FAILURE: {identity_field}")
    return selected_p1, selected_confirm, {
        "allocation_priority": ["p1_benign", "benign_confirm"],
        "p1_capacity": p1_capacity,
        "confirm_capacity_after_p1_identity_removal": confirm_capacity,
        "source_ids_disjoint": True,
        "record_identities_disjoint": True,
        "normalized_prompt_identities_disjoint": True,
    }


def _word_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[^\W_]+", normalized_exact_key(value), flags=re.UNICODE)
        if len(token) >= 3
    }


def _character_ngrams(value: str, n: int = 5) -> set[str]:
    normalized = re.sub(r"\W+", " ", normalized_exact_key(value), flags=re.UNICODE).strip()
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[index:index + n] for index in range(len(normalized) - n + 1)}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def lexical_scores(left: str, right: str) -> tuple[float, float]:
    return (
        _jaccard(_word_tokens(left), _word_tokens(right)),
        _jaccard(_character_ngrams(left), _character_ngrams(right)),
    )


def _frame_key(frame: dict[str, Any]) -> str:
    return f"{frame['frame']}:{frame['source_id']}"


def bounded_near_duplicate_review(
    selected_p1: list[dict[str, Any]],
    selected_confirm: list[dict[str, Any]],
    p1_targets: list[dict[str, Any]],
    jbb_confirm_targets: list[dict[str, Any]],
    jbb_screen_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_frames = [
        {"frame": "p1_benign", "source_id": record["source_id"], "prompt": record["prompt"]}
        for record in selected_p1
    ] + [
        {"frame": "benign_confirm", "source_id": record["source_id"], "prompt": record["prompt"]}
        for record in selected_confirm
    ]
    target_frames = [
        {"frame": "p1_harmful", "source_id": record["source_id"], "prompt": record["prompt"]}
        for record in p1_targets
    ] + [
        {"frame": "jbb_confirm", "source_id": record["source_id"], "prompt": record["prompt"]}
        for record in jbb_confirm_targets
    ] + [
        {
            "frame": "jbb_screen",
            "source_id": record["source_index"],
            "prompt": normalize_prompt(record["prompt"]),
        }
        for record in jbb_screen_records
    ]
    frames = selected_frames + target_frames
    selected_keys = {_frame_key(frame) for frame in selected_frames}
    candidates: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for left_index, left in enumerate(frames):
        for right in frames[left_index + 1:]:
            left_key = _frame_key(left)
            right_key = _frame_key(right)
            if left_key not in selected_keys and right_key not in selected_keys:
                continue
            if normalized_exact_key(left["prompt"]) == normalized_exact_key(right["prompt"]):
                continue
            word_score, char5_score = lexical_scores(left["prompt"], right["prompt"])
            if (
                word_score < WORD_NEAR_DUPLICATE_THRESHOLD
                and char5_score < CHAR5_NEAR_DUPLICATE_THRESHOLD
            ):
                continue
            pair = tuple(sorted((left_key, right_key)))
            review = NEAR_DUPLICATE_REVIEW.get(pair)
            item = {
                "pair": list(pair),
                "word_token_jaccard": round(word_score, 12),
                "character_5gram_jaccard": round(char5_score, 12),
            }
            if review is None:
                missing.append(
                    {
                        **item,
                        "left_prompt": left["prompt"],
                        "right_prompt": right["prompt"],
                    }
                )
            else:
                disposition, rationale = review
                if disposition != "KEEP_DISTINCT" or not rationale:
                    raise SelectionError("NEAR_DUPLICATE_REVIEW_INVALID")
                candidates.append(
                    {**item, "disposition": disposition, "rationale": rationale}
                )
    if missing:
        raise SelectionError(
            "NEAR_DUPLICATE_REVIEW_REQUIRED: "
            + json.dumps(missing, ensure_ascii=True, sort_keys=True)
        )
    candidates.sort(key=lambda item: item["pair"])
    return candidates


def _overlap_summary(
    selected_p1: list[dict[str, Any]],
    selected_confirm: list[dict[str, Any]],
    p1_targets: list[dict[str, Any]],
    jbb_confirm_targets: list[dict[str, Any]],
    jbb_screen_records: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_sets = {
        "p1_benign": {normalized_exact_key(record["prompt"]) for record in selected_p1},
        "benign_confirm": {
            normalized_exact_key(record["prompt"]) for record in selected_confirm
        },
    }
    target_sets = {
        "p1_harmful": {normalized_exact_key(record["prompt"]) for record in p1_targets},
        "jbb_confirm": {
            normalized_exact_key(record["prompt"]) for record in jbb_confirm_targets
        },
        "jbb_screen": {
            normalized_exact_key(record["prompt"]) for record in jbb_screen_records
        },
    }
    counts = {
        f"{selected_name}_to_{target_name}": len(selected_values & target_values)
        for selected_name, selected_values in selected_sets.items()
        for target_name, target_values in target_sets.items()
    }
    counts["between_selected_frames"] = len(
        selected_sets["p1_benign"] & selected_sets["benign_confirm"]
    )
    if any(counts.values()):
        raise SelectionError(f"NORMALIZED_EXACT_OVERLAP_FAILURE: {counts}")
    return {
        "normalization": [
            "Unicode NFKC", "trim", "collapse whitespace to ASCII space", "casefold"
        ],
        "counts": counts,
        "all_zero": True,
    }


def _instruction_type_registry() -> dict[str, Any]:
    definitions = {
        "ACTION_GUIDANCE": {
            "positive_definition": "requests steps, methods, procedures, or direct operational action",
            "exclusion_boundary": "exclude requests whose primary deliverable is a completed artifact",
        },
        "ARTIFACT_CREATION": {
            "positive_definition": "requests a completed code, prose, message, plan, or other artifact",
            "exclusion_boundary": "exclude requests that ask only how to create or operate something",
        },
        "ADVICE_OR_IDEATION": {
            "positive_definition": "requests recommendations, choices, strategies, or ideas",
            "exclusion_boundary": "exclude fact lookup and explicit procedural instructions",
        },
        "INFORMATION_LOOKUP": {
            "positive_definition": "requests a fact, entity, list, location, or short direct answer",
            "exclusion_boundary": "exclude explanation of causes, mechanisms, or comparisons",
        },
        "EXPLANATION_OR_DESCRIPTION": {
            "positive_definition": "requests explanation, description, comparison, reason, or mechanism",
            "exclusion_boundary": "exclude direct fact lookup and transformations of supplied input",
        },
        "TRANSFORMATION_OR_CLASSIFICATION": {
            "positive_definition": "requests classification, extraction, summary, translation, or rewriting",
            "exclusion_boundary": "requires an existing input or an explicit transformation form",
        },
    }
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": "approved_design_selection",
        "taxonomy_is_domain_neutral": True,
        "type_order": list(TYPE_ORDER),
        "types": {type_name: definitions[type_name] for type_name in TYPE_ORDER},
        "candidate_mapping": {
            "priority": [
                "transformation_surface_rule",
                "explicit_procedure_surface_rule",
                "artifact_surface_rule",
                "direct_action_surface_rule",
                "advice_surface_rule",
                "information_surface_rule",
                "explanation_surface_rule",
                "source_native_fallback",
            ],
            "patterns": {
                "transformation": TRANSFORM_RE.pattern,
                "explicit_procedure": PROCEDURE_RE.pattern,
                "artifact_command": ARTIFACT_RE.pattern,
                "artifact_deliverable": ARTIFACT_DELIVERABLE_RE.pattern,
                "direct_action": DIRECT_ACTION_RE.pattern,
                "advice": ADVICE_RE.pattern,
                "information": INFO_RE.pattern,
                "explanation": EXPLAIN_RE.pattern,
            },
            "dolly_native_crosswalk": {
                "creative_writing": "ARTIFACT_CREATION",
                "brainstorming": "ADVICE_OR_IDEATION",
                "classification": "TRANSFORMATION_OR_CLASSIFICATION",
                "open_qa": "surface rule, otherwise EXPLANATION_OR_DESCRIPTION",
                "general_qa": "surface rule, otherwise EXPLANATION_OR_DESCRIPTION",
                "closed_qa": "not eligible under empty-context rule; fallback EXPLANATION_OR_DESCRIPTION",
                "information_extraction": "not eligible under empty-context rule",
                "summarization": "not eligible under empty-context rule",
            },
            "ambiguous_case_rule": (
                "apply the ordered surface rules once; then the native fallback; "
                "otherwise EXPLANATION_OR_DESCRIPTION; no LLM call"
            ),
        },
        "target_mapping": {
            "p1_harmful": {
                "ARTIFACT_CREATION": sorted(P1_ARTIFACT_SOURCE_IDS),
                "ADVICE_OR_IDEATION": sorted(P1_ADVICE_SOURCE_IDS),
                "INFORMATION_LOOKUP": sorted(P1_INFORMATION_SOURCE_IDS),
                "all_remaining_selected_source_ids": "ACTION_GUIDANCE",
            },
            "jbb_confirm": {
                "ARTIFACT_CREATION": sorted(JBB_ARTIFACT_SOURCE_IDS),
                "ADVICE_OR_IDEATION": sorted(JBB_ADVICE_SOURCE_IDS),
                "EXPLANATION_OR_DESCRIPTION": sorted(JBB_EXPLANATION_SOURCE_IDS),
                "all_remaining_selected_source_indices": "ACTION_GUIDANCE",
            },
            "mapping_is_versioned_and_complete": True,
        },
        "unsafe_filter": {
            "purpose": "exclude obvious harmful or unsafe benign-source requests before matching",
            "regex": UNSAFE_RE.pattern,
            "flags": ["IGNORECASE"],
            "outcome_inputs_used": False,
        },
    }


def _selected_artifact(
    role: str,
    selected: list[dict[str, Any]],
    quota_source: str,
) -> dict[str, Any]:
    records = [
        {
            "source_id": record["source_id"],
            "source_index": record["source_index"],
            "prompt": record["prompt"],
            "messages": [{"role": "user", "content": record["prompt"]}],
            "prompt_sha256": record["prompt_sha256"],
            "prompt_identity_sha256": record["prompt_identity_sha256"],
            "source_row_raw_sha256": record["source_row_raw_sha256"],
            "source_record_identity_sha256": record["source_record_identity_sha256"],
            "native_category": record["native_category"],
            "instruction_type": record["instruction_type"],
            "rendered_token_count": record["rendered_token_count"],
            "length_decile": record["length_decile"],
            "stratum": record["stratum"],
            "selection_rank_sha256": record["selection_rank_sha256"],
            "split_membership": record["split_membership"],
            "normalization_modified": record["normalization_modified"],
        }
        for record in selected
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "benign_prompt_frame",
        "role": role,
        "status": "design_selected",
        "formal_experiment_run": False,
        "selection_namespace": SELECTION_NAMESPACE,
        "master_seed": MASTER_SEED,
        "quota_source": quota_source,
        "frame_order_rule": "stable_source_id_ascending",
        "record_count": len(records),
        "frame_source_ids_sha256": canonical_sha256(
            [record["source_id"] for record in records]
        ),
        "frame_record_identities_sha256": canonical_sha256(
            [record["source_record_identity_sha256"] for record in records]
        ),
        "frame_prompt_identities_sha256": canonical_sha256(
            [record["prompt_identity_sha256"] for record in records]
        ),
        "records": records,
    }


def _license_notice() -> bytes:
    text = f"""# Dolly Benign Prompt Frames v1: Provenance and License Notice

Status: `design_selected`. `formal_experiment_run=false`. This is an approved design selection,
not an execution authorization or a run-readiness declaration.

## Source and attribution

- Dataset: `databricks/databricks-dolly-15k`
- Owner and attribution party: Databricks, Inc.
- Dataset title: `databricks-dolly-15k`
- Immutable revision: `{SOURCE_REVISION}`
- Source file: `{SOURCE_PATH}`, config `{SOURCE_CONFIG}`, split `{SOURCE_SPLIT}`
- Source URL: `https://huggingface.co/datasets/databricks/databricks-dolly-15k/tree/{SOURCE_REVISION}`
- Source file SHA-256: `{SOURCE_RAW_SHA256}`
- License: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)
- License URI: `https://creativecommons.org/licenses/by-sa/3.0/`
- Copyright notice stated by the source: Copyright (2023) Databricks, Inc.

## Modifications and data boundary

The selected data are a modified subset of the source instructions. Selection first requires an empty
normalized `context`, then excludes invalid, non-English, reserved-token, obvious unsafe lexical, and
duplicate records. Published prompts are derived only from `instruction` by Unicode NFKC, trimming,
and collapsing consecutive whitespace to one ASCII space. The files add source IDs, hashes,
instruction types, rendered-token counts, deciles, strata, and deterministic ranks. Source `response`
content is not used for eligibility, taxonomy, matching, ranking, runtime input, or published text.

To the extent that the prompt strings and other copied or adapted Dolly dataset content in
`selected_p1_benign_100.json` and `selected_benign_confirm_30.json` constitute Adapted Material, that
data content is distributed under CC BY-SA 3.0 with the attribution and modification notice above.
This ShareAlike statement is limited to the corresponding Dolly-derived data content. It does not
purport to relicense selector code, tests, configuration mechanics, independently authored metadata,
or unrelated repository content. Recipients must retain this notice when redistributing the selected
Dolly-derived data content and must comply with the CC BY-SA 3.0 terms.
"""
    return text.encode("utf-8")


def _active_entry(
    role: str,
    relative_path: Path,
    selected_bytes: bytes,
    selected: list[dict[str, Any]],
    quota_source: str,
    manifest_sha256: str,
    registry_sha256: str,
    notice_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "paper1-stage3-active-dataset-entry-v1",
        "role": role,
        "status": "design_selected",
        "formal_experiment_run": False,
        "relative_path": relative_path.as_posix(),
        "selected_raw_sha256": hashlib.sha256(selected_bytes).hexdigest(),
        "row_count": len(selected),
        "prompt_field": "prompt",
        "messages_field": "messages",
        "messages_contract": "exactly one user message; no system message in input",
        "source_id_field": "source_id",
        "source_record_identity_field": "source_record_identity_sha256",
        "prompt_identity_field": "prompt_identity_sha256",
        "instruction_type_field": "instruction_type",
        "rendered_token_count_field": "rendered_token_count",
        "length_decile_field": "length_decile",
        "selection_rank_field": "selection_rank_sha256",
        "frame_order_rule": "stable_source_id_ascending",
        "selection_namespace": SELECTION_NAMESPACE,
        "master_seed": MASTER_SEED,
        "quota_source": quota_source,
        "source_dataset": SOURCE_DATASET,
        "source_revision": SOURCE_REVISION,
        "source_config": SOURCE_CONFIG,
        "source_split": SOURCE_SPLIT,
        "source_path": SOURCE_PATH,
        "source_raw_sha256": SOURCE_RAW_SHA256,
        "license": SOURCE_LICENSE,
        "tokenizer_source": TOKENIZER_SOURCE,
        "tokenizer_revision": TOKENIZER_REVISION,
        "chat_template_sha256": CHAT_TEMPLATE_SHA256,
        "rendering_package": "T0_native_user_only",
        "add_generation_prompt": True,
        "additional_bos_or_eos": False,
        "selection_manifest_relative_path": (
            DEFAULT_ARTIFACT_DIRECTORY / "benign_selection_manifest.json"
        ).as_posix(),
        "selection_manifest_raw_sha256": manifest_sha256,
        "instruction_type_registry_relative_path": (
            DEFAULT_ARTIFACT_DIRECTORY / "instruction_type_registry.json"
        ).as_posix(),
        "instruction_type_registry_raw_sha256": registry_sha256,
        "provenance_notice_relative_path": (
            DEFAULT_ARTIFACT_DIRECTORY / "provenance_license_notice.md"
        ).as_posix(),
        "provenance_notice_raw_sha256": notice_sha256,
        "model_weights_loaded": False,
        "generation_run": False,
        "judge_run": False,
        "p1_run": False,
        "smoke_run": False,
        "pilot_run": False,
    }


def build_outputs(
    repo_root: Path,
    *,
    source_path: Path | None = None,
    tokenizer_directory: Path | None = None,
    artifact_directory: Path = DEFAULT_ARTIFACT_DIRECTORY,
    config_directory: Path = DEFAULT_CONFIG_DIRECTORY,
) -> dict[Path, bytes]:
    source_path = source_path or repo_root / DEFAULT_SOURCE_RELATIVE_PATH
    tokenizer_directory = tokenizer_directory or repo_root / DEFAULT_TOKENIZER_RELATIVE_DIRECTORY
    validate_dolly_source_card(source_path)
    p1_targets, jbb_targets, jbb_screen_records = validate_and_load_targets(repo_root)
    tokenizer = QwenTokenizer(tokenizer_directory)
    if tokenizer.encode("Hello world") != [9707, 1879]:
        raise SelectionError("TOKENIZER_SANITY_MISMATCH")

    for record in p1_targets + jbb_targets:
        record["rendered_token_count"] = tokenizer.rendered_length(record["prompt"])
    p1_target_keys = assign_target_deciles(p1_targets, "p1_harmful")
    jbb_target_keys = assign_target_deciles(jbb_targets, "jbb_confirm")
    p1_target_counts = Counter(
        (record["instruction_type"], record["length_decile"])
        for record in p1_targets
    )
    jbb_target_counts = Counter(
        (record["instruction_type"], record["length_decile"])
        for record in jbb_targets
    )
    p1_matrix = counter_to_matrix(p1_target_counts)
    jbb_matrix = counter_to_matrix(jbb_target_counts)
    if p1_matrix != EXPECTED_P1_TARGET_MATRIX:
        raise SelectionError(f"P1_TARGET_DISTRIBUTION_MISMATCH: {p1_matrix}")
    if jbb_matrix != EXPECTED_JBB_TARGET_MATRIX:
        raise SelectionError(f"JBB_TARGET_DISTRIBUTION_MISMATCH: {jbb_matrix}")
    confirm_quotas = scaled_largest_remainder_quotas(jbb_target_counts, 30, 50)
    confirm_matrix = counter_to_matrix(confirm_quotas)
    if confirm_matrix != EXPECTED_CONFIRM_QUOTA_MATRIX:
        raise SelectionError(f"CONFIRM_QUOTA_MISMATCH: {confirm_matrix}")

    candidates, eligibility_counts, duplicate_summary = load_and_filter_dolly(source_path)
    expected_reasons = Counter(
        {
            "context_dependent": 4_467,
            "obvious_unsafe_lexical": 125,
            "normalized_exact_duplicate": 180,
            "eligible": 10_239,
        }
    )
    if eligibility_counts != expected_reasons:
        raise SelectionError(
            f"ELIGIBILITY_COUNT_MISMATCH: {dict(sorted(eligibility_counts.items()))}"
        )
    prepare_candidates(candidates, tokenizer, p1_target_keys, jbb_target_keys)
    selected_p1, selected_confirm, capacity = joint_select(
        candidates,
        p1_target_counts,
        confirm_quotas,
    )
    overlap = _overlap_summary(
        selected_p1,
        selected_confirm,
        p1_targets,
        jbb_targets,
        jbb_screen_records,
    )
    near_duplicate_candidates = bounded_near_duplicate_review(
        selected_p1,
        selected_confirm,
        p1_targets,
        jbb_targets,
        jbb_screen_records,
    )

    registry_bytes = pretty_json_bytes(_instruction_type_registry())
    registry_sha256 = hashlib.sha256(registry_bytes).hexdigest()
    notice_bytes = _license_notice()
    notice_sha256 = hashlib.sha256(notice_bytes).hexdigest()
    p1_artifact = _selected_artifact(
        "D_norm_confirm.benign", selected_p1, "P1 harmful 100 exact type-by-decile matrix"
    )
    confirm_artifact = _selected_artifact(
        "D_benign_confirm",
        selected_confirm,
        "JBB confirm 50 type-by-decile matrix scaled to 30 by largest remainder",
    )
    p1_path = artifact_directory / "selected_p1_benign_100.json"
    confirm_path = artifact_directory / "selected_benign_confirm_30.json"
    p1_bytes = pretty_json_bytes(p1_artifact)
    confirm_bytes = pretty_json_bytes(confirm_artifact)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "benign_joint_selection_manifest",
        "status": "design_selected",
        "formal_experiment_run": False,
        "source_provenance": {
            "official_dataset_id": SOURCE_DATASET,
            "immutable_revision": SOURCE_REVISION,
            "config": SOURCE_CONFIG,
            "split": SOURCE_SPLIT,
            "source_path": SOURCE_PATH,
            "source_raw_byte_length": source_path.stat().st_size,
            "source_raw_sha256": SOURCE_RAW_SHA256,
            "source_row_count": SOURCE_ROW_COUNT,
            "source_card_sha256": SOURCE_CARD_SHA256,
            "prompt_field": "instruction",
            "context_rule": "normalized context must be empty",
            "response_role": (
                "not used for eligibility, taxonomy, matching, ranking, runtime input, or published text"
            ),
            "raw_row_sha256_role": (
                "provenance-only whole-line misread detection; excluded from all membership inputs"
            ),
            "stable_source_id_format": (
                "dataset@revision:path:config/split:row=<zero-padded zero-based row index>"
            ),
            "license": SOURCE_LICENSE,
            "license_notice_relative_path": (
                artifact_directory / "provenance_license_notice.md"
            ).as_posix(),
            "license_notice_raw_sha256": notice_sha256,
        },
        "eligibility": {
            "ordered_rules": [
                "exact four-field source schema and string instruction/context/category",
                "nonblank normalized instruction",
                "empty normalized context",
                "at least 90 percent Latin among alphabetic characters",
                "no reserved special-token surface",
                "no obvious unsafe lexical match",
                "one lowest-index representative per normalized exact prompt identity",
            ],
            "normalization": [
                "Unicode NFKC", "trim", "collapse consecutive whitespace to ASCII space"
            ],
            "normalized_exact_identity_addition": "Unicode casefold",
            "counts": dict(sorted(eligibility_counts.items())),
            "normalized_duplicate_representatives": duplicate_summary,
        },
        "instruction_taxonomy": {
            "registry_relative_path": (
                artifact_directory / "instruction_type_registry.json"
            ).as_posix(),
            "registry_raw_sha256": registry_sha256,
            "complete_target_mapping": True,
            "complete_selected_mapping": True,
            "llm_mapping_calls": 0,
        },
        "tokenizer_and_rendering": {
            "source": TOKENIZER_SOURCE,
            "immutable_revision": TOKENIZER_REVISION,
            "file_sha256": TOKENIZER_FILE_SHA256,
            "chat_template_text": tokenizer.chat_template,
            "chat_template_sha256": CHAT_TEMPLATE_SHA256,
            "rendering_package": "T0_native_user_only",
            "messages_input": [{"role": "user", "content": "<canonical prompt>"}],
            "tools": None,
            "add_generation_prompt": True,
            "additional_bos_or_eos": False,
            "default_system_origin": "pinned chat template branch, not an input message",
            "rendered_token_count_algorithm": (
                "token count of the pinned template's no-tools single-user generation-prompt rendering "
                "under the pinned Qwen ByteLevel-BPE"
            ),
            "sanity_hello_world_token_ids": [9707, 1879],
            "model_weights_loaded": False,
        },
        "targets": {
            "p1_harmful": {
                "relative_path": P1_SELECTED_RELATIVE_PATH.as_posix(),
                "raw_sha256": P1_SELECTED_SHA256,
                "row_count": 100,
                "type_by_decile": matrix_to_json(p1_matrix),
            },
            "jbb_confirm": {
                "relative_path": JBB_CONFIRM_RELATIVE_PATH.as_posix(),
                "raw_sha256": JBB_CONFIRM_SHA256,
                "row_count": 50,
                "source_revision": JBB_SOURCE_REVISION,
                "prompt_field": "prompt",
                "Target_excluded": True,
                "type_by_decile": matrix_to_json(jbb_matrix),
            },
        },
        "selection": {
            "namespace": SELECTION_NAMESPACE,
            "length_namespace": LENGTH_NAMESPACE,
            "master_seed": MASTER_SEED,
            "target_decile_rule": (
                "sort by rendered token count then role/source-ID length tie hash; "
                "decile is 1 + floor(10*zero-based rank/N)"
            ),
            "candidate_decile_rule": (
                "bisect-right insertion rank under the same role/source-ID tie hash; "
                "rank N is clamped to N-1"
            ),
            "role_length_support_inclusive": {
                role: list(bounds) for role, bounds in ROLE_LENGTH_SUPPORT.items()
            },
            "p1_quota": matrix_to_json(p1_matrix),
            "benign_confirm_quota": matrix_to_json(confirm_matrix),
            "benign_confirm_quota_rule": (
                "floor(30*n/50), then largest remainder; type order then decile ascending tie-break"
            ),
            "allocation_priority": ["p1_benign", "benign_confirm"],
            "identity_removal_before_confirm": [
                "source_id", "source_record_identity_sha256", "prompt_identity_sha256"
            ],
            "rank_payload_fields": [
                "master_seed", "namespace", "source_id", "split", "stratum"
            ],
            "rank": "SHA256 of canonical UTF-8 JSON",
            "within_stratum_order": "rank ascending, stable source ID tie-break",
            "final_output_order": "stable source ID ascending",
            "capacity_failure": "fail immediately; no refill, reduced N, or source change",
            "capacity": capacity,
        },
        "duplicate_and_overlap": {
            "normalized_exact_overlap": overlap,
            "near_duplicate_thresholds": {
                "word_token_jaccard": WORD_NEAR_DUPLICATE_THRESHOLD,
                "character_5gram_jaccard": CHAR5_NEAR_DUPLICATE_THRESHOLD,
            },
            "bounded_review_rounds": 1,
            "near_duplicate_candidates": near_duplicate_candidates,
            "near_duplicate_review_complete": True,
            "membership_changed_by_near_duplicate_review": False,
        },
        "selected_artifacts": {
            "p1_benign": {
                "relative_path": p1_path.as_posix(),
                "raw_sha256": hashlib.sha256(p1_bytes).hexdigest(),
                "row_count": 100,
                "source_ids_sha256": p1_artifact["frame_source_ids_sha256"],
            },
            "benign_confirm": {
                "relative_path": confirm_path.as_posix(),
                "raw_sha256": hashlib.sha256(confirm_bytes).hexdigest(),
                "row_count": 30,
                "source_ids_sha256": confirm_artifact["frame_source_ids_sha256"],
            },
        },
        "status_boundary": {
            "formal_experiment_run": False,
            "model_weights_loaded": False,
            "generation_run": False,
            "judge_run": False,
            "p1_run": False,
            "smoke_run": False,
            "pilot_run": False,
            "run_ready": False,
            "paper_run_ready": False,
        },
    }
    manifest_bytes = pretty_json_bytes(manifest)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()

    p1_config = _active_entry(
        "D_norm_confirm.benign",
        DEFAULT_ARTIFACT_DIRECTORY / p1_path.name,
        p1_bytes,
        selected_p1,
        "P1 harmful 100 exact type-by-decile matrix",
        manifest_sha256,
        registry_sha256,
        notice_sha256,
    )
    confirm_config = _active_entry(
        "D_benign_confirm",
        DEFAULT_ARTIFACT_DIRECTORY / confirm_path.name,
        confirm_bytes,
        selected_confirm,
        "JBB confirm 50 largest-remainder type-by-decile quota scaled to 30",
        manifest_sha256,
        registry_sha256,
        notice_sha256,
    )
    return {
        p1_path: p1_bytes,
        confirm_path: confirm_bytes,
        artifact_directory / "benign_selection_manifest.json": manifest_bytes,
        artifact_directory / "instruction_type_registry.json": registry_bytes,
        artifact_directory / "provenance_license_notice.md": notice_bytes,
        config_directory / "p1_benign_v1.json": pretty_json_bytes(p1_config),
        config_directory / "benign_confirm_v1.json": pretty_json_bytes(confirm_config),
    }


def write_outputs(repo_root: Path, outputs: dict[Path, bytes], *, check: bool) -> None:
    for output_path, payload in outputs.items():
        path = output_path if output_path.is_absolute() else repo_root / output_path
        if check:
            if not path.is_file() or path.read_bytes() != payload:
                raise SelectionError(f"CHECKED_ARTIFACT_MISMATCH: {output_path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--tokenizer-directory", type=Path)
    parser.add_argument("--artifact-directory", type=Path, default=DEFAULT_ARTIFACT_DIRECTORY)
    parser.add_argument("--config-directory", type=Path, default=DEFAULT_CONFIG_DIRECTORY)
    parser.add_argument("--check", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    source_path = args.source.resolve() if args.source else None
    tokenizer_directory = (
        args.tokenizer_directory.resolve() if args.tokenizer_directory else None
    )
    try:
        outputs = build_outputs(
            repo_root,
            source_path=source_path,
            tokenizer_directory=tokenizer_directory,
            artifact_directory=args.artifact_directory,
            config_directory=args.config_directory,
        )
        write_outputs(repo_root, outputs, check=args.check)
    except SelectionError as exc:
        raise SystemExit(str(exc)) from exc
    for relative_path in sorted(outputs, key=lambda path: path.as_posix()):
        print(
            f"{relative_path.as_posix()} "
            f"{hashlib.sha256(outputs[relative_path]).hexdigest()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
