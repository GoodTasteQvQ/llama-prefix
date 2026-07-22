# v3.3.2 -> v3.4-rc1 P0 Closure Register

- baseline: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md`
- target: `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_4_rc1.md`
- date: `2026-07-22`
- adjudication inputs: `writing/judge subagent/version_readiness_matrix.md`,
  `PIPE-001_protocol_execution_audit.md`, `STAT-001_statistical_closure_audit.md`,
  `resource_and_implementation_audit.md`, and `REG-001_version_regression_audit.md`.
- scope: exactly the nine adjudicated DESIGN P0 items; no formal experiment, confirmation,
  coverage run, power run, or result artifact was generated.
- status vocabulary: `DESIGN_CLOSED` means the protocol rule is unique; `BLOCKED_EXTERNAL_INPUT`
  means an external value/artifact is absent and execution must stop; `FIXTURE_PENDING_IMPLEMENTATION`
  means no pass artifact is asserted.

## IDENTITY-CKPT

- evidence: PIPE-001 v3.3.2 subfinding 1 (`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:381,385,507`) says checkpoint/model
  identity is non-unique. Repository download scripts identify `Qwen/Qwen2.5-7B-Instruct`,
  `LLM-Research/Meta-Llama-3.1-8B-Instruct`, and `mistralai/Mistral-7B-Instruct-v0.3`, but
  their `--revision` defaults are unset. No three-model immutable revision, weight SHA256,
  tokenizer hash, or template hash was found.
- accepted decision: fix those three repository IDs and require an immutable revision/commit,
  execution path, weight hash, tokenizer revision/hash, and full chat-template text/hash for
  every model in `protocol/experiment_identity_manifest.json`; default branch/head and same-name
  local directories are invalid substitutes.
- modification location: rc1 §§0.1, 6.3-6.4, 7.1, 20.2, 24.2.
- fixture: `identity_ckpt_required_fields`; missing revision/weight/tokenizer/template hash is
  non-zero; same model ID with different revision yields different cell identity.
- status: `BLOCKED_EXTERNAL_INPUT` (fixture not generated).

## IDENTITY-PROMPT

- evidence: local `data/jbb_behaviors_harmful.json` is a 100-row JBB candidate source with
  SHA256 `9EE1CB2AAB52550F0817F036E4423E9F3CC05A6BB5A0084DA404F1817D535E77`; its companion
  metadata (`JailbreakBench/JBB-Behaviors`, `behaviors`, `harmful`) has SHA256
  `0F03EF1D440CD364CEA3F8A15ED4D9ED08AE25DCDE791666B49E282BF6D540FF`. The metadata lacks
  dataset revision, license, retrieval timestamp, and a complete category-registry version.
  `data/safe_pairs.json` has only `harmful/harmless` fields (SHA256
  `822202EEED0231C17427138CED8E34EE7736C30AF6937899579697D6B72E4548`) and is not qualified
  V2 provenance.
- accepted decision: one prompt manifest records immutable source/version/revision, license,
  retrieval time, category registry/hash, record IDs, source hashes, Hamilton quotas,
  normalization/dedup/leakage audit, seed 42, and all split identities. Canonical record-hash
  ordering plus a SHA256-derived NumPy PCG64 substream is the only selection contract;
  `D_second_confirm` and stochastic subsets derive only from the frozen behavior frame.
- modification location: rc1 §§0.1, 6.3-6.4, 7.7-7.8, 20.2, 24.2.
- fixture: `identity_prompt_required_fields`; missing source revision/license/category registry
  blocks; same source and seed reproduces the same frame hash.
- status: `BLOCKED_EXTERNAL_INPUT` (fixture not generated).

## IDENTITY-RNG

- evidence: `activation_guard/vectors.py:49-91` defines CPU `torch.Generator`, `manual_seed`,
  `torch.randn`, and row L2 normalization. `Rogue/requirements.txt` pins `torch==2.7.1`.
  Existing Qwen Stage1 pool manifest records hidden dimension 3584, 1000 vectors, seed 42,
  float32, normalized; its manifest SHA256 is
  `1F82FFBB9BB541557509B873908C01B0513967A6B6F883C8A272C9E926E6A60B` and tensor SHA256 is
  `5260D0A3B2CD7206FD10025B6E555C6D1835CA6B2C66CEC59FCE7895EE7EBD2D`. No Stage3
  three-model pool/partition manifest exists.
- accepted decision: use Torch 2.7.1 CPU API, float32, master seed 42, per-row L2 normalization;
  generate each model independently. The only partition is `V_screen=0..9` and
  `V_confirm=10..(9+V)`, with `V in {20,25,30}` selected before confirmation; no outcome-based
  reordering/replacement and no cross-model geometric pairing.
- modification location: rc1 §§7.2, 9, 19.8, 20.2, 24.2.
- fixture: `identity_rng_partition`; checksum and repeated generation are bitwise stable,
  screen/confirm intersection is empty, and each model has the exact index range.
- status: `BLOCKED_EXTERNAL_INPUT` (algorithm/seed closed; complete Stage3 artifacts and fixture absent).

## ANCHOR-DERIVATION

- evidence: PIPE-001 v3.3.2 subfinding 2 (`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:259,267,289`) says the manifest schema
  permits arbitrary ordered triples and names a conversion version without a conversion formula.
  No `base_anchor_manifest.json` exists. Existing Stage1 `c` grids and historical `mu` values
  are outcome-visible and lack a frozen median-content-norm/source-to-rho function.
- accepted decision: the external pre-screen manifest directly supplies one exact decimal/binary
  triple. Selection is identity selection only; check finite/order, source-before-screen,
  dependency-closed hashes, decimal/binary agreement, and no outcome/human-gold contamination.
  Missing/invalid input blocks Freeze B; no default, search, conversion, midpoint, or rescue value.
- modification location: rc1 §§5.4, 6.4, 7.2, 9, 24.2.
- fixture: `base_anchor_manifest_missing_hash_order_contamination`; all five invalid cases block
  and assert that no default numeric anchor is produced.
- status: `BLOCKED_EXTERNAL_INPUT` (fixture not generated).

## RESAMPLING-LOCK

- evidence: resource audit RI-V332-001 (`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:629,869,1004-1026,1122-1129,1144-1146`)
  says required secondary/bootstrap counts and seeds remain free; v3.3.2 only fixes some 10,000
  and 9,999 procedures.
- accepted decision: exact counts are the rc1 §19.8 table: P1/planning/E3/clean/K1/stochastic
  blocks 10,000; P2/rendering/K2/V2/two-phase blocks 9,999; P2 outer simulation 10,526;
  inner simulation 9,999; population integration 160,000 fixed draws with immediate existing
  fallback on MCSE failure. Master seed is 42. Per-block/unit/replicate substreams use the
  canonical SHA256-labeled PCG64 derivation in §19.8; no runtime doubling or executor choice.
- modification location: rc1 §§14.3-14.4, 18.3, 19.3, 19.6, 19.8, 24.2.
- fixture: `resampling_lock_counts_seed_substreams`; verifies every listed count, seed bytes,
  replicate numbering, shared-family identity, and no cross-block stream reuse.
- status: `DESIGN_CLOSED; FIXTURE_PENDING_IMPLEMENTATION`.

## SIM-COMPUTE

- evidence: RI-V332-002 (`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:1015-1026,1068-1088,1150-1161`)
  gives the 10,000 x 9,999 nested infeasibility. The v3.3.2 scenario union and two endpoints
  imply at least 14,600,000,000 core-null endpoint fits before fallback/integration overhead.
- accepted decision: rc1 locks `R_outer=10,526` (so 0.95 completion still leaves 10,000
  successful datasets) and `R_inner=9,999`; §18.5.1 computes 5,684,040,000 fits for the
  27-row audit lower bound, 15,367,960,000 for 73 core-null rows, 34,104,240,000 for 162
  N-screen rows, and 50,314,280,000 for the full 239-row active P2 union. K2/V2's 52+25
  pattern rows are not active because they are pre-downgraded to CI-only. A real
  `simulation_resource_contract.json` is required; if absent/under-cap, do not run simulation
  or create P/V/N, coverage, or power artifacts and take the deterministic P2 `100/30,
  estimation-only` branch.
- modification location: rc1 §§18.3, 18.5-18.5.1, 18.6-18.7, 19.8, 20.9, 24.2.
- fixture: `sim_compute_budget_arithmetic`; recomputes scenario counts, fit formulas, 0.95/10,000
  MCSE guard, and resource-contract stop branch without running a simulation.
- status: `BLOCKED_EXTERNAL_INPUT` (resource contract absent; no budget artifact generated).

## K2V2-SCOPE

- evidence: STAT-001 v3.3.2 (`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:762-779,1150-1167`)
  says K2/V2 multi-df global interactions are not computable under scalar raw-p/max-T; PIPE-001
  and resource audit also retain the same P0 path.
- accepted decision: retain the existing endpoints/models/anchors/samples and estimate only
  fixed canonical contrasts: K2 has 12 members (2 endpoints x 2 non-Qwen models x 3 anchors),
  V2 has 6 (2 endpoints x 3 anchors). Each family uses one synchronized 9,999-replicate
  max-T simultaneous 95% CI. No global statistic, global detection, raw p, Holm, power, or
  reverse expansion; a CI excluding 0 remains an anchor-wise estimate.
- modification location: rc1 §§1.2, 2.3, 4.8, 6.4, 9, 15.1-15.2, 16.4, 18.6-18.7, 19.1,
  19.6-19.8, 20.9, 22.2, 23, 24.2.
- fixture: `k2v2_member_order_ci_only`; checks 12/6 member order, shared resampling identity,
  non-estimable/completion downgrade, and rejects global/Holm/power wording.
- status: `DESIGN_CLOSED; FIXTURE_PENDING_IMPLEMENTATION`.

## TWOPHASE-SE

- evidence: STAT-001 v3.3.2 (`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:721-733,1159`) says
  replicate-level two-phase SE is undefined; v3.3.2 §14.4 has Hájek residual correction but no
  phase-two SRSWOR variance propagation.
- accepted decision: retain self-normalized Hájek residual point estimator and clip. For each
  prompt replicate and phase-two stratum use `d_i=1/pi_i` and the unique Rao-Wu rescaled weight
  `g_(hi,b)` in rc1 §14.4; combine as `prompt multiplicity x d_i x g_(hi,b)`. Compute
  `SE_hat_j` as the successful-replicate SD, use fixed-scale `SE_(j,b)_star=SE_hat_j` for
  studentization, and require 9,500/9,999 common successes. Zero pi, `n=1<N`, invalid weight,
  zero denominator, nonfinite/near-zero SE, or completion failure is non-estimable/downgrade;
  no reroll, new gold, or expansion.
- modification location: rc1 §§6.4, 9, 14.4, 17.5-17.7, 19.6, 19.8, 21.3, 23, 24.2.
- fixture: `two_phase_srswor_rao_wu_se`; census, `n=1<N`, hand-calculated weights/SE/max-T,
  positivity, and 9,499/9,500 completion boundary. No fixture output is claimed.
- status: `DESIGN_CLOSED; BLOCKED_EXTERNAL_INPUT` for actual sample-lock/gold plus
  `FIXTURE_PENDING_IMPLEMENTATION`.

## N-GUARANTEE

- evidence: STAT-001 v3.3.2 (`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:975-986,1086-1088`)
  says the selector used automated P2-B Holm power and P2-U width while final wording also
  requires automated max-T, two-phase, quality, positivity, and support gates.
- accepted decision: keep P1's existing 80% rule. For P2, 80% is only the canonical automated
  P2-B Holm zero-null rejection sub-gate; P2-U contributes automated simultaneous-CI precision.
  No 80% guarantee applies to automated max-T, two-phase CI/sign, judge quality/support,
  positivity/ESS, practical `m_B`, complete §17.7 Boolean gate, K2, or V2. Candidate failure or
  missing resource contract follows the deterministic `P=100,V=30` endpoint downgrade and never
  retrofits N from human/two-phase/confirmation outcomes.
- modification location: rc1 §§18.5, 18.7, 23.1-23.2, 24.2.
- fixture: `n_guarantee_scope`; pass matrix permits only automated P2-B sub-gate wording and
  rejects full-Boolean/K2/V2 power claims.
- status: `DESIGN_CLOSED; BLOCKED_EXTERNAL_INPUT` pending f_screen/backend/resource/simulation
  inputs; no power value generated.
