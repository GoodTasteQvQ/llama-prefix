# Remote Configs

该目录下的配置用于可直接访问 Hugging Face / JailbreakBench 的环境。

统一约定：

- 通过 `dataset_name = JailbreakBench/JBB-Behaviors` 加载 harmful 数据
- 不依赖本地 `./data/jbb_behaviors_harmful.json`
- `experiment_name` 保持原始名称，不附加 `_localdata`

本地服务器无法联网时不要使用本目录配置。

## Stage 1

阶段1正式配置由：

- [build_stage1_configs.py](/D:/llama_prefix/scripts/stage1_phase_aware/build_stage1_configs.py)

生成，核心命名形式为：

- `stage1_trackA_*`
- `stage1_trackB_*`
