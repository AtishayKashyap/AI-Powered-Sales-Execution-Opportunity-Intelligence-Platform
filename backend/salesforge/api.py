"""HTTP API."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Select, case, exists, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from . import models, schemas
from .ai.explainer import get_explanation
from .ai.providers import Provider, build_provider
from .db import get_session
from .ratelimit import RateLimiter
from .settings import Settings, get_settings

log = logging.getLogger("salesforge")

DB = Annotated[Session, Depends(get_session)]

# Status of an opportunity = the outcome of its most recent action.
_latest_outcome = (
    select(models.Outcome.outcome)
    .join(models.Action, models.Action.action_id == models.Outcome.action_id)
    .where(models.Action.opportunity_id == models.Opportunity.opportunity_id)
    .order_by(models.Action.created_at.desc(), models.Action.action_id.desc())
    .limit(1)
    .scalar_subquery()
)
_has_action = exists().where(models.Action.opportunity_id == models.Opportunity.opportunity_id)
STATUS = case(
    (~_has_action, "open"),
    (_latest_outcome == models.OutcomeType.resolved, "resolved"),
    (_latest_outcome == models.OutcomeType.not_viable, "closed"),
    else_="in_progress",
).label("status")


def _summaries(db: Session, stmt: Select[Any]) -> list[schemas.OpportunitySummary]:
    return [
        schemas.OpportunitySummary.model_validate({**_attrs(o), "status": status})
        for o, status in db.execute(stmt).all()
    ]


def _attrs(o: models.Opportunity) -> dict[str, object]:
    return {c: getattr(o, c) for c in schemas.OpportunitySummary.model_fields if c != "status"}


def create_app(settings: Settings | None = None, provider: Provider | None = None) -> FastAPI:
    settings = settings or get_settings()
    llm = provider if provider is not None else build_provider(settings)
    write_limit = RateLimiter(settings.write_requests_per_minute)

    app = FastAPI(
        title="SalesForge API",
        version="2.0.0",
        description="Prioritised sales opportunities for field reps, with grounded explanations and outcome tracking.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    @app.get("/health", tags=["meta"])
    def health(db: DB) -> dict[str, str]:
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            raise HTTPException(503, "database unavailable") from None
        return {"status": "ok", "llm": llm.model if llm else "none"}

    @app.get("/opportunities/queue", response_model=list[schemas.OpportunitySummary], tags=["opportunities"])
    def queue(db: DB) -> list[schemas.OpportunitySummary]:
        stmt = (
            select(models.Opportunity, STATUS)
            .where(models.Opportunity.queue_rank.is_not(None))
            .order_by(models.Opportunity.queue_rank)
        )
        return _summaries(db, stmt)

    @app.get("/opportunities", response_model=schemas.OpportunityPage, tags=["opportunities"])
    def list_opportunities(
        db: DB,
        opportunity_type: models.OpportunityType | None = None,
        priority_band: Annotated[str | None, Query(pattern="^P[123]$")] = None,
        status: schemas.Status | None = None,
        q: Annotated[str | None, Query(max_length=60)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> schemas.OpportunityPage:
        stmt = select(models.Opportunity, STATUS).join(models.Opportunity.outlet)
        if opportunity_type:
            stmt = stmt.where(models.Opportunity.opportunity_type == opportunity_type)
        if priority_band:
            stmt = stmt.where(models.Opportunity.priority_band == priority_band)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    models.Outlet.outlet_name.ilike(like),
                    models.Outlet.city.ilike(like),
                    models.Outlet.outlet_id.ilike(like),
                )
            )
        if status:
            stmt = stmt.where(STATUS.op("=")(status))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        page = stmt.order_by(models.Opportunity.priority_score.desc(), models.Opportunity.opportunity_id)
        items = _summaries(db, page.limit(limit).offset(offset))
        return schemas.OpportunityPage(items=items, total=total, limit=limit, offset=offset)

    def _load(db: Session, opportunity_id: str) -> models.Opportunity:
        o = db.scalar(
            select(models.Opportunity)
            .where(models.Opportunity.opportunity_id == opportunity_id)
            .options(selectinload(models.Opportunity.actions))
        )
        if o is None:
            raise HTTPException(404, "Opportunity not found")
        return o

    def _detail(db: Session, o: models.Opportunity) -> schemas.OpportunityDetail:
        status = db.scalar(select(STATUS).where(models.Opportunity.opportunity_id == o.opportunity_id))
        return schemas.OpportunityDetail.model_validate(
            {**_attrs(o), "status": status, "evidence": o.evidence, "as_of": o.as_of, "actions": o.actions}
        )

    @app.get("/opportunities/{opportunity_id}", response_model=schemas.OpportunityDetail, tags=["opportunities"])
    def get_opportunity(opportunity_id: str, db: DB) -> schemas.OpportunityDetail:
        return _detail(db, _load(db, opportunity_id))

    @app.post(
        "/opportunities/{opportunity_id}/actions",
        response_model=schemas.OpportunityDetail,
        status_code=201,
        dependencies=[Depends(write_limit)],
        tags=["execution"],
    )
    def record_action(opportunity_id: str, body: schemas.ActionIn, db: DB) -> schemas.OpportunityDetail:
        o = _load(db, opportunity_id)
        o.actions.append(models.Action(rep_id=o.outlet.rep_id, action_type=body.action_type, note=body.note))
        db.commit()
        db.refresh(o)
        return _detail(db, o)

    @app.put(
        "/actions/{action_id}/outcome",
        response_model=schemas.OpportunityDetail,
        dependencies=[Depends(write_limit)],
        tags=["execution"],
    )
    def record_outcome(action_id: int, body: schemas.OutcomeIn, db: DB) -> schemas.OpportunityDetail:
        action = db.get(models.Action, action_id)
        if action is None:
            raise HTTPException(404, "Action not found")
        if action.outcome is None:
            action.outcome = models.Outcome(outcome=body.outcome, note=body.note)
        else:
            action.outcome.outcome, action.outcome.note = body.outcome, body.note
        db.commit()
        return _detail(db, _load(db, action.opportunity_id))

    @app.get("/opportunities/{opportunity_id}/explanation", response_model=schemas.ExplanationOut, tags=["ai"])
    def explanation(opportunity_id: str, db: DB) -> schemas.ExplanationOut:
        return schemas.ExplanationOut.model_validate(get_explanation(db, _load(db, opportunity_id), llm).model_dump())

    @app.get("/analytics/summary", response_model=schemas.AnalyticsSummary, tags=["analytics"])
    def analytics(db: DB) -> schemas.AnalyticsSummary:
        per_opp = select(models.Opportunity.opportunity_type, models.Opportunity.value_at_stake, STATUS).subquery()
        by_type = [
            schemas.TypeStats(
                opportunity_type=r.opportunity_type.value,
                opportunities=r.n,
                actioned=r.actioned,
                resolved=r.resolved,
                resolution_rate=(r.resolved / r.actioned) if r.actioned else None,
                value_at_stake=r.value,
            )
            for r in db.execute(
                select(
                    per_opp.c.opportunity_type,
                    func.count().label("n"),
                    func.count().filter(per_opp.c.status != "open").label("actioned"),
                    func.count().filter(per_opp.c.status == "resolved").label("resolved"),
                    func.coalesce(func.sum(per_opp.c.value_at_stake), 0).label("value"),
                )
                .group_by(per_opp.c.opportunity_type)
                .order_by(per_opp.c.opportunity_type)
            )
        ]
        by_outcome = {
            o.value: n
            for o, n in db.execute(select(models.Outcome.outcome, func.count()).group_by(models.Outcome.outcome))
        }
        top_reps = [
            schemas.RepStats(rep_id=r.rep_id, rep_name=r.rep_name, actions=r.actions, resolved=r.resolved)
            for r in db.execute(
                select(
                    models.Rep.rep_id,
                    models.Rep.rep_name,
                    func.count(models.Action.action_id).label("actions"),
                    func.count().filter(models.Outcome.outcome == models.OutcomeType.resolved).label("resolved"),
                )
                .join(models.Action, models.Action.rep_id == models.Rep.rep_id)
                .outerjoin(models.Outcome, models.Outcome.action_id == models.Action.action_id)
                .group_by(models.Rep.rep_id, models.Rep.rep_name)
                .order_by(func.count(models.Action.action_id).desc(), models.Rep.rep_id)
                .limit(5)
            )
        ]
        actioned = sum(t.actioned for t in by_type)
        resolved = sum(t.resolved for t in by_type)
        return schemas.AnalyticsSummary(
            as_of=db.scalar(select(func.max(models.Opportunity.as_of))),
            opportunities=sum(t.opportunities for t in by_type),
            queue_size=db.scalar(select(func.count()).where(models.Opportunity.queue_rank.is_not(None))) or 0,
            value_at_stake=sum(t.value_at_stake for t in by_type),
            actioned=actioned,
            resolved=resolved,
            resolution_rate=resolved / actioned if actioned else None,
            by_type=by_type,
            by_outcome=by_outcome,
            top_reps=top_reps,
        )

    return app
