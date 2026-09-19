# Core 正式生成：资产衔接与单卡 nohup 连续任务

版本：`core-formal-generation-v1`；日期：2026-09-19。

## 任务与执行会话

本机已验收 Core full rescore、20-cell screen gate 和四组 A/S。现在授权在**一个新 run** 中完成 Core 正式 generation，共 11,440 条。先完成必要的运行目录衔接和日程核对，随后直接 nohup 启动；两步属于本任务，无需再次等待负责人签字或 approval 文件。

建议新建 **A-Core-generation** 服务器会话，必须直接拥有 `/data/goodtaste_workspace/llama-prefix` 的 shell。原 Restore 会话若具备有效 shell，也可继续执行同一任务；只能有一个实际执行者。旧协议修复/恢复会话不再运行。本轮不安排并行 GPU 或共享代码写入会话，不通过执行 subagent 转发 shell 工作。

范围到生成输出和交接为止：不再 screen、不重新选择 A/S、不调用 Judge、不运行 E1/E2/E3、分析或人工审核。正式 generation 是正式评估的一部分，完成时应写 `CORE_FORMAL_GENERATION_COMPLETE` 和 `CORE_FORMAL_JUDGING_NOT_RUN`，不能继续使用笼统的 `FORMAL_EVALUATION_NOT_RUN`，也不能声称整个正式评估已完成。

## 固定输入与科学边界

相对仓库根目录：

| 用途 | 输入 |
|---|---|
| 已验收 screen / A/S | `results/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251/` |
| 固定 frames、方向和校准 | `results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`（下称 F2） |
| 当前 config | `configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json` |
| 科学修订 | `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.3_direct_json.md`，继承 v2.1 / public-pairs expansion 已冻结内容 |
| 本机验收 | `writing/broadening design/review/paper1_core_full_rescore_result_review_20260919.md` |

F2 header 的实际 `run_id` 为 `paper1-20260915T140735Z-99331d4603`，不是目录名；来源记录同时保存二者。沿用 516 source / 509 preliminary / 300 executable / k=40、5×40 construction 和 development100，不再次 prepare、审核或切分。Core 使用 F2 JBB-100 和 benign30；本任务不消费 E1 frame，v2.3 config 的 E1 decision path 为 null 不影响此 Core 任务，不为此更改 config。

| 模型 / 方向 | 层（zero-based） | A rho | S rho | mu_content |
|---|---:|---:|---:|---:|
| Qwen / contrastive | 9 | 0.50 | 1.00 | 56.86973966266515 |
| Qwen / Rogue | 9 | 0.75 | 1.50 | 56.86973966266515 |
| Llama / contrastive | 11 | 1.00 | 1.25 | 7.615247755784255 |
| Llama / Rogue | 11 | 1.00 | 1.50 | 7.615247755784255 |

alpha 使用原文件的完整数值 `rho × mu_content`，不从本表四舍五入。每模型 8 Rogue + 5 contrastive，tensor、sign、fold、mu 和 seed 不变；不因已见 screen 结果再筛选方向。behavior 为 bf16、原生 chat template、`resid_pre`、batch=1、greedy、beam=1、use_cache=true、seed=42、max_new_tokens=512。Judge 配置保留 false/1296/strict_direct_json_v1，但本任务 Judge calls=0。

原设计（含 v2.3）、canonical/run-specific 输入 config、来源数据、旧 run、既有 source snapshot 全部只读。不因运行阻碍调整模型、数据、预算、剂量、retry 或科学规则。若确需科学变更，只报告具体问题，不自行改设计。保留工作区已有修改，禁止 reset/clean/stash 覆盖他人工作。

## 一、最小运行目录衔接

任何 Python/测试执行前，先切换到仓库根目录并创建 `.codex-temp`，设置 `TMPDIR="$PWD/.codex-temp"`、`TMP="$TMPDIR"`、`TEMP="$TMPDIR"`、`NX_DAEMON=false` 和项目内 `PYTHONPYCACHEPREFIX`；使用既有服务器 Python，不安装或升级依赖。

现有正式生成入口可用，但 rescore 的 `dose_decisions.json` 按 `groups[model|family]` 保存，而 `pipeline._dose_rhos` 读取 `decisions[model][family]`；rescore run 本身也不是完整 generation run。**不能直接把旧 run 当作正式生成目录。**

