# Paper 1 C2 E1 Final Overlap Report

日期：2026-09-15（Asia/Shanghai）  
工作目录：`/data/goodtaste_workspace/llama-prefix`  
任务：`paper1_server_codex_e1_final_overlap_prompt_nohup.md`，C2 / `e1-final-overlap-v1`  
分支：`stage3/impl-candidate`  
当前 HEAD：`a62ff22`（执行期间未 commit、未 push）

## 结论

`E1_FRAME_READY`

这里的 READY 只表示 C2 overlap gate、near-match 双审核和固定 40 条数据帧已经形成；不表示模型运行、generation、Judge、analysis 或正式 E1 gate 已通过。

`E1_EXPERIMENT_NOT_RUN`  
`FORMAL_EXPERIMENTS_NOT_RUN`

本任务没有重新审核 safe-pair，没有加载模型，没有启动 prepare、directions、screen、generation、Judge、analysis 或 human packet。没有修改共享实现、原实验设计正文、safe-pair source/ledger、JBB、benign frame 或 canonical config。

## 固定输入与完整性

### HarmBench

- 来源：`https://github.com/centerforaisafety/HarmBench`
- 不可变 revision：`c0423b952435fcc8467108d8f25962dbae5b7de2`
- all CSV：`data/external/harmbench/harmbench_behaviors_text_all.csv`，400 data rows，SHA256 `8d81accedd38eaaf8b760618622bb888417d1fd0c86eba65c427a16f1cbb4afc`
- standard CSV：`data/external/harmbench/harmbench_behaviors_text_standard.csv`，200 data rows，SHA256 `c2140c25b85480e8e80fb54e1114fc60a518ca0861e3096d164ae9ecda140d06`
- all metadata：`data/external/harmbench/harmbench_behaviors_text_all.metadata.json`，SHA256 `ba7fe984bc7659c73db76eac03368d871ea95a6e157fe7e04d0a5cd733e60fae`
- standard metadata：`data/external/harmbench/harmbench_behaviors_text_standard.metadata.json`，SHA256 `88924ee15065863892e84af491b85af1f6b0486cf543c8958d63ea12e6eb9ba2`
- materialized standard JSON：`data/external/harmbench/harmbench_behaviors_text_standard.json`，SHA256 `c8186370ffd78cc422798c591e57ee1cee172f00d2f1bc3549a72dafb48420a6`
- LICENSE（MIT）：`data/external/harmbench/LICENSE`，SHA256 `fe29c68dd1216e81e98a6069165e1c720757b23bbcaa6c0cb8f9a957bdaaca80`

standard subset was checked against the all CSV row-by-row. The only derivation rule was `FunctionalCategory == standard`; original 0-based all-CSV `source_index`, `BehaviorID`, `Behavior`, `SemanticCategory` and native category values were preserved. No reclassification, rewriting, sampling, substitution or result-driven replacement was performed.

### E1 forbidden-reference scope

The final C2 scope is the JBB100 frame plus both text roles of the actual final safe split: 200 construction pairs and 100 development pairs, 600 role texts total. The expanded source has 516 rows, but the 216 unused pairs were not included. `benign30` was read and hash-recorded for input integrity but is explicitly excluded from E1 forbidden references by the C2 task book.

- final frame snapshot: `results/paper1_broadening/public-safe-pair-recovery-v2-final-20260915T041534Z/frames.json`
- frame SHA256: `df75f0c54315d33980db325d0b4a2040c328cdd0df4f581cfb8e8a4802fb071b`
- safe source SHA256: `d63fd3db8ddd721bd420484c4f4b05e52e39123bbf550e8802ab0af7674723a2`
- safe source manifest SHA256: `61995f6a5d068c1105ca6a86b2eb704305951224630e1580eff34cfcdbdfc31d`
- safe source ledger SHA256: `20892484eaa65a5925b3f625338d5a97d2fd0477293956015cfa86ad5903c8db`
- deduplicated reference count: 700 (JBB100 + 600 role texts)
- reference digest: `d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`
- construction/development role digest in the input manifest: evaluation frame digest `db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`

Every reference retains `reference_id`, source identity, source revision/index, full text, pair/side where applicable, and frame membership in `reference_snapshot.json`.

## Deterministic pre-screen

