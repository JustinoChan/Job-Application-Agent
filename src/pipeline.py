from __future__ import annotations

from datetime import date
from pathlib import Path

from src import claim_auditor, config, fit_scorer, job_parser, pdf_renderer, resume_tailor, tracker
from src.filelock import version_lock
from src.models import (
    ApplicationRules,
    AuditVerdict,
    ConfirmResult,
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
