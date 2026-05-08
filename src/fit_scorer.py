from __future__ import annotations

import re

from src.models import (
    ApplicationRules,
    FitScore,
    JobPosting,
    MasterProfile,
    Project,
    ProjectScore,
    SkillMatch,
)


def score_fit(
    job: JobPosting,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
) -> FitScore:
    candidate_skills = _build_candidate_skills(profile, projects)
    synonym_map = _build_reverse_synonym_map(rules)

    skill_matches, missing_required = _score_skills(
        job.requirements, candidate_skills, synonym_map, source_label="required"
    )
    nice_matches, missing_nice = _score_skills(
        job.nice_to_haves, candidate_skills, synonym_map, source_label="nice-to-have"
    )

    skill_match_rate = (
        sum(1 for m in skill_matches if m.matched) / max(len(skill_matches), 1)
    )
    nice_match_rate = (
        sum(1 for m in nice_matches if m.matched) / max(len(nice_matches), 1)
    )

    project_scores = _score_projects(job, projects, rules)

    overall = _compute_overall(skill_match_rate, nice_match_rate, project_scores)
    recommendation = _recommendation(overall, rules.min_fit_score_to_apply)

    return FitScore(
        overall_score=round(overall, 3),
        skill_matches=skill_matches + nice_matches,
        skill_match_rate=round(skill_match_rate, 3),
        nice_to_have_match_rate=round(nice_match_rate, 3),
        project_scores=project_scores,
        missing_required=missing_required,
        missing_nice_to_haves=missing_nice,
        recommendation=recommendation,
    )


def _build_candidate_skills(
    profile: MasterProfile, projects: list[Project]
) -> dict[str, str]:
    skills: dict[str, str] = {}
    for s in profile.skills.strong:
        skills[s.lower()] = "profile (strong)"
    for s in profile.skills.familiar:
        skills[s.lower()] = "profile (familiar)"
    for proj in projects:
        for tech in proj.stack:
            key = tech.lower()
            if key not in skills:
                skills[key] = f"project:{proj.id}"
        for fact in proj.facts:
            for kw in fact.keywords:
                key = kw.lower()
                if key not in skills:
                    skills[key] = f"project:{proj.id}"
    return skills


def _build_reverse_synonym_map(rules: ApplicationRules) -> dict[str, str]:
    rev: dict[str, str] = {}
    for canonical, syns in rules.keyword_synonyms.items():
        for syn in syns:
            rev[syn.lower()] = canonical.lower()
    return rev


def _normalize_skill(skill: str, synonym_map: dict[str, str]) -> str:
    lower = skill.lower()
    return synonym_map.get(lower, lower)


def _unique_keywords(requirements: list) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for req in requirements:
        for kw in req.keywords:
            lower = kw.lower()
            if lower not in seen:
                seen.add(lower)
                result.append(kw)
    return result


def _score_skills(
    requirements: list,
    candidate_skills: dict[str, str],
    synonym_map: dict[str, str],
    source_label: str,
) -> tuple[list[SkillMatch], list[str]]:
    matches: list[SkillMatch] = []
    missing: list[str] = []
    seen: set[str] = set()

    for req in requirements:
        if _is_admin_requirement(req.text):
            continue

        education_source = _education_match(req.text)
        if education_source:
            label = "Bachelor's degree"
            if label not in seen:
                seen.add(label)
                matches.append(SkillMatch(skill=label, matched=True, source=education_source))
            continue

        if not req.keywords:
            # Requirement with no recognized keywords still counts as unmatched
            label = req.text[:60] + ("..." if len(req.text) > 60 else "")
            if label not in seen:
                seen.add(label)
                matches.append(SkillMatch(skill=label, matched=False, source=""))
                missing.append(label)
            continue

        if _is_any_of_requirement(req.text):
            grouped_matches = []
            grouped_missing = []
            for kw in req.keywords:
                normalized = _normalize_skill(kw, synonym_map)
                source = _find_candidate_source(normalized, candidate_skills, synonym_map)
                if source:
                    grouped_matches.append(SkillMatch(skill=kw, matched=True, source=source))
                else:
                    grouped_missing.append(kw)

            if grouped_matches:
                for match in grouped_matches:
                    key = _normalize_skill(match.skill, synonym_map)
                    if key not in seen:
                        seen.add(key)
                        matches.append(match)
            else:
                label = req.text[:60] + ("..." if len(req.text) > 60 else "")
                if label not in seen:
                    seen.add(label)
                    matches.append(SkillMatch(skill=label, matched=False, source=""))
                    missing.append(label)
            continue

        for kw in req.keywords:
            normalized = _normalize_skill(kw, synonym_map)
            if normalized in seen:
                continue
            seen.add(normalized)

            source = _find_candidate_source(normalized, candidate_skills, synonym_map)

            if source:
                matches.append(SkillMatch(skill=kw, matched=True, source=source))
            else:
                matches.append(SkillMatch(skill=kw, matched=False, source=""))
                missing.append(kw)

    return matches, missing


