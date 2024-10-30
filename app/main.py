import os
from fastapi import FastAPI, Query, HTTPException, Body, BackgroundTasks
from pydantic import ValidationError, SecretStr, HttpUrl
import asyncio
from concurrent.futures import ProcessPoolExecutor
import logging
from lib.vcs.repo_manager import (
    clone_repository,
    add_repository,
    delete_repository,
    fetch_and_checkout_branch,
    get_repo_info_async,
    delete_store,
    check_pull_access,
    check_push_access,
)
from lib.vcs.git_commit_parser import GitCommitParser
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.indexer.file_summary_indexer import FileSummaryEmbeddingGenerator
from lib.search.commit_embedding_matcher import CommitEmbeddingMatcher
from lib.search.file_embedding_matcher import FileEmbeddingMatcher
from lib.utils.utilities import (
    read_json_file,
    write_json_file,
    url_to_folder_name,
    get_lock_file_path,
    is_locked,
    acquire_lock,
    release_lock
)
from app.utils import DataDir, retrieve_file_contents, count_tokens
from typing import Optional, List, Dict
from lib.utils.enums import (
    SearchMode,
    MatchStrength,
    EmbeddingModel,
    FilePathEntry,
    FileSearchResponse,
    FileContentResponse,
    VCSType,
    AddRepositoryRequest,
    FetchAndCheckoutBranchRequest,
    DeleteStoreRequest
)
from app.routes import (
    test_pull_access,
    get_project_info,
    check_repo_lock,
    get_file_summary,
    load,
    add_repository as route_add_repository,
    fetch_and_checkout,
    infer_file,
    retrieve_file_contents,
)

from app.routes.load import handle_load

# Use the logger instead of print
logger = logging.getLogger("uvicorn")
logger.info("Application is starting up...")

app = FastAPI()
executor = ProcessPoolExecutor(max_workers=10)

app.include_router(test_pull_access.router)
app.include_router(check_repo_lock.router)
app.include_router(get_file_summary.router)
app.include_router(load.router)
app.include_router(route_add_repository.router)
app.include_router(fetch_and_checkout.router)
app.include_router(infer_file.router)
app.include_router(retrieve_file_contents.router)

@app.get("/file-paths/", response_model=FileSearchResponse)
async def get_file_paths(
    prompt: str = Query(..., description="The prompt to search for"),
    mode: SearchMode = Query(..., description="Search mode: pure-chat, commit, or super"),
    model: EmbeddingModel = Query(..., description="The embedding model used")
) -> FileSearchResponse:
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    mock_file_paths = [
        FilePathEntry(path="/path/to/file1.txt"),
        FilePathEntry(path="/path/to/file2.txt"),
        FilePathEntry(path="/path/to/file3.txt")
    ]

    return FileSearchResponse(
        embedding_model=model,
        mode=mode,
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/load/token-count")
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

@app.post("/add-repository/token-count")
async def count_tokens_add_repository(
    data: AddRepositoryRequest,
):
    openai_api_key = data.openai_api_key

    # Normalize the project name
    data.project_name = url_to_folder_name(data.project_name)

    # Add the repository
    result_add_repo = await asyncio.to_thread(add_repository, data)

    # Extract the OpenAI API key value
    openai_api_key_value = openai_api_key.get_secret_value() if openai_api_key else None

    # Prepare the load request for counting tokens
    load_request = {
        "openai_api_key": openai_api_key_value,
        "project_name": data.project_name,
        "ignore_files": data.ignore_files
    }

    # Count tokens
    token_count = await count_tokens_load(load_request)
    logger.info(f"Token count: {token_count}")

    # Call delete_store with the necessary parameters
    # Correctly call the synchronous function within asyncio.to_thread
    await asyncio.to_thread(
        delete_store,
        codehost_url=data.codehost_url,
        project_name=data.project_name,
        ignore_files=data.ignore_files,
        vcs_type=data.vcs_type,
        api_key=data.api_key,
        openai_api_key=openai_api_key,
    )

    # count_tokens_load `return {"token_count": token_count}` already.
    return token_count

@app.post("/fetch-and-checkout/token-count")
async def count_tokens_fetch_and_checkout(
    data: FetchAndCheckoutBranchRequest,
):
    codehost_url = data.codehost_url
    project_name = url_to_folder_name(data.project_name)
    branch_name = data.branch_name
    api_key = data.api_key
    openai_api_key = data.openai_api_key

    if data.vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{data.vcs_type}' is not supported.")

    destination_path = DataDir.REPO.get_path(project_name)

    logger.info(f"Calling fetching and checkout api_key {api_key}")
    await asyncio.to_thread(fetch_and_checkout_branch, codehost_url, destination_path, project_name, branch_name, api_key)

    openai_api_key = openai_api_key.get_secret_value() if openai_api_key else None
    load_request = {"openai_api_key": openai_api_key, "project_name": project_name, "ignore_files": data.ignore_files}
    token_count = await count_tokens_load(load_request)  # Await async method


    # count_tokens_load `return {"token_count": token_count}` already.
    return token_count

@app.post("/generate-response/token-count")
async def count_tokens_generate_response(
    prompt: str = Body(..., description="The prompt to search for"),
    project: str = Body(..., description="The project to search"),
    mode: str = Body(..., description="Search mode: chat, commit, or super"),
    model: str = Body(..., description="The embedding model used"),
    match_strength: str = Body(..., description="The strength of the match"),
):
    """ Count tokens for a given prompt to be used in generating a response. """
    token_count = count_tokens(prompt)

    logger.info(f"Token count for prompt: {token_count}")

    return {
        "embedding_tokens": 0,
        "inference_tokens": token_count
    }

@app.post("/delete-store/")
async def handle_delete_store(
    data: DeleteStoreRequest,
):
    try:
        await asyncio.to_thread(
            delete_store,
            codehost_url=data.codehost_url,
            project_name=data.project_name,
            ignore_files=data.ignore_files,
            vcs_type=data.vcs_type,
            api_key=data.api_key,
            openai_api_key=data.openai_api_key,
        )
        return {"message": f"Store '{data.project_name}' deleted successfully."}
    except ValueError as e:
        logger.error(f"Failed to delete store '{data.project_name}': {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete store '{data.project_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
def shutdown():
    """ Shutdown the executor when the application terminates. """
    logger.info("Shutting down the executor.")
    executor.shutdown(wait=True)
