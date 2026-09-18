# Core Judge protocol v3 direct-JSON compatibility probe

执行会话：`A-judge-v3`
协议：`core-judge-protocol-v3-direct-json`
本任务只执行 direct-JSON probe；不执行 recovery、全量重评分或正式实验。

## 前置事实

v2 的 4096 thinking probe 已失败。第二条固定输入耗尽 4,096 token，没有
semantic `</think>`，并重复拒答文本约 470 次。该结果已经记录为
`JUDGE_PROTOCOL_PROBE_FAIL` / `DESIGN_CHANGE_REQUIRED`，属于历史非正式
probe，不能重新解释或并入新结果。禁止把 v2 的 `max_new_tokens` 提高到
8192 或更高。

Phase 0 已完成 direct-JSON 离线适配，报告状态为
`DIRECT_JSON_IMPLEMENTATION_OFFLINE_PASS` / `READY_FOR_DIRECT_JSON_PROBE_APPROVAL`。
服务器 Phase 0 已验证的代码哈希为：

| 文件 | SHA256 |
|---|---|
| `paper1_broadening/judge.py` | `76886c259a89102c6fbfeee86f8e94d00d0f20f5277fb1f391b77307c710b71f` |
| `paper1_broadening/config.py` | `f55fc81d073d45395e1b8a56cfa81c0dcdab7ad501e2955f1e739d2671e2c950` |
| `paper1_broadening/pipeline.py` | `5e1c2397efecfa42780c524b76bdd552544d9f14e01772cb68004a2738493954` |
| `paper1_broadening/smoke.py` | `5f2d674346d76d8cf1bb27112446bb2b54434952e7c4a367f7f6ccf79d5c3e4e` |
| `tests/paper1_broadening/test_judge_direct_json_protocol.py` | `ce3b90597cb55323b8ccbf377f32b56429015f324fe077837a73cfa9ce6c40c6` |

## 不可违反的边界

1. 先验证固定路径 `.codex-temp/paper1_core_judge_protocol_v3/DIRECT_JSON_PROBE_APPROVAL.md` 存在、状态为 `DIRECT_JSON_PROBE_APPROVED`，并记录批准文件 SHA256。批准文件不完整或哈希不匹配时，不加载模型、不发送请求。
2. 服务器代码哈希必须与上表完全一致。任一不一致时写 `DIRECT_JSON_PROBE_CODE_HASH_MISMATCH` 并停止。
3. 旧 v2.1 设计、旧 F2、旧 recovery、旧 Judge ledger、旧 dose decisions、v2 probe、canonical config、方向、safe-pair 数据和全部 behavior completion 只读。不得覆盖、合并、删除、重命名或回写。
4. 只改变 Judge 输出协议：`enable_thinking=false`、`max_new_tokens=512`、`strict_direct_json_v1`。不得改变模型、endpoint、tokenizer/chat template、dtype、greedy/beam、rubric、label domain、behavior decoder、generation retry 规则或 2% missing gate。
5. direct JSON 必须是去除首尾空白后的完整 JSON 对象，恰好包含 `label` 和 `rationale` 两个键。拒绝 Markdown、额外文本、额外/缺失键、非法 label、空 rationale、`<think>` 或 `</think>`。禁止 regex 修复、substring 提取、手工标签、completion-derived label 和旧 parser fallback。
6. 每条最多一次 four-class Judge 请求；binary Judge、generation retry、additional Judge retry 均为 0。首条失败后立即停止，不发送后续条目。
7. 不执行 v2.3 设计创建、recovery、1,200 条 full rescore、A/S 选择、formal evaluation、E1/E2/E3、analysis 或 human review。probe 通过后只报告 `READY_FOR_V2.3_DESIGN_REVIEW`，等待负责人下一次批准。
8. 不 commit/push，不清理其他会话或用户的工作树修改。

## Linux、离线和 nohup

