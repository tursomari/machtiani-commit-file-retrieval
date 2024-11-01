from fastapi import Query, APIRouter, HTTPException
from pydantic import SecretStr, HttpUrl
from typing import Optional
import logging
from app.services.check_repo_lock_service import check_repo_lock  # Import the service function

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/status")
@router.get("/status/")
async def check_repo_lock_route(
    codehost_url: HttpUrl = Query(..., description="Code host URL for the repository"),
    api_key: Optional[SecretStr] = Query(None, description="Optional API key for authentication")
):
    """ Check if the repo.lock file is present after verifying push access. """
    try:
        return await check_repo_lock(codehost_url, api_key)
    except Exception as e:
        logger.error(f"Error checking repo lock: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
