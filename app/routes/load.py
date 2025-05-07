import logging
from fastapi import APIRouter, HTTPException, Body
from lib.utils.log_utils import reset_logs
from lib.utils.log_utils import LoggedError
from app.models.requests import LoadRequest  # Import LoadRequest model
from app.models.responses import LoadResponse, LoadErrorResponse
from app.services.load_service import load_project_data

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/load/", response_model=LoadResponse, responses={423: {"model": LoadErrorResponse}, 500: {"model": LoadErrorResponse}})
async def handle_load(load_request: LoadRequest):  # Use LoadRequest instead of dict
    # Reset logs for this project on each Load call
    try:
        reset_logs(load_request.project_name)
    except Exception as e:
        logger.error(f"Failed to reset logs for project {load_request.project_name}: {e}")
    try:
        await load_project_data(load_request)
        return {"status": True, "message": "Load operation completed successfully."}
    except RuntimeError as e:
        # Locked operation or similar, propagate as 423
        raise HTTPException(status_code=423, detail=str(e))
    except LoggedError as e:
        # Propagate logged errors with original message to client
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Unexpected errors, return generic message
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

