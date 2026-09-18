# Safe-pair 恢复后的当前任务入口

> **状态更新（2026-09-18）**：4096 compatibility probe 已在第 2 条固定输入失败：输出耗尽 4096 token、重复拒答约 470 次且没有 Qwen3 semantic `</think>`。该结果标记为 `JUDGE_PROTOCOL_PROBE_FAIL`、`DESIGN_CHANGE_REQUIRED`。不再自动提高到 8192+；当前下一入口改为 direct-JSON Judge protocol v3 的离线实现适配。旧 v2 probe、F2、recovery 和原设计仍只读。

更新：2026-09-16，依据 C3、B5、F、F2、B6、F3 与 E2 完成报告。本索引替代此前顺序；旧A/B/A2/A3/B2/B3/E/E4/C2/B4/C3/B5/F 任务均不重新执行。

## 当前决定

服务器报告safe-pair gate通过：516 source − 7 exact = 509 preliminary；旧221 + 新79 = 300 executable；5×40 construction + 100 development = 300，unused=0。无需新增来源或再次审核旧/新safe pairs。`READY_FOR_CONSTRUCTION` 是数据gate；其后已用于 Core direction/calibration 构造和 Core dose screen，后者已完成但被 Judge 解析失败门槛阻断。

C3 已将 E1 final 派生物绑定到 `d148de7d6e89d1a5cdeac392ef94a3d281b54abcffbf7dd4d6bd4cf5229d732a`：200 candidates、9 exact exclusions、17 near-match rows、180 include、40 fixed selections 和 6 native categories，状态为 `E1_CONSUMER_PASS` / `E1_FRAME_READY`。B5 以纯 CPU consumer 检查确认 `E1_CONSUMER_PASS` / `READY_FOR_RUN`；其 run-specific config 是 `configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final_d148.json`，canonical config 未改。

F 已完成 `prepare -> build-directions`，状态为 `CORE_DIRECTIONS_READY`。Qwen layer 9 和 Llama layer 11 均有 8 Rogue + 5 contrastive 方向，分别记录 `mu_content=56.86973966266515`（1172 tokens）和 `7.615247755784255`（1170 tokens）。F2 已完成 Core screen 的 1,200 generation 与 Judge，但 13 条解析失败使 contrastive 缺失超过 2%，状态为 `CORE_DOSE_SCREEN_BLOCKED`，尚无合法的 contrastive A/S。E2/E3 自动方向资产状态已记录；Gemma release 未序列化仍是明确的记录缺口，不构成 E2 实验通过。正式 evaluation、E1/E2/E3 generation、analysis、human audit 和 archive 均未开始。

## 当前任务顺序

