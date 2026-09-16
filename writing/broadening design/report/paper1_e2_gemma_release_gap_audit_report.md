# Paper 1 E2：Gemma release serialization gap 审计

会话：`E2`  
任务：`paper1_server_codex_e2_gemma_release_gap_audit_prompt_nohup.md`  
日期：2026-09-16（Asia/Shanghai）  
范围：只读审计 F run 的 Gemma 方向资产；不是 E2 实验。

## 结论

`IMPLEMENTATION_PATCH_REQUIRED`

`directions.json` 中 Gemma 的 release 字段缺失是一个已证实的 metadata serialization gap。它不等同于 Gemma 模型、hook 或 tokenizer 实际未释放：F run 的 source snapshot 显示 layer-14 runtime 在 `finally` 中调用了 `runtime.release()`，但该调用的返回值没有被写入 Gemma model record。因此，F run 的 Gemma release 状态为：

`UNVERIFIED_NOT_PASS`

现有证据不能把它报告为 `PASS`。单独完成的 Gemma runtime probe 有自己的 release 记录，但不是 F run 的 layer-14 direction-build 生命周期证明。

F run 的 Gemma identity 也是部分不完整：路径、realpath、config/tokenizer/template hash、layer、hook、device、dtype 等均有记录，但 `model_revision` 和 `tokenizer_revision` 在 F identity 中均为 `UNKNOWN`。既有资产报告记录了 ModelScope revision，可作为外部 provenance 参考，但没有被序列化进 F 的 Gemma identity；本审计不回填它们。

`E2_FORMAL_EXPERIMENT_NOT_RUN`  
`FORMAL_EVALUATION_NOT_RUN`

未触发 `DESIGN_CHANGE_REQUIRED`。若要在未来新 run 中闭合该记录，需要改共享实现，故标记为 `IMPLEMENTATION_PATCH_REQUIRED`；本任务没有修改共享实现，也没有重建 F run。

## 审计方法与执行记录

审计脚本和输出均在 `.codex-temp/paper1_e2_release_gap_audit/`：

- `audit_gemma_release_gap.py`：只解析 JSON/元数据，使用 `torch.load(..., map_location="cpu", weights_only=True)` 读取已保存的方向 tensor；没有加载 Gemma 权重、没有导入 Transformers、没有调用 CUDA、没有网络访问。
- `gemma_release_gap_audit.json`：业务结果 `status=AUDIT_COMPLETE`，`directions.json` SHA256 为 `3ca9bb9eed166eefddb62552e603dcf183708e37f6f892923782ec6d46d962eb`。
- 最终 py-compile：PID `1563272`，日志 `pycompile-final2-20260916T045852Z-1563270.log`，`.exit=0`。
- 最终审计：PID `1563384`，日志 `audit-final-20260916T045937Z-1563382.log`，`.exit=0`；业务 JSON 已独立核验。早期外壳启动异常的已产生 log/exit/PID 原件保留在同一临时目录；个别外壳失败没有形成完整三件套，均未被当作业务 PASS/FAIL。

没有运行 `prepare`、`build-directions`、`screen`、`generation`、Judge 或正式 evaluation；没有下载/加载 Gemma，没有使用 GPU，也没有写入 F run。

本次只读输入还包括：F 报告 `paper1_core_direction_calibration_report.md`、F2 报告 `paper1_core_dose_screen_report.md`、B6 报告 `paper1_core_static_handoff_report.md`、当前入口 `paper1_server_codex_post_audit_task_index.md`，以及原实验设计 `paper1_minimal_broadening_experiment_design_no_mistral.md` 与 `paper1_minimal_broadening_experiment_design_v2.1_readable.md`。

## F run 与 source snapshot

核对目录：

`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`

- run ID：`paper1-20260915T140735Z-99331d4603`。
- `directions.json`：SHA256 `3ca9bb9eed166eefddb62552e603dcf183708e37f6f892923782ec6d46d962eb`。
- `directions_gemma2_9b_it.pt`：SHA256 `34e3696a55da7c6bd7c54787e6f7d4046d64707859c13ce2c01703c2b78bb4fd`。
- `source_snapshot_verification_core_screen.json` 与 `_resume.json` 均记录 `status=PASS`、`verified=true`、47 个 source files；当前 `paper1_broadening/pipeline.py` 与 F snapshot 字节一致，SHA256 均为 `1eab7a90e3e6a078e1b4595ed5fd8e8429e27aea8f14ce9cf20d6a026beb9a52`。
- 当前 `run_header.json` SHA256 为 `c0ea17afb6d020bba0f3632adf348f6eb31cdafad5d150907fac83f854e09ff7`；`run_header_before_core_screen.json` SHA256 为 `c32e12ba3db49974f3a784c6acd505bf0c2dd4f592491588c81b6bfe8c8e46c6`。两者的已有差异是 F2 增加 Judge identity/`judge_tokenizer_revision`，不是本 E2 审计改动；本报告以当前 run header 为准。
- F run header 的 `code_commit=107a2412adbb66a9997244efdbdbf4ba92253cb0`、`dirty=true`、`CUDA_VISIBLE_DEVICES=0`、`logical_device=cuda:0`、Python 3.10.20、PyTorch 2.12.0+cu126、Transformers 4.57.6、CUDA 12.6。Gemma identity 使用物理 GPU UUID `GPU-e7424758-25c8-291b-e80f-c1f8c677b127`。