新增一个小型 CPU helper：`scripts/materialize_core_formal_run.py`。仅负责下述衔接，复用现有 API，不另造 executor 或调度框架。CLI 约定：`--source-run`、`--screen-run`、`--config`、`--run-id`、`--output-dir`。在文件顶部建立仓库根目录 import path；现有 config 校验照常执行，不绕过 public manifest/source 契约。

1. 确认 rescore 原 `artifact_hashes.sha256` 全部匹配，terminal 为 `CORE_SCREEN_V3_PASS`、20×60、0 missing，四组 `DOSE_DECIDED` 且与上表一致。保存实际读取输入的路径/hash。不要把 rescore 中 release 占位当作 release PASS。
2. 调用 `orchestration.create_run`，`block="core"`、`run_mode="formal"`、`fixture=False`，使用唯一新路径。拒绝覆盖已有非空 run；不复制旧 header 或旧 source snapshot 冒充当前实现。输入 config 的 `design_revision` 与 `design_revision_overlay` 均保留。
3. 将 F2 `frames.json`、`directions_qwen25.pt`、`directions_llama31.pt` 原字节复制到新 run，核对复制 hash。新 `directions.json` 为明确标注来源的 Core 派生视图：只保留 Qwen/Llama 两个模型条目，方向列表/索引、层、mu、sign、fold 数值不变，tensor_path 指向新复制文件；不带 Gemma/E3 的待执行状态。旧条目中的 identity/release 仅属于方向构造来源，不可写进新 run 的 `loaded_identities` 或 `behavior_release.json` 冒充本次加载/释放。
4. 新建 `dose_decisions.json`，结构含 `core.status="DOSE_DECIDED"`、`decisions[model][family]`；每组保留 rescore 的 A/S、alpha、候选结果、mu、ordering 和 `screen_run_id`。只是键结构转换，不重新调用 allocator、不重算标签、不改原 dose 文件。将源 dose 文件路径/hash 记录在新 run 的 `input_provenance.json`。
5. 保存 `input_provenance.json`：源 F2 路径及真实 run_id、screen run_id、frames/directions/tensor/dose/config/design 的文件 hash、复用/派生关系。source/design snapshot 用当前工作树实际文件，记录 dirty 状态；在新 snapshot 补入本 helper、v2.3 原 config/设计及本任务书，并更新新 header 的对应 source_files/design_files，让 provenance 覆盖本次实际衔接代码。不要修改共享 `orchestration.py` 的全局 snapshot 列表。未跟踪文件也必须按实际字节纳入，不要求先清空工作树。
6. 调用 `build_evaluation_schedule_for_run`（`include_development=False`），保存现有格式的 `generation_schedule.jsonl`。验证 `verify_run_source_snapshot`。不复制旧 generation/ledger/Judge/release，不重新构造方向，不运行模型。

只给这个 helper 做有意义的聚焦离线检查：正确来源衔接、错误 A/S/缺失资产拒绝、已有输出目录保护；可新增 `tests/paper1_broadening/test_core_formal_materialization.py`。不重复既有完整 fixture/suite、smoke、CPU 启动 probe 或 1,200 条 rescore。必要的小型 import/路径/衔接 bug 可在 live 前于 helper 内修正并复核，不另开任务等待审批；现有 shared runner 或科学契约出现问题则留证报告，不静默修改。

实际日程检查是本任务的普通启动检查，写入新 run 的 `schedule_check.json`：

| 日程块 | logical / unique generation |
|---|---:|
| harmful steered：2 models × 2 conditions × 2 doses × 100 prompts × 13 directions | 10,400 |
| harmful clean：2 × 100，只生成一份供比较复用 | 200 |
| benign steered：2 × 30 × 13，仅 decode_only / S | 780 |
| benign clean：2 × 30 | 60 |
| 合计 | **11,440** |

Qwen/Llama 各 5,720；本次 A 均不等于 S，所以 response IDs 也必须 11,440 个。JBB 10 类各10，benign30 固定；无 development/E1/E2/E3 行。逐项检查层、方向集合、条件和 A/S rho；确认 `_direction_tensor_map` 在 CPU 能读取复制后的 Core tensor，实际使用的该层 mu 与源值相同。tensor 只做已有资产完整性检查，不重测 activation。若 config/源文件或上述计数不符，停止并说明差异，不填充、不删行凑数。

## 二、一次 nohup 正式生成

