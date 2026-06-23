from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pytest

from src.models import TrackerEntry, TrackerStatus
from src.tracker import (
    add_entry,
    backup_tracker,
    ensure_tracker_exists,
    generate_job_id,
    get_entry,
    list_entries,
    restore_tracker,
    update_status,
)


@pytest.fixture
def tmp_tracker(tmp_path) -> Path:
    return tmp_path / "tracker.csv"


def _make_entry(job_id: str = "test-swe-20260506", company: str = "TestCo", role: str = "SWE") -> TrackerEntry:
    return TrackerEntry(
        job_id=job_id,
        date_added=date(2026, 5, 6),
        company=company,
        role=role,
        status=TrackerStatus.FOUND,
    )


class TestTracker:
    def test_ensure_creates_file(self, tmp_tracker):
        ensure_tracker_exists(tmp_tracker)
        assert tmp_tracker.exists()
        content = tmp_tracker.read_text()
        assert "job_id" in content

    def test_add_and_get_entry(self, tmp_tracker):
        entry = _make_entry()
        add_entry(tmp_tracker, entry)
        retrieved = get_entry(tmp_tracker, "test-swe-20260506")
        assert retrieved is not None
        assert retrieved.company == "TestCo"
        assert retrieved.status == TrackerStatus.FOUND

    def test_update_status(self, tmp_tracker):
        entry = _make_entry()
        add_entry(tmp_tracker, entry)
        updated = update_status(tmp_tracker, "test-swe-20260506", TrackerStatus.PREPARED, notes="Ready")
        assert updated is True
        retrieved = get_entry(tmp_tracker, "test-swe-20260506")
        assert retrieved.status == TrackerStatus.PREPARED

    def test_update_feedback_fields(self, tmp_tracker):
        entry = _make_entry()
        add_entry(tmp_tracker, entry)
        updated = update_status(
            tmp_tracker,
            "test-swe-20260506",
            TrackerStatus.INTERVIEW,
            response_date=date(2026, 6, 3),
            response_date_set=True,
            response_type="recruiter_screen",
            response_type_set=True,
            interview_stage="recruiter",
            interview_stage_set=True,
            source_quality=4,
            source_quality_set=True,
        )
        assert updated is True
        retrieved = get_entry(tmp_tracker, "test-swe-20260506")
        assert retrieved.status == TrackerStatus.INTERVIEW
        assert retrieved.response_date == date(2026, 6, 3)
        assert retrieved.response_type == "recruiter_screen"
        assert retrieved.interview_stage == "recruiter"
        assert retrieved.source_quality == 4

        update_status(
            tmp_tracker,
            "test-swe-20260506",
            TrackerStatus.INTERVIEW,
            response_date=None,
            response_date_set=True,
            response_type=None,
            response_type_set=True,
            interview_stage=None,
            interview_stage_set=True,
            source_quality=None,
            source_quality_set=True,
        )
        retrieved = get_entry(tmp_tracker, "test-swe-20260506")
        assert retrieved.response_date is None
        assert retrieved.response_type is None
        assert retrieved.interview_stage is None
        assert retrieved.source_quality is None

    def test_update_nonexistent_returns_false(self, tmp_tracker):
        ensure_tracker_exists(tmp_tracker)
        result = update_status(tmp_tracker, "nonexistent", TrackerStatus.PREPARED)
        assert result is False

    def test_reads_and_updates_utf8_bom_tracker(self, tmp_tracker):
        tmp_tracker.write_text(
            "job_id,date_added,company,role,status,date_updated\n"
            "bom-job,2026-06-11,ExampleCo,Engineer,submitted,2026-06-11\n",
            encoding="utf-8-sig",
        )

        entry = get_entry(tmp_tracker, "bom-job")
        assert entry is not None
        assert entry.job_id == "bom-job"

        updated = update_status(
            tmp_tracker, "bom-job", TrackerStatus.INTERVIEW
        )
        assert updated is True
        assert get_entry(tmp_tracker, "bom-job").status == TrackerStatus.INTERVIEW

    def test_list_entries_filter(self, tmp_tracker):
        add_entry(tmp_tracker, _make_entry("job-a", "CompanyA", "SWE"))
        add_entry(tmp_tracker, _make_entry("job-b", "CompanyB", "SWE"))

        update_status(tmp_tracker, "job-a", TrackerStatus.PREPARED)

        all_entries = list_entries(tmp_tracker)
        assert len(all_entries) == 2

        prepared = list_entries(tmp_tracker, TrackerStatus.PREPARED)
        assert len(prepared) == 1
        assert prepared[0].job_id == "job-a"

    def test_generate_job_id_format(self):
        jid = generate_job_id("Google", "Software Engineer")
        assert "google" in jid
        assert "software-engineer" in jid
        assert len(jid) <= 60

    def test_migrates_feedback_columns(self, tmp_tracker):
        tmp_tracker.write_text(
            "job_id,date_added,company,role,status,date_updated\n"
            "legacy,2026-05-06,LegacyCo,SWE,submitted,2026-05-06\n",
            encoding="utf-8",
        )

        entry = get_entry(tmp_tracker, "legacy")

        assert entry is not None
        assert entry.response_date is None
        assert entry.response_type is None
        assert "response_date" in tmp_tracker.read_text(encoding="utf-8").splitlines()[0]

    def test_backup_and_restore_tracker(self, tmp_tracker, tmp_path):
        add_entry(tmp_tracker, _make_entry("job-a", "CompanyA", "SWE"))
        backup = backup_tracker(tmp_tracker, backup_dir=tmp_path)
        assert backup.exists()

        add_entry(tmp_tracker, _make_entry("job-b", "CompanyB", "SWE"))
        assert len(list_entries(tmp_tracker)) == 2

        pre_restore = restore_tracker(tmp_tracker, backup)

        assert pre_restore is not None
        assert pre_restore.exists()
        entries = list_entries(tmp_tracker)
        assert len(entries) == 1
        assert entries[0].job_id == "job-a"
