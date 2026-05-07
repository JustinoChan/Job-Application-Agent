---
name: job-apply-assist
description: Help Justin prepare truthful, tailored job applications using the local job-application-agent repo.
---

Use this skill when Justin asks to apply to a job, tailor a resume, evaluate a job posting, or update the job tracker.

Repository:
C:\Code Stuff\Job-Application-Agent

Hard rules:
- Never submit an application without Justin explicitly saying: "Submit this application."
- Never invent experience, employment, technologies, metrics, certifications, or education.
- Use only the local YAML files as source-of-truth.
- Always run the claim audit before showing a final resume.
- If the audit fails, stop and explain the unsupported claims.
- Pause for human review on:
  - work authorization
  - sponsorship
  - salary
  - disability/veteran/self-ID
  - relocation
  - background check questions
  - free-response questions
  - CAPTCHA or bot checks

Workflow:
1. Save the job URL or pasted job description to a file, e.g. `jobs/raw/temp_input.txt`.
2. Run:
   ```
   python -m src.main ingest-job --file jobs/raw/temp_input.txt --company "<company>" --title "<title>"
   ```
3. Run:
   ```
   python -m src.main tailor "<job_id>"
   ```
4. The `tailor` command automatically runs the claim audit.
5. Show Justin:
   - fit score
   - resume changes (which projects selected, skill reordering)
   - missing requirements
   - audit result
   - tracker row
6. Ask for approval before any browser filling.
7. Do not submit unless Justin explicitly approves.

Alternative: run the full pipeline in one step:
```
python -m src.main pipeline --file jobs/raw/temp_input.txt --company "<company>" --title "<title>"
```

Tracker commands:
- View all: `python -m src.main status`
- Update status: `python -m src.main log "<job_id>" "<status>"`
- Re-audit: `python -m src.main audit "<resume_path>"`
