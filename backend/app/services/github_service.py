import httpx


GITHUB_API_BASE = "https://api.github.com"


async def get_repository_metadata(owner: str, repository: str) -> dict:
    """Fetch public repository metadata from GitHub."""

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repository}"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code == 404:
        raise ValueError("GitHub repository not found.")

    response.raise_for_status()

    data = response.json()

    return {
        "name": data["name"],
        "full_name": data["full_name"],
        "description": data["description"],
        "owner": data["owner"]["login"],
        "language": data["language"],
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "default_branch": data["default_branch"],
        "html_url": data["html_url"],
    }