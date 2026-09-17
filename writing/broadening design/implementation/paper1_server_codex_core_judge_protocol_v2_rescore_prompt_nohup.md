# Core Judge protocol v2：4096 probe、批准门控 recovery 与一致性重评分

版本：`core-judge-protocol-v2-rescore-v2`；执行会话：`A-judge-v2`。

本任务把“确认 Judge thinking/输出边界问题、最小协议变更、独立 recovery 和一致性重评分”组织成一个连续任务，但保留三个硬批准闸门。负责人已经授权：若 4096 probe 证明协议变更合适，可以新增 v2.2 设计；这项授权不等于自动批准 probe、recovery 或 1,200 条重评分请求。服务器必须在每个批准闸门停止并保存报告。旧 run 和旧设计仍必须保留为历史 pilot，不能被覆盖。

## 当前事实与目标

`A-closure` 已完成只读取证收尾，结论为 `CORE_RECOVERY_FAILURE_CLOSURE_PASS`、`CORE_RECOVERY_BLOCKED`、`DESIGN_CHANGE_REQUIRED`。旧 F2 的 1,200 条 behavior generation 本身没有被判定为无效；问题集中在 Qwen3 Judge 的 thinking 输出没有到达 semantic `</think>` 边界，导致严格 JSON parser 将 13 条记为 missing。

目标是验证一个最小、可追溯的 Judge 协议修订：保留 `enable_thinking=true`、rubric、strict final JSON、模型/endpoint、float32、greedy、1 beam 和原 2% missing gate，只把 Judge 的 `max_new_tokens` 从 1296 改为预先登记的 4096，并使该值由新 run-specific config 驱动。behavior model 的 decoder 仍为原设计的 512；不重新生成 behavior completion。

## 必读输入

- `writing/broadening design/report/paper1_core_recovery_failure_closure_report.md`
- `writing/broadening design/report/paper1_core_recovery_execution_report.md`
- `writing/broadening design/report/paper1_core_screen_parse_forensic_report.md`
- `writing/broadening design/implementation/paper1_server_codex_post_audit_task_index.md`
- 三份原设计文件（只读历史基线）：
  - `writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md`
  - `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.1_readable.md`
  - `writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md`
- 旧 F2：`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`
- 旧 recovery：`results/paper1_broadening/paper1-core-fourclass-recovery-20260916-r13-a5a5936/`
- 现有 Judge 代码、配置和测试。

## 不可违反的边界

1. 旧 F2、旧 recovery、三份原设计、原 canonical config、旧 Judge ledger 和旧 dose decisions 全部只读；不得覆盖、合并、回写、删除、重命名或重新解释旧标签。
2. 不修改 safe-pair、JBB、benign、方向 tensor、层、family、rho、seed、rubric、parser 规则、2% gate、模型/endpoint 或 behavior generation decoder。
3. 新代码必须保留旧默认行为：未指定新 run config 时 Judge 仍为 1296；4096 只由新 run-specific config 使用。不得用全局常量替换旧行为。
4. 不使用 binary Judge，不启动 formal evaluation、E1/E2/E3 generation、analysis、human audit 或 A/S 之后的任何工作；本任务最多产出新的 Core screen Judge 结果和新的 dose gate。没有批准文件时不得发送 recovery 或全量重评分请求。
5. 不手工补标签、不从 completion 推断标签、不把 parse failure 转成有效类别。所有 raw、diagnostics、stop reason、token count 和 retry 都如实记录。
6. 不下载模型、不连接 Hugging Face、不升级现有环境、不使用双卡；模型和 Judge 单卡顺序运行。除本任务新增文件外，保留其他会话/用户工作树修改，不执行 reset、checkout 或清理。
7. 不 commit/push。服务器完成后只交付报告和证据，由负责人另行同步。

