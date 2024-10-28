from fastapi import APIRouter, Query, HTTPException
from lib.vcs.repo_manager import get_repo_info_async
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/get-project-info/")
async def get_project_info(
    project: str = Query(..., description="The name of the project"),
    api_key: str = Query(..., description="OpenAI API key")
):
    """ Get project information including the remote URL and the current git branch. """
    try:
        result = await get_repo_info_async(project, api_key)
        return result
    except Exception as e:
        logger.error(f"Failed to get project info for '{project}': {e}")
        raise HTTPException(status_code=500, detail=str(e))
