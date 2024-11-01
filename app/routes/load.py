import os
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Body
from app.services.load_service import load_project_data

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/load/")
async def handle_load(
    load_request: dict = Body(..., description="Request body containing the OpenAI API key."),
):
    try:
        await load_project_data(load_request)
        return {"message": "Load operation completed successfully."}
    except RuntimeError as e:
        raise HTTPException(status_code=423, detail=str(e))
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
