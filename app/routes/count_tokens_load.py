import os
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Body
from app.services.count_tokens_service import count_tokens_load as service_count_tokens_load

# Initialize the router and logger
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/load/token-count")
async def count_tokens_load(
    load_request: dict = Body(..., description="Request body containing the OpenAI API key."),
):
    try:
        return await service_count_tokens_load(load_request)
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
