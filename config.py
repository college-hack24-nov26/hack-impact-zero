"""Central settings for Fix README."""
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def load_dotenv(path=None):
    """Read KEY=VALUE lines from .env into the environment (existing variables win).

    The .env file stays on your computer and is listed in .gitignore, so a GitHub token kept
    there is never uploaded and never sent to the browser.
    """
    path = Path(path) if path else BASE_DIR / ".env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv()

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{20,255}$")


def clean_token(value):
    """Return a GitHub token that is safe to put in a header, or raise ValueError.

    The error message never repeats the token.
    """
    token = str(value or "").strip()
    if not token:
        return ""
    if not TOKEN_PATTERN.match(token):
        raise ValueError("That does not look like a GitHub token. Paste only the token, with no spaces or quotes.")
    return token


def server_github_token():
    """Token from the GITHUB_TOKEN (or GH_TOKEN) environment variable or the .env file."""
    try:
        return clean_token(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    except ValueError:
        return ""


GITHUB_API = "https://api.github.com"
USER_AGENT = "FixREADME-Project-Analyzer/3.0"
MAX_SOURCE_FILES = 18
MAX_FILE_BYTES = 180_000
MAX_EXCERPT_CHARS = 1_500
MAX_INPUT_CHARS = 60_000          # pasted text is truncated beyond this
MAX_REQUEST_BYTES = 1_000_000     # larger requests are rejected with HTTP 413
MAX_BADGES = 8
TREE_MAX_DEPTH = 3
TREE_MAX_LINES = 60

AI_TIMEOUT_SECONDS = 150
AI_MAX_TOKENS = 3000

# Small by default so the first download is quick. Override with FIXREADME_OLLAMA_MODEL.
DEFAULT_OLLAMA_MODEL = os.environ.get("FIXREADME_OLLAMA_MODEL", "qwen2.5:0.5b")
_ollama = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").strip()
if not _ollama.startswith(("http://", "https://")):
    _ollama = "http://" + _ollama
OLLAMA_HOST = _ollama.rstrip("/")
OLLAMA_LOG_PATH = BASE_DIR / "ollama-serve.log"

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".idea", ".vscode",
    "dist", "build", "target", ".pytest_cache", ".mypy_cache", ".next", "coverage",
}
IGNORED_FILES = {".DS_Store", "Thumbs.db"}

PRIORITY_NAMES = (
    "requirements.txt", "pyproject.toml", "Pipfile", "package.json", "Cargo.toml",
    "go.mod", "pom.xml", "build.gradle", "composer.json", "Gemfile", "Dockerfile",
    "docker-compose.yml", "docker-compose.yaml", "Makefile",
)

# Learner settings used by learner.py
LEARN_ENABLED = False      # False = no background collection from GitHub
LEARN_TARGET = 50          # maximum repositories to inspect (only used if enabled)
LEARN_MILESTONE = 25       # write feature_profile.json after this many
LEARN_STEP = 10            # refresh findings every this many repositories
LEARN_RESERVE = 20         # GitHub reads kept free for README requests