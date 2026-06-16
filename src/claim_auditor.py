"""Claim auditor (the truth gate): verifies every resume bullet against source facts + hard constraints; a FAIL blocks rendering."""
from __future__ import annotations

import difflib
import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.models import (
    ApplicationRules,
    AuditEntry,
    AuditReport,
    AuditVerdict,
    Fact,
    MasterProfile,
    Project,
    TailoredResume,
)

console = Console()


def audit_resume(
    tailored: TailoredResume,
    projects: list[Project],
    profile: MasterProfile,
    rules: ApplicationRules,
) -> AuditReport:
    fact_lookup: dict[str, dict[str, Fact]] = {}
    for proj in projects:
        fact_lookup[proj.id] = {f.id: f for f in proj.facts}

    entries: list[AuditEntry] = []
    for tproj in tailored.selected_projects:
        for sf in tproj.selected_facts:
            entry = _verify_fact(sf.fact_id, sf.project_id, sf.original_text, fact_lookup)
            entries.append(entry)

    violations = _check_hard_constraints(tailored, profile, rules)

    passed = sum(1 for e in entries if e.verdict == AuditVerdict.PASS)
    warned = sum(1 for e in entries if e.verdict == AuditVerdict.WARN)
    failed = sum(1 for e in entries if e.verdict == AuditVerdict.FAIL)

    if failed > 0 or violations:
        overall = AuditVerdict.FAIL
    elif warned > 0:
        overall = AuditVerdict.WARN
    else:
        overall = AuditVerdict.PASS

    return AuditReport(
        total_claims=len(entries),
        passed=passed,
        warned=warned,
        failed=failed,
        entries=entries,
        hard_constraint_violations=violations,
        overall_verdict=overall,
    )


def _verify_fact(
    fact_id: str,
    project_id: str,
    resume_text: str,
    fact_lookup: dict[str, dict[str, Fact]],
) -> AuditEntry:
    project_facts = fact_lookup.get(project_id)
    if project_facts is None:
        return AuditEntry(
            fact_id=fact_id,
            project_id=project_id,
            resume_text=resume_text,
            source_text="",
            verdict=AuditVerdict.FAIL,
            reason=f"Project '{project_id}' not found in source data",
        )

    source_fact = project_facts.get(fact_id)
    if source_fact is None:
        return AuditEntry(
            fact_id=fact_id,
            project_id=project_id,
            resume_text=resume_text,
            source_text="",
            verdict=AuditVerdict.FAIL,
            reason=f"Fact '{fact_id}' not found in project '{project_id}'",
        )

    similarity = _text_similarity(resume_text, source_fact.text)

    if similarity >= 0.99:
        return AuditEntry(
            fact_id=fact_id,
            project_id=project_id,
            resume_text=resume_text,
            source_text=source_fact.text,
            verdict=AuditVerdict.PASS,
            reason="Exact match with source",
        )
    elif similarity >= 0.85:
        return AuditEntry(
            fact_id=fact_id,
            project_id=project_id,
            resume_text=resume_text,
            source_text=source_fact.text,
            verdict=AuditVerdict.WARN,
            reason=f"Minor variation from source (similarity: {similarity:.0%})",
        )
    else:
        return AuditEntry(
            fact_id=fact_id,
            project_id=project_id,
            resume_text=resume_text,
            source_text=source_fact.text,
            verdict=AuditVerdict.FAIL,
            reason=f"Text differs significantly from source (similarity: {similarity:.0%})",
        )


FORBIDDEN_PHRASES = [
    "internship",
    "intern ",
    "professional experience",
    "work experience",
    "industry experience",
    "employed at",
    "worked at",
]


def check_text_hard_constraints(text: str, rules: ApplicationRules) -> list[str]:
    """Scan arbitrary text for forbidden phrases. Returns violation messages."""
    violations: list[str] = []
    full_text = text.lower()

    for constraint in rules.never_claim:
        if constraint.lower() in full_text:
            violations.append(f"Never-claim violation: '{constraint}' found in text")

    for phrase in FORBIDDEN_PHRASES:
        if phrase in full_text:
            violations.append(f"Forbidden phrase detected: '{phrase.strip()}'")

    return violations


def _check_hard_constraints(
    tailored: TailoredResume,
    profile: MasterProfile,
    rules: ApplicationRules,
) -> list[str]:
    all_text_parts: list[str] = []
    for tproj in tailored.selected_projects:
        for sf in tproj.selected_facts:
            all_text_parts.append(sf.original_text)
    return check_text_hard_constraints(" ".join(all_text_parts), rules)


def _text_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.strip(), b.strip()).ratio()


def save_audit_report(report: AuditReport, job_id: str, version: int) -> Path:
    from src import config
    paths = config.version_paths(job_id, version)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["audit"].write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return paths["audit"]


def print_audit_report(report: AuditReport) -> None:
    verdict_icons = {
        AuditVerdict.PASS: "[green]PASS[/green]",
        AuditVerdict.WARN: "[yellow]WARN[/yellow]",
        AuditVerdict.FAIL: "[red]FAIL[/red]",
    }

    console.print()
    console.rule("[bold]Claim Audit Report[/bold]")
    console.print()

    table = Table(show_header=True)
    table.add_column("Verdict", width=8)
    table.add_column("Fact ID", width=20)
    table.add_column("Reason", ratio=1)

    for entry in report.entries:
        table.add_row(
            verdict_icons[entry.verdict],
            entry.fact_id,
            entry.reason,
        )

    console.print(table)

    if report.hard_constraint_violations:
        console.print()
        console.print("[bold red]Hard Constraint Violations:[/bold red]")
        for v in report.hard_constraint_violations:
            console.print(f"  [red]X[/red] {v}")

    console.print()
    console.print(
        f"Total: {report.total_claims}  |  "
        f"[green]Pass: {report.passed}[/green]  |  "
        f"[yellow]Warn: {report.warned}[/yellow]  |  "
        f"[red]Fail: {report.failed}[/red]"
    )
    overall_display = verdict_icons[report.overall_verdict]
    console.print(f"Overall: {overall_display}")
    console.print()
