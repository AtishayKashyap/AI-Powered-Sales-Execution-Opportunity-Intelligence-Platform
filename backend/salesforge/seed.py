"""Load data/seed/*.csv into the database, replacing whatever was there (used for the nightly demo reset)."""

from __future__ import annotations

import csv
import json
import logging
from datetime import date
from pathlib import Path

from sqlalchemy import Engine, delete, insert
from sqlalchemy.orm import Session

from . import models

log = logging.getLogger(__name__)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def seed(engine: Engine, data_dir: Path) -> dict[str, int]:
    reps = _rows(data_dir / "reps.csv")
    outlets = [
        {
            **r,
            "baseline_monthly_revenue": float(r["baseline_monthly_revenue"]),
            "days_since_last_order": int(r["days_since_last_order"]),
        }
        for r in _rows(data_dir / "outlets.csv")
    ]
    opportunities = [
        {
            **r,
            "opportunity_type": models.OpportunityType(r["opportunity_type"]),
            "severity": float(r["severity"]),
            "value_at_stake": float(r["value_at_stake"]),
            "priority_score": float(r["priority_score"]),
            "queue_rank": int(r["queue_rank"]) if r["queue_rank"] else None,
            "evidence": json.loads(r["evidence"]),
            "as_of": date.fromisoformat(r["as_of"]),
        }
        for r in _rows(data_dir / "opportunities.csv")
    ]
    with Session(engine) as session, session.begin():
        for table in (models.Outcome, models.Action, models.Explanation, models.Opportunity, models.Outlet, models.Rep):
            session.execute(delete(table))
        session.execute(insert(models.Rep), reps)
        session.execute(insert(models.Outlet), outlets)
        session.execute(insert(models.Opportunity), opportunities)
    counts = {"reps": len(reps), "outlets": len(outlets), "opportunities": len(opportunities)}
    log.info("seeded %s", counts)
    return counts
