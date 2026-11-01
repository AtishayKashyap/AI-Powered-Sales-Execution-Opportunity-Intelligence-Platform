import type {
  ActionType,
  AnalyticsSummary,
  Explanation,
  OpportunityDetail,
  OpportunityPage,
  OpportunitySummary,
  OutcomeType,
} from "./types";

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${response.status})`;
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export interface ListParams {
  opportunity_type?: string;
  priority_band?: string;
  status?: string;
  q?: string;
  limit: number;
  offset: number;
}

export const api = {
  health: () => request<{ status: string; llm: string }>("/health"),
  queue: () => request<OpportunitySummary[]>("/opportunities/queue"),
  list: (params: ListParams) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") query.set(key, String(value));
    }
    return request<OpportunityPage>(`/opportunities?${query.toString()}`);
  },
  detail: (id: string) => request<OpportunityDetail>(`/opportunities/${encodeURIComponent(id)}`),
  explanation: (id: string) => request<Explanation>(`/opportunities/${encodeURIComponent(id)}/explanation`),
  recordAction: (id: string, action_type: ActionType, note?: string) =>
    request<OpportunityDetail>(`/opportunities/${encodeURIComponent(id)}/actions`, {
      method: "POST",
      body: JSON.stringify({ action_type, note: note || null }),
    }),
  recordOutcome: (actionId: number, outcome: OutcomeType, note?: string) =>
    request<OpportunityDetail>(`/actions/${actionId}/outcome`, {
      method: "PUT",
      body: JSON.stringify({ outcome, note: note || null }),
    }),
  analytics: () => request<AnalyticsSummary>("/analytics/summary"),
};
