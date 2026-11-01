"""Synthetic CPG distribution data with planted scenarios and near-miss decoys.

Every outlet orders on random days at a tier-dependent rate, from its own subset
of categories, and carries per-category shelf stock. A minority of outlets get a
planted scenario. Each scenario also has decoys: outlets with a weaker version
of the same pattern that a good detector should *not* flag. That is what makes
the evaluation in evaluate.py meaningful: recall is measured on the planted
cases, precision against decoys and ordinary outlets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

CATEGORIES = ["Beverages", "Snacks", "Personal Care", "Home Care", "Confectionery"]
REGIONS = {
    "North": ["Delhi", "Jaipur", "Lucknow", "Chandigarh"],
    "West": ["Mumbai", "Pune", "Ahmedabad", "Surat"],
    "South": ["Bengaluru", "Chennai", "Hyderabad", "Kochi"],
    "East": ["Kolkata", "Patna", "Bhubaneswar", "Guwahati"],
}
OUTLET_TYPES = ["General Trade", "Modern Trade", "Pharmacy", "Convenience"]
FIRST_NAMES = [
    "Aarav",
    "Diya",
    "Kabir",
    "Isha",
    "Rohan",
    "Meera",
    "Arjun",
    "Sana",
    "Vikram",
    "Neha",
    "Rahul",
    "Priya",
    "Imran",
    "Ananya",
    "Karan",
    "Pooja",
    "Aditya",
    "Riya",
    "Farhan",
    "Kavya",
]
LAST_NAMES = ["Sharma", "Patel", "Reddy", "Iyer", "Khan", "Nair", "Gupta", "Das", "Singh", "Mehta"]
STORE_WORDS = ["General Store", "Mart", "Traders", "Kirana", "Supermarket", "Medicals", "Provisions"]

# Planted-scenario and decoy shares of all outlets.
SCENARIOS = {
    "revenue_decline": (0.05, 0.04),
    "inactive": (0.04, 0.04),
    "stock_risk": (0.05, 0.04),
    "cross_sell": (0.06, 0.04),
}


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 42
    start: str = "2025-01-01"
    as_of: str = "2025-12-31"
    n_territories: int = 12
    n_reps: int = 60
    n_outlets: int = 2000
    products_per_category: int = 12


@dataclass
class Dataset:
    territories: pd.DataFrame
    reps: pd.DataFrame
    outlets: pd.DataFrame
    products: pd.DataFrame
    orders: pd.DataFrame
    order_lines: pd.DataFrame
    stock: pd.DataFrame
    visits: pd.DataFrame
    ground_truth: pd.DataFrame
    config: GeneratorConfig = field(default_factory=GeneratorConfig)


def _dimensions(cfg: GeneratorConfig, rng: np.random.Generator) -> tuple[pd.DataFrame, ...]:
    regions = list(REGIONS)
    territories = pd.DataFrame(
        {
            "territory_id": range(1, cfg.n_territories + 1),
            "region": [regions[i % len(regions)] for i in range(cfg.n_territories)],
        }
    )
    territories["territory_name"] = [f"{r} {i // len(regions) + 1}" for i, r in enumerate(territories["region"])]

    reps = pd.DataFrame({"rep_id": [f"REP-{i:03d}" for i in range(1, cfg.n_reps + 1)]})
    reps["rep_name"] = [
        f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i * 7) % len(LAST_NAMES)]}" for i in range(cfg.n_reps)
    ]
    reps["territory_id"] = [i % cfg.n_territories + 1 for i in range(cfg.n_reps)]

    n = cfg.n_outlets
    rep_idx = rng.integers(0, cfg.n_reps, n)
    territory = reps["territory_id"].to_numpy()[rep_idx]
    region = territories.set_index("territory_id")["region"].to_numpy()[territory - 1]
    tier = rng.choice(["A", "B", "C"], n, p=[0.2, 0.35, 0.45])
    outlets = pd.DataFrame(
        {
            "outlet_id": [f"OUT-{i:04d}" for i in range(1, n + 1)],
            "outlet_name": [
                f"{LAST_NAMES[rng.integers(len(LAST_NAMES))]} {STORE_WORDS[rng.integers(len(STORE_WORDS))]}"
                for _ in range(n)
            ],
            "outlet_type": rng.choice(OUTLET_TYPES, n, p=[0.5, 0.15, 0.15, 0.2]),
            "tier": tier,
            "territory_id": territory,
            "city": [REGIONS[r][rng.integers(4)] for r in region],
            "rep_id": reps["rep_id"].to_numpy()[rep_idx],
        }
    )

    rows = []
    for c_idx, category in enumerate(CATEGORIES):
        for j in range(cfg.products_per_category):
            rows.append(
                {
                    "product_id": f"SKU-{c_idx + 1}{j + 1:02d}",
                    "category": category,
                    "unit_price": round(float(rng.uniform(20, 400)), 2),
                }
            )
    products = pd.DataFrame(rows)
    return territories, reps, outlets, products


def _territory_popularity(outlets: pd.DataFrame, rng: np.random.Generator) -> dict[int, np.ndarray]:
    """Per territory, how likely an outlet is to stock each category (the top one is near-universal)."""
    popularity = {}
    for t in sorted(outlets["territory_id"].unique()):
        weights = rng.permutation(np.array([0.92, 0.85, 0.6, 0.45, 0.3]))
        popularity[int(t)] = weights
    return popularity


def generate(cfg: GeneratorConfig | None = None) -> Dataset:
    cfg = cfg or GeneratorConfig()
    rng = np.random.default_rng(cfg.seed)
    territories, reps, outlets, products = _dimensions(cfg, rng)
    days = pd.date_range(cfg.start, cfg.as_of, freq="D")
    n_days, n_out, n_cat = len(days), len(outlets), len(CATEGORIES)
    as_of_idx = n_days - 1

    # ------------------------------------------------------------- scenario assignment
    order = rng.permutation(n_out)
    role = np.array(["none"] * n_out, dtype=object)
    kind = np.array([""] * n_out, dtype=object)
    cursor = 0
    for name, (share, decoy_share) in SCENARIOS.items():
        k, d = int(share * n_out), int(decoy_share * n_out)
        role[order[cursor : cursor + k]], kind[order[cursor : cursor + k]] = "planted", name
        role[order[cursor + k : cursor + k + d]], kind[order[cursor + k : cursor + k + d]] = "decoy", name
        cursor += k + d

    # ------------------------------------------------------------- assortment
    popularity = _territory_popularity(outlets, rng)
    territory = outlets["territory_id"].to_numpy()
    carries = np.zeros((n_out, n_cat), dtype=bool)
    for i in range(n_out):
        carries[i] = rng.random(n_cat) < popularity[int(territory[i])]
        if not carries[i].any():
            carries[i, int(np.argmax(popularity[int(territory[i])]))] = True
    # Cross-sell: an outlet that does not carry its territory's most popular category.
    gap_category = np.full(n_out, -1)
    for i in np.where(kind == "cross_sell")[0]:
        ranked = np.argsort(-popularity[int(territory[i])])
        target = ranked[0] if role[i] == "planted" else ranked[-1]  # decoys miss the *least* popular one
        carries[i, target] = False
        if not carries[i].any():
            carries[i, ranked[1]] = True
        gap_category[i] = target
    # Ordinary outlets almost always carry the territory's top category; only planted cases miss it.
    for i in np.where(kind != "cross_sell")[0]:
        carries[i, int(np.argmax(popularity[int(territory[i])]))] = True

    # ------------------------------------------------------------- ordering behaviour
    # Outlets are served on a fixed weekly beat (the rep visits on set weekdays) and usually order on a visit.
    beats_per_week = {"A": 3, "B": 2, "C": 1}
    weekday = days.day_of_week.to_numpy()  # Mon=0 .. Sun=6, no visits on Sunday
    scheduled = np.zeros((n_out, n_days), dtype=bool)
    for i, t in enumerate(outlets["tier"]):
        visit_days = rng.choice(6, beats_per_week[t], replace=False)
        scheduled[i] = np.isin(weekday, visit_days)
    order_rate = rng.uniform(0.75, 0.92, n_out)
    season = 1 + 0.08 * np.sin((days.day_of_year.to_numpy() - 80) / 365 * 2 * np.pi)
    p_order = scheduled * order_rate[:, None] * season[None, :]

    detail = np.full(n_out, np.nan)
    for i in np.where(kind == "revenue_decline")[0]:
        drop = rng.uniform(0.5, 0.75) if role[i] == "planted" else rng.uniform(0.05, 0.2)
        p_order[i, as_of_idx - 59 :] *= 1 - drop  # a decline that has built over the last two months
        detail[i] = drop
    for i in np.where(kind == "inactive")[0]:
        silent = int(rng.integers(35, 75)) if role[i] == "planted" else int(rng.integers(12, 22))
        p_order[i, as_of_idx - silent + 1 :] = 0
        detail[i] = silent

    ordered = rng.random((n_out, n_days)) < np.clip(p_order, 0, 1)
    # Every outlet that is not deliberately silent orders at least once in the last two weeks,
    # so ordinary gaps never look like inactivity.
    for i in range(n_out):
        if kind[i] == "inactive":
            visits_before = np.nonzero(scheduled[i, : as_of_idx - int(detail[i]) + 1])[0]
            ordered[i, visits_before[-1]] = True
        elif not ordered[i, as_of_idx - 13 :].any():
            ordered[i, as_of_idx - 13 + int(np.nonzero(scheduled[i, as_of_idx - 13 :])[0][-1])] = True

    # ------------------------------------------------------------- orders and lines
    out_idx, day_idx = np.nonzero(ordered)
    orders = pd.DataFrame(
        {
            "order_id": [f"ORD-{i:06d}" for i in range(1, len(out_idx) + 1)],
            "outlet_id": outlets["outlet_id"].to_numpy()[out_idx],
            "order_date": days[day_idx].date,
        }
    )
    size_factor = {"A": 1.8, "B": 1.0, "C": 0.6}
    tier_factor = np.array([size_factor[t] for t in outlets["tier"]])
    products_by_cat = [products.index[products["category"] == c].to_numpy() for c in CATEGORIES]
    prices = products["unit_price"].to_numpy()
    line_order: list[int] = []
    line_product: list[int] = []
    line_qty: list[int] = []
    for order_pos, outlet_pos in enumerate(out_idx.tolist()):
        cats = np.nonzero(carries[outlet_pos])[0]
        k = int(rng.integers(1, min(len(cats), 3) + 1))
        for c in rng.choice(cats, k, replace=False):
            p = int(rng.choice(products_by_cat[c]))
            line_order.append(order_pos)
            line_product.append(p)
            line_qty.append(max(1, int(rng.poisson(6 * tier_factor[outlet_pos]))))
    line_order_a = np.array(line_order)
    line_product_a = np.array(line_product)
    order_lines = pd.DataFrame(
        {
            "order_id": orders["order_id"].to_numpy()[line_order_a],
            "product_id": products["product_id"].to_numpy()[line_product_a],
            "category": products["category"].to_numpy()[line_product_a],
            "quantity": line_qty,
            "unit_price": prices[line_product_a],
        }
    )
    order_lines["line_value"] = (order_lines["quantity"] * order_lines["unit_price"]).round(2)

    # ------------------------------------------------------------- stock (last 90 days, per outlet)
    window = 90
    stockout_rate = rng.uniform(0.0, 0.025, n_out)
    for i in np.where(kind == "stock_risk")[0]:
        stockout_rate[i] = rng.uniform(0.09, 0.2) if role[i] == "planted" else rng.uniform(0.03, 0.045)
        detail[i] = stockout_rate[i]
    stocked_out = rng.random((n_out, window)) < stockout_rate[:, None]
    level = np.where(stocked_out, 0, rng.poisson(14 * tier_factor[:, None], (n_out, window)))
    stock = pd.DataFrame(
        {
            "outlet_id": np.repeat(outlets["outlet_id"].to_numpy(), window),
            "snapshot_date": np.tile(days[-window:].date, n_out),
            "closing_units": level.ravel(),
        }
    )

    v_out, v_day = np.nonzero(scheduled)
    visits = pd.DataFrame(
        {
            "outlet_id": outlets["outlet_id"].to_numpy()[v_out],
            "visit_date": days[v_day].date,
            "ordered": ordered[v_out, v_day],
        }
    )

    ground_truth = pd.DataFrame(
        {
            "outlet_id": outlets["outlet_id"],
            "scenario": kind,
            "role": role,
            "detail": detail,
            "gap_category": [CATEGORIES[g] if g >= 0 else "" for g in gap_category],
        }
    )
    return Dataset(territories, reps, outlets, products, orders, order_lines, stock, visits, ground_truth, cfg)
