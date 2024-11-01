import os
import logging
import asyncio
from typing import Dict, List, Optional
from app.utils import DataDir
from lib.utils.utilities import read_json_file, url_to_folder_name

logger = logging.getLogger(__name__)

async def fetch_summary(file_path: str, file_summaries: Dict[str, dict]) -> Optional[Dict[str, str]]:
    summary = file_summaries.get(file_path)
    if summary is None:
        logger.warning(f"No summary found for file path: {file_path}")
        return None
    return {"file_path": file_path, "summary": summary["summary"]}

async def get_file_summaries(file_paths: List[str], project_name: str) -> List[Dict[str, str]]:
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
