import logging
from fastapi import APIRouter, HTTPException
from app.services.count_tokens_service import process_repository_and_count_tokens
from lib.utils.enums import AddRepositoryRequest

# Setting up the router and logger
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/add-repository/token-count")
async def count_tokens_add_repository(
    data: AddRepositoryRequest,
):
    try:
        token_count = await process_repository_and_count_tokens(data)
        return token_count
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
