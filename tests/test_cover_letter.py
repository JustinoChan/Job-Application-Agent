from __future__ import annotations

import json
import shutil
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src import config, cover_letter, pipeline, tracker
from src.models import (
    AuditVerdict,
    CoverLetter,
    TrackerEntry,
    TrackerStatus,
    JobPosting,
    JobRequirement,
    SelectedFact,
    TailoredProject,
    TailoredResume,
    SkillSet,
    FitScore,
)


@pytest.fixture
def sample_job() -> JobPosting:
    return JobPosting(
        raw_text="dummy",
        company="ExampleCo",
        title="Software Engineer",
        location="Remote",
        requirements=[
            JobRequirement(text="Experience with React and Python", keywords=["React", "Python"]),
            JobRequirement(text="Experience with SQL databases", keywords=["SQL"]),
        ],
        extracted_keywords=["React", "Python", "SQL", "Django", "Git"],
    )


@pytest.fixture
def sample_tailored(sample_job, sample_projects) -> TailoredResume:
    fit = FitScore(
        overall_score=0.7,
        skill_matches=[],
        skill_match_rate=0.7,
        nice_to_have_match_rate=0.5,
        project_scores=[],
        missing_required=[],
        missing_nice_to_haves=[],
        recommendation="moderate",
    )
    selected = [
        TailoredProject(
            project_id="capstone-archive",
            name="Capstone Project Archive",
            role="Full-Stack Developer",
            date_range="Sep 2024 - Mar 2025",
            stack=["React.js", "Django REST API", "MySQL8"],
            selected_facts=[
                SelectedFact(
                    fact_id="capstone-fact-01",
                    project_id="capstone-archive",
                    original_text="Built a full-stack web application for hosting student projects using React.js frontend and Django REST API backend.",
                    relevance_score=0.9,
                ),
            ],
        ),
    ]
    return TailoredResume(
        job_posting=sample_job,
        fit_score=fit,
        reordered_skills=SkillSet(strong=["Python", "React", "Django"], familiar=["MongoDB"]),
        selected_projects=selected,
    )


def _make_letter(body: list[str], intro: str = "I'm excited to apply.", closing: str = "Thank you for your time.") -> CoverLetter:
    return CoverLetter(
        job_id="test-job-001",
        company="ExampleCo",
        title="Software Engineer",
        intro=intro,
        body_paragraphs=body,
        closing=closing,
    )


class TestAuditCoverLetter:
    def test_passes_with_only_allowlisted_terms(self, sample_profile, sample_projects, sample_rules, sample_job):
        letter = _make_letter([
            "I built a full-stack web application using React and Python.",
            "My experience with Django and SQL aligns well with this role.",
        ])
        report = cover_letter.audit_cover_letter(letter, sample_profile, sample_projects, sample_rules, sample_job)
        assert report.overall_verdict == AuditVerdict.PASS
        assert report.failed == 0

    def test_fails_on_unsourced_technology(self, sample_profile, sample_projects, sample_rules, sample_job):
        letter = _make_letter([
            "I have extensive experience with Kubernetes and Docker in production.",
        ])
        report = cover_letter.audit_cover_letter(letter, sample_profile, sample_projects, sample_rules, sample_job)
        assert report.overall_verdict == AuditVerdict.FAIL
        unsourced_terms = [e.resume_text for e in report.entries]
        assert "kubernetes" in unsourced_terms
        assert "docker" in unsourced_terms

    def test_fails_on_forbidden_phrase(self, sample_profile, sample_projects, sample_rules, sample_job):
        letter = _make_letter([
            "During my internship at a company, I built React applications.",
        ])
        report = cover_letter.audit_cover_letter(letter, sample_profile, sample_projects, sample_rules, sample_job)
        assert report.overall_verdict == AuditVerdict.FAIL
        assert any("internship" in v.lower() for v in report.hard_constraint_violations)

    def test_fails_on_never_claim(self, sample_profile, sample_projects, sample_rules, sample_job):
        letter = _make_letter([
            "My AWS production experience makes me a great fit.",
        ])
        report = cover_letter.audit_cover_letter(letter, sample_profile, sample_projects, sample_rules, sample_job)
        assert report.overall_verdict == AuditVerdict.FAIL
        assert any("aws production" in v.lower() for v in report.hard_constraint_violations)

    def test_synonym_in_allowlist_is_accepted(self, sample_profile, sample_projects, sample_rules, sample_job):
        letter = _make_letter([
            "I built MySQL-backed services using React.js.",
        ])
        report = cover_letter.audit_cover_letter(letter, sample_profile, sample_projects, sample_rules, sample_job)
        assert report.overall_verdict == AuditVerdict.PASS

    def test_fails_on_fabricated_non_tech_claim(self, sample_profile, sample_projects, sample_rules, sample_job):
        letter = _make_letter([
            "I led a six-person engineering team and shipped production systems for enterprise customers.",
        ])
        report = cover_letter.audit_cover_letter(letter, sample_profile, sample_projects, sample_rules, sample_job)
        assert report.overall_verdict == AuditVerdict.FAIL
        assert any("weak overlap" in e.reason for e in report.entries)

    def test_audits_project_claim_without_first_person(self, sample_profile, sample_projects, sample_rules, sample_job):
        letter = _make_letter([
            "That project included Kubernetes production deployments for enterprise customers.",
        ])
        report = cover_letter.audit_cover_letter(letter, sample_profile, sample_projects, sample_rules, sample_job)
        assert report.overall_verdict == AuditVerdict.FAIL
        assert any(e.fact_id.startswith("unsupported-sentence") for e in report.entries)

    def test_allows_generic_cover_letter_framing(self, sample_profile, sample_projects, sample_rules, sample_job):
        letter = _make_letter(
            intro="Dear Hiring Manager, I am excited to apply for the Software Engineer role at ExampleCo.",
            body=[
                "I've built a strong foundation in Python and TypeScript through hands-on projects.",
                "My project work has given me hands-on experience with data structures, algorithms, and careful software design.",
                "In a Python search engine project, I built tokenization, indexing, and query handling to support efficient full-text search over more than 56,000 web pages.",
                "I'm especially interested in writing clean, maintainable code and contributing to reliable systems.",
                "These experiences strengthened my ability to design maintainable systems.",
                "These experiences have helped me develop a practical, detail-oriented approach that I would bring to this team.",
                "I would welcome the opportunity to contribute to ExampleCo.",
            ],
            closing="Thank you for your time and consideration. Sincerely, Test User",
        )
        report = cover_letter.audit_cover_letter(letter, sample_profile, sample_projects, sample_rules, sample_job)
        assert report.overall_verdict == AuditVerdict.PASS


