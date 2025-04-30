import os
import asyncio
from typing import List
from pydantic import HttpUrl
from fastapi import APIRouter, HTTPException, Body
import logging
from lib.utils.utilities import read_json_file, url_to_folder_name
from lib.utils.enums import SearchMode, MatchStrength, EmbeddingModel, FilePathEntry
from app.models.responses import FileSearchResponse
from app.services.generate_response_service import infer_file_service  # Import the service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/infer-file/", response_model=List[FileSearchResponse])
async def infer_file(
    prompt: str = Body(..., description="The prompt to search for"),
    project: str = Body(..., description="The project to search"),
    mode: SearchMode = Body(..., description="Search mode: chat, pure-chat, or default"),
    model: str = Body(..., description="The model used used for inference, actually"),
    match_strength: MatchStrength = Body(..., description="The strength of the match"),
    llm_model_base_url: HttpUrl = Body(..., description="OpenAI API key"),
    llm_model_api_key: str = Body(..., description="OpenAI API key"),
    embeddings_model_api_key: str = Body(..., description="OpenAI API key for Embeddings"),
    ignore_files: List[str] = Body(..., description="List of file to ignore"),
    head: str = Body(..., description="The head commit to checkout"),
) -> List[FileSearchResponse]:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        logger.info("infer_file_service call: {head}")
        responses = await infer_file_service(
            prompt,
            project,
            mode,
            model,
            match_strength,
            llm_model_api_key,
            llm_model_base_url,
            embeddings_model_api_key,
            ignore_files,
            head
        )
    except Exception as e:
        logger.error(f"Error during inferencing: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while inferring file.")

    return responses
