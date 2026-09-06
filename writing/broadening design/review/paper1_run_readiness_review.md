# Paper 1 补充实验运行准备审阅

日期：2026-09-06。审阅基线：`4ec551315760fc049fcc945e9b7849245fceaeae` 及本轮修复。
审阅范围：补充实验实现、完成报告、Linux nohup任务书、用户整理后的文档路径。

## 结论与状态

- `SCOPED_CODE_REVIEW=PASS`：本轮列出的实现问题已修复，定向回归通过。
- `LOCAL_FOCUSED_TESTS=PASS`：54 passed，1项既有测试返回值warning。
- `FULL_REPOSITORY_TESTS=NOT_PASSED_LOCALLY`：完整结果见下文，不把服务器旧报告当本机结果。
- `PREPARE=PASS`：可生成审核材料，数量与固定预算可核对。
- `SAFE_PAIR_GATE=PENDING_SEMANTIC_REVIEW`：目前不能开始正式方向构造或screen。
- `REAL_RUNTIME_GATE=PENDING_SERVER_VERIFICATION`：本机CPU测试不能证明A100真实模型运行通过。
- `FORMAL_EXPERIMENTS=NOT_RUN`：本轮没有启动正式模型实验。
- `RUN_PROMPT_REVIEW=PASS`：任务书已限制为先预检、审核交接，条件满足后执行core。

代码修复完成不等于科学数据与运行条件已满足。下一步是服务器同步本轮修复、离线复核、
prepare和人工审核材料交接；审核通过且服务器已有真实smoke证据核验合格后，才能开始core。

## 发现与修复

| 严重性 | 触发与影响 | 修复位置与验证 |
|---|---|---|
| P1 | core screen按model/family嵌套保存，汇总却在model层查status，完整screen也会被标为阻断；evaluation读取剂量时又未检查core总gate | pipeline：按family叶节点汇总，读取正式core剂量时要求DOSE_DECIDED；测试覆盖完整screen和缺失候选阻断 |
| P1 | A=S共用response，ledger却要求attempt的A/S标签与每条逻辑行相同，合法alias被拒绝；alias上的重试还可能改变标签 | orchestration/pipeline：校验同一response的合法alias集合，retry保留首个attempt标签；保留两逻辑行及一个物理response |
| P1 | generation一轮后可能留下retryable，screen已开始Judge并固化missing | pipeline：在同次generation进程内排入唯一一次技术retry；测试确认两response共三attempt并完成 |
| P1 | Judge加载失败产生0调用记录，恢复时全部跳过，状态可能显示完成但无有效标签；binary更新仅在整批结束后落盘，断线会丢失进度 | pipeline：仅恢复未实际执行的记录；成功/已实际失败结果不重评，binary替换记录逐条原子保存，恢复后更新runtime状态 |
| P1 | Judge release写的是平铺字段，archive按命名runtime字典读取，真实run无法归档；终结generation缺失又被当成待执行Judge | pipeline/archive：统一release结构；仅对ledger已终结失败且error=generation_missing的Judge未执行允许终结，保留missing，不伪造标签 |
| P1 | Gemma层在运行时决定而config仍为null，clean行预期的release键成为layerNone，E2 Judge被错误阻断 | pipeline：clean引用该模型实际scheduled层；Qwen/Gemma参数化测试覆盖Judge与archive交接 |
| P2 | screen generation子进程非零退出后仍启动Judge，且blocked core可标E1 REFERENCES_CORE | pipeline：记录Judge NOT_RUN并阻断；只有core剂量已决定才允许E1引用；定向测试通过 |
| P2 | 人审包只有一句“应用给定rubric”，实际未带分类标准 | CLI：附带现有完整harmful四分类rubric，保持盲化字段 |
| P2 | 文档移动后旧链接和快照路径失效；原nohup模板在会话外不能可靠找回退出码 | 更新目录引用和设计快照；新模板在nohup子进程内写.exit，实测成功0和失败7均正确 |

审阅按本轮数据流和恢复风险展开；未增加模型、数据集、剂量、实验预算、调度框架或历史
Stage 3重构。没有通过删测试、伪造人审、降低阈值或重抽样本来获取PASS。

## 本机实际验证

