import base64

import httpx


GITHUB_API_BASE = "https://api.github.com"


async def get_repository_readme(
    owner: str,
    repository: str,
) -> dict:
    """Retrieve and decode the README of a public GitHub repository."""

    url = (
        f"{GITHUB_API_BASE}/repos/{owner}/{repository}/readme"
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code == 404:
        return {
            "exists": False,
            "filename": None,
            "content": "",
            "size": 0,
        }

    response.raise_for_status()

    data = response.json()
    encoded_content = data.get("content", "")
    content = base64.b64decode(encoded_content).decode(
        "utf-8",
        errors="replace",
    )

    return {
        "exists": True,
        "filename": data["name"],
        "content": content,
        "size": len(content),
    }