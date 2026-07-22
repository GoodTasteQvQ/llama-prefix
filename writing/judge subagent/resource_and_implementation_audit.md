# RESOURCE AND IMPLEMENTATION 执行性审计

审计对象：v1.0、v2.0、v3.0、v3.1、v3.2、v3.3、v3.3.1、v3.3.2。无版本后缀的 `paper1_attention_sink_mu_experiment_design.md` 按 v1.0 处理，`_v3.md` 按 v3.0 处理。

判定规则：只有 P0 阻止 DESIGN-READY；A0 表示文稿已经规定 artifact 契约、但仓库中尚未生成；I0 表示必须通过实现或代码验证。仓库只读核对未发现 `results/paper1_stage3_attention_mu*`、Freeze JSON、Stage 3 simulation/backend manifest 或本文所列 QA fixture；现有 Stage 1 artifact 不视为这些 Stage 3 artifact 的替代品。

## 1. 每个版本的 findings

### v1.0

| Finding ID | 版本 | 精确文件和行号 | 具体失败路径 | 严重度 | 分类 | 最小修复 | 阻止 DESIGN-READY |
|---|---|---|---|---|---|---|---|
| RI-V100-001 | v1.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:681-705,724-739` | 主 bootstrap 只规定“至少 10,000”而非唯一次数；人工集只规定“至少 360”，judge 不达标后使用的新 held-out 集也没有固定数量。实验员 A 可停在 360/10,000，实验员 B 可合法选择更大 N/replicates，得到不同工作量及区间。 | 阻断 | P0 | 为每个必报 bootstrap 固定次数和 seed；固定 human item N，或给出不读取 gold 的确定性封顶扩样函数，并分列 judge calls、response items、双人 assignments 与 adjudication。 | 是 |
| RI-V100-002 | v1.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:816-854` | `frozen_manifest.json`、prompt/vector manifest 只是建议目录和字段清单；没有 schema version、依赖引用闭包、自身 hash 规则或独立 backend config。两个 runner 可用不同字段、序列化和 backend，仍声称遵循文稿，cell 去重与复现无法唯一完成。 | 阻断 | P0 | 为既有 manifest/freeze 名称补齐版本化 schema、相对路径+hash+record count 引用规则、自身 hash 规则和 backend config 必填字段。 | 是 |
| RI-V100-003 | v1.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:343-353,634-651,839-852` | 25,200 只统计 generation trajectories；逐 token 的 `generated_steered_call` 仅要求记录，未与 generation attempts、technical retries、judge attempts 分账。预算算术本身为 25,200，但不能由该数字推出实际调用上限。 | 中 | P1 | 保留 25,200 logical trajectories，另加 attempts/retries/judge-call 公式与按 run 的实际计数。 | 否 |
| RI-V100-004 | v1.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:818-837,940-957` | 文稿要求的 frozen/prompt/vector manifests、QA、human-validation 与统计 artifact 在仓库中尚未生成；这是执行前状态，不是协议设计错误。 | 待生成 | A0 | 按已有契约生成并 hash 这些 artifact；不得用 Stage 1 文件冒充。 | 否 |
| RI-V100-005 | v1.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design.md:397-424` | 文稿明确记录当前 attention 脚本存在未定义变量、padding 截取和数据缺列等问题；在生产实现修复并通过 E0 前，不能确认字面算法已被正确实现。 | 待验证 | I0 | 只实现文稿现有算法，运行列出的 E0 fixtures，并保存逐项 pass/fail artifact。 | 否 |

### v2.0

| Finding ID | 版本 | 精确文件和行号 | 具体失败路径 | 严重度 | 分类 | 最小修复 | 阻止 DESIGN-READY |
|---|---|---|---|---|---|---|---|
| RI-V200-001 | v2.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:764-769,811-833,841-852` | Phase control 可取 100-200 responses，跨模型可取 20-30 prompts，跨层可取 5-10 vectors，总预算也仅给范围。多个不同矩阵都符合文本，generation 数量和 cell identities 不能唯一展开。 | 阻断 | P0 | 把 prompts/vectors/cells 写成固定值或只依赖已定义输入的确定性选择函数，并用同一变量重写分支预算。 | 是 |
| RI-V200-002 | v2.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:884-936,944-952` | 多个 bootstrap 只命名方法而未给 replicates/seed；human validation 仍为“至少 360”，rubric revision 后的新 held-out 数量未定。执行者可合法选择不同的 resampling 与人工规模。 | 阻断 | P0 | 固定每项 bootstrap 的次数/seed，并固定 human N 或给出不读取 gold 的确定性、封顶扩样规则。 | 是 |
| RI-V200-003 | v2.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:1056-1095` | artifact layout 仍是“建议”；run fields 没有版本化 schema、Freeze 文件、依赖 hash 闭包、自身 hash 或 backend config 契约。expected/actual cell 检查无法保证两个实现对同一 cell 有相同身份。 | 阻断 | P0 | 定义命名 Freeze 文件、schema、canonical identity、依赖 hash 和 backend config 必填字段。 | 是 |
| RI-V200-004 | v2.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:841-852,1082-1095` | 预算统计 generations 与 expected/actual cells，但没有 generation attempt、technical retry、judge call/parse retry 的独立口径；范围预算不能当实际调用账。 | 中 | P1 | 分列 scheduled logical outputs、completed outputs、generation attempts 和 automated-judge attempts。 | 否 |
| RI-V200-005 | v2.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:1058-1080,1160-1180` | 所列 Stage 3 v2 manifests、QA、generation、judged 和 human-validation artifact 尚未生成。 | 待生成 | A0 | 按协议生成并 hash，不补造缺失历史结果。 | 否 |
| RI-V200-006 | v2.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v2.md:1097-1124` | 文稿仍要求修复旧脚本并新增八类工具；仓库没有对应 Stage 3 v2 production 实现和通过记录。 | 待验证 | I0 | 实现文稿已定义的工具接口并运行 E0；保留失败日志。 | 否 |

### v3.0

| Finding ID | 版本 | 精确文件和行号 | 具体失败路径 | 严重度 | 分类 | 最小修复 | 阻止 DESIGN-READY |
|---|---|---|---|---|---|---|---|
| RI-V300-001 | v3.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:1103-1108` | 唯一的 `analysis_freeze.json` 在 E1/E2/E3 与 screening 之后才生成，而 E2 是 measurement primary。实验员已经看到 E2 outcomes 后才冻结分析，无法证明 measurement 决策未被结果影响。 | 阻断 | P0 | 在 E2 前写 measurement freeze；behavior/attention 另用后续 freeze，后者只能引用前者且不得覆盖。 | 是 |
| RI-V300-002 | v3.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:282-286,786-820` | behavior N 要由 power plan 调整，但 simulation/bootstrap replicate 数和 human `>=360` 的最终数量/分配均未唯一固定。不同合格实验员可冻结不同 P/V/human N。 | 阻断 | P0 | 为 simulation 与 bootstrap 固定次数/seed和唯一 P/V 选择函数；固定 human N 或确定性无-gold扩样函数。 | 是 |
| RI-V300-003 | v3.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:1019-1047,1107-1108` | layout 与 run 字段没有给 `analysis_freeze.json` 的 schema、外部依赖闭包、自身 hash、backend/statistics config；同名 freeze 可包含不同执行语义。 | 阻断 | P0 | 为 measurement/behavior freeze 与 backend config 定义版本化 schema、canonical serialization 和依赖 hash 契约。 | 是 |
| RI-V300-004 | v3.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:926-950,969-986` | 文稿已区分 logical cells、unique trajectories 和 judged generations，但没有把 technical retries、judge retries 与实际 attempts 分开。 | 中 | P1 | 在现有 registry 上增加 logical、completed、excluded、generation attempts、judge attempts 五列及公式。 | 否 |
| RI-V300-005 | v3.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:1023-1043,1103-1112` | `analysis_freeze.json`、manifests 和 Stage 3 v3 输出目录尚未生成。 | 待生成 | A0 | 按文稿顺序生成并 hash。 | 否 |
| RI-V300-006 | v3.0 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3.md:373-389` | E0 只存在协议表，Stage 3 runner/fixtures 未实现或未留下通过记录。 | 待验证 | I0 | 实现现有 QA 并保存 machine-readable 结果；失败按文稿阻止正式实验。 | 否 |

### v3.1

| Finding ID | 版本 | 精确文件和行号 | 具体失败路径 | 严重度 | 分类 | 最小修复 | 阻止 DESIGN-READY |
|---|---|---|---|---|---|---|---|
| RI-V310-001 | v3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:1003-1011` | coverage check 失败后要求“构造一种 behavior-informed direction”，但没有唯一 construction algorithm；同时允许一个 direction 或至少 20 directions，导致新增 generation 可为 `3 x subset` 或 1,800-3,000。 | 阻断 | P0 | 只保留一个已完整定义的 construction path；把 direction 数、输入分区、失败状态和对应预算写成确定分支。 | 是 |
| RI-V310-002 | v3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:825-837` | human N 为 `>=360`；关键类别 CI 不足时要增加样本，但没有 CI 精度、步长或上限，且允许团队换 acceptance threshold。人工 item 与 assignment 数无法唯一预算。 | 阻断 | P0 | 固定 human item N、阈值和无-gold抽样算法；分列两名标注者与 adjudication assignments。 | 是 |
| RI-V310-003 | v3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:851-874,909-916` | hierarchical simulation 只列 variance ingredients 与 P/V candidates，没有固定 DGP、scenario union、replicates、统计 backend 或联合 candidate 选择函数；实现选择会改变 final N 和预算。 | 阻断 | P0 | 在现有方法内固定 generator、有限 scenarios、replicates/seed、backend manifest 和首个合格 P/V 的机械选择规则。 | 是 |
| RI-V310-004 | v3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:292-326` | Freeze A/B 列出字段但没有规定外部 manifest 的 path/schema/hash/record-count 闭包，也没有排除 `self_sha256` 的 canonical self-hash 算法。两个 freeze 可引用不同内容而哈希表面仍合法。 | 阻断 | P0 | 补齐依赖引用五元组、canonical JSON 和 non-recursive self-hash 规则。 | 是 |
| RI-V310-005 | v3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:944-975` | logical/unique/trajectory/judged 已分开，但实际 generation/judge attempts 与 retries 仍无公式。 | 中 | P1 | 加入 actual-call accounting，不改现有 logical budget。 | 否 |
| RI-V310-006 | v3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:1063-1089,1143-1153` | `measurement_freeze.json`、`behavior_freeze.json` 及 manifests/outputs 尚未生成。 | 待生成 | A0 | 按定义生成并 hash。 | 否 |
| RI-V310-007 | v3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_1.md:459-476` | E0 要求已经定义，但仓库没有对应 Stage 3 production implementation/fixture pass artifact。 | 待验证 | I0 | 实现并执行现有 E0；不改变实验因素。 | 否 |

