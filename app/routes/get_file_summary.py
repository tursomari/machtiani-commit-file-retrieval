import os
from fastapi import Query, APIRouter
from typing import List, Dict
import asyncio
import logging
from app.utils import DataDir
from app.services.get_file_summary_service import get_file_summaries  # Import the service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/get-file-summary/")
async def get_file_summary(
    file_paths: List[str] = Query(..., description="List of file paths to retrieve summaries for"),
    project_name: str = Query(..., description="The name of the project")
):
    """ Retrieve summaries for specified file paths. """
    summaries = await get_file_summaries(file_paths, project_name)  # Call the service function

    return summaries
