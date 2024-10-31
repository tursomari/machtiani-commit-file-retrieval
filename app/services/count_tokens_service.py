import asyncio
from lib.vcs.repo_manager import add_repository, delete_store, fetch_and_checkout_branch
from lib.utils.utilities import url_to_folder_name
from lib.utils.enums import VCSType, AddRepositoryRequest, FetchAndCheckoutBranchRequest
from app.utils import DataDir
from app.routes.count_tokens_load import count_tokens_load
from fastapi import HTTPException

async def process_repository_and_count_tokens(data: AddRepositoryRequest):
    # Normalize the project name
    data.project_name = url_to_folder_name(data.project_name)

    # Add the repository
    result_add_repo = await asyncio.to_thread(add_repository, data)

    # Extract the OpenAI API key value
    openai_api_key_value = data.openai_api_key.get_secret_value() if data.openai_api_key else None

    # Prepare the load request for counting tokens
    load_request = {
        "openai_api_key": openai_api_key_value,
        "project_name": data.project_name,
        "ignore_files": data.ignore_files
    }

    # Count tokens
    token_count = await count_tokens_load(load_request)

    # Call delete_store with the necessary parameters
    await asyncio.to_thread(
        delete_store,
        codehost_url=data.codehost_url,
        project_name=data.project_name,
        ignore_files=data.ignore_files,
        vcs_type=data.vcs_type,
        api_key=data.api_key,
        openai_api_key=data.openai_api_key,
    )

    return token_count

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
