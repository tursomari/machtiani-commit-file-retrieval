import os

from fastapi import FastAPI, Query, HTTPException, Body, BackgroundTasks
import subprocess
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
from lib.vcs.git_commit_manager import GitCommitManager
from lib.indexer.commit_indexer import CommitEmbeddingGenerator
from lib.indexer.file_summary_indexer import FileSummaryGenerator
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

from app.utils import DataDir, retrieve_file_contents, count_tokens, add_all_existing_repos_as_safe, delete_all_repo_lock_files

from typing import Optional, List, Dict
from lib.utils.enums import (
    SearchMode,
    MatchStrength,
    EmbeddingModel,
    FilePathEntry,
    VCSType,
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
    count_tokens_generate_response,
    delete_store,
    file_edit,
    new_files,
)

from app.routes.load import handle_load

# Get log level from environment variable, default to INFO
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

# Configure root logger
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI()


logger.critical("Application is starting up...")

# Add code to clone the model repository if not exists
models_dir = "/data/users/models/"
model_path = os.path.join(models_dir, "all-MiniLM-L6-v2")

# Ensure models directory exists
os.makedirs(models_dir, exist_ok=True)

# Check if model already exists
if not os.path.exists(model_path):
    logger.info(f"Cloning all-MiniLM-L6-v2 model into {model_path}")
    try:
        subprocess.run(
            ["git", "clone", "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2", model_path],
            check=True
        )
        logger.info("Model cloned successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone model: {str(e)}")
else:
    logger.info(f"Model already exists at {model_path}, skipping clone")

add_all_existing_repos_as_safe("/data/users/repositories/")
delete_all_repo_lock_files("/data/users/repositories/")

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
app.include_router(count_tokens_generate_response.router)
app.include_router(delete_store.router)
app.include_router(file_edit.router)
app.include_router(new_files.router)

app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.on_event("shutdown")
def shutdown():
    """ Shutdown the executor when the application terminates. """

    logger.critical("Shutting down the executor.")
    executor.shutdown(wait=True)