### v3.2

| Finding ID | 版本 | 精确文件和行号 | 具体失败路径 | 严重度 | 分类 | 最小修复 | 阻止 DESIGN-READY |
|---|---|---|---|---|---|---|---|
| RI-V320-001 | v3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:723-729,733-751,939-955` | human sample 从 360 开始，依据已观察 gold counts/CI 每轮加 60 到 720；因此数量依赖中途 gold，普通固定样本 CI 不再对应同一设计。预算又把 360-720 response items 写成“human annotations”，漏掉双人 assignments 与第三人 adjudication。 | 阻断 | P0 | 在任何 gold 可见前一次固定 item N；将人工成本写成 `2*N_items + N_adjudication`，不改变标注方法。 | 是 |
| RI-V320-002 | v3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:757-770,782-796` | P1 给出 10,000 simulations，但 P2/K2 没有固定 replicate 数、binary DGP、scenario union 或完整统计 backend；不同实现会选出不同 P/V/fallback。 | 阻断 | P0 | 为现有 simulation 固定 DGP、有限 scenario union、replicates/seed、backend manifest 和唯一 candidate/method 选择函数。 | 是 |
| RI-V320-003 | v3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:278-314` | Freeze A/B 虽有字段清单，但外部引用没有统一 path/schema/hash/record-count 契约，自身 hash 也没有排除 self field 的算法；backend 仅作为普通字段，无法验证统计实现身份。 | 阻断 | P0 | 定义 dependency-closed references、canonical self-hash 和独立 statistics/backend manifest。 | 是 |
| RI-V320-004 | v3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:712-721,896-920` | 技术失败允许重跑、judge parse 可重试或转人工，但预算仅给 logical generated/judged totals；actual generation/judge attempts 无法由公式计算。 | 阻断 | P0 | 保留现有 logical 公式，新增 retry 变量、terminal pre-judge failures 和 actual attempt 上下界。 | 是 |
| RI-V320-005 | v3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:1018-1048,1102-1116` | Freeze、construction manifests、power、QA、judged 与 human-validation artifacts 尚未生成；`data/safe_pairs.json` 现有对象只有 harmful/harmless 文本字段，未满足文稿要求的 provenance manifest。 | 待生成 | A0 | 按既有 schema 补齐真实 provenance 并生成 artifacts；缺失时按文稿阻断，不虚构。 | 否 |
| RI-V320-006 | v3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_2.md:461-479` | E0 包含 V2/cell identity QA，但 fixture 与 Stage 3 实现尚无通过证据。 | 待验证 | I0 | 实现现有算法并运行 E0，保存 reference inputs/expected outputs。 | 否 |

