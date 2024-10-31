import asyncio
import logging
from fastapi import APIRouter, HTTPException
from lib.utils.enums import VCSType, FetchAndCheckoutBranchRequest
from app.services.fetch_and_checkout_service import process_fetch_and_checkout  # Importing the service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/fetch-and-checkout/token-count")
async def count_tokens_fetch_and_checkout(
    data: FetchAndCheckoutBranchRequest,
):
    try:
        token_count = await process_fetch_and_checkout(data)  # This now returns the token count directly
        return token_count  # Return the token count directly
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error("An error occurred while processing token count: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

