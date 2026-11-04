"""Read public GitHub repositories through the GitHub REST API."""
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from config import (GITHUB_API, MAX_FILE_BYTES, MAX_SOURCE_FILES, PRIORITY_NAMES, USER_AGENT)


def github_json(path, token=None):
    """GET from the GitHub API. The token is sent only to api.github.com, never anywhere else."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT,
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(f"{GITHUB_API}{path}", headers=headers), timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _reset_minutes(error):
    reset = error.headers.get("X-RateLimit-Reset", "") if error.headers else ""
    if reset.isdigit():
        return max(1, (int(reset) - int(time.time())) // 60 + 1)
    return None


def github_error_message(error, has_token):
    """Plain-English message for an HTTPError from GitHub. Never contains the token."""
    code = error.code
    if code == 401:
        return "GitHub rejected the access token. Check it in Settings, or clear it to use GitHub without one."
    if code == 404:
        return "GitHub repository not found or it is private. Use a public repository URL."
    if code in (403, 429):
        if error.headers and error.headers.get("X-RateLimit-Remaining") == "0" or code == 429:
            wait = _reset_minutes(error)
            when = f" It resets in about {wait} minute{'s' if wait != 1 else ''}." if wait else ""
            if has_token:
                return "The GitHub rate limit was reached even with your token." + when
            return ("The GitHub rate limit was reached (60 reads per hour without a token). "
                    "Add a free GitHub token in Settings to raise it to 5,000 per hour." + when)
        return "GitHub refused the request (HTTP 403). The repository may be restricted."
    return f"GitHub returned an HTTP {code} error while reading the repository."


def token_status(token=None):
    """Rate-limit information for the token (or for anonymous access). Does not use up the limit."""
    try:
        core = github_json("/rate_limit", token)["resources"]["core"]
    except HTTPError as error:
        if error.code == 401:
            raise ValueError(github_error_message(error, True)) from None
        raise ValueError(f"GitHub returned an HTTP {error.code} error.") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("Could not reach GitHub. Check your internet connection.") from None
    except (KeyError, ValueError, TypeError):
        raise ValueError("GitHub returned a response that could not be read.") from None
    minutes = max(1, (int(core.get("reset", 0)) - int(time.time())) // 60 + 1)
    return {"limit": core.get("limit"), "remaining": core.get("remaining"), "resets_in_minutes": minutes,
            "authenticated": bool(token) and (core.get("limit") or 0) > 60}


def parse_github_url(repo_url):
    parsed = urlparse((repo_url or "").strip())
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() not in ("github.com", "www.github.com") or len(parts) < 2:
        raise ValueError("Enter a valid public GitHub repository URL, such as https://github.com/username/repository.")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise ValueError("The GitHub repository URL contains an invalid owner or repository name.")
    return owner, repo


def _raw(owner, repo, branch, path, timeout):
    req = Request(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}",
                  headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as response:
        return response.read(MAX_FILE_BYTES).decode("utf-8", errors="replace")


def fetch_repo_context(repo_url, token=None):
    owner, repo = parse_github_url(repo_url)
    base = f"/repos/{owner}/{repo}"
    try:
        metadata = github_json(base, token)
        branch = metadata.get("default_branch") or "main"
        languages = github_json(base + "/languages", token)
        tree = github_json(f"{base}/git/trees/{branch}?recursive=1", token).get("tree", [])
        paths = [item.get("path", "") for item in tree if item.get("type") == "blob"]

        readme_text = ""
        try:
            download_url = github_json(base + "/readme", token).get("download_url")
            if download_url:
                with urlopen(Request(download_url, headers={"User-Agent": USER_AGENT}), timeout=12) as response:
                    readme_text = response.read(MAX_FILE_BYTES).decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, ValueError):
            pass

        candidates = []
        for path in paths:
            name = path.rsplit("/", 1)[-1]
            lower = path.lower()
            if name in PRIORITY_NAMES:
                candidates.append(path)
            elif lower.startswith((".github/workflows/", "tests/", "test/")) and lower.endswith((".yml", ".yaml", ".py", ".js", ".ts")):
                candidates.append(path)
            elif lower.endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs")) and len(path.split("/")) <= 3:
                candidates.append(path)
        candidates = list(dict.fromkeys(candidates))[:MAX_SOURCE_FILES]

        inspected = []
        for path in candidates:
            try:
                inspected.append((path, _raw(owner, repo, branch, path, 8)[:MAX_FILE_BYTES]))
            except (HTTPError, URLError, TimeoutError):
                continue

        release = None
        try:
            release = github_json(base + "/releases/latest", token).get("tag_name")
        except (HTTPError, URLError, TimeoutError, ValueError):
            pass

        return {
            "owner": owner, "repo": repo, "url": f"https://github.com/{owner}/{repo}",
            "metadata": metadata, "languages": languages, "paths": paths,
            "readme": readme_text, "files": inspected, "release": release,
        }
    except HTTPError as error:
        raise ValueError(github_error_message(error, bool(token))) from None
    except (URLError, TimeoutError):
        raise ValueError("Could not reach GitHub. Check your internet connection or paste the project text instead.")
