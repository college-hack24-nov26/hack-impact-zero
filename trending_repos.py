#!/usr/bin/env python3
"""Find trending, viral, famous, top and big-company GitHub repositories, extract the
README features that make them good, score them, and save the results as JSON.

Outputs (in ./data by default):
  repos_data.json         every repository that was inspected, with category tags, features and score
  best_repos.json         only repositories that reach --min-score, best first
  feature_profile.json    what the best repositories have in common (sections, badges, extras).
                          FixREADME reads this file to add useful sections to generated READMEs.

Usage:
  python trending_repos.py                       # defaults
  python trending_repos.py --limit 60 --min-score 65
  python trending_repos.py --orgs google microsoft vercel --token ghp_xxx
  python trending_repos.py --offline-sample sample.json   # score repos from a saved file

Collecting 1000 repositories (the default when a token is set):
  1. Create a token at https://github.com/settings/tokens (no permissions needed for public data).
  2. Put it in a file named .env next to this script:   GITHUB_TOKEN=your_token_here
     (.env is in .gitignore, so it is never uploaded). Or set the GITHUB_TOKEN variable.
  3. Run: python trending_repos.py
The program waits for GitHub's rate limit to reset instead of stopping, saves progress after every
repository, and continues where it left off if you stop it (Ctrl+C) and run it again.
Only the Python standard library is used. The token is sent only to api.github.com and is never
printed or written to any file.
"""
import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from config import clean_token, server_github_token

API = "https://api.github.com"
USER_AGENT = "FixREADME-Trending/1.0"
DATA_DIR = Path(__file__).resolve().parent / "data"

BIG_COMPANY_ORGS = [
    "google", "microsoft", "facebook", "apple", "aws", "netflix", "uber", "airbnb", "vercel",
    "openai", "anthropics", "huggingface", "nvidia", "meta-llama", "vuejs", "pallets",
    "tiangolo", "psf", "shopify", "stripe", "spotify", "twitter", "linkedin", "alibaba",
]

CATEGORY_LABELS = ("trending", "viral", "famous", "top", "big_company")

# README sections worth tracking: feature name -> heading regex
SECTION_PATTERNS = {
    "table_of_contents": r"table of contents|contents|toc",
    "features": r"features|key features|highlights|what it does|why\b",
    "installation": r"install\w*|getting started|quick ?start|setup",
    "usage": r"usage|how to use|examples?|quick ?start|tutorial",
    "prerequisites": r"prerequisites|requirements|before you begin",
    "documentation": r"documentation|docs|guide|api reference",
    "configuration": r"configuration|config|environment|settings|options",
    "screenshots_demo": r"screenshots?|demo|preview|gallery|showcase",
    "roadmap": r"roadmap|todo|planned|future",
    "contributing": r"contribut\w*",
    "support": r"support|sponsor\w*|donate|funding|help|community",
    "faq": r"faq|frequently asked|troubleshooting",
    "license": r"licen[sc]e",
    "acknowledgements": r"acknowledg\w*|credits|thanks|inspiration",
    "changelog": r"changelog|release notes|what's new|history",
    "security": r"security",
    "code_of_conduct": r"code of conduct",
    "tech_stack": r"tech(nolog\w*)?|built with|stack|dependencies",
    "project_structure": r"(project |folder |directory )?(structure|layout)|architecture|how it works",
}


# --------------------------------------------------------------------------------------
# GitHub access
# --------------------------------------------------------------------------------------

