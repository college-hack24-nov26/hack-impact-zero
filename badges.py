"""Badge catalog in the style of https://github.com/Ileriayo/markdown-badges.

Each entry is  key -> (label, hex colour, shields.io logo slug, logo colour).
Badges are built as static shields.io "for-the-badge" images, the same format that
markdown-badges uses, for example:

    ![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

The catalog was written from the markdown-badges style guide. It makes no network calls.
"""
import re
from urllib.parse import quote

STYLE = "for-the-badge"

# key (lower case) -> (label, colour, logo, logoColor)
CATALOG = {
    # Languages
    "python": ("python", "3670A0", "python", "ffdd54"),
    "javascript": ("javascript", "323330", "javascript", "F7DF1E"),
    "typescript": ("typescript", "007ACC", "typescript", "white"),
    "java": ("java", "ED8B00", "openjdk", "white"),
    "go": ("go", "00ADD8", "go", "white"),
    "rust": ("rust", "000000", "rust", "white"),
    "c": ("c", "00599C", "c", "white"),
    "c++": ("c++", "00599C", "c%2B%2B", "white"),
    "c#": ("c%23", "239120", "c-sharp", "white"),
    "php": ("php", "777BB4", "php", "white"),
    "ruby": ("ruby", "CC342D", "ruby", "white"),
    "kotlin": ("kotlin", "0095D5", "kotlin", "white"),
    "swift": ("swift", "F54A2A", "swift", "white"),
    "dart": ("dart", "0175C2", "dart", "white"),
    "html": ("html5", "E34F26", "html5", "white"),
    "css": ("css3", "1572B6", "css3", "white"),
    "shell": ("shell", "121011", "gnu-bash", "white"),
    "scala": ("scala", "DC322F", "scala", "white"),
    "r": ("r", "276DC3", "r", "white"),
    "lua": ("lua", "2C2D72", "lua", "white"),
    "jupyter notebook": ("jupyter", "F37626", "jupyter", "white"),
    # Frameworks and libraries
    "flask": ("flask", "000", "flask", "white"),
    "django": ("django", "092E20", "django", "white"),
    "fastapi": ("fastapi", "005571", "fastapi", "white"),
    "streamlit": ("streamlit", "FF4B4B", "streamlit", "white"),
    "react": ("react", "20232A", "react", "61DAFB"),
    "next.js": ("next.js", "000000", "next.js", "white"),
    "vue": ("vue.js", "35495E", "vuedotjs", "4FC08D"),
    "angular": ("angular", "DD0031", "angular", "white"),
    "express": ("express.js", "404D59", "express", "white"),
    "fastify": ("fastify", "000000", "fastify", "white"),
    "spring boot": ("spring", "6DB33F", "spring", "white"),
    "laravel": ("laravel", "FF2D20", "laravel", "white"),
    "node.js": ("node.js", "6DA55F", "node.js", "white"),
    "tailwind css": ("tailwind", "38B2AC", "tailwind-css", "white"),
    "pytorch": ("pytorch", "EE4C2C", "pytorch", "white"),
    "tensorflow": ("tensorflow", "FF6F00", "tensorflow", "white"),
    "scikit-learn": ("scikit-learn", "F7931E", "scikit-learn", "white"),
    "pandas": ("pandas", "150458", "pandas", "white"),
    "numpy": ("numpy", "013243", "numpy", "white"),
    # Tools and platforms
    "docker": ("docker", "2CA5E0", "docker", "white"),
    "github actions": ("github actions", "2088FF", "github-actions", "white"),
    "ollama": ("ollama", "000000", "ollama", "white"),
    "openai": ("openai", "412991", "openai", "white"),
    "anthropic": ("anthropic", "191919", "anthropic", "white"),
    "sqlite": ("sqlite", "07405E", "sqlite", "white"),
    "postgresql": ("postgres", "316192", "postgresql", "white"),
    "mysql": ("mysql", "005C84", "mysql", "white"),
    "mongodb": ("mongodb", "4ea94b", "mongodb", "white"),
    "redis": ("redis", "%23DD0031", "redis", "white"),
    "git": ("git", "F05033", "git", "white"),
    "markdown": ("markdown", "000000", "markdown", "white"),
}

# Features -> a badge key, so a feature can also be shown as a badge.
FEATURE_BADGES = {
    "GitHub Actions workflows": "github actions",
    "Docker container configuration": "docker",
}


def make_badge(key, label=None):
    """Return (label, url) for a catalog key, or None if the key is unknown."""
    entry = CATALOG.get((key or "").strip().lower())
    if not entry:
        return None
    text, colour, logo, logo_colour = entry
    colour = colour.lstrip("#")
    url = (f"https://img.shields.io/badge/{quote(text, safe='%.+-')}-{colour}"
           f"?style={STYLE}&logo={logo}&logoColor={logo_colour}")
    return (label or key.title(), url)


ALT_NAMES = {
    "html": "HTML", "css": "CSS", "php": "PHP", "c": "C", "r": "R", "c++": "C++", "c#": "C#",
    "javascript": "JavaScript", "typescript": "TypeScript", "github actions": "GitHub Actions",
    "next.js": "Next.js", "node.js": "Node.js", "fastapi": "FastAPI", "pytorch": "PyTorch",
    "tensorflow": "TensorFlow", "scikit-learn": "scikit-learn", "openai": "OpenAI", "sqlite": "SQLite",
    "postgresql": "PostgreSQL", "mysql": "MySQL", "mongodb": "MongoDB", "vue": "Vue.js",
    "express": "Express.js", "laravel": "Laravel", "tailwind css": "Tailwind CSS",
    "jupyter notebook": "Jupyter Notebook", "numpy": "NumPy", "pandas": "pandas",
}


def alt_name(key):
    return ALT_NAMES.get(key, key.title())


def tech_badges(languages, frameworks, features, limit):
    """Badges for languages, then frameworks, then tooling the project actually uses."""
    keys, seen = [], set()

    def add(key):
        key = (key or "").strip().lower()
        if key in CATALOG and key not in seen:
            seen.add(key)
            keys.append(key)

    for lang in languages[:3]:
        add(lang)
    for framework in frameworks:
        add(framework)
    for feature in features:
        add(FEATURE_BADGES.get(feature))
    return [make_badge(key, alt_name(key)) for key in keys[:max(limit, 0)]]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
