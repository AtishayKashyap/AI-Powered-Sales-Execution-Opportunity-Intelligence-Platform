import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { TypeBadge } from "../components/Badges";
import { OUTCOME_LABEL, date, percent, rupees } from "../format";
import type { OutcomeType } from "../types";

export function ExecutionPage() {
  const { data, isPending, isError } = useQuery({ queryKey: ["analytics"], queryFn: api.analytics });
  if (isPending) return <p className="empty">Loading…</p>;
  if (isError) return <p className="empty error">The API is not reachable right now.</p>;

  const outcomes = Object.entries(data.by_outcome) as [OutcomeType, number][];
  const totalOutcomes = outcomes.reduce((n, [, v]) => n + v, 0);

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Execution</p>
          <h1>What the field team has done</h1>
          <p className="subtitle">Data as of {data.as_of ? date(data.as_of) : "–"}. Each action counts once, with its latest outcome.</p>
        </div>
      </header>

      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th className="num">Opportunities</th>
              <th className="num">At stake / month</th>
              <th className="num">Actioned</th>
              <th className="num">Resolved</th>
              <th className="num">Resolution rate</th>
            </tr>
          </thead>
          <tbody>
            {data.by_type.map((t) => (
              <tr key={t.opportunity_type}>
                <td>
                  <TypeBadge type={t.opportunity_type} /> {t.opportunity_type}
                </td>
                <td className="num">{t.opportunities}</td>
                <td className="num">{rupees(t.value_at_stake)}</td>
                <td className="num">{t.actioned}</td>
                <td className="num">{t.resolved}</td>
                <td className="num">{percent(t.resolution_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div className="twoColumns">
        <section className="panel padded">
          <h3>Outcomes</h3>
          {totalOutcomes === 0 ? (
            <p className="muted">No outcomes recorded yet. Log a visit from the queue and record how it went.</p>
          ) : (
            <ul className="bars">
              {outcomes.map(([k, v]) => (
                <li key={k}>
                  <span>{OUTCOME_LABEL[k]}</span>
                  <span className="bar">
                    <span style={{ width: `${(100 * v) / totalOutcomes}%` }} />
                  </span>
                  <span className="num">{v}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="panel padded">
          <h3>Most active reps</h3>
          {data.top_reps.length === 0 ? (
            <p className="muted">Nobody has logged an action yet.</p>
          ) : (
            <ul className="reps">
              {data.top_reps.map((r) => (
                <li key={r.rep_id}>
                  <strong>{r.rep_name}</strong>
                  <span>
                    {r.actions} action{r.actions === 1 ? "" : "s"} · {r.resolved} resolved
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
