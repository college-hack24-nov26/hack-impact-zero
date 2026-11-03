from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.readme_analysis_service import analyze_and_score_readme
from app.services.readme_badge_service import generate_tech_badges
from app.services.readme_generation_service import generate_beautified_readme
from app.services.github_service import fetch_github_repository_data

router = APIRouter()

class EnhanceRequest(BaseModel):
    readme_content: Optional[str] = ""
    github_url: Optional[str] = ""
    tech_stack: Optional[List[str]] = ["python", "fastapi", "react"]
    groq_api_key: Optional[str] = ""

@router.post("/process-readme")
def process_readme(payload: EnhanceRequest):
    readme_text = payload.readme_content or ""
    detected_stack = payload.tech_stack or []
    owner, repo_name = None, "Project"

    if payload.github_url:
        gh_data = fetch_github_repository_data(payload.github_url)
        if "error" in gh_data:
            raise HTTPException(status_code=400, detail=gh_data["error"])
        readme_text = gh_data["readme_content"]
        detected_stack = list(set(detected_stack + gh_data["detected_stack"]))
        owner, repo_name = gh_data["owner"], gh_data["repo"]

    if not readme_text.strip():
        readme_text = "# Sample Project\n\nInitial repository context."

    original_analysis = analyze_and_score_readme(readme_text)
    badges = generate_tech_badges(detected_stack, repo_owner=owner, repo_name=repo_name)

    beautified_content = generate_beautified_readme(
        readme_text, 
        original_analysis, 
        badges,
        repo_name=repo_name,
        custom_api_key=payload.groq_api_key
    )

    improved_analysis = analyze_and_score_readme(beautified_content)

    return {
        "repo_name": repo_name,
        "original_readme": readme_text,
        "beautified_readme": beautified_content,
        "detected_stack": detected_stack,
        "original_score": original_analysis["score"],
        "improved_score": improved_analysis["score"],
        "missing_features": original_analysis["missing_features"],
        "present_features": original_analysis["present_features"]
    }
