from app.services.readme_analysis_service import analyze_readme


def test_analyze_readme_content():
    content = "\n".join([
        "# Demo Project",
        "",
        "![Build](https://img.shields.io/badge/build-passing-green)",
        "",
        "## Features",
        "Useful project features.",
        "",
        "## Installation",
        "Install dependencies.",
        "",
        "## Usage",
        "Run the application.",
        "",
        "[GitHub](https://github.com/example/project)",
        "",
        "```python",
        'print("Hello")',
        "```",
        "",
        "## License",
        "MIT",
    ])

    result = analyze_readme(content)

    assert result["word_count"] > 0
    assert result["heading_count"] == 5
    assert result["link_count"] == 1
    assert result["image_count"] == 1
    assert result["badge_count"] == 1
    assert result["code_block_count"] == 1
    assert "features" not in result["missing_sections"]
    assert "installation" not in result["missing_sections"]
    assert "usage" not in result["missing_sections"]
    assert "license" not in result["missing_sections"]
    assert result["is_empty"] is False


def test_analyze_empty_readme():
    result = analyze_readme("")

    assert result["word_count"] == 0
    assert result["heading_count"] == 0
    assert result["link_count"] == 0
    assert result["image_count"] == 0
    assert result["badge_count"] == 0
    assert result["code_block_count"] == 0
    assert len(result["missing_sections"]) == 6
    assert result["is_empty"] is True


def test_analyze_readme_with_missing_sections():
    content = "\n".join([
        "# My Project",
        "",
        "## Features",
        "Some features.",
    ])

    result = analyze_readme(content)

    assert result["heading_count"] == 2
    assert "features" not in result["missing_sections"]
    assert "installation" in result["missing_sections"]
    assert "usage" in result["missing_sections"]
    assert result["is_empty"] is False