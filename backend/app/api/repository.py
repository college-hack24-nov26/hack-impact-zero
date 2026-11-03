from fastapi import APIRouter, HTTPException, Query
import httpx

from app.services.repository_service import parse_github_url
from app.services.github_service import get_repository_metadata
from app.services.repository_tree_service import get_repository_tree
from app.services.repository_analysis_service import analyze_repository_structure
from app.services.readme_service import get_repository_readme
from app.services.readme_analysis_service import analyze_readme


router = APIRouter(prefix="/api/repository", tags=["Repository"])


@router.get("/analyze")
async def analyze_repository(
    url: str = Query(..., description="Public GitHub repository URL")
):
    """Analyze repository metadata, structure, and README quality."""

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

        readme = await get_repository_readme(
            repository["owner"],
            repository["repository"],
        )

        readme_analysis = analyze_readme(readme["content"])

        return {
            "success": True,
            "repository": metadata,
            "analysis": analysis,
            "readme": readme,
            "readme_analysis": readme_analysis,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Unable to communicate with GitHub.",
        )