| 会话 | 任务书 | 已同步结果 / 当前停止点 |
|---|---|---|
| 原C会话，续作C3 | [最终 E1 派生物收尾](paper1_server_codex_c3_e1_consumer_finalize_prompt_nohup.md) | 已完成；final derived files 独立保存，旧 C2 provisional 文件未改，`E1_CONSUMER_PASS` |
| 原B会话，续作B5 | [E1 消费复核与运行入口交接](paper1_server_codex_b5_e1_consumer_handoff_prompt_nohup.md) | 已完成；CPU consumer 为 `READY_FOR_RUN`，新增仅 run-specific E1 config，未加载模型 |
| F会话 | [Core 方向构造与 calibration](paper1_server_codex_core_directions_calibration_prompt_nohup.md) | 已完成；单卡顺序完成 `prepare + build-directions`，`CORE_DIRECTIONS_READY`，未 screen 或 generation |
| 原F会话，续作F2 | [Core development dose screen](paper1_server_codex_core_dose_screen_prompt_nohup.md) | 已完成 1,200 generation/1,200 Judge；13 条 parse failure 使 contrastive 缺失超 2%，状态 `CORE_DOSE_SCREEN_BLOCKED` |
| 原B会话，续作B6 | [Core静态证据交接](paper1_server_codex_b6_static_evidence_handoff_prompt_nohup.md) | 已完成；`B6_STATIC_HANDOFF_PASS`，69 文件 bundle；动态 screen 原件由 F2 另行交付 |
| 新F3会话 | [Core screen parse failure forensic](paper1_server_codex_f3_screen_parse_failure_forensic_prompt_nohup.md) | 只读取证 13 条失败；不新增 Judge 调用，不修改 F2 结果 |
| 新E2会话 | [Gemma release gap audit](paper1_server_codex_e2_gemma_release_gap_audit_prompt_nohup.md) | 只读确认 release 缺口和最小修复建议；不运行 E2、不占 GPU |
| 新F4会话 | [Judge observability patch](paper1_server_codex_f4_judge_observability_patch_prompt_nohup.md) | 最小修复失败路径原文/diagnostics 留存；只跑离线测试，不重跑 F2 |
| 新E2R会话 | [Gemma release serialization patch](paper1_server_codex_e2r_gemma_release_serialization_patch_prompt_nohup.md) | 最小修复 Gemma release 写回；只跑离线测试，不重建 F run |
| 新 A-recovery 会话 | [Core recovery proposal](paper1_server_codex_core_recovery_proposal_prompt_nohup.md) | 已完成；冻结了 13 条旧 generation 输入和批准记录，未发送 Judge 请求 |
| A-recovery-run 会话 | [Core recovery execution](paper1_server_codex_core_recovery_execution_prompt_nohup.md) | 已完成 13/13 four-class 请求；全部 `PARSE_FAILURE`，2% gate 仍阻断，旧 F2 未改写 |
| 新 A-closure 会话 | [Core recovery failure closure](paper1_server_codex_core_recovery_failure_closure_prompt_nohup.md) | 已完成；`CORE_RECOVERY_FAILURE_CLOSURE_PASS`，仅取证闭合，旧 F2/recovery 不变 |
| 新 A-judge-v3 会话 | [Core Judge protocol v3 direct JSON](paper1_server_codex_core_judge_protocol_v3_direct_json_prompt_nohup.md) | 当前下一入口；先做 direct-JSON 离线适配并停在 `READY_FOR_DIRECT_JSON_PROBE_APPROVAL`；probe、recovery 与全量重评分分别等待批准 |
| 原E、A、D | 暂不运行新实验 | Core Judge v3 链条完成并取得对应 gate 后，才安排 Core formal evaluation、E1、E2、E3 |

三项已完成任务不重跑。后续任务如消费 E1，只能读取已固定的 final E1 输入和 Core direction assets，不能回写 C2 provisional、C3 final 或 canonical scientific config。

## 本轮同步要求

服务器完成 F2/B6 后，除各自报告外必须同步可复核的小型原件。F2 至少包括：F run 的 `run_header.json`、`resolved_config.json`、`frames.json`、`directions.json`、Core screen 的 schedule、generation attempts/ledger、four-class Judge records、`dose_decisions.json`、process/release/runtime 状态文件，以及外层和子进程的 PID、日志、`.exit` 和最终 hash 清单。B6 同步其报告中实际列出的 config、frames、direction metadata/tensor、C3 final E1 派生物和 source snapshot/hash 清单；不要同步模型权重、完整 reviewer raw 或正在写入的 ledger。若 F2 因 snapshot mismatch 或运行错误阻断，仍需同步失败报告、检查结果和未完成文件清单，不得用报告摘要替代缺失原件。

F2/B6 的服务器实现代码、配置、frames、directions、safe-pair/E1 派生物和运行原件均以服务器实际 hash 为准。本机报告或旧 evidence/code 副本不能替代这些文件；如果服务器当前代码与 F run snapshot 不一致，必须保留 `SOURCE_SNAPSHOT_MISMATCH`，暂停 screen，不覆盖 snapshot 或修改原科学设计。

## 输入和并行归属

