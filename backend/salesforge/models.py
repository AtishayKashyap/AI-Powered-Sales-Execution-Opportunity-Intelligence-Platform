"""Database schema. Migrations live in migrations/ (Alembic)."""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


class OpportunityType(enum.StrEnum):
    revenue_recovery = "Revenue Recovery"
    inactive_outlet = "Inactive Outlet"
    stock_risk = "Stock Risk"
    cross_sell = "Cross-Sell"


class ActionType(enum.StrEnum):
    visit = "visit"
    call = "call"


class OutcomeType(enum.StrEnum):
    resolved = "resolved"
    follow_up = "follow_up"
    no_response = "no_response"
    not_viable = "not_viable"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    return Enum(e, name=name, values_callable=lambda members: [m.value for m in members])


class Rep(Base):
    __tablename__ = "reps"

    rep_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    rep_name: Mapped[str] = mapped_column(String(100))
    territory: Mapped[str] = mapped_column(String(50))


class Outlet(Base):
    __tablename__ = "outlets"

    outlet_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    outlet_name: Mapped[str] = mapped_column(String(120))
    outlet_type: Mapped[str] = mapped_column(String(40))
    tier: Mapped[str] = mapped_column(String(1))
    city: Mapped[str] = mapped_column(String(60))
    territory: Mapped[str] = mapped_column(String(50))
    rep_id: Mapped[str] = mapped_column(ForeignKey("reps.rep_id"), index=True)
    baseline_monthly_revenue: Mapped[float] = mapped_column(Float)
    days_since_last_order: Mapped[int] = mapped_column(Integer)

    rep: Mapped[Rep] = relationship(lazy="joined")


class Opportunity(Base):
    __tablename__ = "opportunities"

    opportunity_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    outlet_id: Mapped[str] = mapped_column(ForeignKey("outlets.outlet_id"), index=True)
    opportunity_type: Mapped[OpportunityType] = mapped_column(_enum(OpportunityType, "opportunity_type"))
    severity: Mapped[float] = mapped_column(Float)
    value_at_stake: Mapped[float] = mapped_column(Float)
    priority_score: Mapped[float] = mapped_column(Float)
    priority_band: Mapped[str] = mapped_column(String(2))
    queue_rank: Mapped[int | None] = mapped_column(Integer, unique=True)
    evidence: Mapped[dict[str, object]] = mapped_column(JsonType)
    recommended_action: Mapped[str] = mapped_column(Text)
    as_of: Mapped[date] = mapped_column(Date)

    outlet: Mapped[Outlet] = relationship(lazy="joined")
    actions: Mapped[list[Action]] = relationship(
        back_populates="opportunity", order_by="Action.created_at", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_opportunities_type_priority", "opportunity_type", "priority_score"),
        Index("ix_opportunities_priority", "priority_score"),
    )


class Action(Base):
    __tablename__ = "actions"

    action_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.opportunity_id", ondelete="CASCADE"))
    rep_id: Mapped[str] = mapped_column(ForeignKey("reps.rep_id"))
    action_type: Mapped[ActionType] = mapped_column(_enum(ActionType, "action_type"))
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    opportunity: Mapped[Opportunity] = relationship(back_populates="actions")
    outcome: Mapped[Outcome | None] = relationship(
        back_populates="action", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (Index("ix_actions_opportunity_created", "opportunity_id", "created_at"),)


class Outcome(Base):
    """One outcome per action; recording again replaces it, so analytics never double-count."""

    __tablename__ = "outcomes"

    action_id: Mapped[int] = mapped_column(ForeignKey("actions.action_id", ondelete="CASCADE"), primary_key=True)
    outcome: Mapped[OutcomeType] = mapped_column(_enum(OutcomeType, "outcome_type"))
    note: Mapped[str | None] = mapped_column(String(1000))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    action: Mapped[Action] = relationship(back_populates="outcome")


class Explanation(Base):
    """Cached LLM explanation that passed grounding validation. Rule-based ones are computed, not stored."""

    __tablename__ = "explanations"

    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("opportunities.opportunity_id", ondelete="CASCADE"), primary_key=True
    )
    summary: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    evidence_used: Mapped[list[str]] = mapped_column(JsonType)
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
