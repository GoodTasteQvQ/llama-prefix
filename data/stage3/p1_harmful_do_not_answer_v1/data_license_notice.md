# Data license notice

This candidate-only prompt subset is derived from **Do-Not-Answer: A Dataset for Evaluating Safeguards in LLMs** by Yuxia Wang, Haonan Li, Xudong Han, Preslav Nakov, and Timothy Baldwin (2024).

- Repository: `Libr-AI/do-not-answer`
- Fixed revision: `460703484df354958a5e1cd7378a38fcb94a2f3e`
- Source path: `datasets/Instruction/do_not_answer_en.csv`
- Dataset license: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (`CC-BY-NC-SA-4.0`)
- License text: https://creativecommons.org/licenses/by-nc-sa/4.0/

The pinned repository README states that all datasets in the repository use this data license. The root Apache-2.0 license applies to source files and is not used to relicense the dataset.

Modification notice: this package selects a deterministic 100-record subset, preserves exact question text, adds identity hashes and taxonomy metadata, excludes specified duplicate/leakage risks, and reorders records by the documented deterministic frame-order rule. It is a nonformal candidate binding package. Redistribution or adaptation must preserve attribution, NonCommercial restrictions, and ShareAlike obligations. This notice is not legal advice.
