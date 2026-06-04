from __future__ import annotations

import json
import os
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

import re

from server import dependencies
from server.schemas import (
    BrowserApplyRequest,
    BrowserApplyResponse,
    BulkArchiveRequest,
    DeleteResponse,
    BulkArchiveResponse,
    ConfirmRequest,
    ConfirmResponse,
    CoverLetterGenerateRequest,
    CoverLetterListResponse,
    CoverLetterResponse,
    DiscoverRequest,
    DiscoverResponse,
    JobAnalysisResponse,
    OpenClawStatusResponse,
    PreviewRequest,
    PreviewResponse,
    ScrapeRequest,
    ScrapeResponse,
    SearchResponse,
    SearchResult,
    StarRequest,
    StatusUpdateRequest,
    TailorResponse,
    TrackerEntryResponse,
)
from src import claim_auditor, config, fit_scorer, job_parser, job_scraper, notifications, pdf_renderer, pipeline, resume_tailor, tracker
from src.filelock import version_lock
from src.models import AuditVerdict, TrackerEntry, TrackerStatus

import logging as _logging

_log = _logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["applications"])

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
# Exclude brackets so HN footnote markers (`[2]`) don't merge into the URL.
# Closing parens are left in the character class but stripped afterward
# in a balance-aware way (see _clean_url).
_URL_RE = re.compile(r"https?://[^\s<>'\"\[\]]+")
_URL_TRAILING_PUNCT = ".,;:!?"


def _clean_url(url: str) -> str:
    url = url.strip()
    while url and url[-1] in _URL_TRAILING_PUNCT:
        url = url[:-1]
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]
    while url and url[-1] in _URL_TRAILING_PUNCT:
        url = url[:-1]
    return url
# Salary mentions: explicit ranges with $/€/£, k-suffixed numbers, or
# /yr|/year tokens. Conservative — false positives degrade the UI less
# than missing real salary info.
_SALARY_RE = re.compile(
    r"(?ix)"
    r"(?:[\$€£]\s?\d{2,3}(?:[,\.]\d{3})?(?:\s?[-–to]+\s?[\$€£]?\s?\d{2,3}(?:[,\.]\d{3})?)?(?:\s?(?:k|/yr|/year|per\s+year|annually))?)"
    r"|(?:\b\d{2,3}\s?k(?:\s?[-–to]+\s?\d{2,3}\s?k)?\b(?:\s?(?:/yr|/year|per\s+year|annually))?)"
    r"|(?:\bsalary[: ]\s?[\$€£]?\s?\d[\d,\. -]{1,20})"
)


