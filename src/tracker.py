from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.models import TrackerEntry, TrackerStatus

console = Console()

TRACKER_COLUMNS = [
    "job_id",
    "date_added",
    "company",
    "role",
    "url",
    "status",
    "fit_score",
    "resume_path",
    "cover_letter_path",
    "audit_verdict",
    "latest_resume_version",
    "notes",
    "next_action",
    "date_updated",
]


def ensure_tracker_exists(tracker_path: Path) -> None:
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    if not tracker_path.exists():
        with open(tracker_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(TRACKER_COLUMNS)


def generate_job_id(company: str, title: str) -> str:
    slug = f"{company}-{title}-{date.today().strftime('%Y%m%d')}"
    slug = slug.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:60]


def add_entry(tracker_path: Path, entry: TrackerEntry) -> None:
    ensure_tracker_exists(tracker_path)
    with open(tracker_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
        writer.writerow(_entry_to_row(entry))


def update_status(
    tracker_path: Path,
    job_id: str,
    new_status: TrackerStatus,
    notes: str | None = None,
    resume_path: str | None = None,
    audit_verdict: str | None = None,
    latest_resume_version: int | None = None,
    fit_score: float | None = None,
) -> bool:
    if not tracker_path.exists():
        return False

    rows: list[dict] = []
    found = False
    with open(tracker_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["job_id"] == job_id:
                row["status"] = new_status.value
                row["date_updated"] = date.today().isoformat()
                if notes:
                    row["notes"] = notes
                if resume_path:
                    row["resume_path"] = resume_path
                if audit_verdict:
                    row["audit_verdict"] = audit_verdict
                if latest_resume_version is not None:
                    row["latest_resume_version"] = str(latest_resume_version)
                if fit_score is not None:
                    row["fit_score"] = str(fit_score)
                found = True
            rows.append(row)

    if found:
        with open(tracker_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    return found


def job_id_exists(tracker_path: Path, job_id: str) -> bool:
    if not tracker_path.exists():
        return False
    with open(tracker_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["job_id"] == job_id:
                return True
    return False


def get_entry(tracker_path: Path, job_id: str) -> TrackerEntry | None:
    if not tracker_path.exists():
        return None
    with open(tracker_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["job_id"] == job_id:
                return _row_to_entry(row)
    return None


def get_latest_entry(tracker_path: Path) -> TrackerEntry | None:
    if not tracker_path.exists():
        return None
    last_row = None
    with open(tracker_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            last_row = row
    if last_row:
        return _row_to_entry(last_row)
    return None


def list_entries(
    tracker_path: Path, status_filter: TrackerStatus | None = None
) -> list[TrackerEntry]:
    if not tracker_path.exists():
        return []
    entries: list[TrackerEntry] = []
    with open(tracker_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = _row_to_entry(row)
            if status_filter is None or entry.status == status_filter:
                entries.append(entry)
    return entries


def print_tracker(entries: list[TrackerEntry]) -> None:
    if not entries:
        console.print("[dim]No entries found.[/dim]")
        return

    table = Table(title="Job Application Tracker", show_header=True)
    table.add_column("Job ID", style="cyan", max_width=30)
    table.add_column("Company")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("Fit", justify="right")
    table.add_column("Audit")
    table.add_column("Ver", justify="right")
    table.add_column("Date Added")

    status_styles = {
        "found": "dim",
        "prepared": "yellow",
        "reviewed": "blue",
        "submitted": "green",
        "rejected": "red",
        "interview": "bold green",
        "assessment": "bold cyan",
        "offer": "bold magenta",
        "ghosted": "dim red",
    }

    for e in entries:
        style = status_styles.get(e.status.value, "")
        fit_str = f"{e.fit_score:.0%}" if e.fit_score is not None else "-"
        audit_str = e.audit_verdict or "-"
        ver_str = str(e.latest_resume_version) if e.latest_resume_version is not None else "-"
        table.add_row(
            e.job_id,
            e.company,
            e.role,
            f"[{style}]{e.status.value}[/{style}]" if style else e.status.value,
            fit_str,
            audit_str,
            ver_str,
            e.date_added.isoformat(),
        )

    console.print(table)


def _entry_to_row(entry: TrackerEntry) -> dict:
    return {
        "job_id": entry.job_id,
        "date_added": entry.date_added.isoformat(),
        "company": entry.company,
        "role": entry.role,
        "url": entry.url or "",
        "status": entry.status.value,
        "fit_score": str(entry.fit_score) if entry.fit_score is not None else "",
        "resume_path": entry.resume_path or "",
        "cover_letter_path": entry.cover_letter_path or "",
        "audit_verdict": entry.audit_verdict or "",
        "latest_resume_version": str(entry.latest_resume_version) if entry.latest_resume_version is not None else "",
        "notes": entry.notes or "",
        "next_action": entry.next_action or "",
        "date_updated": entry.date_updated.isoformat(),
    }


def _row_to_entry(row: dict) -> TrackerEntry:
    fit = row.get("fit_score", "")
    ver = row.get("latest_resume_version", "")
    return TrackerEntry(
        job_id=row["job_id"],
        date_added=date.fromisoformat(row["date_added"]),
        company=row["company"],
        role=row["role"],
        url=row.get("url") or None,
        status=TrackerStatus(row["status"]),
        fit_score=float(fit) if fit else None,
        resume_path=row.get("resume_path") or None,
        cover_letter_path=row.get("cover_letter_path") or None,
        audit_verdict=row.get("audit_verdict") or None,
        latest_resume_version=int(ver) if ver else None,
        notes=row.get("notes") or None,
        next_action=row.get("next_action") or None,
        date_updated=date.fromisoformat(row.get("date_updated", date.today().isoformat())),
    )
