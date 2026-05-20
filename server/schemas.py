from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, HttpUrl

from src.models import AuditReport, FitScore, TrackerStatus


class TrackerEntryResponse(BaseModel):
    job_id: str
    date_added: date
    posted_at: date | None = None
    company: str
    role: str
    location: str | None = None
    url: str | None = None
    status: TrackerStatus
    fit_score: float | None = None
    resume_path: str | None = None
    cover_letter_path: str | None = None
    audit_verdict: str | None = None
    latest_resume_version: int | None = None
    notes: str | None = None
    next_action: str | None = None
    starred: bool = False
    source: str | None = None
    date_updated: date


class ScrapeRequest(BaseModel):
    url: HttpUrl
    provider: Literal["none", "openclaw"] | None = None


class ScrapeResponse(BaseModel):
    raw_text: str
    suggested_company: str | None = None
    suggested_title: str | None = None
    final_url: str | None = None


class PreviewRequest(BaseModel):
    raw_text: str
    company: str | None = None
    title: str | None = None
    url: str | None = None


class PreviewResponse(BaseModel):
    job_id: str
    company: str
    title: str
    location: str | None
    requirements: list[str]
    extracted_keywords: list[str]
    fit_score: FitScore
    tailored_resume_md: str
    tailored_resume_html: str
    audit_report: AuditReport
    recommendation: str


class ConfirmRequest(PreviewRequest):
    pass


class ConfirmResponse(BaseModel):
    job_id: str
    version: int
    resume_path: str
    audit_verdict: str
    message: str


class StatusUpdateRequest(BaseModel):
    status: TrackerStatus
    notes: str | None = None


class DashboardStatsResponse(BaseModel):
    total: int
    status_counts: dict[str, int]
    response_rate: float
    interview_rate: float
    offer_rate: float


class ReloadConfigResponse(BaseModel):
    message: str


class OpenClawStatusResponse(BaseModel):
    available: bool
    reason: str


class CoverLetterGenerateRequest(BaseModel):
    resume_version: int | None = None


class CoverLetterResponse(BaseModel):
    job_id: str
    version: int
    company: str
    title: str
    intro: str
    body_paragraphs: list[str]
    closing: str
    audit_verdict: str
    audit_report: AuditReport


class CoverLetterListResponse(BaseModel):
    job_id: str
    versions: list[int]


class DiscoverRequest(BaseModel):
    company: str
    title: str
    url: str
    raw_text: str
    source: str | None = None
    posted_at: date | None = None


class DiscoverResponse(BaseModel):
    job_id: str
    status: Literal["saved", "exists", "skipped"]
    fit_score: float | None = None
    recommendation: str | None = None
    reason: str | None = None
    auto_tailored: bool = False


class StarRequest(BaseModel):
    starred: bool


class JobAnalysisResponse(BaseModel):
    """Re-parsed view of a stored posting for display on JobDetail.

    The discover pipeline only persists `fit_score` (overall) to the tracker,
    not the breakdown. This recomputes from the saved raw text so the
    dashboard can show requirements, missing skills, recommendation, etc.
    """
    job_id: str
    company: str
    title: str
    location: str | None = None
    url: str | None = None
    source: str | None = None
    experience_level: str | None = None
    requirements: list[str]
    nice_to_haves: list[str]
    responsibilities: list[str]
    extracted_keywords: list[str]
    fit_score: FitScore
    # Best-effort metadata extracted from the saved raw text.
    contact_emails: list[str] = []
    apply_urls: list[str] = []
    salary_mentions: list[str] = []
    raw_excerpt: str | None = None


class TailorResponse(BaseModel):
    job_id: str
    version: int
    audit_verdict: str
    message: str


class BulkArchiveRequest(BaseModel):
    job_ids: list[str]


class BulkArchiveResponse(BaseModel):
    updated: int


class BrowserApplyRequest(BaseModel):
    url_override: str | None = None
    headless: bool = False


class BrowserApplyResponse(BaseModel):
    job_id: str
    url: str
    fields_filled: list[str] = []
    resume_attached: bool = False
    paused: bool = False
    error: str | None = None


class SearchResult(BaseModel):
    job_id: str
    company: str
    role: str
    status: TrackerStatus
    fit_score: float | None = None
    snippet: str


class SearchResponse(BaseModel):
    query: str
    matches: list[SearchResult]
