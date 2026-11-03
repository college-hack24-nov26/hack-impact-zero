import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trending_repos as tr  # noqa: E402
from learner import Learner  # noqa: E402

README = ("# Rocket\n\n## Features\n\n- Fast incremental builds for large projects\n\n## Installation\n\n```bash\nnpm i rocket\n```\n\n"
          "## Usage\n\n```js\nrocket()\n```\n\n## Contributing\n\nPRs welcome.\n\n## License\n\nMIT\n") + "text " * 200


def fake_repo(i):
    return {"full_name": f"o/r{i}", "stargazers_count": 10_000 - i, "forks_count": 100, "created_at": "2020-01-01T00:00:00Z",
            "pushed_at": "2026-10-01T00:00:00Z", "license": {"spdx_id": "MIT"}}


class FakeGitHub:
    """Stands in for GitHub: 8 repositories, optional failure to prove resuming works."""
    token = "x" * 30

    def __init__(self, pool=8):
        self.pool = pool
        self.read = []

    def log(self, _message):
        pass

    def search_repos(self, query, sort="stars", per_page=30, pages=1):
        return [fake_repo(i) for i in range(self.pool)] if "stars:>=60000" in query or "stars:>50000" in query else []

    def readme(self, name):
        self.read.append(name)
        return README

    def root_files(self, _name):
        return ["LICENSE", "tests"]


class LearnerTests(unittest.TestCase):
    def make(self, folder, gh, **kw):
        opts = dict(out_dir=folder, target=8, milestone=3, step=2, client_factory=lambda: gh, retry_wait=0)
        opts.update(kw)
        return Learner(**opts)

    def test_findings_are_used_from_the_milestone_and_refreshed_by_step(self):
        with tempfile.TemporaryDirectory() as folder:
            learner = self.make(folder, FakeGitHub())
            seen = []
            original = learner._publish

            def spy(records):
                original(records)
                seen.append(len(records))
                self.assertTrue((Path(folder) / "feature_profile.json").exists())
            learner._publish = spy
            learner._run()
            self.assertEqual(seen, [3, 5, 7, 8])          # milestone, every step, then the final refresh
            self.assertEqual(learner.status()["state"], "complete")
            self.assertTrue(learner.status()["in_use"])

    def test_profile_is_not_written_before_the_milestone(self):
        with tempfile.TemporaryDirectory() as folder:
            learner = self.make(folder, FakeGitHub(pool=2), milestone=3, target=3)
            learner._run()
            self.assertFalse((Path(folder) / "feature_profile.json").exists())
            self.assertFalse(learner.status()["in_use"])
            self.assertEqual(learner.inspected, 2)

    def test_relaunch_continues_without_repeating_work(self):
        with tempfile.TemporaryDirectory() as folder:
            first = FakeGitHub(pool=5)
            self.make(folder, first, target=5)._run()
            self.assertEqual(len(first.read), 5)
            second = FakeGitHub(pool=8)
            learner = self.make(folder, second)
            learner._run()
            self.assertEqual(len(second.read), 3)               # only the repositories not yet studied
            self.assertEqual(learner.inspected, 8)
            lines = (Path(folder) / "progress.jsonl").read_text().splitlines()
            self.assertEqual(len({json.loads(x)["full_name"] for x in lines}), 8)

    def test_relaunch_publishes_findings_that_were_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            self.make(folder, FakeGitHub(pool=4), milestone=9, target=9)._run()
            (Path(folder) / "feature_profile.json").unlink(missing_ok=True)
            learner = self.make(folder, FakeGitHub(pool=4), milestone=3, target=4)
            learner._run()
            self.assertTrue((Path(folder) / "feature_profile.json").exists())

    def test_half_written_progress_line_is_survived(self):
        with tempfile.TemporaryDirectory() as folder:
            self.make(folder, FakeGitHub(pool=3), target=3)._run()
            path = Path(folder) / "progress.jsonl"
            path.write_text(path.read_text() + '{"full_name": "o/broken", "sc')   # killed mid-write
            learner = self.make(folder, FakeGitHub(pool=6), target=6)
            learner._run()
            names = [json.loads(x)["full_name"] for x in path.read_text().splitlines() if x.endswith("}")]
            self.assertEqual(len(set(names)), 6)

    def test_no_token_means_no_learning(self):
        class NoToken(FakeGitHub):
            token = ""
        with tempfile.TemporaryDirectory() as folder:
            learner = self.make(folder, NoToken())
            learner._run()
            self.assertEqual(learner.status()["state"], "no_token")

    def test_large_target_uses_many_narrow_star_bands(self):
        queries = []

        class Spy(FakeGitHub):
            def search_repos(self, query, sort="stars", per_page=30, pages=1):
                queries.append((query, pages))
                return []
        tr.collect_candidates(Spy(), 20, orgs=[], target=5000)
        bands = [q for q, _ in queries if q.startswith("stars:")]
        self.assertGreaterEqual(len(bands), 12)
        self.assertTrue(all(pages == 10 for q, pages in queries if q.startswith("stars:")))


class ReserveTests(unittest.TestCase):
    def test_pauses_when_only_the_reserve_is_left(self):
        import time
        slept = []
        gh = tr.GitHub(token="x" * 30, reserve=100, sleep=slept.append, verbose=False)
        gh.remaining, gh.reset_at = 50, int(time.time()) + 20
        gh._respect_reserve()
        self.assertTrue(slept)
        self.assertIsNone(gh.remaining)

    def test_does_not_pause_with_plenty_left_or_no_reserve(self):
        import time
        slept = []
        gh = tr.GitHub(token="x" * 30, reserve=100, sleep=slept.append, verbose=False)
        gh.remaining, gh.reset_at = 4000, int(time.time()) + 20
        gh._respect_reserve()
        free = tr.GitHub(token="x" * 30, reserve=0, sleep=slept.append, verbose=False)
        free.remaining, free.reset_at = 1, int(time.time()) + 20
        free._respect_reserve()
        self.assertEqual(slept, [])

    def test_search_bucket_does_not_count_as_core_reads(self):
        class Response:
            def __init__(self, resource, remaining):
                self.headers = {"X-RateLimit-Resource": resource, "X-RateLimit-Remaining": str(remaining),
                                "X-RateLimit-Reset": "9999999999"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"{}"

        gh = tr.GitHub(token="x" * 30, verbose=False, sleep=lambda s: None)
        gh._request = lambda url, **kw: Response("core", 4321)
        gh.get_json("/repos/a/b")
        gh._request = lambda url, **kw: Response("search", 7)
        gh.get_json("/search/repositories", "q=x", search=True)
        self.assertEqual(gh.remaining, 4321)


if __name__ == "__main__":
    unittest.main()
