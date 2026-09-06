# Paper 1 GPT-5.6 实现任务书审阅

日期：2026-09-05  
对象：[实现任务书](../implementation/paper1_ccf_a_experiment_implementation_spec_gpt56.md)

对应：[实验设计](../paper1_minimal_broadening_experiment_design_no_mistral.md)

版本：`MBD-NM v2.1-ccf-a-target`  
实现规格修订：`linux-single-gpu-v1`  
结论：**PASS，限实现规格静态审阅；尚无新代码、离线测试结果或模型 smoke 结果。**

## 一致性复核

| 检查 | 结果 |
|---|---|
| 模型与范围 | Core Qwen/Llama，E2 Gemma 候选；不含 Mistral；E1/E3 不自行增加新矩阵 |
| Prompt frames | JBB100；JBB40 每类前 4；E1 固定 40/至少 4 native categories；benign30 |
| 数据隔离 | construction 动态五折、development100、screen20、evaluation；overlap 先审再固定 |
| 层与向量 | 全部 resid_pre；明确第三模型/早晚层公式；E3 引用核心 4 tensors，core 参照不重跑 |
| Calibration | user-content span；mu token weighted；两 family 共享同模型/层 mu；E1 引用 A/S，E2/E3 独立 screen |
| A/S | 缺失、平局、无 unsafe、S<=A、sign-negative 状态均明列，禁止从 evaluation 重选 |
| 预算 | Core 12,640 + extension 7,840 = 20,480；两个 Judge 任务不冒充一次模型调用 |
| 时序 | smoke 在 screen 前；screen 包含 Judge；human 标签后另做敏感性分析；最后 archive |
| 科学状态 | 非正结果/未建立 ordering 与技术失败区分；没有 CCF_A_PASS |
| 可追溯性 | run 身份和源码副本在启动时保存，文件 SHA256 只在结果关闭后计算 |

## 代码契约复核

已核对仓库存在的入口：`activation_guard/interventions.py` 的实际 hook 是
`register_forward_pre_hook`；public v1 mask slicing 可能随模型模板不同而产生不同 realized
phase。规范要求记录这种差别，禁止硬编码 prefill-only 来强迫一致结果。

`activation_guard/analysis.py` 的旧过滤器不保证 user-only content，任务书已指出 span
mask 必须单独验证。`stage3_pipeline/real_judge.py` 有 semantic thinking/final 解析，
但现有 Stage 3 rubric 与 Stage 1 four-class rubric 不能只因标签同名就视为同一版本。
任务书明确指定 Phase Judge rubric、Qwen3-8B 配置和 source revision 记录。

Schema 覆盖 run、frames、directions、dose、attempts、canonical ledger、Judge、analysis、
human 和 archive。Logical identity 含真实 scientific key，clean 空向量字段和 A=S alias
可去重；所有 scheduled identities 包括未执行项均进入账本。

Generation status 不含人为预判的 broken；Judge parse/null 不会默认 safe；four-class 与
binary 的缺失互不删除有效记录。短输出规则仅限明示的 legacy binary 指标，不能充作
four-class 判断。

## 统计与人审复核

规定了类别/提示/方向权重、A/S 共同坐标、missing bounds、paired missing 门槛、同步
bootstrap、nearest-rank 百分位和少于 9,500 次成功的处置。区间范围是每组两个端点，
不能升级为全研究同时推断或一般 harmful distribution 结论。

160 概率样本与 40 定向诊断分开；extension 40/block 用轮转整数配额。N/n、blind_id 和
private identity key 完整；类分母为零输出 null，gold count<10 输出人审不足。未要求用
40 条小样本验证每个 family/layer 的效果方向，也没有用 fixed720 混合扩充名义样本量。

## 过度设计与修改边界复核

已避免两套手工同步 registry、OS 只读锁、每条输出完整 trace、每条记录哈希、模型缓存
复制和新的工作流平台。建议模块是职责边界，不强制拆成大量文件。测试集中在科学契约
容易被实现错的地方，普通文档修订不要求写单元测试。

Archive 不自哈希、不回填并改变已哈希输入；dirty 源码通过启动副本可追溯。分析 bug 与
科学参数变更分别处理，避免每次修正都重跑无关 generation。旧 Stage 3 预哈希规则保留
历史语义，不通过修改旧 contract 来运行本次实验。

