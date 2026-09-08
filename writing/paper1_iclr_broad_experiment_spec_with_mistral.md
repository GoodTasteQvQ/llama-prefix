# Paper 1 ICLR Broad Supplementary Experiment Specification (With Mistral)

更新时间：2026-08-17

状态：`DORMANT ALTERNATIVE / INCLUDES MISTRAL / DO NOT RUN WITHOUT EXPLICIT REACTIVATION`

本文件是含 Mistral 的完整替代协议。当前决定是不运行 Mistral，因此本文件不是当前执行入口，
不得据此启动 Mistral 下载、向量生成、sanity、generation 或 Judge。只有在用户明确恢复 Mistral
范围后，才能用本文件整体替换无 Mistral 版本；禁止把两个版本拼接运行或在看到 Qwen/Llama
结果后临时启用 Mistral。

当前执行基线是 `writing/paper1_iclr_broad_experiment_spec_without_mistral.md`。

除第4、5、9、11、12、14、15节明确写出的 Mistral 扩展外，其余科学设计与无 Mistral 版本相同。

## 1. 研究定位与最大主张

本协议将主 random-direction phase matrix 扩展到 Qwen、Llama 和 Mistral，同时仍把第二方向家族、
layer confirmation 和 benign extension 限定在 Qwen/Llama 主线，避免三模型全因子扩张。

全部结果满足时，最大允许主张为：

> Across the evaluated Qwen, Llama, and Mistral checkpoints, the fixed random-direction phase/failure
> ordering extends to the fixed JBB-100 frame. On Qwen and Llama, it is additionally evaluated with
> one prespecified contrastive activation-direction construction and three prespecified depths.

第三模型措辞只来自 Mistral B1/B1-N；不得暗示 Mistral 已完成 contrastive-family、layer 或 benign
实验，也不得声称三个模型来自某个 iid model population。

## 2. 统一设计原则

- B1/B1-N 模型固定为 Qwen2.5-7B-Instruct、Llama-3.1-8B-Instruct、Mistral-7B-Instruct-v0.3。
- B2/B3 固定为 Qwen/Llama；B4固定为Llama；不得补成三模型全因子。
- harmful主frame使用完整JBB100，保留confirm50/screen30/unused20 membership。
- 主dose轴为 `rho=alpha/median_content_norm`；nominal `c` 和 `mu` 仅作追溯字段。
- 主phase为`public_v1`和`decode_only`；`no_cache`只在unused20 semantic slice。
- 模型单独估计，不pool模型，不做脆弱性排名。
- 只有Mistral technical sanity可以决定是否执行Mistral behavior；Qwen/Llama行为结果不能触发
  Mistral启用。

统一 greedy decoder：

```text
do_sample = false
num_beams = 1
max_new_tokens = 512
use_cache = condition-specific
seed = 42
```

所有block报告four-class、ASR、ARR、3-gram repetition、完整性、length、latency、termination、
phase counters和严格missingness。

## 3. B0：完成现有 Stage 3

严格完成Stage 3剩余680、fixed720、matched two-phase sensitivity和final snapshot。不重跑P1/P2/K1，
不移动anchor，不扩大human N。Stage 3 snapshot是全部新行为运行的前置gate。

## 4. B-M：Mistral Technical Sanity 与资产 Gate

### 4.1 Vector asset

Mistral需要20个固定unit-norm random directions：

- 优先恢复历史正式pool exact tensor、manifest和SHA256；
- 无法恢复时，只能在任何本协议behavior output可见前，用固定generator、hidden size、seed42和
  namespace `paper1-iclr-broad-mistral-random-v1` 生成新pool；
- 新pool必须使用新artifact identity，不得声称bitwise recovery；
- tensor/manifest/finite/unit-norm/SHA256缺失则Mistral为`INPUT-ASSET-BLOCKED`。

### 4.2 Zero-strength/cache sanity

从JBB unused20按source order取前10条，每条只运行：

1. no hook + `use_cache=true`；
2. hook installed + `alpha=0` + `use_cache=true`；
3. hook installed + `alpha=0` + `use_cache=false`。

合计30 generations、0 Judge。不同vector metadata不复制。记录首步full-logit comparison摘要、top-k、
token hashes、EOS/stop、template/token IDs、dtype和phase counters。

同cache下no-hook与alpha-zero hook必须在冻结dtype tolerance内一致，greedy tokens和stopping完全一致；
否则`IMPLEMENTATION-FIX-REQUIRED`。cache/no-cache差异允许存在并作为execution baseline记录。

sanity PASS后必须执行完整Mistral B1/B1-N；BLOCKED时不替换模型、不转移其预算。

## 5. B1：Three-Model Full-JBB100 Main Matrix

### 5.1 Prompt、directions、dose和conditions

