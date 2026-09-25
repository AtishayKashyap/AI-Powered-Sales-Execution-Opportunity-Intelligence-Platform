import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bell,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Filter,
  LayoutDashboard,
  PackageCheck,
  Search,
  Sparkles,
  Store,
  Target,
  TrendingDown,
  Users,
  X,
} from "lucide-react";

type Evidence = Record<string, unknown>;

type Opportunity = {
  opportunity_id: string;
  outlet_id: string;
  opportunity_type: string;
  score: number;
  priority?: string;
  evidence: Evidence;
  recommended_action?: string;
};

type ExecutionSummary = {
  total_opportunities: number;
  total_actions: number;
  total_outcomes: number;
  contacted: number;
  resolved: number;
  resolution_rate: number;
};

type ActionResponse = {
  status: string;
  action: {
    action_id: number;
    opportunity_id: string;
    outlet_id: string;
    action_type: string;
    rep_id?: string;
    note?: string;
  };
};

type AIExplanation = {
  opportunity_id: string;
  summary: string;
  why_it_matters: string;
  recommended_action: string;
  evidence_used: string[];
  confidence: "high" | "medium" | "low";
  provider: string;
  model: string;
};

type Page = "command" | "outlets" | "opportunities" | "team";

type OutcomeLearning = {
  overall: {
    actions: number;
    outcomes: number;
    resolved: number;
    resolution_rate: number;
  };
  by_opportunity_type: Array<{
    opportunity_type: string;
    actions: number;
    outcomes: number;
    resolved: number;
    resolution_rate: number;
  }>;
  by_action_type: Array<{
    action_type: string;
    actions: number;
    outcomes: number;
    resolved: number;
    resolution_rate: number;
  }>;
  learning_status: "insufficient_data" | "feedback_available";
  minimum_outcomes_for_feedback: number;
};

const API =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function money(v: unknown) {
  const n = Number(v);

  return Number.isFinite(n)
    ? `₹${n.toLocaleString("en-IN", {
        maximumFractionDigits: 0,
      })}`
    : "—";
}

function pct(v: unknown) {
  const n = Number(v);

  return Number.isFinite(n)
    ? `${(n * 100).toFixed(1)}%`
    : "—";
}

function label(type: string) {
  return type.replace("Outlet", "").trim();
}

function typeIcon(type: string) {
  if (type.includes("Revenue")) {
    return <TrendingDown size={16} />;
  }

  if (type.includes("Stock")) {
    return <PackageCheck size={16} />;
  }

  if (type.includes("Inactive")) {
    return <Store size={16} />;
  }

  return <Target size={16} />;
}

function priorityClass(priority?: string) {
  if (priority === "HIGH") {
    return "priorityHigh";
  }

  if (priority === "MEDIUM") {
    return "priorityMedium";
  }

  return "priorityLow";
}

