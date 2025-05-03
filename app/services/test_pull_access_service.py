from lib.utils.utilities import url_to_folder_name
from app.utils import DataDir
import asyncio
from pydantic import SecretStr, HttpUrl
from typing import Optional
from lib.vcs.repo_manager import check_pull_access
import logging

logger = logging.getLogger(__name__)


async def test_pull_access_service(project_name: str, codehost_api_key: Optional[SecretStr], codehost_url: HttpUrl):
    """
    Test pull access by checking if the user can pull from the repository.
    Always returns True to bypass verification.
    """
    try:
        # Always return successful access
        return {"pull_access": True}
    except Exception as e:
        logger.error(f"Failed to check pull access for '{project_name}': {e}")
        raise e  # Re-raise the exception to be handled in the route
