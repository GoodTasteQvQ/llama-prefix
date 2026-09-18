# Core Judge protocol v3: create the v2.3 direct-JSON design revision

执行会话：`A-judge-v3-design-revision`
协议：`core-judge-protocol-v3-direct-json`

R2 compatibility probe 已通过 6/6：`DIRECT_JSON_PROBE_PASS`，并记录为
`READY_FOR_V2.3_DESIGN_REVIEW`。本任务只创建一个版本化的设计副本和一个
run-specific config，供后续独立 recovery 审批使用；不加载模型、不发送 Judge
请求、不运行 recovery、full rescore、screen 或正式实验。

## 输入和保护边界

先读取并记录以下输入的 SHA256：

- `writing/broadening design/paper1_minimal_broadening_experiment_design_no_mistral.md`
- `writing/broadening design/paper1_minimal_broadening_experiment_design_v2.1_readable.md`
- `writing/broadening design/implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md`
- `configs/paper1_broadening/mbd_nm_v212_public_expanded.json`
- R2 报告及其 run 的 `final_boundary_audit.json`、`artifact_hashes.sha256`

以上文件只读。不要修改、覆盖、删除、重命名或回写 v2.1 设计、canonical
config、R2 run、旧 F2、旧 recovery、v2 probe、safe-pair 数据、方向资产或任何
历史 ledger。不要创建 recovery approval、full-rescore approval 或正式 run。

## 允许创建的两个文件

### 1. 设计副本

创建：
`writing/broadening design/paper1_minimal_broadening_experiment_design_v2.3_direct_json.md`

以 v2.1 科学设计为正文基础，保留原有问题、模型、数据、方向 family、层、
rho grid、A/S 规则、generation budget、统计指标、E1/E2/E3 规模和限制。只增加
一个明确标记的“Judge protocol revision”小节，内容为：

- R2 compatibility probe 已通过 6/6，仅证明协议可运行，不是正式结果；
- four-class Judge 使用 `enable_thinking=false`、`max_new_tokens=1296`、
  `strict_direct_json_v1`；
- 严格 JSON 必须恰好包含 `label` 和 `rationale`，label 合法、rationale 非空，
  拒绝 Markdown、额外文本、thinking marker、非法/缺失/额外字段；
- 不使用 regex 修复、substring 提取、手工标签、completion-derived label 或
  legacy parser fallback；
- binary Judge、generation retry、additional Judge retry、2% missing gate、
  rubric、模型、endpoint、tokenizer/chat template、dtype、greedy/beam 均不变；
- `runtime.decoder.max_new_tokens=512` 仍是 behavior generation 设置，与 Judge
  的 1296 相互独立；
- v2.1 与旧 probe 是历史记录，v2.3 尚未运行，不能把 R2 的六条输出写成科学
  结论。

在文件头标注新版本、来源 v2.1、R2 gate 和 `DESIGN_REVISION_V2.3_WRITTEN`。
不要重写 v2.1 正文或修改原文件的 hash。

### 2. run-specific config

创建：
`configs/paper1_broadening/mbd_nm_v212_public_expanded_judge_direct_json_v23.json`

从 `mbd_nm_v212_public_expanded.json` 复制，仅修改版本标识和显式 Judge 配置。
不要把下面的字段表当作独立 JSON 文件；实际文件必须保留 source config 的全部
字段和值：

| JSON path | v2.3 value | 约束 |
|---|---|---|
| `runtime.decoder.max_new_tokens` | `512` | 保持 source value，不得修改 |
| `runtime.judge.do_sample` | `false` | 保持 source value |
| `runtime.judge.enable_thinking` | `false` | direct-JSON protocol |
| `runtime.judge.max_new_tokens` | `1296` | direct-JSON protocol |
| `runtime.judge.num_beams` | `1` | 保持 source value |
| `runtime.judge.parser` | `strict_direct_json_v1` | 只使用这一 parser 字段 |

实际 JSON 必须保留源配置中的所有其他字段和值；不要同时写入不同的
`parser_mode` 字段，不要删除或修改 behavior decoder。建议版本标识为
`design_revision: v2.3-direct-json-1296`，并保留原数据、模型、方向、剂量和
预算字段。若现有 loader 对版本字段有固定命名，记录兼容性处理，但不改变科学
字段。

## 离线检查和报告

所有检查使用实验室 Python、单卡环境变量和 `nohup`，证据写入：
`.codex-temp/paper1_core_judge_protocol_v3/design_revision/`。保存 PID、日志、
`.exit`、输入/输出 hash 清单和最终边界审计。不得加载模型或发送请求。

必须检查：

1. v2.1 三份设计和 source config 创建前后 hash 一致；
2. v2.3 设计只新增 Judge protocol revision，没有改变科学规模或规则；
3. 新 config 与 source config 的字段差异只包含版本标识和显式 Judge protocol；
4. decoder 仍为 512，Judge 为 false/1296/strict_direct_json_v1；
5. JSON 语法、配置 loader、direct contract 和旧配置回归测试通过；
6. 不存在 recovery approval、full-rescore approval、v2.3 formal run 或新的
   Judge/raw 产物。

## 输出和停止

保存报告：
`writing/broadening design/report/paper1_core_judge_protocol_v3_design_revision_report.md`

报告必须包含：

- `DESIGN_REVISION_V2.3_WRITTEN`；
- `DIRECT_JSON_PROBE_PASS_REFERENCE_ONLY`；
- `CORE_RECOVERY_V3_NOT_RUN`、`CORE_SCREEN_V3_NOT_RUN`、
  `FORMAL_EVALUATION_NOT_RUN`；
- 两个新文件的 SHA256、输入 hash、config diff、测试 PID/log/.exit；
- 旧设计、canonical config、R2 run、旧 F2/recovery/v2 probe 的保护结果；
- `READY_FOR_RECOVERY_APPROVAL`。

若发现任何科学字段被迫改变、loader 不兼容或边界检查失败，写
`DESIGN_CHANGE_REQUIRED`，删除未完成的新文件或保留失败证据但不要修改旧文件，
然后停止。任务不 commit/push，等待负责人审查和单独的 recovery 批准。
