from __future__ import annotations

import re

from src.models import ApplicationRules, JobPosting, JobRequirement, MasterProfile, Project

# Broad list of tech skills so the parser can recognize requirements
# outside the candidate's personal vocabulary. This ensures unknown
# skills show up as "missing" rather than silently disappearing.
COMMON_TECH_SKILLS: set[str] = {
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go",
    "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "Perl",
    "Objective-C", "Dart", "Elixir", "Haskell", "Lua", "MATLAB",
    # Frontend
    "React", "Angular", "Vue", "Vue.js", "Svelte", "Next.js", "Nuxt",
    "jQuery", "Ember", "Backbone", "Redux", "MobX", "Tailwind",
    "Bootstrap", "Material UI", "Chakra UI",
    # Backend
    "Django", "Flask", "FastAPI", "Spring", "Spring Boot", "Express",
    "Node.js", "Rails", "Laravel", "ASP.NET", ".NET", "NestJS",
    "Gin", "Echo", "Actix", "Phoenix",
    # Databases
    "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "DynamoDB", "Cassandra", "SQLite", "Oracle", "MariaDB", "Neo4j",
    "CouchDB", "Firebase", "Supabase",
    # Cloud / Infra
    "AWS", "GCP", "Azure", "Heroku", "Vercel", "Netlify",
    "EC2", "S3", "Lambda", "RDS", "CloudFront", "SQS", "SNS",
    "BigQuery", "Cloud Functions",
    # DevOps / Tools
    "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins",
    "GitHub Actions", "GitLab CI", "CircleCI", "Travis CI",
    "Nginx", "Apache", "Vagrant", "Helm", "ArgoCD",
    # Data / ML
    "PyTorch", "TensorFlow", "Keras", "Scikit-learn", "Pandas",
    "NumPy", "Spark", "Hadoop", "Airflow", "dbt", "Kafka",
    "RabbitMQ", "Celery", "Flink",
    # General
    "Git", "Linux", "REST", "GraphQL", "gRPC", "WebSocket",
    "CI/CD", "Agile", "Scrum", "Jira", "Confluence",
    "data structure", "data structures", "algorithm", "algorithms", "object-oriented design", "OOP",
    "SDLC", "software development lifecycle", "debugging", "troubleshooting",
    "Figma", "Storybook",
    # Testing
    "Jest", "Pytest", "Cypress", "Selenium", "Playwright",
    "JUnit", "Mocha", "Vitest",
    # Mobile
    "React Native", "Flutter", "SwiftUI", "Jetpack Compose",
    "Xamarin", "Ionic",
}


def parse_job_description(
    raw_text: str,
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
    company_override: str | None = None,
    title_override: str | None = None,
) -> JobPosting:
    company, title = _extract_company_and_title(raw_text)
    if company_override:
        company = company_override
    if title_override:
        title = title_override

    sections = _split_sections(raw_text)
    vocab, synonyms = build_skill_vocabulary(profile, projects, rules)

    requirements = _extract_requirements(
        sections.get("requirements", ""), vocab, synonyms, is_required=True
    )
    nice_to_haves = _extract_requirements(
        sections.get("nice_to_have", ""), vocab, synonyms, is_required=False
    )
    responsibilities = _extract_bullet_lines(sections.get("responsibilities", ""))

    location = _extract_location(raw_text)

    all_keywords: list[str] = []
    seen: set[str] = set()
    for req in requirements + nice_to_haves:
        for kw in req.keywords:
            if kw not in seen:
                all_keywords.append(kw)
                seen.add(kw)

    experience_level = _detect_experience_level(raw_text, title)

    return JobPosting(
        raw_text=raw_text,
        company=company,
        title=title,
        location=location,
        experience_level=experience_level,
        requirements=requirements,
        responsibilities=responsibilities,
        nice_to_haves=nice_to_haves,
        extracted_keywords=all_keywords,
    )


