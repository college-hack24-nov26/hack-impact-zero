
from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.api import repository as repository_api


client = TestClient(app)


def mock_repository_data(monkeypatch):
    async def mock_metadata(owner, repository):
        return {
            "name": repository,
            "full_name": f"{owner}/{repository}",
            "description": "Test repository",
            "owner": owner,
            "language": "Python",
            "stars": 100,
            "forks": 20,
            "default_branch": "main",
            "html_url": f"https://github.com/{owner}/{repository}",
        }

    async def mock_tree(owner, repository, branch):
        return {
            "files": [
                {"path": "README.md", "type": "blob", "size": 500},
                {"path": "requirements.txt", "type": "blob", "size": 100},
                {"path": "main.py", "type": "blob", "size": 300},
            ],
            "total_items": 3,
            "truncated": False,
        }

    async def mock_readme(owner, repository):
        return {
            "exists": True,
            "filename": "README.md",
            "content": (
                "# Test Project\n\n"
                "## Features\n"
                "Example features.\n\n"
                "## Installation\n"
                "Install dependencies.\n"
            ),
            "size": 85,
        }

    monkeypatch.setattr(
        repository_api, "get_repository_metadata", mock_metadata
    )
    monkeypatch.setattr(
        repository_api, "get_repository_tree", mock_tree
    )
    monkeypatch.setattr(
        repository_api, "get_repository_readme", mock_readme
    )


def test_analyze_repository(monkeypatch):
    mock_repository_data(monkeypatch)

    response = client.get(
        "/api/repository/analyze",
        params={"url": "https://github.com/owner/project"},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["repository"]["full_name"] == "owner/project"
    assert data["analysis"]["total_files"] == 3
    assert data["analysis"]["languages"] == {"Python": 1}
    assert data["readme"]["exists"] is True
    assert data["readme_analysis"]["heading_count"] == 3
    assert data["readme_analysis"]["word_count"] > 0
    assert "features" not in data["readme_analysis"]["missing_sections"]
    assert "installation" not in data["readme_analysis"]["missing_sections"]


def test_analyze_repository_rejects_invalid_url():
    response = client.get(
        "/api/repository/analyze",
        params={"url": "https://example.com/owner/project"},
    )

    assert response.status_code == 400
    assert "github.com" in response.json()["detail"]


def test_generate_repository_readme(monkeypatch):
    mock_repository_data(monkeypatch)

    async def mock_generate_readme(repository, analysis, existing_readme):
        assert repository["full_name"] == "owner/project"
        assert analysis["total_files"] == 3
        assert "# Test Project" in existing_readme

        return {
            "content": "# Improved Project\n\nGenerated documentation.",
            "model": "qwen2.5-coder:1.5b",
            "provider": "ollama",
            "word_count": 6,
        }

    monkeypatch.setattr(
        repository_api, "generate_readme", mock_generate_readme
    )

    response = client.post(
        "/api/repository/generate",
        params={"url": "https://github.com/owner/project"},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["repository"] == "owner/project"
    assert data["generated_readme"].startswith("# Improved Project")
    assert "img.shields.io" in data["generated_readme"]
    assert "https://github.com/owner/project" in data["generated_readme"]
    assert data["badge_count"] == 6
    assert data["model"] == "qwen2.5-coder:1.5b"
    assert data["provider"] == "ollama"
    assert data["word_count"] > 0


def test_generate_repository_readme_rejects_invalid_url():
    response = client.post(
        "/api/repository/generate",
        params={"url": "https://example.com/owner/project"},
    )

    assert response.status_code == 400
    assert "github.com" in response.json()["detail"]


def test_validate_repository_readme(monkeypatch):
    mock_repository_data(monkeypatch)

    response = client.post(
        "/api/repository/validate",
        params={"url": "https://github.com/owner/project"},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["repository"] == "owner/project"
    assert data["readme_exists"] is True
    assert data["validation"]["is_valid"] is True
    assert data["validation"]["warning_count"] == 0
    assert data["validation"]["severity_counts"] == {
        "critical": 0,
        "warning": 0,
        "unverified": 0,
    }
    assert data["validation"]["checked_files"] == 3


def test_validate_repository_readme_with_missing_readme(monkeypatch):
    mock_repository_data(monkeypatch)

    async def mock_readme_missing(owner, repository):
        return {
            "exists": False,
            "filename": None,
            "content": "",
            "size": 0,
        }

    monkeypatch.setattr(
        repository_api, "get_repository_readme", mock_readme_missing
    )

    response = client.post(
        "/api/repository/validate",
        params={"url": "https://github.com/owner/project"},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["readme_exists"] is False
    assert data["validation"]["is_valid"] is False
    assert data["validation"]["severity_counts"]["critical"] == 1


def test_validate_repository_readme_rejects_invalid_url():
    response = client.post(
        "/api/repository/validate",
        params={"url": "https://example.com/owner/project"},
    )

    assert response.status_code == 400
    assert "github.com" in response.json()["detail"]


def test_validate_repository_readme_github_api_failure(monkeypatch):
    async def failing_metadata(owner, repository):
        raise httpx.HTTPError("GitHub API unavailable")

    monkeypatch.setattr(
        repository_api, "get_repository_metadata", failing_metadata
    )

    response = client.post(
        "/api/repository/validate",
        params={"url": "https://github.com/owner/project"},
    )

    assert response.status_code == 502
    assert "Unable to communicate with GitHub" in response.json()["detail"]
