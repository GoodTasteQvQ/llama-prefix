# Paper 1 B6 Core Static Evidence Handoff

任务书：`paper1_server_codex_b6_static_evidence_handoff_prompt_nohup.md`  
任务版本：`core-static-evidence-handoff-v1`  
日期：2026-09-16（Asia/Shanghai）  
工作目录：`/data/goodtaste_workspace/llama-prefix`  
分支：`stage3/impl-candidate`

## 结论

`B6_STATIC_HANDOFF_PASS`

Core 方向构造静态证据、F run source snapshot、C3 final E1 资产和 B5
run-specific config 已完成只读核对并复制到：

`writing/broadening design/report/evidence/paper1_core_static_handoff/`

当前可交接状态：

- Core data gate：`READY_FOR_CONSTRUCTION`
- F direction/calibration gate：`CORE_DIRECTIONS_READY`
- E1 consumer gate：`READY_FOR_RUN`（C3/B5 final，40 条，6 个原生类别）
- F2 Core screen：`CORE_SCREEN_NOT_SYNCED`；本任务不等待、不启动、不判断其 screen gate
- Gemma release serialization gap：保持原样，未修复
- Formal evaluation：未运行

`FORMAL_EVALUATION_NOT_RUN`

本轮没有使用 GPU、加载模型、运行 prepare、screen、generation、Judge、analysis
或修改 F run、C3/C2 产物。没有 commit、push、pull。

## F run 与启动前 header

F run：
`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`  
run ID：`paper1-20260915T140735Z-99331d4603`

启动前 header 副本：
`run_header_before_core_screen.json`  
SHA256：`c32e12ba3db49974f3a784c6acd505bf0c2dd4f592491588c81b6bfe8c8e46c6`

当前 `run_header.json` 与该副本字节一致，SHA256 也是
`c32e12ba3db49974f3a784c6acd505bf0c2dd4f592491588c81b6bfe8c8e46c6`。
header 记录 `source_files` 共 47 项，`code_commit=107a2412adbb66a9997244efdbdbf4ba92253cb0`，
`dirty=true`，单卡逻辑设备 `cuda:0`。B6 没有重新使用 GPU；这些是 F 已保存的运行身份记录。

F 启动前 source snapshot 校验原件：
`source_snapshot_verification_core_screen.json`  
SHA256：`c863e2debda5d23ca6a723705731c57162b56bbaa3215c8de1d5766894088f16`

其业务结果为 `status=PASS`、`verified=true`、`source_files=47`。B6 逐项比较了当前
工作树、F `source_snapshot/` 和交付 bundle 中的 47 个文件：47/47 字节一致，没有
`SOURCE_SNAPSHOT_MISMATCH`。

47 项的完整相对路径来自 F header，并逐项保存在：

- `evidence/paper1_core_static_handoff/run/run_header_before_core_screen.json`
- `evidence/paper1_core_static_handoff/file_manifest.sha256.json`
- `evidence/paper1_core_static_handoff/source_snapshot/`

路径覆盖 `activation_guard/`、4 个配置/adapter/恢复脚本、HarmBench 与语义来源许可、
`data/safe_pairs_public_semantic_v1.json`、expanded source/ledger/manifest、全部
`paper1_broadening/` 运行源码、单卡 wrapper、Judge adapter 和 A2 rebuilt ledger。

## Core 静态原件

以下文件均从 F run 原路径只读复制，bundle hash 与 F 原件相同：

| 原件 | bundle 相对路径 | SHA256 |
|---|---|---|
| resolved config | `run/resolved_config.json` | `e857f02d60d5db00fdc3747b284f9cfcb4fc68c3bc388f54bf7ada728eb2ae42` |
| frames | `run/frames.json` | `a69a39c1f63f0fc1a9d32876e7e6663ef5bea89233917cf86972e598e0b730ef` |
| directions metadata | `run/directions.json` | `3ca9bb9eed166eefddb62552e603dcf183708e37f6f892923782ec6d46d962eb` |
| Qwen Core tensor | `run/directions_qwen25.pt` | `733d2ebf76d1097184769746f36cd2df072615366cee2aaa6341f2764eca8c49` |
| Llama Core tensor | `run/directions_llama31.pt` | `5bfb6b88592d135baac9c9eb272949dba9a2670b514e9672c39d4bb6b7cd6560` |
| F header backup | `run/run_header_before_core_screen.json` | `c32e12ba3db49974f3a784c6acd505bf0c2dd4f592491588c81b6bfe8c8e46c6` |
| current header | `run/run_header.json` | `c32e12ba3db49974f3a784c6acd505bf0c2dd4f592491588c81b6bfe8c8e46c6` |
| snapshot verification | `run/source_snapshot_verification_core_screen.json` | `c863e2debda5d23ca6a723705731c57162b56bbaa3215c8de1d5766894088f16` |