def _extract_company_and_title(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return "Unknown", "Unknown"

    first = lines[0]

    # "Software Engineer at Google"
    at_match = re.match(r"^(.+?)\s+at\s+(.+)$", first, re.IGNORECASE)
    if at_match:
        return at_match.group(2).strip(), at_match.group(1).strip()

    # Prefer | as separator (title | company), since - is common inside titles
    pipe_match = re.match(r"^(.+?)\s*\|\s*(.+)$", first)
    if pipe_match:
        return pipe_match.group(2).strip(), pipe_match.group(1).strip()

    # Fall back to dash/em-dash as separator (title - company)
    dash_match = re.match(r"^(.+?)\s*[\-–—]\s*(.+)$", first)
    if dash_match:
        return dash_match.group(2).strip(), dash_match.group(1).strip()

    # "Company: X" / "Title: Y" in first few lines
    company = "Unknown"
    title = "Unknown"
    for line in lines[:6]:
        cm = re.match(r"^company\s*:\s*(.+)$", line, re.IGNORECASE)
        if cm:
            company = cm.group(1).strip()
        tm = re.match(r"^(?:title|position|role)\s*:\s*(.+)$", line, re.IGNORECASE)
        if tm:
            title = tm.group(1).strip()
    if company != "Unknown" or title != "Unknown":
        return company, title

    # Fallback: first line is title
    title = first
    if len(lines) > 1 and len(lines[1]) < 60:
        company = lines[1]

    return company, title


_SECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("requirements", re.compile(
        r"^(?:"
        r"(?:core\s+|key\s+|main\s+)?requirements?"
        r"|(?:basic|required|minimum|core|key)\s+qualifications?"
        r"|qualifications?"
        r"|what\s+you.+need"
        r"|must[\s\-]?have"
        r"|who\s+you\s+are"
        r"|what\s+we.+looking"
        r"|we['’]?re\s+looking\s+for"
        r"|looking\s+for"
        r"|skills?\s+(?:and|&)\s+experience"
        r"|your\s+(?:experience|skills)"
        r")",
        re.IGNORECASE,
    )),
    ("responsibilities", re.compile(
        r"^(?:(?:key\s+job\s+)?responsibilit|what\s+you.+do|the\s+role|about\s+the\s+role|in\s+this\s+role|you\s+will|your\s+impact|day[\s\-]to[\s\-]day)",
        re.IGNORECASE,
    )),
    ("nice_to_have", re.compile(
        r"^(?:nice[\s\-]?to[\s\-]?have|preferred(?:\s+qualifications?)?|bonus|plus|additional|it.s\s+a\s+plus)",
        re.IGNORECASE,
    )),
    ("about", re.compile(
        r"^(?:description|about\s+(?:us|the\s+company|the\s+role)|who\s+we\s+are|our\s+(?:mission|team|story|company))",
        re.IGNORECASE,
    )),
    ("benefits", re.compile(
        r"^(?:benefits?|perks|what\s+we\s+offer|compensation)",
        re.IGNORECASE,
    )),
]

_SECTION_STOP_PATTERN = re.compile(
    r"^(?:amazon\s+is\s+an\s+equal\s+opportunity|equal\s+opportunity|our\s+inclusive\s+culture|"
    r"the\s+base\s+salary\s+range|job\s+details|share\s+this\s+job|join\s+us\s+on|"
    r"download\s+our\s+app|find\s+careers|legal\s+disclosures|privacy\s+and\s+data|"
    r"©|\(c\))",
    re.IGNORECASE,
)


def _split_sections(text: str) -> dict[str, str]:
    lines = text.splitlines()
    sections: dict[str, list[str]] = {}
    current_section = "header"
    sections[current_section] = []

    for line in lines:
        stripped = line.strip()
        if _SECTION_STOP_PATTERN.search(stripped):
            current_section = "ignore"
            sections.setdefault(current_section, [])
            continue

        matched_section = None
        for name, pattern in _SECTION_PATTERNS:
            if pattern.search(stripped):
                matched_section = name
                break

        if matched_section:
            current_section = matched_section
            if current_section not in sections:
                sections[current_section] = []
        else:
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append(line)

    result = {k: "\n".join(v).strip() for k, v in sections.items() if v}
    result.pop("ignore", None)

    if "requirements" not in result and "header" in result:
        result["requirements"] = result["header"]

    return result


def _extract_bullet_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = re.sub(r"^[\-\*•\d+\.)\]]+\s*", "", stripped)
        if cleaned:
            lines.append(cleaned)
    return lines


