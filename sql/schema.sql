CREATE TABLE IF NOT EXISTS territories (
    territory_id INTEGER PRIMARY KEY,
    territory_name TEXT NOT NULL,
    region TEXT NOT NULL,
    market_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS distributors (
    distributor_id INTEGER PRIMARY KEY,
    distributor_name TEXT NOT NULL,
    territory_id INTEGER REFERENCES territories(territory_id)
);

CREATE TABLE IF NOT EXISTS sales_reps (
    rep_id INTEGER PRIMARY KEY,
    rep_name TEXT NOT NULL,
    territory_id INTEGER REFERENCES territories(territory_id),
    distributor_id INTEGER REFERENCES distributors(distributor_id),
    tenure_months INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS outlets (
    outlet_id INTEGER PRIMARY KEY,
    outlet_name TEXT NOT NULL,
    outlet_type TEXT NOT NULL,
    territory_id INTEGER REFERENCES territories(territory_id),
    distributor_id INTEGER REFERENCES distributors(distributor_id),
    rep_id INTEGER REFERENCES sales_reps(rep_id),
    city TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    tier TEXT NOT NULL,
    opening_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    pack_size TEXT NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    cost NUMERIC(12,2) NOT NULL,
    active_flag BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS orders (
    order_id BIGINT PRIMARY KEY,
    outlet_id INTEGER REFERENCES outlets(outlet_id),
    rep_id INTEGER REFERENCES sales_reps(rep_id),
    order_date DATE NOT NULL,
    order_status TEXT NOT NULL,
    gross_value NUMERIC(14,2) NOT NULL,
    discount_value NUMERIC(14,2) NOT NULL,
    net_value NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id BIGINT PRIMARY KEY,
    order_id BIGINT REFERENCES orders(order_id),
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    discount_pct NUMERIC(6,3) NOT NULL,
    line_value NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS visits (
    visit_id BIGINT PRIMARY KEY,
    outlet_id INTEGER REFERENCES outlets(outlet_id),
    rep_id INTEGER REFERENCES sales_reps(rep_id),
    visit_date DATE NOT NULL,
    visit_type TEXT NOT NULL,
    productive_flag BOOLEAN NOT NULL,
    duration_minutes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_snapshots (
    snapshot_id BIGINT PRIMARY KEY,
    outlet_id INTEGER REFERENCES outlets(outlet_id),
    product_id INTEGER REFERENCES products(product_id),
    snapshot_date DATE NOT NULL,
    opening_stock INTEGER NOT NULL,
    units_sold INTEGER NOT NULL,
    closing_stock INTEGER NOT NULL,
    stockout_flag BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS targets (
    target_id BIGINT PRIMARY KEY,
    outlet_id INTEGER REFERENCES outlets(outlet_id),
    rep_id INTEGER REFERENCES sales_reps(rep_id),
    target_month DATE NOT NULL,
    revenue_target NUMERIC(14,2) NOT NULL,
    volume_target INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    opportunity_id BIGINT PRIMARY KEY,
    outlet_id INTEGER REFERENCES outlets(outlet_id),
    opportunity_type TEXT NOT NULL,
    detected_at TIMESTAMP NOT NULL,
    score NUMERIC(8,2) NOT NULL,
    priority TEXT NOT NULL,
    estimated_value NUMERIC(14,2),
    confidence NUMERIC(8,2),
    evidence_json JSONB NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id BIGINT PRIMARY KEY,
    opportunity_id BIGINT REFERENCES opportunities(opportunity_id),
    recommended_action TEXT NOT NULL,
    rationale TEXT NOT NULL,
    assigned_rep_id INTEGER REFERENCES sales_reps(rep_id),
    created_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_outcomes (
    outcome_id BIGINT PRIMARY KEY,
    recommendation_id BIGINT REFERENCES recommendations(recommendation_id),
    action_date DATE NOT NULL,
    outcome_type TEXT NOT NULL,
    revenue_impact NUMERIC(14,2),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_outlet_date ON orders(outlet_id, order_date);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_visits_outlet_date ON visits(outlet_id, visit_date);
CREATE INDEX IF NOT EXISTS idx_inventory_outlet_date ON inventory_snapshots(outlet_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_opportunities_priority ON opportunities(priority, score DESC);
