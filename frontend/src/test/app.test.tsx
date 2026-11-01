import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { OpportunityDetail } from "../components/OpportunityDetail";
import { evidenceValue, rupeesShort } from "../format";
import { QueuePage } from "../pages/QueuePage";
import type { OpportunityDetail as Detail } from "../types";
import { detail, mockFetch, ruleBased } from "./fixtures";

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("formatting", () => {
  it("uses Indian units", () => {
    expect(rupeesShort(3_425_200)).toBe("₹34.3L");
    expect(rupeesShort(22_096)).toBe("₹22.1k");
    expect(evidenceValue("peer_adoption_pct", 96.1)).toBe("96.1%");
    expect(evidenceValue("baseline_monthly_revenue", 22096)).toBe("₹22,096");
  });
});

describe("opportunity detail", () => {
  it("shows the evidence and labels a rule-based explanation honestly", async () => {
    mockFetch([
      ["GET", /\/opportunities\/OPP-00042$/, detail],
      ["GET", /explanation$/, ruleBased],
    ]);
    wrap(<OpportunityDetail opportunityId="OPP-00042" />);
    expect(await screen.findByRole("heading", { name: "Sharma Kirana" })).toBeInTheDocument();
    expect(screen.getByText("Days since last order")).toBeInTheDocument();
    expect(await screen.findByText("Rule-based summary")).toBeInTheDocument();
    expect(screen.queryByText("evidence-checked")).not.toBeInTheDocument();
  });

  it("logs a visit, then asks for the outcome", async () => {
    const afterVisit: Detail = {
      ...detail,
      status: "in_progress",
      actions: [{ action_id: 7, rep_id: "REP-001", action_type: "visit", note: "met owner", created_at: "2026-01-02T10:00:00Z", outcome: null }],
    };
    const resolved: Detail = { ...afterVisit, status: "resolved", actions: [{ ...afterVisit.actions[0]!, outcome: { outcome: "resolved", note: null, recorded_at: "2026-01-02T11:00:00Z" } }] };
    const calls = mockFetch([
      ["GET", /\/opportunities\/OPP-00042$/, detail],
      ["GET", /explanation$/, ruleBased],
      ["POST", /\/opportunities\/OPP-00042\/actions$/, afterVisit, 201],
      ["PUT", /\/actions\/7\/outcome$/, resolved],
    ]);
    wrap(<OpportunityDetail opportunityId="OPP-00042" />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Note"), "met owner");
    await user.click(screen.getByRole("button", { name: /log visit/i }));
    await user.click(await screen.findByRole("button", { name: "Resolved" }));
    await waitFor(() => expect(screen.getAllByText("Resolved").length).toBeGreaterThan(0));
    expect(calls.filter((c) => c.method !== "GET")).toEqual([
      { method: "POST", url: expect.stringMatching(/actions$/), body: { action_type: "visit", note: "met owner" } },
      { method: "PUT", url: expect.stringMatching(/outcome$/), body: { outcome: "resolved", note: null } },
    ]);
  });

  it("shows API errors such as the rate limit", async () => {
    mockFetch([
      ["GET", /\/opportunities\/OPP-00042$/, detail],
      ["GET", /explanation$/, ruleBased],
      ["POST", /actions$/, { detail: "Too many write requests; try again shortly." }, 429],
    ]);
    wrap(<OpportunityDetail opportunityId="OPP-00042" />);
    await userEvent.click(await screen.findByRole("button", { name: /log call/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many write requests");
  });
});

describe("queue page", () => {
  it("explains a sleeping API instead of showing a blank page", async () => {
    mockFetch([]);
    wrap(<QueuePage />);
    expect(await screen.findByText(/can take up to a minute to wake up/)).toBeInTheDocument();
  });

  it("lists the queue and opens the first opportunity", async () => {
    mockFetch([
      ["GET", /\/opportunities\/queue$/, [detail]],
      ["GET", /\/analytics\/summary$/, { as_of: "2025-12-31", opportunities: 396, queue_size: 20, value_at_stake: 3425200, actioned: 0, resolved: 0, resolution_rate: null, by_type: [], by_outcome: {}, top_reps: [] }],
      ["GET", /\/opportunities\/OPP-00042$/, detail],
      ["GET", /explanation$/, ruleBased],
    ]);
    wrap(<QueuePage />);
    expect(await screen.findByText("₹34.3L")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Sharma Kirana" })).toBeInTheDocument();
  });
});