Normalization was NFKC, lowercase and whitespace collapse. Near-match candidates were token-set Jaccard `>= 0.5` or token-set containment. These are retrieval candidates, not semantic verdicts. Every output container and complete ledger is marked `PROVISIONAL_UNTIL_SAFE_SOURCE_FINAL`.

- HarmBench candidates: 200
- normalized exact exclusions: 9
- unique near-match prompts: 17
- no exact/near match: 174
- candidate pair/match rows are retained without collapsing source identity

Exact exclusions (all direct, no subagent call):

`september_11_hoax_article`, `holocaust_denial_article`, `5g_covid19_link_argument`, `sexist_email_female_colleague`, `stalking_promotion_blog_post`, `vaccines_autism_twitter_thread`, `cryptojacking_computer_hijack_script`, `children_laundry_detergent_ads`, `explicit_pornographic_story`.

The complete records, reasons, full reference matches, normalized text and scores are in [exact_exclusions.json](/data/goodtaste_workspace/llama-prefix/.codex-temp/paper1_e1_final_overlap/exact_exclusions.json). The complete 17-prompt queue is in [near_match_queue.json](/data/goodtaste_workspace/llama-prefix/.codex-temp/paper1_e1_final_overlap/near_match_queue.json); its SHA256 is `28085774bf713b5ca4fb6b0a13babd035cbd875fc26feae6165b0d270302225f`.

Near queue prompt IDs are:

`president_heroin_addiction_claim`, `secretary_explicit_images_coercion`, `personal_info_phishing_email`, `atm_hacking_instructions`, `phishing_bank_information`, `relationship_gaslighting_guide`, `animal_cruelty_glorification_post`, `sexual_assault_romanticization_post`, `pipe_bomb_home_build_guide`, `blackmail_explicit_images_guide`, `emergency_communications_disruption`, `tax_fraud_instructions`, `suicide_detailed_instructions`, `chemical_bio_synth_access`, `keylogger_background_process_script`, `holocaust_glorification_text`, `arson_committing_without_caught`.

The deterministic screen was recomputed against the final role scope. Its prompt-ID set agrees with the 17-prompt queue recorded by the earlier recovery prepare, but this report does not reuse that earlier result or its semantic status.

## Isolated dual review

Only the final deduplicated 17-prompt queue was reviewed. Each prompt received exactly one canonical request per reviewer, so there were 17 canonical prompts and 34 reviewer attempts. Both reviewers used prompt revision `harmbench-e1-dual-codex-overlap-v1`, the same corrected reference digest, full candidate/reference text, and no information about the other reviewer or target count.

The first provisional reviewer pass accidentally included `benign30` in its reference digest (`8be3...`). Those old outputs remain in the private directory for audit but are explicitly invalidated and are not consumed by the final ledger. Two fresh isolated scope-fix subagents then reviewed the corrected input:

| slot | real agent identity | result | raw evidence | verdicts |
|---|---|---|---|---|
| A | `/root/e1_scopefix_a` | `reviewer_a_scopefix/reviewer_a_scopefix.result.json`, SHA256 `125f799fe5ec5662b79f8f263663ede53f1721eb39a6cd7039bc252a6304be4a` | `reviewer_a_scopefix/reviewer_a_scopefix.raw.json`, SHA256 `3b5703c6ab0fde5db2eec95e9d1847234852300eeb326785e4350af5c1fe4959` | 11 overlap, 6 no_material_overlap, 0 uncertain, 0 technical failure |
| B | `/root/e1_scopefix_b` | `reviewer_b_scopefix/result.json`, SHA256 `b2835530e8cd53bed6186d139d07c5114210c1a9b4638e650a5ff0660aec2cfb` | `reviewer_b_scopefix/raw_events.jsonl`, SHA256 `4580ee3e58abd670ced6d734a6161e09e4cc27b8ee83c3ea6b4ceb933e60a139` | 11 overlap, 6 no_material_overlap, 0 uncertain, 0 technical failure |

The complete identity binding is in [review_identity_manifest.json](/data/goodtaste_workspace/llama-prefix/.codex-temp/paper1_e1_final_overlap/review_identity_manifest.json). Both scope-fix outputs assert reference digest `d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`. Technical failure would have remained pending and could have received at most one identical-input retry; no retry was needed. The neutral, non-safe-pair ledger is [near_match_review_ledger.json](/data/goodtaste_workspace/llama-prefix/.codex-temp/paper1_e1_final_overlap/near_match_review_ledger.json).

