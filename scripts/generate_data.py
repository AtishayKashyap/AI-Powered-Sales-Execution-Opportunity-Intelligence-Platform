"""
Generate reproducible synthetic CPG sales-execution data.

Default scale is intentionally portfolio-friendly. Increase SCALE_* constants
after the pipeline is stable.

The generator plants controlled business scenarios so later opportunity
detection can be evaluated against known ground truth.
"""

from pathlib import Path
import random
import math
import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
START = pd.Timestamp("2025-01-01")
END = pd.Timestamp("2025-12-31")
OUT = Path(__file__).resolve().parents[1] / "data" / "generated"

N_TERRITORIES = 12
N_DISTRIBUTORS = 36
N_REPS = 100
N_OUTLETS = 3000
N_PRODUCTS = 120
N_ORDERS = 80_000

random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)

OUT.mkdir(parents=True, exist_ok=True)

regions = ["North", "West", "South", "East"]
market_types = ["Metro", "Tier-1", "Tier-2", "Rural"]
outlet_types = ["General Trade", "Modern Trade", "Supermarket", "Pharmacy", "Convenience"]
tiers = ["A", "B", "C"]

categories = {
    "Beverages": ["Carbonated", "Juice", "Water"],
    "Snacks": ["Chips", "Namkeen", "Biscuits"],
    "Personal Care": ["Oral Care", "Hair Care", "Skin Care"],
    "Home Care": ["Laundry", "Dishwash", "Surface Care"],
    "Confectionery": ["Chocolate", "Candy", "Gum"],
}

cities = {
    "North": ["Delhi", "Jaipur", "Chandigarh", "Lucknow", "Ludhiana"],
    "West": ["Mumbai", "Pune", "Ahmedabad", "Surat", "Nashik"],
    "South": ["Bengaluru", "Chennai", "Hyderabad", "Kochi", "Coimbatore"],
    "East": ["Kolkata", "Bhubaneswar", "Patna", "Ranchi", "Guwahati"],
}

def save(df, name):
    df.to_csv(OUT / f"{name}.csv", index=False)

# ------------------------- dimensions -------------------------

territories = []
for i in range(1, N_TERRITORIES + 1):
    region = regions[(i - 1) % len(regions)]
    territories.append({
        "territory_id": i,
        "territory_name": f"{region} Territory {((i - 1)//4)+1}",
        "region": region,
        "market_type": random.choice(market_types),
    })
territories = pd.DataFrame(territories)
save(territories, "territories")

distributors = []
for i in range(1, N_DISTRIBUTORS + 1):
    tid = random.randint(1, N_TERRITORIES)
    distributors.append({
        "distributor_id": i,
        "distributor_name": f"Distributor {i:03d}",
        "territory_id": tid,
    })
distributors = pd.DataFrame(distributors)
save(distributors, "distributors")

reps = []
for i in range(1, N_REPS + 1):
    d = distributors.sample(1, random_state=SEED + i).iloc[0]
    reps.append({
        "rep_id": i,
        "rep_name": fake.name(),
        "territory_id": int(d.territory_id),
        "distributor_id": int(d.distributor_id),
        "tenure_months": random.randint(2, 72),
    })
reps = pd.DataFrame(reps)
save(reps, "sales_reps")

products = []
for i in range(1, N_PRODUCTS + 1):
    category = random.choice(list(categories))
    subcategory = random.choice(categories[category])
    price = round(random.uniform(20, 600), 2)
    cost = round(price * random.uniform(0.55, 0.78), 2)
    products.append({
        "product_id": i,
        "sku": f"SKU-{i:04d}",
        "brand": random.choice(["Astra", "Nova", "Pulse", "FreshCo", "DailyMax", "Prime"]),
        "category": category,
        "subcategory": subcategory,
        "pack_size": random.choice(["50g", "100g", "200g", "500g", "1L"]),
        "unit_price": price,
        "cost": cost,
        "active_flag": True,
    })
products = pd.DataFrame(products)
save(products, "products")

