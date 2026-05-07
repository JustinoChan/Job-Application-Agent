from __future__ import annotations

from pathlib import Path

from src import config
from src.models import (
    ApplicationRules,
    FitScore,
    JobPosting,
    MasterProfile,
    MasterResume,
    Project,
    SelectedFact,
    SkillSet,
    TailoredProject,
    TailoredResume,
)


def tailor_resume(
    job: JobPosting,
    fit_score: FitScore,
    profile: MasterProfile,
    projects: list[Project],
    resume_config: MasterResume,
    rules: ApplicationRules,
) -> TailoredResume:
    selected_ids = _select_projects(fit_score, resume_config)
    project_lookup = {p.id: p for p in projects}

    tailored_projects: list[TailoredProject] = []
    for pid in selected_ids:
        proj = project_lookup.get(pid)
        if not proj:
            continue
        facts = _select_facts_for_project(
            proj, job, resume_config.max_facts_per_project, rules
        )
        reordered_stack = _reorder_list_by_relevance(proj.stack, job.extracted_keywords, rules)
        tailored_projects.append(TailoredProject(
            project_id=proj.id,
            name=proj.name,
            role=proj.role,
            date_range=proj.date_range,
            stack=reordered_stack,
            selected_facts=facts,
        ))

    reordered_skills = _reorder_skills(profile.skills, job.extracted_keywords, rules)

    return TailoredResume(
        job_posting=job,
        fit_score=fit_score,
        reordered_skills=reordered_skills,
        selected_projects=tailored_projects,
    )


def _select_projects(fit_score: FitScore, config: MasterResume) -> list[str]:
    return [ps.project_id for ps in fit_score.project_scores[: config.max_projects]]


def _select_facts_for_project(
    project: Project,
    job: JobPosting,
    max_facts: int,
    rules: ApplicationRules,
) -> list[SelectedFact]:
    job_kw_lower = {k.lower() for k in job.extracted_keywords}
    reverse_syn = {}
    for canonical, syns in rules.keyword_synonyms.items():
        for syn in syns:
            reverse_syn[syn.lower()] = canonical.lower()

    scored: list[tuple[float, SelectedFact]] = []
    for fact in project.facts:
        fact_kw_norm = set()
        for kw in fact.keywords:
            norm = reverse_syn.get(kw.lower(), kw.lower())
            fact_kw_norm.add(norm)

        job_kw_norm = set()
        for kw in job_kw_lower:
            norm = reverse_syn.get(kw, kw)
            job_kw_norm.add(norm)

        overlap = fact_kw_norm & job_kw_norm
        relevance = len(overlap) / max(len(fact_kw_norm), 1)

        scored.append((relevance, SelectedFact(
            fact_id=fact.id,
            project_id=project.id,
            original_text=fact.text,
            relevance_score=round(relevance, 3),
        )))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [sf for _, sf in scored[:max_facts]]


def _reorder_skills(
    skills: SkillSet,
    job_keywords: list[str],
    rules: ApplicationRules,
) -> SkillSet:
    job_kw_lower = {k.lower() for k in job_keywords}
    reverse_syn = {}
    for canonical, syns in rules.keyword_synonyms.items():
        for syn in syns:
            reverse_syn[syn.lower()] = canonical.lower()

    job_kw_norm = set()
    for kw in job_kw_lower:
        job_kw_norm.add(reverse_syn.get(kw, kw))

    always_norm = {s.lower() for s in rules.always_include_skills}

    def sort_key(skill: str) -> tuple[int, int]:
        norm = reverse_syn.get(skill.lower(), skill.lower())
        is_match = norm in job_kw_norm
        is_always = skill.lower() in always_norm
        priority = 0 if is_match else (1 if is_always else 2)
        return (priority, 0)

    return SkillSet(
        strong=sorted(skills.strong, key=sort_key),
        familiar=sorted(skills.familiar, key=sort_key),
    )


def _reorder_list_by_relevance(
    items: list[str],
    job_keywords: list[str],
    rules: ApplicationRules,
) -> list[str]:
    job_kw_lower = {k.lower() for k in job_keywords}
    reverse_syn = {}
    for canonical, syns in rules.keyword_synonyms.items():
        for syn in syns:
            reverse_syn[syn.lower()] = canonical.lower()

    job_kw_norm = set()
    for kw in job_kw_lower:
        job_kw_norm.add(reverse_syn.get(kw, kw))

    matched = []
    unmatched = []
    for item in items:
        norm = reverse_syn.get(item.lower(), item.lower())
        if norm in job_kw_norm:
            matched.append(item)
        else:
            unmatched.append(item)

    return matched + unmatched


def render_resume_markdown(tailored: TailoredResume, profile: MasterProfile) -> str:
    lines: list[str] = []

    lines.append(f"# {profile.name}")
    contact_parts: list[str] = []
    if profile.email:
        contact_parts.append(profile.email)
    if profile.phone:
        contact_parts.append(profile.phone)
    if profile.location:
        contact_parts.append(profile.location)
    if profile.linkedin:
        contact_parts.append(profile.linkedin)
    if profile.github:
        contact_parts.append(profile.github)
    if profile.portfolio:
        contact_parts.append(profile.portfolio)
    lines.append(" | ".join(contact_parts))
    lines.append("")

    if profile.education:
        lines.append("## Education")
        for edu in profile.education:
            gpa_str = f" | GPA: {edu.gpa}" if edu.gpa else ""
            lines.append(f"**{edu.school}** - {edu.degree}, {edu.graduation}{gpa_str}")
            if edu.relevant_coursework:
                lines.append(f"Relevant Coursework: {', '.join(edu.relevant_coursework)}")
        lines.append("")

    lines.append("## Skills")
    skills = tailored.reordered_skills
    lines.append(f"**Proficient:** {', '.join(skills.strong)}")
    if skills.familiar:
        lines.append(f"**Familiar:** {', '.join(skills.familiar)}")
    lines.append("")

    lines.append("## Projects")
    for proj in tailored.selected_projects:
        header = f"### {proj.name}"
        if proj.role:
            header += f" | {proj.role}"
        if proj.date_range:
            header += f" | {proj.date_range}"
        lines.append(header)
        lines.append(f"*{', '.join(proj.stack)}*")
        for fact in proj.selected_facts:
            lines.append(f"- {fact.original_text}")
        lines.append("")

    return "\n".join(lines)


def save_resume(markdown: str, job_id: str, version: int) -> Path:
    paths = config.version_paths(job_id, version)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["md"].write_text(markdown, encoding="utf-8")
    return paths["md"]


def save_resume_metadata(tailored: TailoredResume, job_id: str, version: int) -> Path:
    paths = config.version_paths(job_id, version)
    paths["meta"].write_text(tailored.model_dump_json(indent=2), encoding="utf-8")
    return paths["meta"]
