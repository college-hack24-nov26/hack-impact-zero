from fastapi.testclient import TestClient

from app.main import app
from app.api import repository as repository_api


client = TestClient(app)


def test_analyze_repository(monkeypatch):
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

    monkeypatch.setattr(
        repository_api,
        "get_repository_metadata",
        mock_metadata,
    )
    monkeypatch.setattr(
        repository_api,
        "get_repository_tree",
        mock_tree,
    )

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
    assert data["analysis"]["important_files"] == [
        "README.md",
        "requirements.txt",
    ]


def test_analyze_repository_rejects_invalid_url():
    response = client.get(
        "/api/repository/analyze",
        params={"url": "https://example.com/owner/project"},
    )

    assert response.status_code == 400
    assert "github.com" in response.json()["detail"]