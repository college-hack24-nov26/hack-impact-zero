import re
import requests

def parse_github_url(url: str) -> tuple:
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, url)
    if match:
        owner = match.group(1)
        repo = match.group(2).replace(".git", "")
        return owner, repo
    return None, None

def fetch_github_repository_data(repo_url: str) -> dict:
    owner, repo = parse_github_url(repo_url)
    if not owner or not repo:
        return {"error": "Invalid GitHub repository URL format."}

    branches = ["main", "master"]
    readme_content = ""
    found_branch = ""

    for branch in branches:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
        res = requests.get(raw_url, timeout=10)
        if res.status_code == 200:
            readme_content = res.text
            found_branch = branch
            break

    if not readme_content:
        readme_content = f"# {repo}\n\nNo README.md file found in default branches."

    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{found_branch or 'main'}?recursive=1"
    detected_stack = []
    
    try:
        tree_res = requests.get(tree_url, timeout=10)
        if tree_res.status_code == 200:
            tree_data = tree_res.json().get("tree", [])
            file_paths = [item["path"].lower() for item in tree_data]

            if any(f.endswith(".py") for f in file_paths): detected_stack.append("python")
            if any("package.json" in f for f in file_paths): detected_stack.extend(["javascript", "node"])
            if any(f.endswith(".ts") or f.endswith(".tsx") for f in file_paths): detected_stack.append("typescript")
            if any("requirements.txt" in f or "pyproject.toml" in f for f in file_paths): detected_stack.append("fastapi")
            if any("dockerfile" in f for f in file_paths): detected_stack.append("docker")
            if any(f.endswith(".go") for f in file_paths): detected_stack.append("go")
            if any(f.endswith(".rs") for f in file_paths): detected_stack.append("rust")
            if any(f.endswith(".java") for f in file_paths): detected_stack.append("java")
    except Exception:
        detected_stack = ["python", "javascript"]

    return {
        "owner": owner,
        "repo": repo,
        "readme_content": readme_content,
        "detected_stack": list(set(detected_stack)) or ["python"]
    }