### v3.3

| Finding ID | 版本 | 精确文件和行号 | 具体失败路径 | 严重度 | 分类 | 最小修复 | 阻止 DESIGN-READY |
|---|---|---|---|---|---|---|---|
| RI-V330-001 | v3.3 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:749-751,797-848` | final `P/V` 可到 100/30，但 random budget 和 28,284/28,140 “硬上界”按 50/20 常数展开；一旦 simulation 选择更大 P/V，mandatory cells 已超出该上界，预算与 protocol 不自洽。 | 阻断 | P0 | 用 P/V/N 参数化每个 block，并把 50/20 数字只标 planning example；按候选范围另算 scope-grid upper。 | 是 |
| RI-V330-002 | v3.3 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:704-751` | simulation 仍没有固定 DGP、有限 scenario union、statistics backend 和联合 P/V-method 选择函数；它直接决定最终样本与预算。 | 阻断 | P0 | 为既有 P2/K2/V2 方法固定 generator、scenarios、backend、replicates/seed 与首个联合通过 candidate 规则。 | 是 |
| RI-V330-003 | v3.3 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:263-307` | Freeze A/B/sample lock 虽已命名，但外部 manifest 引用没有 schema/record-count 闭包，`self_sha256` 的 canonical 排除规则也未定义。 | 阻断 | P0 | 增加 dependency-closed reference contract 和 non-recursive canonical self-hash。 | 是 |
| RI-V330-004 | v3.3 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:675-686,821-862` | 文稿规定技术失败可重跑，却仍把 generated/judged logical totals当完整资源账；没有 generation attempts、judge parse retries、terminal pre-judge failures。 | 阻断 | P0 | 在现有 totals 外增加 actual-call 公式和一次 retry 上界。 | 是 |
| RI-V330-005 | v3.3 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:921-948,1001-1017` | 三个 freeze、manifests、simulation、human sample lock 与输出 artifacts 尚未生成。 | 待生成 | A0 | 按文稿时序生成并 hash。 | 否 |
| RI-V330-006 | v3.3 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3.md:422-440` | QA 项存在，但 reference fixtures、backend implementation 和 pass artifact 尚未实现验证。 | 待验证 | I0 | 实现并运行既有 QA，失败按 target block 停止。 | 否 |

