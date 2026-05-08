from __future__ import annotations

import json
import re
from datetime import date

from src import claim_auditor, openclaw_adapter
from src.models import (
    ApplicationRules,
    AuditEntry,
    AuditReport,
    AuditVerdict,
    CoverLetter,
    JobPosting,
    MasterProfile,
    Project,
    TailoredResume,
)


KNOWN_TECH_TERMS = {
    "python", "java", "javascript", "typescript", "ruby", "rust", "go", "golang",
    "php", "swift", "kotlin", "scala", "c++", "c#", ".net", "perl", "r",
    "react", "vue", "angular", "svelte", "next.js", "nuxt", "ember",
    "django", "flask", "fastapi", "rails", "spring", "express", "nestjs", "laravel",
    "node", "nodejs", "deno", "bun",
    "aws", "gcp", "azure", "heroku", "digitalocean", "cloudflare",
    "docker", "kubernetes", "k8s", "terraform", "ansible", "helm",
    "postgresql", "postgres", "mysql", "mariadb", "mongodb", "dynamodb", "redis",
    "kafka", "rabbitmq", "nats", "elasticsearch", "snowflake", "bigquery",
    "git", "github", "gitlab", "bitbucket", "jenkins", "circleci", "github actions",
    "html", "css", "sass", "tailwind", "bootstrap",
    "rest", "graphql", "grpc", "websocket", "soap",
    "linux", "unix", "windows", "macos",
    "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn", "sklearn", "keras",
    "spark", "hadoop", "airflow", "dbt",
    "firebase", "supabase", "auth0", "okta",
    "playwright", "selenium", "jest", "pytest", "junit", "cypress",
    "nginx", "apache", "kong",
}

CLAIM_VERBS = {
    "built", "build", "developed", "develop", "implemented", "implement",
    "integrated", "integrate", "migrated", "migrate", "processed", "process",
    "led", "lead", "coordinated", "coordinate", "designed", "design",
    "created", "create", "optimized", "optimize", "deployed", "deploy",
    "shipped", "ship", "maintained", "maintain", "owned", "own",
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "but", "by",
    "for", "from", "has", "have", "i", "in", "is", "it", "my", "of", "on",
    "or", "that", "the", "their", "this", "to", "using", "with", "would",
    "your", "you", "role", "team", "opportunity", "company", "work",
    "experience", "skills", "background", "apply", "excited", "thank",
    "consideration", "position", "aligns", "well", "strong",
}

GENERIC_SENTENCE_HINTS = {
    "excited", "apply", "thank", "consideration", "opportunity", "role",
    "company", "team", "hiring",
}

GENERIC_COVER_LETTER_PATTERNS = [
    r"\b(i am|i'm|i\u2019m|i\?m)\s+excited\b",
    r"\b(i am|i'm|i\u2019m|i\?m)\s+(especially\s+)?interested\b",
    r"\bthank you\b",
    r"\bsincerely\b",
    r"\bi would bring\b",
    r"\bi am applying\b",
    r"\bto apply for\b",
    r"\bproject work has given me hands-on experience\b",
    r"\bthese experiences have helped me develop\b",
]


class CoverLetterGenerationError(RuntimeError):
    pass


def _build_allowlist(
    profile: MasterProfile,
    projects: list[Project],
    job: JobPosting,
    rules: ApplicationRules,
) -> set[str]:
    allowed: set[str] = set()
    allowed.update(s.lower() for s in profile.skills.strong)
    allowed.update(s.lower() for s in profile.skills.familiar)
    for p in projects:
        allowed.update(s.lower() for s in p.stack)
        allowed.add(p.name.lower())
    allowed.update(k.lower() for k in job.extracted_keywords)
    if job.company and job.company.lower() != "unknown":
        allowed.add(job.company.lower())
    for edu in profile.education:
        allowed.add(edu.school.lower())

    for canonical, synonyms in rules.keyword_synonyms.items():
        canon_lower = canonical.lower()
        syns_lower = [s.lower() for s in synonyms]
        if canon_lower in allowed or any(s in allowed for s in syns_lower):
            allowed.add(canon_lower)
            allowed.update(syns_lower)

    return allowed


def _scan_unsourced_tech(text: str, allowlist: set[str]) -> list[str]:
    text_lower = text.lower()
    unsourced: list[str] = []
    for tech in KNOWN_TECH_TERMS:
        pattern = r"(?<![A-Za-z0-9_+#.-])" + re.escape(tech) + r"(?![A-Za-z0-9_+#-])"
        if re.search(pattern, text_lower):
            if tech not in allowlist:
                unsourced.append(tech)
    return unsourced


