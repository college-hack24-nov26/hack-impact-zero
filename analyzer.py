"""Evidence gathering and README composition.

Everything in this module is deterministic and based on evidence from the repository or the
pasted text. An AI model, when configured, only replaces the prose. The evidence-based sections
(features, structure, install and run commands, and so on) are still checked and
added here, so no supported information is lost.
"""
import ast
import json
import re
from urllib.parse import quote

from badges import tech_badges
from best_practices import recommended_sections
from config import IGNORED_DIRS, IGNORED_FILES, MAX_BADGES, MAX_EXCERPT_CHARS, TREE_MAX_DEPTH, TREE_MAX_LINES
from repo_fetch import fetch_repo_context

FEATURE_RULES = [
    (r"templates/|\.html\b|render_template\(|\breact\b|\bvue\.js\b|\bangular\b|\bnext\.js\b|web application|web interface|frontend", "Web interface"),
    (r"sqlalchemy|sqlite3|psycopg|pymysql|mongoose|prisma|database|\.db\b", "Database integration"),
    (r"login|logout|authentication|authorization|jwt|oauth|bcrypt|password_hash", "User authentication"),
    (r"upload_file|multipart/form-data|file upload|multer", "File upload handling"),
    (r"scikit-learn|sklearn|tensorflow|pytorch|torch\.|keras|xgboost|lightgbm", "Machine learning"),
    (r"pandas|numpy|dataframe|csv\.read|read_csv", "Data processing"),
    (r"celery|rq\.worker|apscheduler|background task|asyncio", "Background or asynchronous tasks"),
    (r"websocket|socket\.io|websockets", "Real-time communication"),
    (r"argparse|click\.command|typer\.typer|commander", "Command-line interface"),
    (r"stripe|razorpay|paypal", "Payment integration"),
]

FEATURE_NOTES = {
    "Web interface": "you can use it in a web browser.",
    "Database integration": "it stores and reads information in a database.",
    "User authentication": "users log in to use parts of it.",
    "File upload handling": "users can upload files to it.",
    "Machine learning": "it uses machine-learning models to make predictions.",
    "Data processing": "it reads and transforms data files.",
    "Background or asynchronous tasks": "it runs some work in the background so it stays responsive.",
    "Real-time communication": "it sends updates to users instantly.",
    "Command-line interface": "you run it from the terminal with commands.",
    "Payment integration": "it accepts payments through a payment provider.",
    "GitHub Actions workflows": "it checks the code automatically on GitHub.",
    "Docker container configuration": "it can run inside a Docker container.",
}

FRAMEWORK_RULES = [
    (r"\bflask\b", "Flask"),
    (r"\bdjango\b", "Django"),
    (r"\bfastapi\b", "FastAPI"),
    (r"\bstreamlit\b", "Streamlit"),
    (r"[\"']react[\"']\s*:|from\s+[\"']react[\"']|require\(\s*[\"']react[\"']\s*\)", "React"),
    (r"[\"']next[\"']\s*:|from\s+[\"']next[\"']|\bnext\.config\b", "Next.js"),
    (r"[\"']vue[\"']\s*:|from\s+[\"']vue[\"']", "Vue"),
    (r"@angular/core", "Angular"),
    (r"[\"']express[\"']\s*:|from\s+[\"']express[\"']|require\(\s*[\"']express[\"']\s*\)", "Express"),
    (r"\bfastify\b", "Fastify"),
    (r"spring-boot|springframework", "Spring Boot"),
    (r"laravel/framework|\blaravel\b", "Laravel"),
]

TEXT_LANGUAGE_RULES = [
    ("Python", r"\bPython\b"), ("JavaScript", r"\bJavaScript\b"), ("TypeScript", r"\bTypeScript\b"),
    ("Java", r"\bJava\b"), ("Go", r"\bGo\b"), ("Rust", r"\bRust\b"), ("HTML", r"\bHTML\b"),
    ("CSS", r"\bCSS\b"), ("PHP", r"\bPHP\b"), ("Ruby", r"\bRuby\b"),
]

