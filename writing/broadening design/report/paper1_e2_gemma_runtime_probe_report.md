# Paper 1 E2 Gemma Runtime Probe Report

版本：`e2-gemma-runtime-probe-v1`  
日期：2026-09-08（Asia/Shanghai）  
状态：`RUNTIME_PROBE_PASS`；`E2_FORMAL_EXPERIMENT_NOT_RUN`；`FORMAL_EXPERIMENTS_NOT_RUN`

## 1. 边界与 GPU

- 严格按 `writing/broadening design/implementation/paper1_server_codex_e2_gemma_runtime_probe_prompt_nohup.md` 执行。
- 工作目录：`/data/goodtaste_workspace/llama-prefix`。
- 解释器：`/data/goodtaste_workspace/envs/llama-prefix/bin/python`。
- 只使用 `CUDA_VISIBLE_DEVICES=0`；没有使用 GPU 1、Hugging Face 或网络下载。
- 启动前 GPU 0 无计算进程：A100 80GB，UUID `GPU-e7424758-25c8-291b-e80f-c1f8c677b127`，252 MiB 驱动占用。
- 探针退出后外部复核：GPU 0 仍无计算进程，252 MiB，占用率 0%。未终止任何其他进程。
- 未发现 `BLOCKED_GPU_BUSY` 条件；因此本报告不是 busy-block 报告。

## 2. 资产与身份核对

模型与 tokenizer 均为：
`/data/goodtaste_workspace/models/gemma-2-9b-it`，realpath 相同，非符号链接。

既有资产报告：`.codex-temp/gemma_asset_verification.json`，报告状态 `PASS`。本次再次逐文件核对报告中的 SHA256；必需文件 13/13 存在且一致。关键 hash 如下：

| 文件 | SHA256 |
|---|---|
| `config.json` | `8ecc124513fdb0bb31bf51b4f0dd6c8658a68296dc8cd30af612205ff4a1bc49` |
| `model.safetensors.index.json` | `c38b39b80b2d7aa422464a9b816af4c30d2177e471b89e5325df1336a23ad284` |
| `model-00001-of-00004.safetensors` | `a0d4eb4fcbddfe01b0dc7a58386a3980826ededaf0ecd67d1ef38995b89615ba` |
| `model-00002-of-00004.safetensors` | `712a589c333f49f7b6f3870838a9e0ab4b3c0260abd5130e8c54316e6c99640b` |
| `model-00003-of-00004.safetensors` | `5a9f84eb9846840802200c6502ccaaebf0a146ee89dcb8822fab795c392dd667` |
| `model-00004-of-00004.safetensors` | `3349b4960bbc0bf7e47a624e5c520881adb06e2da4bda6ed14b51c7f647fe26c` |
| `tokenizer.json` | `3f289bc05132635a8bc7aca7aa21255efd5e18f3710f43e3cdb96bcd41be4922` |
| `tokenizer_config.json` | `cb32b7929c62608d46572e813112b3ad8a841fb98fdd6a4da8559e368a951c89` |

Index 含 464 个 tensor entry、4 个声明分片，`total_size=18483411968`，全部分片存在。模型 revision 记录为权重 `dc3d2d5f1517d6f238b394372c8d5d728f56cc15`；config revision `1655fb4e5cb32e82c3580832e2800836c69145e3`；tokenizer revision `ef614e8d344164fab9bb5d02b372f0ad3eca0896`。

## 3. Runtime 环境与命令证据

运行时版本：Python 3.10.20；PyTorch `2.12.0+cu126`；Transformers `4.57.6`；CUDA `12.6`；可见 GPU 数 `1`。

最终成功命令通过 `nohup` wrapper 串行执行：

```text
nohup bash .codex-temp/run_gemma_runtime_probe_nohup.sh >/dev/null 2>&1 &
```

wrapper 内固定使用正式解释器和 `CUDA_VISIBLE_DEVICES=0`。最终记录：

- PID 文件：`logs/paper1_broadening/e2-gemma-runtime-probe-20260908T054500Z.pid`（PID `373225`；业务 Python PID `373227`）。
- 日志：`logs/paper1_broadening/e2-gemma-runtime-probe-20260908T054500Z.log`。
- 退出文件：`logs/paper1_broadening/e2-gemma-runtime-probe-20260908T054500Z.exit`，内容 `0`。
- 业务结果：`.codex-temp/gemma_runtime_probe_result.json`。

此前两个启动包装异常（`.exit=127`，无业务进程）和一次缺少仓库导入路径的探针（`.exit=1`）均未计为通过；没有模型残留，且没有正式实验副作用。修正临时 wrapper 后的最终运行才计入本报告。

所有 Transformers 加载均使用 `local_files_only=True`、`trust_remote_code=False`；没有修改生产 runtime、模型目录或 canonical config。

## 4. Runtime 探针结果

| 检查 | 结果 | 证据 |
|---|---|---|
| 原生 Gemma chat template | PASS | `GemmaTokenizerFast`；`apply_chat_template(add_generation_prompt=True)`；模板存在；输入 20 tokens |
| `num_hidden_layers` 与设计公式 | PASS | `Gemma2Config`，`L=42`，`floor((L-1)/3+0.5)=14`，zero-based 层 14 合法 |
| `resid_pre` forward-pre-hook | PASS | 现有 `BehaviorRuntime` 在层输入注册一次 `register_forward_pre_hook`；capture shape `[11,3584]` |
| tensor finite | PASS | residual 转 CPU float32 后 `torch.isfinite(...).all()` 为真 |
| clean / zero-alpha token ids | PASS | 同一 benign prompt、seed 42、生成 ids 完全一致：`[235274,235265,5231,138540,766,12991,3641,66058]` |
| 模型释放与生命周期 | PASS | `release()` 清理 model/tokenizer/layer 引用，移除 hook，GC、CUDA synchronize、empty_cache；`models_concurrently_resident=false` |

Benign prompt 仅为：`Give two short, practical tips for organizing a desk.`。探针使用一个临时 unit vector 进行 `alpha=0.0` API 一致性检查；未持久化该 vector，没有方向 id、fold、mu、dose 或正式方向构造。探针没有写 generation/Judge ledger。

## 5. 生命周期与正式 gate 区分

探针 JSON 中明确记录：`formal_experiment=false`、`formal_generation_ledger_written=false`、`judge_ledger_written=false`、`dose_selected=false`、`formal_direction_constructed=false`、`formal_e2_started=false`、`formal_e3_started=false`。模型在 release 前存在，release 后 `model/tokenizer/layer_module` 均为 `None`；最终 Python 进程退出后外部 GPU 复核为空闲。

`RUNTIME_PROBE_PASS` 只证明本地 Gemma 资产、原生模板和现有 runtime 的最小 hook 路径可运行。它不通过 safe-pair gate，不选择 E2 剂量，不构造正式方向，也不解除正式 E2 前置条件。因此：

**`E2_FORMAL_EXPERIMENT_NOT_RUN`**  
**`FORMAL_EXPERIMENTS_NOT_RUN`**

本任务未启动 E2/E3 正式 block、screen、generation、Judge、analysis 或 human packet。
