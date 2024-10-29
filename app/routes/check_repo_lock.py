from fastapi import Query, APIRouter, HTTPException
from pydantic import SecretStr, HttpUrl
from typing import Optional
import asyncio
import logging
from app.utils import DataDir
from lib.vcs.repo_manager import (
    get_repo_info_async,
    check_push_access,
)
from lib.utils.utilities import (
    url_to_folder_name,
    is_locked,
    get_lock_file_path,
)
router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/status")
@router.get("/status/")
async def check_repo_lock(
    codehost_url: HttpUrl = Query(..., description="Code host URL for the repository"),
    api_key: Optional[SecretStr] = Query(None, description="Optional API key for authentication")
):
    """ Check if the repo.lock file is present after verifying push access. """
    project_name = url_to_folder_name(str(codehost_url))  # Use the URL to create the folder name

    repo_info = await get_repo_info_async(str(codehost_url))
    logger.info(f"check_repo_lock get repo info: {repo_info}")

    # Check for push access
    has_push_access = await asyncio.to_thread(check_push_access, codehost_url, DataDir.REPO.get_path(project_name), project_name, repo_info['current_branch'], api_key)

    if not has_push_access:
        raise HTTPException(status_code=403, detail="User does not have push access to the repository.")

    lock_file_path = get_lock_file_path(project_name)

    lock_file_exists, lock_time_duration = await is_locked(lock_file_path)

    return {
        "lock_file_present": lock_file_exists,
        "lock_time_duration": lock_time_duration
    }