F、F2、B6、当前任务索引和原实验设计均把 E2 标为未运行的第三模型扩展；F2 的 `CORE_DOSE_SCREEN_BLOCKED` 不改变本次只读 E2 边界。

## Gemma 方向资产实际状态

来自 F run `directions.json` 的 `models.gemma2_9b_it`：

| 字段 | 实际值 |
|---|---|
| asset status | `COMPLETED`（仅方向/calibration asset，不是 E2 实验或 release PASS） |
| layer | `14`，zero-based `resid_pre`；`L=42`，`floor((42-1)/3+0.5)=14` |
| layer count / hidden size | `42` / `3584` |
| `mu_content` | `215.28572219322467` |
| `mu_content_token_count` | `1160` |
| direction tensor | `directions_gemma2_9b_it.pt`，CPU `float32` shape `[9, 3584]`，全有限，行范数 `[0.9999998807907104, 1.0]` |
| direction families | 4 Rogue（`rogue:0..3`，seed `420003`）+ 5 contrastive（`contrastive:fold:0..4`，seed `42`） |
| contrastive diagnostics | 5/5 `SIGN_VALIDATED`、`vector_flipped=false`；projection 范围 `24.083761529922484..25.146402996778487` |
| tensor path | `/data/goodtaste_workspace/llama-prefix/results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/directions_gemma2_9b_it.pt` |

Gemma model record 的实际 key 只有 `directions`、`hidden_size`、`layer`、`layer_count`、`mu_content`、`mu_content_token_count`、`runtime_identity`、`status`、`tensor_path`；没有 `release`。顶层 `E2.status=COMPLETED` 同样只是自动方向资产状态。

## 本地 Gemma 资产与 runtime identity

本地模型/Tokenizer 路径均为：

`/data/goodtaste_workspace/models/gemma-2-9b-it`

realpath 相同，目录不是符号链接。只读资产清单和既有 `.codex-temp/gemma_asset_verification.json`（状态 `PASS`）显示：

- `config.json`：SHA256 `8ecc124513fdb0bb31bf51b4f0dd6c8658a68296dc8cd30af612205ff4a1bc49`；`model_type=gemma2`、`Gemma2ForCausalLM`、`num_hidden_layers=42`、`hidden_size=3584`、`vocab_size=256000`、`bfloat16`。
- `model.safetensors.index.json`：SHA256 `c38b39b80b2d7aa422464a9b816af4c30d2177e471b89e5325df1336a23ad284`；464 tensor entries、4 个声明分片、`total_size=18483411968`，四个分片均存在。
- `tokenizer.json`：SHA256 `3f289bc05132635a8bc7aca7aa21255efd5e18f3710f43e3cdb96bcd41be4922`；`tokenizer_config.json`：SHA256 `cb32b7929c62608d46572e813112b3ad8a841fb98fdd6a4da8559e368a951c89`；Tokenizer 为 `GemmaTokenizerFast`，原生 chat template 存在，BOS/EOS/PAD 为 `2/1/0`。
- 既有资产记录的四个权重 SHA256：`a0d4eb4fcbddfe01b0dc7a58386a3980826ededaf0ecd67d1ef38995b89615ba`、`712a589c333f49f7b6f3870838a9e0ab4b3c0260abd5130e8c54316e6c99640b`、`5a9f84eb9846840802200c6502ccaaebf0a146ee89dcb8822fab795c392dd667`、`3349b4960bbc0bf7e47a624e5c520881adb06e2da4bda6ed14b51c7f647fe26c`。
- 既有 ModelScope 资产报告记录：weights revision `dc3d2d5f1517d6f238b394372c8d5d728f56cc15`，config revision `1655fb4e5cb32e82c3580832e2800836c69145e3`，tokenizer revision `ef614e8d344164fab9bb5d02b372f0ad3eca0896`。这些不是 F run identity 中已绑定的 revision 字段。

F Gemma `runtime_identity` 记录了：

