import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  bulkArchive,
  deleteApplication,
  getDashboardStats,
  listApplications,
  searchPostings,
  toggleStar,
  updateStatus
} from "../api/client";
import type { DashboardStats, SearchResult, TrackerEntry } from "../api/types";
import ApplicationTable from "../components/ApplicationTable";
import FilterBar, { FilterState } from "../components/FilterBar";
import QuickStats from "../components/QuickStats";
import StatusChart from "../components/StatusChart";

const EMPTY_FILTERS: FilterState = { minFit: 0, company: "", location: "", search: "", dateFrom: "", dateTo: "" };

type ViewTab = "discoveries" | "tracker";

const DISCOVERY_STATUSES = new Set(["found", "prepared", "reviewed"]);
const TRACKER_STATUSES = new Set(["submitted", "interview", "assessment", "offer", "rejected", "ghosted"]);

export default function Dashboard() {
  const [applications, setApplications] = useState<TrackerEntry[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  // Default to Applied Tracker tab instead of Discoveries
  const [viewTab, setViewTab] = useState<ViewTab>("tracker");
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [searchMatches, setSearchMatches] = useState<Set<string> | null>(null);
  const [searchSnippets, setSearchSnippets] = useState<Record<string, string>>({});
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const refresh = useCallback(() => {
    Promise.all([listApplications(includeArchived), getDashboardStats()])
      .then(([apps, dashboardStats]) => {
        setApplications(apps);
        setStats(dashboardStats);
      })
      .catch((err) => setError(err.response?.data?.detail || err.message));
  }, [includeArchived]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!filters.search) {
      setSearchMatches(null);
      setSearchSnippets({});
      return;
    }
    let cancelled = false;
    searchPostings(filters.search)
      .then((res) => {
        if (cancelled) return;
        setSearchMatches(new Set(res.matches.map((m: SearchResult) => m.job_id)));
        setSearchSnippets(Object.fromEntries(res.matches.map((m: SearchResult) => [m.job_id, m.snippet])));
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.response?.data?.detail || err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [filters.search]);

  const tabFiltered = useMemo(() => {
    const allowed = viewTab === "discoveries" ? DISCOVERY_STATUSES : TRACKER_STATUSES;
    return applications.filter((app) => {
      if (app.status === "archived") return includeArchived;
      return allowed.has(app.status);
    });
  }, [applications, viewTab, includeArchived]);

  const visible = useMemo(() => {
    const companyNeedle = filters.company.trim().toLowerCase();
    const locationNeedle = filters.location.trim().toLowerCase();
    return tabFiltered.filter((app) => {
      if ((app.fit_score ?? 0) < filters.minFit) return false;
      if (companyNeedle && !app.company.toLowerCase().includes(companyNeedle)) return false;
      if (locationNeedle && !(app.location || "").toLowerCase().includes(locationNeedle)) return false;
      if (searchMatches !== null && !searchMatches.has(app.job_id)) return false;
      if (filters.dateFrom && app.date_added < filters.dateFrom) return false;
      if (filters.dateTo && app.date_added > filters.dateTo) return false;
      return true;
    });
  }, [tabFiltered, filters.minFit, filters.company, filters.location, filters.dateFrom, filters.dateTo, searchMatches]);

  const handleToggleStar = useCallback(async (jobId: string, starred: boolean) => {
    setApplications((prev) => prev.map((a) => (a.job_id === jobId ? { ...a, starred } : a)));
    try {
      const updated = await toggleStar(jobId, starred);
      setApplications((prev) => prev.map((a) => (a.job_id === jobId ? updated : a)));
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
      refresh();
    }
  }, [refresh]);

  const handleDelete = useCallback(async (jobId: string) => {
    const app = applications.find((a) => a.job_id === jobId);
    const label = app ? `${app.company} — ${app.role}` : jobId;
    if (!window.confirm(`Delete "${label}" and all its resumes/cover letters? This cannot be undone.`)) return;
    try {
      await deleteApplication(jobId);
      setSelectedIds((prev) => { const next = new Set(prev); next.delete(jobId); return next; });
      refresh();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    }
  }, [applications, refresh]);

  const handleStatusChange = useCallback(async (jobId: string, status: string) => {
    setApplications((prev) => prev.map((a) => (a.job_id === jobId ? { ...a, status: status as any } : a)));
    try {
      const updated = await updateStatus(jobId, status as any);
      setApplications((prev) => prev.map((a) => (a.job_id === jobId ? updated : a)));
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
      refresh();
    }
  }, [refresh]);

  const handleNotesChange = useCallback(async (jobId: string, notes: string) => {
    const app = applications.find((a) => a.job_id === jobId);
    if (!app) return;
    setApplications((prev) => prev.map((a) => (a.job_id === jobId ? { ...a, notes } : a)));
    try {
      const updated = await updateStatus(jobId, app.status, notes);
      setApplications((prev) => prev.map((a) => (a.job_id === jobId ? updated : a)));
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
      refresh();
    }
  }, [applications, refresh]);

  async function handleBulkArchive() {
    if (selectedIds.size === 0) return;
    setBusy(`Archiving ${selectedIds.size}...`);
    try {
      await bulkArchive(Array.from(selectedIds));
      setSelectedIds(new Set());
      refresh();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setBusy("");
    }
  }

  function switchTab(tab: ViewTab) {
    setViewTab(tab);
    setSelectedIds(new Set());
    setFilters(EMPTY_FILTERS);
  }

  function exportCsv() {
    const headers = ["Company", "Role", "Status", "Fit Score", "Date Added", "Date Updated", "URL", "Notes"];
    const rows = visible.map((a) => [
      a.company,
      a.role,
      a.status,
      a.fit_score != null ? `${Math.round(a.fit_score * 100)}%` : "",
      a.date_added,
      a.date_updated,
      a.url || "",
      (a.notes || "").replace(/"/g, '""'),
    ]);
    const csv = [headers, ...rows].map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${viewTab}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const counts = stats?.status_counts || {};
  const discoveryCount = (counts.found || 0) + (counts.prepared || 0) + (counts.reviewed || 0);
  const trackerCount = (counts.submitted || 0) + (counts.interview || 0) + (counts.assessment || 0) + (counts.offer || 0) + (counts.rejected || 0) + (counts.ghosted || 0);

  // Real fit distribution across the currently-visible discoveries, bucketed
  // by the same thresholds the table badges use.
  const fitBuckets = useMemo(() => {
    const b = { strong: 0, moderate: 0, weak: 0, low: 0 };
    for (const app of visible) {
      const s = app.fit_score;
      if (s == null) continue;
      if (s >= 0.75) b.strong += 1;
      else if (s >= 0.5) b.moderate += 1;
      else if (s >= 0.3) b.weak += 1;
      else b.low += 1;
    }
    return b;
  }, [visible]);

  return (
    <main className="page-shell">
      <div className="view-tabs">
        <button
          className={`view-tab${viewTab === "tracker" ? " active" : ""}`}
          onClick={() => switchTab("tracker")}
        >
          Applied Tracker
          <span className="view-tab-count">{trackerCount}</span>
        </button>
        <button
          className={`view-tab${viewTab === "discoveries" ? " active" : ""}`}
          onClick={() => switchTab("discoveries")}
        >
          Discoveries
          <span className="view-tab-count">{discoveryCount}</span>
        </button>
      </div>

      <div className="toolbar">
        <Link className="primary-button" to="/add">+ Add Application</Link>
        <label className="toggle">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setIncludeArchived(event.target.checked)}
          />
          Show archived
        </label>
        <button className="secondary" onClick={exportCsv} title="Export visible rows as CSV">
          Export CSV
        </button>
        {selectedIds.size > 0 && (
          <button className="danger-button" onClick={handleBulkArchive} disabled={Boolean(busy)}>
            {busy || `Archive ${selectedIds.size} selected`}
          </button>
        )}
      </div>
      {error && <div className="error-banner">{error}</div>}
      <FilterBar value={filters} onChange={setFilters} />
      {filters.search && searchMatches !== null && (
        <div className="search-summary">
          {searchMatches.size === 0
            ? `No raw postings match "${filters.search}"`
            : `${searchMatches.size} posting${searchMatches.size === 1 ? "" : "s"} match "${filters.search}"`}
        </div>
      )}

      {viewTab === "discoveries" ? (
        <div className="stats-cards">
          <div className="stat-card">
            <span className="stat-value">{discoveryCount}</span>
            <span className="stat-label">Discovered</span>
          </div>
          <div className="stat-card stat-found">
            <span className="stat-value">{counts.found || 0}</span>
            <span className="stat-label">New</span>
          </div>
          <div className="stat-card stat-prepared">
            <span className="stat-value">{counts.prepared || 0}</span>
            <span className="stat-label">Resume Ready</span>
          </div>
          <div className="stat-card stat-reviewed-card">
            <span className="stat-value">{counts.reviewed || 0}</span>
            <span className="stat-label">Reviewed</span>
          </div>
        </div>
      ) : (
        <div className="stats-cards">
          <div className="stat-card">
            <span className="stat-value">{trackerCount}</span>
            <span className="stat-label">Total Applied</span>
          </div>
          <div className="stat-card stat-applied">
            <span className="stat-value">{counts.submitted || 0}</span>
            <span className="stat-label">Applied</span>
          </div>
          <div className="stat-card stat-interview">
            <span className="stat-value">{(counts.interview || 0) + (counts.assessment || 0)}</span>
            <span className="stat-label">Interviewing</span>
          </div>
          <div className="stat-card stat-offers">
            <span className="stat-value">{counts.offer || 0}</span>
            <span className="stat-label">Offers</span>
          </div>
          <div className="stat-card stat-rejected">
            <span className="stat-value">{counts.rejected || 0}</span>
            <span className="stat-label">Rejected</span>
          </div>
        </div>
      )}

      <div className="dashboard-grid">
        <section className="workspace-panel">
          <ApplicationTable
            applications={visible}
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
            onToggleStar={handleToggleStar}
            onDelete={handleDelete}
            onStatusChange={handleStatusChange}
            onNotesChange={handleNotesChange}
          />
          {filters.search && Object.keys(searchSnippets).length > 0 && (
            <details className="search-snippets">
              <summary>Show matching snippets</summary>
              <ul>
                {Object.entries(searchSnippets).map(([jobId, snippet]) => (
                  <li key={jobId}>
                    <Link to={`/job/${jobId}`}>{jobId}</Link>: <span>{snippet}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
        <aside className="sidebar">
          <section className="side-card">
            <h2>{viewTab === "discoveries" ? "Fit Distribution" : "Status Breakdown"}</h2>
            <StatusChart
              showLegend
              counts={
                viewTab === "discoveries"
                  ? { strong: fitBuckets.strong, moderate: fitBuckets.moderate, weak: fitBuckets.weak, low: fitBuckets.low }
                  : { submitted: counts.submitted || 0, interview: counts.interview || 0, assessment: counts.assessment || 0, offer: counts.offer || 0, rejected: counts.rejected || 0, ghosted: counts.ghosted || 0 }
              }
            />
          </section>
          {viewTab === "tracker" && (
            <section className="side-card">
              <h2>Quick Stats</h2>
              <QuickStats stats={stats} />
            </section>
          )}
        </aside>
      </div>
    </main>
  );
}
