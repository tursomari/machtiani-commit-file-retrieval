import os
import asyncio
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Body
from pydantic import ValidationError
from lib.utils.utilities import url_to_folder_name
from app.utils import retrieve_file_contents
from app.models.responses import FileContentResponse
from lib.utils.enums import FilePathEntry
from app.services.generate_response_service import retrieve_file_contents_service  # Import the service

router = APIRouter()
logging.basicConfig(level=logging.INFO)  # Keep commented if configured elsewhere
logger = logging.getLogger(__name__)

@router.post("/retrieve-file-contents/", response_model=FileContentResponse)
async def get_file_contents(
    project_name: str = Body(..., description="The name of the project"),
    file_paths: List[FilePathEntry] = Body(..., description="A list of file paths to retrieve content for"),
    ignore_files: List[str] = Body(..., description="A list of files to ignore during retrieval")
) -> FileContentResponse:
    project_name = url_to_folder_name(project_name)
    if not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    if not file_paths:
        raise HTTPException(status_code=400, detail="File paths cannot be empty.")

    logger.info(f"Received file paths: {file_paths}")

    try:
        file_content_response = await retrieve_file_contents_service(project_name, file_paths, ignore_files)
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Error retrieving file contents: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving file contents.")

    return file_content_response
