# Core Judge protocol v2 rescore prompt review

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_judge_protocol_v2_rescore_prompt_nohup.md`

审查日期：2026-09-17；复审版本：`core-judge-protocol-v2-rescore-v2`。

## 结论

`REVIEW_PASS`。

## 边界检查

- 任务先做 4096 单值 probe，probe 失败即停止，不自动升级到更高上限。
- probe 通过后才创建 v2.2 设计和新配置；v2.1、旧 F2、旧 recovery 与旧标签保持只读。
- 阶段 0 只把 max token 参数化并验证默认值，不提前写入 4096 配置；因此 probe 是创建 v2.2 配置的真实前置条件。
- probe 本身也不自动启动：阶段 0 先等待可审计的 probe 批准；probe 通过不自动授权后续请求。13 条独立 recovery 和 1,200 条全量重评分分别要求可审计的负责人批准文件，未批准阶段必须停止并写 `NOT_RUN`。
- 三个批准接口已固定为 `.codex-temp/paper1_core_judge_protocol_v2/PROBE_APPROVAL.md`、`RECOVERY_APPROVAL.md` 与 `FULL_RESCORE_APPROVAL.md`，避免服务器把任意状态文件误当授权。
- recovery 结果通过后仍需全量重评分批准，因为最终 Core screen 不能混合 1296 与 4096 两种 Judge 协议的标签。
- 全量阶段对 1,200 条旧 generation completion 重新 Judge，避免将新旧 Judge 协议混合；没有重复生成 behavior completion 的不必要成本。
- rubric、parser、模型、数据、方向、剂量、gate 和 behavior decoder 均保持不变，科学变更仅限已授权的 Judge 输出预算与配置记录。
- 任务在 Core screen gate/A-S ready 后停止，不会越权启动 formal evaluation、E1/E2/E3、分析或人工审核。
- 明确保存 raw、diagnostics、stop reason、token count、PID/log/exit 和 hash，且要求服务器不 commit/push。

## 过度设计检查

- compatibility probe 仅 6 条，覆盖失败/成功历史输入和两种模型/两种 family，足以验证输出通道而不扩大实验规模。
- 不设置自动 8192/12960 级联，不新增 reviewer、数据集、模型、GPU 或统计指标。
- 全量 1,200 条是为了保证最终 Judge 协议一致性；复用冻结 generation completion 避免与 Judge 修复无关的重复 generation。先做 13 条 recovery 是用户要求的独立验证，且不将其结果混入旧 screen。
- 新增 v2.2 文件而不是覆盖 v2.1，保留 pilot 可追溯性。

## 审查结论

任务书与当前 A-closure 结论一致，条件闸门清晰，没有隐藏的追加请求、gate 放宽或旧结果回写路径，可交给服务器 `A-judge-v2` 会话执行。服务器第一次交付应止于 `READY_FOR_PROBE_APPROVAL`；没有 probe 批准文件不得发送请求，后续也必须分别等待 recovery 和全量重评分批准。
