from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src import config
from src.models import MasterProfile, TailoredResume


def render_html(tailored: TailoredResume, profile: MasterProfile) -> str:
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATES_DIR)))
    template = env.get_template("resume_template.html")
    context = {
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "github": profile.github,
        "portfolio": profile.portfolio,
        "education": [
            {"school": e.school, "degree": e.degree, "graduation": e.graduation}
            for e in profile.education
        ],
        "skills_strong": tailored.reordered_skills.strong,
        "skills_familiar": tailored.reordered_skills.familiar,
        "projects": [
            {
                "name": p.name,
                "role": p.role,
                "date_range": p.date_range,
                "stack": p.stack,
                "bullets": [f.original_text for f in p.selected_facts],
            }
            for p in tailored.selected_projects
        ],
    }
    return template.render(**context)


def save_html(html: str, job_id: str, version: int) -> Path:
    paths = config.version_paths(job_id, version)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["html"].write_text(html, encoding="utf-8")
    return paths["html"]


async def render_pdf(html_path: Path, pdf_path: Path) -> Path:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(html_path.as_uri())
        await page.pdf(
            path=str(pdf_path),
            format="Letter",
            margin={
                "top": "0.5in",
                "bottom": "0.5in",
                "left": "0.5in",
                "right": "0.5in",
            },
        )
        await browser.close()
    return pdf_path
