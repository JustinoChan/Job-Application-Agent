from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src import cover_letter
from src.models import (
    AuditVerdict,
    CoverLetter,
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
