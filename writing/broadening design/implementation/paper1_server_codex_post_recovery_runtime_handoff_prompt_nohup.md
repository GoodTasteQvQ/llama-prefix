# B4：新增适配检查、实际文件交付与 Core 真实 smoke

版本：`post-recovery-runtime-handoff-v1`；日期：2026-09-15。交给原B会话（已完成B3）。

完整读取 [当前任务入口](paper1_server_codex_post_audit_task_index.md)、最新recovery报告、B3报告、[C2任务](paper1_server_codex_e1_final_overlap_prompt_nohup.md)和 `writing/broadening design/review/paper1_experiment_design_immutability_audit_20260915.md`。本次接受已完成的safe-pair审核，检查的是E新增代码是否正确消费结果。允许必要的局部修复和一次有上限的core真实smoke；不构造正式方向、不选剂量、不prepare、不运行evaluation。

## 1. 只检查自B3之后的新适配

从B3交付副本或已存在的base/diff定位E实际改动：`config.py`、`frames.py`、`orchestration.py`、`scripts/recover_public_safe_pair_batch1.py`、expanded config/source/ledger/manifest。记录当前真实文件和执行身份，不拿HEAD+dirty布尔值代替代码内容。

针对以下风险做一次代码/数据核对；无需重做818+200真实reviewer来源审计：

1. **review_pair_id绑定。**内部 `safe-pair:416..515` 与上游 `turkish-over-refusal-set:1..100` 为一一映射；每条实际两侧文本、source revision和原输入hash绑定正确。旧416行原样、旧409决定内容不改；别名不得把一个raw复用给另一pair。新增79与旧221合计300唯一executable，排除209另计。
2. **不能以兼容为由绕过gate。**raw中的身份/revision/verdict与外层及实际source一致；重复alias、伪造alias、混合evaluation digest、改文本但沿用旧raw均不能进入可执行split。至少检查对应已有测试；未覆盖这些新增行为时才补少量有意义的正/反向测试。45 passed的数量不证明新增路径已有覆盖。
3. **固定分割/配置。**5×40+100、Random(42)、unused0、evaluation digest仍为 `db9026dca9a79d4e9128206118a824c862839d5eadb16440f547142386404fb7`。只读比较与已保存frames，不能重新随机分割。public v2.1.2严格指实际expanded文件；Gemma/E1本地路径/层接线及20,480预算不变，不fallback到AI source。
4. **快照覆盖实际输入。**按实际config包含expanded source/ledger/manifest/recovery脚本、已授权来源addendum、当前执行模块及必要资产引用。不是清单“47项”就算通过，不能仍只锁死旧public ledger。设计文档增删不能靠补造历史文件解决，动态run config也不能漏入快照。
5. **原设计保护。**对照任务开始时diff与现有来源addendum，只新增版本化source的已授权变更合理；正文/科学字段若有额外差异，保留并列出来源/影响，不擅自回滚或将其纳入运行。无法证明授权的科学变更报告 `DESIGN_CHANGE_REQUIRED`。

报告里“A/B各200 event stream”与200 canonical、202 attempts可能是文件分类/重复存储差异。只读已有索引明确单位即可；不要仅因文字歧义重复请求或再发起独立审计。历史freeze/review缺exit不伪造、不重跑：将其记为进程记录缺项，结果有效性以已经保存的请求和产物证据区分。

## 2. E1消费接口和未来入口范围

C2并行处理最终queue，B4只检查消费者：E1根据固定reference（JBB与实际300角色pairs）而非safe-pair evaluation digest做绑定；重复/错prompt id、错reference digest、非法raw不得放行。若当前接口仅支持safe-pair raw，允许最小独立E1 adapter/validator和必要正反向测试，不能将E1意见冒充safe-pair审核或human。不要等待C2实际review才能写fixture，也不要为适配要求C2重审。

C2报告完成后，读取其现有raw/ledger/selected40，用当前实现做一次纯CPU消费检查，与C2的40条ID、原文、类别、source index和reference一致。**不调用prepare、不重算/改写safe source或safe ledger。**若C2尚未完成，先完成其他工作，在报告中只将此项记待交接；不把其等待写成code/smoke失败。两边就绪后可在本轮完成交接。

只读列出 `build-directions` 的真实调度范围。本机版本会自动构造core、E3层测量和已接入Gemma的E2资产；若服务器相同，准确报告。不要执行该命令，不为本轮临时加block开关、拆调度系统或设Gemma为null规避。正式方向的content mask/mu/符号诊断仍是下一阶段工作。

## 3. 验证与smoke预算

需要修复时，仅改上述直接相关实现/测试。完成一轮相关测试（未改且既有同版本证据完整可复用）；若新增适配，再跑一次完整 `tests/paper1_broadening`。已包含的focused tests无需另跑，对改动Python/shell做对应compile/syntax检查。不得删断言让测试过关。所有命令采用索引中的项目内临时目录/nohup。

