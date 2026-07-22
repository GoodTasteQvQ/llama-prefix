# REG-001 - VERSION REGRESSION Audit

审计日期：2026-07-22  
审计维度：VERSION REGRESSION  
审计对象：v1.0、v2.0、v3.0、v3.1、v3.2、v3.3、v3.3.1、v3.3.2  
审计目标：判断各版本能否由另一名合格实验员按文稿唯一执行  
Finding ID：`REG-001`

## 1. 各版本 Findings

### v1.0

无 VERSION REGRESSION finding。v1.0 是本次版本序列的比较基线。

### v2.0

#### 三模型匹配确认被弱化

- **Finding ID**：`REG-001`
- **版本**：v2.0
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design.md:146-150`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design.md:712-718`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v2.md:97-105`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v2.md:802-824`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v2.md:1039-1041`
- **具体失败路径**：v1.0 要求三模型完成同协议 primary contrasts 和 dose-matched `model x dose`；v2.0 在 Llama/Mistral structural-leverage Gate 未通过时跳过匹配行为确认，改用既有 full1000/pilot 曲线，却仍允许 `model-specific collapse thresholds remain after accounting for actual dose`。按 v2.0 执行不能生成与 v1.0 同等级的跨模型匹配证据。
- **严重度**：中，非阻断。
- **分类**：`P1`
- **最小修复**：恢复三模型 gate-independent matched-dose minimum；或把允许结论降为 Qwen 主结果加 Llama/Mistral 描述性负对照。
- **是否阻止 DESIGN-READY**：否。

### v3.0

无新 finding。v3.0 的三模型 Gate-independent minimum 恢复了 v2.0 弱化的可比确认要求。

### v3.1

#### 连续 dose/threshold 主分析被降为三点 categorical 分析

- **Finding ID**：`REG-001`
- **版本**：v3.1
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3.md:861-868`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_1.md:49-56`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_1.md:713-723`
- **具体失败路径**：v3.0 将 restricted cubic spline、`rho_50` 和 common-support threshold differences 列为 primary；v3.1 改成三个 categorical anchors，只允许 bracket/not-bracketed。按 v3.1 不能执行或复现 v3.0 的连续 threshold estimand。
- **严重度**：中，非阻断。
- **分类**：`P1`
- **最小修复**：明确声明 continuous-threshold claim 已撤回且旧结果不可并入；或恢复至少五个冻结 dose levels。
- **是否阻止 DESIGN-READY**：否。

#### 第二 vector-family confirmation N 不唯一

- **Finding ID**：`REG-001`
- **版本**：v3.1
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_1.md:996-1009`
- **具体失败路径**：当前缺第二 vector family 时必须启动最小块，但同段同时给出 planning `30 x 20 x 3` 和 hard cap `50 x 20 x 3`，没有从 30 扩到 50 的确定性规则。两名实验员可以合法选择不同 confirmation N。
- **严重度**：高，阻断。
- **分类**：`P0`
- **最小修复**：固定 `D_second_confirm=30`，精度不足直接降级；或定义 outcome-blind 的唯一扩样触发器。
- **是否阻止 DESIGN-READY**：是。

#### 第二 vector-family artifact 尚未形成

- **Finding ID**：`REG-001`
- **版本**：v3.1
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_1.md:1001-1009`
- **具体失败路径**：文稿明确记录尚无合格第二 vector-family artifact，新增范围尚未形成可引用 artifact。
- **严重度**：artifact 待生成。
- **分类**：`A0`
- **最小修复**：提供合格 cross-reference，或执行已定义的独立构造路径；不得虚构 artifact。
- **是否阻止 DESIGN-READY**：否，但阻止相应推广结论。

### v3.2

#### P2 primary endpoint family 发生实质变化

- **Finding ID**：`REG-001`
- **版本**：v3.2
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_1.md:178-202`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_2.md:180-220`
- **具体失败路径**：v3.1 的唯一 P2 是 transition-anchor `RD_broken`，unsafe 为 K1 secondary；v3.2 将 unsafe-A 和 broken-T 改成 Holm-adjusted 双 P2 family。v3.1 的单终点 P2 结果不能直接满足 v3.2 的 family-wise decision。
- **严重度**：中，非阻断。
- **分类**：`P1`
- **最小修复**：标注为 primary-endpoint reset，并禁止把 v3.1 单终点推断当作 v3.2 P2 family。
- **是否阻止 DESIGN-READY**：否。

#### 第二 vector-family confirmation N 歧义持续

- **Finding ID**：`REG-001`
- **版本**：v3.2
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_2.md:364-379`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_2.md:922-935`
- **具体失败路径**：`D_second_confirm` planning size 为 30，但预算另给 50-prompt hard cap，未定义唯一选择或扩样规则。
- **严重度**：高，阻断。
- **分类**：`P0`
- **最小修复**：删除 50-prompt 分支，或定义唯一 outcome-blind 扩样触发器。
- **是否阻止 DESIGN-READY**：是。

