import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { api } from "../api";
import { PriorityBadge, StatusPill, TypeBadge } from "../components/Badges";
import { OpportunityDetail } from "../components/OpportunityDetail";
import { rupees } from "../format";

const PAGE = 25;
const TYPES = ["Revenue Recovery", "Inactive Outlet", "Stock Risk", "Cross-Sell"];

export function OpportunitiesPage() {
  const [type, setType] = useState("");
  const [band, setBand] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const q = useDeferredValue(search.trim());
  const params = { opportunity_type: type, priority_band: band, status, q, limit: PAGE, offset };
  const page = useQuery({ queryKey: ["opportunities", params], queryFn: () => api.list(params), placeholderData: keepPreviousData });

  const reset = <T,>(set: (v: T) => void) => (v: T) => {
    set(v);
    setOffset(0);
  };

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">All opportunities</p>
          <h1>Every detected opportunity</h1>
          <p className="subtitle">Sorted by priority. Filter, search by outlet or city, and open one to act on it.</p>
        </div>
      </header>

      <div className="filters" role="search">
        <label className="searchBox">
          <Search size={15} />
          <input placeholder="Outlet, city or id" value={search} onChange={(e) => reset(setSearch)(e.target.value)} aria-label="Search" />
        </label>
        <select value={type} onChange={(e) => reset(setType)(e.target.value)} aria-label="Type">
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <select value={band} onChange={(e) => reset(setBand)(e.target.value)} aria-label="Priority">
          <option value="">All priorities</option>
          <option>P1</option>
          <option>P2</option>
          <option>P3</option>
        </select>
        <select value={status} onChange={(e) => reset(setStatus)(e.target.value)} aria-label="Status">
          <option value="">Any status</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      <div className={selected ? "workspace" : ""}>
        <section className="panel tablePanel">
          <table>
            <thead>
              <tr>
                <th>Outlet</th>
                <th>Type</th>
                <th>Priority</th>
                <th className="num">At stake / month</th>
                <th>Rep</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {page.data?.items.map((o) => (
                <tr
                  key={o.opportunity_id}
                  className={o.opportunity_id === selected ? "active" : ""}
                  onClick={() => setSelected(o.opportunity_id)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && setSelected(o.opportunity_id)}
                >
                  <td>
                    <strong>{o.outlet.outlet_name}</strong>
                    <small>{o.outlet.city}</small>
                  </td>
                  <td>
                    <TypeBadge type={o.opportunity_type} />
                  </td>
                  <td>
                    <PriorityBadge band={o.priority_band} /> <small className="inline">{o.priority_score.toFixed(0)}</small>
                  </td>
                  <td className="num">{rupees(o.value_at_stake)}</td>
                  <td>{o.outlet.rep.rep_name}</td>
                  <td>
                    <StatusPill status={o.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {page.data?.items.length === 0 && <p className="empty">No opportunities match these filters.</p>}
          {page.isError && <p className="empty error">The API is not reachable right now.</p>}
          <footer className="pager">
            <span>
              {page.data ? `${page.data.total === 0 ? 0 : offset + 1}–${Math.min(offset + PAGE, page.data.total)} of ${page.data.total}` : "…"}
            </span>
            <button className="secondary" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
              Previous
            </button>
            <button className="secondary" disabled={!page.data || offset + PAGE >= page.data.total} onClick={() => setOffset(offset + PAGE)}>
              Next
            </button>
          </footer>
        </section>
        {selected && <OpportunityDetail key={selected} opportunityId={selected} onClose={() => setSelected(null)} />}
      </div>
    </>
  );
}
