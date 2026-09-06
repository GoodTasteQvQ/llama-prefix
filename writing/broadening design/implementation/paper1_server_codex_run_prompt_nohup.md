# 服务器 Codex 运行任务书：预检、审核交接与有条件正式运行

版本：server-run-v2，2026-09-06。对应 MBD-NM v2.1，Linux 单卡。

本文件全文可直接交给服务器 Codex。你负责执行现有补充实验代码，核对产物并报告状态。
当前可立即执行的是环境复核、离线测试和 prepare；正式实验必须满足下文所有前置条件。
本机复核发现并修复了运行契约问题，必须同步修复后使用新 run。当前
`overlap_decisions_path=null`，预期在人工审核交接处停止。

## 1. 权限与必读文件

在 `/data/goodtaste_workspace/llama-prefix` 中依次阅读：

1. `writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md`。
2. `writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md`。
3. `writing/broadening design/report/paper1_server_implementation_completion_report.md`。
4. `writing/broadening design/review/paper1_run_readiness_review.md`。

科学定义以第1份为准，实现/环境契约以第2份为准。旧实现任务的“禁止正式运行”属于已结束
的代码交付任务；本任务在全部运行条件通过后授权 core 的既定 screen/evaluation。

不运行 Mistral，不修改 12,640 core / 7,840 extension / 20,480 总逻辑 generation 上限。
A=S 共享 response，Judge、重试、已有 smoke、activation forwards 分账。不按结果调整
prompt、fold、方向、rho、层或端点。已有 Calibration-Frame Sensitivity 不在本轮重跑。

本轮优先完成 core 并生成其人工标注包。E1/E2/E3 先报告 readiness，不自动接着执行；
缺 E1/E2 资产只阻塞对应扩展。不要下载模型、替换 benchmark、修改历史结果或 commit/push。
不改正式服务器 torch/Transformers 或 Judge float32，不搭建调度平台。

## 2. 环境与 nohup 启动

运行安装、测试或实验入口前设置：

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export NX_DAEMON=false
export MBD_GPU=0
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES="$MBD_GPU"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export HF_HOME="$PWD/.hf_cache"
export MPLCONFIGDIR="$TMPDIR/matplotlib"
export MBD_MODEL_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
export PYTHONUNBUFFERED=1
test -x "$MBD_MODEL_PYTHON" || exit 1
MBD_WRAPPER="$PWD/scripts/run_paper1_broadening_single_gpu.sh"
MBD_CONFIG="$PWD/configs/paper1_broadening/mbd_nm_v21.json"
MBD_LOG_ROOT="$PWD/logs/paper1_broadening"
```

通过下面的薄函数启动测试和各阶段。退出码在 nohup 子进程内落盘，断线后也能查询。
每次只启动一个阶段，确认退出码和业务产物后才提交下一条命令。

```bash
launch_nohup() {
  local step="$1"
  shift
  local tag="${step}-$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM}"
  local log="$MBD_LOG_ROOT/$tag.log"
  local status="$MBD_LOG_ROOT/$tag.exit"
  nohup bash -c '
    status_file="$1"
    shift
    rc=0
    "$@" || rc=$?
    printf "%s\n" "$rc" > "$status_file"
    exit "$rc"
  ' mbd-job "$status" "$@" > "$log" 2>&1 < /dev/null &
  local pid=$!
  printf '%s\n' "$pid" > "$MBD_LOG_ROOT/$tag.pid"
  printf 'pid=%s log=%s exit_file=%s\n' "$pid" "$log" "$status"
}
```

每15-30秒查看状态文件/日志。断线后先核对PID、命令行和产物，进程仍活跃时不得重复启动。
PID消失而.exit缺失表示异常结束，不能猜测成功。退出码0也不等于业务PASS：部分CLI会以0
返回BLOCKED、NOT_RUN或带失败的accounting。只在业务gate与产物也通过后继续。
GPU步骤前用nvidia-smi检查GPU0资源，只用逻辑cuda:0、batch=1，不借第二卡、不量化、
不CPU offload、不杀其他用户进程；资源不足记录状态并停止，不无限等卡。

## 3. 同步复核与离线测试

记录git HEAD、分支、dirty与解释器版本，确认修复后的pipeline、orchestration、archive、
CLI和test_run_readiness.py已同步。保留用户修改，运行期间不改源码或对运行checkout做pull。
文档已整理到implementation/review/report子目录，快照代码必须使用新路径。

```bash
launch_nohup offline-tests "$MBD_MODEL_PYTHON" -m pytest \
  tests/paper1_broadening -q -p no:cacheprovider \
  --basetemp "$TMPDIR/paper1-broadening-pytest"