#### 第二 vector-family provenance artifact 尚未合格

- **Finding ID**：`REG-001`
- **版本**：v3.2
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_2.md:339-360`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_2.md:869-878`
  - `data/safe_pairs.json:1`
- **具体失败路径**：`safe_pairs.json` 只有 `harmful` 和 `harmless` 字段，缺少文稿要求的 source/version/license/taxonomy/retrieval/provenance 等资格信息。
- **严重度**：artifact 待生成。
- **分类**：`A0`
- **最小修复**：补齐可审计 provenance manifest；或保持 random-family-only scope。
- **是否阻止 DESIGN-READY**：否，但阻止第二-family推广结论。

### v3.3

#### 第二 vector-family confirmation N 歧义持续

- **Finding ID**：`REG-001`
- **版本**：v3.3
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3.md:598-618`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3.md:808-817`
- **具体失败路径**：正文把 matched V2/random comparison 限制为 30 prompts，预算仍给出 50-prompt hard cap，且没有扩样算法。
- **严重度**：高，阻断。
- **分类**：`P0`
- **最小修复**：删除 50-prompt 分支，或定义唯一 outcome-blind 扩样触发器。
- **是否阻止 DESIGN-READY**：是。

#### Rendering-package 2x2 操作定义被删除

- **Finding ID**：`REG-001`
- **版本**：v3.3
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_2.md:639-665`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3.md:582-588`
- **具体失败路径**：v3.2 明确定义 `T0/T2`、`mu0/mu1`、`alpha0/alpha1` 和 A-D；v3.3 只保留 `T0/T2 x alpha0/alpha1` 形成 A-D，删除变量与 cell 映射。实验员无法唯一构造 mandatory rendering 2x2。
- **严重度**：高，阻断。
- **分类**：`P0`
- **最小修复**：恢复 v3.2 的完整变量定义、cell table 和 identity freeze。
- **是否阻止 DESIGN-READY**：是。

#### Human-validation sample rule 实质改变

- **Finding ID**：`REG-001`
- **版本**：v3.3
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_2.md:733-751`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3.md:677-700`
- **具体失败路径**：human validation 从 v3.2 的 360 起、按 gold/CI 逐轮扩到 720，改为 v3.3 的预先固定 720、禁止 early stop。两个版本的样本和验证估计不可直接混用。
- **严重度**：中，非阻断。
- **分类**：`P1`
- **最小修复**：声明 human-sampling protocol reset，并禁止复用按 v3.2 adaptive rule 形成的样本。
- **是否阻止 DESIGN-READY**：否。

#### 第二 vector-family provenance artifact 仍未合格

- **Finding ID**：`REG-001`
- **版本**：v3.3
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3.md:319-355`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3.md:789-817`
- **具体失败路径**：candidate `safe_pairs` 仍缺完整 provenance，不能成为 qualified second-family dataset。
- **严重度**：artifact 待生成。
- **分类**：`A0`
- **最小修复**：补齐 provenance/license/taxonomy/leakage manifest；否则保持 blocked 状态。
- **是否阻止 DESIGN-READY**：否。

### v3.3.1

#### Patch 实际引入 major statistical change

