# Recovery launcher readiness prompt boundary review

审查对象：`writing/broadening design/implementation/paper1_server_codex_core_judge_protocol_v3_recovery_launcher_readiness_prompt_nohup.md`

审查结论：`PASS`

## 依据

- readiness 报告确认 bounded executor 的 fixture 测试通过，但 `main()` 仍拒绝生产
  运行，且没有真实 backend/launcher 交付；因此在 recovery approval 前补齐 launcher
  是必要的阶段性任务。
- 本机复核还发现测试文件未同步、Windows CRLF 会改变源码字节哈希；任务书要求在
  Linux 服务器重新完成逐字节同步和 artifact manifest 刷新。

## 边界

- 模型加载、Judge 请求、recovery、full rescore、screen 和正式实验严格为 0。
- 不创建或猜测 approval；不修改 v2.1/v2.3 设计、旧 F2、旧 recovery、R2、canonical
  config 或通用旧 runner。
- 只允许独立 launcher/backend adapter、executor 契约修正、对应 fixture 测试和报告。

## 契约审查

- 明确了 `.md` approval 文件必须是无 Markdown 包装的完整 JSON object，避免运行时解析
  歧义。
- 要求生产路径从 canonical approval 文件读取，且把当前 launcher/executor code hash
  纳入未来 approval；fixture 的内存注入不能绕过生产 gate。
- 要求 backend identity、调用计数、raw、diagnostics 均为必需字段，失败即停且无重试。

## 非过度设计审查

- 没有增加科学实验规模、数据源、模型或审查轮次。
- 只补齐从“离线 executor readiness”到“可审查、可批准、可运行”的最小工程缺口。
- 仍保留独立 recovery approval 和后续 full rescore approval 两道门。

结论：任务书边界清晰，可保存并推送；完成后才能进入 recovery approval 审查。
