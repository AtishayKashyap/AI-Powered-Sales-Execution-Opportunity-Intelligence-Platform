import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, Phone, Store, UserRound, X } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { OUTCOME_LABEL, dateTime, evidenceLabel, evidenceValue, rupees } from "../format";
import type { ActionType, OpportunityDetail as Detail, OutcomeType } from "../types";
import { PriorityBadge, StatusPill, TypeBadge } from "./Badges";
import { ExplanationCard } from "./ExplanationCard";

const OUTCOMES: OutcomeType[] = ["resolved", "follow_up", "no_response", "not_viable"];

function useRecord(opportunityId: string) {
  const client = useQueryClient();
  const onSuccess = (detail: Detail) => {
    client.setQueryData(["opportunity", opportunityId], detail);
    void client.invalidateQueries({ queryKey: ["queue"] });
    void client.invalidateQueries({ queryKey: ["opportunities"] });
    void client.invalidateQueries({ queryKey: ["analytics"] });
  };
  const action = useMutation({
    mutationFn: ({ type, note }: { type: ActionType; note: string }) => api.recordAction(opportunityId, type, note),
    onSuccess,
  });
  const outcome = useMutation({
    mutationFn: ({ actionId, value }: { actionId: number; value: OutcomeType }) => api.recordOutcome(actionId, value),
    onSuccess,
  });
  return { action, outcome };
}

export function OpportunityDetail({ opportunityId, onClose }: { opportunityId: string; onClose?: () => void }) {
  const { data: o, isPending, isError } = useQuery({
    queryKey: ["opportunity", opportunityId],
    queryFn: () => api.detail(opportunityId),
  });
  const { action, outcome } = useRecord(opportunityId);
  const [note, setNote] = useState("");

  if (isPending) return <aside className="detail skeleton" aria-busy="true" />;
  if (isError) return <aside className="detail">This opportunity could not be loaded.</aside>;

  const latest = o.actions.at(-1);
  const awaitingOutcome = latest !== undefined && latest.outcome === null;
  const error = action.error ?? outcome.error;

  return (
    <aside className="detail" aria-label={`Opportunity at ${o.outlet.outlet_name}`}>
      <header className="detailHeader">
        <div>
          <div className="badges">
            <TypeBadge type={o.opportunity_type} />
            <PriorityBadge band={o.priority_band} />
            <StatusPill status={o.status} />
          </div>
          <h2>{o.outlet.outlet_name}</h2>
          <p className="meta">
            <MapPin size={13} /> {o.outlet.city}, {o.outlet.territory} <Store size={13} /> {o.outlet.outlet_type} · tier{" "}
            {o.outlet.tier} <UserRound size={13} /> {o.outlet.rep.rep_name}
          </p>
        </div>
        {onClose && (
          <button className="iconButton" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        )}
      </header>

      <div className="stake">
        <div>
          <span>Revenue at stake / month</span>
          <strong>{rupees(o.value_at_stake)}</strong>
        </div>
        <div>
          <span>Priority score</span>
          <strong>{o.priority_score.toFixed(0)}</strong>
        </div>
      </div>

      <ExplanationCard opportunityId={o.opportunity_id} />

      <section aria-label="Evidence">
        <h3>Evidence</h3>
        <dl className="evidence">
          {Object.entries(o.evidence).map(([key, value]) => (
            <div key={key}>
              <dt>{evidenceLabel(key)}</dt>
              <dd>{evidenceValue(key, value)}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-label="Record work">
        <h3>{awaitingOutcome ? "How did it go?" : "Log a visit or call"}</h3>
        {awaitingOutcome ? (
          <div className="buttonRow">
            {OUTCOMES.map((value) => (
              <button
                key={value}
                className={value === "resolved" ? "primary" : "secondary"}
                disabled={outcome.isPending}
                onClick={() => outcome.mutate({ actionId: latest.action_id, value })}
              >
                {OUTCOME_LABEL[value]}
              </button>
            ))}
          </div>
        ) : (
          <>
            <textarea
              placeholder="Note (optional): who you met, what was agreed"
              maxLength={1000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              aria-label="Note"
            />
            <div className="buttonRow">
              {(["visit", "call"] as const).map((type) => (
                <button
                  key={type}
                  className={type === "visit" ? "primary" : "secondary"}
                  disabled={action.isPending}
                  onClick={() => action.mutate({ type, note }, { onSuccess: () => setNote("") })}
                >
                  {type === "visit" ? <Store size={14} /> : <Phone size={14} />}
                  {action.isPending && action.variables?.type === type ? "Saving…" : `Log ${type}`}
                </button>
              ))}
            </div>
          </>
        )}
        {error && (
          <p className="error" role="alert">
            {error.message}
          </p>
        )}
      </section>

      {o.actions.length > 0 && (
        <section aria-label="History">
          <h3>History</h3>
          <ol className="history">
            {[...o.actions].reverse().map((a) => (
              <li key={a.action_id}>
                <strong>{a.action_type === "visit" ? "Visit" : "Call"}</strong> · {dateTime(a.created_at)}
                {a.outcome && <span className={`outcome outcome-${a.outcome.outcome}`}>{OUTCOME_LABEL[a.outcome.outcome]}</span>}
                {a.note && <p>{a.note}</p>}
              </li>
            ))}
          </ol>
        </section>
      )}
    </aside>
  );
}