class GitHub:
    SEARCH_GAP = 2.2          # the search API allows 30 requests per minute with a token

    def __init__(self, token=None, pause=0.0, verbose=True, wait_for_limit=True, max_wait=3900, sleep=time.sleep):
        self.token = clean_token(token) if token else server_github_token()
        self.pause = pause
        self.verbose = verbose
        self.wait_for_limit = wait_for_limit
        self.max_wait = max_wait
        self.sleep = sleep
        self.remaining = None
        self._last_search = 0.0

    def log(self, message):
        if self.verbose:
            print(f"[trending] {message}", file=sys.stderr, flush=True)

    def _request(self, url, accept="application/vnd.github+json", timeout=20):
        headers = {"Accept": accept, "User-Agent": USER_AGENT, "X-GitHub-Api-Version": "2022-11-28"}
        # The token goes only to the GitHub API, never to raw.githubusercontent.com or other hosts.
        if self.token and url.startswith(API):
            headers["Authorization"] = f"Bearer {self.token}"
        return urlopen(Request(url, headers=headers), timeout=timeout)

    def _wait_seconds(self, error):
        """Seconds to wait after a 403/429, or None if this is not a rate limit."""
        headers = error.headers or {}
        retry_after = headers.get("Retry-After", "")
        if retry_after.isdigit():
            return int(retry_after) + 1
        if headers.get("X-RateLimit-Remaining") == "0":
            reset = headers.get("X-RateLimit-Reset", "")
            if reset.isdigit():
                return max(1, int(reset) - int(time.time())) + 2
            return 60
        return None

    def get_json(self, path, params="", search=False):
        url = API + path + (("?" + params) if params else "")
        failures = 0
        while True:
            if search:
                gap = self.SEARCH_GAP - (time.time() - self._last_search)
                if gap > 0:
                    self.sleep(gap)
                self._last_search = time.time()
            try:
                with self._request(url) as response:
                    remaining = response.headers.get("X-RateLimit-Remaining")
                    self.remaining = int(remaining) if remaining and remaining.isdigit() else self.remaining
                    data = json.loads(response.read().decode("utf-8"))
                if self.pause:
                    self.sleep(self.pause)
                return data
            except HTTPError as error:
                if error.code == 401:
                    raise RuntimeError("GitHub rejected the token. Check GITHUB_TOKEN in your .env file.") from None
                if error.code in (403, 429):
                    wait = self._wait_seconds(error)
                    if wait is not None:
                        if not self.wait_for_limit or wait > self.max_wait:
                            raise RuntimeError(
                                f"GitHub rate limit reached; it resets in about {wait // 60 + 1} minutes. "
                                "Run the program again later; it continues where it stopped."
                                + ("" if self.token else " Set GITHUB_TOKEN to raise the limit.")) from None
                        self.log(f"Rate limit reached. Waiting {wait // 60 + 1} minute(s) for it to reset...")
                        self.sleep(wait)
                        continue
                if error.code == 404:
                    return None
                failures += 1
                if failures < 3 and error.code >= 500:
                    self.sleep(2 * failures)
                    continue
                raise RuntimeError(f"GitHub returned HTTP {error.code} for {path}") from None
            except (URLError, TimeoutError, OSError):
                failures += 1
                if failures < 3:
                    self.sleep(2 * failures)
                    continue
                raise RuntimeError("Could not reach GitHub. Check your internet connection.") from None
            except ValueError:
                return None

    def search_repos(self, query, sort="stars", per_page=30, pages=1):
        """Up to per_page * pages results (the search API stops at 1000 per query)."""
        items = []
        for page in range(1, pages + 1):
            params = f"q={quote(query)}&sort={sort}&order=desc&per_page={min(per_page, 100)}&page={page}"
            batch = (self.get_json("/search/repositories", params, search=True) or {}).get("items", [])
            items.extend(batch)
            if len(batch) < min(per_page, 100):
                break
        return items

    def readme(self, full_name):
        data = self.get_json(f"/repos/{full_name}/readme")
        if not data or not data.get("download_url"):
            return ""
        try:
            with self._request(data["download_url"], accept="text/plain") as response:
                return response.read(400_000).decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError):
            return ""

    def root_files(self, full_name):
        data = self.get_json(f"/repos/{full_name}/contents")
        if not isinstance(data, list):
            return []
        return [item.get("name", "") for item in data]


# --------------------------------------------------------------------------------------
# Collecting candidates
# --------------------------------------------------------------------------------------

def _days_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


STAR_BANDS = ["stars:>=100000", "stars:60000..99999", "stars:40000..59999", "stars:30000..39999",
              "stars:20000..29999", "stars:15000..19999", "stars:10000..14999", "stars:7000..9999",
              "stars:5000..6999", "stars:3000..4999"]


