from __future__ import annotations

from src.claim_auditor import audit_resume
from src.fit_scorer import score_fit
from src.job_parser import parse_job_description
from src.models import AuditVerdict, SelectedFact, SkillSet, TailoredProject, TailoredResume
from src.resume_tailor import tailor_resume
from tests.conftest import REACT_JOB_TEXT


class TestClaimAuditor:
    def test_valid_resume_passes_audit(
        self, sample_profile, sample_projects, sample_rules, sample_resume_config
    ):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        tailored = tailor_resume(job, fit, sample_profile, sample_projects, sample_resume_config, sample_rules)
        report = audit_resume(tailored, sample_projects, sample_profile, sample_rules)

        assert report.overall_verdict == AuditVerdict.PASS
        assert report.failed == 0
        assert report.total_claims > 0

    def test_fake_fact_fails_audit(
        self, sample_profile, sample_projects, sample_rules, sample_resume_config
    ):
        """A resume with a fabricated bullet should fail the audit."""
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        tailored = tailor_resume(job, fit, sample_profile, sample_projects, sample_resume_config, sample_rules)

        tailored.selected_projects.append(TailoredProject(
            project_id="capstone-archive",
            name="Capstone Project Archive",
            stack=["React.js"],
            selected_facts=[
                SelectedFact(
                    fact_id="fake-fact-99",
                    project_id="capstone-archive",
                    original_text="Deployed production application to AWS with Kubernetes orchestration.",
                    relevance_score=1.0,
                ),
            ],
        ))

        report = audit_resume(tailored, sample_projects, sample_profile, sample_rules)
        assert report.overall_verdict == AuditVerdict.FAIL
        assert report.failed >= 1

    def test_nonexistent_project_fails(
        self, sample_profile, sample_projects, sample_rules, sample_resume_config
    ):
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        tailored = tailor_resume(job, fit, sample_profile, sample_projects, sample_resume_config, sample_rules)

        tailored.selected_projects.append(TailoredProject(
            project_id="nonexistent-project",
            name="Fake Project",
            stack=["Magic"],
            selected_facts=[
                SelectedFact(
                    fact_id="fake-01",
                    project_id="nonexistent-project",
                    original_text="Did something impressive.",
                    relevance_score=1.0,
                ),
            ],
        ))

        report = audit_resume(tailored, sample_projects, sample_profile, sample_rules)
        assert report.overall_verdict == AuditVerdict.FAIL

    def test_all_facts_have_source_references(
        self, sample_profile, sample_projects, sample_rules, sample_resume_config
    ):
        """Every selected fact should have a valid fact_id and project_id."""
        job = parse_job_description(REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules)
        fit = score_fit(job, sample_profile, sample_projects, sample_rules)
        tailored = tailor_resume(job, fit, sample_profile, sample_projects, sample_resume_config, sample_rules)

        for proj in tailored.selected_projects:
            for fact in proj.selected_facts:
                assert fact.fact_id, "fact_id should not be empty"
                assert fact.project_id, "project_id should not be empty"
                assert fact.original_text, "original_text should not be empty"
