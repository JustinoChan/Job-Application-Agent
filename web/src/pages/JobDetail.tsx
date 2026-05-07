import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getApplication,
  getAudit,
  getRawJob,
  resumeHtmlUrl,
  resumePdfUrl,
  updateStatus
} from "../api/client";
import type { AuditReport as AuditReportType, TrackerEntry, TrackerStatus } from "../api/types";
import AuditReport from "../components/AuditReport";
import ResumePreview from "../components/ResumePreview";
import StatusBadge from "../components/StatusBadge";

const statuses: TrackerStatus[] = [
  "found",
  "prepared",
  "reviewed",
  "submitted",
  "rejected",
  "interview",
  "assessment",
  "offer",
  "ghosted",
  "archived"
];

export default function JobDetail() {
  const { jobId = "" } = useParams();
  const [entry, setEntry] = useState<TrackerEntry | null>(null);
  const [rawText, setRawText] = useState("");
  const [audit, setAudit] = useState<AuditReportType | null>(null);
  const [tab, setTab] = useState<"resume" | "audit" | "posting">("resume");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getApplication(jobId)
      .then((data) => {
        setEntry(data);
        setNotes(data.notes || "");
        if (data.latest_resume_version) {
          getAudit(data.job_id, data.latest_resume_version).then(setAudit).catch(() => setAudit(null));
        }
      })
      .catch((err) => setError(err.response?.data?.detail || err.message));
    getRawJob(jobId).then(setRawText).catch(() => setRawText(""));
  }, [jobId]);

  async function saveStatus(status: TrackerStatus) {
    if (!entry) return;
    const updated = await updateStatus(entry.job_id, status, notes);
    setEntry(updated);
  }

  if (error) return <main className="page-shell"><div className="error-banner">{error}</div></main>;
  if (!entry) return <main className="page-shell"><div className="loading-banner">Loading...</div></main>;

  const version = entry.latest_resume_version || 1;
  return (
    <main className="page-shell">
      <Link to="/" className="back-link">Back to dashboard</Link>
      <div className="detail-header">
        <div>
          <h1>{entry.company}</h1>
          <p>{entry.role}</p>
        </div>
        <StatusBadge status={entry.status} />
      </div>
      <section className="form-panel">
        <div className="two-col">
          <div>
            <label>Status</label>
            <select value={entry.status} onChange={(event) => saveStatus(event.target.value as TrackerStatus)}>
              {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </div>
          <div>
            <label>Notes</label>
            <input value={notes} onChange={(event) => setNotes(event.target.value)} onBlur={() => saveStatus(entry.status)} />
          </div>
        </div>
      </section>
      <div className="tabs">
        <button className={tab === "resume" ? "active" : ""} onClick={() => setTab("resume")}>Resume</button>
        <button className={tab === "audit" ? "active" : ""} onClick={() => setTab("audit")}>Audit</button>
        <button className={tab === "posting" ? "active" : ""} onClick={() => setTab("posting")}>Job Posting</button>
      </div>
      {tab === "resume" && (
        <section>
          <div className="actions-row">
            <a className="secondary button-link" href={resumePdfUrl(entry.job_id, version)}>Download PDF</a>
          </div>
          <ResumePreview src={resumeHtmlUrl(entry.job_id, version)} />
        </section>
      )}
      {tab === "audit" && audit && <AuditReport report={audit} />}
      {tab === "posting" && <pre className="raw-posting">{rawText || "No raw posting saved."}</pre>}
    </main>
  );
}
