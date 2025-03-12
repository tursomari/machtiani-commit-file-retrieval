import asyncio
from lib.vcs.repo_manager import delete_store

async def delete_store_service(data):
    result = await asyncio.to_thread(
        delete_store,
        codehost_url=data.codehost_url,
        project_name=data.project_name,
        vcs_type=data.vcs_type,
        api_key=data.api_key,
    )

    return result # of type DeleteStoreResponse
