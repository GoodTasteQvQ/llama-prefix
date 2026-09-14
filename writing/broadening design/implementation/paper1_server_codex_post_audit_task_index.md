# A2/B2 完成后的当前任务入口

更新：2026-09-14，已纳入用户转述的A2独立性专项核验。当前任务版本为A3 handoff-v2、B3 delivery-v2、E recovery-v3；此前版本不再交付执行。

## 当前判断

- A2 报告：416 条 source、7 条 exact overlap、409 条 preliminary eligible；818 个完成的 A/B 请求，221 条 unanimous include、188 条 exclude，无 pending。`k=min(80,(221-100)//5)=24<30`。至少还需 **29 条新增 executable pairs**，不是 29 条未经审核的原始数据。
- 用户随后提供A2专项核验：818个真实独立请求/thread/workdir、A/B隔离证据和最终COMPLETE状态已检查。这个已完成结果可以作为服务器继续工作的依据，不重复安排来源/独立性全量核验；原始文件尚未同步本机，不冒称本机独立复现。
- 最终依据是 `rebuilt_summary.json` 和rebuilt ledger；旧 `summary.json` 的817 ok/1 pending是341 retry前统计，不构成当前阻塞。7条exact overlap无需补审。
- B2输出称实现已修复、43 tests passed；上次在 `1124c53` 核对时修复报告/public config/重建脚本和对应代码尚未同步，之后同步的是任务文档。B3仍需补交实际代码和报告。
- 旧v1的194条来自失效审核历史，不能复用。当前以A2最终ledger的221条为恢复基线；数量不足本身不构成再次全量重审的理由。
- A2 prepare 的 E1 资产缺失/E2 未配置，先检查 config 和 loader 接线；C/D 已完成的资产准备不应因此重复执行。

## 现在交付的三个任务

| 会话 | 任务书 | 立即可做 | 停止位置 |
|---|---|---|---|
| 原 A2，续作 A3 | [已完成核验的记录与交付](paper1_server_codex_a2_evidence_handoff_prompt_nohup.md) | 记录既有核验，交付最终ledger/summary等小文件 | 保存 `paper1_a2_evidence_handoff_report.md`；不重复核验、不prepare |
| 原 B2，续作 B3 | [B2 代码交付与资产接线](paper1_server_codex_b2_delivery_asset_wiring_prompt_nohup.md) | 补交报告/代码，接入 E1/E2 本地资产 | 保存 `paper1_b2_delivery_asset_wiring_report.md`；不 prepare、不加载模型 |
| 新 E，或已停止的 E | [公开 safe-pair 恢复 v3](paper1_server_codex_public_safe_pair_gate_recovery_prompt_nohup.md) | 候选发现、独立临时目录内整合和新增双审核；共享代码/最终prepare等待B3交接 | 保存 `paper1_public_safe_pair_gate_recovery_report.md`；不启动模型实验 |
| 原 C、D | 暂无新任务 | 保留报告与证据 | 等待最终 source，不重复 overlap/Gemma 探针 |

三个任务可以现在交付。A3/B3 使用原会话；E 如为新会话，从磁盘读取索引与任务书，不依赖会话记忆。

## 依赖和写入归属

1. A3只读source/ledger/raw/run，仅记录已完成核验和交付必要小文件，不重建历史结果。历史执行不能用当前工作树冒充。
2. B3 是当前共享实现和资产配置的唯一写入者，不修改 A2 审核脚本、source、ledger、旧 run。
3. E先在 `.codex-temp/paper1_source_recovery_v2/` 独立处理新候选/临时转换/新增审核；使用已完成A2核验和实际最终ledger/固定协议，不等A3报告或压缩包。不运行B3正在修改的模块，不修改共享代码/config/source；必要的共享代码操作延后交接。
4. E进入共享实现修改、正式source/config发布、最终测试和prepare前，须读取B3的 `B2_DELIVERY_READY` 报告并确认其停止写代码。该状态只要求core契约/执行版本与测试依据可定位；E1/E2接线和异地打包不是新数据审核的前置。交接后E成为相关代码/source唯一写入者。
5. 有实际证据矛盾时只阻断受影响数据的复用，列出具体项；不能自动全量重审或从221中静默删项凑数。只有新的实际问题才重开检查，A3文件整理尚未完成不算证据矛盾。
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

下次除三个新报告，还需同步B2原报告及一份实际代码/配置/测试、A2最终ledger/rebuilt summary/协议/请求索引和prepare小产物、E新增数据/整合/审核证据（若完成）。报告不能代替代码。完整raw保留服务器并列路径，需要异地复核时再打包；不以复制/压缩进度阻塞数据工作，不要求同时交付源码副本和可应用补丁。

E 通过后，下一阶段是最终 E1 overlap/40 条选择、必要的真实 runtime/smoke 核验，再进入 Core directions/screen。C 届时继续；D 无须重复已通过的零剂量探针。正式运行不在本轮授权范围。
