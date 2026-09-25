"""Basic data-quality checks for generated SalesForge data."""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "data" / "generated"

REQUIRED = {
    "territories.csv": ["territory_id"],
    "distributors.csv": ["distributor_id", "territory_id"],
    "sales_reps.csv": ["rep_id", "territory_id", "distributor_id"],
    "outlets.csv": ["outlet_id", "territory_id", "distributor_id", "rep_id"],
    "products.csv": ["product_id"],
    "orders.csv": ["order_id", "outlet_id", "rep_id", "order_date", "net_value"],
    "order_items.csv": ["order_item_id", "order_id", "product_id", "quantity"],
    "visits.csv": ["visit_id", "outlet_id", "rep_id"],
    "inventory_snapshots.csv": ["snapshot_id", "outlet_id", "product_id"],
    "targets.csv": ["target_id", "outlet_id", "rep_id"],
}

for name, cols in REQUIRED.items():
    path = ROOT / name
    assert path.exists(), f"Missing {name}"
    df = pd.read_csv(path)
    for col in cols:
        assert col in df.columns, f"{name}: missing {col}"
    assert len(df) > 0, f"{name}: empty"
    print(f"PASS {name}: {len(df):,} rows")

orders = pd.read_csv(ROOT / "orders.csv")
items = pd.read_csv(ROOT / "order_items.csv")
assert orders.order_id.is_unique
assert items.order_item_id.is_unique
assert (orders.net_value >= 0).all()
assert (items.quantity > 0).all()

print("PASS core integrity checks")
