import type { TrackerStatus } from "../api/types";

const labels: Record<TrackerStatus, string> = {
  found: "Found",
  prepared: "Prepared",
  reviewed: "Reviewed",
  submitted: "Submitted",
  rejected: "Rejected",
  interview: "Interview",
  assessment: "Assessment",
  offer: "Offer",
  ghosted: "Ghosted",
  archived: "Archived"
};

export default function StatusBadge({ status }: { status: TrackerStatus }) {
  return <span className={`status-badge status-${status}`}>{labels[status]}</span>;
}
