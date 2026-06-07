import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { TrackerEntry } from "../api/types";

type SortKey = "company" | "role" | "level" | "location" | "status" | "fit_score" | "posted_at" | "date_added" | "date_updated" | "starred";
type SortDir = "asc" | "desc";

// Derive a job level from the role title (intern -> principal). Checked from
// most senior down so "Senior Staff" reads as Staff, etc.
const LEVELS: Array<{ rank: number; label: string; test: RegExp }> = [
  { rank: 0, label: "Intern", test: /\b(intern|internship|co-?op)\b/i },
  { rank: 5, label: "Principal", test: /\b(principal|distinguished|fellow)\b/i },
  { rank: 4, label: "Staff", test: /\bstaff\b/i },
  { rank: 3, label: "Senior", test: /\b(senior|sr\.?)\b/i },
  { rank: 1, label: "Entry", test: /\b(new ?grad|entry[- ]?level|junior|jr\.?|associate|early[- ]?career)\b/i },
];

function levelOf(role: string): { rank: number; label: string } {
  for (const lvl of LEVELS) {
    if (lvl.test.test(role)) return { rank: lvl.rank, label: lvl.label };
  }
  return { rank: 2, label: "Mid" };
}

interface Props {
  applications: TrackerEntry[];
  selectedIds: Set<string>;
  onSelectionChange: (next: Set<string>) => void;
  onToggleStar: (jobId: string, starred: boolean) => void;
  onDelete: (jobId: string) => void;
  onStatusChange: (jobId: string, status: TrackerEntry["status"]) => void;
  onNotesChange: (jobId: string, notes: string) => void;
}

const SORTABLE: Array<{ key: SortKey; label: string }> = [
  { key: "starred", label: "★" },
  { key: "company", label: "Company" },
  { key: "fit_score", label: "Fit" },
  { key: "role", label: "Role" },
  { key: "level", label: "Level" },
  { key: "location", label: "Location" },
  { key: "status", label: "Status" },
  { key: "posted_at", label: "Posted" },
  { key: "date_added", label: "Added" },
  { key: "date_updated", label: "Updated" },
];

