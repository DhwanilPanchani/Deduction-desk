# DeductionDesk Accuracy Report

`invalid` is the positive class. A human verdict supersedes the agent verdict when present.

## Overall

| N | Accuracy | Invalid precision | Invalid recall | Invalid F1 | Human-reviewed |
|---:|---:|---:|---:|---:|---:|
| 750 | 90.93% | 87.72% | 97.37% | 92.29% | 1 |

## By deduction type

| Type | N | Accuracy | Invalid precision | Invalid recall | Invalid F1 | True invalid | Predicted invalid |
|---|---:|---:|---:|---:|---:|---:|---:|
| compliance | 113 | 90.27% | 100.00% | 67.65% | 80.70% | 34 | 23 |
| damage | 53 | 88.68% | 83.33% | 100.00% | 90.91% | 30 | 36 |
| pricing | 113 | 88.50% | 83.12% | 100.00% | 90.78% | 64 | 77 |
| promotional | 220 | 90.91% | 87.50% | 100.00% | 93.33% | 140 | 160 |
| shortage | 251 | 92.83% | 89.29% | 100.00% | 94.34% | 150 | 168 |

## By decision method

| Method | N | Accuracy | Invalid precision | Invalid recall | Invalid F1 | True invalid | Predicted invalid |
|---|---:|---:|---:|---:|---:|---:|---:|
| llm | 263 | 74.14% | 69.52% | 92.20% | 79.27% | 141 | 187 |
| rules | 487 | 100.00% | 100.00% | 100.00% | 100.00% | 277 | 277 |
