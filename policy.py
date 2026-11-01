"""Policy constants shared by ground-truth generation and the classification agent.

Both sides of the system must agree on these values: the generator uses them to
derive ground_truth.is_valid, and the agent's rules_engine/llm_classifier use them
to build the evidence the agent reasons over. A mismatch here means the agent is
being graded against a policy it was never shown.
"""

from __future__ import annotations

# Days of delivery lateness tolerated before a compliance (OTIF) deduction is
# considered valid. Matches the strict 1-day on-time window used by most big-box
# retailer OTIF programs (e.g. Walmart, Target) -- a 3-day grace period is unusually
# lenient and was never the policy shown to the agent.
COMPLIANCE_LATE_ALLOWANCE_DAYS = 1
