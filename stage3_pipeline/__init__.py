"""Paper 1 Stage 3 active-development support package."""

from .core import (
    DECODE_CONFIG,
    JUDGE_CONFIG,
    GenerationProducer,
    IdentityError,
    LogicalIdentityRegistry,
    OfflineExecutionGuard,
    PipelineError,
    TechnicalGenerationError,
    classify_support,
    offline_execution_guard,
    parse_judge_payload,
    parse_judge_with_retry,
    validate_dose,
    validate_judge_config,
)
from .execution import reconcile_execution, reconcile_support_mapping
from .offline_assets import load_p1_harmful_active_entry
from .run_manifest import build_run_manifest, validate_run_manifest, write_run_manifest
from .records import build_block_response_record, build_k1_reuse_record, build_response_record

__all__ = [
    "DECODE_CONFIG",
    "JUDGE_CONFIG",
    "GenerationProducer",
    "IdentityError",
    "LogicalIdentityRegistry",
    "OfflineExecutionGuard",
    "PipelineError",
    "TechnicalGenerationError",
    "build_run_manifest",
    "build_block_response_record",
    "build_k1_reuse_record",
    "build_response_record",
    "classify_support",
    "load_p1_harmful_active_entry",
    "offline_execution_guard",
    "parse_judge_payload",
    "parse_judge_with_retry",
    "reconcile_execution",
    "reconcile_support_mapping",
    "validate_dose",
    "validate_judge_config",
    "validate_run_manifest",
    "write_run_manifest",
]
