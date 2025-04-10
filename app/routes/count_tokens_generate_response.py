import os
import logging
from fastapi import APIRouter, Body, HTTPException
from app.utils import count_tokens
from app.models.responses import LoadResponse

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/generate-response/token-count", response_model=LoadResponse)
async def count_tokens_generate_response(
    prompt: str = Body(..., description="The prompt to search for"),
    project: str = Body(..., description="The project to search"),
    mode: str = Body(..., description="Search mode: chat, pure-chat, or default"),
    model: str = Body(..., description="The embedding model used"),
    match_strength: str = Body(..., description="The strength of the match"),
):
    """ Count tokens for a given prompt to be used in generating a response. """
    try:
        embedding_tokens, inference_tokens = count_tokens(prompt)
        return LoadResponse(
            embedding_tokens=embedding_tokens,
            inference_tokens=inference_tokens
        )
    except Exception as e:
        logger.error(f"An error occurred while counting tokens: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
