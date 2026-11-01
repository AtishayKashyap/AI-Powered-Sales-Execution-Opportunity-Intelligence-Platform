import type { OpportunitySummary, Status } from "../types";
import { STATUS_LABEL, TYPE_SHORT } from "../format";

export function PriorityBadge({ band }: { band: OpportunitySummary["priority_band"] }) {
  return <span className={`badge band-${band}`}>{band}</span>;
}

export function TypeBadge({ type }: { type: OpportunitySummary["opportunity_type"] }) {
  const slug = type.toLowerCase().replace(/[^a-z]+/g, "-");
  return <span className={`badge type type-${slug}`}>{TYPE_SHORT[type]}</span>;
}

export function StatusPill({ status }: { status: Status }) {
  return <span className={`status status-${status}`}>{STATUS_LABEL[status]}</span>;
}
