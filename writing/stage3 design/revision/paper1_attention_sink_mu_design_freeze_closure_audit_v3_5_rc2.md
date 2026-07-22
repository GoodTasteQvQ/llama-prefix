# v3.5-rc2 Design-Freeze Closure Audit Archive

归档日期：`2026-07-22`  
审计模式：只读 `DESIGN-FREEZE CLOSURE AUDIT`  
方法学边界：IEEE TDSC-oriented design-freeze review  
审计目标：`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc2.md`  
比较基线：`writing/stage3 design/paper1_attention_sink_mu_experiment_design_v3_5_rc1.md`  
审计分工：A（freeze/identity/execution/support）、B（estimand/statistics）、C（fixed720/resource/scope），主审计者独立复核关键证据并做根因去重。  
文件修改：审计过程中未修改协议、实现、fixture、manifest 或实验结果。

## 1. Executive verdict

`DESIGN-FREEZE-FAIL`

发现两个独立 `TRUE_P0`。两者均位于保留范围内的统计与计算复现闭合，不是因为缺少
外部输入、运行时 manifest、正式结果或执行 fixture。internal validity、survivor-frame、
freeze/support identity、fixed720、资源算术和 evidence-to-claim boundary 基本闭合，但
当前规范仍允许合格实现者在同一数据上得到不同正式 CI。

独立校验记录：

- release manifest 中 25 个 artifacts 的 SHA256 全部匹配；
- rc1 baseline SHA256 为
  `f557fb8a06329f92778e9e1eb7ddb2822b05e80bf83784ba1ec243b9343fb85a`，与记录一致；
- 仓库 static verification report 为 `PASS`，但 verifier 没有覆盖以下两个完整 CI 根因；
- P2 仍为 estimation-only，本审计没有要求 power、coverage、p-value、global test、
  multiplicity-adjusted test 或 confirmatory Boolean gate。

## 2. TRUE_P0 findings

### P0-STAT-01: matched two-phase CI 未绑定完整重抽样算法和同步 RNG 身份

**根因**

主协议 L735-L775 定义 Rao-Wu 权重、replicate statistic、SE、max-statistic、CI 和完成规则，
但 L830-L833 只泛称 two-phase blocks 使用 `prompt-stratum`、`phase2-stratum`、`vector`
轴及 frozen IDs，没有给出 exact canonical `sync_unit_id` object、draw-to-unit mapping 和完整
执行顺序。

`writing/stage3 design/v3_5_rc2_closure/C/binding_manifest.json` L14-L26 所绑定的
`scripts/stage3_design/v3_5_rc2/two_phase_correction.py` L48-L134 只实现 matched point
estimator。对应 golden 只覆盖点估计、armwise clipping 和 incomplete-pair rejection；没有
Rao-Wu replicate weights、同步 RNG、SE、max-statistic、CI 或 completion boundary fixture。

**两条当前均合法的执行路径**

```text
Path A sync_unit_id =
{"axis":"prompt-stratum","entity_id":"cat1","family":"p2-two-phase-prompt"}

Path B sync_unit_id =
{"axis":"prompt-stratum","family":"p2-two-phase-prompt","stratum_id":"cat1"}
```

两者均使用 canonical JSON、规定 block、规定 family、规定轴和 frozen stratum identity，
但产生不同 SHA256 stream。按协议 counter engine，在二单位 stratum 的 replicate 2，
Path A 的两个 prompt draws 为 `[0,1]`，Path B 为 `[0,0]`。若同一 matched arm 的两个
event values 为 `[0,1]`，该 replicate 的 rate/RD 分别为 `0.5` 和 `0`，从而可能改变
`theta_star`、SE、`q_max`、CI 和 common-success status。

**最小修复**

在 normative binding 中加入完整 prompt x Rao-Wu resampling、vector sensitivity、exact
sync JSON、frame/order、draw order、SE/max-statistic、completion/failure mapping 的 reference
implementation，并增加手算 CI、census、`9,499/9,500` boundary 和 failure golden。不得新增
实验、样本、endpoint 或 testing layer。

### P0-STAT-02: retained K1/clean/benign bootstrap 没有唯一执行和身份合同

**根因**

主协议 L588-L632 注册 K1、harmful-clean 和 benign-broken intervals，L828-L847 只给 family、
frame、nearest-rank 和 completion 的通用描述，没有 exact sync object 和完整 multiplicity
mapping。

`writing/stage3 design/v3_5_rc2_statistics/README.md` L3-L5 明确 executable reference 只覆盖
P1 bootstrap 和 raw P2 simultaneous interval；L110-L122 的 retained rule 仅为文字规范。
`statistical_reference_manifest.json` L6-L31 的 production parameters 也只有 P1/raw P2，
`reference_statistics.py` 只有 `p1_interval` 和 `p2_raw_simultaneous`，没有 retained-family
reference 或 fixture。

**两条当前均合法的执行路径**

```text
Path A sync_unit_id =
{"axis":"prompt","entity_id":"frame","family":"harmful-clean"}

Path B sync_unit_id =
{"family":"harmful-clean","frame_hash":"frame"}
```

对同一 50-prompt binary frame（前 5 个值为 1，其余为 0），按各自固定 stream 执行
10,000 次 bootstrap 后，nearest-rank 95% CI 分别为：

```text
Path A: [1,10] / 50 = [0.02,0.20]
Path B: [1, 9] / 50 = [0.02,0.18]
```

因此同一数据可产生不同正式 CI。K1 的 prompt/vector multiplicity combination 同样没有由
reference implementation 固定。K1、harmful clean 和 benign 是同一个 retained-bootstrap
执行/身份根因，不拆成三个 P0。

