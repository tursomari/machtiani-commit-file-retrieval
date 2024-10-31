import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import SecretStr
from app.services.add_repository_service import process_add_repository
from lib.utils.enums import AddRepositoryRequest
from app.routes.load import handle_load

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/add-repository")
@router.post("/add-repository/")
async def handle_add_repository(data: AddRepositoryRequest, background_tasks: BackgroundTasks):
    try:
        response = await process_add_repository(data)

        # Prepare the load request
        load_request = {
            "openai_api_key": data.openai_api_key.get_secret_value() if data.openai_api_key else None,
            "project_name": data.project_name,
            "ignore_files": data.ignore_files
        }

        # Add the load function as a background task
        background_tasks.add_task(handle_load, load_request)

        return {
            "message": response.get("message"),
            "full_path": response.get("full_path"),
            "api_key_provided": response.get("api_key_provided"),
            "openai_api_key_provided": response.get("openai_api_key_provided")
        }

    except HTTPException as e:
        raise e  # re-raise the HTTP exception
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")
