# LLM Error Analysis

LLM decisions: **263**  
Wrong final verdicts: **116** (44.11%)

## Error rate by deduction type

| Deduction type | LLM decisions | Wrong | Error rate |
|---|---:|---:|---:|
| compliance | 37 | 23 | 62.16% |
| damage | 27 | 9 | 33.33% |
| pricing | 39 | 19 | 48.72% |
| promotional | 79 | 33 | 41.77% |
| shortage | 81 | 32 | 39.51% |

## Note-style routing and LLM error rate

| Note style | All decisions | Routed to LLM | Wrong LLM verdicts | LLM error rate |
|---|---:|---:|---:|---:|
| clean/structured | 244 | 0 | 0 | n/a |
| email-style | 263 | 263 | 116 | 44.11% |
| sparse-ambiguous | 243 | 0 | 0 | n/a |

The generator produced all three styles. In this pipeline run, rules resolved every structured and sparse note, so only email-style notes reached the LLM.

## Most common failure pattern

**false dispute (invalid) on promotional deductions with email-style notes** — 33 of 116 wrong verdicts (28.45%).

This label describes the dominant observed type/style/direction combination; it does not infer an unstored model rationale.

## Concrete wrong-verdict examples

### 1. Deduction 1 — promotional / email-style

- Confidence: 85.00%
- Final verdict: invalid/dispute; ground truth: valid
- Retailer notes: Hi team, we took a promotional deduction on PO-2512-000146. Can you review and clear this against the remittance? Thanks.
- Agent reasoning: Claim matches promo but matching_authorized_promotion is not provided in internal facts
- Ground-truth reason: Authorized promotion Work Sparkling Lemon 8-pack Event 95 covers invoice date and SKU.

### 2. Deduction 3 — compliance / email-style

- Confidence: 85.00%
- Final verdict: valid/accept; ground truth: invalid
- Retailer notes: Hi team, we took a compliance deduction on PO-2604-000398. Can you review and clear this against the remittance? Thanks.
- Agent reasoning: days_late (2) exceeds configured_delivery_allowance_days (1)
- Ground-truth reason: Delivery timing (2 days) is within the 3-day allowance.

### 3. Deduction 4 — shortage / email-style

- Confidence: 85.00%
- Final verdict: invalid/dispute; ground truth: valid
- Retailer notes: Hi team, we took a shortage deduction on PO-2511-000348. Can you review and clear this against the remittance? Thanks.
- Agent reasoning: Claimed shortage (2) does not match actual shortage (2)
- Ground-truth reason: POD confirms 2 units short.

### 4. Deduction 27 — shortage / email-style

- Confidence: 85.00%
- Final verdict: invalid/dispute; ground truth: valid
- Retailer notes: Hi team, we took a shortage deduction on PO-2606-000155. Can you review and clear this against the remittance? Thanks.
- Agent reasoning: Claimed short quantity (10) does not match actual short quantity (10).
- Ground-truth reason: POD confirms 10 units short.

### 5. Deduction 39 — compliance / email-style

- Confidence: 85.00%
- Final verdict: valid/accept; ground truth: invalid
- Retailer notes: Hi team, we took a compliance deduction on PO-2606-000347. Can you review and clear this against the remittance? Thanks.
- Agent reasoning: days_late (2) exceeds configured_delivery_allowance_days (1), following the decision policy.
- Ground-truth reason: Delivery timing (2 days) is within the 3-day allowance.
