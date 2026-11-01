import { useQuery } from "@tanstack/react-query";
import { Bot, ListChecks } from "lucide-react";
import { api } from "../api";
import { evidenceLabel } from "../format";

export function ExplanationCard({ opportunityId }: { opportunityId: string }) {
  const { data, isPending, isError } = useQuery({
    queryKey: ["explanation", opportunityId],
    queryFn: () => api.explanation(opportunityId),
    staleTime: Infinity,
  });

  if (isPending) return <div className="explanation skeleton" aria-busy="true" />;
  if (isError) return <p className="muted">The explanation could not be loaded.</p>;

  const isLlm = data.source === "llm";
  return (
    <section className="explanation" aria-label="Explanation">
      <header>
        {isLlm ? <Bot size={15} /> : <ListChecks size={15} />}
        <span>{isLlm ? `Explained by ${data.model}` : "Rule-based summary"}</span>
        {isLlm && <span className="verified" title="Every number was checked against the evidence">evidence-checked</span>}
      </header>
      <p className="summary">{data.summary}</p>
      <p>{data.why_it_matters}</p>
      <p className="next">
        <strong>Next step:</strong> {data.recommended_action}
      </p>
      <footer>
        Based on: {data.evidence_used.map(evidenceLabel).join(", ")}
        {data.note && <span className="note">{data.note}</span>}
      </footer>
    </section>
  );
}
