import json
import os
import re

BENCHMARK_FILE = os.path.join(os.path.dirname(__file__), "../../../docs/benchmark_patterns.json")

def analyze_and_score_readme(readme_content: str) -> dict:
    if not os.path.exists(BENCHMARK_FILE):
        return {"score": 0, "present_features": [], "missing_features": []}

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        benchmarks = json.load(f)["essential_sections"]

    current_score = 0
    max_score = sum(item["weight"] for item in benchmarks)
    present_features = []
    missing_features = []

    for item in benchmarks:
        if re.search(item["pattern"], readme_content):
            current_score += item["weight"]
            present_features.append(item["name"])
        else:
            missing_features.append(item["name"])

    normalized_score = round((current_score / max_score) * 100) if max_score > 0 else 0

    return {
        "score": normalized_score,
        "present_features": present_features,
        "missing_features": missing_features
    }
