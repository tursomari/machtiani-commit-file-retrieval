import asyncio
import logging
from fastapi import APIRouter, HTTPException
from app.models.requests import CountTokenRequest
from lib.utils.enums import VCSType
from app.services.fetch_and_checkout_service import process_fetch_and_checkout  # Importing the service
from app.models.responses import LoadResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/fetch-and-checkout/token-count", response_model=LoadResponse)
async def count_tokens_fetch_and_checkout(
    data: CountTokenRequest
):
    project_name = url_to_folder_name(data.project_name)
    logger.info(f"data.project_name: {data.project_name}")
    try:
        embedding_tokens, inference_tokens = await process_repository_and_count_tokens(data)
        return LoadResponse(
            embedding_tokens=embedding_tokens,
            inference_tokens=inference_tokens
        )
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
