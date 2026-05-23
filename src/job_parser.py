from __future__ import annotations

import re

from src.models import ApplicationRules, JobPosting, JobRequirement, MasterProfile, Project

COMMON_TECH_SKILLS: set[str] = {
    # ── Languages ───────────────────────────────────────────────────
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go",
    "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "Perl",
    "Objective-C", "Dart", "Elixir", "Haskell", "Lua", "MATLAB",
    "OCaml", "F#", "Clojure", "Groovy", "Julia", "Zig", "Erlang",
    "Assembly", "Shell", "Bash", "PowerShell", "Solidity",
    "WebAssembly", "WASM", "SQL", "PL/SQL", "T-SQL",

    # ── Frontend ────────────────────────────────────────────────────
    "React", "Angular", "Vue", "Vue.js", "Svelte", "Next.js", "Nuxt",
    "jQuery", "Ember", "Redux", "MobX", "Tailwind", "Tailwind CSS",
    "Bootstrap", "Material UI", "Chakra UI", "Storybook", "Figma",
    "HTML", "CSS", "SCSS", "Sass", "LESS", "Webpack", "Vite",
    "Rollup", "esbuild", "Babel", "SWC",

    # ── Backend ─────────────────────────────────────────────────────
    "Django", "Flask", "FastAPI", "Spring", "Spring Boot", "Express",
    "Node.js", "Rails", "Ruby on Rails", "Laravel", "ASP.NET", ".NET",
    "NestJS", "Gin", "Echo", "Actix", "Phoenix", "Fiber",

    # ── Databases ───────────────────────────────────────────────────
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "DynamoDB", "Cassandra", "SQLite", "Oracle", "MariaDB", "Neo4j",
    "CouchDB", "Firebase", "Supabase", "InfluxDB", "TimescaleDB",
    "ScyllaDB", "CockroachDB", "TiDB", "Vitess", "Memcached",
    "RocksDB", "LevelDB", "etcd", "ClickHouse", "Druid",
    "Snowflake", "Redshift", "BigQuery", "Presto", "Trino",
    "SingleStore", "Spanner",

    # ── Cloud / Infra ───────────────────────────────────────────────
    "AWS", "GCP", "Azure", "Heroku", "Vercel", "Netlify", "cloud computing",
    "EC2", "S3", "Lambda", "RDS", "CloudFront", "SQS", "SNS",
    "Cloud Functions", "Cloud Run", "Cloud Storage", "Cloud SQL",
    "Pub/Sub", "Bigtable", "App Engine", "Compute Engine",
    "IAM", "VPC", "CloudFormation", "CDK", "Kinesis", "EMR",
    "Glue", "SageMaker", "Bedrock", "ECS", "EKS", "Fargate",
    "Step Functions", "Azure DevOps", "Azure Functions",

    # ── DevOps / CI/CD ──────────────────────────────────────────────
    "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins",
    "GitHub Actions", "GitLab CI", "CircleCI", "Travis CI",
    "Nginx", "Apache", "Helm", "ArgoCD", "Flux", "Spinnaker",
    "Buildkite", "Concourse", "TeamCity", "Puppet", "Chef",
    "Packer", "Vagrant", "containerd", "Podman", "Docker Compose",
    "Nomad", "Mesos", "OpenShift",

    # ── Networking ──────────────────────────────────────────────────
    "TCP", "UDP", "TCP/IP", "IP", "HTTP", "HTTPS", "HTTP/2", "HTTP/3",
    "DNS", "DHCP", "BGP", "OSPF", "MPLS", "VLAN", "VPN", "SDN", "NFV",
    "NAT", "firewall", "load balancer", "load balancing", "proxy",
    "reverse proxy", "CDN", "NIC", "network interface",
    "socket programming", "routing", "switching",
    "RDMA", "InfiniBand", "RoCE", "DPDK", "SR-IOV", "SPDK", "XDP",
    "io_uring", "Ethernet", "WAN", "LAN",
    "networking", "network engineering", "network security",
    "host networking", "datacenter networking",

    # ── Systems / Kernel / OS ───────────────────────────────────────
    "Linux", "Unix", "Windows", "macOS", "kernel", "kernel systems",
    "system call", "device driver", "file system", "memory management",
    "process management", "thread", "threading", "multithreading",
    "concurrency", "parallelism", "synchronization", "mutex", "semaphore",
    "lock-free", "systems programming", "embedded systems",
    "real-time systems", "RTOS", "eBPF", "BPF",
    "operating systems", "OS internals",

    # ── Distributed Systems / Architecture ──────────────────────────
    "distributed systems", "microservices", "microservice", "monolith",
    "service mesh", "event-driven", "event-driven architecture",
    "CQRS", "domain-driven design", "SOA", "API gateway",
    "message queue", "pub/sub", "eventual consistency",
    "consensus", "Raft", "Paxos", "replication",
    "sharding", "partitioning", "consistent hashing",
    "Istio", "Envoy", "Linkerd", "Consul", "ZooKeeper",
    "service discovery", "circuit breaker", "rate limiting",
    "idempotency", "saga pattern",

    # ── Data / ML / AI ──────────────────────────────────────────────
    "PyTorch", "TensorFlow", "Keras", "Scikit-learn", "Pandas",
    "NumPy", "Spark", "Hadoop", "Airflow", "dbt", "Kafka",
    "RabbitMQ", "Celery", "Flink", "Apache Beam", "Dagster",
    "Prefect", "Delta Lake", "Iceberg", "Parquet", "Avro",
    "data pipeline", "ETL", "ELT", "data warehouse", "data lake",
    "data modeling", "data engineering", "data science",
    "machine learning", "deep learning", "neural network",
    "LLM", "NLP", "natural language processing", "computer vision",
    "reinforcement learning", "transformer", "fine-tuning",
    "RAG", "retrieval augmented generation", "embeddings",
    "vector database", "Pinecone", "Weaviate", "FAISS", "Chroma",
    "LangChain", "Hugging Face", "ONNX", "TensorRT", "vLLM",
    "model serving", "inference", "training",
    "recommendation system", "feature engineering",
    "A/B testing", "statistical analysis", "statistics",
    "SciPy", "Matplotlib", "Seaborn", "Jupyter",

    # ── Observability / Monitoring ──────────────────────────────────
    "Prometheus", "Grafana", "Datadog", "Splunk", "ELK",
    "Logstash", "Kibana", "Fluentd", "OpenTelemetry", "Jaeger",
    "Zipkin", "New Relic", "PagerDuty", "tracing", "metrics",
    "alerting", "SLO", "SLI", "SLA", "observability", "monitoring",
    "logging", "APM",

    # ── Security ────────────────────────────────────────────────────
    "security", "cryptography", "TLS", "SSL", "OAuth", "OAuth2",
    "SAML", "LDAP", "RBAC", "SSO", "JWT", "authentication",
    "authorization", "encryption", "hashing", "PKI",
    "WAF", "SIEM", "vulnerability", "penetration testing",
    "OWASP", "secure coding", "zero trust",

    # ── Protocols / Serialization ───────────────────────────────────
    "REST", "GraphQL", "gRPC", "Protobuf", "Protocol Buffers",
    "Thrift", "JSON", "XML", "YAML", "WebSocket", "SSE", "WebRTC",
    "MQTT", "AMQP", "NATS",

    # ── Performance / Reliability ───────────────────────────────────
    "performance", "optimization", "benchmarking", "profiling",
    "latency", "throughput", "caching", "scalability",
    "high availability", "fault tolerance", "disaster recovery",
    "chaos engineering", "load testing", "stress testing",
    "capacity planning",

    # ── Testing ─────────────────────────────────────────────────────
    "Jest", "Pytest", "Cypress", "Selenium", "Playwright",
    "JUnit", "Mocha", "Vitest", "RSpec", "unittest",
    "integration testing", "unit testing", "end-to-end testing",
    "test automation", "TDD", "BDD",

    # ── Mobile ──────────────────────────────────────────────────────
    "React Native", "Flutter", "SwiftUI", "Jetpack Compose",
    "Xamarin", "Ionic", "iOS", "Android",

    # ── General / Process ───────────────────────────────────────────
    "Git", "CI/CD", "Agile", "Scrum", "Kanban", "Jira", "Confluence",
    "data structure", "data structures", "algorithm", "algorithms",
    "object-oriented design", "OOP", "functional programming",
    "design patterns", "SOLID", "clean architecture",
    "SDLC", "software development lifecycle",
    "debugging", "troubleshooting", "code review",
    "system design", "API design", "technical writing",
    "pair programming", "mentoring",

    # ── Package / Build ─────────────────────────────────────────────
    "npm", "yarn", "pnpm", "pip", "poetry", "cargo",
    "Maven", "Gradle", "Bazel", "CMake", "Make",

    # ── Storage / File Systems ──────────────────────────────────────
    "NFS", "iSCSI", "SAN", "NAS", "block storage", "object storage",
    "Ceph", "MinIO", "HDFS", "ZFS", "ext4",

    # ── Messaging / Streaming ───────────────────────────────────────
    "Kafka", "Pulsar", "Amazon SQS", "Google Pub/Sub", "NATS",
    "ActiveMQ", "ZeroMQ", "Redis Streams", "Kinesis",
    "event streaming", "stream processing",

    # ── Virtualization ──────────────────────────────────────────────
    "VMware", "KVM", "QEMU", "Xen", "hypervisor", "virtualization",
    "bare metal",
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
        r"|what\s+you.+(?:need|bring)"
        r"|must[\s\-]?have"
        r"|who\s+you\s+are"
        r"|about\s+you"
        r"|what\s+we.+looking"
        r"|we[‘’]?re\s+looking\s+for"
        r"|looking\s+for"
        r"|skills?\s+(?:and|&)\s+experience"
        r"|your\s+(?:experience|skills|background)"
        r"|you\s+(?:should|will|might)\s+have"
        r"|you\s+have"
        r"|the\s+ideal\s+candidate"
        r"|ideal\s+candidate"
        r"|we[‘’’]?d\s+love.*(?:if\s+you|hear\s+from)"
        r"|experience\s+(?:and|&)\s+skills"
        r"|technical\s+(?:requirements?|qualifications?|skills)"
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
        r"^(?:benefits?|perks|what\s+we\s+offer|compensation|competenc(?:y|ies))",
        re.IGNORECASE,
    )),
]

_SECTION_STOP_PATTERN = re.compile(
    r"^(?:amazon\s+is\s+an\s+equal\s+opportunity|equal\s+opportunity|our\s+inclusive\s+culture|"
    r"the\s+base\s+salary\s+range|job\s+details|share\s+this\s+job|join\s+us\s+on|"
    r"download\s+our\s+app|find\s+careers|legal\s+disclosures|privacy\s+and\s+data|"
    r"drug\s+free\s+workplace|equal\s+employment|affirmative\s+action|"
    r"export\s+control|visa\s+sponsorship|security\s+clearance|"
    r"the\s+salary\s+range|the\s+annual\s+salary|the\s+hourly\s+rate|pay\s+range|"
    r"the\s+typical\s+pay|salary\s+range\s+for\s+this|"
    r"we\s+are\s+an\s+equal|we\s+are\s+committed\s+to|"
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
