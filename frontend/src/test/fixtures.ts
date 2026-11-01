import type { Explanation, OpportunityDetail } from "../types";

export const detail: OpportunityDetail = {
  opportunity_id: "OPP-00042",
  opportunity_type: "Inactive Outlet",
  priority_score: 91.2,
  priority_band: "P1",
  severity: 70,
  value_at_stake: 22096,
  queue_rank: 1,
  recommended_action: "Win-back visit",
  outlet: {
    outlet_id: "OUT-0008",
    outlet_name: "Sharma Kirana",
    outlet_type: "General Trade",
    tier: "A",
    city: "Pune",
    territory: "West 1",
    baseline_monthly_revenue: 22096,
    rep: { rep_id: "REP-001", rep_name: "Aarav Sharma", territory: "West 1" },
  },
  status: "open",
  evidence: { days_since_last_order: 49, baseline_monthly_orders: 7.7, baseline_monthly_revenue: 22096 },
  as_of: "2025-12-31",
  actions: [],
};

export const ruleBased: Explanation = {
  summary: "No order for 49 days from an outlet that used to order regularly.",
  why_it_matters: "It averaged 7.7 orders and ₹22,096 a month before it went quiet.",
  recommended_action: "Make a win-back visit.",
  evidence_used: ["days_since_last_order", "baseline_monthly_revenue"],
  source: "rule_based",
  model: null,
  note: "No language model is configured.",
};

type Route = [method: string, pattern: RegExp, body: unknown, status?: number];

/** Replace fetch with a router over [method, url pattern, response] entries; returns the recorded calls. */
export function mockFetch(routes: Route[]) {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    const route = routes.find(([m, p]) => m === method && p.test(url));
    if (!route) return new Response(JSON.stringify({ detail: "not mocked" }), { status: 500 });
    return new Response(JSON.stringify(route[2]), { status: route[3] ?? 200 });
  }) as typeof fetch;
  return calls;
}
