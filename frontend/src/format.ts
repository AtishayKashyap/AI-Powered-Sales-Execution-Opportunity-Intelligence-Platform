import type { OpportunityType, OutcomeType, Status } from "./types";

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function rupees(value: number): string {
  return inr.format(value);
}

/** ₹1.2L / ₹34.5k style for tight spaces (Indian lakh/crore units). */
export function rupeesShort(value: number): string {
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(1)}Cr`;
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(1)}L`;
  if (value >= 1e3) return `₹${(value / 1e3).toFixed(1)}k`;
  return rupees(value);
}

export function percent(value: number | null, digits = 0): string {
  return value === null ? "–" : `${(value * 100).toFixed(digits)}%`;
}

export function date(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export const STATUS_LABEL: Record<Status, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

export const OUTCOME_LABEL: Record<OutcomeType, string> = {
  resolved: "Resolved",
  follow_up: "Needs follow-up",
  no_response: "No response",
  not_viable: "Not viable",
};

export const TYPE_SHORT: Record<OpportunityType, string> = {
  "Revenue Recovery": "Recovery",
  "Inactive Outlet": "Inactive",
  "Stock Risk": "Stock",
  "Cross-Sell": "Cross-sell",
};

/** Human labels for evidence fields; unknown keys fall back to a tidied version of the key. */
const EVIDENCE_LABEL: Record<string, string> = {
  revenue_60d: "Revenue, last 60 days",
  expected_revenue_60d: "Expected revenue, 60 days",
  revenue_change_pct: "Change vs expected",
  orders_60d: "Orders, last 60 days",
  scheduled_visits_60d: "Scheduled visits, 60 days",
  expected_orders_60d: "Expected orders, 60 days",
  days_since_last_order: "Days since last order",
  baseline_monthly_orders: "Usual orders per month",
  baseline_monthly_revenue: "Usual monthly revenue",
  stockout_days_90d: "Stock-out days, last 90",
  stockout_rate_pct: "Stock-out rate",
  avg_closing_units_90d: "Average shelf stock (units)",
  target_category: "Missing category",
  peer_adoption_pct: "Similar outlets stocking it",
  peer_outlets: "Similar outlets compared",
  peer_median_monthly_revenue: "Their median monthly sales",
  orders_90d: "Orders, last 90 days",
};

export function evidenceLabel(key: string): string {
  return EVIDENCE_LABEL[key] ?? key.replaceAll("_", " ");
}

export function evidenceValue(key: string, value: string | number): string {
  if (typeof value === "string") return value;
  if (key.endsWith("_pct")) return `${value}%`;
  if (key.includes("revenue")) return rupees(value);
  return value.toLocaleString("en-IN");
}
