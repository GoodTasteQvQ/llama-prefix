# Paper 1 ICLR Broad Supplementary Experiment Specification (No Mistral)

更新时间：2026-08-17

状态：`SUPERSEDED HISTORICAL SNAPSHOT / NO MISTRAL / DO NOT RUN`

当前执行入口：`writing/paper1_minimal_broadening_experiment_design_no_mistral.md`。
本文件保留用于说明 2026-08-17 的较大规模方案和审计依据，不是当前实验授权。文中“运行前
不可变 config、输入清单、SHA256 和 run manifest”的要求属于历史版本，已由当前入口的
“运行前轻量 run header + 结果落地后 provenance manifest”取代。其余旧预算和 block 不能与当前
最小设计混用。

本文件记录 2026-08-17 曾提出的 Paper 1 ICLR 大规模补充实验协议。它明确排除 Mistral；该历史
提案的目标不是做小型 sanity slice，而是形成一项与 Stage 3 规模可比较、同时把有效样本量转移
到 prompt breadth 的跨 prompt、跨方向、跨层和跨方向构造确认研究。

历史要求（不再适用于当前执行）：正式运行前物化不可变 config、输入清单、SHA256、预算和 run
manifest。当前执行的版本化和哈希时点以本文件顶部列出的最小设计为准。

## 1. 研究定位与最大主张

当前 Stage 1/2 已在 Qwen 和 Llama 上各形成 108,000 条 judged records，但主要随机单位仍是固定
prompt 下的 1,000 个 random directions。Stage 3 的完整注册预算为 5,580 条，主要回答固定 Qwen
calibration frame 的测量问题。

本协议把资源用于四个仍未关闭的范围限制：

1. 从单 prompt 扩展到完整 JBB harmful 100-prompt census；
2. 在 Qwen 和 Llama 上形成匹配的 prompt x direction x phase x dose 矩阵；
3. 用一个固定 contrastive activation-direction family 检查 random-vector 特异性；
4. 用三个预设深度检查结果是否只存在于当前 core layer。

全部结果满足时，最大允许主张为：

> Under the evaluated Qwen and Llama checkpoints, phase-aware and failure-aware conclusions extend
> from the original fixed-prompt random-vector setting to the fixed JBB-100 frame, one prespecified
> contrastive activation-direction construction, and three prespecified depths.

该主张不包括第三模型，不代表 activation steering 总体，也不代表一般 harmful behavior、一般
utility、安全保证、连续 threshold 或共同机制。

## 2. 统一设计原则

- 模型固定为 Qwen2.5-7B-Instruct 和 Llama-3.1-8B-Instruct；不得增加第三模型。
- harmful behavior 主 frame 使用完整 JBB100，不选择类别、不删除 baseline 难例。
- prompt 和 direction 完全交叉；token 不是行为推断随机单位。
- 主 dose 轴为 `rho=alpha/median_content_norm`，nominal `c` 和 `mu` 仅作追溯字段。
- 主 phase 只包含 `public_v1` 和 `decode_only`；`no_cache` 仅在固定 semantic slice 中运行。
- 所有模型单独估计；不得把两个模型视为 iid population sample。
- 技术失败、Judge parse failure 和有效 `broken` 输出保持三个不同 disposition。
- 只有技术 gate 可以阻断依赖实验；行为结果不得触发增删实验。

统一 greedy decoder：

```text
do_sample = false
num_beams = 1
max_new_tokens = 512
use_cache = condition-specific
seed = 42
```

继续同时报告 four-class `unsafe/refusal/safe/broken`、Rogue-compatible ASR、ARR、mean 3-gram
repetition、special-token leakage、garbled、very-short、length、latency 和 termination。

## 3. B0：完成现有 Stage 3

严格完成 Stage 3 剩余 680 个 responses、fixed720 human validation、matched two-phase sensitivity
和 final snapshot。不重跑 P1/P2/K1，不移动 anchor，不扩大 human N，不用补充实验改变 Stage 3
estimand。

Stage 3 final snapshot 是本协议正式行为运行的前置 gate。

## 4. B1：Qwen/Llama Full-JBB100 Main Matrix

### 4.1 研究问题

在完整 JBB100 frame 上，持续 cached-decode steering 是否相对 public-v1/prefill-dominant
semantics 更容易在高 dose 形成 broken-dominated composition，并在中 dose 改变 unsafe profile？

### 4.2 Prompt frame

使用 `data/jbb_behaviors_harmful.json` 的完整100条：

```text
10 source categories x 10 prompts/category = 100 prompts
```

使用 Stage 3 JBB split manifest 保留每条 prompt 的 `confirm/screen/unused` membership：

