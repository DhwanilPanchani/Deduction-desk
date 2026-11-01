"""Convert rule and language-model results into a final agent decision."""

from __future__ import annotations

from .config import Settings, settings
from .models import AgentDecision, Deduction, LLMResult, RuleResult


def build_decision(
    deduction: Deduction,
    rule_result: RuleResult,
    llm_result: LLMResult | None = None,
    config: Settings = settings,
) -> AgentDecision:
    if rule_result.resolved and rule_result.is_valid is not None:
        confidence = max(0.95, rule_result.confidence)
        return AgentDecision(
            deduction_id=deduction.id,
            is_valid=rule_result.is_valid,
            confidence=confidence,
            reasoning=rule_result.reasoning,
            method="rules",
            needs_human_review=confidence < config.confidence_threshold,
        )

    if llm_result and llm_result.resolved and llm_result.is_valid is not None:
        confidence = min(0.85, llm_result.agreement_rate)
        return AgentDecision(
            deduction_id=deduction.id,
            is_valid=llm_result.is_valid,
            confidence=confidence,
            reasoning=llm_result.reasoning,
            method="llm",
            needs_human_review=(
                llm_result.agreement_rate < 1
                or confidence < config.confidence_threshold
            ),
        )

    reasoning = (
        llm_result.reasoning
        if llm_result
        else "No deterministic or language-model decision was available."
    )
    return AgentDecision(
        deduction_id=deduction.id,
        is_valid=False,
        confidence=0,
        reasoning=reasoning,
        method="escalated",
        needs_human_review=True,
    )
