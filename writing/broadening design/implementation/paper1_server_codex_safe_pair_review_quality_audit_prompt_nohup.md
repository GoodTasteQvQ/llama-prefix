# Safe-pair 审核质量取证任务书

版本：`safe-pair-review-quality-audit-v1`
目的：判断现有 194 条 executable 是否由数据事实导致，还是由审核提示、输入、模型或合并机制导致。
执行位置：`/data/goodtaste_workspace/llama-prefix`
本任务性质：只读取证和有限诊断，不整合新 source，不运行正式实验。

## 1. 当前事实与停止原则

现有纠偏报告给出：409 条 preliminary eligible；reviewer A include=371，reviewer B
include=229；双方共同 include=194，双方共同 exclude=3，A-only=177，B-only=35。由此
observed agreement=197/409=48.17%，边际纳入率 A=90.71%、B=55.99%，Cohen's kappa 约
`-0.149`。这说明审核结果对 reviewer 身份高度敏感，不能仅凭 ledger 完整就视为质量 gate
有效。它可能是提示/上下文不一致、污染、实现 revision 漂移，也可能是数据边界本身含糊；本
任务必须区分这些解释。

任何情况下不得：修改旧 source、旧 409 条 ledger、旧 run 或 `data/safe_pairs.json`；重写
reviewer 结论；降低 `k>=30`；用新 source 补齐；启动 directions、screen、generation、Judge、
analysis 或 human packet。诊断标签不能写入正式 executable ledger。

## 2. Linux 与 nohup

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export NX_DAEMON=false
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export PYTHONUNBUFFERED=1
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
```

每个 shell 审计、统计脚本和 pytest 都通过 `nohup`，记录 PID、日志和 `.exit`；一次只运行
一个后台步骤。不要清理用户文件、不要覆盖旧报告、不要 commit/push。

## 3. 取证清单

先记录 branch、HEAD、dirty 状态、解释器版本、磁盘和当前任务进程。定位并只读核对：

- `writing/broadening design/report/paper1_public_safe_pair_forensic_correction_report.md`；
- 纠偏报告所指向的 `frames.json`、source bundle、旧 review ledger、A/B raw output 目录；
- ledger 中 409 条记录的 `review_prompt_revision`、`evaluation_frame_digest`、review mode、
  reviewer id/model、raw output、rationale、时间和 pair id；
- A/B raw 文件是否一一对应同一 pair，是否存在缺失、重复、截断、JSON 非法或错误 pair；
- 实际发送给 A/B 的完整 prompt、输入 frame 摘要/哈希、system/developer 约束、temperature、
  seed、模型 revision、上下文窗口和是否看到另一位输出。若这些原始请求没有保存，直接报告
  `BLOCKED_REVIEW_PROVENANCE_INCOMPLETE`，不要猜测。

特别核对 `public-semantic-pair-quality-v1` 是否真的包含四项判断：harmful 是否实质不安全、
harmless 是否确实 benign、两侧是否可比较、是否检查 evaluation overlap。若实际 prompt 仍是
只检查 overlap 的旧 `safe-pair-semantic-overlap-v1`，标记 `REVIEW_PROMPT_DRIFT`，不得把两者
当作同一协议。

## 4. 独立统计与偏差定位

用一次性只读脚本从 raw/ledger 重新计算，而不是只抄报告：A/B 总数、include/exclude/uncertain/
failure、双方混淆表、agreement、Cohen's kappa、每个 category/source/near-match strata 的
分歧率。检查 ledger 的最终 `decision` 是否严格等于
`unanimous_include_else_exclude`，并确认没有把 86 条 near-match queue 当成全部审核对象。

抽取至少 20 条 A-only、20 条 B-only（若数量不足则全部）、10 条双方 include 和 10 条双方
exclude 的 rationale，对照原 pair 和 evaluation frame，归类分歧原因：安全性判断、语义可比性、
overlap 定义、格式/截断、上下文污染或其他。只保存摘要和引用，不改写原 raw。

## 5. 有限可重复性诊断

只有在第 3 节确认原始 prompt/input provenance 完整后，才从上述分歧 strata 固定抽取 30 条
（A-only 10、B-only 10、双方 include 5、双方 exclude 5；不足时按实际数量报告）。为每条
启动两个全新的、彼此隔离的 Codex subagent，使用同一份冻结的诊断 prompt 和同一 frame digest；
A 不得看到 B 的输出，二者不得访问网络、运行代码或写仓库。诊断 revision 使用
`public-semantic-pair-quality-audit-v1`，不得写入正式 ledger。

保存每个 raw JSON、实际 agent/thread id、model、prompt/input hash、时间和失败信息。只统计
诊断重现率和分歧类型，不用诊断结论替换旧审核结论。调用失败、agent id 重复或 raw 缺失时停止
诊断并报告。

## 6. 结论分类

报告必须在以下分类中选择一个，并给出证据：

- `REVIEW_MECHANISM_INVALID`：发现 prompt/input drift、A/B 污染、raw/ledger 错配、模型/参数
  不同且未登记，或合并规则实现错误；原 194 条不能作为 gate，恢复任务书暂停，需先修复并
  重新审核受影响 rows。
- `REVIEW_MECHANISM_CONCERN`：provenance 完整但现有结果仍呈负 kappa/重大标准分歧，无法证明
  这是可接受的预先设计；原 ledger 保留但不能据此宣称高质量 gate，需负责人决定是否修订提示
  并重新审核。
- `REVIEW_MECHANISM_PLAUSIBLY_VALID`：provenance、输入、模型、合并规则均一致，诊断样本没有
  发现污染或实现错误，分歧可由 pair 边界解释。该分类仍不改变 194 条计数；恢复任务是否执行
  需在报告中明确“仍需新增至少 56 条 executable”，不能把它写成审核已证明正确。

不要自行发明新的纳入率阈值来把结果升级为 PASS。若原始请求证据缺失，优先使用
`BLOCKED_REVIEW_PROVENANCE_INCOMPLETE`。

## 7. 报告与停止

保存：

`writing/broadening design/report/paper1_safe_pair_review_quality_audit_report.md`

报告必须包含取证路径、原始/重算计数、混淆表和 kappa、prompt/input/schema 核对、有限诊断统计、
结论分类、旧 ledger 是否完全未改动，以及明确的 `FORMAL_EXPERIMENTS_NOT_RUN`。完成报告后
立即停止，不执行公开 source 恢复任务；只有负责人根据该报告决定下一步。
