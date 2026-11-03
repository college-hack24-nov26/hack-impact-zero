import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trending_repos as tr  # noqa: E402
from best_practices import DEFAULT_RECOMMENDED, recommended_sections  # noqa: E402
from badges import make_badge, tech_badges  # noqa: E402

NOW = datetime.now(timezone.utc)


def iso(days):
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


GOOD_README = ("# Rocket\n\n![b1](https://img.shields.io/badge/a-b-c) ![b2](https://img.shields.io/badge/d-e-f)\n\n"
               "![shot](shot.png)\n\n## Table of Contents\n\n- [Features](#features)\n\n## Features\n\n"
               "- Fast incremental builds for large projects\n- Stable plugin interface for extensions\n\n"
               "## Installation\n\n```bash\nnpm i rocket\n```\n\n## Usage\n\n```js\nrocket()\n```\n\n"
               "## Contributing\n\nPRs welcome.\n\n## License\n\nMIT\n") + "text " * 800

STRONG = {"full_name": "a/rocket", "stargazers_count": 90_000, "forks_count": 8_000, "subscribers_count": 1_500,
          "open_issues_count": 100, "created_at": iso(900), "pushed_at": iso(2), "license": {"spdx_id": "MIT"}}
WEAK = {"full_name": "b/tiny", "stargazers_count": 40, "forks_count": 1, "created_at": iso(500), "pushed_at": iso(800)}


class TrendingTests(unittest.TestCase):
    def test_extract_features_finds_sections_and_bullets(self):
        f = tr.extract_features(GOOD_README)
        for name in ("installation", "usage", "features", "contributing", "license", "table_of_contents"):
            self.assertTrue(f["sections"][name], name)
        self.assertFalse(f["sections"]["faq"])
        self.assertEqual(f["badge_count"], 2)
        self.assertEqual(f["image_count"], 1)
        self.assertEqual(f["code_block_count"], 2)
        self.assertEqual(len(f["feature_bullets"]), 2)

    def test_better_repo_scores_higher_and_stays_in_range(self):
        files = ["LICENSE", "CONTRIBUTING.md", "docs", "tests", ".github", "examples", "CHANGELOG.md", "SECURITY.md"]
        strong = tr.build_record(STRONG, GOOD_README, files, {"top", "big_company"})
        weak = tr.build_record(WEAK, "# tiny", ["main.py"], set())
        self.assertGreater(strong["score"], 80)
        self.assertLess(weak["score"], 20)
        for record in (strong, weak):
            self.assertTrue(0 <= record["score"] <= 100)

    def test_archived_repo_gets_no_maintenance_points(self):
        record = tr.build_record(dict(STRONG, archived=True), GOOD_README, [], set())
        self.assertEqual(record["score_breakdown"]["maintenance"], 0)

    def test_save_results_writes_three_json_files_and_filters_best(self):
        records = [tr.build_record(STRONG, GOOD_README, ["LICENSE"], {"top"}),
                   tr.build_record(WEAK, "# tiny", [], set())]
        with tempfile.TemporaryDirectory() as folder:
            _, best, profile = tr.save_results(records, 50, folder)
            data = json.loads((Path(folder) / "repos_data.json").read_text())
            best_file = json.loads((Path(folder) / "best_repos.json").read_text())
            profile_file = json.loads((Path(folder) / "feature_profile.json").read_text())
        self.assertEqual(data["count"], 2)
        self.assertEqual([r["full_name"] for r in best_file["repos"]], ["a/rocket"])
        self.assertEqual(data["repos"][0]["full_name"], "a/rocket")  # best first
        self.assertEqual(profile_file["based_on_repos"], 1)
        self.assertIn("installation", profile["recommended_sections"])

    def test_recommended_sections_use_profile_when_present_else_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "feature_profile.json"
            self.assertEqual(recommended_sections(path), DEFAULT_RECOMMENDED)
            path.write_text(json.dumps({"based_on_repos": 5, "recommended_sections": ["faq", "roadmap"]}))
            self.assertEqual(recommended_sections(path), ["faq", "roadmap"])

    def test_collect_candidates_tags_categories_and_skips_forks(self):
        class FakeGitHub:
            def log(self, _):
                pass

            def search_repos(self, query, sort="stars", per_page=30, pages=1):
                if "org:" in query:
                    return [{"full_name": "big/co-tool", "stargazers_count": 5}]
                if "stars:>50000" in query:
                    return [{"full_name": "a/rocket"}, {"full_name": "x/fork", "fork": True}]
                return [{"full_name": "a/rocket"}]

        found = tr.collect_candidates(FakeGitHub(), 5, orgs=["big"])
        self.assertNotIn("x/fork", found)
        self.assertIn("top", found["a/rocket"]["categories"])
        self.assertIn("famous", found["a/rocket"]["categories"])
        self.assertEqual(found["big/co-tool"]["categories"], {"big_company"})


class BadgeTests(unittest.TestCase):
    def test_badge_format_matches_markdown_badges_style(self):
        label, url = make_badge("python")
        self.assertEqual(url, "https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54")

    def test_unknown_technology_gets_no_badge(self):
        self.assertIsNone(make_badge("brainfuck"))
        self.assertEqual(tech_badges(["Brainfuck"], [], [], 5), [])

    def test_tech_badges_respect_limit_and_order(self):
        badges = tech_badges(["Python", "HTML"], ["Flask"], ["Docker container configuration"], 3)
        self.assertEqual([label for label, _ in badges], ["Python", "HTML", "Flask"])


if __name__ == "__main__":
    unittest.main()
