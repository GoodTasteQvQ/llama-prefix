# Paper 1 E2R Gemma Release Serialization Patch Report

日期：2026-09-16（Asia/Shanghai）  
任务：`gemma-release-serialization-patch-v1`  
范围：未来方向构造 run 的 metadata 修复

## 结论

`E2R_IMPLEMENTATION_PATCH_PASS`

本次只修复 `paper1_broadening/pipeline.py` 的 `_build_e2_assets()` 生命周期记录：layer-14
`runtime.release()` 的真实返回对象现在在 release 成功后原样写入
`output["model"]["release"]`，随后才保存 Gemma 方向 tensor 并返回 `COMPLETED`。release
异常会返回 `status=BLOCKED`、`reason=GEMMA_RELEASE_FAILURE: ...` 和具体
`release_error`；不会写 Gemma model record、不会保存新 tensor，也不会合成 PASS。顶层
`build_directions()` 看到 E2 `BLOCKED` 时也保持顶层 `BLOCKED`。

Qwen/Llama core release 路径和 E3 release 路径未改变。Gemma runtime identity 仍由 runtime
提供；缺失 model/tokenizer revision 的 fixture 仍为 `UNKNOWN`，没有从目录名、旁证或模型
报告回填 revision。

`F_RUN_GEMMA_RELEASE_REMAINS_UNVERIFIED`

F run 的 Gemma release 仍是历史 metadata 缺口，不能因为本 patch 把旧 run 报为 PASS。本次
没有写入或重建 F run。

`E2_FORMAL_EXPERIMENT_NOT_RUN`

`FORMAL_EVALUATION_NOT_RUN`

## 实际修改文件

- `paper1_broadening/pipeline.py`
  - 保留 layer-14 release 返回值并原样挂到 Gemma model record。
  - release 失败 fail-closed，并保留具体错误；tensor 写入移动到 release 成功之后。
  - E2 `BLOCKED` 不再被顶层状态合成为 `COMPLETED`。
- `tests/paper1_broadening/test_e2r_release_serialization.py`
  - CPU-only fake runtime 覆盖 Gemma release identity、schema 对齐、release 异常和
    `UNKNOWN` revision。
- `writing/broadening design/report/paper1_e2r_release_serialization_patch_report.md`
  - 本任务报告。

执行前工作树和目标文件证据：

- `.codex-temp/paper1_e2r_release_serialization/pre_git_status.txt`
- `.codex-temp/paper1_e2r_release_serialization/pre_pipeline.diff`（0 行；`pipeline.py` 执行前无已有 diff）
- `.codex-temp/paper1_e2r_release_serialization/pre_pipeline_diff_stat.txt`

工作树中其他会话/用户已有或期间出现的 `config.py`、`frames.py`、`judge.py`、
`orchestration.py`、既有/新增测试、配置、数据和报告修改均未重置、checkout、覆盖或纳入本
patch；其中 `judge.py` 的并行 observability 修改在本任务最终状态中仍保留。

## Release schema 与行为

fake runtime 返回对象的 key 集合与 Qwen/Llama/E3 记录对照为：

```text
behavior_hook_removed
behavior_model_reference_cleared
behavior_released
behavior_tokenizer_reference_cleared
cuda_empty_cache_called
cuda_synchronize_called
gc_collect_called
gc_collected_count
models_concurrently_resident
```

测试断言 Gemma record 的 `release` 是 fake runtime 返回的同一个对象（不是手工重建的全
true 字典），并且 key 集合与 Qwen/Llama/E3 对齐。release 异常测试断言：

- 返回 `BLOCKED`；
- 保留 `RuntimeError: fixture layer-14 release failure`；
- 没有 `model` 字段或 Gemma tensor；
- 没有任何合成 `behavior_released=true` 的 PASS。

## 测试与检查证据

所有命令均在项目目录使用项目 Python，并设置了 `TMPDIR/TMP/TEMP=.codex-temp`、
`NX_DAEMON=false`、Hugging Face/Transformers/Datasets offline 和
`PYTHONUNBUFFERED/PYTHONPYCACHEPREFIX`；均以 `nohup setsid` 启动并保存 PID、log、`.exit`。

