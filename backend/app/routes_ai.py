from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai.explain import SalesForgeExplainer
from ai.provider_adapter import OllamaProvider
from backend.app.db import SessionLocal
from backend.app.models import Opportunity, AIExplanation


router = APIRouter(prefix="/ai", tags=["ai"])


def build_opportunity_payload(row: Opportunity):
    return {
        "opportunity_id": row.opportunity_id,
        "outlet_id": row.outlet_id,
        "opportunity_type": row.opportunity_type,
        "priority_score": row.score,
        "priority_band": row.priority,
        "recommended_action_from_engine": row.recommended_action,
        "evidence": row.evidence,
    }


def build_response(explanation: AIExplanation):
    return {
        "opportunity_id": explanation.opportunity_id,
        "summary": explanation.summary,
        "why_it_matters": explanation.why_it_matters,
        "recommended_action": explanation.recommended_action,
        "evidence_used": explanation.evidence_used,
        "confidence": explanation.confidence,
        "provider": explanation.provider,
        "model": explanation.model,
    }


@router.post("/opportunities/{opportunity_id}/explain")
def explain_opportunity(opportunity_id: str):
    with SessionLocal() as db:
        row = db.scalar(
            select(Opportunity).where(
                Opportunity.opportunity_id == opportunity_id
            )
        )

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Opportunity {opportunity_id} not found",
            )

        # ---------------------------------------------------------
        # 1. Check PostgreSQL first.
        # ---------------------------------------------------------
        existing = db.scalar(
            select(AIExplanation).where(
                AIExplanation.opportunity_id == opportunity_id
            )
        )

        if existing:
            return build_response(existing)

        # ---------------------------------------------------------
        # 2. No stored explanation -> generate with Ollama.
        # ---------------------------------------------------------
        opportunity = build_opportunity_payload(row)

        try:
            provider = OllamaProvider(model="qwen3:8b")
            explainer = SalesForgeExplainer(provider)

            result = explainer.explain(opportunity)

        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"AI explanation failed: {exc}",
            ) from exc

        # ---------------------------------------------------------
        # 3. Persist the validated explanation.
        # ---------------------------------------------------------
        explanation = AIExplanation(
            opportunity_id=opportunity_id,
            summary=result["summary"],
            why_it_matters=result["why_it_matters"],
            recommended_action=result["recommended_action"],
            evidence_used=result["evidence_used"],
            confidence=result["confidence"],
            provider="ollama",
            model="qwen3:8b",
        )

        db.add(explanation)
        db.commit()
        db.refresh(explanation)

        return build_response(explanation)