```

等待测试通过，另检查wrapper的bash -n和CLI help。离线tests不依赖空闲GPU或模型加载。
失败时做有边界修复审查，不进入正式实验。不要因为本机CPU测试通过就省略服务器运行检查。

```bash
MBD_ASSET_REPORT="$TMPDIR/mbd-assets-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
launch_nohup discover-assets bash "$MBD_WRAPPER" discover-assets \
  --config "$MBD_CONFIG" --output "$MBD_ASSET_REPORT"
```

核对Qwen2.5-7B、Llama-3.1-8B、Qwen3-8B Judge的本地完整性和realpath。未知revision记
UNKNOWN，不能把目录名冒充revision。文件检查不等于模型已加载或hook验证通过。
E1必须独立登记HarmBench标准文本及metadata，JBB的来源标签不充当E1。Gemma缺失写
E2 NOT_RUN。报告磁盘余量，安装/测试临时文件均在项目内。

## 4. prepare 与人工审核交接

```bash
launch_nohup prepare bash "$MBD_WRAPPER" prepare --config "$MBD_CONFIG"
```

从日志结构化JSON读取实际run_dir，将MBD_RUN_DIR设为该绝对路径，再执行：

```bash
test -f "$MBD_RUN_DIR/run_header.json" || exit 1
MBD_RUN_CONFIG="$MBD_RUN_DIR/resolved_config.json"
test -f "$MBD_RUN_CONFIG" || exit 1
```

检查JBB100=100、JBB40=40、benign30=30、五折/100 development/前20 screen角色隔离，
以及frames、源码和设计副本。当前配置未提供语义审核决策，预期
PENDING_SEMANTIC_REVIEW。此时只生成审核材料并停止，不运行模型。

从frames解析overlap_review_queue中的双方id，为研究者列出两侧原文、候选原因和空白
reviewer字段。当前实现要求所有preliminary eligible pairs都有审核决定；候选队列不等于
全部待审pairs，必须同时报告两种数量，不能把无near-match候选自动写成语义PASS。

decision JSON为 {"records":[...]}，每行含pair_id（例如safe-pair:0）、reviewer_a、
reviewer_b、decision，合法结论为include/exclude；保留reviewer身份、依据和时间。
Codex不能冒充两位人工reviewer。设计允许研究者裁决分歧，当前解析器只接受双人一致记录；
确有分歧时保留原始意见和裁决，报告接口差异并完成最小适配及测试，不能篡改reviewer字段。

真实审核完成后，在独立运行配置登记decision路径；保留旧prepare目录，用新run重新
prepare。确认READY_FOR_CONSTRUCTION、实际k>=30及角色隔离。准备阶段可以迭代，
不得为PASS伪造结论。正式结果落地后再按协议归档，不增加运行前manifest。

## 5. 正式运行前复核真实 smoke

safe-pair通过后还须检查服务器已有真实smoke文件：
`.codex-temp/paper1_broadening_smoke-final/smoke_report.json` 及trace和环境记录。
24 generation + 4 Judge属于已使用的实现smoke额度，标NON_EVIDENCE，不自动再次运行。
从原始结果复核当前Qwen/Llama模板、核心层、两phase、zero-alpha与clean token ids、
cache/hook counters及Judge解析。只看总PASS字段不够，fixture不能替代。
缺少可核验记录时列出最小缺项并停在该gate，不直接启动1,200条screen。

新run的源码/config快照须对应执行代码；旧run快照不一致不得改写快照强行继续。
核心预算为screen 1,200 + evaluation 11,440 = 12,640；evaluation分项为10,400 harmful
steered + 200 harmful clean + 780 benign steered + 60 benign clean。A=S时实际生成数
减少，不是漏跑；保留两条逻辑配对行，不把它们当独立response。

## 6. core 串行执行

逐条提交以下命令，每条结束核对产物后才启动下一条，不批量粘贴整个章节。

```bash
launch_nohup directions bash "$MBD_WRAPPER" build-directions \
  --config "$MBD_RUN_CONFIG" --run-dir "$MBD_RUN_DIR"
