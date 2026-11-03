import io
import json
import os
import sys
import tempfile
import time
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as web  # noqa: E402
import config  # noqa: E402
import repo_fetch  # noqa: E402
import trending_repos as tr  # noqa: E402

TOKEN = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


def http_error(code, **headers):
    msg = Message()
    for key, value in headers.items():
        msg[key.replace("_", "-")] = str(value)
    return HTTPError("https://api.github.com/x", code, "err", msg, io.BytesIO(b"{}"))


class FakeResponse:
    def __init__(self, payload, headers=None):
        self._body = json.dumps(payload).encode()
        self.headers = headers or {"X-RateLimit-Remaining": "4000"}

    def read(self, *_):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TokenSafetyTests(unittest.TestCase):
    def test_clean_token_accepts_real_shapes_and_rejects_junk(self):
        self.assertEqual(config.clean_token("  " + TOKEN + " "), TOKEN)
        self.assertEqual(config.clean_token(""), "")
        for bad in ("not a token", 'ghp_"quoted"aaaaaaaaaaaaaaaaaaaa', "short", "a" * 300, TOKEN + "\r\nX-Evil: 1"):
            with self.assertRaises(ValueError) as ctx:
                config.clean_token(bad)
            self.assertNotIn(bad.strip(), str(ctx.exception))

    def test_dotenv_is_read_but_never_overrides_the_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text('# comment\nFIXREADME_T1="value-one"\nexport FIXREADME_T2=value-two\nFIXREADME_T3=from-file\n')
            with mock.patch.dict(os.environ, {"FIXREADME_T3": "from-env"}, clear=False):
                config.load_dotenv(path)
                self.assertEqual(os.environ["FIXREADME_T1"], "value-one")
                self.assertEqual(os.environ["FIXREADME_T2"], "value-two")
                self.assertEqual(os.environ["FIXREADME_T3"], "from-env")
            for key in ("FIXREADME_T1", "FIXREADME_T2", "FIXREADME_T3"):
                os.environ.pop(key, None)

    def test_browser_token_beats_server_token(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "server" + "x" * 20}):
            self.assertEqual(web._github_token({"github_token": TOKEN}), (TOKEN, "browser"))
            self.assertEqual(web._github_token({}), ("server" + "x" * 20, "server"))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(web._github_token({}), ("", "none"))

    def test_token_is_sent_only_to_the_github_api(self):
        seen = []

        def fake_urlopen(request, timeout=0):
            seen.append(request.get_header("Authorization"))
            return FakeResponse({"ok": True})

        with mock.patch.object(repo_fetch, "urlopen", fake_urlopen):
            repo_fetch.github_json("/repos/a/b", TOKEN)
            repo_fetch.github_json("/repos/a/b", None)
        self.assertEqual(seen, ["Bearer " + TOKEN, None])
        gh = tr.GitHub(TOKEN)
        with mock.patch.object(tr, "urlopen", lambda r, timeout=0: seen.append(r.get_header("Authorization")) or FakeResponse({})):
            gh._request("https://raw.githubusercontent.com/a/b/main/README.md")
        self.assertIsNone(seen[-1])

    def test_rate_limit_message_suggests_a_token_only_when_none_is_used(self):
        reset = int(time.time()) + 600
        error = http_error(403, X_RateLimit_Remaining=0, X_RateLimit_Reset=reset)
        without = repo_fetch.github_error_message(error, False)
        with_token = repo_fetch.github_error_message(error, True)
        self.assertIn("Add a free GitHub token", without)
        self.assertNotIn("Add a free GitHub token", with_token)
        self.assertIn("minute", with_token)
        self.assertIn("rejected the access token", repo_fetch.github_error_message(http_error(401), True))

    def test_fetch_uses_the_token_and_reports_rate_limit_clearly(self):
        calls = []

        def fake_json(path, token=None):
            calls.append(token)
            raise http_error(403, X_RateLimit_Remaining=0, X_RateLimit_Reset=int(time.time()) + 120)

        with mock.patch.object(repo_fetch, "github_json", fake_json):
            with self.assertRaises(ValueError) as ctx:
                repo_fetch.fetch_repo_context("https://github.com/a/b", TOKEN)
        self.assertEqual(calls, [TOKEN])
        self.assertNotIn(TOKEN, str(ctx.exception))


