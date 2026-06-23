from __future__ import annotations

from src.fit_scorer import score_fit
from src.job_parser import parse_job_description
from src.resume_tailor import tailor_resume
from tests.conftest import REACT_JOB_TEXT


def test_selected_projects_render_in_reverse_chronological_order(
    sample_profile, sample_projects, sample_rules, sample_resume_config
):
    job = parse_job_description(
        REACT_JOB_TEXT, sample_profile, sample_projects, sample_rules
    )
    fit = score_fit(job, sample_profile, sample_projects, sample_rules)

    assert fit.project_scores[0].project_id == "capstone-archive"

    tailored = tailor_resume(
        job,
        fit,
        sample_profile,
        sample_projects,
        sample_resume_config,
        sample_rules,
    )

    assert [project.project_id for project in tailored.selected_projects] == [
        "search-engine",
        "capstone-archive",
    ]
