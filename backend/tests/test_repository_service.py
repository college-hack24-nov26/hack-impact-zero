import pytest

from app.services.repository_service import parse_github_url


def test_parse_github_url():
    result = parse_github_url("https://github.com/owner/project")

    assert result["owner"] == "owner"
    assert result["repository"] == "project"
    assert result["full_name"] == "owner/project"


def test_parse_github_url_with_git_suffix():
    result = parse_github_url("https://github.com/owner/project.git")

    assert result["repository"] == "project"


def test_reject_non_github_url():
    with pytest.raises(ValueError):
        parse_github_url("https://example.com/owner/project")