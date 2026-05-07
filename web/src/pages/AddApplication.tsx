import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { confirmApplication, getOpenClawStatus, previewApplication, scrapeJob } from "../api/client";
import type { OpenClawStatus, PreviewResponse } from "../api/types";
import AuditReport from "../components/AuditReport";
import ConfirmDialog from "../components/ConfirmDialog";
import FitScoreDisplay from "../components/FitScoreDisplay";
import ResumePreview from "../components/ResumePreview";

export default function AddApplication() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [openclawStatus, setOpenclawStatus] = useState<OpenClawStatus | null>(null);

  useEffect(() => {
    getOpenClawStatus()
      .then(setOpenclawStatus)
      .catch(() => setOpenclawStatus({ available: false, reason: "Could not reach server" }));
  }, []);

  async function fetchUrl(provider?: string) {
    const label = provider === "openclaw" ? "Fetching with OpenClaw" : "Fetching job posting";
    setLoading(label);
    setError("");
    try {
      const result = await scrapeJob(url, provider);
      setRawText(result.raw_text);
      if (result.suggested_company) setCompany(result.suggested_company);
      if (result.suggested_title) setTitle(result.suggested_title);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message;
      if (provider === "openclaw") {
        setError(`OpenClaw extraction failed: ${msg}. You can continue with normal extraction or paste the job text manually.`);
      } else {
        setError(msg);
      }
    } finally {
      setLoading("");
    }
  }

  async function runPreview() {
    setLoading("Preparing preview");
    setError("");
    try {
      const result = await previewApplication({
        raw_text: rawText,
        company: company || undefined,
        title: title || undefined,
        url: url || undefined
      });
      setPreview(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading("");
    }
  }

  async function saveToTracker() {
    setLoading("Saving application");
    setError("");
    try {
      const result = await confirmApplication({
        raw_text: rawText,
        company: company || undefined,
        title: title || undefined,
        url: url || undefined
      });
      navigate(`/job/${result.job_id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail?.message || err.response?.data?.detail || err.message);
    } finally {
      setLoading("");
      setConfirmOpen(false);
    }
  }

  return (
    <main className="page-shell narrow">
      <div className="page-header">
        <h1>Add Application</h1>
        <p>Fetch or paste a job posting, review the generated materials, then save only after the audit looks right.</p>
      </div>
      {error && <div className="error-banner">{String(error)}</div>}
      {loading && <div className="loading-banner">{loading}...</div>}

      <section className="form-panel">
        <label>Job URL</label>
        <div className="inline-row">
          <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://company.com/jobs/..." />
          <button onClick={() => fetchUrl()} disabled={!url || Boolean(loading)}>Fetch</button>
          <button
            onClick={() => fetchUrl("openclaw")}
            disabled={!url || Boolean(loading) || !openclawStatus?.available}
            title={openclawStatus?.available ? "Extract with AI via OpenClaw" : openclawStatus?.reason || "Checking..."}
          >
            Fetch with AI
          </button>
        </div>
        <div className="two-col">
          <div>
            <label>Company</label>
            <input value={company} onChange={(event) => setCompany(event.target.value)} />
          </div>
          <div>
            <label>Role</label>
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
        </div>
        <label>Reviewed Job Text</label>
        <textarea value={rawText} onChange={(event) => setRawText(event.target.value)} rows={14} />
        <div className="actions-row">
          <button onClick={runPreview} disabled={!rawText || Boolean(loading)}>Preview</button>
        </div>
      </section>

      {preview && (
        <section className="preview-grid">
          <div>
            <FitScoreDisplay fit={preview.fit_score} />
            <AuditReport report={preview.audit_report} />
            <div className="actions-row">
              <button
                onClick={() => setConfirmOpen(true)}
                disabled={preview.audit_report.overall_verdict === "fail"}
              >
                Save to Tracker
              </button>
            </div>
          </div>
          <ResumePreview html={preview.tailored_resume_html} />
        </section>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title="Save Prepared Application?"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={saveToTracker}
      >
        <p>This saves the reviewed job text, versioned resume, audit report, and tracker row. It will not submit an application.</p>
      </ConfirmDialog>
    </main>
  );
}
