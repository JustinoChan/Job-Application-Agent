"""Pipeline orchestration shared by the CLI and API: preview (in-memory) and confirm (audit-gate, then persist)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from src import claim_auditor, config, cover_letter as cover_letter_mod, fit_scorer, job_parser, pdf_renderer, resume_tailor, tracker
from src.filelock import version_lock
from src.models import (
    ApplicationRules,
    AuditReport,
    AuditVerdict,
    ConfirmResult,
    CoverLetter,
    JobPosting,
    MasterProfile,
    MasterResume,
    PipelineResult,
    Project,
    TailoredResume,
    TrackerEntry,
    TrackerStatus,
)


class PipelineAuditError(RuntimeError):
    def __init__(self, result: PipelineResult) -> None:
        super().__init__("Claim audit failed; application was not saved.")
        self.result = result


def preview_application(
    raw_text: str,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
    resume_config: MasterResume,
    company: str | None = None,
    title: str | None = None,
) -> PipelineResult:
    """Run the full application pipeline in memory without disk writes."""
    job = job_parser.parse_job_description(
        raw_text,
        profile,
        projects,
        rules,
        company_override=company,
        title_override=title,
    )
    fit = fit_scorer.score_fit(job, profile, projects, rules)
    tailored = resume_tailor.tailor_resume(job, fit, profile, projects, resume_config, rules)
    report = claim_auditor.audit_resume(tailored, projects, profile, rules)
    md = resume_tailor.render_resume_markdown(tailored, profile)
    html = pdf_renderer.render_html(tailored, profile)
    job_id = tracker.generate_job_id(job.company, job.title)

    return PipelineResult(
        job_id=job_id,
        job=job,
        fit=fit,
        tailored=tailored,
        report=report,
        resume_md=md,
        resume_html=html,
    )


def confirm_application(
    raw_text: str,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
    resume_config: MasterResume,
    company: str | None = None,
    title: str | None = None,
    url: str | None = None,
) -> ConfirmResult:
    """Run, audit, persist, and track an application using the reviewed input text."""
    result = preview_application(raw_text, profile, projects, rules, resume_config, company, title)
    if result.report.overall_verdict == AuditVerdict.FAIL:
        raise PipelineAuditError(result)

    with version_lock(result.job_id):
        config.ensure_directories()
        raw_path = config.JOBS_RAW_DIR / f"{result.job_id}.txt"
        raw_path.write_text(raw_text, encoding="utf-8")

        version = config.next_resume_version(result.job_id)
        resume_path = resume_tailor.save_resume(result.resume_md, result.job_id, version)
        resume_tailor.save_resume_metadata(result.tailored, result.job_id, version)
        claim_auditor.save_audit_report(result.report, result.job_id, version)

        if tracker.job_id_exists(config.TRACKER_PATH, result.job_id):
            tracker.update_status(
                config.TRACKER_PATH,
                result.job_id,
                TrackerStatus.PREPARED,
                resume_path=str(resume_path),
                audit_verdict=result.report.overall_verdict.value,
                latest_resume_version=version,
                fit_score=result.fit.overall_score,
            )
        else:
            entry = TrackerEntry(
                job_id=result.job_id,
                date_added=date.today(),
                company=result.job.company,
                role=result.job.title,
                url=url,
                status=TrackerStatus.PREPARED,
                fit_score=result.fit.overall_score,
                resume_path=str(resume_path),
                audit_verdict=result.report.overall_verdict.value,
                latest_resume_version=version,
                next_action="review",
            )
            tracker.add_entry(config.TRACKER_PATH, entry)

    return ConfirmResult(
        job_id=result.job_id,
        version=version,
        resume_path=str(resume_path),
        audit_verdict=result.report.overall_verdict.value,
        message=f"Saved {result.job.company} / {result.job.title} as resume v{version:03d}.",
    )


def resolve_latest_version(job_id: str) -> int:
    version = config.next_resume_version(job_id) - 1
    if version < 1:
        raise FileNotFoundError(f"No resume versions found for job '{job_id}'.")
    return version


def load_tailored_resume(job_id: str, version: int) -> TailoredResume:
    meta_path = config.version_paths(job_id, version)["meta"]
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata not found: {meta_path}")
    return TailoredResume.model_validate_json(meta_path.read_text(encoding="utf-8"))


def render_resume_html_for_version(
    job_id: str,
    version: int,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
) -> Path:
    tailored = load_tailored_resume(job_id, version)
    report = claim_auditor.audit_resume(tailored, projects, profile, rules)
    if report.overall_verdict == AuditVerdict.FAIL:
        raise PipelineAuditError(PipelineResult(
            job_id=job_id,
            job=tailored.job_posting,
            fit=tailored.fit_score,
            tailored=tailored,
            report=report,
            resume_md=resume_tailor.render_resume_markdown(tailored, profile),
            resume_html="",
        ))

    html = pdf_renderer.render_html(tailored, profile)
    return pdf_renderer.save_html(html, job_id, version)


async def render_resume_pdf_for_version(
    job_id: str,
    version: int,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
) -> Path:
    paths = config.version_paths(job_id, version)
    html_path = render_resume_html_for_version(job_id, version, profile, projects, rules)
    return await pdf_renderer.render_pdf(html_path, paths["pdf"])


class CoverLetterAuditError(RuntimeError):
    def __init__(self, letter: CoverLetter, report: AuditReport) -> None:
        super().__init__("Cover letter audit failed; PDF generation is blocked.")
        self.letter = letter
        self.report = report


class CoverLetterResult(BaseModel):
    job_id: str
    version: int
    cover_letter_md_path: str
    audit_verdict: str
    letter: CoverLetter
    report: AuditReport


async def generate_cover_letter_for_job(
    job_id: str,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
    *,
    resume_version: int | None = None,
) -> CoverLetterResult:
    if resume_version is None:
        resume_version = resolve_latest_version(job_id)

    tailored = load_tailored_resume(job_id, resume_version)
    job = tailored.job_posting

    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    source_url = entry.url if entry else None

    letter = await cover_letter_mod.generate_cover_letter(
        job, tailored, profile, projects, rules, source_url=source_url,
    )
    letter = letter.model_copy(update={"job_id": job_id, "resume_version": resume_version})
    report = cover_letter_mod.audit_cover_letter(letter, profile, projects, rules, job)

    with version_lock(job_id):
        config.ensure_directories()
        version = config.next_cover_letter_version(job_id)
        markdown = cover_letter_mod.render_cover_letter_markdown(letter, profile)
        md_path = cover_letter_mod.save_cover_letter(letter, markdown, job_id, version)
        cover_letter_mod.save_cover_letter_audit(report, job_id, version)

        if entry:
            tracker.update_status(
                config.TRACKER_PATH,
                job_id,
                entry.status,
                cover_letter_path=str(md_path),
            )

    return CoverLetterResult(
        job_id=job_id,
        version=version,
        cover_letter_md_path=str(md_path),
        audit_verdict=report.overall_verdict.value,
        letter=letter,
        report=report,
    )


def resolve_latest_cover_letter_version(job_id: str) -> int:
    version = config.next_cover_letter_version(job_id) - 1
    if version < 1:
        raise FileNotFoundError(f"No cover letter versions found for job '{job_id}'.")
    return version


def load_cover_letter(job_id: str, version: int) -> CoverLetter:
    meta_path = config.cover_letter_version_paths(job_id, version)["meta"]
    if not meta_path.exists():
        raise FileNotFoundError(f"Cover letter metadata not found: {meta_path}")
    return CoverLetter.model_validate_json(meta_path.read_text(encoding="utf-8"))


def render_cover_letter_html_for_version(
    job_id: str,
    version: int,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
) -> Path:
    letter = load_cover_letter(job_id, version)
    html = pdf_renderer.render_cover_letter_html(letter, profile)
    return pdf_renderer.save_cover_letter_html(html, job_id, version)


async def render_cover_letter_pdf_for_version(
    job_id: str,
    version: int,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
) -> Path:
    paths = config.cover_letter_version_paths(job_id, version)
    letter = load_cover_letter(job_id, version)
    resume_version = letter.resume_version or resolve_latest_version(job_id)
    tailored = load_tailored_resume(job_id, resume_version)
    job = tailored.job_posting
    report = cover_letter_mod.audit_cover_letter(letter, profile, projects, rules, job)
    if report.overall_verdict == AuditVerdict.FAIL:
        cover_letter_mod.save_cover_letter_audit(report, job_id, version)
        raise CoverLetterAuditError(letter, report)

    html_path = render_cover_letter_html_for_version(job_id, version, profile, projects, rules)
    return await pdf_renderer.render_pdf(html_path, paths["pdf"])