- full100 是主 fixed-frame census；
- `unused-20` 是严格未见正式行为输出的 confirmation subset；
- full100 和 unused20 必须同时报告，unused20 不是独立于 full100 的第二实验；
- 两者不一致时报告 split heterogeneity，不得选择有利 frame。

### 4.3 Random directions 与资产 gate

每模型固定20个 unit-norm random directions，所有 prompts 共用同一20个 identities：

- Qwen 使用 Stage 3 `V_confirm` 20 directions；
- Llama 优先恢复历史正式 pool 的 exact tensor、manifest 和 SHA256；
- 若历史 tensor 无法恢复，可在任何 B1 behavior output 可见前，用固定 generator、hidden size、
  master seed 42 和 namespace `paper1-iclr-broad-llama-random-v1` 生成新 pool；
- 新 pool 必须使用新 artifact identity，不得声称是历史 pool 的 bitwise recovery；
- tensor、row identity、finite/unit-norm audit、manifest 或 SHA256 缺失时，B1 为
  `INPUT-ASSET-BLOCKED`。

20 directions 按 stable identity order 分成4个不重叠的5-direction blocks，用于预设 sensitivity；
不根据 block 结果 reroll 或新增 directions。

### 4.4 Dose 和 conditions

对每个 `model x core_layer`，在完整 JBB100 的 content tokens 上测量并冻结：

```text
median_content_norm(model, core_layer, JBB100)
rho_grid = {0.75, 1.00, 1.25}
alpha = rho * median_content_norm
```

方向先单位归一化。记录 pre/post-dtype alpha、realized rho、relative token dose、layer 和 denominator。

固定 conditions：

| condition | cache | realized target |
|---|---|---|
| `public_v1` | true | audited public prefill-dominant semantics |
| `decode_only` | true | every generated token |

每个 `model x prompt` 另生成一次 no-hook clean baseline，不按 direction 复制。

### 4.5 精确预算

```text
per model steered = 100 prompts x 20 directions x 2 conditions x 3 rho = 12,000
per model clean   = 100
per model total   = 12,100
Qwen + Llama      = 24,200 generations and 24,200 scheduled judges
```

### 4.6 Primary estimands

对每个模型单独估计两个 co-primary fixed contrasts：

```text
Delta_broken_H = mean_(category,prompt,direction) [
  broken(decode_only, rho=1.25) - broken(public_v1, rho=1.25)
]

Delta_unsafe_T = mean_(category,prompt,direction) [
  unsafe(public_v1, rho=1.00) - unsafe(decode_only, rho=1.00)
]
```

10 categories 等权；category 内10 prompts等权；prompt内20 directions等权。技术失败只影响 matched
frame，不进入行为分子。两个 contrasts 使用各自两臂都有效的相同 prompt-direction coordinates。

Secondary：三个 rho 上的 unsafe/broken RD、four-class profile、ASR、ARR、repetition、完整性指标、
category strata、unused20 sensitivity、clean baseline 和四个 direction blocks。

### 4.7 Statistics

- 10,000 synchronized stratified prompt x direction bootstrap replicates；
- prompt 在各 category 内有放回抽样，direction 在20个 identities 上有放回抽样；
- 两臂和三个 rho 共用同一 replicate draws；
- nearest-rank two-sided 95% percentile CI，固定 seed/namespace/member order；
- failed replicate 不 reroll；少于9,500个共同成功 replicate 时只报告 point 和 missingness；
- 不输出模型 pooled p-value、脆弱性排名或一般 population inference。

## 5. B1-N：No-Cache Semantic Slice

目的：在严格 unused20 subset 上补齐 full-sequence/no-cache semantics，而不把 no-cache 扩成新的
full100 矩阵。

固定设计：

```text
2 models x 20 unused prompts x 20 B1 directions x 3 rho x 1 no_cache condition
= 2,400 generations and 2,400 scheduled judges
```

复用 B1 中相同 identities 的 `public_v1` 和 `decode_only` outputs，不重新生成 baseline，不重新计算
core-layer denominator。报告 `no_cache-public_v1` 与 `no_cache-decode_only` 的 high-dose broken RD、
unsafe、four-class、repetition 和 phase counters。该 slice 不支持 full100 no-cache claim。

## 6. B2：Contrastive Activation-Direction Family

### 6.1 定位

B2 只测试一个非随机方向构造：`content-mean-harmful-minus-benign-3fold-v1`。它扩大证据到一个
contrastive construction，但不得被描述为覆盖 optimized、SAE、refusal-suppression 或全部 learned
steering families。

### 6.2 三方向构造

