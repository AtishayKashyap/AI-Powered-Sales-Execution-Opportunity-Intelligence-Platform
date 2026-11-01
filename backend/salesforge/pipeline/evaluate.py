"""Score the detectors against the planted ground truth.

Thresholds were chosen on the tuning seed (42). They are then evaluated, unchanged, on held-out seeds that
generate different outlets, beats and scenarios, so the numbers are not fitted to the data they report on.
Precision counts every flagged outlet that was not planted (decoys and ordinary outlets) as a false positive.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from .detect import Thresholds, detect
from .features import build_features
from .generate import Dataset, GeneratorConfig, generate

TUNING_SEED = 42
HELD_OUT_SEEDS = (7, 101, 2024, 31337)
TYPE_TO_SCENARIO = {
    "Revenue Recovery": "revenue_decline",
    "Inactive Outlet": "inactive",
    "Stock Risk": "stock_risk",
    "Cross-Sell": "cross_sell",
}


@dataclass(frozen=True)
class Score:
    seed: int
    opportunity_type: str
    flagged: int
    planted: int
    true_positives: int
    decoys_flagged: int
    decoys: int

    @property
    def precision(self) -> float:
        return self.true_positives / self.flagged if self.flagged else 0.0

    @property
    def recall(self) -> float:
        return self.true_positives / self.planted if self.planted else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def score(ds: Dataset, opportunities: pd.DataFrame) -> list[Score]:
    truth = ds.ground_truth
    out = []
    for otype, scenario in TYPE_TO_SCENARIO.items():
        flagged = set(opportunities.loc[opportunities["opportunity_type"] == otype, "outlet_id"])
        planted = set(truth.loc[(truth["scenario"] == scenario) & (truth["role"] == "planted"), "outlet_id"])
        decoys = set(truth.loc[(truth["scenario"] == scenario) & (truth["role"] == "decoy"), "outlet_id"])
        out.append(
            Score(
                ds.config.seed,
                otype,
                len(flagged),
                len(planted),
                len(flagged & planted),
                len(flagged & decoys),
                len(decoys),
            )
        )
    return out


def threshold_sweep(ds: Dataset, features: pd.DataFrame) -> pd.DataFrame:
    """Precision/recall for neighbouring thresholds on the tuning seed: shows the operating point is not a cliff."""
    rows = []
    grid: dict[str, list[Thresholds]] = {
        "Revenue Recovery": [Thresholds(revenue_p_value=p) for p in (0.001, 0.005, 0.01, 0.02, 0.05)],
        "Inactive Outlet": [Thresholds(inactive_days=d) for d in (21, 25, 30, 35, 45)],
        "Stock Risk": [Thresholds(stockout_rate=r) for r in (0.04, 0.05, 0.06, 0.08, 0.1)],
        "Cross-Sell": [Thresholds(peer_adoption=a) for a in (0.8, 0.85, 0.9, 0.95)],
    }
    setting = {
        "Revenue Recovery": "revenue_p_value",
        "Inactive Outlet": "inactive_days",
        "Stock Risk": "stockout_rate",
        "Cross-Sell": "peer_adoption",
    }
    for otype, options in grid.items():
        for t in options:
            s = next(x for x in score(ds, detect(features, t)) if x.opportunity_type == otype)
            rows.append(
                {
                    "opportunity_type": otype,
                    "parameter": setting[otype],
                    "value": getattr(t, setting[otype]),
                    "is_default": getattr(t, setting[otype]) == getattr(Thresholds(), setting[otype]),
                    "precision": round(s.precision, 3),
                    "recall": round(s.recall, 3),
                }
            )
    return pd.DataFrame(rows)


def evaluate(seeds: tuple[int, ...] = HELD_OUT_SEEDS) -> dict[str, object]:
    scores: list[Score] = []
    for seed in seeds:
        ds = generate(GeneratorConfig(seed=seed))
        scores.extend(score(ds, detect(build_features(ds))))
    df = pd.DataFrame([{**asdict(s), "precision": s.precision, "recall": s.recall, "f1": s.f1} for s in scores])
    summary = (
        df.groupby("opportunity_type")
        .agg(
            precision_mean=("precision", "mean"),
            precision_min=("precision", "min"),
            recall_mean=("recall", "mean"),
            recall_min=("recall", "min"),
            f1_mean=("f1", "mean"),
            decoys_flagged=("decoys_flagged", "sum"),
            decoys=("decoys", "sum"),
        )
        .round(3)
        .reset_index()
    )
    tuning = generate(GeneratorConfig(seed=TUNING_SEED))
    sweep = threshold_sweep(tuning, build_features(tuning))
    return {
        "tuning_seed": TUNING_SEED,
        "held_out_seeds": list(seeds),
        "thresholds": asdict(Thresholds()),
        "summary": summary.to_dict("records"),
        "per_seed": df.round(3).to_dict("records"),
        "threshold_sweep": sweep.to_dict("records"),
    }