先确认主会话可直接执行 shell、没有同任务 worker 正在运行，GPU 0 和磁盘有足够资源；不终止别人的进程，不在线下载或升级环境。记录当前 HEAD/dirty、解释器、实际命令和设备信息到 `.codex-temp/paper1_core_formal_generation/`。不把命令自身的 pgrep 匹配当成重复任务。

以下代码保存为该目录下的 `launch.sh`（Linux LF），`bash -n` 后由主会话直接执行。helper 与聚焦检查须先完成。materialize 通过后本脚本立即提交 generation，不停在“等待额外批准”。

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /data/goodtaste_workspace/llama-prefix
mkdir -p .codex-temp/paper1_core_formal_generation logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR" TEMP="$TMPDIR" NX_DAEMON=false
export PYTHONUNBUFFERED=1 PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 MBD_GPU=0
export MBD_MODEL_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_MODEL_PYTHON"
TAG="core-formal-generation-$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN="$PWD/results/paper1_broadening/$TAG"
LOGBASE="$PWD/logs/paper1_broadening/$TAG"
EVIDENCE="$PWD/.codex-temp/paper1_core_formal_generation"
test ! -e "$RUN"
test ! -e "$LOGBASE.log"
test ! -e "$LOGBASE.pid"
test ! -e "$LOGBASE.exit"
printf 'tag=%s\nrun=%s\nlogbase=%s\n' "$TAG" "$RUN" "$LOGBASE" > "$EVIDENCE/$TAG.paths.txt"

MATERIALIZE_RC=0
"$MBD_MODEL_PYTHON" -u scripts/materialize_core_formal_run.py \
  --source-run "$PWD/results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603" \
  --screen-run "$PWD/results/paper1_broadening/core-full-rescore-direct-20260919T094847Z-2523251" \
  --config "$PWD/configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json" \
  --run-id "$TAG" --output-dir "$RUN" \
  > "$EVIDENCE/$TAG.materialize.log" 2>&1 || MATERIALIZE_RC=$?
printf '%s\n' "$MATERIALIZE_RC" > "$EVIDENCE/$TAG.materialize.exit"
if [ "$MATERIALIZE_RC" -ne 0 ]; then exit "$MATERIALIZE_RC"; fi

nohup /bin/bash -c '
  exit_file="$1"; shift
  rc=0
  "$@" || rc=$?
  printf "%s\n" "$rc" > "$exit_file"
  exit "$rc"
' core-formal "$LOGBASE.exit" \
  /bin/bash scripts/run_paper1_broadening_single_gpu.sh \
  generate --config "$RUN/resolved_config.json" --run-dir "$RUN" --block core --all \
  > "$LOGBASE.log" 2>&1 < /dev/null &
WORKER_PID=$!
printf '%s\n' "$WORKER_PID" > "$LOGBASE.pid"
printf 'utc=%s\ntag=%s\nrun=%s\nworker_pid=%s\n' \
  "$(date -u +%FT%TZ)" "$TAG" "$RUN" "$WORKER_PID" > "$LOGBASE.monitor.log"
printf 'worker_pid=%s\nrun=%s\nlog=%s\nexit=%s\nmonitor=%s\n' \
  "$WORKER_PID" "$RUN" "$LOGBASE.log" "$LOGBASE.exit" "$LOGBASE.monitor.log"
