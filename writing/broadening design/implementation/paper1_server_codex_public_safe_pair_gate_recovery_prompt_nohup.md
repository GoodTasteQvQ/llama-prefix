# Public safe-pair gate 恢复任务书

版本：`public-safe-pair-gate-recovery-v1`
对应设计：`MBD-NM v2.1.1-public-pairs`（如确需扩大 source 范围，先登记一个新的设计 revision）
执行位置：`/data/goodtaste_workspace/llama-prefix`
执行者：实验室 Linux 服务器上的 Codex
任务状态：当前正式实验被 `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS` 阻塞

执行前置：本任务必须等待 `paper1_safe_pair_review_quality_audit_report.md`。若审核质量审计
结论为 `REVIEW_MECHANISM_INVALID` 或 `REVIEW_MECHANISM_CONCERN`，本任务不得启动；只有审计
结论为 `REVIEW_MECHANISM_PLAUSIBLY_VALID`，或负责人另行批准新的审核协议后，才可继续。

## 0. 目标与硬边界

纠偏报告已经确认：原公开 source 有 416 对，排除 exact overlap 后有 409 对 preliminary
eligible，经 `public-semantic-pair-quality-v1` 的双 subagent 一致审核只有 194 对 executable，
`actual_k=min(80,(194-100)//5)=18`。当前不能开始 directions、screen、generation、Judge、
analysis 或 human packet。

本任务只负责恢复 construction 数据 gate：在保留现有 194 对及其全部证据的前提下，寻找并整合
可追溯的公开 paired source，完成新增 pair 的双 subagent 质量审核和离线 `prepare`。只有最终
executable pair 数量至少 250 且 `actual_k>=30`，才报告 `READY_FOR_CONSTRUCTION`。即使通过，
本任务也立即停止，不启动任何模型实验。

以下规则不可通过本任务改写：

- 不降低 `k>=30`、`k=min(80,(N-100)//5)`、development=100 或五折规则；
- 不修改、重审、覆盖或删除旧 416-row source、旧 194-row ledger、旧 run 或
  `data/safe_pairs.json`；
- 不把旧 AI 生成的 `data/safe_pairs.json`、JBB、HarmBench、新生成文本或实验结果拿来补齐；
- 不根据模型结果挑选 pair，不放宽 `include` 判定，不把机器审核写成 human validation；
- 不改变模型、层、hook、chat template、decoder、rho 网格、seed、预算或 E1/E2/E3 范围；
- 不启动 GPU 模型加载、directions、dose screen、generation、Judge、analysis 或 human 审核。

新增 source 会改变正式 construction source 的范围。若要把新增 source 纳入正式实验，必须
先写一份最小修订记录
`writing/broadening design/review/paper1_public_safe_pair_source_expansion_revision.md`，登记
新的设计 revision（建议 `MBD-NM v2.1.2-public-pairs-expanded`）。该记录只能改变 source
集合、source identity 和 provenance，必须明确预算、prompt、模型、层、fold、审核规则和 gate
均不变；完成一次边界自审后才能复制 run-specific config。不得静默修改已审阅的 v2.1.1 设计或
canonical config。若无法找到合格 source，保持阻塞并报告所需的科学决策，不要强行继续。

## 1. Linux 环境与串行 nohup

所有命令在服务器执行：

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

校验、转换、pytest、subagent 审核合并和 `prepare` 必须使用 `nohup`，并保存 PID、日志和
`.exit`。一次只运行一个后台步骤，等待 PID 退出并读取 `.exit` 后再开始下一步。可复用：

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

不要使用裸 `python`、未设置项目内临时目录的 pytest，或任何 HF 下载命令。不要 `reset --hard`、
`checkout`、覆盖式 `pull`、清理用户文件或覆盖现有 run。

## 2. 开始前的取证和实现契约核对

先只读记录当前 branch、HEAD、dirty 状态、解释器版本和纠偏报告路径。确认
`writing/broadening design/report/paper1_public_safe_pair_forensic_correction_report.md` 与
其报告中列出的 source、ledger、frames digest 均可定位。

再检查当前代码和 run-specific config 是否真的支持以下两点：

1. `public-semantic-pair-quality-v1` 的完整 provenance（两个不同 agent、raw output、rationale、
   prompt revision、frame digest、时间和固定裁决）；
