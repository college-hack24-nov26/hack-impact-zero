import base64

import httpx
import pytest

from app.services.readme_service import get_repository_readme


@pytest.mark.anyio
async def test_get_repository_readme(monkeypatch):
    readme_content = "# Test Project\n\nA sample README."
    encoded_content = base64.b64encode(
        readme_content.encode("utf-8")
    ).decode("utf-8")

    async def mock_get(self, url, headers):
        return httpx.Response(
            200,
            json={
                "name": "README.md",
                "content": encoded_content,
                "encoding": "base64",
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await get_repository_readme("owner", "project")

    assert result["exists"] is True
    assert result["filename"] == "README.md"
    assert result["content"] == readme_content
    assert result["size"] == len(readme_content)


@pytest.mark.anyio
async def test_readme_not_found(monkeypatch):
    async def mock_get(self, url, headers):
        return httpx.Response(
            404,
            json={"message": "Not Found"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await get_repository_readme("owner", "project")

    assert result["exists"] is False
    assert result["filename"] is None
    assert result["content"] == ""
    assert result["size"] == 0