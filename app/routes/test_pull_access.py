from fastapi import APIRouter, Query, HTTPException
from lib.utils.utilities import url_to_folder_name
from app.utils import DataDir
import asyncio
from pydantic import SecretStr
from lib.vcs.repo_manager import check_pull_access
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/test-pull-access/")
async def test_pull_access(
    project_name: str = Query(..., description="The name of the project"),
    codehost_api_key: SecretStr = Query(..., description="Code host API key for authentication"),
    codehost_url: str = Query(..., description="Code host URL for the repository"),
):
    """ Test pull access by checking if the user can pull from the repository. """
    try:
        _project_name = url_to_folder_name(project_name)
        destination_path = DataDir.REPO.get_path(_project_name)

        has_pull_access = await asyncio.to_thread(check_pull_access, codehost_url, destination_path, project_name, codehost_api_key)

        return {"pull_access": has_pull_access}
    except Exception as e:
        logger.error(f"Failed to check pull access for '{project_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")