解释器：`C:/Users/EGOIST/AppData/Local/Programs/Python/Python312/python.exe`。
已按用户授权安装pytest 8.3.5、pytest-subtests、torch 2.7.1（Windows CPU）、
Transformers 4.57.6、datasets 2.21.0、matplotlib、accelerate、psutil及所需传递依赖。
未安装模型权重或改服务器环境。安装缓存、测试临时文件、绘图缓存均在项目.codex-temp。

可在本机复用的测试命令：

```powershell
$codexTemp = Join-Path (Get-Location) '.codex-temp'
New-Item -ItemType Directory -Force $codexTemp | Out-Null
$env:TEMP = $codexTemp
$env:TMP = $codexTemp
$env:TMPDIR = $codexTemp
$env:NX_DAEMON = 'false'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE = '1'
$env:MPLCONFIGDIR = Join-Path $codexTemp 'matplotlib'
python -m pytest tests/paper1_broadening tests/stage3_model -q -p no:cacheprovider --basetemp "$codexTemp/final-focused-review"
```

结果：54 passed，1 warning，20.86秒。包含38个补充实验测试及16个共用模型契约测试。
日志：`.codex-temp/final-focused-review.log`；JUnit：`.codex-temp/final-focused-review.xml`。
warning来自既有stage3_model测试函数返回非None，不影响本次通过结果。

全库验证如实保留：

- 直接 `pytest tests`：2项收集错误，旧Stage 3测试导入时读取服务器绝对路径tokenizer文件。
- 临时在命令行排除这两个收集入口后：233 passed、30 failed、58 errors、96 subtests passed、
  5 warnings。失败出现在旧Stage 3：服务器历史结果缺失、POSIX路径与Windows路径契约、
  staging area必须为空、源码目录不可有bytecode、旧向量跨环境bitwise regeneration等。
- 日志为 `.codex-temp/full-review-tests.log`、`.codex-temp/portable-review-tests.log`。
  未改这些测试或清空用户暂存区，也未将排除入口的运行称为全库通过。服务器全库结果仍需
  在其实际资产环境核验，旧报告中的294 passed不能证明本轮提交全库通过。

其他检查：Python编译、git diff --check；Git Bash对任务书所有bash代码块做语法检查，
并用两个无模型小命令验证nohup模板的PID、日志与.exit（0、7）。这些不是Linux A100实测。

本机prepare使用本机路径副本，不改正式服务器配置，未加载模型。实际得到：

| 项目 | 结果 |
|---|---|
| JBB100 / JBB40 / benign30 | 100 / 40 / 30 |
| safe-pair来源数量 / preliminary合格数量 | 500 / 498 |
| preliminary k | 79，人工筛除后可能变化 |
| overlap候选行数 | 86，不等于全部待审pair数量 |
| gate | PENDING_SEMANTIC_REVIEW |
| E1 | NOT_RUN |
| 总逻辑generation预算 | 20,480 |
| 设计快照 | 已包含整理后implementation/review路径与新运行任务书 |

临时prepare目录：`.codex-temp/local-prepare-review/paper1-20260906T012345Z-38e1cb3e2f`。
上述数量是准备阶段状态，不能将k=79或498合格写成已通过语义审核。

## 仍需服务器或人工完成

1. 当前未提供safe-pair人工决策文件。算法的near-match只是候选检索，不能证明无语义泄漏。
2. 若两位reviewer有分歧，现解析器不支持仅填写研究者裁决就放行；任务书要求保留原始意见，
   先做最小裁决接口适配与测试，而非伪造双人一致。当前无审核输入，所以该路径未实际执行。
3. 核验服务器既有真实smoke原始trace与环境，不能只读总PASS；本机没有对应A100/模型资产。
4. E1缺登记的外部benchmark/metadata，E2缺Gemma；E3还需core及额外层运行验证。
   本轮运行任务书只放行满足条件的core，扩展单独交接，避免把缺资产误写成完成。
5. 人审未完成时不做FINAL归档。新任务书以生成盲标包并交接为core的终点。

## 任务书边界复查

检查了文档与实际CLI参数、nohup断线行为、非零退出/业务阻断、A/S alias、同run恢复、
人审门槛、真实smoke、扩展资产边界和post-run归档。已删除不可直接执行的尖括号路径占位，
使用实际prepare输出设置run变量；不并发GPU作业、不自动下载、不因结果不理想补跑。
这份任务书可以现在交给服务器Codex；按当前数据状态应在审核材料交接后停止。
