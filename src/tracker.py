from __future__ import annotations

import csv
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.filelock import tracker_lock
from src.models import TrackerEntry, TrackerStatus

console = Console()

TRACKER_READ_ENCODING = "utf-8-sig"

TRACKER_COLUMNS = [
    "job_id",
    "date_added",
    "posted_at",
    "company",
    "role",
    "location",
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
    "source",
    "response_date",
    "response_type",
    "interview_stage",
    "source_quality",
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


_COLUMN_DEFAULTS: dict[str, str] = {
    "starred": "0",
    "posted_at": "",
    "location": "",
    "source": "",
    "response_date": "",
    "response_type": "",
    "interview_stage": "",
    "source_quality": "",
}

# Old scraper code wrote the source identifier (e.g. `hn:22665398`) into
# the `notes` column, which destroyed manual notes on first edit. New
# code uses the dedicated `source` column; this regex identifies legacy
# notes values that should migrate over.
_LEGACY_SOURCE_NOTES_RE = re.compile(r"^(hn|greenhouse|lever|ashby):", re.IGNORECASE)

# Legacy URL pollution: the HN scraper's regex used to capture footnote
# markers like `[2]` and trailing punctuation. Detect and clean.
_URL_TRAILING_PUNCT = ".,;:!?"


def _clean_url(url: str) -> str:
    """Strip footnote markers, trailing punctuation, and unbalanced parens.

    Matches the cleaning behavior of scraper.sources._url.clean_url so
    new scrapes and the migration produce the same shape.
    """
    if not url:
        return ""
    url = url.strip()
    # HN footnote markers: `https://...[2]` — strip the trailing bracket pair.
    url = re.sub(r"\[\d+\]$", "", url)
    # Also strip stray trailing brackets entirely.
    while url and url[-1] in "[]":
        url = url[:-1]
    while url and url[-1] in _URL_TRAILING_PUNCT:
        url = url[:-1]
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]
    while url and url[-1] in _URL_TRAILING_PUNCT:
        url = url[:-1]
    return url


