# Safe-pair 恢复后的当前任务入口

更新：2026-09-15，依据 `a5f5dd4` 的最终恢复报告。本索引替代此前顺序；旧A/B/A2/A3/B2/B3/E/E4任务均不重新执行。

## 当前决定

服务器报告safe-pair gate通过：516 source − 7 exact = 509 preliminary；旧221 + 新79 = 300 executable；5×40 construction + 100 development = 300，unused=0。无需新增来源或再次审核旧/新safe pairs。报告的 `READY_FOR_CONSTRUCTION` 仅是数据gate，尚未构造向量或运行正式generation。

本机仅同步报告，没有实际expanded代码/config/source/ledger/frames及来源修订文件。本轮做报告和已同步代码入口对照，不声称本机完成了服务器45项测试或独立复现300条。服务器可按以下任务继续，不等待异地文件打包。

## 只交付两个任务，可同时启动

| 会话 | 任务书 | 范围与停止点 |
|---|---|---|
| 原C会话，续作C2 | [最终E1重叠审核与40条选择](paper1_server_codex_e1_final_overlap_prompt_nohup.md) | CPU+真实双subagent，仅审核最终near-match候选，保存E1 ledger/40条名单和报告；不改共享实现、不prepare、不运行GPU |
| 原B会话（完成B3的会话），续作B4 | [新适配检查、代码交付与真实smoke](paper1_server_codex_post_recovery_runtime_handoff_prompt_nohup.md) | 检查E新增identity/config/snapshot适配，必要小修复/测试；复用充分的旧smoke证据或补做一次≤24 generation/4 Judge的core真实smoke；交付实际文件并停止 |
| 原E、A、D | 本轮无需新任务 | E完成；A证据沿用；D的Gemma探针不重复 |

若C/B原会话无法继续，可新开一个会话承接对应文件，不能同时让新旧会话做同一任务。C2和B4先独立工作；C2的E1结果交付后，B4只需做一次消费接口检查，不额外启动E1审核。

## 输入和并行归属

- 固定safe-pair输入：`data/safe_pairs_public_semantic_v2_expanded.json`、同前缀 `_ledger.json`/`.manifest.json`；config=`configs/paper1_broadening/mbd_nm_v212_public_expanded.json`。
- 数据型prepare：`results/paper1_broadening/public-safe-pair-recovery-v2-final-20260915T041534Z/`。保持其source、ledger、300个分配ID和原run不变；E1补全不回头改safe split。
- C2只读上述稳定文件及HarmBench原件。自己的脚本/数据输出写 `.codex-temp/paper1_e1_final_overlap/`，只写自己的报告，不import B4正在修改的模块；可在启动时复制所需脚本到自己目录。所有语义意见只读，不写共享实现。
- B4是本轮共享实现唯一写入者。只在CPU检查/小修复完成后运行smoke；执行期间代码保持稳定。E1消费者若需要最小schema适配，由B4处理；C2不并发修改frames.py。
- C2/B4各自使用新输出目录，已有同名结果保留另建子目录。不重跑恢复prepare，不对safe-pair再发review请求；缺项先定位，出现实际矛盾只报告受影响项。

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

C2报告：`writing/broadening design/report/paper1_e1_final_overlap_report.md`。
B4报告：`writing/broadening design/report/paper1_post_recovery_runtime_handoff_report.md`。

两份报告分别做一次任务内自审，有问题只修相关项并复核，不加新审计轮次。服务器不commit/push（用户另有明确授权则按其限定范围执行），不清理他人文件。将B4列出的实际代码/数据/配置/来源addendum和C2结果一起同步；raw留服务器，需要复核具体项再转移，不强制大包或双份备份。

C2通过、B4相关接口与runtime通过且实际运行文件可定位后，再交付方向构造→development screen→正式评估任务。现有 `build-directions` 可能自动构造E2/E3资产，下一轮须按其实际范围授权；本轮只调查该入口，不能偷偷执行它或通过设Gemma为空绕过。不会因smoke用了临时向量就声称正式contrastive方向已验证。