- **Finding ID**：`REG-001`
- **版本**：v3.3.1
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3.md:753-785`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:599-655`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:818-856`
- **具体失败路径**：patch 新增 mandatory two-phase human-error correction、family-wise CI、decision-consistency gate 和 P2 cell sampling floors。v3.3 自动 judge 推断即使显著，也可能在 v3.3.1 被强制降级；v3.3 结果不能作为兼容 patch 输入。
- **严重度**：中，非阻断。
- **分类**：`P1`
- **最小修复**：升级协议版本层级，要求 P2 分析按新规则重新冻结，禁止复用 v3.3 判定。
- **是否阻止 DESIGN-READY**：否。

#### 新增统计流程需要实现验证

- **Finding ID**：`REG-001`
- **版本**：v3.3.1
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:625-655`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:874-999`
- **具体失败路径**：新增 two-phase、max-T 和 coverage-based method selector 需要代码及 reference fixtures 验证；当前代码目录未定位到对应实现。
- **严重度**：实现验证待完成。
- **分类**：`I0`
- **最小修复**：实现并通过文稿定义的固定 fixtures，不改变 estimand 或选择规则。
- **是否阻止 DESIGN-READY**：否，但阻止正式 Freeze B。

#### 第二 vector-family provenance artifact 仍未合格

- **Finding ID**：`REG-001`
- **版本**：v3.3.1
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:349-377`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:1003-1009`
- **具体失败路径**：candidate `safe_pairs` 仍缺完整 provenance，不能成为 qualified second-family dataset。
- **严重度**：artifact 待生成。
- **分类**：`A0`
- **最小修复**：补齐规定的 provenance manifest，或保持 random-family-only claim boundary。
- **是否阻止 DESIGN-READY**：否。

### v3.3.2

#### 第二个 patch 再次引入 major statistical/protocol change

- **Finding ID**：`REG-001`
- **版本**：v3.3.2
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:379-431`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:829-842`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_1.md:991-999`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:259-291`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:900-986`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:1002-1163`
- **具体失败路径**：v3.3.2 将 base anchors 改为 pre-screen 外部 manifest，重写 human strata/inclusion probabilities 与 Hájek correction，并新增唯一 P/V selector、raw bootstrap p 和 max-T decision hierarchy。v3.3.1 冻结的 anchors、human sample 或 p 值不能作为 v3.3.2 的兼容输入。
- **严重度**：中，非阻断。
- **分类**：`P1`
- **最小修复**：作为新的统计协议版本发布并重新执行 Freeze B/sample lock；禁止跨 patch 合并确认性结果。
- **是否阻止 DESIGN-READY**：否。

#### Base-anchor manifest 尚未生成

- **Finding ID**：`REG-001`
- **版本**：v3.3.2
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:259-291`
- **具体失败路径**：新要求的 `base_anchor_manifest.json` 当前未生成；无合法 manifest 时文稿明确阻断 Freeze B。
- **严重度**：artifact 待生成。
- **分类**：`A0`
- **最小修复**：由真实 pre-screen 来源生成并哈希，不得补造默认 anchors。
- **是否阻止 DESIGN-READY**：否，但阻止正式 Freeze B。

#### 第二 vector-family provenance artifact 仍未合格

- **Finding ID**：`REG-001`
- **版本**：v3.3.2
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:401-429`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:1171-1177`
- **具体失败路径**：candidate `safe_pairs` 仍缺完整 provenance，不能成为 qualified second-family dataset。
- **严重度**：artifact 待生成。
- **分类**：`A0`
- **最小修复**：补齐 provenance/license/taxonomy/leakage manifest；否则保持 blocked 状态。
- **是否阻止 DESIGN-READY**：否。

#### 新统计 backend 需要实现验证

- **Finding ID**：`REG-001`
- **版本**：v3.3.2
- **精确文件和行号**：
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:1002-1054`
  - `writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_3_2.md:1132-1163`
- **具体失败路径**：新增 backend manifest、binary generator、GLMM/Webb selector、raw-p/max-T fixtures 均需实现验证；当前代码目录未定位到对应实现。
- **严重度**：实现验证待完成。
- **分类**：`I0`
- **最小修复**：按固定 backend/schema 实现并通过 fixtures，不改变预注册方法。
- **是否阻止 DESIGN-READY**：否，但阻止正式 Freeze B。

## 2. 每版本 P0/A0/I0 数量

| 版本 | P0 | A0 | I0 |
|---|---:|---:|---:|
| v1.0 | 0 | 0 | 0 |
| v2.0 | 0 | 0 | 0 |
| v3.0 | 0 | 0 | 0 |
| v3.1 | 1 | 1 | 0 |
| v3.2 | 1 | 1 | 0 |
| v3.3 | 2 | 1 | 0 |
| v3.3.1 | 0 | 1 | 1 |
| v3.3.2 | 0 | 2 | 1 |

## 3. 每版本 DESIGN-READY 判断

判定规则：存在 `P0` 即不通过；`A0/I0` 表示设计后的 artifact 生成或实现验证尚未完成，不单独否定 DESIGN-READY。

| 版本 | DESIGN-READY | 说明 |
|---|---|---|
| v1.0 | YES | 版本序列基线 |
| v2.0 | YES | 存在非阻断跨模型 scope regression |
| v3.0 | YES | 恢复三模型 gate-independent minimum |
| v3.1 | NO | 第二-family confirmation N 不唯一 |
| v3.2 | NO | 30/50-prompt 分支不唯一 |
| v3.3 | NO | 样本分支不唯一且 rendering 2x2 定义丢失 |
| v3.3.1 | YES | A0/I0 pending |
| v3.3.2 | YES | A0/I0 pending |

## 4. VERSION REGRESSION 维度结论

主要回归链有两条：

1. v2.0 弱化了 v1.0 的三模型匹配确认；v3.0 已恢复。
2. v3.1 引入第二-family 的 30/50 样本歧义并持续到 v3.3；v3.3.1 才固定为 30。v3.3 还删除了 v3.2 已成立的 rendering 2x2 操作定义，因此是本序列回归最严重的版本。

`v3.3.1` 和 `v3.3.2` 均发生 major statistical change，不应作为仅修正文案、可直接复用前版冻结结果的兼容 patch。未发现 current-line 模型/checkpoint 集合被悄悄改变，也未发现多个互相竞争的 primary clean baseline。
