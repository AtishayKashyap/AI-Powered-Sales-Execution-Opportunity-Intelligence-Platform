import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDollarSign, ListTodo, Target } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { PriorityBadge, StatusPill, TypeBadge } from "../components/Badges";
import { OpportunityDetail } from "../components/OpportunityDetail";
import { percent, rupeesShort } from "../format";

export function QueuePage() {
  const queue = useQuery({ queryKey: ["queue"], queryFn: api.queue });
  const analytics = useQuery({ queryKey: ["analytics"], queryFn: api.analytics });
  const [selected, setSelected] = useState<string | null>(null);
  const current = selected ?? queue.data?.[0]?.opportunity_id ?? null;
  const done = queue.data?.filter((o) => o.status === "resolved" || o.status === "closed").length ?? 0;

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Today's queue</p>
          <h1>Where to go next</h1>
          <p className="subtitle">
            {queue.data?.length ?? 20} highest-priority opportunities, at most one per outlet and a mix of types.
          </p>
        </div>
      </header>

      <div className="metrics">
        <Metric icon={<ListTodo size={17} />} label="In today's queue" value={queue.data ? `${done}/${queue.data.length} done` : "–"} />
        <Metric icon={<Target size={17} />} label="Opportunities detected" value={analytics.data?.opportunities.toLocaleString("en-IN") ?? "–"} />
        <Metric icon={<CircleDollarSign size={17} />} label="Revenue at stake / month" value={analytics.data ? rupeesShort(analytics.data.value_at_stake) : "–"} />
        <Metric icon={<CheckCircle2 size={17} />} label="Resolution rate" value={analytics.data ? percent(analytics.data.resolution_rate) : "–"} />
      </div>

      <div className="workspace">
        <section className="panel" aria-label="Queue">
          {queue.isPending && <p className="empty">Loading the queue…</p>}
          {queue.isError && <p className="empty error">The API is not reachable. On the free tier it can take up to a minute to wake up.</p>}
          <ol className="queue">
            {queue.data?.map((o) => (
              <li key={o.opportunity_id}>
                <button
                  className={o.opportunity_id === current ? "queueItem active" : "queueItem"}
                  onClick={() => setSelected(o.opportunity_id)}
                  aria-current={o.opportunity_id === current}
                >
                  <span className="rank">{o.queue_rank}</span>
                  <span className="queueMain">
                    <strong>{o.outlet.outlet_name}</strong>
                    <small>
                      {o.outlet.city} · {o.recommended_action}
                    </small>
                  </span>
                  <span className="queueSide">
                    <span className="badges">
                      <TypeBadge type={o.opportunity_type} />
                      <PriorityBadge band={o.priority_band} />
                    </span>
                    <span className="stakeSmall">{rupeesShort(o.value_at_stake)}/mo</span>
                    <StatusPill status={o.status} />
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>
        {current && <OpportunityDetail key={current} opportunityId={current} />}
      </div>
    </>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="metric">
      <span className="metricIcon">{icon}</span>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}
