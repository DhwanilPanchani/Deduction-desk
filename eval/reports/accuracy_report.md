# DeductionDesk Accuracy Report

`invalid` is the positive class. A human verdict supersedes the agent verdict when present.

## Overall

| N | Accuracy | Invalid precision | Invalid recall | Invalid F1 | Human-reviewed |
|---:|---:|---:|---:|---:|---:|
| 750 | 98.27% | 97.65% | 99.28% | 98.46% | 1 |

## By deduction type

| Type | N | Accuracy | Invalid precision | Invalid recall | Invalid F1 | True invalid | Predicted invalid |
|---|---:|---:|---:|---:|---:|---:|---:|
| compliance | 113 | 97.35% | 100.00% | 91.18% | 95.38% | 34 | 31 |
| damage | 53 | 100.00% | 100.00% | 100.00% | 100.00% | 30 | 30 |
| pricing | 113 | 98.23% | 96.97% | 100.00% | 98.46% | 64 | 66 |
| promotional | 220 | 98.64% | 97.90% | 100.00% | 98.94% | 140 | 143 |
| shortage | 251 | 98.01% | 96.77% | 100.00% | 98.36% | 150 | 155 |

## By decision method

| Method | N | Accuracy | Invalid precision | Invalid recall | Invalid F1 | True invalid | Predicted invalid |
|---|---:|---:|---:|---:|---:|---:|---:|
| llm | 263 | 95.06% | 93.24% | 97.87% | 95.50% | 141 | 148 |
| rules | 487 | 100.00% | 100.00% | 100.00% | 100.00% | 277 | 277 |
