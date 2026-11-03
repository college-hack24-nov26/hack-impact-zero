from urllib.parse import quote

import httpx


GITHUB_API_BASE = "https://api.github.com"


async def get_repository_tree(
    owner: str,
    repository: str,
    branch: str,
) -> dict:
    """Retrieve the file and directory structure of a GitHub repository."""

    encoded_branch = quote(branch, safe="")

    url = (
        f"{GITHUB_API_BASE}/repos/{owner}/{repository}"
        f"/git/trees/{encoded_branch}?recursive=1"
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code == 404:
        raise ValueError("GitHub repository tree not found.")

    response.raise_for_status()

    data = response.json()

    files = [
        {
            "path": item["path"],
            "type": item["type"],
            "size": item.get("size"),
        }
        for item in data.get("tree", [])
    ]

    return {
        "files": files,
        "total_items": len(files),
        "truncated": data.get("truncated", False),
    }