def _migrate_if_needed_unlocked(tracker_path: Path) -> None:
    """Bring tracker.csv up to the current TRACKER_COLUMNS layout in one pass.

    Header-agnostic: maps each row's values via the file's own header line
    (when row length matches that header) and fills in any TRACKER_COLUMNS
    keys that didn't exist before with sensible defaults. This way every
    future column addition gets handled by a single _COLUMN_DEFAULTS entry,
    not a new code path. Also performs idempotent data-cleanup passes
    (e.g. moving legacy scraper source out of the notes column) even when
    the header itself is already current.
    """
    if not tracker_path.exists():
        return
    with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return
        body = list(reader)

    header_current = header == TRACKER_COLUMNS
    needs_data_cleanup = _body_needs_cleanup(header, body)
    if header_current and not needs_data_cleanup:
        return

    normalized = _normalize_rows(header, body)

    with open(tracker_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
        writer.writeheader()
        for row in normalized:
            writer.writerow(row)


def _normalize_rows(header: list[str], body: list[list[str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for raw_row in body:
        if not raw_row:
            continue
        if len(raw_row) == len(header):
            row = dict(zip(header, raw_row))
        elif len(raw_row) == len(TRACKER_COLUMNS):
            # Row was written under the current schema even though the file
            # header is stale; trust the positional match against the
            # current column list.
            row = dict(zip(TRACKER_COLUMNS, raw_row))
        else:
            # Pad or truncate against the header line as a best-effort.
            padded = list(raw_row) + [""] * (len(header) - len(raw_row))
            row = dict(zip(header, padded[: len(header)]))
        result = {col: row.get(col, _COLUMN_DEFAULTS.get(col, "")) for col in TRACKER_COLUMNS}
        # Move legacy scraper-source values out of `notes` into `source`
        # so manual notes have somewhere clean to live.
        if not result.get("source") and _LEGACY_SOURCE_NOTES_RE.match(result.get("notes", "")):
            result["source"] = result["notes"]
            result["notes"] = ""
        # Clean URLs polluted by the old extractor (HN `[N]` footnote
        # markers, trailing punctuation, unbalanced parens).
        url_raw = result.get("url", "")
        if url_raw:
            cleaned = _clean_url(url_raw)
            if cleaned != url_raw:
                result["url"] = cleaned
        normalized.append(result)
    return normalized


def _body_needs_cleanup(header: list[str], body: list[list[str]]) -> bool:
    """Detect rows needing data cleanup independent of header changes.

    Two cases:
    - legacy scraper source stuck in `notes` without a matching `source`
    - URL values still polluted by the old extractor (HN footnote markers,
      trailing punctuation, unbalanced closing parens)
    """
    notes_idx = header.index("notes") if "notes" in header else None
    source_idx = header.index("source") if "source" in header else None
    url_idx = header.index("url") if "url" in header else None

    for raw_row in body:
        if not raw_row:
            continue
        if notes_idx is not None and len(raw_row) > notes_idx:
            notes = (raw_row[notes_idx] or "").strip()
            if notes and _LEGACY_SOURCE_NOTES_RE.match(notes):
                existing_source = ""
                if source_idx is not None and len(raw_row) > source_idx:
                    existing_source = (raw_row[source_idx] or "").strip()
                if not existing_source:
                    return True
        if url_idx is not None and len(raw_row) > url_idx:
            url = (raw_row[url_idx] or "").strip()
            if url and _clean_url(url) != url:
                return True
    return False


def generate_job_id(company: str, title: str) -> str:
    slug = f"{company}-{title}-{date.today().strftime('%Y%m%d')}"
    slug = slug.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:60]


def add_entry(tracker_path: Path, entry: TrackerEntry) -> bool:
    """Append an entry, idempotently. Returns True if added, False if the
    job_id already existed.

    The existence check and the append happen inside a single lock
    acquisition. Callers like the /discover endpoint do their own
    job_id_exists() pre-check, but that is a separate lock acquisition —
    leaving a TOCTOU window where two concurrent discoveries of the same
    posting could both append. Doing the check-and-append atomically here
    closes that window so the tracker can never accumulate duplicate rows.
    """
    with tracker_lock():
        _ensure_tracker_exists_unlocked(tracker_path)
        _migrate_if_needed_unlocked(tracker_path)
        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
            existing = {row["job_id"] for row in csv.DictReader(f)}
        if entry.job_id in existing:
            return False
        with open(tracker_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
            writer.writerow(_entry_to_row(entry))
        return True


def backup_tracker(tracker_path: Path, backup_dir: Path | None = None, prefix: str = "tracker.backup") -> Path:
    """Create a timestamped CSV backup of the tracker and return its path."""
    with tracker_lock():
        _ensure_tracker_exists_unlocked(tracker_path)
        _migrate_if_needed_unlocked(tracker_path)
        return _backup_tracker_unlocked(tracker_path, backup_dir, prefix)


def restore_tracker(
    tracker_path: Path,
    backup_path: Path,
    *,
    create_pre_restore_backup: bool = True,
) -> Path | None:
    """Replace tracker.csv with a validated backup CSV.

    Returns the pre-restore backup path when one was created.
    """
    with tracker_lock():
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        with open(backup_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValueError(f"Backup file is empty: {backup_path}") from exc
            if "job_id" not in header:
                raise ValueError(f"Backup file does not look like a tracker CSV: {backup_path}")
            body = list(reader)

        pre_restore_path = None
        if create_pre_restore_backup and tracker_path.exists():
            _migrate_if_needed_unlocked(tracker_path)
            pre_restore_path = _backup_tracker_unlocked(
                tracker_path,
                tracker_path.parent,
                "tracker.pre-restore",
            )

        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = _normalize_rows(header, body)
        with open(tracker_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
            writer.writeheader()
            writer.writerows(normalized)
        return pre_restore_path


def _backup_tracker_unlocked(tracker_path: Path, backup_dir: Path | None, prefix: str) -> Path:
    backup_root = backup_dir or tracker_path.parent
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_root / f"{prefix}-{stamp}.csv"
    backup_path.write_bytes(tracker_path.read_bytes())
    return backup_path


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
    location: str | None = None,
    source: str | None = None,
    response_date: date | None = None,
    response_date_set: bool = False,
    response_type: str | None = None,
    response_type_set: bool = False,
    interview_stage: str | None = None,
    interview_stage_set: bool = False,
    source_quality: int | None = None,
    source_quality_set: bool = False,
) -> bool:
    with tracker_lock():
        if not tracker_path.exists():
            return False
        _migrate_if_needed_unlocked(tracker_path)

        rows: list[dict] = []
        found = False
        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
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
                    if location is not None:
                        row["location"] = location
                    if source is not None:
                        row["source"] = source
                    if response_date_set:
                        row["response_date"] = response_date.isoformat() if response_date else ""
                    if response_type_set:
                        row["response_type"] = response_type or ""
                    if interview_stage_set:
                        row["interview_stage"] = interview_stage or ""
                    if source_quality_set:
                        row["source_quality"] = str(source_quality) if source_quality is not None else ""
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
        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
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


_PROTECTED_STATUSES = {
    TrackerStatus.PREPARED,
    TrackerStatus.REVIEWED,
    TrackerStatus.SUBMITTED,
    TrackerStatus.INTERVIEW,
    TrackerStatus.ASSESSMENT,
    TrackerStatus.OFFER,
    TrackerStatus.REJECTED,
    TrackerStatus.GHOSTED,
    TrackerStatus.ARCHIVED,
}


def archive_stale_discoveries(
    tracker_path: Path,
    max_age_days: int = 7,
) -> int:
    """Archive found-status jobs older than max_age_days.

    Uses posted_at if available, otherwise date_added.
    Skips starred jobs and anything beyond 'found' status.
    """
    cutoff = date.today() - timedelta(days=max_age_days)

    with tracker_lock():
        if not tracker_path.exists():
            return 0
        _migrate_if_needed_unlocked(tracker_path)

        rows: list[dict] = []
        archived = 0
        today = date.today().isoformat()

        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = TrackerStatus(row["status"])
                if status in _PROTECTED_STATUSES or status != TrackerStatus.FOUND:
                    rows.append(row)
                    continue

                starred = (row.get("starred") or "").strip().lower() in {"1", "true", "yes"}
                if starred:
                    rows.append(row)
                    continue

                posted_raw = (row.get("posted_at") or "").strip()
                added_raw = row.get("date_added", "")
                ref_date_str = posted_raw or added_raw
                try:
                    ref_date = date.fromisoformat(ref_date_str)
                except (ValueError, TypeError):
                    rows.append(row)
                    continue

                if ref_date < cutoff:
                    row["status"] = TrackerStatus.ARCHIVED.value
                    row["date_updated"] = today
                    archived += 1

                rows.append(row)

        if archived:
            with open(tracker_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

    return archived


def job_id_exists(tracker_path: Path, job_id: str) -> bool:
    with tracker_lock():
        if not tracker_path.exists():
            return False
        _migrate_if_needed_unlocked(tracker_path)
        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
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
        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["job_id"] == job_id:
                    return _row_to_entry(row)
        return None


def delete_entry(tracker_path: Path, job_id: str) -> bool:
    with tracker_lock():
        if not tracker_path.exists():
            return False
        _migrate_if_needed_unlocked(tracker_path)
        rows: list[dict] = []
        found = False
        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["job_id"] == job_id:
                    found = True
                    continue
                rows.append(row)
        if found:
            with open(tracker_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=TRACKER_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
        return found


def get_latest_entry(tracker_path: Path) -> TrackerEntry | None:
    with tracker_lock():
        if not tracker_path.exists():
            return None
        _migrate_if_needed_unlocked(tracker_path)
        last_row = None
        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
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
        with open(tracker_path, "r", newline="", encoding=TRACKER_READ_ENCODING) as f:
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
        "posted_at": entry.posted_at.isoformat() if entry.posted_at else "",
        "company": entry.company,
        "role": entry.role,
        "location": entry.location or "",
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
        "source": entry.source or "",
        "response_date": entry.response_date.isoformat() if entry.response_date else "",
        "response_type": entry.response_type or "",
        "interview_stage": entry.interview_stage or "",
        "source_quality": str(entry.source_quality) if entry.source_quality is not None else "",
        "date_updated": entry.date_updated.isoformat(),
    }


def _row_to_entry(row: dict) -> TrackerEntry:
    fit = row.get("fit_score", "")
    ver = row.get("latest_resume_version", "")
    starred_raw = (row.get("starred") or "").strip().lower()
    posted_raw = (row.get("posted_at") or "").strip()
    response_raw = (row.get("response_date") or "").strip()
    source_quality_raw = (row.get("source_quality") or "").strip()
    try:
        source_quality = int(source_quality_raw) if source_quality_raw else None
    except ValueError:
        source_quality = None
    return TrackerEntry(
        job_id=row["job_id"],
        date_added=date.fromisoformat(row["date_added"]),
        posted_at=date.fromisoformat(posted_raw) if posted_raw else None,
        company=row["company"],
        role=row["role"],
        location=row.get("location") or None,
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
        source=row.get("source") or None,
        response_date=date.fromisoformat(response_raw) if response_raw else None,
        response_type=row.get("response_type") or None,
        interview_stage=row.get("interview_stage") or None,
        source_quality=source_quality,
        date_updated=date.fromisoformat(row.get("date_updated", date.today().isoformat())),
    )
