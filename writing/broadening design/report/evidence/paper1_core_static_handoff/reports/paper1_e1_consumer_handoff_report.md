# Paper 1 B5 E1 Consumer Handoff Report

任务书：`paper1_server_codex_b5_e1_consumer_handoff_prompt_nohup.md`
任务版本：`e1-consumer-handoff-v1`
日期：2026-09-15（Asia/Shanghai）
工作目录：`/data/goodtaste_workspace/llama-prefix`
分支：`stage3/impl-candidate`

## 结论

`E1_CONSUMER_PASS`
`READY_FOR_RUN`

状态矩阵：`E1_CONSUMER_PASS` = achieved；`E1_CONSUMER_PENDING` = no；
`E1_CONSUMER_BLOCKED` = no。

当前 E1 consumer 使用 C3 final 派生物和 run-specific config 通过纯 CPU
`build_frames` 消费检查。该状态只表示 E1 HarmBench-40 overlap frame 已满足
运行入口契约，不表示模型运行、方向构造、generation、Judge、analysis 或正式
实验 gate 通过。

`FORMAL_EXPERIMENTS_NOT_RUN`

## C3 final 输入

C3 final 报告：
`writing/broadening design/report/paper1_e1_consumer_finalization_report.md`
SHA256：`4e92522754280bba9f8512abe2368255ffab2ae9aafb717f0ec2d09925c71a95`

final 派生目录：`.codex-temp/paper1_e1_consumer_final/`
finalization manifest：`7356a24e00733b19e80d6cd6baff22eca18bfd1d0910fa9aad7b1ee592adc4c2`

所有 final 文件均绑定：

- reference digest：`d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`
- review revision：`harmbench-e1-dual-codex-overlap-v1`
- forbidden references：700（JBB100 + 600 safe-pair role text；不含 benign30）

主要 final 文件哈希：

| 文件 | SHA256 |
|---|---|
| `reference_snapshot.json` | `41eb9125644d8e8c9d50191ec8970902cf57fd250fd489466aeab7b6b6982311` |
| `c3_source_binding.json` | `25462901b9914d34abb16fb7edef0328bc0aca556b70b216ad3c0ab42c5a3110` |
| `review_identity_manifest.json` | `cfb7047fc7374b547503de3b5de81aefdd34d28f6ee7b71dae92391498332de2` |
| `near_match_review_ledger.json` | `51983340a7790fa1aff504b860df83797153d6ecffad7e35421e801ffc5eee3d` |
| `e1_overlap_ledger.json` | `575e3175a9c5fba8a9e2183673351cf06fe8794b0af2696a3c5fb7a483a42d24` |
| `e1_overlap_decisions.json` | `03a1a89a9f50d14c6fc8824bf463e040af2141fd6d77e76e10ba00d26d10e4ab` |
| `harmbench40_selection.json` | `d9c2450ae65615e4d0e10f2601fa8f4c21a098561b2c1b5541ea808428ba636f` |

C3 final report states that the old C2 provisional artifacts remain preserved and
unconsumed. B5 did not re-review prompts or change any C3 final artifact.

## Config binding

Canonical expanded config (unchanged):

- path: `configs/paper1_broadening/mbd_nm_v212_public_expanded.json`
- SHA256: `d15edaeeed1b9f19203ed8271606e4ac09c174c1206ac89955badeca1e8fe720`
- `data.e1_overlap_decisions_path`: `null`

B5 run-specific config:

- path: `configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final_d148.json`
- SHA256: `606721864c4870543c63964fedd4d5a7f4001d54809cb38875ea460152d8e98a`
- `data.e1_overlap_decisions_path`:
  `.codex-temp/paper1_e1_consumer_final/e1_overlap_decisions.json`

A recursive JSON comparison found exactly one difference from canonical config:
the E1 final decision path above. Model paths, layers, hook, template, decoder,
rho grid, seed, split, budgets, endpoint, and all other data bindings are unchanged.
An identically hashed `mbd_nm_v212_public_expanded_e1_final.json` was also present
in the worktree; it was not overwritten or used as the B5 evidence path.

## CPU consumer result

The B5 validator loaded the run-specific config and called the current
`paper1_broadening.frames.build_frames` path without importing or loading a model.
The business result was:

| check | result |
|---|---:|
| reference digest | `d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a` |
| review revision | `harmbench-e1-dual-codex-overlap-v1` |
| candidate rows | 200 |
| exact exclusions | 9 |
| near-match ledger rows | 17 |
| semantic exclusions | 11 |
| remaining near queue | 0 |
| selected rows | 40 |
| native categories | 6 |
| consumer status | `READY_FOR_RUN` |
| result | `E1_CONSUMER_PASS` |

The 40 selected prompt IDs and order exactly match C3
`harmbench40_selection.json`. The six native categories are
`chemical_biological`, `cybercrime_intrusion`, `harassment_bullying`, `harmful`,
`illegal`, and `misinformation_disinformation`.

## Verification evidence

The successful B5 CPU check ran through `nohup` while retaining the shell until
completion:

| step | PID | log | exit |
|---|---:|---|---|
| B5 final CPU consumer | `1386866` | `logs/paper1_broadening/b5-e1-consumer-cpu-nohup-proof2-20260915T142718Z-1386863.log` | `...1386863.exit = 0` |

Offline syntax/config check: PID `1388726`, log
`logs/paper1_broadening/b5-e1-offline-syntax-20260915T143522Z-1388723.log`,
exit `...1388723.exit = 0` (`bash_n=0 py_compile=0 json=0`).

The log contains the complete JSON result above. The C3 report's existing test
evidence was reused (`50 passed in 17.95s`, C3 consumer validator exit 0); no
shared implementation code changed during B5, so no duplicate full-suite run was
needed. The final check also performed JSON config parity, final artifact hash
verification, protected-file hash verification, and `git diff --check`.

Two early B5 launcher attempts produced only a PID and empty log without an
`.exit`; they are retained as failed wrapper evidence and are not counted. The
successful evidence is the PID/log/exit row above.

## Actual B5 files

Files added for this handoff:

- `configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final_d148.json`
- `.codex-temp/paper1_b5_e1_consumer_check.py`
- `.codex-temp/paper1_b5_e1_consumer_runner.sh`
- this report

The C3 final directory and C3 report were consumed as inputs; C2 provisional
files, safe-pair source/ledger, JBB, benign frame, raw reviewer evidence, old
runs, and canonical scientific config were not modified. No commit or push was
performed.

## Design protection and boundary self-audit

The following protected hashes were unchanged during B5:

- original design: `efaf55d7df2265bb68bca702c385e4ba1b9584415bb37a234dd16e0c1ffb51ad`
- readable design: `398eda7172eab16cfd4fe899292f87079d474c5262c7dd7361892c70785d23d0`
- implementation specification: `9cae99db1ff9ec91dc4222672f8bf643d35139f5d1b9af9d1606a26a003da2ee`
- approved source revision: `615dba787f402e77d35fd25d2207131eccd648eff9d18e416e2f7e5bde2b401c`
- expanded safe-pair source: `d63fd3db8ddd721bd420484c4f4b05e52e39123bbf550e8802ab0af7674723a2`
- expanded safe-pair ledger: `20892484eaa65a5925b3f625338d5a97d2fd0477293956015cfa86ad5903c8db`

No scientific field changed and no `DESIGN_CHANGE_REQUIRED` condition was
triggered. No model, prepare, build-directions, screen, generation, Judge, or
analysis process was run by B5. E1 is ready for a later authorized run-specific
entry point only; this is not an E1 experiment result or formal gate.

`FORMAL_EXPERIMENTS_NOT_RUN`
