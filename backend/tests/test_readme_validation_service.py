
from app.services.readme_validation_service import validate_readme


def test_valid_readme():
    result = validate_readme(
        "# Demo\n\n## Installation\n\nInstall dependencies.",
        ["requirements.txt"],
    )

    assert result["is_valid"] is True
    assert result["warning_count"] == 0


def test_empty_readme():
    result = validate_readme("")

    assert result["is_valid"] is False
    assert result["severity_counts"]["critical"] == 1


def test_missing_local_link():
    result = validate_readme(
        "# Demo\n\n[Installation](docs/install.md)",
        ["README.md"],
    )

    assert result["is_valid"] is False
    assert result["warnings"][0]["category"] == "missing_local_link"


def test_installation_without_dependency_manifest():
    result = validate_readme(
        "# Demo\n\n## Installation\n\npip install example",
        ["README.md"],
    )

    assert result["severity_counts"]["unverified"] == 1
    assert result["warnings"][0]["category"] == "installation_command"


def test_missing_configuration_file():
    result = validate_readme(
        "# Demo\n\nCopy the .env.example file.",
        ["README.md"],
    )

    assert result["warnings"][0]["category"] == "configuration_reference"


def test_empty_section_ignores_title():
    result = validate_readme(
        "# Demo\n\n## Installation\n\nInstall dependencies.",
        ["requirements.txt"],
    )

    assert not any(
        warning["category"] == "empty_section"
        for warning in result["warnings"]
    )


def test_empty_documentation_section():
    result = validate_readme(
        "# Demo\n\n## Installation\n\n## Usage\n\nRun the application.",
        ["requirements.txt"],
    )

    assert any(
        warning["category"] == "empty_section"
        and warning["evidence"] == "Installation"
        for warning in result["warnings"]
    )
