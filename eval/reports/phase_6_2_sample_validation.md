# Phase 6.2 Sample Validation

The full 263-row refresh was intentionally stopped to control local inference time.
These figures must not replace the full-dataset Phase 6 accuracy report.

## Observed stratified LLM sample

| Type | Correct | Accuracy |
|---|---:|---:|
| Compliance | 1/2 | 50.00% |
| Damage | 2/2 | 100.00% |
| Pricing | 2/2 | 100.00% |
| Promotional | 2/2 | 100.00% |
| Shortage | 2/2 | 100.00% |
| **Overall** | **9/10** | **90.00%** |

## Full-label evidence-policy check (no LLM inference)

| Type | Correct | Policy accuracy |
|---|---:|---:|
| Compliance | 26/37 | 70.27% |
| Damage | 27/27 | 100.00% |
| Pricing | 39/39 | 100.00% |
| Promotional | 79/79 | 100.00% |
| Shortage | 81/81 | 100.00% |
| **Overall** | **252/263** | **95.82%** |

The 11 compliance policy disagreements are caused by ground-truth rows that use
an unstored three-day allowance while production-visible logic uses one day.
