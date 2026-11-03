
import pytest

from app.services.readme_badge_service import (
    generate_readme_badges,
    insert_badges_into_readme,
)


def test_generate_repository_badges():
    repository = {
        "full_name": "owner/project",
        "html_url": "https://github.com/owner/project",
        "language": "Python",
    }

    result = generate_readme_badges(repository)

    assert result["repository"] == "owner/project"
    assert result["project_url"] == "https://github.com/owner/project"
    assert result["badge_count"] == 6
    assert "img.shields.io" in result["markdown"]
    assert "github/stars/owner/project" in result["markdown"]


def test_every_badge_links_to_actual_project():
    repository = {
        "full_name": "owner/project",
        "html_url": "https://github.com/owner/project",
        "language": "Python",
    }

    result = generate_readme_badges(repository)

    for badge in result["badges"]:
        assert badge["project_url"] == repository["html_url"]
        assert repository["html_url"] in badge["markdown"]
        assert badge["image_url"].startswith("https://img.shields.io/")


def test_language_badge_is_optional():
    repository = {
        "full_name": "owner/project",
        "html_url": "https://github.com/owner/project",
        "language": None,
    }

    result = generate_readme_badges(repository)

    assert result["badge_count"] == 5


def test_invalid_repository_is_rejected():
    with pytest.raises(ValueError):
        generate_readme_badges({
            "full_name": "",
            "html_url": "https://github.com/owner/project",
        })


def test_non_github_project_url_is_rejected():
    with pytest.raises(ValueError):
        generate_readme_badges({
            "full_name": "owner/project",
            "html_url": "https://example.com/project",
        })


def test_badges_are_inserted_after_readme_title():
    result = insert_badges_into_readme(
        "# My Project\n\nProject description.",
        "[![Stars](https://img.shields.io/github/stars/owner/project)](https://github.com/owner/project)",
    )

    assert result.startswith("# My Project")
    assert result.index("My Project") < result.index("img.shields.io")
    assert "Project description." in result


def test_badges_are_inserted_when_readme_has_no_title():
    result = insert_badges_into_readme(
        "Project description.",
        "[![Stars](https://img.shields.io/example)](https://github.com/owner/project)",
    )

    assert result.startswith("[![Stars]")
    assert "Project description." in result
