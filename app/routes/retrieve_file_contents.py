import os
import asyncio
import logging
from typing import List
from concurrent.futures import ProcessPoolExecutor
from fastapi import APIRouter, HTTPException, Body, FastAPI, APIRouter, HTTPException, Body
from pydantic import ValidationError
from lib.utils.utilities import url_to_folder_name
from app.utils import retrieve_file_contents
from lib.utils.enums import FilePathEntry, FileContentResponse
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

executor = ProcessPoolExecutor(max_workers=10)

@router.post("/retrieve-file-contents/", response_model=FileContentResponse)
async def get_file_contents(
    project_name: str = Body(..., description="The name of the project"),
    file_paths: List[FilePathEntry] = Body(..., description="A list of file paths to retrieve content for"),
    ignore_files: List[str] = Body(..., description="A list of files to ignore during retrieval")  # New parameter
) -> FileContentResponse:
    """ Retrieve the content of files specified by file paths within a given project. """
    project_name = url_to_folder_name(project_name)
    if not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    if not file_paths:
        raise HTTPException(status_code=400, detail="File paths cannot be empty.")

    logger.info(f"Received file paths: {file_paths}")

    retrieved_file_paths = []
    contents = {}

    try:
        for entry in file_paths:
            logger.info(f"Validating file path entry: {entry.path}")
            entry = FilePathEntry(**entry.dict())

        file_contents = await asyncio.to_thread(retrieve_file_contents, project_name, file_paths, ignore_files)  # Pass ignore_files

        for path in file_contents.keys():
            retrieved_file_paths.append(path)

    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e}")
    except Exception as e:
        logger.error(f"Error retrieving file contents: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving file contents.")

    return FileContentResponse(contents=file_contents, retrieved_file_paths=retrieved_file_paths)
    # Implementation goes here