| 类别 | 值 |
|---|---|
| model/tokenizer path + realpath | 上述同一 Gemma 目录 |
| model/tokenizer revision | `UNKNOWN` / `UNKNOWN` |
| config/tokenizer/template SHA256 | `8ecc1245...1bc49` / `cb32b792...a951c89` / `a4722367...927ce9` |
| layer/hook | `14` / `resid_pre`，`forward_pre_hook_on_layer_input` |
| dtype/size | `bfloat16` / hidden size `3584` |
| device | `cuda:0`，physical index `0`，GPU UUID `GPU-e7424758-25c8-291b-e80f-c1f8c677b127` |
| local loading | `local_files_only=true`，Transformers `4.57.6` |

所以路径、配置、模板和 hook identity 有直接证据；checkpoint revision identity 在 F 记录中明确未知，不能报告为完整 provenance。

## Release schema 对照与现有记录

Qwen 与 Llama 的 F `directions.json` model record 均有以下 release schema：

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

Qwen layer 9 的记录为全部布尔释放标记为 true、`gc_collected_count=61`、`models_concurrently_resident=false`；Llama layer 11 同形，`gc_collected_count=42`、`models_concurrently_resident=false`。E3 layer records 也沿用这一 schema。

Gemma 对照结果：

- `directions.json.models.gemma2_9b_it.release` 不存在；不是空对象，也没有可验证的 release 状态。
- `screen_behavior_release_core.json` 只有 `qwen25|layer9` 和 `llama31|layer11`；没有 Gemma entry。
- `screen_judge_release_core.json` 是 Judge release；不能充当 Gemma behavior release。
- `run_header.loaded_identities.behavior` 有 `gemma2_9b_it|layer0` 和 `gemma2_9b_it|layer14` 的加载 identity，但 loaded identity 不是 release 记录。
- F 报告的 Automatic Extension Assets 段落已明确写出：Gemma runtime identity/方向 metadata 已序列化，但当前实现没有把 Gemma `release` return 序列化；该 gap 不被当作 E2 pass。

## 源码因果定位

F snapshot 与当前 `paper1_broadening/pipeline.py` 相同：

- `_build_e2_assets()` 在约 609--624 行对 layer-0 probe 调用 `probe.release()`，只检查异常，不保存 release return。
- layer-14 runtime 在约 632--689 行的 `finally` 调用 `runtime.release()`；成功返回的 model dict（约 657--687 行）没有 `release` 字段。
- Qwen/Llama core 路径在约 803--806 行把 `release = runtime.release()` 写入 `output["models"][model_id]["release"]`。
- `BehaviorRuntime.release()`（约 482--510 行）本身会移除 active hook、清除 model/tokenizer/layer 引用、执行 GC、CUDA synchronize/empty-cache，并返回上述 schema。

这组代码证据支持“返回值被丢弃的序列化缺口”，但不能替代 F run 的实际 release raw 记录。

## Release 状态判断

| 问题 | 判断 | 依据 |
|---|---|---|
| Gemma direction/tensor 是否存在 | `CONFIRMED` | F `directions.json`、9 行 CPU tensor、hash/shape/finite/norm 核验 |
| layer 14、`mu_content`、token count 是否有记录 | `CONFIRMED` | F model record 与 runtime identity |
| Gemma hook/model/tokenizer 在 F build 后实际已释放 | `UNPROVEN`，不得写 PASS | source 只证明调用 `runtime.release()` 的路径；return、生命周期快照和 Gemma release 文件均缺失 |
| 缺口是否为 metadata serialization | `CONFIRMED` | Qwen/Llama 同 schema 对照；Gemma model record 没有 release；源码丢弃返回值 |
| F Gemma identity 是否完整 | `PARTIAL / INCOMPLETE` | 路径、hash、layer/hook/device 完整；model/tokenizer revision 为 `UNKNOWN` |
| E2 正式实验/评估 | `NOT_RUN` | 无 E2 screen/generation/Judge/dose/evaluation 产物；任务索引和 F/F2/B6 报告均保持未运行 |

既有独立 runtime probe：`.codex-temp/gemma_runtime_probe_result.json`（SHA256 `b290ba85fd95d1a5fae3aab6b6a08738b2831eba03e3b8b0d090670f05ea4c25`）确实记录了另一次 `release` 全 true、release 前后对象清理和 `RUNTIME_PROBE_PASS`。它证明本地 runtime 能够释放 Gemma，但不是 F direction-build 的 release record；因此不能把它提升为 F run Gemma release `PASS`。

## 风险

1. 下游消费者可能只看 `status=COMPLETED` 和 tensor 路径，误把方向资产当作生命周期已闭合的 E2 输入；当前 F 记录无法证明 Gemma release 后没有残留 hook/model/tokenizer 或并驻模型。
2. 缺失 release raw 会削弱单卡顺序和显存边界的可复核性；这是真实的证据缺口，不足以反推“已经发生泄漏”。
3. F identity 的两个 `UNKNOWN` revision 降低 checkpoint/tokenizer provenance 的可重建性；既有资产报告的 revision 只能作为旁证，不能未经新 run 绑定后回填。
4. `run_header` 在 F2 后相对 B6 交接副本发生了已有 Judge identity 变化；本审计没有覆盖或修正该差异。后续消费时应以当前 run header 和对应 F2/B6 时间线为准。

