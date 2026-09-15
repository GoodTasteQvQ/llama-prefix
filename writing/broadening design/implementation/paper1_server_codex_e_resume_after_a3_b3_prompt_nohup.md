# E4：恢复 safe-pair 来源整合与新增双审核

版本：`public-safe-pair-gate-recovery-v4`；日期：2026-09-15。交给 **原 E 会话继续**，不要新开重复来源调查。

先阅读：

1. `writing/broadening design/implementation/paper1_server_codex_post_audit_task_index.md`
2. `writing/broadening design/implementation/paper1_server_codex_public_safe_pair_gate_recovery_prompt_nohup.md`
3. `writing/broadening design/report/paper1_a2_evidence_handoff_report.md`
4. `writing/broadening design/report/paper1_b2_delivery_asset_wiring_report.md`
5. `writing/broadening design/review/paper1_experiment_design_immutability_audit_20260915.md`

A2专项核验已完成，A3已记录交付；B3已报告 `B2_DELIVERY_READY` 并停止共享代码写入。不要重复A2的818条独立性检查，不重审旧409条，不补审7条exact overlap。最终基线是221 executable、`actual_k=24`，至少需要29条新的 executable pairs。

## 只做以下工作

### 1. 固定并审查候选

继续使用 E 已下载的候选调查目录：
`.codex-temp/paper1_source_recovery_v2/candidate_research/`。

优先审查 `turkish-over-refusal-set` 的英文 safe/harmful 成对行：固定提交 `13682bf03c9e7805b81df2eab7e23fb2512e560b`，数据文件 hash 必须与 E 报告一致。逐行确认两侧均为英文、pair_id明确、原始配对关系真实；土耳其文行不纳入本实验。第二候选 `agentic-prompt-injection-boundary-pairs` 只有在第一候选通过结构/许可/语义接口且完整审核后仍不足时才启用，不因600 pairs的行数自动接受。

候选必须通过原任务书的公开来源、许可证、英文双侧、pair identity和非循环使用检查。不能把两张列表按行号配对，不能把safe/unsafe标签直接当本实验的harmful/harmless语义结论。

### 2. 冻结一批新增候选

在任何reviewer请求前，保存一份批次文件，包含：来源提交、原始文件hash、候选顺序、每个pair的原始source index、英文双侧文本、与旧416条及JBB100/JBB40/benign30的exact预检排除、入选和未入选ID。第一批最多100个新的preliminary eligible pairs；批次固定后不得按review结果换行或补行。

如果第一候选可提供至少29个合格新pair，第一批完成后即可停止，不启用第二候选。若不足，只有在第一批完整双审核结束后才能按原任务书启用第二候选，且第二候选同样最多100个、必须与旧416条和第一批全部行去重。不要为了凑数在批次中途停止。

### 3. 新增pair真实双审核

沿用已核验的 `public-semantic-pair-quality-v2` prompt和 `public-safe-pair-quality-ledger-v2` schema。每个新增pair启动两个真实、隔离的Codex subagent；A/B不共享结果，保存实际prompt、input hash、evaluation digest、thread/agent id、raw output和时间。真实请求失败或raw不一致时保持pending；不得用regex、embedding分数、本地模型批处理或旧ledger替代。合法exclude/uncertain不得为改变结论重试。审核主记录放 E 独立临时目录，保留原始raw。

双方都include才纳入；任一exclude/uncertain则exclude。旧A2的221条和其raw不可重新请求或改写。审核工作可以在B3交接完成前进行，因为只写独立临时目录；不得改共享代码、设计正文、旧source、旧ledger或旧run。

### 4. 交接后合并与gate

新增审核完成后，确认 B3 报告和实际代码交付已可读取且 B3 不再写共享代码，再接手必要的最小脚本/config适配。不得修改 `paper1_minimal_broadening_experiment_design_no_mistral.md`；如果发现必须改变模型、层、预算、split、判定标准或任何科学字段，立即停止并写 `DESIGN_CHANGE_REQUIRED`，不自行编辑设计。

将旧416行逐字保留，新增行只追加并记录来源revision、dataset、pair id和source index。依据完整raw生成新的versioned source/ledger/config；旧ledger、旧source和旧run不覆盖。离线测试只覆盖本次必要改动；不要重复未变化的A2/B3全套检查。若最终N<250，直接报告 `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`，无需运行必然失败的prepare；若N≥250且无pending，再按原任务书运行一次prepare并核对5 folds、development=100、`actual_k`和角色隔离。

### 5. 报告和停止

保存并更新：`writing/broadening design/report/paper1_public_safe_pair_gate_recovery_report.md`。报告必须说明候选来源、批次冻结、全部新增请求/attempts、ledger/gate、实际代码/config修改文件，以及“设计正文未修改”或 `DESIGN_CHANGE_REQUIRED`。记录命令、PID、日志、`.exit`；不commit/push，不加载模型，不运行directions/screen/generation/Judge/analysis/human packet。

完成一次边界自审，只检查：来源与配对真实性、批次是否预先固定、旧416/旧ledger是否未改、双审核证据、N/k和split计算、实现修改是否越界、是否误启动模型。修复任务内问题并复核；不可解决则保存阻塞报告。写 `FORMAL_EXPERIMENTS_NOT_RUN` 后停止。