def collect_candidates(gh, per_source=20, orgs=None, languages=None, target=None):
    """Return {full_name: {"repo": api_item, "categories": set()}}.

    With a large target (for example 1000) the star bands are searched page by page so the pool
    holds well over `target` repositories before the best ones are selected.
    """
    found = {}
    big = bool(target and target > 100)
    pages = 3 if big else 1
    per_page = 100 if big else per_source

    def add(items, category):
        for item in items or []:
            name = item.get("full_name")
            if not name or item.get("fork") or item.get("archived"):
                continue
            entry = found.setdefault(name, {"repo": item, "categories": set()})
            entry["categories"].add(category)

    def search(label, query, category, pages_=1):
        gh.log(f"Searching {label}...")
        try:
            add(gh.search_repos(query, "stars", per_page, pages_), category)
        except RuntimeError as error:
            if "rate limit" in str(error).lower() or "rejected" in str(error).lower():
                raise
            gh.log(f"Skipped {label}: {error}")

    if big:
        for band in STAR_BANDS:
            search(f"top repositories ({band})", band, "top", pages)
    else:
        search("top (most starred) repositories", "stars:>50000", "top")
    search("famous (well-known, active) repositories", f"stars:>10000 pushed:>{_days_ago(30)}", "famous", pages)
    search("trending (new and rising) repositories", f"created:>{_days_ago(30)} stars:>300", "trending", pages)
    search("viral (fast-growing) repositories", f"created:>{_days_ago(90)} stars:>2000", "viral", pages)
    if big:
        search("rising repositories of the last year", f"created:>{_days_ago(365)} stars:>5000", "trending", pages)
    for language in languages or []:
        search(f"trending {language} repositories", f"language:{language} created:>{_days_ago(60)} stars:>200",
               "trending", pages)
    for org in orgs if orgs is not None else BIG_COMPANY_ORGS:
        search(f"big-company organisation {org}", f"org:{org}", "big_company", 2 if big else 1)
    return found


def select_candidates(found, limit):
    """Keep repositories that match several categories first, then the most starred."""
    ranked = sorted(found.items(),
                    key=lambda kv: (len(kv[1]["categories"]), kv[1]["repo"].get("stargazers_count", 0)),
                    reverse=True)
    return ranked[:limit]


# --------------------------------------------------------------------------------------
# Feature extraction from a README
# --------------------------------------------------------------------------------------

BADGE_RE = re.compile(r"!\[[^\]]*\]\((?:https?://)?[^)]*(?:shields\.io|badge|badgen|travis-ci|codecov|coveralls)[^)]*\)", re.I)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)|<img\s", re.I)
CODE_FENCE_RE = re.compile(r"(?m)^```")
HEADING_RE = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*#*\s*$")


def readme_headings(text):
    return [re.sub(r"[*_`]|<[^>]+>|\[([^\]]*)\]\([^)]*\)", r"\1", h).strip()
            for h in HEADING_RE.findall(text or "")]


def extract_features(text):
    """Describe what a README contains. Pure function: easy to test, no network."""
    text = text or ""
    headings = readme_headings(text)
    lowered = [re.sub(r"[^\w\s'&/+.-]", "", h).strip().lower() for h in headings]
    sections = {}
    for name, pattern in SECTION_PATTERNS.items():
        sections[name] = any(re.match(rf"^(?:{pattern})\b", h) or re.search(rf"\b(?:{pattern})\b", h)
                             for h in lowered)
    if re.search(r"(?m)^\s*[-*]\s+\[[^\]]+\]\(#[^)]+\)", text):
        sections["table_of_contents"] = True
    badges = BADGE_RE.findall(text)
    return {
        "length_chars": len(text),
        "heading_count": len(headings),
        "headings": headings[:40],
        "sections": sections,
        "badge_count": len(badges),
        "image_count": max(0, len(IMAGE_RE.findall(text)) - len(badges)),
        "code_block_count": len(CODE_FENCE_RE.findall(text)) // 2,
        "has_table": bool(re.search(r"(?m)^\|.+\|\s*\n\|[\s:|-]+\|", text)),
        "has_emoji_headings": any(re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", h) for h in headings),
        "has_centered_header": bool(re.search(r"<(?:p|div|h1)[^>]*align=[\"']center", text, re.I)),
        "has_collapsible": "<details" in text.lower(),
        "link_count": len(re.findall(r"\[[^\]]+\]\(https?://", text)),
        "feature_bullets": feature_bullets(text),
    }


def feature_bullets(text, limit=12):
    """Bullet points under a 'Features'-style heading."""
    bullets, active = [], False
    for line in (text or "").splitlines():
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading:
            active = bool(re.search(r"\b(features?|highlights?|why)\b", heading.group(1), re.I))
            continue
        if active:
            match = re.match(r"^\s*[-*+]\s+(.+)$", line)
            if match:
                clean = re.sub(r"[*_`]|\[([^\]]*)\]\([^)]*\)", r"\1", match.group(1)).strip()
                if 8 <= len(clean) <= 160:
                    bullets.append(clean)
                if len(bullets) >= limit:
                    break
    return bullets


def repo_signals(repo, root_files):
    """Project-level signals that make a repository trustworthy."""
    names = {n.lower() for n in root_files}
    return {
        "has_license": bool((repo.get("license") or {}).get("spdx_id")) or any(n.startswith(("license", "licence")) for n in names),
        "has_ci": ".github" in names or ".travis.yml" in names or ".circleci" in names,
        "has_docker": "dockerfile" in names or "docker-compose.yml" in names,
        "has_contributing": "contributing.md" in names,
        "has_code_of_conduct": "code_of_conduct.md" in names,
        "has_security_policy": "security.md" in names,
        "has_changelog": any(n.startswith(("changelog", "changes", "history")) for n in names),
        "has_tests_dir": any(n in names for n in ("tests", "test", "__tests__", "spec")),
        "has_docs_dir": "docs" in names or "documentation" in names,
        "has_examples_dir": "examples" in names or "example" in names,
    }


# --------------------------------------------------------------------------------------
# Scoring (0 to 100)
# --------------------------------------------------------------------------------------

WEIGHTS = {"popularity": 25, "momentum": 15, "community": 10, "maintenance": 15,
           "readme": 25, "project": 10}


def _scale(value, full):
    """Log scale 0..1: reaches 1.0 when value >= full."""
    if value <= 0:
        return 0.0
    return min(1.0, math.log10(value + 1) / math.log10(full + 1))


def _age_days(iso):
    try:
        then = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - then).total_seconds() / 86400)