## 尚待实施的检查

本次只修改设计文档，未运行模型、未启动新实验、未实现代码或声称测试通过。GPT-5.6 实现
后应先运行规定 fixtures、输出实际 prepare 预算，然后按可用资产与用户运行授权做模型
smoke。缺 E1/E2 不阻塞 core 与 fixtures 的开发，未审 overlap 不可由代码自动填 PASS。

最终交付必须说明实际通过的检查和未完成条件；本审阅不能替代模型运行中的行为、模板、
token span、Judge 可靠性与数值精度验证。

已完成文档静态检查：四份文件版本均为 v2.1，预算均为 20,480；相互链接存在，代码围栏
配对。离线 fixtures 是后续代码交付的验收要求，本次没有声称这些测试已经执行。

## Linux 单卡适配复审

本轮只修改实现任务书及本审阅记录，科学设计 v2.1、20,480 条逻辑 generation 和新增人审
预算不变。环境信息来自用户提供的服务器快照；没有远程登录或将其标为本机实测。

| 检查项 | 审阅结果 |
|---|---|
| Linux 路径 | 项目固定 `/data/goodtaste_workspace/llama-prefix`；结果新增 `results/paper1_broadening/`，不混入历史 Stage 3 |
| 解释器 | 正式模型/默认测试使用 `/data/goodtaste_workspace/envs/llama-prefix/bin/python`，不误用 base/llama_attack；CPU 统计环境单列 |
| 临时目录 | Bash 在进程启动前导出 TMPDIR/TMP/TEMP 到项目 `.codex-temp`，后台/安装/测试同样适用 |
| 单卡 | 默认物理 0，逻辑 cuda:0；GPU worker 只可见一张卡，禁止 auto 多卡放置和并行模型驻留 |
| 单卡 screen | CPU 调度器依次 generation/进程退出/Judge/进程退出/A-S 决策，不因串行改变科学筛选顺序 |
| 共享资源 | 启动时查 GPU UUID/占用和磁盘，OOM 不自动加卡或改 dtype；不用 /tmp 绕过同分区空间限制 |
| 本地模型 | Qwen/Llama 的配置链接和 realpath 均记录；Qwen3 Judge 本地加载；目录名不伪造 revision |
| HF 离线 | 三个离线环境变量与 local_files_only=True；缺文件返回状态而非联网重试 |
| E1 | 独立 HarmBench 仍缺失；小型原始数据及 source metadata 可经 GitHub 同步，现有 JBB 来源行不替代外部集 |
| E2 | Gemma 仍缺失；ModelScope 镜像/本机文件传输为后续准备途径，身份需核对，不把权重纳入普通 Git |
| Git 同步 | 必需同步科学设计和本任务书，建议同步两份审阅；旧 HEAD 1dd4ef9 为快照，更新后记录实际启动 commit |
| 启动/恢复 | 薄 Bash wrapper、nohup 单作业、PID/退出码/日志和 ledger 恢复；示例等待实现与实际 config |
| 依赖授权 | 用户已允许必要安装/新环境；不重复索要授权，不无关升级历史环境 |
| 归档 | 保持结果关闭后 SHA256，未增加运行前全量哈希或模型复制 |

结论：Linux 单卡文档适配通过有边界静态自审，可在文档同步后交给服务器 Codex 实现。
无需为编写核心代码再提供服务器信息；E1/E2 运行前仍须取得数据/权重并登记来源 revision。
真正执行的 Python/CUDA 兼容性、单卡显存、token span 和 smoke 仍由服务器运行时验证。

本轮静态检查已通过：Linux 单卡必需字段、临时目录/离线变量、两份修改文件的相互链接与
Markdown 围栏，以及与原科学设计的版本/预算一致性。未在本机执行文中的 Bash/Python
预检或 nohup 示例，未安装依赖、下载资产、提交/推送 Git 或连接服务器；文档同步仍待完成。

## 文档迁移复核

用户已把四份文档集中到 `writing/broadening design/`。本次修正任务书中的四处同步路径，
明确 Bash 对含空格目录加引号，并复核同目录相对链接。科学版本和 Linux 单卡规格不变。
上节“未推送”是环境适配当时的记录，后续同步状态以本次 Git 提交和远端分支为准。
