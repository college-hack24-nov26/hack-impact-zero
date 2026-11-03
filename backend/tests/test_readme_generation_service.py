
import asyncio

from app.services.readme_generation_service import (
    build_readme_prompt,
    generate_readme,
)


def test_build_readme_prompt_uses_repository_evidence():
    repository = {
        "full_name": "owner/project",
        "description": "A test project",
        "language": "Python",
    }

    analysis = {
        "total_files": 10,
        "languages": {"Python": 5},
    }

    prompt = build_readme_prompt(repository, analysis)

    assert "owner/project" in prompt
    assert "A test project" in prompt
    assert "Python" in prompt
    assert "Never invent features" in prompt


def test_build_readme_prompt_includes_existing_readme():
    prompt = build_readme_prompt(
        {"full_name": "owner/project"},
        {},
        "# Existing Project",
    )

    assert "# Existing Project" in prompt


def test_generate_readme_returns_model_output(monkeypatch):

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "response": "# Generated README\n\nA sample project."
            }

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            assert "api/generate" in url
            assert json["model"] == "qwen2.5-coder:1.5b"
            return MockResponse()

    monkeypatch.setattr(
        "app.services.readme_generation_service.httpx.AsyncClient",
        MockClient,
    )

    result = asyncio.run(
        generate_readme(
            {"full_name": "owner/project"},
            {"total_files": 5},
        )
    )

    assert result["content"].startswith("# Generated README")
    assert result["provider"] == "ollama"
    assert result["model"] == "qwen2.5-coder:1.5b"
    assert result["word_count"] > 0
