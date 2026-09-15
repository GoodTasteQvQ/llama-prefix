from __future__ import annotations

import json
from pathlib import Path

from paper1_broadening.config import load_config, resolve_path
from paper1_broadening.frames import (
    DEFAULT_E1_REVIEW_PROMPT_REVISION,
    _e1_reference_snapshot,
    _load_e1,
    build_frames,
    close_e1_overlap_gate,
)


ROOT = Path(__file__).resolve().parents[1]
config = load_config(ROOT / "configs/paper1_broadening/mbd_nm_v212_public_expanded.json")
frames = build_frames(config)
e1 = _load_e1(
    resolve_path(config, config["data"]["e1_harmbench_path"]),
    resolve_path(config, config["data"]["e1_metadata_path"]),
)
snapshot = json.loads((ROOT / ".codex-temp/paper1_e1_final_overlap/reference_snapshot.json").read_text())
safe_pairs = json.loads(
    (ROOT / config["data"]["safe_pairs_path"]).read_text(encoding="utf-8")
)
references = _e1_reference_snapshot(
    jbb100=frames["jbb100"],
    jbb40=frames["jbb40"],
    benign30=frames["benign30"],
    safe_pairs=safe_pairs,
    safe_split=frames["safe_pair_split"],
)
assert references == snapshot["references"]
assert len(references) == 700
assert not any(row["reference_kind"] == "benign30" for row in references)
closed = close_e1_overlap_gate(
    e1["candidate_records"],
    forbidden_frames=snapshot["references"],
    reference_digest=snapshot["reference_digest"],
)
assert closed["reference_digest"] == snapshot["reference_digest"]
assert closed["review_prompt_revision"] == DEFAULT_E1_REVIEW_PROMPT_REVISION
assert closed["status"] == "NOT_RUN"
assert closed["reason"] == "E1_SEMANTIC_OVERLAP_REVIEW_PENDING"
assert len(closed["review_queue"]) == 17
assert closed["records"] == []
assert frames["e1"]["status"] == "NOT_RUN"
print(json.dumps({
    "status": "E1_CONSUMER_PENDING",
    "reason": closed["reason"],
    "candidate_count": len(e1["candidate_records"]),
    "review_queue_count": len(closed["review_queue"]),
    "reference_digest": closed["reference_digest"],
    "selected_count": len(closed["records"]),
    "reference_count": len(references),
}, sort_keys=True))
