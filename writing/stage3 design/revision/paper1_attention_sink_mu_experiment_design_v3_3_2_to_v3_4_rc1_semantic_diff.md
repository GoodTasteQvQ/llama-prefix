# v3.3.2 -> v3.4-rc1 Semantic Diff

- baseline: `paper1_attention_sink_mu_experiment_design_v3_3_2.md`
- target: `paper1_attention_sink_mu_experiment_design_v3_4_rc1.md`
- closure register: `p0_closure_register.md`
- scope: the nine adjudicated DESIGN P0 items only.

| ID | v3.3.2 | v3.4-rc1 semantic change | execution state |
|---|---|---|---|
| `IDENTITY-CKPT` | model series named; revision/hash chosen later | one identity manifest requires fixed repository ID plus immutable checkpoint/tokenizer/template identities; no default branch | `BLOCKED_EXTERNAL_INPUT` |
| `IDENTITY-PROMPT` | manifest fields described; source revision/category frame not fixed | canonical source-hash order, Hamilton quotas, SHA256-derived PCG64 selection, full source/category/license/split identity contract | `BLOCKED_EXTERNAL_INPUT` |
| `IDENTITY-RNG` | random algorithm/seed merely recorded | Torch 2.7.1 CPU `manual_seed(42)`/float32 `randn`/row normalization; screen indices 0-9, confirm 10-(9+V) | `BLOCKED_EXTERNAL_INPUT` for Stage3 pools |
| `ANCHOR-DERIVATION` | any finite ordered external triple could pass; conversion formula absent | exact decimal/binary triple is supplied directly by one pre-screen manifest; no conversion/search/default/fallback | `BLOCKED_EXTERNAL_INPUT` |
| `RESAMPLING-LOCK` | E3/raw/K1/clean/stochastic and other secondary R/seeds open; integration dynamically doubles | every required block has exact R/draw count, master42, canonical SHA256-to-PCG64 substream; integration fixed at 160,000 then fallback | `DESIGN_CLOSED`, fixtures pending |
| `SIM-COMPUTE` | `R_sim>=10,000` plus 9,999 inner fits creates an unbounded/infeasible implementation choice | outer fixed 10,526, inner 9,999; 73 core-null rows require 15,367,960,000 endpoint fits and full 239 rows require 50,314,280,000; resource contract absent/under-cap deterministically stops simulation and sets P2 estimation-only | `BLOCKED_EXTERNAL_INPUT` |
| `K2V2-SCOPE` | multi-df global interactions used scalar raw p, Holm detection, localization, and power language | K2 fixed 12-member and V2 fixed 6-member key-secondary estimate vectors with synchronized simultaneous CI only; global statistic/raw p/Holm/detection/power deleted | `DESIGN_CLOSED`, fixtures pending |
| `TWOPHASE-SE` | prompt bootstrap inherited `1/pi` but did not propagate SRSWOR phase-two error or define `SE_star` | prompt multiplicity x inverse-inclusion x Rao-Wu replicate weight; replicate-SD SE, fixed-scale studentization, explicit non-estimable and family downgrade | `DESIGN_CLOSED`; actual sample input blocked |
| `N-GUARANTEE` | 80% selector wording could be read as guaranteeing the complete final Boolean claim | 80% applies only to the automated P2-B Holm zero-null sub-gate; P2-U is precision; no full-gate/practical/K2/V2 power guarantee | `DESIGN_CLOSED`; selection inputs blocked |

## Preserved Invariants

- endpoints, model count, named model line, formal layers, sample candidates, human N=720,
  scenario values, anchors count, vector-family count, phase schedules, decoding primary, and
  logical generation budget formulas are unchanged.
- P1, P2, K1, rendering, benign, stochastic, attention, V2 construction/rescue, failure taxonomy,
  and human sampling estimands/methods are not otherwise optimized or expanded.
- planning logical totals remain `23,034/22,890`; completed-rescue planning remains
  `24,984/24,840`; scope-grid totals remain `59,234/59,090`.
- all v3.3.2 and older files remain unchanged.

## Deliberate Non-Outputs

This revision did not run a formal experiment, confirmation, bootstrap, simulation, model fit,
or coverage/power calculation. It did not create a checkpoint/prompt/vector/anchor manifest,
Freeze A/B, human sample lock, resource contract, fixture pass record, or result artifact.
Repository-unsupported values remain `BLOCKED_EXTERNAL_INPUT`.
