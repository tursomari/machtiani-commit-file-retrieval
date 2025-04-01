import os
import asyncio
import logging
from lib.vcs.repo_manager import delete_store
from lib.utils.utilities import url_to_folder_name, read_json_file
from lib.utils.enums import VCSType
from app.utils import count_tokens
from fastapi import APIRouter, HTTPException
from app.utils import DataDir
from fastapi import HTTPException
from lib.utils.utilities import read_json_file
from app.models.requests import CountTokenRequest, LoadRequest


router = APIRouter()
logger = logging.getLogger(__name__)


async def process_repository_and_count_tokens(data: CountTokenRequest):
    # Normalize the project name
    #data.project_name = url_to_folder_name(data.project_name)
    project_name = url_to_folder_name(data.project_name)
    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project_name)
    commits_embeddings_dir_path = DataDir.COMMITS_EMBEDDINGS.get_path(project_name)

    mock_commits_logs_file_path = os.path.join(commits_logs_dir_path, "mock_commits_logs.json")
    mock_new_commits_file_path = os.path.join(commits_logs_dir_path, "mock_new_commits.json")
    mock_commits_embeddings_file_path = os.path.join(commits_embeddings_dir_path, "mock_commits_embeddings.json")

    #mock_commits_logs = await asyncio.to_thread(read_json_file, mock_commits_logs_file_path)
    #mock_new_commits = await asyncio.to_thread(read_json_file, mock_new_commits_file_path)
    #mock_commits_embeddings = await asyncio.to_thread(read_json_file, mock_commits_embeddings_file_path)

    #return mock_commits_logs, mock_new_commits, mock_commits_embeddings


    #embedding_tokens, inference_token = await count_tokens_load(load_request)  # Pass the dictionary representation
    embedding_tokens, inference_token = (1000, 1000)

    # Call delete_store with the necessary parameters
    #await asyncio.to_thread(
    #    delete_store,
    #    codehost_url=data.codehost_url,
    #    project_name=data.project_name,
    #    vcs_type=data.vcs_type,
    #    api_key=data.api_key,
    #    new_repo=True,
    #)

    return embedding_tokens, inference_token

async def count_tokens_load(load_request: LoadRequest):
    llm_model_api_key = load_request.llm_model_api_key
    llm_model_base_url = load_request.llm_model_base_url
    embeddings_model_api_key = load_request.embeddings_model_api_key
    project = load_request.project_name
    ignore_files = load_request.ignore_files or []
    head = load_request.head

    projects = DataDir.list_projects()

    all_new_commits = []

    git_project_path = os.path.join(DataDir.REPO.get_path(project), "git")
    logger.info(f"{project}'s git repo path: {git_project_path}")

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    logger.info(f"{project}'s commit logs file path: {commits_logs_file_path}")

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)
    parser = GitCommitManager(
        commits_logs_json,
        project,
        llm_model_api_key=llm_model_api_key,
        llm_model_base_url=llm_model_base_url,
        embeddings_model_api_key=embeddings_model_api_key,
        llm_model="gpt-4o-mini",
        ignore_files=ignore_files,
        skip_summaries=True,
        head=head,
        use_mock_llm = load_request.use_mock_llm or False
    )


    depth = 1000
    await parser.add_commits_and_summaries_to_log(git_project_path, depth)

    new_commits_string = parser.new_commits

    commits_embeddings_file_path = os.path.join(DataDir.COMMITS_EMBEDDINGS.get_path(project), "commits_embeddings.json")
    logger.info(f"{project}'s embedded commit logs file path: {commits_embeddings_file_path}")

    commits_logs_json = parser.commits_logs
    existing_commits_embeddings_json = await asyncio.to_thread(read_json_file, commits_embeddings_file_path)
    generator = CommitEmbeddingGenerator(
        commits_logs_json,
        embeddings_model_api_key,
        embeddings_model_base_url=llm_model_base_url,  # Pass the llm_model_base_url here
        existing_commits_embeddings=existing_commits_embeddings_json,
        use_mock_llm = load_request.use_mock_llm or False
    )

    new_commits = await asyncio.to_thread(generator._filter_new_commits)
    logger.info(f"new commits:\n{new_commits}")

    # Ensure you have the correct new commits to count tokens
    if not new_commits:
        logger.info("No new commits to count tokens for.")
        return 0, 0

    # Since 'message' is now a list of messages, join them into a single string for token counting
    new_commits_messages = ['\n'.join(commit['message']) for commit in new_commits]
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
            detail=f"Operation would be {total_inference_tokens} input tokens, exceeded maximum usage of {max_token_count}."
        )

    logger.info(f"Total embedding tokens: {total_embedding_tokens}, Total inference tokens: {total_inference_tokens}")

    return total_embedding_tokens, total_inference_tokens
