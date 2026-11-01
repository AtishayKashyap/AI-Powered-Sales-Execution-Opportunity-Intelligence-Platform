"""Request and response models (also the OpenAPI documentation)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import ActionType, OpportunityType, OutcomeType

Status = Literal["open", "in_progress", "resolved", "closed"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RepOut(ORM):
    rep_id: str
    rep_name: str
    territory: str


class OutletOut(ORM):
    outlet_id: str
    outlet_name: str
    outlet_type: str
    tier: str
    city: str
    territory: str
    baseline_monthly_revenue: float
    rep: RepOut


class OutcomeOut(ORM):
    outcome: OutcomeType
    note: str | None
    recorded_at: datetime


class ActionOut(ORM):
    action_id: int
    rep_id: str
    action_type: ActionType
    note: str | None
    created_at: datetime
    outcome: OutcomeOut | None


class OpportunitySummary(ORM):
    opportunity_id: str
    opportunity_type: OpportunityType
    priority_score: float
    priority_band: str
    severity: float
    value_at_stake: float
    queue_rank: int | None
    recommended_action: str
    outlet: OutletOut
    status: Status


class OpportunityDetail(OpportunitySummary):
    evidence: dict[str, object]
    as_of: date
    actions: list[ActionOut]


class OpportunityPage(BaseModel):
    items: list[OpportunitySummary]
    total: int
    limit: int
    offset: int


class ActionIn(BaseModel):
    action_type: ActionType
    note: str | None = Field(default=None, max_length=1000)


class OutcomeIn(BaseModel):
    outcome: OutcomeType
    note: str | None = Field(default=None, max_length=1000)


class TypeStats(BaseModel):
    opportunity_type: str
    opportunities: int
    actioned: int
    resolved: int
    resolution_rate: float | None
    value_at_stake: float


class RepStats(BaseModel):
    rep_id: str
    rep_name: str
    actions: int
    resolved: int


class AnalyticsSummary(BaseModel):
    as_of: date | None
    opportunities: int
    queue_size: int
    value_at_stake: float
    actioned: int
    resolved: int
    resolution_rate: float | None
    by_type: list[TypeStats]
    by_outcome: dict[str, int]
    top_reps: list[RepStats]


class ExplanationOut(BaseModel):
    summary: str
    why_it_matters: str
    recommended_action: str
    evidence_used: list[str]
    source: Literal["llm", "rule_based"]
    model: str | None
    note: str | None
