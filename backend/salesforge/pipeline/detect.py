"""Rule-based opportunity detectors.

Each detector reads only outlet features (never the ground truth), returns an
opportunity with a 0-100 severity, the evidence that justifies it, and the
monthly revenue at stake. Thresholds are module constants so evaluate.py can
sweep them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .generate import CATEGORIES

REVENUE_DROP_THRESHOLD = -0.35  # last 60 days vs the outlet's own baseline
REVENUE_MIN_BASELINE = 3000.0
REVENUE_MAX_P_VALUE = 0.01  # the drop in order count must be unlikely under the outlet's normal rate
INACTIVE_DAYS = 30
INACTIVE_MIN_BASELINE_ORDERS = 2.0  # per month: only outlets that used to order regularly
STOCKOUT_RATE_THRESHOLD = 0.08
STOCKOUT_MIN_DAYS = 5
CROSS_SELL_PEER_ADOPTION = 0.90  # share of similar outlets that carry the category
CROSS_SELL_MIN_ORDERS_90D = 3  # the outlet must be actively buying


@dataclass(frozen=True)
class Thresholds:
    revenue_drop: float = REVENUE_DROP_THRESHOLD
    revenue_p_value: float = REVENUE_MAX_P_VALUE
    inactive_days: int = INACTIVE_DAYS
    stockout_rate: float = STOCKOUT_RATE_THRESHOLD
    peer_adoption: float = CROSS_SELL_PEER_ADOPTION


def _clip(x: float) -> float:
    return float(min(100.0, max(0.0, x)))


def _record(
    row: pd.Series, kind: str, severity: float, value: float, evidence: dict[str, Any], action: str
) -> dict[str, Any]:
    return {
        "outlet_id": row["outlet_id"],
        "opportunity_type": kind,
        "severity": round(_clip(severity), 1),
        "value_at_stake": round(float(value), 0),
        "evidence": evidence,
        "recommended_action": action,
    }


def binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p)."""
    p = min(max(p, 0.0), 1.0)
    return min(1.0, sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, min(k, n) + 1)))


def revenue_recovery(f: pd.DataFrame, t: Thresholds) -> list[dict[str, Any]]:
    """A real decline, not noise or season.

    Outlets order on scheduled beat visits. The expected order rate per visit is the outlet's own baseline
    rate, scaled by how much the median outlet's rate moved over the same 60 days (removes seasonality).
    Flag when revenue is well below expectation AND the number of orders from the scheduled visits would be
    unlikely at the expected rate (one-sided binomial test).
    """
    ok = (f["baseline_order_rate"] > 0) & (f["visits_60d"] > 0)
    recent_rate = f["orders_60d"] / f["visits_60d"]
    season = float((recent_rate[ok] / f.loc[ok, "baseline_order_rate"]).median())
    expected_rate = (f["baseline_order_rate"] * season).clip(upper=1)
    expected_orders = f["visits_60d"] * expected_rate
    expected_revenue = 2 * f["baseline_monthly_revenue"] * season
    change = f["revenue_60d"] / expected_revenue.replace(0, np.nan) - 1
    scored = f.assign(
        expected_rate=expected_rate, expected_orders=expected_orders, expected_revenue=expected_revenue, change=change
    )
    candidates = scored[
        ok
        & (f["baseline_monthly_revenue"] >= REVENUE_MIN_BASELINE)
        & (f["orders_30d"] > 0)
        & (change <= t.revenue_drop)
    ]
    out = []
    for _, r in candidates.iterrows():
        p_value = binomial_cdf(int(r["orders_60d"]), int(r["visits_60d"]), float(r["expected_rate"]))
        if p_value > t.revenue_p_value:
            continue
        drop = -float(r["change"])
        evidence = {
            "revenue_60d": round(float(r["revenue_60d"])),
            "expected_revenue_60d": round(float(r["expected_revenue"])),
            "revenue_change_pct": round(-drop * 100, 1),
            "orders_60d": int(r["orders_60d"]),
            "scheduled_visits_60d": int(r["visits_60d"]),
            "expected_orders_60d": round(float(r["expected_orders"]), 1),
        }
        out.append(
            _record(
                r,
                "Revenue Recovery",
                drop * 100 + 20,
                float(r["expected_revenue"] - r["revenue_60d"]) / 2,
                evidence,
                "Visit to find which categories dropped and agree a recovery order.",
            )
        )
    return out


