# Paper 1 Stage 3 production closure

These entry points implement the non-formal local closure for the frozen
`v3.5-rc2 + binding-amendment-01` design. They do not download models or data,
run model inference, or produce formal P1/P2 results.

Always run from the repository root after setting the project-local temporary
directory required by `AGENTS.md`:

```powershell
$codexTemp = Join-Path (Get-Location) ".codex-temp"
New-Item -ItemType Directory -Force $codexTemp | Out-Null
$env:TEMP = $codexTemp
$env:TMP = $codexTemp
$env:NX_DAEMON = "false"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:HF_HUB_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

python -B scripts/stage3_production/verify_e0.py
python -B scripts/stage3_production/verify_binding_ready.py
python -B scripts/stage3_production/offline_smoke.py
python -B scripts/stage3_production/synthetic_dry_run.py --output stage3_artifacts/synthetic_dry_run
python -B scripts/stage3_production/build_offline_assets.py --output stage3_artifacts/offline
```

The asset loader resolves `PAPER1_STAGE3_ASSET_ROOT/data/...`; when the
variable is absent it uses the repository root. Paths are not experimental
identity. Raw file SHA256 and the separately computed canonical frame hash are.

The approved `data/stage3/p1_harmful_do_not_answer_v1/` package is validated as
`CANDIDATE_BINDING_INPUT`. Its exact 100-row identity, source provenance,
checksums, self hashes, category registry, and CC-BY-NC-SA-4.0 notice are bound,
but it is not a `FORMAL_INPUT`. P1 benign, behavior screen/confirm, and benign
confirm identities remain A0, so the repository manifest remains
`DATA_IDENTITY_BLOCKED` with `formal_inputs=[]` and `run_ready=false`.

`stage3_pipeline.binding` provides versioned implementation schemas and
dependency-closed validators for checkpoint and judge attestations, the
30x3584 float32 vector pool, the complete base-anchor provenance variant, and
the five-split 310-identity prompt-frame manifest. A real
`OFFLINE-ASSET-READY` state is derived only after all five validators pass and
produce five nonempty, uniquely loadable `FORMAL_INPUT` source entries. Each
entry binds raw bytes, source schema, ordered row/frame identity, prompt-frame
membership, immutable upstream provenance, and explicit license material.
`OfflineJsonLoader` revalidates the complete binding set and these files before
loading. Full-shaped fixtures use `SYNTHETIC-BINDING-VALIDATED` or the explicit
`SYNTHETIC-OFFLINE-LOADER-READY` bundle-test status; neither is a formal claim.

For prompt payload provenance, every non-P1 split must use a byte-addressed
`local_snapshot` whose tree hash is the `source_revision`. A Git, Hugging Face,
or object-store revision declaration alone is not accepted as offline proof that
`revision:upstream_source_path` resolves to the supplied bytes. The fixed P1
harmful candidate is the only exception because its upstream commit, package
bytes, frame, manifest, and candidate-only boundary are independently pinned.

On a server where the complete real assets have been installed below one asset
root, the bundle entry point requires all five named binding documents and an
explicit output path:

```powershell
python -B scripts/stage3_production/build_offline_assets.py `
  --output .codex-temp/stage3_server_build `
  --asset-root .codex-temp/stage3_assets `
  --binding-root .codex-temp/stage3_assets `
  --bundle-output .codex-temp/stage3_bundle/offline_bundle
```

The binding root must contain `checkpoint_identity_attestation.json`,
`judge_identity_attestation.json`, `stage3_vector_manifest.json`,
`base_anchor_binding_manifest.json`, and `prompt_frame_binding_manifest.json`.
If any document, prompt payload, snapshot evidence, license, or source byte is
missing or inconsistent, the command fails without emitting a READY bundle.

The Round 12 portable implementation inventory hashes only canonical checkout
and prospective Git-blob bytes plus fixed attribute policy, producer identity,
and the Round 11/10/9 parent chain. Current tracking/index classifications are
non-normative diagnostics. An isolated local Git fixture verifies identical
identity before staging, after commit, and in a clean LF/byte-exact clone.

`scripts/download_jbb_behaviors.py` is a connected-workstation reconstruction
tool only. It requires an exact 40-hex dataset commit, fixes the repository,
config, split, 100-row schema, and JSON format, and denies overwrite by default.
It must never be run on the server or used as an online fallback.

Support and confirmation use separate immutable registry-bound attempt ledgers,
authorized by lifecycle events 7 and 10 respectively. Event 8 binds the fixed
`receipts/support_execution_attempts.jsonl` ledger and the canonical
`records/support_execution_sources.json` source set. The 900-row support
manifest is uniquely materialized from the event-7 lifecycle entry, receipt
tip/count/file hash, phase registry, generation and judge records, terminal
dispositions, and response/dose records. Events 8, 9, and 10 revalidate those
bindings. Final reconciliation verifies both historical authorizations, their
disjoint 900/4,680 identity partitions, paired start/terminal events, exact call
counts, and all 5,580 terminal dispositions. Integrity blocks are derived only
from canonical identity, dose, and support manifests; A/T blocks cannot spill
into clean or unrelated cells, H never blocks a confirmation cell, and each
confirmation ID is checked before `GENERATION_STARTED` and before backend use.

Judge execution accepts a completed materialized generation and derives domain,
phase, judge-freeze hash, and the exact domain rubric from the fixed registry
and `protocol/judge_freeze.json`. P2, benign, and K1 production records must use
their source-aware materialization validators; these bind registry identity,
generation and judge hashes, prompt/vector/anchor/estimator fields, pair
identity, mode, the frozen measurement-result dose manifest, and exact retained
P2 reuse. `FreezeLifecycle.authenticated_dose_context()` verifies the lifecycle
prefix and issues an immutable context containing the canonical measurement
manifest self hash, its four parent hashes, the registry hash, mode, and current
authorization tip. Support, P2, benign, and K1 materializers require this
context, so a fully rechained manifest with substituted parents is rejected.

Generation injects the authenticated measurement-result manifest hash into
every completed or failed attempt before recording it. Technical and terminal
backend exceptions may carry validated diagnostics; conflicting lifecycle keys
are terminalized rather than accepted. When call geometry is available on a
failure, its dose-evidence hash is retained exactly as on a completed call.
Valid per-call geometry is authenticated by that hash in the terminal attempt.
Invalid dose evidence uses the canonical all-null numeric representation.
Clean benign records require null dose evidence while retaining the frozen
measurement-result manifest binding. Synthetic E0 covers completed+parsed
support plus terminal technical, deterministic, and indeterminate generation
paths through source materialization and event 8.

Every lifecycle event binds strict production-shaped backing documents. The
validators enforce exact fields, modes, self hashes, parent hashes, the full
logical registry, 200 P1 terminal rows, the zero-call manual judge-development
ledger, a derived 900-row support manifest, and the fixed 4,680-row behavior
confirmation mapping.

Server-only bindings remain checkpoint/tokenizer/template, base anchors,
vectors, judge identity, CUDA/GPU/runtime, and the formal append-only freeze
manifests. Windows wheels and local cache paths are not transferable runtime
identity.

The server must also enforce OS/container-level egress denial (network
namespace, firewall, or equivalent) and verify it before formal calls. The
Python audit hook is a fail-closed application control, not a substitute for
kernel-level isolation.
