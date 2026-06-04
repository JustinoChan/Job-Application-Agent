# Job Application Agent

A truth-constrained, proactive job-hunting agent. It scrapes new job postings on a schedule, scores each one against your real skills and projects, and only when you ask does it generate a tailored resume and cover letter — with every claim audited against source-of-truth YAML so the system literally cannot fabricate experience.

## How it works

```
Job posting (scraped or pasted)
        │
        ▼
   Job Parser ──► extract company, title, skills, requirements
        │
        ▼
   Fit Scorer ──► compatibility % vs your profile + project bank
        │
        ▼   (on demand — manual review at the dashboard)
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
  Output: versioned resume (MD + HTML + PDF) + cover letter + audit report
```

The key constraint: the resume tailor selects and reorders from approved facts in [data/project_bank.yaml](data/project_bank.yaml). It cannot invent companies, titles, internships, metrics, or technologies. Cover letters are LLM-written but pass a separate audit that flags any tech term not in your allowlist.

## Architecture

Three components run together:

```
┌────────────────────────────┐     ┌────────────────────────────┐
│  GCP VM (e2-micro)         │     │  Local machine             │
│                            │     │                            │
│  Scraper (systemd timer)   │     │  FastAPI backend :8000     │
│    every 4h                │     │    AUTH_MODE=token         │
│    • Greenhouse boards     │     │    Bearer token auth       │
│    • Lever boards          ├────►│    OpenClaw (local LLM)    │
│    • Ashby boards          │     │    Playwright (PDF)        │
│    • HN Who Is Hiring      │     │                            │
│    POSTs /discover         │     │  tracker.csv on disk       │
└────────────────────────────┘     └────────────────────────────┘
            ▲                                  ▲
            │            Cloudflare Tunnel     │
            │      api.<your-domain>           │
            │                                  │
            └──────────────────┬───────────────┘
                               │
                  ┌────────────┴───────────────┐
                  │  Cloudflare Pages          │
                  │  www.<your-domain>         │
                  │                            │
                  │  React dashboard           │
                  │   • sortable table         │
                  │   • fit / company / search │
                  │   • star, bulk archive     │
                  │   • per-job resume + audit │
                  └────────────────────────────┘
```

- **Backend** owns the YAML truth, the audit, and the artifact files. Stateless except for `jobs/tracker.csv` and the `outputs/` tree.
- **Scraper** is a one-shot Python service on a small VM that fires every 4h via a systemd timer. It pulls postings from public board APIs and POSTs each to the backend's idempotent `/api/applications/discover` endpoint.
- **Dashboard** is a static React/Vite bundle hosted on Cloudflare Pages, calling the same backend through the Tunnel.

## Project structure

```
job-application-agent/
  data/
    master_profile.yaml          # your profile (gitignored)
    project_bank.yaml            # approved project facts (gitignored)
    master_resume.yaml           # tailoring caps
    application_rules.yaml       # hard constraints + synonyms
    sample_master_profile.yaml   # committed template
    sample_project_bank.yaml     # committed template
  jobs/
    raw/                         # saved job description text
    tracker.csv                  # application tracker (gitignored)
  outputs/
    resumes/{job-id}/
      resume_v001.md             # tailored markdown
      resume_v001.meta.json      # structured metadata
      resume_v001.audit.json     # truth audit report
      resume_v001.html / .pdf    # rendered
    cover_letters/{job-id}/
      cover_letter_v001.{md,meta.json,audit.json,html,pdf}
  templates/
    resume_template.html
    cover_letter_template.html
  src/
    main.py                      # Typer CLI
    models.py                    # Pydantic data models
    config.py                    # paths and YAML loaders
    job_parser.py                # job description parser
    fit_scorer.py                # compatibility scoring
    resume_tailor.py             # project/skill selection
    claim_auditor.py             # truth verification gate
    pdf_renderer.py              # Jinja2 + Playwright
    pipeline.py                  # shared CLI/API orchestration
    job_scraper.py               # safe URL fetch + optional AI extraction
    cover_letter.py              # OpenClaw-backed cover letter generation
    openclaw_adapter.py          # local-LLM subprocess bridge
    tracker.py                   # CSV tracker + schema migrations
    filelock.py                  # portalocker-backed locks
  server/
    app.py                       # FastAPI entrypoint
    auth.py                      # token / Cloudflare Access auth
    routers/
      applications.py            # discover, preview, confirm, star, bulk-archive, search, ...
      dashboard.py               # stats
  scraper/                       # runs on the GCP VM
    main.py                      # entrypoint, dispatches by source kind
    config.py                    # env-based config
    api_client.py                # POSTs to /discover
    sources/
      __init__.py                # SourceFn registry + WatchlistEntry
      greenhouse.py / lever.py / ashby.py / hn_who_is_hiring.py
      _html.py / _date.py / _match.py
    deploy/
      scraper.service            # systemd one-shot unit
      scraper.timer              # fires every 4h with jitter
      install.sh                 # two-phase deploy: keygen, then clone+install
    watchlist.example.yaml       # ~45 starter sources
  web/
    src/
      api/{client.ts,types.ts}
      pages/{Dashboard,AddApplication,JobDetail,Login}.tsx
      components/{ApplicationTable,FilterBar,...}.tsx
      styles.css
  skills/
    job-apply-assist/SKILL.md    # OpenClaw / Claude-style chat skill
  tests/
```

