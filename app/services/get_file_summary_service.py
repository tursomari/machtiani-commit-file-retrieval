import os
import logging
import asyncio
from typing import Dict, List, Optional
from app.utils import DataDir
from lib.utils.utilities import read_json_file, url_to_folder_name
from lib.vcs.git_commit_manager import GitCommitManager

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
    project = url_to_folder_name(project_name)
    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")

    # Read the commit logs asynchronously
    commits_log = await asyncio.to_thread(read_json_file, commits_logs_file_path)

    # Create a list of async tasks for fetching summaries from the commit log
    tasks = [fetch_summary_from_commit(file_path, commits_log) for file_path in file_paths]
    results = await asyncio.gather(*tasks)

    # Prepare the output, filtering out None results
    summaries = [result for result in results if result is not None]

    if len(summaries) < len(file_paths):
        missing_files = [file_path for file_path, result in zip(file_paths, results) if result is None]
        for file_path in missing_files:
            logger.warning(f"No summary found for file path: {file_path}")

    return summaries
