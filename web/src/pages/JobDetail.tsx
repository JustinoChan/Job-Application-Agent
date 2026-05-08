import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  coverLetterHtmlUrl,
  coverLetterPdfUrl,
  generateCoverLetter,
  getApplication,
  getAudit,
  getCoverLetterAudit,
  getOpenClawStatus,
  getRawJob,
  listCoverLetters,
  resumeHtmlUrl,
  resumePdfUrl,
  updateStatus
} from "../api/client";
import type {
  AuditReport as AuditReportType,
  OpenClawStatus,
  TrackerEntry,
  TrackerStatus
} from "../api/types";
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

type Tab = "resume" | "cover-letter" | "audit" | "posting";

export default function JobDetail() {
  const { jobId = "" } = useParams();
  const [entry, setEntry] = useState<TrackerEntry | null>(null);
  const [rawText, setRawText] = useState("");
  const [audit, setAudit] = useState<AuditReportType | null>(null);
  const [tab, setTab] = useState<Tab>("resume");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [coverLetterVersions, setCoverLetterVersions] = useState<number[]>([]);
  const [selectedCoverVersion, setSelectedCoverVersion] = useState<number | null>(null);
  const [coverAudit, setCoverAudit] = useState<AuditReportType | null>(null);
  const [openclawStatus, setOpenclawStatus] = useState<OpenClawStatus | null>(null);
  const [generating, setGenerating] = useState(false);
  const [coverError, setCoverError] = useState("");

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
    getOpenClawStatus()
      .then(setOpenclawStatus)
      .catch(() => setOpenclawStatus({ available: false, reason: "Could not reach server" }));
    refreshCoverLetters();
  }, [jobId]);

  function refreshCoverLetters() {
    listCoverLetters(jobId)
      .then((data) => {
        setCoverLetterVersions(data.versions);
        if (data.versions.length > 0) {
          const latest = data.versions[data.versions.length - 1];
          setSelectedCoverVersion(latest);
          getCoverLetterAudit(jobId, latest).then(setCoverAudit).catch(() => setCoverAudit(null));
        }
      })
      .catch(() => setCoverLetterVersions([]));
  }

  async function saveStatus(status: TrackerStatus) {
    if (!entry) return;
    const updated = await updateStatus(entry.job_id, status, notes);
    setEntry(updated);
  }

  async function handleGenerateCoverLetter() {
    setGenerating(true);
    setCoverError("");
    try {
      const result = await generateCoverLetter(jobId, entry?.latest_resume_version || undefined);
      setSelectedCoverVersion(result.version);
      setCoverAudit(result.audit_report);
      refreshCoverLetters();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : detail?.message || err.message;
      setCoverError(msg);
    } finally {
      setGenerating(false);
    }
  }

  function handleSelectCoverVersion(v: number) {
    setSelectedCoverVersion(v);
    getCoverLetterAudit(jobId, v).then(setCoverAudit).catch(() => setCoverAudit(null));
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
        <button className={tab === "cover-letter" ? "active" : ""} onClick={() => setTab("cover-letter")}>Cover Letter</button>
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
      {tab === "cover-letter" && (
        <section>
          {coverError && <div className="error-banner">{String(coverError)}</div>}
          <div className="actions-row">
            <button
              onClick={handleGenerateCoverLetter}
              disabled={generating || !openclawStatus?.available}
              title={openclawStatus?.available ? "Generate cover letter via OpenClaw" : openclawStatus?.reason || "Checking..."}
            >
              {generating ? "Generating..." : coverLetterVersions.length > 0 ? "Regenerate Cover Letter" : "Generate Cover Letter"}
            </button>
            {coverLetterVersions.length > 1 && (
              <select
                value={selectedCoverVersion || ""}
                onChange={(event) => handleSelectCoverVersion(Number(event.target.value))}
              >
                {coverLetterVersions.map((v) => (
                  <option key={v} value={v}>v{String(v).padStart(3, "0")}</option>
                ))}
              </select>
            )}
            {selectedCoverVersion && (
              <a className="secondary button-link" href={coverLetterPdfUrl(jobId, selectedCoverVersion)}>Download PDF</a>
            )}
          </div>
          {selectedCoverVersion ? (
            <>
              <ResumePreview src={coverLetterHtmlUrl(jobId, selectedCoverVersion)} />
              {coverAudit && <AuditReport report={coverAudit} />}
            </>
          ) : (
            <p>No cover letter generated yet. {openclawStatus?.available ? "Click the button above to create one." : `OpenClaw is unavailable: ${openclawStatus?.reason || "checking..."}`}</p>
          )}
        </section>
      )}
      {tab === "audit" && audit && <AuditReport report={audit} />}
      {tab === "posting" && <pre className="raw-posting">{rawText || "No raw posting saved."}</pre>}
    </main>
  );
}
