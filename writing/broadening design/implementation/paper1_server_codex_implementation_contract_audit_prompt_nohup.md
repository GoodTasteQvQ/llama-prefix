# Broadening 实现契约与版本一致性审计任务书

版本：`broadening-implementation-contract-audit-v1`
目的：在 safe-pair 审核质量未确定时，独立核对代码、配置、source snapshot 和测试是否与当前设计一致。
本任务不运行模型，不修改实验结果。

## 1. 边界

保留所有用户修改、旧 run、旧 ledger 和旧 source。不得启动 directions、screen、generation、
Judge、analysis 或 human packet；不得使用旧 `data/safe_pairs.json` 作为正式 source。本会话默认
只读审计；若发现确有证据的 schema/路径兼容问题，只在 `.codex-temp` 生成最小补丁和测试建议，
不要直接修改共享工作树。不能改模型、层、hook、decoder、rho、seed、fold、预算或审核裁决规则。
不得 commit/push。

## 2. 环境与命令

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp logs/paper1_broadening
export TMPDIR="$PWD/.codex-temp"; export TMP="$TMPDIR"; export TEMP="$TMPDIR"
export NX_DAEMON=false; export HF_HUB_OFFLINE=1; export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1; export PYTHONUNBUFFERED=1
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
```

pytest、静态检查和脚本均通过 `nohup`，保存 PID、log 和 `.exit`，串行等待完成。

## 3. 必查项目

1. `paper1_broadening/frames.py` 的 `_semantic_status` 是否同时、等价、严格接受
   `safe-pair-semantic-overlap-v1` 与 `public-semantic-pair-quality-v1`，并拒绝缺失 provenance、
   重复 agent、非法 verdict、digest 不一致和错误 adjudication。将本机代码与服务器报告的
   dirty patch 分开记录。
2. `configs/paper1_broadening/mbd_nm_v21.json`、`paper1_broadening/config.py` 和 prepare
   loader 是否仍硬编码 `data/safe_pairs.json`、旧 design revision 或旧 ledger schema。canonical
   config 不得直接改写；只生成验证用的临时 config 副本。
3. 公开 v1 整合脚本、输出文件、source manifest、LF-canonical 候选和纠偏报告是否存在；若
   服务器只有未跟踪文件，记录其路径和 hash，不把“未同步”误当科学结果。
4. source snapshot 是否能包含实际 dirty/new implementation 文件，且 prepare 能引用正确的
   design revision、source path 和 review ledger。
5. 运行 `bash -n`、Python compile 和 `tests/paper1_broadening` 离线测试；测试失败只报告或做
   最小契约修复，不删测试、不放宽断言。使用项目内 `--basetemp "$TMPDIR/..."`。

## 4. 修复准则

如果第 3 节发现 public revision 被错误拒绝，提出只增加该 revision 等价字段校验并保留旧
revision 兼容性的补丁；如果配置路径错误，提出只在临时 config 中替换 public source/ledger
路径的补丁。不要在本会话直接应用补丁或运行依赖修改后的 prepare。对建议补丁运行可行的
静态检查/测试，保存 diff 和结果。若无法证明服务器 ledger 与代码 schema 一致，报告
`BLOCKED_REVIEW_SCHEMA_MISMATCH`，停止后续动作。

## 5. 报告

保存：

`writing/broadening design/report/paper1_implementation_contract_audit_report.md`

报告包含 branch/HEAD/dirty、文件存在性、代码/配置差异、实际命令/PID/log/exit、测试结果、
最小修复 diff（如有）、剩余阻塞和明确的 `FORMAL_EXPERIMENTS_NOT_RUN`。报告完成后停止。
