from fastapi import APIRouter, HTTPException, Query
import httpx

from app.services.repository_service import parse_github_url
from app.services.github_service import get_repository_metadata


router = APIRouter(prefix="/api/repository", tags=["Repository"])


@router.get("/analyze")
async def analyze_repository(
    url: str = Query(..., description="Public GitHub repository URL")
):
    """Parse a GitHub URL and retrieve repository metadata."""

    try:
        repository = parse_github_url(url)

        metadata = await get_repository_metadata(
            repository["owner"],
            repository["repository"],
        )

        return {
            "success": True,
            "repository": metadata,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Unable to communicate with GitHub.",
        )