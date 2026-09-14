# A3：记录已完成的 A2 核验并交付文件

版本：`a2-evidence-handoff-v2`；日期：2026-09-14。交给**原 A2 会话继续**，取代本文件 v1。

先读 [当前任务入口](paper1_server_codex_post_audit_task_index.md)。本次仅收尾交付；不重跑818请求核验、不重新评判409条、不新增6对诊断、不发reviewer请求、不prepare或加载模型。

## 1. 直接复用已经完成的检查

负责人已收到原A2会话的专项核验结果：409条preliminary eligible各有A/B，818个request/thread ID全局唯一；每pair两侧身份不同，执行严格串行；各有独立prompt/input hash/raw events/output/模型参数及独立空workdir，read-only与peer-output隔离证据齐全。最终rebuilt ledger为COMPLETE，无invalid/pending；`safe-pair:341`使用单独retry raw。

将你实际已经执行的核验命令/脚本/结果路径写入报告，直接引用已有证据。串行和唯一ID是辅助证据，隔离结论以已检查的实际请求内容/运行设置为依据。不要仅为了换一个任务名重复检查；若某一必要项此前确实没有做，准确列出，仅补该项。

## 2. 记录最终产物，避免旧统计误用

完整review目录：

`.codex-temp/paper1_broadening_machine_reviews/public-semantic-pairs-v2-20260908T111917Z/`

只使用其中的 `rebuilt_summary.json` 与 `public_pair_quality_decisions.v2.rebuilt.json` 作为最终依据。原 `summary.json` 的817 ok/1 pending是retry前统计，保留作历史，不更新原文件、不算最终失败、不触发重审。416条source中7条因exact overlap在preliminary阶段排除，无需reviewer。

把最终ledger已存在的计数写清：221 include、188 exclude、无pending，k=24；无需再运行prepare得到同一阻塞。若实际文件与该计数不一致，报告具体差异，不能修改记录凑数。旧v1的194条仍无效。

## 3. 最小交付

小文件统一放 `writing/broadening design/report/evidence/paper1_a2_b2_delivery/a2/`，或复用已有可同步目录：

- 最终ledger、rebuilt summary；
- 实际固定review prompt/协议、已有请求索引、此次核验结果文件或日志；
- prepare的header/config/frames小文件（已有就引用或复制，不重新生成）；
- 一份简短文件清单，列原路径、交付路径及必要的落地后hash，避免误拿旧summary。

完整raw/attempts保留服务器原路径，报告位置和如何定位即可；本任务不强制复制全部raw或生成压缩包。需要异地复核时再打包，打包不是后续数据审核的前置。不要加入认证信息、无关会话或模型权重。`scripts/rebuild_public_safe_pair_ledger_v2.py`由B3统一收进代码交付，A3只引用路径。

存在性/最终文件身份核对属于正常交付检查，不应重新发展成全量来源审计。必要批量脚本采用索引中的Linux/nohup规则；已有核验日志直接复用，不追补虚假的PID或历史执行记录。

## 4. 报告与停止

保存 `writing/broadening design/report/paper1_a2_evidence_handoff_report.md`，记录实际核验依据、最终summary/ledger、计数、341 retry、旧summary说明及交付清单。核验已完成且文件定位无误时写 `A2_HANDOFF_RECORDED`；如果出现具体证据矛盾，列受影响项和阻塞原因。不要把尚未在本机重新核验写成本机验收通过。

一次收尾自查仅检查：有没有用旧summary、漏交最终ledger、改动原记录或重复启动任务。文件打包问题自行修正；原始证据矛盾如实报告，不自动全量重审。写 `FORMAL_EXPERIMENTS_NOT_RUN`，保存后停止，不commit/push。
