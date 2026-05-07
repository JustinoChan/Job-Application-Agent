# Job Application Agent

A CLI tool that tailors resumes to job descriptions using only verified, truthful data from structured YAML files. Every resume bullet is audited against source-of-truth project data before output — the system cannot fabricate experience, skills, or credentials.

## How It Works

```
Job Description (pasted text or file)
        │
        ▼
   Job Parser ──► extract company, title, skills, requirements
        │
        ▼
   Fit Scorer ──► match job requirements against your profile
        │
        ▼
  Resume Tailor ──► select relevant projects, reorder skills
        │
        ▼
  Claim Auditor ──► verify every bullet against YAML source data
        │
        ▼
  Output: tailored resume (Markdown) + audit report + tracker row
```

The key constraint: the model can only select and rewrite from approved facts stored in `project_bank.yaml`. It cannot invent companies, titles, internships, metrics, or technologies.

## Project Structure

```
job-application-agent/
  data/
    master_profile.yaml      # your real profile (gitignored)
    project_bank.yaml        # approved project facts (gitignored)
    master_resume.yaml       # resume structure config
    application_rules.yaml   # constraints, synonyms, thresholds
    sample_master_profile.yaml   # example profile template
    sample_project_bank.yaml     # example project bank template
  jobs/
    raw/                     # saved job descriptions
    tracker.csv              # application tracker (gitignored)
  outputs/
    resumes/                 # generated resume markdown + metadata
    cover_letters/           # (v0.2)
    audits/                  # audit report JSON files
  templates/
    resume_template.html     # Jinja2 HTML template (for v0.2 PDF)
  src/
    main.py                  # Typer CLI
    models.py                # Pydantic data models
    config.py                # paths and YAML loaders
    job_parser.py            # job description parser
    fit_scorer.py            # candidate fit scoring
    resume_tailor.py         # project/skill selection and markdown generation
    claim_auditor.py         # truth verification gate
    tracker.py               # CSV tracker operations
    pdf_renderer.py          # stub (v0.2)
    browser_apply.py         # stub (v0.3)
  skills/
    job-apply-assist/
      SKILL.md               # OpenClaw skill definition
  tests/
```

## Setup

```bash
git clone https://github.com/JustinoChan/Job-Application-Agent.git
cd Job-Application-Agent

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install typer pydantic pyyaml rich jinja2
```

### Configure Your Profile

Copy the sample files and fill in your real data:

```bash
cp data/sample_master_profile.yaml data/master_profile.yaml
cp data/sample_project_bank.yaml data/project_bank.yaml
```

Edit `data/master_profile.yaml` with your name, email, education, and skills. Edit `data/project_bank.yaml` with your real projects and approved facts.

## Usage

### Full Pipeline (recommended)

Run ingest, scoring, tailoring, and audit in one command:

```bash
python -m src.main pipeline --file job_description.txt --company "ExampleCo" --title "Software Engineer"
```

### Individual Commands

```bash
# Ingest a job description
python -m src.main ingest-job --file job_description.txt --company "ExampleCo" --title "SWE"

# Tailor resume for a tracked job
python -m src.main tailor <job-id>

# Run standalone truth audit
python -m src.main audit outputs/resumes/exampleco_swe_20260506.md

# Update application status
python -m src.main log <job-id> submitted --notes "Applied via website"

# View tracker
python -m src.main status
python -m src.main status --filter interview
```

### Interactive Mode

Run without `--file` to paste a job description directly:

```bash
python -m src.main pipeline --company "ExampleCo" --title "Software Engineer"
# Paste the job description, press Enter twice to finish
```

## Example Output

```
┌──────── Fit Score: ExampleCo - Software Engineer ────────┐
│ Overall: MODERATE (55%)                                  │
│                                                          │
│ Strong matches:                                          │
│   + React                                                │
│   + Python                                               │
│   + Django                                               │
│   + SQL                                                  │
│   + JavaScript                                           │
│   + Git                                                  │
│                                                          │
│ Missing required:                                        │
│   - AWS                                                  │
│   - Docker                                               │
│                                                          │
│ Missing nice-to-haves:                                   │
│   ~ Kubernetes                                           │
│   ~ CI/CD                                                │
└──────────────────────────────────────────────────────────┘

┌──────────── Claim Audit Report ──────────────┐
│ Verdict │ Fact ID          │ Reason          │
│ PASS    │ capstone-fact-01 │ Exact match     │
│ PASS    │ capstone-fact-02 │ Exact match     │
│ PASS    │ search-fact-01   │ Exact match     │
│                                              │
│ Total: 7 │ Pass: 7 │ Warn: 0 │ Fail: 0      │
│ Overall: PASS                                │
└──────────────────────────────────────────────┘
```

## Truth Audit

The claim auditor is a required gate. Every resume bullet must trace back to an approved fact in `project_bank.yaml`. The audit checks:

- **PASS**: bullet exactly matches a source fact
- **WARN**: minor variation detected (similarity > 85%)
- **FAIL**: no matching source found, or hard constraint violated

Hard constraints (defined in `application_rules.yaml`) prevent claiming things like professional internship experience, AWS production deployment, or other unsupported credentials.

## Tracker

Applications are tracked in `jobs/tracker.csv` with statuses:

`found` → `prepared` → `reviewed` → `submitted` → `interview` / `assessment` / `rejected` / `offer` / `ghosted`

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Roadmap

- **v0.1** (current): CLI pipeline with fit scoring, resume tailoring, truth audit, CSV tracker
- **v0.2**: PDF generation via Playwright, resume versioning, cover letter support
- **v0.3**: Browser form filling with Playwright (pause before submit)
- **v0.4**: OpenClaw integration as a chat-driven workflow

## License

MIT
