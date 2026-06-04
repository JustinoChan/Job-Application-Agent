from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ── Source-of-Truth Models (deserialized from YAML) ──────────────


class Education(BaseModel):
    school: str
    degree: str
    graduation: str
    gpa: Optional[float] = None
    relevant_coursework: list[str] = Field(default_factory=list)


class SkillSet(BaseModel):
    strong: list[str]
    familiar: list[str]


class Constraints(BaseModel):
    never_claim: list[str]
    allowed_actions: list[str]


class MasterProfile(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    location: str
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    education: list[Education]
    skills: SkillSet
    summary: Optional[str] = None
    constraints: Constraints


class Fact(BaseModel):
    id: str
    text: str
    keywords: list[str] = Field(default_factory=list)


class Project(BaseModel):
    id: str
    name: str
    role: Optional[str] = None
    date_range: Optional[str] = None
    stack: list[str]
    url: Optional[str] = None
    description: Optional[str] = None
    facts: list[Fact]
    themes: list[str] = Field(default_factory=list)


class ProjectBank(BaseModel):
    projects: list[Project]


class MasterResume(BaseModel):
    max_projects: int = 4
    max_facts_per_project: int = 4


class ApplicationRules(BaseModel):
    never_claim: list[str]
    always_include_skills: list[str] = Field(default_factory=list)
    preferred_project_order: list[str] = Field(default_factory=list)
    min_fit_score_to_apply: float = 0.3
    keyword_synonyms: dict[str, list[str]] = Field(default_factory=dict)


# ── Pipeline Models (produced during processing) ────────────────


class JobRequirement(BaseModel):
    text: str
    keywords: list[str] = Field(default_factory=list)
    is_required: bool = True


class JobPosting(BaseModel):
    raw_text: str
    company: str = "Unknown"
    title: str = "Unknown"
    location: Optional[str] = None
    experience_level: Optional[str] = None
    requirements: list[JobRequirement] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    nice_to_haves: list[JobRequirement] = Field(default_factory=list)
    extracted_keywords: list[str] = Field(default_factory=list)
    source_file: Optional[str] = None


class SkillMatch(BaseModel):
    skill: str
    matched: bool
    source: str


class ProjectScore(BaseModel):
    project_id: str
    project_name: str
    relevance_score: float
    matched_keywords: list[str]
    matched_themes: list[str]


class FitScore(BaseModel):
    overall_score: float
    skill_matches: list[SkillMatch]
    skill_match_rate: float
    nice_to_have_match_rate: float
    project_scores: list[ProjectScore]
    missing_required: list[str]
    missing_nice_to_haves: list[str]
    recommendation: str


class SelectedFact(BaseModel):
    fact_id: str
    project_id: str
    original_text: str
    relevance_score: float


class TailoredProject(BaseModel):
    project_id: str
    name: str
    role: Optional[str] = None
    date_range: Optional[str] = None
    url: Optional[str] = None
    stack: list[str]
    selected_facts: list[SelectedFact]


class TailoredResume(BaseModel):
    job_posting: JobPosting
    fit_score: FitScore
    reordered_skills: SkillSet
    selected_projects: list[TailoredProject]
    generated_at: datetime = Field(default_factory=datetime.now)
    output_path: Optional[str] = None


class PipelineResult(BaseModel):
    job_id: str
    job: JobPosting
    fit: FitScore
    tailored: TailoredResume
    report: "AuditReport"
    resume_md: str
    resume_html: str


class ConfirmResult(BaseModel):
    job_id: str
    version: int
    resume_path: str
    audit_verdict: str
    message: str


class CoverLetter(BaseModel):
    job_id: str
    company: str
    title: str
    resume_version: Optional[int] = None
    intro: str
    body_paragraphs: list[str]
    closing: str
    referenced_project_ids: list[str] = Field(default_factory=list)
    referenced_fact_ids: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.now)


# ── Audit Models ─────────────────────────────────────────────────


class AuditVerdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class AuditEntry(BaseModel):
    fact_id: str
    project_id: str
    resume_text: str
    source_text: str
    verdict: AuditVerdict
    reason: str


class AuditReport(BaseModel):
    total_claims: int
    passed: int
    warned: int
    failed: int
    entries: list[AuditEntry]
    hard_constraint_violations: list[str]
    overall_verdict: AuditVerdict
    audited_at: datetime = Field(default_factory=datetime.now)


# ── Tracker Models ───────────────────────────────────────────────


class TrackerStatus(str, Enum):
    FOUND = "found"
    PREPARED = "prepared"
    REVIEWED = "reviewed"
    SUBMITTED = "submitted"
    REJECTED = "rejected"
    INTERVIEW = "interview"
    ASSESSMENT = "assessment"
    OFFER = "offer"
    GHOSTED = "ghosted"
    ARCHIVED = "archived"


class TrackerEntry(BaseModel):
    job_id: str
    date_added: date
    posted_at: Optional[date] = None
    company: str
    role: str
    location: Optional[str] = None
    url: Optional[str] = None
    status: TrackerStatus
    fit_score: Optional[float] = None
    resume_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
    audit_verdict: Optional[str] = None
    latest_resume_version: Optional[int] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    starred: bool = False
    source: Optional[str] = None
    response_date: Optional[date] = None
    response_type: Optional[str] = None
    interview_stage: Optional[str] = None
    source_quality: Optional[int] = None
    date_updated: date = Field(default_factory=date.today)
