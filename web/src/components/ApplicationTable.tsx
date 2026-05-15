import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { TrackerEntry } from "../api/types";
import StatusBadge from "./StatusBadge";

type SortKey = "company" | "role" | "status" | "fit_score" | "date_updated" | "starred";
type SortDir = "asc" | "desc";

interface Props {
  applications: TrackerEntry[];
  selectedIds: Set<string>;
  onSelectionChange: (next: Set<string>) => void;
  onToggleStar: (jobId: string, starred: boolean) => void;
}

const SORTABLE: Array<{ key: SortKey; label: string }> = [
  { key: "starred", label: "★" },
  { key: "company", label: "Company" },
  { key: "role", label: "Role" },
  { key: "status", label: "Status" },
  { key: "fit_score", label: "Fit" },
  { key: "date_updated", label: "Updated" }
];

export default function ApplicationTable({ applications, selectedIds, onSelectionChange, onToggleStar }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("fit_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const items = [...applications];
    items.sort((a, b) => compare(a, b, sortKey, sortDir));
    return items;
  }, [applications, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "company" || key === "role" ? "asc" : "desc");
    }
  }

  function toggleRow(jobId: string) {
    const next = new Set(selectedIds);
    if (next.has(jobId)) next.delete(jobId);
    else next.add(jobId);
    onSelectionChange(next);
  }

  function toggleAll() {
    if (selectedIds.size === sorted.length) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(sorted.map((a) => a.job_id)));
    }
  }

  if (applications.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">+</div>
        <h2>No applications match these filters</h2>
        <p>Loosen the filters or add a job posting.</p>
      </div>
    );
  }

  return (
    <table className="application-table">
      <thead>
        <tr>
          <th>
            <input
              type="checkbox"
              checked={selectedIds.size > 0 && selectedIds.size === sorted.length}
              onChange={toggleAll}
              title="Select all"
            />
          </th>
          {SORTABLE.map(({ key, label }) => (
            <th
              key={key}
              className="sortable"
              onClick={() => handleSort(key)}
              title="Click to sort"
            >
              {label}{sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
            </th>
          ))}
          <th>Audit</th>
          <th>Ver</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((app) => (
          <tr key={app.job_id} className={selectedIds.has(app.job_id) ? "selected" : ""}>
            <td>
              <input
                type="checkbox"
                checked={selectedIds.has(app.job_id)}
                onChange={() => toggleRow(app.job_id)}
              />
            </td>
            <td>
              <button
                type="button"
                className={`star-btn${app.starred ? " starred" : ""}`}
                onClick={() => onToggleStar(app.job_id, !app.starred)}
                title={app.starred ? "Unstar" : "Star this job"}
              >
                {app.starred ? "★" : "☆"}
              </button>
            </td>
            <td><Link to={`/job/${app.job_id}`}>{app.company}</Link></td>
            <td>{app.role}</td>
            <td><StatusBadge status={app.status} /></td>
            <td>{app.fit_score == null ? "-" : `${Math.round(app.fit_score * 100)}%`}</td>
            <td>{app.date_updated}</td>
            <td>{app.audit_verdict || "-"}</td>
            <td>{app.latest_resume_version ? `v${String(app.latest_resume_version).padStart(3, "0")}` : "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function compare(a: TrackerEntry, b: TrackerEntry, key: SortKey, dir: SortDir): number {
  const sign = dir === "asc" ? 1 : -1;
  switch (key) {
    case "company":
      return sign * a.company.localeCompare(b.company);
    case "role":
      return sign * a.role.localeCompare(b.role);
    case "status":
      return sign * a.status.localeCompare(b.status);
    case "fit_score":
      return sign * ((a.fit_score ?? -1) - (b.fit_score ?? -1));
    case "date_updated":
      return sign * a.date_updated.localeCompare(b.date_updated);
    case "starred":
      return sign * (Number(b.starred ?? false) - Number(a.starred ?? false));
  }
}