F frames 内容：source=516，`actual_k=40`，5 个 construction folds 各 40，development=100，
unused=0，safe-pair gate=`READY_FOR_CONSTRUCTION`，evaluation digest=
`db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`。

Core directions 内容：

- Qwen2.5 layer 9，8 Rogue + 5 contrastive，`mu_content=56.86973966266515`，1172 tokens；
- Llama-3.1 layer 11，8 Rogue + 5 contrastive，`mu_content=7.615247755784255`，1170 tokens；
- 两个 tensor 均 13 行，方向顺序与 F 报告一致，tensor SHA256 如上；
- F 报告中的 finite/norm、fold membership、sign diagnostics 和顺序 release 结果沿用，未重新提取 activation；
- Qwen/Llama release 记录均为已释放、hook/tokenizer/model 引用清理、非并驻模型。

F `directions.json` 还记录 E2/E3 自动资产状态。B6 没有修改或回填 Gemma release
字段；`directions_gemma2_9b_it.pt` 不属于本次 Core 两个 tensor 的交付清单，未复制。

## C3 final E1 与 B5 config

C3 final 目录原件位于 `.codex-temp/paper1_e1_consumer_final/`，bundle 中的
`c3_final/` 保留以下 8 个文件：reference snapshot、source binding、review identity
manifest、near-match ledger、final E1 ledger、consumer adapter、40 条 selection 和
finalization manifest。关键 hash：

| 文件 | SHA256 |
|---|---|
| `reference_snapshot.json` | `41eb9125644d8e8c9d50191ec8970902cf57fd250fd489466aeab7b6b6982311` |
| `e1_overlap_ledger.json` | `575e3175a9c5fba8a9e2183673351cf06fe8794b0af2696a3c5fb7a483a42d24` |
| `review_identity_manifest.json` | `cfb7047fc7374b547503de3b5de81aefdd34d28f6ee7b71dae92391498332de2` |
| `harmbench40_selection.json` | `d9c2450ae65615e4d0e10f2601fa8f4c21a098561b2c1b5541ea808428ba636f` |
| `finalization_manifest.json` | `7356a24e00733b19e80d6cd6baff22eca18bfd1d0910fa9aad7b1ee592adc4c2` |
| `e1_overlap_decisions.json` | `03a1a89a9f50d14c6fc8824bf463e040af2141fd6d77e76e10ba00d26d10e4ab` |

C3/B5 绑定结果保持：reference digest=
`d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`，review revision=
`harmbench-e1-dual-codex-overlap-v1`，200 candidates、9 exact、17 near、180 include、
40 selected、6 native categories、pending=0，consumer=`READY_FOR_RUN`。

B5 config：
`configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final_d148.json`  
bundle path：`configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final_d148.json`  
SHA256：`606721864c4870543c63964fedd4d5a7f4001d54809cb38875ea460152d8e98a`

F resolved config SHA256 为 `e857f02d60d5db00fdc3747b284f9cfcb4fc68c3bc388f54bf7ada728eb2ae42`。
递归比较显示 B5 config 与 F resolved config 的 scientific/data/model/protocol/runtime/
budget 字段完全一致；F resolved config 仅额外包含运行元数据字段 `block=prepare`、
`fixture=false`、`run_id=paper1-20260915T140735Z-99331d4603`、`run_mode=pilot`。
没有将旧 C2 provisional 文件替换进 F run。

## F2 动态未同步项

