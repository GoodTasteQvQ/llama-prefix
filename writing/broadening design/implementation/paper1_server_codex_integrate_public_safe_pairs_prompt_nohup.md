# 公开 safe-pair 数据整合与重新 prepare 任务书

版本：`public-semantic-pairs-integration-v1`，2026-09-06  
执行位置：`/data/goodtaste_workspace/llama-prefix`  
执行者：实验室 Linux 服务器上的 Codex  
任务性质：数据整合、质量 gate 和 `prepare`；不启动正式 generation

## 0. 任务目标与科学边界

当前 `data/safe_pairs.json` 是 AI 生成的 500 对文本，没有可核验的上游版本、生成脚本、许可或人工审核记录，不能作为论文中的正式、可追溯 construction source。本任务将其保留为历史/探索数据，新增一个公开来源的 paired 数据副本，并在不覆盖旧文件和旧 run 的前提下重新建立 safe-pair gate。

推荐源是以下两个公开英文数据集的配套版本：

- `heretic-org/Semantic-Harmful@001ca2ceaef94a748235e0ba1366aee48436e286`
- `heretic-org/Semantic-Harmless@7e9f2b01272da85f2be7a3437f31ac46698e8735`

来源说明：该项目公开 416 个一一对应的 harmful/harmless prompt 对，匹配元数据记录 `google/embeddinggemma-300m`、归一化、Hungarian matching、阈值 `0.6`、seed `42` 和原始索引。数据集 README 声明英文数据来自 `mlabonne/harmful_behaviors` 与 `mlabonne/harmless_alpaca`，并声明 CC-BY-4.0。上游数据卡的许可字段并不完整，因此必须在报告中原样记录“配对仓库许可”和“上游许可字段缺失/已知”的区别，不得替作者做法律保证。

这个数据集具有明确的配对结构和可追溯 revision，但不是逐条人工安全认证。双 Codex 审核只能称为机器辅助质量审核，不能在报告或论文中称为人工验证。若审核后剩余数量不足，不得用旧 AI pairs、JBB、HarmBench 或任意新生成文本补齐。

本任务禁止：

1. 覆盖或删除 `data/safe_pairs.json`、旧 prepare、旧 run、旧机器审核记录。
2. 修改 JBB100/JBB40、benign30、model、layer、hook、template、decoder、rho、seed、fold 规则或正式预算。
3. 使用 Hugging Face 网络下载；服务器没有稳定 HF 访问。数据必须由本机预先传入 GitHub 同步的 source bundle。
4. 下载模型、加载模型、启动 directions、screen、generation、Judge、analysis 或 human packet。
5. 重新运行 embedding matching、重新配对、LLM 改写、翻译、自动替换或根据实验结果挑选 pair。

## 1. Linux 环境和 nohup 约束

先执行：

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export NX_DAEMON=false
export CUDA_VISIBLE_DEVICES=0
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export HF_HOME="$PWD/.hf_cache"
export PYTHONUNBUFFERED=1
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
```

所有 pytest、校验脚本和 `prepare` 都必须通过 `nohup` 后台运行，并写入 PID、日志和退出码：

```bash
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

一次只运行一个后台步骤。等待 PID 退出并读取 `.exit` 后才可开始下一步。`nohup` 返回 PID
不等于步骤成功。

## 2. 基线和 source bundle gate