### v3.3.1

| Finding ID | 版本 | 精确文件和行号 | 具体失败路径 | 严重度 | 分类 | 最小修复 | 阻止 DESIGN-READY |
|---|---|---|---|---|---|---|---|
| RI-V331-001 | v3.3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:301-319,870-872` | `rho_A/T/H` 只要求写进 Freeze B，文稿没有给其来源 manifest 或无 outcome 搜索规则，同时保留 Qwen extra-range/midpoint screening。不同实验员可从不同 base anchors 开始，改变全部 E5/E6/V2 cells。 | 阻断 | P0 | 增加 pre-screen、哈希闭合的 base-anchor manifest；固定三锚点 screen，禁止 screen 移动 anchors。 | 是 |
| RI-V331-002 | v3.3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:874-951` | scenario 构造虽有限化，但 binary DGP、endpoint correlation/failure generator、statistics backend 以及 P2-U/P2-B 联合 P/V selector仍未唯一规定；coverage 结果不可跨实现复现。 | 阻断 | P0 | 在现有 simulation plan 中补 exact generator、backend manifest、固定 candidate order和联合 pass/fallback 函数。 | 是 |
| RI-V331-003 | v3.3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:379-403,1015-1025,1063-1086` | V2 可在 initial 150 或 rescue 后 300 responses 因 technical/support gate 被阻断；预算变量 `N_V2` 却只允许 0/1,950/2,100，无法记录 150/300 已发生的 logical 成本，并可能错误触发 1,800 rematch。 | 阻断 | P0 | 把 V2 拆成 `S_V2 in {0,150,300}`、`C_V2 in {0,1800}` 与受状态约束的 rematch 变量。 | 是 |
| RI-V331-004 | v3.3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:816-816,1011-1128` | technical rerun 已允许，但账本只区分 generated 与 automated judged logical totals；没有 completed outputs、terminal failure、generation/judge attempts，logical budget被误当实际调用量。 | 阻断 | P0 | 增加一次 retry 变量、pre-judge terminal 变量及 generation/judge attempt 公式。 | 是 |
| RI-V331-005 | v3.3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:878-912,943-949,991-997` | 每个 core scenario 要至少 10,000 个外层 simulation replicates，而被验证的 max-T procedure 对每个 dataset 又要求 9,999 次完整重拟合。仅 9 个 candidate、3 个 prevalence 的 N-screen null 就至少产生约 `9*3*10,000*9,999 = 2.70e9` 次内层重采样/重拟合，尚未计 alternatives、stress、K2/V2；按字面明显不可执行。 | 阻断 | P0 | 不增加统计方法：在 Freeze B 前固定一个满足既有 MCSE/coverage 标准且通过资源可行性检查的外层/内层计算方案；若不存在，预先把相应 family 降为 estimation-only，不启动不可完成的嵌套计算。 | 是 |
| RI-V331-006 | v3.3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:1188-1227,1297-1310` | dependency-closed freeze、simulation plan、QA 与 human sample lock 的规则已定义，但对应 artifact 尚未生成。 | 待生成 | A0 | 按 schema 和时点生成；不得填造 backend、anchor 或结果。 | 否 |
| RI-V331-007 | v3.3.1 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_1.md:498-525` | QA 覆盖已显著扩展，但 fixture 文件、statistics implementation 与 pass artifact 仍不存在。 | 待验证 | I0 | 实现现有 fixtures 并保存 machine-readable reference/pass 状态。 | 否 |

### v3.3.2

| Finding ID | 版本 | 精确文件和行号 | 具体失败路径 | 严重度 | 分类 | 最小修复 | 阻止 DESIGN-READY |
|---|---|---|---|---|---|---|---|
| RI-V332-001 | v3.3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:629-629,869-869,1004-1026,1122-1129,1144-1146` | confirmatory max-T、P1 和 two-phase bootstrap 已有次数，但 required ranking、K1 profile、clean 和 stochastic CI bootstraps仍未给各自 replicates/seed；`R_sim`也只要求在 artifact 中取任意 `>=10,000`。两名实验员可在不违反文稿的情况下选不同 resampling 数/seed，产出不同必报 CI。 | 阻断 | P0 | 不增加方法，只在 Freeze A/B/backend schema 中为每个已要求的 bootstrap/simulation 固定 exact replicate count、master seed、substream derivation；将 `R_sim` 改为一个固定数或确定性选择规则。 | 是 |
| RI-V332-002 | v3.3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:1015-1026,1068-1088,1150-1161` | 每个 core scenario 要至少 10,000 个外层 simulation replicates，正式 max-T 又要求 9,999 个同步 replicates且每次完整重拟合。即使 `f_screen=0` 去重，N-screen null 下界仍为 `9 candidates * 3 prevalence * 10,000 * 9,999 = 2,699,730,000` 次内层重采样/重拟合；K2/V2、stress 和 fallback 尚未计入，按字面明显不可行。 | 阻断 | P0 | 不增加统计方法：在 pre-Freeze-B resource feasibility 中固定可完成的外层/内层计算方案并继续满足既有 MCSE/coverage标准；无法同时满足时，按预注册规则把相应 family 降为 estimation-only。 | 是 |
| RI-V332-003 | v3.3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:264-289,306-373,1002-1013,1388-1428` | base-anchor、simulation/backend、Freeze A/B、human sample lock、manifests 与 QA artifacts 均已定义 schema/时点/失败后果，但仓库中尚未生成；`safe_pairs.json` 也尚无协议要求的 provenance companion manifest。 | 待生成 | A0 | 严格按现有 schema 生成并 hash；缺数据时保留 blocked 状态，不虚构字段或结果。 | 否 |
| RI-V332-004 | v3.3.2 | `D:\llama_prefix\writing\stage3 design\paper1_attention_sink_mu_experiment_design_v3_3_2.md:552-594` | QA fixture 集已足以覆盖 anchor、selector、backend、quota、Hájek、partial budget 与 actual-call 关键算法，但仓库没有 Stage 3 实现、fixture inputs/reference outputs 或通过记录，正确性仍只能由代码验证。 | 待验证 | I0 | 实现文稿已有算法并逐项运行 E0；保存 fixture hash、reference output 和 pass/fail。 | 否 |

