import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import (build_tree_lines, compose_readme, detect_features, gather_evidence,  # noqa: E402
                      remove_unwanted_sections, strip_badges, detect_run_command)

FAKE_CONTEXT = {
    "owner": "example", "repo": "demo", "url": "https://github.com/example/demo",
    "metadata": {"description": "A small Flask service that converts CSV files to JSON.",
                 "license": {"spdx_id": "MIT"}},
    "languages": {"Python": 9000, "HTML": 1000},
    "paths": ["README.md", "app.py", "requirements.txt", "LICENSE", "templates/index.html",
              "static/style.css", "tests/test_app.py", ".github/workflows/ci.yml", "node_modules/x/y.js"],
    "readme": "",
    "files": [
        ("app.py", '"""Flask app that converts CSV uploads to JSON."""\nfrom flask import Flask\napp = Flask(__name__)\n\n'
                   '@app.get("/")\ndef index():\n    return "ok"\n\n@app.post("/api/convert")\ndef convert():\n    return {}\n\n'
                   "if __name__ == '__main__':\n    app.run(debug=True, host='127.0.0.1', port=5000)\n"),
        ("requirements.txt", "Flask>=3.0,<4.0\n"),
        ("tests/test_app.py", "import unittest\n"),
    ],
    "release": "v1.0.0",
}


