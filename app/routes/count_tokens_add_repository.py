import logging
from fastapi import APIRouter, HTTPException
from app.services.count_tokens_service import process_repository_and_count_tokens
from lib.utils.utilities import url_to_folder_name, repo_exists
from app.models.responses import LoadResponse
from app.models.requests import AddRepositoryRequest

# Setting up the router and logger
router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/add-repository/token-count", response_model=LoadResponse)
async def count_tokens_add_repository(
    data: AddRepositoryRequest,
):

    logger.info(f"data.project_name: {data.project_name}")
    project_name = url_to_folder_name(data.project_name)
    if repo_exists(project_name):
        raise HTTPException(status_code=400, detail="The project already exists!")
    try:
        embedding_tokens, inference_tokens = await process_repository_and_count_tokens(data)
        return LoadResponse(
            embedding_tokens=embedding_tokens,
            inference_tokens=inference_tokens
        )
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