def _build_prompt(
    job: JobPosting,
    tailored: TailoredResume,
    profile: MasterProfile,
    source_url: str | None,
) -> str:
    selected_projects = []
    for tproj in tailored.selected_projects:
        selected_projects.append({
            "name": tproj.name,
            "role": tproj.role,
            "stack": tproj.stack,
            "approved_facts": [
                {
                    "fact_id": sf.fact_id,
                    "text": sf.original_text,
                }
                for sf in tproj.selected_facts
            ],
        })

    payload = {
        "target_job": {
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "source_url": source_url,
            "top_requirements": [r.text for r in job.requirements[:6]],
            "top_keywords": job.extracted_keywords[:12],
            "responsibilities": job.responsibilities[:6],
        },
        "candidate": {
            "name": profile.name,
            "education": [
                {
                    "school": edu.school,
                    "degree": edu.degree,
                    "graduation": edu.graduation,
                }
                for edu in profile.education
            ],
            "skills": {
                "strong": profile.skills.strong,
                "familiar": profile.skills.familiar,
            },
            "selected_projects": selected_projects,
        },
        "rules": {
            "allowed": [
                "Use only candidate education, skills, selected projects, and approved facts from this JSON.",
                "Rewrite approved facts for clarity while keeping the meaning truthful.",
                "Emphasize matches to target_job requirements and keywords.",
            ],
            "forbidden": [
                "Do not invent companies, internships, technologies, metrics, certifications, awards, deployments, team sizes, customers, or employment.",
                "Do not claim professional, paid, industry, internship, or production work experience.",
                "Do not mention employers other than the target company.",
                "Do not ask for more information; all usable context is in this INPUT_JSON.",
            ],
        },
        "output_schema": {
            "intro": "string",
            "body_paragraphs": ["string", "string"],
            "closing": "string",
        },
    }

    return (
        "TASK: Generate a truthful 3-paragraph cover letter from INPUT_JSON. "
        "You already have the target company, role, job requirements, source URL, candidate skills, education, and approved project facts. "
        "Do not ask follow-up questions. Respond only with valid JSON matching output_schema. "
        f"INPUT_JSON: {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}"
    )


def _parse_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise CoverLetterGenerationError(
                f"Could not extract JSON from OpenClaw response: {cleaned[:300]}"
            )
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise CoverLetterGenerationError(
                f"OpenClaw returned invalid JSON: {exc}"
            ) from exc


async def generate_cover_letter(
    job: JobPosting,
    tailored: TailoredResume,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
    *,
    source_url: str | None = None,
) -> CoverLetter:
    prompt = _build_prompt(job, tailored, profile, source_url)
    try:
        raw = await openclaw_adapter.ask_openclaw(prompt)
    except openclaw_adapter.OpenClawError as exc:
        raise CoverLetterGenerationError(f"OpenClaw call failed: {exc}") from exc

    data = _parse_response(raw)
    intro = data.get("intro")
    body = data.get("body_paragraphs")
    closing = data.get("closing")
    if not isinstance(intro, str) or not isinstance(closing, str):
        raise CoverLetterGenerationError("Response missing intro or closing string.")
    if not isinstance(body, list) or not all(isinstance(p, str) for p in body):
        raise CoverLetterGenerationError("Response body_paragraphs must be a list of strings.")

    job_id = f"{job.company}-{job.title}".lower().replace(" ", "-")
    referenced_project_ids = [p.project_id for p in tailored.selected_projects]
    referenced_fact_ids = [
        sf.fact_id for tp in tailored.selected_projects for sf in tp.selected_facts
    ]

    return CoverLetter(
        job_id=job_id,
        company=job.company,
        title=job.title,
        intro=intro.strip(),
        body_paragraphs=[p.strip() for p in body],
        closing=closing.strip(),
        referenced_project_ids=referenced_project_ids,
        referenced_fact_ids=referenced_fact_ids,
        source_url=source_url,
    )


def _full_letter_text(letter: CoverLetter) -> str:
    return "\n\n".join([letter.intro, *letter.body_paragraphs, letter.closing])


def _tokens(text: str) -> set[str]:
    return {
        token.strip(".")
        for token in re.findall(r"[a-z0-9+#.]+", text.lower())
        if len(token.strip(".")) > 2 and token.strip(".") not in STOPWORDS
    }


def _sentences(text: str) -> list[str]:
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
        if s.strip()
    ]


def _source_texts(
    letter: CoverLetter,
    profile: MasterProfile,
    projects: list[Project],
) -> list[str]:
    fact_lookup = {
        fact.id: fact.text
        for project in projects
        for fact in project.facts
    }
    if letter.referenced_fact_ids:
        facts = [
            fact_lookup[fact_id]
            for fact_id in letter.referenced_fact_ids
            if fact_id in fact_lookup
        ]
    else:
        facts = list(fact_lookup.values())

    profile_sources = [
        profile.name,
        profile.location,
        " ".join(profile.skills.strong),
        " ".join(profile.skills.familiar),
    ]
    profile_sources.extend(
        f"{edu.degree} {edu.school} {edu.graduation}"
        for edu in profile.education
    )
    project_sources = [
        f"{project.name} {' '.join(project.stack)} {project.role or ''} {project.description or ''}"
        for project in projects
    ]
    return facts + profile_sources + project_sources


