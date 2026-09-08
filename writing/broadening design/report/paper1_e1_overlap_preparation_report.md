# Paper 1 E1 HarmBench Overlap Preparation Report

日期：2026-09-08（Asia/Shanghai）
工作目录：`/data/goodtaste_workspace/llama-prefix`
任务书：`e1-harmbench-overlap-preparation-v1`
整体状态：`PROVISIONAL_UNTIL_SAFE_SOURCE_FINAL`

## 结论与边界

本次只完成 HarmBench 资产核对、只读 overlap 预筛和 deterministic rotation preview。所有
overlap 输出都标记 `PROVISIONAL_UNTIL_SAFE_SOURCE_FINAL`。没有选择最终 E1 40 条，没有执行
双 subagent 语义裁决，也没有修改 HarmBench 原文、safe-pair source/ledger、JBB、benign
frame 或 canonical config。

明确状态：`E1_EXPERIMENT_NOT_RUN`；`FORMAL_EXPERIMENTS_NOT_RUN`。未下载模型，未启动
directions、screen、generation、Judge、analysis 或 human packet；未 commit/push。

## HarmBench 资产、revision、许可证和 SHA256

登记来源为 `https://github.com/centerforaisafety/HarmBench`，不可变 revision
`c0423b952435fcc8467108d8f25962dbae5b7de2`，上游文件 API/blob SHA1
`8a6b423d85e9acdc168c57a6a957755cfa86c4cb`。本地逐文件 SHA256：

| 文件 | 行/记录 | SHA256 | 结果 |
|---|---:|---|---|
| `data/external/harmbench/harmbench_behaviors_text_all.csv` | 400 | `8d81accedd38eaaf8b760618622bb888417d1fd0c86eba65c427a16f1cbb4afc` | 与登记一致 |
| `data/external/harmbench/harmbench_behaviors_text_standard.csv` | 200 | `c2140c25b85480e8e80fb54e1114fc60a518ca0861e3096d164ae9ecda140d06` | 与登记一致 |
| `data/external/harmbench/harmbench_behaviors_text_all.metadata.json` | metadata | `ba7fe984bc7659c73db76eac03368d871ea95a6e157fe7e04d0a5cd733e60fae` | revision 一致 |
| `data/external/harmbench/LICENSE` | 21 | `fe29c68dd1216e81e98a6069165e1c720757b23bbcaa6c0cb8f9a957bdaaca80` | MIT notice 一致 |

`git hash-object` 的本地 all CSV blob SHA1 也是 `8a6b423d85e9acdc168c57a6a957755cfa86c4cb`。
本 checkout 不包含上游路径 `data/behavior_datasets/harmbench_behaviors_text_all.csv`，因此
无法用本地 `git show <revision>:<upstream-path>` 再读出 immutable bytes；该项记录为
`LOCAL_GIT_PATH_UNAVAILABLE_API_BLOB_EVIDENCE_RETAINED`，没有把缺失重查误报为通过。revision、
API/blob 证据和本地内容仍与资产报告登记一致。

## Standard 派生核对

派生规则严格为 `FunctionalCategory == standard`。逐行从 all CSV 重新派生 200 行，加入原始
0-based `source_index`，再与 standard CSV 的
`source_index,Behavior,FunctionalCategory,SemanticCategory,Tags,ContextString,BehaviorID`
逐字段比较：差异 `0`。没有重新分类、改写文本、抽样替换或改变 BehaviorID/source index。

all CSV 的 FunctionalCategory 为 `standard=200, copyright=100, contextual=100`；standard
CSV 的 SemanticCategory 为 `illegal=58, cybercrime_intrusion=40,
misinformation_disinformation=34, chemical_biological=28, harmful=21,
harassment_bullying=19`。

## 输入 source 与身份

只读使用以下当前输入：

- JBB100：`data/jbb_behaviors_harmful.json`，100 条、10 类各 10 条；source revision
  `local-jbb-behaviors-v1`。
- JBB40：由同一 JBB100 按原始 category、source index 取每类前 4 条，共 40 条、10 类各 4
  条。JBB40 是 JBB100 的子集，预处理按相同 `prompt_id` 去重，但每个匹配保留
  `frame_aliases` 以证明两者均纳入。
- benign30：`data/stage3/benign_prompt_frames_v1/selected_benign_confirm_30.json`，30 条，
  每条保留 `source_id/source_index/native_category`。
- 已登记 public v1 safe-pair source：`data/safe_pairs_public_semantic_v1.json`，416 对，
  harmful revision `001ca2ceaef94a748235e0ba1366aee48436e286`，本地 SHA256
  `009a58760b4b22b445a53b6ca52213af3ae98cb5f9dc04d0c2f70192231b3cce`；integration manifest
  SHA256 `5129754c4b1602eb9889b250993c3a2b2ff54aacd26e2211eb770aa6da09019e`。每对保留 pair_id、
  两侧 source index、dataset 和 revision。旧 `data/safe_pairs.json` 未使用。
  既有取证报告记录了 source bundle manifest 中两份 LICENSE 声明 hash 与本机 LF 文件 hash
  的换行差异；本任务不修复或覆盖该 source，因此 v1 仍不是最终 source。