# Assign outlets to reps/distributors.
rep_lookup = reps.set_index("rep_id")
outlets = []
for i in range(1, N_OUTLETS + 1):
    rep_id = random.randint(1, N_REPS)
    rep = rep_lookup.loc[rep_id]
    region = territories.loc[territories.territory_id == rep.territory_id, "region"].iloc[0]
    city = random.choice(cities[region])
    tier = random.choices(tiers, weights=[0.20, 0.35, 0.45])[0]
    base = {"A": 1.8, "B": 1.0, "C": 0.55}[tier]
    outlets.append({
        "outlet_id": i,
        "outlet_name": f"{fake.last_name()} {random.choice(['General Store','Mart','Retail','Traders','Supermarket'])}",
        "outlet_type": random.choice(outlet_types),
        "territory_id": int(rep.territory_id),
        "distributor_id": int(rep.distributor_id),
        "rep_id": rep_id,
        "city": city,
        "latitude": round(random.uniform(8.0, 29.5), 5),
        "longitude": round(random.uniform(72.5, 88.5), 5),
        "tier": tier,
        "opening_date": (START - pd.Timedelta(days=random.randint(180, 3000))).date(),
        "_demand_factor": base,
    })
outlets = pd.DataFrame(outlets)
outlet_lookup = outlets.set_index("outlet_id").to_dict("index")
product_lookup = products.set_index("product_id").to_dict("index")

# Controlled scenarios: these IDs become our future ground truth.
declining_ids = set(outlets.sample(120, random_state=101).outlet_id)
inactive_ids = set(outlets.sample(100, random_state=102).outlet_id)
cross_sell_ids = set(outlets.sample(140, random_state=103).outlet_id)
stock_risk_ids = set(outlets.sample(110, random_state=104).outlet_id)

scenario_rows = []
for oid in outlets.outlet_id:
    scenario_rows.append({
        "outlet_id": oid,
        "revenue_decline_scenario": oid in declining_ids,
        "inactive_scenario": oid in inactive_ids,
        "cross_sell_scenario": oid in cross_sell_ids,
        "stock_risk_scenario": oid in stock_risk_ids,
    })
save(pd.DataFrame(scenario_rows), "scenario_ground_truth")

# ------------------------- orders -------------------------

# Weighted outlet selection by tier/demand.
outlet_weights = outlets["_demand_factor"].to_numpy()
outlet_weights = outlet_weights / outlet_weights.sum()

dates = pd.date_range(START, END, freq="D")
order_rows = []
item_rows = []

for order_id in range(1, N_ORDERS + 1):
    oid = int(np.random.choice(outlets.outlet_id, p=outlet_weights))
    o = outlet_lookup[oid]
    rep_id = int(o["rep_id"])

    # Mild seasonality, with stronger year-end demand.
    d = pd.Timestamp(np.random.choice(dates))
    month_factor = 1.0 + 0.18 * math.sin((d.month - 1) / 12 * 2 * math.pi)

    # Planted decline scenario becomes more severe in the last quarter.
    decline_factor = 1.0
    if oid in declining_ids and d >= pd.Timestamp("2025-10-01"):
        decline_factor = 0.55

    # Inactive outlets stop ordering during the last 45 days.
    if oid in inactive_ids and d >= pd.Timestamp("2025-11-17"):
        continue

    n_items = random.randint(1, 6)
    chosen_products = random.sample(range(1, N_PRODUCTS + 1), n_items)

    gross = 0.0
    item_buffer = []

    for pid in chosen_products:
        p = product_lookup[pid]
        qty = max(1, int(np.random.poisson(4 * o["_demand_factor"] * month_factor * decline_factor)))
        discount = random.uniform(0.0, 0.15)
        line = qty * float(p["unit_price"]) * (1 - discount)
        gross += line
        item_buffer.append((pid, qty, float(p["unit_price"]), discount, line))

    discount_value = gross * random.uniform(0.0, 0.04)
    net = gross - discount_value

    order_rows.append({
        "order_id": order_id,
        "outlet_id": oid,
        "rep_id": rep_id,
        "order_date": d.date(),
        "order_status": "Completed",
        "gross_value": round(gross, 2),
        "discount_value": round(discount_value, 2),
        "net_value": round(net, 2),
    })

    start_item_id = len(item_rows) + 1
    for j, (pid, qty, unit_price, discount, line) in enumerate(item_buffer):
        item_rows.append({
            "order_item_id": start_item_id + j,
            "order_id": order_id,
            "product_id": pid,
            "quantity": qty,
            "unit_price": unit_price,
            "discount_pct": round(discount, 4),
            "line_value": round(line, 2),
        })

