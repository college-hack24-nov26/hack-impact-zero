import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as web  # noqa: E402
import llm  # noqa: E402
import local_ai  # noqa: E402

LONG_README = (
    "# Mock Tool\n\nMock Tool converts CSV files into JSON for analysts who need a dependable "
    "conversion step in their scripts. It validates headers, streams rows, and reports errors clearly.\n\n"
    "## Features\n\n- Streams large files so memory use stays low.\n- Reports malformed rows with line numbers.\n"
)


class MockAI(BaseHTTPRequestHandler):
    """Answers OpenAI-compatible and Anthropic-style requests, and records the auth header."""
    seen_auth = []

    def log_message(self, *args):
        pass

    flag = None  # when this file exists, the mock Ollama reports the model as installed

    def do_GET(self):
        if self.path == "/api/tags":
            models = [{"name": "qwen2.5:0.5b"}] if MockAI.flag and os.path.exists(MockAI.flag) else []
            data = json.dumps({"models": models}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        MockAI.seen_auth.append(self.headers.get("Authorization") or self.headers.get("x-api-key"))
        if self.path.endswith("/chat/completions"):
            reply = {"choices": [{"message": {"content": "OK" if body.get("max_tokens") == 8 else LONG_README}}]}
        elif self.path.endswith("/v1/messages"):
            reply = {"content": [{"type": "text", "text": "OK" if body.get("max_tokens") == 8 else LONG_README}]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        if self.headers.get("Authorization") == "Bearer bad-key":
            self.send_response(401)
            self.end_headers()
            return
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ServicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockAI)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.client = web.app.test_client()
        web.app.config["TESTING"] = True

    def test_default_settings_use_local_ollama_without_key(self):
        settings = llm.resolve_settings({})
        self.assertEqual(settings["provider"], "ollama")
        self.assertEqual(settings["key"], "")
        self.assertTrue(settings["base"].endswith("/v1"))

    def test_hosted_providers_require_a_key(self):
        with self.assertRaises(llm.AIError):
            llm.resolve_settings({"provider": "anthropic"})
        with self.assertRaises(llm.AIError):
            llm.resolve_settings({"provider": "openai"})
        with self.assertRaises(llm.AIError):
            llm.resolve_settings({"provider": "openai", "base_url": "ftp://bad"})

    def test_openai_compatible_chat_with_key_and_custom_base(self):
        settings = llm.resolve_settings({"provider": "openai", "api_key": "good", "base_url": self.base + "/v1", "model": "m"})
        self.assertEqual(llm.chat(settings, "sys", "user", max_tokens=8), "OK")

    def test_bad_key_gives_friendly_message_without_leaking_key(self):
        settings = llm.resolve_settings({"provider": "openai", "api_key": "bad-key", "base_url": self.base + "/v1"})
        with self.assertRaises(llm.AIError) as ctx:
            llm.chat(settings, "sys", "user")
        self.assertIn("rejected", str(ctx.exception))
        self.assertNotIn("bad-key", str(ctx.exception))

    def test_anthropic_style_chat(self):
        settings = llm.resolve_settings({"provider": "anthropic", "api_key": "k", "base_url": self.base})
        self.assertIn("# Mock Tool", llm.chat(settings, "sys", "user"))

    def test_unreachable_server_is_a_friendly_error(self):
        settings = llm.resolve_settings({"provider": "openai", "api_key": "k", "base_url": "http://127.0.0.1:1/v1"})
        with self.assertRaises(llm.AIError) as ctx:
            llm.chat(settings, "sys", "user")
        self.assertIn("Could not reach", str(ctx.exception))

    def test_local_ai_reports_missing_binary_without_crashing(self):
        original = local_ai.shutil.which
        local_ai.shutil.which = lambda _name: None
        try:
            ai = local_ai.LocalAI()
            ai._setup()
            self.assertEqual(ai.state, "missing")
            self.assertFalse(ai.status()["installed"])
        finally:
            local_ai.shutil.which = original

    def test_local_setup_pulls_missing_model_and_reports_ready(self):
        import shutil
        import stat
        import tempfile
        tmp = tempfile.mkdtemp()
        flag = os.path.join(tmp, "pulled")
        fake = os.path.join(tmp, "ollama")
        with open(fake, "w") as handle:
            handle.write(f'#!/bin/sh\nif [ "$1" = "pull" ]; then echo "pulling manifest"; touch "{flag}"; exit 0; fi\nexit 0\n')
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        original_which, original_host = local_ai.shutil.which, local_ai.OLLAMA_HOST
        MockAI.flag = flag
        local_ai.shutil.which = lambda _name: fake
        local_ai.OLLAMA_HOST = self.base  # the mock answers as the running Ollama server
        try:
            ai = local_ai.LocalAI()
            ai._setup()
            self.assertEqual(ai.state, "ready")
            self.assertTrue(os.path.exists(flag), "the pull command should have run")
            self.assertTrue(ai.status()["installed"])
        finally:
            local_ai.shutil.which, local_ai.OLLAMA_HOST = original_which, original_host
            MockAI.flag = None
            shutil.rmtree(tmp, ignore_errors=True)

    def test_generate_uses_ai_when_configured(self):
        response = self.client.post("/api/generate", json={
            "readme_text": "A Python tool that converts CSV files to JSON for analysts.",
            "use_ai": True,
            "ai": {"provider": "openai", "api_key": "good", "base_url": self.base + "/v1", "model": "m"},
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["analysis"]["ai_used"])
        self.assertIn("Mock Tool", payload["readme"])
        self.assertIn("Written by OpenAI", payload["analysis"]["generator_label"])

    def test_generate_falls_back_when_ai_fails_and_reports_why(self):
        response = self.client.post("/api/generate", json={
            "readme_text": "# Demo\n\nA Python Flask web application with API routes.",
            "use_ai": True,
            "ai": {"provider": "openai", "api_key": "bad-key", "base_url": self.base + "/v1"},
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["analysis"]["ai_used"])
        self.assertIn("rejected", payload["analysis"]["ai_status"])
        self.assertIn("## Features", payload["readme"])

    def test_generate_without_ai_is_still_detailed(self):
        response = self.client.post("/api/generate", json={"readme_text": "# Demo\n\nA Flask app.", "use_ai": False})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Built from repository evidence", response.get_json()["analysis"]["generator_label"])

    def test_settings_test_endpoint(self):
        ok = self.client.post("/api/settings/test", json={"ai": {"provider": "openai", "api_key": "good", "base_url": self.base + "/v1"}})
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.get_json()["ok"])
        bad = self.client.post("/api/settings/test", json={"ai": {"provider": "anthropic"}})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("error", bad.get_json())

    def test_oversized_request_is_rejected_cleanly(self):
        big = "x" * (web.app.config["MAX_CONTENT_LENGTH"] + 10)
        response = self.client.post("/api/generate", data=json.dumps({"readme_text": big}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.get_json())

    def test_status_and_providers_endpoints(self):
        status = self.client.get("/api/status").get_json()
        self.assertIn(status["state"], {"idle", "checking", "missing", "starting", "pulling", "ready", "error"})
        providers = self.client.get("/api/providers").get_json()
        self.assertEqual(set(providers), {"ollama", "openai", "anthropic"})
        self.assertNotIn("api_key", json.dumps(providers))

    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"settingsDialog", response.data)


if __name__ == "__main__":
    unittest.main()
