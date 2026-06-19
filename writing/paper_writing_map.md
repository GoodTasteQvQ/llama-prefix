# 论文写作映射总表

这份文档把两篇论文的章节、图表和实验结果做统一映射，目的是避免后续“实验做了很多，但写作时不知道放哪里”。

## Paper 1

主文档：

- [paper1_writing_blueprint.md](/D:/llama_prefix/paper1_writing_blueprint.md)

最核心问题：

- 公开 Rogue v1 在 `use_cache=True` 下是否真的在 generation phase 稳定生效？
- decode-time steering 是否会引发 collapse？
- 为什么 `ASR` 单指标不够？

最关键实验：

1. phase matrix A-F
2. 三模型关键对照
3. decode collapse 诊断
4. attention sink / structural token 分析
5. beyond-ASR summary

## Paper 2

主文档：

- [paper2_writing_blueprint.md](/D:/llama_prefix/paper2_writing_blueprint.md)

最核心问题：

- 既然 steering 的阶段语义决定结论，为什么防御必须 phase-aware？
- 为什么动态干预优于静态全程插入？
- dynamic defense 是否真的带来更好的 safety-utility-collapse trade-off？

最关键实验：

1. safety vector 层扫描
2. projection vs cosine vs norm 消融
3. harmful + harmless 双评估
4. static vs dynamic defense 主结果
5. first-k / decay / threshold / layer 消融

## 推荐写作顺序

1. 先按 [paper1_writing_blueprint.md](/D:/llama_prefix/paper1_writing_blueprint.md) 整理 Paper 1
2. Paper 1 的图表编号和主结论稳定后，再开始 Paper 2
3. Paper 2 只复用 Paper 1 的必要背景，不重复大段机制审计
4. 所有实验结果文件都尽量按“能直接映射到章节”的方式归档

## 最实用的落地原则

- 每做完一组实验，就立刻标记它属于 Paper 1 还是 Paper 2
- 每张图都提前决定“放主文还是补充材料”
- 每个表都只回答一个问题，不要混合机制审计和防御主结果
