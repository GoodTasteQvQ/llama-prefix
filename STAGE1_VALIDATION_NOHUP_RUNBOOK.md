# Stage 1 Validation `nohup` Runbook

本说明只针对 `Qwen` 的阶段1验证队列，不直接启动 1000 向量 formal 批量。

统一约定：

- 工作目录：`/data/goodtaste_workspace/prefix`
- 配置目录：`configs/local`
- 数据文件：`./data/jbb_behaviors_harmful.json`
- 日志目录：`logs/stage1_validation`
- 输出目录：`results/stage1_phase_aware/validation`

不要再使用：

- `configs/server_local`
- `old/SERVER_NOHUP_RUNBOOK.md`

## 1. 运行前准备

默认你已经手动激活好 Python 环境。

先在前台执行：

```bash
cd /data/goodtaste_workspace/prefix
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES=0
mkdir -p logs/stage1_validation results/stage1_phase_aware/validation results/stage1_phase_aware/summaries
```

如果你实际要用的不是 `0` 号卡，只改 `CUDA_VISIBLE_DEVICES` 即可。

## 2. 提交阶段1验证队列

执行：

```bash
nohup bash ./scripts/stage1_phase_aware/run_stage1_validation_queue.sh \
  > logs/stage1_validation/nohup.out 2>&1 &
echo $!
```

该脚本会串行执行：

1. `mu` 测量
2. Track A A-F 六组 debug
3. Track B A-F 六组 debug
4. `summarize_stage1_results.py`

## 3. 查看日志

看总队列进度：

```bash
tail -f logs/stage1_validation/queue.log
```

看 `nohup` 主输出：

```bash
tail -f logs/stage1_validation/nohup.out
```

看某一步的详细日志：

```bash
tail -f logs/stage1_validation/mu_qwen.log
tail -f logs/stage1_validation/trackA_C_decode_only.log
tail -f logs/stage1_validation/trackB_D_full.log
```

看进程和 GPU：

```bash
ps -ef | grep "stage1_phase_aware" | grep -v grep
watch -n 2 nvidia-smi
```

## 4. 验收标准

至少确认以下文件生成：

- `results/stage1_phase_aware/validation/qwen25_mu_trackB_rogue_v1.json`
- `results/stage1_phase_aware/validation/stage1_trackA_qwen25_rogue_v1_debug.json`
- `results/stage1_phase_aware/validation/stage1_trackB_qwen25_rogue_v1_debug.json`
- `results/stage1_phase_aware/summaries/qwen25_stage1_validation_summary.json`

并检查：

- `logs/stage1_validation/queue.log` 最后一行是 `ALL DONE`
- Track A / Track B 输出里包含：
  - `prefill_calls`
  - `decode_cached_calls`
  - `decode_full_calls`
  - `generated_steered_calls`
- Track B 输出中的 `c / mu / alpha` 关系正确

## 5. 下一步

这一步跑通后，再做：

- 把同样流程从 `--mode debug` 切到 `--mode formal`
- 扩展到 `Llama-3.1-8B-Instruct`
- 扩展到 `Mistral-7B-Instruct-v0.3`