## Setup

### Backend (local machine)

```bash
git clone https://github.com/JustinoChan/Job-Application-Agent.git
cd Job-Application-Agent

python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e .

# Chromium for PDF rendering (one-time)
playwright install chromium
```

Copy the sample YAML files and edit them with your real data:

```bash
cp data/sample_master_profile.yaml data/master_profile.yaml
cp data/sample_project_bank.yaml data/project_bank.yaml
```

Configure the FastAPI environment:

```bash
cp .env.example .env
# Then set in .env:
#   AUTH_MODE=token
#   API_TOKEN=<a long random string — VM and dashboard will both use this>
#   CORS_ORIGINS=https://www.<your-domain>
```

### Web dashboard

```bash
cd web
npm install
npm run build   # output: web/dist/
```

For production, deploy `web/dist/` to Cloudflare Pages. The Login page asks for the `API_TOKEN` and stashes it in `localStorage`.

### Cloudflare Tunnel

Create a Tunnel pointing your API hostname at `http://127.0.0.1:8000`:

```yaml
# ~/.cloudflared/config.yml
tunnel: <your-tunnel-id>
ingress:
  - hostname: api.<your-domain>
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Do **not** layer Cloudflare Access on top of the API hostname — the VM can't follow Access auth redirects. Bearer-token auth on FastAPI is the gate.

### GCP VM (scraper)

Provision an `e2-micro` (free-tier eligible) Debian 12+ instance in `us-west1-a` or similar. Then from your local machine:

```powershell
# Copy the installer
gcloud compute scp scraper\deploy\install.sh <instance-name>:install.sh `
    --zone=<zone>

# SSH in
gcloud compute ssh <instance-name> --zone=<zone>
```

On the VM, run install.sh **twice**:

```bash
sudo bash ~/install.sh
# Phase 1: prints an SSH public key. Copy it.
# Add it to GitHub → repo → Settings → Deploy keys (read-only).

sudo bash ~/install.sh
# Phase 2: clones the repo via SSH, sets up the venv, installs systemd units.

# Configure scraper env (paste the same API_TOKEN as the backend)
sudo nano /opt/job-application-agent/scraper/.env
# Set:
#   API_BASE_URL=https://api.<your-domain>
#   API_TOKEN=<the same token from backend .env>

# Self-test end-to-end (requires backend + tunnel running)
sudo -u scraper /opt/job-application-agent/scraper/.venv/bin/python -m scraper.main --self-test

# Enable the recurring timer
sudo systemctl enable --now scraper.timer
```

## Running the system

There are three things that need to be live at the same time for the scraper → tracker → dashboard pipeline to work end-to-end.

### 1. Local machine — FastAPI backend

```powershell
cd "C:\Code Stuff\Job-Application-Agent"
.\.venv\Scripts\python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

Sanity checks:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/applications/openclaw-status   (requires Bearer)
```

Restart whenever you edit `.env`, `master_profile.yaml`, `project_bank.yaml`, or `application_rules.yaml`.

### 2. Local machine — Cloudflare Tunnel

```powershell
cloudflared tunnel run <your-tunnel-name>
```

Sanity check from anywhere (or the VM):

```bash
curl -fsS https://api.<your-domain>/health
# {"status":"ok"}
```

### 3. GCP VM — scraper

Runs automatically every 4 hours under systemd. To trigger manually:

```bash
sudo systemctl start scraper.service
sudo journalctl -u scraper.service --since '5 minutes ago' --no-pager
systemctl list-timers scraper.timer
```

To deploy code updates pushed to `main`:

