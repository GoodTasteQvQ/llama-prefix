# JBB Behavior Frames v1: Provenance and License Notice

Status: `design_selected`. `formal_experiment_run=false`. This package is not a freeze, binding,
promotion, execution authorization, `RUN-READY`, or `PAPER-RUN-READY` declaration.

## Source provenance

- Official dataset: `JailbreakBench/JBB-Behaviors`
- Official benchmark code: `JailbreakBench/jailbreakbench`
- Immutable dataset revision: `886acc352a31533ffbcf4ef22c744658688086fc`
- Dataset selector: config `behaviors`, split `harmful`
- Source path: `data/harmful-behaviors.csv`
- Source file Git OID: `5a7549cd9de9bb327914de0800606a1af1ec8849`
- Official CSV: 23,116 bytes, SHA-256 `4a8ec6832056b631eb092dccc60d37a61c3d441268268888b3d006288afeffa1`
- Local JSON transform: 34,556 bytes, SHA-256 `9ee1cb2aab52550f0817f036e4423e9f3cc05a6bb5a0084da404f1817d535e77`
- Format-independent 100-record frame SHA-256: `ffd1760322b378c27496ea8f188b5b1e0fa463b2e3f0b6c6b90db24ec9358a0e`
- Identity relation: all 100 records and all six source fields match the pinned official CSV in
  source order with zero mismatches. The raw bytes differ because the local copy is JSON with CRLF
  while the official source is CSV with LF.

The selected runtime artifacts retain the source `Goal` as `prompt`. The source `Target` is excluded
from selection, ranking, matching, selected runtime JSON, and runtime input. Source record-identity
digests bind the complete original record only for provenance and misread detection.

## License and redistribution

The pinned dataset declares the MIT License, copyright (c) 2023 JailbreakBench Team. Redistribution is
permitted, including use, copying, modification, merging, publishing, sublicensing, and sale, provided
the copyright notice and permission notice are included in all copies or substantial portions. The work
is provided without warranty. The official dataset card separately requests citation of JailbreakBench
and consideration of the constituent AdvBench and TDC/HarmBench sources; that citation request is
distinct from the MIT redistribution condition. Source labels are retained in every selected record.

## MIT License

Copyright (c) 2023 JailbreakBench Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
