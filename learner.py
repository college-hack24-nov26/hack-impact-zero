"""Learns from top GitHub repositories in the background while FixREADME is running.

What happens, in order:
  1. The app calls start_learning(). It does nothing unless LEARN_ENABLED is True in config.py
     and a GitHub token is available.
  2. It builds a pool of popular repositories and inspects up to LEARN_TARGET of them, saving
     every result to data/progress.jsonl as it goes.
  3. When LEARN_MILESTONE repositories have been inspected, it writes data/feature_profile.json.
     best_practices.py reads that file on every request, so no restart is needed.
  4. It refreshes the findings every LEARN_STEP repositories and once more at the end.
  5. If the app is closed, nothing is lost. The next launch reads progress.jsonl, uses the findings
     that already exist, and continues where it stopped.

Limits that protect your GitHub quota:
  - LEARN_RESERVE core requests are always kept free for README requests. When the remaining
    core quota reaches that number, learning pauses and resumes on the next launch.
  - When GitHub reports a rate limit, learning pauses instead of waiting for the reset.
  - Search requests have their own quota and are not counted against LEARN_RESERVE.
"""
import json
import threading
import time
from pathlib import Path

import trending_repos as tr
from config import LEARN_ENABLED, LEARN_MILESTONE, LEARN_RESERVE, LEARN_STEP, LEARN_TARGET, server_github_token
from local_ai import log

MIN_SCORE = 60.0
LOG_EVERY = 10
MAX_FAILURES = 5


class ReserveReached(RuntimeError):
    """Raised when learning must stop to keep the remaining GitHub requests for README requests."""


class _Client(tr.GitHub):
    """GitHub client for learning. It stays quiet, never waits for a rate limit, and keeps a reserve."""

    def __init__(self, reserve=0, sleep_fn=None, token=None):
        super().__init__(token=token, pause=0.5, verbose=False, wait_for_limit=False,
                         sleep=sleep_fn or time.sleep)
        self.reserve = reserve
        self.core_remaining = None

    def _request(self, url, accept="application/vnd.github+json", timeout=20):
        response = super()._request(url, accept=accept, timeout=timeout)
        # Only the core quota is reserved. Search has its own quota, reported under another resource name.
        if response.headers.get("X-RateLimit-Resource", "core") == "core":
            value = response.headers.get("X-RateLimit-Remaining", "")
            if value.isdigit():
                self.core_remaining = int(value)
        return response

    def get_json(self, path, params="", search=False):
        if not search and self.core_remaining is not None and self.core_remaining <= self.reserve:
            raise ReserveReached(
                f"Paused: {self.core_remaining} GitHub requests are left, and {self.reserve} are kept for README "
                "requests. Learning resumes the next time the app starts.")
        return super().get_json(path, params, search=search)


