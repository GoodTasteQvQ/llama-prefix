# Paper 1 E1/E2 资产准备报告

日期：2026-09-06（Asia/Shanghai）
工作目录：`/data/goodtaste_workspace/llama-prefix`
任务边界：仅资产准备、来源/完整性检查和最小离线预检；没有启动方向构造、screen、generation、Judge 或 analysis。

## 1. 代码同步与环境

- 分支：`stage3/impl-candidate`
- 开始同步时 `HEAD`/`origin/stage3/impl-candidate`：`5c21fd9e15261ee265ff61c16b1b6a74bd94f735`。
- 收尾只读核对时远端和本地已快进到 `fdf68cae1fe5e785ad7607554695c8ff9ba83c18`（`Add public semantic safe-pair integration bundle`）；该并发快进被保留，当前分支仍与 origin 同步。
- 最终 fetch 发现 origin 再次前进至 `6a21b29c483f75c8fe7a57c1fa26689a37cbdfd8`（`Revise experiment scale for public safe pairs`）；随后用 `git merge --ff-only origin/stage3/impl-candidate` 快进，PID `4119382`，日志 `logs/paper1_broadening/e1e2-final-ff-20260906T105705Z-4119380-27342.log`，退出码 `0`。当前本地与 origin 均为 `6a21b29c483f75c8fe7a57c1fa26689a37cbdfd8`。
- 同步命令（按 `nohup` 包装）：`git fetch origin stage3/impl-candidate`，PID `4098278`，日志 `logs/paper1_broadening/e1e2-git-sync-20260906T091747Z-4098275-15773.log`，退出码文件同前缀 `.exit`，退出码 `0`。
- 未执行 `reset`、覆盖式 pull、commit 或 push。保留的用户/并发修改包括：`paper1_broadening/frames.py`、`tests/paper1_broadening/test_frames_directions.py`、`scripts/integrate_public_safe_pairs.py`、`data/safe_pairs_public_semantic_v1.json`、`data/external/semantic_harmful_harmless_v1/integration_manifest.json`；新增 E1 资产和本报告未提交。
- 正式解释器：`/data/goodtaste_workspace/envs/llama-prefix/bin/python`。
- 所有 shell/下载/预检命令先设置：`TMPDIR=TMP=TEMP=/data/goodtaste_workspace/llama-prefix/.codex-temp`。
- 初始磁盘：`/data` 可用约 311G；下载完成后可用约 294G（使用率 94%）。
- 网络预检：DNS 可解析 GitHub/ModelScope；ModelScope HTTPS 返回 200/302；GitHub `git ls-remote` 曾因 TLS 超时失败，但 raw/API 请求可用。

## 2. E1 HarmBench

状态：`ASSET_READY_FOR_OVERLAP_GATE / E1_EXPERIMENT_NOT_RUN`。来源、版本和许可证已确认；按要求没有执行 overlap gate、语义筛选或正式 generation。

来源与文件：

- 仓库：`https://github.com/centerforaisafety/HarmBench`
- 文件：`data/behavior_datasets/harmbench_behaviors_text_all.csv`
- 不可变文件提交（GitHub API path history）：`c0423b952435fcc8467108d8f25962dbae5b7de2`，提交信息 `HarmBench 1.0 update`。
- 文件 API Git blob SHA：`8a6b423d85e9acdc168c57a6a957755cfa86c4cb`；本地 Git blob SHA 相同。
- 原始文件：`data/external/harmbench/harmbench_behaviors_text_all.csv`，400 行，SHA256 `8d81accedd38eaaf8b760618622bb888417d1fd0c86eba65c427a16f1cbb4afc`。
- 许可证：`data/external/harmbench/LICENSE`，MIT（Copyright centerforaisafety 2024），SHA256 `fe29c68dd1216e81e98a6069165e1c720757b23bbcaa6c0cb8f9a957bdaaca80`。
- 简短 metadata：`data/external/harmbench/harmbench_behaviors_text_all.metadata.json`。
- 标准文本派生文件：`data/external/harmbench/harmbench_behaviors_text_standard.csv`，200 行，SHA256 `c2140c25b85480e8e80fb54e1114fc60a518ca0861e3096d164ae9ecda140d06`。规则仅为上游字段 `FunctionalCategory == standard`；添加原始 0-based `source_index`，保留 `BehaviorID`、文本和其他字段原样。原始 400 行文件未改写。
- 原始字段：`Behavior`、`FunctionalCategory`、`SemanticCategory`、`Tags`、`ContextString`、`BehaviorID`。原始 `BehaviorID` 400 个非空且唯一；`SemanticCategory` 7 类；standard 行覆盖 6 类。

