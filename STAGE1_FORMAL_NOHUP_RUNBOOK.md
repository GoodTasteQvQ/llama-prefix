# Stage 1 Formal `nohup` Runbook

本说明对应 `Qwen` 的阶段1 formal 分批运行。

统一约定：

- 工作目录：`/data/goodtaste_workspace/prefix`
- 配置目录：`configs/local`
- 数据规模：`100` 条 harmful prompts -> 这个改成1条了
- 向量分片：每片 `100` 个向量
- 分片范围：
  - `0-99`
  - `100-199`
  - `200-299`
  - `300-399`
  - `400-499`
  - `500-599`
  - `600-699`
  - `700-799`
  - `800-899`
  - `900-999`

## 1. 运行前准备

```bash
cd /data/goodtaste_workspace/prefix
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES=0
mkdir -p logs/stage1_formal/qwen25/trackA logs/stage1_formal/qwen25/trackB
mkdir -p results/stage1_phase_aware/formal/qwen25/trackA
mkdir -p results/stage1_phase_aware/formal/qwen25/trackB
mkdir -p results/stage1_phase_aware/formal/qwen25/summaries
```

## 2. 先跑最小 formal smoke test

先只跑：

- Track A
- `rogue_v1`
- 第一片 `v0000_0099`

```bash
nohup bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
  trackA \
  rogue_v1 \
  configs/local/stage1_trackA_qwen25_rogue_v1.json \
  results/stage1_phase_aware/formal/qwen25/trackA/stage1_trackA_qwen25_rogue_v1_formal_v0000_0099.json \
  0 99 100 \
  > logs/stage1_formal/qwen25/trackA/trackA_rogue_v1_v0000_0099.log 2>&1 &
echo $!
```

确认：

- 输出文件正常生成
- 日志无报错
- 单片耗时和显存可接受

再批量提交后续分片。

## 3. 第一优先级 formal 队列

第一批只跑论文主线关键组：

- Track A: `rogue_v1`, `decode_only`, `full`
- Track B: `rogue_v1`, `decode_only`, `full`

其中 Track B 统一使用：

- `results/stage1_phase_aware/validation/qwen25_mu_trackB_rogue_v1.json`

### Track A 示例

```bash
nohup bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
  trackA \
  decode_only \
  configs/local/stage1_trackA_qwen25_decode_only.json \
  results/stage1_phase_aware/formal/qwen25/trackA/stage1_trackA_qwen25_decode_only_formal_v0100_0199.json \
  100 199 100 \
  > logs/stage1_formal/qwen25/trackA/trackA_decode_only_v0100_0199.log 2>&1 &
echo $!
```

### Track B 示例

```bash
nohup bash ./scripts/stage1_phase_aware/run_stage1_formal_shard.sh \
  trackB \
  full \
  configs/local/stage1_trackB_qwen25_full.json \
  results/stage1_phase_aware/formal/qwen25/trackB/stage1_trackB_qwen25_full_formal_v0200_0299.json \
  200 299 100 \
  results/stage1_phase_aware/validation/qwen25_mu_trackB_rogue_v1.json \
  > logs/stage1_formal/qwen25/trackB/trackB_full_v0200_0299.log 2>&1 &
echo $!
```

## 4. 建议提交顺序

推荐顺序固定为：

1. `trackA / rogue_v1 / v0000_0099`
2. `trackA / decode_only / v0000_0099`
3. `trackA / full / v0000_0099`
4. `trackB / rogue_v1 / v0000_0099`
5. `trackB / decode_only / v0000_0099`
6. `trackB / full / v0000_0099`
7. 以上 6 个首片都稳定后，再补每组剩余 9 片

如果首片都稳定，希望继续用队列串行补完关键组剩余分片，可直接执行：

```bash
nohup bash ./scripts/stage1_phase_aware/run_stage1_formal_priority_queue.sh \
  > logs/stage1_formal/qwen25/priority_queue.nohup.out 2>&1 &
echo $!
```

该队列会继续完成：

- Track A: `rogue_v1`, `decode_only`, `full`
- Track B: `rogue_v1`, `decode_only`, `full`

每组的剩余分片：

- `v0100_0199`
- `v0200_0299`
- ...
- `v0900_0999`

并在每组结束后自动写 summary。

## 5. 结果汇总

单组分片完成后可执行：

```bash
python scripts/stage1_phase_aware/summarize_stage1_results.py \
  --input results/stage1_phase_aware/formal/qwen25/trackA/stage1_trackA_qwen25_rogue_v1_formal_v*.json \
  --output results/stage1_phase_aware/formal/qwen25/summaries/stage1_trackA_qwen25_rogue_v1_formal_summary.json
```

同理可分别汇总：

- `trackA_rogue_v1`
- `trackA_decode_only`
- `trackA_full`
- `trackB_rogue_v1`
- `trackB_decode_only`
- `trackB_full`

## 6. 查看日志

```bash
tail -f logs/stage1_formal/qwen25/trackA/trackA_rogue_v1_v0000_0099.log
tail -f logs/stage1_formal/qwen25/trackB/trackB_decode_only_v0000_0099.log
tail -f logs/stage1_formal/qwen25/priority_queue.log
tail -f logs/stage1_formal/qwen25/priority_queue.nohup.out
watch -n 2 nvidia-smi
```