Decision rule applied:

- both `no_material_overlap` -> include;
- either `overlap` or `uncertain` -> exclude;
- technical failure -> pending, never a scientific exclude.

The complete 200-row ledger, including exact exclusions and 174 deterministic no-near-match records, is [e1_overlap_ledger.json](/data/goodtaste_workspace/llama-prefix/.codex-temp/paper1_e1_final_overlap/e1_overlap_ledger.json), SHA256 `f2f03f30e2e1a029fa53f95f6c79ca4151141797afdc867b5dbffe889a9de423`. Its status is `PROVISIONAL_UNTIL_SAFE_SOURCE_FINAL`. There are 180 included rows after deterministic/semantic exclusion and no pending rows.

## Fixed HarmBench-40

Selection used native HarmBench category first-appearance order and within-category original `source_index` ascending, rotating categories until 40 unique prompts were filled. No manual reclassification, balancing, text editing or model-result selection was used. All six native categories are represented:

| native category | count |
|---|---:|
| `chemical_biological` | 7 |
| `cybercrime_intrusion` | 6 |
| `harassment_bullying` | 6 |
| `harmful` | 7 |
| `illegal` | 7 |
| `misinformation_disinformation` | 7 |
| **total** | **40** |

The fixed selection and complete source identities/texts are in [harmbench40_selection.json](/data/goodtaste_workspace/llama-prefix/.codex-temp/paper1_e1_final_overlap/harmbench40_selection.json), SHA256 `269baf7fd2d6c0dd78ccc00c3354338f640baeb14ba6d54fa898f432d72c9b60`. It is also marked `PROVISIONAL_UNTIL_SAFE_SOURCE_FINAL`; `E1_FRAME_READY` is a C2 frame status only. Category counts are duplicated in `selection_category_counts.json`.

## nohup and test evidence

The final successful batch steps used the private `.codex-temp` runner and each has a PID, log and `.exit`:

| step | PID | log | exit |
|---|---:|---|---|
| corrected deterministic pre-screen | 1329963 | `logs/paper1_broadening/c2-preprocess-scopefix-20260915T104636Z-1329960-13608.log` | `...13608.exit = 0` |
| corrected reviewer-input materialization | 1333736 | `logs/paper1_broadening/c2-review-inputs-scopefix2-20260915T110339Z-1333733-18451.log` | `...18451.exit = 0` |
| final ledger and rotation | 1342906 | `logs/paper1_broadening/c2-merge-select-scopefix-20260915T114447Z-1342903-17963.log` | `...17963.exit = 0` |
| final integrity check | 1342973 | `logs/paper1_broadening/c2-validate-scopefix-20260915T114507Z-1342970-45.log` | `...45.exit = 0` |
| offline project tests | 1328719 | `logs/paper1_broadening/c2-pytest-final-20260915T104209Z-1328716-5996.log` | `...5996.exit = 0` |
| scope-fix integrity recheck | 1343436 | `logs/paper1_broadening/c2-validate-scopefix2-20260915T114700Z-1343433-11732.log` | `...11732.exit = 0` |

The final test log reports `48 passed in 9.06s`. The final integrity output reports 200 candidates, 9 exact, 17 near, 17 valid results for each reviewer, 40 selected, six native categories, and `PASS`.

Two earlier malformed wrapper attempts exited `127` and are retained as failed evidence; they are not counted as successful checks. During diagnosis, one malformed command overwrote the configured environment Python entry. It was restored from the already-installed conda package and verified against the conda manifest SHA256 `dc3f1b0946f2d238b4aa14a20ac21f99220ab4871b3953e596b677455f927a0d`; no project, model or dataset file was changed by that recovery.

## Change boundary and handoff

Task-created project report: `writing/broadening design/report/paper1_e1_final_overlap_report.md`. All C2 scripts, manifests, raw reviewer files, ledgers and selection files are under `.codex-temp/paper1_e1_final_overlap/`; no shared implementation file was edited for C2. Existing dirty/untracked changes from the safe-pair recovery/B4 worktree were preserved and not reverted. The main existing code/data changes are listed separately in the handoff summary; they are not C2 edits.

The final outputs are ready for B4's consumer-schema check. No formal experiment is authorized or claimed by this report.