使用完整JBB100：10 categories x10 prompts。full100为主fixed census，unused20为严格confirmation
subset；二者结果同时报告，不选择有利frame。

每模型20个固定random directions：Qwen使用V_confirm；Llama和Mistral分别恢复历史pool或按
`paper1-iclr-broad-llama-random-v1` 和 `paper1-iclr-broad-mistral-random-v1` namespace在预结果
阶段生成。每模型20 directions按stable identity分为4个5-direction blocks。

每个`model x core_layer`在JBB100 content tokens上独立冻结denominator：

```text
rho_grid = {0.75,1.00,1.25}
alpha = rho * median_content_norm(model, core_layer, JBB100)
```

conditions固定为`public_v1`和`decode_only`。每个model-prompt另生成一次clean baseline。

### 5.2 精确预算

```text
per model = 100 prompts x 20 directions x 2 conditions x 3 rho + 100 clean
          = 12,100
three models = 36,300 generations and 36,300 scheduled judges
```

### 5.3 Estimands 与统计

每模型单独估计：

```text
Delta_broken_H = broken(decode_only, rho=1.25) - broken(public_v1, rho=1.25)
Delta_unsafe_T = unsafe(public_v1, rho=1.00) - unsafe(decode_only, rho=1.00)
```

10 categories、category内prompts、prompt内directions依次等权。只使用两臂有效的matched
prompt-direction coordinates。Secondary包括三个rho的profile/RD、ASR、ARR、repetition、完整性、
category、unused20和direction-block sensitivity。

每模型使用10,000 synchronized stratified prompt x direction bootstrap；prompt在category内重采样，
direction在20 identities上重采样；固定seed/namespace/member order，nearest-rank 95% CI。模型不pool。

## 6. B1-N：Three-Model No-Cache Semantic Slice

```text
3 models x 20 unused prompts x 20 directions x 3 rho x 1 no_cache condition
= 3,600 generations and 3,600 scheduled judges
```

复用B1相同identities的public_v1/decode_only outputs、baseline和core denominator。每模型单独报告
`no_cache-public_v1`及`no_cache-decode_only` high-dose broken RD、unsafe、four-class、repetition和
phase counters。不得外推到fullJBB100 no-cache。

## 7. B2：Qwen/Llama Contrastive Activation-Direction Family

B2不加入Mistral。每个Qwen/Llama模型在core layer使用Stage 3 P1 harmful100和benign100构造
`content-mean-harmful-minus-benign-3fold-v1`：

1. 两domain分别按`SHA256(namespace|prompt_identity)`排序并rank modulo3分fold（34/33/33）；
2. 每prompt先对user-content residuals求均值；
3. 每fold方向为prompt-equal harmful mean minus benign mean，再单位归一化；
4. sign、fold、content span、norm、cosine matrix和SHA256在evaluation前冻结；
5. nonfinite/zero/leakage失败则B2 BLOCKED，不换构造。

Evaluation：

```text
2 models x JBB100 x 3 directions x 2 conditions x 2 rho {1.00,1.25}
= 2,400 generations and 2,400 scheduled judges
```

Primary为每模型、每方向high-dose`decode_only-public_v1` broken RD；报告三方向等权summary、范围、
unsafe、four-class和repetition。只能声称one contrastive construction，不得泛化全部direction families。

## 8. B3：Qwen/Llama Three-Depth Confirmation

B3不加入Mistral。使用JBB confirm50、B1前10 random directions、两个主conditions、rho1.25。

- shallow index：`floor(0.25*(L-1)+0.5)`；
- core：现有主实验layer；
- deep index：`floor(0.75*(L-1)+0.5)`。

重复index在预结果阶段取最近唯一index并冻结。core匹配identities复用B1，只新增两层：

```text
2 models x 2 layers x 50 prompts x 10 directions x 2 conditions
= 4,000 generations and 4,000 scheduled judges
```

每model-layer报告high-dose broken/unsafe RD和prompt x direction bootstrap CI；只作离散异质性，不搜层。

## 9. B4：Llama Benign Integrity Extension

Mistral不加入benign。Qwen使用Stage 3 benign结果；Llama使用固定benign_confirm30和B1前10 directions：

```text
30 prompts x 10 directions x 2 conditions x rho1.25 + 30 clean
= 630 generations and 630 scheduled judges
```

报告phase broken/incomplete RD、相对clean完整性、repetition、length和可确定rubric的task success；
不建立一般utility、harmlessness或capability结论。

## 10. B5：Three-Model Supplement Human Audit

Stage 3 fixed720独立保存。Supplement固定720 responses，双人盲标，分歧第三人裁决。

H1：固定240个B1 rho1.25 matched pairs，共480 responses；Qwen/Llama/Mistral各80 pairs。每模型在
10categories等额分配后按outcome-independent pair SHA256取样。报告每模型human-gold phase
broken/unsafe RD和matched-pair bootstrap CI。

