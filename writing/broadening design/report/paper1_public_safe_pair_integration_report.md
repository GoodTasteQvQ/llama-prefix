# Paper 1 Public Safe-Pair Integration Report

执行日期：2026-09-06（UTC）。本报告对应任务书 `public-semantic-pairs-integration-v1`，不代表人工安全验证。

## 基线与运行边界

- branch：`stage3/impl-candidate`
- HEAD：`fdf68cae1fe5e785ad7607554695c8ff9ba83c18`
- 初始 dirty 状态：仅有用户已有未跟踪目录 `data/external/harmbench/`；本任务新增文件未覆盖已有文件。
- Python：`/data/goodtaste_workspace/envs/llama-prefix/bin/python`，3.10.20；GPU 仅可见 `CUDA_VISIBLE_DEVICES=0`；HF/Transformers/Datasets offline，`TMPDIR=$PWD/.codex-temp`。
- 所有转换、校验、pytest、review 合并和 prepare 均通过任务书 `launch_nohup` 包装，PID、日志和 `.exit` 保存在 `logs/paper1_broadening/`。
- 转换：PID `4114059`，`public-pair-convert-20260906T103955Z-4114056-18925.{log,pid,exit}`，exit `0`。
- preliminary prepare：PID `4114676`，`public-pair-preliminary-prepare-20260906T104128Z-4114673-26177.*`，exit `0`。
- 离线 pytest：PID `4115427`，`public-pair-tests-20260906T104320Z-4115424-4921.*`，exit `0`，`40 passed in 9.15s`。
- 双审核合并：PID `4119033`，`public-pair-review-combine-20260906T105603Z-4119030-16706.*`，exit `0`。
- 最终 prepare：PID `4119141`，`public-pair-prepare-20260906T105642Z-4119138-13106.*`，exit `0`。

## Source bundle 与哈希

source 目录：`data/external/semantic_harmful_harmless_v1/source/`。

- `heretic-org/Semantic-Harmful` revision `001ca2ceaef94a748235e0ba1366aee48436e286`，URL 已原样记录于 manifest。
- `heretic-org/Semantic-Harmless` revision `7e9f2b01272da85f2be7a3437f31ac46698e8735`，URL 已原样记录于 manifest。
- source manifest 声明配对仓库许可证 `CC-BY-4.0`。两个 README 的原文均声明 `Creative Commons Attribution 4.0 International`；许可证正文保留为 `semantic_harmful_LICENSE` 与 `semantic_harmless_LICENSE`（两者相同）。
- README 原文说明 harmful 来自 `mlabonne/harmful_behaviors`、harmless 来自 `mlabonne/harmless_alpaca`；这些上游数据卡的许可字段在 source manifest 中原样披露为不完整/缺失，未作法律保证。
- source SHA256：`matched_pairs.json` `d066ddd4a8005271d21f269aacc4cc30bfb5d2f1d7004f3f37004e42f63f5225`；`semantic_harmful_README.md` `2157ee61e1e2b180f2c8ba5c702566bb7f29b3f41155368d673b2c65d7cf87a3`；`semantic_harmless_README.md` `ec4c6c98e47c723d4ba73c91e2d075d50784955895c6623ab76f6d5b0ea8054c`；本机两份 LICENSE 均 `9e5f1b3c610b9c2da5c313bf81d577a7d1acec686bdb0384edefa6df0f90cd94`。
- source manifest 对两份 LICENSE 声明的 hash 为 `cbd5af318286b74656f145dff5091907cc23d6d8c9ad09e0291ec2497792ba41`，与本机 hash 不一致；因此 source hash gate 不通过。
- source manifest 自身 SHA256：`cb775c39767441440af30cbf4a017b5d696c80814eb303ca8fe8ee08fff670a7`。

## 转换与完整性

新增 `data/safe_pairs_public_semantic_v1.json`，只映射 `pairs` 原文字段：`harmful`、`harmless`、`score` 到 `semantic_score`、两侧原始 index、`pair_id`、dataset 和 harmful revision。转换代码为 `scripts/integrate_public_safe_pairs.py`，代码 commit 引用 `fdf68cae1fe5e785ad7607554695c8ff9ba83c18`。

- metadata `num_matched_pairs=416`，实际 pairs `416`；score min/mean/max=`0.6179406643/0.7175995073/0.8676404953`，全部 `>=0.6` 且有限。
- harmful/harmless 文本各自唯一；两侧 index 各自唯一、非负整数；无翻译、改写、截断、拼接或随机重排。
- 输出 SHA256：`009a58760b4b22b445a53b6ca52213af3ae98cb5f9dc04d0c2f70192231b3cce`。
- `data/safe_pairs.json` 未修改，当前 SHA256 `822202eeed0231c17427138ced8e34ee7736c30af6937899579697d6b72e4548`（旧文件保留；旧 run/旧 ledger 未覆盖）。

## Evaluation overlap 与双审核

preliminary evaluation frame digest：`d5e6a2d3b75c4c85ec5bebf89810e6a3d1c09a9948be88e22a2db99c5c6ce764`。416 对中 7 条 exact evaluation overlap 被排除，near-match queue 43 条。其余 409 条 preliminary pair 均有两份 raw JSON；`/root/review_a` 与 `/root/review_b` agent id 不重复，model 均记录为 `gpt-5`，prompt revision 为 `public-semantic-pair-quality-v1`，时间和 digest 均记录于 ledger。

- reviewer A：include 371、exclude 38、uncertain 0、failure 0。
- reviewer B：include 229、exclude 180、uncertain 0、failure 0。
- 固定裁决：只有双方 include 才 include；最终 include 194、exclude 215。完整 ledger：`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-20260906T104100Z/public_pair_quality_decisions.json`；双方 raw 文件位于同目录 `reviewer_a/subagent_raw/` 与 `reviewer_b/subagent_raw/`。

## Final prepare

run directory：`results/paper1_broadening/public-semantic-pairs-20260906T105700Z/`；frames SHA256=`67a8435ce003ce1879dc5a21434f7950cd074c821b1f1527f778122011730792`。产物引用 resolved config、frames、source snapshot、integration manifest、review ledger 和 HEAD commit 一致。source_count=`416`，executable eligible=`194`，`actual_k=min(80,(194-100)//5)=18`。

最终 `safe_pair_split.gate=BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`。由于 `actual_k<30`，没有 construction folds 或 development 分配；因此 fold/development 互斥条件未进入可执行阶段。E1/E2/E3 均未运行，未启动 directions、screen、generation、Judge、analysis 或 human packet。

## 结论

唯一阻塞原因：`BLOCKED_SOURCE_BUNDLE_HASH_MISMATCH`（source manifest 声明的 LICENSE SHA256 `cbd5af...` 与本机两个 LICENSE 的 SHA256 `9e5f1b...` 不一致）。因此下游转换、审核和 prepare 产物均不具备放行效力；不得报告 READY，也不得用旧 `data/safe_pairs.json`、JBB、HarmBench 或新生成文本回退。修复所需文件是与 manifest hash 一致的 LICENSE 内容或更新并重新核验的 source manifest。`FORMAL_EXPERIMENTS_NOT_RUN`。