## Linux 与 nohup 前置

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
export CUDA_VISIBLE_DEVICES=0
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
```

每个检查、测试、probe 和正式重评分步骤都必须用 `nohup` 保存 PID、日志和 `.exit`；等待进程结束并核对业务 JSON 后才能进入下一步。启动 GPU 前确认 GPU 0 空闲和显存足够。

## 阶段 0：预检与最小实现适配（不发送 Judge 请求）

1. 记录 `git status --short --branch`、三份原设计和旧 F2/旧 recovery 关键文件的 SHA256；把执行前已有 diff 单独保存。
2. 先写入 `.codex-temp/paper1_core_judge_protocol_v2/proposal.md`，明确本次只改变 Judge `max_new_tokens=4096`，并说明旧 v2.1 是历史 pilot，不删除、不覆盖。
3. 将 Judge 的 max token 从硬编码改为 run config 参数，默认值保持 1296；阶段 0 只验证显式参数传递，不提前创建 4096 配置文件。`enable_thinking=true`、strict parser、rubric 和 semantic split 不变。
4. 增加最小离线测试，至少验证：默认仍为 1296；新配置传入 4096；实际 `generate()` 使用配置值；Judge identity/run header 记录该值；旧 parser/rubric/计数规则没有变化。
5. 用项目内环境运行聚焦测试、完整 `tests/paper1_broadening`、Python compile 和 `git diff --check`。若适配需要改变科学规则、旧结果或原设计正文，立即写 `DESIGN_CHANGE_REQUIRED` 并停止。
6. 保存 `PROPOSAL_WRITTEN` 和 `READY_FOR_PROBE_APPROVAL`，然后停止。固定批准文件路径为 `.codex-temp/paper1_core_judge_protocol_v2/PROBE_APPROVAL.md`；不存在或内容不完整时不得发送任何 probe 请求。批准文件必须明确：6 条固定 probe 输入、`enable_thinking=true`、`max_new_tokens=4096`、每条一次 four-class、binary/generation/额外 retry 均为 0、probe 非正式结果、旧 F2/recovery 只读，并在 probe run header 记录批准文件路径、SHA256 和写入时间。

## 阶段 1：4096 compatibility probe（第一道结果闸门；需先获 probe 批准）

1. 先验证 `.codex-temp/paper1_core_judge_protocol_v2/PROBE_APPROVAL.md` 存在且字段完整，再从旧 F2 generation ledger 固定 6 条只读输入，选择规则必须写入 probe manifest：3 条来自旧 13 条 parse failure（至少覆盖 qwen25 与 llama31、rogue 与 contrastive），3 条来自旧 F2 已成功解析的不同身份。不得按结果临时挑选。
2. 为 probe 创建全新目录，例如 `results/paper1_broadening/core-judge-protocol-probe-<UTC>-<shortid>/`；保存输入 completion/prompt hash、new config、runtime identity、request manifest、Judge records、raw/diagnostics 和 process evidence。
3. 每条只发送一次 four-class Judge 请求，使用 `max_new_tokens=4096`、`enable_thinking=true`；不使用 binary Judge，不做 generation retry 或额外 retry。probe 不是正式实验结果。
4. probe 通过条件必须同时满足：6/6 有 semantic `</think>`、strict final JSON、合法 domain label、非空 rationale；raw/diagnostics/hash/stop reason/token count 全部存在；无 OOM、无隐藏 retry、无跨 run 输入。
5. 任一条不满足条件时，保存 `JUDGE_PROTOCOL_PROBE_FAIL` 与 `DESIGN_CHANGE_REQUIRED`，不创建 v2.2，不进行 recovery 或全量重评分，任务停止。不要自动把 4096 提高到 8192 或更高；更高上限须另行 proposal。
6. 只有 6/6 通过才写入 `JUDGE_PROTOCOL_PROBE_PASS`，然后进入阶段 2。Probe 通过本身不授权任何额外请求。

## 阶段 2：版本化设计与配置（仅 probe 通过时；不发送 recovery 请求）

1. 从 v2.1 复制形成新文件：`writing/broadening design/paper1_minimal_broadening_experiment_design_v2.2_judge4096.md`。保留 v2.1 原文件不变，并在 v2.2 中明确：Judge 必须输出 strict final JSON，`enable_thinking=true`，`max_new_tokens=4096`；behavior generation 仍为 512；missing gate 仍为 2%。
2. 明确旧 F2/recovery 为 `PILOT_DESIGN_INSUFFICIENT_JUDGE_PROTOCOL`，仅作为历史尝试和输入证据；旧标签不进入新统计。
3. 新增 run-specific config，例如 `configs/paper1_broadening/mbd_nm_v212_public_expanded_judge4096_v22.json`，只改变 Judge decoder 字段并绑定 v2.2 revision。不得修改旧 canonical config 或旧 run-specific config。
4. 对 v2.2 文档、配置和实现做一次边界自审：改动仅限 Judge 预算/记录，不新增模型、数据集、方向、剂量或指标。自审结果写入最终报告。
5. 保存 `DESIGN_REVISION_V2.2_WRITTEN` 和 `READY_FOR_RECOVERY_APPROVAL`，然后停止。批准文件的固定路径为 `.codex-temp/paper1_core_judge_protocol_v2/RECOVERY_APPROVAL.md`；不存在或内容不完整时不得进入阶段 3。批准文件必须明确：
   - 新 recovery 的完整 `run_id` 和目录路径；
   - 最多 13 次 four-class Judge 请求、每条输入最多 1 次；
   - 使用 v2.2 Judge 4096、原 F2 的 prompt/frame/completion/rubric/parser/endpoint；
   - binary Judge=0、generation retry=0、额外 retry=0、原 2% gate 不变；
   - 旧 F2、旧 recovery、旧 Judge ledger 和旧 dose decisions 只读；
   - 批准文件路径、SHA256 和写入时间记录在 recovery run header。

## 阶段 3：新的独立 recovery（第二道闸门之后）

1. 只有阶段 2 完成且批准文件完整时，才新建独立 recovery run，例如 `results/paper1_broadening/core-judge-recovery-v22-<UTC>-<shortid>/`。
2. 只消费旧 F2 中原 13 条 `PARSE_FAILURE` 的 generation completion；每条发送一次 four-class Judge，固定 `enable_thinking=true`、`max_new_tokens=4096`，不做 generation retry、binary Judge 或额外 retry。保存 request manifest、输入/请求/响应 hash、raw、diagnostics、stop reason、token count、runtime/release、PID/log/exit 和 ledger。
3. 不读取旧 Judge label 作为新标签，不手工补标签，不与旧 1,187 条标签合并。13 条 recovery 是独立验证结果，不是新的 Core screen 结果。
4. 13/13 均满足 semantic `</think>`、strict final JSON、合法 label、非空 rationale 且完整证据存在时，写 `CORE_RECOVERY_V2_PASS` 和 `READY_FOR_FULL_RESCORE_APPROVAL`，然后停止。任一条失败时写 `CORE_RECOVERY_V2_BLOCKED`，不启动全量重评分。

## 阶段 4：Core screen 全量新 Judge 重评分（第三道闸门之后）

只有阶段 3 为 `CORE_RECOVERY_V2_PASS`，并且固定路径 `.codex-temp/paper1_core_judge_protocol_v2/FULL_RESCORE_APPROVAL.md` 存在且内容完整时才能执行。该批准文件必须写明新 run id/path、1,200 个 logical identity、Judge 4096、无 generation retry、无 binary Judge、原 2% gate 和旧文件只读。

1. 新建独立 run，例如 `results/paper1_broadening/core-screen-v22-judge4096-<UTC>-<shortid>/`。完整读取旧 F2 的 1,200 条 generation completion 作为只读输入，包含原 13 条失败项；不要读取旧 Judge label 作为新标签，也不要只重跑 13 条后与旧 1,187 条混合。
2. 按旧 F2 schedule 的 20 个 model/family/rho cell 全量发送 four-class Judge；新 Judge 设置固定为 `enable_thinking=true`、`max_new_tokens=4096`。沿用原设计的 parse/技术失败最多一次相同设置重试规则，retry 单独记账；不做 generation retry、不做 binary Judge。
3. 新 run 必须保存 1,200 个 logical identity 的 request manifest、每次 attempt 的 raw/diagnostics/stop reason/token count、canonical Judge ledger、运行身份/release、gate 输入和完整 hash 清单。每个 scheduled identity 都要有 terminal accounting。
4. 计算原 2% missing gate，只使用新 run 的新 Judge 结果。任一 cell 超过 2% 时写 `CORE_SCREEN_V2_BLOCKED`，不选择 A/S，不开始 formal evaluation。
5. 全部 cell 通过时，按原 A/S 选择规则生成新的 `dose_decisions_v2.json`，状态写为 `CORE_SCREEN_V2_PASS`、`CORE_A_S_READY_FOR_FORMAL_EVALUATION`。不要在本任务启动 Core formal evaluation 或 E1/E2/E3。

## 最终报告与停止条件

保存：`writing/broadening design/report/paper1_core_judge_protocol_v2_rescore_report.md`。

报告必须根据实际分支写出：

- 若执行 probe：`JUDGE_PROTOCOL_PROBE_PASS` 或 `JUDGE_PROTOCOL_PROBE_FAIL`；否则写 `JUDGE_PROTOCOL_PROBE_NOT_RUN`；
- 若 probe 通过：`DESIGN_REVISION_V2.2_WRITTEN`；
- 若尚未获得 probe 批准：`READY_FOR_PROBE_APPROVAL`；
- 若阶段 2 完成但尚未批准 recovery：`READY_FOR_RECOVERY_APPROVAL`；
- 若执行 recovery：`CORE_RECOVERY_V2_PASS` 或 `CORE_RECOVERY_V2_BLOCKED`；
- 若 recovery 通过但尚未批准全量重评分：`READY_FOR_FULL_RESCORE_APPROVAL`；
- 若执行全量重评分：`CORE_SCREEN_V2_PASS` 或 `CORE_SCREEN_V2_BLOCKED`；否则写 `CORE_SCREEN_V2_NOT_RUN`；
- `CORE_RECOVERY_FAILURE_CLOSURE_PASS`（历史证据状态，不冒充新结果）；
- `FORMAL_EVALUATION_NOT_RUN`；
- `OLD_F2_AND_OLD_RECOVERY_IMMUTABLE`。

列出实际 config/design/code hash、批准文件 hash、probe/recovery/全量 run id/path（仅列已执行阶段）、每阶段 logical/request/retry/missing 计数、gate 表、A/S 状态、GPU/runtime identity、所有 PID/log/.exit、实际改动文件和 pre-existing 工作树差异。不得用退出码 0 代替业务 PASS；未获批准的阶段必须写 `NOT_RUN`，不能预填 PASS。

完成报告后进行最终边界自审：旧 F2/旧 recovery/三份 v2.1 设计 hash 不变；新 v2.2 只包含批准的 Judge 协议修订；新 run 不混入旧 Judge label；没有 formal evaluation 或其他后续实验进程；任何未批准阶段没有请求或后台进程。自审失败写 `TASK_BOUNDARY_FAIL` 并停止。
