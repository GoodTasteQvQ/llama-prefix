from __future__ import annotations

import hashlib
import json
from pathlib import Path

from paper1_broadening.config import load_config
from paper1_broadening.frames import build_frames
from paper1_broadening.orchestration import DESIGN_SNAPSHOT_PATHS, SOURCE_SNAPSHOT_PATHS


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/paper1_broadening/mbd_nm_v212_public_expanded.json"
MANIFEST = ROOT / "data/safe_pairs_public_semantic_v2_expanded.manifest.json"
SOURCE = ROOT / "data/safe_pairs_public_semantic_v2_expanded.json"
LEDGER = ROOT / "data/safe_pairs_public_semantic_v2_expanded_ledger.json"
E1 = ROOT / ".codex-temp/paper1_e1_final_overlap"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


config = load_config(CONFIG)
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
assert manifest["source_sha256"] == sha(SOURCE)
assert manifest["ledger_sha256"] == sha(LEDGER)
assert manifest["source_count"] == 516 and manifest["ledger_count"] == 509
frames = build_frames(config)
split = frames["safe_pair_split"]
assert (split["source_count"], split["preliminary_eligible_count"], split["executable_eligible_count"]) == (516, 509, 300)
assert split["actual_k"] == 40 and split["gate"] == "READY_FOR_CONSTRUCTION"
assert len(split["construction_folds"]) == 5 and all(len(fold) == 40 for fold in split["construction_folds"])
assert len(split["development"]) == 100 and split["unused"] == []
assert frames["e1"]["status"] == "NOT_RUN"
assert frames["e1"]["reason"] == "E1_SEMANTIC_OVERLAP_REVIEW_PENDING"
reference_snapshot = json.loads((E1 / "reference_snapshot.json").read_text())
assert frames["e1"]["reference_digest"] == reference_snapshot["reference_digest"]
assert reference_snapshot["reference_digest"] == "d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a"
assert len(reference_snapshot["references"]) == 700
assert not any(row["reference_kind"] == "benign30" for row in reference_snapshot["references"])
# The currently materialized C2 ledger/selection still point at the older
# provisional digest and must remain unavailable to the runtime consumer.
for name in ("e1_overlap_ledger.json", "near_match_review_ledger.json", "harmbench40_selection.json", "review_identity_manifest.json"):
    document = json.loads((E1 / name).read_text())
    assert document.get("reference_digest") != reference_snapshot["reference_digest"]
    assert "PROVISIONAL" in str(document.get("status", "")) or "PROVISIONAL" in str(document.get("provisional_status", "")) or name == "review_identity_manifest.json"
assert not (E1 / "e1_final_overlap_ledger.json").exists()
assert not (E1 / "selected40.json").exists()
assert all((ROOT / path).is_file() for path in SOURCE_SNAPSHOT_PATHS + DESIGN_SNAPSHOT_PATHS)
print(json.dumps({
    "status": "CODE_CONTRACT_PASS",
    "source_count": split["source_count"],
    "preliminary": split["preliminary_eligible_count"],
    "executable": split["executable_eligible_count"],
    "actual_k": split["actual_k"],
    "gate": split["gate"],
    "e1_status": frames["e1"]["status"],
    "e1_reason": frames["e1"]["reason"],
    "e1_reference_digest": frames["e1"]["reference_digest"],
    "source_snapshot_paths": len(SOURCE_SNAPSHOT_PATHS),
    "design_snapshot_paths": len(DESIGN_SNAPSHOT_PATHS),
}, sort_keys=True))
