"""Small outcome analytics queries for the dashboard."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import OpportunityAction, OpportunityOutcome


def execution_summary(db: Session):
    total_actions = db.query(func.count(OpportunityAction.action_id)).scalar() or 0
    total_outcomes = db.query(func.count(OpportunityOutcome.outcome_id)).scalar() or 0

    resolved = (
        db.query(func.count(OpportunityOutcome.outcome_id))
        .filter(OpportunityOutcome.outcome == "resolved")
        .scalar()
        or 0
    )

    contacted = (
        db.query(func.count(OpportunityOutcome.outcome_id))
        .filter(OpportunityOutcome.outcome == "contacted")
        .scalar()
        or 0
    )

    return {
        "total_actions": total_actions,
        "total_outcomes": total_outcomes,
        "contacted": contacted,
        "resolved": resolved,
        "resolution_rate": round(resolved / total_outcomes, 4)
        if total_outcomes else 0.0,
    }
