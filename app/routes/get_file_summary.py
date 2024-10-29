import os
from fastapi import Query, APIRouter
from app.utils import DataDir
from typing import List, Dict, Optional
import asyncio
from lib.utils.utilities import (
    url_to_folder_name,
    read_json_file,
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

async def fetch_summary(file_path: str, file_summaries: Dict[str, dict]) -> Optional[Dict[str, str]]:
    summary = file_summaries.get(file_path)
    if summary is None:
        logger.warning(f"No summary found for file path: {file_path}")
        return None
    return {"file_path": file_path, "summary": summary["summary"]}

@router.get("/get-file-summary/")
async def get_file_summary(
    file_paths: List[str] = Query(..., description="List of file paths to retrieve summaries for"),
    project_name: str = Query(..., description="The name of the project")
):
    """ Retrieve summaries for specified file paths. """
    project_name = url_to_folder_name(project_name)
    file_summaries_file_path = os.path.join(DataDir.CONTENT_EMBEDDINGS.get_path(project_name), "files_embeddings.json")

    # Read the existing file summaries asynchronously
    file_summaries = await asyncio.to_thread(read_json_file, file_summaries_file_path)

    # Create a list of async tasks for fetching summaries
    tasks = [fetch_summary(file_path, file_summaries) for file_path in file_paths]
    results = await asyncio.gather(*tasks)

    # Prepare the output, filtering out None results
    summaries = [result for result in results if result is not None]

    if len(summaries) < len(file_paths):
        missing_files = [file_path for file_path, result in zip(file_paths, results) if result is None]
        for file_path in missing_files:
            logger.warning(f"No summary found for file path: {file_path}")

    return summaries

