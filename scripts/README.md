# Scripts Layout

当前默认运行环境已经切到 Linux 服务器：

- 仓库根目录：`/data/goodtaste_workspace/prefix`
- 模型目录：`/data/goodtaste_workspace/models`

请从仓库根目录执行脚本。配置里的 `./data`、`./results`、`./vectors` 相对路径都依赖这个前提。

当前脚本目录已经清理为两层：

- 顶层 `scripts/*.py`
  - 保留通用真实实现脚本
- `scripts/stage1_phase_aware/`
  - 保留阶段1正式实验入口

推荐按下面的分组理解当前代码结构：

## `scripts/stage1_phase_aware/`

阶段1正式实验入口，专门对应：

- Track A: `fixed_alpha semantic audit`
- Track B: `rogue_calibrated alpha = c * mu`

包含：

- `measure_activation_norm.py`
- `run_phase_semantic_matrix.py`
- `run_rogue_calibrated_matrix.py`
- `summarize_stage1_results.py`
- `build_stage1_configs.py`

## 顶层 Phase Matrix

对应配置主要在：

- `configs/local/`
- `configs/remote/`

服务器优先使用 `configs/local/`；可联网环境再使用 `configs/remote/`。
两套配置现在都默认指向服务器本地模型目录，而不是 Hugging Face model id。

## 顶层 Evaluation

用于对生成结果做 judge 和 summary。

- `judge_phase_outputs.py`
- `summarize_phase_results.py`

## 顶层 Vectors

用于安全向量提取与层扫描。

- `extract_safe_vectors.py`

## 顶层 Analysis

用于机制分析与 score 对照实验。

- `analyze_attention_sink.py`
- `run_score_ablation.py`

这里建议把攻击强度协议拆成两条线分别记录：

- `fixed-alpha semantic audit`
- `rogue-calibrated alpha = c * mu`

## 顶层 Setup

用于实验准备，包括数据、模型和本地配置。

- `download_jbb_behaviors.py`
- `download_qwen25_7b_it.py`
- `download_mistral_7b_it_v03.py`
- `download_llama31_8b_it.py`
- `make_local_model_configs.py`

模型下载脚本仅作为补充工具保留；如果服务器上的模型目录已经准备好，主实验不依赖这些脚本。

## Compatibility

现在不再保留旧的分组 wrapper 目录。

后续请统一：

- 顶层 `scripts/*.py` 调用真实实现
- `scripts/stage1_phase_aware/` 调用阶段1正式实现

## Strength semantics

当前框架里的攻击强度需要严格区分：

- `fixed_alpha`
  - 直接把 `attack.coefficient` 当作最终注入强度 `alpha`
  - 适用于阶段语义审计
- `rogue_calibrated`
  - 使用 `alpha = c * mu`
  - 其中 `coefficient_c` 是 Rogue 风格倍率，`activation_norm_mu` 是层依赖平均激活范数
  - 适用于与 Rogue 论文数值结果对齐的攻击复现

后续文档、图表和论文中，不能再把单个 `coefficient` 同时混称为 `c` 与 `alpha`。