## 2. 每个版本的 P0/A0/I0 数量

| 版本 | P0 | A0 | I0 |
|---|---:|---:|---:|
| v1.0 | 2 | 1 | 1 |
| v2.0 | 3 | 1 | 1 |
| v3.0 | 3 | 1 | 1 |
| v3.1 | 4 | 1 | 1 |
| v3.2 | 4 | 1 | 1 |
| v3.3 | 4 | 1 | 1 |
| v3.3.1 | 5 | 1 | 1 |
| v3.3.2 | 2 | 1 | 1 |

## 3. 每个版本的 DESIGN-READY 判断

| 版本 | DESIGN-READY | 直接原因 |
|---|---|---|
| v1.0 | 否 | human/bootstrap 数量与 freeze/schema 不唯一。 |
| v2.0 | 否 | generation 分支范围、human/bootstrap 数量与 artifact contract 不唯一。 |
| v3.0 | 否 | measurement primary 在统一 freeze 前暴露，且 N/schema 未闭合。 |
| v3.1 | 否 | second-family、human N、simulation/backend 与依赖闭包仍有运行时自由度。 |
| v3.2 | 否 | gold-dependent human 扩样、simulation/backend、freeze closure 与 actual-call 账不闭合。 |
| v3.3 | 否 | P/V 可变但 hard upper 固定，simulation/backend、freeze closure 与 actual-call 账不闭合。 |
| v3.3.1 | 否 | base anchors、simulation/backend、V2 partial cost、actual-call 账与嵌套 simulation 计算量仍未闭合。 |
| v3.3.2 | 否 | required resampling 数/seed仍有自由度，且 10,000 外层 simulation 与 9,999 内层 max-T 重拟合按字面形成十亿级计算。 |