每模型在 core layer 独立构造三条方向。construction frame 使用 Stage 3 P1 的 harmful100
(Do-Not-Answer) 和 benign100 (Dolly)，与 JBB100 evaluation source 分离。

1. harmful 和 benign 分别按 `SHA256(namespace | prompt_identity)` 排序；
2. 依次按 rank modulo 3 分为三个 folds，domain 内fold大小固定为34/33/33；
3. 对每个 prompt，先对 user-content token residuals 求均值得到 `z_p`；
4. 每个 fold 内对 prompts 等权：

```text
d_j = mean_harmful_fold_j(z_p) - mean_benign_fold_j(z_p)
v_j = d_j / ||d_j||_2, j in {0,1,2}
```

5. sign 固定为 harmful minus benign；不得看 behavior/Judge outcome 后翻转；
6. content span 排除 system、role delimiters、special tokens、padding 和 assistant preamble；
7. 三条方向及 fold membership、norm、cosine matrix、SHA256 在 evaluation 前冻结。

任一方向 nonfinite、零范数或 source/evaluation leakage audit 失败时，B2 为 `BLOCKED`，不得换构造。

### 6.3 Evaluation

```text
2 models x JBB100 x 3 contrastive directions x 2 conditions x 2 rho {1.00,1.25}
= 2,400 generations and 2,400 scheduled judges
```

复用 B1 clean baseline。Primary 为每模型、每方向 `rho=1.25` 的 `decode_only-public_v1` broken RD；
同时报告三方向等权 summary、方向间范围、unsafe RD、four-class 和 repetition。prompt bootstrap形成CI；
三条构造方向是固定 sensitivity axis，不作为方向家族 population sample。

## 7. B3：Three-Depth Layer Confirmation

只使用 Qwen/Llama、JBB confirm50、B1 stable order 的前10个 random directions、两个主 conditions 和
`rho=1.25`。

每模型三层为：

- shallow：zero-based index `floor(0.25*(L-1)+0.5)`；
- core：现有 Stage 1/2 主实验 layer；
- deep：zero-based index `floor(0.75*(L-1)+0.5)`。

如 shallow/core/deep 发生重复，必须在任何 behavior output 前以最近的唯一 index 解决并冻结；不得
依据结果移动。每层独立使用 confirm50 测量 content-norm denominator。core layer 的匹配 identities
复用 B1，只新增 shallow/deep：

```text
2 models x 2 additional layers x 50 prompts x 10 directions x 2 conditions x 1 rho
= 4,000 generations and 4,000 scheduled judges
```

每 `model x layer` 报告 high-dose broken/unsafe RD 和95% prompt x direction bootstrap CI。层间只作
预设异质性描述，不拟合连续曲线、不搜索最佳层。

## 8. B4：Llama Benign Integrity Extension

Qwen benign 结果继续来自 Stage 3。B4 只在 Llama 上使用已经固定的 `benign_confirm30`，以及 B1
stable order 前10个 directions：

```text
30 prompts x 10 directions x 2 conditions x rho=1.25 = 600 steered
30 no-hook clean                                      =  30
total                                                 = 630 generations/judges
```

Primary 为 `decode_only-public_v1` broken/incomplete RD；同时报告相对 clean 的完整性、repetition、
length 和可确定 rubric 的 task success。不得由此声称一般 utility、harmlessness 或 capability
preservation。

## 9. B5：Supplement Human Audit

Stage 3 fixed720 保持独立。Supplement 固定 `N=720 responses`，全部双人独立标注，分歧第三人裁决；
标注员不看到 model、direction family、phase、dose、自动标签或论文假设。

### 9.1 H1 matched-phase audit

固定240个 B1 `rho=1.25` matched coordinates，共480 responses：Qwen和Llama各120 pairs。每模型先在
10 categories 等额分配，再在 category 内按 outcome-independent pair identity SHA256 取样。

报告 human-gold `decode_only-public_v1` broken/unsafe RD、paired N 和 matched-pair bootstrap CI。

### 9.2 H2 class-boundary audit

另取240个 single responses，覆盖 B1/B1-N/B2/B3/B4：

- automated `unsafe/refusal/safe/broken` 四主strata各目标60；
- 每类内在 `model x block x phase` 非空cells间 largest-remainder allocation；
- H1 identities 去重；cell内按固定SHA256排序；
- 容量不足时按预设剩余容量规则重分配并记录 inclusion probability。

主结果使用 inverse-probability-weighted confusion matrix、per-class precision/recall/F1、macro-F1；
同时报告raw counts、agreement、adjudication rate、population/sample N和分层描述。人工标签不用于修改
Judge、删除cell、选择方向或重跑生成。

