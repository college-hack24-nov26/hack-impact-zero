"""Fix README web application.

Run with `python app.py`. The local Ollama model starts in the background and its progress
is printed to this terminal. Every route returns JSON errors instead of crashing the server.
"""
import traceback

from flask import Flask, jsonify, render_template, request

import analyzer
import llm
import repo_fetch
from config import MAX_INPUT_CHARS, MAX_REQUEST_BYTES, clean_token, server_github_token
from learner import learner, start_learning
from local_ai import local_ai, log

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES


def _ai_from(data):
    ai = data.get("ai")
    return ai if isinstance(ai, dict) else {}


def _inputs(data):
    repo_url = str(data.get("repo_url") or "").strip()[:300]
    text = str(data.get("readme_text") or data.get("readme") or "").strip()[:MAX_INPUT_CHARS]
    return repo_url, text


def _github_token(data):
    """Token typed in the browser wins; otherwise the server's GITHUB_TOKEN / .env token; otherwise none.

    Returns (token, source). Raises ValueError (HTTP 400) if the typed token is malformed.
    """
    typed = clean_token(data.get("github_token"))
    if typed:
        return typed, "browser"
    server = server_github_token()
    return (server, "server") if server else ("", "none")


def _generator_label(ai_info, ai_used):
    if ai_used and ai_info:
        short = llm.PROVIDERS[ai_info["provider"]]["short"]
        return f"Written by {short} · {ai_info['model']}"
    return "Built from repository evidence (no AI)"


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "The request is too large. Shorten the pasted text and try again."}), 413


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify(local_ai.status())


@app.get("/api/learning")
def learning():
    return jsonify(learner.status())


@app.get("/api/providers")
def providers():
    return jsonify(llm.public_providers())


@app.post("/api/settings/test")
def settings_test():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(llm.test_connection(_ai_from(data)))
    except llm.AIError as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        log("Unexpected error while testing AI settings:\n" + traceback.format_exc())
        return jsonify({"error": "Unexpected error while testing the connection."}), 500


@app.post("/api/github/test")
def github_test():
    data = request.get_json(silent=True) or {}
    try:
        token, source = _github_token(data)
        info = repo_fetch.token_status(token)
        info["source"] = source
        return jsonify(info)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        log("Unexpected error while testing the GitHub token.")
        return jsonify({"error": "Unexpected error while testing the GitHub token."}), 500


@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True) or {}
    repo_url, text = _inputs(data)
    if not repo_url and not text:
        return jsonify({"error": "Enter a GitHub repository URL or paste project text to analyze."}), 400
    try:
        token, _ = _github_token(data)
        context = repo_fetch.fetch_repo_context(repo_url, token) if repo_url else None
        _, analysis = analyzer.compose_readme(analyzer.gather_evidence(context, text))
        return jsonify(analysis)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        log("Unexpected error in /api/analyze:\n" + traceback.format_exc())
        return jsonify({"error": "Unexpected error while analyzing the project."}), 500


@app.post("/api/generate")
def generate():
    data = request.get_json(silent=True) or {}
    repo_url, text = _inputs(data)
    if not repo_url and not text:
        return jsonify({"error": "Enter a GitHub repository URL or paste project text to analyze."}), 400
    use_ai = bool(data.get("use_ai", True))
    try:
        token, _ = _github_token(data)
        context = repo_fetch.fetch_repo_context(repo_url, token) if repo_url else None
        evidence = analyzer.gather_evidence(context, text)

        ai_markdown, ai_info, ai_error = None, None, None
        if use_ai:
            try:
                ai_markdown, ai_info = llm.generate_readme(_ai_from(data), evidence)
            except llm.AIError as error:
                ai_error = str(error)

        readme, analysis = analyzer.compose_readme(evidence, ai_markdown)
        analysis["generator_label"] = _generator_label(ai_info, analysis["ai_used"])
        if analysis["ai_used"] and ai_info:
            analysis["generator"] = ai_info
        if ai_error:
            analysis["ai_status"] = ai_error
        elif use_ai and not analysis["ai_used"]:
            analysis["ai_status"] = "The AI answer was too short to use, so the README was built from repository evidence."
        else:
            analysis["ai_status"] = ""
        return jsonify({"readme": readme, "analysis": analysis})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        log("Unexpected error in /api/generate:\n" + traceback.format_exc())
        return jsonify({"error": "Something went wrong while generating the README. The server is still running; try again."}), 500


if __name__ == "__main__":
    log("Fix README is starting.")
    local_ai.start()
    start_learning()
    log("Open http://127.0.0.1:5000 in your browser. Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
