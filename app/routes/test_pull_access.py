from fastapi import APIRouter, Query, HTTPException
from app.services.test_pull_access_service import test_pull_access_service  # Import the service
from pydantic import SecretStr
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/test-pull-access/")
async def test_pull_access(
    project_name: str = Query(..., description="The name of the project"),
    codehost_api_key: SecretStr = Query(..., description="Code host API key for authentication"),
    codehost_url: str = Query(..., description="Code host URL for the repository"),
):
    """ Test pull access by checking if the user can pull from the repository. """
    try:
        # Call the service function instead of the logic directly here
        return await test_pull_access_service(project_name, codehost_api_key, codehost_url)
    except Exception as e:
        logger.error(f"Failed to check pull access for '{project_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")
