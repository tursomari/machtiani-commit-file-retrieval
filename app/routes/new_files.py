
from fastapi import APIRouter, HTTPException, Body
from pydantic import HttpUrl
from typing import List, Dict
import logging

from app.services.new_files_service import new_files_service

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/new-files/")
async def new_files(
    project: str = Body(..., description="Project name"),
    instructions: str = Body(..., description="Instructions for file creation"),
    llm_model_api_key: str = Body(..., description="LLM API key"),
    llm_model_base_url: HttpUrl = Body(..., description="LLM API base URL"),
    model: str = Body("gpt-4", description="LLM model name"),
    ignore_files: List[str] = Body(default_factory=list, description="Ignore files list (optional)")
) -> Dict:
    """
    Call new_files_service to identify and create new files based on instructions.
    """
    logger.info("Received request to create new files")
    logger.debug(f"Project: {project}, Instructions: {instructions[:100]}...")  # Log the first 100 characters of instructions

    if not instructions.strip():
        logger.warning("Empty instructions provided")
        raise HTTPException(status_code=400, detail="Instructions cannot be empty.")

    try:
        logger.info("Calling new_files_service")
        new_content, new_file_paths, errors = await new_files_service(
            project_name=project,
            instructions=instructions,
            llm_model_api_key=llm_model_api_key,
            llm_model_base_url=llm_model_base_url,
            model_name=model,
            ignore_files=ignore_files
        )

        logger.info(f"Identified {len(new_file_paths)} new files to create")
        if errors:
            logger.warning(f"Errors encountered: {errors}")

    except Exception as e:
        logger.error(f"File creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File creation failed: {e}")

    logger.info("Returning response")
    return {
        "new_content": new_content,
        "new_file_paths": new_file_paths,
        "errors": errors
    }
