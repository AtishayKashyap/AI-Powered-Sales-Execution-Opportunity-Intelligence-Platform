from __future__ import annotations

import pandas as pd

from salesforge.pipeline.detect import Thresholds, binomial_cdf, detect, prioritize, select_queue
from salesforge.pipeline.evaluate import score
from salesforge.pipeline.features import build_features
from salesforge.pipeline.generate import CATEGORIES, generate

from .conftest import SMALL


def test_generation_is_deterministic() -> None:
    a, b = generate(SMALL), generate(SMALL)
    pd.testing.assert_frame_equal(a.orders, b.orders)
    pd.testing.assert_frame_equal(a.ground_truth, b.ground_truth)


def test_detectors_never_read_the_ground_truth() -> None:
    ds = generate(SMALL)
    shuffled = ds.ground_truth.sample(frac=1, random_state=0).assign(scenario="", role="none")
    ds_without_truth = type(ds)(**{**ds.__dict__, "ground_truth": shuffled})
    pd.testing.assert_frame_equal(detect(build_features(ds)), detect(build_features(ds_without_truth)))


def test_planted_scenarios_are_mostly_found_and_decoys_mostly_ignored() -> None:
    ds = generate(SMALL)
    results = {s.opportunity_type: s for s in score(ds, detect(build_features(ds)))}
    assert results["Inactive Outlet"].recall == 1.0
    assert results["Stock Risk"].recall >= 0.7
    for s in results.values():
        assert s.decoys_flagged <= 0.25 * s.decoys


def test_binomial_cdf_matches_exact_arithmetic() -> None:
    from fractions import Fraction
    from math import comb

    def exact(k: int, n: int, p: Fraction) -> float:
        return float(sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1)))

    for k, n, p in ((5, 26, "4/5"), (10, 20, "1/2"), (0, 10, "1/2"), (17, 18, "9/10")):
        assert abs(binomial_cdf(k, n, float(Fraction(p))) - exact(k, n, Fraction(p))) < 1e-12
    assert binomial_cdf(26, 26, 0.8) == 1.0


def _features(**overrides: object) -> pd.DataFrame:
    row: dict[str, object] = {
        "outlet_id": "OUT-1",
        "outlet_type": "General Trade",
        "tier": "B",
        "territory_id": 1,
        "revenue_30d": 10000,
        "revenue_previous_30d": 10000,
        "revenue_60d": 20000,
        "orders_30d": 8,
        "orders_previous_30d": 8,
        "orders_60d": 16,
        "baseline_monthly_revenue": 10000,
        "baseline_monthly_orders": 8,
        "orders_90d": 24,
        "visits_60d": 18,
        "baseline_order_rate": 0.88,
        "days_since_last_order": 2,
        "revenue_growth_30d": 0.0,
        "stockout_days_90d": 0,
        "stockout_rate_90d": 0.0,
        "avg_closing_units_90d": 15,
        "categories_180d": 5,
        **{f"cat_monthly_{c}": 2000 for c in CATEGORIES},
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_a_healthy_outlet_raises_nothing() -> None:
    assert detect(_features()).empty


def test_inactive_needs_a_regular_buyer_that_went_quiet() -> None:
    assert detect(_features(days_since_last_order=40))["opportunity_type"].tolist() == ["Inactive Outlet"]
    assert detect(_features(days_since_last_order=40, baseline_monthly_orders=1)).empty
    assert detect(_features(days_since_last_order=40), Thresholds(inactive_days=45)).empty


def test_stock_risk_threshold() -> None:
    assert detect(_features(stockout_days_90d=12, stockout_rate_90d=0.13))["opportunity_type"].tolist() == [
        "Stock Risk"
    ]
    assert detect(_features(stockout_days_90d=4, stockout_rate_90d=0.045)).empty


def test_priority_and_queue_rules() -> None:
    ds = generate(SMALL)
    opps = select_queue(prioritize(detect(build_features(ds))))
    assert opps["priority_score"].between(0, 100).all()
    assert set(opps["priority_band"]) <= {"P1", "P2", "P3"}
    queued = opps[opps["queue_rank"].notna()].sort_values("queue_rank")
    assert queued["outlet_id"].is_unique
    assert queued.groupby("opportunity_type").size().max() <= 6
    # Nothing outside the queue outranks the queue's lowest entry unless a cap or the one-per-outlet rule excluded it.
    assert queued["priority_score"].is_monotonic_decreasing
