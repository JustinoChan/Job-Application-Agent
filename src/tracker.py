from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.filelock import tracker_lock
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
    "starred",
    "date_updated",
]


def ensure_tracker_exists(tracker_path: Path) -> None:
    with tracker_lock():
        _ensure_tracker_exists_unlocked(tracker_path)
        _migrate_if_needed_unlocked(tracker_path)


def _ensure_tracker_exists_unlocked(tracker_path: Path) -> None:
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    if not tracker_path.exists():
        with open(tracker_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(TRACKER_COLUMNS)


def _migrate_if_needed_unlocked(tracker_path: Path) -> None:
    """Bring tracker.csv up to the current TRACKER_COLUMNS layout in one pass.

    Handles two legacy shapes that can coexist in the same file:
    - rows written when there were no `starred` column (one short)
    - rows written under a stale header that lacks `starred`
    """
    if not tracker_path.exists():
        return
    with open(tracker_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return
        if header == TRACKER_COLUMNS:
            return
        body = list(reader)

    starred_idx = TRACKER_COLUMNS.index("starred")
    normalized: list[dict[str, str]] = []
    for raw_row in body:
        if not raw_row:
            continue
        if len(raw_row) == len(TRACKER_COLUMNS):
            row = dict(zip(TRACKER_COLUMNS, raw_row))
        elif len(raw_row) == len(TRACKER_COLUMNS) - 1:
            # Old row missing the starred column — insert "0" in the right slot
            patched = list(raw_row[:starred_idx]) + ["0"] + list(raw_row[starred_idx:])
            row = dict(zip(TRACKER_COLUMNS, patched))
        else:
            # Best-effort: map what we can from the old header, default the rest
            mapped = {k: v for k, v in zip(header, raw_row)}
            row = {col: mapped.get(col, "") for col in TRACKER_COLUMNS}
            if not row.get("starred"):
                row["starred"] = "0"
        normalized.append(row)

    with open(tracker_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
        writer.writeheader()
        for row in normalized:
            writer.writerow({k: row.get(k, "") for k in TRACKER_COLUMNS})


def generate_job_id(company: str, title: str) -> str:
    slug = f"{company}-{title}-{date.today().strftime('%Y%m%d')}"
    slug = slug.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:60]


def add_entry(tracker_path: Path, entry: TrackerEntry) -> None:
    with tracker_lock():
        _ensure_tracker_exists_unlocked(tracker_path)
        _migrate_if_needed_unlocked(tracker_path)
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
    cover_letter_path: str | None = None,
    starred: bool | None = None,
) -> bool:
    with tracker_lock():
        if not tracker_path.exists():
            return False
        _migrate_if_needed_unlocked(tracker_path)

        rows: list[dict] = []
        found = False
        with open(tracker_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["job_id"] == job_id:
                    row["status"] = new_status.value
                    row["date_updated"] = date.today().isoformat()
                    if notes is not None:
                        row["notes"] = notes
                    if resume_path:
                        row["resume_path"] = resume_path
                    if audit_verdict:
                        row["audit_verdict"] = audit_verdict
                    if latest_resume_version is not None:
                        row["latest_resume_version"] = str(latest_resume_version)
                    if fit_score is not None:
                        row["fit_score"] = str(fit_score)
                    if cover_letter_path:
                        row["cover_letter_path"] = cover_letter_path
                    if starred is not None:
                        row["starred"] = "1" if starred else "0"
                    found = True
                rows.append(row)

        if found:
            with open(tracker_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

        return found


def bulk_update_status(
    tracker_path: Path,
    job_ids: list[str],
    new_status: TrackerStatus,
) -> int:
    """Set status=new_status for every row whose job_id is in job_ids. Returns count updated."""
    target = set(job_ids)
    if not target:
        return 0
    with tracker_lock():
        if not tracker_path.exists():
            return 0
        _migrate_if_needed_unlocked(tracker_path)
        rows: list[dict] = []
        updated = 0
        today = date.today().isoformat()
        with open(tracker_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["job_id"] in target:
                    row["status"] = new_status.value
                    row["date_updated"] = today
                    updated += 1
                rows.append(row)

        if updated:
            with open(tracker_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
        return updated


def job_id_exists(tracker_path: Path, job_id: str) -> bool:
    with tracker_lock():
        if not tracker_path.exists():
            return False
        _migrate_if_needed_unlocked(tracker_path)
        with open(tracker_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["job_id"] == job_id:
                    return True
        return False


def get_entry(tracker_path: Path, job_id: str) -> TrackerEntry | None:
    with tracker_lock():
        if not tracker_path.exists():
            return None
        _migrate_if_needed_unlocked(tracker_path)
        with open(tracker_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["job_id"] == job_id:
                    return _row_to_entry(row)
        return None


def get_latest_entry(tracker_path: Path) -> TrackerEntry | None:
    with tracker_lock():
        if not tracker_path.exists():
            return None
        _migrate_if_needed_unlocked(tracker_path)
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
    with tracker_lock():
        if not tracker_path.exists():
            return []
        _migrate_if_needed_unlocked(tracker_path)
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
        "archived": "dim",
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
        "starred": "1" if entry.starred else "0",
        "date_updated": entry.date_updated.isoformat(),
    }


def _row_to_entry(row: dict) -> TrackerEntry:
    fit = row.get("fit_score", "")
    ver = row.get("latest_resume_version", "")
    starred_raw = (row.get("starred") or "").strip().lower()
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
        starred=starred_raw in {"1", "true", "yes"},
        date_updated=date.fromisoformat(row.get("date_updated", date.today().isoformat())),
    )
