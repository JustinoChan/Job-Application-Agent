import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  bulkArchive,
  getDashboardStats,
  listApplications,
  searchPostings,
  toggleStar
} from "../api/client";
import type { DashboardStats, SearchResult, TrackerEntry } from "../api/types";
import ApplicationTable from "../components/ApplicationTable";
import FilterBar, { FilterState } from "../components/FilterBar";
import QuickStats from "../components/QuickStats";
import StatusChart from "../components/StatusChart";

const EMPTY_FILTERS: FilterState = { minFit: 0, company: "", search: "" };

export default function Dashboard() {
  const [applications, setApplications] = useState<TrackerEntry[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);
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

  const visible = useMemo(() => {
    const companyNeedle = filters.company.trim().toLowerCase();
    return applications.filter((app) => {
      if ((app.fit_score ?? 0) < filters.minFit) return false;
      if (companyNeedle && !app.company.toLowerCase().includes(companyNeedle)) return false;
      if (searchMatches !== null && !searchMatches.has(app.job_id)) return false;
      return true;
    });
  }, [applications, filters.minFit, filters.company, searchMatches]);

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

  const counts = stats?.status_counts || {};
  return (
    <main className="page-shell">
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
      <div className="stats-strip">
        <span><strong>{stats?.total ?? 0}</strong> Total</span>
        <span><strong>{counts.prepared || 0}</strong> Prepared</span>
        <span><strong>{counts.submitted || 0}</strong> Submitted</span>
        <span><strong>{(counts.interview || 0) + (counts.assessment || 0)}</strong> Interviewing</span>
        <span><strong>{counts.offer || 0}</strong> Offers</span>
        <span><strong>{counts.rejected || 0}</strong> Rejected</span>
      </div>
      <div className="dashboard-grid">
        <section className="workspace-panel">
          <ApplicationTable
            applications={visible}
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
            onToggleStar={handleToggleStar}
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
            <h2>Status Breakdown</h2>
            <StatusChart counts={counts} />
          </section>
          <section className="side-card">
            <h2>Quick Stats</h2>
            <QuickStats stats={stats} />
          </section>
        </aside>
      </div>
    </main>
  );
}
