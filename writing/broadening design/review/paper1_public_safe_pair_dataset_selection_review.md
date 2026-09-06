# 公开 safe-pair 数据集选择与整合任务书审阅

日期：2026-09-06  
对象：`public-semantic-pairs-integration-v1` 任务书  
审阅结论：`PASS_WITH_DISCLOSURE`

## 结论

推荐把 `heretic-org/Semantic-Harmful` 与配套的 `heretic-org/Semantic-Harmless` 作为本实验
safe-pair construction 的公开替代源。它是当前候选中唯一同时满足以下核心接口约束的选择：

- 直接提供一一对应的英文 harmful/harmless prompt 对；
- 公开固定 revision 和配对元数据；
- 元数据包含原始索引、相似度、阈值、matching strategy 和 seed；
- 配对数据规模足以在现有动态规则下形成五折 construction 和 100 条 development；
- 不需要服务器访问 Hugging Face 模型或重新运行 embedding matching；
- 配对文件体积小，可以随 source bundle 通过 GitHub 同步。

这不是“已人工验证”的数据集。配对仓库说明了语义匹配过程，但没有逐条独立的人类安全
标注；其上游 `mlabonne/harmful_behaviors` 与 `mlabonne/harmless_alpaca` 的许可字段也不
完整。因此任务书要求双独立 Codex 机器质量审核、保留 source/raw/hash，并要求论文中如实
称为机器辅助审核。若研究目标或投稿 venue 要求人工安全标注，仍需另行安排人工抽样或全量
审核，不能把本任务的结果升级为 human validation。

## 数据事实核验

通过 Hugging Face 数据卡、固定 revision 的 README 和 `metadata/matched_pairs.json` 核验：

| 项目 | 结果 |
|---|---|
| `Semantic-Harmful` revision | `001ca2ceaef94a748235e0ba1366aee48436e286` |
| `Semantic-Harmless` revision | `7e9f2b01272da85f2be7a3437f31ac46698e8735` |
| 配对数 | 416 |
| metadata `num_matched_pairs` | 416 |
| matching | normalized embeddings + Hungarian |
| embedding model | `google/embeddinggemma-300m` |
| threshold / seed | `0.6` / `42` |
| score min / mean / max | `0.61794` / `0.71760` / `0.86764` |
| 配对仓库许可证 | CC-BY-4.0（README/数据卡声明） |
| 多语言版本 | 不采用，避免翻译质量和额外数据工程 |

本地与现有 evaluation frame 的预检结果：harmful 侧 exact overlap 7 条，harmless 侧 exact
overlap 0 条；按现有 token Jaccard/containment 候选规则，harmful 侧 45 条、harmless 侧 2
条进入 near-match 候选。这些数字只是预检，不是语义裁决；任务书要求逐条双 subagent 审核。

## 候选排除理由

| 候选 | 不作为本次 construction source 的原因 |
|---|---|
| HarmBench | 主要是 harmful behavior evaluation，不提供配套 harmless prompt，不能直接构造 pair |
| XSTest | 有明确 safe/unsafe 标签，但只有 450 条且不是一一对应 pair；unsafe 数量不足现有 split |
| WildJailbreak | 有 benign/harmful contrast 类型，但数据集 gated、体量接近 262K，超出本任务的最小整合范围 |
| PKU-SafeRLHF | 主要是 prompt + response 安全偏好，不是 prompt-level harmful/harmless pair；许可也有 NC 限制 |
| WildGuardMix | 有 prompt harmfulness 标签但不是配对源，且数据集 gated |
| AI 生成 `data/safe_pairs.json` | 无上游 revision、生成记录、许可证和独立质量证明，保留为 exploratory/backup |

## 边界审计

任务书已经明确：

- 不覆盖旧 safe pairs、旧 prepare 和旧 run；
- 不改变正式实验科学参数；
- source bundle 缺失、配对不一致、许可/哈希不可追溯时停止；
- 不用旧 AI pairs、JBB 或 HarmBench 自动补齐；
- 416 条在审核前理论最大 `k=min(80,(416-100)//5)=63`，审核后必须再次核对 `k>=30`；
- 所有测试和 prepare 使用项目内临时目录并通过 `nohup`、PID、日志和 `.exit` 记录；
- `READY_FOR_CONSTRUCTION` 只代表数据 gate，不触发 directions、screen、generation、Judge 或 analysis；
- 机器审核保存原始输出、两个独立 agent id、prompt revision、frame digest 和时间，不能写成人工验证；
- 新 `public-semantic-pair-quality-v1` revision 只允许最小 schema/gate 扩展，并保留旧 revision 兼容性。

## 残余风险

1. `Semantic-Harmful` 的 416 个 harmful 行来自公开上游，但上游数据卡许可字段缺失；报告应
   原样披露，并在论文投稿前由作者/机构确认许可可用性。
2. embedding 相似度不等于安全正确性；例如 harmless 数据中可能存在边界或双用途表达，故
   需要双 subagent 质量 gate。机器审核仍不能替代人工审核。
3. 416 少于原 AI pairs 的 500，construction fold 的最大 `k` 会从 79 降到 63；这是可解释的
   设计内动态变化，若审核后 `k<30` 必须停止，不能为了维持预算扩展数据或改参数。

## 审阅决定

任务书在上述披露和停止条件下通过，可以交给服务器 Codex 执行 source bundle 校验、转换、
双机器质量审核、离线测试和重新 prepare。执行完成后应先审阅服务器报告，再决定是否把新
数据正式用于 directions；本任务书本身不授权正式实验运行。
