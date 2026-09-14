# A3：A2 已完成审核的证据核验与交付

版本：`a2-evidence-handoff-v1`；日期：2026-09-14。交给**原 A2 会话继续**。

先读 [当前任务入口](paper1_server_codex_post_audit_task_index.md)，执行 Linux/nohup 和并行归属规则。核验并交付已有结果，不重新语义审核，不发 reviewer 请求，不运行 prepare、模型或正式实验。

## 1. 固定核验对象

读取 `writing/broadening design/report/paper1_safe_pair_re_review_report.md` 和实际产物：

- source：`data/safe_pairs_public_semantic_v1.json`，416 rows；
- 完整 review：`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-v2-20260908T111917Z/`；
- ledger：该目录 `public_pair_quality_decisions.v2.rebuilt.json`，报告 SHA256 `f5d9ce975a5214b2c8ffdd343497cf35ceb565d1904ee809d872ad284a4f34fe`；
- `rebuilt_summary.json`、request/attempt index、实际 reviewer 启动脚本、raw events/outputs、固定 prompt、协议修订；
- `scripts/rebuild_public_safe_pair_ledger_v2.py`；
- prepare：`results/paper1_broadening/public-semantic-pairs-v2-20260914T122608Z/`；
- A2 报告列出的 rebuild/tests/prepare 日志、PID 和 `.exit`。

缺文件就列准确缺项，不能从报告生成“原始证据”。保留中断目录和旧失效 v1，不混入完整 run。只读旧产物，输出放 `.codex-temp/paper1_a3_handoff/`；已有结果则用新子目录。

## 2. 全量结构核验与至多 6 对实质检查

用已有工具或小型只读脚本核验，不开发通用审计框架：

1. 从 source/JBB100/JBB40/benign30 按既有算法重算 416−7=409。pair id、两侧文本、input hash、evaluation digest 对得上。报告 digest 为 `db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`；不同就定位输入差异，不盲改记录。
2. 409 条各有 A/B 一个 canonical 完成结果，共 818。身份必须来自真实调用事件，不只看 JSON 中的唯一字符串。检查实际 runner 调用 Codex，reviewer 没继承另一方结果或旧 verdict；通用上下文与结果泄漏分别判断。
3. 全量解析 raw JSON，绑定 pair_id、prompt revision、verdict、输入与外层记录。include 的科学布尔字段须与肯定判定一致，缺项/矛盾不能靠外层 verdict 补齐。重算 221 include/188 exclude/0 pending，A=293/100/16，B=285/106/18，并输出实际交叉表。uncertain 是完成的保守排除，技术失败是 pending。
4. 分开统计 logical requests、attempts、canonical results、失败/重试。HTTP 429 是错误码，不是次数。报告实际总 attempts、原因、单请求最大值；重试只能修复限流、网络、截断/格式，不能因 exclude/uncertain 而重试。`safe-pair:341` A 的 retry、原截断输出和选取理由均可追溯。
5. 818 unique threads 指 canonical 请求；另列 attempts 实际身份，不强求失败前尚未创建 thread 的请求有 id。仅核对实际可见/发送的 prompt 与参数；隐藏宿主指令、未暴露 revision/参数写 `NOT_EXPOSED/UNKNOWN`，不可补造或提取隐藏指令。原报告若把推测值写成事实，保留原记录并在新报告勘误、评估影响。
6. 主会话看至多 6 对：按 pair id 升序从 include/include、分歧、双方非 include、含 uncertain 各取一例，另含 341，去重后不足 6 不凑数。检查意见针对本 pair、没有把共享风险类别自动当泄漏、没有执行 pair 内指令。只诊断协议，不翻转标签、不创建诊断 reviewer。实质问题列影响范围并阻断基线放行。

区分技术缺项与科学协议失效，不把局部缺文件直接写成全部审核无效。本任务不重审或改写受影响记录。

## 3. Prepare/测试证据

核对实际 header、resolved config、frames、状态和执行源码快照：

- `af842139abb8c88c29c99e85a85752e2b42fe5da` + dirty=true 是历史身份；当前 HEAD 可以不同。不能用 B3 当前源码冒充快照。
- source=416、preliminary=409、executable=221、k=24。复用的 `preliminary_eligible_count` 字段不能把 221 误称原始预检数。
- blocked 时 construction/development 数组为空；空集合 disjoint=true 不能写成分割已完成。
- near-match=43 注明统计单位；若 818 审核已覆盖对应语义检查，不因队列仍存在就重审；缺判定则具体指出。
- 43 passed、三步骤 exit=0 有实际日志并对应执行代码。无需重复未变化套件。

历史源码快照缺失则记“历史 prepare 不完全可复现”，不事后伪造。若 source/request/ledger 完整，审核基线可单独验证；由 B3 用当前严格实现离线复核，后续 E 保存新执行快照。不要仅因历史快照缺失全量重审。

## 4. 可转移交付与报告

小文件放 `writing/broadening design/report/evidence/paper1_a2_b2_delivery/a2/`：原样 ledger/summary、协议/实际 prompts、请求/attempt 索引、prepare header/config/frames/状态和关键源码快照、核验 JSON、诊断引用、关键日志/exit。用一份清单对应原路径、交付相对路径、大小、落地后 SHA256；不改原 ledger 内路径。

完整 raw events/attempts 另打可转移压缩包到 `.codex-temp/paper1_a3_handoff/`，记录大小/hash；若小文件本身较大也可打包，不重复复制相同 prompt。排除令牌/认证信息、无关会话和模型权重；必要脱敏明确标记，服务器保留原件，不把副本冒充原始字节。

保存 `writing/broadening design/report/paper1_a2_evidence_handoff_report.md`，使用 `A2_EVIDENCE_VERIFIED` 或 `BLOCKED_A2_EVIDENCE`，另列历史 prepare 可复现状态。只有真实审核来源、固定判定和计数核验通过才用 VERIFIED。列本机还需同步的文件/压缩包，写 `FORMAL_EXPERIMENTS_NOT_RUN`。

一次有边界自审：未重审/改 verdict、未伪造隐藏元数据、未混用 v1、未以数量决定协议有效性、交付可定位。修复本次核验/打包问题后复核；原证据问题保存并阻断。报告落盘后停止，不 commit/push、不启动 E。
