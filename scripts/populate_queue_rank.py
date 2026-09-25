from pathlib import Path

import pandas as pd

from backend.app.db import SessionLocal
from backend.app.models import Opportunity


ROOT = Path(__file__).resolve().parents[1]

QUEUE_FILE = ROOT / "data" / "processed_v5" / "top_actions_v5.csv"


def main():
    queue = pd.read_csv(QUEUE_FILE)

    required = {"selection_rank", "opportunity_id"}

    missing = required - set(queue.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    queue = queue.sort_values("selection_rank")

    db = SessionLocal()

    try:
        updated = 0

        for _, row in queue.iterrows():
            opportunity = (
                db.query(Opportunity)
                .filter(
                    Opportunity.opportunity_id
                    == str(row["opportunity_id"])
                )
                .first()
            )

            if opportunity is None:
                print(
                    f"WARNING: {row['opportunity_id']} "
                    "not found in database"
                )
                continue

            opportunity.queue_rank = int(
                row["selection_rank"]
            )

            updated += 1

        db.commit()

        print(
            f"Queue population complete: "
            f"updated={updated}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()