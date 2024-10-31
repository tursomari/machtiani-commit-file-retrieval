import asyncio
import logging
from fastapi import APIRouter, HTTPException
from app.utils import DataDir
from lib.utils.utilities import url_to_folder_name, get_lock_file_path
from lib.utils.enums import VCSType, FetchAndCheckoutBranchRequest
from lib.vcs.repo_manager import fetch_and_checkout_branch
from app.services.count_tokens_service import count_tokens_load

router = APIRouter()
logger = logging.getLogger(__name__)

async def process_fetch_and_checkout(data: FetchAndCheckoutBranchRequest):
    codehost_url = data.codehost_url
    project_name = url_to_folder_name(data.project_name)
    branch_name = data.branch_name
    api_key = data.api_key
    openai_api_key = data.openai_api_key

    if data.vcs_type != VCSType.git:
        raise HTTPException(status_code=400, detail=f"VCS type '{data.vcs_type}' is not supported.")

    destination_path = DataDir.REPO.get_path(project_name)

    await asyncio.to_thread(fetch_and_checkout_branch, codehost_url, destination_path, project_name, branch_name, api_key)

    openai_api_key_value = openai_api_key.get_secret_value() if openai_api_key else None
    load_request = {"openai_api_key": openai_api_key_value, "project_name": project_name, "ignore_files": data.ignore_files}

    # Count tokens
    token_count = await count_tokens_load(load_request)

    return token_count  # Return the token count directly
