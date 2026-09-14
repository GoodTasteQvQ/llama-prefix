# B3：B2 代码交付与 E1/E2 资产接线

版本：`b2-delivery-asset-wiring-v2`；日期：2026-09-14。交给**原 B2 会话继续**，取代本文件v1。

先读 [当前任务入口](paper1_server_codex_post_audit_task_index.md)，执行 Linux/nohup 和并行归属规则。只做交付收尾/最小接线，不重新开发实验，不 prepare、smoke、加载模型或正式运行。

## 1. 补齐 B2 实际交付

上次在 `1124c53` 核对时，本机及远端尚无B2修复报告、public config、ledger重建脚本及修复源码；之后推送的是任务文档。记录服务器实际HEAD/branch/dirty/新文件，区分B2与A2后续修改，保留用户文件。

找到原 `writing/broadening design/report/paper1_implementation_contract_repair_report.md`；若服务器也没有，依据真实 diff/日志/产物补写，明确“事后重建的交付报告”、依据和缺项，不伪造历史保存时间或测试。

读原 B2 任务逐项核对：raw JSON 与 pair/revision/verdict 绑定；actual evaluation digest；严格 public config；snapshot 无已删路径，覆盖实际 public 输入和 dirty/new code。旧 canonical config 可历史兼容，正式入口显式 public，不 fallback 到 AI source；schema 兼容不意味着旧失效 ledger 可用。

原A2已经完成真实请求/独立性专项核验，本任务直接复用其结论，不重复核验agent身份。只确认当前集中校验能接受最终rebuilt ledger并拒绝已知非法输入；相同版本已有测试覆盖时引用证据。不改A2 runner/协议/标签/旧run。必要修复限于上述契约，不重写审核系统。

## 2. 接入已有 E1/E2 资产

读 C/D 与资产报告，先排查 A2 的缺资产状态是否来自未配置，不能据此再次下载。

1. E1：已验证 CSV/metadata/LICENSE 在 `data/external/harmbench/`，revision=`c0423b952435fcc8467108d8f25962dbae5b7de2`；standard=200，严格由 `FunctionalCategory == standard` 派生。
2. 检查 `_load_e1` 接口。如果只接 JSON，复用已有 adapter；没有才补确定性 CSV→JSON，小版本输出单独保存。映射 `Behavior→text`、`SemanticCategory→category`、`BehaviorID→source_id`、原始 all CSV index→`source_index`；metadata benchmark 按现有契约 `HarmBench_standard_text`。逐行核对原文/类别/ID/index，不改成筛选后的索引，不选择最终 40 条。
3. E2：model/tokenizer=`/data/goodtaste_workspace/models/gemma-2-9b-it`。复用 D 证据，读 config 确认 L=42、设计解析层14；按现有字段设置或推导。仅文件/配置检查，不重 hash 全部权重、不重复零剂量探针。
4. 从 public config 另存资产模板，建议 `configs/paper1_broadening/mbd_nm_v211_public_assets.json`，接 E1 路径/metadata、E2 路径。core 参数、20,480 logical generation、无 Mistral 不变。仍指公开 source，ledger 显式绑定实际审核，未绑定则 fail closed；不填虚假的 E1 overlap PASS。E 以后复制为 run config。
5. 核实是否已采用 LF-canonical manifest 纠偏；若未采用，另存修复 manifest revision，登记原 hash/实际 LF hash/规范化规则，保留原 manifest/LICENSE。不再把已解释的 CRLF/LF 差异当新来源事故，不改 source 内容。

资产可读/adapter正常不等于E1 overlap、E2 runtime/dose gate通过。能顺手完成的接线在本次完成；若某扩展资产问题需要额外排查，记录E1/E2具体PENDING原因后先交付可用的core实现，不用扩展接线阻塞safe-pair恢复。不以“缺资产”为由重新下载/探针或扩大修复范围。

## 3. 验证与可复核交付

代码/配置变动后运行一次包含必要针对性覆盖的 `tests/paper1_broadening`；必要adapter测试验证原文/类别/原始索引保留，已被完整套件覆盖的测试不另跑一遍。对实际改动的Python/shell做对应compile/syntax检查，并检查 `git diff --check`。测试数量以实际为准，不把“必须43”当门槛。使用共用nohup，例如：

```bash
launch_nohup b3-broadening-tests "$MBD_PYTHON" -m pytest \
  tests/paper1_broadening -q -p no:cacheprovider \
  --basetemp "$TMPDIR/b3-tests-$(date -u +%Y%m%dT%H%M%SZ)"
```

若只打包且执行文件/输入未变化、原43 passed可对应代码，复用证据，不为新时间戳重复跑。不运行 prepare 复现已知 k=24 阻塞。

交付目录 `writing/broadening design/report/evidence/paper1_a2_b2_delivery/b2/` 保存：

- 原 B2 报告引用、受控文件清单、base commit/HEAD/dirty；
- 一份与测试对应的相关执行代码最终副本，包含修改文件、必要依赖和untracked脚本/config/协议/public source/manifest/adapter；保留项目相对路径，与声明的base checkout结合可恢复执行版本。也可交付已存在的等价代码归档；二者选一，不同时强制制作补丁；
- 测试/compile/syntax 证据；文件清单、落地后 hash；区分 B2 测试版本、A2 prepare 快照和 B3 最终版本，无法重建的旧版本如实记录；
- A2 的 `scripts/rebuild_public_safe_pair_ledger_v2.py` 等运行依赖只复制，不改写。

按文件清单检查交付完整即可，不强制制作diff、另建checkout或执行 `git apply --check`。只收集相关文件，不暂存/撤销/提交用户修改；不可分割共改文件说明范围。历史A2源码快照若已有就保留引用，不尝试伪造缺失历史版本。报告不能代替实际代码交付。

## 4. 报告、自审与停止

保存 `writing/broadening design/report/paper1_b2_delivery_asset_wiring_report.md`：原报告位置/是否补写、实际修改/snapshot清单、public/asset模板、E1 adapter、E2路径/层、测试与命令/PID/log/exit、交付恢复方法、剩余 gate、无后台模型进程。

当前core契约/public入口/执行版本与测试证据对应且可定位、共享代码写入已结束，才用 `B2_DELIVERY_READY`；否则 `BLOCKED_B2_DELIVERY`。文件复制/异地同步进度另记，不把打包当数据门槛。E1/E2接线状态分别报告，其未完成不把core已通过改为失败，也不授权对应扩展实验。写 `FORMAL_EXPERIMENTS_NOT_RUN`。

做一次有边界自审：未动科学参数/旧ledger/source/run；未重下载/加载模型；未把资产状态当正式gate；交付包含新文件、无无关修改、本机可复核。修复本任务问题并复核对应项，解决不了就保存具体阻塞报告。落盘后停止代码写入供E接手；不commit/push、不启动后续实验。
