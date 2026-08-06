# Dolly Benign Prompt Frames v1: Provenance and License Notice

Status: `design_selected`. `formal_experiment_run=false`. This is an approved design selection,
not an execution authorization or a run-readiness declaration.

## Source and attribution

- Dataset: `databricks/databricks-dolly-15k`
- Owner and attribution party: Databricks, Inc.
- Dataset title: `databricks-dolly-15k`
- Immutable revision: `bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a`
- Source file: `databricks-dolly-15k.jsonl`, config `default`, split `train`
- Source URL: `https://huggingface.co/datasets/databricks/databricks-dolly-15k/tree/bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a`
- Source file SHA-256: `2df9083338b4abd6bceb5635764dab5d833b393b55759dffb0959b6fcbf794ec`
- License: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)
- License URI: `https://creativecommons.org/licenses/by-sa/3.0/`
- Copyright notice stated by the source: Copyright (2023) Databricks, Inc.

## Modifications and data boundary

The selected data are a modified subset of the source instructions. Selection first requires an empty
normalized `context`, then excludes invalid, non-English, reserved-token, obvious unsafe lexical, and
duplicate records. Published prompts are derived only from `instruction` by Unicode NFKC, trimming,
and collapsing consecutive whitespace to one ASCII space. The files add source IDs, hashes,
instruction types, rendered-token counts, deciles, strata, and deterministic ranks. Source `response`
content is not used for eligibility, taxonomy, matching, ranking, runtime input, or published text.

To the extent that the prompt strings and other copied or adapted Dolly dataset content in
`selected_p1_benign_100.json` and `selected_benign_confirm_30.json` constitute Adapted Material, that
data content is distributed under CC BY-SA 3.0 with the attribution and modification notice above.
This ShareAlike statement is limited to the corresponding Dolly-derived data content. It does not
purport to relicense selector code, tests, configuration mechanics, independently authored metadata,
or unrelated repository content. Recipients must retain this notice when redistributing the selected
Dolly-derived data content and must comply with the CC BY-SA 3.0 terms.
