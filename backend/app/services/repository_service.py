from urllib.parse import urlparse


def parse_github_url(repository_url: str) -> dict:
    """Extract owner and repository name from a GitHub URL."""

    parsed = urlparse(repository_url.strip())

    if parsed.scheme != "https":
        raise ValueError("Only HTTPS GitHub URLs are supported.")

    if parsed.netloc.lower() != "github.com":
        raise ValueError("The URL must belong to github.com.")

    parts = parsed.path.strip("/").split("/")

    if len(parts) != 2 or not all(parts):
        raise ValueError("The URL must contain an owner and repository name.")

    owner = parts[0]
    repository = parts[1]

    if repository.endswith(".git"):
        repository = repository[:-4]

    if not owner or not repository:
        raise ValueError("Invalid GitHub repository URL.")

    return {
        "owner": owner,
        "repository": repository,
        "full_name": f"{owner}/{repository}",
    }