```bash
cd /data/goodtaste_workspace/llama-prefix || exit 1
mkdir -p .codex-temp/paper1_core_judge_protocol_v3/phase1 logs/paper1_broadening results/paper1_broadening
export TMPDIR="$PWD/.codex-temp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export PYTHONUNBUFFERED=1
export PYTHONPYCACHEPREFIX="$TMPDIR/pycache"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES=0
MBD_PYTHON=/data/goodtaste_workspace/envs/llama-prefix/bin/python
test -x "$MBD_PYTHON" || exit 1
```

所有 preflight、probe、审计和检查都使用 `nohup`，保存 PID、日志和 `.exit`。
启动模型前确认选定 GPU 空闲且显存足够；模型和 Judge 顺序加载，完成后释放。

## Probe 输入与请求

所有输入必须只读自：
`results/paper1_broadening/core-directions-calibration-20260915T140731Z-1382603/`。
必须使用批准文件列出的 6 个 `response_id`、身份字段和 64 字符
`request_sha256`，不得替换或按结果重新选择：

- `response-ca3528d9552b3203b3a0d34564f9f92ff6125a1a1ae534f1ea7e79f1a619135a`，request hash `5a89190c479eff7dba9b42aaef1ee3d6c17f2794c4e8061a5886c780d7a32b5d`
- `response-122c80122328a689cc58e19ec44de6344d4ed5df4cff6810030874496afb9ce4`，request hash `c68976bb9eae3fab6ed1d6a1d168b936b2c86c92d7c6ff35191f4661f296116f`
- `response-a790919720fb4c57eb7930924e0ec173ff1cf03c9aa7a3616c9bb5967e5c7c64`，request hash `b1ec849d32ba717251d5fe70464503fc1a3473548d18c7402b5901a40ba92218`
- `response-eff883ac2874e097b0309f008d78079f9ddfead6881540faf4c43a65d9bfdc33`，request hash `8150adaeefadcdb8f07c1aa1ded10a7eebc2bb1b40df2b2d6ffe0f0a27546c08`
- `response-50acbb7ed5f494b9a431981f7ff603414f4e2ac3f24aa7627b015eac835233d5`，request hash `342036f7951ea28cba7792291fb5569e1ff7666d54dfa0417783f4c6cb6ed116`
- `response-75c90e4a40a1fc1beec3150104ef12df2b854d1fd0fb142bae7b3a1f9d8d6f4e`，request hash `e00df94b1ea281da64a1a541de14bfceb39b24e6f19133855c80b56aa38cb766`

创建独立目录：
`results/paper1_broadening/core-judge-protocol-v3-direct-json-probe-<UTC>-<shortid>/`。
先保存输入、prompt/request hash、批准文件 hash、代码 hash、run config 和
pre-request validation，再发送请求。每条请求必须记录 raw、diagnostics、
strict parse result、stop reason、token counts、response hash、runtime/release
identity 和 call counts。保存完整 artifact hash manifest。

## 通过条件与停止

只有 6/6 条均具备完整 direct JSON、合法 label、非空 rationale、无 thinking
marker/额外文本、完整 raw/diagnostic/hash/stop/token 证据时，才记录
`DIRECT_JSON_PROBE_PASS` 和 `READY_FOR_V2.3_DESIGN_REVIEW`。

任一条失败、缺证据、OOM、身份不一致、隐藏 retry 或 parser 放宽时，记录
`DIRECT_JSON_PROBE_FAIL` 和 `DESIGN_CHANGE_REQUIRED`，立即停止，不提高 token，
不切回 thinking 模式，不补发剩余请求。

最终报告保存至：
`writing/broadening design/report/paper1_core_judge_protocol_v3_direct_json_report.md`。
报告必须列出实际 request/retry 计数、run 路径、PID/log/.exit、代码/批准文件
哈希、旧文件保护哈希和最终边界审计。无论 probe 成功或失败，都写
`CORE_RECOVERY_V3_NOT_RUN`、`CORE_SCREEN_V3_NOT_RUN`、`FORMAL_EVALUATION_NOT_RUN`
和 `OLD_F2_AND_OLD_RECOVERY_IMMUTABLE`。