class AnalyzerTests(unittest.TestCase):
    def test_no_literal_escape_sequences_in_output(self):
        readme, _ = compose_readme(gather_evidence(FAKE_CONTEXT, ""))
        self.assertNotIn("\\n", readme)
        readme, _ = compose_readme(gather_evidence(None, "# Demo\n\nA Python Flask web application."))
        self.assertNotIn("\\n", readme)

    def test_badges_capped_at_eight(self):
        readme, analysis = compose_readme(gather_evidence(FAKE_CONTEXT, ""))
        self.assertLessEqual(analysis["badge_count"], 8)
        self.assertLessEqual(readme.count("img.shields.io"), 8)

    def test_verified_badge_is_removed(self):
        source = ("# Demo App\n[![Verified by FixREADME](https://img.shields.io/badge/verified-fixreadme-green)]"
                  "(https://fixreadme.example)\n\nA Python Flask web application with API routes.\n")
        readme, _ = compose_readme(gather_evidence(None, source))
        self.assertNotIn("fixreadme", readme.lower())
        self.assertNotIn("verified", readme.lower())

    def test_repo_gets_detailed_sections(self):
        readme, analysis = compose_readme(gather_evidence(FAKE_CONTEXT, ""))
        for heading in ("## Features", "## Technologies", "## How It Works", "## Project Structure",
                        "## Dependencies", "## Prerequisites", "## Quick Start", "## Repository", "## License"):
            self.assertIn(heading, readme)
        self.assertIn("pip install -r requirements.txt", readme)
        self.assertIn("python app.py", readme)
        self.assertIn("http://127.0.0.1:5000", readme)
        self.assertIn("**Step 1: Download the project**", readme)
        self.assertIn("**Step 3: Start the project**", readme)
        self.assertNotIn("node_modules", readme)
        self.assertIn("A small Flask service that converts CSV files to JSON.", readme)
        self.assertIn("Project Structure", analysis["sections_added"])

    def test_no_api_endpoints_or_testing_in_output(self):
        readme, _ = compose_readme(gather_evidence(FAKE_CONTEXT, ""))
        for word in ("API Endpoints", "## Testing", "unittest", "curl ", "/api/convert", "tests/", "test_app.py",
                     "Automated tests", "tests-configured"):
            self.assertNotIn(word, readme)

    def test_existing_api_and_testing_sections_are_removed(self):
        source = ("# Demo\n\nA Python Flask web application.\n\n## API\n\n- GET /x\n\n## Usage\n\nRun it.\n\n"
                  "## Testing\n\n```bash\npytest\n```\n\n## License\n\nMIT\n")
        readme, _ = compose_readme(gather_evidence(None, source))
        self.assertNotIn("GET /x", readme)
        self.assertNotIn("pytest", readme)
        self.assertIn("## Usage", readme)
        self.assertIn("## License", readme)

    def test_remove_unwanted_sections_keeps_code_fence_comments(self):
        text = "# T\n\n## Usage\n\n```bash\n# Testing comment\nrun\n```\n\n## Tests\n\nx\n\n## License\n\nMIT\n"
        cleaned = remove_unwanted_sections(text)
        self.assertIn("# Testing comment", cleaned)
        self.assertNotIn("## Tests", cleaned)
        self.assertIn("## License", cleaned)

    def test_badges_use_markdown_badges_style(self):
        readme, analysis = compose_readme(gather_evidence(FAKE_CONTEXT, ""))
        self.assertIn("style=for-the-badge&logo=python", readme)
        self.assertIn("img.shields.io/badge/flask", readme)

    def test_prerequisites_are_added_but_no_table_of_contents(self):
        readme, analysis = compose_readme(gather_evidence(FAKE_CONTEXT, ""))
        self.assertNotIn("Table of Contents", readme)
        self.assertNotIn("Table of Contents", analysis["sections_added"])
        self.assertIn("- Python 3 and pip", readme)

    def test_existing_table_of_contents_is_removed(self):
        source = ("# Demo\n\nA Python app.\n\n## Table of Contents\n\n- [Install](#install)\n- [Use](#use)\n\n"
                  "## Install\n\npip install demo\n\n## Use\n\n- [One](#one)\n- [Two](#two)\n- [Three](#three)\n")
        readme, _ = compose_readme(gather_evidence(None, source))
        self.assertNotIn("Table of Contents", readme)
        self.assertNotIn("(#install)", readme)
        self.assertNotIn("(#three)", readme)
        self.assertIn("## Install", readme)

    def test_ai_output_never_keeps_copied_instructions(self):
        leaked = ("# Demo\n\nDemo is a small Python tool that helps people check their files quickly and safely every day.\n\n"
                  "## Features\n\n- **Fast** It checks files quickly and reports problems in plain words for everyone.\n\n"
                  "Rules:\n- Do not add shields.io badges.\n- Do not write sections about API endpoints, routes, or tests.\n"
                  "- Every command must be inside a ```bash code block, one command per line.\n"
                  "- Keep paragraphs short (two to four sentences).\n"
                  "- Do not invent facts the evidence does not support. If something is unknown, leave it out instead of guessing.\n\n"
                  "## License\n\nMIT\n")
        readme, analysis = compose_readme(gather_evidence(None, "# Demo\nA Python tool."), leaked)
        self.assertTrue(analysis["ai_used"])
        for phrase in ("Rules:", "shields.io badges", "Keep paragraphs short", "Do not invent facts", "Every command must"):
            self.assertNotIn(phrase, readme)
        self.assertIn("## Features", readme)

    def test_prompt_keeps_rules_out_of_the_user_message(self):
        from llm import build_prompt
        system, user = build_prompt(gather_evidence(FAKE_CONTEXT, ""))
        self.assertNotIn("Rules:", user)
        self.assertIn("table of contents", system.lower())

    def test_existing_sections_are_not_duplicated(self):
        source = "# Demo\n\nA Python Flask web application.\n\n## Installation\n\npip install demo\n"
        readme, analysis = compose_readme(gather_evidence(None, source))
        self.assertEqual(readme.count("## Installation"), 1)
        self.assertNotIn("Quick Start", analysis["sections_added"])

    def test_ai_markdown_is_used_when_valid_and_sections_are_still_added(self):
        ai = ("```markdown\n# Demo Tool\n\nDemo Tool converts CSV files into JSON for analysts who need "
              "a quick, dependable conversion step inside their own scripts and dashboards.\n\n"
              "## Features\n\n- Converts large files in streaming chunks so memory use stays low.\n```")
        readme, analysis = compose_readme(gather_evidence(FAKE_CONTEXT, ""), ai_markdown=ai)
        self.assertTrue(analysis["ai_used"])
        self.assertIn("converts CSV files into JSON", readme)
        self.assertEqual(readme.count("## Features"), 1)
        self.assertIn("## Project Structure", readme)
        self.assertNotIn("```markdown", readme)

    def test_too_short_ai_output_falls_back_to_template(self):
        readme, analysis = compose_readme(gather_evidence(FAKE_CONTEXT, ""), ai_markdown="# Hi")
        self.assertFalse(analysis["ai_used"])
        self.assertIn("## Quick Start", readme)

    def test_analysis_reports_file_counts_for_the_ui(self):
        _, analysis = compose_readme(gather_evidence(FAKE_CONTEXT, ""))
        self.assertGreater(analysis["file_count"], 0)
        self.assertGreater(analysis["folder_count"], 0)
        self.assertNotIn("node_modules", str(analysis["file_count"]))

    def test_tree_skips_ignored_directories_and_annotates_known_files(self):
        text = "\n".join(build_tree_lines("demo", ["app.py", "templates/index.html", "node_modules/x.js", "static/style.css"]))
        self.assertNotIn("node_modules", text)
        self.assertIn("# application entry point", text)
        self.assertIn("# HTML templates", text)

    def test_features_detected(self):
        features = detect_features("import sqlite3", ["templates/index.html"], {"app.py": "import sqlite3"})
        self.assertIn("Database integration", features)
        self.assertNotIn("Automated tests", features)
        self.assertNotIn("HTTP/API endpoints", features)
        self.assertNotIn("Payment integration", features)

    def test_run_detection(self):
        run, endpoint = detect_run_command(["app.py"], {"app.py": "if __name__ == '__main__':\n    app.run(port=8080)"})
        self.assertEqual(run, "python app.py")
        self.assertEqual(endpoint, ("127.0.0.1", "8080"))

    def test_strip_badges_keeps_normal_images(self):
        text = "# Title\n\n![Stars](https://img.shields.io/github/stars/a/b)\n\nSome text ![logo](logo.png)"
        cleaned = strip_badges(text)
        self.assertNotIn("img.shields.io", cleaned)
        self.assertIn("![logo](logo.png)", cleaned)


if __name__ == "__main__":
    unittest.main()