2. `safe_pairs_path` 指向公开 source，而不是 `data/safe_pairs.json`。

若 `_semantic_status`、schema 或 loader 仍只接受旧 revision，或 canonical config 仍是旧路径，
只做最小兼容修复：保留旧 `safe-pair-semantic-overlap-v1`，增加等价的
`public-semantic-pair-quality-v1` 检查；创建 run-specific config，不改 canonical config 的科学
字段。新增或修改代码必须增加针对性离线测试，并在报告记录文件、diff、commit/dirty 状态。若无法
证明旧 ledger 与当前 schema 一致，停止并报告 `BLOCKED_REVIEW_SCHEMA_MISMATCH`。

## 3. source manifest 与新增公开 paired source

### 3.1 既有 source 的修复性核对

核对 `data/external/semantic_harmful_harmless_v1/source/` 的文件、URL、精确 revision、README、
许可证和 SHA256。纠偏报告已经证明两个 LICENSE 的差异只是 CRLF/LF；不得改写原始 source 文件。
若采用报告生成的 LF-canonical 修复候选，另存一个新的 manifest revision，保留旧 manifest 和
补丁，并在报告说明“只修正 manifest 的换行规范化 hash”。没有可核对的 source bundle 时，写
`BLOCKED_SOURCE_BUNDLE_MISSING` 并停止。

### 3.2 新 source 的准入条件

只从本地已有文件、GitHub 或 ModelScope 获取公开 source；服务器禁止访问 Hugging Face。候选
必须已经由上游提供 prompt-level 的一一对应 harmful/harmless pair，或明确的 pair id/两侧
source index；不得重新做 embedding matching、随机配对、翻译、改写、截断、拼接或 LLM 生成。
每个候选 source 必须能保存：原始 URL、不可变 commit/tag/revision、下载时间、README/data
card、许可证原文、上游许可字段是否缺失，以及原始文件 SHA256。

新增 rows 还必须满足：英文、两侧非空字符串、pair identity 唯一、两侧文本各自唯一、没有与
JBB100/JBB40/benign30 或既有 public source 的 normalized exact overlap。近邻只进入审核队列，
不自动排除。不能为了凑数量无限搜索：至多评估两个新增 source bundle，并在达到 gate 后立即
停止；若两个 bundle 仍不足，报告阻塞并等待设计决策。

### 3.3 保持旧 ledger 可复用的整合方式

生成新的版本化输出（例如 `data/safe_pairs_public_semantic_v2_expanded.json`）和
`data/external/.../integration_manifest_v2.json`，不得覆盖 `data/safe_pairs_public_semantic_v1.json`
或旧 manifest。输出中前 416 行必须与既有 public v1 的 harmful/harmless 文本和顺序逐字一致，
以便 `safe-pair:0` 到 `safe-pair:415` 的旧决策仍指向同一行；新增 rows 只能追加，使用全局唯一的
dataset/revision/index metadata。合并脚本必须可重复，记录输入文件和转换代码 commit。

若服务器工作区缺少 `data/safe_pairs_public_semantic_v1.json`，可以先用已核验的 v1 source bundle
和既有整合脚本重建它，再逐字逐行核对纠偏报告中的旧输出 hash；核对失败时停止，不得用
`data/safe_pairs.json` 代替。重建的 v1 文件另存并在报告标明来源，不覆盖任何旧 run。

不要把“找到 56 个新 row”当成已经获得 56 个 executable。最终数量以新增双审核完成后的固定裁决
为准；达到 250 即停止追加 source，不为追求更大的 N 继续扩展。

## 4. 离线测试

在任何 `prepare` 前运行：

```bash
launch_nohup public-safe-pair-gate-tests "$MBD_PYTHON" -m pytest \
  tests/paper1_broadening -q -p no:cacheprovider \
  --basetemp "$TMPDIR/public-safe-pair-gate-tests"
```

测试必须覆盖新增 source 的旧行稳定性、追加行唯一性、manifest/hash 校验、双审核 provenance、
动态 `k` 和角色隔离。测试失败、退出码非零或 schema 不完整就停止；不得删测试、放宽断言或继续
`prepare`。

## 5. 新增 pair 的双 subagent 审核

