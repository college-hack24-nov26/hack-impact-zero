import httpx
import pytest

from app.services.github_service import get_repository_metadata


@pytest.mark.anyio
async def test_get_repository_metadata(monkeypatch):
    expected_data = {
        "name": "test-project",
        "full_name": "owner/test-project",
        "description": "A test repository",
        "owner": {"login": "owner"},
        "language": "Python",
        "stargazers_count": 100,
        "forks_count": 20,
        "default_branch": "main",
        "html_url": "https://github.com/owner/test-project",
    }

    async def mock_get(self, url, headers):
        return httpx.Response(
            200,
            json=expected_data,
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await get_repository_metadata("owner", "test-project")

    assert result["name"] == "test-project"
    assert result["full_name"] == "owner/test-project"
    assert result["language"] == "Python"
    assert result["stars"] == 100
    assert result["forks"] == 20


@pytest.mark.anyio
async def test_repository_not_found(monkeypatch):
    async def mock_get(self, url, headers):
        return httpx.Response(
            404,
            json={"message": "Not Found"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.raises(ValueError, match="GitHub repository not found"):
        await get_repository_metadata("owner", "missing-project")