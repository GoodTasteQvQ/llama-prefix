# Paper 1 Stage 3 Archive

归档日期：2026-07-22

本目录保存不再参与 Stage 3 实现的历史材料。当前唯一实现入口是：

`writing/stage3 design/CURRENT_RELEASE.md`

## 物理归档

以下未被当前冻结 verifier 按原路径绑定的文件已移动到本目录：

- `legacy_root/paper1_attention_sink_mu_experiment_design_v3_3_2.md`
- `legacy_root/paper1_tdsc_readiness_audit.md`
- `unbound_revision/paper1_attention_sink_mu_v3_5_rc2_binding_amendment_01_repair_handoff.md`
- `unbound_revision/paper1_attention_sink_mu_design_freeze_binding_amendment_01_partial_witness_final_audit.md`

这些文件只用于历史追溯，不是实现规范。

`pre_cleanup_snapshots/` 保存本次整理前的 `paper1_writing_blueprint.md` 和
`paper1_claim_evidence_matrix.md`，用于在需要时恢复本次引用更新。

## 原路径固定的逻辑归档

下列旧材料没有移动，因为
`writing/stage3 design/v3_5_rc2_contracts/preexisting_files.sha256.json`
和 `scripts/stage3_rc2/verify_release.py` 将其原路径、长度和 SHA256 作为基础 rc2 的冻结证据：

- `writing/judge subagent/` 全部六份裁决文件
- `writing/stage3 design/` 中 v1.0 至 v3.5-rc1 的旧协议
- `writing/stage3 design/revision/` 中早期 revision brief、semantic diff、scope-removal 和资源评估
- `paper1_attention_sink_mu_design_freeze_audit_v3_5_rc1_summary.md`
- `p0_closure_register.md`

它们属于“逻辑归档”：必须保持原字节和原路径，但后续编码任务不得读取。
直接移动、重命名或修改这些文件会使基础 release verifier 失败，并破坏 amendment 保存的基础快照。

## 当前冻结链中仍需原位保留的审计/修复记录

以下文件虽然不是日常编码需求，仍被 amendment verifier、release manifest 或修复依赖直接绑定：

- `paper1_attention_sink_mu_design_freeze_closure_audit_v3_5_rc2.md`
- `paper1_attention_sink_mu_design_freeze_binding_amendment_01_final_closure_audit.md`
- `paper1_attention_sink_mu_experiment_design_v3_5_rc1_to_v3_5_rc2_semantic_diff.md`
- `paper1_attention_sink_mu_v3_5_rc2_binding_amendment_01_repair_completion.md`
- `paper1_attention_sink_mu_v3_5_rc2_binding_amendment_01_partial_witness_repair_completion.md`

这些文件不得移动或编辑。其存在是 provenance/closure 证据，不会提高其相对于协议、schema、manifest
或 reference implementation 的规范优先级。

## 恢复映射

需要恢复物理归档文件时，按目录名反向移动即可：

- `legacy_root/*` -> `writing/`
- `unbound_revision/*` -> `writing/stage3 design/revision/`

归档操作没有删除文件，也没有修改任何 frozen artifact。
