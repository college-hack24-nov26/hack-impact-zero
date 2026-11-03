from fastapi import APIRouter, HTTPException, Query
import httpx

from app.services.repository_service import parse_github_url
from app.services.github_service import get_repository_metadata
from app.services.repository_tree_service import get_repository_tree
from app.services.repository_analysis_service import analyze_repository_structure


router = APIRouter(prefix="/api/repository", tags=["Repository"])


@router.get("/analyze")
async def analyze_repository(
    url: str = Query(..., description="Public GitHub repository URL")
):
    """Analyze GitHub repository metadata and project structure."""

    try:
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

        return {
            "success": True,
            "repository": metadata,
            "analysis": analysis,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Unable to communicate with GitHub.",
        )