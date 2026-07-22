# v3.5-rc2 binding amendment 01

Status: `DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`

This directory contains the append-only executable binding amendment that
repairs only closure-audit findings `P0-STAT-01` and `P0-STAT-02`. It is not a
new experiment-design version. The base v3.5-rc2 protocol, its audit and
semantic diff, and every previously hash-bound rc2 artifact remain unchanged.

## Normative map

| Role | Path |
|---|---|
| amendment specification | `writing/stage3 design/revision/paper1_attention_sink_mu_experiment_design_v3_5_rc2_binding_amendment_01.md` |
| matched two-phase schema/specification | `two_phase/two_phase_input.schema.json`, `two_phase/README.md` |
| matched two-phase executable/golden verifier | `scripts/stage3_design/v3_5_rc2_binding_amendment_01/two_phase/` |
| retained-bootstrap schema/specification | `retained_bootstrap/retained_bootstrap_schema.json`, `retained_bootstrap/README.md` |
| retained-bootstrap executable/golden verifier | `scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/` |
| immutable pre-amendment evidence | `base_rc2_hashes_initial.sha256` |
| static-verifier contract | `verifier_contract.json` |
| complete content binding | `amendment_binding_manifest.json` |
| release inventory | `amendment_release_manifest.json` |
| audit mapping | `audit_disposition.md` |
| aggregate static verifier | `scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py` |

The amendment specification has priority only for the two incomplete
executable bindings identified by the closure audit. Within each repair, the
input schema fixes admitted records, the local README fixes the algorithmic
contract, the reference implementation fixes operation and draw order, and the
synthetic golden fixtures fix byte-exact behavior. The local hash manifest and
the aggregate manifests bind those files. No amendment artifact may override
any other v3.5-rc2 term.

## Integrity model

`base_rc2_hashes_initial.sha256` is preserved byte-for-byte. The aggregate
verifier checks all 25 entries against the working tree, including the physical
SHA256 of the base rc2 release manifest. The old release manifest is treated as
immutable historical evidence; this amendment does not rebuild or rewrite it.

JSON manifest self hashes use canonical UTF-8 JSON with recursively sorted
keys, ASCII escaping, no insignificant whitespace, finite values only, and the
top-level `self_sha256` field excluded. `amendment_binding_manifest.json` binds
every new implementation, schema, README, fixture, and verifier plus the base
transitive dependencies. `amendment_release_manifest.json` additionally binds
the aggregate binding manifest and the initial base-hash evidence. Any missing
file, unbound extra file, length mismatch, content-hash mismatch, self-hash
mismatch, or transitive mismatch is fatal.

All fixture records are explicitly marked `synthetic_data=true`. They contain
no formal P1, support, generation, judge, or human data.

## Verification

From the repository root, redirect temporary files before running any verifier:

```powershell
$codexTemp = Join-Path (Get-Location) ".codex-temp"
New-Item -ItemType Directory -Force $codexTemp | Out-Null
$env:TEMP = $codexTemp
$env:TMP = $codexTemp
$env:NX_DAEMON = "false"
$env:PYTHONDONTWRITEBYTECODE = "1"

python -B scripts/stage3_design/v3_5_rc2_binding_amendment_01/two_phase/verify_two_phase_golden.py
python -B scripts/stage3_design/v3_5_rc2_binding_amendment_01/retained_bootstrap/verify_golden.py
python -B scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py
```

The aggregate verifier imports and calls both reference modules, runs both
success/failure golden suites, verifies exact sync JSON and RNG draw behavior,
checks executable coverage and production counts, rescans the scope guard,
recomputes budgets, and exits nonzero on any discrepancy. Its success marker is
`AMENDMENT_STATIC_VERIFICATION_PASS`; this is an artifact-verification result,
not a final design-freeze verdict.
