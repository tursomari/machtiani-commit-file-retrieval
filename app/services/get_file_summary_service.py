import os
import logging
import asyncio
from typing import Dict, List, Optional
from app.utils import DataDir
from lib.utils.utilities import read_json_file, url_to_folder_name

logger = logging.getLogger(__name__)

async def fetch_summary_from_commit(file_path: str, commits_log: List[Dict]) -> Optional[Dict[str, str]]:
    # Iterate over each commit in the commit log
    for commit in commits_log:
        files = commit.get('files', [])
        summaries = commit.get('summaries', [])

        # Check if file_path is in the list of files
        if file_path in files:
            # Find the index of the file_path
            index = files.index(file_path)
            # Get the summary at the same index
            summary = summaries[index] if index < len(summaries) else None

            if summary:
                return {"file_path": file_path, "summary": summary}
            else:
                logger.warning(f"No summary found for file path: {file_path} in commit {commit.get('oid')}")
    logger.warning(f"No summary found for file path: {file_path}")
    return None

async def get_file_summaries(file_paths: List[str], project_name: str) -> List[Dict[str, str]]:
    # Require project name
    if not project_name:
        logger.error("Project name is required to retrieve file summaries.")
        return []
    # Prepare path to embeddings JSON
    embeddings_dir = DataDir.CONTENT_EMBEDDINGS.get_path(project_name)
    embeddings_file = os.path.join(embeddings_dir, "files_embeddings.json")
    try:
        data = await asyncio.to_thread(read_json_file, embeddings_file)
    except Exception as e:
        # In case read_json_file raises, though it normally returns {} on missing file
        logger.error(f"Error loading file embeddings from '{embeddings_file}': {e}")
        return []
    summaries: List[Dict[str, str]] = []
    for file_path in file_paths:
        entry = data.get(file_path)
        if isinstance(entry, dict) and 'summary' in entry:
            summaries.append({'file_path': file_path, 'summary': entry['summary']})
        else:
            logger.warning(f"No summary found for file path: {file_path}")
    return summaries
