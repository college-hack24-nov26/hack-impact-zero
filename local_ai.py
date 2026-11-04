"""Starts the local Ollama server and downloads the small default model in the background.

Progress is printed to the terminal. The server's own log goes to ollama-serve.log so the
terminal stays readable. Nothing here can stop the web server: every failure becomes a status.
"""
import atexit
import json
import shutil
import subprocess
import threading
import time
from urllib.request import urlopen

from config import DEFAULT_OLLAMA_MODEL, OLLAMA_HOST, OLLAMA_LOG_PATH


def log(message):
    print(f"[FixREADME] {message}", flush=True)


class LocalAI:
    def __init__(self, model=DEFAULT_OLLAMA_MODEL):
        self.model = model
        self.state = "idle"
        self.message = "Local AI has not started yet."
        self.binary = None
        self._process = None
        self._started = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._started:
                return
            self._started = True
        threading.Thread(target=self._safe_setup, name="ollama-setup", daemon=True).start()

    def status(self):
        return {"state": self.state, "message": self.message, "model": self.model,
                "host": OLLAMA_HOST, "installed": bool(self.binary)}

    def _set(self, state, message):
        self.state, self.message = state, message

    def _safe_setup(self):
        try:
            self._setup()
        except Exception as error:  # the web server must keep running whatever happens here
            self._set("error", f"Local AI setup failed: {error}")
            log(f"Local AI setup failed: {error}")

    def _setup(self):
        self._set("checking", "Looking for Ollama on this computer.")
        log("Checking for Ollama...")
        self.binary = shutil.which("ollama")
        if not self.binary:
            self._set("missing", "Ollama is not installed. Install it from https://ollama.com for the free local model, or add an API key in Settings.")
            log("Ollama is not installed. Get it from https://ollama.com, then restart this app.")
            log("Until then, READMEs are built from repository evidence, or add an API key in Settings.")
            return
        log(f"Found Ollama: {self.binary}")

        if self._serving():
            log(f"Ollama is already running at {OLLAMA_HOST}.")
        else:
            self._set("starting", "Starting the Ollama server.")
            log("Starting 'ollama serve' ...")
            self._start_server()
            if not self._wait_for_server(40):
                self._set("error", "Ollama did not start in time. See ollama-serve.log in the project folder.")
                log("Ollama did not start in time. See ollama-serve.log for details.")
                return
            log(f"Ollama server is running at {OLLAMA_HOST}.")

        if self._has_model():
            self._set("ready", f"{self.model} is ready.")
            log(f"Model '{self.model}' is ready.")
            return

        self._set("pulling", f"Downloading {self.model}. This is a small one-time download.")
        log(f"Downloading model '{self.model}' (small, one time). Progress:")
        result = subprocess.run([self.binary, "pull", self.model])
        if result.returncode == 0 and self._has_model():
            self._set("ready", f"{self.model} is ready.")
            log(f"Model '{self.model}' is ready.")
        else:
            self._set("error", f"Model download failed. Run 'ollama pull {self.model}' manually.")
            log(f"Model download failed. Run: ollama pull {self.model}")

    def _serving(self):
        try:
            with urlopen(OLLAMA_HOST + "/api/tags", timeout=2) as response:
                return response.status == 200
        except (OSError, ValueError):
            return False

    def _start_server(self):
        log_file = open(OLLAMA_LOG_PATH, "ab")
        self._process = subprocess.Popen([self.binary, "serve"], stdout=log_file, stderr=subprocess.STDOUT)
        atexit.register(self._stop)
        log(f"ollama serve started (process {self._process.pid}). Its log: {OLLAMA_LOG_PATH.name}")

    def _wait_for_server(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._serving():
                return True
            if self._process and self._process.poll() is not None:
                return False
            time.sleep(1)
        return False

    def _has_model(self):
        try:
            with urlopen(OLLAMA_HOST + "/api/tags", timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError):
            return False
        names = {item.get("name", "") for item in data.get("models", [])}
        wanted = {self.model} if ":" in self.model else {self.model, self.model + ":latest"}
        return bool(names & wanted)

    def _stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()


local_ai = LocalAI()
