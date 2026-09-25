"""Seed application tables from V5 CSV outputs.

Run from the repository root after PostgreSQL is available.
"""

from pathlib import Path
import json
import pandas as pd

from .db import SessionLocal
from .init_db import init_db
from .models import Opportunity

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed_v5"
SOURCE = DATA / "prioritized_opportunities_v5.csv"


def parse_evidence(value):
    if isinstance(value, dict):
        return value
    if pd.isna(value):
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def seed():
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)

    init_db()
    df = pd.read_csv(SOURCE)

    db = SessionLocal()
    try:
        inserted = 0
        updated = 0

        for _, row in df.iterrows():
            oid = str(row["opportunity_id"])
            existing = db.get(Opportunity, oid)

            payload = dict(
                opportunity_id=oid,
                outlet_id=str(row["outlet_id"]),
                opportunity_type=str(row["opportunity_type"]),
                score=float(row["score"]),
                priority=str(row["priority"]) if "priority" in row and pd.notna(row["priority"]) else None,
                evidence=parse_evidence(row["evidence"]) if "evidence" in row else {},
                recommended_action=(
                    str(row["recommended_action"])
                    if "recommended_action" in row and pd.notna(row["recommended_action"])
                    else None
                ),
            )

            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                db.add(Opportunity(**payload))
                inserted += 1

        db.commit()
        print(f"Seed complete: inserted={inserted}, updated={updated}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
