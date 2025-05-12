from fastapi import Query, APIRouter, HTTPException
from pydantic import SecretStr, HttpUrl
from typing import Optional
import logging
from app.services.status_service import status_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/status")
@router.get("/status/")
async def status_route(
    codehost_url: HttpUrl = Query(..., description="Code host URL for the repository"),
    # Should also have a codehost_api_key, to validate user has access?
):
    """ Check if the repo.lock file is present after verifying push access. """
    try:
        return await status_service(codehost_url)
    except Exception as e:
        logger.error(f"Error checking repo lock: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