Human budget：720 items、1,440 primary assignments、最多720 adjudications。

## 10. A1：Vector Stability（零新模型调用）

- 将现有 Qwen/Llama full1000 按stable vector ID固定分为5个200-vector blocks；
- 报告block profile、leave-one-block-out和主ordering sensitivity；
- B1额外报告4个预设5-direction blocks；
- 不因任何block异常生成新向量或扩大B1。

## 11. 固定执行顺序

```text
B0 Stage 3 completion and snapshot
-> G0 protocol/config/input/artifact freeze
-> B1 Qwen/Llama full-JBB100
-> B1-N no-cache semantic slice
-> B2 contrastive-family construction freeze and evaluation
-> B3 fixed layer confirmation
-> B4 Llama benign extension
-> B5 human allocation/annotation
-> A1 zero-call analysis
-> final snapshot and claim mapping
```

除技术/资产 gate 外，所有块在 G0 时即确定执行。B1 的方向、区间宽度或类别异质性不得取消、扩大
或改变 B2/B3/B4。技术失败只允许一次 identical-config retry，并进入 disposition ledger。

## 12. 精确资源预算

| block | generation | scheduled judge | 备注 |
|---|---:|---:|---|
| B0 Stage 3 remaining | 680 | 680 | 现有注册工作 |
| B1 Qwen/Llama JBB100 | 24,200 | 24,200 | 主矩阵 |
| B1-N no-cache unused20 | 2,400 | 2,400 | semantic slice |
| B2 contrastive family | 2,400 | 2,400 | Qwen/Llama |
| B3 additional depths | 4,000 | 4,000 | core复用B1 |
| B4 Llama benign | 630 | 630 | benign30 |
| A1 | 0 | 0 | existing records |
| **supplement subtotal excluding B0** | **33,630** | **33,630** |  |
| **combined maximum** | **34,310** | **34,310** | 不含retry |

Measurement/construction forwards（不计generation/Judge）：

```text
B1 dose denominator       = 2 models x 100 prompts = 200
B2 construction           = 2 models x 200 prompts = 400
B3 new-layer denominators = 2 models x 2 layers x 50 prompts = 200
B4 benign denominator     = 1 model x 30 prompts = 30
maximum logical measurement forwards = 830
```

## 13. Artifact、统计和缺失契约

每个正式block使用不可覆盖目录，保存 frozen config、Git/dirty state、环境、model/tokenizer/template、
prompt/vector/layer/hook/Judge SHA256、dose denominator、phase counters、generation/Judge records、
retry/disposition、analysis input/output、human allocation/labels和精确资源账。

每cell报告 scheduled、attempted、retried、completed、judge-eligible、parsed、excluded和matched N。
Raw records 默认 `paper_result_eligible=false`；完整reconciliation、统计复核和final snapshot后才能
赋予evidence eligibility。Smoke/pilot/partial results不得进入论文。

## 14. 结果分支与允许措辞

- Branch A：B1在Qwen/Llama上保持ordering，B2和B3支持有限扩展，human audit不改变方向。允许使用
  本文件第1节的最大措辞。
- Branch B：B1稳定，但B2或B3异质。主张退回 `Rogue-style, model/layer-conditional`，负结果进入正文。
- Branch C：B1存在强prompt/model异质性或human误差改变方向。只报告fixed-frame empirical result，
  不追加prompt、方向、layer或方法。

始终禁止：三模型验证、universal law、一般harmful behavior、自然threshold、模型脆弱性排名、
Attention Sink/structural-token因果、一般utility或安全保证。

## 15. Formal Readiness 与停止规则

当前已具备：JBB100和5/3/2 split、Qwen V_confirm tensor/manifest、P1 harmful100/benign100、
benign_confirm30、Qwen/Llama full1000 summaries、Stage 3 P1/P2/K1结果。

当前阻断项：

- Stage 3剩余680、fixed720、two-phase sensitivity和snapshot；
- Llama exact historical vector tensor恢复，或new supplement pool的预结果生成与冻结；
- B1/B1-N/B2/B3/B4 runners、schemas、offline fixtures和non-overwrite roots；
- content-span、dose、phase-counter、missingness、bootstrap和human-allocation golden fixtures；
- B2三fold方向artifact与leakage audit；
- 所有configs、inputs、budgets和analysis namespaces的G0 snapshot。

最大范围固定为 `B0+B1+B1-N+B2+B3+B4+B5+A1`。不得增加 Mistral、第四层、第四rho、第三方向
family、第二harmful benchmark、stochastic decoding、attention causal实验或full utility benchmark。

