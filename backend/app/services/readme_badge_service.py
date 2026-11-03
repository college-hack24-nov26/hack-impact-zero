import re

BADGE_CATALOG = {
    # Languages
    "python": "![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)",
    "javascript": "![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)",
    "typescript": "![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)",
    "java": "![Java](https://img.shields.io/badge/Java-ED8B00?style=for-the-badge&logo=openjdk&logoColor=white)",
    "cpp": "![C++](https://img.shields.io/badge/C%2B%2B-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)",
    "go": "![Go](https://img.shields.io/badge/Go-00ADD8?style=for-the-badge&logo=go&logoColor=white)",
    "rust": "![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white)",
    "html5": "![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)",
    "css3": "![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)",

    # Frameworks & Libraries
    "react": "![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)",
    "fastapi": "![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)",
    "django": "![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)",
    "flask": "![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)",
    "express": "![Express.js](https://img.shields.io/badge/Express.js-404D59?style=for-the-badge)",
    "nextjs": "![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)",
    "vue": "![Vue.js](https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D)",
    "angular": "![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)",
    "tailwind": "![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)",
    "node": "![Node.js](https://img.shields.io/badge/Node.js-43853D?style=for-the-badge&logo=node.js&logoColor=white)",

    # Databases & DevOps
    "docker": "![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)",
    "kubernetes": "![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)",
    "aws": "![AWS](https://img.shields.io/badge/Amazon_AWS-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white)",
    "postgresql": "![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)",
    "mongodb": "![MongoDB](https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white)",
    "redis": "![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)",
    "sqlite": "![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)",

    # Standard Repo Shields
    "license_mit": "![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)",
    "prs_welcome": "![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=for-the-badge)"
}

def generate_tech_badges(tech_stack: list, repo_owner: str = None, repo_name: str = None) -> str:
    badges = []
    
    for tech in tech_stack:
        key = tech.lower().strip()
        if key in BADGE_CATALOG:
            badges.append(BADGE_CATALOG[key])
            
    if repo_owner and repo_name:
        stars_badge = f"![GitHub Stars](https://img.shields.io/github/stars/{repo_owner}/{repo_name}?style=for-the-badge&logo=github)"
        forks_badge = f"![GitHub Forks](https://img.shields.io/github/forks/{repo_owner}/{repo_name}?style=for-the-badge&logo=github)"
        issues_badge = f"![GitHub Issues](https://img.shields.io/github/issues/{repo_owner}/{repo_name}?style=for-the-badge&logo=github)"
        badges.extend([stars_badge, forks_badge, issues_badge])
        
    if not any("license" in b.lower() for b in badges):
        badges.append(BADGE_CATALOG["license_mit"])
        badges.append(BADGE_CATALOG["prs_welcome"])
        
    return "  \n".join(badges)