class TokenEndpointTests(unittest.TestCase):
    def setUp(self):
        web.app.config["TESTING"] = True
        self.client = web.app.test_client()

    def test_test_endpoint_reports_limits_and_never_echoes_the_token(self):
        core = {"resources": {"core": {"limit": 5000, "remaining": 4990, "reset": int(time.time()) + 1800}}}
        with mock.patch.object(repo_fetch, "github_json", lambda path, token=None: core):
            data = self.client.post("/api/github/test", json={"github_token": TOKEN}).get_json()
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["source"], "browser")
        self.assertEqual(data["remaining"], 4990)
        self.assertNotIn(TOKEN, json.dumps(data))

    def test_malformed_token_is_a_clean_400(self):
        response = self.client.post("/api/github/test", json={"github_token": "has spaces in it, not a token"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("has spaces", response.get_data(as_text=True))

    def test_generate_passes_the_browser_token_to_github(self):
        captured = {}

        def fake_fetch(url, token=None):
            captured["token"] = token
            raise ValueError("stop here")

        with mock.patch.object(repo_fetch, "fetch_repo_context", fake_fetch):
            self.client.post("/api/generate", json={"repo_url": "https://github.com/a/b", "use_ai": False,
                                                    "github_token": TOKEN})
        self.assertEqual(captured["token"], TOKEN)

    def test_page_has_a_hidden_token_field_with_show_button(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="githubTokenInput" type="password"', html)
        self.assertIn('id="toggleGhBtn"', html)


class CollectorTests(unittest.TestCase):
    def test_collector_waits_for_the_rate_limit_instead_of_stopping(self):
        sleeps, attempts = [], []
        gh = tr.GitHub(TOKEN, sleep=sleeps.append)

        def fake_request(url, **_):
            attempts.append(url)
            if len(attempts) == 1:
                raise http_error(403, X_RateLimit_Remaining=0, X_RateLimit_Reset=int(time.time()) + 30)
            return FakeResponse({"items": []})

        gh._request = fake_request
        self.assertEqual(gh.get_json("/rate_limit"), {"items": []})
        self.assertEqual(len(attempts), 2)
        self.assertTrue(any(25 <= s <= 40 for s in sleeps), sleeps)

    def test_no_wait_mode_stops_with_a_clear_message(self):
        gh = tr.GitHub(TOKEN, wait_for_limit=False, sleep=lambda _: None)

        def fake_request(url, **_):
            raise http_error(403, X_RateLimit_Remaining=0, X_RateLimit_Reset=int(time.time()) + 600)

        gh._request = fake_request
        with self.assertRaises(RuntimeError) as ctx:
            gh.get_json("/rate_limit")
        self.assertIn("rate limit", str(ctx.exception).lower())
        self.assertNotIn(TOKEN, str(ctx.exception))

    def test_search_pages_until_a_short_page(self):
        gh = tr.GitHub(TOKEN, sleep=lambda _: None)
        pages = [{"items": [{"full_name": f"o/r{i}"} for i in range(100)]}, {"items": [{"full_name": "o/last"}]}]
        gh._request = lambda url, **_: FakeResponse(pages.pop(0))
        items = gh.search_repos("stars:>1", per_page=100, pages=5)
        self.assertEqual(len(items), 101)

    def test_select_candidates_prefers_multi_category_then_stars(self):
        found = {"a/low": {"repo": {"stargazers_count": 10}, "categories": {"top", "viral"}},
                 "b/high": {"repo": {"stargazers_count": 999}, "categories": {"top"}},
                 "c/mid": {"repo": {"stargazers_count": 500}, "categories": {"top"}}}
        self.assertEqual([n for n, _ in tr.select_candidates(found, 2)], ["a/low", "b/high"])

    def test_progress_file_allows_resuming(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "progress.jsonl"
            path.write_text('{"full_name": "a/b", "score": 70}\nnot json\n{"full_name": "c/d", "score": 50}\n')
            self.assertEqual(sorted(tr.load_progress(path)), ["a/b", "c/d"])
            self.assertEqual(tr.load_progress(Path(folder) / "missing.jsonl"), {})


if __name__ == "__main__":
    unittest.main()
