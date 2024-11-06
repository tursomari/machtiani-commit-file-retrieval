import logging
from fastapi import APIRouter, HTTPException, Body
from app.models.requests import LoadRequest  # Import LoadRequest model
from app.models.responses import LoadResponse, LoadErrorResponse
from app.services.load_service import load_project_data

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/load/", response_model=LoadResponse, responses={423: {"model": LoadErrorResponse}, 500: {"model": LoadErrorResponse}})
async def handle_load(load_request: LoadRequest):  # Use LoadRequest instead of dict
    try:
        await load_project_data(load_request)  # Pass LoadRequest instance
        return {"status": True, "message": "Load operation completed successfully."}
    except RuntimeError as e:
        raise HTTPException(status_code=423, detail=str(e))
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
