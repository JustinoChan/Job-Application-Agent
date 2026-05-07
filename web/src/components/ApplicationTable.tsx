import { Link } from "react-router-dom";
import type { TrackerEntry } from "../api/types";
import StatusBadge from "./StatusBadge";

export default function ApplicationTable({ applications }: { applications: TrackerEntry[] }) {
  if (applications.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">+</div>
        <h2>No applications yet</h2>
        <p>Add a job posting to prepare your first audited resume.</p>
      </div>
    );
  }

  return (
    <table className="application-table">
      <thead>
        <tr>
          <th>Company</th>
          <th>Role</th>
          <th>Status</th>
          <th>Fit</th>
          <th>Audit</th>
          <th>Version</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody>
        {applications.map((app) => (
          <tr key={app.job_id}>
            <td>
              <Link to={`/job/${app.job_id}`}>{app.company}</Link>
            </td>
            <td>{app.role}</td>
            <td><StatusBadge status={app.status} /></td>
            <td>{app.fit_score == null ? "-" : `${Math.round(app.fit_score * 100)}%`}</td>
            <td>{app.audit_verdict || "-"}</td>
            <td>{app.latest_resume_version ? `v${String(app.latest_resume_version).padStart(3, "0")}` : "-"}</td>
            <td>{app.date_updated}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