ROOT_FILE_NOTES = {"app.py": "application entry point", "main.py": "application entry point",
                   "manage.py": "Django management script", "index.html": "main HTML page"}
FILE_NOTES = {
    "README.md": "project documentation", "LICENSE": "license terms",
    "requirements.txt": "Python dependencies", "pyproject.toml": "Python project configuration",
    "package.json": "Node.js dependencies and scripts", "Dockerfile": "container build instructions",
    "docker-compose.yml": "multi-container setup", "docker-compose.yaml": "multi-container setup",
    ".gitignore": "files excluded from Git", "Makefile": "build and task shortcuts",
    "Cargo.toml": "Rust package manifest", "go.mod": "Go module definition",
    "CONTRIBUTING.md": "contribution guidelines",
}
DIR_NOTES = {
    "templates": "HTML templates", "static": "CSS, JavaScript, and other static assets",
    ".github": "GitHub configuration", "workflows": "CI workflows", "src": "source code",
    "docs": "documentation", "scripts": "helper scripts", "assets": "images and media",
    "public": "publicly served files", "migrations": "database migrations",
    "components": "UI components",
}
EXTENSION_NOTES = {".css": "stylesheet", ".js": "JavaScript", ".html": "HTML page"}

LANGUAGE_COLORS = {"python": "3776AB", "javascript": "F7DF1E", "typescript": "3178C6", "java": "ED8B00",
                   "go": "00ADD8", "rust": "000000", "html": "E34F26", "css": "663399", "php": "777BB4", "ruby": "CC342D"}
LANGUAGE_LOGOS = {"python": "python", "javascript": "javascript", "typescript": "typescript", "java": "openjdk",
                  "go": "go", "rust": "rust", "html": "html5", "css": "css3", "php": "php", "ruby": "ruby"}