orders = pd.DataFrame(order_rows)
order_items = pd.DataFrame(item_rows)
save(orders, "orders")
save(order_items, "order_items")

# ------------------------- visits -------------------------

visit_rows = []
visit_id = 1
for _, o in outlets.iterrows():
    # Higher-tier outlets get more expected visits.
    n_visits = random.randint(10, 55) if o["tier"] == "A" else random.randint(5, 35)
    visit_dates = random.sample(list(dates), min(n_visits, len(dates)))
    for d in visit_dates:
        productive = random.random() < (0.70 if o["tier"] == "A" else 0.58)
        if o["rep_id"] % 17 == 0:
            productive = random.random() < 0.42
        visit_rows.append({
            "visit_id": visit_id,
            "outlet_id": int(o.outlet_id),
            "rep_id": int(o.rep_id),
            "visit_date": d.date(),
            "visit_type": random.choice(["Routine", "Order Capture", "Merchandising", "Recovery"]),
            "productive_flag": productive,
            "duration_minutes": random.randint(8, 42),
        })
        visit_id += 1

visits = pd.DataFrame(visit_rows)
save(visits, "visits")

# ------------------------- inventory -------------------------

# Daily inventory for a sampled outlet/SKU panel keeps the dataset manageable.
inventory_rows = []
sample_outlets = outlets.sample(min(300, len(outlets)), random_state=201)
sample_products = products.sample(min(15, len(products)), random_state=202)

sid = 1
for _, o in sample_outlets.iterrows():
    for _, p in sample_products.iterrows():
        stock = random.randint(10, 80)
        for d in pd.date_range(START, END, freq="7D"):
            demand = max(0, int(np.random.poisson(4 * o._demand_factor)))
            opening = stock
            sold = min(opening, demand)
            # Planted stock-risk scenario causes constrained closing inventory.
            if o["outlet_id"] in stock_risk_ids and d >= pd.Timestamp("2025-09-01"):
                sold = min(opening, max(0, int(demand * 1.45)))
            closing = max(0, opening - sold + random.randint(0, 15))
            stockout = closing == 0 or (o["outlet_id"] in stock_risk_ids and sold >= opening)
            inventory_rows.append({
                "snapshot_id": sid,
                "outlet_id": int(o.outlet_id),
                "product_id": int(p["product_id"]),
                "snapshot_date": d.date(),
                "opening_stock": int(opening),
                "units_sold": int(sold),
                "closing_stock": int(closing),
                "stockout_flag": bool(stockout),
            })
            stock = closing
            sid += 1

inventory = pd.DataFrame(inventory_rows)
save(inventory, "inventory_snapshots")

# ------------------------- targets -------------------------

target_rows = []
target_id = 1
for _, o in outlets.iterrows():
    rep_id = int(o["rep_id"])
    monthly_base = {"A": 65000, "B": 38000, "C": 19000}[o["tier"]]
    for month in pd.date_range(START, END, freq="MS"):
        target_rows.append({
            "target_id": target_id,
            "outlet_id": int(o.outlet_id),
            "rep_id": rep_id,
            "target_month": month.date(),
            "revenue_target": round(monthly_base * random.uniform(0.85, 1.15), 2),
            "volume_target": random.randint(80, 500),
        })
        target_id += 1

targets = pd.DataFrame(target_rows)
save(targets, "targets")

# Clean helper column before final outlet export.
outlets = outlets.drop(columns=["_demand_factor"])
save(outlets, "outlets")

print("Synthetic SalesForge dataset generated.")
for p in sorted(OUT.glob("*.csv")):
    df = pd.read_csv(p)
    print(f"{p.name:28s} {len(df):>10,} rows")
