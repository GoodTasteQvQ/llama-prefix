# Safe-pair 恢复结果和下一步任务审阅

日期：2026-09-15；本机报告基线 `a5f5dd4`。范围仅为最终恢复报告、现有设计/接口、C2/B4任务及状态表；不作全库或新一轮safe-pair语义审计。

## 结论依据

报告计数一致：516−7=509 preliminary；221+79=300 executable；188+21=209 exclude；300+209=509；`min(80,(300−100)//5)=40`，5×40+100用尽300条。新增100对全部200 canonical审核已结束，两个技术retry对应202 attempts，未启用第二来源。接受服务器已完成结果作为继续工作的依据，无需再次补数据或重复请求。

报告中freeze/review wrapper缺exit是运行记录缺项；报告保留了完整请求/raw、批次固定及后续整合/测试/prepare exit=0依据，不能仅为补一份exit重复科学审核，也不能把缺失exit写成存在。“A/B各200 event stream”与canonical/attempt不是同一单位，B4仅复用索引澄清分类，不重发请求。最终safe-pair ready不等于正式runtime或E1 gate已通过。

本机只同步了报告，没有 `mbd_nm_v212_public_expanded.json`、expanded source/ledger、实际E代码、来源addendum及prepare原件，`report/evidence/`也尚不存在。因此未在本机复现45 tests或300条分割。此前对B3的“通过”应理解为报告层接受，不能解释成实际源码/原始文件已在本机验收。本轮B4要求交付一份实际文件集合，不再以摘要代替代码，也不把异地压缩包作为服务器工作前置。

## 设计变化

已同步设计正文没有本轮新增修改；恢复报告称新增独立 `v2.1.2-public-pairs-expanded` 来源修订，保留旧416行并追加100行、同一判定/分割规则，得到k=40。这属于此前明确授权的有限来源扩展，原则上应保留。该revision原件和服务器dirty diff未同步，具体内容由B4对照实际文件核验，不能先断言正文绝对未改。模型/层/预算/endpoint等若有额外差异，必须记录并报告 `DESIGN_CHANGE_REQUIRED`，不直接保存为批准设计。

## 后续安排及边界审查

| 项目 | 判断与处理 | 结果 |
|---|---|---|
| 是否重复恢复任务 | source已经足够，E/A/D本轮不新开任务，旧509项审核复用 | 通过 |
| E1是否需要全量双审 | 只重新确定实际角色集合下的near queue；约17个prompt才双审，200候选做确定性预筛，不自动做400次review | 通过 |
| E1排除依据 | JBB和实际200 construction+100 development两侧；不把未使用/排除source也当角色数据 | 通过 |
| C2/B4并发 | C2只写自有数据/raw/报告，不import变动模块；B4唯一共享代码写入者且唯一GPU使用者 | 通过 |
| 新identity兼容风险 | review_pair_id映射必须绑定实际source/input，重复alias/错pair/错digest不能放行；补缺失的针对性测试而非重审语义 | 通过 |
| E1接口适配 | C2原始意见不得伪装成safe-pair/human；必要最小消费者适配由B4做，避免并发改frames.py | 通过 |
| smoke是否重复 | 先看旧完整trace/环境能否证明等效；没有才一次≤24 generation+4 Judge，不要求另外独立trace文件，不再做Gemma零剂量探针 | 通过 |
| 是否误跑正式构造 | 本机build-directions会连带E2/E3资产；B4只读确认真实范围，不加新调度框架，不执行 | 通过 |
| 不必要的prepare/测试 | 本轮不重跑safe-pair prepare，不跑全库；只测直接变更，完整套件已覆盖的focused不另跑 | 通过 |
| 交付冗余 | 一份实际执行文件与新数据清单即可，raw按需转移，不强制补丁+clone+压缩三套 | 通过 |
| 科学门槛与原设计 | 无新模型/剂量/来源/实验块，20,480预算未变；原正文及已批准revision只读 | 通过 |
| 退出与结果声明 | C2报告数据状态；B4分别报告代码、smoke、E1消费状态，不把NON_EVIDENCE或E1_FRAME_READY当论文结果 | 通过 |

补充检查：当前 `a5f5dd4` 与恢复前设计版本之间，原实验设计正文没有新的差异；E 只新增了已授权的 `MBD-NM v2.1.2-public-pairs-expanded` 来源修订。C2/B4 任务现已明确将设计正文只读，遇到必须改变科学字段时报告 `DESIGN_CHANGE_REQUIRED` 并停止。任务文档已完成一次上述边界审阅，发现的范围风险（build-directions自动包含扩展资产）已写入约束。后续文档检查仅验证链接/代码块/差异，不另发服务器审计任务。

结论：`NEXT_TASK_DOCUMENT_REVIEW_PASS`。可以交付C2/B4；当前 `FORMAL_EXPERIMENTS_NOT_RUN`。下一轮正式方向、dose screen和evaluation仍需基于实际C2/B4交接结果安排。