只对新 source 中 `preliminary_include=true` 的 rows 审核。每一条启动两个彼此隔离的 Codex
subagent：A 不得看到 B 的输出，B 不得看到 A 的输出；二者不运行代码、不访问网络、不写仓库，
只读取该 pair 和固定 evaluation frame 摘要。主会话保存两份原始 JSON、实际 agent/thread id、
model、UTC 时间、输入 frame digest、prompt revision 和 rationale。

固定提示版本：`public-semantic-pair-quality-v1`。每个 subagent 只返回一个 JSON：

```json
{
  "pair_id": "safe-pair:416",
  "verdict": "include|exclude|uncertain",
  "harmful_is_materially_unsafe": true,
  "harmless_is_materially_benign": true,
  "semantic_pair_is_comparable": true,
  "evaluation_overlap_checked": true,
  "rationale": "简短、基于文本的理由",
  "prompt_revision": "public-semantic-pair-quality-v1"
}
```

只有双方都 `include` 才固定写 `decision=include`；任一 `exclude` 或 `uncertain` 写
`decision=exclude`。调用失败、原文丢失、agent id 重复、JSON 非法、frame digest 不一致或
prompt revision 不一致时保持 `PENDING_SEMANTIC_REVIEW` 并停止。不得修改旧 409 条 ledger；新增
ledger 以新目录保存，并在合并文件中明确旧/新增记录边界。机器审核结果只能写成
`dual_codex_subagents_v1`，不能称为人工验证。

`include` 必须同时满足：harmful 有实质安全风险；harmless 不促进高风险行为；两侧任务/主题
结构可比较；与 evaluation frames 的 exact/near overlap 已检查。仅共享词或风险类别不自动构成
overlap，无法判断时使用 `uncertain`。

## 6. 重新 prepare 与 gate

审核 ledger 完整且 tests 通过后，创建新的 run-specific config。除 source path、ledger path 和
必要的设计 revision 外，不得改变科学字段。使用新 run id 串行运行：

```bash
MBD_WRAPPER="$PWD/scripts/run_paper1_broadening_single_gpu.sh"
MBD_CONFIG="$PWD/.codex-temp/mbd_public_safe_pairs_expanded_config.json"
launch_nohup public-safe-pair-gate-prepare bash "$MBD_WRAPPER" prepare \
  --config "$MBD_CONFIG" \
  --run-id "public-safe-pair-gate-$(date -u +%Y%m%dT%H%M%SZ)"
```

读取实际 run directory 和 JSON 产物，独立重算并记录：

- source_count、preliminary eligible、双方审核完成数、include/exclude/uncertain/失败数；
- `executable_eligible_count>=250`、`actual_k>=30`；
- 前 416 行与旧 source/ledger 的 identity 稳定；
- 五个 construction folds 各为 `actual_k`，development 恰为 100，二者互斥；
- exact overlap、near-match queue、排除理由、source/manifest/integration hash 均可追溯；
- resolved config、frames、review ledger、代码 commit/dirty state 引用一致。

任一条件不满足时最终 gate 必须保持 `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`、
`BLOCKED_SOURCE_BUNDLE_MISSING` 或相应明确阻塞状态。不得降低门槛、把 preliminary 当 executable、
把 194 条旧记录与新记录重复计数，或在结果不理想时换 source/换规则。

## 7. 报告、边界审查与停止

保存新报告：

`writing/broadening design/report/paper1_public_safe_pair_gate_recovery_report.md`

报告必须包含 branch/HEAD/dirty、实际命令/PID/log/`.exit`、解释器和离线设置；旧与新 source
的 URL/revision/license/hash；整合映射和旧行稳定性；双 subagent 的数量、provenance 和固定
裁决；prepare run directory、独立计数、`actual_k`、fold/development 隔离、最终 gate；实际
pytest 结果；明确 `FORMAL_EXPERIMENTS_NOT_RUN`。

完成后做一次有边界的自审，只检查：source provenance 是否完整、旧 ledger 是否未改写、计数公式
是否正确、role isolation 是否通过、代码/配置是否仍符合 v2.1.1（或明确记录新的 revision）、
以及是否误启动了下游实验。自审不新增实验块、不扩大样本到 gate 之外、不重写设计结论。若自审
发现任何问题，报告失败和阻塞原因并停止。

不要 `git commit` 或 `git push`，除非实验负责人另行授权；不要删除 `.codex-temp` 审计证据，
不要提交模型权重、缓存或私密文件。
