# Paper 2 写作蓝图

## 暂定标题

可选标题：

- Phase-Aware Dynamic Activation Guard for Defending Against Steering Attacks
- Dynamic Activation Guardrails for Inference-Time Steering Attacks in Large Language Models
- Phase-Aware and Norm-Calibrated Defense Against Activation Steering Attacks

推荐主标题方向：

> Phase-Aware Dynamic Activation Guard: Utility-Preserving Defense Against Inference-Time Steering Attacks

## 一句话主张

由于 activation steering 的风险和副作用高度依赖 prefill / decode 阶段语义，安全向量防御不能静态全程插入，而应基于异常投影分数进行 phase-aware、norm-calibrated 的动态干预。

## 摘要骨架

摘要建议固定为四句话：

1. 背景句：现有 activation steering 防御通常采用静态全程插入，容易损伤正常生成能力。
2. 动机句：我们的前期审计表明 steering 的真实生效阶段决定攻击与防御结论，并且 decode-time 干预容易引发 collapse。
3. 方法句：我们提出 `phase-aware dynamic activation guard`，在 prefill 轻量校正，在 decode 仅对异常投影越阈值的 token 进行 gated 干预。
4. 结果句：在三模型、多攻击设置下，该方法相较静态 steering 取得更好的 `ASR / UFR / FRR / ARR / utility / latency` 平衡。

## 章节结构

### 1. Introduction

这节要回答：

- 为什么静态 activation steering 防御不够好
- 为什么 dynamic / phase-aware 是自然需求
- 这篇方法解决什么问题

结尾固定贡献：

1. 提出 phase-aware dynamic activation guard
2. 提出 projection-based, norm-calibrated trigger
3. 在多模型、多攻击、多指标下验证更好的 safety-utility-collapse trade-off

### 2. Background and Motivation

这节只复用 Paper 1 的必要背景：

- activation steering 攻击/防御概念
- Paper 1 的核心发现：when steering happens matters
- 为什么 decode 全程干预会有 collapse 风险

不要重新展开大篇幅 Rogue 审计。

### 3. Threat Model

必须明确：

- 防御的是 `inference-time activation steering attack`
- 不是通用 prompt jailbreak 的完整解决方案
- 不是攻击者可任意关掉 defense hook 的最强白盒
- 防御目标是降低 harmful 顺从，同时保留 harmless / utility

### 4. Method: Phase-Aware Dynamic Activation Guard

这是正文核心。

建议按以下小节写：

1. safety direction extraction
2. projection-based anomaly score
3. prefill base correction
4. decode-time gated intervention
5. first-k / decay variants

公式层面建议固定为：

- score：`s = h · v_safe_hat` 或其 norm-calibrated 版本
- trigger：`ReLU(s - T)`
- intervention：`C_base + k * ReLU(s - T)`

### 5. Experimental Setup

写清楚：

- 三模型
- 攻击设置
- harmful / harmless / utility 数据
- train / validation / test 划分
- 层、阈值、`k`、`base` 的选择流程

这节一定要避免“测试集调参”嫌疑。

### 6. Main Results

这一节用于放主表：

- no defense
- static defense
- prefill-only
- decode-only
- full
- phase-aware first-k
- phase-aware decay / gated

指标必须至少包含：

- `ASR`
- `UFR`
- `FRR`
- `ARR`
- `repetition rate`
- `special-token leakage`
- `avg output length`
- `utility`
- `latency`

### 7. Ablations and Analysis

这节回答“为什么方法有效”。

建议分成：

1. projection vs cosine vs norm
2. layer ablation
3. threshold / `k` / `base` ablation
4. first-k vs full decode
5. decay vs static

### 8. Robustness and Generalization

这一节用来顶住审稿人的常见质疑。

至少回答：

- 不同随机种子 random steering 是否稳定
- 不同攻击层 / 强度是否稳定
- stronger steering variant 是否还能防
- 跨模型是否仍然有效

### 9. Discussion and Limitations

重点写：

- 该方法并不是万能安全方案
- 对更强白盒攻击仍有限制
- utility benchmark 仍可扩展

## 图表清单

### 主文图

Figure 1. phase-aware defense 机制示意图  
用途：清楚展示 prefill base + decode gated 的工作方式

Figure 2. projection score 分布图  
用途：展示 harmful / harmless 在安全方向上的分离

Figure 3. static vs dynamic defense 的 safety-utility 曲线  
用途：直观体现 trade-off 改善

Figure 4. first-k / decay / full decode 的对比图  
用途：说明为什么 phase-aware 优于全程 decode 干预

Figure 5. 三模型主结果图  
用途：展示跨模型一致性或差异性

### 主文表

Table 1. 防御方法设置表  
列：no defense、static、prefill-only、decode-only、phase-aware first-k、phase-aware decay

Table 2. harmful 主结果表  
列：`ASR`、`ARR`、`repetition`、`latency`

Table 3. harmless / utility 主结果表  
列：`UFR`、`FRR`、utility score、`avg output length`

Table 4. 消融实验表  
列：projection、cosine、norm、不同层、不同 `T/k/base`

## 实验到章节映射

### 章节 4 对应实验

- safety vector 提取
- score ablation
- projection 分布

### 章节 6 对应实验

- defense 主实验
- harmful judge + harmless judge
- summary 输出

### 章节 7 对应实验

- projection vs cosine vs norm
- layer / threshold / `k` / first-k / decay 消融

### 章节 8 对应实验

- 不同随机种子 / 强度 / 层
- stronger steering variant
- 三模型对比

## 最小必跑结果

如果只保最小成稿包，优先保证下面这些结果完整：

1. `no defense / static / phase-aware` 三线主比较
2. harmful + harmless 双评估
3. projection vs cosine vs norm 消融
4. first-k / decay / full decode 消融
5. 三模型结果

这五组结果做扎实，Paper 2 就具备独立成稿基础。

## 写作提醒

- 不要把方法写成“抵消 Rogue 向量”
- 要写成“检测并校正异常 activation deviation”
- 主结果必须同时报安全收益和正常能力损失
- 审稿人最关心的是：dynamic defense 是否真的比 static defense 更少误伤、更少 collapse
