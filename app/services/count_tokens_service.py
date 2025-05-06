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
    project_name = url_to_folder_name(data.project_name)
    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project_name)
    mock_new_commits_file_path = os.path.join(commits_logs_dir_path, "mock_new_commits.json")


    logger.critical("Starting token count processing for repository '%s'", project_name)

    # Read the mock_new_commits file
    mock_new_commits = await asyncio.to_thread(read_json_file, mock_new_commits_file_path)
    logger.debug("mock_new_commits content: %s", mock_new_commits)

    # Initialize token counters
    total_inference_tokens = 0
    total_embedding_tokens = 0

    # Iterate over each commit and count tokens
    for commit in mock_new_commits:
        for message in commit.get("message", []):
            tokens = count_tokens(message)
            total_inference_tokens += tokens
            total_embedding_tokens += 500  # Assuming max token between summary (500) and message (200).


    logger.info("Total Inference Tokens: %d", total_inference_tokens)
    logger.info("Total Embedding Tokens: %d", total_embedding_tokens)

    logger.critical("Completed token count processing for repository '%s'", project_name)

    # Call delete_store with the necessary parameters (if needed)
    # await asyncio.to_thread(
    #     delete_store,
    #     codehost_url=data.codehost_url,
    #     project_name=data.project_name,
    #     vcs_type=data.vcs_type,
    #     api_key=data.api_key,
    #     new_repo=True,
    # )

    return total_embedding_tokens, total_inference_tokens

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
    logger.debug("%s's git repo path: %s", project, git_project_path)

    commits_logs_dir_path = DataDir.COMMITS_LOGS.get_path(project)
    commits_logs_file_path = os.path.join(commits_logs_dir_path, "commits_logs.json")
    logger.debug("%s's commit logs file path: %s", project, commits_logs_file_path)

    commits_logs_json = await asyncio.to_thread(read_json_file, commits_logs_file_path)


    parser = GitCommitManager(
        commits_logs_json,
        project,
        llm_model_api_key=llm_model_api_key,
        llm_model_base_url=llm_model_base_url,
        embeddings_model_api_key=embeddings_model_api_key,
        llm_model=load_request.llm_model or "gpt-4o-mini",
        ignore_files=ignore_files,
        skip_summaries=True,
        head=head,
        use_mock_llm=load_request.use_mock_llm or False,
        llm_threads=load_request.llm_threads  # Pass the thread parameter
    )



    depth = 1000
    logger.critical("Starting commit processing and summarization for project '%s' (depth %d)", project, depth)
    await parser.add_commits_and_summaries_to_log(git_project_path, depth)
    logger.critical("Completed commit processing for project '%s'", project)

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
    logger.debug("New commits to process: %s", new_commits)

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
        logger.critical(
            "Token count limit exceeded: %d tokens, maximum allowed is %d",
            total_inference_tokens, max_token_count
        )
        raise HTTPException(
            status_code=400,
            detail=f"Operation would be {total_inference_tokens} input tokens, exceeded maximum usage of {max_token_count}."
        )

    logger.info(f"Total embedding tokens: {total_embedding_tokens}, Total inference tokens: {total_inference_tokens}")

    return total_embedding_tokens, total_inference_tokens
