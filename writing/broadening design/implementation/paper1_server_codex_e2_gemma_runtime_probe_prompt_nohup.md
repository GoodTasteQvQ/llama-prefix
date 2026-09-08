# E2 Gemma 运行探针任务书

版本：`e2-gemma-runtime-probe-v1`
目的：验证本地 Gemma-2-9B-it 资产、原生 chat template、`resid_pre` 层输入 hook 和单卡运行路径，独立于 safe-pair gate。
本任务不是 E2 正式实验，也不选择剂量、不构造正式方向。

## 1. 硬边界

只使用 `/data/goodtaste_workspace/models/gemma-2-9b-it`、正式解释器和 GPU 0。不得访问 Hugging
Face、下载模型、使用 GPU 1、修改模型目录、修改 canonical config、写 generation/Judge 正式
ledger 或启动 E2/E3 正式 block。不得与其他 GPU 作业并行；发现 GPU 0 已有其他用户或项目作业
时停止并在报告中写 `BLOCKED_GPU_BUSY`，不杀进程。不得 commit/push。

探针输出只能作为 runtime 能力证据，不能解除 safe-pair gate，也不能当作正式行为结果。

## 2. 环境与串行 nohup

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening
export TMPDIR="$PWD/.codex-temp"; export TMP="$TMPDIR"; export TEMP="$TMPDIR"
export NX_DAEMON=false; export CUDA_VISIBLE_DEVICES=0
export HF_HUB_OFFLINE=1; export TRANSFORMERS_OFFLINE=1; export HF_DATASETS_OFFLINE=1
export HF_HOME="$PWD/.hf_cache"; export PYTHONUNBUFFERED=1
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
```

探针脚本和执行必须通过 `nohup`，保存 PID、日志、`.exit`；等待退出后再读取业务 JSON。

## 3. 探针内容

1. 只读检查模型目录 realpath、必需分片、index、config/tokenizer 和资产报告中的权重 hash；
   使用 `local_files_only=True`、`trust_remote_code=False`。
2. 解析 `num_hidden_layers` 和设计规定的 Gemma core layer 公式，确认层索引合法；不得凭经验
   填写固定层或修改设计。
3. 用现有 runtime API 或一次性 `.codex-temp` 探针脚本加载模型，在 GPU 0 做极少量、非评估的
   benign prompts：至少检查原生 chat template、`resid_pre` forward-pre-hook、有限 tensor、
   clean/zero-alpha token-id 一致性和释放生命周期。探针不得进入正式 generation ledger；输出
   只保存必要 trace 摘要、环境版本、GPU UUID 和错误信息。
4. 若现有 runtime API 不支持 Gemma，只记录具体异常并交给实现契约审计任务；不要在本任务中
   重写生产代码或换模型。任何探针失败都不能伪造 PASS。

## 4. 报告

保存：

`writing/broadening design/report/paper1_e2_gemma_runtime_probe_report.md`

报告包含路径/realpath、模型 revision/hash、Python/PyTorch/Transformers/CUDA、GPU UUID、
实际命令/PID/log/exit、探针调用数、template/hook/lifecycle 证据、失败原因（如有）、与正式
E2 gate 的区别，并明确 `E2_FORMAL_EXPERIMENT_NOT_RUN`、`FORMAL_EXPERIMENTS_NOT_RUN`。报告完成
后释放模型并停止。
