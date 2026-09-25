# SalesForge Data Model

## Entity relationships

```text
Territory 1 ─── N Outlet
Territory 1 ─── N SalesRep
Distributor 1 ─── N Outlet
SalesRep 1 ─── N Outlet
Outlet 1 ─── N Order
Order 1 ─── N OrderItem
Product 1 ─── N OrderItem
Outlet 1 ─── N Visit
Outlet 1 ─── N InventorySnapshot
Outlet 1 ─── N Target
Outlet 1 ─── N Opportunity
Opportunity 1 ─── N Recommendation
Recommendation 1 ─── N ActionOutcome
```

## Core tables

### territories
- territory_id
- territory_name
- region
- market_type

### distributors
- distributor_id
- distributor_name
- territory_id

### sales_reps
- rep_id
- rep_name
- territory_id
- distributor_id
- tenure_months

### outlets
- outlet_id
- outlet_name
- outlet_type
- territory_id
- distributor_id
- rep_id
- city
- latitude
- longitude
- tier
- opening_date

### products
- product_id
- sku
- brand
- category
- subcategory
- pack_size
- unit_price
- cost
- active_flag

### orders
- order_id
- outlet_id
- rep_id
- order_date
- order_status
- gross_value
- discount_value
- net_value

### order_items
- order_item_id
- order_id
- product_id
- quantity
- unit_price
- discount_pct
- line_value

### visits
- visit_id
- outlet_id
- rep_id
- visit_date
- visit_type
- productive_flag
- duration_minutes

### inventory_snapshots
- snapshot_id
- outlet_id
- product_id
- snapshot_date
- opening_stock
- units_sold
- closing_stock
- stockout_flag

### targets
- target_id
- outlet_id
- rep_id
- target_month
- revenue_target
- volume_target

### opportunities
- opportunity_id
- outlet_id
- opportunity_type
- detected_at
- score
- priority
- estimated_value
- confidence
- evidence_json
- status

### recommendations
- recommendation_id
- opportunity_id
- recommended_action
- rationale
- assigned_rep_id
- created_at
- status

### action_outcomes
- outcome_id
- recommendation_id
- action_date
- outcome_type
- revenue_impact
- notes