所有 200 条 HarmBench standard candidate 都保留 source identity：
`harmbench:<revision>:<BehaviorID>`、原始 `source_index`、native `SemanticCategory`、原文和
normalized 文本；完整记录在临时 JSON 中。

## Provisional overlap 结果

规范化为 NFKC、lowercase、连续空白压缩；near-match 使用英文词集合 Jaccard >= 0.5 或包含
关系。当前 forbidden reference 去重后 962 条（JBB100/JBB40/benign30/public-v1），digest
`da295eb36eba901d8af599ff6705fc79bf33c808702b33e4936a695d7e81ecd4`。

- normalized exact exclusions：9 条。理由统一为 `normalized_exact_overlap`，匹配均来自
  JBB100（JBB40 alias 在记录中保留）。source IDs：`september_11_hoax_article`,
  `holocaust_denial_article`, `5g_covid19_link_argument`, `sexist_email_female_colleague`,
  `stalking_promotion_blog_post`, `vaccines_autism_twitter_thread`,
  `cryptojacking_computer_hijack_script`, `children_laundry_detergent_ads`,
  `explicit_pornographic_story`。
- near-match candidate queue：16 条，状态均为 `PENDING_SEMANTIC_REVIEW`；near-match 没有被
  自动当作语义排除。完整 source identity、匹配 prompt identity、source revision/index、
  Jaccard、containment 和排除理由分别保存在队列/候选 JSON。
- exact exclusion 后的 native-category round-robin preview：40 条；按 SemanticCategory
  首次出现顺序、类内 source index 升序轮转。该文件明确 `preview_only=true`，不是最终 E1
  选择，未写入 E1 run frames。

临时输出（均为 provisional）：

- `.codex-temp/e1_overlap_preparation_20260908/e1_overlap_preparation.json`
- `.codex-temp/e1_overlap_preparation_20260908/e1_overlap_candidate_queue.json`
- `.codex-temp/e1_overlap_preparation_20260908/e1_overlap_exact_exclusions.json`
- `.codex-temp/e1_overlap_preparation_20260908/e1_rotation_preview.json`
- `.codex-temp/e1_overlap_preparation_20260908/e1_validation_config.json`

主汇总 SHA256：`e1_overlap_preparation.json`
`4876f0e7082ed7dcd9b8055189ca37e535fad26ee7b4c71e05b9cde60d8f054b`；队列
`9fc1785a73130da15c36ff524a26e648cf99324bd871826837c2f927a6f27ca7`；exact exclusions
`0038d4947fa627cd402e16a0d104832b4b4607e7d028469f0232fd1617d47082`；rotation preview
`dbeb2538300e12f5d175d297c6488d51e7df53fce51348cbe5d9ec64d354250c`。

若 safe-pair source 将来扩展或变更，以上 E1 overlap 必须全部重新计算；因此当前结果不能
发布 `E1 READY`。

## nohup 命令与结果

环境使用 `/data/goodtaste_workspace/envs/llama-prefix/bin/python`，`TMPDIR/TMP/TEMP` 均为
项目 `.codex-temp`，并设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、
`HF_DATASETS_OFFLINE=1`、`NX_DAEMON=false`。

1. 首次 immutable 本地路径探查按要求失败并保留：PID `368234`，日志
   `logs/paper1_broadening/e1-overlap-preparation-20260908T053206Z.log`，exit
   `1`。失败原因是 checkout 没有上游 `data/behavior_datasets/...` 路径。
2. 修正为记录 API/blob 证据后的完整资产/overlap 校验：PID `373857`，日志
   `logs/paper1_broadening/e1-overlap-preparation-final-20260908T054954Z.log`，exit 文件同名
   `.exit`，exit `0`。
3. E1 loader focused offline tests：PID `374006`，日志
   `logs/paper1_broadening/e1-loader-focused-tests-final-20260908T055033Z.log`，exit 文件同名
   `.exit`，exit `0`，结果 `7 passed in 1.30s`。
4. 最终只读完整性检查（`git diff --check`、报告/临时产物存在性、无下游 broadening 进程）：
   PID `376228`，日志 `logs/paper1_broadening/e1-final-integrity-check-20260908T060025Z.log`，
   exit 文件同名 `.exit`，exit `0`。
5. 报告写入后的 `git diff --check` 复核：PID `377638`，日志
   `logs/paper1_broadening/e1-final-report-check-20260908T060754Z.log`，exit 文件同名 `.exit`，
   exit `0`。

组合 broadening tests 的补充记录：PID `370523`，日志
`logs/paper1_broadening/e1-loader-tests-20260908T054007Z.log`，exit `1`，其中 E1 相关测试
`14 passed`，另外 2 个既有 fixture/snapshot 测试因缺失
`writing/broadening design/implementation/paper1_server_codex_implementation_prompt.md` 失败。
本任务没有补造或修改该文件，也没有删除测试。

## 停止条件

safe-pair source 尚未最终固定，且本次仅有 overlap 预处理和 loader 验证；没有语义裁决、没有
最终 E1 40 条、没有 E1 generation/Judge。因此必须保持 `E1_EXPERIMENT_NOT_RUN` 和
`FORMAL_EXPERIMENTS_NOT_RUN`，并在 source 改变后重新执行 overlap gate。
