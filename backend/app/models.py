"""Application database models."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Opportunity(Base):
    __tablename__ = "opportunities"

    opportunity_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    outlet_id: Mapped[str] = mapped_column(String(100), index=True)
    opportunity_type: Mapped[str] = mapped_column(String(80), index=True)
    score: Mapped[float] = mapped_column(Float)
    priority: Mapped[str | None] = mapped_column(String(10), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    queue_rank = Column(Integer, nullable=True)
    actions: Mapped[list["OpportunityAction"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class OpportunityAction(Base):
    __tablename__ = "opportunity_actions"

    action_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("opportunities.opportunity_id"), index=True
    )
    outlet_id: Mapped[str] = mapped_column(String(100), index=True)
    action_type: Mapped[str] = mapped_column(String(50))
    rep_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    opportunity: Mapped[Opportunity] = relationship(back_populates="actions")
    outcomes: Mapped[list["OpportunityOutcome"]] = relationship(
        back_populates="action", cascade="all, delete-orphan"
    )


class OpportunityOutcome(Base):
    __tablename__ = "opportunity_outcomes"

    outcome_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_id: Mapped[int] = mapped_column(
        ForeignKey("opportunity_actions.action_id"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    action: Mapped[OpportunityAction] = relationship(back_populates="outcomes")


class AIExplanation(Base):
    __tablename__ = "ai_explanations"

    explanation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("opportunities.opportunity_id"), index=True
    )
    summary: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    evidence_used: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(50), default="unknown")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
