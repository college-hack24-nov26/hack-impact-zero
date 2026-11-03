
import re
from urllib.parse import quote


def generate_readme_badges(repository: dict) -> dict:
    """Generate repository-specific Shields.io badges."""

    full_name = repository.get("full_name", "").strip()
    project_url = repository.get("html_url", "").strip()

    if not full_name or "/" not in full_name:
        raise ValueError("Valid repository full_name is required.")

    if not project_url.startswith("https://github.com/"):
        raise ValueError("A valid GitHub project URL is required.")

    safe_repository = quote(full_name, safe="/-_.")
    safe_project_url = project_url.rstrip("/")

    badge_definitions = [
        ("GitHub Stars", f"https://img.shields.io/github/stars/{safe_repository}?style=for-the-badge"),
        ("GitHub Forks", f"https://img.shields.io/github/forks/{safe_repository}?style=for-the-badge"),
        ("GitHub Issues", f"https://img.shields.io/github/issues/{safe_repository}?style=for-the-badge"),
        ("Last Commit", f"https://img.shields.io/github/last-commit/{safe_repository}?style=for-the-badge"),
        ("Top Language", f"https://img.shields.io/github/languages/top/{safe_repository}?style=for-the-badge"),
    ]

    language = repository.get("language")

    if language:
        badge_definitions.append(
            (
                "Language",
                f"https://img.shields.io/badge/language-{quote(language, safe='')}-blue?style=for-the-badge",
            )
        )

    badges = [
        {
            "name": name,
            "image_url": image_url,
            "project_url": safe_project_url,
            "markdown": f"[![{name}]({image_url})]({safe_project_url})",
        }
        for name, image_url in badge_definitions
    ]

    return {
        "repository": full_name,
        "project_url": safe_project_url,
        "badges": badges,
        "badge_count": len(badges),
        "markdown": "\n".join(badge["markdown"] for badge in badges),
    }


def insert_badges_into_readme(content: str, badge_markdown: str) -> str:
    """Insert generated badges immediately after the first README title."""

    content = (content or "").strip()
    badge_markdown = (badge_markdown or "").strip()

    if not badge_markdown:
        return content

    if not content:
        return badge_markdown

    title_match = re.search(r"^# .+$", content, re.MULTILINE)

    if title_match:
        insertion_point = title_match.end()
        return (
            content[:insertion_point]
            + "\n\n"
            + badge_markdown
            + "\n\n"
            + content[insertion_point:].lstrip()
        )

    return badge_markdown + "\n\n" + content