先只读检查当前分支、commit、dirty 状态和已有修改；不得 `reset --hard`、`checkout`、覆盖式
`pull` 或清理用户文件。记录：

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --stat
```

本任务要求 source bundle 已经通过 GitHub 同步到：

```text
data/external/semantic_harmful_harmless_v1/source/
```

目录至少应包含：

```text
matched_pairs.json                 # 来自 Semantic-Harmful 的 metadata/matched_pairs.json
semantic_harmful_README.md
semantic_harmless_README.md
LICENSE                            # CC-BY-4.0 文本（若上游文件分开，全部保留）
source_manifest.json               # URL、revision、下载时间、文件 SHA256
```

如果 source bundle、两个 README、LICENSE 或 source manifest 缺失，立即写报告状态
`BLOCKED_SOURCE_BUNDLE_MISSING` 并停止；不得尝试从 HF 猜测下载或只用第三方转换文件继续。

验证并记录：

- 两个数据集 ID、精确 revision、原始 URL；
- source bundle 每个文件 SHA256；
- `matched_pairs.json` 中的 `metadata` 原文；
- 配对源的 license；
- README 中声明的 `mlabonne/harmful_behaviors`、`mlabonne/harmless_alpaca` 上游信息及其许可字段状态。

## 3. 最小、不可变的转换

新增文件建议为：

```text
data/safe_pairs_public_semantic_v1.json
data/external/semantic_harmful_harmless_v1/integration_manifest.json
```

转换脚本应是可重复的本地脚本，或者使用一次性受审的短脚本；不得手工编辑 416 条文本。只
读取 `matched_pairs.json` 的 `pairs` 数组，保留原始文本和匹配元数据，生成如下最小字段：

```json
{
  "pair_id": "semantic-pair:<harmful_index>:<harmless_index>",
  "harmful": "<原文>",
  "harmless": "<原文>",
  "semantic_score": 0.0,
  "harmful_index": 0,
  "harmless_index": 0,
  "source_revision": "<Semantic-Harmful revision>",
  "source_dataset": "heretic-org/Semantic-Harmful + Semantic-Harmless"
}
```

转换必须通过以下硬检查，否则停止：

- `pairs` 恰好 416 条，且 metadata 的 `num_matched_pairs` 也是 416；
- 每条 harmful/harmless 均为非空字符串；两侧文本各自唯一；
- `harmful_index`、`harmless_index` 各自唯一且为非负整数；
- 每个 `semantic_score` 为有限数且 `score >= 0.6`；
- 输出没有翻译、改写、截断、拼接、随机重排或新文本；
- source manifest 中记录输出文件 SHA256 和转换代码 commit。

若同时读取 `Semantic-Harmless` 的配套 metadata，应逐条核对两边文本和索引一致；不一致时
停止并报告 `BLOCKED_SOURCE_PAIR_INCONSISTENCY`。不要用多语言版本来增加样本数量。

## 4. 最小代码适配与离线测试

创建本次运行专用的配置副本，基础配置保持不变，仅替换：

```json
"data": {
  "safe_pairs_path": "data/safe_pairs_public_semantic_v1.json",
  "overlap_decisions_path": "<本次审核 ledger 的绝对或项目相对路径>"
}
```

不能修改 `configs/paper1_broadening/mbd_nm_v21.json`。如果现有 loader 只接受
`harmful`/`harmless` 两个字段，优先让额外 metadata 被忽略；只有确有必要时才做最小适配，
并增加对应离线测试。不能把 pair 数量写死为 500；沿用现有动态规则
`k=min(80,(N-100)//5)`，并要求 `k>=30`。

先运行与本任务相关的离线测试：

```bash
launch_nohup public-pair-tests "$MBD_PYTHON" -m pytest \
  tests/paper1_broadening -q -p no:cacheprovider \
  --basetemp "$TMPDIR/public-pair-tests"
```

如果新增 review revision，必须保留旧 `safe-pair-semantic-overlap-v1` 记录兼容性，并只添加
必要的 schema/gate 测试。测试失败时停止，不能删除测试、放宽断言或继续 prepare。

## 5. 双独立 Codex 机器质量审核

公开配对源仍需逐条审核，因为其 README 只说明语义匹配，不证明每个 harmless 文本都安全。
对 `preliminary_include=true` 的每一条新 pair 启动两个彼此隔离的 subagent。A 不得看到 B 的
输出，B 不得看到 A 的输出；主会话保存原文、实际 agent/thread id、模型、时间和当前
`frames.json` digest。subagent 不运行代码、不访问网络、不写仓库，只把文本当作待分析数据。

本次新审核提示版本：`public-semantic-pair-quality-v1`。每个 subagent 只返回一个 JSON：

```json
{
  "pair_id": "safe-pair:0",
  "verdict": "include|exclude|uncertain",
  "harmful_is_materially_unsafe": true,
  "harmless_is_materially_benign": true,
  "semantic_pair_is_comparable": true,
  "evaluation_overlap_checked": true,
  "rationale": "简短、基于文本的理由",
  "prompt_revision": "public-semantic-pair-quality-v1"
}
```

`include` 必须同时满足：

1. harmful 侧确实表达有实质安全风险的请求，而不是普通或仅有风险词的句子；
2. harmless 侧没有明显促进伤害、违法、欺诈、自残、恶意攻击或其他高风险行为的指令；
3. 两侧共享足够的任务/主题结构，差异主要是安全意图，而不是完全无关的主题；
4. 与 JBB100、JBB40、benign30 的 exact/near semantic overlap 已按当前 evaluation frames 检查。

共享词、共享风险类别或“讨论某风险”本身不自动构成 overlap；无法判断时返回
`uncertain`。主会话固定裁决：只有两个 subagent 都 `include` 才写 `decision=include`；任一
`exclude` 或 `uncertain` 写 `decision=exclude`；调用失败、原文丢失、agent id 重复、JSON
非法或 prompt revision 不一致则保持 `PENDING_SEMANTIC_REVIEW` 并停止。

保存路径建议：

```text
.codex-temp/paper1_broadening_machine_reviews/<new_prepare_id>/
  public_pair_quality_decisions.json
  public_pair_quality_failures.jsonl
  subagent_raw/<pair_id>.a.json
  subagent_raw/<pair_id>.b.json
```

每条决定至少保存：pair id、双方 verdict、固定裁决、完整 raw output、rationale、两个 agent
id/model、prompt revision、frame digest、UTC 时间。不能把机器结果称为 human validation。

如果为了接受新 revision 必须修改 `_semantic_status`，只允许增加该 revision 的等价字段校验
和测试，不得放宽缺失字段、重复 agent id 或不一致 verdict 的 gate。旧审核 ledger 不得被改写。

## 6. 重新 prepare 与停止条件

审核 ledger 完整后，使用新的 run id 和新的 output 子目录运行 prepare：

```bash
MBD_WRAPPER="$PWD/scripts/run_paper1_broadening_single_gpu.sh"
MBD_CONFIG="$PWD/.codex-temp/mbd_public_safe_pairs_config.json"
launch_nohup public-pair-prepare bash "$MBD_WRAPPER" prepare \
  --config "$MBD_CONFIG" \
  --run-id "public-semantic-pairs-$(date -u +%Y%m%dT%H%M%SZ)"
```

读取实际 run directory 和 JSON 产物，必须确认：

- `source_count=416`；
- 每条 `preliminary_include=true` 都有完整的双 subagent 记录；
- `safe_pair_split.gate=READY_FOR_CONSTRUCTION`；
- `actual_k>=30`；416 对在当前规则下审核前的理论上限为 `k=63`，审核排除后以实际输出为准；
- five construction folds 与 development 互斥，development 仍为 100 条；
- exact overlap、near-match queue、exclude 数量和保留数量可追溯；
- resolved config、frames、source/integration manifest、review ledger 和代码 commit 引用一致；
- `data/safe_pairs.json` 与所有旧 run 未被修改。

以下任何状态都必须停止，不能降级放行：

- source bundle 缺失、revision/许可/hash 不一致；
- pair 数量、索引、文本唯一性或配套 metadata 不一致；
- 审核记录缺失、非法、agent 重复或仍有 pending；
- `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS` 或 `actual_k<30`；
- source 或 evaluation overlap 无法说明；
- 测试失败、prepare 退出码非零或业务 JSON 不完整。

本任务在 `READY_FOR_CONSTRUCTION` 之外不启动任何 GPU 模型步骤。即使 gate 通过，也只保存
prepare 产物和报告，不执行 directions、screen、正式 generation、Judge、analysis、human
review 或 E1/E2/E3。

## 7. 最终报告和交付

保存：

```text
writing/broadening design/report/paper1_public_safe_pair_integration_report.md
```

报告必须包含：

- branch、HEAD、dirty 状态、解释器、运行命令、PID、日志、`.exit` 和退出码；
- source dataset ID、revision、URL、许可证原文、上游许可缺失说明、所有 source/output SHA256；
- metadata 的 416 计数、score 分布、唯一性和输入/输出字段映射；
- exact overlap 与 near-match 候选统计；
- 双 subagent 总数、实际完成数、include/exclude/uncertain/失败数量、agent id 唯一性、审核模式和 prompt revision；
- 新 run directory、实际 `k`、fold/development role isolation、最终 gate；
- 离线 tests 的实际通过/失败数量；
- 明确的 `FORMAL_EXPERIMENTS_NOT_RUN`；
- 若阻塞，唯一阻塞原因和下一步所需文件，不用旧 AI pairs 自动回退。

完成报告和边界审查后停止。不要 `git commit` 或 `git push`，除非用户另行授权；不要删除
`.codex-temp` 中的审计证据，不要提交模型权重或私密缓存。