def _is_claim_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    if not re.search(r"\b(i|my|i've|i have|i'm|i am)\b", lower):
        return False
    tokens = _tokens(sentence)
    if tokens & CLAIM_VERBS:
        return True
    if any(re.search(r"\d", token) for token in tokens):
        return True
    mentioned_tech = _scan_unsourced_tech(sentence, set()) or [
        tech for tech in KNOWN_TECH_TERMS if tech in lower
    ]
    return bool(mentioned_tech)


def _is_generic_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    if any(re.search(pattern, lower) for pattern in GENERIC_COVER_LETTER_PATTERNS):
        return True
    tokens = _tokens(sentence)
    return bool(tokens) and tokens <= GENERIC_SENTENCE_HINTS


def _best_source_overlap(sentence: str, source_tokens: list[set[str]]) -> float:
    sentence_tokens = _tokens(sentence)
    if not sentence_tokens:
        return 1.0
    best = 0.0
    for tokens in source_tokens:
        if not tokens:
            continue
        overlap = len(sentence_tokens & tokens)
        score = overlap / max(1, len(sentence_tokens))
        best = max(best, score)
    return best


def audit_cover_letter(
    letter: CoverLetter,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
    job: JobPosting,
) -> AuditReport:
    full_text = _full_letter_text(letter)
    violations = claim_auditor.check_text_hard_constraints(full_text, rules)

    allowlist = _build_allowlist(profile, projects, job, rules)
    unsourced = _scan_unsourced_tech(full_text, allowlist)

    entries: list[AuditEntry] = []
    for term in unsourced:
        entries.append(AuditEntry(
            fact_id=f"unsourced:{term}",
            project_id="cover_letter",
            resume_text=term,
            source_text="",
            verdict=AuditVerdict.FAIL,
            reason=f"Unsourced technology mention: '{term}' is not in profile, project bank, or job keywords.",
        ))

    sources = _source_texts(letter, profile, projects)
    source_tokens = [_tokens(source) for source in sources]
    for index, sentence in enumerate(_sentences(full_text), start=1):
        if not _is_claim_sentence(sentence) or _is_generic_sentence(sentence):
            continue
        score = _best_source_overlap(sentence, source_tokens)
        if score >= 0.28:
            entries.append(AuditEntry(
                fact_id=f"cover-letter-sentence-{index}",
                project_id="cover_letter",
                resume_text=sentence,
                source_text="approved source overlap",
                verdict=AuditVerdict.PASS,
                reason=f"Claim has source overlap ({score:.0%}).",
            ))
        else:
            entries.append(AuditEntry(
                fact_id=f"unsupported-sentence-{index}",
                project_id="cover_letter",
                resume_text=sentence,
                source_text="",
                verdict=AuditVerdict.FAIL,
                reason=(
                    "Cover-letter claim has weak overlap with the approved "
                    f"profile/project facts ({score:.0%})."
                ),
            ))

    failed = sum(1 for e in entries if e.verdict == AuditVerdict.FAIL)
    warned = sum(1 for e in entries if e.verdict == AuditVerdict.WARN)
    passed = sum(1 for e in entries if e.verdict == AuditVerdict.PASS)

    if failed > 0 or violations:
        overall = AuditVerdict.FAIL
    elif warned > 0:
        overall = AuditVerdict.WARN
    else:
        overall = AuditVerdict.PASS

    return AuditReport(
        total_claims=len(entries),
        passed=passed,
        warned=warned,
        failed=failed,
        entries=entries,
        hard_constraint_violations=violations,
        overall_verdict=overall,
    )


def render_cover_letter_markdown(letter: CoverLetter, profile: MasterProfile) -> str:
    today = date.today().strftime("%B %d, %Y")
    contact_parts = [profile.email]
    if profile.phone:
        contact_parts.append(profile.phone)
    contact_parts.append(profile.location)
    contact_line = " | ".join(contact_parts)

    lines = [
        f"# {profile.name}",
        contact_line,
        "",
        today,
        "",
        f"**{letter.company}**",
        f"Re: {letter.title}",
        "",
        "Dear Hiring Team,",
        "",
        letter.intro,
        "",
    ]
    for para in letter.body_paragraphs:
        lines.append(para)
        lines.append("")
    lines.extend([
        letter.closing,
        "",
        "Sincerely,",
        profile.name,
    ])
    return "\n".join(lines)


def save_cover_letter(letter: CoverLetter, markdown: str, job_id: str, version: int):
    from src import config
    paths = config.cover_letter_version_paths(job_id, version)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["md"].write_text(markdown, encoding="utf-8")
    paths["meta"].write_text(letter.model_dump_json(indent=2), encoding="utf-8")
    return paths["md"]


def save_cover_letter_audit(report: AuditReport, job_id: str, version: int):
    from src import config
    paths = config.cover_letter_version_paths(job_id, version)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["audit"].write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return paths["audit"]