def inactive(f: pd.DataFrame, t: Thresholds) -> list[dict[str, Any]]:
    hits = f[
        (f["days_since_last_order"] >= t.inactive_days) & (f["baseline_monthly_orders"] >= INACTIVE_MIN_BASELINE_ORDERS)
    ]
    out = []
    for _, r in hits.iterrows():
        days = int(r["days_since_last_order"])
        evidence = {
            "days_since_last_order": days,
            "baseline_monthly_orders": round(float(r["baseline_monthly_orders"]), 1),
            "baseline_monthly_revenue": round(float(r["baseline_monthly_revenue"])),
        }
        out.append(
            _record(
                r,
                "Inactive Outlet",
                40 + (days - t.inactive_days) * 1.5,
                r["baseline_monthly_revenue"],
                evidence,
                "Win-back visit: find out why ordering stopped and place a reorder from the usual mix.",
            )
        )
    return out


def stock_risk(f: pd.DataFrame, t: Thresholds) -> list[dict[str, Any]]:
    hits = f[(f["stockout_rate_90d"] >= t.stockout_rate) & (f["stockout_days_90d"] >= STOCKOUT_MIN_DAYS)]
    out = []
    for _, r in hits.iterrows():
        rate = float(r["stockout_rate_90d"])
        evidence = {
            "stockout_days_90d": int(r["stockout_days_90d"]),
            "stockout_rate_pct": round(rate * 100, 1),
            "avg_closing_units_90d": round(float(r["avg_closing_units_90d"]), 1),
            "baseline_monthly_revenue": round(float(r["baseline_monthly_revenue"])),
        }
        out.append(
            _record(
                r,
                "Stock Risk",
                rate * 500,
                rate * float(r["baseline_monthly_revenue"]),
                evidence,
                "Raise replenishment with the distributor and agree a higher safety stock.",
            )
        )
    return out


def cross_sell(f: pd.DataFrame, t: Thresholds) -> list[dict[str, Any]]:
    out = []
    for (_territory, _otype), peers in f.groupby(["territory_id", "outlet_type"]):
        if len(peers) < 8:
            continue
        for c in CATEGORIES:
            col = f"cat_monthly_{c}"
            carriers = peers[peers[col] > 0]
            adoption = len(carriers) / len(peers)
            if adoption < t.peer_adoption:
                continue
            peer_value = float(carriers[col].median())
            gaps = peers[(peers[col] == 0) & (peers["orders_90d"] >= CROSS_SELL_MIN_ORDERS_90D)]
            for _, r in gaps.iterrows():
                evidence = {
                    "target_category": c,
                    "peer_adoption_pct": round(adoption * 100, 1),
                    "peer_outlets": len(peers),
                    "peer_median_monthly_revenue": round(peer_value),
                    "orders_90d": int(r["orders_90d"]),
                }
                out.append(
                    _record(
                        r,
                        "Cross-Sell",
                        adoption * 100,
                        peer_value,
                        evidence,
                        f"Introduce {c}: most similar outlets nearby already stock it.",
                    )
                )
    return out


DETECTORS = (revenue_recovery, inactive, stock_risk, cross_sell)


def detect(features: pd.DataFrame, thresholds: Thresholds | None = None) -> pd.DataFrame:
    t = thresholds or Thresholds()
    rows = [o for detector in DETECTORS for o in detector(features, t)]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values(["outlet_id", "opportunity_type"]).reset_index(drop=True)
    df.insert(0, "opportunity_id", [f"OPP-{i:05d}" for i in range(1, len(df) + 1)])
    return df


def percentile(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method="average") * 100 if len(series) else series


def prioritize(opps: pd.DataFrame) -> pd.DataFrame:
    """Priority = half severity, half revenue at stake (percentile across all opportunities)."""
    df = opps.copy()
    df["priority_score"] = (0.5 * df["severity"] + 0.5 * percentile(df["value_at_stake"])).round(1)
    df["priority_band"] = np.select([df["priority_score"] >= 75, df["priority_score"] >= 50], ["P1", "P2"], "P3")
    return df


QUEUE_SIZE = 20
TYPE_CAPS = {"Revenue Recovery": 6, "Inactive Outlet": 5, "Stock Risk": 5, "Cross-Sell": 5}


def select_queue(opps: pd.DataFrame, size: int = QUEUE_SIZE) -> pd.DataFrame:
    """Highest priority first, at most one opportunity per outlet and a cap per type so the queue stays mixed."""
    taken: dict[str, int] = {}
    outlets: set[str] = set()
    picks = []
    for idx, r in opps.sort_values(["priority_score", "value_at_stake"], ascending=False).iterrows():
        if r["outlet_id"] in outlets or taken.get(r["opportunity_type"], 0) >= TYPE_CAPS[r["opportunity_type"]]:
            continue
        picks.append(idx)
        outlets.add(r["outlet_id"])
        taken[r["opportunity_type"]] = taken.get(r["opportunity_type"], 0) + 1
        if len(picks) == size:
            break
    queued = opps.copy()
    queued["queue_rank"] = pd.Series(range(1, len(picks) + 1), index=picks)
    return queued
