
import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse


DEPENDENCY_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "Pipfile.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
}

CONFIG_FILES = {
    ".env",
    ".env.example",
    "config.json",
    "config.yaml",
    "config.yml",
    "settings.py",
    "config.py",
}

INSTALL_COMMAND_PATTERNS = [
    r"pip install",
    r"npm install",
    r"npm ci",
    r"yarn install",
    r"pnpm install",
    r"cargo build",
    r"go build",
    r"mvn install",
    r"gradle build",
]


def _normalize_repository_files(repository_files) -> set:
    """Convert repository file paths into a normalized set."""

    normalized = set()

    for item in repository_files or []:
        path = item.get("path") if isinstance(item, dict) else item

        if isinstance(path, str) and path.strip():
            normalized.add(
                unquote(path.strip().replace("\\", "/").lstrip("./"))
            )

    return normalized


def _add_warning(warnings, severity, category, message, evidence):
    """Add a structured validation warning."""

    warnings.append({
        "severity": severity,
        "category": category,
        "message": message,
        "evidence": evidence,
    })


def _check_local_links(content, repository_files, warnings):
    """Find README links pointing to missing repository files."""

    link_pattern = (
        r'(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+"[^"]*")?\)'
    )

    for link in re.findall(link_pattern, content):
        parsed = urlparse(link)

        if parsed.scheme or parsed.netloc:
            continue

        if link.startswith("mailto:"):
            continue

        target = unquote(parsed.path)

        if not target:
            continue

        normalized_target = str(
            PurePosixPath(target.replace("\\", "/"))
        ).lstrip("./")

        if normalized_target not in repository_files:
            _add_warning(
                warnings,
                "warning",
                "missing_local_link",
                "README references a repository file that was not found.",
                link,
            )


def _check_installation_commands(content, repository_files, warnings):
    """Check installation commands against available dependency manifests."""

    has_dependency_file = bool(
        repository_files.intersection(DEPENDENCY_FILES)
    )

    for line in content.splitlines():
        stripped = line.strip()

        if not any(
            re.search(pattern, stripped, re.IGNORECASE)
            for pattern in INSTALL_COMMAND_PATTERNS
        ):
            continue

        if not has_dependency_file:
            _add_warning(
                warnings,
                "unverified",
                "installation_command",
                (
                    "An installation command is documented, but no "
                    "recognized dependency manifest was found."
                ),
                stripped,
            )


def _check_configuration_references(
    content,
    repository_files,
    warnings,
):
    """Detect references to known configuration files that are missing."""

    for filename in CONFIG_FILES:
        if filename not in content:
            continue

        if filename not in repository_files:
            _add_warning(
                warnings,
                "unverified",
                "configuration_reference",
                (
                    "README references a configuration file that "
                    "was not found in the repository."
                ),
                filename,
            )


def _check_empty_sections(content, warnings):
    """Detect empty sections while ignoring the main README title."""

    heading_pattern = re.compile(
        r"^(#{1,6})\s+(.+?)\s*$",
        re.MULTILINE,
    )

    headings = list(heading_pattern.finditer(content))

    for index, heading in enumerate(headings):
        # H1 is the document title, not a documentation section.
        if len(heading.group(1)) == 1:
            continue

        section_start = heading.end()

        next_heading_start = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(content)
        )

        section_content = content[
            section_start:next_heading_start
        ].strip()

        if not section_content:
            _add_warning(
                warnings,
                "warning",
                "empty_section",
                "README contains a heading with no section content.",
                heading.group(2),
            )


def validate_readme(
    content: str,
    repository_files=None,
) -> dict:
    """
    Validate README links, installation commands,
    configuration references, and documentation structure.

    This function never modifies the original README.
    """

    content = content or ""

    repository_files = _normalize_repository_files(
        repository_files
    )

    warnings = []

    if not content.strip():
        _add_warning(
            warnings,
            "critical",
            "empty_readme",
            "README content is empty.",
            "",
        )
    else:
        _check_local_links(
            content,
            repository_files,
            warnings,
        )

        _check_installation_commands(
            content,
            repository_files,
            warnings,
        )

        _check_configuration_references(
            content,
            repository_files,
            warnings,
        )

        _check_empty_sections(
            content,
            warnings,
        )

    severity_counts = {
        "critical": 0,
        "warning": 0,
        "unverified": 0,
    }

    for warning in warnings:
        severity_counts[warning["severity"]] += 1

    return {
        "is_valid": (
            severity_counts["critical"] == 0
            and severity_counts["warning"] == 0
        ),
        "warning_count": len(warnings),
        "severity_counts": severity_counts,
        "warnings": warnings,
        "checked_files": len(repository_files),
    }