- 固定safe-pair输入：`data/safe_pairs_public_semantic_v2_expanded.json`、同前缀 `_ledger.json`/`.manifest.json`；config=`configs/paper1_broadening/mbd_nm_v212_public_expanded.json`。
- 数据型prepare：`results/paper1_broadening/public-safe-pair-recovery-v2-final-20260915T041534Z/`。保持其source、ledger、300个分配ID和原run不变；E1补全不回头改safe split。
- C3 final 输出为 `.codex-temp/paper1_e1_consumer_final/`；旧 provisional 文件保留，且不对 safe-pair 或 E1 near queue 重发 reviewer。
- B5 的 E1 路径绑定使用 `configs/paper1_broadening/mbd_nm_v212_public_expanded_e1_final_d148.json`。F 实际使用的 `mbd_nm_v212_public_expanded_e1_final.json` 与其 SHA256 相同（`606721864c4870543c63964fedd4d5a7f4001d54809cb38875ea460152d8e98a`），两者相对 canonical config 仅改变最终 E1 decision path。
- F 的已完成 run 为 `results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`。F2 是该 run 的唯一写入者；B6 只读并将传输副本写入自己的交付目录。其他会话不得并行改写此 run 或上述 final 派生目录。

## 原实验设计保护

以下文件和已批准的科学revision默认只读：

- `writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md`
- `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.1_readable.md`
- `writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md`
- `writing/broadening design/review/paper1_public_safe_pair_source_expansion_revision.md`（服务器已有的v2.1.2来源修订）

v2.1.2是此前已授权的一次来源追加，并不允许继续更换来源或科学规则。模型/层/hook/模板/decoder/rho/seed、分割和判定标准、预算/endpoint不得为了让代码通过而修改。必要科学变更只另写proposal、标 `DESIGN_CHANGE_REQUIRED`，相关步骤停止；不自动改正文或把未批准proposal作为新run依据。普通状态、执行报告和独立实现修复记录不属于科学设计变更，可以按本任务保存。

执行前记录这些文件相对当前HEAD的已有diff/未跟踪状态，执行后只比较本任务新增变化。发现既有差异先保存说明，不reset他人修改；报告列实际修改文件，区分授权来源addendum与原设计正文。本机尚未见服务器diff，不能仅凭报告替服务器保证完全无改动。

## Linux/nohup与单卡

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export NX_DAEMON=false
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export PYTHONUNBUFFERED=1
export PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export MBD_GPU=0
export CUDA_VISIBLE_DEVICES=0
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1

