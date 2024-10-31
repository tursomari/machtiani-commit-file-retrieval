import os
import logging
from fastapi import FastAPI, APIRouter, Body
from typing import Optional, List, Dict
from app.utils import count_tokens

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/generate-response/token-count")
async def count_tokens_generate_response(
    prompt: str = Body(..., description="The prompt to search for"),
    project: str = Body(..., description="The project to search"),
    mode: str = Body(..., description="Search mode: chat, commit, or super"),
    model: str = Body(..., description="The embedding model used"),
    match_strength: str = Body(..., description="The strength of the match"),
):
    """ Count tokens for a given prompt to be used in generating a response. """
    token_count = count_tokens(prompt)

    logger.info(f"Token count for prompt: {token_count}")

    return {
        "embedding_tokens": 0,
        "inference_tokens": token_count
    }