def score_repo(repo, features, signals, categories):
    """Return (total, breakdown). Every component is explained so scores can be audited."""
    stars = repo.get("stargazers_count", 0) or 0
    forks = repo.get("forks_count", 0) or 0
    watchers = repo.get("subscribers_count") or repo.get("watchers_count", 0) or 0
    issues = repo.get("open_issues_count", 0) or 0
    age = _age_days(repo.get("created_at"))
    since_push = _age_days(repo.get("pushed_at"))

    popularity = _scale(stars, 200_000)
    stars_per_day = stars / max(age or 1, 1)
    momentum = _scale(stars_per_day, 300)
    if "trending" in categories or "viral" in categories:
        momentum = min(1.0, momentum + 0.15)

    fork_ratio = min(1.0, (forks / stars) * 4) if stars else 0.0
    community = 0.5 * _scale(forks, 30_000) + 0.2 * _scale(watchers, 5_000) + 0.3 * fork_ratio
    if issues:  # an active issue tracker shows real use
        community = min(1.0, community + 0.05)

    if repo.get("archived"):
        maintenance = 0.0
    elif since_push is None:
        maintenance = 0.3
    elif since_push <= 14:
        maintenance = 1.0
    elif since_push <= 60:
        maintenance = 0.8
    elif since_push <= 180:
        maintenance = 0.5
    elif since_push <= 365:
        maintenance = 0.25
    else:
        maintenance = 0.05

    s = features["sections"]
    readme = 0.0
    readme += 0.18 * (1 if s.get("installation") else 0)
    readme += 0.14 * (1 if s.get("usage") else 0)
    readme += 0.10 * (1 if s.get("features") else 0)
    readme += 0.06 * (1 if s.get("table_of_contents") else 0)
    readme += 0.06 * (1 if s.get("contributing") else 0)
    readme += 0.05 * (1 if s.get("license") else 0)
    readme += 0.05 * (1 if s.get("documentation") or s.get("configuration") else 0)
    readme += 0.05 * (1 if s.get("faq") or s.get("roadmap") or s.get("support") else 0)
    readme += 0.06 * min(1.0, features["badge_count"] / 4)
    readme += 0.07 * min(1.0, features["image_count"] / 2)
    readme += 0.08 * min(1.0, features["code_block_count"] / 4)
    readme += 0.05 * min(1.0, features["length_chars"] / 4000)
    readme += 0.05 * (1 if features["has_table"] else 0)
    readme = min(1.0, readme)
    if features["length_chars"] < 300:
        readme *= 0.3

    flags = [signals[k] for k in ("has_license", "has_ci", "has_tests_dir", "has_contributing",
                                  "has_docs_dir", "has_examples_dir", "has_changelog", "has_security_policy")]
    project = sum(flags) / len(flags)

    parts = {"popularity": popularity, "momentum": momentum, "community": community,
             "maintenance": maintenance, "readme": readme, "project": project}
    breakdown = {k: round(v * WEIGHTS[k], 2) for k, v in parts.items()}
    total = round(sum(breakdown.values()), 2)
    if "big_company" in categories:
        total = round(min(100.0, total + 2.0), 2)
        breakdown["big_company_bonus"] = 2.0
    return total, breakdown


