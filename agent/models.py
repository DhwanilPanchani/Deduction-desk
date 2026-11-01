"""Typed data contracts used throughout the agent pipeline."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Deduction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    retailer: str
    type: Literal["shortage", "pricing", "promotional", "compliance", "damage"]
    claimed_amount: Decimal
    status: Literal["pending", "disputed", "accepted"]
    retailer_notes: str | None = None
    invoice_id: int


class AgentDecision(BaseModel):
    deduction_id: int
    is_valid: bool
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    method: Literal["rules", "llm", "escalated"]
    needs_human_review: bool


class RuleResult(BaseModel):
    resolved: bool
    is_valid: bool | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    reasoning: str
    context: dict[str, Any] = Field(default_factory=dict)


class LLMResult(BaseModel):
    resolved: bool
    is_valid: bool | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    reasoning: str
    agreement_rate: float = Field(default=0, ge=0, le=1)
    votes: list[bool] = Field(default_factory=list)
    raw_responses: list[str] = Field(default_factory=list)
    error: str | None = None
