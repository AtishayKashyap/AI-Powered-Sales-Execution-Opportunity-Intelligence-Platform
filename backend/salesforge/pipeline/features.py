"""Outlet-level features as of a date. Everything an opportunity cites comes from here."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .generate import CATEGORIES, Dataset


def build_features(ds: Dataset) -> pd.DataFrame:
    as_of = pd.Timestamp(ds.config.as_of)
    orders = ds.orders.assign(order_date=pd.to_datetime(ds.orders["order_date"]))
    value = ds.order_lines.groupby("order_id", as_index=False)["line_value"].sum()
    orders = orders.merge(value, on="order_id")
    age = (as_of - orders["order_date"]).dt.days  # 0 = as-of day

    def window(lo: int, hi: int, column: str = "line_value", how: str = "sum") -> pd.Series:
        mask = (age >= lo) & (age < hi)
        grouped = orders[mask].groupby("outlet_id")[column]
        result: pd.Series = grouped.sum() if how == "sum" else grouped.count()
        return result

    f = ds.outlets[["outlet_id", "outlet_type", "tier", "territory_id"]].set_index("outlet_id")
    f["revenue_30d"] = window(0, 30)
    f["revenue_previous_30d"] = window(30, 60)
    f["orders_30d"] = window(0, 30, how="count")
    f["orders_previous_30d"] = window(30, 60, how="count")
    f["revenue_60d"] = window(0, 60)
    f["orders_60d"] = window(0, 60, how="count")
    # Baseline: average 30-day revenue over days 60-240, before any recent change.
    f["baseline_monthly_revenue"] = window(60, 240) / 6
    f["baseline_monthly_orders"] = window(60, 240, how="count") / 6
    f["orders_90d"] = window(0, 90, how="count")
    visits = ds.visits.assign(visit_date=pd.to_datetime(ds.visits["visit_date"]))
    v_age = (as_of - visits["visit_date"]).dt.days
    f["visits_60d"] = visits[v_age < 60].groupby("outlet_id").size()
    baseline_visits = visits[(v_age >= 60) & (v_age < 240)].groupby("outlet_id").size()
    f["baseline_order_rate"] = (f["baseline_monthly_orders"] * 6 / baseline_visits).clip(upper=1)
    f["days_since_last_order"] = orders.groupby("outlet_id")["order_date"].max().rsub(as_of).dt.days
    f = f.fillna({c: 0 for c in f.columns if c not in ("outlet_type", "tier", "territory_id")})
    f["revenue_growth_30d"] = np.where(
        f["revenue_previous_30d"] > 0, f["revenue_30d"] / f["revenue_previous_30d"].replace(0, np.nan) - 1, np.nan
    )

    stock = ds.stock.groupby("outlet_id")["closing_units"]
    f["stockout_days_90d"] = stock.apply(lambda s: int((s == 0).sum()))
    f["stockout_rate_90d"] = stock.apply(lambda s: float((s == 0).mean()))
    f["avg_closing_units_90d"] = stock.mean()

    # Category revenue per outlet over the last 180 days (cross-sell inputs).
    recent = orders.loc[age < 180, ["order_id", "outlet_id"]]
    lines = ds.order_lines.merge(recent, on="order_id")
    cat_rev = lines.pivot_table(index="outlet_id", columns="category", values="line_value", aggfunc="sum")
    cat_rev = cat_rev.reindex(index=f.index, columns=CATEGORIES).fillna(0) / 6  # per month
    for c in CATEGORIES:
        f[f"cat_monthly_{c}"] = cat_rev[c]
    f["categories_180d"] = (cat_rev > 0).sum(axis=1)
    return f.reset_index()
