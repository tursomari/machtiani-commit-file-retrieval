import asyncio
import logging
from fastapi import APIRouter, HTTPException
from app.models.requests import FetchAndCheckoutBranchRequest
from lib.utils.enums import VCSType
from app.services.fetch_and_checkout_service import process_fetch_and_checkout  # Importing the service
from app.models.responses import LoadResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/fetch-and-checkout/token-count", response_model=LoadResponse)
async def count_tokens_fetch_and_checkout(
    data: FetchAndCheckoutBranchRequest
):
    try:
        embedding_tokens, inference_tokens = await process_fetch_and_checkout(data)  # This now returns the token count directly
        return LoadResponse(
            embedding_tokens=embedding_tokens,
            inference_tokens=inference_tokens
        )
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error("An error occurred while processing token count: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
