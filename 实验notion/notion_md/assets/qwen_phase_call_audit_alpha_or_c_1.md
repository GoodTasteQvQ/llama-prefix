# Qwen phase-call audit table (representative strength alpha/c=1.0)

## trackA

| method | phase_mode | use_cache | prefill attack | decode cached/run | decode full/run | generated steered/run | mean decode mask | max decode mask |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `rogue_v1` | `rogue_v1_cache_semantics` | True | True | 124.2 | 0.0 | 0.0 | 0.00 | 0.0 |
| `no_cache` | `prefill_and_decode` | False | True | 0.0 | 125.2 | 125.2 | 96.30 | 172.0 |
| `decode_only` | `decode_only` | True | False | 124.4 | 0.0 | 124.4 | 1.00 | 1.0 |
| `first_k` | `first_k_decode` | True | False | 124.7 | 0.0 | 3.0 | 1.00 | 1.0 |
| `decay` | `decode_only` | True | False | 125.0 | 0.0 | 125.0 | 1.00 | 1.0 |
| `full` | `prefill_and_decode` | True | True | 122.7 | 0.0 | 122.7 | 1.00 | 1.0 |

## trackB

| method | phase_mode | use_cache | prefill attack | decode cached/run | decode full/run | generated steered/run | mean decode mask | max decode mask |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `rogue_v1` | `rogue_v1_cache_semantics` | True | True | 70.8 | 0.0 | 0.0 | 0.00 | 0.0 |
| `no_cache` | `prefill_and_decode` | False | True | 0.0 | 154.2 | 154.2 | 181.82 | 544.0 |
| `decode_only` | `decode_only` | True | False | 189.0 | 0.0 | 189.0 | 1.00 | 1.0 |
| `first_k` | `first_k_decode` | True | False | 95.1 | 0.0 | 3.0 | 1.00 | 1.0 |
| `decay` | `decode_only` | True | False | 91.5 | 0.0 | 91.5 | 1.00 | 1.0 |
| `full` | `prefill_and_decode` | True | True | 159.4 | 0.0 | 159.4 | 1.00 | 1.0 |
