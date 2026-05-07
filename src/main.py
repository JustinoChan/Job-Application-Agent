from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src import claim_auditor, config, fit_scorer, job_parser, pdf_renderer, resume_tailor, tracker
from src.models import AuditVerdict, TailoredResume, TrackerEntry, TrackerStatus

app = typer.Typer(
    name="job-agent",
    help="Job Application Agent - truthful resume tailoring from YAML source data.",
    add_completion=False,
)
console = Console()


def _read_multiline_input() -> str:
    console.print(
        "[bold]Paste the job description below.[/bold]\n"
        "[dim]Press Enter twice (blank line) to finish.[/dim]\n"
    )
    lines: list[str] = []
    blank_count = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            blank_count += 1
            if blank_count >= 2:
                break
            lines.append("")
        else:
            blank_count = 0
            lines.append(line)
    return "\n".join(lines).strip()


def _read_job_text(file: Path | None) -> str:
    if file:
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        return file.read_text(encoding="utf-8")

    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    return _read_multiline_input()


@app.command()
def ingest_job(
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Path to a text file containing the job description"),
    company: Optional[str] = typer.Option(None, "--company", "-c", help="Override company name"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Override job title"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Job posting URL for reference"),
) -> None:
    """Ingest a job description from a file or interactive paste."""
    config.ensure_directories()
    raw_text = _read_job_text(file)
    if not raw_text:
        console.print("[red]No job description provided.[/red]")
        raise typer.Exit(1)

    profile = config.load_profile()
    projects = config.load_projects()
    rules = config.load_rules()

    job = job_parser.parse_job_description(
        raw_text, profile, projects, rules,
        company_override=company, title_override=title,
    )

    console.print()
    console.print(Panel(
        f"[bold]{job.title}[/bold] at [bold]{job.company}[/bold]\n"
        f"Location: {job.location or 'Not specified'}\n"
        f"Requirements extracted: {len(job.requirements)}\n"
        f"Nice-to-haves: {len(job.nice_to_haves)}\n"
        f"Keywords found: {', '.join(job.extracted_keywords) or 'None'}",
        title="Parsed Job Posting",
    ))

    job_id = tracker.generate_job_id(job.company, job.title)

    if tracker.job_id_exists(config.TRACKER_PATH, job_id):
        console.print(f"[yellow]Job '{job_id}' already exists in tracker. Skipping duplicate entry.[/yellow]")
    else:
        raw_path = config.JOBS_RAW_DIR / f"{job_id}.txt"
        raw_path.write_text(raw_text, encoding="utf-8")

        entry = TrackerEntry(
            job_id=job_id,
            date_added=date.today(),
            company=job.company,
            role=job.title,
            url=url,
            status=TrackerStatus.FOUND,
        )
        tracker.add_entry(config.TRACKER_PATH, entry)

        console.print(f"[green]Saved job as:[/green] {job_id}")
        console.print(f"[green]Raw text:[/green] {raw_path}")

    console.print(f"\nRun [bold]python -m src.main tailor {job_id}[/bold] to generate a tailored resume.")


@app.command()
def tailor(
    job_id: str = typer.Argument(help="Job ID from the tracker (or 'latest')"),
) -> None:
    """Generate a tailored resume for a job, then auto-audit it."""
    config.ensure_directories()
    profile = config.load_profile()
    projects = config.load_projects()
    rules = config.load_rules()
    resume_config = config.load_resume_config()

    if job_id == "latest":
        entry = tracker.get_latest_entry(config.TRACKER_PATH)
        if not entry:
            console.print("[red]No entries in tracker.[/red]")
            raise typer.Exit(1)
        job_id = entry.job_id

    raw_path = config.JOBS_RAW_DIR / f"{job_id}.txt"
    if not raw_path.exists():
        console.print(f"[red]Job file not found: {raw_path}[/red]")
        raise typer.Exit(1)

    raw_text = raw_path.read_text(encoding="utf-8")

    entry = tracker.get_entry(config.TRACKER_PATH, job_id)
    company_override = entry.company if entry else None
    title_override = entry.role if entry else None

    job = job_parser.parse_job_description(
        raw_text, profile, projects, rules,
        company_override=company_override, title_override=title_override,
    )

    fit = fit_scorer.score_fit(job, profile, projects, rules)

    console.print()
    _print_fit_score(fit, job)

    if fit.recommendation == "skip":
        console.print("[yellow]Fit score is below threshold. Consider skipping this job.[/yellow]")

    tailored = resume_tailor.tailor_resume(
        job, fit, profile, projects, resume_config, rules
    )

    version = config.next_resume_version(job_id)

    md = resume_tailor.render_resume_markdown(tailored, profile)
    resume_path = resume_tailor.save_resume(md, job_id, version)
    resume_tailor.save_resume_metadata(tailored, job_id, version)

    console.print(f"[green]Resume saved:[/green] {resume_path}")

    report = claim_auditor.audit_resume(tailored, projects, profile, rules)
    claim_auditor.print_audit_report(report)

    audit_path = claim_auditor.save_audit_report(report, job_id, version)
    console.print(f"[green]Audit saved:[/green] {audit_path}")

    tracker.update_status(
        config.TRACKER_PATH,
        job_id,
        TrackerStatus.PREPARED,
        resume_path=str(resume_path),
        audit_verdict=report.overall_verdict.value,
        latest_resume_version=version,
        fit_score=fit.overall_score,
    )

    if report.overall_verdict == AuditVerdict.FAIL:
        console.print("[bold red]Audit FAILED. Review the resume before proceeding.[/bold red]")
    else:
        console.print(f"[bold green]Resume v{version:03d} prepared and audit passed.[/bold green]")


