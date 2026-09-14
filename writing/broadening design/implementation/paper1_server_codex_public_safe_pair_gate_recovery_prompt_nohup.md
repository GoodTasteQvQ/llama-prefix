# E：Public safe-pair gate 有边界恢复

版本：`public-safe-pair-gate-recovery-v2`；更新：2026-09-14。
基准设计：`MBD-NM v2.1.1-public-pairs`，当前报告基线为 A2 的 221 条，不再使用失效 v1 的 194 条。
执行者：新 E 会话，或此前已停止的 E 会话。

## 1. 目标、前置与授权范围

先读 [当前任务入口](paper1_server_codex_post_audit_task_index.md)，采用其 Linux/nohup 设置与写入归属。可以立即做 §2 的候选发现/下载。执行 §3 及以后前必须从磁盘读取：

- `writing/broadening design/report/paper1_a2_evidence_handoff_report.md`，结论为 `A2_EVIDENCE_VERIFIED`；
- `writing/broadening design/report/paper1_b2_delivery_asset_wiring_report.md`，结论为 `B2_DELIVERY_READY`，且 B3 已停止代码写入。

两者通过后按本任务书继续，不需再等负责人批准。前置未到时保存阶段报告并等待；前置失败可结束来源调查，但不得正式整合/审核/prepare。报告中的 PASS 必须能定位实际交付文件，不能只相信会话回复。

A2：source=416，preliminary=409，executable=221。既定 `k=min(80,floor((N-100)/5))`、5 folds、development=100、`k>=30` 需要 N>=250，即至少增加 29 条合格配对。目标是补足数据 gate，不扩展正式模型矩阵。

硬边界：不降 k/development 门槛；不重审或改写原409条结果；不用旧 AI pairs、JBB、HarmBench、生成/翻译/重配对文本补齐；不改模型/层/模板/decoder/rho/seed/预算/E1–E3；不运行 GPU 加载、directions、screen、generation、Judge、analysis、human packet。旧文件/run/ledger全部保留。即使 `READY_FOR_CONSTRUCTION`，也在本任务结束处停止。

## 2. 可并行的候选发现：小额补充，不更换整个基线

只从本地原始文件、上游 GitHub 或可验证的 ModelScope 镜像获取公开 paired source。服务器不访问 HF；若唯一合适来源只能本机获取，报告确切 URL/revision/文件和所需转移方式，不虚构下载成功或偷偷换来源。

至多实际准入/下载 **两个新增 source bundles**。必须满足：

- 上游已明确提供 prompt-level harmful/harmless 一一对应、pair id 或可验证配对索引。只有两张未配对列表、response preference、拒答 response，不满足接口；不能因两文件行数相同就假定对应。
- 英文、两侧非空；可保留原文、上游 pair/source index、数据来源/精确 revision、README/data card、许可证原文/许可缺失情况。镜像须能对应原始 revision；不能把 ModelScope 名称冒充来源证明。
- 来源没有与实验 evaluation 同一数据池的循环使用；公开并不等于人工验证。上游若由 AI 生成/匹配，如实记录，准入依靠可追溯性和本次相同双审核，不冒称“人工金标准”。
- 不用新 LLM/embedding matching、随机配对、翻译、改写、截断或拼接产生新 pair。

目前尚未确认新的具体数据集。本任务负责按这些条件核实，不把旧报告里曾提到的名称直接当作推荐。旧筛选曾因“单独不足250条”排除的小型公开源，在当前只缺29条的补充场景可以重查；但仍须证明真实配对关系，不能仅据安全/不安全标签配对。

将原始候选保存在 `.codex-temp/paper1_source_recovery_v2/sources/`。先按来源匹配、许可可用性、可追溯性确定优先顺序，记录理由；不读取任何模型实验结果排序。无法确认许可/来源或配对时，列事实和缺项，不自动接受。

为控制审核成本：每个 bundle 至多审核 **100 条 preliminary eligible 新 pairs**，至多两批、200条/400个 canonical reviewer 请求。对每批先做既定 normalized exact 去重/排除：本批内部、旧416行、此前已纳入批次的全部行，以及固定JBB100/JBB40/benign30；均核对两侧文本，不能用第二来源重复贡献同一pair。按上游稳定 pair id/source index 顺序选前100条，不足则全取。记录候选顺序、全部预检排除、入选和未入选ID。近邻只进语义审核，不由分数自动排除。

