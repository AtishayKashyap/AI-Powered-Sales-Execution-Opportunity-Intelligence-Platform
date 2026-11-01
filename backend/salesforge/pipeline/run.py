"""Run the offline pipeline and write the files the API is seeded from."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from .detect import detect, prioritize, select_queue
from .evaluate import evaluate
from .features import build_features
from .generate import GeneratorConfig, generate

log = logging.getLogger(__name__)


def run(out_dir: Path, seed: int = 42, with_evaluation: bool = True, config: GeneratorConfig | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ds = generate(config or GeneratorConfig(seed=seed))
    log.info("generated %d outlets, %d orders, %d visits", len(ds.outlets), len(ds.orders), len(ds.visits))
    features = build_features(ds)
    opportunities = select_queue(prioritize(detect(features)))
    log.info("detected %d opportunities", len(opportunities))

    territories = ds.territories.set_index("territory_id")
    reps = ds.reps.assign(territory=lambda r: r["territory_id"].map(territories["territory_name"]))
    reps[["rep_id", "rep_name", "territory"]].to_csv(out_dir / "reps.csv", index=False)

    outlets = ds.outlets.merge(
        features[["outlet_id", "baseline_monthly_revenue", "days_since_last_order"]], on="outlet_id"
    ).assign(
        territory=lambda o: o["territory_id"].map(territories["territory_name"]),
        baseline_monthly_revenue=lambda o: o["baseline_monthly_revenue"].round(0),
    )
    outlets[
        [
            "outlet_id",
            "outlet_name",
            "outlet_type",
            "tier",
            "city",
            "territory",
            "rep_id",
            "baseline_monthly_revenue",
            "days_since_last_order",
        ]
    ].to_csv(out_dir / "outlets.csv", index=False)

    export = opportunities.assign(
        evidence=opportunities["evidence"].map(lambda e: json.dumps(e, sort_keys=True)),
        queue_rank=opportunities["queue_rank"].astype("Int64"),
        as_of=ds.config.as_of,
    )
    export[
        [
            "opportunity_id",
            "outlet_id",
            "opportunity_type",
            "severity",
            "value_at_stake",
            "priority_score",
            "priority_band",
            "queue_rank",
            "evidence",
            "recommended_action",
            "as_of",
        ]
    ].to_csv(out_dir / "opportunities.csv", index=False)

    if with_evaluation:
        report = evaluate()
        (out_dir / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
        summary = pd.DataFrame(report["summary"])  # type: ignore[call-overload]
        log.info("held-out evaluation:\n%s", summary.to_string(index=False))