class Learner:
    def __init__(self, out_dir=None, target=LEARN_TARGET, milestone=LEARN_MILESTONE, step=LEARN_STEP,
                 min_score=MIN_SCORE, reserve=LEARN_RESERVE, client_factory=None, retry_wait=120):
        self.out_dir = Path(out_dir) if out_dir else tr.DATA_DIR
        self.target = target
        self.milestone = min(milestone, target)
        self.step = max(1, step)
        self.min_score = min_score
        self.reserve = reserve
        self.retry_wait = retry_wait
        self._client_factory = client_factory
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self.state = "idle"
        self.message = "Learning from top repositories has not started."
        self.inspected = 0
        self.in_use = False
        self.publishes = 0
        self._published_at = 0

    # ---- control -------------------------------------------------------------------------

    def start(self):
        with self._lock:
            if self._thread:
                return False
            self._thread = threading.Thread(target=self._safe_run, name="learner", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def status(self):
        return {"state": self.state, "message": self.message, "inspected": self.inspected,
                "target": self.target, "milestone": self.milestone, "in_use": self.in_use}

    def _set(self, state, message):
        self.state, self.message = state, message

    # ---- work ----------------------------------------------------------------------------

    def _safe_run(self):
        try:
            self._run()
        except Exception as error:  # the web server must keep running whatever happens here
            self._set("error", f"Learning stopped: {error}")
            log(f"Learning stopped: {error}")

    def _client(self):
        if self._client_factory:
            return self._client_factory()
        return _Client(reserve=self.reserve, sleep_fn=self._stop.wait)

    def _publish(self, records):
        """Write the JSON files. feature_profile.json is what the rest of the app reads."""
        tr.save_results(records, self.min_score, self.out_dir)
        self.in_use = True
        self.publishes += 1
        self._published_at = len(records)
        log(f"Learning: findings from {len(records)} repositories are saved and used for new READMEs.")

    def _profile_exists(self):
        return (self.out_dir / "feature_profile.json").exists()

    def _prepare_progress_file(self, path):
        """A run that was stopped mid-write can leave a partial line. Start the next record on a new line."""
        try:
            data = path.read_bytes()
        except OSError:
            return
        if data and not data.endswith(b"\n"):
            with open(path, "ab") as handle:
                handle.write(b"\n")

    def _due(self, count):
        if count < self.milestone:
            return False
        return count == self.milestone or (count - self.milestone) % self.step == 0

    def _pause(self, message):
        self._set("paused", message)
        log(f"Learning paused. {message}")

    def _run(self):
        gh = self._client()
        if not gh.token:
            self._set("no_token", "Add GITHUB_TOKEN to .env to learn from top repositories in the background.")
            log("Learning is off: add GITHUB_TOKEN to the .env file to study top repositories in the background.")
            return

        self.out_dir.mkdir(parents=True, exist_ok=True)
        progress_path = self.out_dir / "progress.jsonl"
        self._prepare_progress_file(progress_path)
        done = tr.load_progress(progress_path)
        records = list(done.values())
        self.inspected = len(records)

        if self.inspected >= self.milestone and not self._profile_exists():
            self._publish(records)
        self.in_use = self._profile_exists()
        if self.inspected:
            log(f"Learning: continuing with {self.inspected} of {self.target} repositories already studied.")
        if self.inspected >= self.target:
            self._set("complete", f"Studied {self.inspected} repositories.")
            return

        self._set("collecting", "Looking for popular repositories.")
        log(f"Learning: building a pool of popular repositories (target {self.target}).")
        try:
            candidates = tr.collect_candidates(gh, 20, None, None, target=self.target)
        except ReserveReached as error:
            return self._pause(str(error))
        except RuntimeError as error:
            return self._pause(str(error))
        if not candidates:
            return self._pause("No repositories were found. GitHub may be unreachable.")

        selected = tr.select_candidates(candidates, self.target)
        todo = [(name, entry) for name, entry in selected if name not in done]
        log(f"Learning: {len(candidates)} repositories found; studying {len(todo)} more.")

        self._set("learning", f"Studied {self.inspected} of {self.target} repositories.")
        failures = 0
        with open(progress_path, "a", encoding="utf-8") as progress:
            index = 0
            while index < len(todo) and not self._stop.is_set():
                name, entry = todo[index]
                try:
                    readme = gh.readme(name)
                    files = gh.root_files(name)
                except ReserveReached as error:
                    return self._pause(str(error))
                except RuntimeError as error:
                    if "rate limit" in str(error).lower():
                        return self._pause(str(error))
                    failures += 1
                    if "rejected" in str(error).lower() or failures >= MAX_FAILURES:
                        return self._pause(str(error))
                    log(f"Learning: {error} Trying again in {self.retry_wait} seconds.")
                    self._stop.wait(self.retry_wait)
                    continue
                failures = 0
                index += 1
                record = tr.build_record(entry["repo"], readme, files, entry["categories"])
                records.append(record)
                progress.write(json.dumps(record, ensure_ascii=False) + "\n")
                progress.flush()
                self.inspected = len(records)
                self._set("learning", f"Studied {self.inspected} of {self.target} repositories.")
                if self.inspected % LOG_EVERY == 0:
                    log(f"Learning: {self.inspected} of {self.target} repositories studied.")
                if self._due(self.inspected):
                    self._publish(records)

        if self._stop.is_set():
            self._set("stopped", f"Stopped after {self.inspected} repositories.")
            return
        if self.inspected >= self.milestone and self._published_at != self.inspected:
            self._publish(records)   # final refresh with everything that was studied
        self._set("complete", f"Studied {self.inspected} repositories.")
        log(f"Learning: finished. Studied {self.inspected} repositories.")


learner = Learner()


def start_learning():
    """Called by app.py. Does nothing unless learning is enabled and a token exists."""
    if not LEARN_ENABLED:
        learner._set("off", "Learning from top repositories is off (LEARN_ENABLED is False in config.py).")
        return False
    if not server_github_token():
        learner._set("no_token", "Add GITHUB_TOKEN to .env to learn from top repositories in the background.")
        log("Learning from top repositories needs a GitHub token. Put GITHUB_TOKEN=... in the .env file to turn it on.")
        return False
    return learner.start()