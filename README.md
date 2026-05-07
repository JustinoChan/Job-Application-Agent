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
  PDF Renderer ──► HTML via Jinja2, PDF via Playwright Chromium
        │
        ▼
  Output: versioned resume (MD + HTML + PDF) + audit report + tracker row
```

The key constraint: the system can only select and reorder from approved facts stored in `project_bank.yaml`. It cannot invent companies, titles, internships, metrics, or technologies.

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
    resumes/
      {job-id}/              # per-job versioned folder
        resume_v001.md       # tailored markdown
        resume_v001.meta.json  # structured metadata
        resume_v001.audit.json # truth audit report
        resume_v001.html     # rendered HTML
        resume_v001.pdf      # final PDF
    cover_letters/           # (future)
  templates/
    resume_template.html     # Jinja2 HTML template for PDF
  src/
    main.py                  # Typer CLI
    models.py                # Pydantic data models
    config.py                # paths and YAML loaders
    job_parser.py            # job description parser
    fit_scorer.py            # candidate fit scoring
    resume_tailor.py         # project/skill selection and markdown generation
    claim_auditor.py         # truth verification gate
    pdf_renderer.py          # HTML + PDF rendering via Jinja2/Playwright
    pipeline.py              # shared CLI/API orchestration
    job_scraper.py           # safe URL fetch + optional AI extraction
    filelock.py              # tracker/version file locks
    tracker.py               # CSV tracker operations
    browser_apply.py         # stub (future)
  server/
    app.py                   # FastAPI app
    auth.py                  # token / Cloudflare Access auth
    routers/                 # applications + dashboard endpoints
  web/
    src/                     # React + Vite dashboard
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

pip install -e .

# Install Playwright's Chromium browser for PDF generation
playwright install chromium
```

### Web Dashboard Setup

The dashboard is optional. It runs as a React/Vite frontend talking to a local FastAPI backend.

```bash
# Backend
copy .env.example .env
# edit .env and set API_TOKEN or AUTH_MODE=none for local-only testing
uvicorn server.app:app --reload --port 8000

# Frontend
cd web
npm install
npm run dev
```

Open `http://localhost:5173`.

For deployment, host `web/dist` on Cloudflare Pages and expose the local FastAPI backend with Cloudflare Tunnel. Protect the API hostname with Cloudflare Access. Do not rely on `VITE_API_TOKEN` as production security because Vite exposes frontend env vars in the browser bundle.

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

Then generate the PDF:

```bash
python -m src.main render-pdf exampleco-software-engineer-20260506
```

### Resume Versioning

Each time you run `tailor` or `pipeline` for the same job, a new version is created without overwriting previous ones:

```
outputs/resumes/exampleco-software-engineer-20260506/
  resume_v001.md
  resume_v001.meta.json
  resume_v001.audit.json
  resume_v002.md        # second run
  resume_v002.meta.json
  resume_v002.audit.json
```

### Individual Commands

```bash
# Ingest a job description
python -m src.main ingest-job --file job_description.txt --company "ExampleCo" --title "SWE"

# Tailor resume for a tracked job (creates new version each run)
python -m src.main tailor <job-id>

# Run standalone truth audit
python -m src.main audit <job-id>
python -m src.main audit <job-id> --version 1

# Render PDF (runs audit gate first)
python -m src.main render-pdf <job-id>
python -m src.main render-pdf <job-id> --version 1 --allow-warn

# Update application status
python -m src.main log <job-id> submitted --notes "Applied via website"

# View tracker
python -m src.main status
python -m src.main status --filter interview
```

## Web/API Flow

The web dashboard supports:

1. Fetch a job URL or paste job text.
2. Review/edit extracted job text.
3. Preview fit score, resume HTML, and audit report without disk writes.
4. Confirm save to create versioned artifacts and update `jobs/tracker.csv`.
5. Open a job detail page to preview the resume, download the PDF, view audit entries, and update status.

The confirm step uses the exact reviewed text from preview. It does not re-scrape the URL.

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

The `render-pdf` command re-runs the audit before generating a PDF. If the audit fails, PDF generation is blocked. Warnings block by default unless `--allow-warn` is passed.

## Tracker

Applications are tracked in `jobs/tracker.csv` with statuses:

`found` -> `prepared` -> `reviewed` -> `submitted` -> `interview` / `assessment` / `rejected` / `offer` / `ghosted` / `archived`

The tracker also records the latest resume version number for each job.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v

# If Windows temp permissions get cranky:
python -m pytest tests/ -v --basetemp .pytest_tmp_run
```

## Roadmap

- **v0.1**: CLI pipeline with fit scoring, resume tailoring, truth audit, CSV tracker
- **v0.2**: PDF generation via Playwright, per-job resume versioning, audit gate for PDF
- **v0.3** (current): React dashboard, FastAPI backend, safe URL scraping, preview/confirm workflow
- **v0.4**: Browser form filling with Playwright (pause before submit)
- **v0.5**: OpenClaw integration as a chat-driven workflow

## License

MIT