先定位旧core真实smoke的原始case/trace/环境记录。如可确认与当前runtime/hook/template/decoder/Judge路径等效、完整覆盖下列核验，可复用并说明绑定依据，不强求独立trace/environment文件。source追加本身不使基于两个非evaluation prompt的smoke失效。仅有PASS摘要或零剂量结果不足。

缺充分旧证据时，本任务授权 **一次新的Core真实smoke：最多24次generation、4次four-class Judge**，调用上限包含任何重试。使用已有两个非evaluation benign prompts及临时向量，生成上限16 tokens；不得拿JBB、HarmBench或development做smoke，不顺手扩展到Gemma。此smoke是工程检查，不构造正式contrastive向量，也不提供论文unsafe证据。

确认GPU0空闲、代码修复结束，显式传expanded config，使用新输出目录。例如先检查现有CLI参数及函数仍符合上述预算，再运行：

```bash
MBD_WRAPPER="$PWD/scripts/run_paper1_broadening_single_gpu.sh"
MBD_CONFIG="$PWD/configs/paper1_broadening/mbd_nm_v212_public_expanded.json"
MBD_SMOKE_OUT="$PWD/.codex-temp/paper1_b4_smoke-$(date -u +%Y%m%dT%H%M%SZ)"
launch_nohup b4-real-smoke bash "$MBD_WRAPPER" smoke \
  --real --config "$MBD_CONFIG" --output-dir "$MBD_SMOKE_OUT"
```

执行前保存实际config/runtime源码引用与Python/PyTorch/Transformers/CUDA、模型/tokenizer/Judge身份和实际模板等可见信息，复用现有记录不另造全项目不可变manifest；case完整落地后再做必要hash。hf离线、单GPU0、顺序加载Qwen/Llama/Judge，实际释放前不能加载下一模型。失败保留报告/日志/raw，在预算内只修明确技术问题；本轮不自动重开另一套24+4。

必须读取实际trace核验：原生模板/use_cache/resid_pre；decode_only无prefill注入、非零dose在cached decode按规则注入；public_v1按现有实际mask/时序工作，不强行要求模型间相同；clean与zero-alpha的token ids对应相等（检查已有case中的两个phase）；有限tensor/正确层、无silent no-cache fallback；正常EOS/零decode状态诚实记录，缺未覆盖路径不能声称通过；四次Judge真实输出可解析且生命周期正确。PASS顶层字段不能替代这些case证据。

若某必要trace字段缺失，可在新smoke前做最小记录修复；不能要求标准运行保存巨量完整trace。新smoke最多24 generation+4 Judge=28条case是不同类型合计，不能把28写成generation次数。记录实际调用和失败计数，而不是仅成功输出数。

## 4. 实际文件交付和停止

本机至今只收到报告。本轮交付一份**最终可执行文件集合**，不要再次只同步报告：

- 改动及必要新增代码/测试、explicit expanded config、其执行依赖；
- 516-row expanded source、509-record ledger、manifest、原public v1及必要来源README/LICENSE/NOTICE/匹配与配对metadata；
- `paper1_public_safe_pair_source_expansion_revision.md`、实际review协议、batch freeze/summary/必要请求索引；
- 恢复prepare的header/config/frames/plan/identity_plan等小文件，C2完成的ledger/40条（若已到）；
- 本次代码检查/测试/smoke原始小产物与当前文件清单。完整raw可留原路径，按需转移；不重复制权重/缓存，不强制同时制作补丁和快照。

复用B3已有交付目录，但E已修改的文件用新的交付revision另存，不能把B3旧副本当最新代码。文件清单列项目相对路径、来源、关闭写入后hash；只收集实验相关文件，完整raw含敏感认证信息的部分不要对外提交。说明用户应如何同步实际文件；本任务本身不commit/push。

保存 `writing/broadening design/report/paper1_post_recovery_runtime_handoff_report.md`，分别列 `CODE_CONTRACT_PASS/BLOCKED`、`CORE_REAL_SMOKE_PASS/BLOCKED/NOT_RUN`、`E1_CONSUMER_PASS/PENDING/BLOCKED` 和交付进度。源代码快照/历史记录缺项如实分层，不因一个报告缺文字伪造全局失败。没有新实际证据不重开A2/E全量审核。

一次边界自审只检查：新identity映射正确、未改科学设计、检查覆盖真实变更、smoke调用数/phase证据/单卡生命周期、E1接口诚实、实际文件可交付。修正本任务直接问题并复核对应项；无法解决则保存具体阻塞，不强行PASS。完成后停止：`FORMAL_EXPERIMENTS_NOT_RUN`，真实smoke标 `NON_EVIDENCE`；没有directions、dose screen、evaluation或human结果。
