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

    monkeypatch.setattr(
        repository_api,
        "get_repository_metadata",
        mock_metadata,
    )

    response = client.get(
        "/api/repository/analyze",
        params={"url": "https://github.com/owner/project"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["repository"]["full_name"] == "owner/project"


def test_analyze_repository_rejects_invalid_url():
    response = client.get(
        "/api/repository/analyze",
        params={"url": "https://example.com/owner/project"},
    )

    assert response.status_code == 400
    assert "github.com" in response.json()["detail"]