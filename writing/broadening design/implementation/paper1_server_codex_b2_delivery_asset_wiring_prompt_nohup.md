# B3：B2 代码交付与 E1/E2 资产接线

版本：`b2-delivery-asset-wiring-v1`；日期：2026-09-14。交给**原 B2 会话继续**。

先读 [当前任务入口](paper1_server_codex_post_audit_task_index.md)，执行 Linux/nohup 和并行归属规则。只做交付收尾/最小接线，不重新开发实验，不 prepare、smoke、加载模型或正式运行。

## 1. 补齐 B2 实际交付

本机及远端 `1124c53` 尚无 B2 修复报告、public config、ledger 重建脚本及修复源码。记录服务器 HEAD/branch/dirty/新文件，区分 B2 与 A2 后续修改，保留用户文件。

找到原 `writing/broadening design/report/paper1_implementation_contract_repair_report.md`；若服务器也没有，依据真实 diff/日志/产物补写，明确“事后重建的交付报告”、依据和缺项，不伪造历史保存时间或测试。

读原 B2 任务逐项核对：raw JSON 与 pair/revision/verdict 绑定；actual evaluation digest；严格 public config；snapshot 无已删路径，覆盖实际 public 输入和 dirty/new code。旧 canonical config 可历史兼容，正式入口显式 public，不 fallback 到 AI source；schema 兼容不意味着旧失效 ledger 可用。

对 A2 ledger 做只读集中契约校验；A3 同时读取时使用稳定副本。不改 A2 runner/协议/标签/旧 run。必要修复限于上述契约，不重写审核系统。

## 2. 接入已有 E1/E2 资产

读 C/D 与资产报告，先排查 A2 的缺资产状态是否来自未配置，不能据此再次下载。

1. E1：已验证 CSV/metadata/LICENSE 在 `data/external/harmbench/`，revision=`c0423b952435fcc8467108d8f25962dbae5b7de2`；standard=200，严格由 `FunctionalCategory == standard` 派生。
2. 检查 `_load_e1` 接口。如果只接 JSON，复用已有 adapter；没有才补确定性 CSV→JSON，小版本输出单独保存。映射 `Behavior→text`、`SemanticCategory→category`、`BehaviorID→source_id`、原始 all CSV index→`source_index`；metadata benchmark 按现有契约 `HarmBench_standard_text`。逐行核对原文/类别/ID/index，不改成筛选后的索引，不选择最终 40 条。
3. E2：model/tokenizer=`/data/goodtaste_workspace/models/gemma-2-9b-it`。复用 D 证据，读 config 确认 L=42、设计解析层14；按现有字段设置或推导。仅文件/配置检查，不重 hash 全部权重、不重复零剂量探针。
4. 从 public config 另存资产模板，建议 `configs/paper1_broadening/mbd_nm_v211_public_assets.json`，接 E1 路径/metadata、E2 路径。core 参数、20,480 logical generation、无 Mistral 不变。仍指公开 source，ledger 显式绑定实际审核，未绑定则 fail closed；不填虚假的 E1 overlap PASS。E 以后复制为 run config。
5. 核实是否已采用 LF-canonical manifest 纠偏；若未采用，另存修复 manifest revision，登记原 hash/实际 LF hash/规范化规则，保留原 manifest/LICENSE。不再把已解释的 CRLF/LF 差异当新来源事故，不改 source 内容。

资产可读/adapter 正常不等于 E1 overlap、E2 runtime/dose gate 通过。

## 3. 验证与可复核交付

代码/配置变动后做针对性离线验证及一次完整 `tests/paper1_broadening`；必要 adapter 测试验证原文/类别/原始索引保留。相关 Python compile、shell syntax、`git diff --check` 也通过。测试数量以实际为准，不把“必须43”当门槛。使用共用 nohup，例如：

```bash
launch_nohup b3-broadening-tests "$MBD_PYTHON" -m pytest \
  tests/paper1_broadening -q -p no:cacheprovider \
  --basetemp "$TMPDIR/b3-tests-$(date -u +%Y%m%dT%H%M%SZ)"
```

若只打包且执行文件/输入未变化、原43 passed可对应代码，复用证据，不为新时间戳重复跑。不运行 prepare 复现已知 k=24 阻塞。

交付目录 `writing/broadening design/report/evidence/paper1_a2_b2_delivery/b2/` 保存：

- 原 B2 报告引用、受控文件清单、base commit/HEAD/dirty；
- B2/B3 tracked 相关文件的真实可应用 diff，以及必需 untracked 脚本/config/协议/public source/manifest/adapter 的原样副本；仅 diff 不含新文件，不能漏交；
- 测试/compile/syntax 证据；文件清单、落地后 hash；区分 B2 测试版本、A2 prepare 快照和 B3 最终版本，无法重建的旧版本如实记录；
- A2 的 `scripts/rebuild_public_safe_pair_ledger_v2.py` 等运行依赖只复制，不改写。

在独立临时副本对声明 base 做 `git apply --check`，不向共享树应用。只打包归属本任务的文件/hunk，不暂存/撤销/提交用户修改；不可分割共改文件交付最终副本并说明范围。Git 同步需要实际代码或可应用 diff+新文件包，报告不能代替它们。

## 4. 报告、自审与停止

保存 `writing/broadening design/report/paper1_b2_delivery_asset_wiring_report.md`：原报告位置/是否补写、实际修改/snapshot清单、public/asset模板、E1 adapter、E2路径/层、测试与命令/PID/log/exit、交付恢复方法、剩余 gate、无后台模型进程。

当前契约/public入口/资产接线/可重建交付核验通过才用 `B2_DELIVERY_READY`，否则 `BLOCKED_B2_DELIVERY`。写 `FORMAL_EXPERIMENTS_NOT_RUN`。

做一次有边界自审：未动科学参数/旧 ledger/source/run；未重下载/加载模型；未把资产状态当正式 gate；diff覆盖新文件、无无关修改、本机可复核。修复本任务问题并复核对应项，解决不了就保存阻塞报告。落盘后停止代码写入供 E 接手；不 commit/push、不启动后续实验。