```

确认Qwen/Llama directions COMPLETED，finite/norm/shape/content span、mu/token count、
release正确。sign-not-validated按设计报告，不自动翻转或重训。当前build-directions
也会测E3额外层mu，这是既有activation forwards，不代表E3 screen/evaluation已放行。
方向文件已有结果时不盲目重跑覆盖；缺Gemma只记E2 NOT_RUN。

```bash
launch_nohup core-screen bash "$MBD_WRAPPER" screen \
  --config "$MBD_RUN_CONFIG" --run-dir "$MBD_RUN_DIR" --block core
```

screen内部GPU子进程由nohup父进程串行管理。检查generation/release、Judge/release、
screen_processes以及全部20个候选（2 models x 2 families x 5 rho）的accounting。
每候选60条，missing>2%阻塞；dose_decisions.core.status必须为DOSE_DECIDED。
A_NOT_ESTABLISHED、S_NOT_ATTAINED、ordering_not_established是保留的科学状态，不改grid，
不要求结果符合预期。技术失败至多重试一次，不能通过反复screen增加重试额度。

```bash
launch_nohup core-schedule bash "$MBD_WRAPPER" generate \
  --config "$MBD_RUN_CONFIG" --run-dir "$MBD_RUN_DIR" --block core --build-evaluation-schedule
```

确认11,440逻辑行及物理response数、A/S aliases、clean去重后，在本任务授权内运行：

```bash
launch_nohup core-generation bash "$MBD_WRAPPER" generate \
  --config "$MBD_RUN_CONFIG" --run-dir "$MBD_RUN_DIR" --block core --all
```

检查未执行、retryable、终结失败和release。中断按同一run恢复，保留首个成功attempt，
至多一次技术重试；空/短/broken是有效输出。终结失败保留missing并对其他成功输出Judge，
不删除分母。release不全先解决运行故障，不伪造释放文件。
generation尚可恢复时不要先创建generation_missing Judge记录。

```bash
launch_nohup core-judge bash "$MBD_WRAPPER" judge \
  --config "$MBD_RUN_CONFIG" --run-dir "$MBD_RUN_DIR" --block core
```

four-class每物理response一行；parse/technical failure按原配置至多重试一次。加载失败、
调用数0的记录可以恢复，不能抹掉实际调用失败的记账。随后独立计binary：

```bash
launch_nohup core-binary bash "$MBD_WRAPPER" judge \
  --config "$MBD_RUN_CONFIG" --run-dir "$MBD_RUN_DIR" --block core --binary
```

binary不替代four-class，short-rule命中0次模型调用，其余调用独立计数。两个Judge阶段均
核对业务状态与release，不能因进程返回0忽略RUNTIME_NOT_RUN。

```bash
launch_nohup core-analysis bash "$MBD_WRAPPER" analyze \
  --config "$MBD_RUN_CONFIG" --run-dir "$MBD_RUN_DIR" --block core
```

核对配对/分母/missing bounds、表图与证据状态，超阈值输出accounting-only，不放宽阈值。
完成后：

```bash
launch_nohup core-human-packet bash "$MBD_WRAPPER" sample-human \
  --config "$MBD_RUN_CONFIG" --run-dir "$MBD_RUN_DIR" --block core
```

检查最多160概率样本+40诊断样本、allocation/private key与双人包分开保存。标注包只含
blind_id/request/response/完整rubric，不含模型、phase、自动label，不自动重抽已有包。
此时HUMAN_REVIEW=PENDING并交接停止。收到真实标签后才analyze --human；
全部结果关闭后才archive --require-human，不用空标签或fixture标FINAL。

## 7. 有边界审查与报告

一轮完整产物/命令审查，阻断问题最多两轮集中修复和定向复查。不扩展到全库重构、新模型
或新实验，格式建议不阻塞。科学歧义、人工缺项或资源未满足时保留材料报告BLOCKED/PENDING，
不伪造PASS。修改代码先通过相关测试，再尝试运行。

保存 `writing/broadening design/report/paper1_server_run_status.md`，包含HEAD/dirty、
解释器、GPU UUID、资产、命令/PID/.exit/日志/run_dir、开始/结束时间、逻辑/物理完成、
失败/未执行数、重试/Judge调用数、release与科学gate。分列测试、safe-pair、真实smoke复核、
directions、screen、generation、Judge、analysis、human、E1/E2/E3状态。

不要commit/push，不改写历史完成报告掩盖失败，不以nohup返回PID当作任务完成。
当前审核未完成时明确交接人工审核，不能写“可立即开始全量实验”。
