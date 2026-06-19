# Local Configs

该目录下的配置用于无法访问 Hugging Face / JailbreakBench 的环境。

统一约定：

- harmful 数据从 `./data/jbb_behaviors_harmful.json` 读取
- 配置中保留 `dataset_name` / `dataset_config` / `split` 仅用于记录原始数据来源
- 实际加载以 `dataset_path` / `dataset_format` 为准
- `experiment_name` 统一带 `_localdata`，避免与联网环境输出重名

服务器上优先使用本目录配置。

## Stage 1

阶段1正式配置由：

- [build_stage1_configs.py](/D:/llama_prefix/scripts/stage1_phase_aware/build_stage1_configs.py)

生成，核心命名形式为：

- `stage1_trackA_*`
- `stage1_trackB_*`

其中：

- Track A = `fixed_alpha semantic audit`
- Track B = `rogue_calibrated alpha = c * mu`