H2：另取240 single responses，automated四类各目标60；在`model x block x family x phase`非空cells
间largest-remainder allocation，H1去重并记录inclusion probability。主报告design-weighted confusion
matrix、per-class precision/recall/F1、macro-F1，同时给raw counts/agreement/adjudication。

Mistral只在B1/B1-N cells进入H2；不得伪造不存在的Mistral B2/B3/B4 strata。

Human budget：720 items、1,440 primary assignments、最多720 adjudications。

## 11. A1 与固定执行顺序

A1只重分析现有Qwen/Llama full1000的5个200-vector blocks和B1每模型4个5-direction blocks；不生成
新向量。Mistral历史100-sample若artifact不完整，不进入A1正式claim。

```text
B0 Stage 3 completion
-> G0 all-version protocol freeze and explicit Mistral reactivation record
-> B-M Mistral asset/sanity
-> B1 Qwen/Llama/Mistral full-JBB100 (Mistral only after sanity PASS)
-> B1-N three-model no-cache slice
-> B2 Qwen/Llama contrastive family
-> B3 Qwen/Llama layers
-> B4 Llama benign
-> B5 human audit
-> A1
-> final snapshot and claim mapping
```

技术sanity之外，行为结果不触发块的增删。Mistral sanity PASS后不得因先导behavior方向取消完整B1/B1-N。

## 12. 精确资源预算

| block | generation | scheduled judge | 备注 |
|---|---:|---:|---|
| B0 Stage 3 remaining | 680 | 680 | 现有注册工作 |
| B-M Mistral sanity | 30 | 0 | technical only |
| B1 three-model JBB100 | 36,300 | 36,300 | 主矩阵 |
| B1-N three-model no-cache | 3,600 | 3,600 | unused20 |
| B2 contrastive family | 2,400 | 2,400 | Qwen/Llama |
| B3 additional depths | 4,000 | 4,000 | Qwen/Llama |
| B4 Llama benign | 630 | 630 | benign30 |
| A1 | 0 | 0 | existing records |
| **supplement subtotal excluding B0** | **46,960** | **46,930** | 含sanity |
| **combined maximum** | **47,640** | **47,610** | 不含retry |

Mistral阻断分两种固定账目：

- vector/model asset在sanity前BLOCKED：不产生任何Mistral调用，combined maximum回到无Mistral版的
  34,310 generations和34,310 judges；
- 30次sanity已运行后BLOCKED：combined maximum为34,340 generations和34,310 judges。

两种情况都不运行Mistral B1/B1-N；未使用的13,300个behavior identities不得转移到其他模型、
direction、layer或family。

Measurement/construction forwards：

```text
B1 denominators            = 3 x 100 = 300
B2 construction            = 2 x 200 = 400
B3 additional layers       = 2 x 2 x 50 = 200
B4 benign denominator      = 1 x 30 = 30
maximum logical forwards   = 930
```

## 13. Artifact、missingness 与 eligibility

每block使用不可覆盖目录，保存config、Git/dirty state、环境、model/tokenizer/template、prompt/vector/
layer/hook/Judge hashes、dose、phase counters、generation/Judge、retry/disposition、analysis和human
artifacts。每cell报告scheduled/attempted/retried/completed/judge-eligible/parsed/excluded/matched N。

Raw records默认`paper_result_eligible=false`；只有完整reconciliation、统计复核和final snapshot后才能
升级。Smoke/pilot/partial outputs不得进入论文。

## 14. 结果分支与允许措辞

- Branch A：三模型B1保持ordering，Qwen/Llama B2/B3有限扩展，human audit支持。允许第1节最大措辞。
- Branch B：Qwen/Llama稳定但Mistral异质，或B2/B3异质。分别报告model/family/layer conditionality，
  不删除Mistral负结果。
- Branch C：B1强prompt/model异质或human误差改变方向。退回fixed-frame empirical result，不扩实验。

始终禁止：模型population generalization、universal steering law、所有攻击家族、自然threshold、模型排名、
Attention Sink因果、一般utility/harmlessness或安全保证。

## 15. Activation、Readiness 与停止规则

本文件当前最关键的前置条件是用户明确书面恢复 Mistral scope。在此之前，Mistral所有动作均禁止。

恢复后仍需：Stage 3完成；Llama/Mistral vector tensor恢复或新pool预结果冻结；Mistral sanity runner；
B1-B5 runners/schemas/fixtures；B2 direction artifacts；human allocator；non-overwrite roots；统计golden
fixtures和G0 snapshot。

最大范围固定为`B0+B-M+B1+B1-N+B2+B3+B4+B5+A1`。不得增加第四模型、Mistral B2/B3/B4、第四层、
第四rho、第三direction family、第二harmful benchmark、stochastic decoding、attention causal实验或
full utility benchmark。