def _extract_emails(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _EMAIL_RE.findall(text):
        low = m.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(m)
        if len(out) >= 5:
            break
    return out


def _extract_apply_urls(text: str, exclude: str | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    excl = _clean_url(exclude or "").rstrip("/")
    for m in _URL_RE.findall(text):
        clean = _clean_url(m)
        if not clean or clean.rstrip("/") == excl or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
        if len(out) >= 5:
            break
    return out


def _extract_salary_mentions(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _SALARY_RE.findall(text):
        m = m.strip()
        if not m or m in seen:
            continue
        seen.add(m)
        out.append(m)
        if len(out) >= 4:
            break
    return out


@router.post("/archive-stale")
def archive_stale(max_age_days: int = Query(default=7)):
    """Archive found-status discoveries older than max_age_days."""
    archived = tracker.archive_stale_discoveries(
        config.TRACKER_PATH, max_age_days=max_age_days,
    )
    return {"archived": archived}


@router.post("/rescore")
def rescore_all():
    """Re-parse and re-score every tracked job that has a raw file."""
    profile = dependencies.get_profile()
    projects = list(dependencies.get_projects())
    rules = dependencies.get_rules()

    entries = tracker.list_entries(config.TRACKER_PATH)
    updated = 0
    for entry in entries:
        raw_path = config.JOBS_RAW_DIR / f"{entry.job_id}.txt"
        if not raw_path.exists():
            continue
        raw_text = raw_path.read_text(encoding="utf-8")
        job = job_parser.parse_job_description(
            raw_text, profile, projects, rules,
            company_override=entry.company, title_override=entry.role,
        )
        fit = fit_scorer.score_fit(job, profile, projects, rules)
        old_score = entry.fit_score or 0.0
        if abs(old_score - fit.overall_score) > 0.001:
            tracker.update_status(
                config.TRACKER_PATH, entry.job_id, entry.status,
                fit_score=fit.overall_score,
            )
            updated += 1
    return {"updated": updated, "total": len(entries)}


@router.get("/", response_model=list[TrackerEntryResponse])
def list_applications(
    status: TrackerStatus | None = Query(default=None),
    include_archived: bool = Query(default=False),
) -> list:
    entries = tracker.list_entries(config.TRACKER_PATH, status)
    if not include_archived:
        entries = [entry for entry in entries if entry.status != TrackerStatus.ARCHIVED]
    return entries


@router.get("/openclaw-status", response_model=OpenClawStatusResponse)
def openclaw_status() -> OpenClawStatusResponse:
    from src.openclaw_adapter import is_openclaw_available

    available, reason = is_openclaw_available()
    return OpenClawStatusResponse(available=available, reason=reason)


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_application(request: ScrapeRequest) -> ScrapeResponse:
    provider = request.provider or os.getenv("LLM_PROVIDER", "none")
    try:
        scraped = await job_scraper.fetch_page(str(request.url))
        source_url = scraped.final_url or str(request.url)
        raw_text = await job_scraper.extract_job_posting(
            scraped.raw_text,
            provider=provider,
            source_url=source_url,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile = dependencies.get_profile()
    projects = list(dependencies.get_projects())
    rules = dependencies.get_rules()
    job = job_parser.parse_job_description(raw_text, profile, projects, rules)
    return ScrapeResponse(
        raw_text=raw_text,
        suggested_company=None if job.company == "Unknown" else job.company,
        suggested_title=None if job.title == "Unknown" else job.title,
        final_url=scraped.final_url,
    )


@router.post("/preview", response_model=PreviewResponse)
def preview_application(request: PreviewRequest) -> PreviewResponse:
    result = pipeline.preview_application(
        request.raw_text,
        dependencies.get_profile(),
        list(dependencies.get_projects()),
        dependencies.get_rules(),
        dependencies.get_resume_config(),
        company=request.company,
        title=request.title,
    )
    return _preview_response(result)


@router.post("/discover", response_model=DiscoverResponse)
def discover_application(request: DiscoverRequest) -> DiscoverResponse:
    """Ingest a pre-scraped posting from the VM scraper. Idempotent on job_id."""
    config.ensure_directories()
    job_id = tracker.generate_job_id(request.company, request.title)

    if tracker.job_id_exists(config.TRACKER_PATH, job_id):
        return DiscoverResponse(job_id=job_id, status="exists")

    profile = dependencies.get_profile()
    projects = list(dependencies.get_projects())
    rules = dependencies.get_rules()

    job = job_parser.parse_job_description(
        request.raw_text, profile, projects, rules,
        company_override=request.company, title_override=request.title,
    )
    fit = fit_scorer.score_fit(job, profile, projects, rules)

    if fit.recommendation == "skip":
        return DiscoverResponse(
            job_id=job_id,
            status="skipped",
            fit_score=fit.overall_score,
            recommendation=fit.recommendation,
            reason=f"Fit score {fit.overall_score:.0%} below threshold",
        )

    raw_path = config.JOBS_RAW_DIR / f"{job_id}.txt"
    raw_path.write_text(request.raw_text, encoding="utf-8")

    entry = TrackerEntry(
        job_id=job_id,
        date_added=date.today(),
        posted_at=request.posted_at,
        company=request.company,
        role=request.title,
        location=job.location,
        url=request.url,
        status=TrackerStatus.FOUND,
        fit_score=fit.overall_score,
        source=request.source,
        next_action="review",
    )
    tracker.add_entry(config.TRACKER_PATH, entry)

    if notifications.should_notify(fit.overall_score):
        notifications.send_new_job_notification(
            job_id=job_id,
            company=request.company,
            title=request.title,
            fit_score=fit.overall_score,
            recommendation=fit.recommendation,
            url=request.url,
            location=job.location,
            experience_level=job.experience_level,
            source=request.source,
            auto_tailored=False,
            dashboard_base_url=os.getenv("DASHBOARD_BASE_URL"),
        )

    return DiscoverResponse(
        job_id=job_id,
        status="saved",
        fit_score=fit.overall_score,
        recommendation=fit.recommendation,
        auto_tailored=False,
    )


@router.post("/confirm", response_model=ConfirmResponse)
def confirm_application(request: ConfirmRequest) -> ConfirmResponse:
    try:
        result = pipeline.confirm_application(
            request.raw_text,
            dependencies.get_profile(),
            list(dependencies.get_projects()),
            dependencies.get_rules(),
            dependencies.get_resume_config(),
            company=request.company,
            title=request.title,
            url=request.url,
        )
    except pipeline.PipelineAuditError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Claim audit failed; application was not saved.",
                "audit_report": exc.result.report.model_dump(mode="json"),
            },
        ) from exc
    return ConfirmResponse.model_validate(result.model_dump())


@router.post("/bulk-archive", response_model=BulkArchiveResponse)
def bulk_archive(request: BulkArchiveRequest):
    """Set status=archived for many applications at once."""
    if not request.job_ids:
        return BulkArchiveResponse(updated=0)
    updated = tracker.bulk_update_status(
        config.TRACKER_PATH, request.job_ids, TrackerStatus.ARCHIVED,
    )
    return BulkArchiveResponse(updated=updated)


@router.get("/search", response_model=SearchResponse)
def search_postings(q: str = Query(min_length=2)):
    """Case-insensitive substring search across saved raw posting texts."""
    needle = q.lower()
    matches: list[SearchResult] = []
    for entry in tracker.list_entries(config.TRACKER_PATH):
        raw_path = config.JOBS_RAW_DIR / f"{entry.job_id}.txt"
        if not raw_path.exists():
            continue
        try:
            text = raw_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        idx = text.lower().find(needle)
        if idx < 0:
            continue
        start = max(0, idx - 80)
        end = min(len(text), idx + len(q) + 120)
        snippet = text[start:end].replace("\n", " ").strip()
        matches.append(SearchResult(
            job_id=entry.job_id,
            company=entry.company,
            role=entry.role,
            status=entry.status,
            fit_score=entry.fit_score,
            snippet=snippet,
        ))
    return SearchResponse(query=q, matches=matches)


@router.get("/{job_id}", response_model=TrackerEntryResponse)
def get_application(job_id: str):
    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return entry


@router.put("/{job_id}/star", response_model=TrackerEntryResponse)
def set_star(job_id: str, request: StarRequest):
    """Toggle the starred flag on a single application."""
    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    tracker.update_status(
        config.TRACKER_PATH, job_id, entry.status, starred=request.starred,
    )
    refreshed = tracker.get_entry(config.TRACKER_PATH, job_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return refreshed


@router.delete("/{job_id}", response_model=DeleteResponse)
def delete_application(job_id: str) -> DeleteResponse:
    """Permanently delete a job and all its generated artifacts."""
    import shutil

    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    deleted_files: list[str] = []

    raw_path = config.JOBS_RAW_DIR / f"{job_id}.txt"
    if raw_path.exists():
        raw_path.unlink()
        deleted_files.append(str(raw_path))

    resume_dir = config.job_resume_dir(job_id)
    if resume_dir.exists():
        shutil.rmtree(resume_dir)
        deleted_files.append(str(resume_dir))

    cl_dir = config.job_cover_letter_dir(job_id)
    if cl_dir.exists():
        shutil.rmtree(cl_dir)
        deleted_files.append(str(cl_dir))

    tracker.delete_entry(config.TRACKER_PATH, job_id)
    _log.info("deleted job %s and %d artifact paths", job_id, len(deleted_files))

    return DeleteResponse(job_id=job_id, deleted_files=deleted_files)


@router.put("/{job_id}/status", response_model=TrackerEntryResponse)
def update_application_status(job_id: str, request: StatusUpdateRequest):
    provided_fields = request.model_fields_set
    updated = tracker.update_status(
        config.TRACKER_PATH,
        job_id,
        request.status,
        notes=request.notes,
        response_date=request.response_date,
        response_date_set="response_date" in provided_fields,
        response_type=request.response_type,
        response_type_set="response_type" in provided_fields,
        interview_stage=request.interview_stage,
        interview_stage_set="interview_stage" in provided_fields,
        source_quality=request.source_quality,
        source_quality_set="source_quality" in provided_fields,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Application not found.")
    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return entry


@router.get("/{job_id}/raw", response_class=PlainTextResponse)
def get_raw_job(job_id: str) -> str:
    raw_path = config.JOBS_RAW_DIR / f"{job_id}.txt"
    if not raw_path.exists():
        raise HTTPException(status_code=404, detail="Raw job text not found.")
    return raw_path.read_text(encoding="utf-8")


@router.get("/{job_id}/analysis", response_model=JobAnalysisResponse)
def get_job_analysis(job_id: str) -> JobAnalysisResponse:
    """Re-parse the saved raw posting and return the fit breakdown.

    The discover pipeline persists only the overall fit score; the full
    breakdown (skill matches, missing skills, recommendation, requirements,
    extracted keywords) is regenerated here on demand so the dashboard can
    show *why* a posting fits.
    """
    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    raw_path = config.JOBS_RAW_DIR / f"{job_id}.txt"
    if not raw_path.exists():
        raise HTTPException(status_code=404, detail="Raw job text not found.")

    profile = dependencies.get_profile()
    projects = list(dependencies.get_projects())
    rules = dependencies.get_rules()
    raw_text = raw_path.read_text(encoding="utf-8")
    job = job_parser.parse_job_description(
        raw_text, profile, projects, rules,
        company_override=entry.company, title_override=entry.role,
    )
    fit = fit_scorer.score_fit(job, profile, projects, rules)

    excerpt = raw_text.strip()
    if len(excerpt) > 600:
        excerpt = excerpt[:600].rstrip() + "..."

    return JobAnalysisResponse(
        job_id=job_id,
        company=entry.company,
        title=entry.role,
        location=entry.location or job.location,
        url=entry.url,
        source=entry.source,
        experience_level=job.experience_level,
        requirements=[req.text for req in job.requirements],
        nice_to_haves=[req.text for req in job.nice_to_haves],
        responsibilities=job.responsibilities,
        extracted_keywords=job.extracted_keywords,
        fit_score=fit,
        contact_emails=_extract_emails(raw_text),
        apply_urls=_extract_apply_urls(raw_text, entry.url),
        salary_mentions=_extract_salary_mentions(raw_text),
        raw_excerpt=excerpt,
    )


@router.post("/{job_id}/tailor", response_model=TailorResponse)
def tailor_from_tracker(job_id: str) -> TailorResponse:
    """Generate a versioned resume for an existing tracker entry.

    Reads the saved raw posting, runs the full tailor + audit pipeline,
    persists a new resume version, and advances the tracker row to
    `prepared`. Used by the dashboard's Generate Resume button on
    found-status rows.
    """
    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    raw_path = config.JOBS_RAW_DIR / f"{job_id}.txt"
    if not raw_path.exists():
        raise HTTPException(status_code=404, detail="Raw job text not found.")

    profile = dependencies.get_profile()
    projects = list(dependencies.get_projects())
    rules = dependencies.get_rules()
    resume_config = dependencies.get_resume_config()
    raw_text = raw_path.read_text(encoding="utf-8")

    job = job_parser.parse_job_description(
        raw_text, profile, projects, rules,
        company_override=entry.company, title_override=entry.role,
    )
    fit = fit_scorer.score_fit(job, profile, projects, rules)
    tailored = resume_tailor.tailor_resume(job, fit, profile, projects, resume_config, rules)
    report = claim_auditor.audit_resume(tailored, projects, profile, rules)

    if report.overall_verdict == AuditVerdict.FAIL:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Claim audit failed; resume was not saved.",
                "audit_report": report.model_dump(mode="json"),
            },
        )

    md = resume_tailor.render_resume_markdown(tailored, profile)
    with version_lock(job_id):
        version = config.next_resume_version(job_id)
        resume_path = resume_tailor.save_resume(md, job_id, version)
        resume_tailor.save_resume_metadata(tailored, job_id, version)
        claim_auditor.save_audit_report(report, job_id, version)

        next_status = entry.status
        if next_status == TrackerStatus.FOUND:
            next_status = TrackerStatus.PREPARED
        tracker.update_status(
            config.TRACKER_PATH,
            job_id,
            next_status,
            resume_path=str(resume_path),
            audit_verdict=report.overall_verdict.value,
            latest_resume_version=version,
            fit_score=fit.overall_score,
        )

    return TailorResponse(
        job_id=job_id,
        version=version,
        audit_verdict=report.overall_verdict.value,
        message=f"Saved resume v{version:03d} for {entry.company} / {entry.role}.",
    )


@router.post("/{job_id}/browser-apply", response_model=BrowserApplyResponse)
async def browser_apply(job_id: str, request: BrowserApplyRequest) -> BrowserApplyResponse:
    """Open the job's apply page in a browser, pre-fill fields, and pause for user review."""
    from src import browser_apply as ba

    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    profile = dependencies.get_profile()
    result = await ba.prefill_application(
        job_id, profile,
        url_override=request.url_override,
        headless=request.headless,
    )
    return BrowserApplyResponse(
        job_id=result.job_id,
        url=result.url,
        fields_filled=result.fields_filled,
        resume_attached=result.resume_attached,
        paused=result.paused,
        error=result.error,
    )


@router.get("/{job_id}/resume/{version}", response_class=PlainTextResponse)
def get_resume_markdown(job_id: str, version: int) -> str:
    path = config.version_paths(job_id, version)["md"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Resume markdown not found.")
    return path.read_text(encoding="utf-8")


@router.get("/{job_id}/resume/{version}/html", response_class=HTMLResponse)
def get_resume_html(job_id: str, version: int) -> str:
    paths = config.version_paths(job_id, version)
    if paths["html"].exists():
        return paths["html"].read_text(encoding="utf-8")
    try:
        html_path = pipeline.render_resume_html_for_version(
            job_id,
            version,
            dependencies.get_profile(),
            list(dependencies.get_projects()),
            dependencies.get_rules(),
        )
    except (FileNotFoundError, pipeline.PipelineAuditError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return html_path.read_text(encoding="utf-8")


@router.get("/{job_id}/resume/{version}/pdf")
async def get_resume_pdf(job_id: str, version: int) -> FileResponse:
    paths = config.version_paths(job_id, version)
    if not paths["pdf"].exists():
        try:
            await pipeline.render_resume_pdf_for_version(
                job_id,
                version,
                dependencies.get_profile(),
                list(dependencies.get_projects()),
                dependencies.get_rules(),
            )
        except (FileNotFoundError, pipeline.PipelineAuditError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(
        paths["pdf"],
        media_type="application/pdf",
        filename=paths["pdf"].name,
    )


@router.get("/{job_id}/audit/{version}")
def get_audit_report(job_id: str, version: int):
    path = config.version_paths(job_id, version)["audit"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audit report not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/{job_id}/cover-letter", response_model=CoverLetterResponse)
async def generate_cover_letter(job_id: str, request: CoverLetterGenerateRequest) -> CoverLetterResponse:
    from src.openclaw_adapter import is_openclaw_available
    available, reason = is_openclaw_available()
    if not available:
        raise HTTPException(status_code=503, detail=f"OpenClaw is unavailable: {reason}")

    try:
        result = await pipeline.generate_cover_letter_for_job(
            job_id,
            dependencies.get_profile(),
            list(dependencies.get_projects()),
            dependencies.get_rules(),
            resume_version=request.resume_version,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {exc}") from exc

    return CoverLetterResponse(
        job_id=result.job_id,
        version=result.version,
        company=result.letter.company,
        title=result.letter.title,
        intro=result.letter.intro,
        body_paragraphs=result.letter.body_paragraphs,
        closing=result.letter.closing,
        audit_verdict=result.audit_verdict,
        audit_report=result.report,
    )


@router.get("/{job_id}/cover-letters", response_model=CoverLetterListResponse)
def list_cover_letter_versions(job_id: str) -> CoverLetterListResponse:
    job_dir = config.job_cover_letter_dir(job_id)
    if not job_dir.exists():
        return CoverLetterListResponse(job_id=job_id, versions=[])
    versions: list[int] = []
    for f in job_dir.glob("cover_letter_v*.md"):
        import re as _re
        m = _re.search(r"cover_letter_v(\d+)\.md$", f.name)
        if m:
            versions.append(int(m.group(1)))
    return CoverLetterListResponse(job_id=job_id, versions=sorted(versions))


@router.get("/{job_id}/cover-letter/{version}", response_class=PlainTextResponse)
def get_cover_letter_markdown(job_id: str, version: int) -> str:
    path = config.cover_letter_version_paths(job_id, version)["md"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover letter markdown not found.")
    return path.read_text(encoding="utf-8")


@router.get("/{job_id}/cover-letter/{version}/html", response_class=HTMLResponse)
def get_cover_letter_html(job_id: str, version: int) -> str:
    paths = config.cover_letter_version_paths(job_id, version)
    if paths["html"].exists():
        return paths["html"].read_text(encoding="utf-8")
    try:
        html_path = pipeline.render_cover_letter_html_for_version(
            job_id, version,
            dependencies.get_profile(),
            list(dependencies.get_projects()),
            dependencies.get_rules(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return html_path.read_text(encoding="utf-8")


@router.get("/{job_id}/cover-letter/{version}/pdf")
async def get_cover_letter_pdf(job_id: str, version: int) -> FileResponse:
    paths = config.cover_letter_version_paths(job_id, version)
    try:
        await pipeline.render_cover_letter_pdf_for_version(
            job_id, version,
            dependencies.get_profile(),
            list(dependencies.get_projects()),
            dependencies.get_rules(),
        )
    except (FileNotFoundError, pipeline.CoverLetterAuditError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(
        paths["pdf"],
        media_type="application/pdf",
        filename=paths["pdf"].name,
    )


@router.get("/{job_id}/cover-letter/{version}/audit")
def get_cover_letter_audit(job_id: str, version: int):
    path = config.cover_letter_version_paths(job_id, version)["audit"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover letter audit not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def _preview_response(result) -> PreviewResponse:
    return PreviewResponse(
        job_id=result.job_id,
        company=result.job.company,
        title=result.job.title,
        location=result.job.location,
        requirements=[req.text for req in result.job.requirements],
        extracted_keywords=result.job.extracted_keywords,
        fit_score=result.fit,
        tailored_resume_md=result.resume_md,
        tailored_resume_html=result.resume_html,
        audit_report=result.report,
        recommendation=result.fit.recommendation,
    )
