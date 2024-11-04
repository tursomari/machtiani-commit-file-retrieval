import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import SecretStr
from app.services.add_repository_service import process_add_repository
from app.models.responses import AddRepositoryResponse, ErrorResponse
from app.models.requests import AddRepositoryRequest
from lib.utils.enums import AddRepositoryRequest
from app.routes.load import handle_load

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/add-repository/", response_model=AddRepositoryResponse, responses={500: {"model": ErrorResponse}})
@router.post("/add-repository", response_model=AddRepositoryResponse, responses={500: {"model": ErrorResponse}})
async def handle_add_repository(data: AddRepositoryRequest, background_tasks: BackgroundTasks):
    try:
        response = await process_add_repository(data)

        load_request = {
            "openai_api_key": data.openai_api_key.get_secret_value() if data.openai_api_key else None,
            "project_name": data.project_name,
            "ignore_files": data.ignore_files
        }

        background_tasks.add_task(handle_load, load_request)

        return AddRepositoryResponse(
            message=response.get("message"),
            full_path=response.get("full_path"),
            api_key_provided=response.get("api_key_provided"),
            openai_api_key_provided=response.get("openai_api_key_provided")
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")
