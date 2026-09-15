# Core 方向完成后的下一步审阅

日期：2026-09-15。对象：C3、B5、F 报告及 Core dose screen 任务书。

## 结论

C3/B5 已将 E1 frame 绑定到最终 digest `d148...732a`，B5 的 run-specific config 只改变 E1 decision path；F 已完成 Qwen/Llama Core 方向和 `mu_content`，并通过单卡 runtime 检查。因此可以在服务器确认 F source snapshot 与当前源码字节一致后运行 Core development screen，且只到 A/S 剂量决策为止。

## 边界审查

- screen 固定为 1,200 generation：2 model × 2 family × 5 rho × 20 development prompts × 3 directions；不增加方向、剂量、prompt、模型或 phase。
- 只使用 decode_only 和 four-class Judge；不启动 binary Judge、JBB100、benign30、E1/E2/E3 或正式 evaluation。
- 复用 F run 的 frames/directions/source snapshot，不重做 prepare/build-directions；源码字节不匹配就停止。
- A/S 由现有 allocator 固定规则产生，完整保留五个 rho 的失败与 missing；不按结果重跑或手工挑剂量。
- Gemma release 序列化缺口不影响 Core screen；在 E2 正式运行前另行修复，不并行改 Core run 的共享源码。
- 本机根目录实现与服务器交付副本存在已知差异，screen 任务必须先做 source snapshot 字节校验；不一致时停止，不能把 B4 证据副本当作当前运行代码。

结论：`NEXT_TASK_DOCUMENT_REVIEW_PASS`。Core screen 完成并得到可用 A/S 后，下一任务是 Core harmful/benign evaluation -> Judge -> analysis；若 screen gate blocked，先修复直接运行问题并重新审阅，不运行正式 evaluation。

## 任务书自审结论

F2 只授权既定 Core development screen 的 1,200 个 logical generation 和 four-class Judge，复用已完成的方向与 calibration 资产，不增加模型、层、prompt、rho、方向或预算；B6 只读同步静态证据，不使用 GPU，也不修改运行目录。两项均要求 source snapshot mismatch 时 fail-closed，并明确禁止修改原实验设计正文、canonical config、C3 final 或既有 safe-pair 记录。报告、raw ledger、release 状态和 `.exit` 是必要交付，不能以 PASS 摘要代替。未发现冗余实验、开放式扩展或会改变科学问题的任务。
