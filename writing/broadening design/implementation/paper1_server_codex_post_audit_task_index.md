# A2/B2 完成后的当前任务入口

更新：2026-09-15，已纳入A3/B3/E回执及设计不可变性审阅。A3/B3已完成；当前只需交付E4续作任务。此前版本不再交付执行。

## 当前判断

- A2 报告：416 条 source、7 条 exact overlap、409 条 preliminary eligible；818 个完成的 A/B 请求，221 条 unanimous include、188 条 exclude，无 pending。`k=min(80,(221-100)//5)=24<30`。至少还需 **29 条新增 executable pairs**，不是 29 条未经审核的原始数据。
- 用户随后提供A2专项核验：818个真实独立请求/thread/workdir、A/B隔离证据和最终COMPLETE状态已检查。A3已将最终ledger、summary和必要小文件交付；不重复安排来源/独立性全量核验。
- 最终依据是 `rebuilt_summary.json` 和rebuilt ledger；旧 `summary.json` 的817 ok/1 pending是341 retry前统计，不构成当前阻塞。7条exact overlap无需补审。
- B3已交付实际实现/配置接线和45项主测试、5项adapter测试，状态`B2_DELIVERY_READY`；实际代码仍需按B3交付清单从服务器同步后才能在本机复核。
- 旧v1的194条来自失效审核历史，不能复用。当前以A2最终ledger的221条为恢复基线；数量不足本身不构成再次全量重审的理由。
- A2 prepare 的 E1 资产缺失/E2 未配置，先检查 config 和 loader 接线；C/D 已完成的资产准备不应因此重复执行。

## 现在交付的三个任务

| 会话 | 任务书 | 立即可做 | 停止位置 |
|---|---|---|---|
| 原 A2 | 已完成 | A3_HANDOFF_RECORDED；不再重复 | 等待后续数据交接 |
| 原 B2 | 已完成 | B2_DELIVERY_READY；不再重复 | 等待后续数据交接 |
| 原 E，继续做 E4 | [恢复 safe-pair 来源整合与新增双审核](paper1_server_codex_e_resume_after_a3_b3_prompt_nohup.md) | 审查已下载候选、冻结批次、完成新增双审核；交接后合并/prepare | 保存更新后的 recovery report；不启动模型实验 |
| 原 C、D | 暂无新任务 | 保留报告与证据 | 等待最终 source，不重复 overlap/Gemma 探针 |

三个任务可以现在交付。A3/B3 使用原会话；E 如为新会话，从磁盘读取索引与任务书，不依赖会话记忆。

## 依赖和写入归属

1. A3只读source/ledger/raw/run，仅记录已完成核验和交付必要小文件，不重建历史结果。历史执行不能用当前工作树冒充。
2. B3 是当前共享实现和资产配置的唯一写入者，不修改 A2 审核脚本、source、ledger、旧 run。
3. E继续在 `.codex-temp/paper1_source_recovery_v2/` 独立处理新候选/临时转换/新增审核；A3交付已完成，不再等待A3。E进入共享实现修改、正式source/config发布、最终测试和prepare前，读取B3的 `B2_DELIVERY_READY` 报告并确认其停止写代码。交接后E成为相关代码/source唯一写入者。
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

E 通过后，下一阶段是最终 E1 overlap/40 条选择、必要的真实 runtime/smoke 核验，再进入 Core directions/screen。C 届时继续；D 无须重复已通过的零剂量探针。正式运行不在本轮授权范围。所有后续任务必须遵守 `paper1_experiment_design_immutability_audit_20260915.md`。