@app.command()
def audit(
    job_id: str = typer.Argument(help="Job ID from the tracker, or path to a .meta.json file"),
    version: Optional[int] = typer.Option(None, "--version", "-v", help="Resume version number (default: latest)"),
) -> None:
    """Run truth audit on a previously generated resume."""
    meta_path: Path

    if Path(job_id).suffix in (".json", ".md"):
        p = Path(job_id)
        meta_path = p.with_suffix(".meta.json") if p.suffix == ".md" else p
    else:
        if version is None:
            version = config.next_resume_version(job_id) - 1
            if version < 1:
                console.print(f"[red]No resume versions found for job '{job_id}'.[/red]")
                raise typer.Exit(1)
        paths = config.version_paths(job_id, version)
        meta_path = paths["meta"]

    if not meta_path.exists():
        console.print(f"[red]Metadata file not found: {meta_path}[/red]")
        console.print("[dim]The audit command requires the .meta.json sidecar file.[/dim]")
        raise typer.Exit(1)

    tailored = TailoredResume.model_validate_json(meta_path.read_text(encoding="utf-8"))

    profile = config.load_profile()
    projects = config.load_projects()
    rules = config.load_rules()

    report = claim_auditor.audit_resume(tailored, projects, profile, rules)
    claim_auditor.print_audit_report(report)


@app.command()
def render_pdf(
    job_id: str = typer.Argument(help="Job ID from the tracker"),
    version: Optional[int] = typer.Option(None, "--version", "-v", help="Resume version (default: latest)"),
    allow_warn: bool = typer.Option(False, "--allow-warn", help="Proceed even if audit has warnings"),
) -> None:
    """Render a tailored resume to HTML and PDF."""
    if version is None:
        version = config.next_resume_version(job_id) - 1
        if version < 1:
            console.print(f"[red]No resume versions found for job '{job_id}'.[/red]")
            raise typer.Exit(1)

    paths = config.version_paths(job_id, version)
    meta_path = paths["meta"]

    if not meta_path.exists():
        console.print(f"[red]Metadata not found: {meta_path}[/red]")
        raise typer.Exit(1)

    tailored = TailoredResume.model_validate_json(meta_path.read_text(encoding="utf-8"))

    profile = config.load_profile()
    projects = config.load_projects()
    rules = config.load_rules()

    report = claim_auditor.audit_resume(tailored, projects, profile, rules)
    claim_auditor.print_audit_report(report)

    if report.overall_verdict == AuditVerdict.FAIL:
        console.print("[bold red]Audit FAILED. PDF generation blocked.[/bold red]")
        console.print("[dim]Fix the resume and re-run the tailor command first.[/dim]")
        raise typer.Exit(1)

    if report.overall_verdict == AuditVerdict.WARN and not allow_warn:
        console.print("[bold yellow]Audit has warnings. Use --allow-warn to proceed.[/bold yellow]")
        raise typer.Exit(1)

    html = pdf_renderer.render_html(tailored, profile)
    html_path = pdf_renderer.save_html(html, job_id, version)
    console.print(f"[green]HTML saved:[/green] {html_path}")

    pdf_path = paths["pdf"]
    asyncio.run(pdf_renderer.render_pdf(html_path, pdf_path))
    console.print(f"[green]PDF saved:[/green] {pdf_path}")

    console.print(f"\n[bold green]Resume v{version:03d} rendered successfully.[/bold green]")