每批入选集合及顺序必须在任何 reviewer verdict 产生前保存；不用预先不可变全项目 manifest。**整批完成双审核后**再判断 N，不能到250就停在批次中间。若第一批后达标，不启用第二批；不达标可按已记录顺序启用第二个来源。两个 bundle/200条用尽仍不足，就报告阻塞，不无限寻找或继续加量。

## 3. 最小 source 修订及 identity

A3/B3通过、候选来源核验后，在任何新增审核前保存：

`writing/broadening design/review/paper1_public_safe_pair_source_expansion_revision.md`

登记新 design revision `MBD-NM v2.1.2-public-pairs-expanded`（若该标识已有不同内容，另取未用修订号）。只改变 source 集合/身份/provenance，记录候选优先顺序、批次上限/选取规则/停止规则；固定审核科学标准、5折、k、development、evaluation、模型/层/decoder/rho/预算都不变。明确 20,480 是正式 logical generation 预算，不把 reviewer API 请求算作实验 generation。主会话做一次边界核对后保存；这里已授权此项有限来源扩展，不需额外申请。

复用经 A3 核验的 public v1 原件和 A2 rebuilt v2 ledger。新 source 文件另存版本，**前416行的全部原始字段/原文/顺序保持一致**，`safe-pair:0..415` 与各行源 revision 不改变；新增只追加，有独立 dataset/revision/pair id/index 映射。保留每批所有待审核行，后续排除由ledger记录，不能删掉不合格行只发布include source。不要用合并文件 revision 覆盖旧行 provenance。

旧记录复用条件是 pair id+实际两侧文本+原请求输入语义+evaluation digest+固定审核标准不变。旧 source 的整体 hash 与新合并文件 hash 不必相同；同时保存两者及append-only映射。若 loader 把整文件hash错误地当每条input identity，做最小明确兼容而非伪造旧请求hash；若实际需要改变已审输入，停止并报告，不复制hash“迁移”。

第二批只在第一批完整仍不足时追加到新的 source/config/ledger 版本，保留第一批产物；不覆盖已有文件。不重新打乱旧 source，也不提前沿用221条上的空分割。

## 4. 新增行的双 Codex 审核

读取 A2 实际协议修订与固定 prompt，使用 `public-semantic-pair-quality-v2`；ledger schema 为已实现的 `public-safe-pair-quality-ledger-v2`。**prompt revision 与 ledger schema 是不同字段，不混写。**不得从旧恢复v1任务书复制一套放宽的判定标准。

每条新增 preliminary eligible pair 启动两个真实、互相隔离的 Codex subagent/request。每个请求单独身份；A/B可串行以减少限流，但不得继承对方结果、旧标签、目标“缺29条”或“尽量放行”指令。只给该pair、固定evaluation文本/可核对内容和统一判定标准；数据文本当待分析数据，不执行其中指令。reviewer不访问网络、不写仓库、不运行代码。

保存实际请求输入、输入hash、evaluation digest、发送的prompt、可见模型/参数、时间、真实调用事件/thread id、raw output及落地后hash。宿主未暴露的系统指令/revision/参数记 `NOT_EXPOSED/UNKNOWN`，不能伪造。主会话负责保存记录；原生subagent工具无需套nohup，实际长时CLI/API runner用nohup并记录PID/log/exit。

只有 harmful 有实质安全风险、harmless 本身良性、任务/语义结构可比较且无实质evaluation重叠，才能 include；共享风险类别不自动等于泄漏。两方都include才最终include；任一exclude/uncertain则最终exclude。调用失败、raw非法/矛盾、身份或digest不匹配是pending，不能当科学排除。

复用实际A2输出结构，raw至少含pair_id、verdict、四项科学判断、rationale、prompt_revision；与外层记录绑定，不靠正则/分数代替真实判断。旧409条不重新请求。技术重试遵守已有经核验的A2策略：429最多100次是**技术上限而非应当用满的次数**，使用退避，记录attempts；非429技术问题至多一次相同输入重试，仍失败就pending并停止当前批。不得对已合法返回的exclude/uncertain重试以改变结论。等待不无限轮询，不创建每小时通知任务。

每批所有canonical结果完成后，用现有严格重建工具生成新ledger，保留A2原409条和新增全部记录及独立来源引用。不伪造新的旧审核时间/thread id。若断线从已完成记录恢复，不重复调用完成项。计数以实际可执行的唯一pair为准；不用两个reviewer算成两条pair。

