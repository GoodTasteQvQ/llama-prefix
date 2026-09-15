# Core：方向构造与 calibration 资产

版本：`core-directions-calibration-v1`；日期：2026-09-15。交给新的 F 会话；也可交给已完成 B4 的会话，但不得与 B5 同时写共享文件。

开始前必须读取当前任务入口、C3/B5 最终报告、safe-pair recovery 报告、expanded source/ledger/manifest/config、原实验设计三份正文/规范和设计不可变性审计。只有在 safe-pair=`READY_FOR_CONSTRUCTION`、B4=`CODE_CONTRACT_PASS`、Core smoke=`PASS/NON_EVIDENCE` 且 B5=`E1_CONSUMER_PASS` 后，才创建本次正式 run；若 B5 尚未通过，只做静态检查并停止等待，不创建带有过期 E1 frames 的运行目录。

## 1. Prepare（只生成输入和计划）

使用最终 run-specific expanded config（包含 C3 final E1 path；不改 canonical scientific fields），在 Linux 项目目录执行：

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp" TMP="$TMPDIR" TEMP="$TMPDIR" NX_DAEMON=false
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONUNBUFFERED=1
export PYTHONPYCACHEPREFIX="$TMPDIR/pycache" CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES=0 MBD_GPU=0
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
MBD_CONFIG="$PWD/configs/paper1_broadening/<final_run_config>.json"
MBD_OUT="$PWD/results/paper1_broadening/<new-run-id>"
nohup bash -c 'rc=0; "$1" scripts/paper1_broadening.py prepare --config "$2" --output-dir "$3" || rc=$?; printf "%s\n" "$rc" > "$4"; exit "$rc"' \
  mbd-prepare "$MBD_PYTHON" "$MBD_CONFIG" "$MBD_OUT" "$PWD/logs/paper1_broadening/<tag>.exit" \
  > "$PWD/logs/paper1_broadening/<tag>.log" 2>&1 < /dev/null &
printf '%s\n' "$!" > "$PWD/logs/paper1_broadening/<tag>.pid"
```

等待进程结束并核对 exit 和业务 JSON。确认 `safe_pair_split.gate=READY_FOR_CONSTRUCTION`、`actual_k=40`、5 folds 各40、development=100、unused=0、construction/development disjoint，且 E1=`READY_FOR_RUN`。prepare 不加载模型。

## 2. Build directions and calibration

在同一 run、同一显式 config 上，以单卡顺序运行 `scripts/paper1_broadening.py build-directions --config "$MBD_CONFIG" --run-dir "$MBD_OUT"`，通过 nohup 保存 PID/log/exit。不要先运行 screen 或任何 generation。

必须核对并保存：

- Qwen2.5-7B-Instruct 核心 layer 9、Llama-3.1-8B-Instruct 核心 layer 11；均为 zero-based `resid_pre`；每个模型8个 Rogue + 5个 contrastive、五个 construction fold 来源、float32 unit-norm tensor、非零/finite sign diagnostics；
- development harmless 的 content-token `mu_content` 和 token count，使用 native chat template、可靠 user span/content mask，不把 JBB/benign 作为 construction 或 calibration；
- 实际 runtime identity、model/tokenizer path、Python/PyTorch/Transformers/CUDA/driver、GPU UUID、模板和释放记录；Qwen/Llama 不并存。

当前实现的 `build-directions` 在 Core 成功后可能自动接着构造 E3 额外层和 Gemma E2 方向资产。不得为了只保留 Core 而加 block 开关；若这些资产被实际构造，单独记录 E2/E3 状态、层公式和释放信息。Gemma 缺失只标对应扩展 `NOT_RUN/BLOCKED`，不把 Core 方向结果伪装成扩展通过。

验证方向文件的模型、层、fold membership、seed（Rogue 为 `420000 + model_index`）、norm、shape、mu、sign status 和 release；发现 zero/nonfinite、wrong layer、模板 span 失败或科学字段不一致时保留证据并停止。不能按 sign 或结果重新训练、翻转、换层或删方向。若必须改变模型、层、模板、decoder、rho、seed、split、判定标准、预算或 endpoint，立即报告 `DESIGN_CHANGE_REQUIRED`，不得自行修改设计正文。

## 3. 停止与报告

不运行 `screen`、`generate`、`judge`、`analyze`、`sample-human`、`archive`，不选择 A/S 剂量，不生成正式评价 schedule，不建立全项目 hash manifest。只在结果文件关闭写入后对必要 direction/calibration 产物做 hash。

保存 `writing/broadening design/report/paper1_core_direction_calibration_report.md`，列 run/header、prepare 与 build 命令/PID/log/exit、实际模型和资产状态、方向/层/mu/sign 计数、E2/E3 自动接入状态、测试/未运行项、文件 hash、设计未修改声明和一次有边界自审。成功写 `CORE_DIRECTIONS_READY`；缺必要 Qwen/Llama 资产写 `CORE_DIRECTIONS_BLOCKED`；始终保留 `FORMAL_EXPERIMENTS_NOT_RUN`。不要 commit/push。
