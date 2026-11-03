from collections import Counter
from pathlib import PurePosixPath


LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".html": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
}

IMPORTANT_FILES = {
    "readme.md",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "dockerfile",
    "makefile",
    "license",
    ".gitignore",
}


def analyze_repository_structure(tree_result: dict) -> dict:
    """Analyze repository paths and identify project technologies."""

    files = tree_result.get("files", [])

    extensions = Counter()
    languages = Counter()
    important_files = []
    directories = set()

    for item in files:
        path = item.get("path", "")
        if not path:
            continue

        parsed_path = PurePosixPath(path)
        filename = parsed_path.name
        extension = parsed_path.suffix.lower()

        if item.get("type") == "tree":
            directories.add(path)
            continue

        if extension:
            extensions[extension] += 1

        language = LANGUAGE_EXTENSIONS.get(extension)
        if language:
            languages[language] += 1

        if filename.lower() in IMPORTANT_FILES:
            important_files.append(path)

        for parent in parsed_path.parents:
            if str(parent) != ".":
                directories.add(str(parent))

    return {
        "total_files": sum(
            1 for item in files if item.get("type") == "blob"
        ),
        "total_directories": len(directories),
        "languages": dict(languages.most_common()),
        "extensions": dict(extensions.most_common()),
        "important_files": sorted(important_files),
        "truncated": tree_result.get("truncated", False),
    }