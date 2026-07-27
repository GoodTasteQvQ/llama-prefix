# Paper 1 Stage 3 Current Release

更新时间：2026-07-22

## 当前状态

- 唯一实验设计基线：`v3.5-rc2 + binding-amendment-01`
- 设计状态：`DESIGN-FREEZE-PASS`
- 运行状态：`RUN-BLOCKED`
- 正式实验数据：尚未产生
- 后续允许工作：E0、真实 identity/runtime manifests、生产管线实现和 implementation-fidelity audit
- 禁止事项：继续迭代协议版本、恢复已删除实验范围、把 fixture/verifier PASS 当作正式实验结果

本文件是后续 Codex 任务的唯一阅读入口，但不是新的规范层，也不覆盖任何冻结文件。

最终冻结裁决保存在：

`writing/archive/paper1_stage3_history/unbound_revision/paper1_attention_sink_mu_design_freeze_binding_amendment_01_partial_witness_final_audit.md`

该终局审计给出 `DESIGN-FREEZE-PASS / RUN-BLOCKED`。amendment manifest 和聚合 verifier
仍显示审计前锁定的 `DESIGN-FREEZE-CANDIDATE / RUN-BLOCKED`，这是预期的不可变历史状态；
不得为了改写显示文本而修改或重建冻结 manifest。

## 实现时必须读取

按以下顺序读取；后项只在明确冲突范围内覆盖前项：

1. 基础协议：
   `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc2.md`
2. 绑定修正：
   `writing/stage3 design/revision/paper1_attention_sink_mu_experiment_design_v3_5_rc2_binding_amendment_01.md`
3. 基础执行契约和统计参考：
   `writing/stage3 design/v3_5_rc2_contracts/`
   `writing/stage3 design/v3_5_rc2_statistics/`
   `writing/stage3 design/v3_5_rc2_closure/C/`
4. amendment 的 schema、manifests、README 和 fixtures：
   `writing/stage3 design/v3_5_rc2_binding_amendment_01/`
5. 与上述规范绑定的参考实现和 verifier：
   `scripts/stage3_rc2/`
   `scripts/stage3_design/v3_5_rc2/`
   `scripts/stage3_design/v3_5_rc2_binding_amendment_01/`

`binding-amendment-01` 只覆盖其明示的 `P0-STAT-01` 和 `P0-STAT-02` 统计绑定缺口。
它不是完整协议副本，也不得用于覆盖 v3.5-rc2 的其他条款。

## 不作为实现输入

除非任务明确要求追溯设计历史，否则不得读取或据此改变实现：

- `writing/judge subagent/`
- v1.0 至 v3.5-rc1 的旧协议正文
- 一般 revision brief、semantic diff、审计报告和 repair handoff
- `writing/archive/`
- Codex 对话提示词和临时裁决材料

其中一部分历史文件仍保留在原路径，是因为旧版 release verifier 将其哈希和路径作为冻结证据。
“保留在原路径”不代表它们是当前规范，也不授权 Codex 比较版本或重新设计实验。

## 规范优先级

出现冲突时按以下规则处理：

1. amendment 明示覆盖的两项统计绑定，以 amendment 的 schema、局部 README、参考实现和 golden fixtures 为准。
2. 其余实验范围、estimand、预算、状态和声明边界，以 v3.5-rc2 及基础 contracts 为准。
3. manifest 和 hash 负责身份绑定，不能被审计报告或 completion report 覆盖。
4. 审计报告只证明某次检查的结论，不定义新的算法或实验范围。
5. 仍无法确定时停止实现并登记 implementation-fidelity 问题，不得自行扩样、增加 endpoint 或修改协议。

## 当前运行阻断项

设计已冻结，但正式运行仍需关闭以下 A0/I0：

- 锁定真实 checkpoint、tokenizer、template、prompt frame、base anchors 和 vectors 身份。
- 按协议顺序生成不可覆盖的 identity/runtime/freeze manifests。
- 完成 E0 fixtures 和生产管线集成。
- 对生产代码进行 implementation-fidelity audit，并保存机器可读验证记录。

A0/I0 只能通过生成工件、实现代码和验证来关闭，不能触发 v3.5-rc3 或新的开放式 TDSC 设计审查。

## 验证命令

从仓库根目录 `D:\llama_prefix` 执行：

```powershell
$codexTemp = Join-Path (Get-Location) ".codex-temp"
New-Item -ItemType Directory -Force $codexTemp | Out-Null
$env:TEMP = $codexTemp
$env:TMP = $codexTemp
$env:NX_DAEMON = "false"
$env:PYTHONDONTWRITEBYTECODE = "1"

python -B scripts/stage3_rc2/verify_release.py
python -B scripts/stage3_design/v3_5_rc2_binding_amendment_01/verify_amendment.py
```

预期关键标记：

- base release：`"verdict": "DESIGN-FREEZE-PASS"`
- current aggregate：`AMENDMENT_STATIC_VERIFICATION_PASS`

`verify_release.py` 校验基础 rc2 的发行时冻结链，包含 28 个历史证据路径。
`verify_amendment.py` 是当前组合基线的最终聚合 verifier，并会调用两个 component verifier。
二者都不应重写 frozen manifests、schemas、fixtures 或 expected outputs。
新的运行回执应写入 `writing/stage3 design/verification_receipts/`，不得覆盖冻结工件。

## 给后续 Codex 的固定指令

```text
先阅读 writing/stage3 design/CURRENT_RELEASE.md，并严格遵守其中的读取范围和优先级。
只以 CURRENT_RELEASE.md 列出的 normative files、manifests、schemas、reference
implementations 和 fixtures 为实现依据。不要读取 writing/archive/、writing/judge subagent/
或旧协议/revision 来提出新的实验设计修改。

当前唯一基线是 v3.5-rc2 + binding-amendment-01。设计已经冻结；任务只允许完成 E0、
真实 identity/runtime manifests、生产管线实现和 implementation-fidelity 验证。
不得新增模型、prompt、vector、anchor、endpoint、response cell、human item、实验分支、
confirmatory test 或正式 claim。遇到 A0/I0 时生成协议已经要求的工件或实现；不得新建协议版本。

实现完成后，在项目本地 .codex-temp 下运行 base release verifier 和 amendment aggregate
verifier，并报告 exit code、关键 PASS marker 和仍未关闭的 A0/I0。不要修改任何 frozen
manifest、schema、fixture、expected output 或 verifier 来迎合实现结果。
```
