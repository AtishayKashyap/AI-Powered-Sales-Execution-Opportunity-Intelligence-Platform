"""
SalesForge FastAPI backend.

Database-backed API for the SalesForge sales execution copilot.

Architecture:
    React â†’ FastAPI â†’ PostgreSQL

The deterministic V5 pipeline remains responsible for generating and
prioritizing opportunities. PostgreSQL is the live application store for
opportunities, sales-rep actions, outcomes, and AI explanations.
"""

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.app.routes_ai import router as ai_router
from backend.app.routes_feedback import router as feedback_router

from .db import get_db
from .models import (
    Opportunity,
    OpportunityAction,
    OpportunityOutcome,
)


app = FastAPI(
    title="SalesForge API",
    version="5.0.0",
    description="AI-powered CPG sales execution copilot backend.",
)
app.include_router(ai_router)
app.include_router(feedback_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    action_type: str = Field(
        ...,
        description="Action taken by the sales representative.",
    )
    rep_id: str | None = Field(
        default=None,
        description="Sales representative identifier.",
    )
    note: str | None = Field(
        default=None,
        description="Optional field note.",
    )


class OutcomeRequest(BaseModel):
    outcome: str = Field(
        ...,
        description=(
            "Outcome of the action, e.g. contacted, resolved, "
            "snoozed, no_response."
        ),
    )
    note: str | None = None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def serialize_opportunity(opportunity: Opportunity) -> dict:
    return {
        "opportunity_id": opportunity.opportunity_id,
        "outlet_id": opportunity.outlet_id,
        "opportunity_type": opportunity.opportunity_type,
        "score": opportunity.score,
        "priority": opportunity.priority,
        "evidence": opportunity.evidence or {},
        "recommended_action": opportunity.recommended_action,
        "created_at": opportunity.created_at.isoformat()
        if opportunity.created_at
        else None,
    }


def serialize_action(action: OpportunityAction) -> dict:
    return {
        "action_id": action.action_id,
        "opportunity_id": action.opportunity_id,
        "outlet_id": action.outlet_id,
        "action_type": action.action_type,
        "rep_id": action.rep_id,
        "note": action.note,
        "created_at": action.created_at.isoformat()
        if action.created_at
        else None,
    }


def serialize_outcome(outcome: OpportunityOutcome) -> dict:
    return {
        "outcome_id": outcome.outcome_id,
        "action_id": outcome.action_id,
        "outcome": outcome.outcome,
        "note": outcome.note,
        "created_at": outcome.created_at.isoformat()
        if outcome.created_at
        else None,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health(db: Session = Depends(get_db)):
    """
    Health endpoint.

    Also verifies that the API can reach PostgreSQL.
    """
    try:
        db.execute(func.now())
        database = "connected"
    except Exception:
        database = "error"

    return {
        "status": "ok" if database == "connected" else "degraded",
        "service": "salesforge-api",
        "version": "5.0.0",
        "database": database,
    }


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

@app.get("/opportunities")
def opportunities(
    priority: str | None = Query(default=None),
    opportunity_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Return opportunities from PostgreSQL.

    Supports filtering by priority and opportunity type.
    """

    query = db.query(Opportunity)

    if priority:
        query = query.filter(
            func.upper(Opportunity.priority) == priority.upper()
        )

    if opportunity_type:
        query = query.filter(
            func.lower(Opportunity.opportunity_type)
            == opportunity_type.lower()
        )

    rows = (
        query
        .order_by(Opportunity.score.desc())
        .limit(limit)
        .all()
    )

    return {
        "count": len(rows),
        "items": [serialize_opportunity(row) for row in rows],
    }


@app.get("/opportunities/top")
def top_opportunities(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Return the curated SalesForge execution queue.

    queue_rank is populated from the deterministic top-action
    selection pipeline and is the authoritative ordering for
    the field-sales queue.
    """

    rows = (
        db.query(Opportunity)
        .filter(Opportunity.queue_rank.isnot(None))
        .order_by(Opportunity.queue_rank.asc())
        .limit(limit)
        .all()
    )

    return {
        "count": len(rows),
        "items": [serialize_opportunity(row) for row in rows],
    }


@app.get("/opportunities/{opportunity_id}")
def opportunity(
    opportunity_id: str,
    db: Session = Depends(get_db),
):
    """
    Return one opportunity.
    """

    row = db.get(Opportunity, opportunity_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Opportunity not found",
        )

    return serialize_opportunity(row)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@app.post("/opportunities/{opportunity_id}/actions")
def create_action(
    opportunity_id: str,
    request: ActionRequest,
    db: Session = Depends(get_db),
):
    """
    Record an action taken by a sales representative.
    """

    opportunity = db.get(Opportunity, opportunity_id)

    if opportunity is None:
        raise HTTPException(
            status_code=404,
            detail="Opportunity not found",
        )

    action = OpportunityAction(
        opportunity_id=opportunity.opportunity_id,
        outlet_id=opportunity.outlet_id,
        action_type=request.action_type,
        rep_id=request.rep_id,
        note=request.note,
        created_at=datetime.now(timezone.utc),
    )

    db.add(action)
    db.commit()
    db.refresh(action)

    return {
        "status": "created",
        "action": serialize_action(action),
    }


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

@app.post("/opportunities/{opportunity_id}/actions/{action_id}/outcome")
def record_action_outcome(
    opportunity_id: str,
    action_id: int,
    request: OutcomeRequest,
    db: Session = Depends(get_db),
):
    """
    Record the outcome of a specific sales-rep action.
    """

    opportunity = db.get(Opportunity, opportunity_id)

    if opportunity is None:
        raise HTTPException(
            status_code=404,
            detail="Opportunity not found",
        )

    action = db.get(OpportunityAction, action_id)

    if action is None or action.opportunity_id != opportunity_id:
        raise HTTPException(
            status_code=404,
            detail="Action not found for this opportunity",
        )

    outcome = OpportunityOutcome(
        action_id=action.action_id,
        outcome=request.outcome,
        note=request.note,
        created_at=datetime.now(timezone.utc),
    )

    db.add(outcome)
    db.commit()
    db.refresh(outcome)

    return {
        "status": "created",
        "outcome": serialize_outcome(outcome),
    }


@app.post("/opportunities/{opportunity_id}/outcome")
def record_outcome(
    opportunity_id: str,
    request: OutcomeRequest,
    db: Session = Depends(get_db),
):
    """
    Backward-compatible outcome endpoint.

    Creates an action first and then records its outcome.
    """

    opportunity = db.get(Opportunity, opportunity_id)

    if opportunity is None:
        raise HTTPException(
            status_code=404,
            detail="Opportunity not found",
        )

    action = OpportunityAction(
        opportunity_id=opportunity.opportunity_id,
        outlet_id=opportunity.outlet_id,
        action_type="legacy_outcome",
        note=request.note,
        created_at=datetime.now(timezone.utc),
    )

    db.add(action)
    db.flush()

    outcome = OpportunityOutcome(
        action_id=action.action_id,
        outcome=request.outcome,
        note=request.note,
        created_at=datetime.now(timezone.utc),
    )

    db.add(outcome)
    db.commit()

    db.refresh(action)
    db.refresh(outcome)

    return {
        "status": "created",
        "opportunity_id": opportunity_id,
        "action": serialize_action(action),
        "outcome": serialize_outcome(outcome),
    }


# ---------------------------------------------------------------------------
# Execution analytics
# ---------------------------------------------------------------------------

@app.get("/analytics/execution-summary")
def execution_summary(db: Session = Depends(get_db)):
    """
    Return basic sales-execution funnel metrics.
    """

    total_opportunities = db.query(Opportunity).count()
    total_actions = db.query(OpportunityAction).count()
    total_outcomes = db.query(OpportunityOutcome).count()

    contacted = (
        db.query(OpportunityOutcome)
        .filter(
            func.lower(OpportunityOutcome.outcome) == "contacted"
        )
        .count()
    )

    resolved = (
        db.query(OpportunityOutcome)
        .filter(
            func.lower(OpportunityOutcome.outcome) == "resolved"
        )
        .count()
    )

    resolution_rate = (
        resolved / total_outcomes
        if total_outcomes
        else 0.0
    )

    return {
        "total_opportunities": total_opportunities,
        "total_actions": total_actions,
        "total_outcomes": total_outcomes,
        "contacted": contacted,
        "resolved": resolved,
        "resolution_rate": round(resolution_rate, 4),
    }

@app.get("/analytics/execution-breakdown")
def execution_breakdown(db: Session = Depends(get_db)):
    """
    Return execution analytics used by the command-center insight cards.

    The endpoint is intentionally read-only. It summarizes persisted actions
    and outcomes without changing the deterministic opportunity pipeline.
    """

    outcome_rows = (
        db.query(
            OpportunityOutcome.outcome,
            func.count(OpportunityOutcome.outcome_id),
        )
        .group_by(OpportunityOutcome.outcome)
        .order_by(func.count(OpportunityOutcome.outcome_id).desc())
        .all()
    )

    outcome_breakdown = [
        {
            "outcome": str(outcome),
            "count": int(count),
        }
        for outcome, count in outcome_rows
    ]

    type_rows = (
        db.query(
            Opportunity.opportunity_type,
            func.count(func.distinct(OpportunityAction.action_id)),
            func.count(func.distinct(OpportunityOutcome.outcome_id)),
            func.count(
                func.distinct(
                    OpportunityOutcome.outcome_id
                )
            ).filter(
                func.lower(OpportunityOutcome.outcome) == "resolved"
            ),
        )
        .outerjoin(
            OpportunityAction,
            OpportunityAction.opportunity_id == Opportunity.opportunity_id,
        )
        .outerjoin(
            OpportunityOutcome,
            OpportunityOutcome.action_id == OpportunityAction.action_id,
        )
        .group_by(Opportunity.opportunity_type)
        .order_by(Opportunity.opportunity_type.asc())
        .all()
    )

    opportunity_type_breakdown = []

    for (
        opportunity_type,
        actions,
        outcomes,
        resolved,
    ) in type_rows:
        actions = int(actions or 0)
        outcomes = int(outcomes or 0)
        resolved = int(resolved or 0)

        opportunity_type_breakdown.append(
            {
                "opportunity_type": opportunity_type,
                "actions": actions,
                "outcomes": outcomes,
                "resolved": resolved,
                "resolution_rate": round(
                    resolved / outcomes,
                    4,
                )
                if outcomes
                else 0.0,
            }
        )

    recent_rows = (
        db.query(OpportunityAction, Opportunity.opportunity_type)
        .join(
            Opportunity,
            Opportunity.opportunity_id
            == OpportunityAction.opportunity_id,
        )
        .order_by(OpportunityAction.created_at.desc())
        .limit(8)
        .all()
    )

    recent_actions = []

    for action, opportunity_type in recent_rows:
        latest_outcome = (
            db.query(OpportunityOutcome)
            .filter(
                OpportunityOutcome.action_id
                == action.action_id
            )
            .order_by(OpportunityOutcome.created_at.desc())
            .first()
        )

        recent_actions.append(
            {
                "action_id": action.action_id,
                "opportunity_id": action.opportunity_id,
                "outlet_id": action.outlet_id,
                "opportunity_type": opportunity_type,
                "action_type": action.action_type,
                "rep_id": action.rep_id,
                "outcome": (
                    latest_outcome.outcome
                    if latest_outcome
                    else None
                ),
                "created_at": (
                    action.created_at.isoformat()
                    if action.created_at
                    else None
                ),
            }
        )

    return {
        "outcome_breakdown": outcome_breakdown,
        "opportunity_type_breakdown": opportunity_type_breakdown,
        "recent_actions": recent_actions,
    }
