from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, HttpUrl

from src.models import AuditReport, FitScore, TrackerStatus


class TrackerEntryResponse(BaseModel):
    job_id: str
    date_added: date
    company: str
    role: str
    url: str | None = None
    status: TrackerStatus
    fit_score: float | None = None
    resume_path: str | None = None
    cover_letter_path: str | None = None
    audit_verdict: str | None = None
    latest_resume_version: int | None = None
    notes: str | None = None
    next_action: str | None = None
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


class DiscoverResponse(BaseModel):
    job_id: str
    status: Literal["saved", "exists", "skipped"]
    fit_score: float | None = None
    recommendation: str | None = None
    reason: str | None = None
