import os
import asyncio
import logging
from fastapi import APIRouter
from concurrent.futures import ProcessPoolExecutor
from lib.vcs.repo_manager import (
    add_repository,
    delete_store,
)
from lib.utils.utilities import url_to_folder_name
from lib.utils.enums import AddRepositoryRequest
from app.routes.count_tokens_load import count_tokens_load

# Setting up the router and logger
router = APIRouter()
executor = ProcessPoolExecutor(max_workers=10)
logger = logging.getLogger(__name__)

@router.post("/add-repository/token-count")
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