const STATUS_OPTIONS: Array<{ value: TrackerEntry["status"]; label: string }> = [
  { value: "found", label: "Found" },
  { value: "prepared", label: "Prepared" },
  { value: "reviewed", label: "Reviewed" },
  { value: "submitted", label: "Applied" },
  { value: "interview", label: "Interview" },
  { value: "assessment", label: "Assessment" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
  { value: "ghosted", label: "Ghosted" },
  { value: "archived", label: "Archived" },
];

export default function ApplicationTable({
  applications, selectedIds, onSelectionChange,
  onToggleStar, onDelete, onStatusChange, onNotesChange,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("fit_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expandedNote, setExpandedNote] = useState<string | null>(null);
  const [editingNote, setEditingNote] = useState("");
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  const sorted = useMemo(() => {
    const items = [...applications];
    items.sort((a, b) => compare(a, b, sortKey, sortDir));
    return items;
  }, [applications, sortKey, sortDir]);

  // Only render one page of rows at a time. Painting thousands of rows x ~17
  // columns at once chokes the browser's table layout (columns fail to render);
  // paginating keeps the DOM small so every column shows at any filter level.
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const clampedPage = Math.min(page, pageCount - 1);
  const pageStart = clampedPage * PAGE_SIZE;
  const paged = useMemo(
    () => sorted.slice(pageStart, pageStart + PAGE_SIZE),
    [sorted, pageStart],
  );

  // Reset to the first page whenever the underlying set or sort changes.
  useEffect(() => {
    setPage(0);
  }, [applications, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "company" || key === "role" || key === "location" ? "asc" : "desc");
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

  function openNote(app: TrackerEntry) {
    if (expandedNote === app.job_id) {
      setExpandedNote(null);
    } else {
      setExpandedNote(app.job_id);
      setEditingNote(app.notes || "");
    }
  }

  function saveNote(jobId: string) {
    onNotesChange(jobId, editingNote);
    setExpandedNote(null);
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
    <div className="table-card">
      <table className="application-table">
        <thead>
          <tr>
            <th className="col-check">
              <input
                type="checkbox"
                checked={selectedIds.size > 0 && selectedIds.size === sorted.length}
                onChange={toggleAll}
                title="Select all"
              />
            </th>
            <th className="col-num">#</th>
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
            <th>Ver</th>
            <th>Link</th>
            <th className="col-notes">Notes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {paged.map((app, idx) => (
            <>
              <tr key={app.job_id} className={selectedIds.has(app.job_id) ? "selected" : ""}>
                <td className="col-check">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(app.job_id)}
                    onChange={() => toggleRow(app.job_id)}
                  />
                </td>
                <td className="col-num">{pageStart + idx + 1}</td>
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
                <td><Link to={`/job/${app.job_id}`} className="company-link">{app.company}</Link></td>
                <td>
                  {app.fit_score == null ? (
                    <span className="fit-cell fit-unscored">—</span>
                  ) : (
                    <span className={`fit-cell ${fitClass(app.fit_score)}`}>
                      {Math.round(app.fit_score * 100)}%
                    </span>
                  )}
                </td>
                <td className="role-cell">{app.role}</td>
                <td><span className="level-badge">{levelOf(app.role).label}</span></td>
                <td className="loc-cell" title={app.location || ""}>{app.location || "-"}</td>
                <td>
                  <select
                    className={`status-select status-${app.status}`}
                    value={app.status}
                    onChange={(e) => onStatusChange(app.job_id, e.target.value as TrackerEntry["status"])}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {STATUS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </td>
                <td className="date-cell">{app.posted_at || "-"}</td>
                <td className="date-cell">{app.date_added || "-"}</td>
                <td className="date-cell">{app.date_updated}</td>
                <td>{app.latest_resume_version ? `v${String(app.latest_resume_version).padStart(3, "0")}` : "-"}</td>
                <td>
                  {app.url ? (
                    <a href={app.url} target="_blank" rel="noreferrer" title={app.url} className="link-icon" onClick={(e) => e.stopPropagation()}>↗</a>
                  ) : "-"}
                </td>
                <td className="col-notes">
                  <button
                    type="button"
                    className={`notes-toggle${app.notes ? " has-notes" : ""}`}
                    onClick={() => openNote(app)}
                    title={app.notes || "Add notes"}
                  >
                    {app.notes ? "📝" : "＋"}
                  </button>
                </td>
                <td>
                  <button
                    type="button"
                    className="delete-btn"
                    onClick={(e) => { e.stopPropagation(); onDelete(app.job_id); }}
                    title="Delete this job and all artifacts"
                  >
                    ✕
                  </button>
                </td>
              </tr>
              {expandedNote === app.job_id && (
                <tr key={`${app.job_id}-note`} className="note-row">
                  <td colSpan={17}>
                    <div className="note-editor">
                      <textarea
                        value={editingNote}
                        onChange={(e) => setEditingNote(e.target.value)}
                        placeholder="Add notes about this application..."
                        rows={2}
                      />
                      <div className="note-actions">
                        <button onClick={() => saveNote(app.job_id)}>Save</button>
                        <button className="secondary" onClick={() => setExpandedNote(null)}>Cancel</button>
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
      {sorted.length > PAGE_SIZE && (
        <div className="pagination">
          <span className="pagination-info">
            Showing {pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, sorted.length)} of {sorted.length}
          </span>
          <div className="pagination-controls">
            <button
              className="secondary"
              disabled={clampedPage === 0}
              onClick={() => setPage(clampedPage - 1)}
            >
              ‹ Prev
            </button>
            <span className="pagination-page">Page {clampedPage + 1} of {pageCount}</span>
            <button
              className="secondary"
              disabled={clampedPage >= pageCount - 1}
              onClick={() => setPage(clampedPage + 1)}
            >
              Next ›
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function fitClass(score: number): string {
  if (score >= 0.75) return "fit-strong";
  if (score >= 0.5) return "fit-moderate";
  if (score >= 0.3) return "fit-weak";
  return "fit-skip";
}

function compare(a: TrackerEntry, b: TrackerEntry, key: SortKey, dir: SortDir): number {
  const sign = dir === "asc" ? 1 : -1;
  switch (key) {
    case "company":
      return sign * a.company.localeCompare(b.company);
    case "role":
      return sign * a.role.localeCompare(b.role);
    case "location":
      return sign * (a.location || "").localeCompare(b.location || "");
    case "level":
      return sign * (levelOf(a.role).rank - levelOf(b.role).rank);
    case "status":
      return sign * a.status.localeCompare(b.status);
    case "fit_score":
      return sign * ((a.fit_score ?? -1) - (b.fit_score ?? -1));
    case "posted_at":
      return sign * ((a.posted_at || "").localeCompare(b.posted_at || ""));
    case "date_added":
      return sign * (a.date_added || "").localeCompare(b.date_added || "");
    case "date_updated":
      return sign * a.date_updated.localeCompare(b.date_updated);
    case "starred":
      return sign * (Number(b.starred ?? false) - Number(a.starred ?? false));
  }
}