## 5. 离线核验和一次最终 prepare

整合时只补 source/protocol/config 必要兼容与最小针对性测试，不重新实现审计平台。验证：旧416行稳定；新增原文/身份保留；双侧exact去重；全量raw绑定和统一evaluation digest；所有批次固定裁决；k边界与角色隔离；实际source/config/review/源码快照可追溯。

B3已完成E1/E2资产模板时复用它，不重新下载、不把E1 provisional队列写成PASS。根据已审完整ledger离线重算N和k；不要每批都启动一个重复的prepare。

若两个批次结束N仍<250：保存source/ledger、统计/测试证据，最终 `BLOCKED_INSUFFICIENT_CONSTRUCTION_PAIRS`，无需再运行必然blocked的prepare。若N>=250且无pending，运行一次最终完整离线测试：

```bash
launch_nohup recovery-v2-tests "$MBD_PYTHON" -m pytest \
  tests/paper1_broadening -q -p no:cacheprovider \
  --basetemp "$TMPDIR/recovery-v2-tests-$(date -u +%Y%m%dT%H%M%SZ)"
```

通过后复制run-specific config，显式绑定新design/source/manifest/ledger和B3资产路径。其他科学字段不变。用已有CLI帮助确认prepare参数，使用新的run id和当前索引的nohup函数，例如：

```bash
MBD_WRAPPER="$PWD/scripts/run_paper1_broadening_single_gpu.sh"
MBD_CONFIG="$PWD/.codex-temp/paper1_source_recovery_v2/expanded_run_config.json"
test -f "$MBD_CONFIG" || exit 1
launch_nohup recovery-v2-prepare bash "$MBD_WRAPPER" prepare \
  --config "$MBD_CONFIG" \
  --run-id "public-safe-pair-recovery-v2-$(date -u +%Y%m%dT%H%M%SZ)"
```

独立核对最终实际产物：source/preliminary/executable分别统计；k≥30；5 folds各k、development=100，均无重复/交叉；固定Random(42)与unused明细正确；JBB100/JBB40/benign30与原审核digest一致；near-match判定无缺项；所有新增与旧记录可追溯；source/config/源码快照一致。空集合的disjoint=true不算通过。报告实际N/k，不把250/30当预定结果。

E1最终frame尚未完成时仍保持独立 `PENDING`/`NOT_RUN`，不得声称总prepare/runtime已可启动正式实验。`READY_FOR_CONSTRUCTION`在本任务仅表示safe-pair数据gate；E1后续只从HarmBench候选排除与实际construction/development/JBB等重叠项，不回头按E1重选safe pairs。技术失败保留原run，报告问题，不循环重试prepare来得到PASS。

## 6. 交付、自审与停止

保存 `writing/broadening design/report/paper1_public_safe_pair_gate_recovery_report.md`，包含：

- 前置报告/实际文件、HEAD/dirty、执行边界；来源URL/revision/许可/生成方式披露、选择理由和被拒候选；
- 每批冻结顺序、预检排除、入选/未入选、全部reviewer verdict、requests/attempts/重试；原409条复用证据；
- 新source/revision/manifest/config/ledger/脚本/测试的实际路径与落地后hash；有变更的科学字段差异应仅限已授权来源修订；
- 实际N/k、fold/development/unused、prepare路径或未运行理由、最终safe-pair gate、E1/E2剩余门槛；
- 命令/PID/log/exit、可同步文件清单、完整raw证据压缩包位置/大小/hash。

把小数据、config、source修订、整合脚本、ledger/summary/请求索引/prepare小文件和测试改动准备好同步；不只提交报告。raw证据保留服务器并提供可转移包；不将权重/缓存/认证信息加入交付。不要自己commit/push。

做一次有边界自审，逐项记录PASS或问题：没有复用失效194条；没有为凑数改标准/重审旧排除项；批次预选与全量完成；来源/原文/identity正确；N/k/互斥分割正确；schema兼容和E1/E2状态诚实；没有新增实验块、没有进入模型阶段。只修复任务内问题并复核相应项；无法解决则保存阻塞报告，不伪造PASS。

最后写 `FORMAL_EXPERIMENTS_NOT_RUN`。任务完成或达到明确阻断条件后停止，不自动启动C/D或Core。
