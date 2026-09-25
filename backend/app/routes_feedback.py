from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .db import get_db
from .models import Opportunity, OpportunityAction, OpportunityOutcome

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/outcome-learning")
def outcome_learning(db: Session = Depends(get_db)):
    """
    Return observational outcome effectiveness by opportunity signal
    and action type.

    This endpoint does not modify the deterministic detector or priority
    engine. It only summarizes persisted execution outcomes.
    """

    outcome_rows = (
        db.query(
            Opportunity.opportunity_type,
            OpportunityAction.action_type,
            OpportunityOutcome.outcome,
        )
        .join(
            OpportunityAction,
            OpportunityAction.opportunity_id == Opportunity.opportunity_id,
        )
        .join(
            OpportunityOutcome,
            OpportunityOutcome.action_id == OpportunityAction.action_id,
        )
        .all()
    )

    action_rows = (
        db.query(
            Opportunity.opportunity_type,
            OpportunityAction.action_type,
        )
        .join(
            OpportunityAction,
            OpportunityAction.opportunity_id == Opportunity.opportunity_id,
        )
        .all()
    )

    by_signal = {}
    by_action = {}

    for opportunity_type, action_type in action_rows:
        signal = opportunity_type or "Unknown"
        action = action_type or "Unknown"

        by_signal.setdefault(
            signal,
            {"actions": 0, "outcomes": 0, "resolved": 0},
        )
        by_action.setdefault(
            action,
            {"actions": 0, "outcomes": 0, "resolved": 0},
        )

        by_signal[signal]["actions"] += 1
        by_action[action]["actions"] += 1

    for opportunity_type, action_type, outcome in outcome_rows:
        signal = opportunity_type or "Unknown"
        action = action_type or "Unknown"
        normalized = (outcome or "").strip().lower()

        by_signal.setdefault(
            signal,
            {"actions": 0, "outcomes": 0, "resolved": 0},
        )
        by_action.setdefault(
            action,
            {"actions": 0, "outcomes": 0, "resolved": 0},
        )

        by_signal[signal]["outcomes"] += 1
        by_action[action]["outcomes"] += 1

        if normalized == "resolved":
            by_signal[signal]["resolved"] += 1
            by_action[action]["resolved"] += 1

    def serialize(groups, key_name):
        result = []

        for key, stats in groups.items():
            outcomes = stats["outcomes"]
            result.append(
                {
                    key_name: key,
                    "actions": stats["actions"],
                    "outcomes": outcomes,
                    "resolved": stats["resolved"],
                    "resolution_rate": round(
                        stats["resolved"] / outcomes
                        if outcomes
                        else 0.0,
                        4,
                    ),
                }
            )

        return sorted(
            result,
            key=lambda row: (-row["outcomes"], row[key_name]),
        )

    total_actions = len(action_rows)
    total_outcomes = len(outcome_rows)
    total_resolved = sum(
        1
        for _, _, outcome in outcome_rows
        if (outcome or "").strip().lower() == "resolved"
    )

    minimum_outcomes = 10

    return {
        "overall": {
            "actions": total_actions,
            "outcomes": total_outcomes,
            "resolved": total_resolved,
            "resolution_rate": round(
                total_resolved / total_outcomes
                if total_outcomes
                else 0.0,
                4,
            ),
        },
        "by_opportunity_type": serialize(
            by_signal,
            "opportunity_type",
        ),
        "by_action_type": serialize(
            by_action,
            "action_type",
        ),
        "learning_status": (
            "learning_available"
            if total_outcomes >= minimum_outcomes
            else "insufficient_data"
        ),
        "minimum_outcomes_for_feedback": minimum_outcomes,
    }
