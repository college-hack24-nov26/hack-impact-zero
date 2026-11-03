
from fastapi import APIRouter, HTTPException, Query
import httpx

from app.services.repository_service import parse_github_url
from app.services.github_service import get_repository_metadata
from app.services.repository_tree_service import get_repository_tree
from app.services.repository_analysis_service import analyze_repository_structure
from app.services.readme_service import get_repository_readme
from app.services.readme_analysis_service import analyze_readme
from app.services.readme_recommendation_service import (
    generate_readme_recommendations,
)
from app.services.readme_generation_service import generate_readme


router = APIRouter(prefix="/api/repository", tags=["Repository"])


async def collect_repository_data(url: str):
    """Collect repository metadata, structure, and README."""

    repository = parse_github_url(url)

    metadata = await get_repository_metadata(
        repository["owner"],
        repository["repository"],
    )

    tree = await get_repository_tree(
        repository["owner"],
        repository["repository"],
        metadata["default_branch"],
    )

    analysis = analyze_repository_structure(tree)

    readme = await get_repository_readme(
        repository["owner"],
        repository["repository"],
    )

    return metadata, analysis, readme


@router.get("/analyze")
async def analyze_repository(
    url: str = Query(..., description="Public GitHub repository URL")
):
    """Analyze repository metadata, structure, and README quality."""

    try:
        metadata, analysis, readme = await collect_repository_data(url)

        readme_analysis = analyze_readme(readme["content"])

        recommendations = generate_readme_recommendations(
            readme_analysis
        )

        return {
            "success": True,
            "repository": metadata,
            "analysis": analysis,
            "readme": readme,
            "readme_analysis": readme_analysis,
            "recommendations": recommendations,
            "recommendation_count": len(recommendations),
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Unable to communicate with GitHub.",
        )


@router.post("/generate")
async def generate_repository_readme(
    url: str = Query(..., description="Public GitHub repository URL")
):
    """Generate an improved README using local Ollama."""

    try:
        metadata, analysis, readme = await collect_repository_data(url)

        try:
            generated = await generate_readme(
                repository=metadata,
                analysis=analysis,
                existing_readme=readme["content"],
            )
        except ValueError as error:
            raise HTTPException(
                status_code=502,
                detail=f"README generation failed: {error}",
            )

        return {
            "success": True,
            "repository": metadata["full_name"],
            "generated_readme": generated["content"],
            "model": generated["model"],
            "provider": generated["provider"],
            "word_count": generated["word_count"],
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Unable to communicate with GitHub or local Ollama.",
        )