# --------------------------------------------------------------------------------------
# Building records and the feature profile
# --------------------------------------------------------------------------------------

def build_record(repo, readme_text, root_files, categories):
    features = extract_features(readme_text)
    signals = repo_signals(repo, root_files)
    categories = sorted(categories, key=CATEGORY_LABELS.index) if categories else []
    score, breakdown = score_repo(repo, features, signals, set(categories))
    return {
        "full_name": repo.get("full_name"),
        "url": repo.get("html_url") or f"https://github.com/{repo.get('full_name')}",
        "description": repo.get("description") or "",
        "language": repo.get("language"),
        "topics": repo.get("topics", []),
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "created_at": repo.get("created_at"),
        "pushed_at": repo.get("pushed_at"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "categories": categories,
        "score": score,
        "score_breakdown": breakdown,
        "readme_features": features,
        "project_signals": signals,
    }


def build_feature_profile(best, total_inspected):
    """What the best repositories have in common. Used by FixREADME to add sections."""
    n = len(best)
    if not n:
        return {"based_on_repos": 0, "inspected": total_inspected, "sections": {}, "recommended_sections": [], "style": {}, "common_headings": []}
    section_counts = Counter()
    for record in best:
        for name, present in record["readme_features"]["sections"].items():
            if present:
                section_counts[name] += 1
    sections = {name: {"count": section_counts[name], "share": round(section_counts[name] / n, 2)}
                for name in SECTION_PATTERNS}
    ordered = dict(sorted(sections.items(), key=lambda kv: -kv[1]["share"]))

    def average(key):
        return round(sum(r["readme_features"][key] for r in best) / n, 1)

    def share(key):
        return round(sum(1 for r in best if r["readme_features"][key]) / n, 2)

    signal_share = {k: round(sum(1 for r in best if r["project_signals"][k]) / n, 2)
                    for k in best[0]["project_signals"]}
    heading_counts = Counter()
    position = {name: [] for name in SECTION_PATTERNS}
    for record in best:
        features = record["readme_features"]
        for h in {re.sub(r"[^\w\s'&/+.-]", "", x).strip().lower() for x in features["headings"]}:
            if 2 < len(h) < 40:
                heading_counts[h] += 1
    words = Counter()
    for record in best:
        for bullet in record["readme_features"]["feature_bullets"]:
            for word in re.findall(r"[a-z][a-z-]{3,}", bullet.lower()):
                words[word] += 1
    stop = {"with", "that", "this", "from", "your", "have", "also", "support", "supports", "using", "into",
            "more", "than", "most", "many", "easy", "based", "built", "like", "when", "which", "every"}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "based_on_repos": n,
        "inspected": total_inspected,
        "sections": ordered,
        "recommended_sections": [name for name, info in ordered.items() if info["share"] >= 0.5],
        "common_headings": [h for h, _ in heading_counts.most_common(25)],
        "style": {
            "average_badges": average("badge_count"),
            "average_images": average("image_count"),
            "average_code_blocks": average("code_block_count"),
            "average_readme_chars": average("length_chars"),
            "share_with_table": share("has_table"),
            "share_with_emoji_headings": share("has_emoji_headings"),
            "share_with_centered_header": share("has_centered_header"),
            "share_with_collapsible_blocks": share("has_collapsible"),
        },
        "project_signals": signal_share,
        "common_feature_words": [w for w, _ in words.most_common(30) if w not in stop][:20],
    }


# --------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def save_results(records, min_score, out_dir):
    out_dir = Path(out_dir)
    records = sorted(records, key=lambda r: r["score"], reverse=True)
    best = [r for r in records if r["score"] >= min_score]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json(out_dir / "repos_data.json", {
        "generated_at": now, "count": len(records), "weights": WEIGHTS, "repos": records})
    write_json(out_dir / "best_repos.json", {
        "generated_at": now, "min_score": min_score, "count": len(best), "repos": best})
    profile = build_feature_profile(best, len(records))
    write_json(out_dir / "feature_profile.json", profile)
    return records, best, profile


