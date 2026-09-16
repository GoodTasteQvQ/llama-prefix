# Core screen 阻断后的下一步审阅

日期：2026-09-16。对象：F2 Core dose screen、B6 静态交接及 F3/E2 两份任务书。

## 结论

F2 的 source snapshot、运行身份、generation/Judge 串行释放和 1,200 logical budget 均闭合；但 13 条 four-class `PARSE_FAILURE` 造成 Qwen/Llama contrastive cell 的 missing 超过 2%，所以 Core dose screen 未通过。Rogue A/S 结果只能作为局部描述，不能启动 Core 正式 evaluation，也不能让 E1 引用尚未完整的 Core dose gate。

## 下一步边界

- F3 只读定位和分类 13 条失败，不新增模型/Judge 调用，不改变 label 或 retry 规则；结果用于判断是否存在可证明的 parser/记录缺陷。
- E2 只读审计 Gemma release serialization gap，可并行；不加载 Gemma、不改 `directions.json` 或 F2 run。
- 在 F3 结论前，不允许修复后重跑 Judge、重做 1,200 screen、增加 rho、放宽 2% gate 或手工填补 missing。
- 只有 F3 明确证明实现缺陷并另行批准最小修复后，才可设计受限的恢复任务；若是不可解析 completion，保留 `CORE_DOSE_SCREEN_BLOCKED` 并提交科学/运行决策。

## 有边界自审

两份任务书只读取现有证据，输出具体报告和可选的 `.codex-temp` 草案；没有重复实验、扩大预算、修改科学设计或把 E2 提前当作正式结果。交付仍需保留 `FORMAL_EVALUATION_NOT_RUN` / `E2_FORMAL_EXPERIMENT_NOT_RUN`，并同步实际证据而非仅同步摘要。
