import os
from fastapi import Query, APIRouter, HTTPException, status
from typing import List
import logging
from app.services.get_file_summary_service import get_file_summaries  # Import the service
from app.models.responses import FileSummaryResponse, ErrorResponse  # Import the response models

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/get-file-summary/", response_model=List[FileSummaryResponse], responses={status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse}})
async def get_file_summary(
    file_paths: List[str] = Query(..., description="List of file paths to retrieve summaries for"),
    project_name: str = Query(..., description="The name of the project")
):
    """ Retrieve summaries for specified file paths. """
    try:
        summaries = await get_file_summaries(file_paths, project_name)
        
        # Assuming summaries is a list of dictionaries, we can convert it to FileSummaryResponse
        file_summaries = [FileSummaryResponse(**summary) for summary in summaries]

        return file_summaries

    except ValueError as e:
        # Handle specific value errors (e.g., invalid file paths)
        logger.error(f"ValueError: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        # Handle other unexpected errors
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")