**最小修复**

增加一个统一、hash-bound 的 retained-bootstrap reference，固定三块的 frame ordering、
sample size、K1 multiplicity combination、exact sync JSON、common-success set、degenerate 和
failure rules，并提供 success/failure/RNG golden。不得新增输出或实验。

### 为什么不能降为 A0/I0

主协议 L83-L86 明令未来 `inference_backend_manifest.json` 不得选择、替换或参数化 algorithm、
quantile、SE、RNG、failure rule、estimator 或 fallback。当前不存在能够消除上述合法路径
分歧的 bound reference/fixture；现在直接生成 fixture 等于让实现者替协议选择算法。

把相关 CI 一律标为不可用或删除也不能解决：这些 intervals 已是 retained registered outputs，
无数据触发条件的永久降级会改变协议输出和 evidence contract，而不是合法的 failure mapping。

## 3. Non-P0 findings

| Class | Finding | Disposition |
|---|---|---|
| A0 | checkpoint/tokenizer/template、prompt/anchor/vector identity，以及 measurement spec/result-dose、judge/support/confirmation/human freezes、`inference_backend_manifest` 未生成 | RUN 前置，不是本次 FAIL 原因 |
| A0 | 未找到独立 rc1 -> rc2 scope-removal manifest | 删除范围已由 rc1 -> rc2 semantic diff L103-L112 和 C removal matrix 记录；不构成 P0 |
| I0 | execution-specific E0 fixtures、runtime schemas/validators、正式 pipeline integration 尚未完成 | 规范已确定的部分按主协议 L349-L350 记 `FIXTURE_PENDING_IMPLEMENTATION` |
| P1/P2 | §9.3 的 judge `cluster-aware intervals` 未定义置信度、cluster 轴、SE/CI 和失败规则 | 属于辅助 judge-error 诊断，不控制正式 endpoint、gate、status 或 allowed claim；发表前闭合 |
| P1/P2 | C merge note 的 actual judge-call 公式未扣除 `E_generation_unattempted`，最终 rc2 已扣除 | 最终协议优先；legacy wording 不一致，不改变主要结果或状态 |
| P1/P2 | README 允许 exact parser 或仅复现现有 golden 的 implementation | 主协议和 hash-bound `freeze_contract.py` 已指定 formal parser；保留为实现忠实度风险 |
| SCOPE_REINTRODUCTION | 恢复 model-based RD/CI、power/coverage、selector、K2、V2、rendering 2x2、stochastic、attention 或 phase confirmation | 拒绝；均不属于最小修复 |
| DUPLICATE | E0/checklist/static report 声称相关 golden PASS | verifier 只验证 point two-phase 与 P1/raw P2；属于 P0-STAT-01/02 的同根症状 |

## 4. Twelve closure conditions

| ID | Status | Evidence and conclusion |
|---:|---|---|
| 1 | PASS | Pre-outcome measurement specification 禁止 realized P1 values；主协议 L193-L203 |
| 2 | PASS, artifact A0 | Result/dose exactly-once、不可覆盖、先于 judge/support；L205-L252 |
| 3 | PASS | P1 nearest-rank、success threshold、SE floor、nonfinite 和 gate 唯一；L420-L450，reference L172-L239 |
| 4 | FAIL | Raw P2 Webb/CR1 部分 PASS；matched two-phase RNG/CI 因 P0-STAT-01 不唯一 |
| 5 | PASS | Raw P2 无 marginal/memberwise fallback；retained 也明确禁止 fallback；L582-L584、L843-L847 |
| 6 | PASS | model-based、160,000 draws、model 9,999 replicates及关联输出已删除 |
| 7 | PASS | Raw/corrected 均使用 `M_A/M_T`；L521-L535、L705-L733 |
| 8 | PASS | fixed720、Hamilton、capacity status 和 ties 唯一；L639-L690，`human_quota.py` L155-L310 |
| 9 | PASS | Nine-field retained predicate、status precedence、A/T/H mapping 唯一；L455-L485 |
| 10 | PASS | Judge identity/parser 在任何 formal support label 可见前锁定；L225-L242 |
| 11 | PASS | `900+4000+50+600+30=5580`；human `720/1440/(<=2160)`；L864-L923 |
| 12 | PASS | Active figures、claims、registry、checklist 和 artifact tree 无删除范围残留；L939-L1081 |

## 5. Scope and resource review

没有重新引入任何已删除实验。P2 保持 estimation-only；不要求 power、coverage、全局检验、
multiplicity-adjusted p-value、拒绝决策或 prospective power claim。

逻辑预算仍符合 `compact_single_gpu` profile：

```text
Qwen A/T/H support   900
P2 four cells       4000
K1 reuse               0
harmful clean          50
benign T-steered      600
benign clean           30
total                5580

human response items  720
primary assignments  1440
total assignments    1440 + D_adj, D_adj <= 720
```

模型和 judge 可顺序执行，没有隐藏并行模型、nested simulation 或新增行为分支。实际硬件、
checkpoint 和 inference backend readiness 仍为 A0，但不是本次设计冻结失败原因。

## 6. Final action

只允许以下两个最小规范补丁：

1. 完整绑定 matched two-phase resampling/max-statistic CI；
2. 完整绑定 retained K1/clean/benign bootstrap。

不得增加模型、样本、endpoint、robustness block、testing layer 或恢复已删除范围。不得自动
启动开放式设计迭代或新实验。修补与否由用户决定；修补后应再次执行针对这两个根因的
closure audit，再进入 E0、runtime manifests 和 implementation-fidelity audit。
