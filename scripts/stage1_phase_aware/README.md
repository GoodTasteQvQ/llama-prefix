# Stage 1 Phase-Aware Reproduction

本目录是阶段1 `phase-aware reproduction` 的正式实验入口。

阶段1只做两件事：

- Track A: `fixed_alpha semantic audit`
- Track B: `rogue_calibrated alpha = c * mu`

默认服务器环境：

- 仓库根目录：`/data/goodtaste_workspace/prefix`
- 模型目录：`/data/goodtaste_workspace/models`

请在 `/data/goodtaste_workspace/prefix` 下运行，例如：

```bash
python scripts/stage1_phase_aware/build_stage1_configs.py
python scripts/stage1_phase_aware/run_phase_semantic_matrix.py --config configs/local/stage1_trackA_qwen25_rogue_v1.json --output results/stage1_phase_aware/debug_track_a.json --mode debug
```

如果要在服务器后台串行跑完整的阶段1验证队列，请使用：

- [STAGE1_VALIDATION_NOHUP_RUNBOOK.md](/D:/llama_prefix/STAGE1_VALIDATION_NOHUP_RUNBOOK.md)
- `scripts/stage1_phase_aware/run_stage1_validation_queue.sh`

如果要分片运行阶段1 formal，请使用：

- [STAGE1_FORMAL_NOHUP_RUNBOOK.md](/D:/llama_prefix/STAGE1_FORMAL_NOHUP_RUNBOOK.md)
- `scripts/stage1_phase_aware/run_stage1_formal_shard.sh`
- `scripts/stage1_phase_aware/run_stage1_formal_priority_queue.sh`

## Scripts

- `measure_activation_norm.py`
  - 按 Rogue 风格测量层平均激活范数 `mu`
  - 修正 left padding 下“前 5 个 token 过滤”逻辑
- `run_phase_semantic_matrix.py`
  - 跑 Track A
  - 支持 A-F 六组
  - 支持 debug 单向量与正式 1000 向量批量模式
- `run_rogue_calibrated_matrix.py`
  - 跑 Track B
  - 使用 `alpha = c * mu`
  - 默认 `c = 0.0..2.0, step = 0.25`
- `summarize_stage1_results.py`
  - 汇总阶段1结果
- `build_stage1_configs.py`
  - 生成阶段1正式配置

## Principles

- A 组尽量保持 Rogue v1 攻击实现语义一致
- 不继承 `prompts[20:21]` 的单 prompt slicing
- 1000 个随机向量必须在 A-F 六组间共享
- 只过滤 special token
- Qwen 阶段1默认：
  - `torch_dtype = bfloat16`
  - `max_new_tokens = 512`
  - `do_sample = false`
  - `repetition_penalty` 保持默认
