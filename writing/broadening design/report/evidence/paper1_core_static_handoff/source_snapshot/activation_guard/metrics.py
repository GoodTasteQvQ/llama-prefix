from __future__ import annotations

from collections import Counter
import math
import re


def repetition_rate(text: str, ngram_size: int = 3) -> float:
    tokens = text.split()
    if len(tokens) < ngram_size or not tokens:
        return 0.0

    ngrams = [
        tuple(tokens[index : index + ngram_size])
        for index in range(0, len(tokens) - ngram_size + 1)
    ]
    counts = Counter(ngrams)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / max(len(ngrams), 1)


def detect_special_token_leakage(text: str) -> bool:
    patterns = [
        r"<\|.*?\|>",
        r"<s>",
        r"</s>",
        r"\[INST\]",
        r"\[/INST\]",
        r"<think>",
        r"</think>",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def detect_garbled_text(text: str) -> bool:
    if not text:
        return False

    replacement_chars = text.count("\ufffd")
    control_chars = sum(1 for char in text if ord(char) < 32 and char not in "\n\t\r")
    long_symbol_runs = bool(re.search(r"([^\w\s])\1{6,}", text))
    return replacement_chars > 0 or control_chars > 0 or long_symbol_runs


def detect_empty_or_truncated(text: str, min_tokens: int = 8) -> bool:
    tokens = text.split()
    if not tokens:
        return True
    return len(tokens) < min_tokens


def detect_language_switch_like(text: str) -> bool:
    if not text:
        return False

    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    latin_words = re.findall(r"[A-Za-z]{3,}", text)
    if has_cjk and len(latin_words) >= 3:
        return True

    has_latin = bool(re.search(r"[A-Za-z]", text))
    cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    if has_latin and len(cjk_runs) >= 2:
        return True
    return False


def pathological_generation_rate(metrics: dict[str, float | bool]) -> float:
    flags = [
        bool(metrics["empty_or_truncated"]),
        bool(metrics["special_token_leakage"]),
        bool(metrics["garbled"]),
        float(metrics["repetition_rate"]) > 0.2,
    ]
    return 1.0 if any(flags) else 0.0


def compute_response_metrics(text: str) -> dict[str, float | bool | int]:
    tokens = text.split()
    metrics: dict[str, float | bool | int] = {
        "token_count": len(tokens),
        "char_count": len(text),
        "avg_token_length": (
            sum(len(token) for token in tokens) / len(tokens) if tokens else 0.0
        ),
        "repetition_rate": repetition_rate(text),
        "special_token_leakage": detect_special_token_leakage(text),
        "garbled": detect_garbled_text(text),
        "empty_or_truncated": detect_empty_or_truncated(text),
        "early_stop_like": detect_empty_or_truncated(text),
        "language_switch_like": detect_language_switch_like(text),
        "contains_refusal_phrase": any(
            marker in text.lower()
            for marker in [
                "i can't help",
                "i cannot help",
                "i can't assist",
                "cannot comply",
                "不能帮助",
                "无法提供",
            ]
        ),
    }
    metrics["arr"] = pathological_generation_rate(metrics)
    metrics["length_log10"] = math.log10(max(metrics["char_count"], 1))
    return metrics
