# A2/B2 完成后的当前任务入口

更新：2026-09-14。此索引取代此前 A–E 的执行顺序；历史报告保留，旧任务不重复执行。

## 当前判断

- A2 报告：416 条 source、7 条 exact overlap、409 条 preliminary eligible；818 个完成的 A/B 请求，221 条 unanimous include、188 条 exclude，无 pending。`k=min(80,(221-100)//5)=24<30`。至少还需 **29 条新增 executable pairs**，不是 29 条未经审核的原始数据。
- B2 输出称实现已修复、43 tests passed；但截至本机及远端 `1124c53`，B2 修复报告、public config、ledger 重建脚本及对应代码尚未同步。A2 原始请求证据和 prepare 产物也不在本机；目前不能写成已独立验收。
- 旧 v1 的 194 条来自失效审核历史，不能复用。A2 的 221 条是待核验证据的新基线；数量不足本身不构成再次全量重审的理由。
- A2 prepare 的 E1 资产缺失/E2 未配置，先检查 config 和 loader 接线；C/D 已完成的资产准备不应因此重复执行。

## 现在交付的三个任务

| 会话 | 任务书 | 立即可做 | 停止位置 |
|---|---|---|---|
| 原 A2，续作 A3 | [A2 证据核验与交付](paper1_server_codex_a2_evidence_handoff_prompt_nohup.md) | 只读核验 409/818 记录、重算计数、打包证据 | 保存 `paper1_a2_evidence_handoff_report.md`；不重审、不 prepare |
| 原 B2，续作 B3 | [B2 代码交付与资产接线](paper1_server_codex_b2_delivery_asset_wiring_prompt_nohup.md) | 补交报告/代码，接入 E1/E2 本地资产 | 保存 `paper1_b2_delivery_asset_wiring_report.md`；不 prepare、不加载模型 |
| 新 E，或已停止的 E | [公开 safe-pair 恢复 v2](paper1_server_codex_public_safe_pair_gate_recovery_prompt_nohup.md) | 候选发现/下载；A3/B3 通过后继续整合、双审核、prepare | 保存 `paper1_public_safe_pair_gate_recovery_report.md`；数据 gate 通过也不启动模型实验 |
| 原 C、D | 暂无新任务 | 保留报告与证据 | 等待最终 source，不重复 overlap/Gemma 探针 |

三个任务可以现在交付。A3/B3 使用原会话；E 如为新会话，从磁盘读取索引与任务书，不依赖会话记忆。

## 依赖和写入归属

1. A3 只读 source/ledger/raw/run，只写自己的核验脚本、证据副本和新报告。历史执行从旧 run 快照核验，不拿 B3 当前工作树冒充历史源码。
2. B3 是当前共享实现和资产配置的唯一写入者，不修改 A2 审核脚本、source、ledger、旧 run。
3. E 的候选发现/下载在 `.codex-temp/paper1_source_recovery_v2/` 独立进行。整合/审核等待 A3=`A2_EVIDENCE_VERIFIED`、B3=`B2_DELIVERY_READY` 且 B3 停止代码写入。
4. 两个前置通过后，E 可以按任务书直接继续，不需再次等待批准；此时 E 是新增 source/config/review 脚本的唯一写入者。前置未完成则保存阶段报告并等待，时间经过不视为通过。
5. A3 若发现证据/协议问题，列出具体受影响记录并阻断整合，不能自动全量重审或从 221 中静默删项凑数。E 可以完成来源调查，不能据此正式纳入数据。
6. 三会话不 commit/push、不覆盖式 pull、不 reset/clean，不动其他用户文件或进程。保留交付包供用户同步回来，由本机负责人审核和提交。不得把模型权重、缓存或无关会话提交 Git。

## 共用 Linux/nohup 规则

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

测试、批量核验、转换、ledger 汇总和 prepare 用 nohup。同会话一次一个后台步骤，确认退出并读取 `.exit` 后继续；不同会话只读 CPU 工作可并行。没有 `.exit` 不能写成通过。轻量阅读/Git 状态查询、原生 subagent 调用无需套虚假 nohup 包装；实际 CLI/API runner 才按需要后台运行。PID 不能替代 reviewer 调用证据。

服务器下载只用明确来源的 GitHub/ModelScope，不访问 HF，不在线加载模型。三个任务均不启动 GPU 模型实验。文件关闭写入后再计算交付 hash，不增加运行前不可变设计 manifest。

## 交付与后续

每个任务完成一次有边界自审：发现问题只修复相关项并复核，不扩展实验。失败也保存事实报告和证据，不能为了 PASS 改门槛。报告列实际文件、命令/PID/log/exit、代码状态、未解决项，写 `FORMAL_EXPERIMENTS_NOT_RUN`。

下次除三个新报告，还需同步 B2 原报告及实际代码/配置/测试、A2 ledger/summary/协议/请求索引和 prepare 小产物、E 新增数据/整合/审核证据（若完成）。报告不能代替代码。完整 raw 证据保留并提供压缩包，不要求把大文件放进 Git。

E 通过后，下一阶段是最终 E1 overlap/40 条选择、必要的真实 runtime/smoke 核验，再进入 Core directions/screen。C 届时继续；D 无须重复已通过的零剂量探针。正式运行不在本轮授权范围。
