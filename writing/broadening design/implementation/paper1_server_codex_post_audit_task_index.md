# Safe-pair 恢复后的当前任务入口

更新：2026-09-15，依据 C2/B4 完成报告。本索引替代此前顺序；旧A/B/A2/A3/B2/B3/E/E4/C2/B4任务均不重新执行。

## 当前决定

服务器报告safe-pair gate通过：516 source − 7 exact = 509 preliminary；旧221 + 新79 = 300 executable；5×40 construction + 100 development = 300，unused=0。无需新增来源或再次审核旧/新safe pairs。报告的 `READY_FOR_CONSTRUCTION` 仅是数据gate，尚未构造向量或运行正式generation。

服务器已交付 B4 运行时证据和 C2 overlap 产物。C2 派生文件仍绑定旧 reference digest，B4 consumer 正确 fail-closed；先完成最终派生物收尾，再建立含最终 E1 frames 的正式 run。

## 当前任务顺序

| 会话 | 任务书 | 范围与停止点 |
|---|---|---|
| 原C会话，续作C3 | [最终 E1 派生物收尾](paper1_server_codex_c3_e1_consumer_finalize_prompt_nohup.md) | 复用 C2 raw；只重建 digest/状态/路径绑定，不重审、不加载模型、不改共享实现 |
| 原B会话，续作B5 | [E1 消费复核与运行入口交接](paper1_server_codex_b5_e1_consumer_handoff_prompt_nohup.md) | 等 C3 final 文件后纯 CPU 验证 `READY_FOR_RUN`，必要时创建 run-specific config，不运行模型 |
| 新F会话 | [Core 方向构造与 calibration](paper1_server_codex_core_directions_calibration_prompt_nohup.md) | B5 PASS 后 `prepare + build-directions`；单卡顺序构造 Core，并记录自动接入的 E2/E3 方向资产；不screen、不generation |
| 原E、A、D | 本轮无需新任务 | E完成；A证据沿用；D的Gemma探针不重复 |

若原C/B会话无法继续，可新开会话承接对应任务，不能让新旧会话同时写同一输出。C3完成后才启动B5；F可提前做静态检查，但在 B5 PASS 前不得创建正式 run。

## 输入和并行归属

- 固定safe-pair输入：`data/safe_pairs_public_semantic_v2_expanded.json`、同前缀 `_ledger.json`/`.manifest.json`；config=`configs/paper1_broadening/mbd_nm_v212_public_expanded.json`。
- 数据型prepare：`results/paper1_broadening/public-safe-pair-recovery-v2-final-20260915T041534Z/`。保持其source、ledger、300个分配ID和原run不变；E1补全不回头改safe split。
- C3只读 C2 raw/reference 和 safe-source snapshot，输出写独立 final 目录，保留旧 provisional 文件；不对 safe-pair 或 E1 near queue 重发 reviewer。
- B5只读 C3 final 文件和当前实现，必要时写最小 E1 path adapter/run-specific config；不改 canonical scientific config。
- F 是唯一 GPU 方向构造者；使用 B5 通过后的稳定 config/run。C3、B5、F 不共享同一正在写入的 run 目录。

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

只有B4可使用GPU0；启动前确认空闲/足够显存，不终止其他用户进程，不切双卡、不在线下载、不升级现有模型环境。被测模型和Judge顺序加载并释放。小型检查无需下载模型、重hash所有权重或重新建立环境。

## 输出与下一阶段

C3报告：`writing/broadening design/report/paper1_e1_consumer_finalization_report.md`。
B5报告：`writing/broadening design/report/paper1_e1_consumer_handoff_report.md`。
F报告：`writing/broadening design/report/paper1_core_direction_calibration_report.md`。

两份报告分别做一次任务内自审，有问题只修相关项并复核，不加新审计轮次。服务器不commit/push（用户另有明确授权则按其限定范围执行），不清理他人文件。将B4列出的实际代码/数据/配置/来源addendum和C2结果一起同步；raw留服务器，需要复核具体项再转移，不强制大包或双份备份。

C3/B5通过后，F 才建立最终 run 并运行 `prepare -> build-directions`。现有 `build-directions` 可能自动构造 E2/E3 方向资产，按实际状态分别记录；不会因扩展资产缺失而改写 Core gate。F 完成后再单独交付 Core development screen 任务，锁定 A/S 后才可安排正式 evaluation。
