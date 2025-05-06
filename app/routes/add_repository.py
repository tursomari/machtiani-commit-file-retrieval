from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.services.add_repository_service import process_add_repository
from app.models.responses import AddRepositoryResponse, ErrorResponse
from app.models.requests import AddRepositoryRequest
from lib.utils.enums import VCSType  # Ensure you import VCSType for VS type checks
from app.routes.load import handle_load
from app.models.requests import LoadRequest  # Import the LoadRequest model
from lib.vcs.git_content_manager import GitContentManager
from app.utils import DataDir
from git import Repo  # Ensure you have the GitPython library imported
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/add-repository/", response_model=AddRepositoryResponse, responses={500: {"model": ErrorResponse}})
async def handle_add_repository(data: AddRepositoryRequest, background_tasks: BackgroundTasks):
    try:
        response = await process_add_repository(data)

        logger.info(f"Calling add-repository route with use_mock_llm: {data.use_mock_llm}")

        load_request = LoadRequest(
            llm_model = None,
            embeddings_model=None,
            embeddings_model_api_key=data.llm_model_api_key.get_secret_value() if data.llm_model_api_key and data.llm_model_api_key.get_secret_value().strip() else None,
            llm_model_api_key=data.llm_model_api_key.get_secret_value() if data.llm_model_api_key and data.llm_model_api_key.get_secret_value().strip() else None,
            llm_model_base_url=data.llm_model_base_url,
            project_name=data.project_name,
            ignore_files=data.ignore_files,
            head=data.head,
            use_mock_llm=data.use_mock_llm or False,
            amplification_level=data.amplification_level,
            depth_level=data.depth_level,
            llm_threads=data.llm_threads  # Add thread parameter
        )

        # Add the background task to handle loading
        background_tasks.add_task(handle_load, load_request)

        # Load above already results in commit
        # Add a task to commit the embedding file after handle_load is done
        #background_tasks.add_task(commit_embedding_file, data.project_name)

        return AddRepositoryResponse(
            message=response.get("message"),
            full_path=response.get("full_path"),
            api_key_provided=response.get("api_key_provided"),
            llm_model_api_key_provided=response.get("llm_model_api_key_provided")
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")