@app.command()
def log(
    job_id: str = typer.Argument(help="Job ID to update"),
    new_status: str = typer.Argument(help="New status (found, prepared, reviewed, submitted, rejected, interview, assessment, offer, ghosted)"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Add notes"),
) -> None:
    """Update tracker status for a job application."""
    try:
        status_enum = TrackerStatus(new_status)
    except ValueError:
        valid = ", ".join(s.value for s in TrackerStatus)
        console.print(f"[red]Invalid status '{new_status}'. Valid: {valid}[/red]")
        raise typer.Exit(1)

    found = tracker.update_status(
        config.TRACKER_PATH, job_id, status_enum, notes=notes
    )
    if found:
        console.print(f"[green]Updated {job_id} -> {new_status}[/green]")
    else:
        console.print(f"[red]Job ID '{job_id}' not found in tracker.[/red]")


@app.command()
def status(
    filter_status: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter by status"),
) -> None:
    """Display the application tracker."""
    status_filter = None
    if filter_status:
        try:
            status_filter = TrackerStatus(filter_status)
        except ValueError:
            valid = ", ".join(s.value for s in TrackerStatus)
            console.print(f"[red]Invalid status '{filter_status}'. Valid: {valid}[/red]")
            raise typer.Exit(1)

    entries = tracker.list_entries(config.TRACKER_PATH, status_filter)
    tracker.print_tracker(entries)


@app.command()
def pipeline(
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Path to job description file"),
    company: Optional[str] = typer.Option(None, "--company", "-c", help="Override company name"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Override job title"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Job posting URL"),
) -> None:
    """Run the full pipeline: ingest -> score -> tailor -> audit."""
    config.ensure_directories()
    profile = config.load_profile()
    projects = config.load_projects()
    rules = config.load_rules()
    resume_config = config.load_resume_config()

    raw_text = _read_job_text(file)
    if not raw_text:
        console.print("[red]No job description provided.[/red]")
        raise typer.Exit(1)

    job = job_parser.parse_job_description(
        raw_text, profile, projects, rules,
        company_override=company, title_override=title,
    )

    console.print()
    console.print(Panel(
        f"[bold]{job.title}[/bold] at [bold]{job.company}[/bold]\n"
        f"Location: {job.location or 'Not specified'}\n"
        f"Keywords: {', '.join(job.extracted_keywords) or 'None'}",
        title="Parsed Job Posting",
    ))

    job_id = tracker.generate_job_id(job.company, job.title)
    raw_path = config.JOBS_RAW_DIR / f"{job_id}.txt"
    raw_path.write_text(raw_text, encoding="utf-8")

    fit = fit_scorer.score_fit(job, profile, projects, rules)
    _print_fit_score(fit, job)

    tailored = resume_tailor.tailor_resume(
        job, fit, profile, projects, resume_config, rules
    )

    version = config.next_resume_version(job_id)

    md = resume_tailor.render_resume_markdown(tailored, profile)
    resume_path = resume_tailor.save_resume(md, job_id, version)
    resume_tailor.save_resume_metadata(tailored, job_id, version)

    console.print(f"[green]Resume saved:[/green] {resume_path}")

    report = claim_auditor.audit_resume(tailored, projects, profile, rules)
    claim_auditor.print_audit_report(report)
    audit_path = claim_auditor.save_audit_report(report, job_id, version)

    is_existing = tracker.job_id_exists(config.TRACKER_PATH, job_id)
    if is_existing:
        tracker.update_status(
            config.TRACKER_PATH,
            job_id,
            TrackerStatus.PREPARED,
            resume_path=str(resume_path),
            audit_verdict=report.overall_verdict.value,
            latest_resume_version=version,
            fit_score=fit.overall_score,
        )
    else:
        entry = TrackerEntry(
            job_id=job_id,
            date_added=date.today(),
            company=job.company,
            role=job.title,
            url=url,
            status=TrackerStatus.PREPARED,
            fit_score=fit.overall_score,
            resume_path=str(resume_path),
            audit_verdict=report.overall_verdict.value,
            latest_resume_version=version,
        )
        tracker.add_entry(config.TRACKER_PATH, entry)

    console.print()
    console.rule("[bold]Pipeline Complete[/bold]")
    console.print(f"Job ID:      {job_id}")
    console.print(f"Version:     v{version:03d}")
    console.print(f"Fit:         {fit.recommendation} ({fit.overall_score:.0%})")
    console.print(f"Audit:       {report.overall_verdict.value}")
    console.print(f"Resume:      {resume_path}")
    console.print(f"Audit file:  {audit_path}")

    if report.overall_verdict == AuditVerdict.FAIL:
        console.print("\n[bold red]Audit FAILED. Review before proceeding.[/bold red]")
    else:
        console.print("\n[bold green]Ready for review.[/bold green]")
        console.print(f"Run [bold]python -m src.main render-pdf {job_id}[/bold] to generate PDF.")


def _print_fit_score(fit, job) -> None:
    matched = [m for m in fit.skill_matches if m.matched]
    unmatched_req = fit.missing_required
    unmatched_nice = fit.missing_nice_to_haves

    console.print(Panel(
        f"Overall: [bold]{fit.recommendation.upper()}[/bold] ({fit.overall_score:.0%})\n\n"
        f"[green]Strong matches:[/green]\n"
        + "\n".join(f"  + {m.skill}" for m in matched) + "\n\n"
        + (f"[red]Missing required:[/red]\n"
           + "\n".join(f"  - {s}" for s in unmatched_req) + "\n\n" if unmatched_req else "")
        + (f"[yellow]Missing nice-to-haves:[/yellow]\n"
           + "\n".join(f"  ~ {s}" for s in unmatched_nice) if unmatched_nice else ""),
        title=f"Fit Score: {job.company} - {job.title}",
    ))

    if fit.project_scores:
        table = Table(title="Project Relevance", show_header=True)
        table.add_column("Project")
        table.add_column("Score", justify="right")
        table.add_column("Matched Keywords")
        for ps in fit.project_scores:
            table.add_row(
                ps.project_name,
                f"{ps.relevance_score:.0%}",
                ", ".join(ps.matched_keywords[:5]) or "-",
            )
        console.print(table)


if __name__ == "__main__":
    app()
