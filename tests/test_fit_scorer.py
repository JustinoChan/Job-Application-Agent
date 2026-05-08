from __future__ import annotations

from src.fit_scorer import score_fit
from src.job_parser import parse_job_description
from tests.conftest import AMAZON_JOB_TEXT, JAVA_JOB_TEXT, REACT_JOB_TEXT


class TestFitScoring:
    def test_react_job_scores_moderate_or_strong(self, sample_profile, sample_projects, sample_rules):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        assert fit.recommendation in ("moderate", "strong")
        assert fit.overall_score >= 0.4

    def test_java_job_scores_weak_or_skip(self, sample_profile, sample_projects, sample_rules):
        """A senior Java/Spring/K8s/AWS role should score low for a new grad with no Java focus."""
        job = parse_job_description(JAVA_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        assert fit.recommendation in ("weak", "skip")
        assert fit.overall_score < 0.50

    def test_java_job_missing_requirements_not_empty(self, sample_profile, sample_projects, sample_rules):
        """Spring Boot, Kubernetes, Docker, AWS etc should show as missing."""
        job = parse_job_description(JAVA_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        missing_lower = {m.lower() for m in fit.missing_required}
        assert len(missing_lower) >= 3
        has_infra_missing = any(
            term in missing_lower
            for term in ["spring boot", "spring", "kubernetes", "docker", "aws", "kafka"]
        )
        assert has_infra_missing, f"Expected infra skills in missing, got: {fit.missing_required}"

    def test_react_job_project_relevance(self, sample_profile, sample_projects, sample_rules):
        """Capstone (React/Django) should score higher than Search Engine for a React job."""
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        scores_by_id = {ps.project_id: ps.relevance_score for ps in fit.project_scores}
        assert scores_by_id["capstone-archive"] > scores_by_id["search-engine"]

    def test_skill_match_rate_bounded(self, sample_profile, sample_projects, sample_rules):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        assert 0.0 <= fit.skill_match_rate <= 1.0
        assert 0.0 <= fit.nice_to_have_match_rate <= 1.0
        assert 0.0 <= fit.overall_score <= 1.0

    def test_any_of_language_requirement_does_not_require_every_language(
        self, sample_profile, sample_projects, sample_rules
    ):
        job = parse_job_description(AMAZON_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)

        assert "Python" in [match.skill for match in fit.skill_matches if match.matched]
        assert "Rust" not in fit.missing_required
        assert "Go" not in fit.missing_required
        assert "C#" not in fit.missing_required

    def test_amazon_admin_and_education_requirements_do_not_pollute_missing(
        self, sample_profile, sample_projects, sample_rules
    ):
        job = parse_job_description(AMAZON_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        missing_text = "\n".join(fit.missing_required)

        assert "18 years" not in missing_text
        assert "bachelor" not in missing_text.lower()
        assert "Skip to main content" not in missing_text
