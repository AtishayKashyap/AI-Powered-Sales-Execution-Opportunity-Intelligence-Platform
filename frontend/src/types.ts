export type OpportunityType = "Revenue Recovery" | "Inactive Outlet" | "Stock Risk" | "Cross-Sell";
export type Status = "open" | "in_progress" | "resolved" | "closed";
export type ActionType = "visit" | "call";
export type OutcomeType = "resolved" | "follow_up" | "no_response" | "not_viable";

export interface Rep {
  rep_id: string;
  rep_name: string;
  territory: string;
}

export interface Outlet {
  outlet_id: string;
  outlet_name: string;
  outlet_type: string;
  tier: string;
  city: string;
  territory: string;
  baseline_monthly_revenue: number;
  rep: Rep;
}

export interface OpportunitySummary {
  opportunity_id: string;
  opportunity_type: OpportunityType;
  priority_score: number;
  priority_band: "P1" | "P2" | "P3";
  severity: number;
  value_at_stake: number;
  queue_rank: number | null;
  recommended_action: string;
  outlet: Outlet;
  status: Status;
}

export interface Action {
  action_id: number;
  rep_id: string;
  action_type: ActionType;
  note: string | null;
  created_at: string;
  outcome: { outcome: OutcomeType; note: string | null; recorded_at: string } | null;
}

export interface OpportunityDetail extends OpportunitySummary {
  evidence: Record<string, string | number>;
  as_of: string;
  actions: Action[];
}

export interface OpportunityPage {
  items: OpportunitySummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface Explanation {
  summary: string;
  why_it_matters: string;
  recommended_action: string;
  evidence_used: string[];
  source: "llm" | "rule_based";
  model: string | null;
  note: string | null;
}

export interface TypeStats {
  opportunity_type: OpportunityType;
  opportunities: number;
  actioned: number;
  resolved: number;
  resolution_rate: number | null;
  value_at_stake: number;
}

export interface AnalyticsSummary {
  as_of: string | null;
  opportunities: number;
  queue_size: number;
  value_at_stake: number;
  actioned: number;
  resolved: number;
  resolution_rate: number | null;
  by_type: TypeStats[];
  by_outcome: Partial<Record<OutcomeType, number>>;
  top_reps: { rep_id: string; rep_name: string; actions: number; resolved: number }[];
}
