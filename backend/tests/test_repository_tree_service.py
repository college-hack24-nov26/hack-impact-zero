import httpx
import pytest

from app.services.repository_tree_service import get_repository_tree


@pytest.mark.anyio
async def test_get_repository_tree(monkeypatch):
    expected_data = {
        "sha": "abc123",
        "truncated": False,
        "tree": [
            {
                "path": "README.md",
                "type": "blob",
                "size": 1200,
            },
            {
                "path": "backend",
                "type": "tree",
            },
            {
                "path": "backend/main.py",
                "type": "blob",
                "size": 500,
            },
        ],
    }

    async def mock_get(self, url, headers):
        return httpx.Response(
            200,
            json=expected_data,
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await get_repository_tree("owner", "project", "main")

    assert result["total_items"] == 3
    assert result["truncated"] is False
    assert result["files"][0]["path"] == "README.md"
    assert result["files"][1]["type"] == "tree"
    assert result["files"][2]["size"] == 500


@pytest.mark.anyio
async def test_repository_tree_not_found(monkeypatch):
    async def mock_get(self, url, headers):
        return httpx.Response(
            404,
            json={"message": "Not Found"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.raises(ValueError, match="GitHub repository tree not found"):
        await get_repository_tree("owner", "missing-project", "main")