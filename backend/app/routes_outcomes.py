"""Outcome/action API router."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Opportunity, OpportunityAction, OpportunityOutcome

router = APIRouter(prefix="/opportunities", tags=["outcomes"])


class ActionRequest(BaseModel):
    action_type: str
    rep_id: str | None = None
    note: str | None = None


class OutcomeRequest(BaseModel):
    outcome: str
    note: str | None = None


@router.post("/{opportunity_id}/actions")
def create_action(
    opportunity_id: str,
    request: ActionRequest,
    db: Session = Depends(get_db),
):
    opportunity = db.get(Opportunity, opportunity_id)

    if not opportunity:
        raise HTTPException(
            status_code=404,
            detail="Opportunity not found",
        )

    action = OpportunityAction(
        opportunity_id=opportunity_id,
        outlet_id=opportunity.outlet_id,
        action_type=request.action_type,
        rep_id=request.rep_id,
        note=request.note,
    )

    db.add(action)
    db.commit()
    db.refresh(action)

    return {
        "status": "created",
        "action": {
            "action_id": action.action_id,
            "opportunity_id": opportunity_id,
            "outlet_id": action.outlet_id,
            "action_type": action.action_type,
            "rep_id": action.rep_id,
            "note": action.note,
        },
    }


@router.post("/{opportunity_id}/actions/{action_id}/outcome")
def create_outcome(
    opportunity_id: str,
    action_id: int,
    request: OutcomeRequest,
    db: Session = Depends(get_db),
):
    action = db.get(OpportunityAction, action_id)

    if not action or action.opportunity_id != opportunity_id:
        raise HTTPException(
            status_code=404,
            detail="Action not found",
        )

    outcome = OpportunityOutcome(
        action_id=action_id,
        outcome=request.outcome,
        note=request.note,
    )

    db.add(outcome)
    db.commit()
    db.refresh(outcome)

    return {
        "status": "recorded",
        "outcome_id": outcome.outcome_id,
        "action_id": action_id,
        "outcome": outcome.outcome,
    }


@router.get("/{opportunity_id}/execution-state")
def get_execution_state(
    opportunity_id: str,
    db: Session = Depends(get_db),
):
    opportunity = db.get(Opportunity, opportunity_id)

    if not opportunity:
        raise HTTPException(
            status_code=404,
            detail="Opportunity not found",
        )

    latest_action = db.scalar(
        select(OpportunityAction)
        .where(
            OpportunityAction.opportunity_id == opportunity_id
        )
        .order_by(desc(OpportunityAction.created_at))
        .limit(1)
    )

    if latest_action is None:
        return {
            "opportunity_id": opportunity_id,
            "action": None,
            "outcome": None,
        }

    latest_outcome = db.scalar(
        select(OpportunityOutcome)
        .where(
            OpportunityOutcome.action_id
            == latest_action.action_id
        )
        .order_by(desc(OpportunityOutcome.created_at))
        .limit(1)
    )

    return {
        "opportunity_id": opportunity_id,
        "action": {
            "action_id": latest_action.action_id,
            "opportunity_id": latest_action.opportunity_id,
            "outlet_id": latest_action.outlet_id,
            "action_type": latest_action.action_type,
            "rep_id": latest_action.rep_id,
            "note": latest_action.note,
            "created_at": latest_action.created_at,
        },
        "outcome": (
            {
                "outcome_id": latest_outcome.outcome_id,
                "action_id": latest_outcome.action_id,
                "outcome": latest_outcome.outcome,
                "note": latest_outcome.note,
                "created_at": latest_outcome.created_at,
            }
            if latest_outcome
            else None
        ),
    }