function App() {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [selected, setSelected] =
    useState<Opportunity | null>(null);

  const [activePage, setActivePage] =
    useState<Page>("command");

  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");

  const [loading, setLoading] = useState(true);
  const [apiLive, setApiLive] = useState(false);

  const [analytics, setAnalytics] =
    useState<ExecutionSummary>({
      total_opportunities: 0,
      total_actions: 0,
      total_outcomes: 0,
      contacted: 0,
      resolved: 0,
      resolution_rate: 0,
    });

  const [learning, setLearning] =
    useState<OutcomeLearning>({
      overall: {
        actions: 0,
        outcomes: 0,
        resolved: 0,
        resolution_rate: 0,
      },
      by_opportunity_type: [],
      by_action_type: [],
      learning_status: "insufficient_data",
      minimum_outcomes_for_feedback: 10,
    });

  const [actionId, setActionId] =
    useState<number | null>(null);

  const [actionLoading, setActionLoading] =
    useState(false);

  const [outcomeLoading, setOutcomeLoading] =
    useState(false);

  const [outcome, setOutcome] = useState("");

  const [repNote, setRepNote] = useState("");

  // Real AI explanation state
  const [aiExplanation, setAiExplanation] =
    useState<AIExplanation | null>(null);

  const [aiLoading, setAiLoading] = useState(false);

  const [aiError, setAiError] = useState("");

  async function loadData() {
    setLoading(true);

    try {
      const [
        opportunityResponse,
        analyticsResponse,
        learningResponse,
      ] = await Promise.all([
        fetch(`${API}/opportunities/top?limit=20`),
        fetch(`${API}/analytics/execution-summary`),
        fetch(`${API}/analytics/outcome-learning`),
      ]);

      if (
        !opportunityResponse.ok ||
        !analyticsResponse.ok
      ) {
        throw new Error("API unavailable");
      }

      const opportunityData =
        await opportunityResponse.json();

      const analyticsData =
        await analyticsResponse.json();

      const learningData = learningResponse.ok
        ? await learningResponse.json()
        : null;

      setItems(opportunityData.items || []);
      setAnalytics(analyticsData);
      if (learningData) {
        setLearning(learningData);
      }
      setApiLive(true);
    } catch {
      setApiLive(false);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const filtered = useMemo(() => {
    return items.filter((item) => {
      const typeOK =
        filter === "All" ||
        item.opportunity_type === filter;

      const q = query.toLowerCase();

      const searchOK =
        !q ||
        item.outlet_id.toLowerCase().includes(q) ||
        item.opportunity_type
          .toLowerCase()
          .includes(q) ||
        item.opportunity_id
          .toLowerCase()
          .includes(q);

      return typeOK && searchOK;
    });
  }, [items, filter, query]);

  const counts = useMemo(
    () => ({
      total: items.length,

      revenue: items.filter(
        (x) =>
          x.opportunity_type ===
          "Revenue Recovery"
      ).length,

      stock: items.filter(
        (x) =>
          x.opportunity_type === "Stock Risk"
      ).length,

      inactive: items.filter(
        (x) =>
          x.opportunity_type ===
          "Inactive Outlet"
      ).length,

      cross: items.filter(
        (x) =>
          x.opportunity_type === "Cross-Sell"
      ).length,
    }),
    [items]
  );

  async function loadAIExplanation(
    opportunityId: string
  ) {
    setAiLoading(true);
    setAiError("");
    setAiExplanation(null);

    try {
      const response = await fetch(
        `${API}/ai/opportunities/${opportunityId}/explain`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
          errorText || "AI explanation failed"
        );
      }

      const data: AIExplanation =
        await response.json();

      setAiExplanation(data);
    } catch (error) {
      console.error(
        "AI explanation error:",
        error
      );

      setAiError(
        "Unable to generate the AI explanation. Make sure Ollama and the API are running."
      );
    } finally {
      setAiLoading(false);
    }
  }

  async function createAction() {
    if (!selected) return;

    setActionLoading(true);

    try {
      const response = await fetch(
        `${API}/opportunities/${selected.opportunity_id}/actions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            action_type: "outlet_visit",
            rep_id: "REP-001",
            note:
              repNote ||
              `Planned field action for ${selected.opportunity_type}.`,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          "Failed to create action"
        );
      }

      const data: ActionResponse = await response.json();

      setActionId(data.action.action_id);
      setRepNote(data.action.note || "");

      // Refresh execution metrics immediately.
      await loadData();
    } catch (error) {
      console.error(error);

      alert(
        "Unable to record the action. Check that the API is running."
      );
    } finally {
      setActionLoading(false);
    }
  }

  async function recordOutcome(value: string) {
    if (!selected || !actionId) return;

    setOutcomeLoading(true);

    try {
      const response = await fetch(
        `${API}/opportunities/${selected.opportunity_id}/actions/${actionId}/outcome`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            outcome: value,
            note: repNote || undefined,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          "Failed to record outcome"
        );
      }

      setOutcome(value);

      await loadData();
    } catch (error) {
      console.error(error);

      alert(
        "Unable to record the outcome."
      );
    } finally {
      setOutcomeLoading(false);
    }
  }

  async function selectOpportunity(item: Opportunity) {
    setSelected(item);

    // Reset per-opportunity execution state before loading the saved state.
    setOutcome("");
    setActionId(null);
    setRepNote("");

    // Never show the previous outlet's AI explanation while the new one loads.
    setAiExplanation(null);
    setAiError("");

    // AI explanations are cache-first on the backend, so this is cheap for
    // opportunities that have already been explained.
    void loadAIExplanation(item.opportunity_id);

    try {
      const response = await fetch(
        `${API}/opportunities/${item.opportunity_id}/execution-state`
      );

      if (!response.ok) {
        throw new Error("Failed to load execution state");
      }

      const data = await response.json();

      if (data.action) {
        setActionId(data.action.action_id);
        setRepNote(data.action.note || "");
      }

      if (data.outcome) {
        setOutcome(data.outcome.outcome);
      }
    } catch (error) {
      console.error("Unable to load execution state:", error);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <Activity size={20} />
          </div>

          <div>
            <strong>SalesForge</strong>
            <span>
              Sales execution copilot
            </span>
          </div>
        </div>

        <nav>
          <button
            className={`nav ${activePage === "command" ? "active" : ""}`}
            onClick={() => {
              setActivePage("command");
              setSelected(null);
            }}
          >
            <LayoutDashboard size={17} />
            Command Center
          </button>

          <button
            className={`nav ${activePage === "outlets" ? "active" : ""}`}
            onClick={() => {
              setActivePage("outlets");
              setSelected(null);
            }}
          >
            <Store size={17} />
            Outlets
          </button>

          <button
            className={`nav ${activePage === "opportunities" ? "active" : ""}`}
            onClick={() => setActivePage("opportunities")}
          >
            <Target size={17} />
            Opportunities
          </button>

          <button
            className={`nav ${activePage === "team" ? "active" : ""}`}
            onClick={() => setActivePage("team")}
          >
            <Users size={17} />
            Team
          </button>
        </nav>

        <div className="sidebarBottom">
          <div
            className={`apiStatus ${
              apiLive ? "live" : ""
            }`}
          >
            <span />
            {apiLive
              ? "API connected"
              : "API unavailable"}
          </div>

          <div className="user">
            <div className="avatar">AK</div>

            <div>
              <b>Sales Rep</b>
              <small>CPG Field Team</small>
            </div>
          </div>
        </div>
      </aside>

      <main>
        {activePage === "command" ? (
          <>
        <header className="topbar">
          <div>
            <p className="eyebrow">
              FIELD SALES / AS OF 31 DEC 2025
            </p>

            <h1>Command Center</h1>

            <p className="subtitle">
              Your highest-value actions,
              ranked by SalesForge.
            </p>
          </div>

          <div className="topActions">
            <button className="iconBtn">
              <Bell size={18} />
            </button>

            <div className="date">
              DATA AS OF � 31 DEC 2025
            </div>
          </div>
        </header>

        <section className="metrics">
          <Metric
            icon={<CircleDollarSign />}
            label="Revenue recovery"
            value={counts.revenue}
            hint="priority actions"
          />

          <Metric
            icon={<PackageCheck />}
            label="Stock risk"
            value={counts.stock}
            hint="outlets flagged"
          />

          <Metric
            icon={<Store />}
            label="Inactive outlets"
            value={counts.inactive}
            hint="win-back actions"
          />

          <Metric
            icon={<Target />}
            label="Cross-sell"
            value={counts.cross}
            hint="assortment gaps"
          />
        </section>

        <section className="executionBar">
          <div>
            <span>EXECUTION</span>
            <strong>
              {analytics.total_actions}
            </strong>
            <small>actions taken</small>
          </div>

          <div>
            <span>OUTCOMES</span>
            <strong>
              {analytics.total_outcomes}
            </strong>
            <small>recorded</small>
          </div>

          <div>
            <span>RESOLVED</span>
            <strong>
              {analytics.resolved}
            </strong>
            <small>opportunities</small>
          </div>

          <div>
            <span>RESOLUTION RATE</span>
            <strong>
              {(
                analytics.resolution_rate *
                100
              ).toFixed(0)}
              %
            </strong>
            <small>
              of recorded outcomes
            </small>
          </div>
        </section>

        <section className="learningPanel">
          <div className="learningHeader">
            <div>
              <p className="eyebrow">OUTCOME LEARNING</p>
              <h2>Execution feedback</h2>
              <span>Observed field outcomes are tracked before any learning logic is activated.</span>
            </div>
            <div className={`learningBadge ${learning.learning_status === "feedback_available" ? "ready" : "waiting"}`}>
              {learning.learning_status === "feedback_available" ? "FEEDBACK AVAILABLE" : "INSUFFICIENT DATA"}
            </div>
          </div>

          <div className="learningStats">
            <div><span>Resolution rate</span><strong>{(learning.overall.resolution_rate * 100).toFixed(0)}%</strong></div>
            <div><span>Outcomes recorded</span><strong>{learning.overall.outcomes}</strong></div>
            <div><span>Resolved</span><strong>{learning.overall.resolved}</strong></div>
            <div><span>Feedback threshold</span><strong>{learning.minimum_outcomes_for_feedback}</strong></div>
          </div>

          <div className="learningNote">
            {learning.learning_status === "feedback_available"
              ? "Sufficient outcome history is available for the next feedback-learning stage. Detection and priority scores are still unchanged."
              : `${Math.max(learning.minimum_outcomes_for_feedback - learning.overall.outcomes, 0)} more outcome${Math.max(learning.minimum_outcomes_for_feedback - learning.overall.outcomes, 0) === 1 ? "" : "s"} required before feedback learning becomes available.`}
          </div>
        </section>

        <section className="workspace">
          <div className="queuePanel">
            <div className="queueHeader">
              <div>
                <h2>Action queue</h2>

                <span>
                  {counts.total} prioritized
                  opportunities
                </span>
              </div>

              <div className="tools">
                <div className="search">
                  <Search size={16} />

                  <input
                    value={query}
                    onChange={(e) =>
                      setQuery(e.target.value)
                    }
                    placeholder="Search outlet..."
                  />
                </div>

                <button className="filterBtn">
                  <Filter size={15} />
                  Filter
                </button>
              </div>
            </div>

            <div className="filters">
              {[
                "All",
                "Revenue Recovery",
                "Inactive Outlet",
                "Stock Risk",
                "Cross-Sell",
              ].map((x) => (
                <button
                  key={x}
                  onClick={() => setFilter(x)}
                  className={
                    filter === x
                      ? "chip selected"
                      : "chip"
                  }
                >
                  {x === "All"
                    ? "All"
                    : label(x)}
                </button>
              ))}
            </div>

            <div className="queue">
              {loading ? (
                <div className="empty">
                  Loading SalesForge
                  opportunities…
                </div>
              ) : filtered.length === 0 ? (
                <div className="empty">
                  No opportunities match
                  this filter.
                </div>
              ) : (
                filtered.map(
                  (item, index) => (
                    <button
                      className={`opportunity ${
                        selected?.opportunity_id ===
                        item.opportunity_id
                          ? "selectedRow"
                          : ""
                      }`}
                      key={
                        item.opportunity_id
                      }
                      onClick={() =>
                        selectOpportunity(
                          item
                        )
                      }
                    >
                      <div className="rank">
                        {String(
                          index + 1
                        ).padStart(2, "0")}
                      </div>

                      <div className="typeIcon">
                        {typeIcon(
                          item.opportunity_type
                        )}
                      </div>

                      <div className="oppMain">
                        <div className="oppTitle">
                          {label(
                            item.opportunity_type
                          )}
                        </div>

                        <div className="oppMeta">
                          Outlet{" "}
                          {item.outlet_id} ·{" "}
                          <span
                            className={priorityClass(
                              item.priority
                            )}
                          >
                            {item.priority ||
                              "—"}
                          </span>
                        </div>
                      </div>

                      <div className="score">
                        <b>
                          {Number(
                            item.score
                          ).toFixed(0)}
                        </b>

                        <span>score</span>
                      </div>

                      <ChevronRight
                        size={17}
                        className="chevron"
                      />
                    </button>
                  )
                )
              )}
            </div>
          </div>

          <aside className="detail">
            {selected ? (
              <>
                <div className="detailTop">
                  <div className="detailBadge">
                    {typeIcon(
                      selected.opportunity_type
                    )}

                    {label(
                      selected.opportunity_type
                    )}
                  </div>

                  <button
                    className="close"
                    onClick={() => {
                      setSelected(null);
                      setAiExplanation(null);
                      setAiError("");
                      setAiLoading(false);
                      setActionId(null);
                      setOutcome("");
                      setRepNote("");
                    }}
                  >
                    <X size={18} />
                  </button>
                </div>

                <h2>
                  Outlet {selected.outlet_id}
                </h2>

                <div className="priorityLine">
                  <span
                    className={`priorityBadge ${priorityClass(
                      selected.priority
                    )}`}
                  >
                    {selected.priority ||
                      "—"}
                  </span>

                  <span>
                    SalesForge score{" "}
                    <b>
                      {Number(
                        selected.score
                      ).toFixed(0)}
                    </b>
                  </span>
                </div>

                <div className="aiCard">
                  <div className="aiTitle">
                    <Sparkles size={17} />

                    SalesForge explanation

                    <span>
                      {aiLoading
                        ? "GENERATING"
                        : "AI"}
                    </span>
                  </div>

                  {aiLoading ? (
                    <div className="aiLoading">
                      Generating a grounded
                      explanation...
                    </div>
                  ) : aiError ? (
                    <div className="aiError">
                      {aiError}
                    </div>
                  ) : aiExplanation ? (
                    <>
                      <p className="aiSummary">
                        {aiExplanation.summary}
                      </p>

                      <div className="aiWhy">
                        <b>
                          Why it matters
                        </b>

                        <span>
                          {
                            aiExplanation.why_it_matters
                          }
                        </span>
                      </div>

                      <div className="aiAction">
                        <b>
                          Recommended action
                        </b>

                        <span>
                          {
                            aiExplanation.recommended_action
                          }
                        </span>
                      </div>

                      <div className="aiEvidence">
                        <b>
                          AI evidence used
                        </b>

                        <ul>
                          {aiExplanation.evidence_used.map(
                            (
                              evidence,
                              index
                            ) => (
                              <li
                                key={
                                  index
                                }
                              >
                                {evidence}
                              </li>
                            )
                          )}
                        </ul>
                      </div>

                      <div className="aiMeta">
                        <span>
                          Confidence:{" "}
                          <b>
                            {
                              aiExplanation.confidence
                            }
                          </b>
                        </span>

                        <span>
                          {
                            aiExplanation.provider
                          }{" "}
                          ·{" "}
                          {
                            aiExplanation.model
                          }
                        </span>
                      </div>
                    </>
                  ) : (
                    <div className="aiLoading">
                      Select an opportunity
                      to generate an
                      explanation.
                    </div>
                  )}
                </div>

                <h3>Evidence</h3>

                <div className="evidenceGrid">
                  {Object.entries(
                    selected.evidence
                  )
                    .slice(0, 8)
                    .map(
                      ([key, value]) => (
                        <div
                          className="evidence"
                          key={key}
                        >
                          <span>
                            {key.replaceAll(
                              "_",
                              " "
                            )}
                          </span>

                          <b>
                            {typeof value ===
                            "number"
                              ? value.toLocaleString(
                                  "en-IN",
                                  {
                                    maximumFractionDigits: 2,
                                  }
                                )
                              : String(value)}
                          </b>
                        </div>
                      )
                    )}
                </div>

                <h3>Field action</h3>

                <textarea
                  className="repNote"
                  value={repNote}
                  onChange={(e) =>
                    setRepNote(e.target.value)
                  }
                  placeholder="Add a field note..."
                  disabled={actionLoading || !!actionId}
                />

                {!actionId ? (
                  <button
                    className="primaryAction"
                    disabled={actionLoading}
                    onClick={createAction}
                  >
                    {actionLoading
                      ? "Recording action..."
                      : "Record outlet visit"}
                  </button>
                ) : (
                  <div className="actionRecorded">
                    <CheckCircle2 size={16} />
                    <div>
                      <b>Field action recorded</b>
                      <span>Action #{actionId}</span>
                    </div>
                  </div>
                )}

                <h3>Outcome</h3>

                <div className="outcomes">
                  {[
                    "contacted",
                    "resolved",
                    "snoozed",
                    "no_response",
                  ].map((x) => (
                    <button
                      key={x}
                      disabled={!actionId || outcomeLoading}
                      className={
                        outcome === x
                          ? "outcome active"
                          : "outcome"
                      }
                      onClick={() =>
                        recordOutcome(x)
                      }
                    >
                      <CheckCircle2 size={15} />

                      {outcomeLoading && outcome === x
                        ? "Saving..."
                        : x.replace("_", " ")}
                    </button>
                  ))}
                </div>

                {!actionId && (
                  <div className="saved">
                    Record the field action before
                    selecting an outcome.
                  </div>
                )}

                {actionId && !outcome && !outcomeLoading && (
                  <div className="saved">
                    Select the outcome after the outlet
                    visit.
                  </div>
                )}

                {outcome && !outcomeLoading && (
                  <div className="saved success">
                    <CheckCircle2 size={14} />
                    Outcome recorded: <b>{outcome.replace("_", " ")}</b>
                  </div>
                )}
              </>
            ) : (
              <div className="detailEmpty">
                <Sparkles size={25} />

                <h3>
                  Select an opportunity
                </h3>

                <p>
                  SalesForge will show the
                  evidence, explanation,
                  and next action here.
                </p>
              </div>
            )}
          </aside>
        </section>
          </>
        ) : activePage === "outlets" ? (
          <OutletsPage items={items} />
        ) : activePage === "opportunities" ? (
          <OpportunitiesPage
            items={items}
            filtered={filtered}
            filter={filter}
            setFilter={setFilter}
            query={query}
            setQuery={setQuery}
            onSelect={(item) => {
              setActivePage("command");
              selectOpportunity(item);
            }}
          />
        ) : (
          <TeamPage analytics={analytics} learning={learning} />
        )}
      </main>
    </div>
  );
}

function OutletsPage({ items }: { items: Opportunity[] }) {
  const outlets = useMemo(() => {
    const grouped = new Map<string, Opportunity[]>();
    items.forEach((item) => {
      const existing = grouped.get(item.outlet_id) || [];
      existing.push(item);
      grouped.set(item.outlet_id, existing);
    });
    return Array.from(grouped.entries()).map(([outlet_id, opportunities]) => ({
      outlet_id,
      opportunities,
    }));
  }, [items]);

  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">FIELD SALES / OUTLETS</p>
          <h1>Outlets</h1>
          <p className="subtitle">Prioritized outlets surfaced by the current SalesForge action queue.</p>
        </div>
      </header>

      <section className="pageIntro">
        <div><strong>{outlets.length}</strong><span>outlets in current queue</span></div>
        <div><strong>{items.length}</strong><span>active opportunities</span></div>
      </section>

      <section className="outletGrid">
        {outlets.map(({ outlet_id, opportunities }) => (
          <div className="outletCard" key={outlet_id}>
            <div className="outletCardTop">
              <div className="outletIcon"><Store size={17} /></div>
              <span>{opportunities.length} opportunit{opportunities.length === 1 ? "y" : "ies"}</span>
            </div>
            <h2>Outlet {outlet_id}</h2>
            <div className="outletTypes">
              {opportunities.map((x) => (
                <span key={x.opportunity_id} className={`miniPriority ${priorityClass(x.priority)}`}>
                  {label(x.opportunity_type)} · {Number(x.score).toFixed(0)}
                </span>
              ))}
            </div>
          </div>
        ))}
      </section>
    </>
  );
}

function OpportunitiesPage({
  items,
  filtered,
  filter,
  setFilter,
  query,
  setQuery,
  onSelect,
}: {
  items: Opportunity[];
  filtered: Opportunity[];
  filter: string;
  setFilter: (value: string) => void;
  query: string;
  setQuery: (value: string) => void;
  onSelect: (item: Opportunity) => void;
}) {
  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">FIELD SALES / OPPORTUNITIES</p>
          <h1>Opportunity Explorer</h1>
          <p className="subtitle">Inspect prioritized opportunities and open any one in the execution workspace.</p>
        </div>
      </header>

      <section className="explorerBar">
        <div className="search"><Search size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search outlet or opportunity..." /></div>
        <div className="filters">
          {["All", "Revenue Recovery", "Inactive Outlet", "Stock Risk", "Cross-Sell"].map((x) => (
            <button key={x} onClick={() => setFilter(x)} className={filter === x ? "chip selected" : "chip"}>
              {x === "All" ? "All" : label(x)}
            </button>
          ))}
        </div>
      </section>

      <section className="opportunityTable">
        <div className="tableHeader"><span>OPPORTUNITY</span><span>OUTLET</span><span>PRIORITY</span><span>SCORE</span></div>
        {filtered.map((item) => (
          <button className="tableRow" key={item.opportunity_id} onClick={() => onSelect(item)}>
            <span className="tableOpportunity">{typeIcon(item.opportunity_type)} {label(item.opportunity_type)}</span>
            <span>Outlet {item.outlet_id}</span>
            <span className={priorityClass(item.priority)}>{item.priority || "—"}</span>
            <strong>{Number(item.score).toFixed(0)}</strong>
          </button>
        ))}
        {!filtered.length && <div className="empty">No opportunities match this filter.</div>}
      </section>
      <div className="pageFootnote">Showing {filtered.length} of {items.length} prioritized opportunities.</div>
    </>
  );
}

function TeamPage({ analytics, learning }: { analytics: ExecutionSummary; learning: OutcomeLearning }) {
  const rate = analytics.resolution_rate * 100;
  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">FIELD SALES / TEAM</p>
          <h1>Team execution</h1>
          <p className="subtitle">Execution activity and outcome feedback for the current field-sales team.</p>
        </div>
      </header>

      <section className="teamHero">
        <div className="avatar large">AK</div>
        <div><span>REP-001</span><h2>Sales Rep</h2><p>CPG Field Team</p></div>
      </section>

      <section className="teamStats">
        <div><span>Actions taken</span><strong>{analytics.total_actions}</strong></div>
        <div><span>Outcomes recorded</span><strong>{analytics.total_outcomes}</strong></div>
        <div><span>Resolved</span><strong>{analytics.resolved}</strong></div>
        <div><span>Resolution rate</span><strong>{rate.toFixed(0)}%</strong></div>
      </section>

      <section className="teamPanel">
        <div><p className="eyebrow">FEEDBACK STATUS</p><h2>{learning.learning_status === "feedback_available" ? "Feedback available" : "Collecting outcome history"}</h2></div>
        <div className="teamProgress"><span style={{ width: `${Math.min((learning.overall.outcomes / learning.minimum_outcomes_for_feedback) * 100, 100)}%` }} /></div>
        <p>{learning.overall.outcomes} of {learning.minimum_outcomes_for_feedback} outcomes recorded. Feedback learning remains observational until the threshold is reached.</p>
      </section>
    </>
  );
}

function Metric({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  hint: string;
}) {
  return (
    <div className="metric">
      <div className="metricIcon">
        {icon}
      </div>

      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{hint}</small>
      </div>

      <ArrowUpRight
        size={16}
        className="metricArrow"
      />
    </div>
  );
}

export default App;