class TestGenerateCoverLetter:
    @pytest.mark.asyncio
    async def test_parses_valid_json_response(self, sample_profile, sample_projects, sample_rules, sample_job, sample_tailored):
        response = json.dumps({
            "intro": "I'm excited about the role.",
            "body_paragraphs": ["Para 1 about React.", "Para 2 about Django."],
            "closing": "Thank you for considering my application.",
        })
        with patch("src.cover_letter.openclaw_adapter.ask_openclaw", AsyncMock(return_value=response)):
            letter = await cover_letter.generate_cover_letter(
                sample_job, sample_tailored, sample_profile, sample_projects, sample_rules,
            )
        assert letter.intro == "I'm excited about the role."
        assert len(letter.body_paragraphs) == 2
        assert letter.company == "ExampleCo"
        assert letter.referenced_project_ids == ["capstone-archive"]

    @pytest.mark.asyncio
    async def test_prompt_includes_job_and_candidate_context(self, sample_profile, sample_projects, sample_rules, sample_job, sample_tailored):
        response = json.dumps({
            "intro": "I'm excited about the role.",
            "body_paragraphs": ["Para 1 about React.", "Para 2 about Django."],
            "closing": "Thank you for considering my application.",
        })
        with patch("src.cover_letter.openclaw_adapter.ask_openclaw", AsyncMock(return_value=response)) as mock_ask:
            await cover_letter.generate_cover_letter(
                sample_job,
                sample_tailored,
                sample_profile,
                sample_projects,
                sample_rules,
                source_url="https://example.com/job",
            )

        prompt = mock_ask.call_args.args[0]
        assert "INPUT_JSON" in prompt
        assert "Do not ask follow-up questions" in prompt
        assert "https://example.com/job" in prompt
        assert "ExampleCo" in prompt
        assert "Software Engineer" in prompt
        assert "Test User" in prompt
        assert "Capstone Project Archive" in prompt
        assert "Built a full-stack web application" in prompt

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fences(self, sample_profile, sample_projects, sample_rules, sample_job, sample_tailored):
        response = '```json\n{"intro": "Hi.", "body_paragraphs": ["Body."], "closing": "Bye."}\n```'
        with patch("src.cover_letter.openclaw_adapter.ask_openclaw", AsyncMock(return_value=response)):
            letter = await cover_letter.generate_cover_letter(
                sample_job, sample_tailored, sample_profile, sample_projects, sample_rules,
            )
        assert letter.intro == "Hi."

    @pytest.mark.asyncio
    async def test_extracts_json_from_preamble(self, sample_profile, sample_projects, sample_rules, sample_job, sample_tailored):
        response = 'Sure, here is the cover letter:\n{"intro": "Hi.", "body_paragraphs": ["Body."], "closing": "Bye."}'
        with patch("src.cover_letter.openclaw_adapter.ask_openclaw", AsyncMock(return_value=response)):
            letter = await cover_letter.generate_cover_letter(
                sample_job, sample_tailored, sample_profile, sample_projects, sample_rules,
            )
        assert letter.intro == "Hi."

    @pytest.mark.asyncio
    async def test_repairs_nested_duplicate_body_paragraphs(self, sample_profile, sample_projects, sample_rules, sample_job, sample_tailored):
        response = (
            '{"intro":"Hi.",'
            '"body_paragraphs":["First body paragraph.",'
            '"body_paragraphs":["Second body paragraph."],'
            '"closing":"Bye."}'
        )
        with patch("src.cover_letter.openclaw_adapter.ask_openclaw", AsyncMock(return_value=response)):
            letter = await cover_letter.generate_cover_letter(
                sample_job, sample_tailored, sample_profile, sample_projects, sample_rules,
            )

        assert letter.body_paragraphs == ["First body paragraph.", "Second body paragraph."]
        assert letter.closing == "Bye."

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, sample_profile, sample_projects, sample_rules, sample_job, sample_tailored):
        with patch("src.cover_letter.openclaw_adapter.ask_openclaw", AsyncMock(return_value="not json")):
            with pytest.raises(cover_letter.CoverLetterGenerationError):
                await cover_letter.generate_cover_letter(
                    sample_job, sample_tailored, sample_profile, sample_projects, sample_rules,
                )

    @pytest.mark.asyncio
    async def test_missing_fields_raises(self, sample_profile, sample_projects, sample_rules, sample_job, sample_tailored):
        response = json.dumps({"intro": "Hi.", "closing": "Bye."})  # missing body_paragraphs
        with patch("src.cover_letter.openclaw_adapter.ask_openclaw", AsyncMock(return_value=response)):
            with pytest.raises(cover_letter.CoverLetterGenerationError):
                await cover_letter.generate_cover_letter(
                    sample_job, sample_tailored, sample_profile, sample_projects, sample_rules,
                )

    @pytest.mark.asyncio
    async def test_openclaw_failure_propagates(self, sample_profile, sample_projects, sample_rules, sample_job, sample_tailored):
        from src.openclaw_adapter import OpenClawError
        with patch("src.cover_letter.openclaw_adapter.ask_openclaw", AsyncMock(side_effect=OpenClawError("daemon down"))):
            with pytest.raises(cover_letter.CoverLetterGenerationError, match="daemon down"):
                await cover_letter.generate_cover_letter(
                    sample_job, sample_tailored, sample_profile, sample_projects, sample_rules,
                )