def _find_candidate_source(
    normalized: str,
    candidate_skills: dict[str, str],
    synonym_map: dict[str, str],
) -> str | None:
    variants = {normalized}
    if normalized.endswith("s"):
        variants.add(normalized[:-1])
    else:
        variants.add(f"{normalized}s")

    source = next((candidate_skills[v] for v in variants if v in candidate_skills), None)
    if source:
        return source
    for candidate_key, candidate_source in candidate_skills.items():
        canon_candidate = synonym_map.get(candidate_key, candidate_key)
        candidate_variants = {canon_candidate}
        if canon_candidate.endswith("s"):
            candidate_variants.add(canon_candidate[:-1])
        else:
            candidate_variants.add(f"{canon_candidate}s")
        if variants & candidate_variants:
            return candidate_source
    return None


def _is_any_of_requirement(text: str) -> bool:
    lower = text.lower()
    return any(
        phrase in lower
        for phrase in [
            "at least one",
            "one or more",
            "and/or",
            "such as",
            "or related",
            "or similar",
        ]
    )


def _is_admin_requirement(text: str) -> bool:
    lower = text.lower()
    return any(
        phrase in lower
        for phrase in [
            "must be 18",
            "18 years of age",
            "legally authorized",
            "work authorization",
            "sponsorship",
        ]
    )


def _education_match(text: str) -> str | None:
    lower = text.lower()
    if "bachelor" in lower or "degree" in lower:
        return "profile education"
    return None


def _score_projects(
    job: JobPosting,
    projects: list[Project],
    rules: ApplicationRules,
) -> list[ProjectScore]:
    synonym_map = _build_reverse_synonym_map(rules)
    job_keywords_norm = {_normalize_skill(k, synonym_map) for k in job.extracted_keywords}

    scores: list[ProjectScore] = []
    for proj in projects:
        proj_keywords: set[str] = set()
        for tech in proj.stack:
            proj_keywords.add(_normalize_skill(tech, synonym_map))
        for fact in proj.facts:
            for kw in fact.keywords:
                proj_keywords.add(_normalize_skill(kw, synonym_map))

        proj_themes = {t.lower() for t in proj.themes}

        keyword_overlap = job_keywords_norm & proj_keywords
        theme_overlap = job_keywords_norm & proj_themes

        matched_kw_display = [k for k in job.extracted_keywords if _normalize_skill(k, synonym_map) in keyword_overlap]
        matched_theme_display = [t for t in proj.themes if t.lower() in theme_overlap]

        total_possible = max(len(job_keywords_norm), 1)
        relevance = (len(keyword_overlap) * 2 + len(theme_overlap)) / (total_possible * 2 + len(proj_themes) if proj_themes else total_possible * 2)
        relevance = min(relevance, 1.0)

        scores.append(ProjectScore(
            project_id=proj.id,
            project_name=proj.name,
            relevance_score=round(relevance, 3),
            matched_keywords=matched_kw_display,
            matched_themes=matched_theme_display,
        ))

    scores.sort(key=lambda s: s.relevance_score, reverse=True)
    return scores


def _compute_overall(
    skill_rate: float, nice_rate: float, project_scores: list[ProjectScore]
) -> float:
    top_project_scores = [ps.relevance_score for ps in project_scores[:2]]
    avg_project = sum(top_project_scores) / max(len(top_project_scores), 1) if top_project_scores else 0.0

    return 0.50 * skill_rate + 0.15 * nice_rate + 0.35 * avg_project


def _recommendation(overall: float, min_threshold: float) -> str:
    if overall >= 0.75:
        return "strong"
    if overall >= 0.50:
        return "moderate"
    if overall >= min_threshold:
        return "weak"
    return "skip"