def _extract_requirements(
    text: str,
    vocab: set[str],
    synonyms: dict[str, list[str]],
    is_required: bool,
) -> list[JobRequirement]:
    bullet_lines = _extract_bullet_lines(text)
    requirements: list[JobRequirement] = []
    for line in bullet_lines:
        keywords = _extract_keywords_from_line(line, vocab, synonyms)
        requirements.append(JobRequirement(
            text=line,
            keywords=keywords,
            is_required=is_required,
        ))
    return requirements


def _extract_keywords_from_line(
    line: str,
    vocab: set[str],
    synonyms: dict[str, list[str]],
) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    line_lower = line.lower()

    reverse_map: dict[str, str] = {}
    for canonical, syns in synonyms.items():
        for syn in syns:
            reverse_map[syn.lower()] = canonical

    all_terms: list[tuple[str, str]] = []
    for skill in vocab:
        all_terms.append((skill, skill))
    for syn_lower, canonical in reverse_map.items():
        all_terms.append((syn_lower, canonical))

    all_terms.sort(key=lambda t: len(t[0]), reverse=True)

    for term, canonical in all_terms:
        if canonical in seen:
            continue
        escaped = re.escape(term)
        if re.search(r"(?<![a-zA-Z])" + escaped + r"(?![a-zA-Z])", line_lower, re.IGNORECASE):
            matched.append(canonical)
            seen.add(canonical)

    return matched


_EXPERIENCE_LEVEL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("intern", re.compile(
        r"(?i)\b(?:intern(?:ship)?)\b"
    )),
    ("entry-level", re.compile(
        r"(?i)(?:"
        r"\bentry[\s\-]?level\b"
        r"|\bnew\s+grad(?:uate?)?\b"
        r"|\brecent\s+grad(?:uate?)?\b"
        r"|\b(?:0|zero)[\s\-]?(?:to|\-)[\s\-]?[12]\s*(?:year|yr)s?\b"
        r"|\bjunior\b"
        r"|\bearly[\s\-]?career\b"
        r"|\bassociate\s+(?:software|developer|engineer)\b"
        r")"
    )),
    ("mid-level", re.compile(
        r"(?i)(?:"
        r"\bmid[\s\-]?level\b"
        r"|\b[2-5]\+?\s*(?:year|yr)s?\s*(?:of\s+)?(?:experience|exp)\b"
        r")"
    )),
    ("senior", re.compile(
        r"(?i)(?:"
        r"\bsenior\b"
        r"|\bsr\.?\b"
        r"|\bstaff\b"
        r"|\bprincipal\b"
        r"|\b[5-9]\+?\s*(?:year|yr)s?\s*(?:of\s+)?(?:experience|exp)\b"
        r"|\b\d{2}\+?\s*(?:year|yr)s?\s*(?:of\s+)?(?:experience|exp)\b"
        r"|\blead\b"
        r")"
    )),
]


def _detect_experience_level(text: str, title: str) -> str | None:
    combined = f"{title}\n{text}"
    title_lower = title.lower()
    if re.search(r"\bintern(?:ship)?\b", title_lower):
        return "intern"
    if any(kw in title_lower for kw in ["junior", "jr.", "jr ", "entry"]):
        return "entry-level"
    if any(kw in title_lower for kw in ["senior", "sr.", "sr ", "staff", "principal", "lead"]):
        return "senior"
    for level, pattern in _EXPERIENCE_LEVEL_PATTERNS:
        if pattern.search(combined):
            return level
    return None


def _extract_location(text: str) -> str | None:
    loc = re.search(
        r"(?:location|based\s+in|located\s+in)\s*:?\s*(.+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    if loc:
        return loc.group(1).strip()

    remote = re.search(r"\b(remote|hybrid|on[\-\s]?site)\b", text, re.IGNORECASE)
    if remote:
        return remote.group(1).strip()

    return None


def build_skill_vocabulary(
    profile: MasterProfile,
    projects: list[Project],
    rules: ApplicationRules,
) -> tuple[set[str], dict[str, list[str]]]:
    vocab: set[str] = set()

    for skill in profile.skills.strong + profile.skills.familiar:
        vocab.add(skill)

    for project in projects:
        for tech in project.stack:
            vocab.add(tech)
        for fact in project.facts:
            for kw in fact.keywords:
                vocab.add(kw)
        for theme in project.themes:
            vocab.add(theme)

    vocab.update(COMMON_TECH_SKILLS)

    synonyms = dict(rules.keyword_synonyms)

    return vocab, synonyms
