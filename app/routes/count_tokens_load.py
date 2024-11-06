import os
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Body
from app.services.count_tokens_service import count_tokens_load as service_count_tokens_load
from app.models.requests import LoadRequest
from app.models.responses import LoadResponse

# Initialize the router and logger
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/load/token-count", response_model=LoadResponse)
async def count_tokens_load(load_request: LoadRequest):
    try:
        embedding_tokens, inference_tokens = await service_count_tokens_load(load_request)
        return LoadResponse(
            embedding_tokens=embedding_tokens,
            inference_tokens=inference_tokens
        )
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
