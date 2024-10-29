import os
import asyncio
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import SecretStr
from lib.vcs.repo_manager import (
    add_repository,
)
from lib.utils.utilities import url_to_folder_name
from typing import Optional
from lib.utils.enums import (
    AddRepositoryRequest,
)
from fastapi import APIRouter, HTTPException
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/add-repository")
@router.post("/add-repository/")
async def handle_add_repository(data: AddRepositoryRequest, background_tasks: BackgroundTasks):
    # Normalize the project name
    data.project_name = url_to_folder_name(data.project_name)

    # Obtain the OpenAI API key value
    openai_api_key_value = data.openai_api_key.get_secret_value() if data.openai_api_key else None

    # Add the repository and retrieve the response
    response = await asyncio.to_thread(add_repository, data)

    # Prepare the load request
    load_request = {
        "openai_api_key": openai_api_key_value,
        "project_name": data.project_name,
        "ignore_files": data.ignore_files
    }

    # Add the load function as a background task
    background_tasks.add_task(load, load_request)

    return {
        "message": response["message"],
        "full_path": response["full_path"],
        "api_key_provided": response["api_key_provided"],
        "openai_api_key_provided": response["openai_api_key_provided"]
    }
