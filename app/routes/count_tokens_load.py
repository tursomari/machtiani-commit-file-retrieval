import os
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Body
from concurrent.futures import ProcessPoolExecutor
from lib.vcs.git_commit_parser import GitCommitParser
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.utils.utilities import read_json_file, write_json_file
from app.utils import DataDir, count_tokens

# Initialize the router and logger
router = APIRouter()
executor = ProcessPoolExecutor(max_workers=10)
logger = logging.getLogger(__name__)

@router.post("/load/token-count")
async def count_tokens_load(
    load_request: dict = Body(..., description="Request body containing the OpenAI API key."),
):
    openai_api_key = load_request.get("openai_api_key")
    project = load_request.get("project_name")
    ignore_files = load_request.get("ignore_files")
    projects = DataDir.list_projects()

    all_new_commits = []

    git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
    logger.info(f"{project}'s git repo path: {git_project_path}")

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    parser = GitCommitParser(commits_logs_json, project)

    depth = 1000
    #await asyncio.to_thread(parser.add_commits_to_log, git_project_path, depth)
    await parser.add_commits_to_log(git_project_path, depth)

    new_commits_string = parser.new_commits

    await asyncio.to_thread(write_json_file, parser.commits, commits_logs_file_path)

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    existing_commits_embeddings_json = await asyncio.to_thread(read_json_file, commits_embeddings_file_path)
    generator = CommitEmbeddingGenerator(commits_logs_json, openai_api_key, existing_commits_embeddings_json)

    new_commits = await asyncio.to_thread(generator._filter_new_commits)
    logger.info(f"new commits:\n{new_commits}")

    # Ensure you have the correct new commits to count tokens
    if not new_commits:
        logger.info("No new commits to count tokens for.")
        return {"token_count": 0}

    new_commits_messages = [commit['message'] for commit in new_commits]
    new_commits_string = '\n'.join(new_commits_messages)  # Create a string from messages

    total_embedding_tokens = count_tokens(new_commits_string)

    # Retrieve files changed in new commits for additional token counting
    total_inference_tokens = 0
    inference_token_count = parser.count_tokens_in_files(new_commits, project, ignore_files)
    for file_path, count in inference_token_count.items():
        total_inference_tokens += count

    # Check if total token count exceeds the limit
    max_token_count = 3_000_000
    if total_inference_tokens > max_token_count:
        raise HTTPException(
            status_code=400,
            detail=f"Operation would be {total_inference_tokens} input token, exceeded maximum usage of {max_token_count}."
        )

    logger.info(f"Total embedding tokens: {total_embedding_tokens}, Total inference tokens: {total_inference_tokens}")

    return {
        "embedding_tokens": total_embedding_tokens,
        "inference_tokens": total_inference_tokens
    }
