# E1 HarmBench overlap 预处理任务书

版本：`e1-harmbench-overlap-preparation-v1`
目的：在 safe-pair 最终 source 尚未决定时，完成 HarmBench 标准文本的只读完整性核对和 overlap 候选预处理。
本任务不选择最终 40 条，不运行 E1 generation/Judge。

## 1. 边界

使用资产报告登记的 HarmBench 文件和不可变 revision。不得用 JBB 冒充 HarmBench，不得下载模型，
不得修改 HarmBench 原文、safe-pair ledger、JBB、benign frame 或 canonical config。safe-pair source
若将来扩展，E1 overlap gate 必须重新计算；本任务输出只能标记 provisional，不能作为 E1 READY。
不得启动 directions、screen、generation、Judge、analysis 或 human packet；不得 commit/push。

## 2. Linux/nohup

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp"; export TMP="$TMPDIR"; export TEMP="$TMPDIR"
export NX_DAEMON=false; export HF_HUB_OFFLINE=1; export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1; export PYTHONUNBUFFERED=1
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
```

所有校验、转换和 pytest 通过 `nohup`，记录 PID、日志和 `.exit`，每次串行执行。

## 3. 任务步骤

1. 读取 `writing/broadening design/report/paper1_e1_e2_asset_preparation_report.md`，定位
   HarmBench all/standard CSV、metadata、LICENSE 和报告中的 revision/hash；逐文件重算 SHA256。
2. 检查 standard 派生规则是否仅为 `FunctionalCategory == standard`，字段、BehaviorID、source
   index 和 native category 是否保持原样；不重新分类，不抽样改写。
3. 使用当前 JBB100/JBB40/benign30 以及已登记的 public v1 source 做 normalized exact overlap
   和词集合 near-match 预筛，输出 candidate queue、exact exclusions 和每条 source identity。
   这些结果标记 `PROVISIONAL_UNTIL_SAFE_SOURCE_FINAL`；不得把 near-match 自动判为语义排除。
4. 生成临时验证 config 和 deterministic preview，预览设计规定的 native-category rotation，
   但不写最终 E1 40 条，也不执行双 subagent 语义裁决。若 source v1 文件缺失，只报告缺失，
   不用旧 AI pairs 回退。
5. 运行与 E1 loader 相关的离线 tests；失败时报告，不删除测试或改 E1 规则。

## 4. 报告

保存：

`writing/broadening design/report/paper1_e1_overlap_preparation_report.md`

报告包含资产路径/revision/license/hash、输入行数和类别、exact/near overlap 统计、临时输出
路径、实际命令/PID/log/exit、测试结果、为何不能在 safe source 未固定时发布 E1 READY，以及
明确的 `E1_EXPERIMENT_NOT_RUN` 和 `FORMAL_EXPERIMENTS_NOT_RUN`。报告完成后停止。
