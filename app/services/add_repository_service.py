import asyncio
from lib.vcs.repo_manager import add_repository
from lib.utils.utilities import url_to_folder_name
from lib.utils.enums import AddRepositoryRequest
from fastapi import HTTPException

async def process_add_repository(data: AddRepositoryRequest):
    # Normalize the project name
    data.project_name = url_to_folder_name(data.project_name)

    # Add the repository and retrieve the response
    response = await asyncio.to_thread(add_repository, data)

    if "error" in response:
        raise HTTPException(status_code=400, detail=response["error"])

    return response