| 检查 | PID | log | `.exit` | 结果 |
|---|---:|---|---|---|
| E2R focused pytest（3 tests） | `1678445` | `.codex-temp/paper1_e2r_release_serialization/checks/e2r-focused-pytest-final3-20260916T115839Z-1678443.log` | 同前缀 `.exit` | `3 passed`, `0` |
| Qwen/Llama/E3 release regression（runtime/pipeline/readiness） | `1677203` | `.codex-temp/paper1_e2r_release_serialization/checks/release-regression-pytest-20260916T115412Z-1677201.log` | 同前缀 `.exit` | `23 passed`, `0` |
| 全部 `tests/paper1_broadening` | `1677207` | `.codex-temp/paper1_e2r_release_serialization/checks/all-paper1-broadening-pytest-20260916T115412Z-1677204.log` | 同前缀 `.exit` | `56 passed`, `0` |
| Python compileall | `1677819` | `.codex-temp/paper1_e2r_release_serialization/checks/python-compileall-final-20260916T115554Z-1677816.log` | 同前缀 `.exit` | `0` |
| 修改文件 py_compile | `1678454` | `.codex-temp/paper1_e2r_release_serialization/checks/python-compile-final3-20260916T115839Z-1678450.log` | 同前缀 `.exit` | `0` |
| `git diff --check` | `1678449` | `.codex-temp/paper1_e2r_release_serialization/checks/git-diff-check-final2-20260916T115839Z-1678446.log` | 同前缀 `.exit` | `0` |
| 报告加入后的最终 `git diff --check` | `1679919` | `.codex-temp/paper1_e2r_release_serialization/checks/git-diff-check-report-final-20260916T120437Z-1679917.log` | 同前缀 `.exit` | `0` |
| F run 只读 hash 不变核验 | `1677815` | `.codex-temp/paper1_e2r_release_serialization/checks/f-run-immutability-20260916T115554Z-1677813.log` | 同前缀 `.exit` | `PASS`, `0` |

初次 fake fixture 诊断曾因 harmless residual 全零而触发真实 `mu_content` gate，保留为非
通过原件：PID `1674259`，log `.codex-temp/paper1_e2r_release_serialization/checks/e2r-focused-pytest-final-20260916T114224Z-1674257.log`，exit `1`。该 fixture 随后改为正的 harmless residual；没有触碰实现之外的科学输入。修正后的 focused pytest 如上为 `3 passed`。

## F run 与科学边界

只读核验文件：`.codex-temp/paper1_e2r_release_serialization/f_run_immutability.json`，状态为
`PASS`、`f_run_modified=false`。F run
`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/` 的关键
hash 仍为：

- `directions.json`: `3ca9bb9eed166eefddb62552e603dcf183708e37f6f892923782ec6d46d962eb`
- `directions_gemma2_9b_it.pt`: `34e3696a55da7c6bd7c54787e6f7d4046d64707859c13ce2c01703c2b78bb4fd`
- `run_header.json`: `c0ea17afb6d020bba0f3632adf348f6eb31cdafad5d150907fac83f854e09ff7`
- `run_header_before_core_screen.json`: `c32e12ba3db49974f3a784c6acd505bf0c2dd4f592491588c81b6bfe8c8e46c6`

没有修改旧 `directions.json`、旧 Gemma tensor、run header、source snapshot、canonical
config、三份原实验设计或任何科学字段。没有下载/加载模型、占用 GPU 或联网。

没有运行 `prepare`、正式 CLI `build-directions`、E2、screen、generation、Judge、分析或
正式 evaluation。focused tests 只调用 `_build_e2_assets()` 和 `_build_e3_layer_assets()`
并注入 CPU fake runtime；初次 fixture 诊断对 `build_directions()` 的调用也只在项目
`.codex-temp` 临时目录中使用 fake runtime，未产生正式 run 或修改 F 原件。

没有 commit 或 push。

## 边界自审

- [x] 只改未来 Gemma release metadata 的共享实现；未改变方向公式、数量、层、fold、mu、模板、decoder、seed、预算或 endpoint。
- [x] layer-14 release 成功时原样写入；异常时 `BLOCKED` + 具体 `release_error`，不写伪造 PASS。
- [x] Qwen/Llama/E3 release regression、revision `UNKNOWN`、compile、diff-check、focused pytest 全部有 nohup PID/log/exit 证据。
- [x] F run hash unchanged；旧 directions/tensor、配置、设计和科学字段未修改。
- [x] 未运行正式实验或正式评估；未 commit/push。

到此停止，不提出或执行 F run 重建。
