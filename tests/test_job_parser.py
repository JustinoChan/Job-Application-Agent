from __future__ import annotations

from src.job_parser import _extract_company_and_title, parse_job_description
from tests.conftest import AMAZON_JOB_TEXT, JAVA_JOB_TEXT, REACT_JOB_TEXT


class TestCompanyTitleParsing:
    def test_pipe_separator(self):
        company, title = _extract_company_and_title("Software Engineer - New Grad | ExampleCo")
        assert company == "ExampleCo"
        assert title == "Software Engineer - New Grad"

    def test_at_separator(self):
        company, title = _extract_company_and_title("Backend Engineer at Google")
        assert company == "Google"
        assert title == "Backend Engineer"

    def test_dash_separator_no_pipe(self):
        company, title = _extract_company_and_title("Software Engineer - Google")
        assert company == "Google"
        assert title == "Software Engineer"

    def test_dash_in_title_with_pipe(self):
        """Hyphens in the title should not split when pipe is present."""
        company, title = _extract_company_and_title("Software Engineer - New Grad | Acme Corp")
        assert company == "Acme Corp"
        assert "New Grad" in title

    def test_unknown_fallback(self):
        company, title = _extract_company_and_title("Just some random text")
        assert title == "Just some random text"

    def test_empty_input(self):
        company, title = _extract_company_and_title("")
        assert company == "Unknown"
        assert title == "Unknown"


class TestJobParsing:
    def test_react_job_extracts_keywords(self, sample_profile, sample_projects, sample_rules):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        kw_lower = {k.lower() for k in job.extracted_keywords}
        assert "react" in kw_lower or "react.js" in kw_lower
        assert "python" in kw_lower
        assert "sql" in kw_lower
        assert "git" in kw_lower

    def test_react_job_has_requirements(self, sample_profile, sample_projects, sample_rules):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        assert len(job.requirements) > 0
        assert len(job.nice_to_haves) > 0

    def test_java_job_extracts_unknown_skills(self, sample_profile, sample_projects, sample_rules):
        """Skills not in the candidate's profile should still be extracted."""
        job = parse_job_description(JAVA_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        kw_lower = {k.lower() for k in job.extracted_keywords}
        assert "spring boot" in kw_lower or "spring" in kw_lower
        assert "kubernetes" in kw_lower
        assert "docker" in kw_lower
        assert "kafka" in kw_lower or "aws" in kw_lower

    def test_amazon_style_sections_ignore_page_chrome(self, sample_profile, sample_projects, sample_rules):
        job = parse_job_description(AMAZON_JOB_TEXT, sample_profile, sample_projects, sample_rules)

        requirement_text = "\n".join(req.text for req in job.requirements)
        nice_text = "\n".join(req.text for req in job.nice_to_haves)
        responsibility_text = "\n".join(job.responsibilities)

        assert "Experience with at least one general-purpose programming language" in requirement_text
        assert "Experience with one or more of the following" in nice_text
        assert "Design and develop scalable solutions" in responsibility_text
        assert "Skip to main content" not in requirement_text
        assert "Home" not in requirement_text
        assert "Sign out" not in requirement_text

    def test_company_override(self, sample_profile, sample_projects, sample_rules):
        job = parse_job_description(
            REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules,
            company_override="OverrideCo",
        )
        assert job.company == "OverrideCo"

    def test_location_extraction(self, sample_profile, sample_projects, sample_rules):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        assert job.location is not None
        assert "San Francisco" in job.location or "Hybrid" in job.location