launch_nohup() {
  local step="$1"; shift
  local tag="${step}-$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM}"
  local log="$PWD/logs/paper1_broadening/$tag.log"
  local status="$PWD/logs/paper1_broadening/$tag.exit"
  nohup bash -c 'status_file="$1"; shift; rc=0; "$@" || rc=$?; printf "%s\n" "$rc" > "$status_file"; exit "$rc"' \
    mbd-job "$status" "$@" > "$log" 2>&1 < /dev/null &
  local pid=$!
  printf '%s\n' "$pid" > "$PWD/logs/paper1_broadening/$tag.pid"
  printf 'pid=%s log=%s exit_file=%s\n' "$pid" "$log" "$status"
}
```

批量检查、测试及实际runner/smoke通过nohup保存PID/log/exit。同一会话一次一个后台步骤，核对进程结束、退出码和业务JSON再继续；退出0不等于业务PASS。原生subagent调用保存实际事件，无需伪造nohup外壳。历史freeze/review缺exit如实标记，已有完整raw/产物可用于证明结果，不重发已完成请求、不事后编造exit。

F 已在 GPU0 完成方向构造并记录顺序释放。后续获授权的 GPU 任务仍须启动前确认空闲/足够显存，不终止其他用户进程，不切双卡、不在线下载、不升级现有模型环境；被测模型和 Judge 必须顺序加载并释放。小型检查无需下载模型、重 hash 所有权重或重新建立环境。

## 输出与下一阶段

C3报告：`writing/broadening design/report/paper1_e1_consumer_finalization_report.md`（报告 SHA256：`4e92522754280bba9f8512abe2368255ffab2ae9aafb717f0ec2d09925c71a95`；`tests/paper1_broadening` 为 50 passed）。任务期间发生过一次外部 `git pull --ff` 到 `107a2412`，该同步与 C3 自身工作明确区分；C3 未 commit/push。
B5报告：`writing/broadening design/report/paper1_e1_consumer_handoff_report.md`（CPU PID `1386866`、exit `0`；syntax/JSON PID `1388726`、exit `0`）。
F报告：`writing/broadening design/report/paper1_core_direction_calibration_report.md`（prepare PID `1382607`、build-directions PID `1383422`，均 exit `0`；`git diff --check` 与 47 项源码快照核验通过）。

三份报告均已完成各自边界自审，且没有 commit/push。本轮交付 F2/B6 任务，不改写 C2 provisional、canonical config、safe-pair 数据、科学设计或既有历史 run report。F2 锁定 A/S 后才可安排正式 evaluation。

## 剩余实验任务

下表是既定设计的待办清单，不是自动启动后续阶段的指令。generation 规模不含另行记账的 Judge、技术重试和既有 smoke。

| 模块 | 剩余规模 | 当前依赖与执行安排 |
|---|---:|---|
| Core recovery failure closure | 已完成；0 新请求 | `CORE_RECOVERY_FAILURE_CLOSURE_PASS`；确认 13 条输出边界失败，旧 F2/recovery 只读 |
| Judge protocol v2 compatibility probe | 已完成；2/6 请求后失败 | 第 2 条在 4096 token 达到上限且无 semantic `</think>`；标记 `JUDGE_PROTOCOL_PROBE_FAIL`，不再追加 v2 请求 |
| Judge protocol v3 direct-JSON offline adaptation | 0 新请求（当前入口） | `A-judge-v3` 参数化 `enable_thinking=false` 与 strict direct JSON；旧默认保持 true/1296；完成后等待 direct-JSON probe 批准 |
| Judge protocol v3 direct-JSON compatibility probe | 6 Judge 请求（需新批准） | 复用同一 6 条固定输入；1296 token、无 thinking、零 retry；失败即停，不提高到 1296 以上或切回 thinking |
| Core Judge v3 independent recovery | 最多 13 Judge 请求（需批准） | 只处理旧 F2 的 13 条失败输入；通过后仍不与旧 1,187 条混合；失败则保持 blocked |
| Core screen v3 full rescore | 1,200 logical Judge（需 recovery 通过及再次批准） | 使用统一 direct-JSON 协议重评分全部旧 generation completion；通过 2% gate 后才产生新的 A/S |
| Core harmful / benign evaluation | 10,600 + 840 generation | F2 技术 gate 通过并保存四组 A/S 后安排；保留负结果状态 |
| E1 外部集 | 2,320 generation | final frame 已就绪；引用 Core A/S，无独立 screen |
| E2 第三模型 | 600 screen + 1,160 evaluation | 方向已有；运行前处理 Gemma release 记录缺口并验证该模型的运行边界 |
| E3 两个额外层 | 1,200 screen + 2,560 evaluation | 方向/各层 mu 已有；仍需各层运行检查和独立 screen；按 E1 -> E2 -> E3 优先级串行使用单卡 |
| Judge、分析与人工验证 | Core 200 + E1/E2/E3 各 40 条人工样本 | 自动 Judge 与分析随对应输出完成后进行；必须有真实人工标签才称人工验证完成 |
| 最终归档 | 已关闭的源码/配置/结果/日志 | 汇总状态、生成最终文件 hash；缺失项保留 pending，不伪造 FINAL |

F3/E2 已完成，F4/E2R 实现修复和离线测试也已完成，A-recovery proposal、批准的 recovery run 和 A-closure 均已结束；v2 的 4096 probe 在重复 thinking 输出上失败。下一步只执行 A-judge-v3 任务书的离线适配；direct-JSON probe 通过后再创建 v2.3 设计，之后的 13 条 recovery 和 1,200 条一致协议重评分必须分别获得批准。F2、旧 recovery、B6、C3、v2 probe 不重跑或回写，不启动正式 evaluation；不得追加旧 run Judge 调用或突破批准预算。