在 B6 检查时，F run 中已经出现 `screen_generation_schedule_core.jsonl`（1200 行，
仅为 schedule），但未见可交接的 attempts、generation ledger、Judge records、dose
decisions、release/status 文件或成功的 F2 `.exit`。当时没有可见的 screen worker。B6
不等待 F2、不重新提交 screen、不复制正在生成或可能不完整的动态文件，因此以下均明确
未同步：

`screen_generation_schedule_core.jsonl`、`screen_generation_attempts_core.jsonl`、
`screen_generation_ledger_core.jsonl`、`screen_judge_records_core.jsonl`、
`dose_decisions.json`、`screen_processes_core.json`、`screen_release_core.json`、
`screen_judge_runtime_status_core.json`。

这不构成 screen 通过或失败结论；Core screen 仍是 `CORE_SCREEN_NOT_SYNCED`，应由 F2
按其任务书单独交付最终动态产物和报告。

## B6 交付文件与验证

交付目录：
`writing/broadening design/report/evidence/paper1_core_static_handoff/`

内容包括：

- `run/`：F header 副本、resolved config、frames、directions metadata、Qwen/Llama tensors、snapshot verification；
- `c3_final/`：C3 final E1 派生文件；
- `configs/`：B5 final run-specific config；
- `reports/`：F、C3、B5 报告副本；
- `source_snapshot/`：F header 实际列出的全部 47 项原文件；
- `file_manifest.sha256.json`：67 个内容文件的 hash；
- `handoff_manifest.json`：69 个实际 bundle 文件、动态排除项和边界标记。

成功的 B6 批量检查均通过项目 `.codex-temp` 和 `nohup`：

| 检查 | PID | log | exit | 结果 |
|---|---:|---|---:|---|
| static materialization | `1405744` | `logs/paper1_broadening/b6-static-materialize-20260915T155951Z-1405741.log` | `0` | source snapshot 47，交付目录生成 |
| static source/config verification | `1407075` | `logs/paper1_broadening/b6-static-verify-final-20260915T160420Z-1407072.log` | `0` | `B6_STATIC_HANDOFF_PASS` |
| final bundle audit | `1407944` | `logs/paper1_broadening/b6-bundle-audit-final-20260915T160843Z-1407941.log` | `0` | 69 files、67 hashes、0 dynamic screen copied |

私有检查脚本/交付 JSON 语法检查：PID `1408844`，log
`logs/paper1_broadening/b6-static-syntax-final-20260915T161313Z-1408841.log`，exit
`...1408841.exit = 0`（`py_compile=0 bundle_json=0`）。

首次 verification 因临时验证器错误地把 B5 config 与 F resolved config 的运行元数据
差异当作 scientific mismatch 而退出 1；该错误只在 `.codex-temp/paper1_b6_static_verify.py`
中修正，F/C3/B5 原件未改，随后 final verification exit=0。一次 bundle audit 的路径
拼写错误退出 2，同样未改任何原件；最终 audit exit=0。

## 实际修改与边界自审

B6 新增或生成的文件仅为：

- 本报告；
- `evidence/paper1_core_static_handoff/` 交付副本及 manifest；
- `.codex-temp/paper1_b6_static_materialize.py`、`paper1_b6_static_verify.py`、
  `paper1_b6_bundle_audit.py` 私有只读检查脚本；
- 上述 B6 检查的 PID/log/exit 文件。

没有修改 `paper1_broadening` 共享实现、canonical config、F run、F source snapshot、
C3 final、C2 provisional、safe-pair source/ledger、原实验设计、Gemma release 记录或旧
run。B6 没有重新运行测试套件、screen、模型或 GPU 工作；F/B4/C3/B5 已有的有效测试
证据仅按任务书引用。

边界自审结果：关键文件 hash、47 项 snapshot 字节一致性、Core fold/mu/layer/tensor
身份、E1 digest/40/6 gate、B5/F 配置关系、动态 screen 未同步边界和 Gemma gap 标记均
已核对。未触发 `SOURCE_SNAPSHOT_MISMATCH` 或 `DESIGN_CHANGE_REQUIRED`。

`FORMAL_EVALUATION_NOT_RUN`
