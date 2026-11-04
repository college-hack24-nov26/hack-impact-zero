"""Which README sections do the best repositories use?

`python trending_repos.py` writes data/feature_profile.json from the top-scoring repositories.
This module reads that file. If it does not exist yet, a built-in profile is used, so the app
works the same way before the first run.
"""
import json

from config import BASE_DIR

PROFILE_PATH = BASE_DIR / "data" / "feature_profile.json"

# Sections that nearly every well-regarded README has. Used until the first trending run.
DEFAULT_RECOMMENDED = [
    "features", "installation", "usage", "table_of_contents", "prerequisites",
    "contributing", "license", "support",
]


def load_profile(path=PROFILE_PATH):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("based_on_repos") else None


def recommended_sections(path=PROFILE_PATH):
    """Section names (e.g. 'contributing') that at least half of the best repositories include."""
    profile = load_profile(path)
    if profile and profile.get("recommended_sections"):
        return list(profile["recommended_sections"])
    return list(DEFAULT_RECOMMENDED)


def profile_summary(path=PROFILE_PATH):
    """Short description of where the recommendations come from, for the UI or logs."""
    profile = load_profile(path)
    if profile:
        return f"Based on {profile['based_on_repos']} top-scoring repositories (data/feature_profile.json)."
    return "Built-in defaults. Run `python trending_repos.py` to learn from top-scoring repositories."
