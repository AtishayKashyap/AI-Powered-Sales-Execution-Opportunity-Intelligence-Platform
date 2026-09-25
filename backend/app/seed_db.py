"""Seed SalesForge application tables from tracked deployment seed data.

The deployment seed contains:
- all V5 opportunities
- the 20 selected top actions / queue ranks
- deterministic AI explanations for those 20 top actions

The operation is idempotent and safe to run on application restarts.
"""

from pathlib import Path
import json

import pandas as pd
from sqlalchemy import select

from .db import SessionLocal
from .init_db import init_db
from .models import AIExplanation, Opportunity


ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "seed"

OPPORTUNITIES_SOURCE = SEED / "opportunities.csv"
AI_EXPLANATIONS_SOURCE = SEED / "ai_explanations.csv"
TOP_ACTIONS_SOURCE = SEED / "top_actions.csv"


def parse_json(value):
    """Parse a JSON value stored as a CSV string."""
    if isinstance(value, dict):
        return value

    if value is None:
        return {}

    try:
        if pd.isna(value):
            return {}
    except (TypeError, ValueError):
        pass

    try:
        return json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def optional_string(row, column):
    """Return a nullable string from a dataframe row."""
    if column not in row.index:
        return None

    value = row[column]

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return str(value)


def seed_opportunities(db):
    """Seed all V5 opportunities and their queue ranks."""
    if not OPPORTUNITIES_SOURCE.exists():
        raise FileNotFoundError(OPPORTUNITIES_SOURCE)

    if not TOP_ACTIONS_SOURCE.exists():
        raise FileNotFoundError(TOP_ACTIONS_SOURCE)

    opportunities = pd.read_csv(OPPORTUNITIES_SOURCE)
    top_actions = pd.read_csv(TOP_ACTIONS_SOURCE)

    required_opportunity_columns = {
        "opportunity_id",
        "outlet_id",
        "opportunity_type",
        "score",
        "evidence",
        "recommended_action",
    }

    missing = required_opportunity_columns - set(opportunities.columns)

    if missing:
        raise ValueError(
            f"Missing opportunity columns: {sorted(missing)}"
        )

    required_queue_columns = {
        "selection_rank",
        "opportunity_id",
    }

    missing = required_queue_columns - set(top_actions.columns)

    if missing:
        raise ValueError(
            f"Missing queue columns: {sorted(missing)}"
        )

    queue_ranks = {
        str(row["opportunity_id"]): int(row["selection_rank"])
        for _, row in top_actions.iterrows()
    }

    inserted = 0
    updated = 0
    queue_updated = 0

    for _, row in opportunities.iterrows():
        opportunity_id = str(row["opportunity_id"])

        payload = {
            "opportunity_id": opportunity_id,
            "outlet_id": str(row["outlet_id"]),
            "opportunity_type": str(row["opportunity_type"]),
            "score": float(row["score"]),
            "priority": optional_string(row, "priority"),
            "evidence": parse_json(row["evidence"]),
            "recommended_action": optional_string(
                row,
                "recommended_action",
            ),
        }

        existing = db.get(Opportunity, opportunity_id)

        if existing is None:
            existing = Opportunity(**payload)
            db.add(existing)
            inserted += 1
        else:
            for key, value in payload.items():
                setattr(existing, key, value)

            updated += 1

        if opportunity_id in queue_ranks:
            existing.queue_rank = queue_ranks[opportunity_id]
            queue_updated += 1

    return inserted, updated, queue_updated


def seed_ai_explanations(db):
    """Seed deterministic AI explanations for the top 20 actions."""
    if not AI_EXPLANATIONS_SOURCE.exists():
        raise FileNotFoundError(AI_EXPLANATIONS_SOURCE)

    explanations = pd.read_csv(AI_EXPLANATIONS_SOURCE)

    required_columns = {
        "opportunity_id",
        "summary",
        "why_it_matters",
        "recommended_action",
        "evidence_used",
        "confidence",
    }

    missing = required_columns - set(explanations.columns)

    if missing:
        raise ValueError(
            f"Missing AI explanation columns: {sorted(missing)}"
        )

    inserted = 0
    updated = 0

    for _, row in explanations.iterrows():
        opportunity_id = str(row["opportunity_id"])

        opportunity = db.get(Opportunity, opportunity_id)

        if opportunity is None:
            raise ValueError(
                f"AI explanation references missing opportunity: "
                f"{opportunity_id}"
            )

        existing = db.scalar(
            select(AIExplanation).where(
                AIExplanation.opportunity_id == opportunity_id
            )
        )

        payload = {
            "opportunity_id": opportunity_id,
            "summary": str(row["summary"]),
            "why_it_matters": str(row["why_it_matters"]),
            "recommended_action": str(row["recommended_action"]),
            "evidence_used": parse_json(row["evidence_used"]),
            "confidence": str(row["confidence"]),
            "provider": "deterministic_fallback",
            "model": "salesforge-v5-fallback",
        }

        if existing is None:
            db.add(AIExplanation(**payload))
            inserted += 1
        else:
            for key, value in payload.items():
                setattr(existing, key, value)

            updated += 1

    return inserted, updated


def seed():
    """Initialize the schema and seed all deployment data."""
    init_db()

    db = SessionLocal()

    try:
        (
            opportunities_inserted,
            opportunities_updated,
            queue_updated,
        ) = seed_opportunities(db)
        # Make newly inserted opportunities visible to subsequent
        # queries without committing the transaction yet.
        db.flush()
        (
            ai_inserted,
            ai_updated,
        ) = seed_ai_explanations(db)

        db.commit()

        print("SalesForge deployment seed complete:")
        print(
            f"  opportunities inserted={opportunities_inserted}, "
            f"updated={opportunities_updated}"
        )
        print(
            f"  queue ranks updated={queue_updated}"
        )
        print(
            f"  AI explanations inserted={ai_inserted}, "
            f"updated={ai_updated}"
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()