INSTALL_RULES = [
    ("requirements.txt", "pip install -r requirements.txt"),
    ("pyproject.toml", "pip install ."),
    ("Pipfile", "pipenv install"),
    ("package.json", "npm install"),
    ("Gemfile", "bundle install"),
    ("composer.json", "composer install"),
    ("go.mod", "go mod download"),
    ("Cargo.toml", "cargo build"),
    ("pom.xml", "mvn install"),
    ("build.gradle", "./gradlew build"),
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def human_join(items):
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def has_h1(text):
    return bool(re.search(r"(?m)^#\s+\S", text or ""))


def title_of(text):
    match = re.search(r"(?m)^#\s+(.+)$", text or "")
    return match.group(1).strip() if match else ""


def first_paragraph(text):
    for line in (text or "").splitlines():
        line = line.strip()
        if len(line) >= 30 and not re.match(r"^(#|!|\[|<|```|\||-|\*|>)", line):
            return line
    return ""


def sentence(text):
    text = (text or "").strip()
    if not text:
        return ""
    return text if text[-1] in ".!?" else text + "."


def _root(paths):
    return {p for p in paths if "/" not in p}


def _visible(path):
    parts = path.split("/")
    return not any(part in IGNORED_DIRS for part in parts) and parts[-1] not in IGNORED_FILES and not is_test_path(path)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_features(text, paths, file_map):
    corpus = (text + "\n" + "\n".join(paths) + "\n" + "\n".join(file_map.values())).lower()
    features = [label for pattern, label in FEATURE_RULES if re.search(pattern, corpus, re.I)]
    if any(p.lower().startswith(".github/workflows/") for p in paths):
        features.append("GitHub Actions workflows")
    if any(p.rsplit("/", 1)[-1].lower() in ("dockerfile", "docker-compose.yml", "docker-compose.yaml") for p in paths):
        features.append("Docker container configuration")
    return list(dict.fromkeys(features))


def detect_frameworks(file_map, text=""):
    corpus = "\n".join([text or ""] + list(file_map.values()))
    found = []
    for pattern, name in FRAMEWORK_RULES:
        if re.search(pattern, corpus, re.I) and name not in found:
            found.append(name)
    return found


def languages_from_text(text):
    # Case-sensitive, so ordinary words such as "go" or "rust" are not read as languages.
    return [name for name, pattern in TEXT_LANGUAGE_RULES if re.search(pattern, text)]


def is_test_path(path):
    lower = path.lower()
    name = lower.rsplit("/", 1)[-1]
    return (lower.startswith(("tests/", "test/", "__tests__/")) or name.startswith("test_")
            or name.endswith(("_test.py", "_test.go", ".test.js", ".spec.js", ".test.ts", ".spec.ts")))


def detect_install_commands(paths):
    root = _root(paths)
    return [command for name, command in INSTALL_RULES if name in root]


def _package_scripts(file_map):
    try:
        data = json.loads(file_map.get("package.json", "") or "{}")
    except ValueError:
        return {}
    scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
    return scripts if isinstance(scripts, dict) else {}


def detect_run_command(paths, file_map):
    """Return (command, (host, port) or None). Only commands the repository clearly supports."""
    root = _root(paths)
    if _package_scripts(file_map).get("start"):
        return "npm start", None
    for name in ("app.py", "main.py", "run.py", "server.py"):
        if name in root:
            content = file_map.get(name, "")
            if "__main__" in content or "app.run(" in content:
                port = re.search(r"port\s*=\s*(\d{2,5})", content)
                host = re.search(r"host\s*=\s*[\"']([^\"']+)[\"']", content)
                endpoint = ((host.group(1) if host else "127.0.0.1"), port.group(1)) if port else None
                return f"python {name}", endpoint
    if "manage.py" in root:
        return "python manage.py runserver", ("127.0.0.1", "8000")
    for name in ("server.js", "index.js"):
        if name in root and "listen(" in file_map.get(name, ""):
            return f"node {name}", None
    if "main.go" in root:
        return "go run .", None
    if "Cargo.toml" in root and "src/main.rs" in paths:
        return "cargo run", None
    return None, None


def python_summary(content):
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return "", []
    doc = (ast.get_docstring(tree) or "").strip()
    first = doc.splitlines()[0].strip() if doc else ""
    names = [n.name for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_")]
    return first, names[:8]


def dependency_list(file_map):
    deps = []
    for line in file_map.get("requirements.txt", "").splitlines():
        line = line.split("#")[0].strip()
        if line and not line.startswith("-"):
            deps.append(line)
    try:
        package = json.loads(file_map.get("package.json", "") or "{}")
    except ValueError:
        package = {}
    if isinstance(package, dict):
        for name, version in (package.get("dependencies") or {}).items():
            deps.append(f"{name} {version}")
    return deps[:20]


def build_tree_lines(root_name, paths):
    tree = {}
    for raw in paths:
        parts = [p for p in raw.split("/") if p]
        if not parts or any(p in IGNORED_DIRS for p in parts) or parts[-1] in IGNORED_FILES or is_test_path(raw):
            continue
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None  # None marks a file; a dict marks a directory

    rows = []

    def note_for(name, is_dir, depth):
        if is_dir:
            return DIR_NOTES.get(name, "")
        if depth == 0 and name in ROOT_FILE_NOTES:
            return ROOT_FILE_NOTES[name]
        if name in FILE_NOTES:
            return FILE_NOTES[name]
        for extension, note in EXTENSION_NOTES.items():
            if name.endswith(extension):
                return note
        return ""

    def walk(node, prefix, depth):
        items = sorted(node.items(), key=lambda kv: (kv[1] is None, kv[0].lower()))
        for index, (name, child) in enumerate(items):
            if len(rows) >= TREE_MAX_LINES:
                rows.append((prefix + "└── ", "…", ""))
                return False
            is_last = index == len(items) - 1
            is_dir = child is not None
            label = name + ("/" if is_dir else "")
            rows.append((prefix + ("└── " if is_last else "├── "), label, note_for(name, is_dir, depth)))
            if is_dir and child:
                child_prefix = prefix + ("    " if is_last else "│   ")
                if depth + 1 >= TREE_MAX_DEPTH:
                    rows.append((child_prefix + "└── ", "…", ""))
                elif walk(child, child_prefix, depth + 1) is False:
                    return False
        return True

    walk(tree, "", 0)
    width = max((len(prefix) + len(label) for prefix, label, _ in rows), default=0)
    lines = [f"{root_name}/"]
    for prefix, label, note in rows:
        text = prefix + label
        if note:
            text = text.ljust(width + 2) + "# " + note
        lines.append(text.rstrip())
    return lines


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

def build_badges(context, languages, frameworks, features, license_name, paths):
    """At most MAX_BADGES badges in the markdown-badges style: project stats first, then technologies."""
    badges = []
    if context:
        owner, repo = context["owner"], context["repo"]
        base = "https://img.shields.io/github"
        style = "style=for-the-badge"
        workflows = [p for p in paths if p.lower().startswith(".github/workflows/") and p.lower().endswith((".yml", ".yaml"))]
        stats = [
            ("Stars", f"{base}/stars/{owner}/{repo}?{style}&logo=github&color=yellow"),
            ("Forks", f"{base}/forks/{owner}/{repo}?{style}&logo=github"),
            ("License", f"{base}/license/{owner}/{repo}?{style}") if license_name else None,
            ("Latest release", f"{base}/v/release/{owner}/{repo}?{style}") if context.get("release") else None,
            ("Last commit", f"{base}/last-commit/{owner}/{repo}?{style}&logo=git"),
        ]
        badges += [b for b in stats if b][:3]
    elif license_name:
        license_slug = re.sub(r"[^A-Za-z0-9.-]+", "-", license_name)
        badges.append(("License", f"https://img.shields.io/badge/License-{license_slug}-blue?style=for-the-badge"))
    badges += tech_badges(languages, frameworks, features, MAX_BADGES - len(badges))
    return badges[:MAX_BADGES]


LINKED_BADGE = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)")
IMAGE_BADGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def _is_unwanted_badge(text):
    """Shields.io badges are regenerated here, and any 'verified' or 'fixreadme' badge is dropped."""
    return bool(re.search(r"img\.shields\.io|verified|fixreadme", text, re.I))


def strip_badges(text):
    out = []
    for line in (text or "").splitlines():
        cleaned = LINKED_BADGE.sub(lambda m: "" if _is_unwanted_badge(m.group(0)) else m.group(0), line)
        cleaned = IMAGE_BADGE.sub(lambda m: "" if _is_unwanted_badge(m.group(0)) else m.group(0), cleaned)
        if line.strip() and not cleaned.strip():
            continue
        out.append(cleaned.rstrip() if cleaned != line else line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


UNWANTED_HEADING = re.compile(
    r"(?i)^(?:\W*)(?:api(?:\s+(?:endpoints?|routes?|reference|docs|documentation))?|endpoints?|routes?|"
    r"(?:running\s+(?:the\s+)?)?tests?|testing|test\s+suite|unit\s+tests?|table\s+of\s+contents|contents|toc)\s*$"
)


def remove_unwanted_sections(text):
    """Drop 'API Endpoints' and 'Testing' style sections, including everything under them."""
    out, skip_level, in_fence = [], None, False
    for line in (text or "").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if skip_level is None:
                out.append(line)
            continue
        heading = None if in_fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            level = len(heading.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and level >= 2 and UNWANTED_HEADING.match(heading.group(2)):
                skip_level = level
                continue
        if skip_level is None:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", remove_anchor_lists("\n".join(out)))


ANCHOR_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\[[^\]]+\]\(#[^)]*\)\s*$")


def remove_anchor_lists(text):
    """Drop lists made only of in-page links (a table of contents without a heading)."""
    lines, out, run, in_fence = text.splitlines(), [], [], False

    def flush():
        if len(run) < 3:
            out.extend(run)
        run.clear()

    for line in lines:
        if line.lstrip().startswith("```"):
            flush()
            in_fence = not in_fence
            out.append(line)
        elif not in_fence and ANCHOR_ITEM.match(line):
            run.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def place_badges(body, badges):
    if not badges:
        return body
    row = " ".join(f"![{label}]({url})" for label, url in badges)
    title = re.search(r"(?m)^#\s+\S.*$", body)
    head, rest = body[:title.end()], body[title.end():].lstrip("\n")
    return f"{head}\n\n{row}\n\n{rest}".rstrip() + "\n"


# ---------------------------------------------------------------------------
# Section writers
# ---------------------------------------------------------------------------

def _has_heading(body, pattern):
    return bool(re.search(rf"(?im)^#{{1,6}}\s+(?:{pattern})\b", body))


CLOSING_HEADING = re.compile(
    r"(?im)^#{1,6}\s+(?:contributing|contributors|acknowledg\w*|credits|authors?|contact|support|changelog|roadmap|license|licence)\b"
)


def _insert_before_closing(body, block):
    block = block.rstrip() + "\n"
    match = CLOSING_HEADING.search(body)
    if match:
        return body[:match.start()].rstrip() + "\n\n" + block + "\n" + body[match.start():]
    return body.rstrip() + "\n\n" + block


def _code(commands, language="bash"):
    return f"```{language}\n" + "\n".join(commands) + "\n```\n"


def features_md(ev):
    lines = ["## Features", ""]
    for feature in ev["features"]:
        note = FEATURE_NOTES.get(feature)
        lines.append(f"- **{feature}**" + (f": {note}" if note else ""))
    return "\n".join(lines) + "\n"


def technologies_md(ev):
    lines = ["## Technologies", ""]
    for lang in ev["tech_languages"]:
        pct = ev["percentages"].get(lang)
        lines.append(f"- **{lang}** ({pct}% of the code)" if pct is not None else f"- **{lang}**")
    for framework in ev["frameworks"]:
        lines.append(f"- {framework}")
    return "\n".join(lines) + "\n"


def how_it_works_md(ev):
    lines = ["## How It Works", "", "The main modules in this project:", ""]
    for path, summary, names in ev["module_notes"]:
        description = sentence(summary) if summary else (f"Defines {human_join(names[:5])}." if names else "")
        lines.append(f"- `{path}`: {description}")
    return "\n".join(lines) + "\n"


def structure_md(ev):
    return "## Project Structure\n\n```text\n" + "\n".join(ev["tree_lines"]) + "\n```\n"


def dependencies_md(ev):
    lines = ["## Dependencies", ""]
    lines += [f"- `{dep}`" for dep in ev["dependencies"]]
    return "\n".join(lines) + "\n"


def quick_start_md(ev):
    """Numbered, copy-friendly steps. Each step is a short title and one code block."""
    steps = []
    if ev["repo_url"]:
        steps.append(("Download the project", [f"git clone {ev['repo_url']}.git", f"cd {ev['project_name']}"]))
    if ev["install_commands"]:
        steps.append(("Install what it needs", ev["install_commands"]))
    if ev["run_command"]:
        steps.append(("Start the project", [ev["run_command"]]))
    if not steps:
        return ""
    lines = ["## Quick Start", "", "Follow these steps. Every command has a Copy button.", ""]
    for number, (title, commands) in enumerate(steps, 1):
        lines += [f"**Step {number}: {title}**", "", _code(commands).rstrip(), ""]
    if ev["endpoint"]:
        host, port = ev["endpoint"]
        lines += [f"When it is running, open **http://{host}:{port}** in your browser.", ""]
    return "\n".join(lines).rstrip() + "\n"


PREREQUISITE_RULES = [
    ("requirements.txt", "Python 3 and pip"), ("pyproject.toml", "Python 3 and pip"), ("Pipfile", "Python 3 and pipenv"),
    ("package.json", "Node.js and npm"), ("go.mod", "Go"), ("Cargo.toml", "Rust and Cargo"),
    ("pom.xml", "a Java JDK and Maven"), ("build.gradle", "a Java JDK"), ("Gemfile", "Ruby and Bundler"),
    ("composer.json", "PHP and Composer"), ("Dockerfile", "Docker (optional, for the container setup)"),
]


def prerequisites_md(ev):
    root = _root(ev["paths"])
    needs = list(dict.fromkeys(label for name, label in PREREQUISITE_RULES if name in root))
    if ev["repo_url"]:
        needs.insert(0, "Git")
    if not needs:
        return ""
    return "## Prerequisites\n\nInstall these first:\n\n" + "\n".join(f"- {item}" for item in needs) + "\n"


def contributing_md(ev):
    if "CONTRIBUTING.md" in _root(ev["paths"]):
        return "## Contributing\n\nSee [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute, report issues, and submit changes.\n"
    if ev["repo_url"] and "contributing" in ev["recommended"]:
        return ("## Contributing\n\nContributions are welcome.\n\n"
                "1. Fork the repository.\n"
                "2. Create a branch for your change.\n"
                "3. Commit your work with a clear message.\n"
                "4. Open a pull request and describe what you changed.\n")
    return ""


def support_md(ev):
    if ev["repo_url"] and "support" in ev["recommended"]:
        return ("## Support\n\nIf this project helps you, give it a star on "
                f"[GitHub]({ev['repo_url']}) and share it with others. "
                f"Found a problem? [Open an issue]({ev['repo_url']}/issues).\n")
    return ""


def license_md(ev):
    name, has_file = ev["license_name"], ev["has_license_file"]
    if name and has_file:
        text = f"This project is licensed under the **{name}** license. See the [LICENSE](LICENSE) file for details."
    elif name:
        text = f"This project is licensed under the **{name}** license."
    elif has_file:
        text = "See the [LICENSE](LICENSE) file for license terms."
    else:
        return ""
    return "## License\n\n" + text + "\n"


def section_blocks(ev):
    """(name, heading pattern, markdown) for every section the project supports, in display order."""
    blocks = []

    def add(name, pattern, markdown):
        if markdown:
            blocks.append((name, pattern, markdown))

    add("Features", r"features|key features|highlights", features_md(ev) if ev["features"] else "")
    add("Technologies", r"technologies|tech stack|built with|stack",
        technologies_md(ev) if ev["tech_languages"] or ev["frameworks"] else "")
    add("How It Works", r"how it works|how this works|architecture|internals", how_it_works_md(ev) if ev["module_notes"] else "")
    add("Project Structure", r"(?:project |file |directory |source )?(?:structure|layout|tree)",
        structure_md(ev) if ev["tree_lines"] else "")
    add("Dependencies", r"dependencies|requirements", dependencies_md(ev) if ev["dependencies"] else "")
    add("Prerequisites", r"prerequisites|requirements|before you begin", prerequisites_md(ev) if ev["repo_url"] else "")
    add("Quick Start", r"quick ?start|getting started|installation|install\w*|setup|usage|how to use|prerequisites",
        quick_start_md(ev))
    add("Contributing", r"contributing|contribute", contributing_md(ev))
    add("Support", r"support|sponsor\w*|help", support_md(ev))
    add("Repository", r"repository|repo", f"## Repository\n\n{ev['repo_url']}\n" if ev["repo_url"] else "")
    add("License", r"license|licence", license_md(ev))
    return blocks


# ---------------------------------------------------------------------------
# Evidence and composition
# ---------------------------------------------------------------------------

def _evidence_summary(ev):
    parts = []
    if ev["tech_languages"]:
        text = f"Most of the code is written in {ev['tech_languages'][0]}"
        if ev["frameworks"]:
            text += f", and it uses {human_join(ev['frameworks'])}"
        parts.append(sentence(text))
    if ev["features"]:
        parts.append(sentence("Its main capabilities include " + human_join(ev["features"][:5])))
    if ev["file_count"]:
        parts.append(sentence(f"The repository contains {ev['file_count']} files across {ev['folder_count']} folders"))
    return " ".join(parts)


def _excerpts(file_map):
    out = []
    for path, content in file_map.items():
        if is_test_path(path) or not content.strip() or path.lower().endswith(("lock.json", ".lock")):
            continue
        out.append((path, content[:MAX_EXCERPT_CHARS]))
        if len(out) >= 5:
            break
    return out


def gather_evidence(context=None, pasted_text=""):
    source = (pasted_text or "").strip()
    repo_readme, repo_url, metadata_desc, license_name = "", "", "", None
    file_map, paths, languages = {}, [], {}
    if context:
        repo_url = context["url"]
        repo_readme = context.get("readme") or ""
        file_map = dict(context.get("files") or [])
        paths = list(context.get("paths") or [])
        languages = dict(context.get("languages") or {})
        metadata = context.get("metadata") or {}
        metadata_desc = (metadata.get("description") or "").strip()
        spdx = (metadata.get("license") or {}).get("spdx_id")
        license_name = spdx if spdx and spdx != "NOASSERTION" else None
        project_name = context["repo"]
    else:
        project_name = title_of(source) or "Project Name"

    analysis_text = "\n\n".join(part for part in (repo_readme, source) if part)
    if not license_name and re.search(r"\bMIT License\b", analysis_text):
        license_name = "MIT"
    root = _root(paths)
    has_license_file = any(name.upper().startswith(("LICENSE", "LICENCE")) for name in root)

    tech_languages = list(languages) if languages else languages_from_text(analysis_text)
    total = sum(languages.values()) if languages else 0
    percentages = {k: round(v * 100 / total, 1) for k, v in languages.items()} if total else {}
    frameworks = detect_frameworks(file_map, analysis_text)
    features = detect_features(analysis_text, paths, file_map)

    install_commands = detect_install_commands(paths) if context else []
    run_command, endpoint = detect_run_command(paths, file_map) if context else (None, None)

    module_notes = []
    for path, content in file_map.items():
        if path.endswith(".py") and not is_test_path(path):
            summary, names = python_summary(content)
            if summary or names:
                module_notes.append((path, summary, names))
    module_notes = module_notes[:8]

    visible = [p for p in paths if _visible(p)]
    folders = {p.rsplit("/", 1)[0] for p in visible if "/" in p}

    ev = {
        "project_name": project_name,
        "repo_url": repo_url,
        "source": source,
        "repo_readme": repo_readme,
        "description": metadata_desc or first_paragraph(repo_readme) or first_paragraph(source),
        "license_name": license_name,
        "has_license_file": has_license_file,
        "tech_languages": tech_languages,
        "percentages": percentages,
        "frameworks": frameworks,
        "features": features,
        "install_commands": install_commands,
        "run_command": run_command,
        "endpoint": endpoint,
        "module_notes": module_notes,
        "dependencies": dependency_list(file_map),
        "tree_lines": build_tree_lines(project_name, paths) if paths else [],
        "file_count": len(visible),
        "folder_count": len(folders),
        "paths": paths,
        "file_map": file_map,
        "excerpts": _excerpts(file_map),
        "languages": languages,
        "frameworks_text": analysis_text,
    }
    ev["recommended"] = recommended_sections()
    ev["evidence_summary"] = _evidence_summary(ev)
    ev["badges"] = build_badges(context, tech_languages, frameworks, features, license_name, paths)
    return ev


# Small models sometimes copy their instructions into the answer. These lines are never README content.
LEAK_LINE = re.compile(
    r"(?i)do not add (?:any )?shields\.io badges|do not (?:add|write|include) (?:a )?(?:table of contents|badges)|"
    r"do not write sections? about|every command must be inside|keep paragraphs short|"
    r"do not invent facts|if something is unknown, leave it out|write these sections|sections, in this order|"
    r"^\W*(?:\d+\.\s*)?title \(h1\)|^\W*\d+\.\s*##\s+[\w ]+:|these instructions are private|"
    r"never repeat, quote, or mention")
LEAK_HEADER = re.compile(r"(?i)^\W*(?:rules|instructions|guidelines|requirements for the readme)\W*:?\W*$")


def strip_prompt_leaks(text):
    lines, out, in_fence = (text or "").splitlines(), [], False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
        elif LEAK_LINE.search(line):
            continue
        elif LEAK_HEADER.match(line) and any(LEAK_LINE.search(n) for n in lines[index + 1:index + 4]):
            continue
        else:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def clean_ai_markdown(text):
    text = strip_prompt_leaks((text or "").strip())
    fence = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", text, re.S)
    if fence:
        text = fence.group(1).strip()
    match = re.search(r"(?m)^#\s+\S", text)
    if match:
        text = text[match.start():]
    return text.strip()


def template_base(ev):
    name = ev["project_name"]
    if has_h1(ev["source"]):
        return ev["source"]
    if ev["repo_readme"]:
        base = ev["repo_readme"].strip()
        if ev["source"]:
            base = _insert_after_title_text(base, f"## Project Overview\n\n{ev['source']}\n")
        return base
    if ev["source"]:
        parts = [f"# {name}", "", "## Overview", "", ev["source"]]
        if ev["evidence_summary"]:
            parts += ["", ev["evidence_summary"]]
        return "\n".join(parts) + "\n"
    overview = " ".join(p for p in (sentence(ev["description"]), ev["evidence_summary"]) if p)
    if overview:
        return f"# {name}\n\n## Overview\n\n{overview}\n"
    return f"# {name}\n"


def _insert_after_title_text(text, block):
    match = re.search(r"(?m)^#\s+\S.*$", text)
    if not match:
        return block + "\n" + text
    return text[:match.end()] + "\n\n" + block.rstrip() + "\n\n" + text[match.end():].lstrip("\n")


def compose_readme(ev, ai_markdown=None):
    """Return (readme_markdown, analysis). ai_markdown is used only when it is a real README."""
    cleaned = clean_ai_markdown(ai_markdown) if ai_markdown else ""
    ai_used = len(cleaned) >= 200 and has_h1(cleaned)
    base = cleaned if ai_used else template_base(ev)

    body = remove_unwanted_sections(strip_badges(base)).strip()
    if not has_h1(body):
        body = f"# {ev['project_name']}\n\n" + body
    body = place_badges(body, ev["badges"])

    added = []
    blocks = []
    for name, pattern, markdown in section_blocks(ev):
        if not _has_heading(body, pattern):
            blocks.append(markdown)
            added.append(name)
    if blocks:
        body = _insert_before_closing(body, "\n".join(blocks))

    analysis = {
        "project": ev["project_name"],
        "languages": ev["tech_languages"],
        "frameworks": ev["frameworks"],
        "features": ev["features"],
        "badge_count": len(ev["badges"]),
        "file_count": ev["file_count"],
        "folder_count": ev["folder_count"],
        "badges": [{"label": label, "url": url} for label, url in ev["badges"]],
        "sections_added": added,
        "ai_used": ai_used,
        "source": ("GitHub repository and supplied text" if ev["repo_url"] and ev["source"]
                   else ("GitHub repository" if ev["repo_url"] else "pasted text")),
    }
    return body.strip() + "\n", analysis


def build_readme(repo_url="", pasted_text="", ai_markdown=None):
    """Convenience wrapper: fetch the repository if a URL is given, then compose."""
    context = fetch_repo_context(repo_url) if repo_url else None
    return compose_readme(gather_evidence(context, pasted_text), ai_markdown)
