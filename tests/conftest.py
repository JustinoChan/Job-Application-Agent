from __future__ import annotations

import pytest

from src.models import (
    ApplicationRules,
    Constraints,
    Education,
    Fact,
    MasterProfile,
    MasterResume,
    Project,
    SkillSet,
)


@pytest.fixture
def sample_profile() -> MasterProfile:
    return MasterProfile(
        name="Test User",
        email="test@example.com",
        location="Test City, CA",
        education=[
            Education(school="Test University", degree="B.S. Computer Science", graduation="June 2025")
        ],
        skills=SkillSet(
            strong=["Python", "React", "JavaScript", "TypeScript", "Django", "SQL", "HTML", "CSS", "Git", "REST API"],
            familiar=["Java", "C++", "PyTorch", "Firebase", "MongoDB", "Linux"],
        ),
        constraints=Constraints(
            never_claim=[
                "professional software engineering internship",
                "paid industry software engineering experience",
                "AWS production experience",
                "Kubernetes experience",
            ],
            allowed_actions=["reorder projects", "rewrite bullets"],
        ),
    )


@pytest.fixture
def sample_projects() -> list[Project]:
    return [
        Project(
            id="capstone-archive",
            name="Capstone Project Archive",
            role="Full-Stack Developer",
            date_range="Sep 2024 - Mar 2025",
            stack=["React.js", "Django REST API", "MySQL8", "Firebase Authentication"],
            description="A full-stack web application for hosting student capstone projects.",
            themes=["full-stack", "backend", "frontend", "authentication", "web development"],
            facts=[
                Fact(
                    id="capstone-fact-01",
                    text="Built a full-stack web application for hosting student projects using React.js frontend and Django REST API backend.",
                    keywords=["React", "Django", "REST API", "full-stack", "web development"],
                ),
                Fact(
                    id="capstone-fact-02",
                    text="Led frontend improvements and coordinated team development using agile practices.",
                    keywords=["frontend", "agile", "team leadership", "React"],
                ),
                Fact(
                    id="capstone-fact-03",
                    text="Integrated Firebase Authentication for secure user login and access control.",
                    keywords=["Firebase", "authentication", "security"],
                ),
                Fact(
                    id="capstone-fact-04",
                    text="Helped migrate from Firebase database usage to MySQL8 and Django REST API after requirements changed.",
                    keywords=["MySQL", "Django", "database migration", "SQL"],
                ),
            ],
        ),
        Project(
            id="search-engine",
            name="Search Engine",
            role="Developer",
            date_range="Jan 2025 - Mar 2025",
            stack=["Python"],
            description="A search engine that indexes and queries over 56,000 web pages.",
            themes=["algorithms", "backend", "search", "performance", "Python"],
            facts=[
                Fact(
                    id="search-fact-01",
                    text="Developed a search engine in Python capable of indexing and querying over 56,000 web pages.",
                    keywords=["Python", "search", "indexing", "information retrieval"],
                ),
                Fact(
                    id="search-fact-02",
                    text="Implemented tokenization, indexing, and query handling for efficient full-text search.",
                    keywords=["algorithms", "tokenization", "indexing", "search"],
                ),
            ],
        ),
    ]


@pytest.fixture
def sample_rules() -> ApplicationRules:
    return ApplicationRules(
        never_claim=["internship experience", "paid work experience", "AWS production", "Kubernetes"],
        always_include_skills=["Python", "Git"],
        preferred_project_order=["capstone-archive", "search-engine"],
        min_fit_score_to_apply=0.3,
        keyword_synonyms={
            "React": ["React.js", "ReactJS"],
            "JavaScript": ["JS", "ES6"],
            "SQL": ["MySQL", "MySQL8", "PostgreSQL", "databases", "database"],
            "Django": ["Django REST Framework", "Django REST API", "DRF"],
            "REST API": ["RESTful", "RESTful API", "REST", "RESTful APIs"],
            "Python": ["Python3"],
            "Git": ["GitHub", "Version Control"],
            "C++": ["CPP"],
        },
    )


@pytest.fixture
def sample_resume_config() -> MasterResume:
    return MasterResume(max_projects=4, max_facts_per_project=4)


REACT_JOB_TEXT = """Software Engineer - New Grad | ExampleCo

Location: San Francisco, CA (Hybrid)

About the Role
We're looking for a new grad software engineer to join our web platform team.

Responsibilities
- Build and maintain web applications using React and TypeScript
- Design and implement RESTful APIs using Python and Django
- Collaborate with product and design teams

Requirements
- Bachelor's degree in Computer Science or related field
- Experience with React or similar frontend frameworks
- Proficiency in Python
- Experience with SQL databases
- Strong understanding of HTML, CSS, JavaScript
- Experience with version control (Git)

Nice to Have
- Experience with TypeScript
- Experience with Django or Flask
- Knowledge of cloud platforms (AWS, GCP, or Azure)
- Experience with Docker
"""

JAVA_JOB_TEXT = """Senior Java Developer | BigCorpInc

Location: Remote

Requirements
- 5+ years of professional Java development experience
- Strong experience with Spring Boot and Spring Framework
- Production experience with Kubernetes and Docker
- AWS services (EC2, S3, Lambda, RDS)
- Experience with Apache Kafka or similar message queues
- Production experience with PostgreSQL
- CI/CD pipeline management (Jenkins, GitHub Actions)
- Microservices architecture design

Nice to Have
- Experience with Terraform or CloudFormation
- GraphQL API development
"""


AMAZON_JOB_TEXT = """Software Development Engineer, AWS Data Services - 2026 (US) - Job ID: 10414316 | Amazon.jobs
Skip to main content
Home
Teams
Locations
Job categories
My career
Settings
Sign out
Resources
Accommodations
Software Development Engineer, AWS Data Services - 2026 (US)
Job ID: 10414316 | Amazon.com Services LLC
Apply now
Description
AWS operates some of the world's most widely used database, storage, and analytics services.
Key job responsibilities
• Design and develop scalable solutions using cloud-native architectures and microservices in a large distributed computing environment.
• Build and maintain resilient distributed systems that are scalable, fault-tolerant, and cost-effective.
• Work in an agile environment practicing CI/CD principles while participating in operational responsibilities including on-call duties.
Basic Qualifications
- Experience with at least one general-purpose programming language such as Java, Python, C++, C#, Go, Rust, or TypeScript
- Experience with data structure implementation, basic algorithm development, and/or object-oriented design principles
- Currently has, or is in the process of obtaining a bachelor's degree in Computer Science, Computer Engineering, Data Science, Information Systems, or related STEM fields
- Must be 18 years of age of older
Preferred Qualifications
- Experience from previous technical internship(s) or demonstrated project experience
- Experience with one or more of the following: AI tools for development productivity, Cloud platforms (preferably AWS), Database systems (SQL and NoSQL), Contributing to open-source projects, Version control systems, Debugging and troubleshooting complex systems
- Basic understanding of software development lifecycle (SDLC)
- Strong problem-solving and analytical skills
Amazon is an equal opportunity employer and does not discriminate on the basis of protected veteran status, disability, or other legally protected status.
Job details
USA, WA, Seattle
Jobs for grads
Software Development
Share this job
"""
