from __future__ import annotations

from src.fit_scorer import score_fit
from src.job_parser import parse_job_description
from src.pdf_renderer import render_html
from src.resume_tailor import tailor_resume
from tests.conftest import REACT_JOB_TEXT


class TestRenderHtml:
    def test_produces_valid_html(
        self, sample_profile, sample_projects, sample_rules, sample_resume_config
    ):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        tailored = tailor_resume(job, fit, sample_profile, sample_projects, sample_resume_config, sample_rules)

        html = render_html(tailored, sample_profile)

        assert "<html>" in html
        assert sample_profile.name in html
        assert sample_profile.email in html

    def test_contains_skills(
        self, sample_profile, sample_projects, sample_rules, sample_resume_config
    ):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        tailored = tailor_resume(job, fit, sample_profile, sample_projects, sample_resume_config, sample_rules)

        html = render_html(tailored, sample_profile)

        assert "Proficient:" in html
        assert "Python" in html

    def test_contains_project_bullets(
        self, sample_profile, sample_projects, sample_rules, sample_resume_config
    ):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        tailored = tailor_resume(job, fit, sample_profile, sample_projects, sample_resume_config, sample_rules)

        html = render_html(tailored, sample_profile)

        assert "<li>" in html
        for proj in tailored.selected_projects:
            assert proj.name in html

    def test_contains_education(
        self, sample_profile, sample_projects, sample_rules, sample_resume_config
    ):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        tailored = tailor_resume(job, fit, sample_profile, sample_projects, sample_resume_config, sample_rules)

        html = render_html(tailored, sample_profile)

        assert "Test University" in html
        assert "B.S. Computer Science" in html