def load_progress(path):
    """Records saved by an earlier, interrupted run (one JSON object per line)."""
    done = {}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("full_name"):
                done[record["full_name"]] = record
    except OSError:
        pass
    return done


def run(args):
    gh = GitHub(args.token, pause=args.pause, wait_for_limit=not args.no_wait)
    out = Path(args.out)

    if args.offline_sample:
        sample = json.loads(Path(args.offline_sample).read_text(encoding="utf-8"))
        records = [build_record(item["repo"], item.get("readme", ""), item.get("root_files", []),
                                set(item.get("categories", []))) for item in sample]
        return save_results(records, args.min_score, out)

    limit = args.limit or (1000 if gh.token else 40)
    if gh.token:
        gh.log("Using the GitHub token from GITHUB_TOKEN / .env (it is never printed or saved).")
    else:
        gh.log("No GitHub token found: limited to 60 requests per hour, so the target is 40 repositories. "
               "Put GITHUB_TOKEN=... in a .env file to collect 1000.")

    progress_path = out / "progress.jsonl"
    done = {} if args.fresh else load_progress(progress_path)
    if args.fresh and progress_path.exists():
        progress_path.unlink()
    if done:
        gh.log(f"Continuing: {len(done)} repositories were already inspected in an earlier run.")

    candidates = collect_candidates(gh, args.per_source, args.orgs, args.language, target=limit)
    selected = select_candidates(candidates, limit)
    gh.log(f"Pool: {len(candidates)} repositories. Inspecting the best {len(selected)}...")

    records = list(done.values())
    out.mkdir(parents=True, exist_ok=True)
    todo = [(n, e) for n, e in selected if n not in done]
    try:
        with open(progress_path, "a", encoding="utf-8") as progress:
            for index, (name, entry) in enumerate(todo, 1):
                try:
                    readme = gh.readme(name)
                    files = gh.root_files(name)
                except RuntimeError as error:
                    gh.log(f"Stopped early: {error}")
                    break
                record = build_record(entry["repo"], readme, files, entry["categories"])
                records.append(record)
                progress.write(json.dumps(record, ensure_ascii=False) + "\n")
                progress.flush()
                gh.log(f"[{index}/{len(todo)}] {name}  score {record['score']}  {','.join(record['categories'])}")
                if index % 50 == 0:
                    save_results(records, args.min_score, out)   # partial results stay usable
    except KeyboardInterrupt:
        gh.log("Interrupted. Saving what was collected; run again to continue.")
    if not records:
        raise SystemExit("No repositories could be inspected. Check your connection and your token.")
    return save_results(records, args.min_score, out)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Score trending, viral, famous, top and big-company GitHub repositories.")
    p.add_argument("--limit", type=int, default=None,
                   help="repositories to inspect (default: 1000 with a token, 40 without)")
    p.add_argument("--per-source", type=int, default=20, help="results per search (default 20)")
    p.add_argument("--min-score", type=float, default=60.0, help="score needed to enter best_repos.json (default 60)")
    p.add_argument("--orgs", nargs="*", default=None, help="company organisations to include (default: a built-in list)")
    p.add_argument("--language", nargs="*", default=None, help="also search trending repos in these languages")
    p.add_argument("--token", default=None,
                   help="GitHub token. Prefer GITHUB_TOKEN in .env: a token typed here can show up in shell history")
    p.add_argument("--no-wait", action="store_true", help="stop at the rate limit instead of waiting for it to reset")
    p.add_argument("--fresh", action="store_true", help="ignore saved progress and start over")
    p.add_argument("--pause", type=float, default=0.0, help="seconds to wait between requests")
    p.add_argument("--out", default=str(DATA_DIR), help="output folder (default ./data)")
    p.add_argument("--offline-sample", default=None, help="score repositories from a saved JSON file instead of GitHub")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        records, best, profile = run(args)
    except RuntimeError as error:
        raise SystemExit(f"Error: {error}")
    out = Path(args.out)
    print(f"\nInspected {len(records)} repositories; {len(best)} scored {args.min_score:g} or higher.")
    print(f"  {out / 'repos_data.json'}\n  {out / 'best_repos.json'}\n  {out / 'feature_profile.json'}")
    for record in best[:10]:
        print(f"  {record['score']:5.1f}  {record['full_name']}  ({record['stars']:,} stars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