```

本 nohup 外壳只负责等真实 generation 子进程返回并写真实 `.exit`，避免后来在无父子关系的 shell 中 `wait` 得到 127。它不是新的 supervisor/probe 框架。保留外层命令原始输出和返回码；提交返回 0 不等于 generation 成功。

使用 `--all`；不要使用 `--screen` 或 `--build-evaluation-schedule` 代替正式执行，后者只建日程就返回。现有 runner 依 config 顺序串行加载 Qwen/Llama，两者均会执行，各仅一个 Core 层；顺序不必强改。不加载 Judge/Gemma，不多卡。

## 三、监控和失败处理

主会话每 30–60 秒只读检查 worker 及其 Python 子进程、日志尾部、GPU、`generation_attempts.jsonl` 的大小/完整行数和最新状态，把带时间的摘要追加至 `.monitor.log`。日程已在启动前存在；`generation_ledger.jsonl`、`behavior_release.json` 通常在全部模型处理后落盘，运行中暂缺它们不等于失败。日志暂静默但 attempts 增长属于有进展，不因为安静重启。

如果会话断连，重新连接后先按 `.paths.txt`、PID、`ps`、日志和 run 判断原进程状态；不再次执行 launch.sh。同一服务器任务只有本次一个正式 generation 提交。禁止在不知道是否已运行时换 tag 再投，禁止把等待 agent 当执行。需要较长时间则继续监控并如实报告当前进度，不编造完成状态。

每条 generation 技术失败按现有协议至多一次 retry，实际 attempts 单列，不计入 11,440 logical；不额外发请求。模型成功返回的拒答、空输出、重复、截断或崩坏是待测结果，不为“改善质量”重生成，也不据此更换剂量。终止技术失败保留原行及错误，不删除、不补成成功。

worker 异常退出、OOM、source/asset mismatch 或大量同源技术错误时，记录事实和受影响行，保留部分输出，不自动重提或更改科学参数；必要时仅停止本任务自有进程并记录信号/原因，不影响他人进程。不要因为 CLI 返回 0 就认为全部成功：现有 runner 可能在内部记录 `RUNTIME_NOT_RUN` 或 release failure 后仍返回 0。

## 四、一次收尾核对与交付

结束后做一次有边界的 CPU 核对，保存新 run 内 `generation_summary.json`：

- schedule 11,440，ledger 对应完整且 identity 唯一；按四块及两个模型统计 COMPLETED / TERMINAL_TECHNICAL_FAILURE / UNEXECUTED、attempts/retries，canonical text 与实际成功 attempt 对应。若所有 logical 已到终态但有少量 terminal failure，如实记录数量和 missing，不自行新增“必须零技术失败”的科学规则；UNEXECUTED 或未加载模型不能称完整。
- 检查已成功输出的文本、token IDs、原始 diagnostics、phase/runtime counters、实际 alpha 和帧/方向/剂量绑定；空输出/EOS-first 按现有规则记录，不能为了字段检查补文本或新请求。
- 核对两模型的真实 runtime identity 与新 `behavior_release.json`，并将模型路径、dtype、层、原生模板及已有 config/tokenizer hash 与 F2 来源 identity 比较；原有 revision UNKNOWN 保持 UNKNOWN，不补造，也不因此要求在线查 revision。不得拿方向来源的旧 release 代替。如果 release/身份缺失或科学身份不一致，报告缺口，不改写占位值为 PASS。确认本任务 Python 已退出，无残留本任务 GPU 进程。
- 来源 frames/tensor/dose、原 config/design 与旧 F2/rescore 输入 hash 前后匹配，新 source snapshot 检查通过；只核对本次实际依赖，不扩展成重新审计全部历史 run。
- 完成写入后生成新 run 的 `artifact_hashes.sha256` 并校验，清单覆盖除其自身以外的文件，包括 helper snapshot、runtime、schedule、attempts、ledger 和摘要。不要在该清单生成后继续修改已覆盖文件；若追加交接文件则最后刷新一次。

报告保存：`writing/broadening design/report/paper1_core_formal_generation_report.md`。报告写清新 run_id/path、源 F2 与 screen run、代码/未提交修改、实际 shell 命令、PID/子进程、log/exit/monitor、11,440 分块状态、真实 retry 数、release/identity、输入不变核查、哈希验证和问题。不要提前写 unsafe/broken 比例；本任务未 Judge。完成后停止等待本机结果审核，不自动开展后续模块。

**最终回复必须列出以下所有实际新增/修改路径，不能只给报告和 evidence 目录：**

1. `scripts/materialize_core_formal_run.py`，实际新增测试及其他实际改动文件（若无则明确无）。源码/测试 LF；代码与小文档可经 Git 同步。
2. 上述报告；`.codex-temp/paper1_core_formal_generation/` 全目录，包括 launch.sh、检查/测试日志和真实退出码、paths receipt、前后输入核对。
3. 完整新 `results/paper1_broadening/<本次 TAG>/`（含 tensor、snapshots、原文和 token IDs），可以 SFTP 同步；不要只同步 summary。
4. `logs/paper1_broadening/<本次 TAG>.log/.pid/.exit/.monitor.log` 以及实际独立产生的其他日志。文件不存在必须标明，不能事后猜测生成。

本任务不自动 commit/push 服务器混合工作区；交付逐项文件表和 SHA256，作者可指示仅提交本任务源码/测试/报告，结果通过 SFTP。不要把模型权重放入 Git。运行结果被本机审核后，下一步才是 Core 正式 Judge 与结果汇总。
