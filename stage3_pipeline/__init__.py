"""Paper 1 Stage 3 v3.5-rc2 production support package.

This package never downloads assets and never runs a formal experiment by
itself. Server model/runtime bindings must be supplied explicitly.
"""

from .core import (
    AppendOnlyReceipt,
    GenerationProducer,
    IdentityError,
    LogicalIdentityRegistry,
    PipelineError,
    TechnicalGenerationError,
    classify_support,
    parse_judge_with_retry,
    validate_dose,
)

__all__ = [
    "AppendOnlyReceipt",
    "GenerationProducer",
    "IdentityError",
    "LogicalIdentityRegistry",
    "PipelineError",
    "TechnicalGenerationError",
    "classify_support",
    "parse_judge_with_retry",
    "validate_dose",
]
