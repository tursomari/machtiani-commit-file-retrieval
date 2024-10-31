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
    file_paths,
    count_tokens_load as route_count_tokens_load,
    count_tokens_add_repository,
    count_tokens_fetch_and_checkout,
)

from app.routes.load import handle_load
from app.routes.count_tokens_load import count_tokens_load

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
app.include_router(file_paths.router)
app.include_router(route_count_tokens_load.router)
app.include_router(count_tokens_add_repository.router)
app.include_router(count_tokens_fetch_and_checkout.router)

app.get("/health")
async def health_check():
    return {"status": "healthy"}

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
