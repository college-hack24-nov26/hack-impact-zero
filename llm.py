def _line_key(line):
    """Normalise a line so a bullet, number, heading mark, or bold marker does not change the match."""
    text = line.strip()
    text = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", text)
    text = re.sub(r"^#{1,6}\s+", "", text)
    text = re.sub(r"[*_`]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def instruction_lines(prompt):
    """Lines of the writing instructions only (the project facts are not used for matching)."""
    start = prompt.find("Write these sections")
    if start < 0:
        return set()
    return {key for key in (_line_key(l) for l in prompt[start:].splitlines()) if len(key) >= 4}


def strip_prompt_echo(markdown, prompt):
    """Remove lines the model copied from the writing instructions, such as the numbered section list.

    A long line (25+ characters) is removed when it matches an instruction line. A short line such
    as "Rules:" is removed only when it sits next to an removed line, so a real heading is kept.
    """
    banned = instruction_lines(prompt)
    lines = (markdown or "").splitlines()
    keys = [_line_key(line) for line in lines]
    drop = [len(key) >= 25 and key in banned for key in keys]
    changed = True
    while changed:
        changed = False
        for index, key in enumerate(keys):
            if drop[index] or not key or key not in banned:
                continue
            before = next((j for j in range(index - 1, -1, -1) if keys[j]), None)
            after = next((j for j in range(index + 1, len(keys)) if keys[j]), None)
            if any(j is not None and drop[j] for j in (before, after)):
                drop[index] = True
                changed = True
    return "\n".join(line for line, gone in zip(lines, drop) if not gone)


"""AI providers used for writing README prose.

Three providers are supported:
  ollama     - local Ollama server (default, no key needed)
  openai     - any OpenAI-compatible API (OpenAI, OpenRouter, Groq, LM Studio, ...)
  anthropic  - Anthropic Messages API

API keys are passed in per request and are never stored or logged on the server.
"""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from config import AI_MAX_TOKENS, AI_TIMEOUT_SECONDS, DEFAULT_OLLAMA_MODEL, OLLAMA_HOST

PROVIDERS = {
    "ollama": {"label": "Local Ollama (default)", "short": "Ollama",
               "base": OLLAMA_HOST + "/v1", "model": DEFAULT_OLLAMA_MODEL, "key": False},
    "openai": {"label": "OpenAI or compatible API", "short": "OpenAI",
               "base": "https://api.openai.com/v1", "model": "gpt-4o-mini", "key": True},
    "anthropic": {"label": "Anthropic Claude", "short": "Anthropic",
                  "base": "https://api.anthropic.com", "model": "claude-haiku-5-5", "key": True},
}
OPENAI_DEFAULT_BASE = PROVIDERS["openai"]["base"]


class AIError(Exception):
    """A user-facing AI problem. The message never contains the API key."""


def public_providers():
    return {name: {k: v for k, v in spec.items()} for name, spec in PROVIDERS.items()}


def resolve_settings(ai=None):
    ai = ai if isinstance(ai, dict) else {}
    provider = ai.get("provider") if ai.get("provider") in PROVIDERS else "ollama"
    spec = PROVIDERS[provider]
    base = str(ai.get("base_url") or "").strip()[:300].rstrip("/") or spec["base"]
    if not base.startswith(("http://", "https://")):
        raise AIError("The base URL must start with http:// or https://.")
    key = str(ai.get("api_key") or "").strip()[:300]
    model = str(ai.get("model") or "").strip()[:120] or spec["model"]

    if provider == "anthropic" and not key:
        raise AIError("Add an Anthropic API key in Settings to use Claude.")
    if provider == "openai" and base == OPENAI_DEFAULT_BASE and not key:
        raise AIError("Add an API key in Settings to use the OpenAI API.")
    return {"provider": provider, "base": base, "key": key, "model": model}


def _http_message(code, settings):
    if code in (401, 403):
        return f"The API key was rejected (HTTP {code}). Check the key in Settings."
    if code == 404 and settings["provider"] == "ollama":
        return "The local model is not downloaded yet. Watch the terminal for the download, then try again."
    if code == 404:
        return "The model or endpoint was not found (HTTP 404). Check the model name and base URL in Settings."
    if code == 429:
        return "The AI service rate limit or quota was reached (HTTP 429). Try again later."
    return f"The AI service returned an error (HTTP {code})."


def _connection_message(settings):
    host = urlparse(settings["base"]).netloc or settings["base"]
    if settings["provider"] == "ollama":
        return f"Local Ollama is not reachable at {host}. It may still be starting. Check the terminal, or add an API key in Settings."
    return f"Could not reach the AI service at {host}. Check the base URL and your connection."


def _post(url, headers, payload, settings):
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=AI_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise AIError(_http_message(error.code, settings)) from None
    except (URLError, OSError):
        raise AIError(_connection_message(settings)) from None
    except ValueError:
        raise AIError("The AI service returned a response that could not be read.") from None


def chat(settings, system, user, max_tokens=AI_MAX_TOKENS):
    if settings["provider"] == "anthropic":
        url = settings["base"] + "/v1/messages"
        headers = {"Content-Type": "application/json", "x-api-key": settings["key"],
                   "anthropic-version": "2023-06-01"}
        payload = {"model": settings["model"], "max_tokens": max_tokens, "system": system,
                   "messages": [{"role": "user", "content": user}]}
        data = _post(url, headers, payload, settings)
        try:
            text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        except (AttributeError, TypeError):
            raise AIError("The AI service returned an unexpected response.") from None
    else:
        url = settings["base"] + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if settings["key"]:
            headers["Authorization"] = "Bearer " + settings["key"]
        payload = {"model": settings["model"], "max_tokens": max_tokens, "temperature": 0.2,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        data = _post(url, headers, payload, settings)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise AIError("The AI service returned an unexpected response.") from None

    text = (text or "").strip()
    if not text:
        raise AIError("The AI service returned an empty answer.")
    return text


def test_connection(ai):
    settings = resolve_settings(ai)
    chat(settings, "You are a connection test.", "Reply with the single word OK.", max_tokens=8)
    return {"ok": True, "provider": settings["provider"], "model": settings["model"]}


SYSTEM_PROMPT = (
    "You are a patient technical writer who turns code projects into clear, friendly GitHub README files "
    "for beginners and experienced developers alike. Write in plain English with short sentences. Explain any "
    "technical term the first time you use it. Use only facts supported by the evidence you are given. Never "
    "invent features, commands, endpoints, or links. Output only the Markdown document, with no preface and no "
    "closing remarks."
)


def build_prompt(ev):
    tech = ", ".join(ev.get("tech_languages") or []) or "unknown"
    pct = ev.get("percentages") or {}
    share = ", ".join(f"{k} {v}%" for k, v in pct.items()) or tech
    deps = "\n".join(f"- {d}" for d in ev.get("dependencies", [])) or "none found"
    modules = "\n".join(
        f"- {path}: " + (summary or ("defines " + ", ".join(names) if names else "no summary"))
        for path, summary, names in ev.get("module_notes", [])
    ) or "none found"
    excerpts = "\n\n".join(f"--- {path} ---\n{text}" for path, text in ev.get("excerpts", [])) or "none"
    existing = (ev.get("repo_readme") or ev.get("source") or "").strip()[:6000] or "none"
    tree = "\n".join(ev.get("tree_lines") or []) or "unavailable"
    commands = "\n".join(ev.get("install_commands") or []) or "unknown"

    user = f"""Write a complete, easy-to-read README.md for this project.

Project name: {ev['project_name']}
Repository: {ev.get('repo_url') or 'not provided'}
Short description: {ev.get('description') or 'not provided'}
Languages (share of code): {share}
Frameworks: {', '.join(ev.get('frameworks') or []) or 'none detected'}
Detected features: {', '.join(ev.get('features') or []) or 'none detected'}
Install commands: {commands}
Run command: {ev.get('run_command') or 'unknown'}
License: {ev.get('license_name') or 'unknown'}

Dependencies:
{deps}

Main modules:
{modules}

Project structure:
```text
{tree}
```

Key file excerpts:
{excerpts}

Existing README or notes from the author (may be empty):
{existing}

Write these sections, in this order:
1. Title (H1), then an introduction of two or three paragraphs, each with three to five full sentences. Cover what the project is, what problem it solves, who would use it, and what makes it useful. Do not give the introduction a heading.
2. ## Features: a bullet list. Each bullet starts with the feature name in bold, then one or two full sentences (about 20 to 35 words) explaining what it means for the user.
3. ## Technologies: a bullet list of languages and frameworks. Each bullet has the name in bold and a full sentence about its job in this project.
4. ## Project Structure: copy the project structure above exactly inside a text code block, then one line per important folder or file.
5. ## Quick Start: numbered steps. Each step has a bold title on its own line and then ONE bash code block with the exact commands. Include the clone, install, and run commands when they are known.
6. ## How to Use: two or three short examples that show what a user does and what they get.
7. ## How It Works: explain the main modules in plain language, two or three sentences each.
8. ## Contributing: three or four friendly sentences.
9. ## License: only if a license is known.

Rules:
- Do not add shields.io badges.
- Do not write sections about API endpoints, routes, or tests.
- Every command must be inside a ```bash code block, one command per line.
- Write descriptive, flowing sentences instead of fragments. Prefer one clear, detailed sentence over a few words.
- Do not write a table of contents. A one-line navigation bar is added automatically.
- Keep paragraphs focused (three to five sentences).
- Do not invent facts the evidence does not support. If something is unknown, leave it out instead of guessing."""
    return SYSTEM_PROMPT, user


def generate_readme(ai, evidence):
    settings = resolve_settings(ai)
    system, user = build_prompt(evidence)
    markdown = chat(settings, system, user)
    return markdown, {"provider": settings["provider"], "model": settings["model"]}