E1 实际命令与记录：

1. 官方 raw/API 下载：`curl -L ... harmbench_behaviors_text_all.csv`、`LICENSE`、GitHub commit/file API；PID `4099684`，日志 `logs/paper1_broadening/e1-download-20260906T092606Z-4099681-4635.log`，退出码 `0`。
2. 不可变 commit raw 复核：PID `4107870`，日志 `logs/paper1_broadening/e1-immutable-verify-20260906T101231Z-4107867-3199.log`；raw 请求在 60 秒超时，未将超时猜测为通过。API commit/blob 与本地内容已核验，因此来源版本仍可追溯。
3. standard 派生：PID `4111184`，日志 `logs/paper1_broadening/e1-standard-materialize-20260906T102716Z-4111181-191.log`，退出码 `0`。

E1 没有使用 `data/jbb_behaviors_harmful.json`，没有做 overlap gate，也没有正式选择 40 条；下一 gate 是对独立 HarmBench standard 行执行设计规定的 overlap 审查并记录排除理由，之后才能进入 E1 运行。

## 3. E2 Gemma-2-9B-it

状态：`ASSET_READY_FOR_RUNTIME_CHECK / E2_EXPERIMENT_NOT_RUN`。未执行 E2 dose screen、方向构造或任何 generation/Judge。

最终采用的官方可核验镜像：

- ModelScope：`AI-ModelScope/gemma-2-9b-it`
- 镜像来源 URL：`https://modelscope.cn/models/AI-ModelScope/gemma-2-9b-it`
- revision：`master`；权重文件 revision `dc3d2d5f1517d6f238b394372c8d5d728f56cc15`，config revision `1655fb4e5cb32e82c3580832e2800836c69145e3`，tokenizer revision `ef614e8d344164fab9bb5d02b372f0ad3eca0896`。
- ModelScope model card 标注作者 Google、Gemma license，并链接 `google/gemma-2-9b-it` 模型页；API 架构为 `Gemma2ForCausalLM`、类型 `gemma2`。
- 本地模型路径：`/data/goodtaste_workspace/models/gemma-2-9b-it`
- tokenizer 路径：`/data/goodtaste_workspace/models/gemma-2-9b-it`
- `realpath`：两者均为 `/data/goodtaste_workspace/models/gemma-2-9b-it`，不是符号链接。
- 不使用 Hugging Face，不写入 Git 仓库；模型和缓存均在 `/data/goodtaste_workspace/models/` 与项目 `.codex-temp/modelscope-cache`。

完整性和身份检查：

