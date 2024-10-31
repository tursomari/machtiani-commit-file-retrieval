import os
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from concurrent.futures import ProcessPoolExecutor
from lib.vcs.repo_manager import delete_store
from lib.utils.enums import DeleteStoreRequest  # Assuming DeleteStoreRequest is a Pydantic model

# Initialize the router and logger
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/delete-store/")
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
