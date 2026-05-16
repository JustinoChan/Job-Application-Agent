import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  coverLetterHtmlUrl,
  coverLetterPdfUrl,
  generateCoverLetter,
  getApplication,
  getAudit,
  getCoverLetterAudit,
  getJobAnalysis,
  getOpenClawStatus,
  getRawJob,
  listCoverLetters,
  resumeHtmlUrl,
  resumePdfUrl,
  tailorFromTracker,
  updateStatus
} from "../api/client";
import type {
  AuditReport as AuditReportType,
  JobAnalysis,
  OpenClawStatus,
  TrackerEntry,
  TrackerStatus
} from "../api/types";
import AuditReport from "../components/AuditReport";
import FitScoreDisplay from "../components/FitScoreDisplay";
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

type Tab = "overview" | "resume" | "cover-letter" | "audit" | "posting";

export default function JobDetail() {
  const { jobId = "" } = useParams();
  const [entry, setEntry] = useState<TrackerEntry | null>(null);
  const [analysis, setAnalysis] = useState<JobAnalysis | null>(null);
  const [rawText, setRawText] = useState("");
  const [audit, setAudit] = useState<AuditReportType | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [coverLetterVersions, setCoverLetterVersions] = useState<number[]>([]);
  const [selectedCoverVersion, setSelectedCoverVersion] = useState<number | null>(null);
  const [coverAudit, setCoverAudit] = useState<AuditReportType | null>(null);
  const [openclawStatus, setOpenclawStatus] = useState<OpenClawStatus | null>(null);
  const [generating, setGenerating] = useState(false);
  const [coverError, setCoverError] = useState("");
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState("");

  useEffect(() => {
    loadEntry();
    getRawJob(jobId).then(setRawText).catch(() => setRawText(""));
    getOpenClawStatus()
      .then(setOpenclawStatus)
      .catch(() => setOpenclawStatus({ available: false, reason: "Could not reach server" }));
    getJobAnalysis(jobId).then(setAnalysis).catch(() => setAnalysis(null));
    refreshCoverLetters();
  }, [jobId]);

  function loadEntry() {
    getApplication(jobId)
      .then((data) => {
        setEntry(data);
        setNotes(data.notes || "");
        if (data.latest_resume_version) {
          getAudit(data.job_id, data.latest_resume_version).then(setAudit).catch(() => setAudit(null));
        } else {
          setAudit(null);
        }
      })
      .catch((err) => setError(err.response?.data?.detail || err.message));
  }

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

  async function handleTailor() {
    setTailoring(true);
    setTailorError("");
    try {
      await tailorFromTracker(jobId);
      loadEntry();
      setTab("resume");
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === "string" ? detail : detail?.message || err.message;
      setTailorError(msg);
    } finally {
      setTailoring(false);
    }
  }

  if (error) return <main className="page-shell"><div className="error-banner">{error}</div></main>;
  if (!entry) return <main className="page-shell"><div className="loading-banner">Loading...</div></main>;

  const version = entry.latest_resume_version || 0;
  const hasResume = version > 0;
  const location = entry.location || analysis?.location || null;

  return (
    <main className="page-shell">
      <Link to="/" className="back-link">Back to dashboard</Link>
      <div className="detail-header">
        <div>
          <h1>{entry.company}</h1>
          <p>{entry.role}</p>
          <div className="detail-meta">
            {location && <span className="meta-chip">{location}</span>}
            {entry.posted_at && <span className="meta-chip">Posted {entry.posted_at}</span>}
            {entry.source && <span className="meta-chip">{entry.source}</span>}
            {entry.url && (
              <a className="meta-chip link" href={entry.url} target="_blank" rel="noreferrer">
                View original posting ↗
              </a>
            )}
          </div>
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
        <button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>Overview</button>
        <button
          className={tab === "resume" ? "active" : ""}
          onClick={() => setTab("resume")}
        >
          Resume{hasResume ? ` v${String(version).padStart(3, "0")}` : ""}
        </button>
        <button className={tab === "cover-letter" ? "active" : ""} onClick={() => setTab("cover-letter")}>Cover Letter</button>
        <button className={tab === "audit" ? "active" : ""} onClick={() => setTab("audit")} disabled={!audit}>Audit</button>
        <button className={tab === "posting" ? "active" : ""} onClick={() => setTab("posting")}>Job Posting</button>
      </div>

      {tab === "overview" && (
        <section>
          {analysis ? (
            <>
              <FitScoreDisplay fit={analysis.fit_score} />
              {analysis.fit_score.missing_nice_to_haves.length > 0 && (
                <div className="info-panel">
                  <h3>Nice-to-haves missing</h3>
                  <ul className="chip-list">
                    {analysis.fit_score.missing_nice_to_haves.map((skill) => (
                      <li key={skill} className="chip dim">{skill}</li>
                    ))}
                  </ul>
                </div>
              )}
              {analysis.extracted_keywords.length > 0 && (
                <div className="info-panel">
                  <h3>Extracted keywords</h3>
                  <ul className="chip-list">
                    {analysis.extracted_keywords.map((kw) => (
                      <li key={kw} className="chip">{kw}</li>
                    ))}
                  </ul>
                </div>
              )}
              {analysis.requirements.length > 0 && (
                <div className="info-panel">
                  <h3>Requirements ({analysis.requirements.length})</h3>
                  <ul className="bullet-list">
                    {analysis.requirements.map((req, i) => <li key={i}>{req}</li>)}
                  </ul>
                </div>
              )}
              {analysis.nice_to_haves.length > 0 && (
                <div className="info-panel">
                  <h3>Nice to have ({analysis.nice_to_haves.length})</h3>
                  <ul className="bullet-list">
                    {analysis.nice_to_haves.map((req, i) => <li key={i}>{req}</li>)}
                  </ul>
                </div>
              )}
              {analysis.responsibilities.length > 0 && (
                <div className="info-panel">
                  <h3>Responsibilities</h3>
                  <ul className="bullet-list">
                    {analysis.responsibilities.map((line, i) => <li key={i}>{line}</li>)}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="loading-banner">
              No analysis available yet. The saved posting may be missing — check the Job Posting tab.
            </div>
          )}
        </section>
      )}

      {tab === "resume" && (
        <section>
          {!hasResume ? (
            <div className="info-panel">
              <h3>No resume generated yet</h3>
              <p>Generate a tailored resume from this posting. The truth audit runs automatically.</p>
              {tailorError && <div className="error-banner">{tailorError}</div>}
              <div className="actions-row">
                <button onClick={handleTailor} disabled={tailoring}>
                  {tailoring ? "Generating..." : "Generate Resume"}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="actions-row">
                <a className="secondary button-link" href={resumePdfUrl(entry.job_id, version)} target="_blank" rel="noreferrer">
                  Download PDF
                </a>
                <button onClick={handleTailor} disabled={tailoring}>
                  {tailoring ? "Regenerating..." : "Regenerate Resume"}
                </button>
              </div>
              {tailorError && <div className="error-banner">{tailorError}</div>}
              <ResumePreview src={resumeHtmlUrl(entry.job_id, version)} />
            </>
          )}
        </section>
      )}

      {tab === "cover-letter" && (
        <section>
          {!hasResume && (
            <div className="info-panel">
              <h3>Generate a resume first</h3>
              <p>Cover letters reference the tailored resume version. Open the Resume tab to create one.</p>
            </div>
          )}
          {coverError && <div className="error-banner">{String(coverError)}</div>}
          {hasResume && (
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
              {selectedCoverVersion && coverAudit?.overall_verdict === "pass" && (
                <a className="secondary button-link" href={coverLetterPdfUrl(jobId, selectedCoverVersion)} target="_blank" rel="noreferrer">
                  Download PDF
                </a>
              )}
              {selectedCoverVersion && coverAudit?.overall_verdict === "fail" && (
                <button className="secondary" disabled title="PDF generation is blocked until the cover letter audit passes.">
                  PDF Blocked
                </button>
              )}
            </div>
          )}
          {coverAudit?.overall_verdict === "fail" && (
            <div className="error-banner">
              Draft saved, but the audit found unsupported claims. Review the audit below before generating a PDF.
            </div>
          )}
          {selectedCoverVersion ? (
            <>
              <ResumePreview src={coverLetterHtmlUrl(jobId, selectedCoverVersion)} />
              {coverAudit && <AuditReport report={coverAudit} />}
            </>
          ) : hasResume ? (
            <p>No cover letter generated yet. {openclawStatus?.available ? "Click the button above to create one." : `OpenClaw is unavailable: ${openclawStatus?.reason || "checking..."}`}</p>
          ) : null}
        </section>
      )}
      {tab === "audit" && audit && <AuditReport report={audit} />}
      {tab === "posting" && <pre className="raw-posting">{rawText || "No raw posting saved."}</pre>}
    </main>
  );
}