## 最小修复建议（不在本任务执行）

不需要科学设计变更；需要一个共享实现 patch，位置为 `paper1_broadening/pipeline.py` 的 `_build_e2_assets()`，并在新 run/新不可变产物中执行：

1. 保留 layer-14 `runtime.release()` 的实际返回对象，并把它原样写入 `output["models"]["gemma2_9b_it"]["release"]`，字段集合与 Qwen/Llama 完全一致；不得手工构造全 true 字段。
2. 保持现有 fail-closed 行为：probe 或 layer-14 release 抛异常时返回 `BLOCKED`/具体错误，不写伪造 PASS。若要记录 layer-0 probe 生命周期，可单独保留内部诊断，但不必为了 schema parity 增加科学字段。
3. 不回填或覆盖本 F run 的 `directions.json`，不重建 F run；修复后的输出应来自新 run 或独立离线 fixture，并保留旧 hash。
4. revision 只有在 runtime/资产 provenance 有明确值时才写入；否则继续写 `UNKNOWN`，不得使用目录名或猜测值。

## 最小离线测试建议

本任务没有运行下列测试，只提出建议；测试不应下载/加载 Gemma、不使用 GPU、不改 F run：

1. 用 fake `BehaviorRuntime` 和 fake tensor/frames 对 `_build_e2_assets()` 做 monkeypatch fixture，让 `release()` 返回带哨兵值的 Qwen/Llama schema；断言 Gemma model record 原样包含该 release，且 key 集合精确相等。
2. 用 fake runtime 让 layer-14 `release()` 抛异常；断言结果为 `BLOCKED`/具体 `release_error`，没有合成的 `behavior_released=true` 或 E2 PASS。
3. 对 synthetic directions document 做 schema regression：Qwen/Llama/Gemma 三个 model record 的 release 对照、Gemma `status/tensor/mu/layer` 保持不变；测试前后 F `directions.json` SHA256 必须仍是 `3ca9...d962eb`。
4. CPU-only tensor regression：读取 Gemma direction tensor 的 shape `[9,3584]`、`float32`、finite、unit norms 和 SHA256；确认 serialization patch 不改 tensor 内容。
5. identity regression：给定缺少 checkpoint revision 的 fixture 时保持 `model_revision=UNKNOWN`、`tokenizer_revision=UNKNOWN`；给定显式 revision 时只复制该值，并保持 config/tokenizer/template hash、路径、layer 14、`resid_pre` 不变。

## 本任务文件边界

本任务新增/写入：

- 本报告 `writing/broadening design/report/paper1_e2_gemma_release_gap_audit_report.md`；
- `.codex-temp/paper1_e2_release_gap_audit/audit_gemma_release_gap.py`；
- `.codex-temp/paper1_e2_release_gap_audit/gemma_release_gap_audit.json`；
- 同目录本任务的 nohup PID、日志和 `.exit` 文件。

以下均未修改：

- F run 的 `directions.json`、`directions_gemma2_9b_it.pt`、`run_header*.json`、`source_snapshot/` 及所有 Core/F2 原件；
- `paper1_broadening/pipeline.py`、`runtime.py`、`directions.py` 及其他共享实现；
- canonical config、原实验设计、任务索引、safe-pair/E1 派生物、Core screen 产物和 E1 文件；
- `/data/goodtaste_workspace/models/gemma-2-9b-it` 模型目录；
- 用户/并发任务在审计前已经存在的 worktree dirty files。

没有 `git reset`、覆盖式 checkout、commit 或 push。

## 边界自审

- [x] 只读核对 F、F2、B6、当前任务索引和原实验设计。
- [x] 只读核对 Gemma tensor、layer 14、`mu_content`、token count、runtime identity、source snapshot、已有 release 文件和 Qwen/Llama schema。
- [x] 未下载/加载 Gemma；未占 GPU；未运行 prepare/build-directions/screen/generation/Judge。
- [x] 未回填/覆盖 `directions.json`，未伪造 release 或 revision 字段。
- [x] 未修改 canonical config、科学设计、Core screen 产物或 E1 文件。
- [x] 已把 F Gemma release 标成 `UNPROVEN_NOT_PASS`，没有把独立 runtime probe 当作 F run PASS。

`E2_FORMAL_EXPERIMENT_NOT_RUN`  
`FORMAL_EVALUATION_NOT_RUN`

审计到此停止，不 commit/push。
