from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from src import config
from src.models import TrackerEntry, TrackerStatus
from src.tracker import (
    TRACKER_COLUMNS,
    add_entry,
    ensure_tracker_exists,
    get_entry,
    job_id_exists,
    update_status,
)


class TestNextResumeVersion:
    def test_starts_at_1_for_new_job(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RESUMES_DIR", tmp_path)
        assert config.next_resume_version("new-job-id") == 1

    def test_increments_after_existing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RESUMES_DIR", tmp_path)
        job_dir = tmp_path / "test-job"
        job_dir.mkdir()
        (job_dir / "resume_v001.md").write_text("v1")
        assert config.next_resume_version("test-job") == 2

    def test_finds_max_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RESUMES_DIR", tmp_path)
        job_dir = tmp_path / "test-job"
        job_dir.mkdir()
        (job_dir / "resume_v001.md").write_text("v1")
        (job_dir / "resume_v003.md").write_text("v3")
        assert config.next_resume_version("test-job") == 4

    def test_old_versions_not_overwritten(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RESUMES_DIR", tmp_path)
        job_dir = tmp_path / "test-job"
        job_dir.mkdir()
        (job_dir / "resume_v001.md").write_text("original content")

        v2_paths = config.version_paths("test-job", 2)
        v2_paths["dir"].mkdir(parents=True, exist_ok=True)
        v2_paths["md"].write_text("v2 content")

        assert (job_dir / "resume_v001.md").read_text() == "original content"
        assert (job_dir / "resume_v002.md").read_text() == "v2 content"


class TestVersionPaths:
    def test_returns_correct_paths(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RESUMES_DIR", tmp_path)
        paths = config.version_paths("my-job", 1)
        assert paths["md"].name == "resume_v001.md"
        assert paths["meta"].name == "resume_v001.meta.json"
        assert paths["audit"].name == "resume_v001.audit.json"
        assert paths["html"].name == "resume_v001.html"
        assert paths["pdf"].name == "resume_v001.pdf"
        assert paths["dir"] == tmp_path / "my-job"


class TestTrackerVersionColumn:
    def test_latest_version_stored_and_read(self, tmp_path):
        tracker_path = tmp_path / "tracker.csv"
        entry = TrackerEntry(
            job_id="test-job",
            date_added=date.today(),
            company="TestCo",
            role="Engineer",
            status=TrackerStatus.PREPARED,
            latest_resume_version=3,
        )
        add_entry(tracker_path, entry)

        loaded = get_entry(tracker_path, "test-job")
        assert loaded is not None
        assert loaded.latest_resume_version == 3

    def test_backward_compat_missing_column(self, tmp_path):
        tracker_path = tmp_path / "tracker.csv"
        old_columns = [c for c in TRACKER_COLUMNS if c != "latest_resume_version"]
        with open(tracker_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=old_columns)
            writer.writeheader()
            writer.writerow({
                "job_id": "old-job",
                "date_added": "2026-01-01",
                "company": "OldCo",
                "role": "Dev",
                "url": "",
                "status": "found",
                "fit_score": "",
                "resume_path": "",
                "cover_letter_path": "",
                "audit_verdict": "",
                "notes": "",
                "next_action": "",
                "date_updated": "2026-01-01",
            })

        loaded = get_entry(tracker_path, "old-job")
        assert loaded is not None
        assert loaded.latest_resume_version is None

    def test_update_status_sets_version(self, tmp_path):
        tracker_path = tmp_path / "tracker.csv"
        entry = TrackerEntry(
            job_id="test-job",
            date_added=date.today(),
            company="TestCo",
            role="Engineer",
            status=TrackerStatus.FOUND,
        )
        add_entry(tracker_path, entry)

        update_status(
            tracker_path, "test-job", TrackerStatus.PREPARED,
            latest_resume_version=2,
        )

        loaded = get_entry(tracker_path, "test-job")
        assert loaded is not None
        assert loaded.latest_resume_version == 2
        assert loaded.status == TrackerStatus.PREPARED


class TestJobIdExists:
    def test_exists_true(self, tmp_path):
        tracker_path = tmp_path / "tracker.csv"
        entry = TrackerEntry(
            job_id="existing-job",
            date_added=date.today(),
            company="Co",
            role="Dev",
            status=TrackerStatus.FOUND,
        )
        add_entry(tracker_path, entry)
        assert job_id_exists(tracker_path, "existing-job") is True

    def test_exists_false(self, tmp_path):
        tracker_path = tmp_path / "tracker.csv"
        ensure_tracker_exists(tracker_path)
        assert job_id_exists(tracker_path, "nonexistent") is False

    def test_exists_no_file(self, tmp_path):
        tracker_path = tmp_path / "tracker.csv"
        assert job_id_exists(tracker_path, "anything") is False