## 4. RESOURCE AND IMPLEMENTATION 维度结论

版本演进真实关闭了主要资源执行缺口：v3.1 开始区分 logical/unique trajectories，v3.2 参数化 identity reuse 与第二 family，v3.3 固定 720 human items并分离 assignments，v3.3.1 引入 dependency-closed freeze 与参数化预算，v3.3.2 又补齐 base-anchor provenance、V2 partial states、scope-grid budget及 logical/actual call accounting。v3.3.2 的 planning 算术 `23,034/22,890` 与 scope-grid `59,234/59,090` 复算一致；human 为 720 items、1,440 primary assignments，加实际 disagreements 的 adjudication；attention 为 192 teacher-forced trajectories；V2 construction forwards 为 750 planning、1,000 cap。generation、annotation 与 Parquet/Arrow token-summary storage 未显示字面不可行；明显不可行项来自 v3.3.1/v3.3.2 的嵌套 coverage simulation：外层每 scenario 至少 10,000 次，内层 max-T 9,999 次完整重拟合，最低即十亿级重采样/拟合。

本维度仍不能给任何版本 DESIGN-READY。v3.3.2 已接近结构闭合，但 required descriptive/secondary bootstrap 与 `R_sim` 的 exact resampling 数/seed仍留给执行者选择；同时其字面 nested-simulation 规模没有可完成的资源路径。除此之外，v3.3.2 剩余事项属于 A0/I0：先生成已定义的 manifests/freezes/fixtures，再用实现验证；这些事项本身不应被改写成新的协议 P0。
