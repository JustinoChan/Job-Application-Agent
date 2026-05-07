import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDashboardStats, listApplications } from "../api/client";
import type { DashboardStats, TrackerEntry } from "../api/types";
import ApplicationTable from "../components/ApplicationTable";
import QuickStats from "../components/QuickStats";
import StatusChart from "../components/StatusChart";

export default function Dashboard() {
  const [applications, setApplications] = useState<TrackerEntry[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([listApplications(includeArchived), getDashboardStats()])
      .then(([apps, dashboardStats]) => {
        setApplications(apps);
        setStats(dashboardStats);
      })
      .catch((err) => setError(err.response?.data?.detail || err.message));
  }, [includeArchived]);

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
      </div>
      {error && <div className="error-banner">{error}</div>}
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
          <ApplicationTable applications={applications} />
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
