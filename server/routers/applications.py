from __future__ import annotations

import json
import os
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from server import dependencies
from server.schemas import (
    ConfirmRequest,
    ConfirmResponse,
    CoverLetterGenerateRequest,
    CoverLetterListResponse,
    CoverLetterResponse,
    DiscoverRequest,
    DiscoverResponse,
    OpenClawStatusResponse,
    PreviewRequest,
    PreviewResponse,
    ScrapeRequest,
    ScrapeResponse,
    StatusUpdateRequest,
    TrackerEntryResponse,
)
from src import config, fit_scorer, job_parser, job_scraper, pipeline, tracker
from src.models import TrackerEntry, TrackerStatus

router = APIRouter(prefix="/applications", tags=["applications"])


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
        company=request.company,
        role=request.title,
        url=request.url,
        status=TrackerStatus.FOUND,
        fit_score=fit.overall_score,
        notes=request.source,
        next_action="review",
    )
    tracker.add_entry(config.TRACKER_PATH, entry)

    return DiscoverResponse(
        job_id=job_id,
        status="saved",
        fit_score=fit.overall_score,
        recommendation=fit.recommendation,
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
    return ConfirmResponse.model_validate(result)


@router.get("/{job_id}", response_model=TrackerEntryResponse)
def get_application(job_id: str):
    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return entry


@router.put("/{job_id}/status", response_model=TrackerEntryResponse)
def update_application_status(job_id: str, request: StatusUpdateRequest):
    updated = tracker.update_status(
        config.TRACKER_PATH,
        job_id,
        request.status,
        notes=request.notes,
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
