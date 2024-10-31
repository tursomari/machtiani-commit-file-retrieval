import asyncio
import logging
from fastapi import APIRouter, HTTPException
from typing import Optional
from fastapi import APIRouter, HTTPException
from app.utils import DataDir
from lib.utils.utilities import url_to_folder_name, get_lock_file_path
from lib.vcs.repo_manager import fetch_and_checkout_branch
from app.routes.load import handle_load
from lib.utils.enums import (
    VCSType,
    FetchAndCheckoutBranchRequest,
)
from app.routes.count_tokens_load import count_tokens_load

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/fetch-and-checkout/token-count")
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
