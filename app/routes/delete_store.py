import os
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.delete_store_service import delete_store_service  # Import the service
from lib.utils.enums import DeleteStoreRequest  # Assuming DeleteStoreRequest is a Pydantic model

# Initialize the router and logger
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/delete-store/")
async def handle_delete_store(
    data: DeleteStoreRequest,
):
    try:
        return await delete_store_service(data)  # Use the service to delete the store
    except ValueError as e:
        logger.error(f"Failed to delete store '{data.project_name}': {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete store '{data.project_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))