```bash
cd /opt/job-application-agent
sudo -u scraper git pull
sudo bash /opt/job-application-agent/scraper/deploy/install.sh
```

The installer is idempotent — it preserves your `.env` and `watchlist.yaml`, only re-syncing systemd units and venv deps.

### 4. Browser — dashboard

Open `https://www.<your-domain>` (Cloudflare Pages). Log in with your `API_TOKEN`. You'll see:

- A table of every tracked application with sortable columns (company, role, status, fit %, posted date, updated)
- A filter bar (min fit % slider, company name filter, full-text search across saved postings)
- Star button per row, multi-select checkboxes with bulk-archive action
- Per-job detail page with resume preview, audit report, cover-letter generation

## CLI usage (interactive resume tailoring)

The CLI still works for one-shot manual flows.

```bash
# Full pipeline (parse + score + tailor + audit)
python -m src.main pipeline --file job_description.txt \
    --company "ExampleCo" --title "Software Engineer"

# Then render the PDF
python -m src.main render-pdf exampleco-software-engineer-20260514

# Cover letter
python -m src.main cover-letter <job-id>
python -m src.main render-cover-letter-pdf <job-id>

# Tracker
python -m src.main status
python -m src.main log <job-id> submitted --notes "Applied via website"
python -m src.main log <job-id> interview --response-date 2026-06-03 --response-type recruiter_screen --interview-stage recruiter --source-quality 4
python -m src.main backup-tracker
python -m src.main restore-tracker jobs/tracker.backup-20260603-120000.csv
```

Versions are monotonic per `job-id` — each `tailor` run writes `resume_v001.md`, `resume_v002.md`, etc. and never overwrites.

## Truth audit

The claim auditor is a required gate. Every resume bullet must trace back to an approved fact in [data/project_bank.yaml](data/project_bank.yaml):

- **PASS**: bullet matches a source fact exactly
- **WARN**: minor variation (similarity > 85%)
- **FAIL**: no matching source, or a hard constraint was violated

Hard constraints (in [data/application_rules.yaml](data/application_rules.yaml)) prevent claiming things like professional internship experience, AWS production deployment, or other unsupported credentials. `render-pdf` re-runs the audit before generating a PDF and blocks on FAIL. WARN blocks unless `--allow-warn` is passed.

Cover letters get a different audit: each technical term is checked against an allowlist built from your profile, project stacks, and the job's extracted keywords. Generic framing sentences ("Thank you for your time") are exempt; specific claims must overlap with approved sources.

## Tracker

Applications flow through these statuses:

`found → prepared → reviewed → submitted → {interview, assessment, offer, rejected, ghosted, archived}`

The scraper inserts new postings as `found`. You review on the dashboard, then click `Save to Tracker` (or run `python -m src.main tailor <job-id>`) to advance to `prepared` with a versioned audited resume attached. Manual status updates from there.

The tracker also captures lightweight application feedback: `response_date`, `response_type`, `interview_stage`, and `source_quality` (1-5). These fields let the dashboard report real response rate and source quality instead of only counting status changes.

The tracker.csv schema auto-migrates on each read — adding a new column to `TRACKER_COLUMNS` requires only a one-line entry in `_COLUMN_DEFAULTS` in [src/tracker.py](src/tracker.py), no manual migration script. Before risky tracker work, run `python -m src.main backup-tracker`; restoring with `restore-tracker` automatically saves a `tracker.pre-restore-*.csv` copy first.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v

# If Windows temp permissions get cranky:
python -m pytest tests/ -v --basetemp .pytest_tmp_run
```

## Roadmap

- **v0.1** CLI pipeline with fit scoring, resume tailoring, truth audit, CSV tracker
- **v0.2** PDF generation via Playwright, per-job resume versioning, audit gate
- **v0.3** React dashboard, FastAPI backend, safe URL scraping, preview/confirm
- **v0.4** Proactive scraper on GCP VM, multi-source watchlist (Greenhouse / Lever / Ashby / Workday / HN), Bearer-token auth, sortable / filterable dashboard with star + bulk-archive + full-text search, `posted_at` capture from sources
- **v0.5 (current)** Cover-letter generation with audit-visible drafts, Discord notifications for high-fit roles, tracker backup/restore commands, and response-feedback fields for tracking outcomes
- **v0.6** Semantic fit scoring with embeddings while preserving the explainable deterministic score
- **v0.7** Browser form filling with Playwright (pause before submit)

## License

MIT
