"""Learns from top GitHub repositories in the background while FixREADME is running.

What happens, in order:
  1. The app starts this thread (only when a GitHub token is available).
  2. It builds a pool of popular repositories and inspects up to LEARN_TARGET of them (5,000 by default),
     saving every result to data/progress.jsonl.
  3. When LEARN_MILESTONE repositories (1,000) have been inspected, it writes data/feature_profile.json.
     From that moment FixREADME uses the findings. No restart is needed, because best_practices.py
     reads the file on every request.
  4. It refreshes the findings every LEARN_STEP repositories (500) and once more at the end.
  5. If you close the app, nothing is lost. The next launch reads progress.jsonl, uses the findings
     that already exist, and carries on from the repository where it stopped.

It never uses the whole GitHub quota: LEARN_RESERVE reads are always kept free for README requests.
"""
import json
import threading
from pathlib import Path

import trending_repos as tr
from config import LEARN_ENABLED, LEARN_MILESTONE, LEARN_RESERVE, LEARN_STEP, LEARN_TARGET, server_github_token
from local_ai import log

MIN_SCORE = 60.0
LOG_EVERY = 50
MAX_FAILURES = 5


class _Client(tr.GitHub):
    """GitHub client that reports through the app's log and keeps the terminal quiet while searching."""

    def log(self, message):
        if not message.startswith("Searching"):
            log(f"Learning: {message}")


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

    # ---- control -----------------------------------------------------------------------------

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

    # ---- work --------------------------------------------------------------------------------

    def _safe_run(self):
        try:
            self._run()
        except Exception as error:  # the web server must keep running whatever happens here
            self._set("error", f"Learning stopped: {error}")
            log(f"Learning stopped: {error}")

    def _client(self):
        if self._client_factory:
            return self._client_factory()
        return _Client(wait_for_limit=True, reserve=self.reserve, should_stop=self._stop.is_set)

    def _publish(self, records):
        """Write the JSON files. feature_profile.json is what the rest of the app reads."""
        tr.save_results(records, self.min_score, self.out_dir)
        self.in_use = True
        self.publishes += 1
        self._published_at = len(records)
        log(f"Learning: findings from {len(records)} repositories are saved and now used for new READMEs.")

    def _profile_exists(self):
        return (self.out_dir / "feature_profile.json").exists()

    def _prepare_progress_file(self, path):
        """A run that was killed mid-write can leave a half line. Start the next record on a fresh line."""
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

        if self.inspected >= self.milestone:
            self.in_use = self._profile_exists()
            if not self.in_use:
                self._publish(records)
        if self.inspected:
            log(f"Learning: continuing with {self.inspected} of {self.target} repositories already studied.")
        if self.inspected >= self.target:
            self._set("complete", f"Studied {self.inspected} repositories.")
            return

        self._set("collecting", "Looking for popular repositories.")
        log(f"Learning: building a pool of popular repositories (target {self.target}). This runs in the background.")
        try:
            candidates = tr.collect_candidates(gh, 20, None, None, target=self.target)
        except RuntimeError as error:
            self._set("paused", str(error))
            log(f"Learning paused: {error} It tries again the next time the app starts.")
            return
        if not candidates:
            self._set("paused", "No repositories were found. GitHub may be unreachable.")
            log("Learning paused: no repositories were found. It tries again the next time the app starts.")
            return
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
                except RuntimeError as error:
                    failures += 1
                    if "rejected" in str(error).lower() or failures >= MAX_FAILURES:
                        self._set("paused", str(error))
                        log(f"Learning paused: {error} It continues from here the next time the app starts.")
                        return
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
        learner._set("off", "Learning from top repositories is turned off (FIXREADME_LEARN=0).")
        return False
    if not server_github_token():
        learner._set("no_token", "Add GITHUB_TOKEN to .env to learn from top repositories in the background.")
        log("Learning from top repositories needs a GitHub token. Put GITHUB_TOKEN=... in the .env file to turn it on.")
        return False
    return learner.start()