class TestRenderMarkdown:
    def test_includes_company_and_title(self, sample_profile):
        letter = _make_letter(["Body para."])
        md = cover_letter.render_cover_letter_markdown(letter, sample_profile)
        assert "ExampleCo" in md
        assert "Software Engineer" in md
        assert sample_profile.name in md
        assert "Dear Hiring Team" in md


class TestCoverLetterPipeline:
    @pytest.mark.asyncio
    async def test_saves_draft_when_audit_fails(
        self,
        monkeypatch,
        sample_profile,
        sample_projects,
        sample_rules,
        sample_tailored,
    ):
        job_id = "test-job"
        work_dir = Path(".pytest_pipeline_cover_letter") / uuid.uuid4().hex
        try:
            monkeypatch.setattr(config, "RESUMES_DIR", work_dir / "resumes")
            monkeypatch.setattr(config, "COVER_LETTERS_DIR", work_dir / "cover_letters")
            monkeypatch.setattr(config, "TRACKER_PATH", work_dir / "tracker.csv")

            resume_paths = config.version_paths(job_id, 1)
            resume_paths["dir"].mkdir(parents=True, exist_ok=True)
            resume_paths["md"].write_text("resume markdown", encoding="utf-8")
            resume_paths["meta"].write_text(sample_tailored.model_dump_json(), encoding="utf-8")

            tracker.add_entry(config.TRACKER_PATH, TrackerEntry(
                job_id=job_id,
                date_added=date.today(),
                company="ExampleCo",
                role="Software Engineer",
                status=TrackerStatus.PREPARED,
                latest_resume_version=1,
            ))

            generated = CoverLetter(
                job_id=job_id,
                company="ExampleCo",
                title="Software Engineer",
                intro="I am excited to apply.",
                body_paragraphs=[
                    "I led a six-person engineering team and shipped production systems for enterprise customers.",
                ],
                closing="Thank you.",
            )
            with patch("src.pipeline.cover_letter_mod.generate_cover_letter", AsyncMock(return_value=generated)):
                result = await pipeline.generate_cover_letter_for_job(
                    job_id,
                    sample_profile,
                    sample_projects,
                    sample_rules,
                )

            assert result.audit_verdict == "fail"
            paths = config.cover_letter_version_paths(job_id, result.version)
            assert paths["md"].exists()
            assert paths["meta"].exists()
            assert paths["audit"].exists()
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