- 必需文件 13 个全部存在：`.gitattributes`、`config.json`、`configuration.json`、`generation_config.json`、4 个 `model-0000x-of-00004.safetensors`、`model.safetensors.index.json`、`special_tokens_map.json`、`tokenizer.json`、`tokenizer.model`、`tokenizer_config.json`。
- ModelScope API 声明权重总大小 `18,483,411,968` bytes；index 声明 464 个 tensor entry、4 个分片，所有分片存在。
- 4 个权重 SHA256 与 API 完全匹配：`a0d4eb4fcbddfe01b0dc7a58386a3980826ededaf0ecd67d1ef38995b89615ba`、`712a589c333f49f7b6f3870838a9e0ab4b3c0260abd5130e8c54316e6c99640b`、`5a9f84eb9846840802200c6502ccaaebf0a146ee89dcb8822fab795c392dd667`、`3349b4960bbc0bf7e47a624e5c520881adb06e2da4bda6ed14b51c7f647fe26c`。
- `safetensors.safe_open` 检查四个分片实际 dtype 均为 `torch.bfloat16`，不是量化权重。
- `AutoConfig.from_pretrained(local_files_only=True, trust_remote_code=False)`：`Gemma2Config`，`model_type=gemma2`，`architectures=[Gemma2ForCausalLM]`，`num_hidden_layers=42`，`hidden_size=3584`，`vocab_size=256000`，`torch_dtype=bfloat16`。
- `AutoTokenizer.from_pretrained(local_files_only=True, trust_remote_code=False)`：`GemmaTokenizerFast`，词表 256000，BOS/EOS/PAD ids 为 2/1/0，chat template 存在。
- 预检 JSON：`.codex-temp/gemma_asset_verification.json`，最终 `status=PASS`。

E2 实际命令与记录：

1. ModelScope API 元数据/文件清单：PID `4099929`，日志 `logs/paper1_broadening/e1-meta-probe-20260906T092711Z-4099927-11530.log`，退出码 `0`。
2. 初次 `LLM-Research/gemma-2-9b-it` snapshot 尝试因包装路径错误退出 `127`，未产生模型文件；该失败未计作资产通过。
3. 正式 ModelScope snapshot：PID `4107379`，日志 `logs/paper1_broadening/e2-download-20260906T101030Z-4107376-24348.log`，退出码 `0`，13/13 文件完成。
4. 补取隐藏 `.gitattributes`：PID `4114075`，日志 `logs/paper1_broadening/e2-gitattributes-fetch-20260906T103956Z-4114073-21759.log`，退出码 `0`。
5. 官方 AI-ModelScope config/tokenizer 元文件替换（权重未重复下载）：PID `4115720`，日志 `logs/paper1_broadening/e2-ai-official-metadata-20260906T104401Z-4115718-29432.log`，退出码 `0`。
6. 最终逐文件哈希、index/config/tokenizer 预检：PID `4117023`，日志 `logs/paper1_broadening/e2-verify-ai-required-20260906T104930Z-4117021-6498.log`，退出码 `0`。

曾检查的 `LLM-Research/gemma-2-9b-it` 候选与最终选择不同：其权重 SHA 与官方镜像相同，但 config/README 身份包含 Unsloth/4-bit 描述，不能单独作为“准确官方 Gemma”证据；因此最终采用 AI-ModelScope 的官方 config/tokenizer 元文件，并按其 API 清单校验。

## 4. 只读 CLI 资产发现

使用临时配置 `.codex-temp/e1e2_asset_config.json`（未修改基础 `configs/paper1_broadening/mbd_nm_v21.json`）运行：

`nohup ... scripts/paper1_broadening.py discover-assets --config .codex-temp/e1e2_asset_config.json --output .codex-temp/discover-assets-e1e2-20260906T104136Z-4114852-27439.json`

PID `4114855`，日志 `logs/paper1_broadening/discover-assets-e1e2-20260906T104136Z-4114852-27439.log`，退出码 `0`。结果：E1 `READY_FOR_OVERLAP_GATE`；Gemma `READY_FOR_RUNTIME_CHECK`，4 个分片无缺失；该检查未加载模型、未使用 GPU。

## 5. 下一步 gate 与停止确认

- E1 下一步唯一动作：执行独立 HarmBench standard 子集的 overlap 审查/筛选，保留 source index/id 和排除理由；在此之前 E1 保持 `NOT_RUN`。
- E2 下一步唯一动作：在正式运行授权下，以上述本地 realpath、`local_files_only=True` 和 Gemma 原生模板做服务器 runtime/smoke gate；本报告没有运行该 smoke 或任何 E2 实验。
- 方向构造、screen、generation、Judge、analysis、human、archive 均未启动。
- 未修改核心实验参数、safe-pair 审核结果、20,480 预算或历史结果；未执行 Git commit/push。
